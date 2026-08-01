use cubrim::config::{EncodeConfig, ValueScheme};
use std::path::{Path, PathBuf};

fn corpus_files() -> Vec<PathBuf> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../bench/web-corpus/payloads-v2");
    let mut files: Vec<PathBuf> = std::fs::read_dir(&root)
        .expect("web corpus is missing")
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.is_file())
        .collect();
    files.sort();
    assert!(!files.is_empty(), "web corpus is empty");
    files
}

fn assert_scheme_roundtrips(scheme: ValueScheme) {
    let files = corpus_files();
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
            Ok(decoded) => corrupted.push(format!("{name}:{}->{}", payload.len(), decoded.len())),
            Err(error) => errored.push(format!("{name}:{error}")),
        }
    }
    assert!(corrupted.is_empty(), "{scheme:?} corrupt: {}", corrupted.join(", "));
    assert!(errored.is_empty(), "{scheme:?} errors: {}", errored.join(", "));
}

#[test]
fn all_shipped_value_schemes_roundtrip_web_corpus() {
    for scheme in [
        ValueScheme::BitpackFixed,
        ValueScheme::RleCodes,
        ValueScheme::Entropy,
        ValueScheme::EntropyContext2,
        ValueScheme::EntropyContext,
        ValueScheme::BwtEntropy,
        ValueScheme::BwtGeoMix,
    ] {
        assert_scheme_roundtrips(scheme);
    }
}
