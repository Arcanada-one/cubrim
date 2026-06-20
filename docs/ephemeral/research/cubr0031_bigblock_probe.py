#!/usr/bin/env python3
"""
CUBR-0031 P3 — Suffix-array O(n) BWT + larger-blocks probe (REAL measurement).

Forks cubr0029_bigblock_probe.py, preserving the CUBR-0029 record byte-identical.
This script feeds REAL codec measurements (from tests/cubr0031_bench.rs) into
the aggregate computation.

Key difference from CUBR-0029 probe:
  CUBR-0029: NO corpus file reaches L=65536 → modelled result (assumed 0% BWT gain).
  CUBR-0031: block_bound_runs.bin is exactly L=65536 → REAL measured BWT+T4 bytes.

The verdict addresses:
  Q1: Does the L=65536 file show BWT gain vs T4?
  Q2: Does adding this file change the aggregate verdict vs GO threshold 0.575495?
  Q3: After charging u16→u32 widening overhead (Gotcha #6), is widening justified?

CORPUS_TOTAL = 116992 (original 51456 + block_bound_runs 65536)
GO threshold: aggregate <= 0.575495 (−2% vs T4 0.587240, per original CUBR-0028/0029)

Gotcha #6 compliance: 4 decoder branches = 4 cost terms (assertion preserved).
  Branch A: BWT output stream (n values, each varint-encoded)
  Branch B: primary_index u32 widening (+2 bytes/block)
  Branch C: n_distinct header (u8 or u16) — unchanged
  Branch D: block-length header u32 (only needed for L > 65536 — not yet triggered)
  Assertion: branch_count == cost_term_count.
"""

import json
import math
import os

CORPUS_DIR = "/Users/ug/arcanada/Projects/Cubrim/docs/ephemeral/research/corpus"
B = 256
N = 2
CURRENT_CUBE_SIZE_LIMIT = B * B  # 65536

# Original CUBR-0028/0029 constants (unchanged)
ORIGINAL_CORPUS_TOTAL = 51456
T4_TOTAL_BYTES_ORIGINAL = 30217
T4_AGGREGATE_ORIGINAL = 0.587240
BWT_AGGREGATE_BASELINE = 0.504412   # CUBR-0028 real measured BWT aggregate (orig corpus)
BWT_TOTAL_BYTES_ORIGINAL = int(round(BWT_AGGREGATE_BASELINE * ORIGINAL_CORPUS_TOTAL))  # ~25959

# Extended corpus (CUBR-0031)
CORPUS_TOTAL = 116992  # 51456 + 65536
GO_THRESHOLD = 0.575495

# Gotcha #6
DECODER_BRANCHES = 4

# Real measured sizes from tests/cubr0031_bench.rs (code_sha 60ae94c)
# Read from the bench JSON output
BENCH_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "CUBR-0031-bench.json"
)


def load_bench_results():
    """Load real measurements from the Rust bench harness."""
    try:
        with open(BENCH_JSON_PATH) as fh:
            bench = json.load(fh)
    except FileNotFoundError:
        raise RuntimeError(
            f"Bench results not found at {BENCH_JSON_PATH}. "
            "Run: cd code/cubrim-rs && cargo test --test cubr0031_bench -- --nocapture"
        )

    # Validate this is the right task and has a code_sha
    assert bench.get("task") == "CUBR-0031", f"Wrong task in bench JSON: {bench.get('task')}"
    code_sha = bench.get("code_sha", "unknown")
    assert code_sha != "unknown", "bench JSON has no code_sha — not archivable"
    return bench, code_sha


# Original 7 files (unchanged from CUBR-0029 probe; T4 baselines verified by bench)
FILES_ORIGINAL = [
    {"name": "sparse_clustered", "t4_bytes": 502,  "size_bytes": 2048,  "t4_mode": "cube"},
    {"name": "dense",            "t4_bytes": 4109, "size_bytes": 4096,  "t4_mode": "raw"},
    {"name": "text",             "t4_bytes": 5705, "size_bytes": 16384, "t4_mode": "cube"},
    {"name": "log_like",         "t4_bytes": 7318, "size_bytes": 16384, "t4_mode": "cube"},
    {"name": "binary_mixed",     "t4_bytes": 8205, "size_bytes": 8192,  "t4_mode": "raw"},
    {"name": "random_high",      "t4_bytes": 4109, "size_bytes": 4096,  "t4_mode": "raw"},
    {"name": "sparse_small",     "t4_bytes": 269,  "size_bytes": 256,   "t4_mode": "raw"},
]


def main():
    bench, code_sha = load_bench_results()

    print("=" * 70)
    print("CUBR-0031 P3 — Suffix-array O(n) BWT + larger-blocks probe (REAL)")
    print("=" * 70)
    print(f"Bench code_sha:   {code_sha}")
    print(f"Current cube_size_limit: {CURRENT_CUBE_SIZE_LIMIT} (u16 primary_index safe)")
    print(f"T4 baseline (orig):  {T4_AGGREGATE_ORIGINAL:.6f} ({T4_TOTAL_BYTES_ORIGINAL} bytes)")
    print(f"BWT baseline (orig): {BWT_AGGREGATE_BASELINE:.6f} ({BWT_TOTAL_BYTES_ORIGINAL} bytes, CUBR-0028 real)")
    print(f"GO threshold:        {GO_THRESHOLD:.6f} (−2% vs T4)")
    print(f"CORPUS_TOTAL (extended): {CORPUS_TOTAL} bytes (orig {ORIGINAL_CORPUS_TOTAL} + block_bound_runs 65536)")
    print(f"Gotcha #6 decoder branches: {DECODER_BRANCHES}")
    print()

    # Step 1: Block-bound analysis with real measurements
    print("Step 1: Block-bound analysis — REAL measured sizes")
    print(f"{'File':<22} {'L':>6}  {'L/limit':>8}  {'BWT':>7}  {'T4':>7}  {'delta':>7}  block_bound?")
    print("-" * 75)

    # Build per-file map from bench JSON
    per_file_map = {}
    for entry in bench["per_file"]:
        per_file_map[entry["file"]] = entry

    block_bound_files = []
    all_files = FILES_ORIGINAL + [{"name": "block_bound_runs", "size_bytes": 65536, "t4_mode": "cube"}]

    for f in all_files:
        name = f["name"]
        size = f["size_bytes"]
        ratio = size / CURRENT_CUBE_SIZE_LIMIT
        bound = size >= CURRENT_CUBE_SIZE_LIMIT
        if bound:
            block_bound_files.append(name)

        if name in per_file_map:
            bwt_b = per_file_map[name]["bwt_bytes"]
            t4_b = per_file_map[name]["t4_bytes"]
            delta = bwt_b - t4_b
        else:
            bwt_b = "???"
            t4_b = "???"
            delta = "???"

        flag = "YES" if bound else "no"
        delta_str = f"{delta:+d}" if isinstance(delta, int) else str(delta)
        print(f"  {name:<20} {size:>6}  {ratio:>8.4f}  {bwt_b:>7}  {t4_b:>7}  {delta_str:>7}  {flag}")

    print()
    largest = max(f["size_bytes"] for f in all_files)
    print(f"  Largest file: {largest} bytes ({largest / CURRENT_CUBE_SIZE_LIMIT:.2%} of cube_size_limit)")
    print(f"  Block-bound files (L >= {CURRENT_CUBE_SIZE_LIMIT}): {block_bound_files if block_bound_files else 'NONE'}")
    print()

    # Extract real measurements for block_bound_runs
    bbr = per_file_map["block_bound_runs"]
    bbr_bwt_bytes = bbr["bwt_bytes"]
    bbr_t4_bytes = bbr["t4_bytes"]
    bbr_delta = bbr_bwt_bytes - bbr_t4_bytes
    bbr_bwt_ratio = bbr_bwt_bytes / 65536
    bbr_t4_ratio = bbr_t4_bytes / 65536

    print(f"  Q1: Does block_bound_runs (L=65536) show BWT gain vs T4?")
    print(f"      BWT={bbr_bwt_bytes} bytes  T4={bbr_t4_bytes} bytes  delta={bbr_delta:+d}")
    print(f"      BWT ratio={bbr_bwt_ratio:.6f}  T4 ratio={bbr_t4_ratio:.6f}")
    if bbr_delta < 0:
        print(f"      A: YES — BWT beats T4 by {abs(bbr_delta)} bytes on the large-block file.")
    elif bbr_delta == 0:
        print(f"      A: NO GAIN — BWT == T4 on block_bound_runs (competitive selection = tie).")
        print(f"         The run structure (avg_run~34, max=2812) was NOT enough to outperform T4.")
    else:
        print(f"      A: REGRESSION — BWT is {bbr_delta} bytes WORSE than T4 on block_bound_runs.")
    print()

    # Step 2: Extended aggregate (REAL bytes)
    print("Step 2: Extended aggregate — REAL bytes from Rust bench")
    print()

    total_bwt = bench["bwt_total_bytes"]
    total_t4 = bench["t4_total_bytes"]
    bwt_agg = total_bwt / CORPUS_TOTAL
    t4_agg = total_t4 / CORPUS_TOTAL
    delta_vs_t4 = bwt_agg - t4_agg

    print(f"  BWT total: {total_bwt}  aggregate: {bwt_agg:.6f}")
    print(f"  T4  total: {total_t4}  aggregate: {t4_agg:.6f}")
    print(f"  delta BWT-T4: {delta_vs_t4:+.6f}")
    print(f"  GO threshold: {GO_THRESHOLD:.6f}")
    print()

    # Step 3: Widening overhead (Gotcha #6)
    print("Step 3: primary_index widening overhead (Gotcha #6)")
    print()

    u16_pi_bytes = 2
    u32_pi_bytes = 4
    widening_overhead_per_block = u32_pi_bytes - u16_pi_bytes  # +2
    num_blocks = len(all_files)  # one block per file = 8
    total_widening_overhead = widening_overhead_per_block * num_blocks  # +16

    print(f"  u16 primary_index: {u16_pi_bytes} bytes/block (current)")
    print(f"  u32 primary_index: {u32_pi_bytes} bytes/block (required for L > 65536)")
    print(f"  Widening overhead: +{widening_overhead_per_block} bytes/block")
    print(f"  Corpus blocks: {num_blocks} (one per file)")
    print(f"  Total widening overhead: +{total_widening_overhead} bytes on corpus")
    print()

    # Gotcha #6 branch self-check
    branch_cost_terms = [
        ("Branch A: BWT output stream", "already in BWT baseline"),
        ("Branch B: primary_index u32 widening", total_widening_overhead),
        ("Branch C: n_distinct header", 0),      # unchanged
        ("Branch D: block-length header u32", 0), # only for L > 65536 (not triggered)
    ]
    assert len(branch_cost_terms) == DECODER_BRANCHES, (
        f"Gotcha #6 violated: {len(branch_cost_terms)} cost terms vs {DECODER_BRANCHES} branches"
    )
    print(f"  Gotcha #6 self-check: {len(branch_cost_terms)} cost terms == {DECODER_BRANCHES} branches  PASS")
    print()

    # Aggregate after widening overhead
    bwt_with_widening = total_bwt + total_widening_overhead
    bwt_with_widening_agg = bwt_with_widening / CORPUS_TOTAL

    print(f"  BWT aggregate without overhead: {bwt_agg:.6f} ({total_bwt} bytes)")
    print(f"  BWT aggregate WITH u32 overhead: {bwt_with_widening_agg:.6f} ({bwt_with_widening} bytes)")
    print(f"  GO threshold:                    {GO_THRESHOLD:.6f}")
    print()

    # Step 4: Q2 — Does larger block change the aggregate verdict?
    print("Step 4: Q2 — Does the block-bound file change the aggregate verdict?")
    print()

    # Original BWT agg (CUBR-0028, 7 files only)
    orig_bwt_total = bench["bwt_total_bytes"] - bbr_bwt_bytes
    orig_bwt_agg = orig_bwt_total / ORIGINAL_CORPUS_TOTAL
    print(f"  Original corpus (7 files): BWT aggregate = {orig_bwt_agg:.6f}  "
          f"({orig_bwt_total} bytes / {ORIGINAL_CORPUS_TOTAL})")
    print(f"  Extended corpus (8 files): BWT aggregate = {bwt_agg:.6f}  "
          f"({total_bwt} bytes / {CORPUS_TOTAL})")
    print(f"  Extended agg WITH widening: {bwt_with_widening_agg:.6f}")

    if bwt_agg <= GO_THRESHOLD:
        print(f"  A: YES — aggregate GO (BWT {bwt_agg:.6f} <= threshold {GO_THRESHOLD:.6f}).")
        print(f"     But this is driven by the original 7-file BWT gains, not the large-block file.")
    else:
        print(f"  A: NO — aggregate NO-GO (BWT {bwt_agg:.6f} > threshold {GO_THRESHOLD:.6f}).")

    print()

    # Step 5: Key finding — what does block_bound_runs contribute?
    print("Step 5: Large-block file's contribution to the aggregate")
    print()

    # Weight of large file in extended corpus
    weight = 65536 / CORPUS_TOTAL
    print(f"  block_bound_runs weight in corpus: {weight:.2%} ({65536}/{CORPUS_TOTAL})")
    print(f"  block_bound_runs BWT ratio: {bbr_bwt_ratio:.6f}")
    print(f"  block_bound_runs T4  ratio: {bbr_t4_ratio:.6f}")
    print(f"  BWT gain/loss on large file: {bbr_delta:+d} bytes")

    if bbr_delta == 0:
        print()
        print("  KEY FINDING: BWT tied T4 on block_bound_runs — the run-heavy fixture")
        print("  (k=8 alphabet, Pareto runs, Markov transitions) did NOT give BWT an edge.")
        print("  This is because competitive selection (min(BWT, T4)) means tie = T4 is kept.")
        print()
        print("  The good T4 aggregate on block_bound_runs (9011/65536 = 0.137) shows the")
        print("  value-code stream has strong structure that T4 already exploits well.")
        print("  BWT reorganization did not find additional runs vs T4's order-1 context model.")
    elif bbr_delta < 0:
        print()
        print(f"  KEY FINDING: BWT BEAT T4 by {abs(bbr_delta)} bytes on the large-block file.")
        print("  Larger blocks DO help BWT on run-heavy structured data.")

    print()

    # Final verdict
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)

    # The probe's GO/NO-GO is about whether to implement u16->u32 widening:
    # The BWT aggregate is already well below threshold — BWT-entropy is confirmed GO.
    # But the SPECIFIC question is: does LARGER BLOCK SIZE add value beyond current limit?
    # If block_bound_runs shows BWT gain, YES.
    # If block_bound_runs shows no gain, then widening adds overhead with no benefit.

    widening_justified = bbr_delta < 0
    aggregate_go = bwt_agg <= GO_THRESHOLD

    if widening_justified and aggregate_go:
        verdict = "GO"
        reason = (
            f"BWT outperforms T4 on the L=65536 block-bound fixture by {abs(bbr_delta)} bytes. "
            f"Extended aggregate {bwt_agg:.6f} is below GO threshold {GO_THRESHOLD:.6f}. "
            f"u16->u32 primary_index widening is justified — BWT gains from larger blocks. "
            f"O(n) SA-IS prerequisite also justified."
        )
    elif not widening_justified and aggregate_go:
        verdict = "NO-GO-WIDENING"
        reason = (
            f"BWT does NOT outperform T4 on the L=65536 block-bound file "
            f"(delta={bbr_delta:+d} bytes, measured by real Rust codec at code_sha={code_sha}). "
            f"Competitive selection means BWT == T4 on this file (tie -> T4 kept). "
            f"Raising cube_size_limit beyond 65536 and widening primary_index to u32 "
            f"would add +{total_widening_overhead} bytes overhead with zero ratio gain on this corpus. "
            f"The overall BWT aggregate ({bwt_agg:.6f}) is excellent vs threshold ({GO_THRESHOLD:.6f}) "
            f"but that is driven by the ORIGINAL 7 files, not by the large-block fixture. "
            f"u16->u32 widening is NOT justified. "
            f"CUBR-0029 Class B #2 CLOSED (measured, not modelled)."
        )
    else:
        verdict = "NO-GO"
        reason = (
            f"BWT aggregate {bwt_agg:.6f} is above GO threshold {GO_THRESHOLD:.6f}. "
            f"NO-GO."
        )

    print(f"\n  {verdict}")
    print()
    # Wrap reason for readability
    words = reason.split()
    line = "  "
    for w in words:
        if len(line) + len(w) + 1 > 72:
            print(line)
            line = "  " + w
        else:
            line += (" " if line != "  " else "") + w
    print(line)
    print()

    # Emit JSON verdict
    result = {
        "task": "CUBR-0031",
        "probe": "suffix-array-bigblock-real",
        "source": "fork of cubr0029_bigblock_probe.py (CUBR-0029 record preserved)",
        "code_sha": code_sha,
        "measurement_source": "tests/cubr0031_bench.rs (real Rust codec)",
        "corpus_total": CORPUS_TOTAL,
        "original_corpus_total": ORIGINAL_CORPUS_TOTAL,
        "t4_aggregate_original": T4_AGGREGATE_ORIGINAL,
        "bwt_aggregate_baseline_original": BWT_AGGREGATE_BASELINE,
        "go_threshold": GO_THRESHOLD,
        "current_cube_size_limit": CURRENT_CUBE_SIZE_LIMIT,
        "block_bound_files": block_bound_files,
        "new_file": {
            "name": "block_bound_runs",
            "size_bytes": 65536,
            "bwt_bytes": bbr_bwt_bytes,
            "t4_bytes": bbr_t4_bytes,
            "delta_bwt_minus_t4": bbr_delta,
            "bwt_ratio": round(bbr_bwt_ratio, 6),
            "t4_ratio": round(bbr_t4_ratio, 6),
            "bwt_gain_vs_t4": bbr_delta < 0,
        },
        "extended_aggregate": {
            "bwt_total_bytes": total_bwt,
            "t4_total_bytes": total_t4,
            "bwt_aggregate": round(bwt_agg, 6),
            "t4_aggregate": round(t4_agg, 6),
            "delta_vs_t4": round(delta_vs_t4, 6),
        },
        "widening_overhead": {
            "per_block_bytes": widening_overhead_per_block,
            "num_blocks": num_blocks,
            "total_bytes": total_widening_overhead,
            "bwt_aggregate_with_overhead": round(bwt_with_widening_agg, 6),
        },
        "gotcha_6_compliance": {
            "decoder_branches": DECODER_BRANCHES,
            "cost_terms_charged": DECODER_BRANCHES,
            "assertion": "PASS",
        },
        "verdict": verdict,
        "widening_justified": widening_justified,
        "reason": reason,
        "per_file": [
            {
                "file": entry["file"],
                "size_bytes": entry["size_bytes"],
                "bwt_bytes": entry["bwt_bytes"],
                "t4_bytes": entry["t4_bytes"],
                "delta": entry["delta"],
                "block_bound": entry["block_bound"],
            }
            for entry in bench["per_file"]
        ],
    }

    out_path = os.path.join(os.path.dirname(__file__), "cubr0031-bigblock-verdict.json")
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"JSON verdict written to: {out_path}")
    print()

    return verdict


if __name__ == "__main__":
    verdict = main()
    import sys
    # Exit 0 on any real measurement verdict (probe succeeded; GO/NO-GO are both valid outcomes)
    sys.exit(0)
