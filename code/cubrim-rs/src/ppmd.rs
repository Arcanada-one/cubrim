//! MODE_PPMD backend (CUBR-0059) — a real variable-order PPM/PPMd text model.
//!
//! Built incrementally under strict TDD; byte-exact round-trip (`cmp=0`) is the
//! invariant of every step. This module reuses the crate's existing carryless
//! range coder (`codec::RangeEncoder` / `RangeDecoder`, `total ≤ 2^16`) — no new
//! arithmetic coder (PRD D-REQ-02).
//!
//! Step 1 (coder-reuse harness): an order-0 adaptive byte model over the reused
//! range coder, proving the reuse wrapper round-trips byte-exact before the real
//! variable-order PPM/PPMd model (steps 3+) is layered on top.

// The public entry points are exercised by this module's own tests but are not
// wired into the codec's top-level dispatch until the `MODE_PPMD` integration
// (plan Phase 2, step 7). Until then they read as dead code to the lib build;
// this allow is REMOVED when the integration lands.
#![allow(dead_code)]

use crate::codec::{RangeDecoder, RangeEncoder};
use crate::error::CubrimError;

/// Rescale when the model total would exceed this. Kept well under the coder's
/// `RC_BOT = 2^16` precision cap so `total + inc` never reaches it.
const O0_RESCALE: u32 = 1 << 15;
/// Laplace increment per observation (effective smoothing alpha = 1/inc).
const O0_INC: u32 = 24;

/// Order-0 adaptive model over the 256-symbol byte alphabet.
struct ByteModelO0 {
    freq: [u32; 256],
    total: u32,
}

impl ByteModelO0 {
    fn new() -> Self {
        Self {
            freq: [1u32; 256],
            total: 256,
        }
    }
    /// Cumulative frequency strictly below symbol `s` (linear; alphabet ≤ 256).
    #[inline]
    fn cum_below(&self, s: usize) -> u32 {
        self.freq[..s].iter().sum()
    }
    #[inline]
    fn update(&mut self, s: usize) {
        self.freq[s] += O0_INC;
        self.total += O0_INC;
        if self.total >= O0_RESCALE {
            self.rescale();
        }
    }
    fn rescale(&mut self) {
        let mut t = 0u32;
        for f in self.freq.iter_mut() {
            *f = (*f >> 1) | 1; // halve, keep ≥ 1 so every symbol stays codable
            t += *f;
        }
        self.total = t;
    }
}

/// Encode `data` with the order-0 model. Wire: `[orig_len u64 BE][range-coded]`.
pub(crate) fn ppmd_o0_encode(data: &[u8]) -> Vec<u8> {
    let mut out = (data.len() as u64).to_be_bytes().to_vec();
    let mut model = ByteModelO0::new();
    let mut enc = RangeEncoder::new();
    for &b in data {
        let s = b as usize;
        let cum = model.cum_below(s);
        enc.encode(cum, model.freq[s], model.total);
        model.update(s);
    }
    out.extend_from_slice(&enc.finish());
    out
}

/// Decode a blob produced by [`ppmd_o0_encode`]. Fail-closed on truncation.
///
/// Full container-header validation (an untrusted-blob attack surface) lands
/// with the `MODE_PPMD` wiring in step 7; here we cap the pre-allocation so an
/// adversarial length field cannot force an OOM.
pub(crate) fn ppmd_o0_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 8 {
        return Err(CubrimError::Decode(
            "MODE_PPMD(o0): header truncated".into(),
        ));
    }
    let orig_len = u64::from_be_bytes(blob[..8].try_into().unwrap());
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = ByteModelO0::new();
    let mut dec = RangeDecoder::new(&blob[8..]);
    for _ in 0..orig_len {
        let f = dec.get_freq(model.total);
        // Locate the symbol whose cumulative interval contains `f`.
        let mut cum = 0u32;
        let mut s = 0usize;
        while s < 255 && cum + model.freq[s] <= f {
            cum += model.freq[s];
            s += 1;
        }
        dec.decode(cum, model.freq[s], model.total);
        out.push(s as u8);
        model.update(s);
    }
    Ok(out)
}

// ── Step 2: binary bit-coder primitive (SSE / escape primitive) ──────────────
// A single binary decision coded through the reused range coder via its A=2
// special case (`encode(0, p0, T)` for bit 0, `encode(p0, T-p0, T)` for bit 1).
// PPMd/PPMII escape and SEE decisions are binary events; this is their coder.

/// Probability scale for the binary coder — 12-bit, matching the crate's
/// existing `CmEncoder` (`p >> 12`). Well under the coder's `RC_BOT = 2^16` cap.
const BIT_TOTAL: u32 = 1 << 12;

/// Encode one `bit` given `p0` = P(bit == 0) in `[1, BIT_TOTAL-1]`.
#[inline]
fn encode_bit(enc: &mut RangeEncoder, bit: u8, p0: u32) {
    if bit == 0 {
        enc.encode(0, p0, BIT_TOTAL);
    } else {
        enc.encode(p0, BIT_TOTAL - p0, BIT_TOTAL);
    }
}

/// Decode one bit given the same `p0` the encoder used.
#[inline]
fn decode_bit(dec: &mut RangeDecoder, p0: u32) -> u8 {
    if dec.get_freq(BIT_TOTAL) < p0 {
        dec.decode(0, p0, BIT_TOTAL);
        0
    } else {
        dec.decode(p0, BIT_TOTAL - p0, BIT_TOTAL);
        1
    }
}

/// Adaptive binary probability state. `p0` = P(bit == 0), 12-bit, init centred.
/// Integer-only shift update (lpaq-style) — deterministic, no float.
struct BitModel {
    p0: u32,
}

impl BitModel {
    fn new() -> Self {
        Self { p0: BIT_TOTAL / 2 }
    }
    #[inline]
    fn predict(&self) -> u32 {
        self.p0
    }
    #[inline]
    fn update(&mut self, bit: u8) {
        const RATE: u32 = 5;
        if bit == 0 {
            self.p0 += (BIT_TOTAL - self.p0) >> RATE;
        } else {
            self.p0 -= self.p0 >> RATE;
        }
        // Keep both intervals non-empty (the coder needs freq ≥ 1 on each side).
        self.p0 = self.p0.clamp(1, BIT_TOTAL - 1);
    }
}

// ── Step 3: variable-order PPM skeleton (PPMC, escape method C) ───────────────
// A real variable-order PPM: per-order context stores, method-C escape, coding-
// time (partial) exclusion, order-ramp N→0→(-1). Correctness-first structure
// (deterministic BTreeMap context store); the Shkarin SubAllocator that makes it
// memory/speed-efficient lands in step 6. This is the model class where PPMd's
// superiority over the block-reset order-limited CM lives.

use std::collections::BTreeMap;

/// Per-context total cap — rescale (halve counts) when reached. Kept below the
/// coder's `RC_BOT = 2^16` cap with headroom for the method-C escape band (≤ 256).
/// Tuned from 2^14 to 2^13: on full-dickens o8 the more frequent count-halving
/// keeps the stats slightly fresher on the larger corpus (−39 B, RT cmp=0; inert
/// at 1 MiB). Overridable via `CUBR_PPM_RESCALE`.
const CTX_RESCALE: u32 = 1 << 13;
/// Count increment per observation — the effective Laplace smoothing is
/// `alpha = 1 / PPM_INC`. Tuned from 4 to 3 (softer smoothing) after a
/// count-scaling sweep: on full-dickens o8 this improved the ratio from
/// 0.230166 to 0.229923 (−0.106%, RT cmp=0). Overridable via `CUBR_PPM_INC`
/// for the gauge; the default IS the champion value.
const PPM_INC: u32 = 3;

/// SEE run-length ceiling probe: quantization of the SEE2 escape probability and
/// of the deterministic-run length into diagnostic buckets.
const SEE_PBUCKETS: usize = 16;
const SEE_RLBUCKETS: usize = 8;

/// Bucket the SEE2 escape probability by its bit-length (−log2 p), 0..15.
#[inline]
fn see_p_bucket(p_esc: f64) -> usize {
    let bits = -p_esc.max(1e-9).log2(); // ~0..30
    ((bits * 1.5) as usize).min(SEE_PBUCKETS - 1)
}

/// Bucket the deterministic-run length 0,1,2,3-4,5-8,9-16,17-32,33+.
#[inline]
fn see_rl_bucket(rl: u32) -> usize {
    match rl {
        0 => 0,
        1 => 1,
        2 => 2,
        3..=4 => 3,
        5..=8 => 4,
        9..=16 => 5,
        17..=32 => 6,
        _ => 7,
    }
}

/// Binary entropy (bits) of a Bernoulli(p) event, with 0·log0 = 0.
#[inline]
fn bin_entropy(p: f64) -> f64 {
    if p <= 0.0 || p >= 1.0 {
        0.0
    } else {
        -p * p.log2() - (1.0 - p) * (1.0 - p).log2()
    }
}

/// One PPM context: (symbol, count) stats in deterministic insertion order.
/// `last_used` is the model tick of the most recent update touching this context;
/// it drives least-recently-used eviction under the bounded-memory RESCALE policy
/// and is a pure function of the processed history (identical on encode/decode).
#[derive(Default)]
struct Ctx {
    stats: Vec<(u8, u32)>,
    total: u32,
    last_used: u64,
    /// Deterministic-run length: consecutive hits at this context since the last
    /// escape/creation. Causal (known before coding the next symbol). Diagnostic
    /// only in this branch — measured, not yet used for coding.
    det_run: u32,
}

impl Ctx {
    fn seeded(sym: u8, freq: u32) -> Self {
        Self {
            stats: vec![(sym, freq.max(1))],
            total: freq.max(1),
            last_used: 0,
            det_run: 0,
        }
    }

    #[inline]
    fn bump(&mut self, sym: u8, inc: u32, rescale_at: u32) {
        if let Some(e) = self.stats.iter_mut().find(|(s, _)| *s == sym) {
            e.1 += inc;
        } else {
            self.stats.push((sym, inc));
        }
        self.total += inc;
        if self.total >= rescale_at {
            self.rescale();
        }
    }
    fn rescale(&mut self) {
        let mut t = 0u32;
        for (_, c) in self.stats.iter_mut() {
            *c = (*c >> 1) | 1; // halve, keep ≥ 1 → distinct set (and method-C esc) stays stable
            t += *c;
        }
        self.total = t;
    }
}

/// Initial frequency for a newly-created successor, derived from its suffix
/// parent without copying the parent's symbol table (PPMd var.H update model).
fn successor_freq(parent: &Ctx, sym: u8) -> u32 {
    let Some((_, freq)) = parent.stats.iter().find(|(s, _)| *s == sym) else {
        return 1;
    };
    let cf = freq.saturating_sub(1);
    let s0 = parent.total.saturating_sub(cf).max(1);
    1 + if 2 * cf <= s0 {
        u32::from(5 * cf > s0)
    } else {
        (2 * cf + s0 - 1) / (2 * s0) + 1
    }
}

const LOE_DIRECT_ORDER: usize = 5;
const LOE_MID_ORDER: usize = 8;
const LOE_MIN_MID_TOTAL: u32 = 32;
const LOE_MIN_DEEP_TOTAL: u32 = 64;

fn context_admitted(ctx: &Ctx, order: usize) -> bool {
    order <= LOE_DIRECT_ORDER
        || (order <= LOE_MID_ORDER && ctx.total >= LOE_MIN_MID_TOTAL)
        || ctx.total >= LOE_MIN_DEEP_TOTAL
}
/// PPMd var.H SEE2 state: a decaying escape mean with an adaptive period.
#[derive(Clone, Copy)]
struct SeeState {
    summ: u32,
    shift: u8,
    count: u16,
}

impl SeeState {
    fn new() -> Self {
        Self::with_init(10)
    }

    fn with_init(init: u32) -> Self {
        Self {
            summ: init << 3,
            shift: 3,
            count: 4,
        }
    }

    fn predict(&mut self, _base: u32) -> u32 {
        let mean = self.summ >> self.shift;
        self.summ -= mean;
        mean.max(1)
    }

    fn update_escape(&mut self, total: u32) {
        self.summ = self.summ.saturating_add(total).min(u16::MAX as u32);
    }

    fn update_hit(&mut self) {
        if self.shift < 7 {
            self.count -= 1;
            if self.count == 0 {
                self.summ = (self.summ << 1).min(u16::MAX as u32);
                self.count = 3 << self.shift;
                self.shift += 1;
            }
        }
    }
}

#[inline]
fn see_bucket(
    order: usize,
    max_order: usize,
    masked: usize,
    symbols: usize,
    _run: usize,
    _suffix: usize,
    _scale: usize,
) -> usize {
    (order.min(max_order) << 8) | (masked.min(15) << 4) | symbols.min(15)
}

/// PAQ-style Adaptive Probability Map (a.k.a. SSE): a secondary calibration
/// stage applied to the escape probability AFTER SEE2. Each context row holds
/// `APM_N + 1` interpolation knots over the 12-bit probability domain; a lookup
/// linearly interpolates between the two knots bracketing the input probability,
/// and the update nudges the nearer knot toward the observed outcome. This
/// corrects systematic residual miscalibration in SEE2's escape estimate that a
/// single estimator cannot (PAQ chains such maps for exactly this reason). It
/// touches only the escape/hit mass split — orthogonal to the per-symbol context
/// statistics (LOE / inheritance).
const APM_N: usize = 24;
const APM_RATE: u32 = 7;

struct Apm {
    t: Vec<u16>, // nctx rows of (APM_N + 1) 12-bit probabilities
    nctx: usize,
}

impl Apm {
    fn new(nctx: usize) -> Self {
        let mut t = vec![0u16; nctx * (APM_N + 1)];
        for c in 0..nctx {
            for i in 0..=APM_N {
                // Identity initialisation: knot i sits at its own probability, so
                // an untrained APM is a no-op passthrough (no cold-start damage).
                let p = ((i as u32 * 4096) / APM_N as u32).clamp(1, 4095);
                t[c * (APM_N + 1) + i] = p as u16;
            }
        }
        Self { t, nctx }
    }

    /// Refine 12-bit probability `p` in context `ctx`; returns `(refined_p, knot_idx)`
    /// where `knot_idx` is the knot the paired [`Apm::update`] must nudge.
    #[inline]
    fn refine(&self, ctx: usize, p: u32) -> (u32, usize) {
        debug_assert!(ctx < self.nctx);
        let pos = p * APM_N as u32; // p/4096 scaled into [0, APM_N*4096)
        let bin = (pos >> 12) as usize;
        let frac = pos & 4095;
        let base = ctx * (APM_N + 1) + bin;
        let lo = self.t[base] as u32;
        let hi = self.t[base + 1] as u32;
        let refined = (lo * (4096 - frac) + hi * frac) >> 12;
        let idx = base + if frac >= 2048 { 1 } else { 0 };
        (refined.clamp(1, 4095), idx)
    }

    /// Nudge knot `idx` toward the outcome (`escaped` = escape actually occurred).
    #[inline]
    fn update(&mut self, idx: usize, escaped: bool) {
        let g: i32 = if escaped { 4095 } else { 0 };
        let cur = self.t[idx] as i32;
        self.t[idx] = (cur + ((g - cur) >> APM_RATE)) as u16;
    }
}

/// PPMII binary-context model (BinSumm) for *deterministic* contexts — those
/// with exactly one stored symbol. Instead of the general method-C/SEE2 escape
/// path (which pays a distinct-symbol escape frequency plus the symbol count),
/// a deterministic context codes a single binary event "does the one symbol
/// repeat?" through a probability pooled across all binary contexts that share
/// `(count_bucket, order)`. Pooling by the symbol's own count is the precise
/// indexing PPMd's BinSumm needs — a single shared state (the campaign's failed
/// coarse binary-SSE) cannot tell a count-2 context from a count-1000 one.
/// Orthogonal to LOE / inheritance / promotion (which shape the *stats*); this
/// only changes how a one-symbol context's repeat/escape split is coded.
const BIN_TOTAL: u32 = 1 << 12;
const BIN_COUNT_BUCKETS: usize = 64;
const BIN_CTX: usize = 16;
const BIN_RATE: u32 = 5;

struct BinModel {
    t: Vec<u16>, // [BIN_COUNT_BUCKETS * BIN_CTX] 12-bit P(repeat)
}

impl BinModel {
    fn new() -> Self {
        let mut t = vec![0u16; BIN_COUNT_BUCKETS * BIN_CTX];
        for i in 0..BIN_COUNT_BUCKETS {
            // Higher accumulated count ⇒ higher prior P(repeat). Smooth curve
            // i/(i+2), clamped to leave escape headroom on both ends.
            let pm = (((i as u32 + 1) * BIN_TOTAL) / (i as u32 + 2)).clamp(2048, 4020);
            for j in 0..BIN_CTX {
                t[i * BIN_CTX + j] = pm as u16;
            }
        }
        Self { t }
    }

    #[inline]
    fn slot(i: usize, j: usize) -> usize {
        i.min(BIN_COUNT_BUCKETS - 1) * BIN_CTX + j.min(BIN_CTX - 1)
    }

    /// 12-bit P(the one symbol repeats) for count bucket `i`, order bucket `j`.
    #[inline]
    fn predict(&self, i: usize, j: usize) -> u32 {
        (self.t[Self::slot(i, j)] as u32).clamp(1, BIN_TOTAL - 1)
    }

    #[inline]
    fn update(&mut self, i: usize, j: usize, repeated: bool) {
        let s = Self::slot(i, j);
        let g: i32 = if repeated { (BIN_TOTAL - 1) as i32 } else { 0 };
        let cur = self.t[s] as i32;
        self.t[s] = (cur + ((g - cur) >> BIN_RATE)) as u16;
    }
}

/// Count bucket for a deterministic symbol's accumulated count (in `PPM_INC`
/// units ⇒ roughly the number of observations).
#[inline]
fn bin_count_bucket(c: u32) -> usize {
    (c >> 2).min((BIN_COUNT_BUCKETS - 1) as u32) as usize
}

/// Experimental probability-calibration levers, all off by default so the
/// default path is byte-identical to the committed champion.
#[derive(Clone, Copy)]
struct Flags {
    apm: bool,
    bin: bool,
}

impl Flags {
    const OFF: Flags = Flags {
        apm: false,
        bin: false,
    };
}

/// Bounded-memory RESCALE policy (PPMII-style graceful reclamation).
///
/// When the number of stored contexts reaches `max_ctx`, instead of the naive
/// full clear-and-restart (which destroys all learned statistics and regressed
/// the ratio badly — see campaign log), we evict the least-recently-used
/// contexts (orders `>= evict_min_order`) down to `low_mark`, keeping the hot,
/// low-order backbone warm; and optionally halve all survivor counts (`halve`)
/// to bias the model toward recent statistics on non-stationary input.
///
/// `DISABLED` (`max_ctx = usize::MAX`) is the exact champion behaviour: contexts
/// are never evicted, so encode/decode wire bytes are byte-identical to the
/// unbounded model.
#[derive(Clone, Copy)]
struct MemCfg {
    max_ctx: usize,
    low_mark: usize,
    halve: bool,
    evict_min_order: usize,
}

impl MemCfg {
    const DISABLED: MemCfg = MemCfg {
        max_ctx: usize::MAX,
        low_mark: usize::MAX,
        halve: false,
        evict_min_order: 2,
    };

    /// A bounded config with a `low_mark` at `low_pct`% of `max_ctx`.
    fn bounded(max_ctx: usize, low_pct: usize, halve: bool, evict_min_order: usize) -> Self {
        let low_mark = (max_ctx / 100) * low_pct.min(100);
        Self {
            max_ctx,
            low_mark: low_mark.max(1),
            halve,
            evict_min_order,
        }
    }

    #[inline]
    fn enabled(&self) -> bool {
        self.max_ctx != usize::MAX
    }
}

/// Variable-order PPM model with shared, bucketed secondary escape estimators.
struct PpmModel {
    order: usize,
    ctx: Vec<BTreeMap<Vec<u8>, Ctx>>,
    see: Vec<SeeState>,
    mem: MemCfg,
    tick: u64,
    n_ctx: usize,
    peak_ctx: usize,
    rescales: u32,
    /// Diagnostic only (never affects the wire): sum of -log2(p) over every
    /// coded event under the model's assigned probabilities. Comparing this to
    /// the actual blob size isolates pure range-coder rounding loss from model
    /// loss. Written on the encode path only.
    ideal_bits: f64,
    /// Diagnostic bit-attribution (encode path only): bits spent on escapes and
    /// on the order-(-1) uniform fallback. Hit bits = ideal_bits - esc - uniform.
    esc_bits: f64,
    uni_bits: f64,
    /// Two-order mixing ceiling probe (encode path, hits only; no wire effect).
    /// `mix_actual` = actual hit bits under order-k alone; `mix_oracle` = bits if
    /// we could pick per-hit the cheaper of order-k / order-(k-1); `mix_blend` =
    /// bits under a fixed 50/50 blend. Gap actual→oracle bounds the mixing gain.
    mix_actual: f64,
    mix_oracle: f64,
    mix_blend: f64,
    /// SEE deterministic-run-length ceiling probe (encode path; no wire effect).
    /// `see_esc_bits` = actual binary escape-decision bits under the live SEE2
    /// estimate. `esc_n`/`esc_t` = per-(P_esc bucket × run-length bucket) escape
    /// and total counts; comparing the empirical binary entropy conditioned on
    /// (P_esc × run-length) vs on P_esc alone gives run-length's MARGINAL,
    /// causally-realizable value over SEE2.
    see_esc_bits: f64,
    esc_n: Vec<u32>,
    esc_t: Vec<u32>,
    /// Optional PAQ-style APM on the escape probability (chained after SEE2).
    /// `None` = exact champion behaviour (byte-identical wire).
    apm: Option<Apm>,
    /// Optional PPMII binary-context (BinSumm) model for deterministic contexts.
    bin: Option<BinModel>,
    /// Count-scaling weights (statistics-shaping sweep). Default = champion
    /// (`PPM_INC`, `CTX_RESCALE`); overridable via env for the gauge only, so
    /// unset env ⇒ byte-identical champion.
    inc: u32,
    ctx_rescale: u32,
}

/// Number of APM contexts = escape probability calibration is keyed by order
/// bucket (`k.min(APM_CTX - 1)`), so deterministic contexts (high order) and
/// shallow contexts get separate calibration curves.
const APM_CTX: usize = 16;

impl PpmModel {
    fn new(order: usize) -> Self {
        Self::new_bounded(order, MemCfg::DISABLED, Flags::OFF)
    }

    fn new_bounded(order: usize, mem: MemCfg, flags: Flags) -> Self {
        Self {
            order,
            ctx: (0..=order).map(|_| BTreeMap::new()).collect(),
            see: (0..((order + 1) << 8))
                .map(|bucket| SeeState::with_init(5 * ((bucket & 15) as u32) + 10))
                .collect(),
            mem,
            tick: 0,
            n_ctx: 0,
            peak_ctx: 0,
            rescales: 0,
            ideal_bits: 0.0,
            esc_bits: 0.0,
            uni_bits: 0.0,
            mix_actual: 0.0,
            mix_oracle: 0.0,
            mix_blend: 0.0,
            see_esc_bits: 0.0,
            esc_n: vec![0u32; SEE_PBUCKETS * SEE_RLBUCKETS],
            esc_t: vec![0u32; SEE_PBUCKETS * SEE_RLBUCKETS],
            apm: flags.apm.then(|| Apm::new(APM_CTX)),
            bin: flags.bin.then(BinModel::new),
            inc: std::env::var("CUBR_PPM_INC")
                .ok()
                .and_then(|s| s.parse().ok())
                .filter(|&v| v > 0)
                .unwrap_or(PPM_INC),
            ctx_rescale: std::env::var("CUBR_PPM_RESCALE")
                .ok()
                .and_then(|s| s.parse().ok())
                .filter(|&v| v > PPM_INC && v <= (1u32 << 16))
                .unwrap_or(CTX_RESCALE),
        }
    }

    /// Graceful bounded-memory reclamation: evict the least-recently-used
    /// contexts of order `>= mem.evict_min_order` down to `mem.low_mark`, then
    /// optionally halve survivor counts. Deterministic in the processed history
    /// (total order on `(last_used, order, key)`), so encode and decode reclaim
    /// identically and round-trip stays byte-exact.
    fn rescale_memory(&mut self) {
        self.rescales += 1;
        let mut cand: Vec<(u64, usize, &Vec<u8>)> = Vec::new();
        for (k, map) in self.ctx.iter().enumerate() {
            if k < self.mem.evict_min_order {
                continue;
            }
            for (key, c) in map.iter() {
                cand.push((c.last_used, k, key));
            }
        }
        cand.sort_unstable();
        let target = self.n_ctx.saturating_sub(self.mem.low_mark);
        let victims: Vec<(usize, Vec<u8>)> = cand
            .into_iter()
            .take(target)
            .map(|(_, k, key)| (k, key.clone()))
            .collect();
        for (k, key) in victims {
            if self.ctx[k].remove(&key).is_some() {
                self.n_ctx -= 1;
            }
        }
        if self.mem.halve {
            for map in self.ctx.iter_mut() {
                for c in map.values_mut() {
                    c.rescale();
                }
            }
        }
    }

    /// Apply the escape APM (if enabled) to `(run, esc)`. Returns the coded
    /// `(esc2, total2, knot_idx)`. `total2` is capped at `APM_TOTAL_CAP` so the
    /// reused range coder's `total ≤ 2^16` invariant always holds. When the APM
    /// is off, `esc2 == esc` and `total2 == run + esc` (byte-identical champion).
    #[inline]
    fn apm_escape(&self, k: usize, run: u32, esc: u32) -> (u32, u32, Option<usize>) {
        const APM_TOTAL_CAP: u32 = 1 << 15;
        match &self.apm {
            None => (esc, run + esc, None),
            Some(apm) => {
                let total = run + esc;
                let p = ((esc * 4096) / total).clamp(1, 4095);
                // Context adds a signal SEE2 does not bucket on: run magnitude
                // (populated vs sparse context) crossed with a coarse order band.
                let run_band = if run >= 256 {
                    2
                } else if run >= 32 {
                    1
                } else {
                    0
                };
                let ctx = (k.min(4) * 3 + run_band).min(APM_CTX - 1);
                let (rp, idx) = apm.refine(ctx, p);
                // esc' so that esc'/(run + esc') = rp/4096, run held fixed.
                let mut esc2 = ((run as u64 * rp as u64) / (4096 - rp) as u64).max(1) as u32;
                if run + esc2 > APM_TOTAL_CAP {
                    esc2 = APM_TOTAL_CAP.saturating_sub(run).max(1);
                }
                (esc2, run + esc2, Some(idx))
            }
        }
    }

    fn encode_symbol(&mut self, enc: &mut RangeEncoder, hist: &[u8], sym: u8) -> usize {
        let mut excluded = [false; 256];
        let mut k = self.order.min(hist.len());
        loop {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get(key).filter(|ctx| context_admitted(ctx, k)) {
                let (run, base_esc) = escape_band(ctx, &excluded);
                if base_esc > 0 {
                    if self.bin.is_some() && ctx.stats.len() == 1 && k >= 4 {
                        // Deterministic (single-symbol) context → BinSumm binary
                        // coding. `s0` is non-excluded here (base_esc > 0).
                        let (s0, c) = ctx.stats[0];
                        let i = bin_count_bucket(c);
                        let j = k.min(BIN_CTX - 1);
                        let pm = self.bin.as_ref().unwrap().predict(i, j);
                        if s0 == sym {
                            enc.encode(0, pm, BIN_TOTAL);
                            self.ideal_bits += -((pm as f64) / (BIN_TOTAL as f64)).log2();
                            self.bin.as_mut().unwrap().update(i, j, true);
                            return k;
                        }
                        enc.encode(pm, BIN_TOTAL - pm, BIN_TOTAL);
                        let eb = -(((BIN_TOTAL - pm) as f64) / (BIN_TOTAL as f64)).log2();
                        self.ideal_bits += eb;
                        self.esc_bits += eb;
                        self.bin.as_mut().unwrap().update(i, j, false);
                        excluded[s0 as usize] = true;
                    } else {
                        let masked = excluded.iter().filter(|&&v| v).count();
                        let bucket = see_bucket(
                            k,
                            self.order,
                            masked,
                            base_esc as usize,
                            run as usize,
                            0,
                            CTX_RESCALE as usize,
                        );
                        let esc = self.see[bucket].predict(base_esc);
                        let (esc2, total, apm_idx) = self.apm_escape(k, run, esc);
                        let mut cum = 0u32;
                        let mut found = None;
                        for &(s, c) in &ctx.stats {
                            if excluded[s as usize] {
                                continue;
                            }
                            if s == sym {
                                found = Some((cum, c));
                                break;
                            }
                            cum += c;
                        }
                        // SEE run-length ceiling probe: record this binary escape
                        // decision under the live SEE2 estimate, bucketed by
                        // (P_esc × deterministic-run length). Read-only.
                        {
                            let p_esc = (esc2 as f64) / (total as f64);
                            let escaped = found.is_none();
                            self.see_esc_bits += if escaped {
                                -p_esc.max(1e-12).log2()
                            } else {
                                -(1.0 - p_esc).max(1e-12).log2()
                            };
                            let idx =
                                see_p_bucket(p_esc) * SEE_RLBUCKETS + see_rl_bucket(ctx.det_run);
                            self.esc_t[idx] += 1;
                            if escaped {
                                self.esc_n[idx] += 1;
                            }
                        }
                        if let Some((cum, c)) = found {
                            enc.encode(cum, c, total);
                            self.ideal_bits += -((c as f64) / (total as f64)).log2();
                            // Two-order mixing ceiling probe (read-only).
                            let pk = (c as f64) / (total as f64);
                            let mut poracle = pk;
                            let mut pblend = pk;
                            if k >= 1 {
                                let pkey = &hist[hist.len() - (k - 1)..];
                                if let Some(pctx) = self.ctx[k - 1].get(pkey) {
                                    if let Some(&(_, ck1)) =
                                        pctx.stats.iter().find(|(s, _)| *s == sym)
                                    {
                                        let tot1 = pctx.total + pctx.stats.len() as u32;
                                        let pk1 = (ck1 as f64) / (tot1 as f64);
                                        poracle = pk.max(pk1);
                                        // Representative causal mixer weight
                                        // (trust order-k by its non-escape mass).
                                        // Measured NO-GO: every causal weight tried
                                        // — this (run/total, −5008 B), reliability
                                        // total/(total+24) (−13915 B), and uniform
                                        // 0.5 (−18518 B) — REGRESSES vs order-k
                                        // alone; the realizable optimum is w→1 (no
                                        // mixing). The oracle's +14147 B is not
                                        // causally realizable because tiered-LOE
                                        // already gates out unreliable sparse
                                        // high-order contexts, leaving order-k the
                                        // best causal predictor at the hit path.
                                        let w = (run as f64) / (total as f64);
                                        pblend = w * pk + (1.0 - w) * pk1;
                                    }
                                }
                            }
                            self.mix_actual += -pk.log2();
                            self.mix_oracle += -poracle.max(1e-12).log2();
                            self.mix_blend += -pblend.max(1e-12).log2();
                            self.see[bucket].update_hit();
                            if let (Some(apm), Some(idx)) = (self.apm.as_mut(), apm_idx) {
                                apm.update(idx, false);
                            }
                            return k;
                        }
                        enc.encode(run, esc2, total);
                        let eb = -((esc2 as f64) / (total as f64)).log2();
                        self.ideal_bits += eb;
                        self.esc_bits += eb;
                        self.see[bucket].update_escape(total);
                        if let (Some(apm), Some(idx)) = (self.apm.as_mut(), apm_idx) {
                            apm.update(idx, true);
                        }
                        for &(s, _) in &ctx.stats {
                            excluded[s as usize] = true;
                        }
                    }
                }
            }
            if k == 0 {
                break;
            }
            k -= 1;
        }
        let (rank, nfree) = uniform_rank(sym, &excluded);
        enc.encode(rank, 1, nfree);
        let ub = -(1.0f64 / (nfree as f64)).log2();
        self.ideal_bits += ub;
        self.uni_bits += ub;
        0
    }

    fn decode_symbol(&mut self, dec: &mut RangeDecoder, hist: &[u8]) -> (u8, usize) {
        let mut excluded = [false; 256];
        let mut k = self.order.min(hist.len());
        loop {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get(key).filter(|ctx| context_admitted(ctx, k)) {
                let (run, base_esc) = escape_band(ctx, &excluded);
                if base_esc > 0 {
                    if self.bin.is_some() && ctx.stats.len() == 1 && k >= 4 {
                        let (s0, c) = ctx.stats[0];
                        let i = bin_count_bucket(c);
                        let j = k.min(BIN_CTX - 1);
                        let pm = self.bin.as_ref().unwrap().predict(i, j);
                        let f = dec.get_freq(BIN_TOTAL);
                        if f < pm {
                            dec.decode(0, pm, BIN_TOTAL);
                            self.bin.as_mut().unwrap().update(i, j, true);
                            return (s0, k);
                        }
                        dec.decode(pm, BIN_TOTAL - pm, BIN_TOTAL);
                        self.bin.as_mut().unwrap().update(i, j, false);
                        excluded[s0 as usize] = true;
                    } else {
                        let masked = excluded.iter().filter(|&&v| v).count();
                        let bucket = see_bucket(
                            k,
                            self.order,
                            masked,
                            base_esc as usize,
                            run as usize,
                            0,
                            CTX_RESCALE as usize,
                        );
                        let esc = self.see[bucket].predict(base_esc);
                        let (esc2, total, apm_idx) = self.apm_escape(k, run, esc);
                        let f = dec.get_freq(total);
                        if f < run {
                            let mut cum = 0u32;
                            for &(s, c) in &ctx.stats {
                                if excluded[s as usize] {
                                    continue;
                                }
                                if f < cum + c {
                                    dec.decode(cum, c, total);
                                    self.see[bucket].update_hit();
                                    if let (Some(apm), Some(idx)) = (self.apm.as_mut(), apm_idx) {
                                        apm.update(idx, false);
                                    }
                                    return (s, k);
                                }
                                cum += c;
                            }
                            unreachable!("PPM decode: f<run but no symbol matched");
                        }
                        dec.decode(run, esc2, total);
                        self.see[bucket].update_escape(total);
                        if let (Some(apm), Some(idx)) = (self.apm.as_mut(), apm_idx) {
                            apm.update(idx, true);
                        }
                        for &(s, _) in &ctx.stats {
                            excluded[s as usize] = true;
                        }
                    }
                }
            }
            if k == 0 {
                break;
            }
            k -= 1;
        }
        let mut nfree = 0u32;
        for &e in &excluded {
            if !e {
                nfree += 1;
            }
        }
        let f = dec.get_freq(nfree);
        let mut rank = 0u32;
        for (b, &e) in excluded.iter().enumerate() {
            if !e {
                if rank == f {
                    dec.decode(rank, 1, nfree);
                    return (b as u8, 0);
                }
                rank += 1;
            }
        }
        unreachable!("PPM decode: uniform rank not found")
    }

    fn update(&mut self, hist: &[u8], sym: u8, found_order: usize) {
        self.tick += 1;
        let tick = self.tick;
        let inc = self.inc;
        let rescale_at = self.ctx_rescale;
        let maxk = self.order.min(hist.len());
        for k in found_order..=maxk {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get_mut(key) {
                ctx.bump(sym, inc, rescale_at);
                ctx.last_used = tick;
                // Deterministic-run bookkeeping (causal, diagnostic-only): a hit
                // at the found order extends the run; a consulted higher order
                // that escaped resets it.
                if k == found_order {
                    ctx.det_run += 1;
                } else {
                    ctx.det_run = 0;
                }
            } else {
                let seed = if k == 0 {
                    inc
                } else {
                    let parent_key = &hist[hist.len() - (k - 1)..];
                    self.ctx[k - 1]
                        .get(parent_key)
                        .map(|parent| successor_freq(parent, sym))
                        .unwrap_or(1)
                };
                if self.mem.enabled() && self.n_ctx >= self.mem.max_ctx {
                    self.rescale_memory();
                }
                let mut c = Ctx::seeded(sym, seed);
                c.last_used = tick;
                self.ctx[k].insert(key.to_vec(), c);
                self.n_ctx += 1;
                if self.n_ctx > self.peak_ctx {
                    self.peak_ctx = self.n_ctx;
                }
            }
        }
    }
}

/// Method-C escape band over the non-excluded symbols of a context:
/// returns `(run, esc)` where `run` = sum of non-excluded counts and `esc` = number
/// of distinct non-excluded symbols (the method-C escape frequency).
#[inline]
fn escape_band(ctx: &Ctx, excluded: &[bool; 256]) -> (u32, u32) {
    let mut run = 0u32;
    let mut esc = 0u32;
    for &(s, c) in &ctx.stats {
        if !excluded[s as usize] {
            run += c;
            esc += 1;
        }
    }
    (run, esc)
}

/// Rank of `sym` among the non-excluded symbols, and the count of non-excluded
/// symbols. `sym` MUST be non-excluded (guaranteed at order -1).
#[inline]
fn uniform_rank(sym: u8, excluded: &[bool; 256]) -> (u32, u32) {
    let mut rank = 0u32;
    let mut nfree = 0u32;
    for (b, &e) in excluded.iter().enumerate() {
        if !e {
            if b == sym as usize {
                rank = nfree;
            }
            nfree += 1;
        }
    }
    (rank, nfree)
}

/// Encode `data` with an order-`order` PPM. Wire: `[orig_len u64 BE][order u8][rc]`.
fn ppm_encode(data: &[u8], order: usize) -> Vec<u8> {
    ppm_encode_bounded(data, order, MemCfg::DISABLED, Flags::OFF).0
}

/// Bounded-memory encode. Returns `(blob, rescale_events, peak_context_count,
/// ideal_bits)`. `ideal_bits` is the model-entropy lower bound (diagnostic; not
/// on the wire). With `MemCfg::DISABLED` and `apm_on = false` the wire bytes are
/// byte-identical to [`ppm_encode`].
#[allow(clippy::type_complexity)]
fn ppm_encode_bounded(
    data: &[u8],
    order: usize,
    mem: MemCfg,
    flags: Flags,
) -> (
    Vec<u8>,
    u32,
    usize,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
    f64,
) {
    let mut out = (data.len() as u64).to_be_bytes().to_vec();
    out.push(order as u8);
    let mut model = PpmModel::new_bounded(order, mem, flags);
    let mut enc = RangeEncoder::new();
    for i in 0..data.len() {
        let fo = model.encode_symbol(&mut enc, &data[..i], data[i]);
        model.update(&data[..i], data[i], fo);
    }
    out.extend_from_slice(&enc.finish());
    // SEE run-length ceiling: empirical binary escape entropy conditioned on
    // (P_esc × run-length) [joint] vs on P_esc alone [marginal]. Their gap is
    // run-length's marginal, causally-realizable value over SEE2.
    let mut oracle_joint = 0.0f64;
    let mut oracle_marginal = 0.0f64;
    for pb in 0..SEE_PBUCKETS {
        let (mut mn, mut mt) = (0u32, 0u32);
        for rb in 0..SEE_RLBUCKETS {
            let idx = pb * SEE_RLBUCKETS + rb;
            let (e, t) = (model.esc_n[idx], model.esc_t[idx]);
            if t > 0 {
                oracle_joint += bin_entropy(e as f64 / t as f64) * t as f64;
            }
            mn += e;
            mt += t;
        }
        if mt > 0 {
            oracle_marginal += bin_entropy(mn as f64 / mt as f64) * mt as f64;
        }
    }
    (
        out,
        model.rescales,
        model.peak_ctx,
        model.ideal_bits,
        model.esc_bits,
        model.uni_bits,
        model.mix_actual,
        model.mix_oracle,
        model.mix_blend,
        model.see_esc_bits,
        oracle_marginal,
        oracle_joint,
    )
}

/// Decode a blob produced by [`ppm_encode`]. Fail-closed on a truncated header.
fn ppm_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    ppm_decode_bounded(blob, MemCfg::DISABLED, Flags::OFF)
}

/// Bounded-memory decode. The `mem` config and `apm_on` MUST match the ones used
/// at encode time, so the deterministic LRU eviction and escape APM reclaim/
/// refine identically and the round-trip stays byte-exact.
fn ppm_decode_bounded(blob: &[u8], mem: MemCfg, flags: Flags) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 9 {
        return Err(CubrimError::Decode("MODE_PPMD: header truncated".into()));
    }
    let orig_len = u64::from_be_bytes(blob[..8].try_into().unwrap());
    let order = blob[8] as usize;
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = PpmModel::new_bounded(order, mem, flags);
    let mut dec = RangeDecoder::new(&blob[9..]);
    for _ in 0..orig_len {
        let (sym, fo) = model.decode_symbol(&mut dec, &out);
        model.update(&out, sym, fo);
        out.push(sym);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Round-trip invariant: decode(encode(x)) == x, byte-exact (cmp=0).
    fn rt(data: &[u8]) {
        let blob = ppmd_o0_encode(data);
        let out = ppmd_o0_decode(&blob).expect("decode must succeed on our own blob");
        assert_eq!(out, data, "round-trip cmp!=0 for input len {}", data.len());
    }

    #[test]
    fn rt_empty() {
        rt(b"");
    }

    #[test]
    fn rt_single_byte() {
        rt(b"A");
    }

    #[test]
    fn rt_short_run() {
        rt(&[0x42u8; 300]);
    }

    #[test]
    fn rt_text() {
        let data = b"the quick brown fox jumps over the lazy dog. ".repeat(64);
        rt(&data);
    }

    #[test]
    fn rt_all_byte_values() {
        let data: Vec<u8> = (0..5000).map(|i| (i % 256) as u8).collect();
        rt(&data);
    }

    #[test]
    fn rt_pseudo_random() {
        // Deterministic LCG — no float, no external rng in the test data.
        let mut x: u32 = 0x1234_5678;
        let data: Vec<u8> = (0..8000)
            .map(|_| {
                x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                (x >> 24) as u8
            })
            .collect();
        rt(&data);
    }

    // ── Step 2: binary bit-coder primitive ───────────────────────────────────

    /// Round-trip an adaptive bit sequence: encode with a BitModel, decode with
    /// an identically-initialised BitModel, assert bit-exact.
    fn rt_bits(bits: &[u8]) -> usize {
        let mut enc = RangeEncoder::new();
        let mut m = BitModel::new();
        for &b in bits {
            let p = m.predict();
            encode_bit(&mut enc, b, p);
            m.update(b);
        }
        let blob = enc.finish();
        let mut dec = RangeDecoder::new(&blob);
        let mut m2 = BitModel::new();
        let mut out = Vec::with_capacity(bits.len());
        for _ in 0..bits.len() {
            let p = m2.predict();
            let b = decode_bit(&mut dec, p);
            m2.update(b);
            out.push(b);
        }
        assert_eq!(out, bits, "bit round-trip cmp!=0 for {} bits", bits.len());
        blob.len()
    }

    #[test]
    fn bits_rt_all_zero() {
        rt_bits(&[0u8; 4000]);
    }

    #[test]
    fn bits_rt_all_one() {
        rt_bits(&[1u8; 4000]);
    }

    #[test]
    fn bits_rt_alternating() {
        let bits: Vec<u8> = (0..4000).map(|i| (i % 2) as u8).collect();
        rt_bits(&bits);
    }

    #[test]
    fn bits_rt_pseudo_random() {
        let mut x: u32 = 0xDEAD_BEEF;
        let bits: Vec<u8> = (0..8000)
            .map(|_| {
                x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                ((x >> 31) & 1) as u8
            })
            .collect();
        rt_bits(&bits);
    }

    // ── Step 3: variable-order PPM (PPMC) ────────────────────────────────────

    /// Round-trip through the order-`order` PPM, byte-exact (cmp=0).
    fn ppm_rt(data: &[u8], order: usize) -> usize {
        let blob = ppm_encode(data, order);
        let out = ppm_decode(&blob).expect("ppm decode");
        assert_eq!(
            out,
            data,
            "PPM(order {order}) round-trip cmp!=0 for len {}",
            data.len()
        );
        blob.len()
    }

    #[test]
    fn ppm_rt_edge_cases() {
        for order in [0usize, 1, 2, 4, 6] {
            ppm_rt(b"", order);
            ppm_rt(b"A", order);
            ppm_rt(&[0x5Au8; 500], order);
        }
    }

    #[test]
    fn ppm_rt_text_multi_order() {
        let text = b"To be, or not to be, that is the question. \
                     Whether 'tis nobler in the mind to suffer. "
            .repeat(40);
        for order in [0usize, 2, 4, 6] {
            ppm_rt(&text, order);
        }
    }

    #[test]
    fn ppm_rt_all_byte_values() {
        let data: Vec<u8> = (0..6000).map(|i| (i % 256) as u8).collect();
        for order in [0usize, 2, 4] {
            ppm_rt(&data, order);
        }
    }

    #[test]
    fn ppm_rt_pseudo_random() {
        let mut x: u32 = 0xF00D_CAFE;
        let data: Vec<u8> = (0..6000)
            .map(|_| {
                x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                (x >> 24) as u8
            })
            .collect();
        for order in [0usize, 3, 6] {
            ppm_rt(&data, order);
        }
    }

    /// Repetitive English-like text must compress far below 8 bits/byte — a
    /// higher order captures the repetition better than order 0.
    #[test]
    fn ppm_text_compresses_with_order() {
        let text = b"the quick brown fox jumps over the lazy dog. ".repeat(400);
        let o0 = ppm_rt(&text, 0);
        let o4 = ppm_rt(&text, 4);
        assert!(
            o4 < text.len(),
            "order-4 PPM did not compress: {o4} vs {}",
            text.len()
        );
        assert!(
            o4 < o0,
            "order-4 ({o4}) should beat order-0 ({o0}) on repetitive text"
        );
    }

    // ── Step 5: proper SEE + binary-context SSE ─────────────────────────────

    #[test]
    fn see_escape_frequency_rises_on_escape_and_falls_on_hits() {
        let mut see = SeeState::new();
        let initial = see.predict(3);

        see.update_escape(80);
        let raised = see.predict(3);
        assert!(
            raised > initial,
            "escape must raise SEE frequency: initial={initial}, raised={raised}"
        );

        for _ in 0..12 {
            see.update_hit();
            let _ = see.predict(3);
        }
        let lowered = see.predict(3);
        assert!(
            lowered < raised,
            "hits must lower SEE frequency: raised={raised}, lowered={lowered}"
        );
    }

    #[test]
    fn see_bucket_separates_masking_and_high_order() {
        let plain_low = see_bucket(2, 16, 4, 4, 0, 8, 32);
        let masked_low = see_bucket(2, 16, 4, 2, 2, 8, 32);
        let plain_high = see_bucket(14, 16, 4, 4, 0, 8, 32);
        assert_ne!(
            plain_low, masked_low,
            "masked and unmasked SEE states must differ"
        );
        assert_ne!(
            plain_low, plain_high,
            "low and high orders must not share SEE state"
        );
    }

    #[test]
    fn ppm_rt_order16_with_escape_bursts() {
        let mut data = Vec::new();
        for i in 0..4000u32 {
            data.extend_from_slice(b"common-prefix:");
            data.push(if i % 29 == 0 { (i / 29) as u8 } else { b'e' });
        }
        ppm_rt(&data, 16);
    }

    #[test]
    fn successor_inheritance_tracks_parent_probability() {
        let mut parent = Ctx::default();
        for _ in 0..8 {
            parent.bump(b'a', PPM_INC, CTX_RESCALE);
        }
        parent.bump(b'b', PPM_INC, CTX_RESCALE);
        let common = successor_freq(&parent, b'a');
        let rare = successor_freq(&parent, b'b');
        assert!(common > rare, "common={common}, rare={rare}");
        assert!(rare >= 1);
    }

    #[test]
    fn inherited_context_seeds_only_target_symbol() {
        let ctx = Ctx::seeded(b'x', 7);
        assert_eq!(ctx.stats, vec![(b'x', 7)]);
        assert_eq!(ctx.total, 7);
    }

    #[test]
    fn loe_skips_sparse_high_order_contexts() {
        let sparse = Ctx::seeded(b'x', 4);
        let mid = Ctx::seeded(b'x', 32);
        let deep = Ctx::seeded(b'x', 64);
        assert!(context_admitted(&sparse, 5));
        assert!(!context_admitted(&sparse, 8));
        assert!(context_admitted(&mid, 8));
        assert!(!context_admitted(&mid, 12));
        assert!(context_admitted(&deep, 12));
    }

    // ── Bounded-memory RESCALE (PPMII-style graceful reclamation) ───────────

    /// Round-trip through a memory-bounded PPM must stay byte-exact: the LRU
    /// eviction is a deterministic function of the processed history, so decode
    /// reclaims exactly the contexts encode did.
    fn ppm_rt_bounded(data: &[u8], order: usize, mem: MemCfg, flags: Flags) -> (usize, u32, usize) {
        let (blob, rescales, peak, _, _, _, _, _, _, _, _, _) =
            ppm_encode_bounded(data, order, mem, flags);
        let out = ppm_decode_bounded(&blob, mem, flags).expect("bounded ppm decode");
        assert_eq!(
            out,
            data,
            "bounded PPM(order {order}) round-trip cmp!=0 for len {}",
            data.len()
        );
        (blob.len(), rescales, peak)
    }

    #[test]
    fn bounded_round_trips_with_eviction() {
        // A tiny cap on high-entropy + structured text forces many eviction
        // rounds; RT must remain byte-exact across orders and both halve modes.
        let mut data = Vec::new();
        let mut x: u32 = 0xC0FFEE11;
        for i in 0..20_000u32 {
            data.extend_from_slice(b"ctx-");
            x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            data.push((x >> 24) as u8);
            data.push((i % 251) as u8);
        }
        for order in [4usize, 8, 16] {
            for halve in [false, true] {
                let mem = MemCfg::bounded(2_000, 75, halve, 2);
                let (_, rescales, peak) = ppm_rt_bounded(&data, order, mem, Flags::OFF);
                assert!(
                    rescales > 0,
                    "cap must actually fire for order {order} halve={halve}"
                );
                assert!(
                    peak <= mem.max_ctx,
                    "peak {peak} exceeded cap {} (order {order})",
                    mem.max_ctx
                );
            }
        }
    }

    #[test]
    fn bounded_disabled_is_byte_identical_to_champion() {
        // The DISABLED config must reproduce the unbounded wire exactly.
        let text = b"the quick brown fox jumps over the lazy dog. ".repeat(200);
        for order in [4usize, 8, 16] {
            let champ = ppm_encode(&text, order);
            let (bounded, rescales, _, _, _, _, _, _, _, _, _, _) =
                ppm_encode_bounded(&text, order, MemCfg::DISABLED, Flags::OFF);
            assert_eq!(
                champ, bounded,
                "DISABLED diverged from champion (order {order})"
            );
            assert_eq!(rescales, 0, "DISABLED must never rescale");
        }
    }

    #[test]
    fn bounded_edge_cases_round_trip() {
        let mem = MemCfg::bounded(64, 50, true, 2);
        for order in [0usize, 2, 8] {
            ppm_rt_bounded(b"", order, mem, Flags::OFF);
            ppm_rt_bounded(b"A", order, mem, Flags::OFF);
            ppm_rt_bounded(&[0x5Au8; 500], order, mem, Flags::OFF);
        }
    }

    // ── Escape APM (PAQ-style SSE on the escape probability) ────────────────

    /// The escape APM must keep round-trip byte-exact: encode and decode compute
    /// the same refined escape mass and update the map identically, so the coded
    /// distribution matches on both sides across orders and edge cases.
    #[test]
    fn apm_round_trips_byte_exact() {
        let text = b"the quick brown fox jumps over the lazy dog. \
                     PACK MY BOX WITH FIVE DOZEN LIQUOR JUGS. "
            .repeat(120);
        let mut mixed = text.clone();
        let mut x: u32 = 0xA5A5_1234;
        for _ in 0..3000 {
            x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            mixed.push((x >> 24) as u8);
        }
        for order in [0usize, 4, 8, 16] {
            for data in [text.as_slice(), mixed.as_slice(), b"", b"A", &[7u8; 400]] {
                let (blob, _, _, _, _, _, _, _, _, _, _, _) = ppm_encode_bounded(
                    data,
                    order,
                    MemCfg::DISABLED,
                    Flags {
                        apm: true,
                        bin: false,
                    },
                );
                let out = ppm_decode_bounded(
                    &blob,
                    MemCfg::DISABLED,
                    Flags {
                        apm: true,
                        bin: false,
                    },
                )
                .expect("apm decode");
                assert_eq!(
                    out,
                    data,
                    "APM RT cmp!=0 (order {order}, len {})",
                    data.len()
                );
            }
        }
    }

    /// The BinSumm deterministic-context model must keep round-trip byte-exact:
    /// encode and decode take the identical binary branch (same one-symbol
    /// contexts, same table index, same table state) so the coded probabilities
    /// match on both sides across orders and edge cases.
    #[test]
    fn bin_round_trips_byte_exact() {
        let bin = Flags {
            apm: false,
            bin: true,
        };
        let text = b"the quick brown fox jumps over the lazy dog. \
                     she sells sea shells by the sea shore. "
            .repeat(150);
        let mut mixed = text.clone();
        let mut x: u32 = 0x1357_9BDF;
        for _ in 0..4000 {
            x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            mixed.push((x >> 24) as u8);
        }
        for order in [0usize, 4, 8, 16] {
            for data in [text.as_slice(), mixed.as_slice(), b"", b"A", &[9u8; 600]] {
                let (blob, _, _, _, _, _, _, _, _, _, _, _) =
                    ppm_encode_bounded(data, order, MemCfg::DISABLED, bin);
                let out = ppm_decode_bounded(&blob, MemCfg::DISABLED, bin).expect("bin decode");
                assert_eq!(
                    out,
                    data,
                    "BinSumm RT cmp!=0 (order {order}, len {})",
                    data.len()
                );
            }
        }
    }

    #[test]
    fn bin_and_apm_compose_round_trip() {
        let both = Flags {
            apm: true,
            bin: true,
        };
        let text = b"pack my box with five dozen liquor jugs. ".repeat(180);
        for order in [4usize, 8, 16] {
            let (blob, _, _, _, _, _, _, _, _, _, _, _) =
                ppm_encode_bounded(&text, order, MemCfg::DISABLED, both);
            let out = ppm_decode_bounded(&blob, MemCfg::DISABLED, both).expect("both decode");
            assert_eq!(out, text, "APM+BinSumm RT cmp!=0 (order {order})");
        }
    }

    #[test]
    fn apm_off_is_byte_identical_to_champion() {
        let text = b"the quick brown fox jumps over the lazy dog. ".repeat(200);
        for order in [4usize, 8, 16] {
            let champ = ppm_encode(&text, order);
            let (apm_off, _, _, _, _, _, _, _, _, _, _, _) =
                ppm_encode_bounded(&text, order, MemCfg::DISABLED, Flags::OFF);
            assert_eq!(
                champ, apm_off,
                "apm_on=false diverged from champion (order {order})"
            );
        }
    }

    /// Step 4 self-probe (charged, real numbers). Not run by default -- invoke:
    ///   CUBR_PROBE_FILE=/path/to/dickens [CUBR_PROBE_LIMIT=N]
    ///     cargo test --release -j4 ppmd::tests::self_probe -- --ignored --nocapture
    /// Reports the PPM charged ratio at several orders vs the incumbent Cubrim
    /// (`crate::encode` = competitive-min best = what Cubrim actually ships), and
    /// whether PPM strictly beats it. RT cmp=0 is enforced per order.
    #[test]
    #[ignore]
    fn self_probe() {
        let path = std::env::var("CUBR_PROBE_FILE").expect("set CUBR_PROBE_FILE");
        let mut data = std::fs::read(&path).expect("read probe file");
        if let Ok(lim) = std::env::var("CUBR_PROBE_LIMIT") {
            let lim: usize = lim.parse().expect("CUBR_PROBE_LIMIT usize");
            data.truncate(lim);
        }
        let n = data.len() as f64;
        let inc = crate::encode(&data).len();
        println!(
            "PROBE file={} n={} incumbent={} ratio={:.9}",
            path,
            data.len(),
            inc,
            inc as f64 / n
        );
        // 1 MB dickens-head gauge showed the method-C skeleton peaks around
        // order 4–5 (higher orders lose to escape overhead without SEE, exactly
        // as the consilium predicted for order-16). Probe the competitive band.
        let orders: Vec<usize> = std::env::var("CUBR_PROBE_ORDERS")
            .ok()
            .map(|s| s.split(',').map(|x| x.trim().parse().unwrap()).collect())
            .unwrap_or_else(|| vec![3, 4, 5]);
        // Bounded-memory RESCALE gauge knobs. Unset CUBR_PPM_MAXCTX ⇒ DISABLED
        // ⇒ exact champion behaviour (byte-identical baseline).
        let mem = match std::env::var("CUBR_PPM_MAXCTX")
            .ok()
            .and_then(|s| s.parse().ok())
        {
            Some(max_ctx) => {
                let low_pct = std::env::var("CUBR_PPM_LOWPCT")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(75usize);
                let halve = std::env::var("CUBR_PPM_HALVE")
                    .map(|s| s == "1")
                    .unwrap_or(false);
                let emin = std::env::var("CUBR_PPM_EVICTMIN")
                    .ok()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(2usize);
                MemCfg::bounded(max_ctx, low_pct, halve, emin)
            }
            None => MemCfg::DISABLED,
        };
        let flags = Flags {
            apm: std::env::var("CUBR_PPM_APM")
                .map(|s| s == "1")
                .unwrap_or(false),
            bin: std::env::var("CUBR_PPM_BIN")
                .map(|s| s == "1")
                .unwrap_or(false),
        };
        for order in orders {
            let (
                blob,
                rescales,
                peak,
                ideal_bits,
                esc_bits,
                uni_bits,
                mix_a,
                mix_o,
                mix_b,
                see_eb,
                orc_m,
                orc_j,
            ) = ppm_encode_bounded(&data, order, mem, flags);
            let out = ppm_decode_bounded(&blob, mem, flags).expect("decode");
            let rt = out == data;
            let p = blob.len();
            // Model-entropy floor vs actual bytes: (actual - ideal)/actual is the
            // pure range-coder overhead (rounding + 4-byte flush), separated from
            // model loss. If this is tiny, the coder is already tight and the
            // only remaining lever is model-side calibration (SSE/APM).
            let ideal_bytes = ideal_bits / 8.0;
            let coder_overhead = (p as f64 - ideal_bytes) / p as f64;
            let esc_frac = esc_bits / ideal_bits;
            let uni_frac = uni_bits / ideal_bits;
            // Two-order mixing ceiling: potential HIT-byte savings if we could
            // pick per-hit the better of order-k / order-(k-1) (oracle) or a
            // fixed 50/50 blend, vs actual order-k-alone hit bits.
            let mix_oracle_saved = (mix_a - mix_o) / 8.0;
            let mix_blend_saved = (mix_a - mix_b) / 8.0;
            // SEE run-length ceiling: bytes saved if an adaptive SEE indexed by
            // (P_esc × run-length) reached its empirical binary entropy [joint]
            // vs indexed by P_esc alone [marginal]. (marginal-joint) = run-length
            // marginal ceiling; (see_esc_bits-marginal) = SEE2 adaptation lag.
            let see_actual_bytes = see_eb / 8.0;
            let see_marginal_bytes = orc_m / 8.0;
            let see_joint_bytes = orc_j / 8.0;
            let see_rl_ceiling = (orc_m - orc_j) / 8.0;
            let see_lag = (see_eb - orc_m) / 8.0;
            println!(
                "PROBE order={} ppm={} ratio={:.9} rt_cmp0={} beats_incumbent={} \
                 maxctx={} lowpct={} halve={} peak_ctx={} rescales={} \
                 ideal_bytes={:.1} coder_overhead={:.6} esc_frac={:.4} uni_frac={:.4} \
                 hit_bytes={:.0} mix_oracle_saved={:.0} mix_blend_saved={:.0} \
                 see_actual={:.0} see_marginal={:.0} see_joint={:.0} \
                 see_rl_ceiling={:.0} see_lag={:.0}",
                order,
                p,
                p as f64 / n,
                rt,
                p < inc,
                if mem.enabled() {
                    mem.max_ctx as i64
                } else {
                    -1
                },
                mem.low_mark,
                mem.halve,
                peak,
                rescales,
                ideal_bytes,
                coder_overhead,
                esc_frac,
                uni_frac,
                mix_a / 8.0,
                mix_oracle_saved,
                mix_blend_saved,
                see_actual_bytes,
                see_marginal_bytes,
                see_joint_bytes,
                see_rl_ceiling,
                see_lag,
            );
            assert!(rt, "self-probe RT cmp!=0 at order {order}");
        }
    }

    /// A strongly biased bit stream must compress well below the raw 1-bit/bit
    /// bound — the adaptive model learns the bias. This is the coder-loss /
    /// V-AC-6 sanity: a working coder + model beats the entropy of the source.
    #[test]
    fn bits_biased_compresses() {
        // ~1 in 32 bits is a 1 → source entropy ≈ 0.20 bit/bit.
        let mut x: u32 = 0x0BADF00D;
        let n = 40_000usize;
        let bits: Vec<u8> = (0..n)
            .map(|_| {
                x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                if (x >> 27) % 32 == 0 {
                    1
                } else {
                    0
                }
            })
            .collect();
        let bytes = rt_bits(&bits);
        // Raw would be n/8 = 5000 B; entropy ~0.2 bit/bit ⇒ ~1000 B. Require the
        // coder to reach well under half the raw bound (loose, robust bound).
        assert!(
            bytes < n / 8 / 2,
            "biased bit stream did not compress: {bytes} B for {n} bits (raw {} B)",
            n / 8
        );
    }
}
