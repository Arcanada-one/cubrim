//! Produce `application/cubrim` fixtures from the web census corpus.
//!
//! Encoder-side, so it lives in an example rather than in the decoder library:
//! the shipped decoder crate cannot compress, by design.
//!
//! Usage: make_web_fixtures <payload-dir> <out-dir> [block-size]
//!
//! With a block size, frames are cut into multi-block form — the shape a
//! streaming consumer wants, and the one worth exercising through the real
//! WASM module rather than only through Rust tests.

use cubrim::{decode, encode_with_config, EncodeConfig};

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

fn main() {
    let mut args = std::env::args().skip(1);
    let src = args
        .next()
        .expect("usage: make_web_fixtures <payload-dir> <out-dir>");
    let dst = args
        .next()
        .expect("usage: make_web_fixtures <payload-dir> <out-dir>");
    std::fs::create_dir_all(&dst).expect("create out dir");

    let block_size: Option<usize> = args.next().map(|v| v.parse().expect("block size"));

    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = block_size;

    let mut manifest = String::from("name\torig_bytes\tframe_bytes\tratio\n");
    for name in SAMPLES {
        let data = std::fs::read(format!("{src}/{name}")).expect("read payload");
        let frame = encode_with_config(&data, &config);
        // Never publish a fixture that does not round-trip.
        assert_eq!(decode(&frame).expect("decode"), data, "{name}");
        // Not every file yields a web frame: the profile competes against
        // raw-store, and blocking adds a table descriptor per block, so an
        // already-compressed payload can fall back. That is the no-regression
        // rail working, so report it rather than failing.
        let mode = if frame[5] == 18 { "web" } else { "store" };
        std::fs::write(format!("{dst}/{name}.cbr"), &frame).expect("write frame");
        std::fs::write(format!("{dst}/{name}"), &data).expect("write original");
        manifest.push_str(&format!(
            "{name}\t{}\t{}\t{:.4}\n",
            data.len(),
            frame.len(),
            frame.len() as f64 / data.len() as f64
        ));
        println!("{name}: {} -> {} bytes ({mode})", data.len(), frame.len());
    }
    std::fs::write(format!("{dst}/fixtures.tsv"), manifest).expect("write manifest");
}
