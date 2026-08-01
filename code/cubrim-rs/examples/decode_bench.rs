//! In-process decode timing.
//!
//! The Phase-A benchmark spawns a subprocess per trial, which costs ~3.1-3.7 ms
//! before any codec work happens. A 13.9 KB sample and a 321 KB sample come out
//! 3.18 ms and 3.97 ms apart there — 23x the data for 1.25x the time — so that
//! harness measures `fork`/`exec`, not decoding, and cannot resolve a
//! 100 MB/s threshold. This binary times the decode call itself.
//!
//! It reports two things:
//!
//! 1. **Whole-stream `decode()` throughput**, the number a Web Profile decode
//!    hypothesis actually needs.
//! 2. **A repeatable whole-stream comparison** on one fixed input and runner;
//!    the before/after source revisions are measured with the same harness.
//!
//! ```text
//! cargo run --release --example decode_bench -- [path ...]
//! ```

use cubrim::config::{EncodeConfig, ValueScheme};
use std::time::Instant;

/// Median of repeated timings, in seconds. Median rather than mean because a
/// scheduler hiccup on a shared host skews the mean and not the middle.
fn median_secs(mut samples: Vec<f64>) -> f64 {
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = samples.len();
    if n % 2 == 1 {
        samples[n / 2]
    } else {
        (samples[n / 2 - 1] + samples[n / 2]) / 2.0
    }
}

fn bench_decode(label: &str, payload: &[u8], scheme: ValueScheme, trials: usize) {
    let mut config = EncodeConfig::v1_default();
    config.value_scheme = scheme;
    config.use_square_limit = false;
    let blob = cubrim::encode_with_config(payload, &config);

    // A benchmark that measured a failing decode would be meaningless.
    let decoded = match cubrim::decode(&blob) {
        Ok(d) => d,
        Err(e) => {
            println!("{label:34} {scheme:?}: decode failed: {e}");
            return;
        }
    };
    if decoded != payload {
        // Several schemes lose data on real files (see tests/scheme_roundtrip.rs).
        // Timing a decoder that returns wrong bytes would be meaningless, so the
        // case is reported and skipped rather than silently benchmarked.
        println!(
            "{label:34} {:<14} SKIPPED — round trip is not exact",
            format!("{scheme:?}")
        );
        return;
    }

    // Warm caches; the first decode also faults in the output allocation.
    for _ in 0..3 {
        let _ = cubrim::decode(&blob);
    }

    let mut times = Vec::with_capacity(trials);
    for _ in 0..trials {
        let start = Instant::now();
        let out = cubrim::decode(&blob).expect("decode");
        let elapsed = start.elapsed().as_secs_f64();
        std::hint::black_box(&out);
        times.push(elapsed);
    }
    let secs = median_secs(times);
    let mib = payload.len() as f64 / (1024.0 * 1024.0);
    println!(
        "{label:34} {:<14} ratio={:.4} decode={:8.3} ms  {:9.3} MiB/s",
        format!("{scheme:?}"),
        blob.len() as f64 / payload.len() as f64,
        secs * 1000.0,
        mib / secs,
    );
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    let mut inputs: Vec<(String, Vec<u8>)> = Vec::new();
    for path in &args {
        match std::fs::read(path) {
            Ok(bytes) => inputs.push((path.clone(), bytes)),
            Err(e) => eprintln!("skip {path}: {e}"),
        }
    }
    if inputs.is_empty() {
        // Structured text with the redundancy real web assets have.
        let synthetic: Vec<u8> = (0..6000u32)
            .flat_map(|i| {
                format!(
                    "<div class=\"row r{}\"><span>value {}</span></div>\n",
                    i % 17,
                    i % 29
                )
                .into_bytes()
            })
            .collect();
        inputs.push(("synthetic-html".to_string(), synthetic));
    }

    let trials: usize = std::env::var("TRIALS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(15);

    println!("=== whole-stream decode(), median of {trials} in-process trials ===");
    for (name, payload) in &inputs {
        let short: String = name
            .rsplit('/')
            .next()
            .unwrap_or(name)
            .chars()
            .take(32)
            .collect();
        for scheme in [
            ValueScheme::Entropy,
            ValueScheme::EntropyContext2,
            ValueScheme::BwtEntropy,
        ] {
            bench_decode(&short, payload, scheme, trials);
        }
        println!();
    }
}
