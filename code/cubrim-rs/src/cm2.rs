//! MODE_CM2 — bit-level context-mixing codec (CM PoC, CUBR-0059 CM track).
//!
//! Models (each context model emits a DUAL prediction — a stationary
//! count-adaptive probability AND a nonstationary lpaq/zpaq bit-history state via
//! a StateMap — as two independent mixer inputs): order-0..11, 6 sparse
//! (skip-gram), 1 indirect (history-of-history, order-2 keyed), 3 match models
//! (min-len 12/6/3), 4 word models (current word, prev×current bigram,
//! case-folded word, case-folded bigram). Combined by a TWO-LAYER integer
//! logistic mixer: 5 context-specialised layer-1 mixers (prev-byte / order-2 /
//! match-state / partial-byte / order-3) → a layer-2 mixer over their outputs,
//! refined by a 2-stage APM/SSE chain, coded per bit through the crate's
//! carryless range coder in binary mode (12-bit). Hash tables are sized to the
//! input length (tbits = clamp(ceil(log2(len))+3, 18, 27)).
//!
//! Full trajectory (RT cmp=0): the decisive levers were the dual counter, a
//! strongly-nonstationary bit-history state machine, the 5th mixer view, and
//! larger hash tables (collision reduction at scale). full-dickens 0.231335 →
//! 0.211565; enwik8-head 0.234742 → 0.200615 (BELOW the ppmd text floor
//! 0.201379). Reverted dead ends (see log): straight StateMap replacement,
//! 2nd indirect (Gotcha #9), 6th mixer, order-12/13, richer l2 context, a 3rd
//! APM, 16-bit resolution — all REGRESSED.
//!
//! ALL prediction/mixing/adaptation is integer, so encode and decode — processing
//! the identical byte sequence — build byte-exact identical state and the round
//! trip is `cmp=0` by construction. f64 only builds the static tables once.
//!
//! Competitive-min candidate: it need not beat PPM on every file, only where CM
//! is best (enwik8/webster). `min(len)` guards correctness.

use crate::codec::{RangeDecoder, RangeEncoder};
use crate::error::CubrimError;

const PBITS: u32 = 12;
const PSCALE: i32 = 1 << PBITS; // 4096

// QA-F-001 fail-closed decode guards (branch F adversarial-QA).
// Maximum output bytes produced without the range decoder consuming a new input byte. A
// valid stream never rides longer than the renormalization run-length: with PSCALE=4096
// and the mixer/APM predictions clamped to ST_MAX, the per-symbol probability stays bounded
// away from 1, so renorm reads recur within well under ~6 KB even for maximally-compressible
// data. 64 KiB is an ~11x safety margin and bounds a truncated stream's fabricated output
// (and decode time) to 64 KiB before it fails closed.
const CM2_STALL_LIMIT: u64 = 1 << 16;

const ST_MAX: i32 = 2047; // stretch domain [-2047, 2047]
const ST_SCALE: f64 = 256.0; // ln-scale: stretch(1..PSCALE-1) spans ≈ [-ST_MAX, ST_MAX]

/// Integer logistic tables: `squash` maps a stretched value back to a 16-bit
/// probability; `stretch` is its inverse (FINE per-p). Built once (f64 at init).
struct Logistic {
    squash: Vec<u16>,
    stretch: Vec<i16>,
}
impl Logistic {
    fn new() -> Self {
        let mut squash = vec![0u16; (2 * ST_MAX + 1) as usize];
        for x in -ST_MAX..=ST_MAX {
            let v = PSCALE as f64 / (1.0 + (-(x as f64) / ST_SCALE).exp());
            squash[(x + ST_MAX) as usize] = v.round().clamp(1.0, (PSCALE - 1) as f64) as u16;
        }
        let mut stretch = vec![0i16; PSCALE as usize];
        for p in 0..PSCALE {
            let pc = (p as f64).clamp(1.0, (PSCALE - 1) as f64);
            let v = ST_SCALE * (pc / (PSCALE as f64 - pc)).ln();
            stretch[p as usize] = v.round().clamp(-(ST_MAX as f64), ST_MAX as f64) as i16;
        }
        Self { squash, stretch }
    }
    #[inline]
    fn squash(&self, x: i32) -> i32 {
        self.squash[(x.clamp(-ST_MAX, ST_MAX) + ST_MAX) as usize] as i32
    }
    #[inline]
    fn stretch(&self, p: i32) -> i32 {
        self.stretch[p.clamp(1, PSCALE - 1) as usize] as i32
    }
}

/// Bit-history state-transition table `nex[state][bit]` over a 16×16 (n0,n1)
/// grid: observing a bit increments its own bounded count and applies a
/// NONSTATIONARY discount to the contradicting count (halving its excess above
/// 2). This is what lets a cell forget stale statistics after a regime change.
fn build_nex() -> Vec<[u8; 2]> {
    // Nonstationary discount mode for the losing count (env CM_NEXMODE):
    //   0 = halve excess above 2 (baseline);
    //   1 = baseline, then bound the loser to winner+BND (faster forget when one
    //       bit dominates — closer to a real lpaq state machine);
    //   2 = aggressive: cap loser at 3 once the winner is confident (>=4).
    // Default mode=1 bnd=0: bound the losing count to the (post-increment) winning
    // count — a strongly-nonstationary state machine. The stationary counter
    // already preserves balanced statistics, so the state-map input specialises
    // in "what is happening now"; measured best on both dickens and enwik8.
    let mode: i32 = std::env::var("CM_NEXMODE")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    let bnd: i32 = std::env::var("CM_NEXBND")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let discount = |loser: i32, winner_new: i32| -> i32 {
        let mut d = if loser > 2 { 2 + ((loser - 2) >> 1) } else { loser };
        match mode {
            1 => d = d.min(winner_new + bnd),
            2 => {
                if winner_new >= 4 {
                    d = d.min(3);
                }
            }
            _ => {}
        }
        d.max(0)
    };
    let mut nex = vec![[0u8; 2]; 256];
    for s in 0..256usize {
        let n0 = (s >> 4) as i32;
        let n1 = (s & 15) as i32;
        // observe bit 1
        let a1 = (n1 + 1).min(15);
        let d0 = discount(n0, a1);
        nex[s][1] = ((d0 << 4) | a1) as u8;
        // observe bit 0
        let a0 = (n0 + 1).min(15);
        let d1 = discount(n1, a0);
        nex[s][0] = ((a0 << 4) | d1) as u8;
    }
    nex
}

/// StateMap: state → adaptive P(bit==1), learned online with a count-scaled rate
/// (fast when a state is fresh). 22-bit internal probability.
struct StateMap {
    t: Vec<u32>,
    cnt: Vec<u16>,
    cap: u16,
}
impl StateMap {
    fn new(n: usize, cap: u16) -> Self {
        Self {
            t: vec![1u32 << 21; n], // 0.5
            cnt: vec![0u16; n],
            cap,
        }
    }
    #[inline]
    fn p12(&self, s: usize) -> i32 {
        (self.t[s] >> 10) as i32 // -> 12-bit
    }
    #[inline]
    fn upd(&mut self, s: usize, y: i32) {
        let c = self.cnt[s].min(self.cap) as i64;
        let cur = self.t[s] as i64;
        let tgt = (y as i64) << 22;
        self.t[s] = (cur + (tgt - cur) / (c + 2)) as u32;
        if self.cnt[s] < self.cap {
            self.cnt[s] += 1;
        }
    }
}

/// A context model emitting TWO predictions per cell (fed as two independent
/// mixer inputs, the strong-CM way — the mixer weights each per context):
///   1. a STATIONARY count-adaptive probability (`t`/`c`, rate 1/(count+2),
///      count capped at `lim`) — converges to a stable estimate, best on
///      stationary text;
///   2. a NONSTATIONARY bit-history state (`st`) mapped through a `StateMap`
///      (the lpaq/zpaq counter) — forgets stale statistics after a regime
///      change, best on short/changing contexts.
/// Keeping BOTH (rather than replacing #1 with #2) is regression-proof: the
/// mixer can drive the nonstationary weight to zero where it hurts (large
/// stationary streams) yet exploit it where it helps.
struct Ctr {
    t: Vec<u16>,
    c: Vec<u8>,
    st: Vec<u8>,
    sm: StateMap,
    mask: usize,
    lim: i32,
}
impl Ctr {
    fn new(bits: usize, lim: i32, sm_cap: i32) -> Self {
        Self {
            t: vec![(PSCALE / 2) as u16; 1usize << bits],
            c: vec![0u8; 1usize << bits],
            st: vec![0u8; 1usize << bits],
            sm: StateMap::new(256, sm_cap.clamp(2, 1023) as u16),
            mask: (1usize << bits) - 1,
            lim,
        }
    }
    /// Predict: returns (stationary 12-bit prob, state-map 12-bit prob, state).
    /// The state is fed back to [`Ctr::upd`].
    #[inline]
    fn predict(&self, cx: usize) -> (i32, i32, u8) {
        let i = cx & self.mask;
        let s = self.st[i];
        (
            self.t[i] as i32,
            self.sm.p12(s as usize).clamp(1, PSCALE - 1),
            s,
        )
    }
    #[inline]
    fn upd(&mut self, cx: usize, state: u8, y: i32, nex: &[[u8; 2]]) {
        let i = cx & self.mask;
        // stationary count-adaptive counter (identical to the pre-StateMap codec)
        let cur = self.t[i] as i32;
        let cnt = self.c[i] as i32;
        self.t[i] = (cur + (y * PSCALE - cur) / (cnt + 2)).clamp(1, PSCALE - 1) as u16;
        if cnt < self.lim {
            self.c[i] = (cnt + 1) as u8;
        }
        // nonstationary bit-history state machine + StateMap
        self.sm.upd(state as usize, y);
        self.st[i] = nex[state as usize][y as usize];
    }
}

/// One APM/SSE stage: `nctx` rows of `APM_N+1` interpolation knots (16-bit prob).
struct Apm {
    t: Vec<u16>,
    n1: usize,
}
impl Apm {
    fn new(lg: &Logistic, nctx: usize) -> Self {
        let n1 = APM_N + 1;
        let mut t = vec![0u16; nctx * n1];
        for c in 0..nctx {
            for i in 0..=APM_N {
                let x = (i as i32) * (2 * ST_MAX) / (APM_N as i32) - ST_MAX;
                t[c * n1 + i] = lg.squash(x) as u16;
            }
        }
        Self { t, n1 }
    }
    /// Refine `p` (16-bit) in context `ctx`; returns (refined_p, knot_to_update).
    #[inline]
    fn refine(&self, lg: &Logistic, ctx: usize, p: i32) -> (i32, usize) {
        let sx = lg.stretch(p);
        let num = (sx + ST_MAX) * (APM_N as i32);
        let lo = (num / (2 * ST_MAX)).clamp(0, APM_N as i32 - 1) as usize;
        let frac = (num % (2 * ST_MAX)).max(0);
        let base = ctx * self.n1 + lo;
        let a0 = self.t[base] as i32;
        let a1 = self.t[base + 1] as i32;
        let r = a0 + (a1 - a0) * frac / (2 * ST_MAX);
        let idx = base + if frac * 2 >= 2 * ST_MAX { 1 } else { 0 };
        (r.clamp(1, PSCALE - 1), idx)
    }
    #[inline]
    fn upd(&mut self, idx: usize, y: i32) {
        let cur = self.t[idx] as i32;
        self.t[idx] = (cur + (y * PSCALE - cur) / 32).clamp(1, PSCALE - 1) as u16;
    }
}

/// One logistic mixer layer: `nsets` weight-sets of `nin` fixed-point weights.
/// `mix` returns the stretched output (for chaining into the next layer) and
/// stashes the squashed prediction for the paired [`Mixer::update`] (each mixer
/// is trained independently toward the bit, paq-style).
struct Mixer {
    w: Vec<i32>,
    nin: usize,
    shift: i32,
    set: usize,
    px: i32,
    raw: i32, // unclamped (dot>>16) — for the FH2-06 quant-audit only
}
impl Mixer {
    fn new(nsets: usize, nin: usize, shift: i32) -> Self {
        Self {
            w: vec![0i32; nsets * nin],
            nin,
            shift,
            set: 0,
            px: PSCALE / 2,
            raw: 0,
        }
    }
    #[inline]
    fn mix(&mut self, lg: &Logistic, inp: &[i32], ctx: usize) -> i32 {
        self.set = ctx * self.nin;
        let mut dot: i64 = 0;
        for i in 0..self.nin {
            dot += self.w[self.set + i] as i64 * inp[i] as i64;
        }
        let x = (dot >> 16) as i32;
        self.raw = x;
        self.px = lg.squash(x);
        x.clamp(-ST_MAX, ST_MAX)
    }
    #[inline]
    fn update(&mut self, inp: &[i32], y: i32) {
        let err = y * PSCALE - self.px;
        for i in 0..self.nin {
            self.w[self.set + i] += (inp[i] * err) >> self.shift;
        }
    }
}

const NORD: usize = 12; // order-0..11
const NSPARSE: usize = 6;
const SP_I: usize = NORD; // 8,9,10
const IND_I: usize = SP_I + NSPARSE; // 11
const M1_I: usize = IND_I + 1; //  long match
const M2_I: usize = M1_I + 1; //  short match
const WORD_I: usize = M2_I + 1;
// Second (nonstationary state-map) prediction per counter model — appended so the
// stationary block (0..=WORD_I) is byte-identical to the pre-dual codec.
const SM_ORD_I: usize = WORD_I + 1; // NORD state-map order probs
const SM_SP_I: usize = SM_ORD_I + NORD; // NSPARSE state-map sparse probs
const SM_IND_I: usize = SM_SP_I + NSPARSE; // indirect state-map prob
const SM_WORD_I: usize = SM_IND_I + 1; // word state-map prob
// 2nd word model (previous-word × current-word bigram context) — appended so all
// prior indices stay stable.
const WORD2_I: usize = SM_WORD_I + 1; // stationary 2nd-word prob
const SM_WORD2_I: usize = WORD2_I + 1; // state-map 2nd-word prob
// 3rd word model: case-folded current word (The/the/THE share statistics).
const WORD3_I: usize = SM_WORD2_I + 1;
const SM_WORD3_I: usize = WORD3_I + 1;
// 3rd (long) match model — catches long exact repeats (wiki markup/templates).
const M3_I: usize = SM_WORD3_I + 1;
// 4th word model: case-folded word bigram (prev-word-lc x current-word-lc).
const WORD4_I: usize = M3_I + 1;
const SM_WORD4_I: usize = WORD4_I + 1;
const NMODELS: usize = SM_WORD4_I + 1; // model inputs
const NIN: usize = NMODELS + 1; // (bias at NIN-1)

const TBITS_MAX: usize = 27; // hash-table cap (~12 GB/model at the max)
/// Size the per-model hash tables to the input length: ceil(log2(len)) + 3,
/// clamped to [18, TBITS_MAX]. Large files (enwik8, dickens) get the full 27
/// (the collision-free ratio win); small files use small tables (no memory /
/// init-time waste). The decoder derives the identical value from `orig_len` in
/// the wire header, so the round trip stays byte-exact.
fn tbits_for(len: usize) -> usize {
    let ceil_log2 = (usize::BITS - (len.max(2) - 1).leading_zeros()) as usize;
    (ceil_log2 + 3).clamp(18, TBITS_MAX)
}
const IBITS: usize = 20; // indirect map bits
const M1_MIN: usize = 6;
const M2_MIN: usize = 3;
const M3_MIN: usize = 12;
const WSHIFT_DEFAULT: i32 = 12;
const MM_CAP: usize = 63;
const APM_N: usize = 32;
const NL1: usize = 5; // layer-1 mixers (distinct context views)

struct Match {
    hash: Vec<u32>,
    mask: usize,
    ptr: usize,
    len: usize,
    prob: Vec<u16>,
    minlen: usize,
    predbyte: i32,
    // per-bit scratch
    bucket: usize,
    predbit: i32,
    active: bool,
}
impl Match {
    fn new(minlen: usize, tbits: usize) -> Self {
        Self {
            hash: vec![0u32; 1usize << tbits],
            mask: (1usize << tbits) - 1,
            ptr: 0,
            len: 0,
            prob: vec![(PSCALE * 3 / 4) as u16; MM_CAP + 1],
            minlen,
            predbyte: -1,
            bucket: 0,
            predbit: 0,
            active: false,
        }
    }
    fn start(&mut self, buf: &[u8]) {
        let t = buf.len();
        self.predbyte = if self.len > 0 && self.ptr < t {
            buf[self.ptr] as i32
        } else {
            -1
        };
    }
    #[inline]
    fn stretch_in(&mut self, lg: &Logistic, bit: u32) -> i32 {
        if self.predbyte >= 0 {
            self.predbit = ((self.predbyte >> (7 - bit)) & 1) as i32;
            self.bucket = self.len.min(MM_CAP);
            let mm = self.prob[self.bucket] as i32;
            let p = if self.predbit == 1 { mm } else { PSCALE - mm };
            self.active = true;
            lg.stretch(p)
        } else {
            self.active = false;
            0
        }
    }
    #[inline]
    fn update(&mut self, y: i32) {
        if self.active {
            let correct = (y == self.predbit) as i32;
            let cur = self.prob[self.bucket] as i32;
            self.prob[self.bucket] =
                (cur + (correct * PSCALE - cur) / 32).clamp(1, PSCALE - 1) as u16;
        }
    }
    fn end(&mut self, buf: &[u8]) {
        let t = buf.len() - 1;
        let b = buf[t] as i32;
        if self.len > 0 && self.predbyte == b {
            self.ptr += 1;
            self.len += 1;
        } else {
            self.len = 0;
        }
        if buf.len() >= self.minlen {
            let mut h = 0xABCD_EF01u32 ^ (self.minlen as u32);
            for j in 0..self.minlen {
                h = h.wrapping_mul(0x85EB_CA77).wrapping_add(buf[t - j] as u32);
                h ^= h >> 13;
            }
            let hi = (h as usize) & self.mask;
            if self.len == 0 {
                let cand = self.hash[hi] as usize;
                if cand > 0 && cand < t {
                    self.ptr = cand + 1;
                    self.len = 1;
                }
            }
            self.hash[hi] = t as u32;
        }
    }
}

struct CmModel {
    lg: Logistic,
    ord: Vec<Ctr>,
    sp: Vec<Ctr>,
    ind: Ctr,
    ind_map: Vec<u32>,
    ind_mask: usize,
    wtab: Ctr,
    word_hash: u32,
    wtab2: Ctr,
    prev_word: u32,
    word2_cx: usize,
    word2state: u8,
    wtab3: Ctr,
    word_lc: u32,
    word3_cx: usize,
    word3state: u8,
    wtab4: Ctr,
    prev_word_lc: u32,
    word4_cx: usize,
    word4state: u8,
    m1: Match,
    m2: Match,
    m3: Match,
    // 2-layer mixer
    l1: Vec<Mixer>,
    l2: Mixer,
    wshift: i32,
    l2in: [i32; NL1 + 1],
    mctx: [usize; NL1],
    // SSE chain
    apm1: Apm,
    apm2: Apm,
    // per-byte scratch
    hk: [usize; NORD],
    sphash: [usize; NSPARSE],
    ind_key: usize,
    ind_hist: usize,
    prev: usize,
    nex: Vec<[u8; 2]>,
    // per-bit scratch
    st: [i32; NIN],
    cxs: [usize; NORD],
    spcx: [usize; NSPARSE],
    indcx: usize,
    word_cx: usize,
    ostate: [u8; NORD],
    spstate: [u8; NSPARSE],
    indstate: u8,
    wordstate: u8,
    pmix: i32,
    apm1_idx: usize,
    apm2_idx: usize,
    // FH2-06 quant-audit (encode-path diagnostic; no wire effect)
    audit: bool,
    q_bits: f64,
    i_bits: f64,
}

impl CmModel {
    fn new(tbits: usize) -> Self {
        let lg = Logistic::new();
        let apm1 = Apm::new(&lg, 256);
        let apm2 = Apm::new(&lg, 1024);
        let ws: i32 = std::env::var("CM_WSHIFT")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(WSHIFT_DEFAULT);
        // Stationary counter count-cap (higher = smoother, best on stationary
        // text) and StateMap adaptation cap. Both env-tunable.
        let ctrlim: i32 = std::env::var("CM_CTRLIM")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(254);
        let smcap: i32 = std::env::var("CM_SMCAP")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(1023);
        Self {
            ord: (0..NORD).map(|_| Ctr::new(tbits, ctrlim, smcap)).collect(),
            sp: (0..NSPARSE).map(|_| Ctr::new(tbits, ctrlim, smcap)).collect(),
            ind: Ctr::new(tbits, ctrlim, smcap),
            ind_map: vec![0u32; 1usize << IBITS],
            ind_mask: (1usize << IBITS) - 1,
            wtab: Ctr::new(tbits, ctrlim, smcap),
            word_hash: 0,
            wtab2: Ctr::new(tbits, ctrlim, smcap),
            prev_word: 0,
            word2_cx: 0,
            word2state: 0,
            wtab3: Ctr::new(tbits, ctrlim, smcap),
            word_lc: 0,
            word3_cx: 0,
            word3state: 0,
            wtab4: Ctr::new(tbits, ctrlim, smcap),
            prev_word_lc: 0,
            word4_cx: 0,
            word4state: 0,
            m1: Match::new(M1_MIN, tbits),
            m2: Match::new(M2_MIN, tbits),
            m3: Match::new(M3_MIN, tbits),
            // layer-1 mixers over NIN inputs, distinct context selectors; layer 2
            // combines their NL1 stretched outputs (+bias).
            l1: vec![
                Mixer::new(256, NIN, ws),  // prev byte
                Mixer::new(1024, NIN, ws), // order-2 hash
                Mixer::new(64, NIN, ws),   // match state
                Mixer::new(256, NIN, ws),  // partial byte c0
                Mixer::new(1024, NIN, ws), // order-3 hash
            ],
            l2: Mixer::new(64, NL1 + 1, ws),
            wshift: ws,
            l2in: [0; NL1 + 1],
            mctx: [0; NL1],
            apm1,
            apm2,
            lg,
            nex: build_nex(),
            hk: [0; NORD],
            sphash: [0; NSPARSE],
            ind_key: 0,
            ind_hist: 0,
            prev: 0,
            st: [0; NIN],
            cxs: [0; NORD],
            spcx: [0; NSPARSE],
            indcx: 0,
            word_cx: 0,
            ostate: [0; NORD],
            spstate: [0; NSPARSE],
            indstate: 0,
            wordstate: 0,
            pmix: 0,
            apm1_idx: 0,
            apm2_idx: 0,
            audit: std::env::var("CM_AUDIT").map(|s| s == "1").unwrap_or(false),
            q_bits: 0.0,
            i_bits: 0.0,
        }
    }

    #[inline]
    fn bhash(seed: u32, bytes: &[u8]) -> usize {
        let mut h = seed;
        for &b in bytes {
            h = h.wrapping_mul(0x85EB_CA77).wrapping_add(b as u32);
            h ^= h >> 15;
        }
        h as usize
    }

    fn start_byte(&mut self, buf: &[u8]) {
        let t = buf.len();
        for k in 0..NORD {
            self.hk[k] = if k == 0 {
                0
            } else if t >= k {
                Self::bhash(0x9E37_79B1 ^ k as u32, &buf[t - k..t])
            } else {
                0xDEAD ^ k
            };
        }
        // sparse skip-gram contexts (non-contiguous byte subsets)
        let g = |a: usize, b: usize| -> usize {
            if t > a && t > b {
                let mut h = 0x1000_0193u32;
                h = h.wrapping_mul(0x85EB_CA77).wrapping_add(buf[t - a] as u32);
                h ^= h >> 15;
                h = h.wrapping_mul(0x85EB_CA77).wrapping_add(buf[t - b] as u32);
                h ^= h >> 15;
                h as usize
            } else {
                0xBEEF ^ (a * 7 + b)
            }
        };
        self.sphash[0] = g(1, 3); // skip t-2
        self.sphash[1] = g(1, 4); // skip t-2,t-3
        self.sphash[2] = g(2, 4); // skip t-1,t-3
        self.sphash[3] = g(2, 3); // t-2,t-3 (skip t-1)
        self.sphash[4] = g(1, 5); // t-1,t-5
        self.sphash[5] = g(3, 5); // t-3,t-5
                                  // indirect: history-of-history keyed by the order-2 context
        self.ind_key = if t >= 2 {
            Self::bhash(0x2222_3333, &buf[t - 2..t]) & self.ind_mask
        } else {
            0
        };
        self.ind_hist = self.ind_map[self.ind_key] as usize;
        self.prev = if t > 0 { buf[t - 1] as usize } else { 0 };
        self.m1.start(buf);
        self.m2.start(buf);
        self.m3.start(buf);
    }

    fn predict_bit(&mut self, c0: usize, bit: u32) -> i32 {
        for k in 0..NORD {
            let cx = self.hk[k].wrapping_mul(0x2545_F491).wrapping_add(c0);
            self.cxs[k] = cx;
            let (ps, psm, s) = self.ord[k].predict(cx);
            self.ostate[k] = s;
            self.st[k] = self.lg.stretch(ps);
            self.st[SM_ORD_I + k] = self.lg.stretch(psm);
        }
        for s in 0..NSPARSE {
            let cx = self.sphash[s].wrapping_mul(0x2545_F491).wrapping_add(c0);
            self.spcx[s] = cx;
            let (ps, psm, stt) = self.sp[s].predict(cx);
            self.spstate[s] = stt;
            self.st[SP_I + s] = self.lg.stretch(ps);
            self.st[SM_SP_I + s] = self.lg.stretch(psm);
        }
        let icx = self.ind_hist.wrapping_mul(0x2545_F491).wrapping_add(c0);
        self.indcx = icx;
        let (ips, ipsm, ist) = self.ind.predict(icx);
        self.indstate = ist;
        self.st[IND_I] = self.lg.stretch(ips);
        self.st[SM_IND_I] = self.lg.stretch(ipsm);
        self.st[M1_I] = self.m1.stretch_in(&self.lg, bit);
        self.st[M2_I] = self.m2.stretch_in(&self.lg, bit);
        self.st[M3_I] = self.m3.stretch_in(&self.lg, bit);
        let wcx = (self.word_hash as usize)
            .wrapping_mul(0x2545_F491)
            .wrapping_add(c0);
        self.word_cx = wcx;
        let (wps, wpsm, wst) = self.wtab.predict(wcx);
        self.wordstate = wst;
        self.st[WORD_I] = self.lg.stretch(wps);
        self.st[SM_WORD_I] = self.lg.stretch(wpsm);
        // 2nd word model: previous completed word × current partial word.
        let w2cx = (self
            .prev_word
            .wrapping_mul(0x9E37_79B1)
            .wrapping_add(self.word_hash) as usize)
            .wrapping_mul(0x2545_F491)
            .wrapping_add(c0);
        self.word2_cx = w2cx;
        let (w2ps, w2psm, w2st) = self.wtab2.predict(w2cx);
        self.word2state = w2st;
        self.st[WORD2_I] = self.lg.stretch(w2ps);
        self.st[SM_WORD2_I] = self.lg.stretch(w2psm);
        // 3rd word model: case-folded current word.
        let w3cx = (self.word_lc as usize)
            .wrapping_mul(0x2545_F491)
            .wrapping_add(c0);
        self.word3_cx = w3cx;
        let (w3ps, w3psm, w3st) = self.wtab3.predict(w3cx);
        self.word3state = w3st;
        self.st[WORD3_I] = self.lg.stretch(w3ps);
        self.st[SM_WORD3_I] = self.lg.stretch(w3psm);
        // 4th word model: case-folded word bigram.
        let w4cx = (self
            .prev_word_lc
            .wrapping_mul(0x9E37_79B1)
            .wrapping_add(self.word_lc) as usize)
            .wrapping_mul(0x2545_F491)
            .wrapping_add(c0);
        self.word4_cx = w4cx;
        let (w4ps, w4psm, w4st) = self.wtab4.predict(w4cx);
        self.word4state = w4st;
        self.st[WORD4_I] = self.lg.stretch(w4ps);
        self.st[SM_WORD4_I] = self.lg.stretch(w4psm);
        self.st[NIN - 1] = 256; // bias

        // 2-layer mixer: NL1 context-specialised layer-1 mixers over all inputs,
        // combined by a layer-2 mixer over their stretched outputs.
        self.mctx[0] = self.prev;
        self.mctx[1] = self.ind_key & 1023;
        self.mctx[2] = ((self.m1.len.min(15) << 1) | (self.m1.active as usize)) & 63;
        self.mctx[3] = c0 & 255;
        self.mctx[4] = self.hk[3] & 1023; // order-3 hash
        for m in 0..NL1 {
            self.l2in[m] = self.l1[m].mix(&self.lg, &self.st, self.mctx[m]);
        }
        self.l2in[NL1] = 256; // layer-2 bias
        let _ = self.l2.mix(&self.lg, &self.l2in, self.prev & 63);
        let pmix = self.l2.px;
        self.pmix = pmix;

        // SSE chain: apm1 (prev byte) then apm2 (order-2 hash), gently blended.
        let (a1, i1) = self.apm1.refine(&self.lg, self.prev, pmix);
        self.apm1_idx = i1;
        let a2ctx = (self.ind_key ^ (c0 << 3)) & 1023;
        let (a2, i2) = self.apm2.refine(&self.lg, a2ctx, a1);
        self.apm2_idx = i2;
        ((pmix * 10 + a1 * 3 + a2 * 3) >> 4).clamp(1, PSCALE - 1)
    }

    fn update_bit(&mut self, y: i32) {
        if self.audit {
            // FH2-06: layer-2 mixer output — quantized (12-bit squash + ST_MAX
            // clamp) vs the f64-ideal (unclamped logistic of the raw dot). The
            // gap = exact ceiling recoverable by widening the stretch domain /
            // raising probability resolution, per bit outcome.
            let pq = (self.pmix as f64 / PSCALE as f64).clamp(1e-9, 1.0 - 1e-9);
            let pi =
                (1.0 / (1.0 + (-(self.l2.raw as f64) / ST_SCALE).exp())).clamp(1e-9, 1.0 - 1e-9);
            self.q_bits += -if y == 1 { pq } else { 1.0 - pq }.log2();
            self.i_bits += -if y == 1 { pi } else { 1.0 - pi }.log2();
        }
        for m in 0..NL1 {
            self.l1[m].update(&self.st, y);
        }
        self.l2.update(&self.l2in, y);
        for k in 0..NORD {
            self.ord[k].upd(self.cxs[k], self.ostate[k], y, &self.nex);
        }
        for s in 0..NSPARSE {
            self.sp[s].upd(self.spcx[s], self.spstate[s], y, &self.nex);
        }
        self.ind.upd(self.indcx, self.indstate, y, &self.nex);
        self.wtab.upd(self.word_cx, self.wordstate, y, &self.nex);
        self.wtab2.upd(self.word2_cx, self.word2state, y, &self.nex);
        self.wtab3.upd(self.word3_cx, self.word3state, y, &self.nex);
        self.wtab4.upd(self.word4_cx, self.word4state, y, &self.nex);
        self.m1.update(y);
        self.m2.update(y);
        self.m3.update(y);
        self.apm1.upd(self.apm1_idx, y);
        if self.apm2_idx != usize::MAX {
            self.apm2.upd(self.apm2_idx, y);
        }
    }

    fn end_byte(&mut self, buf: &[u8]) {
        let t = buf.len() - 1;
        let b = buf[t];
        // indirect map: fold the new byte into this order-2 context's history
        let h = (self.ind_map[self.ind_key])
            .wrapping_mul(0x6F4A_7C13)
            .wrapping_add(b as u32 + 1);
        self.ind_map[self.ind_key] = h;
        // word model state
        if b.is_ascii_alphanumeric() {
            self.word_hash = self
                .word_hash
                .wrapping_mul(0x6F4A_7C13)
                .wrapping_add(b as u32 + 1);
            self.word_lc = self
                .word_lc
                .wrapping_mul(0x6F4A_7C13)
                .wrapping_add(b.to_ascii_lowercase() as u32 + 1);
        } else {
            // word boundary: remember the just-completed word for the bigram model
            if self.word_hash != 0 {
                self.prev_word = self.word_hash;
                self.prev_word_lc = self.word_lc;
            }
            self.word_hash = 0;
            self.word_lc = 0;
        }
        self.m1.end(buf);
        self.m2.end(buf);
        self.m3.end(buf);
    }
}

/// Encode `data`. Wire: `[orig_len u64 BE][bit-range-coded]`.
pub(crate) fn cm2_encode(data: &[u8]) -> Vec<u8> {
    cm2_encode_audit(data).0
}

/// Encode, also returning the FH2-06 quant-audit `(quant_bits, ideal_bits)` (both
/// 0 unless `CM_AUDIT=1`). The wire bytes are identical to [`cm2_encode`].
pub(crate) fn cm2_encode_audit(data: &[u8]) -> (Vec<u8>, f64, f64) {
    let mut out = (data.len() as u64).to_be_bytes().to_vec();
    let mut model = CmModel::new(tbits_for(data.len()));
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
            model.update_bit(y);
            c0 = (c0 << 1) | (y as usize);
        }
        buf.push(byte);
        model.end_byte(&buf);
    }
    out.extend_from_slice(&enc.finish());
    (out, model.q_bits, model.i_bits)
}

/// Decode a blob produced by [`cm2_encode`]. Fail-closed on a truncated header.
pub(crate) fn cm2_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 8 {
        return Err(CubrimError::Decode("MODE_CM2: header truncated".into()));
    }
    let orig_len = u64::from_be_bytes(blob[..8].try_into().unwrap());
    // QA-F-001 fail-closed guard (part 1 — decompression-bomb cap): a corrupt MODE_CM2
    // blob can carry an attacker-controlled orig_len up to 2^64. Reject anything beyond a
    // sane absolute maximum before allocating or looping, so the classic 2^64 claim fails
    // in O(1) instead of driving an unbounded loop + OOM.
    if orig_len > crate::codec::MAX_DECODE_LEN as u64 {
        return Err(CubrimError::Decode(format!(
            "MODE_CM2: orig_len {orig_len} exceeds maximum {}",
            crate::codec::MAX_DECODE_LEN
        )));
    }
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = CmModel::new(tbits_for(orig_len as usize));
    let mut dec = RangeDecoder::new(&blob[8..]);
    // QA-F-001 fail-closed guard (part 2 — stall detector): once the coded stream is
    // exhausted the range decoder only reads zero-padding and stops consuming input, yet
    // the loop would keep fabricating bytes toward orig_len. Track output produced since
    // the decoder last consumed a real input byte; a valid stream never stalls beyond the
    // renormalization run-length (a few KB even for maximally-compressible data), so a long
    // stall means the stream is truncated/corrupt -> fail closed with Err.
    let mut last_progress = dec.progress();
    let mut stall: u64 = 0;
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
            model.update_bit(y);
            byte = (byte << 1) | (y as u8);
            c0 = (c0 << 1) | (y as usize);
        }
        out.push(byte);
        model.end_byte(&out);
        // Stall accounting (QA-F-001 part 2).
        let p = dec.progress();
        if p != last_progress {
            last_progress = p;
            stall = 0;
        } else {
            stall += 1;
            if stall > CM2_STALL_LIMIT {
                return Err(CubrimError::Decode(
                    "MODE_CM2: coded stream exhausted before orig_len bytes decoded".into(),
                ));
            }
        }
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

    // QA-F-001 (branch F adversarial-QA): a MODE_CM2 blob whose 8-byte orig_len header
    // claims a gigantic length but whose coded stream is short must fail-closed with Err
    // in bounded time/memory — NOT hang or grow `out` toward OOM. Regression guard for the
    // fixed unbounded length-driven decode loop.
    #[test]
    fn cm2_decode_bogus_orig_len_is_err_not_oom() {
        // orig_len = u64::MAX, followed by a tiny coded stub.
        let mut blob = vec![0xFFu8; 8];
        blob.extend_from_slice(&[0x00, 0x11, 0x22, 0x33, 0x44]);
        let r = cm2_decode(&blob);
        assert!(
            r.is_err(),
            "cm2_decode must reject bogus orig_len, got Ok(len={})",
            r.map(|v| v.len()).unwrap_or(0)
        );
    }

    // QA-F-001: orig_len UNDER the absolute cap but with a truncated coded stream must
    // also fail closed via the stall detector (bounded work), not hang or grow unbounded.
    #[test]
    fn cm2_decode_truncated_stream_stalls_to_err() {
        // Valid blob for a compressible input, then rewrite orig_len to a large value
        // (< CM2_MAX_DECODE_LEN) the short coded stream cannot satisfy.
        let mut blob = cm2_encode(&vec![0u8; 4096]);
        // Claim more than the coded stream can supply (but small enough that the CM model
        // sizing stays cheap for the test); the stall detector must still fail it closed.
        let bogus: u64 = 200_000;
        blob[..8].copy_from_slice(&bogus.to_be_bytes());
        let r = cm2_decode(&blob);
        assert!(
            r.is_err(),
            "truncated CM2 stream must fail closed, got Ok(len={})",
            r.map(|v| v.len()).unwrap_or(0)
        );
    }

    // The exhaustion guard must never break a VALID round-trip: for real blobs the coded
    // stream is long enough that input_exhausted() only trips (if ever) after the final
    // byte is emitted. Exercise a range of sizes incl. the highly-compressible tail where
    // the decoder rides closest to the end of input.
    #[test]
    fn cm2_guard_preserves_valid_roundtrip() {
        for d in [
            vec![],
            vec![0u8; 1],
            vec![0u8; 4096],           // maximally compressible — shortest coded stream
            vec![0x5Au8; 1000],
            b"lorem ipsum dolor sit amet ".repeat(200),
        ] {
            let blob = cm2_encode(&d);
            let out = cm2_decode(&blob).expect("valid cm2 blob must decode");
            assert_eq!(out, d, "guard broke valid RT for len {}", d.len());
        }
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

    #[test]
    #[ignore]
    fn self_probe() {
        let path = std::env::var("CUBR_PROBE_FILE").expect("set CUBR_PROBE_FILE");
        let mut data = std::fs::read(&path).expect("read");
        if let Ok(l) = std::env::var("CUBR_PROBE_LIMIT") {
            data.truncate(l.parse().expect("limit"));
        }
        let n = data.len() as f64;
        let (blob, q_bits, i_bits) = cm2_encode_audit(&data);
        let out = cm2_decode(&blob).expect("decode");
        let rt = out == data;
        // FH2-06 quant-audit: recoverable ceiling from removing the mixer-output
        // ST_MAX clamp + 12-bit squash quant (i.e. widening the stretch domain).
        let q_bytes = q_bits / 8.0;
        let i_bytes = i_bits / 8.0;
        let ceiling_pct = if q_bytes > 0.0 {
            (q_bytes - i_bytes) / (blob.len() as f64) * 100.0
        } else {
            0.0
        };
        println!(
            "CM2-PROBE file={} n={} cm2={} ratio={:.9} rt_cmp0={} \
             vs_champion_0.229919={:+.6} vs_floor_0.2253={:+.6} \
             audit_q_bytes={:.0} audit_i_bytes={:.0} audit_ceiling_pct={:.4}",
            path,
            data.len(),
            blob.len(),
            blob.len() as f64 / n,
            rt,
            blob.len() as f64 / n - 0.229919,
            blob.len() as f64 / n - 0.2253,
            q_bytes,
            i_bytes,
            ceiling_pct,
        );
        assert!(rt, "self-probe RT cmp!=0");
    }
}
