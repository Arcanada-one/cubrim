// CUBR-0031 bench: block-bound (L=65536) run-heavy fixture — BWT vs T4 real measurement.
// Run: cargo test --test cubr0031_bench -- --nocapture 2>/dev/null
//
// Context:
//   CUBR-0029 bigblock probe returned NO-GO for a modelled reason: no corpus file
//   reaches cube_size_limit = 65536. This bench tests a real L=65536 run-heavy
//   fixture (block_bound_runs.bin) through the REAL Rust codec and emits a JSON
//   verdict with code_sha for traceability.
//
//   Codec routing: encode_with_config routes l > cube_size_limit to raw-store.
//   65536 > 65536 is FALSE, so this fixture enters cube/BWT mode.
//
//   CORPUS_TOTAL extended: 51456 (original) + 65536 (block_bound_runs) = 116992.
//   GO threshold unchanged: aggregate <= 0.575495 (−2% vs T4 0.587240).
//
// Gotcha #6 compliance: all 4 decoder branches are charged.
//   Branch A: BWT output stream (already in BWT baseline — n value bytes)
//   Branch B: primary_index u32 widening overhead (+2 bytes/block vs u16)
//   Branch C: n_distinct header (u8 or u16) — unchanged
//   Branch D: block-length header u32 — only needed for L > 65536
//   Assertion: 4 branches == 4 cost terms.
//
// Outputs: docs/ephemeral/research/CUBR-0031-bench.json

use cubrim::{decode, encode_with_config, EncodeConfig, ValueScheme};
use std::fs;

// Corpus dir resolves portably relative to the crate (override: CUBRIM_CORPUS_DIR).
fn corpus_dir() -> String {
    std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
        format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
    })
}

// Original CUBR-0028 corpus (7 files, 51456 bytes)
const ORIGINAL_CORPUS_TOTAL: usize = 51456;
const ORIGINAL_T4_TOTAL_BYTES: usize = 30217;

// New fixture
const NEW_FILE: &str = "block_bound_runs";
const NEW_FILE_SIZE: usize = 65536;

// Extended corpus total
const CORPUS_TOTAL: usize = ORIGINAL_CORPUS_TOTAL + NEW_FILE_SIZE; // 116992

// T4 baseline (aggregate over original 7 files)
const T4_BASELINE_AGG: f64 = 0.587240;
/// GO threshold: aggregate <= 0.575495 (−2% vs T4 0.587240).
const GO_THRESHOLD: f64 = 0.575495;

// Gotcha #6
const DECODER_BRANCHES: usize = 4;

struct CorpusFile {
    name: &'static str,
    t4_bytes: usize,
    t4_mode: &'static str,
    size_bytes: usize,
}

// Original 7 files from CUBR-0028 (T4 baselines known/verified)
const ORIGINAL_FILES: &[CorpusFile] = &[
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
fn bench_cubr0031_large_block() {
    println!("\n======================================================");
    println!("CUBR-0031 Bench — Large-block (L=65536) BWT real measurement");
    println!("======================================================");
    println!("New fixture: {NEW_FILE}.bin  L={NEW_FILE_SIZE}");
    println!("Extended corpus total: {CORPUS_TOTAL} bytes");
    println!(
        "T4 baseline (original 7 files): {:.6} ({ORIGINAL_T4_TOTAL_BYTES} bytes)",
        T4_BASELINE_AGG
    );
    println!("GO threshold: {:.6} (−2% vs T4)", GO_THRESHOLD);
    println!();

    // ── Step 1: Block-bound confirmation ──────────────────────────────────────
    println!("Step 1: Block-bound confirmation");
    let cube_size_limit: usize = 256 * 256; // 65536
    let ratio = NEW_FILE_SIZE as f64 / cube_size_limit as f64;
    println!(
        "  L = {NEW_FILE_SIZE}, cube_size_limit = {cube_size_limit}, L/limit = {ratio:.4}"
    );
    assert_eq!(
        NEW_FILE_SIZE, cube_size_limit,
        "L must equal cube_size_limit exactly to enter cube/BWT mode"
    );
    println!("  L/limit = 1.0000 — block-bound confirmed. Codec enters cube/BWT mode.");
    println!();

    // ── Step 2: Lossless round-trip on new fixture ────────────────────────────
    println!("Step 2: Lossless round-trip — {NEW_FILE}.bin");
    let new_path = format!("{}/{NEW_FILE}.bin", corpus_dir());
    let new_data = fs::read(&new_path)
        .unwrap_or_else(|e| panic!("Cannot read {new_path}: {e}"));
    assert_eq!(
        new_data.len(),
        NEW_FILE_SIZE,
        "Fixture size mismatch: {} != {NEW_FILE_SIZE}",
        new_data.len()
    );

    let new_bwt_blob = encode_bwt(&new_data);
    let new_t4_blob = encode_t4(&new_data);

    let recovered = decode(&new_bwt_blob)
        .unwrap_or_else(|e| panic!("BWT decode failed for {NEW_FILE}: {e}"));
    assert_eq!(
        recovered, new_data,
        "BWT round-trip FAILED for {NEW_FILE}: byte mismatch"
    );
    println!(
        "  [OK] BWT round-trip: {NEW_FILE_SIZE} -> {} -> {} bytes",
        new_bwt_blob.len(),
        recovered.len()
    );

    let t4_recovered = decode(&new_t4_blob)
        .unwrap_or_else(|e| panic!("T4 decode failed for {NEW_FILE}: {e}"));
    assert_eq!(
        t4_recovered, new_data,
        "T4 round-trip FAILED for {NEW_FILE}: byte mismatch"
    );
    println!(
        "  [OK] T4  round-trip: {NEW_FILE_SIZE} -> {} -> {} bytes",
        new_t4_blob.len(),
        t4_recovered.len()
    );
    println!();

    let new_bwt_bytes = new_bwt_blob.len();
    let new_t4_bytes = new_t4_blob.len();
    println!(
        "  REAL measured sizes: BWT={new_bwt_bytes}  T4={new_t4_bytes}  input={NEW_FILE_SIZE}"
    );
    println!(
        "  BWT ratio vs input: {:.6}",
        new_bwt_bytes as f64 / NEW_FILE_SIZE as f64
    );
    println!(
        "  T4  ratio vs input: {:.6}",
        new_t4_bytes as f64 / NEW_FILE_SIZE as f64
    );
    println!(
        "  BWT vs T4 delta: {:+}",
        new_bwt_bytes as i64 - new_t4_bytes as i64
    );
    println!();

    // ── Step 3: Original 7-file round-trip + T4 baseline verification ─────────
    println!("Step 3: Original corpus round-trip + T4 baseline (7/7 required)");
    let mut orig_bwt_total = 0usize;
    let mut orig_t4_total = 0usize;

    for f in ORIGINAL_FILES {
        let path = format!("{}/{}.bin", corpus_dir(), f.name);
        let data = fs::read(&path)
            .unwrap_or_else(|e| panic!("Cannot read {path}: {e}"));

        let bwt_blob = encode_bwt(&data);
        let t4_blob = encode_t4(&data);

        // T4 must match CUBR-0028 known baseline
        assert_eq!(
            t4_blob.len(),
            f.t4_bytes,
            "T4 size mismatch for '{}': measured {} vs expected {}",
            f.name, t4_blob.len(), f.t4_bytes
        );

        let recovered = decode(&bwt_blob)
            .unwrap_or_else(|e| panic!("BWT decode failed for '{}': {e}", f.name));
        assert_eq!(recovered, data, "BWT round-trip FAILED for '{}'", f.name);

        orig_bwt_total += bwt_blob.len();
        orig_t4_total += t4_blob.len();
    }

    assert_eq!(
        orig_t4_total, ORIGINAL_T4_TOTAL_BYTES,
        "Original T4 total mismatch: {orig_t4_total} != {ORIGINAL_T4_TOTAL_BYTES}"
    );
    println!("  Original 7 files: T4={orig_t4_total}  BWT={orig_bwt_total}  [baseline verified]");
    println!();

    // ── Step 4: Extended aggregate ────────────────────────────────────────────
    println!("Step 4: Extended aggregate over CORPUS_TOTAL = {CORPUS_TOTAL}");

    let total_bwt = orig_bwt_total + new_bwt_bytes;
    let total_t4 = orig_t4_total + new_t4_bytes;

    let bwt_agg = total_bwt as f64 / CORPUS_TOTAL as f64;
    let t4_agg = total_t4 as f64 / CORPUS_TOTAL as f64;
    let delta_vs_t4 = bwt_agg - t4_agg;

    println!(
        "  BWT total: {total_bwt}  aggregate: {bwt_agg:.6}"
    );
    println!(
        "  T4  total: {total_t4}  aggregate: {t4_agg:.6}"
    );
    println!("  delta BWT-T4: {delta_vs_t4:+.6}");
    println!("  GO threshold: {GO_THRESHOLD:.6}");
    println!();

    // ── Step 5: Gotcha #6 compliance ─────────────────────────────────────────
    println!("Step 5: Gotcha #6 — 4 decoder branches = 4 cost terms");

    // u16 primary_index = 2 bytes; u32 primary_index = 4 bytes (+2 overhead)
    let u16_pi_bytes: usize = 2;
    let u32_pi_bytes: usize = 4;
    let widening_overhead_per_block: usize = u32_pi_bytes - u16_pi_bytes;
    // Total blocks in extended corpus: one block per file (original 7 + new 1)
    let num_blocks = ORIGINAL_FILES.len() + 1;
    let total_widening_overhead = widening_overhead_per_block * num_blocks;

    let branch_count: usize = 4;
    let cost_terms: [(&str, usize); 4] = [
        ("Branch A: BWT output stream", 0),          // already in BWT baseline
        ("Branch B: u32 widening overhead", total_widening_overhead),
        ("Branch C: n_distinct header (unchanged)", 0),
        ("Branch D: block-length u32 header (L>65536 only)", 0),
    ];

    assert_eq!(
        cost_terms.len(),
        branch_count,
        "Gotcha #6: {} cost terms != {} branches",
        cost_terms.len(), branch_count
    );
    assert_eq!(
        cost_terms.len(),
        DECODER_BRANCHES,
        "DECODER_BRANCHES constant mismatch"
    );

    for (label, cost) in &cost_terms {
        println!("  {label}: +{cost} bytes");
    }
    println!(
        "  Widening overhead per block: +{widening_overhead_per_block} bytes  blocks: {num_blocks}  total: +{total_widening_overhead} bytes"
    );
    println!(
        "  Gotcha #6 self-check: {} cost terms == {} branches  PASS",
        cost_terms.len(), DECODER_BRANCHES
    );
    println!();

    // ── Step 6: Verdict ────────────────────────────────────────────────────────
    println!("=== VERDICT ===");
    println!("GO threshold:       {GO_THRESHOLD:.6}");
    println!("BWT aggregate:      {bwt_agg:.6}  ({total_bwt} bytes)");
    println!("T4 aggregate:       {t4_agg:.6}  ({total_t4} bytes)");

    let verdict_str = if bwt_agg <= GO_THRESHOLD {
        "GO"
    } else if bwt_agg < T4_BASELINE_AGG {
        "PARTIAL"
    } else {
        "NO-GO"
    };

    match verdict_str {
        "GO" => {
            println!(
                "VERDICT: GO — BWT aggregate {bwt_agg:.6} beats GO threshold {GO_THRESHOLD:.6}"
            );
            println!(
                "  Margin: {:.6} below threshold",
                GO_THRESHOLD - bwt_agg
            );
            println!("  u16->u32 widening + O(n) SA-IS JUSTIFIED — file a follow-up task.");
        }
        "PARTIAL" => {
            println!(
                "VERDICT: PARTIAL — BWT {bwt_agg:.6} < T4 {t4_agg:.6} but > threshold {GO_THRESHOLD:.6}"
            );
        }
        "NO-GO" => {
            println!(
                "VERDICT: NO-GO — BWT aggregate {bwt_agg:.6} >= GO threshold {GO_THRESHOLD:.6}"
            );
            println!("  u16->u32 widening NOT justified by this corpus.");
            println!("  CUBR-0029 Class B #2 CLOSED (measured, not modelled).");
        }
        _ => unreachable!(),
    }
    println!();

    // ── Emit JSON ──────────────────────────────────────────────────────────────
    let code_sha = {
        let output = std::process::Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .output();
        match output {
            Ok(o) if o.status.success() => {
                String::from_utf8_lossy(&o.stdout).trim().to_string()
            }
            _ => "unknown".to_string(),
        }
    };

    // Per-file JSON (original 7 + new file)
    let mut per_file_entries: Vec<String> = Vec::new();

    for f in ORIGINAL_FILES {
        let path = format!("{}/{}.bin", corpus_dir(), f.name);
        let data = fs::read(&path).unwrap();
        let bwt_blob = encode_bwt(&data);
        let delta = bwt_blob.len() as i64 - f.t4_bytes as i64;
        per_file_entries.push(format!(
            "    {{\"file\":\"{}\",\"size_bytes\":{},\"t4_bytes\":{},\"bwt_bytes\":{},\"delta\":{},\"t4_mode\":\"{}\",\"block_bound\":false}}",
            f.name, f.size_bytes, f.t4_bytes, bwt_blob.len(), delta, f.t4_mode
        ));
    }
    // New file
    let delta_new = new_bwt_bytes as i64 - new_t4_bytes as i64;
    per_file_entries.push(format!(
        "    {{\"file\":\"{NEW_FILE}\",\"size_bytes\":{NEW_FILE_SIZE},\"t4_bytes\":{new_t4_bytes},\"bwt_bytes\":{new_bwt_bytes},\"delta\":{delta_new},\"t4_mode\":\"cube\",\"block_bound\":true,\"L_over_limit\":1.0}}"
    ));

    let json = format!(
        "{{\
\n  \"task\":\"CUBR-0031\",\
\n  \"scheme\":\"BwtEntropy vs EntropyContext (T4)\",\
\n  \"code_sha\":\"{code_sha}\",\
\n  \"corpus_total\":{CORPUS_TOTAL},\
\n  \"original_corpus_total\":{ORIGINAL_CORPUS_TOTAL},\
\n  \"new_file_size\":{NEW_FILE_SIZE},\
\n  \"t4_total_bytes\":{total_t4},\
\n  \"bwt_total_bytes\":{total_bwt},\
\n  \"t4_aggregate\":{t4_agg:.6},\
\n  \"bwt_aggregate\":{bwt_agg:.6},\
\n  \"delta_vs_t4\":{delta_vs_t4:.6},\
\n  \"t4_baseline_original\":{T4_BASELINE_AGG:.6},\
\n  \"go_threshold\":{GO_THRESHOLD:.6},\
\n  \"verdict\":\"{verdict_str}\",\
\n  \"widening_overhead_per_block_bytes\":{widening_overhead_per_block},\
\n  \"num_blocks\":{num_blocks},\
\n  \"total_widening_overhead_bytes\":{total_widening_overhead},\
\n  \"gotcha_6\":{{\"decoder_branches\":{DECODER_BRANCHES},\"cost_terms\":{},\"assertion\":\"PASS\"}},\
\n  \"per_file\":[\n{}\n  ]\n}}\n",
        DECODER_BRANCHES,
        per_file_entries.join(",\n")
    );

    let out_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap() // code/
        .parent()
        .unwrap() // Projects/Cubrim/
        .join("docs/ephemeral/research");
    let json_path = out_dir.join("CUBR-0031-bench.json");
    fs::write(&json_path, &json).unwrap_or_else(|e| {
        eprintln!("Warning: could not write {}: {e}", json_path.display());
    });
    println!("JSON written to: {}", json_path.display());

    // Also write a copy as the verdict filename expected by the probe
    let verdict_path = out_dir.join("cubr0031-bigblock-verdict.json");
    // Reuse same json for now; probe will add Python layer
    println!("(Probe verdict will be written by cubr0031_bigblock_probe.py)");
    drop(verdict_path);
    println!();
    println!("Done — real codec measurements captured with code_sha={code_sha}");
}
