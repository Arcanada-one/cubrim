//! Tripwire: the value-scheme round-trip gate does not currently exercise the
//! schemes it names.
//!
//! `tests/scheme_roundtrip.rs` is the CI job called *Lossless scheme
//! round-trip* — the silent-data-loss gate. It forces
//! `EncodeConfig::value_scheme` to each of seven schemes and round-trips the
//! web corpus. But `value_scheme` selects the **cube path's** value coder,
//! while `encode_with_config` runs a competitive rail over whole-file
//! candidates and keeps the smallest. On this corpus CM2 wins every file, so
//! all seven "different scheme" runs produce **byte-identical archives through
//! the CM2 path**. The gate is one test wearing seven names: every BWT, rANS
//! and entropy-context coder could be catastrophically broken and it would
//! still pass.
//!
//! Measured 2026-08-11 on `tailwind.css`: BitpackFixed, Entropy,
//! EntropyContext, BwtEntropy, BwtGeoMix and LzRans all emit 6,847 bytes with
//! mode byte 16 (MODE_CM2). One distinct output from six requested schemes.
//!
//! **This file exists to fail when that is fixed.** It asserts the current,
//! undesirable reality. The day someone gives the encoder a way to reach the
//! forced scheme — a config knob that suppresses the rail, or a per-scheme
//! entry point — this test starts failing, and the correct response is to
//! delete it and make `scheme_roundtrip.rs` genuinely exercise seven paths.
//! A silent false-green is worse than a red test; a tripwire converts one into
//! the other.
//!
//! Reference: `documentation/ephemeral/reviews/CUBR-0075-BRANCH-TRIAGE-20260811.md`.

use cubrim::config::{EncodeConfig, ValueScheme};
use std::path::{Path, PathBuf};

const SCHEMES: [ValueScheme; 6] = [
    ValueScheme::BitpackFixed,
    ValueScheme::Entropy,
    ValueScheme::EntropyContext,
    ValueScheme::BwtEntropy,
    ValueScheme::BwtGeoMix,
    ValueScheme::LzRans,
];

/// The mode byte the competitive rail actually selects for this corpus.
const MODE_CM2: u8 = 16;

fn corpus_file(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../bench/web-corpus/payloads-v2")
        .join(name)
}

fn encode_forced(data: &[u8], scheme: ValueScheme) -> Vec<u8> {
    let mut config = EncodeConfig::v1_default();
    config.value_scheme = scheme;
    // Exactly what scheme_roundtrip.rs does.
    config.use_square_limit = false;
    cubrim::encode_with_config(data, &config)
}

#[test]
fn forcing_a_value_scheme_is_currently_inert_through_the_public_api() {
    let path = corpus_file("tailwind.css");
    if !path.is_file() {
        eprintln!("web corpus absent; skipping");
        return;
    }
    let data = std::fs::read(&path).expect("read corpus file");

    let outputs: Vec<Vec<u8>> = SCHEMES.iter().map(|&s| encode_forced(&data, s)).collect();
    let first = &outputs[0];

    for (scheme, blob) in SCHEMES.iter().zip(&outputs) {
        assert_eq!(
            blob, first,
            "{scheme:?} produced a DIFFERENT archive from BitpackFixed.\n\
             \n\
             That is good news and this test is now obsolete: forcing a value \
             scheme has become effective through the public API.\n\
             Delete this file and strengthen tests/scheme_roundtrip.rs, which \
             has been passing seven times over the same CM2 path and must now \
             be made to exercise the schemes it names."
        );
        assert_eq!(
            blob[5], MODE_CM2,
            "{scheme:?} selected mode {} rather than CM2 — the rail's behaviour \
             changed; re-derive what scheme_roundtrip.rs actually covers",
            blob[5]
        );
    }
}

/// The same inertness, stated as the property that makes the gate weak: the
/// number of distinct archives produced by N requested schemes is 1.
#[test]
fn the_roundtrip_gate_covers_one_encode_path_not_seven() {
    let path = corpus_file("json-api-small-hypotheses-v2.json");
    if !path.is_file() {
        eprintln!("web corpus absent; skipping");
        return;
    }
    let data = std::fs::read(&path).expect("read corpus file");

    let distinct: std::collections::HashSet<Vec<u8>> =
        SCHEMES.iter().map(|&s| encode_forced(&data, s)).collect();

    assert_eq!(
        distinct.len(),
        1,
        "the value-scheme rail now yields {} distinct archives for {} requested \
         schemes — the gate can and should be strengthened; see this file's \
         module comment",
        distinct.len(),
        SCHEMES.len()
    );
}
