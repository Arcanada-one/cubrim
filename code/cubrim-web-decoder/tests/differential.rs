//! The standalone reference decoder must agree with `cubrim::decode`, byte for
//! byte, on valid frames — and must agree about *rejection* on invalid ones.
//!
//! This is the mechanism that keeps a second implementation of the same wire
//! format from drifting away from the first. If someone changes the frame in
//! `cubrim` without changing this crate, these tests fail.

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder as refdec;

const SAMPLES: [&str; 12] = [
    "tailwind.css",
    "html-large-web-codec-v2.html",
    "html-medium-home-v2.html",
    "magic-string.umd.js",
    "sourcemap-codec.umd.js",
    "resolve-uri.umd.js",
    "json-api-large-world-benchmark-v2.json",
    "json-api-medium-web-benchmark-v2.json",
    "json-api-small-hypotheses-v2.json",
    "magic-string.umd.js.map",
    "sourcemap-codec.umd.js.map",
    "inter-latin.medium.woff2",
];

fn corpus_dir() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bench/web-corpus/payloads-v2")
}

fn web_config() -> EncodeConfig {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config
}

/// Deterministic PRNG, so a failure is reproducible from the seed alone.
struct Lcg(u64);

impl Lcg {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        self.0 >> 16
    }
}

#[test]
fn reference_decoder_matches_cubrim_on_the_census() {
    let dir = corpus_dir();
    if !dir.is_dir() {
        eprintln!("census corpus absent at {dir:?}; skipping");
        return;
    }
    for name in SAMPLES {
        let data = std::fs::read(dir.join(name)).unwrap();
        let frame = encode_with_config(&data, &web_config());
        assert_eq!(frame[5], 18, "{name}: expected a MODE_WEB frame");

        let theirs = cubrim::decode(&frame).expect("cubrim decode");
        let ours = refdec::decode(&frame).expect("reference decode");
        assert_eq!(ours, data, "{name}: reference decoder lost bytes");
        assert_eq!(ours, theirs, "{name}: decoders disagree");
    }
}

#[test]
fn reference_decoder_matches_cubrim_on_synthetic_shapes() {
    // Shapes that exercise the branches the census may not: overlapping runs,
    // an all-literal stream, every byte value, and short inputs.
    let mut cases: Vec<Vec<u8>> = vec![
        vec![b'A'; 5000],
        b"abcabcabcabc".repeat(400),
        (0..=255u8).cycle().take(4096).collect(),
        b"{\"k\":[1,2,3]}".repeat(300),
    ];
    let mut rng = Lcg(0xC0FFEE);
    cases.push((0..20_000).map(|_| (rng.next() >> 3) as u8).collect());
    for len in [1usize, 2, 3, 17, 63, 64, 65, 511] {
        cases.push((0..len).map(|i| (i % 11) as u8 + b'a').collect());
    }

    for (idx, data) in cases.iter().enumerate() {
        let frame = encode_with_config(data, &web_config());
        if frame[5] != 18 {
            // The profile competitively picked raw-store; nothing to compare.
            continue;
        }
        let theirs = cubrim::decode(&frame).expect("cubrim decode");
        let ours = refdec::decode(&frame).expect("reference decode");
        assert_eq!(&ours, data, "case {idx}: reference decoder lost bytes");
        assert_eq!(ours, theirs, "case {idx}: decoders disagree");
    }
}

#[test]
fn both_decoders_reject_the_same_corrupted_frames() {
    let data = b"the quick brown fox jumps over the lazy dog ".repeat(60);
    let frame = encode_with_config(&data, &web_config());
    assert_eq!(frame[5], 18);

    let mut rng = Lcg(20_260_811);
    let mut checked = 0usize;
    for _ in 0..4000 {
        let mut corrupt = frame.clone();
        let idx = (rng.next() as usize) % corrupt.len();
        let mask = 1u8 << (rng.next() % 8);
        corrupt[idx] ^= mask;

        let theirs = cubrim::decode(&corrupt);
        let ours = refdec::decode(&corrupt);
        match (&theirs, &ours) {
            (Ok(a), Ok(b)) => assert_eq!(a, b, "decoders returned different output for a mutant"),
            (Err(_), Err(_)) => {}
            (a, b) => panic!("decoders disagree on validity: cubrim={a:?} reference={b:?}"),
        }
        checked += 1;
    }
    assert_eq!(checked, 4000);
}

#[test]
fn hostile_frames_never_panic_and_respect_the_output_limit() {
    let mut rng = Lcg(7);
    // Random bytes wearing a valid-looking header: the shape an attacker sends.
    for _ in 0..3000 {
        let len = 14 + (rng.next() as usize % 400);
        let mut frame: Vec<u8> = (0..len).map(|_| (rng.next() >> 5) as u8).collect();
        frame[0..4].copy_from_slice(&refdec::MAGIC);
        frame[4] = refdec::VERSION;
        frame[5] = refdec::MODE_WEB;
        let _ = refdec::decode(&frame);
    }

    // A frame declaring a gigantic output must be refused before allocating.
    let mut frame = vec![0u8; 64];
    frame[0..4].copy_from_slice(&refdec::MAGIC);
    frame[4] = refdec::VERSION;
    frame[5] = refdec::MODE_WEB;
    frame[6..10].copy_from_slice(&u32::MAX.to_be_bytes());
    let limits = refdec::DecodeLimits {
        max_output_size: 1 << 20,
        ..refdec::DecodeLimits::default()
    };
    let err = refdec::decode_with_limits(&frame, &limits).unwrap_err();
    assert!(err.0.contains("exceeds the limit"), "got {err:?}");
}

#[test]
fn truncation_at_every_length_fails_closed() {
    let data = b"abcdefghij".repeat(200);
    let frame = encode_with_config(&data, &web_config());
    assert_eq!(frame[5], 18);
    for cut in 0..frame.len() {
        let out = refdec::decode(&frame[..cut]);
        assert!(out.is_err(), "truncation to {cut} bytes must fail closed");
    }
    // The whole frame still decodes.
    assert_eq!(refdec::decode(&frame).unwrap(), data);
}

#[test]
fn header_probes_are_honest() {
    let data = b"probe".repeat(500);
    let frame = encode_with_config(&data, &web_config());
    if frame[5] == 18 {
        assert!(refdec::is_web_frame(&frame));
        assert_eq!(refdec::declared_len(&frame), Some(data.len()));
    }
    assert!(!refdec::is_web_frame(b"not a frame at all"));
    assert_eq!(refdec::declared_len(b"short"), None);
}

/// Multi-block frames must decode identically in both implementations.
///
/// The frame format has always carried `BFINAL`, but until the encoder could
/// emit more than one block the multi-block path was specified and untested in
/// both decoders at once. This is the test that makes the specification's
/// claim true.
#[test]
fn both_decoders_agree_on_multi_block_frames() {
    let cases: Vec<Vec<u8>> = vec![
        b"the quick brown fox jumps over the lazy dog ".repeat(200),
        br#"{"k":"v","n":[1,2,3],"pad":"xxxxxxxxxxxxxxxx"}"#.repeat(250),
        vec![b'M'; 30_000],
        (0..=255u8).cycle().take(16_384).collect(),
    ];
    for data in &cases {
        for block_size in [1usize, 64, 1000, 8192] {
            let mut config = web_config();
            config.web_block_size = Some(block_size);
            let frame = encode_with_config(data, &config);
            if frame[5] != 18 {
                continue;
            }
            let theirs = cubrim::decode(&frame).expect("cubrim decode");
            let ours = refdec::decode(&frame).expect("reference decode");
            assert_eq!(&ours, data, "block_size {block_size}: lost bytes");
            assert_eq!(ours, theirs, "block_size {block_size}: decoders disagree");
        }
    }
}

/// A corrupted multi-block frame must be rejected by both, identically.
#[test]
fn both_decoders_reject_the_same_corrupted_multi_block_frames() {
    let data = b"multi block corruption fixture ".repeat(300);
    let mut config = web_config();
    config.web_block_size = Some(512);
    let frame = encode_with_config(&data, &config);
    assert_eq!(frame[5], 18);

    let mut rng = Lcg(4242);
    for _ in 0..2000 {
        let mut corrupt = frame.clone();
        let idx = (rng.next() as usize) % corrupt.len();
        corrupt[idx] ^= 1u8 << (rng.next() % 8);
        match (cubrim::decode(&corrupt), refdec::decode(&corrupt)) {
            (Ok(a), Ok(b)) => assert_eq!(a, b, "different output for a mutant"),
            (Err(_), Err(_)) => {}
            (a, b) => panic!("validity disagreement: cubrim={a:?} reference={b:?}"),
        }
    }
}

/// A page fetching `application/cubrim` can legitimately receive a raw-store
/// frame: the web profile competes against a verbatim copy per file, and an
/// already-compressed asset (WOFF2, PNG) is where compression is correctly
/// declined. A decoder that only understood MODE_WEB would fail on exactly
/// those payloads.
#[test]
fn reference_decoder_handles_raw_store_frames() {
    // Incompressible bytes: the profile must decline and store.
    let mut state = 0x51EEDu32;
    let data: Vec<u8> = (0..30_000)
        .map(|_| {
            state = state.wrapping_mul(1_103_515_245).wrapping_add(12345);
            (state >> 16) as u8
        })
        .collect();
    let frame = encode_with_config(&data, &web_config());
    assert_eq!(frame[5], 1, "expected the raw-store fallback");
    assert!(refdec::is_decodable_frame(&frame));
    assert!(!refdec::is_web_frame(&frame));
    assert_eq!(refdec::declared_len(&frame), Some(data.len()));

    let ours = refdec::decode(&frame).expect("reference decode of a raw frame");
    let theirs = cubrim::decode(&frame).expect("cubrim decode");
    assert_eq!(ours, data);
    assert_eq!(ours, theirs);
}

#[test]
fn raw_store_frames_respect_limits_and_truncation() {
    let data = vec![0xA5u8; 5000];
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = Some(16); // blocking makes store win
    let frame = encode_with_config(&data, &config);
    if frame[5] != 1 {
        return; // the web frame still won; nothing to assert here
    }
    let limits = refdec::DecodeLimits {
        max_output_size: data.len() - 1,
        ..refdec::DecodeLimits::default()
    };
    let err = refdec::decode_with_limits(&frame, &limits).unwrap_err();
    assert!(err.0.contains("exceeds the limit"), "got {err:?}");
    for cut in 0..frame.len() {
        assert!(
            refdec::decode(&frame[..cut]).is_err(),
            "truncation to {cut} must fail closed"
        );
    }
}
