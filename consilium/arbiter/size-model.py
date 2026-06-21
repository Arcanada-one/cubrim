#!/usr/bin/env python3
"""
size-model.py — Full-branch wire-cost model gate (Gotcha #6 and #7).

Validates that a candidate compression scheme's size model is sound:
  1. len(cost_terms) >= len(decoder_branches)  (Gotcha #6)
  2. If phi_map_transmitted=True, the phi-map must appear in cost_terms  (Gotcha #7)
  3. The candidate name/mechanism does not match a CLOSED branch in the ledger

This is a DETERMINISTIC LOCAL gate — no model calls, no network.

Schema for --model <model.json>:
{
  "candidate_name": "PPM-order2-value-stream",
  "mechanism": "...",
  "decoder_branches": [
    {"name": "order-2 table", "cost_bytes_estimate": 1024},
    {"name": "order-1 fallback table", "cost_bytes_estimate": 256},
    {"name": "order-0 fallback table", "cost_bytes_estimate": 64}
  ],
  "cost_terms": [
    {"name": "order-2 table header", "cost_bytes_estimate": 1024},
    {"name": "order-0 fallback bytes", "cost_bytes_estimate": 64}
    // Missing: "order-1 fallback table" — UNSOUND, will be rejected
  ],
  "phi_map_transmitted": false,
  "closed_branch_check": false,
  "predicted_improvement": -0.03
}

Exit 0 = PASS
Exit 1 = NO-GO (unsound)
Exit 2 = error
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ── Closed-branch keyword patterns (fast auto-reject before Python analysis) ──
# These match the mechanism descriptions in closed-branches.md

CLOSED_BRANCH_PATTERNS = [
    # Distance-map / coordinate-storing phi variants
    r"distance.?map",
    r"content.?derived.*phi",
    r"phi.?map.*permut",
    r"coordinate.?stor",
    r"sorted.?value.?placement",
    r"content.?derived.?address",
    r"oivr",  # the specific content-derived-phi steel-man candidate (Gotcha #7)
    # N-sweep targeting T4 value stream
    r"n.?sweep.*t4",
    r"vary.*n.*t4",
    r"tune.*dimension.*t4",
    # Order-2+ fallback chains (without fix)
    r"order.?2.*fallback.*chain",
    r"order.?k.*fallback",
    # RLE pre-pass before entropy coding
    r"rle.?pre.?pass",
    r"pre.?pass.*rle.*entrop",
]

def matches_closed_branch(text: str) -> list[str]:
    """Return list of matched pattern descriptions, or empty list if none."""
    text_lower = text.lower()
    matched = []
    for pattern in CLOSED_BRANCH_PATTERNS:
        if re.search(pattern, text_lower):
            matched.append(pattern)
    return matched


def validate_model(model: dict) -> list[str]:
    """
    Validate the size model. Returns a list of issues (empty = PASS).
    """
    issues = []

    candidate_name = model.get("candidate_name", "")
    mechanism = model.get("mechanism", "")
    decoder_branches = model.get("decoder_branches", [])
    cost_terms = model.get("cost_terms", [])
    phi_map_transmitted = model.get("phi_map_transmitted", False)
    closed_branch_check = model.get("closed_branch_check", False)

    # ── 1. Closed-branch auto-reject ──────────────────────────────────────────
    if closed_branch_check:
        issues.append(
            "closed_branch_check=True: proposal explicitly marked as a closed branch"
        )
    else:
        combined_text = f"{candidate_name} {mechanism}"
        matches = matches_closed_branch(combined_text)
        if matches:
            issues.append(
                f"Proposal matches closed-branch pattern(s): {matches}. "
                "See consilium/closed-branches.md for the evidence. "
                "Rejected before full size-model analysis."
            )

    # ── 2. Gotcha #6: len(cost_terms) >= len(decoder_branches) ───────────────
    n_branches = len(decoder_branches)
    n_terms = len(cost_terms)

    if n_terms < n_branches:
        branch_names = [b.get("name", "?") for b in decoder_branches]
        term_names = [t.get("name", "?") for t in cost_terms]
        missing = n_branches - n_terms
        issues.append(
            f"Gotcha #6 violation: {n_terms} cost term(s) but {n_branches} decoder branch(es). "
            f"Missing {missing} term(s). "
            f"Branches: {branch_names}. "
            f"Terms: {term_names}. "
            "A GO from a model with fewer terms than branches is UNSOUND "
            "(measured: an order-2 spike GO became a real codec WORSE than T4 once "
            "the order-1 fallback table cost was charged — see Gotcha #6)."
        )

    # ── 3. Gotcha #7: phi-map must be a cost term if transmitted ─────────────
    if phi_map_transmitted:
        phi_in_terms = any(
            "phi" in t.get("name", "").lower() or
            "permut" in t.get("name", "").lower() or
            "map" in t.get("name", "").lower()
            for t in cost_terms
        )
        if not phi_in_terms:
            issues.append(
                "Gotcha #7 violation: phi_map_transmitted=True but no phi-map cost term found. "
                "The phi-map permutation MUST be charged as a decoder branch. "
                "Information conservation: map cost >= disorder removed from value stream. "
                "A proposal with an uncharged phi-map is UNSOUND."
            )
        # Additionally: phi_map_transmitted=True is itself an auto-NO-GO
        # unless the permutation is implicit (BWT-style LF-mapping)
        bwt_exception = any(
            "bwt" in t.get("name", "").lower() or
            "lf.?map" in t.get("name", "").lower() or
            "implicit" in t.get("name", "").lower()
            for t in cost_terms
        )
        if not bwt_exception:
            issues.append(
                "Gotcha #7: phi_map_transmitted=True without an implicit-permutation exception "
                "(BWT LF-mapping or equivalent). A transmitted coordinate map pays for itself "
                "in information: map_cost >= disorder_removed. Unless the permutation is "
                "encoded implicitly (like BWT primary_index), this is NO-GO."
            )

    return issues


def main():
    parser = argparse.ArgumentParser(
        description="Full-branch size model gate (Gotcha #6 + #7)"
    )
    parser.add_argument("--model", required=True, help="Path to size-model JSON")
    parser.add_argument("--ledger", help="Path to closed-branches.md (for context logging)")
    args = parser.parse_args()

    try:
        model = json.loads(Path(args.model).read_text())
    except Exception as e:
        print(f"size-model: ERROR reading model JSON: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"size-model: validating '{model.get('candidate_name', '?')}'")
    print(f"  decoder_branches: {len(model.get('decoder_branches', []))}")
    print(f"  cost_terms:       {len(model.get('cost_terms', []))}")
    print(f"  phi_map_transmitted: {model.get('phi_map_transmitted', False)}")

    issues = validate_model(model)

    if issues:
        print("\nNO-GO — size model has the following issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  [{i}] {issue}")
        sys.exit(1)

    print("\nPASS — size model is sound:")
    print(f"  branches={len(model.get('decoder_branches', []))}, "
          f"terms={len(model.get('cost_terms', []))}, "
          f"phi_map_transmitted={model.get('phi_map_transmitted', False)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
