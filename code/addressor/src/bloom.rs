//! Bloom prefilter for fleet lookups (AH-10): built by the HUB over its
//! catalog keys, distributed as a FILE inside the epoch snapshot, checked
//! locally on the spoke — no network component of its own.

use crate::cas::HASH_LEN;
use crate::error::{AddressorError, Result};
use growable_bloom_filter::GrowableBloom;

/// Engineering bound for the filter's configured false-positive probability
/// (NOT an AH-10 measurement — AH-10's −70.16% is a property of the lookup
/// stream's negative fraction).
pub const TARGET_FP: f64 = 0.01;

pub struct FleetBloom {
    inner: GrowableBloom,
}

impl FleetBloom {
    pub fn new(estimated_keys: usize) -> Self {
        FleetBloom {
            inner: GrowableBloom::new(TARGET_FP, estimated_keys.max(16)),
        }
    }

    pub fn insert(&mut self, hash: &[u8; HASH_LEN]) {
        self.inner.insert(hash);
    }

    pub fn contains(&self, hash: &[u8; HASH_LEN]) -> bool {
        self.inner.contains(hash)
    }

    /// Serializes to the snapshot file format (bincode over serde).
    pub fn to_bytes(&self) -> Result<Vec<u8>> {
        bincode::serialize(&self.inner)
            .map_err(|e| AddressorError::Format(format!("bloom serialize: {e}")))
    }

    pub fn from_bytes(data: &[u8]) -> Result<Self> {
        Ok(FleetBloom {
            inner: bincode::deserialize(data)
                .map_err(|e| AddressorError::Format(format!("bloom deserialize: {e}")))?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> [u8; HASH_LEN] {
        *blake3::hash(s.as_bytes()).as_bytes()
    }

    #[test]
    fn no_false_negatives() {
        let mut b = FleetBloom::new(10_000);
        for i in 0..10_000 {
            b.insert(&h(&format!("key-{i}")));
        }
        for i in 0..10_000 {
            assert!(b.contains(&h(&format!("key-{i}"))), "false negative at {i}");
        }
    }

    #[test]
    fn negative_lookup_reduction_on_pinned_stream() {
        // the mechanism half of AH-10: with negative_fraction f_neg pinned by
        // the stream construction, avoided lookups ≈ f_neg * (1 − fp).
        let mut b = FleetBloom::new(5_000);
        for i in 0..5_000 {
            b.insert(&h(&format!("present-{i}")));
        }
        let total = 20_000u32;
        let negative_fraction = 0.75; // pinned stream parameter
        let negatives = (total as f64 * negative_fraction) as u32;
        let mut avoided = 0u32;
        for i in 0..negatives {
            if !b.contains(&h(&format!("absent-{i}"))) {
                avoided += 1;
            }
        }
        // positives always pass the filter (no false negatives) — they cost
        // a lookup regardless; reduction comes from the negative mass.
        let reduction = avoided as f64 / total as f64;
        assert!(
            reduction >= 0.70,
            "lookup reduction {reduction:.4} < 0.70 (fp too high or stream wrong)"
        );
        // and the configured fp bound holds on this stream
        let fp = 1.0 - (avoided as f64 / negatives as f64);
        assert!(fp <= 0.05, "measured fp {fp:.4} > 0.05");
    }

    #[test]
    fn snapshot_serialization_roundtrip() {
        let mut b = FleetBloom::new(100);
        for i in 0..100 {
            b.insert(&h(&format!("k{i}")));
        }
        let bytes = b.to_bytes().unwrap();
        let b2 = FleetBloom::from_bytes(&bytes).unwrap();
        for i in 0..100 {
            assert!(b2.contains(&h(&format!("k{i}"))));
        }
        assert!(FleetBloom::from_bytes(b"garbage").is_err());
    }
}
