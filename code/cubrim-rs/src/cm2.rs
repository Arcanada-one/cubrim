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

// Exact reciprocal-multiply replacement for the two per-bit count-adaptive
// divisions (`Ctr::upd` and `StateMap::upd`). Each decoded bit performs 46
// variable-divisor integer divisions on the serial update path; `idiv` is the
// longest-latency scalar op in that path. A division by d in a known range
// with a bounded numerator is computed exactly as `(n * ceil(2^K / d)) >> K`,
// by the Granlund–Montgomery bound: with m = ceil(2^K/d), the shift is exact
// floor division for every 0 <= n <= N provided N*(m*d - 2^K) < 2^K. Rust's
// `/` truncates toward zero, so negative numerators go through the same
// unsigned path on |n| and are negated — identical results bit for bit, which
// the table constructor asserts per divisor and the byte-identity gate
// verifies end to end.
const CTR_RECIP_K: u32 = 24; // numerator bound PSCALE, divisors 2..=256
const SM_RECIP_K: u32 = 33; // numerator bound 2^22, divisors 2..=1025

fn ctr_recip() -> &'static [u32; 257] {
    use std::sync::OnceLock;
    static T: OnceLock<[u32; 257]> = OnceLock::new();
    T.get_or_init(|| {
        let mut t = [0u32; 257];
        for d in 2..=256u64 {
            let m = (1u64 << CTR_RECIP_K).div_ceil(d);
            assert!(
                (PSCALE as u64) * (m * d - (1u64 << CTR_RECIP_K)) < (1u64 << CTR_RECIP_K),
                "ctr reciprocal inexact for divisor {d}"
            );
            t[d as usize] = m as u32;
        }
        t
    })
}

fn sm_recip() -> &'static [u64; 1026] {
    use std::sync::OnceLock;
    static T: OnceLock<[u64; 1026]> = OnceLock::new();
    T.get_or_init(|| {
        let mut t = [0u64; 1026];
        for d in 2..=1025u128 {
            let m = (1u128 << SM_RECIP_K).div_ceil(d);
            assert!(
                (1u128 << 22) * (m * d - (1u128 << SM_RECIP_K)) < (1u128 << SM_RECIP_K),
                "statemap reciprocal inexact for divisor {d}"
            );
            t[d as usize] = m as u64;
        }
        t
    })
}

/// Exact `n / d` (truncated toward zero) for `|n| <= PSCALE`, `2 <= d <= 256`.
#[inline]
fn ctr_div(n: i32, d: i32) -> i32 {
    let m = ctr_recip()[d as usize] as u64;
    if n >= 0 {
        ((n as u64 * m) >> CTR_RECIP_K) as i32
    } else {
        -(((n.unsigned_abs() as u64 * m) >> CTR_RECIP_K) as i32)
    }
}

/// Exact `n / d` (truncated toward zero) for `|n| <= 2^22`, `2 <= d <= 1025`.
#[inline]
fn sm_div(n: i64, d: i64) -> i64 {
    let m = sm_recip()[d as usize];
    if n >= 0 {
        ((n as u64 * m) >> SM_RECIP_K) as i64
    } else {
        -(((n.unsigned_abs() * m) >> SM_RECIP_K) as i64)
    }
}

// QA-F-001 fail-closed decode guards (branch F adversarial-QA).
// Maximum output bytes produced without the range decoder consuming a new input byte. A
// valid stream never rides longer than the renormalization run-length: with PSCALE=4096
// and the mixer/APM predictions clamped to ST_MAX, the per-symbol probability stays bounded
// away from 1, so renorm reads recur within well under ~6 KB even for maximally-compressible
// data. 64 KiB is an ~11x safety margin and bounds a truncated stream's fabricated output
// (and decode time) to 64 KiB before it fails closed.
const CM2_STALL_LIMIT: u64 = 1 << 16;

// QA-F-007 expansion bound: the declared orig_len sizes BOTH the output vector and the CM
// hash tables (`tbits_for(orig_len)`, up to TBITS_MAX=27 ≈ multi-GB) — and it did so BEFORE
// any content was validated, so a 214-byte crafted blob drove RSS to 6.3 GB and only failed
// closed afterwards (on a memory-limited host: OOM before Err). A real coded stream of
// `coded_len` bytes cannot expand past a bounded factor, so reject any claim beyond it up
// front — this also closes the CM2 model-amplification (a big model now requires
// proportionally many real coded bytes).
//
// Calibrated by measurement, not guesswork (cm2_encoder_output_satisfies_expansion_bound
// pins it): the worst real CM2 ratios are all-zeros/short-period repeats, which asymptote
// around ~2400x (zeros 64K 1820x, 1M 2346x, 8M 2387x — only +1.7% for 8x the size).
// 10000x is a >4x margin over the measured worst, so no legitimate high-ratio input is
// rejected, while the practical amplification from a tiny blob is gone.
const CM2_MAX_EXPANSION: u64 = 10_000;
/// Additive slack so short streams (whose model is still warming up, hence a low ratio)
/// and the minimal-blob edge are never rejected.
const CM2_EXPANSION_SLACK: u64 = 1 << 16;

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
        let mut d = if loser > 2 {
            2 + ((loser - 2) >> 1)
        } else {
            loser
        };
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
        self.t[s] = (cur + sm_div(tgt - cur, c + 2)) as u32;
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
const CTR_PROB_BIAS: u32 = (PSCALE / 2) as u32;

struct Ctr {
    // One packed 4-byte record per slot — bits 16..32 stationary prob (u16),
    // XOR-biased by the initial midpoint so an untouched record is all-zero;
    // bits 8..16 count (u8), bits 0..8 bit-history state (u8). predict() and
    // upd() hit the same hashed index in what were three parallel arrays; a
    // single record makes that one cache line instead of two (predict) or
    // three (update). Total memory per table is unchanged (4 B/slot either
    // way) and the unpacked values are bit-for-bit the old ones, so emitted
    // bytes cannot change.
    v: Vec<u32>,
    sm: StateMap,
    mask: usize,
    lim: i32,
}
impl Ctr {
    fn new(bits: usize, lim: i32, sm_cap: i32) -> Self {
        Self {
            v: vec![0u32; 1usize << bits],
            sm: StateMap::new(256, sm_cap.clamp(2, 1023) as u16),
            mask: (1usize << bits) - 1,
            lim,
        }
    }
    /// Predict: returns (stationary 12-bit prob, state-map 12-bit prob, state).
    /// The state is fed back to [`Ctr::upd`].
    #[inline]
    fn predict(&self, cx: usize) -> (i32, i32, u8) {
        let w = self.v[cx & self.mask];
        let s = (w & 0xFF) as u8;
        (
            ((w >> 16) ^ CTR_PROB_BIAS) as i32,
            self.sm.p12(s as usize).clamp(1, PSCALE - 1),
            s,
        )
    }
    #[inline]
    fn upd(&mut self, cx: usize, state: u8, y: i32, nex: &[[u8; 2]]) {
        let i = cx & self.mask;
        let w = self.v[i];
        // stationary count-adaptive counter (identical to the pre-StateMap codec)
        let cur = ((w >> 16) ^ CTR_PROB_BIAS) as i32;
        let cnt = ((w >> 8) & 0xFF) as i32;
        let t = (cur + ctr_div(y * PSCALE - cur, cnt + 2)).clamp(1, PSCALE - 1) as u32;
        let c = if cnt < self.lim {
            (cnt + 1) as u32
        } else {
            cnt as u32
        };
        // nonstationary bit-history state machine + StateMap
        self.sm.upd(state as usize, y);
        let st = nex[state as usize][y as usize] as u32;
        self.v[i] = ((t ^ CTR_PROB_BIAS) << 16) | (c << 8) | st;
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

// FH4-03 column-position model — a VARIANT-only pair of inputs appended after
// every existing model, so the default configuration keeps each index and its
// mixer input count bit-for-bit unchanged (the mixers read only their own `nin`).
// Enabled only when a record delimiter with stable spacing is detected.
const COL_I: usize = NMODELS; // stationary column prob
const SM_COL_I: usize = COL_I + 1; // state-map column prob
const NIN_COL: usize = SM_COL_I + 1 + 1; // + bias
const NIN_MAX: usize = NIN_COL;
const COL_CAP: usize = 63; // bytes-since-delimiter cap (Gotcha #9: keep cells learnable)

const TBITS_MAX: usize = 27; // hash-table cap (~12 GB/model at the max)
/// Size the per-model hash tables to the input length: ceil(log2(len)) + 3,
/// clamped to [18, TBITS_MAX]. Large files (enwik8, dickens) get the full 27
/// (the collision-free ratio win); small files use small tables (no memory /
/// init-time waste). The decoder derives the identical value from `orig_len` in
/// the wire header, so the round trip stays byte-exact.
fn tbits_for(len: usize) -> usize {
    tbits_cap().map_or_else(
        || tbits_for_uncapped(len),
        |cap| tbits_for_uncapped(len).min(cap),
    )
}

/// The exponent a length derives on its own, before any cap. The encoder
/// compares against this to decide whether the blob needs to carry an explicit
/// exponent at all: when nothing was capped the field stays 0 and the blob is
/// byte-identical to one written before the field existed.
fn tbits_for_uncapped(len: usize) -> usize {
    let ceil_log2 = (usize::BITS - (len.max(2) - 1).leading_zeros()) as usize;
    (ceil_log2 + 3).clamp(18, TBITS_MAX)
}

/// Development knob for the memory/ratio/throughput sweep: caps the per-model
/// hash-table exponent, so `CUBRIM_CM2_TBITS=23` makes every model at most
/// 2^23 entries (~0.85 GiB total instead of 13.5 GiB at the 27 cap).
///
/// A cap, never a raise: it can only shrink the tables a file would otherwise
/// get, so it cannot push a small input past its own derived size.
///
/// **This is a measurement instrument, not a shipping feature.** Because the
/// decoder derives its table size from the same function, an archive written
/// under one cap is only decodable under the same cap — the size is not in the
/// wire format. Any production memory knob must therefore record the exponent
/// in the header (or bind it to a preset byte) rather than read the
/// environment; until then this stays a sweep-only override.
fn tbits_cap() -> Option<usize> {
    use std::sync::OnceLock;
    static CAP: OnceLock<Option<usize>> = OnceLock::new();
    *CAP.get_or_init(|| {
        std::env::var("CUBRIM_CM2_TBITS")
            .ok()
            .and_then(|v| v.trim().parse::<usize>().ok())
            .map(|v| v.clamp(12, TBITS_MAX))
    })
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
    // FH4-03 column-position model — None on the default path
    col: Option<Ctr>,
    col_delim: u8,
    col_pos: usize,
    col_hash: usize,
    col_cx: usize,
    col_state: u8,
    nin: usize,
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
    st: [i32; NIN_MAX],
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
    /// `col_delim = Some(d)` enables the FH4-03 column-position model keyed on
    /// bytes-since-`d`. `None` reproduces the default model set exactly.
    fn new_with_col(tbits: usize, col_delim: Option<u8>) -> Self {
        let nin = if col_delim.is_some() { NIN_COL } else { NIN };
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
            sp: (0..NSPARSE)
                .map(|_| Ctr::new(tbits, ctrlim, smcap))
                .collect(),
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
            col: col_delim.map(|_| Ctr::new(tbits, ctrlim, smcap)),
            col_delim: col_delim.unwrap_or(0),
            col_pos: 0,
            col_hash: 0,
            col_cx: 0,
            col_state: 0,
            nin,
            // layer-1 mixers over NIN inputs, distinct context selectors; layer 2
            // combines their NL1 stretched outputs (+bias).
            l1: vec![
                Mixer::new(256, nin, ws),  // prev byte
                Mixer::new(1024, nin, ws), // order-2 hash
                Mixer::new(64, nin, ws),   // match state
                Mixer::new(256, nin, ws),  // partial byte c0
                Mixer::new(1024, nin, ws), // order-3 hash
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
            st: [0; NIN_MAX],
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
        // FH4-03: column context = (bytes since the record delimiter, previous byte).
        // The probe measured this pair as the carrier — position alone was weaker.
        if self.col.is_some() {
            self.col_hash = (self.col_pos.min(COL_CAP))
                .wrapping_mul(0x9E37_79B1)
                .wrapping_add(self.prev.wrapping_mul(0x85EB_CA77));
        }
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
        // FH4-03: column-position inputs sit after every default model, so the
        // bias moves to nin-1 and the default layout is untouched.
        if let Some(col) = self.col.as_mut() {
            let ccx = self.col_hash.wrapping_mul(0x2545_F491).wrapping_add(c0);
            self.col_cx = ccx;
            let (cps, cpsm, cst) = col.predict(ccx);
            self.col_state = cst;
            self.st[COL_I] = self.lg.stretch(cps);
            self.st[SM_COL_I] = self.lg.stretch(cpsm);
        }
        self.st[self.nin - 1] = 256; // bias

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
        if let Some(col) = self.col.as_mut() {
            col.upd(self.col_cx, self.col_state, y, &self.nex);
        }
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
        // FH4-03: advance the within-record position (reset on the delimiter).
        if self.col.is_some() {
            self.col_pos = if b == self.col_delim {
                0
            } else {
                self.col_pos.saturating_add(1)
            };
        }
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

/// Skip the FH4-03 column-model variants and emit the base CM2 encode only.
///
/// `cm2_encode` runs one full CM2 pass per candidate column delimiter on top of
/// the base pass (up to `MAX = 2` extra passes), while the decoder replays
/// exactly one — measured as the bulk of the encode/decode asymmetry. This knob
/// exists to price that sweep: how much ratio do the extra passes actually buy?
///
/// Unlike the table-size cap, this one is **wire-compatible in both
/// directions**: the column model and its delimiter are recorded in the blob's
/// length header, so a base-only blob decodes under any build, and an archive
/// written with the sweep enabled still decodes when it is disabled. That makes
/// it a legitimate candidate for a speed preset rather than a sweep-only
/// override — but it costs ratio wherever a column variant would have won, so
/// it must never be the default without that trade measured and recorded.
fn skip_col_variants() -> bool {
    use std::sync::OnceLock;
    static SKIP: OnceLock<bool> = OnceLock::new();
    *SKIP.get_or_init(|| {
        std::env::var("CUBRIM_CM2_NO_COL")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false)
    })
}

/// Encode `data`. Wire: `[orig_len u64 BE][bit-range-coded]`.
#[cfg(test)]
pub(crate) fn cm2_encode(data: &[u8]) -> Vec<u8> {
    cm2_encode_with(data, true, None)
}

/// `cm2_encode`, with the FH4-03 column-variant sweep under caller control.
///
/// `column_variants = false` emits the base variant only. Wire-compatible in both
/// directions — the column flag and delimiter live in the blob's length header —
/// so this changes cost and ratio, never decodability. See
/// `EncodeConfig::cm2_column_variants` for the measured price.
pub(crate) fn cm2_encode_with(
    data: &[u8],
    column_variants: bool,
    max_tbits: Option<usize>,
) -> Vec<u8> {
    let base = crate::prof::track(
        "cm2_variant_base",
        |v: &Vec<u8>| v.len(),
        || cm2_encode_variant(data, None, max_tbits),
    );
    // FH4-03: competitive-min. The column variant ships only when it is strictly
    // smaller, so adding it cannot regress any input — the gate above merely
    // avoids paying for a candidate that has no chance.
    let mut best = base;
    crate::prof::win("cm2_variant_base");
    // The environment override stays as a sweep instrument and can only ever
    // *disable* the sweep, so it cannot re-enable what a preset turned off.
    if !column_variants || skip_col_variants() {
        return best;
    }
    for d in detect_col_delims(data) {
        let alt = crate::prof::track(
            "cm2_variant_col",
            |v: &Vec<u8>| v.len(),
            || cm2_encode_variant(data, Some(d), max_tbits),
        );
        if alt.len() < best.len() {
            best = alt;
            crate::prof::win("cm2_variant_col");
        }
    }
    best
}

/// Encode, also returning the FH2-06 quant-audit `(quant_bits, ideal_bits)` (both
/// 0 unless `CM_AUDIT=1`). The wire bytes are identical to [`cm2_encode`].
// FH4-03 wire packing. MAX_DECODE_LEN is 1<<40, so the top bits of the 8-byte
// length header are unused: bit 63 flags the column model and bits 48..55 carry
// its delimiter. A blob written without the model leaves both zero, so every
// archive produced before this existed still decodes byte-identically.
const CM2_COL_FLAG: u64 = 1 << 63;
const CM2_COL_DELIM_SHIFT: u32 = 48;
const CM2_LEN_MASK: u64 = (1u64 << 48) - 1;

// CUBR-0087 (NEW-27) wire packing: the model table exponent, in bits 56..60.
//
// Why this has to be in the blob. `cm2_decode` sized its tables by calling
// `tbits_for(orig_len)` — the *same* derivation the encoder used — so the
// exponent was implied, not transmitted, and a decoder had no way to be told to
// use less. Measured consequence (DB `meta_id=35`): decoding a file of ≥16 MB
// takes ~12.3 GiB of model tables, allocated before any decoding happens.
// `wasm32` has a 4 GiB address space, so the web-codec decoder could not exist
// at any size that matters. Making the exponent explicit is what unblocks it.
//
// Backward compatible in the only direction that can be: **0 means "derive as
// before"**. Every archive written before this existed leaves these bits zero
// and decodes byte-identically, and nothing about the default path changes.
//
// **The explicit value may only SHRINK the derived one, never grow it** — see
// `effective_tbits`. Dropping that clamp would hand back the QA-F-007
// model-amplification vector: a 214-byte crafted blob could ask for 2^27 tables
// and drive RSS to gigabytes before any content was validated. The clamp is the
// reason this is a safe field to add rather than a new attack surface.
const CM2_TBITS_SHIFT: u32 = 56;
const CM2_TBITS_MASK: u64 = 0x1F; // 5 bits: 0 = derive, else 12..=27

/// Resolve the table exponent for a blob: the derived size, lowered by the
/// blob's declared exponent when it carries one.
///
/// Never raises. An out-of-range or larger-than-derived declaration is ignored
/// rather than rejected, because a decoder that merely uses *more accurate*
/// tables than requested still decodes correctly — the exponent only has to
/// match between encoder and decoder, and both call this function.
fn effective_tbits(orig_len: usize, declared: u64) -> usize {
    let derived = tbits_for(orig_len);
    let d = (declared >> CM2_TBITS_SHIFT) & CM2_TBITS_MASK;
    if d == 0 {
        return derived;
    }
    (d as usize).clamp(12, TBITS_MAX).min(derived)
}

/// FH4-03 gate: propose record-delimiter candidates whose spacing is regular
/// enough that a within-record position is a meaningful context.
///
/// Returns up to `MAX` candidates, best (most regular) first. Precision is NOT
/// required: the encoder competes every candidate and keeps the winner, recording
/// its delimiter in the header, so a bad proposal costs encode time and never
/// ratio. The gate therefore errs toward proposing — a threshold tight enough to
/// be "correct" silently dropped nci, whose newline spacing varies more than a
/// strict regularity test allows (CV 0.64) yet still carries a 5% column signal.
fn detect_col_delims(data: &[u8]) -> Vec<u8> {
    const SAMPLE: usize = 1 << 18;
    const MAX: usize = 2;
    let s = &data[..data.len().min(SAMPLE)];
    if s.len() < 4096 {
        return Vec::new();
    }
    let mut count = [0u32; 256];
    for &b in s {
        count[b as usize] += 1;
    }
    let mut scored: Vec<(f64, u8)> = Vec::new();
    for cand in 0..256usize {
        if (count[cand] as usize) < 32 {
            continue;
        }
        let mean = s.len() as f64 / count[cand] as f64;
        if !(4.0..=512.0).contains(&mean) {
            continue;
        }
        let (mut prev, mut sum, mut sumsq, mut k) = (0usize, 0f64, 0f64, 0usize);
        for (i, &b) in s.iter().enumerate() {
            if b as usize == cand {
                let g = (i - prev) as f64;
                sum += g;
                sumsq += g * g;
                k += 1;
                prev = i;
            }
        }
        if k < 32 {
            continue;
        }
        let m = sum / k as f64;
        let var = (sumsq / k as f64 - m * m).max(0.0);
        let cv = var.sqrt() / m.max(1.0);
        if cv <= 1.2 {
            scored.push((cv, cand as u8));
        }
    }
    scored.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then(a.1.cmp(&b.1)));
    scored.into_iter().take(MAX).map(|(_, d)| d).collect()
}

// Intentionally unused in production: this is the manual audit instrument
// exercised only by the ignored `self_probe` test.
#[allow(dead_code)]
pub(crate) fn cm2_encode_audit(data: &[u8]) -> (Vec<u8>, f64, f64) {
    cm2_encode_audit_variant(data, None)
}

fn cm2_encode_variant(data: &[u8], col_delim: Option<u8>, max_tbits: Option<usize>) -> Vec<u8> {
    cm2_encode_audit_variant_with(data, col_delim, max_tbits).0
}

// Intentionally unused outside the manual audit instrument above; keep it for
// the ignored `self_probe` test without hiding unrelated dead code.
#[allow(dead_code)]
fn cm2_encode_audit_variant(data: &[u8], col_delim: Option<u8>) -> (Vec<u8>, f64, f64) {
    cm2_encode_audit_variant_with(data, col_delim, None)
}

fn cm2_encode_audit_variant_with(
    data: &[u8],
    col_delim: Option<u8>,
    max_tbits: Option<usize>,
) -> (Vec<u8>, f64, f64) {
    let mut hdr = data.len() as u64;
    if let Some(d) = col_delim {
        hdr |= CM2_COL_FLAG | ((d as u64) << CM2_COL_DELIM_SHIFT);
    }
    // NEW-27: declare the table exponent when it is smaller than the derived
    // one, so the decoder can allocate the same reduced model instead of
    // re-deriving the full-size one. `tbits_for` already applies the sweep cap,
    // so writing what it returns keeps encoder and decoder in step by
    // construction — there is no second source of the number to drift from.
    let tb = max_tbits.map_or_else(
        || tbits_for(data.len()),
        |cap| tbits_for(data.len()).min(cap.clamp(12, TBITS_MAX)),
    );
    if tb < tbits_for_uncapped(data.len()) {
        hdr |= (tb as u64 & CM2_TBITS_MASK) << CM2_TBITS_SHIFT;
    }
    let mut out = hdr.to_be_bytes().to_vec();
    let mut model = CmModel::new_with_col(tb, col_delim);
    let mut enc = RangeEncoder::new();
    let mut buf: Vec<u8> = Vec::with_capacity(data.len());
    // M1 (pre-registered by the CUBR-0087 consilium): split the per-bit budget
    // between the model — predict + update over 24 hash-indexed tables — and the
    // range coder that consumes the model's probability. The consilium's kill rule
    // for NEW-22 (SIMD rANS) is "coder share < 25% => cancelled on the CM path",
    // so the share has to be a measurement, not an estimate.
    //
    // Timed in place rather than by stubbing the coder: a null coder emits no
    // bytes, which changes every downstream competitive comparison and therefore
    // measures a different encoder. This costs two `Instant::now()` per bit while
    // enabled (~20 ns each, ~0.7 s per 2 MB against a ~140 s encode) and **emits
    // byte-identical output**, so the split is measured on the real path.
    let time_coder = coder_timing_enabled();
    let mut coder_nanos: u128 = 0;
    let mut model_nanos: u128 = 0;
    for &byte in data {
        model.start_byte(&buf);
        let mut c0 = 1usize;
        for bit in 0..8u32 {
            let y = ((byte >> (7 - bit)) & 1) as i32;
            if time_coder {
                let t0 = std::time::Instant::now();
                let pf = model.predict_bit(c0, bit);
                let t1 = std::time::Instant::now();
                if y == 1 {
                    enc.encode(0, pf as u32, PSCALE as u32);
                } else {
                    enc.encode(pf as u32, (PSCALE - pf) as u32, PSCALE as u32);
                }
                let t2 = std::time::Instant::now();
                model.update_bit(y);
                let t3 = std::time::Instant::now();
                coder_nanos += (t2 - t1).as_nanos();
                model_nanos += (t1 - t0).as_nanos() + (t3 - t2).as_nanos();
            } else {
                let pf = model.predict_bit(c0, bit);
                if y == 1 {
                    enc.encode(0, pf as u32, PSCALE as u32);
                } else {
                    enc.encode(pf as u32, (PSCALE - pf) as u32, PSCALE as u32);
                }
                model.update_bit(y);
            }
            c0 = (c0 << 1) | (y as usize);
        }
        buf.push(byte);
        model.end_byte(&buf);
    }
    if time_coder {
        let total = (coder_nanos + model_nanos) as f64;
        eprintln!(
            "CM2-BIT-SPLIT bytes={} model_s={:.3} coder_s={:.3} coder_share={:.2}%",
            data.len(),
            model_nanos as f64 / 1e9,
            coder_nanos as f64 / 1e9,
            if total > 0.0 {
                100.0 * coder_nanos as f64 / total
            } else {
                0.0
            }
        );
    }
    out.extend_from_slice(&enc.finish());
    (out, model.q_bits, model.i_bits)
}

/// Enable the M1 per-bit model/coder split (`CUBRIM_PROFILE_CODER=1`).
fn coder_timing_enabled() -> bool {
    use std::sync::OnceLock;
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| {
        std::env::var("CUBRIM_PROFILE_CODER")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false)
    })
}

/// Decode a blob produced by [`cm2_encode`]. Fail-closed on a truncated header.
pub(crate) fn cm2_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 8 {
        return Err(CubrimError::Decode("MODE_CM2: header truncated".into()));
    }
    // FH4-03: unpack the column-model flag/delimiter first, so every guard below
    // sees the true declared length and not the packed word.
    let raw = u64::from_be_bytes(blob[..8].try_into().unwrap());
    let col_delim = if raw & CM2_COL_FLAG != 0 {
        Some(((raw >> CM2_COL_DELIM_SHIFT) & 0xFF) as u8)
    } else {
        None
    };
    let orig_len = raw & CM2_LEN_MASK;
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
    // QA-F-007 expansion bound — MUST precede the output and model allocations below, since
    // both are sized from `orig_len`. Anything the coded stream cannot plausibly expand into
    // is rejected in O(1), before a single byte is reserved.
    let coded_len = (blob.len() - 8) as u64;
    let max_plausible = coded_len
        .saturating_mul(CM2_MAX_EXPANSION)
        .saturating_add(CM2_EXPANSION_SLACK);
    if orig_len > max_plausible {
        return Err(CubrimError::Decode(format!(
            "MODE_CM2: orig_len {orig_len} implausible for {coded_len} coded bytes \
             (max {max_plausible} at {CM2_MAX_EXPANSION}x expansion)"
        )));
    }
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = CmModel::new_with_col(effective_tbits(orig_len as usize, raw), col_delim);
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
    fn ctr_zero_representation_starts_zero_and_predicts_midpoint() {
        let ctr = Ctr::new(4, 15, 512);

        assert!(ctr.v.iter().all(|&word| word == 0));
        let (stationary, _, state) = ctr.predict(7);
        assert_eq!(stationary, PSCALE / 2);
        assert_eq!(state, 0);
    }

    #[test]
    fn ctr_zero_representation_update_preserves_logical_fields() {
        let mut ctr = Ctr::new(4, 15, 512);
        let nex = build_nex();
        let cx = 7;
        let (initial, _, state) = ctr.predict(cx);
        let expected = (initial + ctr_div(PSCALE - initial, 2)).clamp(1, PSCALE - 1) as u32;

        ctr.upd(cx, state, 1, &nex);

        let word = ctr.v[cx & ctr.mask];
        let (stationary, _, next_state) = ctr.predict(cx);
        assert_eq!(stationary, expected as i32);
        assert_eq!(next_state, nex[state as usize][1]);
        assert_eq!((word >> 8) & 0xFF, 1);
        assert_eq!(word >> 16, expected ^ ((PSCALE / 2) as u32));
    }

    /// QA-F-007 calibration guard: every blob the ENCODER can produce must satisfy the
    /// decoder's expansion bound. This is what makes CM2_MAX_EXPANSION safe — if a future
    /// model change pushes real ratios past it, this test fails instead of silently
    /// rejecting legitimate files at decode time. Reports the margin so drift is visible.
    #[test]
    fn cm2_encoder_output_satisfies_expansion_bound() {
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("zeros_4k", vec![0u8; 4096]),
            ("zeros_64k", vec![0u8; 65536]),
            ("zeros_256k", vec![0u8; 256 * 1024]),
            ("const_128k", vec![0x5Au8; 128 * 1024]),
            (
                "rep2_128k",
                (0..(128 * 1024)).map(|i| (i % 2) as u8).collect(),
            ),
            (
                "rep16_128k",
                (0..(128 * 1024)).map(|i| (i % 16) as u8).collect(),
            ),
            (
                "text_128k",
                b"the quick brown fox. "
                    .iter()
                    .cloned()
                    .cycle()
                    .take(128 * 1024)
                    .collect(),
            ),
        ];
        let mut worst_ratio = 0f64;
        for (name, data) in cases {
            let blob = cm2_encode(&data);
            let coded = (blob.len() - 8) as u64;
            let bound = coded
                .saturating_mul(CM2_MAX_EXPANSION)
                .saturating_add(CM2_EXPANSION_SLACK);
            let ratio = data.len() as f64 / coded.max(1) as f64;
            if ratio > worst_ratio {
                worst_ratio = ratio;
            }
            assert!(
                data.len() as u64 <= bound,
                "{name}: encoder produced orig={} from coded={coded}, exceeding the decoder \
                 bound {bound} (ratio {ratio:.1} vs CM2_MAX_EXPANSION {CM2_MAX_EXPANSION})",
                data.len()
            );
        }
        assert!(
            worst_ratio * 2.0 < CM2_MAX_EXPANSION as f64,
            "measured worst ratio {worst_ratio:.1} leaves under 2x margin below \
             CM2_MAX_EXPANSION {CM2_MAX_EXPANSION} — re-calibrate before shipping"
        );
    }

    /// QA-F-007: a tiny blob claiming a huge orig_len must be rejected BEFORE the output and
    /// CM-model allocations (which are sized from orig_len). Repro of the 214-byte blob that
    /// drove RSS to 6.3 GB and only failed closed afterwards.
    #[test]
    fn cm2_decode_implausible_expansion_is_err_before_alloc() {
        let mut blob = 5_000_000_000u64.to_be_bytes().to_vec();
        blob.extend_from_slice(&[0xA5u8; 200]); // 206 coded bytes total container payload
        let r = cm2_decode(&blob);
        let e = r.expect_err("implausible expansion must be rejected");
        assert!(
            e.to_string().contains("implausible"),
            "expected the expansion bound to fire, got: {e}"
        );
    }

    /// The stall guard protects a limit of CM2_STALL_LIMIT (65536) output bytes, but the
    /// shipped valid-RT test only covered 4096 bytes — structurally unable to execute the
    /// path it guards. This exercises a valid, maximally-compressible stream whose output is
    /// well ABOVE the stall limit (so long no-progress runs really occur) and whose ratio is
    /// near the measured worst case, proving neither the stall guard nor the expansion bound
    /// false-fires on legitimate high-ratio data.
    #[test]
    fn cm2_valid_high_ratio_above_stall_limit_round_trips() {
        for data in [
            vec![0u8; 128 * 1024],
            (0..(128 * 1024))
                .map(|i| (i % 2) as u8)
                .collect::<Vec<u8>>(),
        ] {
            assert!(
                data.len() as u64 > CM2_STALL_LIMIT,
                "fixture must exceed the guarded limit"
            );
            let blob = cm2_encode(&data);
            let out = cm2_decode(&blob).expect("valid high-ratio blob must decode");
            assert_eq!(out, data, "valid RT broken for len {}", data.len());
        }
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
            vec![0u8; 4096], // maximally compressible — shortest coded stream
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

    /// The reciprocal path must equal `/` exactly on its full declared domain:
    /// any divergence anywhere is a silent model change and therefore silent
    /// output drift. Ctr's domain is small enough to check exhaustively; the
    /// StateMap domain is checked at every divisor over the numerator extremes,
    /// dense low magnitudes, and a fixed stride across the full range (the
    /// per-divisor Granlund-Montgomery bound is asserted at table build).
    #[test]
    fn reciprocal_division_matches_idiv_exactly() {
        for d in 2..=256i32 {
            for n in -PSCALE..=PSCALE {
                assert_eq!(super::ctr_div(n, d), n / d, "ctr n={n} d={d}");
            }
        }
        let big = 1i64 << 22;
        for d in 2..=1025i64 {
            for n in (-big..=big).step_by(4093) {
                assert_eq!(super::sm_div(n, d), n / d, "sm n={n} d={d}");
            }
            for n in [-big, -big + 1, -1, 0, 1, big - 1, big] {
                assert_eq!(super::sm_div(n, d), n / d, "sm edge n={n} d={d}");
            }
        }
    }
}
