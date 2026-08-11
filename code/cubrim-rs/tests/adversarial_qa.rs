//! Adversarial QA harness for Cubrim-2 industrial reliability (MONITOR-DIRECTIVE
//! 2026-07-23 / [QA-C]). It hunts for inputs that break the codec invariants:
//!
//!   (1) RT byte-exact:      decode(encode(x)) == x  for every input.
//!   (2) determinism:        encode(x) == encode(x).
//!   (3) fail-safe size:     encode(x).len() <= x.len() + BOUND (never blows up).
//!   (4) fail-closed decode:  a corrupt / truncated blob returns Err — never
//!                            panics, never hangs on a huge length field, never
//!                            returns silently-wrong bytes for a header mutation.
//!
//! Input classes: empty / 1-byte / boundary sizes (64 KB block, u16 index) /
//! all-same-byte / structural (MZ-heavy exe gate, alternating, incrementing,
//! nested .cub) / seeded pseudo-random. RT is also checked adversarially against
//! every value-scheme (LZ / BWT-rANS / GeoCM / CM paths) via encode_with_config.
//!
//! Deterministic: a fixed-seed xorshift RNG, no external rand. Any failure prints
//! the class + a reproducing description; a decode panic is caught and reported
//! as a fail-closed violation (never an unhandled abort).

use std::panic::{catch_unwind, AssertUnwindSafe};

use cubrim::{decode, encode, encode_with_config, EncodeConfig, ValueScheme};

const EXPAND_BOUND: usize = 512; // header/frame overhead ceiling over the input size

// ---- deterministic xorshift RNG (reproducible corpus, no rand crate) ----
struct Rng(u64);
impl Rng {
    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
    fn byte(&mut self) -> u8 {
        (self.next_u64() & 0xff) as u8
    }
    fn fill(&mut self, n: usize) -> Vec<u8> {
        (0..n).map(|_| self.byte()).collect()
    }
}

/// The core invariant: round-trip byte-exact + deterministic + bounded expansion.
fn assert_rt(class: &str, data: &[u8]) {
    let blob = catch_unwind(AssertUnwindSafe(|| encode(data)))
        .unwrap_or_else(|_| panic!("[{class}] encode PANICKED on {}-byte input", data.len()));
    // determinism
    let blob2 = encode(data);
    assert_eq!(blob, blob2, "[{class}] encode not deterministic ({} bytes)", data.len());
    // fail-safe size bound
    assert!(
        blob.len() <= data.len() + EXPAND_BOUND,
        "[{class}] output blew up: {} -> {} (bound {}+{})",
        data.len(), blob.len(), data.len(), EXPAND_BOUND
    );
    // round-trip byte-exact, decode must not panic
    let decoded = catch_unwind(AssertUnwindSafe(|| decode(&blob)))
        .unwrap_or_else(|_| panic!("[{class}] decode PANICKED on a self-produced blob ({} bytes)", data.len()));
    let decoded = decoded.unwrap_or_else(|e| panic!("[{class}] decode ERRORED on a self-produced blob: {e}"));
    assert!(decoded == data, "[{class}] ROUND-TRIP MISMATCH: {} bytes in, {} bytes out", data.len(), decoded.len());
}

/// RT under an explicit value-scheme (adversarial to a specific mode).
fn assert_rt_scheme(class: &str, data: &[u8], scheme: ValueScheme) {
    let mut cfg = EncodeConfig::v1_default();
    cfg.value_scheme = scheme;
    let blob = match catch_unwind(AssertUnwindSafe(|| encode_with_config(data, &cfg))) {
        Ok(b) => b,
        Err(_) => panic!("[{class}/{scheme:?}] encode_with_config PANICKED ({} bytes)", data.len()),
    };
    let decoded = catch_unwind(AssertUnwindSafe(|| decode(&blob)))
        .unwrap_or_else(|_| panic!("[{class}/{scheme:?}] decode PANICKED ({} bytes)", data.len()))
        .unwrap_or_else(|e| panic!("[{class}/{scheme:?}] decode ERRORED: {e}"));
    assert!(decoded == data, "[{class}/{scheme:?}] ROUND-TRIP MISMATCH ({} bytes)", data.len());
}

// ---------------------------------------------------------------------------
// (1)+(2)+(3): RT / determinism / size over adversarial input classes
// ---------------------------------------------------------------------------

#[test]
fn rt_empty_and_tiny() {
    assert_rt("empty", &[]);
    for b in 0u16..=255 {
        assert_rt("one-byte", &[b as u8]);
    }
    assert_rt("two-byte", &[0x4d, 0x5a]); // "MZ"
}

#[test]
fn rt_size_boundaries() {
    // Around the 64 KB chunk block size / u16 primary_index boundary and multiples.
    let sizes = [
        63, 255, 256, 257, 4095, 4096, 65535, 65536, 65537, 65600, 131071, 131072, 131073, 200_000,
    ];
    let mut rng = Rng(0xC0FFEE);
    for &n in &sizes {
        assert_rt(&format!("boundary-zeros-{n}"), &vec![0u8; n]);
        assert_rt(&format!("boundary-ff-{n}"), &vec![0xffu8; n]);
        let r = rng.fill(n);
        assert_rt(&format!("boundary-rand-{n}"), &r);
    }
}

#[test]
fn rt_all_same_byte_values() {
    // Pathological runs of every byte value at a mid size (exercises RLE/BWT paths).
    for v in 0u16..=255 {
        assert_rt(&format!("run-{v}"), &vec![v as u8; 70_000]);
    }
}

#[test]
fn rt_structural_patterns() {
    // MZ-heavy (exe/BCJ gate), alternating, incrementing, sparse-spikes, text-like.
    let mz: Vec<u8> = (0..80_000).map(|i| if i % 64 < 2 { if i % 64 == 0 { 0x4d } else { 0x5a } } else { (i % 251) as u8 }).collect();
    assert_rt("mz-heavy", &mz);

    let alt: Vec<u8> = (0..80_000).map(|i| if i % 2 == 0 { 0x00 } else { 0xff }).collect();
    assert_rt("alternating", &alt);

    let inc: Vec<u8> = (0..80_000).map(|i| (i % 256) as u8).collect();
    assert_rt("incrementing", &inc);

    let mut spikes = vec![0u8; 80_000];
    for i in (0..spikes.len()).step_by(997) { spikes[i] = 0xAA; }
    assert_rt("sparse-spikes", &spikes);

    let text: Vec<u8> = "the quick brown fox jumps over the lazy dog 0123456789\n"
        .bytes().cycle().take(120_000).collect();
    assert_rt("text-like", &text);
}

#[test]
fn rt_nested_recompression() {
    // Compress structured data, then compress the compressed blob (high-entropy),
    // then compress *that* — exercises the incompressible/random path via real blobs.
    let base: Vec<u8> = "nested payload ".bytes().cycle().take(90_000).collect();
    let b1 = encode(&base);
    assert_rt("nested-1", &b1);
    let b2 = encode(&b1);
    assert_rt("nested-2", &b2);
}

#[test]
fn rt_random_fuzz_many_sizes() {
    // Seeded random inputs across a spread of sizes and seeds.
    for seed in 0u64..24 {
        let mut rng = Rng(0x9E3779B97F4A7C15 ^ seed.wrapping_mul(0x2545F4914F6CDD1D));
        let n = (rng.next_u64() % 150_000) as usize;
        let data = rng.fill(n);
        assert_rt(&format!("fuzz-seed{seed}-n{n}"), &data);
    }
}

#[test]
fn rt_adversarial_per_scheme() {
    // Each value-scheme must round-trip every class (adversarial to each mode).
    let schemes = [
        ValueScheme::BitpackFixed,
        ValueScheme::BwtRans,
        ValueScheme::BwtGeoMix,
        ValueScheme::BwtContextMix,
        ValueScheme::LzRans,
        ValueScheme::Order2Rans,
    ];
    let mut rng = Rng(0xDEADBEEF);
    let inputs: Vec<(String, Vec<u8>)> = vec![
        ("empty".into(), vec![]),
        ("one".into(), vec![0x00]),
        ("run-zero".into(), vec![0u8; 70_000]),
        ("mz".into(), (0..70_000).map(|i| if i % 2 == 0 { 0x4d } else { 0x5a }).collect()),
        ("text".into(), "abcdefgh ".bytes().cycle().take(70_000).collect()),
        ("rand".into(), rng.fill(70_000)),
    ];
    for scheme in schemes {
        for (name, data) in &inputs {
            assert_rt_scheme(name, data, scheme);
        }
    }
}

// ---------------------------------------------------------------------------
// (4): fail-closed decode — corrupt / truncated / hostile blobs
// ---------------------------------------------------------------------------

/// decode must never panic and never hang; it either returns Ok (a benign
/// mutation that happens to stay valid) or Err. A panic is a fail-closed defect.
fn decode_must_not_panic(label: &str, blob: &[u8]) {
    let owned = blob.to_vec();
    let res = catch_unwind(AssertUnwindSafe(|| decode(&owned)));
    if res.is_err() {
        panic!("[fail-closed] decode PANICKED on {label} ({} bytes) — must return Err, not panic", blob.len());
    }
    // Ok or Err are both acceptable; we only forbid panic / UB / hang.
}

#[test]
fn decode_truncation_is_fail_closed() {
    // A valid blob truncated at every prefix length must never panic.
    let inputs: Vec<Vec<u8>> = vec![
        vec![0u8; 70_000],
        "structured text ".bytes().cycle().take(80_000).collect(),
        (0..80_000u32).map(|i| (i % 256) as u8).collect(),
    ];
    for data in &inputs {
        let blob = encode(data);
        // sample prefixes: all short ones + a stride over the rest
        let len = blob.len();
        let mut cuts: Vec<usize> = (0..len.min(64)).collect();
        cuts.extend((64..len).step_by((len / 200).max(1)));
        for cut in cuts {
            decode_must_not_panic(&format!("truncate@{cut}/{len}"), &blob[..cut]);
        }
    }
}

#[test]
fn decode_header_mutation_is_fail_closed() {
    let data: Vec<u8> = "header mutation corpus ".bytes().cycle().take(90_000).collect();
    let blob = encode(&data);
    // Flip every bit in the first 32 header bytes (magic/version/mode/length region).
    for i in 0..blob.len().min(32) {
        for bit in 0..8u8 {
            let mut m = blob.clone();
            m[i] ^= 1 << bit;
            decode_must_not_panic(&format!("hdrflip@{i}.{bit}"), &m);
            // If it decodes Ok, it must NOT silently differ from the original AND
            // claim success on a corrupted header — a benign flip that still
            // reproduces the input is fine; a flip that yields different bytes but
            // Ok would be a silent-corruption defect.
            let owned = m.clone();
            if let Ok(Ok(out)) = catch_unwind(AssertUnwindSafe(move || decode(&owned))) {
                assert!(
                    out == data,
                    "[silent-corruption] hdrflip@{i}.{bit} decoded Ok but bytes differ ({} vs {})",
                    out.len(), data.len()
                );
            }
        }
    }
}

#[test]
fn decode_hostile_length_fields_no_oom_no_panic() {
    // Blobs whose length/count fields are set to huge values must fail cleanly,
    // not attempt a multi-GB allocation or panic. Build minimal headers with the
    // real magic and drive the length fields to the extreme.
    let base = encode(&vec![7u8; 1000]);
    // Overwrite bytes 6..10 (typical u32 length/count field just after magic+ver+mode)
    // and a few other offsets with 0xFF (max) — decode must reject, not OOM.
    for off in [5usize, 6, 7, 8, 9, 10, 11, 12] {
        if off + 4 > base.len() { continue; }
        let mut m = base.clone();
        for k in 0..4 { m[off + k] = 0xff; }
        decode_must_not_panic(&format!("hugelen@{off}"), &m);
    }
    // Pure hostile: magic + version + mode + max length, nothing else.
    let magic = [0xCB, b'R', b'I', b'M'];
    for mode in 0u8..16 {
        let mut m = Vec::new();
        m.extend_from_slice(&magic);
        m.push(1); // version
        m.push(mode);
        m.extend_from_slice(&u32::MAX.to_be_bytes());
        m.extend_from_slice(&[0xff; 8]);
        decode_must_not_panic(&format!("hostile-mode{mode}"), &m);
    }
}

#[test]
fn decode_random_garbage_is_fail_closed() {
    let mut rng = Rng(0x1234_5678_9ABC_DEF0);
    for i in 0..2000 {
        let n = (rng.next_u64() % 256) as usize;
        let mut g = rng.fill(n);
        // Half the time, prefix with the real magic so decode goes past magic check.
        if i % 2 == 0 && g.len() >= 4 {
            g[0] = 0xCB; g[1] = b'R'; g[2] = b'I'; g[3] = b'M';
        }
        decode_must_not_panic(&format!("garbage{i}-n{n}"), &g);
    }
}
