//! Generate a seed corpus of valid Cubrim streams for the `decode_hostile`
//! fuzz target.
//!
//! Without seeds the fuzzer spends nearly all of its budget failing the magic
//! check, so the entropy stages — where the interesting decode defects live —
//! are effectively unreachable. Seeding with one valid stream per value scheme
//! puts the fuzzer inside those paths from the first iteration.

use cubrim::config::{EncodeConfig, ValueScheme};
use std::fs;
use std::path::Path;

fn payload(kind: usize) -> Vec<u8> {
    match kind {
        0 => (0..3000u32)
            .flat_map(|i| format!("<li class=\"r{}\">item {}</li>\n", i % 13, i % 31).into_bytes())
            .collect(),
        1 => (0..4000u32)
            .flat_map(|i| format!("{{\"id\":{},\"v\":\"{}\"}},", i, i % 7).into_bytes())
            .collect(),
        2 => vec![b'A'; 2048],
        _ => (0..2048u32).map(|i| (i % 251) as u8).collect(),
    }
}

fn main() {
    let out = Path::new("fuzz/corpus/decode_hostile");
    fs::create_dir_all(out).expect("create corpus dir");

    let schemes = [
        ("bitpack-fixed", ValueScheme::BitpackFixed),
        ("rle-codes", ValueScheme::RleCodes),
        ("entropy", ValueScheme::Entropy),
        ("entropy-context", ValueScheme::EntropyContext),
        ("entropy-context2", ValueScheme::EntropyContext2),
        ("bwt-entropy", ValueScheme::BwtEntropy),
        ("bwt-rans", ValueScheme::BwtRans),
        ("bwt-geo-mix", ValueScheme::BwtGeoMix),
    ];

    let mut written = 0usize;
    for kind in 0..4 {
        let data = payload(kind);
        for (name, scheme) in schemes {
            for square in [true, false] {
                let mut config = EncodeConfig::v1_default();
                config.value_scheme = scheme;
                config.use_square_limit = square;
                let blob = cubrim::encode_with_config(&data, &config);
                // Only seed streams that actually decode — a seed that is
                // already invalid teaches the fuzzer nothing about the format.
                if cubrim::decode(&blob).map(|d| d == data).unwrap_or(false) {
                    let path = out.join(format!("seed-{kind}-{name}-sq{square}.cbm"));
                    fs::write(&path, &blob).expect("write seed");
                    written += 1;
                }
            }
        }
    }
    println!("wrote {written} seeds to {}", out.display());
}
