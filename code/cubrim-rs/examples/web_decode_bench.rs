//! Whole-buffer decode-throughput harness for the web profile (CUBR-0076).
//!
//! Measures what hypothesis 12's decode criterion is written against: bytes of
//! ORIGINAL content produced per second by a single-threaded whole-buffer
//! decode of the web-profile archive. Every timed decode is verified
//! byte-exact against the source; an observation without a passing check is
//! not an observation.
//!
//! Protocol implemented here (the caller supplies the quiet host and the pin):
//!   * warmups before any timed iteration,
//!   * a randomized sample schedule per round, seeded and reported, so a drift
//!     in background load cannot be absorbed by a fixed ordering,
//!   * repeated rounds with the per-sample MINIMUM time reported (the least
//!     contaminated observation) alongside the median,
//!   * load admission printed before and after, for the caller to record.
//!
//! Usage:
//!   web_decode_bench <corpus-dir> [rounds] [warmups] [seed]

use cubrim::{decode, encode_with_config, EncodeConfig};
use std::time::Instant;

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

/// Deterministic PRNG — the schedule must be reproducible from the seed.
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

fn load_avg() -> String {
    std::fs::read_to_string("/proc/loadavg")
        .map(|s| s.split_whitespace().take(3).collect::<Vec<_>>().join(" "))
        .unwrap_or_else(|_| "unavailable".into())
}

fn main() {
    let mut args = std::env::args().skip(1);
    let dir = args
        .next()
        .expect("usage: web_decode_bench <corpus-dir> [rounds] [warmups] [seed]");
    let rounds: usize = args.next().map(|v| v.parse().unwrap()).unwrap_or(9);
    let warmups: usize = args.next().map(|v| v.parse().unwrap()).unwrap_or(3);
    let seed: u64 = args
        .next()
        .map(|v| v.parse().unwrap())
        .unwrap_or(20_260_811);

    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;

    println!("# admission-before loadavg: {}", load_avg());
    println!("# rounds={rounds} warmups={warmups} seed={seed}");

    let mut payloads = Vec::new();
    for name in SAMPLES {
        let data = std::fs::read(format!("{dir}/{name}"))
            .unwrap_or_else(|e| panic!("read {dir}/{name}: {e}"));
        let blob = encode_with_config(&data, &config);
        let decoded = decode(&blob).expect("decode");
        assert_eq!(
            decoded, data,
            "{name}: archive must round-trip byte-exactly"
        );
        payloads.push((name, data, blob));
    }

    // Warmups, in fixed order — untimed.
    for _ in 0..warmups {
        for (_, data, blob) in &payloads {
            let out = decode(blob).expect("warmup decode");
            assert_eq!(&out, data);
        }
    }

    let mut times: Vec<Vec<f64>> = vec![Vec::with_capacity(rounds); payloads.len()];
    let mut rng = Lcg(seed);
    for _ in 0..rounds {
        // Randomized schedule for this round (Fisher-Yates over the indices).
        let mut order: Vec<usize> = (0..payloads.len()).collect();
        for i in (1..order.len()).rev() {
            let j = (rng.next() as usize) % (i + 1);
            order.swap(i, j);
        }
        for &idx in &order {
            let (name, data, blob) = &payloads[idx];
            let start = Instant::now();
            let out = decode(blob).expect("timed decode");
            let elapsed = start.elapsed().as_secs_f64();
            assert_eq!(out.len(), data.len(), "{name}: length");
            assert_eq!(&out, data, "{name}: byte-exact check inside the timed loop");
            times[idx].push(elapsed);
        }
    }

    println!(
        "{:<40} {:>10} {:>9} {:>12} {:>12}",
        "sample", "orig_bytes", "archive", "best_MB_s", "median_MB_s"
    );
    let mut total_bytes = 0usize;
    let mut total_best = 0f64;
    for (idx, (name, data, blob)) in payloads.iter().enumerate() {
        let mut t = times[idx].clone();
        t.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let best = t[0];
        let median = t[t.len() / 2];
        total_bytes += data.len();
        total_best += best;
        println!(
            "{:<40} {:>10} {:>9} {:>12.2} {:>12.2}",
            name,
            data.len(),
            blob.len(),
            data.len() as f64 / best / 1e6,
            data.len() as f64 / median / 1e6
        );
    }
    println!(
        "AGGREGATE bytes={total_bytes} best_total_s={total_best:.6} \
         corpus_best_MB_s={:.2}",
        total_bytes as f64 / total_best / 1e6
    );
    println!("# admission-after loadavg: {}", load_avg());
}
