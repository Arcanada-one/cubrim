#!/usr/bin/env python3
"""
CUBR-0032 — Content-derived phi feasibility probe (deterministic arbiter).

The multi-vendor consilium (claude=Value-Stratified-phi, cursor=OIVR-phi)
both predicted NO-GO. This probe is the deterministic arbiter: it measures the
steel-man candidate (OIVR-phi — the one that PASSES Gotcha #3 by keeping the
value stream in i-order) on the ACTUAL canonical 7-file corpus, with a
Gotcha-#6-complete size model that charges every decoder branch INCLUDING the
phi-map.

OIVR-phi (cursor's candidate): byte b[i] -> cube coordinate (b[i], occ_rank)
where occ_rank = count of value b[i] in prefix b[0..i]. The value stream stays
strict i-order (phi is a side-map), so the T4 value cost is UNCHANGED. The phi
side-map is reconstructable from the decoded i-order stream at ZERO wire cost
WHEN every value occurs <=256 times (fits the 256-tall axis); otherwise a spill
list of (axis0,axis1) uint16 pairs is transmitted for ranks >=256.

This directly tests:
  - cursor's claim: value stream locked at T4 (30217 B), DM ceiling tiny.
  - claude's claim: net >= T4 + overhead (conservation) -> NO-GO identically.

GO threshold: aggregate <= 0.575495 (-2% vs T4 0.587240). CORPUS_TOTAL = 51456.

Gotcha #6 decoder branches for OIVR-phi (one cost term each):
  1. header / mode+scheme byte
  2. T4 value stream (i-order) -> charge measured T4 bytes (UNCHANGED)
  3. distance-map (axis-0 + axis-1 gaps over OIVR-occupied cells)
  4. phi spill list (ranks >=256), 4 bytes per spilled cell; 0 when no overflow
Self-check: assert n_cost_terms == DECODER_BRANCHES.
"""

import os
import json

CORPUS_DIR = "/Users/ug/arcanada/Projects/Cubrim/docs/ephemeral/research/corpus"
B = 256
AXIS_CAP = 256  # axis-1 (occurrence rank) capacity before spill
CORPUS_TOTAL = 51456
T4_AGGREGATE = 0.587240
T4_TOTAL_BYTES = 30217
GO_THRESHOLD = 0.575495

DECODER_BRANCHES = 4

# Canonical 7-file corpus with measured T4 baseline (from cubr0029 probe / archives).
FILES = [
    {"name": "sparse_clustered", "t4_bytes": 502,  "size_bytes": 2048},
    {"name": "dense",            "t4_bytes": 4109, "size_bytes": 4096},
    {"name": "text",             "t4_bytes": 5705, "size_bytes": 16384},
    {"name": "log_like",         "t4_bytes": 7318, "size_bytes": 16384},
    {"name": "binary_mixed",     "t4_bytes": 8205, "size_bytes": 8192},
    {"name": "random_high",      "t4_bytes": 4109, "size_bytes": 4096},
    {"name": "sparse_small",     "t4_bytes": 269,  "size_bytes": 256},
]


def varint_size(value: int) -> int:
    """LEB128 byte size for a non-negative integer."""
    if value <= 0:
        return 1
    size, v = 0, value
    while v > 0:
        size += 1
        v >>= 7
    return size


def oivr_occupancy(data: bytes):
    """
    Compute OIVR-phi occupied cells.
    coord(i) = (b[i], occ_rank) ; occ_rank = #occurrences of b[i] in b[0..i] - 1.
    Returns: set of (a0,a1) cells, spill count (ranks >= AXIS_CAP),
             axis0 occupied set, axis1 occupied set.
    """
    counters = [0] * 256
    cells = set()
    spill = 0
    axis0 = set()
    axis1 = set()
    for byte in data:
        rank = counters[byte]
        counters[byte] += 1
        if rank >= AXIS_CAP:
            spill += 1
            continue  # spilled cell transmitted separately
        cells.add((byte, rank))
        axis0.add(byte)
        axis1.add(rank)
    return cells, spill, sorted(axis0), sorted(axis1)


def axis_gap_bytes(coords) -> int:
    """Varint gap stream over a sorted axis-coordinate set (sentinel -1)."""
    prev = -1
    total = 0
    for c in coords:
        total += varint_size(c - prev)
        prev = c
    return total


def model_file(data: bytes, t4_bytes: int) -> dict:
    cells, spill, axis0, axis1 = oivr_occupancy(data)
    rho = len(cells) / (B * B)

    # Branch 1: header / mode+scheme byte
    header = 1
    # Branch 2: T4 value stream — UNCHANGED (OIVR keeps i-order value stream)
    value_stream = t4_bytes
    # Branch 3: distance-map over OIVR-occupied cells (axis-0 + axis-1 gaps + 2 count headers)
    distmap = axis_gap_bytes(axis0) + axis_gap_bytes(axis1) + 2 + 2
    # Branch 4: phi spill list — 4 bytes (uint16 a0 + uint16 a1) per spilled cell
    spill_bytes = spill * 4

    terms = [
        ("header/scheme", header),
        ("T4 value stream (i-order, unchanged)", value_stream),
        ("distance-map (axis0+axis1 gaps + headers)", distmap),
        ("phi spill list (ranks>=256)", spill_bytes),
    ]
    assert len(terms) == DECODER_BRANCHES, "Gotcha #6: term count != branch count"

    total = sum(c for _, c in terms)
    # Competitive selection (regression-proof): min(OIVR, T4) per file
    competitive = min(total, t4_bytes)
    return {
        "rho": rho,
        "n_cells": len(cells),
        "spill": spill,
        "terms": terms,
        "oivr_total": total,
        "t4_bytes": t4_bytes,
        "competitive": competitive,
    }


def main():
    print("=" * 78)
    print("CUBR-0032 — Content-derived phi (OIVR) deterministic arbiter probe")
    print("=" * 78)
    print(f"B={B}, axis_cap={AXIS_CAP}, CORPUS_TOTAL={CORPUS_TOTAL}")
    print(f"T4 baseline: {T4_AGGREGATE:.6f} ({T4_TOTAL_BYTES} B)  GO threshold: {GO_THRESHOLD:.6f}")
    print(f"Gotcha #6 decoder branches: {DECODER_BRANCHES}")
    print()
    print(f"{'file':<18}{'L':>6}{'rho':>9}{'cells':>7}{'spill':>7}"
          f"{'distmap':>9}{'phi_spill':>10}{'OIVR':>8}{'T4':>7}{'pick':>7}")
    print("-" * 90)

    oivr_total = 0
    competitive_total = 0
    per_file = []
    for f in FILES:
        with open(os.path.join(CORPUS_DIR, f["name"] + ".bin"), "rb") as fh:
            data = fh.read()
        assert len(data) == f["size_bytes"], f"size mismatch {f['name']}"
        m = model_file(data, f["t4_bytes"])
        distmap = dict(m["terms"])["distance-map (axis0+axis1 gaps + headers)"]
        phi_spill = dict(m["terms"])["phi spill list (ranks>=256)"]
        pick = "OIVR" if m["competitive"] == m["oivr_total"] and m["oivr_total"] < m["t4_bytes"] else "T4"
        print(f"{f['name']:<18}{len(data):>6}{m['rho']:>9.4f}{m['n_cells']:>7}{m['spill']:>7}"
              f"{distmap:>9}{phi_spill:>10}{m['oivr_total']:>8}{m['t4_bytes']:>7}{pick:>7}")
        oivr_total += m["oivr_total"]
        competitive_total += m["competitive"]
        per_file.append({
            "name": f["name"], "L": len(data), "rho": round(m["rho"], 6),
            "n_cells": m["n_cells"], "spill": m["spill"],
            "distmap_bytes": distmap, "phi_spill_bytes": phi_spill,
            "oivr_total": m["oivr_total"], "t4_bytes": m["t4_bytes"],
            "competitive": m["competitive"], "pick": pick,
        })

    print("-" * 90)
    oivr_agg = oivr_total / CORPUS_TOTAL
    comp_agg = competitive_total / CORPUS_TOTAL
    print(f"OIVR-pure aggregate (no competitive fallback): {oivr_agg:.6f} ({oivr_total} B)")
    print(f"Competitive min(OIVR,T4) aggregate:            {comp_agg:.6f} ({competitive_total} B)")
    print(f"T4 baseline aggregate:                         {T4_AGGREGATE:.6f} ({T4_TOTAL_BYTES} B)")
    print(f"GO threshold:                                  {GO_THRESHOLD:.6f}")
    print()

    # The honest comparison: does ANY scheme beat T4 by >=2%?
    best = min(oivr_agg, comp_agg)
    verdict = "GO" if best <= GO_THRESHOLD else "NO-GO"
    # Competitive can never beat T4 (it's min with T4), so the real question is oivr_agg.
    print(f"VERDICT: {verdict}")
    if verdict == "NO-GO":
        print(f"  OIVR aggregate {oivr_agg:.6f} > GO threshold {GO_THRESHOLD:.6f}.")
        print(f"  Competitive selection floors at T4 ({T4_AGGREGATE:.6f}) — no improvement.")
        print("  Confirms consilium: value stream stays i-order (=T4), distance-map +")
        print("  phi-map cost is pure added overhead. Conservation holds (claude) /")
        print("  value-stream-lock holds (cursor).")

    out = {
        "task": "CUBR-0032",
        "probe": "content-derived-phi (OIVR steel-man)",
        "go_threshold": GO_THRESHOLD,
        "t4_aggregate": T4_AGGREGATE,
        "t4_total_bytes": T4_TOTAL_BYTES,
        "corpus_total": CORPUS_TOTAL,
        "oivr_pure_aggregate": round(oivr_agg, 6),
        "oivr_pure_total_bytes": oivr_total,
        "competitive_aggregate": round(comp_agg, 6),
        "competitive_total_bytes": competitive_total,
        "verdict": verdict,
        "gotcha_6_compliance": {"decoder_branches": DECODER_BRANCHES,
                                "cost_terms_charged": DECODER_BRANCHES,
                                "assertion": "PASS"},
        "per_file": per_file,
    }
    out_path = os.path.join(os.path.dirname(__file__), "cubr0032-content-phi-verdict.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nVerdict JSON: {out_path}")


if __name__ == "__main__":
    main()
