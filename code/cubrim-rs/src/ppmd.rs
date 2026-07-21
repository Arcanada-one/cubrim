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

/// Per-context total cap — rescale when reached. Kept below the coder's
/// `RC_BOT = 2^16` cap with headroom for the method-C escape band (≤ 256).
const CTX_RESCALE: u32 = 1 << 14;
/// Count increment per observation.
const PPM_INC: u32 = 4;

/// One PPM context: (symbol, count) stats in deterministic insertion order.
#[derive(Default)]
struct Ctx {
    stats: Vec<(u8, u32)>,
    total: u32,
}

impl Ctx {
    fn seeded(sym: u8, freq: u32) -> Self {
        Self {
            stats: vec![(sym, freq.max(1))],
            total: freq.max(1),
        }
    }

    #[inline]
    fn bump(&mut self, sym: u8) {
        if let Some(e) = self.stats.iter_mut().find(|(s, _)| *s == sym) {
            e.1 += PPM_INC;
        } else {
            self.stats.push((sym, PPM_INC));
        }
        self.total += PPM_INC;
        if self.total >= CTX_RESCALE {
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

/// Variable-order PPM model with shared, bucketed secondary escape estimators.
struct PpmModel {
    order: usize,
    ctx: Vec<BTreeMap<Vec<u8>, Ctx>>,
    see: Vec<SeeState>,
}

impl PpmModel {
    fn new(order: usize) -> Self {
        Self {
            order,
            ctx: (0..=order).map(|_| BTreeMap::new()).collect(),
            see: (0..((order + 1) << 8))
                .map(|bucket| SeeState::with_init(5 * ((bucket & 15) as u32) + 10))
                .collect(),
        }
    }

    fn encode_symbol(&mut self, enc: &mut RangeEncoder, hist: &[u8], sym: u8) -> usize {
        let mut excluded = [false; 256];
        let mut k = self.order.min(hist.len());
        loop {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get(key) {
                let (run, base_esc) = escape_band(ctx, &excluded);
                if base_esc > 0 {
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
                    let total = run + esc;
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
                    if let Some((cum, c)) = found {
                        enc.encode(cum, c, total);
                        self.see[bucket].update_hit();
                        return k;
                    }
                    enc.encode(run, esc, total);
                    self.see[bucket].update_escape(total);
                    for &(s, _) in &ctx.stats {
                        excluded[s as usize] = true;
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
        0
    }

    fn decode_symbol(&mut self, dec: &mut RangeDecoder, hist: &[u8]) -> (u8, usize) {
        let mut excluded = [false; 256];
        let mut k = self.order.min(hist.len());
        loop {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get(key) {
                let (run, base_esc) = escape_band(ctx, &excluded);
                if base_esc > 0 {
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
                    let total = run + esc;
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
                                return (s, k);
                            }
                            cum += c;
                        }
                        unreachable!("PPM decode: f<run but no symbol matched");
                    }
                    dec.decode(run, esc, total);
                    self.see[bucket].update_escape(total);
                    for &(s, _) in &ctx.stats {
                        excluded[s as usize] = true;
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
        let maxk = self.order.min(hist.len());
        for k in found_order..=maxk {
            let key = &hist[hist.len() - k..];
            if let Some(ctx) = self.ctx[k].get_mut(key) {
                ctx.bump(sym);
            } else {
                let seed = if k == 0 {
                    PPM_INC
                } else {
                    let parent_key = &hist[hist.len() - (k - 1)..];
                    self.ctx[k - 1]
                        .get(parent_key)
                        .map(|parent| successor_freq(parent, sym))
                        .unwrap_or(1)
                };
                self.ctx[k].insert(key.to_vec(), Ctx::seeded(sym, seed));
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
    let mut out = (data.len() as u64).to_be_bytes().to_vec();
    out.push(order as u8);
    let mut model = PpmModel::new(order);
    let mut enc = RangeEncoder::new();
    for i in 0..data.len() {
        let fo = model.encode_symbol(&mut enc, &data[..i], data[i]);
        model.update(&data[..i], data[i], fo);
    }
    out.extend_from_slice(&enc.finish());
    out
}

/// Decode a blob produced by [`ppm_encode`]. Fail-closed on a truncated header.
fn ppm_decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < 9 {
        return Err(CubrimError::Decode("MODE_PPMD: header truncated".into()));
    }
    let orig_len = u64::from_be_bytes(blob[..8].try_into().unwrap());
    let order = blob[8] as usize;
    let cap = orig_len.min(1 << 20) as usize;
    let mut out = Vec::with_capacity(cap);
    let mut model = PpmModel::new(order);
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
            parent.bump(b'a');
        }
        parent.bump(b'b');
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
    /// Step 4 self-probe (charged, real numbers). Not run by default — invoke:
    ///   CUBR_PROBE_FILE=/path/to/dickens [CUBR_PROBE_LIMIT=N] \
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
        for order in orders {
            let blob = ppm_encode(&data, order);
            let out = ppm_decode(&blob).expect("decode");
            let rt = out == data;
            let p = blob.len();
            println!(
                "PROBE order={} ppm={} ratio={:.9} rt_cmp0={} beats_incumbent={}",
                order,
                p,
                p as f64 / n,
                rt,
                p < inc
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
