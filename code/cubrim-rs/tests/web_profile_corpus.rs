//! CUBR-0076 step-2 gate: the web-profile prototype on the real web census.
//!
//! Byte-exact round trip through the PUBLIC decode entry point on all 12
//! census payloads, and the density bar the size model predicted, asserted as
//! a test rather than reported as a claim.
//!
//! Bytes only. Nothing here is timed, on this host or any other.

use cubrim::{decode, encode, encode_web_dynamic, encode_with_config, EncodeConfig};
use std::path::{Path, PathBuf};

/// Per-sample gzip-9 and brotli-11 baselines, from
/// `documentation/ephemeral/research/CUBR-0076-DENSITY-20260806/baselines.tsv`.
/// (file name, gzip-9 bytes, brotli-11 bytes)
const CENSUS: [(&str, usize, usize); 12] = [
    ("tailwind.css", 11278, 9161),
    ("html-large-web-codec-v2.html", 15804, 11746),
    ("html-medium-home-v2.html", 5801, 4763),
    ("magic-string.umd.js", 9896, 8672),
    ("sourcemap-codec.umd.js", 3705, 3280),
    ("resolve-uri.umd.js", 2895, 2467),
    ("json-api-large-world-benchmark-v2.json", 21196, 14910),
    ("json-api-medium-web-benchmark-v2.json", 10516, 8344),
    ("json-api-small-hypotheses-v2.json", 1674, 1383),
    ("magic-string.umd.js.map", 20194, 17827),
    ("sourcemap-codec.umd.js.map", 2546, 2319),
    ("inter-latin.medium.woff2", 23688, 23623),
];

/// Aggregate gzip-9 bytes over the census — the hypothesis-12 GO density bar.
const GZIP9_BAR: usize = 129_193;
/// Aggregate brotli-11 bytes over the census — the WIN density bar.
const BROTLI11_BAR: usize = 108_495;

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../bench/web-corpus/payloads-v2")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from("/nonexistent"))
}

fn web_config() -> EncodeConfig {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config
}

#[test]
fn web_profile_round_trips_the_whole_census_byte_exactly() {
    let dir = corpus_dir();
    if !dir.is_dir() {
        eprintln!("census corpus not present at {dir:?}; skipping");
        return;
    }

    let mut total = 0usize;
    let mut total_gzip9 = 0usize;
    let mut total_brotli11 = 0usize;
    let mut beat_gzip9 = 0usize;
    let mut selected_web = 0usize;

    println!(
        "{:<40} {:>9} {:>9} {:>9} {:>9} {:>7} {:>7}",
        "sample", "orig", "web", "gzip9", "brotli11", "vs_gz", "mode"
    );
    for (name, gzip9, brotli11) in CENSUS {
        let path = dir.join(name);
        let data = std::fs::read(&path).unwrap_or_else(|e| panic!("read {path:?}: {e}"));

        let blob = encode_with_config(&data, &web_config());
        let decoded = decode(&blob).unwrap_or_else(|e| panic!("{name}: decode failed: {e}"));
        assert_eq!(
            decoded, data,
            "{name}: web-profile round trip must be byte-exact"
        );

        let is_web = blob[5] == 18;
        if is_web {
            selected_web += 1;
        }
        if blob.len() <= gzip9 {
            beat_gzip9 += 1;
        }
        total += blob.len();
        total_gzip9 += gzip9;
        total_brotli11 += brotli11;
        println!(
            "{:<40} {:>9} {:>9} {:>9} {:>9} {:>7.3} {:>7}",
            name,
            data.len(),
            blob.len(),
            gzip9,
            brotli11,
            blob.len() as f64 / gzip9 as f64,
            if is_web { "web" } else { "other" }
        );
    }

    println!(
        "TOTAL web={total} gzip9={total_gzip9} brotli11={total_brotli11} \
         vs_gz={:.4} vs_br={:.4} beat_gzip9={beat_gzip9}/12 selected_web={selected_web}/12",
        total as f64 / total_gzip9 as f64,
        total as f64 / total_brotli11 as f64
    );

    assert_eq!(total_gzip9, GZIP9_BAR, "baseline table drifted");
    assert_eq!(total_brotli11, BROTLI11_BAR, "baseline table drifted");
    assert!(
        total <= GZIP9_BAR,
        "web profile must hold gzip-9 density parity: {total} > {GZIP9_BAR}"
    );
}

#[test]
fn web_profile_off_is_byte_identical_to_the_default_encoder() {
    let dir = corpus_dir();
    if !dir.is_dir() {
        eprintln!("census corpus not present at {dir:?}; skipping");
        return;
    }
    for (name, _, _) in CENSUS {
        let data = std::fs::read(dir.join(name)).unwrap();
        let default_blob = encode(&data);
        let explicit = encode_with_config(&data, &EncodeConfig::v1_default());
        assert_eq!(
            default_blob, explicit,
            "{name}: default config must match encode()"
        );
        assert_ne!(
            default_blob[5], 18,
            "{name}: MODE_WEB must never appear with the profile off"
        );
    }
}

#[test]
fn web_profile_never_regresses_a_file() {
    // A payload the web scheme cannot win: high-entropy bytes, where the
    // incumbent raw-store path is already optimal.
    let mut state = 0x5EED_1234u32;
    let data: Vec<u8> = (0..40_000)
        .map(|_| {
            state = state.wrapping_mul(1_103_515_245).wrapping_add(12345);
            (state >> 16) as u8
        })
        .collect();
    let incumbent = encode(&data);
    let with_web = encode_with_config(&data, &web_config());
    assert!(
        with_web.len() <= incumbent.len(),
        "competitive pick must never grow a file: {} > {}",
        with_web.len(),
        incumbent.len()
    );
    assert_eq!(decode(&with_web).unwrap(), data);
}

#[test]
fn dynamic_web_profile_is_public_and_streaming_compatible() {
    let data = br#"{"dynamic":true,"payload":"near-realtime"}"#.repeat(500);
    let frame = encode_web_dynamic(&data, Some(256)).expect("dynamic frame");
    assert_eq!(frame[5], 18, "dynamic mode uses the Web Profile frame");
    assert_eq!(decode(&frame).unwrap(), data);
}

#[test]
fn dynamic_web_profile_round_trips_the_real_census() {
    let dir = corpus_dir();
    if !dir.is_dir() {
        eprintln!("census corpus not present at {dir:?}; skipping");
        return;
    }

    let mut total = 0usize;
    let mut selected_smaller_than_identity = 0usize;
    for (name, _, _) in CENSUS {
        let data = std::fs::read(dir.join(name)).unwrap();
        let frame = encode_web_dynamic(&data, Some(65_536)).expect("dynamic frame");
        assert_eq!(frame[5], 18, "{name}: dynamic mode must emit MODE_WEB");
        assert_eq!(decode(&frame).unwrap(), data, "{name}: round trip");
        if frame.len() < data.len() {
            selected_smaller_than_identity += 1;
        }
        total += frame.len();
    }
    println!(
        "dynamic web census: total_frame_bytes={total}, smaller_than_identity={selected_smaller_than_identity}/12"
    );
    assert!(selected_smaller_than_identity >= 10);
}
