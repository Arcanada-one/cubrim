//! Round-trip every value scheme against the real web corpus.
//!
//! Cubrim is a lossless compressor, so the only acceptable outcomes for
//! `decode(encode(x))` are `x` or a hard error. Returning `Ok` with different
//! bytes is silent data loss, and matching output lengths do not make it
//! detectable to callers that only check the framing.
//!
//! The web corpus is committed under `bench/web-corpus/payloads-v2`, so these
//! cases run in every checkout and in CI rather than depending on ignored
//! research material.

use cubrim::config::{EncodeConfig, ValueScheme};
use std::path::{Path, PathBuf};

fn corpus_files() -> Vec<PathBuf> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bench/web-corpus/payloads-v2");
    let Ok(entries) = std::fs::read_dir(&root) else {
        return vec![];
    };
    let mut files: Vec<PathBuf> = entries
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_file())
        .collect();
    files.sort();
    files
}

/// `decode(encode(x))` must equal `x`, or fail loudly. Never a quiet wrong answer.
fn assert_scheme_roundtrips(scheme: ValueScheme) {
    let files = corpus_files();
    assert!(
        !files.is_empty(),
        "web corpus is missing; this suite proves nothing without it"
    );

    let mut corrupted = Vec::new();
    let mut errored = Vec::new();
    for path in &files {
        let payload = std::fs::read(path).expect("read corpus file");
        let mut config = EncodeConfig::v1_default();
        config.value_scheme = scheme;
        config.use_square_limit = false;
        let blob = cubrim::encode_with_config(&payload, &config);
        let name = path.file_name().unwrap().to_string_lossy().to_string();
        match cubrim::decode(&blob) {
            Ok(decoded) if decoded == payload => {}
            Ok(decoded) => corrupted.push(format!(
                "{name} (in {} B, out {} B)",
                payload.len(),
                decoded.len()
            )),
            Err(e) => errored.push(format!("{name}: {e}")),
        }
    }

    assert!(
        corrupted.is_empty(),
        "{scheme:?} SILENTLY CORRUPTED {} of {} files — decode() returned Ok with wrong bytes:\n  {}",
        corrupted.len(),
        files.len(),
        corrupted.join("\n  ")
    );
    assert!(
        errored.is_empty(),
        "{scheme:?} failed to decode its own output for {} of {} files:\n  {}",
        errored.len(),
        files.len(),
        errored.join("\n  ")
    );
}

#[test]
fn bitpack_fixed_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::BitpackFixed);
}

#[test]
fn rle_codes_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::RleCodes);
}

#[test]
fn entropy_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::Entropy);
}

#[test]
fn entropy_context2_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::EntropyContext2);
}

#[test]
fn entropy_context_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::EntropyContext);
}

#[test]
fn bwt_entropy_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::BwtEntropy);
}

#[test]
fn bwt_geo_mix_roundtrips_the_web_corpus() {
    assert_scheme_roundtrips(ValueScheme::BwtGeoMix);
}
