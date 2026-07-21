//! MODE_CM2 — bit-level context-mixing codec (CM PoC, CUBR-0059 CM track).
//!
//! Phase 1 PoC: order-0..7 bit-context models + a match model + a word model,
//! combined by an integer logistic mixer (per-prev-byte weight set) and refined
//! by one APM/SSE stage, coded one bit at a time through the crate's existing
//! carryless range coder in binary mode (12-bit probabilities).
//!
//! Full-dickens: ratio 0.231880 (RT cmp=0), ~+0.96% vs the f64 entropy probe
//! (0.229671) — that gap is the integer/coder tax at 12-bit resolution; Phase-2
//! model additions (sparse/indirect, 2-layer mixer, SSE chain) dwarf it.
//!
//! ALL prediction/mixing/adaptation is integer (fixed-point stretch/squash
//! tables), so encode and decode — processing the identical byte sequence — build
//! byte-exact identical model state and the round-trip is `cmp=0` by construction.
//! f64 is used only to build the static tables once (deterministic).
//!
//! This is a competitive-min candidate: it need not beat PPM on every file, only
//! where CM is best (enwik8/webster). `min(len)` guards correctness.

use crate::codec::{RangeDecoder, RangeEncoder};
use crate::error::CubrimError;

const PBITS: u32 = 12;
const PSCALE: i32 = 1 << PBITS; // 4096
const ST_MAX: i32 = 2047; // stretch domain [-2047, 2047]

/// Integer logistic tables: `squash` maps a stretched value back to a 12-bit
/// probability; `stretch` is its inverse. Built once (f64 at init only).
struct Logistic {
    squash: Vec<u16>,  // index x+ST_MAX in [0, 2*ST_MAX]
    stretch: Vec<i16>, // index p in [0, PSCALE)
}
impl Logistic {
    fn new() -> Self {
        let mut squash = vec![0u16; (2 * ST_MAX + 1) as usize];
        for x in -ST_MAX..=ST_MAX {
            let v = PSCALE as f64 / (1.0 + (-(x as f64) / 256.0).exp());
            squash[(x + ST_MAX) as usize] = v.round().clamp(1.0, (PSCALE - 1) as f64) as u16;
        }
        let mut stretch = vec![0i16; PSCALE as usize];
        for p in 0..PSCALE {
            let pc = (p as f64).clamp(1.0, (PSCALE - 1) as f64);
            let v = 256.0 * (pc / (PSCALE as f64 - pc)).ln();
            stretch[p as usize] = v.round().clamp(-(ST_MAX as f64), ST_MAX as f64) as i16;
        }
        Self { squash, stretch }
    }
    #[inline]
    fn squash(&self, x: i32) -> i32 {
        let xc = x.clamp(-ST_MAX, ST_MAX);
        self.squash[(xc + ST_MAX) as usize] as i32
    }
    #[inline]
    fn stretch(&self, p: i32) -> i32 {
        self.stretch[p.clamp(1, PSCALE - 1) as usize] as i32
    }
}

/// One hashed bit-probability table with a count-adaptive rate (lpaq counter).
struct Ctr {
    t: Vec<u16>,
    c: Vec<u8>,
    mask: usize,
}
impl Ctr {
    fn new(bits: usize) -> Self {
        Self {
            t: vec![(PSCALE / 2) as u16; 1usize << bits],
            c: vec![0u8; 1usize << bits],
            mask: (1usize << bits) - 1,
        }
    }
    #[inline]
    fn p(&self, cx: usize) -> i32 {
        self.t[cx & self.mask] as i32
    }
    #[inline]
    fn upd(&mut self, cx: usize, y: i32) {
        let i = cx & self.mask;
        let cur = self.t[i] as i32;
        let cnt = self.c[i] as i32;
        let nv = cur + (y * PSCALE - cur) / (cnt + 2);
        self.t[i] = nv.clamp(1, PSCALE - 1) as u16;
        if cnt < 254 {
            self.c[i] = (cnt + 1) as u8;
        }
    }
}

const NORD: usize = 8; // orders 0..7
const MATCH_I: usize = NORD;
const WORD_I: usize = NORD + 1;
const NMODELS: usize = NORD + 2; // + match model + word model
const NIN: usize = NMODELS + 1; // + bias
const TBITS: usize = 22;
const MINLEN: usize = 6;
const WSHIFT_DEFAULT: i32 = 12; // mixer learning-rate shift (bigger = slower)
const MM_LEN_CAP: usize = 63;

const APM_N: usize = 24;
const APM_CTX: usize = 256;

/// The context-mixing model. Deterministic integer state; identical evolution on
/// encode and decode guarantees `cmp=0`.
struct CmModel {
    lg: Logistic,
    ord: Vec<Ctr>, // order-0..7
    wtab: Ctr,     // word model
    word_hash: u32,
    // match model
    match_hash: Vec<u32>,
    mm_mask: usize,
    match_ptr: usize,
    match_len: usize,
    mm_prob: Vec<u16>, // P(predicted bit correct) by length bucket
    // mixer: per prev-byte weight set, NIN i32 weights (16-frac fixed point)
    w: Vec<i32>,
    // apm
    apm: Vec<u16>,
    // per-byte scratch
    hk: [usize; NORD],
    pred_byte: i32,
    // per-bit scratch (predict -> update handoff)
    st: [i32; NIN],
    cxs: [usize; NORD],
    word_cx: usize,
    wset: usize,
    apm_base: usize,
    apm_idx: usize,
    mm_bucket: usize,
    mm_predbit: i32,
    mm_active: bool,
    pmix: i32,
    wshift: i32,
}

impl CmModel {
    fn new() -> Self {
        let mut apm = vec![0u16; APM_CTX * (APM_N + 1)];
        let lg = Logistic::new();
        for c in 0..APM_CTX {
            for i in 0..=APM_N {
                // identity init: knot i at input-stretch spread over [-ST_MAX,ST_MAX]
                let x = (i as i32) * (2 * ST_MAX) / (APM_N as i32) - ST_MAX;
                apm[c * (APM_N + 1) + i] = lg.squash(x) as u16;
            }
        }
        Self {
            lg,
            ord: (0..NORD).map(|_| Ctr::new(TBITS)).collect(),
            wtab: Ctr::new(TBITS),
            word_hash: 0,
            match_hash: vec![0u32; 1usize << TBITS],
            mm_mask: (1usize << TBITS) - 1,
            match_ptr: 0,
            match_len: 0,
            mm_prob: vec![(PSCALE * 3 / 4) as u16; MM_LEN_CAP + 1],
            w: vec![0i32; APM_CTX * NIN],
            apm,
            hk: [0; NORD],
            pred_byte: -1,
            st: [0; NIN],
            cxs: [0; NORD],
            word_cx: 0,
            wset: 0,
            apm_base: 0,
            apm_idx: 0,
            mm_bucket: 0,
            mm_predbit: 0,
            mm_active: false,
            pmix: 0,
            wshift: std::env::var("CM_WSHIFT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(WSHIFT_DEFAULT),
        }
    }

    /// Compute per-byte context state (order hashes, match prediction) from the
    /// bytes seen so far (`buf` = data[..t] on encode, decoded prefix on decode).
    fn start_byte(&mut self, buf: &[u8]) {
        let t = buf.len();
        for k in 0..NORD {
            self.hk[k] = if k == 0 {
                0
            } else if t >= k {
                let mut h = 0x9E37_79B1u32 ^ (k as u32);
                for j in 0..k {
                    h = h
                        .wrapping_mul(0x85EB_CA77)
                        .wrapping_add(buf[t - 1 - j] as u32);
                    h ^= h >> 15;
                }
                h as usize
            } else {
                0xDEAD ^ k
            };
        }
        self.pred_byte = if self.match_len > 0 && self.match_ptr < t {
            buf[self.match_ptr] as i32
        } else {
            -1
        };
        let prev = if t > 0 { buf[t - 1] as usize } else { 0 };
        self.wset = prev * NIN;
        self.apm_base = prev * (APM_N + 1);
    }

    /// Predict P(next bit == 1), 12-bit. Stashes scratch for [`update_bit`].
    fn predict_bit(&mut self, c0: usize, bit: u32) -> i32 {
        for k in 0..NORD {
            let cx = self.hk[k].wrapping_mul(0x2545_F491).wrapping_add(c0);
            self.cxs[k] = cx;
            self.st[k] = self.lg.stretch(self.ord[k].p(cx));
        }
        // match model
        if self.pred_byte >= 0 {
            let predbit = ((self.pred_byte >> (7 - bit)) & 1) as i32;
            let bucket = self.match_len.min(MM_LEN_CAP);
            let mm = self.mm_prob[bucket] as i32;
            let p = if predbit == 1 { mm } else { PSCALE - mm };
            self.st[MATCH_I] = self.lg.stretch(p);
            self.mm_active = true;
            self.mm_bucket = bucket;
            self.mm_predbit = predbit;
        } else {
            self.st[MATCH_I] = 0;
            self.mm_active = false;
        }
        // word model
        let wcx = (self.word_hash as usize)
            .wrapping_mul(0x2545_F491)
            .wrapping_add(c0);
        self.word_cx = wcx;
        self.st[WORD_I] = self.lg.stretch(self.wtab.p(wcx));
        self.st[NIN - 1] = 256; // bias input

        // mixer dot product (i64) -> squash
        let mut dot: i64 = 0;
        for i in 0..NIN {
            dot += self.w[self.wset + i] as i64 * self.st[i] as i64;
        }
        let x = (dot >> 16) as i32;
        let pmix = self.lg.squash(x);

        // APM/SSE refine
        let sx = self.lg.stretch(pmix);
        let pos = (sx + ST_MAX) * (APM_N as i32) / (2 * ST_MAX);
        let lo = pos.clamp(0, APM_N as i32 - 1) as usize;
        let frac = ((sx + ST_MAX) * (APM_N as i32) % (2 * ST_MAX)).max(0);
        let a0 = self.apm[self.apm_base + lo] as i32;
        let a1 = self.apm[self.apm_base + lo + 1] as i32;
        let papm = a0 + (a1 - a0) * frac / (2 * ST_MAX);
        self.apm_idx = self.apm_base + if frac * 2 >= 2 * ST_MAX { lo + 1 } else { lo };

        // blend ~0.8 mix / 0.2 apm (probe-tuned), clamp
        let pf = ((pmix * 13 + papm * 3) >> 4).clamp(1, PSCALE - 1);
        self.pmix = pmix; // handoff for the weight update
        pf
    }

    /// Update all models + mixer + APM with the observed bit `y`.
    fn update_bit(&mut self, c0: usize, _bit: u32, y: i32, pmix: i32) {
        // mixer weight update: err in prob domain
        let err = y * PSCALE - pmix;
        for i in 0..NIN {
            let dw = (self.st[i] * err) >> self.wshift;
            self.w[self.wset + i] += dw;
        }
        // order models
        for k in 0..NORD {
            self.ord[k].upd(self.cxs[k], y);
        }
        self.wtab.upd(self.word_cx, y);
        // match model probability (was the predicted bit correct?)
        if self.mm_active {
            let correct = (y == self.mm_predbit) as i32;
            let cur = self.mm_prob[self.mm_bucket] as i32;
            self.mm_prob[self.mm_bucket] =
                (cur + (correct * PSCALE - cur) / 32).clamp(1, PSCALE - 1) as u16;
        }
        // APM knot toward outcome
        let cur = self.apm[self.apm_idx] as i32;
        self.apm[self.apm_idx] = (cur + (y * PSCALE - cur) / 32).clamp(1, PSCALE - 1) as u16;
        let _ = c0;
    }

    /// Advance match state after a full byte `b` is known and appended to `buf`
    /// (so `buf.last() == b`, at index `t`).
    fn end_byte(&mut self, buf: &[u8]) {
        let t = buf.len() - 1;
        let b = buf[t] as i32;
        // word-model state: extend on alnum, reset otherwise.
        if buf[t].is_ascii_alphanumeric() {
            self.word_hash = self
                .word_hash
                .wrapping_mul(0x6F4A_7C13)
                .wrapping_add(buf[t] as u32 + 1);
        } else {
            self.word_hash = 0;
        }
        if self.match_len > 0 && self.pred_byte == b {
            self.match_ptr += 1;
            self.match_len += 1;
        } else {
            self.match_len = 0;
        }
        if buf.len() >= MINLEN {
            let mut h = 0xABCD_EF01u32;
            for j in 0..MINLEN {
                h = h.wrapping_mul(0x85EB_CA77).wrapping_add(buf[t - j] as u32);
                h ^= h >> 13;
            }
            let hi = (h as usize) & self.mm_mask;
            if self.match_len == 0 {
                let cand = self.match_hash[hi] as usize;
                if cand > 0 && cand < t {
                    self.match_ptr = cand + 1;
                    self.match_len = 1;
                }
            }
            self.match_hash[hi] = t as u32;
        }
    }
}

/// Encode `data` with the CM PoC. Wire: `[orig_len u64 BE][bit-range-coded]`.
pub(crate) fn cm2_encode(data: &[u8]) -> Vec<u8> {
    let mut out = (data.len() as u64).to_be_bytes().to_vec();
    let mut model = CmModel::new();
    let mut enc = RangeEncoder::new();
    let mut buf: Vec<u8> = Vec::with_capacity(data.len());
    for &byte in data {
        model.start_byte(&buf);
        let mut c0 = 1usize;
        for bit in 0..8u32 {
            let y = ((byte >> (7 - bit)) & 1) as i32;
            let pf = model.predict_bit(c0, bit);
            if y == 1 {
                enc.encode(0, pf as u32, PSCALE as u32);
            } else {
                enc.encode(pf as u32, (PSCALE - pf) as u32, PSCALE as u32);
            }
            let pmix = model.pmix;
            model.update_bit(c0, bit, y, pmix);
            c0 = (c0 << 1) | (y as usize);
        }
        buf.push(byte);
        model.end_byte(&buf);
    }
    out.extend_from_slice(&enc.finish());
    out
}

/// Decode a blob produced by [`cm2_encode`]. Fail-closed on a truncated header.
pub(crate) fn cm2_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 8 {
        return Err(CubrimError::Decode("MODE_CM2: header truncated".into()));
    }
    let orig_len = u64::from_be_bytes(blob[..8].try_into().unwrap());
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = CmModel::new();
    let mut dec = RangeDecoder::new(&blob[8..]);
    for _ in 0..orig_len {
        model.start_byte(&out);
        let mut c0 = 1usize;
        let mut byte = 0u8;
        for bit in 0..8u32 {
            let pf = model.predict_bit(c0, bit);
            let f = dec.get_freq(PSCALE as u32);
            let y = if f < pf as u32 {
                dec.decode(0, pf as u32, PSCALE as u32);
                1
            } else {
                dec.decode(pf as u32, (PSCALE - pf) as u32, PSCALE as u32);
                0
            };
            let pmix = model.pmix;
            model.update_bit(c0, bit, y, pmix);
            byte = (byte << 1) | (y as u8);
            c0 = (c0 << 1) | (y as usize);
        }
        out.push(byte);
        model.end_byte(&out);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rt(data: &[u8]) -> usize {
        let blob = cm2_encode(data);
        let out = cm2_decode(&blob).expect("cm2 decode");
        assert_eq!(out, data, "CM2 round-trip cmp!=0 for len {}", data.len());
        blob.len()
    }

    #[test]
    fn cm2_rt_edge() {
        rt(b"");
        rt(b"A");
        rt(&[0x42u8; 300]);
        rt(b"the quick brown fox jumps over the lazy dog. "
            .repeat(50)
            .as_slice());
    }

    #[test]
    fn cm2_rt_all_bytes() {
        let d: Vec<u8> = (0..6000).map(|i| (i % 256) as u8).collect();
        rt(&d);
    }

    #[test]
    fn cm2_rt_pseudo_random() {
        let mut x: u32 = 0x1234_5678;
        let d: Vec<u8> = (0..8000)
            .map(|_| {
                x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                (x >> 24) as u8
            })
            .collect();
        rt(&d);
    }

    #[test]
    fn cm2_text_compresses() {
        let d = b"she sells sea shells by the sea shore. ".repeat(300);
        let sz = rt(&d);
        assert!(
            sz < d.len() / 2,
            "CM2 did not compress text: {sz} vs {}",
            d.len()
        );
    }

    /// Charged self-probe vs the incumbent, RT cmp=0 enforced. Not run by default:
    ///   CUBR_PROBE_FILE=/path [CUBR_PROBE_LIMIT=N]
    ///     cargo test --release cm2::tests::self_probe -- --ignored --nocapture
    #[test]
    #[ignore]
    fn self_probe() {
        let path = std::env::var("CUBR_PROBE_FILE").expect("set CUBR_PROBE_FILE");
        let mut data = std::fs::read(&path).expect("read");
        if let Ok(l) = std::env::var("CUBR_PROBE_LIMIT") {
            data.truncate(l.parse().expect("limit"));
        }
        let n = data.len() as f64;
        let blob = cm2_encode(&data);
        let out = cm2_decode(&blob).expect("decode");
        let rt = out == data;
        println!(
            "CM2-PROBE file={} n={} cm2={} ratio={:.9} rt_cmp0={} \
             vs_champion_0.229919={:+.6}",
            path,
            data.len(),
            blob.len(),
            blob.len() as f64 / n,
            rt,
            blob.len() as f64 / n - 0.229919,
        );
        assert!(rt, "self-probe RT cmp!=0");
    }
}
