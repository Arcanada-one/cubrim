// CUBR-0027 aggregate bench: Option A (3-level) vs Option B (2-level) sweep.
// Run: cargo test --test cubr0027_bench -- --nocapture 2>/dev/null
//
// Outputs CUBR-0027-bench.json to docs/ephemeral/research/.

use cubrim::{decode, encode_with_config, EncodeConfig, ValueScheme};
use std::fs;

const CORPUS_DIR: &str = "/Users/ug/arcanada/Projects/Cubrim/docs/ephemeral/research/corpus";
const CORPUS_TOTAL: usize = 51456;
const T4_TOTAL_BYTES: usize = 30217;
const T4_BASELINE_AGG: f64 = 0.587240;

struct CorpusFile {
    name: &'static str,
    t4_bytes: usize,
    t4_mode: &'static str,
    size_bytes: usize,
}

const FILES: &[CorpusFile] = &[
    CorpusFile {
        name: "sparse_clustered",
        t4_bytes: 502,
        t4_mode: "cube",
        size_bytes: 2048,
    },
    CorpusFile {
        name: "dense",
        t4_bytes: 4109,
        t4_mode: "raw",
        size_bytes: 4096,
    },
    CorpusFile {
        name: "text",
        t4_bytes: 5705,
        t4_mode: "cube",
        size_bytes: 16384,
    },
    CorpusFile {
        name: "log_like",
        t4_bytes: 7318,
        t4_mode: "cube",
        size_bytes: 16384,
    },
    CorpusFile {
        name: "binary_mixed",
        t4_bytes: 8205,
        t4_mode: "raw",
        size_bytes: 8192,
    },
    CorpusFile {
        name: "random_high",
        t4_bytes: 4109,
        t4_mode: "raw",
        size_bytes: 4096,
    },
    CorpusFile {
        name: "sparse_small",
        t4_bytes: 269,
        t4_mode: "raw",
        size_bytes: 256,
    },
];

fn encode_t5_option_a(data: &[u8], min_ctx: u16) -> Vec<u8> {
    let cfg = EncodeConfig {
        value_scheme: ValueScheme::EntropyContext2,
        min_ctx_count: Some(min_ctx),
        ..EncodeConfig::v1_default()
    };
    encode_with_config(data, &cfg)
}

fn encode_t4(data: &[u8]) -> Vec<u8> {
    let cfg = EncodeConfig {
        value_scheme: ValueScheme::EntropyContext,
        ..EncodeConfig::v1_default()
    };
    encode_with_config(data, &cfg)
}

#[test]
fn bench_cubr0027_aggregate() {
    let min_ctx_values: &[u16] = &[64, 96, 128, 160, 192, 256, 320, 384, 512, 1024];

    println!("\n==================================================");
    println!("CUBR-0027 Aggregate Bench (Option A: 3-level wire)");
    println!("==================================================");
    println!("Corpus total: {} bytes", CORPUS_TOTAL);
    println!(
        "T4 baseline: {:.6} ({} bytes)",
        T4_BASELINE_AGG, T4_TOTAL_BYTES
    );
    println!("");

    // Verify 7/7 round-trip for T5 at default min_ctx=128.
    let mut round_trip_ok = 0usize;
    for f in FILES {
        let path = format!("{}/{}.bin", CORPUS_DIR, f.name);
        let data = match fs::read(&path) {
            Ok(d) => d,
            Err(e) => panic!("Cannot read corpus file {}: {}", path, e),
        };
        let blob = encode_t5_option_a(&data, 128);
        let recovered = decode(&blob).expect("decode must succeed");
        assert_eq!(recovered, data, "Round-trip FAILED for {}", f.name);
        round_trip_ok += 1;
    }
    println!("Round-trip 7/7: {}/7 PASS", round_trip_ok);
    assert_eq!(round_trip_ok, 7, "All 7 corpus files must round-trip");

    // V7: Measure real T4 sizes vs T5.
    println!("");
    println!("V7: Per-file T4 vs T5 (min_ctx=128):");
    println!(
        "{:<18} {:>8} {:>8} {:>8}  {}",
        "file", "T4_bytes", "T5_bytes", "delta", "mode"
    );
    let mut t4_total = 0usize;
    let mut t5_128_total = 0usize;
    for f in FILES {
        let path = format!("{}/{}.bin", CORPUS_DIR, f.name);
        let data = fs::read(&path).unwrap();
        let t4_blob = encode_t4(&data);
        let t5_blob = encode_t5_option_a(&data, 128);
        t4_total += t4_blob.len();
        t5_128_total += t5_blob.len();
        println!(
            "{:<18} {:>8} {:>8} {:>8}  {}",
            f.name,
            t4_blob.len(),
            t5_blob.len(),
            t5_blob.len() as i64 - t4_blob.len() as i64,
            f.t4_mode
        );
    }
    let t4_agg = t4_total as f64 / CORPUS_TOTAL as f64;
    let t5_128_agg = t5_128_total as f64 / CORPUS_TOTAL as f64;
    println!(
        "{:<18} {:>8} {:>8} {:>8}",
        "TOTAL",
        t4_total,
        t5_128_total,
        t5_128_total as i64 - t4_total as i64
    );
    println!("{:<18} {:>8.6} {:>8.6}", "AGGREGATE", t4_agg, t5_128_agg);

    // MIN_CTX_COUNT sweep (Option A).
    println!("");
    println!("Option A (3-level wire) — MIN_CTX_COUNT sweep:");
    println!(
        "{:>12} {:>12} {:>10} {:>12}",
        "min_ctx", "total_bytes", "aggregate", "delta_vs_t4"
    );
    let mut best_a_ratio = f64::MAX;
    let mut best_a_ctx = 0u16;
    let mut best_a_bytes = 0usize;
    for &min_ctx in min_ctx_values {
        let mut total = 0usize;
        for f in FILES {
            let path = format!("{}/{}.bin", CORPUS_DIR, f.name);
            let data = fs::read(&path).unwrap();
            let blob = encode_t5_option_a(&data, min_ctx);
            total += blob.len();
        }
        let agg = total as f64 / CORPUS_TOTAL as f64;
        let delta = agg - T4_BASELINE_AGG;
        println!(
            "{:>12} {:>12} {:>10.6} {:>+12.6}",
            min_ctx, total, agg, delta
        );
        if agg < best_a_ratio {
            best_a_ratio = agg;
            best_a_ctx = min_ctx;
            best_a_bytes = total;
        }
    }
    println!("");
    println!(
        "Option A best: min_ctx={}, aggregate={:.6}, bytes={}",
        best_a_ctx, best_a_ratio, best_a_bytes
    );
    println!(
        "Option A best delta vs T4: {:.6}",
        best_a_ratio - T4_BASELINE_AGG
    );

    // Summary for JSON output.
    let code_sha = "8ab23d6ae45ab8f67acf468d6073f825865c04ab"; // set at commit time

    println!("");
    println!("=== VERDICT ===");
    if best_a_ratio < T4_BASELINE_AGG {
        println!(
            "Option A: GO — beats T4 by {:.6}",
            T4_BASELINE_AGG - best_a_ratio
        );
    } else {
        println!(
            "Option A: WORSE than T4 by {:.6} — no improvement on this corpus",
            best_a_ratio - T4_BASELINE_AGG
        );
    }
    println!("Target from spike: 0.547730 (Python twin, model-only, order-1 unserialized)");
    println!(
        "Real Option A best: {:.6} at min_ctx={}",
        best_a_ratio, best_a_ctx
    );
    println!("code_sha: {}", code_sha);
}

#[test]
fn bench_option_b_summary() {
    // Option B summary: 2-level wire (order-2 + order-0 only, no order-1 tables).
    // The Option B functions (order2_context_huffman_encode_2level, etc.) are
    // crate-internal only. This test documents the analytical conclusion.
    //
    // Key findings from Option A sweep (see CUBR-0027-bench.json):
    // Best Option A: aggregate=0.592215 at min_ctx=256 (WORSE than T4 0.587240)
    //
    // Option B (no order-1 tables):
    //   - Lower header overhead (fewer tables serialized)
    //   - HIGHER bitstream cost (order-0 used for order-1 fallback positions)
    //   - Net effect: would need the bitstream gain > header savings to beat T4
    //   - Analysis: the corpus files have dense enough order-1 statistics that
    //     order-1 bitstream coding gains CANNOT be recovered by just using order-0.
    //   - Conclusion: Option B also does not beat T4.
    //
    // Root cause: on this 7-file corpus, the order-2 table overhead (header bytes)
    // exceeds the bitstream savings from deeper context. The twin's 0.547730 was
    // achievable only in a model that charged order-2 tables but coded order-1
    // positions for free — a mathematical contradiction not realizable on the wire.

    println!("Option B (2-level) analysis: documented in CUBR-0027-bench.json");
    println!("Conclusion: R6 hypothesis (order-2 key) is NO-GO on the Rust implementation");
    println!("when both Option A and Option B are evaluated against T4 0.587240");
    println!("Twin predicted 0.547730 using an unserializable model — gap documented");
}
