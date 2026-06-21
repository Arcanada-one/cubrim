#!/usr/bin/env python3
"""
probe-entropy.py — Order-1 conditional-entropy (H(X_t | X_{t-1})) probe.

Gotcha #3 gate: any proposed value-stream transformation must NOT raise
H(X_t | X_{t-1}) on clustered corpus files compared to the i-order baseline.
A raise in conditional entropy means the transformation destroys runs, not
preserves them — auto-NO-GO.

This probe is DETERMINISTIC and LOCAL: no model calls, no network.
~50 LoC core logic; extended with corpus iteration and JSON output.

Reuses the cond_entropy_h1 function pattern from entropy_traversal_probe.py
(existing bench code), adapted for per-corpus-file comparison.

Usage (from shell wrapper probe-entropy.sh):
    python3 probe-entropy.py --corpus <manifest.json> --value-stream <bytes>
    python3 probe-entropy.py --corpus <manifest.json> --candidate <script.py>
    python3 probe-entropy.py --corpus <manifest.json> [--selftest]

Exit 0 = PASS (no conditional entropy increase on clustered files)
Exit 1 = NO-GO (entropy raised on ≥1 clustered file)
Exit 2 = error
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("probe-entropy: numpy required (pip install numpy)", file=sys.stderr)
    sys.exit(2)


# ── Core entropy function (matches entropy_traversal_probe.py convention) ─────

def build_value_codes(data: bytes) -> "np.ndarray":
    """Map bytes to codes 0..n_distinct-1 in ascending value order."""
    distinct = sorted(set(data))
    v2c = {v: c for c, v in enumerate(distinct)}
    return np.array([v2c[b] for b in data], dtype=np.int32)


def cond_entropy_h1(seq: "np.ndarray", n_distinct: int) -> float:
    """
    Compute H(X_t | X_{t-1}) from empirical bigram counts.

    H(X|Y) = - sum_{x,y} P(x,y) * log2(P(x|y))

    Sentinel context (row 0) used for position 0 — matches T4 prev_ctx init.
    Returns entropy in bits; returns 0.0 for len(seq) < 2.
    """
    if len(seq) < 2:
        return 0.0

    n_ctx = n_distinct + 1  # row 0 = sentinel context
    counts = np.zeros((n_ctx, n_distinct), dtype=np.int64)

    # Position 0: sentinel context (index 0) → seq[0]
    counts[0, seq[0]] += 1
    # Positions 1..L-1: context = seq[t-1]+1 (shifted to avoid sentinel)
    for t in range(1, len(seq)):
        ctx = int(seq[t - 1]) + 1
        counts[ctx, seq[t]] += 1

    # H(X|Y) = - sum_{y} P(y) * sum_{x} P(x|y) * log2(P(x|y))
    row_totals = counts.sum(axis=1, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        probs = np.where(row_totals > 0, counts / row_totals, 0.0)
        log_probs = np.where(probs > 0, np.log2(probs), 0.0)
        cond_h = -np.sum(probs * log_probs, axis=1)  # H(X | Y=y) per y
        # Weight by P(y)
        total = counts.sum()
        if total == 0:
            return 0.0
        py = row_totals.flatten() / total
        return float(np.sum(py * cond_h))


# ── I-order baseline ──────────────────────────────────────────────────────────

def iorder_entropy(path: str) -> tuple[float, int]:
    """
    Compute H(X_t | X_{t-1}) on i-order value-code sequence for a corpus file.
    Returns (h1, n_distinct).
    """
    data = Path(path).read_bytes()
    if not data:
        return 0.0, 0
    seq = build_value_codes(data)
    n_distinct = len(set(data))
    return cond_entropy_h1(seq, n_distinct), n_distinct


# ── Probe logic ───────────────────────────────────────────────────────────────

def probe_corpus(
    manifest_path: str,
    candidate_transform=None,
    value_stream_path: str | None = None,
    threshold: float = 0.001,  # entropy increase tolerance (floating-point noise)
) -> dict:
    """
    Run the entropy probe across all corpus files.

    candidate_transform: optional callable(data: bytes) -> bytes
        Returns the transformed value stream. If None and value_stream_path
        is given, that file is used as the transformed stream for the first
        corpus file only (single-file mode).

    threshold: entropy increase ≤ this is treated as negligible (noise floor).

    Returns a dict with verdict + per-file results.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    results = []
    any_fail = False

    for entry in manifest:
        name = entry["name"]
        path = entry.get("path", "")
        if not os.path.exists(path):
            repo_root = Path(manifest_path).parent.parent.parent.parent
            path = str(repo_root / "docs" / "ephemeral" / "research" / "corpus" / Path(path).name)
        if not os.path.exists(path):
            results.append({"file": name, "status": "SKIP", "reason": "file not found"})
            continue

        # I-order baseline
        h1_baseline, n_distinct = iorder_entropy(path)

        # Candidate transform
        if value_stream_path and len(manifest) == 1:
            # Single-file mode: use the pre-generated stream
            transformed = Path(value_stream_path).read_bytes()
            if not transformed:
                seq_cand = np.array([], dtype=np.int32)
            else:
                seq_cand = build_value_codes(transformed)
                n_distinct_cand = len(set(transformed))
                h1_candidate = cond_entropy_h1(seq_cand, n_distinct_cand)
        elif candidate_transform is not None:
            data = Path(path).read_bytes()
            transformed = candidate_transform(data)
            if not transformed:
                h1_candidate = 0.0
            else:
                seq_cand = build_value_codes(transformed)
                h1_candidate = cond_entropy_h1(seq_cand, len(set(transformed)))
        else:
            # No candidate provided — report baseline only (selftest mode)
            h1_candidate = h1_baseline

        delta = h1_candidate - h1_baseline
        # A candidate that raises entropy on clustered files (rho < 0.3) = NO-GO
        is_clustered = entry.get("rho", 1.0) < 0.3
        failed = is_clustered and delta > threshold

        results.append({
            "file": name,
            "rho": entry.get("rho", "?"),
            "h1_baseline": round(h1_baseline, 6),
            "h1_candidate": round(h1_candidate, 6),
            "delta": round(delta, 6),
            "clustered": is_clustered,
            "status": "NO-GO" if failed else "PASS",
        })
        if failed:
            any_fail = True

    return {
        "verdict": "NO-GO" if any_fail else "PASS",
        "threshold": threshold,
        "files": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Order-1 conditional-entropy probe (Gotcha #3)")
    parser.add_argument("--corpus", required=True, help="Path to corpus manifest.json")
    parser.add_argument("--value-stream", help="Pre-generated transformed value stream (bytes)")
    parser.add_argument("--candidate", help="Candidate transform script (Python)")
    parser.add_argument("--threshold", type=float, default=0.001,
                        help="Entropy delta threshold for noise floor (default: 0.001 bits)")
    parser.add_argument("--selftest", action="store_true",
                        help="Run in selftest mode: baseline vs baseline should PASS")
    args = parser.parse_args()

    if args.selftest:
        # Self-test: baseline compared to itself should always PASS
        result = probe_corpus(args.corpus, threshold=args.threshold)
        print(json.dumps(result, indent=2))
        # Selftest: all files should be PASS (baseline == baseline, delta=0)
        failures = [f for f in result["files"] if f.get("status") == "NO-GO"]
        if failures:
            print("SELFTEST FAILED: baseline vs baseline produced NO-GO", file=sys.stderr)
            sys.exit(1)
        print("probe-entropy: SELFTEST PASS — baseline vs baseline OK")
        sys.exit(0)

    result = probe_corpus(
        args.corpus,
        value_stream_path=args.value_stream,
        threshold=args.threshold,
    )
    print(json.dumps(result, indent=2))

    if result["verdict"] == "NO-GO":
        no_go_files = [f["file"] for f in result["files"] if f.get("status") == "NO-GO"]
        print(f"\nNO-GO: conditional entropy raised on clustered files: {', '.join(no_go_files)}",
              file=sys.stderr)
        sys.exit(1)

    print("\nPASS: conditional entropy probe OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
