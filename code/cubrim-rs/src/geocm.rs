//! GeoCM image codec — port of cubr2-geocm v6 (frozen tag A-port-ref-image = b799a3c).
//! Detected native-axis (stride) neighbour contexts feeding an integer logistic mixer +
//! APM through a carryless binary range coder. Integer-deterministic, fail-closed
//! (self-describing CG2 container with an FNV-1a-64 checksum verified after decode),
//! competitive-min internally (RAW/O1/GEO/GEOA/MIX) and wrapped as a MODE_GEOCM candidate.
#![allow(clippy::needless_range_loop, dead_code)]

// ==================== rc (carryless binary range coder) ====================
// Carryless binary range coder (LZMA-style), integer-only, deterministic.
// Probabilities are 12-bit (0..4096), p = P(bit == 1).

pub const PBITS: u32 = 12;
pub const PMAX: u16 = 1 << PBITS; // 4096
pub const PINIT: u16 = PMAX / 2;
const TOP: u32 = 1 << 24;
const RATE: u32 = 5;

#[inline]
pub fn update(p: &mut u16, bit: u8) {
    if bit == 1 {
        *p += (PMAX - *p) >> RATE;
    } else {
        *p -= *p >> RATE;
    }
}

pub struct RcEnc {
    low: u64,
    range: u32,
    cache: u8,
    cache_size: u64,
    pub out: Vec<u8>,
}

impl RcEnc {
    pub fn new() -> Self {
        RcEnc { low: 0, range: u32::MAX, cache: 0, cache_size: 1, out: Vec::new() }
    }

    #[inline]
    fn shift_low(&mut self) {
        if self.low < 0xFF00_0000 || self.low > 0xFFFF_FFFF {
            let carry = (self.low >> 32) as u8;
            self.out.push(self.cache.wrapping_add(carry));
            for _ in 1..self.cache_size {
                self.out.push(0xFFu8.wrapping_add(carry));
            }
            self.cache = (self.low >> 24) as u8;
            self.cache_size = 0;
        }
        self.cache_size += 1;
        self.low = (self.low & 0x00FF_FFFF) << 8;
    }

    #[inline]
    pub fn encode_bit(&mut self, p: u16, bit: u8) {
        let bound = (self.range >> PBITS) * p as u32;
        if bit == 1 {
            self.range = bound;
        } else {
            self.low += bound as u64;
            self.range -= bound;
        }
        while self.range < TOP {
            self.range <<= 8;
            self.shift_low();
        }
    }

    pub fn finish(mut self) -> Vec<u8> {
        for _ in 0..5 {
            self.shift_low();
        }
        self.out
    }
}

pub struct RcDec<'a> {
    range: u32,
    code: u32,
    buf: &'a [u8],
    pos: usize,
}

impl<'a> RcDec<'a> {
    /// Fail-closed: returns None if the stream is too short to prime.
    pub fn new(buf: &'a [u8]) -> Option<Self> {
        if buf.len() < 5 {
            return None;
        }
        let mut d = RcDec { range: u32::MAX, code: 0, buf, pos: 1 };
        for _ in 0..4 {
            d.code = (d.code << 8) | d.next_byte();
        }
        Some(d)
    }

    #[inline]
    fn next_byte(&mut self) -> u32 {
        // Past-the-end reads pad with 0; corruption is caught by the
        // container checksum (fail-closed at the codec layer).
        let b = if self.pos < self.buf.len() { self.buf[self.pos] } else { 0 };
        self.pos += 1;
        b as u32
    }

    #[inline]
    pub fn decode_bit(&mut self, p: u16) -> u8 {
        let bound = (self.range >> PBITS) * p as u32;
        let bit;
        if self.code < bound {
            self.range = bound;
            bit = 1;
        } else {
            self.code -= bound;
            self.range -= bound;
            bit = 0;
        }
        while self.range < TOP {
            self.range <<= 8;
            self.code = (self.code << 8) | self.next_byte();
        }
        bit
    }
}

// ==================== mix (integer logistic mixer + APM) ====================
// Integer logistic mixing (lpaq/CM2 pattern).
//
// f64 is used ONLY to build the static stretch/squash tables once at startup
// (deterministic: same code -> same tables on every IEEE-754 platform, the
// same discipline as cubr-cm-poc cm2.rs). The per-bit predict/mix/update
// loop is integer-only, so encoder and decoder reconstruct identical state.


pub const STRETCH_MAX: i32 = 2047;

pub struct Tables {
    /// stretch[p] for p in 0..4096 -> [-STRETCH_MAX, STRETCH_MAX]
    pub stretch: Vec<i32>,
    /// squash[x + 2048] for x in [-2048, 2047] -> p in [1, 4095]
    pub squash: Vec<u16>,
}

impl Tables {
    pub fn new() -> Self {
        let mut squash = vec![0u16; 4096];
        for i in 0..4096usize {
            let x = (i as f64 - 2048.0) / 256.0;
            let p = 1.0 / (1.0 + (-x).exp());
            let v = (p * PMAX as f64) as i64;
            squash[i] = v.clamp(1, (PMAX - 1) as i64) as u16;
        }
        let mut stretch = vec![0i32; PMAX as usize];
        // invert squash monotonically
        let mut j = 0usize;
        for p in 0..PMAX as usize {
            while j < 4095 && (squash[j] as usize) < p {
                j += 1;
            }
            stretch[p] = j as i32 - 2048;
        }
        for p in 0..PMAX as usize {
            stretch[p] = stretch[p].clamp(-STRETCH_MAX, STRETCH_MAX);
        }
        Tables { stretch, squash }
    }

    #[inline]
    pub fn squash_i(&self, x: i32) -> u16 {
        let xi = x.clamp(-2048, 2047) + 2048;
        self.squash[xi as usize]
    }
}

/// One weight set per mixer context; NM model inputs.
pub struct Mixer {
    pub weights: Vec<i32>, // n_sets * nm, 16.16-ish fixed point
    nm: usize,
}

impl Mixer {
    pub fn new(n_sets: usize, nm: usize) -> Self {
        // start at ~0.3 weight each so the initial mix is a mild average
        Mixer { weights: vec![1 << 14; n_sets * nm], nm }
    }

    /// Returns (p12, dot) — caller passes stretched inputs st[0..nm].
    #[inline]
    pub fn predict(&self, tabs: &Tables, set: usize, st: &[i32]) -> (u16, i32) {
        let base = set * self.nm;
        let mut dot: i64 = 0;
        for (i, &s) in st.iter().enumerate() {
            dot += self.weights[base + i] as i64 * s as i64;
        }
        let x = (dot >> 16) as i32;
        (tabs.squash_i(x), x)
    }

    #[inline]
    pub fn update(&mut self, set: usize, st: &[i32], p: u16, bit: u8) {
        let err = ((bit as i32) << 12) - p as i32; // [-4095, 4095]
        let base = set * self.nm;
        for (i, &s) in st.iter().enumerate() {
            let w = &mut self.weights[base + i];
            *w += (s * err) >> 10;
            *w = (*w).clamp(-(1 << 20), 1 << 20);
        }
    }
}

/// Adaptive probability map (SSE): 33 interpolated buckets per context.
pub struct Apm {
    t: Vec<u16>,
    idx: usize,
    w: i32,
}

impl Apm {
    pub fn new(n_ctx: usize, tabs: &Tables) -> Self {
        let mut t = vec![0u16; n_ctx * 33];
        for c in 0..n_ctx {
            for j in 0..33 {
                t[c * 33 + j] = tabs.squash_i((j as i32 - 16) * 128);
            }
        }
        Apm { t, idx: 0, w: 0 }
    }

    #[inline]
    pub fn pp(&mut self, tabs: &Tables, p: u16, cx: usize) -> u16 {
        let st = tabs.stretch[p as usize] + 2048; // 0..4095
        let w = st & 127;
        let idx = cx * 33 + (st >> 7) as usize;
        self.idx = idx;
        self.w = w;
        (((self.t[idx] as i32) * (128 - w) + (self.t[idx + 1] as i32) * w) >> 7)
            .clamp(1, 4095) as u16
    }

    #[inline]
    pub fn update(&mut self, bit: u8) {
        let g = (bit as i32) << 12;
        let a = &mut self.t[self.idx];
        *a = (*a as i32 + ((g - *a as i32) >> 7)) as u16;
        let b = &mut self.t[self.idx + 1];
        *b = (*b as i32 + ((g - *b as i32) >> 7)) as u16;
    }
}

// ==================== geodetect ====================
// M0 — GeoDetect: deterministic integer detection of native axis strides.
// Byte-equality autocorrelation over a sampled window; ties break to the
// smaller stride. No floats, no RNG — same input always yields same output.

pub const MAX_STRIDE: usize = 8192;
const MAX_SAMPLES: usize = 1 << 18; // 262144 comparisons per stride

/// Top-k candidate strides (s >= 2), best (highest match count) first.
pub fn detect_strides(data: &[u8], k: usize) -> Vec<u32> {
    let n = data.len();
    if n < 16 {
        return Vec::new();
    }
    let max_s = MAX_STRIDE.min(n - 1);
    let mut scored: Vec<(u64, usize)> = Vec::with_capacity(max_s);
    for s in 2..=max_s {
        let avail = n - s;
        let step = (avail / MAX_SAMPLES).max(1);
        let mut eq: u64 = 0;
        let mut cnt: u64 = 0;
        let mut i = 0usize;
        while i < avail {
            if data[i] == data[i + s] {
                eq += 1;
            }
            cnt += 1;
            i += step;
        }
        // normalize to per-2^20 samples to compare across strides fairly
        let score = if cnt > 0 { eq * (1 << 20) / cnt } else { 0 };
        scored.push((score, s));
    }
    // sort by score desc, then stride asc (deterministic tie-break)
    scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    scored.into_iter().take(k).map(|(_, s)| s as u32).collect()
}

// ==================== codec ====================
// M1 — GeoCM(image2d) MVP codec.
//
// Container (fixed 25-byte header):
//   magic  "CG2" + version 0x01          (4 B)
//   mode   u8: 0=RAW, 1=GEO, 2=O1        (1 B)
//   orig_len u64 LE                      (8 B)
//   fnv64 of original data, u64 LE       (8 B)
//   stride u32 LE (0 unless mode=GEO)    (4 B)
// payload follows.
//
// Invariants: lossless byte-exact round-trip; fail-closed decode (magic,
// version, bounds, and FNV-1a 64 checksum verified after decode); integer
// determinism (no floats anywhere); raw fallback bounds expansion to
// HEADER_LEN bytes. Encoder is competitive-min over {RAW, O1, GEO(top
// strides)} — picking a candidate never makes output worse than raw.
//
// Models (bitwise, one 12-bit adaptive probability per node):
//   O1 : ctx = prev byte                          (256 * 256 nodes)
//   GEO: ctx = above byte (t-S) * 16 + prev>>4    (4096 * 256 nodes)
// The GEO context is the X1-probe winner (see cubr-cubecore-research,
// x-experiment-verdict.md): real-adaptive KT cost 0.552 bpb on ptt5 vs
// champion 0.754 bpb.


pub const MAGIC: [u8; 4] = *b"CG2\x03";
pub const HEADER_LEN: usize = 26;
pub const MODE_RAW: u8 = 0;
pub const MODE_GEO: u8 = 1;
pub const MODE_O1: u8 = 2;
pub const MODE_GEOA: u8 = 3;
pub const MODE_MIX: u8 = 4;

#[derive(Debug, PartialEq, Eq)]
pub enum CodecError {
    BadMagic,
    Truncated,
    BadMode(u8),
    ChecksumMismatch,
    BadStride,
}

pub fn fnv64(data: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in data {
        h ^= b as u64;
        h = h.wrapping_mul(0x1000_0000_01b3);
    }
    h
}

fn header(mode: u8, orig_len: u64, check: u64, stride: u32, cfg: u8) -> Vec<u8> {
    let mut h = Vec::with_capacity(HEADER_LEN);
    h.extend_from_slice(&MAGIC);
    h.push(mode);
    h.extend_from_slice(&orig_len.to_le_bytes());
    h.extend_from_slice(&check.to_le_bytes());
    h.extend_from_slice(&stride.to_le_bytes());
    h.push(cfg);
    h
}

/// Encode `data` bytewise: 8 bits per byte through a per-context node tree.
/// `ctx_of(i)` must be pure and depend only on already-decoded bytes.
fn encode_stream<F: Fn(&[u8], usize) -> usize>(
    data: &[u8],
    n_ctx: usize,
    ctx_of: F,
) -> Vec<u8> {
    let mut probs = vec![PINIT; n_ctx * 256];
    let mut enc = RcEnc::new();
    for i in 0..data.len() {
        let g = ctx_of(data, i);
        debug_assert!(g < n_ctx);
        let base = g * 256;
        let x = data[i];
        let mut node: usize = 1;
        for k in (0..8).rev() {
            let bit = (x >> k) & 1;
            let p = &mut probs[base + node];
            enc.encode_bit(*p, bit);
            update(p, bit);
            node = (node << 1) | bit as usize;
        }
    }
    enc.finish()
}

fn decode_stream<F: Fn(&[u8], usize) -> usize>(
    payload: &[u8],
    orig_len: usize,
    n_ctx: usize,
    ctx_of: F,
) -> Result<Vec<u8>, CodecError> {
    let mut probs = vec![PINIT; n_ctx * 256];
    let mut dec = RcDec::new(payload).ok_or(CodecError::Truncated)?;
    let mut out: Vec<u8> = Vec::with_capacity(orig_len);
    for i in 0..orig_len {
        let g = ctx_of(&out, i);
        debug_assert!(g < n_ctx);
        let base = g * 256;
        let mut node: usize = 1;
        for _ in 0..8 {
            let p = &mut probs[base + node];
            let bit = dec.decode_bit(*p);
            update(p, bit);
            node = (node << 1) | bit as usize;
        }
        out.push((node & 0xFF) as u8);
    }
    Ok(out)
}

#[inline]
fn ctx_o1(hist: &[u8], i: usize) -> usize {
    if i == 0 { 0 } else { hist[i - 1] as usize }
}

#[inline]
fn ctx_geoa(hist: &[u8], i: usize, s: usize) -> usize {
    if i >= s { hist[i - s] as usize } else { 0 }
}

#[inline]
fn ctx_geo(hist: &[u8], i: usize, s: usize) -> usize {
    let above = if i >= s { hist[i - s] as usize } else { 0 };
    let prev = if i > 0 { hist[i - 1] as usize } else { 0 };
    above * 16 + (prev >> 4)
}


// ---------------- MODE_MIX: logistic mixing of 6 geo/1D models ----------------

const NM: usize = 8;
const MIX_NCTX: [usize; NM] = [256, 256, 256, 4096, 256, 256, 65536, 65536];

#[inline]
fn med_u8(a: i32, b: i32, c: i32) -> usize {
    (a + b - c).clamp(0, 255) as usize
}

/// Contexts for the 6 mixed models; depends only on already-decoded bytes.
#[inline]
fn mix_ctxs(hist: &[u8], i: usize, s: usize, ctx: &mut [usize; NM]) {
    let prev = if i > 0 { hist[i - 1] as i32 } else { 0 };
    let t2 = if i > 1 { hist[i - 2] as i32 } else { 0 };
    let ab = if i >= s { hist[i - s] as i32 } else { 0 };
    let ab1 = if i >= s + 1 { hist[i - s - 1] as i32 } else { 0 };
    let ab2 = if i >= s + 2 { hist[i - s - 2] as i32 } else { 0 };
    ctx[0] = prev as usize;
    ctx[1] = t2 as usize;
    ctx[2] = ab as usize;
    ctx[3] = (ab as usize) * 16 + ((prev as usize) >> 4);
    ctx[4] = med_u8(prev, ab, ab1);
    ctx[5] = med_u8(t2, ab, ab2);
    ctx[6] = (prev as usize) * 256 + t2 as usize;
    ctx[7] = (ab as usize) * 256 + t2 as usize;
}

struct MixState {
    tabs: Tables,
    probs: Vec<Vec<u16>>,
    mixer: Mixer,
    apm: Apm,
    apm2: Apm,
}

impl MixState {
    fn new(cfg: u8) -> Self {
        let _ = cfg;
        let tabs = Tables::new();
        let apm = Apm::new(256, &tabs);
        let apm2 = Apm::new(256, &tabs);
        MixState {
            tabs,
            probs: MIX_NCTX.iter().map(|&n| vec![PINIT; n * 256]).collect(),
            mixer: Mixer::new(512, NM),
            apm,
            apm2,
        }
    }
}

fn encode_stream_mix(data: &[u8], s: usize, cfg: u8) -> Vec<u8> {
    let mut st = MixState::new(cfg);
    let mut enc = RcEnc::new();
    let mut ctx = [0usize; NM];
    let mut stv = [0i32; NM];
    for i in 0..data.len() {
        mix_ctxs(data, i, s, &mut ctx);
        let x = data[i];
        let mut node: usize = 1;
        for k in (0..8).rev() {
            let bit = (x >> k) & 1;
            for m in 0..NM {
                let pm = st.probs[m][ctx[m] * 256 + node];
                stv[m] = st.tabs.stretch[pm as usize];
            }
            let set = if cfg & 1 != 0 { node + ((i & 1) << 8) } else { node };
            let (p, _) = st.mixer.predict(&st.tabs, set, &stv);
            let pa = st.apm.pp(&st.tabs, p, ctx[0]);
            let pf1 = (((p as u32) + 3 * (pa as u32)) >> 2).clamp(1, 4095) as u16;
            let pf = if cfg & 2 != 0 {
                let pa2 = st.apm2.pp(&st.tabs, pf1, ctx[2]);
                (((pf1 as u32) + 3 * (pa2 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf1
            };
            enc.encode_bit(pf, bit);
            st.apm.update(bit);
            if cfg & 2 != 0 {
                st.apm2.update(bit);
            }
            st.mixer.update(set, &stv, p, bit);
            for m in 0..NM {
                update(&mut st.probs[m][ctx[m] * 256 + node], bit);
            }
            node = (node << 1) | bit as usize;
        }
    }
    enc.finish()
}

fn decode_stream_mix(
    payload: &[u8],
    orig_len: usize,
    s: usize,
    cfg: u8,
) -> Result<Vec<u8>, CodecError> {
    let mut st = MixState::new(cfg);
    let mut dec = RcDec::new(payload).ok_or(CodecError::Truncated)?;
    let mut out: Vec<u8> = Vec::with_capacity(orig_len);
    let mut ctx = [0usize; NM];
    let mut stv = [0i32; NM];
    for i in 0..orig_len {
        mix_ctxs(&out, i, s, &mut ctx);
        let mut node: usize = 1;
        for _ in 0..8 {
            for m in 0..NM {
                let pm = st.probs[m][ctx[m] * 256 + node];
                stv[m] = st.tabs.stretch[pm as usize];
            }
            let set = if cfg & 1 != 0 { node + ((i & 1) << 8) } else { node };
            let (p, _) = st.mixer.predict(&st.tabs, set, &stv);
            let pa = st.apm.pp(&st.tabs, p, ctx[0]);
            let pf1 = (((p as u32) + 3 * (pa as u32)) >> 2).clamp(1, 4095) as u16;
            let pf = if cfg & 2 != 0 {
                let pa2 = st.apm2.pp(&st.tabs, pf1, ctx[2]);
                (((pf1 as u32) + 3 * (pa2 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf1
            };
            let bit = dec.decode_bit(pf);
            st.apm.update(bit);
            if cfg & 2 != 0 {
                st.apm2.update(bit);
            }
            st.mixer.update(set, &stv, p, bit);
            for m in 0..NM {
                update(&mut st.probs[m][ctx[m] * 256 + node], bit);
            }
            node = (node << 1) | bit as usize;
        }
        out.push((node & 0xFF) as u8);
    }
    Ok(out)
}

pub fn encode(data: &[u8]) -> Vec<u8> {
    let check = fnv64(data);
    let n = data.len() as u64;
    // candidate: RAW (always available)
    let mut best_mode = MODE_RAW;
    let mut best_stride: u32 = 0;
    let mut best_cfg: u8 = 0;
    let mut best_payload: Vec<u8> = data.to_vec();

    if !data.is_empty() {
        // candidate: O1
        let o1 = encode_stream(data, 256, |h, i| ctx_o1(h, i));
        if o1.len() < best_payload.len() {
            best_mode = MODE_O1;
            best_stride = 0;
            best_payload = o1;
        }
        // candidates: GEO over top detected strides
        for s in detect_strides(data, 3) {
            let su = s as usize;
            if su < 2 || su >= data.len() {
                continue;
            }
            let geo = encode_stream(data, 4096, |h, i| ctx_geo(h, i, su));
            if geo.len() < best_payload.len() {
                best_mode = MODE_GEO;
                best_stride = s;
                best_payload = geo;
            }
            let geoa = encode_stream(data, 256, |h, i| ctx_geoa(h, i, su));
            if geoa.len() < best_payload.len() {
                best_mode = MODE_GEOA;
                best_stride = s;
                best_payload = geoa;
            }
            for cfg in [0u8, 3u8] {
                let mixed = encode_stream_mix(data, su, cfg);
                if mixed.len() < best_payload.len() {
                    best_mode = MODE_MIX;
                    best_stride = s;
                    best_cfg = cfg;
                    best_payload = mixed;
                }
            }
        }
    }
    let mut out = header(best_mode, n, check, best_stride, best_cfg);
    out.extend_from_slice(&best_payload);
    out
}

pub fn decode(blob: &[u8]) -> Result<Vec<u8>, CodecError> {
    if blob.len() < HEADER_LEN {
        return Err(CodecError::Truncated);
    }
    if blob[0..4] != MAGIC {
        return Err(CodecError::BadMagic);
    }
    let mode = blob[4];
    let orig_len = u64::from_le_bytes(blob[5..13].try_into().unwrap()) as usize;
    let check = u64::from_le_bytes(blob[13..21].try_into().unwrap());
    let stride = u32::from_le_bytes(blob[21..25].try_into().unwrap()) as usize;
    let cfg = blob[25];
    let payload = &blob[HEADER_LEN..];

    let out = match mode {
        MODE_RAW => {
            if payload.len() != orig_len {
                return Err(CodecError::Truncated);
            }
            payload.to_vec()
        }
        MODE_O1 => {
            if orig_len == 0 {
                Vec::new()
            } else {
                decode_stream(payload, orig_len, 256, |h, i| ctx_o1(h, i))?
            }
        }
        MODE_GEO => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            decode_stream(payload, orig_len, 4096, |h, i| ctx_geo(h, i, stride))?
        }
        MODE_GEOA => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            decode_stream(payload, orig_len, 256, |h, i| ctx_geoa(h, i, stride))?
        }
        MODE_MIX => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            decode_stream_mix(payload, orig_len, stride, cfg)?
        }
        m => return Err(CodecError::BadMode(m)),
    };
    if fnv64(&out) != check {
        return Err(CodecError::ChecksumMismatch);
    }
    Ok(out)
}

// ==================== shipped-rail gate ====================

/// Performance gate for the shipped competitive-min: run GeoCM only on image-like
/// inputs (a strongly periodic native byte-axis, bounded size). Correctness never
/// depends on this — competitive-min discards GeoCM whenever it is not strictly
/// smaller — so this only avoids wasting encode time on non-periodic / huge inputs.
pub fn should_try(data: &[u8]) -> bool {
    let n = data.len();
    if n < 8192 || n > 12_000_000 {
        return false;
    }
    let max_s = MAX_STRIDE.min(n - 1);
    if max_s < 2 {
        return false;
    }
    const MAX_SAMPLES: usize = 1 << 16;
    let mut scores: Vec<u64> = Vec::with_capacity(max_s);
    for s in 2..=max_s {
        let avail = n - s;
        let step = (avail / MAX_SAMPLES).max(1);
        let (mut eq, mut cnt, mut i) = (0u64, 0u64, 0usize);
        while i < avail {
            if data[i] == data[i + s] {
                eq += 1;
            }
            cnt += 1;
            i += step;
        }
        scores.push(if cnt > 0 { eq * (1 << 20) / cnt } else { 0 });
    }
    // Absolute best-stride byte-equality autocorrelation separates the image class
    // (measured: ptt5 0.918, x-ray 0.456, mr 0.332 of 2^20) from non-image inputs
    // (ooffice 0.096, dickens 0.074). A run-heavy bilevel fax (ptt5) is FLAT across
    // strides so a prominence test would miss it; the absolute floor catches it while
    // still rejecting text/exe. 0.15 * 2^20 sits with wide margin on both sides.
    let best = *scores.iter().max().unwrap_or(&0);
    best >= (1u64 << 20) * 15 / 100
}
