#!/usr/bin/env python3
"""
CUBR-0018 Phase 1 — Axis-traversal order-1 conditional entropy probe.

Reads all corpus files, builds value-code sequences in three traversal orders
(i-order, axis-0-sorted, axis-1-sorted), and computes H(X_t | X_{t-1}) from
empirical bigram tables.

Fidelity invariant: the i-order value-code sequence produced here is byte-exact
to the seq_codes Vec<usize> built in codec.rs encode_with_config (lines 247-262).

Phi mapping (matches phi.rs):
  phi(i, b=256) -> coords = [i % b, i // b]  (N=2)
  phi_inv(coords, b=256) -> i = coords[0] + coords[1] * b

seq_codes[i] = v2c[data[i]], where v2c maps each distinct byte value to a code
in [0, n_distinct) in ascending value order — matches build_value_dict in codec.rs.

Usage:
  python3 entropy_traversal_probe.py \\
      --corpus /path/to/corpus/manifest.json \\
      --out /path/to/output.md
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def phi(i: int, b: int = 256) -> tuple[int, int]:
    """Mixed-radix 2D phi: position -> (coord0, coord1). Matches phi.rs phi()."""
    return i % b, i // b


def build_value_codes(data: bytes) -> np.ndarray:
    """
    Build seq_codes[i] for i in [0, L-1].
    Distinct byte values sorted ascending -> code 0..n_distinct-1.
    Matches build_value_dict + seq_codes construction in codec.rs lines 229/247-262.
    """
    distinct = sorted(set(data))
    v2c = {v: c for c, v in enumerate(distinct)}
    return np.array([v2c[b] for b in data], dtype=np.int32)


def cond_entropy_h1(seq: np.ndarray, n_distinct: int) -> float:
    """
    Compute H(X_t | X_{t-1}) from empirical bigram counts.

    H(X|Y) = - sum_{y} P(y) * sum_{x} P(x|y) * log2(P(x|y))
            = - sum_{x,y} P(x,y) * log2(P(x|y))

    Sentinel context 0 used for position 0 (matches T4 prev_ctx initialisation).
    Bigrams are (seq[t-1], seq[t]) for t=1..L-1 plus (sentinel=0, seq[0]) at t=0.

    Returns entropy in bits. Returns 0.0 for sequences of length < 2.
    """
    if len(seq) < 2:
        return 0.0

    # Build bigram matrix: counts[prev][curr] — shape (n_distinct+1, n_distinct)
    # Row 0 = sentinel context (position 0 predecessor)
    # Rows 1..n_distinct = context code+1 (shift by 1 to keep sentinel at row 0)
    n_ctx = n_distinct + 1
    counts = np.zeros((n_ctx, n_distinct), dtype=np.int64)

    # First symbol: context = sentinel (row 0 = context code -1 shifted; use row 0 directly)
    counts[0, seq[0]] += 1

    # Remaining symbols: context = previous code + 1 (shift to avoid collision with sentinel row)
    prev = seq[:-1].astype(np.int64) + 1  # shape (L-1,)
    curr = seq[1:]                          # shape (L-1,)
    np.add.at(counts, (prev, curr), 1)

    # Compute conditional entropy
    row_totals = counts.sum(axis=1, keepdims=True)  # (n_ctx, 1)
    # Avoid divide-by-zero for empty contexts
    valid = row_totals[:, 0] > 0
    p_row = np.zeros_like(counts, dtype=np.float64)
    p_row[valid] = counts[valid] / row_totals[valid]  # P(x|y)

    # H = - sum_{x,y} P(y) * P(x|y) * log2(P(x|y))
    # = - sum_{y} P(y) * sum_{x} P(x|y) * log2(P(x|y))
    total = counts.sum()
    p_y = row_totals[:, 0] / total  # P(y) marginal

    with np.errstate(divide='ignore', invalid='ignore'):
        log_p = np.where(p_row > 0, np.log2(p_row), 0.0)
    per_row_h = -np.sum(p_row * log_p, axis=1)  # H(X|Y=y) per context
    h = float(np.sum(p_y * per_row_h))
    return h


def traversal_axis_sorted(data: bytes, axis: int, b: int = 256) -> np.ndarray:
    """
    Build value-code sequence sorted by coord[axis].
    axis=0 -> sort by (i % b); axis=1 -> sort by (i // b).
    Stable sort preserves i-order within equal coordinate groups.
    """
    codes = build_value_codes(data)
    l = len(data)
    indices = np.arange(l)
    if axis == 0:
        key = indices % b
    else:
        key = indices // b
    order = np.argsort(key, kind='stable')
    return codes[order]


def process_file(entry: dict) -> dict:
    """Process one corpus file; return per-traversal entropy row."""
    path = Path(entry['path'])
    data = path.read_bytes()
    l = len(data)
    n_distinct = len(set(data))

    seq_iorder = build_value_codes(data)
    seq_ax0 = traversal_axis_sorted(data, axis=0)
    seq_ax1 = traversal_axis_sorted(data, axis=1)

    h_iorder = cond_entropy_h1(seq_iorder, n_distinct)
    h_ax0 = cond_entropy_h1(seq_ax0, n_distinct)
    h_ax1 = cond_entropy_h1(seq_ax1, n_distinct)

    # Relative reduction vs i-order (negative = regression)
    rel_ax0 = (h_iorder - h_ax0) / h_iorder if h_iorder > 0 else 0.0
    rel_ax1 = (h_iorder - h_ax1) / h_iorder if h_iorder > 0 else 0.0

    return {
        'name': entry['name'],
        'l': l,
        'n_distinct': n_distinct,
        'h_iorder': h_iorder,
        'h_ax0': h_ax0,
        'h_ax1': h_ax1,
        'rel_ax0': rel_ax0,
        'rel_ax1': rel_ax1,
        'rho': entry.get('rho', '?'),
    }


def verdict(rows: list[dict], threshold: float = 0.05) -> tuple[str, str]:
    """
    GO iff any axis-sort reduces H(X_t|X_{t-1}) by >= threshold relative
    on at least one file. Returns (GO|NO-GO, rationale string).
    """
    best_ax0 = max(r['rel_ax0'] for r in rows)
    best_ax1 = max(r['rel_ax1'] for r in rows)
    best_overall = max(best_ax0, best_ax1)

    if best_overall >= threshold:
        best_file_ax0 = max(rows, key=lambda r: r['rel_ax0'])
        best_file_ax1 = max(rows, key=lambda r: r['rel_ax1'])
        if best_ax0 >= best_ax1:
            best_file = best_file_ax0
            best_trav = 'axis-0-sorted'
            best_rel = best_ax0
            best_h = best_file['h_ax0']
            baseline_h = best_file['h_iorder']
        else:
            best_file = best_file_ax1
            best_trav = 'axis-1-sorted'
            best_rel = best_ax1
            best_h = best_file['h_ax1']
            baseline_h = best_file['h_iorder']
        rationale = (
            f"{best_trav} reduces H by {best_rel*100:.1f}% relative on '{best_file['name']}' "
            f"(H: {baseline_h:.4f} -> {best_h:.4f} bits). "
            f"Threshold {threshold*100:.0f}% met. Proceed to Rust implementation."
        )
        return 'GO', rationale
    else:
        rationale = (
            f"Best relative reduction: ax0={best_ax0*100:.1f}%, ax1={best_ax1*100:.1f}%. "
            f"Neither meets {threshold*100:.0f}% threshold on any file. "
            f"Axis-sort does not meaningfully reduce conditional entropy on this corpus."
        )
        return 'NO-GO', rationale


def render_markdown(rows: list[dict], go_verdict: str, rationale: str,
                    manifest_path: str) -> str:
    """Render the result table + verdict as markdown."""
    import subprocess
    py_ver = sys.version.split()[0]
    numpy_ver = np.__version__
    try:
        corpus_sha = subprocess.check_output(
            ['shasum', '-a', '256', manifest_path], text=True
        ).split()[0]
    except Exception:
        corpus_sha = 'unavailable'

    header = (
        "# CUBR-0018 Phase 1 — Axis-Traversal Conditional Entropy Probe\n\n"
        f"**Generated:** 2026-06-18\n"
        f"**Python:** {py_ver}  **NumPy:** {numpy_ver}\n"
        f"**Corpus manifest:** `{manifest_path}`\n"
        f"**Manifest SHA-256:** `{corpus_sha}`\n\n"
        "## Methodology\n\n"
        "For each corpus file, three value-code sequences are built:\n"
        "- **i-order**: `seq_codes[i] = v2c[data[i]]` (i = 0..L-1) — matches Rust T4 `seq_codes`\n"
        "- **axis-0-sorted**: positions sorted by `phi(i)[0] = i % 256` (stable sort)\n"
        "- **axis-1-sorted**: positions sorted by `phi(i)[1] = i // 256` (stable sort)\n\n"
        "Phi mapping matches `phi.rs` exactly: `phi(i) = (i % 256, i // 256)` for N=2, B=256.\n\n"
        "Conditional entropy H(Xt|Xt-1) is computed from empirical bigram counts.\n"
        "Sentinel context 0 is used for position 0 (matches T4 `prev_ctx = 0` initialisation).\n\n"
        "**Fidelity:** The i-order sequence produced here is byte-exact to the `seq_codes`\n"
        "vector built in `codec.rs` `encode_with_config` (lines 247-262).\n\n"
        "## Results Table\n\n"
        "| File | L | n_distinct | rho | H(i-order) | H(ax0-sorted) | H(ax1-sorted) | delta-ax0 rel | delta-ax1 rel |\n"
        "|------|---|-----------|-----|-----------|--------------|--------------|--------------|--------------|"
        "\n"
    )

    rows_md = []
    for r in rows:
        rows_md.append(
            f"| {r['name']} | {r['l']} | {r['n_distinct']} | {r['rho']} "
            f"| {r['h_iorder']:.4f} | {r['h_ax0']:.4f} | {r['h_ax1']:.4f} "
            f"| {r['rel_ax0']*100:+.1f}% | {r['rel_ax1']*100:+.1f}% |"
        )

    verdict_section = (
        "\n## Decision Checkpoint (AC-2)\n\n"
        f"**Verdict: {go_verdict}**\n\n"
        f"{rationale}\n\n"
        "**Proxy caveat:** conditional entropy is a proxy for the real T4 coded size. A reduction\n"
        "is necessary but not sufficient — the Rust bench in Phase 2 is the ground truth. The gate\n"
        "exists to avoid writing Rust against an unmeasured win.\n"
    )

    return header + '\n'.join(rows_md) + '\n' + verdict_section


def main():
    parser = argparse.ArgumentParser(description='CUBR-0018 entropy traversal probe')
    parser.add_argument('--corpus', required=True, help='Path to corpus manifest.json')
    parser.add_argument('--out', required=True, help='Output markdown path')
    args = parser.parse_args()

    manifest_path = args.corpus
    with open(manifest_path) as f:
        entries = json.load(f)

    rows = []
    for entry in entries:
        print(f"Processing {entry['name']} ({entry['size_bytes']} bytes)...", file=sys.stderr)
        row = process_file(entry)
        rows.append(row)
        print(
            f"  H: i-order={row['h_iorder']:.4f}  ax0={row['h_ax0']:.4f} ({row['rel_ax0']*100:+.1f}%)  "
            f"ax1={row['h_ax1']:.4f} ({row['rel_ax1']*100:+.1f}%)",
            file=sys.stderr
        )

    go_verdict, rationale = verdict(rows)

    md = render_markdown(rows, go_verdict, rationale, manifest_path=manifest_path)
    Path(args.out).write_text(md)
    print(f"\nOutput written to {args.out}", file=sys.stderr)

    # Print table to stdout for easy inspection
    print(f"\n{'File':<20} {'H(i-order)':>12} {'H(ax0)':>10} {'H(ax1)':>10} {'Δax0':>8} {'Δax1':>8}")
    print('-' * 72)
    for r in rows:
        print(
            f"{r['name']:<20} {r['h_iorder']:>12.4f} {r['h_ax0']:>10.4f} {r['h_ax1']:>10.4f} "
            f"{r['rel_ax0']*100:>+7.1f}% {r['rel_ax1']*100:>+7.1f}%"
        )
    print(f"\nVERDICT: {go_verdict}")
    print(f"Rationale: {rationale}")


if __name__ == '__main__':
    main()
