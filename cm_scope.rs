// CM-SCOPING probe (CUBR-0059, research/cubr-ppmd-rescale).
//
// A pragmatic lpaq-lite bit-level context-mixing model that measures ONLY the
// ideal cross-entropy (sum of -log2 p over the actual bits) — no arithmetic
// coder, no round-trip, no wire. bits/byte here ≈ the ratio a real CM codec
// would achieve (measured coder overhead on this project is 0.037%, negligible).
//
// Purpose: estimate the realistic CM ceiling vs the current PPM champion
// (0.229919 = 1.83935 bits/byte on dickens) and the ppmd floor (0.2253 =
// 1.80264) BEFORE committing to a full CM rewrite.
//
// Models (10): order-0..7 bit-context predictors + a match model + a word model,
// combined by a single-layer logistic mixer (per-prev-byte weight set) + one
// APM/SSE stage. This is a LOWER bound on a real CM (lpaq adds a 2-layer mixer,
// SSE chains, sparse/indirect contexts, 2 match models; cmix far more) — if this
// already beats the champion, a real CM beats it by more.
//
// Result (full-dickens, 10192446 B): ratio 0.229671 (bits/byte 1.83737),
// BEATS the PPM champion 0.229919 by 248 B; ~35.9 s / 131 MB (unoptimized f64).
//
// Build: rustc -O cm_scope.rs -o cm_scope
// Run:   CUBR_PROBE_FILE=/path/dickens [CUBR_PROBE_LIMIT=N] [CM_LR=..] [CM_APMW=..] ./cm_scope

use std::env;
use std::io::Read;

#[inline]
fn stretch(p: f64) -> f64 {
    (p / (1.0 - p)).ln()
}
#[inline]
fn squash(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}
#[inline]
fn clampp(p: f64) -> f64 {
    p.clamp(1.0 / 4096.0, 4095.0 / 4096.0)
}

/// One hashed bit-probability table with a count-adaptive learning rate
/// (fast when a cell is fresh, stable once well-observed — the lpaq counter).
struct BitTable {
    t: Vec<u16>, // 12-bit prob
    c: Vec<u8>,  // observation count (capped)
    mask: usize,
    cap: i32,
}
impl BitTable {
    fn new(bits: usize, cap: i32) -> Self {
        Self {
            t: vec![2048u16; 1usize << bits],
            c: vec![0u8; 1usize << bits],
            mask: (1usize << bits) - 1,
            cap,
        }
    }
    #[inline]
    fn p(&self, cx: usize) -> f64 {
        (self.t[cx & self.mask] as f64) / 4096.0
    }
    #[inline]
    fn upd(&mut self, cx: usize, y: u32) {
        let i = cx & self.mask;
        let cur = self.t[i] as i32;
        let cnt = self.c[i] as i32;
        // rate = 1/(cnt+2): fast early, stabilising as the cell matures.
        let nv = cur + ((y as i32) * 4096 - cur) / (cnt + 2);
        self.t[i] = nv.clamp(1, 4095) as u16;
        if cnt < self.cap {
            self.c[i] = (cnt + 1) as u8;
        }
    }
}

const NORD: usize = 8; // order models: 0,1,2,3,4,5,6,7
const NM: usize = NORD + 2; // + match model + word model
const TBITS: usize = 22; // 4M entries per table

fn main() {
    let path = env::var("CUBR_PROBE_FILE").expect("set CUBR_PROBE_FILE");
    let lim: usize = env::var("CUBR_PROBE_LIMIT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(usize::MAX);
    let mut data = Vec::new();
    std::fs::File::open(&path)
        .expect("open")
        .read_to_end(&mut data)
        .expect("read");
    if data.len() > lim {
        data.truncate(lim);
    }
    let n = data.len();

    // Order-k bit tables (k = 0..6). Index = hash(order-k bytes, c0).
    let orders = [0usize, 1, 2, 3, 4, 5, 6, 7];
    let mut tabs: Vec<BitTable> = orders.iter().map(|_| BitTable::new(TBITS, 254)).collect();
    // Word model: hashed run of alnum bytes + c0.
    let mut wtab = BitTable::new(TBITS, 254);
    let mut word_hash: u32 = 0;
    let apm_w: f64 = env::var("CM_APMW").ok().and_then(|s| s.parse().ok()).unwrap_or(0.65);
    let lr: f64 = env::var("CM_LR").ok().and_then(|s| s.parse().ok()).unwrap_or(0.02);

    // Match model: hash(last 6 bytes) -> last position.
    const MINLEN: usize = 6;
    let mut match_hash = vec![0u32; 1usize << TBITS];
    let match_mask = (1usize << TBITS) - 1;
    let mut match_ptr: usize = 0;
    let mut match_len: usize = 0;

    // Mixer: per-(prev byte) weight set, NM+1 weights (bias). f64 for probe.
    let mut w = vec![0.0f64; 256 * (NM + 1)];

    // APM: 24 interpolation knots x (prev-byte context), on the mixed prob.
    const APM_N: usize = 24;
    const APM_CTX: usize = 256;
    // Standard APM/SSE: each knot stores a PROBABILITY, init to the identity
    // curve squash(sx_i) at input-stretch sx_i = i*16/N - 8. Interpolate in
    // probability space; update the nearer knot toward the outcome.
    let mut apm = vec![0.0f64; APM_CTX * (APM_N + 1)];
    for c in 0..APM_CTX {
        for i in 0..=APM_N {
            apm[c * (APM_N + 1) + i] = squash((i as f64) * 16.0 / (APM_N as f64) - 8.0);
        }
    }

    let mut bits_total = 0.0f64;
    let mut st = [0.0f64; NM + 1];

    // Precompute order hashes incrementally per byte.
    for t in 0..n {
        // order-k byte-context hashes (independent of current partial byte).
        let mut hk = [0usize; 8];
        for (oi, &k) in orders.iter().enumerate() {
            if k == 0 {
                hk[oi] = 0;
            } else if t >= k {
                let mut h = 0x9E3779B1u32 ^ (k as u32);
                for j in 0..k {
                    h = h
                        .wrapping_mul(0x85EBCA77)
                        .wrapping_add(data[t - 1 - j] as u32);
                    h ^= h >> 15;
                }
                hk[oi] = h as usize;
            } else {
                hk[oi] = 0xDEAD ^ k;
            }
        }
        // Match model: refresh pointer at byte boundary.
        let prev = if t > 0 { data[t - 1] as usize } else { 0 };
        let wset = prev * (NM + 1);
        let apm_base = prev * (APM_N + 1);

        let predicted_byte = if match_len > 0 && match_ptr < t {
            data[match_ptr] as i32
        } else {
            -1
        };

        let mut c0: usize = 1; // partial-byte context with leading-1 sentinel
        for bit in 0..8u32 {
            let y = ((data[t] >> (7 - bit)) & 1) as u32;

            // model stretched predictions
            for oi in 0..orders.len() {
                let cx = hk[oi].wrapping_mul(0x2545F491).wrapping_add(c0);
                st[oi] = stretch(clampp(tabs[oi].p(cx)));
            }
            // match model prediction
            let pm = if predicted_byte >= 0 {
                let pbit = ((predicted_byte >> (7 - bit)) & 1) as u32;
                let conf = 1.0 - 1.0 / ((match_len as f64) + 1.5);
                let p = if pbit == 1 {
                    0.5 + 0.5 * conf
                } else {
                    0.5 - 0.5 * conf
                };
                stretch(clampp(p))
            } else {
                0.0
            };
            st[NORD] = pm;
            // word model prediction
            let wcx = (word_hash as usize)
                .wrapping_mul(0x2545F491)
                .wrapping_add(c0);
            st[NORD + 1] = stretch(clampp(wtab.p(wcx)));
            st[NM] = 1.0; // bias

            // mix
            let mut dot = 0.0f64;
            for i in 0..=NM {
                dot += w[wset + i] * st[i];
            }
            let pmix = squash(dot);

            // APM/SSE: map stretch(pmix) to a knot position, interpolate the
            // stored probabilities.
            let sx = stretch(clampp(pmix));
            let pos = ((sx + 8.0) / 16.0 * (APM_N as f64)).clamp(0.0, APM_N as f64);
            let lo = pos.floor() as usize;
            let frac = pos - lo as f64;
            let hi = (lo + 1).min(APM_N);
            let papm = apm[apm_base + lo] * (1.0 - frac) + apm[apm_base + hi] * frac;
            let pf = clampp((1.0 - apm_w) * pmix + apm_w * papm);

            // accumulate ideal bits under final prob
            let pbit1 = pf;
            bits_total += -(if y == 1 { pbit1 } else { 1.0 - pbit1 }).log2();

            // ---- updates ----
            let err = (y as f64) - pmix;
            for i in 0..=NM {
                w[wset + i] += lr * err * st[i];
            }
            for oi in 0..orders.len() {
                let cx = hk[oi].wrapping_mul(0x2545F491).wrapping_add(c0);
                tabs[oi].upd(cx, y);
            }
            let wcx = (word_hash as usize)
                .wrapping_mul(0x2545F491)
                .wrapping_add(c0);
            wtab.upd(wcx, y);
            // APM update: nudge the nearer knot's stored probability toward y.
            let ki = apm_base + if frac >= 0.5 { hi } else { lo };
            apm[ki] += 0.04 * ((y as f64) - apm[ki]);
            apm[ki] = clampp(apm[ki]);

            c0 = (c0 << 1) | (y as usize);
        }

        // word-model state: extend on alnum, reset otherwise.
        let b = data[t];
        if b.is_ascii_alphanumeric() {
            word_hash = word_hash
                .wrapping_mul(0x6F4A7C13)
                .wrapping_add(b as u32 + 1);
        } else {
            word_hash = 0;
        }

        // update match model after the full byte is known
        if match_len > 0 && predicted_byte == data[t] as i32 {
            match_ptr += 1;
            match_len += 1;
        } else {
            match_len = 0;
        }
        if t + 1 >= MINLEN {
            let mut h = 0xABCDEF01u32;
            for j in 0..MINLEN {
                h = h.wrapping_mul(0x85EBCA77).wrapping_add(data[t - j] as u32);
                h ^= h >> 13;
            }
            let hi = (h as usize) & match_mask;
            if match_len == 0 {
                let cand = match_hash[hi] as usize;
                if cand > 0 && cand < t {
                    match_ptr = cand + 1;
                    match_len = 1;
                }
            }
            match_hash[hi] = (t as u32).wrapping_add(1).wrapping_sub(1); // store t
            match_hash[hi] = t as u32;
        }
    }

    let bpb = bits_total / n as f64;
    let ratio = bpb / 8.0;
    println!(
        "CM-PROBE file={} n={} ideal_bytes={:.0} bits_per_byte={:.5} ratio={:.6} \
         vs_champion_0.229919={:+.6} vs_ppmd_floor_0.2253={:+.6}",
        path,
        n,
        bits_total / 8.0,
        bpb,
        ratio,
        ratio - 0.229919,
        ratio - 0.2253,
    );
}
