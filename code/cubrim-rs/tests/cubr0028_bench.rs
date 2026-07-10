// CUBR-0028 bench: BWT (ValueScheme::BwtEntropy, scheme byte 6) vs T4 aggregate.
// Run: cargo test --test cubr0028_bench -- --nocapture 2>/dev/null
//
// Outputs CUBR-0028-bench.json to documentation/ephemeral/research/.

use cubrim::{decode, encode_with_config, EncodeConfig, ValueScheme};
use std::fs;

// Corpus dir resolves portably relative to the crate (override: CUBRIM_CORPUS_DIR).
fn corpus_dir() -> String {
    std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
        format!(
            "{}/../../documentation/ephemeral/research/corpus",
            env!("CARGO_MANIFEST_DIR")
        )
    })
}
const CORPUS_TOTAL: usize = 51456;
const T4_TOTAL_BYTES: usize = 30217;
const T4_BASELINE_AGG: f64 = 0.587240;
/// GO threshold: aggregate ≤ 0.575495 (−2% vs T4).
const GO_THRESHOLD: f64 = 0.575495;

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

fn encode_bwt(data: &[u8]) -> Vec<u8> {
    let cfg = EncodeConfig {
        value_scheme: ValueScheme::BwtEntropy,
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
fn bench_cubr0028_bwt_aggregate() {
    println!("\n======================================================");
    println!("CUBR-0028 Aggregate Bench — BWT (ValueScheme::BwtEntropy)");
    println!("======================================================");
    println!("Corpus total:  {} bytes", CORPUS_TOTAL);
    println!(
        "T4 baseline:   {:.6} ({} bytes)",
        T4_BASELINE_AGG, T4_TOTAL_BYTES
    );
    println!("GO threshold:  {:.6} (−2% vs T4)", GO_THRESHOLD);
    println!();

    // ── Step 1: Lossless round-trip on all 7 corpus files ──────────────────
    println!("Step 1: BWT round-trip (7/7 required)");
    let mut round_trip_ok = 0usize;
    for f in FILES {
        let path = format!("{}/{}.bin", corpus_dir(), f.name);
        let data = match fs::read(&path) {
            Ok(d) => d,
            Err(e) => panic!("Cannot read corpus file {path}: {e}"),
        };
        let blob = encode_bwt(&data);
        let recovered =
            decode(&blob).unwrap_or_else(|e| panic!("BWT decode failed for '{}': {e}", f.name));
        assert_eq!(
            recovered, data,
            "BWT round-trip FAILED for '{}': byte mismatch",
            f.name
        );
        round_trip_ok += 1;
        println!(
            "  [OK] {:<18} {} -> {} bytes",
            f.name,
            data.len(),
            blob.len()
        );
    }
    println!("Round-trip: {round_trip_ok}/7 PASS");
    assert_eq!(
        round_trip_ok, 7,
        "All 7 corpus files must round-trip losslessly"
    );
    println!();

    // ── Step 2: Per-file size comparison vs T4 ─────────────────────────────
    println!("Step 2: Per-file BWT vs T4");
    println!(
        "{:<18} {:>8} {:>8} {:>8}  {}",
        "file", "T4_bytes", "BWT_bytes", "delta", "mode"
    );

    let mut t4_total = 0usize;
    let mut bwt_total = 0usize;

    for f in FILES {
        let path = format!("{}/{}.bin", corpus_dir(), f.name);
        let data = fs::read(&path).unwrap_or_else(|e| panic!("read {path}: {e}"));

        let t4_blob = encode_t4(&data);
        let bwt_blob = encode_bwt(&data);

        // Sanity check: T4 matches known baseline.
        assert_eq!(
            t4_blob.len(),
            f.t4_bytes,
            "T4 size mismatch for '{}': measured {} vs expected {}",
            f.name,
            t4_blob.len(),
            f.t4_bytes
        );

        let delta = bwt_blob.len() as i64 - t4_blob.len() as i64;
        println!(
            "{:<18} {:>8} {:>8} {:>+8}  {}",
            f.name,
            t4_blob.len(),
            bwt_blob.len(),
            delta,
            f.t4_mode
        );

        t4_total += t4_blob.len();
        bwt_total += bwt_blob.len();
    }

    let t4_agg = t4_total as f64 / CORPUS_TOTAL as f64;
    let bwt_agg = bwt_total as f64 / CORPUS_TOTAL as f64;
    let delta_vs_t4 = bwt_agg - t4_agg;

    println!(
        "{:<18} {:>8} {:>8} {:>+8}",
        "TOTAL",
        t4_total,
        bwt_total,
        bwt_total as i64 - t4_total as i64
    );
    println!(
        "{:<18} {:>8.6} {:>8.6} {:>+8.6}",
        "AGGREGATE", t4_agg, bwt_agg, delta_vs_t4
    );
    println!();

    // ── Step 3: Verdict ────────────────────────────────────────────────────
    println!("=== VERDICT ===");
    println!("Python probe predicted: 0.464088 (−20.971%, modelled)");
    println!(
        "Real Rust aggregate:    {:.6} ({} bytes)",
        bwt_agg, bwt_total
    );
    println!("GO threshold:           {:.6} (−2% vs T4)", GO_THRESHOLD);

    if bwt_agg <= GO_THRESHOLD {
        println!(
            "VERDICT: GO — BWT beats GO threshold by {:.6}",
            GO_THRESHOLD - bwt_agg
        );
    } else if bwt_agg < T4_BASELINE_AGG {
        println!("VERDICT: PARTIAL — beats T4 but NOT the −2% GO threshold");
        println!(
            "  BWT aggregate {:.6} < T4 {:.6} but > threshold {:.6}",
            bwt_agg, T4_BASELINE_AGG, GO_THRESHOLD
        );
    } else {
        println!("VERDICT: NO-GO — BWT does not beat T4 baseline");
        println!(
            "  BWT aggregate {:.6} vs T4 {:.6}",
            bwt_agg, T4_BASELINE_AGG
        );
    }

    // Emit JSON summary to documentation/ephemeral/research/
    let code_sha = {
        let output = std::process::Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .output();
        match output {
            Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).trim().to_string(),
            _ => "unknown".to_string(),
        }
    };

    let per_file_json: Vec<String> = FILES.iter().map(|f| {
        let path = format!("{}/{}.bin", corpus_dir(), f.name);
        let data = fs::read(&path).unwrap();
        let bwt_blob = encode_bwt(&data);
        let delta = bwt_blob.len() as i64 - f.t4_bytes as i64;
        format!(
            "    {{\"file\":\"{}\",\"size_bytes\":{},\"t4_bytes\":{},\"bwt_bytes\":{},\"delta\":{},\"mode\":\"{}\"}}",
            f.name, f.size_bytes, f.t4_bytes, bwt_blob.len(), delta, f.t4_mode
        )
    }).collect();

    let verdict_str = if bwt_agg <= GO_THRESHOLD {
        "GO"
    } else if bwt_agg < T4_BASELINE_AGG {
        "PARTIAL"
    } else {
        "NO-GO"
    };

    let json = format!(
        "{{\n  \"task\":\"CUBR-0028\",\n  \"scheme\":\"BwtEntropy\",\n  \"code_sha\":\"{}\",\n  \"corpus_total\":{},\n  \"t4_total_bytes\":{},\n  \"bwt_total_bytes\":{},\n  \"t4_aggregate\":{:.6},\n  \"bwt_aggregate\":{:.6},\n  \"delta_vs_t4\":{:.6},\n  \"go_threshold\":{:.6},\n  \"verdict\":\"{}\",\n  \"per_file\":[\n{}\n  ]\n}}\n",
        code_sha,
        CORPUS_TOTAL,
        t4_total,
        bwt_total,
        t4_agg,
        bwt_agg,
        delta_vs_t4,
        GO_THRESHOLD,
        verdict_str,
        per_file_json.join(",\n")
    );

    let out_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap() // code/
        .parent()
        .unwrap() // Projects/Cubrim/
        .join("documentation/ephemeral/research");
    let json_path = out_dir.join("CUBR-0028-bench.json");
    fs::write(&json_path, &json).unwrap_or_else(|e| {
        eprintln!("Warning: could not write {}: {e}", json_path.display());
    });
    println!();
    println!("JSON written to: {}", json_path.display());
}
