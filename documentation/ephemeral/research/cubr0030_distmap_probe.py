#!/usr/bin/env python3
"""
CUBR-0030 — Extended distance-map probe (sparse-corpus extension).

Extends CUBR-0029 P2 probe with:
  (a) Per-axis rho reporting (rho_axis0 = axis0_distinct/B, rho_axis1 = axis1_distinct/B)
  (b) Extended corpus (original 7 files + 2 new both-axis-sparse files)
  (c) Honest aggregate computation and GO/NO-GO gate on the extended corpus

Corpus: /Users/ug/arcanada/Projects/Cubrim/documentation/ephemeral/research/corpus/
N=2, B=256, cube_volume=256^2=65536

T4 baseline (7 original files): aggregate=0.587240, T4_TOTAL_BYTES=30217, CORPUS_TOTAL=51456
Extended corpus (9 files): CORPUS_TOTAL += 16 + 24 = 51496
Extended T4 total: T4_TOTAL_BYTES += t4_bytes(both_sparse_16) + t4_bytes(both_sparse_24)
  T4 assumption for L<=25 near-incompressible files: raw mode, t4_bytes=L (conservative).
  (No Rust run — spike-gate prohibits src change unless GO; raw is always the winner for L<=25.)

GO threshold: hypothetical_aggregate <= 0.575495 (−2% vs T4 0.587240, original corpus)
Honest verdict: NO-GO expected (small files raise aggregate; even zero distmap cost misses gate).

Gotcha #6 compliance: 4 decoder branches = 4 cost terms (unchanged from CUBR-0029).
"""

import json
import math
import os
import sys

# Reuse cost-modelling functions from the CUBR-0029 probe directly (same file, same dir)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from cubr0029_distmap_probe import (
    compute_rho,
    model_distmap_wire_cost,
    varint_size,
    B,
    N,
    CUBE_VOLUME,
    DECODER_BRANCHES,
    GO_THRESHOLD,
    T4_AGGREGATE,
)

CORPUS_DIR = os.path.join(_HERE, "corpus")

# ─── Original 7 files (from CUBR-0029 probe) ─────────────────────────────────
ORIGINAL_FILES = [
    {"name": "sparse_clustered", "t4_bytes": 502,  "t4_mode": "cube",  "size_bytes": 2048},
    {"name": "dense",            "t4_bytes": 4109, "t4_mode": "raw",   "size_bytes": 4096},
    {"name": "text",             "t4_bytes": 5705, "t4_mode": "cube",  "size_bytes": 16384},
    {"name": "log_like",        "t4_bytes": 7318, "t4_mode": "cube",  "size_bytes": 16384},
    {"name": "binary_mixed",    "t4_bytes": 8205, "t4_mode": "raw",   "size_bytes": 8192},
    {"name": "random_high",     "t4_bytes": 4109, "t4_mode": "raw",   "size_bytes": 4096},
    {"name": "sparse_small",    "t4_bytes": 269,  "t4_mode": "raw",   "size_bytes": 256},
]

# ─── New both-axis-sparse files (CUBR-0030) ───────────────────────────────────
# T4 bytes = L for near-incompressible tiny files (conservative raw mode assumption).
# No Rust run performed — spike-gate: no src change unless GO.
NEW_FILES = [
    {
        "name": "both_sparse_16",
        "t4_bytes": 16,   # raw mode, L=16
        "t4_mode": "raw",
        "size_bytes": 16,
        "t4_assumption": (
            "Conservative bound: raw mode t4_bytes=L=16. "
            "Near-incompressible (random 16 bytes); T4 raw mode always wins. "
            "No Rust run (spike-gate prohibits Rust src change unless GO)."
        ),
    },
    {
        "name": "both_sparse_24",
        "t4_bytes": 24,   # raw mode, L=24
        "t4_mode": "raw",
        "size_bytes": 24,
        "t4_assumption": (
            "Conservative bound: raw mode t4_bytes=L=24. "
            "Near-incompressible (random 24 bytes); T4 raw mode always wins. "
            "No Rust run (spike-gate prohibits Rust src change unless GO)."
        ),
    },
]

ALL_FILES = ORIGINAL_FILES + NEW_FILES

# ─── Corpus totals ────────────────────────────────────────────────────────────
ORIG_CORPUS_TOTAL = 51456   # sum of original 7 file sizes
ORIG_T4_TOTAL = 30217       # sum of original 7 T4 bytes
EXT_CORPUS_TOTAL = ORIG_CORPUS_TOTAL + sum(f["size_bytes"] for f in NEW_FILES)  # 51496
EXT_T4_TOTAL = ORIG_T4_TOTAL + sum(f["t4_bytes"] for f in NEW_FILES)            # 30257


def process_file(f: dict) -> dict:
    """Read file from disk, compute rho + per-axis rho + distmap wire cost."""
    path = os.path.join(CORPUS_DIR, f["name"] + ".bin")
    with open(path, "rb") as fh:
        data = fh.read()

    assert len(data) == f["size_bytes"], (
        f"Size mismatch for {f['name']}: got {len(data)}, expected {f['size_bytes']}"
    )

    info = compute_rho(data)  # returns L, rho, axis0_distinct, axis0_coords, axis1_distinct, axis1_coords
    cost = model_distmap_wire_cost(info)

    # Per-axis rho (S2 extension — this is what V-1 requires)
    rho_axis0 = info["axis0_distinct"] / B
    rho_axis1 = info["axis1_distinct"] / B

    return {
        "name": f["name"],
        "size_bytes": f["size_bytes"],
        "L": info["L"],
        "rho": round(info["rho"], 6),
        "rho_axis0": round(rho_axis0, 6),
        "rho_axis1": round(rho_axis1, 6),
        "axis0_distinct": info["axis0_distinct"],
        "axis1_distinct": info["axis1_distinct"],
        "distmap_wire_bytes": cost["total_distmap_bytes"],
        "branch_cost_terms": [(n, c) for n, c in cost["branch_cost_terms"]],
        "t4_bytes": f["t4_bytes"],
        "t4_mode": f["t4_mode"],
        "t4_assumption": f.get("t4_assumption"),
        "is_new": f in NEW_FILES,
        "both_axis_sparse": rho_axis0 < 0.1 and rho_axis1 < 0.1,
    }


def main():
    print("=" * 72)
    print("CUBR-0030 — Extended distance-map probe (sparse-corpus extension)")
    print("=" * 72)
    print(f"N={N}, B={B}, cube_volume={CUBE_VOLUME}")
    print(f"T4 baseline (original 7): {T4_AGGREGATE:.6f} ({ORIG_T4_TOTAL} bytes / {ORIG_CORPUS_TOTAL} corpus)")
    print(f"GO threshold:              {GO_THRESHOLD:.6f} (−2% vs T4 aggregate)")
    print(f"Extended corpus:           {len(ALL_FILES)} files, {EXT_CORPUS_TOTAL} bytes total")
    print(f"Extended T4 total:         {EXT_T4_TOTAL} bytes (new files: raw-mode assumption)")
    print(f"Gotcha #6 decoder branches: {DECODER_BRANCHES}")
    print()

    # ─── Step 1: Per-file table ────────────────────────────────────────────────
    print("Step 1: Per-file ρ table (extended corpus — 9 files)")
    hdr = (f"{'File':<22} {'L':>6} {'ρ':>9} {'ρ_ax0':>8} {'ρ_ax1':>8} "
           f"{'ax0d':>5} {'ax1d':>5} {'both_sp':>7}  T4_mode  NEW")
    print(hdr)
    print("-" * len(hdr))

    results = []
    for f in ALL_FILES:
        r = process_file(f)
        results.append(r)
        new_tag = " *" if r["is_new"] else ""
        both_tag = "YES" if r["both_axis_sparse"] else "no"
        print(f"  {r['name']:<20} {r['L']:>6} {r['rho']:>9.6f} {r['rho_axis0']:>8.4f} {r['rho_axis1']:>8.4f} "
              f"{r['axis0_distinct']:>5} {r['axis1_distinct']:>5} {both_tag:>7}  {r['t4_mode']:<7}{new_tag}")

    print()

    # ─── Step 2: Distmap wire cost (extended corpus) ───────────────────────────
    total_distmap_bytes = sum(r["distmap_wire_bytes"] for r in results)
    orig_distmap_bytes  = sum(r["distmap_wire_bytes"] for r in results if not r["is_new"])
    new_distmap_bytes   = sum(r["distmap_wire_bytes"] for r in results if r["is_new"])

    print("Step 2: Distance-map wire cost")
    print(f"  Original 7 files: {orig_distmap_bytes} bytes distmap cost")
    print(f"  New 2 files:      {new_distmap_bytes} bytes distmap cost")
    print(f"  Extended total:   {total_distmap_bytes} bytes distmap cost")
    print(f"  As fraction of extended T4 total ({EXT_T4_TOTAL}): {total_distmap_bytes / EXT_T4_TOTAL:.4%}")
    print(f"  As fraction of extended corpus total ({EXT_CORPUS_TOTAL}): {total_distmap_bytes / EXT_CORPUS_TOTAL:.4%}")
    print()

    # ─── Step 3: GO/NO-GO decision on extended corpus ─────────────────────────
    print("Step 3: GO/NO-GO decision — extended corpus")
    print()

    # Extended T4 aggregate
    ext_t4_aggregate = EXT_T4_TOTAL / EXT_CORPUS_TOTAL
    print(f"  Extended T4 aggregate (9 files): {ext_t4_aggregate:.6f}")
    print(f"  Original T4 aggregate (7 files): {T4_AGGREGATE:.6f}")
    print(f"  Delta (new files added):         {ext_t4_aggregate - T4_AGGREGATE:+.6f}")
    print()

    # Best-case: distmap cost = zero for new sparse files (they're already tiny)
    # Even if we save ALL distmap bytes from original 7 (26-byte prior from CUBR-0028),
    # compute the hypothetical aggregate
    distmap_prior_savings = 26  # bytes, from CUBR-0028 axis-1 measurement on original 7
    hypothetical_total = EXT_T4_TOTAL - distmap_prior_savings
    hypothetical_agg = hypothetical_total / EXT_CORPUS_TOTAL

    print(f"  Prior distance-map savings (CUBR-0028, original 7 files): {distmap_prior_savings} bytes")
    print(f"  Best-case hypothetical:")
    print(f"    extended T4 total - distmap savings = {EXT_T4_TOTAL} - {distmap_prior_savings} = {hypothetical_total}")
    print(f"    hypothetical_aggregate = {hypothetical_agg:.6f}")
    print(f"    GO threshold:           {GO_THRESHOLD:.6f}")
    print(f"    Gap to GO threshold:    {hypothetical_agg - GO_THRESHOLD:+.6f}")
    print()

    # Per-axis sparse verification
    both_sparse_files = [r for r in results if r["both_axis_sparse"]]
    print(f"  Both-axis-sparse files (rho_axis0 < 0.1 AND rho_axis1 < 0.1): {len(both_sparse_files)}")
    for r in both_sparse_files:
        print(f"    {r['name']}: rho_axis0={r['rho_axis0']:.4f}, rho_axis1={r['rho_axis1']:.4f} [NEW]")
    print()

    # Gotcha #6 self-check on extended corpus
    for r in results:
        assert len(r["branch_cost_terms"]) == DECODER_BRANCHES, (
            f"Gotcha #6 FAIL for {r['name']}: "
            f"{len(r['branch_cost_terms'])} terms vs {DECODER_BRANCHES} branches"
        )
    print(f"  Gotcha #6 self-check: PASS (all {len(results)} files, {DECODER_BRANCHES} branches = {DECODER_BRANCHES} cost terms)")
    print()

    # Verdict
    if hypothetical_agg > GO_THRESHOLD:
        verdict = "NO-GO"
        reason = (
            f"Even with zero distance-map cost on all prior savings ({distmap_prior_savings} bytes / CUBR-0028), "
            f"hypothetical_aggregate {hypothetical_agg:.6f} > GO threshold {GO_THRESHOLD:.6f} "
            f"(gap = {hypothetical_agg - GO_THRESHOLD:+.6f}). "
            f"New both-axis-sparse files (L=16, L=24) have rho_axis0 < 0.1 AND rho_axis1 < 0.1 "
            f"as required, but they RAISE the extended T4 aggregate from {T4_AGGREGATE:.6f} to "
            f"{ext_t4_aggregate:.6f} because near-incompressible tiny files (L<=25) cannot be "
            f"compressed below raw-mode. Structural blocker: position-based phi forces both-axis-sparse "
            f"to L<=25; content-derived phi would be required for a GO-capable re-test (CUBR-0032)."
        )
    else:
        verdict = "GO"
        reason = (
            f"hypothetical_aggregate {hypothetical_agg:.6f} <= GO threshold {GO_THRESHOLD:.6f}. "
            f"Proceed to Rust implementation."
        )

    print(f"  VERDICT: {verdict}")
    print(f"  Reason: {reason}")
    print()

    # ─── Step 4: Emit JSON verdict ─────────────────────────────────────────────
    import hashlib
    code_sha = "60ae94c"  # HEAD of main at task start (feat branch diverges here)

    verdict_data = {
        "task": "CUBR-0030",
        "probe": "extended-distmap-sparse-corpus",
        "code_sha": code_sha,
        "corpus_files": len(ALL_FILES),
        "original_corpus_total": ORIG_CORPUS_TOTAL,
        "original_t4_total": ORIG_T4_TOTAL,
        "original_t4_aggregate": T4_AGGREGATE,
        "extended_corpus_total": EXT_CORPUS_TOTAL,
        "extended_t4_total": EXT_T4_TOTAL,
        "extended_t4_aggregate": round(ext_t4_aggregate, 6),
        "go_threshold": GO_THRESHOLD,
        "distmap_prior_savings_bytes": distmap_prior_savings,
        "hypothetical_aggregate_if_distmap_free": round(hypothetical_agg, 6),
        "gap_to_go_threshold": round(hypothetical_agg - GO_THRESHOLD, 6),
        "verdict": verdict,
        "reason": reason,
        "gotcha_6_compliance": {
            "decoder_branches": DECODER_BRANCHES,
            "cost_terms_charged": DECODER_BRANCHES,
            "assertion": "PASS",
            "verified_on_all_files": True,
        },
        "both_axis_sparse_files": [
            {
                "name": r["name"],
                "L": r["L"],
                "rho_axis0": r["rho_axis0"],
                "rho_axis1": r["rho_axis1"],
                "both_axis_sparse": True,
            }
            for r in results if r["both_axis_sparse"]
        ],
        "t4_assumption_for_new_files": (
            "Conservative bound: raw mode t4_bytes=L for both_sparse_16 (L=16) and "
            "both_sparse_24 (L=24). No Rust compilation — spike-gate prohibits src change unless GO. "
            "Raw mode is always the winner for near-incompressible random L<=25 byte files."
        ),
        "structural_blocker": (
            "Under position-based phi (phi(i)=(i%B, i//B), B=256): "
            "axis0_distinct=min(L,256), axis1_distinct=ceil(L/256). "
            "Both-axis rho<0.1 requires L<=25 bytes. Files this small are near-incompressible "
            "and raise the aggregate compression ratio vs T4. "
            "A GO-capable re-test requires content-derived phi coordinates (CUBR-0032, L3)."
        ),
        "follow_up": "CUBR-0032: Content-derived-phi distance-map feasibility (L3, consilium-gated)",
        "per_file": [
            {
                "file": r["name"],
                "size_bytes": r["size_bytes"],
                "rho": r["rho"],
                "rho_axis0": r["rho_axis0"],
                "rho_axis1": r["rho_axis1"],
                "axis0_distinct": r["axis0_distinct"],
                "axis1_distinct": r["axis1_distinct"],
                "both_axis_sparse": r["both_axis_sparse"],
                "distmap_wire_bytes": r["distmap_wire_bytes"],
                "t4_bytes": r["t4_bytes"],
                "t4_mode": r["t4_mode"],
                "is_new": r["is_new"],
            }
            for r in results
        ],
    }

    out_path = os.path.join(_HERE, "cubr0030-distmap-verdict.json")
    with open(out_path, "w") as fh:
        json.dump(verdict_data, fh, indent=2)
    print(f"JSON verdict written to: {out_path}")
    print("=" * 72)

    return verdict


if __name__ == "__main__":
    verdict = main()
    sys.exit(0 if verdict == "NO-GO" else 1)
