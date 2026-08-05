//! Measure encoded size under `use_square_limit = false` for every value scheme.
//!
//! The BWT-decline guard only fires on blocks past the u16 primary-index ceiling,
//! which `use_square_limit = false` makes reachable. This prints per-file, per-scheme
//! sizes so the density delta is measured rather than assumed.
use cubrim::{EncodeConfig, ValueScheme};
use std::path::Path;

fn main() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../bench/web-corpus/payloads-v2");
    let mut files: Vec<_> = std::fs::read_dir(&root)
        .expect("corpus")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.is_file())
        .collect();
    files.sort();

    let schemes = [
        ("bwt-entropy", ValueScheme::BwtEntropy),
        ("bwt-geo-mix", ValueScheme::BwtGeoMix),
        ("bwt-rans", ValueScheme::BwtRans),
    ];
    for (name, scheme) in schemes {
        let mut total_in = 0usize;
        let mut total_out = 0usize;
        for path in &files {
            let payload = std::fs::read(path).expect("read");
            let mut config = EncodeConfig::v1_default();
            config.value_scheme = scheme;
            config.use_square_limit = false;
            let blob = cubrim::encode_with_config(&payload, &config);
            let ok = cubrim::decode(&blob).map(|d| d == payload).unwrap_or(false);
            // The emitted scheme byte is the condition that matters: round-trip
            // success alone would also pass if the guard never fired.
            let emitted = cubrim::header::parse_header(&blob)
                .map(|(h, _)| h.value_scheme)
                .map(|b| match ValueScheme::from_byte(b) {
                    Some(s) => format!("{s:?}"),
                    None => format!("byte:{b}"),
                })
                .unwrap_or_else(|_| "hdr-parse-err".to_string());
            println!(
                "{name}\t{}\t{}\t{}\t{}\temitted={emitted}",
                path.file_name().unwrap().to_string_lossy(),
                payload.len(),
                blob.len(),
                if ok { "RT-OK" } else { "RT-FAIL" }
            );
            total_in += payload.len();
            total_out += blob.len();
        }
        println!(
            "{name}\tTOTAL\t{total_in}\t{total_out}\tratio={:.6}",
            total_out as f64 / total_in as f64
        );
    }
}
