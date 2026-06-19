#!/usr/bin/env python3
"""
CUBR-0020 AC-2 — BWT pre-pass conditional entropy probe.

For each of the 7 corpus files, builds the i-order value-code sequence
(byte-exact to the T4 seq_codes stream) and measures:

  H1_iorder   : H(X_t | X_{t-1}) on i-order seq_codes          (T4 incumbent)
  H1_bwt      : H(X_t | X_{t-1}) on bwt_forward(seq_iorder)[0] (BWT output)
  H0_bwt_mtf  : H(X) on mtf_encode(bwt_forward(seq_iorder)[0]) (BWT + MTF)
  H0_iorder   : H(X) on i-order seq_codes                       (reference)

GO/NO-GO criterion:
  GO iff max over 7 files of max(rel_bwt_h1, rel_bwt_mtf) >= 0.05  (5% relative)

BWT variant: primary-index (no sentinel). Single whole-stream block.
Round-trip correctness is asserted before any entropy measurement.

Usage:
  python3 bench/entropy_bwt_probe.py \\
      --corpus /path/to/corpus/manifest.json \\
      --out /path/to/output.md
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Core codec mirror — byte-exact to T4 seq_codes (codec.rs lines 229/247-262)
# ---------------------------------------------------------------------------

def build_value_codes(data: bytes) -> np.ndarray:
    """
    Build seq_codes[i] = v2c[data[i]] for i in [0, L-1].
    Distinct byte values sorted ascending -> code 0..n_distinct-1.
    Matches build_value_dict + seq_codes construction in codec.rs lines 229/247-262.
    Byte-exact to CUBR-0018/0019 build_value_codes.
    """
    distinct = sorted(set(data))
    v2c = {v: c for c, v in enumerate(distinct)}
    return np.array([v2c[b] for b in data], dtype=np.int32)


# ---------------------------------------------------------------------------
# Entropy functions
# ---------------------------------------------------------------------------

def cond_entropy_h1(seq: np.ndarray) -> float:
    """
    Compute H(X_t | X_{t-1}) from empirical bigram counts.

    Sentinel context 0 used for position 0 (matches T4 prev_ctx initialisation).
    Bigrams: (sentinel, seq[0]) at t=0; (seq[t-1], seq[t]) for t=1..L-1.

    The bigram matrix shape is (n_distinct+1, n_distinct) — the +1 row is the
    sentinel context for position 0.  Context codes are shifted by +1 to avoid
    colliding with the sentinel row.

    Returns entropy in bits. Returns 0.0 for sequences of length < 2.
    """
    if len(seq) < 2:
        return 0.0

    n_distinct = int(seq.max()) + 1
    n_ctx = n_distinct + 1
    counts = np.zeros((n_ctx, n_distinct), dtype=np.int64)

    # Position 0: sentinel context (row 0)
    counts[0, seq[0]] += 1

    # Positions 1..L-1: context = previous code + 1 (shifted to avoid sentinel row)
    prev = seq[:-1].astype(np.int64) + 1
    curr = seq[1:]
    np.add.at(counts, (prev, curr), 1)

    row_totals = counts.sum(axis=1, keepdims=True)
    valid = row_totals[:, 0] > 0
    p_row = np.zeros_like(counts, dtype=np.float64)
    p_row[valid] = counts[valid] / row_totals[valid]

    total = counts.sum()
    p_y = row_totals[:, 0] / total

    with np.errstate(divide='ignore', invalid='ignore'):
        log_p = np.where(p_row > 0, np.log2(p_row), 0.0)
    per_row_h = -np.sum(p_row * log_p, axis=1)
    return float(np.sum(p_y * per_row_h))


def entropy_h0(seq: np.ndarray) -> float:
    """
    Compute order-0 (marginal) Shannon entropy H(X) in bits per symbol.
    Returns 0.0 for empty sequences.
    """
    if len(seq) == 0:
        return 0.0
    _, counts = np.unique(seq, return_counts=True)
    total = counts.sum()
    p = counts / total
    with np.errstate(divide='ignore', invalid='ignore'):
        log_p = np.where(p > 0, np.log2(p), 0.0)
    return float(-np.sum(p * log_p))


# ---------------------------------------------------------------------------
# BWT implementation (primary-index variant, no sentinel)
# ---------------------------------------------------------------------------

def bwt_forward(seq: np.ndarray) -> tuple[np.ndarray, int]:
    """
    Burrows-Wheeler Transform (primary-index variant).

    Given a sequence of integer codes, returns (L, primary_index) where:
      L[k] = last symbol of k-th lexicographically-sorted rotation
      primary_index = index k whose rotation starts at offset 0 (the original)

    Uses O(n^2) naive rotation sort — acceptable for n <= 65536 in the probe.
    Alphabet is preserved (no sentinel added).
    """
    n = len(seq)
    if n == 0:
        return np.array([], dtype=seq.dtype), 0
    if n == 1:
        return seq.copy(), 0

    # Build rotation sort key: compare rotations lexicographically.
    # For small n (corpus max 16384), this is fast enough.
    # We use Python tuples for the sort key (handles tie-breaking correctly).
    lst = seq.tolist()

    # Each rotation i is: lst[i:] + lst[:i]
    # Sort indices by rotation key
    indices = sorted(range(n), key=lambda i: lst[i:] + lst[:i])

    primary_index = indices.index(0)  # which sorted rotation is the identity

    # L[k] = last symbol of k-th sorted rotation = seq[(indices[k] - 1) % n]
    L = np.array([seq[(indices[k] - 1) % n] for k in range(n)], dtype=seq.dtype)

    return L, primary_index


def bwt_inverse(L: np.ndarray, primary_index: int) -> np.ndarray:
    """
    Invert the BWT (primary-index variant) using the LF mapping.

    Reconstruct the original sequence from (L, primary_index).
    """
    n = len(L)
    if n == 0:
        return np.array([], dtype=L.dtype)
    if n == 1:
        return L.copy()

    # Counting-sort L to get F (first column)
    # F is the sorted version of L
    # Build LF mapping: for the k-th occurrence of symbol c in L,
    # its predecessor in F is the k-th occurrence of c in F.
    alphabet = sorted(set(L.tolist()))

    # Count occurrences of each symbol
    count = {}
    for sym in alphabet:
        count[sym] = 0

    # Count occurrences in L
    L_list = L.tolist()
    for sym in L_list:
        count[sym] += 1

    # Starting positions in F for each symbol (sorted order)
    start = {}
    pos = 0
    for sym in alphabet:
        start[sym] = pos
        pos += count[sym]

    # Build LF array: lf[k] = position in F that L[k] maps to
    # (the k-th occurrence of L[k] in L maps to the same-rank occurrence in F)
    sym_count = {sym: 0 for sym in alphabet}
    lf = np.zeros(n, dtype=np.int64)
    for k in range(n):
        sym = L_list[k]
        lf[k] = start[sym] + sym_count[sym]
        sym_count[sym] += 1

    # Reconstruct original by walking LF mapping n times from primary_index
    result = np.zeros(n, dtype=L.dtype)
    k = primary_index
    for i in range(n - 1, -1, -1):
        result[i] = L[k]
        k = lf[k]

    return result


# ---------------------------------------------------------------------------
# MTF (Move-To-Front) encoding
# ---------------------------------------------------------------------------

def mtf_encode(seq: np.ndarray) -> np.ndarray:
    """
    Standard Move-To-Front encoding.

    Initialise the alphabet list as sorted(distinct symbols in seq).
    For each symbol s, output its current position in the list, then
    move s to position 0.

    Returns an array of integer ranks (0..n_distinct-1).
    """
    if len(seq) == 0:
        return np.array([], dtype=np.int32)

    alphabet = sorted(set(seq.tolist()))
    # Use a list for O(n * alphabet_size) — fine for n <= 65536, alphabet <= 256
    result = []
    for sym in seq.tolist():
        rank = alphabet.index(sym)
        result.append(rank)
        # Move sym to front
        alphabet.pop(rank)
        alphabet.insert(0, sym)

    return np.array(result, dtype=np.int32)


# ---------------------------------------------------------------------------
# Round-trip assertion
# ---------------------------------------------------------------------------

def assert_round_trip(seq: np.ndarray, name: str) -> None:
    """
    Verify that bwt_inverse(bwt_forward(seq)) == seq exactly.
    Raises AssertionError with diagnostics if not.
    """
    L, pi = bwt_forward(seq)
    recovered = bwt_inverse(L, pi)

    if len(recovered) != len(seq):
        raise AssertionError(
            f"Round-trip FAIL on '{name}': length mismatch "
            f"{len(recovered)} != {len(seq)}"
        )
    if not np.array_equal(recovered, seq):
        mismatches = int(np.sum(recovered != seq))
        raise AssertionError(
            f"Round-trip FAIL on '{name}': {mismatches}/{len(seq)} positions differ"
        )


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

def process_file(entry: dict) -> dict:
    """
    Process one corpus file. Returns per-metric entropy row.
    Asserts BWT round-trip correctness before measuring entropy.
    """
    path = Path(entry['path'])
    data = path.read_bytes()
    n_distinct = len(set(data))

    seq_iorder = build_value_codes(data)

    # Assert round-trip correctness — probe numbers are meaningless without this
    assert_round_trip(seq_iorder, entry['name'])

    # Forward BWT
    L, _pi = bwt_forward(seq_iorder)

    # MTF on BWT output
    mtf_out = mtf_encode(L)

    # Entropy measurements
    H1_iorder = cond_entropy_h1(seq_iorder)
    H1_bwt    = cond_entropy_h1(L)
    H0_bwt_mtf = entropy_h0(mtf_out)
    H0_iorder  = entropy_h0(seq_iorder)

    # Relative reductions vs H1_iorder (positive = improvement)
    denom = H1_iorder if H1_iorder > 0 else 1.0
    rel_bwt_h1  = (H1_iorder - H1_bwt)   / denom
    rel_bwt_mtf = (H1_iorder - H0_bwt_mtf) / denom

    return {
        'name': entry['name'],
        'l': len(data),
        'n_distinct': n_distinct,
        'rho': entry.get('rho', '?'),
        'H1_iorder':   H1_iorder,
        'H1_bwt':      H1_bwt,
        'H0_bwt_mtf':  H0_bwt_mtf,
        'H0_iorder':   H0_iorder,
        'rel_bwt_h1':  rel_bwt_h1,
        'rel_bwt_mtf': rel_bwt_mtf,
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def verdict(rows: list[dict], threshold: float = 0.05) -> tuple[str, str]:
    """
    GO iff max over 7 files of max(rel_bwt_h1, rel_bwt_mtf) >= threshold.
    Returns (GO|NO-GO, rationale string).
    """
    best_bwt_h1  = max(r['rel_bwt_h1']  for r in rows)
    best_bwt_mtf = max(r['rel_bwt_mtf'] for r in rows)
    best_overall = max(best_bwt_h1, best_bwt_mtf)

    if best_overall >= threshold:
        # Identify the best file+column
        if best_bwt_h1 >= best_bwt_mtf:
            best_file = max(rows, key=lambda r: r['rel_bwt_h1'])
            best_col  = 'H1_bwt (BWT order-1)'
            best_rel  = best_bwt_h1
            best_h    = best_file['H1_bwt']
        else:
            best_file = max(rows, key=lambda r: r['rel_bwt_mtf'])
            best_col  = 'H0_bwt_mtf (BWT+MTF order-0)'
            best_rel  = best_bwt_mtf
            best_h    = best_file['H0_bwt_mtf']
        baseline_h = best_file['H1_iorder']
        rationale = (
            f"{best_col} reduces entropy by {best_rel*100:.1f}% relative on "
            f"'{best_file['name']}' "
            f"(H: {baseline_h:.4f} -> {best_h:.4f} bits). "
            f"Threshold {threshold*100:.0f}% met. Proceed to Rust implementation (AC-3/AC-4)."
        )
        return 'GO', rationale
    else:
        rationale = (
            f"Best relative reduction: BWT-H1={best_bwt_h1*100:.1f}%, "
            f"BWT+MTF-H0={best_bwt_mtf*100:.1f}%. "
            f"Neither meets the {threshold*100:.0f}% threshold on any corpus file. "
            f"BWT pre-pass does not meaningfully reduce entropy on this corpus — "
            f"NO-GO recorded as third entry in CUBR-0018/0019 NO-GO lineage."
        )
        return 'NO-GO', rationale


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def render_markdown(rows: list[dict], go_verdict: str, rationale: str,
                    manifest_path: str) -> str:
    """Render per-file results table + verdict as markdown."""
    py_ver = sys.version.split()[0]
    numpy_ver = np.__version__
    try:
        corpus_sha = subprocess.check_output(
            ['shasum', '-a', '256', manifest_path], text=True
        ).split()[0]
    except Exception:
        corpus_sha = 'unavailable'

    from datetime import date
    today = date.today().isoformat()

    header = (
        "# CUBR-0020 AC-2 — BWT Pre-pass Conditional Entropy Probe\n\n"
        f"**Generated:** {today}\n"
        f"**Python:** {py_ver}  **NumPy:** {numpy_ver}\n"
        f"**Corpus manifest:** `{manifest_path}`\n"
        f"**Manifest SHA-256:** `{corpus_sha}`\n\n"
        "## Methodology\n\n"
        "For each corpus file, the i-order value-code sequence `seq_iorder` is built as\n"
        "`seq_codes[i] = v2c[data[i]]` (byte-exact to T4 `seq_codes` in `codec.rs`).\n\n"
        "Four entropy metrics are measured per file:\n\n"
        "| Symbol | Definition | Pipeline it proxies |\n"
        "|--------|-----------|--------------------|\n"
        "| `H1_iorder` | `cond_entropy_h1(seq_iorder)` | T4 incumbent (order-1, i-order) |\n"
        "| `H0_iorder` | `entropy_h0(seq_iorder)` | Reference order-0 |\n"
        "| `H1_bwt` | `cond_entropy_h1(bwt_forward(seq_iorder))` | BWT → order-1 coding |\n"
        "| `H0_bwt_mtf` | `entropy_h0(mtf_encode(bwt_forward(seq_iorder)))` | BWT → MTF → order-0 (bzip2 path) |\n\n"
        "BWT variant: primary-index (no sentinel). Single whole-stream block. "
        "Naive O(n² log n) rotation sort — acceptable for n ≤ 65536 in this probe.\n\n"
        "**Round-trip invariant:** `bwt_inverse(bwt_forward(seq)) == seq` is asserted "
        "for all 7 files before any entropy measurement. A failure aborts the probe.\n\n"
        "## Results\n\n"
        "Relative reductions are computed against `H1_iorder` (T4 baseline). "
        "Positive = improvement over incumbent; negative = regression.\n\n"
        "| File | L | n_dist | rho | H0_iorder | H1_iorder | H1_bwt | H0_bwt_mtf | "
        "Δbwt-H1 rel | Δbwt-mtf rel |\n"
        "|------|---|--------|-----|-----------|-----------|--------|------------|"
        "------------|-------------|\n"
    )

    rows_md = []
    for r in rows:
        rows_md.append(
            f"| {r['name']} | {r['l']} | {r['n_distinct']} | {r['rho']:.4f} "
            f"| {r['H0_iorder']:.4f} | {r['H1_iorder']:.4f} "
            f"| {r['H1_bwt']:.4f} | {r['H0_bwt_mtf']:.4f} "
            f"| {r['rel_bwt_h1']*100:+.1f}% | {r['rel_bwt_mtf']*100:+.1f}% |"
        )

    verdict_section = (
        "\n## Decision Checkpoint (AC-2)\n\n"
        f"**Verdict: {go_verdict}**\n\n"
        f"{rationale}\n\n"
        "**Proxy caveat:** conditional/marginal entropy is a proxy for the real coded size.\n"
        "A reduction is necessary but not sufficient — the Rust bench (AC-3/AC-4) is ground truth.\n"
        "This gate exists to avoid writing Rust against an unmeasured win.\n"
    )

    return header + '\n'.join(rows_md) + '\n' + verdict_section


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='CUBR-0020 AC-2 BWT entropy probe')
    parser.add_argument('--corpus', required=True, help='Path to corpus manifest.json')
    parser.add_argument('--out',    required=True, help='Output markdown path')
    args = parser.parse_args()

    manifest_path = args.corpus
    with open(manifest_path) as f:
        entries = json.load(f)

    print(f"BWT entropy probe — {len(entries)} corpus files", file=sys.stderr)
    print(f"Round-trip assertions: ENABLED (abort on any failure)", file=sys.stderr)
    print("", file=sys.stderr)

    rows = []
    for entry in entries:
        print(f"Processing {entry['name']} (L={entry['size_bytes']})...", file=sys.stderr)
        row = process_file(entry)
        rows.append(row)
        print(
            f"  H1_iorder={row['H1_iorder']:.4f}  "
            f"H1_bwt={row['H1_bwt']:.4f} ({row['rel_bwt_h1']*100:+.1f}%)  "
            f"H0_bwt_mtf={row['H0_bwt_mtf']:.4f} ({row['rel_bwt_mtf']*100:+.1f}%)",
            file=sys.stderr
        )

    go_verdict, rationale = verdict(rows)

    md = render_markdown(rows, go_verdict, rationale, manifest_path=manifest_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)

    # Console summary table
    print(f"\n{'File':<20} {'H1_iorder':>10} {'H1_bwt':>10} {'H0_bwt_mtf':>12} {'Δbwt-H1':>8} {'Δmtf':>8}")
    print('-' * 76)
    for r in rows:
        print(
            f"{r['name']:<20} {r['H1_iorder']:>10.4f} {r['H1_bwt']:>10.4f} "
            f"{r['H0_bwt_mtf']:>12.4f} "
            f"{r['rel_bwt_h1']*100:>+7.1f}% {r['rel_bwt_mtf']*100:>+7.1f}%"
        )
    print(f"\nVERDICT: {go_verdict}")
    print(f"Rationale: {rationale}")
    print(f"\nReport written to: {args.out}", file=sys.stderr)


if __name__ == '__main__':
    main()
