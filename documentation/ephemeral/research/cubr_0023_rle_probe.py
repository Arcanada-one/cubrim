#!/usr/bin/env python3
"""
CUBR-0023 — RLE pre-pass on value-stream Phase A probe.

Research question: does an RLE pre-pass applied to the value-code stream
BEFORE order-1 Huffman (T4) yield a net reduction vs T4 alone?

Key architectural facts replicated from codec.rs:
- seq_codes[i] = v2c[data[i]] for i in 0..L-1 (i-order, N-invariant)
- T4 (EntropyContext) uses order-1 context with MIN_CTX_COUNT=16 threshold.
- This probe models:
    (a) RLE-codes alone (scheme 2): 3 bytes per run (code:u8 + run:u16 BE)
    (b) RLE pre-pass + order-1 Huffman (proposed scheme 6):
        side-table overhead + order-1 Huffman on the residual literal+escape stream
    (c) T4 baseline: exact Python twin of context_huffman_size from codec.rs

Corpus: 7 SHA-pinned files, manifest.json fidelity check.
"""

import json
import math
import os
import hashlib
import heapq
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

CORPUS_DIR = os.path.join(
    os.path.dirname(__file__), "corpus"
)
MANIFEST_PATH = os.path.join(CORPUS_DIR, "manifest.json")
# T4 constants from codec.rs
MIN_CTX_COUNT = 16
MAX_RUN = 65535  # rle.rs MAX_RUN

# ─── Huffman helpers ──────────────────────────────────────────────────────────

def compute_huffman_code_lengths(freqs: List[int]) -> List[int]:
    """
    Canonical Huffman code-length assignment matching canonical_code_lengths in huffman.rs.
    freqs[sym] = count of symbol sym. Returns code_len[sym] (0 = not used / length-0 sentinel).
    """
    n = len(freqs)
    if n == 0:
        return []
    total = sum(freqs)
    if total == 0:
        return [0] * n

    # Build heap with (freq, sym) for all symbols with freq>0
    heap = [(f, i) for i, f in enumerate(freqs) if f > 0]
    if not heap:
        return [0] * n

    heapq.heapify(heap)

    if len(heap) == 1:
        # Only one symbol: code-length = 1
        code_len = [0] * n
        code_len[heap[0][1]] = 1
        return code_len

    # Standard Huffman tree
    # Use internal node sentinel as negative index
    parent: Dict[int, int] = {}
    freq_map: Dict[int, int] = {i: f for f, i in heap}
    next_internal = -1

    # heap holds (freq, node_id) where node_id >= 0 is a leaf, < 0 is internal
    heap2 = list(heap)
    heapq.heapify(heap2)

    while len(heap2) > 1:
        f1, n1 = heapq.heappop(heap2)
        f2, n2 = heapq.heappop(heap2)
        internal = next_internal
        next_internal -= 1
        freq_map[internal] = f1 + f2
        parent[n1] = internal
        parent[n2] = internal
        heapq.heappush(heap2, (f1 + f2, internal))

    # Root is the last remaining node
    root = heap2[0][1]

    # Compute depths
    code_len = [0] * n
    for i, f in enumerate(freqs):
        if f == 0:
            continue
        node = i
        depth = 0
        while node != root:
            node = parent[node]
            depth += 1
        code_len[i] = depth

    return code_len


def huffman_bitstream_size(seq: List[int], code_len: List[int]) -> int:
    """Compute total bits for sequence using code_len table."""
    return sum(code_len[c] for c in seq)


def context_huffman_size_python(seq_codes: List[int], n_distinct: int) -> int:
    """
    Python twin of context_huffman_size from codec.rs.
    Wire: 2(n_contexts:u16) + n_ctx*(2+n_distinct) header + ceil(bits/8) bitstream.
    MIN_CTX_COUNT=16. Fallback ctx_id=0 always present.
    """
    if not seq_codes:
        return 2  # n_contexts=0 header

    # Build per-context frequency tables
    fallback_freq = [0] * n_distinct
    ctx_freq: Dict[int, List[int]] = {}

    prev_ctx = 0  # sentinel
    for code in seq_codes:
        if prev_ctx not in ctx_freq:
            ctx_freq[prev_ctx] = [0] * n_distinct
        if code < n_distinct:
            ctx_freq[prev_ctx][code] += 1
            fallback_freq[code] += 1
        prev_ctx = code

    # Determine which contexts meet MIN_CTX_COUNT
    ctx_total = {ctx: sum(f) for ctx, f in ctx_freq.items()}

    # Build fallback code_len from global order-0 frequencies
    fallback_code_len = compute_huffman_code_lengths(fallback_freq)

    # Emit: fallback (ctx_id=0) + qualifying real contexts (ascending ctx_id)
    ctx_tables = [(0, fallback_code_len)]  # fallback always first
    for ctx_id in sorted(ctx_freq.keys()):
        if ctx_id == 0:
            continue  # fallback already handled
        if ctx_total.get(ctx_id, 0) >= MIN_CTX_COUNT:
            cl = compute_huffman_code_lengths(ctx_freq[ctx_id])
            ctx_tables.append((ctx_id, cl))

    n_ctx = len(ctx_tables)
    header_bytes = 2 + n_ctx * (2 + n_distinct)

    # Compute bitstream size
    ctx_idx = {ctx_id: i for i, (ctx_id, _) in enumerate(ctx_tables)}
    fallback_idx = ctx_idx.get(0, 0)

    total_bits = 0
    prev_ctx = 0
    for code in seq_codes:
        table_idx = ctx_idx.get(prev_ctx, fallback_idx)
        _, code_len_table = ctx_tables[table_idx]
        bits = code_len_table[code] if code < len(code_len_table) else 8
        total_bits += bits
        prev_ctx = code

    bitstream_bytes = math.ceil(total_bits / 8)
    return header_bytes + bitstream_bytes


# ─── RLE pre-pass model ───────────────────────────────────────────────────────

@dataclass
class RunStructure:
    """Run-length statistics for a value-code sequence."""
    total_codes: int
    n_runs: int
    frac_in_runs_ge2: float   # fraction of codes in runs of length >= 2
    frac_in_runs_ge3: float
    frac_in_runs_ge4: float
    avg_run_len: float
    max_run_len: int
    run_len_histogram: Dict[int, int] = field(default_factory=dict)


def analyze_run_structure(seq_codes: List[int]) -> RunStructure:
    """Measure run structure of seq_codes (identical code values in sequence)."""
    if not seq_codes:
        return RunStructure(0, 0, 0.0, 0.0, 0.0, 0.0, 0, {})

    runs = []
    cur = seq_codes[0]
    run = 1
    for c in seq_codes[1:]:
        if c == cur:
            run += 1
        else:
            runs.append(run)
            cur = c
            run = 1
    runs.append(run)

    hist = Counter(runs)
    total = len(seq_codes)
    n_runs = len(runs)

    codes_in_ge2 = sum(r for r in runs if r >= 2)
    codes_in_ge3 = sum(r for r in runs if r >= 3)
    codes_in_ge4 = sum(r for r in runs if r >= 4)

    return RunStructure(
        total_codes=total,
        n_runs=n_runs,
        frac_in_runs_ge2=codes_in_ge2 / total if total else 0.0,
        frac_in_runs_ge3=codes_in_ge3 / total if total else 0.0,
        frac_in_runs_ge4=codes_in_ge4 / total if total else 0.0,
        avg_run_len=total / n_runs if n_runs else 0.0,
        max_run_len=max(runs) if runs else 0,
        run_len_histogram=dict(hist),
    )


def rle_codes_size_bytes(seq_codes: List[int]) -> int:
    """
    Byte size of ValueScheme::RleCodes (scheme 2) stream.
    3 bytes per run: code(u8) + run_len(u16 BE), max run = MAX_RUN.
    """
    n_runs = 0
    if not seq_codes:
        return 0
    cur = seq_codes[0]
    run = 1
    for c in seq_codes[1:]:
        if c == cur and run < MAX_RUN:
            run += 1
        else:
            n_runs += 1
            cur = c
            run = 1
    n_runs += 1
    return n_runs * 3


def rle_then_huffman_size(seq_codes: List[int], n_distinct: int) -> int:
    """
    Model the proposed RLE pre-pass + order-1 Huffman scheme (AC-2).

    Design: encode runs as (LITERAL_token | ESCAPE + run_len), then apply
    order-1 Huffman to the resulting token stream.

    Token alphabet = [0..n_distinct-1] + escape symbol n_distinct.
    - For each run of length 1: emit one literal token = code
    - For each run of length k >= 2: emit one literal token = code,
      then one ESCAPE token (= n_distinct) + run_len stored as u16 (2 bytes side-channel).
      The Huffman stream codes only the escape token; the run count goes in a parallel
      side table.

    Side-table: 2 bytes (u16) per run >= 2.
    Escape token n_distinct is added to the alphabet for Huffman.
    The Huffman stream = seq of tokens: literal + optional escape per run.

    This is the "canonical" RLE+Huffman model. Key insight: the residual stream
    after RLE marking has collapsed runs to 1 literal + 1 escape. Order-1 Huffman
    on this shorter, lower-entropy stream competes with T4's per-symbol coding.

    Cost = side_table_bytes + context_huffman_size(token_stream, n_distinct+1)
    """
    if not seq_codes:
        return 2  # empty

    # Build token stream
    tokens: List[int] = []
    escape_sym = n_distinct  # new symbol for "continuation run"
    side_table_count = 0  # runs >= 2 that go to side table

    cur = seq_codes[0]
    run = 1
    for c in seq_codes[1:]:
        if c == cur and run < MAX_RUN:
            run += 1
        else:
            tokens.append(cur)  # literal
            if run >= 2:
                tokens.append(escape_sym)  # escape
                side_table_count += 1
            cur = c
            run = 1
    tokens.append(cur)
    if run >= 2:
        tokens.append(escape_sym)
        side_table_count += 1

    side_table_bytes = side_table_count * 2  # u16 per run count

    # Order-1 Huffman on token stream with extended alphabet n_distinct+1
    huffman_bytes = context_huffman_size_python(tokens, n_distinct + 1)

    return side_table_bytes + huffman_bytes


# ─── Corpus loading + value-code extraction ───────────────────────────────────

def build_v2c(data: bytes) -> Tuple[Dict[int, int], List[int]]:
    """
    Build value->code map and inverse_dict, matching codec.rs build_value_dict.
    Codes assigned in ascending order of value (sorted distinct values).
    """
    distinct = sorted(set(data))
    v2c = {v: c for c, v in enumerate(distinct)}
    inverse_dict = distinct  # inverse_dict[code] = value
    return v2c, inverse_dict


def extract_seq_codes(data: bytes) -> Tuple[List[int], int]:
    """
    Extract value-code sequence in i-order (matching codec.rs seq_codes construction).
    Returns (seq_codes, n_distinct).
    """
    v2c, inverse_dict = build_v2c(data)
    seq_codes = [v2c[b] for b in data]
    return seq_codes, len(inverse_dict)


def verify_sha256(path: str, expected: str) -> bool:
    with open(path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    return actual == expected


def load_corpus():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    corpus = []
    for entry in manifest:
        path = entry["path"]
        sha = entry["sha256"]
        if not verify_sha256(path, sha):
            raise ValueError(f"SHA256 mismatch for {entry['name']}: {path}")
        with open(path, "rb") as f:
            data = f.read()
        corpus.append({
            "name": entry["name"],
            "size": entry["size_bytes"],
            "rho": entry["rho"],
            "data": data,
            "sha256": sha,
            "actual_t4_bytes": entry.get("actual_t4_bytes"),
            "actual_t4_mode": entry.get("actual_t4_mode"),
        })
    return corpus


# ─── T4 actual output measurement via Rust CLI ───────────────────────────────

def measure_t4_actual_bytes(data: bytes, cubrim_bin: str) -> Optional[int]:
    """
    Run the actual Cubrim encoder to get real T4 output bytes.
    Returns encoded size or None if binary unavailable.
    """
    import subprocess, tempfile
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tf:
            tf.write(data)
            input_path = tf.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".cbr") as tf:
            output_path = tf.name

        result = subprocess.run(
            [cubrim_bin, "compress", input_path, output_path],
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            size = os.path.getsize(output_path)
            return size
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(input_path)
            os.unlink(output_path)
        except Exception:
            pass


# ─── Main analysis ────────────────────────────────────────────────────────────

@dataclass
class FileResult:
    name: str
    size: int
    rho: float
    n_distinct: int
    # Run structure
    run_struct: RunStructure
    # Size models (value-stream bytes only — does not include header/gap-stream)
    rle_codes_bytes: int        # scheme 2 alone
    rle_huffman_bytes: int      # proposed: RLE pre-pass + T4 Huffman
    t4_huffman_bytes: int       # T4 baseline (context_huffman_size Python twin)
    # Full encoded size from Rust binary or manifest (if available)
    t4_actual_bytes: Optional[int]
    # Actual storage mode from Rust encoder ("cube" or "raw"); from manifest or binary run
    t4_actual_mode: Optional[str]


def run_probe(cubrim_bin: Optional[str] = None) -> List[FileResult]:
    corpus = load_corpus()
    results = []

    for entry in corpus:
        data = entry["data"]
        seq_codes, n_distinct = extract_seq_codes(data)

        run_struct = analyze_run_structure(seq_codes)
        rle_codes_b = rle_codes_size_bytes(seq_codes)
        rle_huff_b = rle_then_huffman_size(seq_codes, n_distinct)
        t4_b = context_huffman_size_python(seq_codes, n_distinct)

        # Prefer manifest-pinned actuals (from CUBR-0017-bench.json, code_sha 734d540);
        # fall back to live Rust binary measurement when binary is present.
        t4_actual: Optional[int] = entry.get("actual_t4_bytes")
        t4_mode: Optional[str] = entry.get("actual_t4_mode")
        if cubrim_bin and os.path.exists(cubrim_bin) and t4_actual is None:
            t4_actual = measure_t4_actual_bytes(data, cubrim_bin)

        results.append(FileResult(
            name=entry["name"],
            size=entry["size"],
            rho=entry["rho"],
            n_distinct=n_distinct,
            run_struct=run_struct,
            rle_codes_bytes=rle_codes_b,
            rle_huffman_bytes=rle_huff_b,
            t4_huffman_bytes=t4_b,
            t4_actual_bytes=t4_actual,
            t4_actual_mode=t4_mode,
        ))

    return results


def print_report(results: List[FileResult], code_sha: str, manifest_sha: str):
    print("# CUBR-0023 — RLE Pre-pass Value-Stream Probe")
    print()
    print(f"**Code SHA:** {code_sha}")
    print(f"**Manifest SHA-256:** {manifest_sha}")
    print()

    print("## AC-1 — Run-Length Structure of Value-Stream (i-order)")
    print()
    print("| File | L | n_dist | rho | n_runs | avg_run | max_run | frac≥2 | frac≥3 | frac≥4 |")
    print("|------|---|--------|-----|--------|---------|---------|--------|--------|--------|")
    for r in results:
        rs = r.run_struct
        print(f"| {r.name} | {r.size} | {r.n_distinct} | {r.rho:.4f} "
              f"| {rs.n_runs} | {rs.avg_run_len:.2f} | {rs.max_run_len} "
              f"| {rs.frac_in_runs_ge2:.3f} | {rs.frac_in_runs_ge3:.3f} "
              f"| {rs.frac_in_runs_ge4:.3f} |")

    print()
    print("## AC-2 — Value-Stream Size: RLE-codes vs RLE+T4 vs T4 baseline")
    print()
    print("Notes:")
    print("- Sizes are value-stream bytes only (header + gap streams excluded — identical across schemes).")
    print("- RLE-codes: scheme 2, 3 bytes/run (code:u8 + run:u16).")
    print("- RLE+T4: escape-based RLE token stream + order-1 Huffman (side-table 2B/run-ge-2).")
    print("- T4 (Python twin): Python replication of context_huffman_size from codec.rs.")
    print()
    print("| File | L | T4 bytes | RLE-codes bytes | RLE+T4 bytes | RLE-codes vs T4 | RLE+T4 vs T4 |")
    print("|------|---|----------|-----------------|--------------|-----------------|--------------|")
    for r in results:
        t4 = r.t4_huffman_bytes
        rc = r.rle_codes_bytes
        rh = r.rle_huffman_bytes
        delta_rc = (rc - t4) / t4 * 100 if t4 else 0
        delta_rh = (rh - t4) / t4 * 100 if t4 else 0
        sign_rc = "+" if delta_rc > 0 else ""
        sign_rh = "+" if delta_rh > 0 else ""
        print(f"| {r.name} | {r.size} | {t4} | {rc} | {rh} "
              f"| {sign_rc}{delta_rc:.1f}% | {sign_rh}{delta_rh:.1f}% |")

    print()
    print("## AC-2b — Ratio Estimates (value-stream + header estimate)")
    print()
    print("Note: The header size is fixed regardless of value scheme.")
    print("Aggregate ratio = sum(encoded_size) / sum(original_size).")
    print("For a rough per-file ratio, we use value_stream_bytes / original_bytes as proxy.")
    print("T4 baseline aggregate 0.587240 is from real Rust bench (includes header+gap streams).")
    print()
    print("| File | T4 bytes/orig | RLE-codes bytes/orig | RLE+T4 bytes/orig |")
    print("|------|---------------|---------------------|-------------------|")
    for r in results:
        t4_ratio = r.t4_huffman_bytes / r.size
        rc_ratio = r.rle_codes_bytes / r.size
        rh_ratio = r.rle_huffman_bytes / r.size
        print(f"| {r.name} | {t4_ratio:.4f} | {rc_ratio:.4f} | {rh_ratio:.4f} |")


def compute_t6_effective(r: "FileResult") -> int:
    """
    Compute the raw-store-clamped T6 (RLE+Huffman) size estimate for a single file.

    For files that the real encoder raw-stores (actual_t4_mode == "raw"), no value-scheme
    change can help — the encoder will raw-store T6 output just as it does T4.  Using the
    unclamped rle_huffman_bytes (a fictional cube-mode model) for these files produces a
    spuriously low T6 total and a false GO verdict.

    Clamped model:
      - raw-stored files  → actual_t4_bytes  (raw-store size is invariant to value scheme)
      - cube-stored files → actual_t4_bytes × (1 + relative_delta_of_python_model)
                            i.e. apply the Python model's relative improvement/regression
                            to the real T4 bytes so the estimate is anchored to measured data.
      - fallback (no actuals) → rle_huffman_bytes (value-stream model, may be inaccurate)
    """
    if r.t4_actual_bytes is None or r.t4_actual_mode is None:
        # No manifest actuals: fall back to raw value-stream model (less accurate).
        return r.rle_huffman_bytes

    if r.t4_actual_mode == "raw":
        # Raw-stored regardless of value scheme — T6 cannot change this outcome.
        return r.t4_actual_bytes

    # Cube-stored: apply Python model's relative delta to the real T4 encoded size.
    if r.t4_huffman_bytes == 0:
        return r.rle_huffman_bytes
    relative_delta = (r.rle_huffman_bytes - r.t4_huffman_bytes) / r.t4_huffman_bytes
    return round(r.t4_actual_bytes * (1.0 + relative_delta))


def compute_go_nogo(results: List[FileResult]) -> Tuple[str, str]:
    """
    AC-3: Determine GO/NO-GO based on whether RLE+T4 beats T4 on aggregate.

    Uses the raw-store-clamped T6 model (compute_t6_effective) so files that the
    real encoder raw-stores are not counted with fictional cube-mode value-stream
    sizes — which would produce a spurious GO verdict.

    Returns (verdict, explanation).
    """
    # Baseline: real T4 encoded totals from manifest actuals (or Python model fallback).
    t4_total = sum(
        r.t4_actual_bytes if r.t4_actual_bytes is not None else r.t4_huffman_bytes
        for r in results
    )
    rh_total = sum(compute_t6_effective(r) for r in results)
    rc_total = sum(r.rle_codes_bytes for r in results)

    delta_rh_pct = (rh_total - t4_total) / t4_total * 100 if t4_total else 0
    delta_rc_pct = (rc_total - t4_total) / t4_total * 100 if t4_total else 0

    files_rh_better = [r.name for r in results if compute_t6_effective(r) < (r.t4_actual_bytes or r.t4_huffman_bytes)]
    files_rc_better = [r.name for r in results if r.rle_codes_bytes < (r.t4_actual_bytes or r.t4_huffman_bytes)]

    threshold_pct = -2.0  # require at least 2% aggregate improvement to go GO

    if delta_rh_pct <= threshold_pct:
        verdict = "GO"
        explanation = (
            f"RLE+T4 clamped aggregate {delta_rh_pct:+.2f}% vs T4 "
            f"(threshold {threshold_pct:.0f}%). Better on: {files_rh_better}."
        )
    else:
        verdict = "NO-GO"
        explanation = (
            f"RLE+T4 clamped aggregate {delta_rh_pct:+.2f}% vs T4 "
            f"(threshold {threshold_pct:.0f}%). "
            f"RLE-codes aggregate {delta_rc_pct:+.2f}% vs T4. "
            f"Order-1 context Huffman already absorbs the run structure; "
            f"the escape overhead and Huffman table side-cost cancel any RLE gain. "
            f"Files where RLE-codes beats T4: {files_rc_better}. "
            f"Files where RLE+T4 beats T4: {files_rh_better}."
        )
    return verdict, explanation


def main():
    import subprocess
    import sys

    # Get code SHA from git
    try:
        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
            text=True
        ).strip()
    except Exception:
        code_sha = "unknown"

    # Manifest SHA
    with open(MANIFEST_PATH, "rb") as f:
        manifest_sha = hashlib.sha256(f.read()).hexdigest()

    # Cubrim binary path
    cubrim_bin = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "target", "release", "cubrim"
    )
    if not os.path.exists(cubrim_bin):
        cubrim_bin = None

    results = run_probe(cubrim_bin)

    print_report(results, code_sha, manifest_sha)

    verdict, explanation = compute_go_nogo(results)
    print()
    print(f"## AC-3 — GO/NO-GO")
    print()
    print(f"**Verdict: {verdict}**")
    print()
    print(explanation)

    if verdict == "GO":
        print()
        print("Phase B (Rust implementation) is warranted.")
        sys.exit(0)
    else:
        print()
        print("Phase B (Rust implementation) is SKIPPED — NO-GO result.")
        print("AC-4 is n/a.")
        sys.exit(0)


if __name__ == "__main__":
    main()
