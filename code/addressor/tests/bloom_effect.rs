//! Bloom prefilter effect (AH-10 mechanism): on a stream with a pinned
//! negative fraction, avoided catalog probes ≥ 70% of the stream. Honesty:
//! the reduction is bounded by the stream's negative_fraction — this test
//! verifies the FILTER (fp ≤ 5% on negatives); the 70% figure requires
//! negative_fraction ≥ ~0.74, pinned here at 0.80.

use addressor::bloom::FleetBloom;

fn h(s: &str) -> [u8; 32] {
    *blake3::hash(s.as_bytes()).as_bytes()
}

#[test]
fn lookup_reduction_on_pinned_stream() {
    // hub catalog: 50k keys
    let mut bloom = FleetBloom::new(50_000);
    for i in 0..50_000 {
        bloom.insert(&h(&format!("hub-{i}")));
    }
    // snapshot roundtrip (the filter travels as a file)
    let bloom = FleetBloom::from_bytes(&bloom.to_bytes().unwrap()).unwrap();

    let total = 50_000u32;
    let negative_fraction = 0.80; // pinned stream parameter (manifest value)
    let negatives = (total as f64 * negative_fraction) as u32;
    let positives = total - negatives;

    let mut lookups_needed = 0u32;
    for i in 0..positives {
        if bloom.contains(&h(&format!("hub-{i}"))) {
            lookups_needed += 1;
        }
    }
    let mut fp = 0u32;
    for i in 0..negatives {
        if bloom.contains(&h(&format!("spoke-only-{i}"))) {
            fp += 1;
            lookups_needed += 1;
        }
    }
    let reduction = 1.0 - (lookups_needed as f64 / total as f64);
    let fp_rate = fp as f64 / negatives as f64;
    assert!(fp_rate <= 0.05, "bloom fp {fp_rate:.4} > 0.05");
    assert!(
        reduction >= 0.70,
        "lookup reduction {reduction:.4} < 0.70 (negative_fraction=0.80, fp={fp_rate:.4})"
    );
}
