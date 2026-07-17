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
        return Err(CubrimError::Decode("MODE_PPMD(o0): header truncated".into()));
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
