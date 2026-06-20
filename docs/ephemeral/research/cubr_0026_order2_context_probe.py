#!/usr/bin/env python3
"""
CUBR-0026 — Order-2 context key: entropy-depth hypothesis probe.

Research question: does keying the Huffman context on TWO previous value-codes
(prev2_code, prev_code) yield a net size reduction vs T4 order-1 baseline?

Architectural grounding:
  - T4 (EntropyContext, codec.rs): prev_ctx = code as u16 (sentinel 0 at pos 0).
    Wire header: 2(n_contexts:u16 BE) + n_ctx*(2+n_distinct) + bitstream.
    MIN_CTX_COUNT=16; sparse contexts fall back to order-0 fallback table.
  - build_value_dict (bitpack.rs:19-31): sorts distinct values ascending;
    code = rank. Monotonic bijection: code in [0, n_distinct).

Order-2 extension:
  - Context key = (prev2_code, prev_code) — a pair of u16 values.
  - Position 0: context = (0, 0)  [sentinel pair — mirrors T4's prev_ctx=0 at pos 0]
  - Position 1: context = (0, seq_codes[0])  [prev2 not yet defined → sentinel 0]
  - Position i>=2: context = (seq_codes[i-2], seq_codes[i-1])
  - Decoder reconstructs identical context from the two already-decoded values.
    REVERSIBILITY: the context is a pure deterministic function of the previously
    decoded sequence — no side-channel needed.

Wire format modelled for order-2 header:
  n_contexts: u16 BE  (2 bytes)
  for each qualifying context (prev2, prev) with count >= MIN_CTX_COUNT:
    prev2_code: u16 BE  (2 bytes)
    prev_code:  u16 BE  (2 bytes)  [<-- 2x u16 per key vs T4's 1x u16]
    code_len[n_distinct]: n_distinct bytes
  [fallback table always present, key = (0, 0)]
  bitstream: MSB-first, ceil(bits/8) bytes

Header cost: 2 + n_ctx * (4 + n_distinct)  [vs T4: 2 + n_ctx * (2 + n_distinct)]
The extra 2 bytes per context entry (second u16 in the key) is the order-2
header surcharge.

Fallback chain:
  1. If (prev2, prev) context has >= MIN_CTX_COUNT observations → use its table.
  2. Else fall back to order-1 context (prev) if that has >= MIN_CTX_COUNT obs.
  3. Else fall back to order-0 (global fallback) table.
  This is a 3-level fallback chain. At encoding/decoding time the decoder walks
  the same deterministic chain from the two previously decoded values — fully
  reversible.

Clamp rule (CUBR-0023 lesson, reused from CUBR-0025):
  Raw-stored files (actual_t4_mode == "raw"): the real encoder picks raw when
  raw_size <= encoded_size. No value-scheme change can improve them — clamp to
  actual_t4_bytes.
  Cube-stored files (actual_t4_mode == "cube"): scale actual_t4_bytes by the
  Python model's relative delta vs T4 Python model:
    estimate = actual_t4_bytes * (order2_python_bytes / t4_python_bytes)
  This anchors to real Rust T4 measurements while applying the model's delta.

The Python twin is ratio-anchored, NOT per-file byte-exact against Rust.
(T4 twin diverges absolutely: text: ~6059 B twin vs 5705 B actual, +6.2%.)
The relative delta and clamp-anchoring make the aggregate comparison meaningful.

Threshold sweep: MIN_CTX_COUNT values tested = {16, 32, 64, 128}.
GO threshold: aggregate ratio <= 0.5755 (i.e. >= -2% improvement vs 0.587240).
"""

import json
import math
import os
import hashlib
import heapq
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

CORPUS_DIR = os.path.join(
    os.path.dirname(__file__), "corpus"
)
MANIFEST_PATH = os.path.join(CORPUS_DIR, "manifest.json")

# Threshold sweep values for MIN_CTX_COUNT (AC-1 requires >=2)
MIN_CTX_COUNT_VALUES = [16, 32, 64, 128]

T4_BASELINE_AGGREGATE = 0.587240
T4_BASELINE_TOTAL = 30217  # = sum(actual_t4_bytes) from manifest
CORPUS_TOTAL = 51456       # = sum(size_bytes) from manifest
GO_THRESHOLD_RATIO = 0.5755  # = 0.587240 * 0.98 (2% improvement)


# ─── Huffman helpers (identical to cubr_0023/0025 — verified canonical) ──────

def compute_huffman_code_lengths(freqs: List[int]) -> List[int]:
    """
    Canonical Huffman code-length assignment matching canonical_code_lengths in huffman.rs.
    freqs[sym] = count. Returns code_len[sym] (0 = unused / sentinel).
    """
    n = len(freqs)
    if n == 0:
        return []
    total = sum(freqs)
    if total == 0:
        return [0] * n

    heap = [(f, i) for i, f in enumerate(freqs) if f > 0]
    if not heap:
        return [0] * n
    heapq.heapify(heap)

    if len(heap) == 1:
        code_len = [0] * n
        code_len[heap[0][1]] = 1
        return code_len

    parent: Dict[int, int] = {}
    freq_map: Dict[int, int] = {i: f for f, i in heap}
    next_internal = -1

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

    root = heap2[0][1]

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


def huffman_bits_for_seq(freqs: List[int], seq_len: int) -> float:
    """
    Given frequency vector, compute expected bits for encoding seq_len symbols.
    Used for conditional entropy comparison.
    """
    code_lens = compute_huffman_code_lengths(freqs)
    total = sum(freqs)
    if total == 0:
        return 0.0
    bits = sum(freqs[i] * code_lens[i] for i in range(len(freqs)) if freqs[i] > 0)
    return bits


# ─── T4 Python twin (byte-exact verified aggregate from CUBR-0023/0025) ──────

def context_huffman_size_t4(seq_codes: List[int], n_distinct: int,
                             min_ctx_count: int = 16) -> int:
    """
    Python twin of context_huffman_encode from codec.rs (T4 order-1 baseline).
    Wire: 2(n_contexts:u16) + n_ctx*(2+n_distinct) header + ceil(bits/8) bitstream.
    Fallback ctx_id=0 always present.

    NOTE: per-file this twin diverges absolutely from Rust (text: ~+6.2%).
    Used only for the within-model order-2/T4 ratio; the absolute offset cancels.
    """
    if not seq_codes:
        return 2

    fallback_freq = [0] * n_distinct
    ctx_freq: Dict[int, List[int]] = {}

    prev_ctx = 0  # sentinel for position 0
    for code in seq_codes:
        if prev_ctx not in ctx_freq:
            ctx_freq[prev_ctx] = [0] * n_distinct
        if code < n_distinct:
            ctx_freq[prev_ctx][code] += 1
            fallback_freq[code] += 1
        prev_ctx = code

    ctx_total = {ctx: sum(f) for ctx, f in ctx_freq.items()}
    fallback_code_len = compute_huffman_code_lengths(fallback_freq)

    # ctx_id=0 is always the fallback
    ctx_tables = [(0, fallback_code_len)]
    for ctx_id in sorted(ctx_freq.keys()):
        if ctx_id == 0:
            continue
        if ctx_total.get(ctx_id, 0) >= min_ctx_count:
            cl = compute_huffman_code_lengths(ctx_freq[ctx_id])
            ctx_tables.append((ctx_id, cl))

    n_ctx = len(ctx_tables)
    # T4 wire header: 2 + n_ctx * (2 + n_distinct)  [2-byte ctx_id per entry]
    header_bytes = 2 + n_ctx * (2 + n_distinct)

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


# ─── Order-2 context Huffman size model ───────────────────────────────────────

def order2_huffman_size(
    seq_codes: List[int],
    n_distinct: int,
    min_ctx_count: int,
) -> Tuple[int, int, int, int, int, int]:
    """
    Compute theoretical total bytes for order-2 context-adaptive Huffman.

    Context key = (prev2_code, prev_code) — a tuple of two u16 codes.
    Sentinel: position 0 → (0, 0); position 1 → (0, seq_codes[0]).

    Fallback chain (3 levels):
      1. (prev2, prev) has >= min_ctx_count → use its table
      2. elif (prev) order-1 context has >= min_ctx_count → use order-1 table
      3. else → use order-0 (global) fallback

    Wire header per order-2 qualifying context: 4 bytes key (2×u16) + n_distinct
    vs T4's 2 bytes key (1×u16) + n_distinct. Header formula:
      2 (n_contexts:u16) + n_ctx * (4 + n_distinct)

    Returns:
      (total_bytes, header_bytes, bitstream_bytes,
       n_order2_tables, n_order1_fallback_tables, n_order0_fallback_used)
      where n_order2_tables = number of (prev2,prev) contexts meeting threshold
            n_order1_fallback_tables = distinct order-1 contexts serving as fallback
            n_order0_fallback_used = positions encoded with order-0 fallback
    """
    if not seq_codes:
        # Minimal: fallback table only
        header_bytes = 2 + 1 * (4 + n_distinct)
        return header_bytes, header_bytes, 0, 0, 0, 0

    # ── Step 1: Build per-context (order-2) frequency tables ─────────────────
    # ctx2_freq[(prev2, prev)][sym] = count
    ctx2_freq: Dict[Tuple[int, int], List[int]] = {}
    # Also build order-1 frequency tables for fallback
    ctx1_freq: Dict[int, List[int]] = {}
    # Global order-0 fallback
    fallback_freq = [0] * n_distinct

    # Walk the sequence
    for i, code in enumerate(seq_codes):
        if i == 0:
            ctx2 = (0, 0)   # sentinel pair
            ctx1 = 0        # sentinel
        elif i == 1:
            ctx2 = (0, seq_codes[0])  # prev2 not yet defined → sentinel 0
            ctx1 = seq_codes[0]
        else:
            ctx2 = (seq_codes[i - 2], seq_codes[i - 1])
            ctx1 = seq_codes[i - 1]

        if ctx2 not in ctx2_freq:
            ctx2_freq[ctx2] = [0] * n_distinct
        if ctx1 not in ctx1_freq:
            ctx1_freq[ctx1] = [0] * n_distinct

        if code < n_distinct:
            ctx2_freq[ctx2][code] += 1
            ctx1_freq[ctx1][code] += 1
            fallback_freq[code] += 1

    # ── Step 2: Determine qualifying contexts at each level ───────────────────
    ctx2_total = {ctx: sum(f) for ctx, f in ctx2_freq.items()}
    ctx1_total = {ctx: sum(f) for ctx, f in ctx1_freq.items()}

    # Order-2 contexts that qualify (have own table in the wire)
    qualifying_ctx2 = {ctx for ctx, tot in ctx2_total.items() if tot >= min_ctx_count}
    # Order-1 contexts that qualify (used as intermediate fallback)
    qualifying_ctx1 = {ctx for ctx, tot in ctx1_total.items() if tot >= min_ctx_count}

    # ── Step 3: Build Huffman code lengths ────────────────────────────────────
    # Global (order-0) fallback
    fallback_code_len = compute_huffman_code_lengths(fallback_freq)

    # Order-1 tables (for fallback chain)
    ctx1_code_len: Dict[int, List[int]] = {}
    for ctx1 in qualifying_ctx1:
        ctx1_code_len[ctx1] = compute_huffman_code_lengths(ctx1_freq[ctx1])

    # Order-2 tables (the "primary" tables in the wire format)
    ctx2_code_len: Dict[Tuple[int, int], List[int]] = {}
    for ctx2 in qualifying_ctx2:
        ctx2_code_len[ctx2] = compute_huffman_code_lengths(ctx2_freq[ctx2])

    # ── Step 4: Compute header size ───────────────────────────────────────────
    # Wire format: n_contexts (u16, 2B) + for each qualifying order-2 ctx:
    #   prev2 (u16, 2B) + prev (u16, 2B) + code_len[n_distinct] (n_distinct B)
    # Fallback table (order-0): stored as key (0, 0) — same 4+n_distinct bytes.
    # Total contexts written to wire = 1 (fallback) + len(qualifying_ctx2)
    # But if (0,0) is also a qualifying order-2 context, it's already included —
    # we use the order-2 table for it. Count distinct entries:
    wire_contexts = qualifying_ctx2 | {(0, 0)}  # (0,0) fallback always present
    n_wire_contexts = len(wire_contexts)
    header_bytes = 2 + n_wire_contexts * (4 + n_distinct)

    # ── Step 5: Compute bitstream ─────────────────────────────────────────────
    total_bits = 0
    n_order2_used = 0    # positions using order-2 table
    n_order1_used = 0    # positions falling back to order-1
    n_order0_used = 0    # positions falling back to order-0

    # Track which order-1 contexts serve as fallback (for counting unique fallback tables)
    order1_fallback_ctxs_used: set = set()

    for i, code in enumerate(seq_codes):
        if i == 0:
            ctx2 = (0, 0)
            ctx1 = 0
        elif i == 1:
            ctx2 = (0, seq_codes[0])
            ctx1 = seq_codes[0]
        else:
            ctx2 = (seq_codes[i - 2], seq_codes[i - 1])
            ctx1 = seq_codes[i - 1]

        # Fallback chain: order-2 → order-1 → order-0
        if ctx2 in ctx2_code_len:
            cl = ctx2_code_len[ctx2]
            n_order2_used += 1
        elif ctx1 in ctx1_code_len:
            cl = ctx1_code_len[ctx1]
            n_order1_used += 1
            order1_fallback_ctxs_used.add(ctx1)
        else:
            cl = fallback_code_len
            n_order0_used += 1

        bits = cl[code] if code < len(cl) else 8
        total_bits += bits

    bitstream_bytes = math.ceil(total_bits / 8)
    total_bytes = header_bytes + bitstream_bytes

    n_order2_tables = len(qualifying_ctx2)
    n_order1_fallback_tables = len(order1_fallback_ctxs_used)
    return (total_bytes, header_bytes, bitstream_bytes,
            n_order2_tables, n_order1_fallback_tables, n_order0_used)


# ─── Conditional entropy comparison (AC-2) ────────────────────────────────────

def conditional_entropy_order1(seq_codes: List[int], n_distinct: int) -> float:
    """
    H(X_t | X_{t-1}) — empirical conditional entropy using order-1 context.
    Uses Huffman code lengths as proxy (matching the actual coder).
    """
    if len(seq_codes) <= 1:
        return 0.0

    ctx1_freq: Dict[int, List[int]] = {}
    for i in range(1, len(seq_codes)):
        ctx1 = seq_codes[i - 1]
        if ctx1 not in ctx1_freq:
            ctx1_freq[ctx1] = [0] * n_distinct
        code = seq_codes[i]
        if code < n_distinct:
            ctx1_freq[ctx1][code] += 1

    total_bits = 0
    total_syms = 0
    for ctx1, freqs in ctx1_freq.items():
        cl = compute_huffman_code_lengths(freqs)
        for sym, cnt in enumerate(freqs):
            if cnt > 0:
                total_bits += cnt * cl[sym]
                total_syms += cnt

    return total_bits / total_syms if total_syms > 0 else 0.0


def conditional_entropy_order2(seq_codes: List[int], n_distinct: int) -> float:
    """
    H(X_t | X_{t-1}, X_{t-2}) — empirical conditional entropy using order-2 context.
    Uses Huffman code lengths as proxy (ALL positions, including fallback positions).
    """
    if len(seq_codes) <= 1:
        return 0.0

    ctx2_freq: Dict[Tuple[int, int], List[int]] = {}
    for i, code in enumerate(seq_codes):
        if i == 0:
            ctx2 = (0, 0)
        elif i == 1:
            ctx2 = (0, seq_codes[0])
        else:
            ctx2 = (seq_codes[i - 2], seq_codes[i - 1])
        if ctx2 not in ctx2_freq:
            ctx2_freq[ctx2] = [0] * n_distinct
        if code < n_distinct:
            ctx2_freq[ctx2][code] += 1

    total_bits = 0
    total_syms = 0
    for ctx2, freqs in ctx2_freq.items():
        cl = compute_huffman_code_lengths(freqs)
        for sym, cnt in enumerate(freqs):
            if cnt > 0:
                total_bits += cnt * cl[sym]
                total_syms += cnt

    return total_bits / total_syms if total_syms > 0 else 0.0


# ─── Corpus loading (identical to CUBR-0025) ──────────────────────────────────

def build_v2c(data: bytes) -> Tuple[Dict[int, int], List[int]]:
    """Build code map and inverse_dict matching codec.rs build_value_dict."""
    distinct = sorted(set(data))
    v2c = {v: c for c, v in enumerate(distinct)}
    inverse_dict = distinct
    return v2c, inverse_dict


def extract_seq_codes(data: bytes) -> Tuple[List[int], int, List[int]]:
    """Extract value-code sequence, n_distinct, and inverse_dict."""
    v2c, inverse_dict = build_v2c(data)
    seq_codes = [v2c[b] for b in data]
    return seq_codes, len(inverse_dict), inverse_dict


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


# ─── Clamp model (CUBR-0023/0025 lesson, reused verbatim) ────────────────────

def compute_clamped(
    entry: dict,
    order2_python_bytes: int,
    t4_python_bytes: int,
) -> int:
    """
    Produce the raw-store-clamped order-2 estimate.

    Raw-stored files: clamp to actual_t4_bytes (no value-scheme change can help).
    Cube-stored files: scale actual_t4_bytes by Python model's relative delta.
    """
    actual = entry.get("actual_t4_bytes")
    mode = entry.get("actual_t4_mode")

    if actual is None or mode is None:
        return order2_python_bytes

    if mode == "raw":
        return actual

    if t4_python_bytes == 0:
        return order2_python_bytes
    relative_delta = (order2_python_bytes - t4_python_bytes) / t4_python_bytes
    return round(actual * (1.0 + relative_delta))


# ─── Main probe ───────────────────────────────────────────────────────────────

def run_probe():
    # Get code SHA
    try:
        code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
            text=True
        ).strip()
    except Exception:
        code_sha = "unknown"

    with open(MANIFEST_PATH, "rb") as f:
        manifest_sha = hashlib.sha256(f.read()).hexdigest()

    corpus = load_corpus()

    # Verify manifest actuals match constants
    computed_t4_total = sum(e["actual_t4_bytes"] for e in corpus)
    computed_corpus_total = sum(e["size"] for e in corpus)
    assert computed_t4_total == T4_BASELINE_TOTAL, (
        f"T4 total mismatch: got {computed_t4_total}, expected {T4_BASELINE_TOTAL}"
    )
    assert computed_corpus_total == CORPUS_TOTAL, (
        f"Corpus total mismatch: got {computed_corpus_total}, expected {CORPUS_TOTAL}"
    )

    print("# CUBR-0026 — Order-2 Context Key Entropy-Depth Probe")
    print()
    print(f"**Code SHA (feature branch):** `{code_sha}`")
    print(f"**Manifest SHA-256:** `{manifest_sha}`")
    print(f"**T4 baseline aggregate:** {T4_BASELINE_AGGREGATE} "
          f"(total {T4_BASELINE_TOTAL} / {CORPUS_TOTAL} bytes, main @ 794148d)")
    print(f"**GO threshold:** aggregate ratio <= {GO_THRESHOLD_RATIO} "
          f"(>= -2% vs T4 baseline)")
    print()
    print("**Fallback chain (3 levels):**")
    print("  1. (prev2, prev) has >= MIN_CTX_COUNT observations → use order-2 table")
    print("  2. elif (prev) has >= MIN_CTX_COUNT observations → use order-1 fallback table")
    print("  3. else → use order-0 (global) fallback table")
    print()
    print("**Reversibility:** the decoder reconstructs (prev2_code, prev_code) from the")
    print("two previously decoded values, applying the same sentinel rules. The context")
    print("is a pure deterministic function of the decoded sequence — no side-channel.")
    print()

    # ── Pre-compute T4 Python baseline per file ────────────────────────────────
    t4_python_by_file: Dict[str, int] = {}
    for entry in corpus:
        seq_codes, n_distinct, _ = extract_seq_codes(entry["data"])
        # T4 twin uses fixed MIN_CTX_COUNT=16 (matches Rust codec.rs constant)
        t4_python_by_file[entry["name"]] = context_huffman_size_t4(seq_codes, n_distinct, 16)

    # ── AC-2: Conditional entropy comparison (once, independent of threshold) ──
    print("## AC-2a — Conditional Entropy: H(X|prev) vs H(X|prev2,prev)")
    print()
    print("| File | mode | n_dist | H(X|prev) [bits] | H(X|prev2,prev) [bits] | entropy drop |")
    print("|------|------|--------|-------------------|------------------------|--------------|")
    entropy_data = {}
    for entry in corpus:
        seq_codes, n_distinct, _ = extract_seq_codes(entry["data"])
        h1 = conditional_entropy_order1(seq_codes, n_distinct)
        h2 = conditional_entropy_order2(seq_codes, n_distinct)
        drop = h1 - h2
        entropy_data[entry["name"]] = {"h1": h1, "h2": h2, "drop": drop}
        sign = "-" if drop > 0 else "+"
        print(f"| {entry['name']} | {entry['actual_t4_mode']} | {n_distinct} "
              f"| {h1:.4f} | {h2:.4f} | {sign}{abs(drop):.4f} bits |")
    print()
    print("Negative entropy drop means order-2 offers MORE conditional entropy")
    print("(context dilution effect — too many sparse contexts).")
    print()

    # ── AC-1 + AC-2b: Per-threshold sweep ─────────────────────────────────────
    # results_by_threshold[threshold] = list of per-file dicts
    results_by_threshold: Dict[int, List[dict]] = {}

    print("## AC-1 — Order-2 Probe: Per-file × Per-threshold Results")
    print()
    print("Full wire cost = order-2 header (2 + n_ctx*(4+n_distinct)) + bitstream,")
    print("clamped to raw-store invariant.")
    print()

    best_overall_ratio = float("inf")
    best_overall_threshold = None

    for min_ctx in MIN_CTX_COUNT_VALUES:
        file_results = []

        print(f"### MIN_CTX_COUNT = {min_ctx}")
        print()
        print("| File | size | mode | n_dist | T4 actual | O2 python | O2 clamped "
              "| delta vs T4 | n_o2_tables | n_o1_fallback |")
        print("|------|------|------|--------|-----------|-----------|------------|"
              "-------------|-------------|---------------|")

        for entry in corpus:
            seq_codes, n_distinct, _ = extract_seq_codes(entry["data"])
            t4_py = t4_python_by_file[entry["name"]]

            (o2_total, o2_header, o2_bits,
             n_o2, n_o1_fb, n_o0_fb) = order2_huffman_size(
                seq_codes, n_distinct, min_ctx
            )

            clamped = compute_clamped(entry, o2_total, t4_py)
            actual_t4 = entry["actual_t4_bytes"]
            delta_pct = (clamped - actual_t4) / actual_t4 * 100 if actual_t4 else 0

            file_results.append({
                "name": entry["name"],
                "size": entry["size"],
                "mode": entry["actual_t4_mode"],
                "n_distinct": n_distinct,
                "actual_t4": actual_t4,
                "t4_python": t4_py,
                "o2_python": o2_total,
                "o2_header": o2_header,
                "o2_bitstream": o2_bits,
                "clamped": clamped,
                "delta_pct": delta_pct,
                "n_o2_tables": n_o2,
                "n_o1_fallback_tables": n_o1_fb,
                "n_o0_fallback": n_o0_fb,
            })

            sign = "+" if delta_pct > 0 else ""
            print(f"| {entry['name']} | {entry['size']} | {entry['actual_t4_mode']} "
                  f"| {n_distinct} | {actual_t4} | {o2_total} | {clamped} "
                  f"| {sign}{delta_pct:.2f}% | {n_o2} | {n_o1_fb} |")

        agg_clamped = sum(r["clamped"] for r in file_results)
        agg_t4 = T4_BASELINE_TOTAL
        agg_ratio = agg_clamped / CORPUS_TOTAL
        agg_delta_pct = (agg_clamped - agg_t4) / agg_t4 * 100
        sign = "+" if agg_delta_pct > 0 else ""
        print()
        print(f"**Aggregate:** {agg_clamped} / {CORPUS_TOTAL} bytes = ratio "
              f"**{agg_ratio:.6f}** ({sign}{agg_delta_pct:.4f}% vs T4 {T4_BASELINE_AGGREGATE})")
        print()

        # Header cost analysis
        cube_entries = [r for r in file_results if r["mode"] == "cube"]
        print("**Header cost breakdown (cube-stored files only — raw-store clamped):**")
        print()
        print("| File | T4 header (python) | O2 header (python) | header delta |")
        print("|------|--------------------|--------------------|--------------|")
        for r in cube_entries:
            # Estimate T4 header: build context count from T4 twin
            seq_codes, n_distinct, _ = extract_seq_codes(
                [f for f in corpus if f["name"] == r["name"]][0]["data"]
            )
            # Estimate T4 n_ctx from scratch
            ctx_freq: Dict[int, List[int]] = {}
            prev_ctx = 0
            for code in seq_codes:
                if prev_ctx not in ctx_freq:
                    ctx_freq[prev_ctx] = [0] * n_distinct
                if code < n_distinct:
                    ctx_freq[prev_ctx][code] += 1
                prev_ctx = code
            ctx_total = {ctx: sum(f) for ctx, f in ctx_freq.items()}
            t4_n_ctx = 1 + sum(
                1 for ctx, tot in ctx_total.items()
                if tot >= 16 and ctx != 0  # T4 fixed MIN_CTX_COUNT=16
            )
            t4_header = 2 + t4_n_ctx * (2 + r["n_distinct"])
            o2_header = r["o2_header"]
            hdr_delta = o2_header - t4_header
            print(f"| {r['name']} | {t4_header} | {o2_header} "
                  f"| +{hdr_delta} bytes |")
        print()

        if agg_ratio < best_overall_ratio:
            best_overall_ratio = agg_ratio
            best_overall_threshold = min_ctx

        results_by_threshold[min_ctx] = file_results

    # ── AC-2b: Context explosion summary ──────────────────────────────────────
    print("## AC-2b — Context Count: T4 (order-1) vs Order-2 Qualifying Contexts")
    print()
    print("Number of qualifying context tables (meeting MIN_CTX_COUNT) per file.")
    print("Order-2 potential contexts = up to n_distinct^2 pairs.")
    print()
    print("| File | n_dist | n_dist^2 | T4 n_ctx (fixed min=16) | " +
          " | ".join(f"O2 n_ctx (min={m})" for m in MIN_CTX_COUNT_VALUES) + " |")
    print("|------|--------|----------|-------------------------|" +
          "-----------|" * len(MIN_CTX_COUNT_VALUES))

    for entry in corpus:
        seq_codes, n_distinct, _ = extract_seq_codes(entry["data"])
        n_sq = n_distinct ** 2

        # T4 n_ctx at fixed min=16
        ctx_freq_tmp: Dict[int, int] = defaultdict(int)
        prev_ctx = 0
        for code in seq_codes:
            ctx_freq_tmp[prev_ctx] += 1
            prev_ctx = code
        t4_n_ctx = 1 + sum(1 for ctx, tot in ctx_freq_tmp.items() if tot >= 16 and ctx != 0)

        o2_n_ctx_list = []
        for min_ctx in MIN_CTX_COUNT_VALUES:
            r_list = results_by_threshold[min_ctx]
            r = next(r for r in r_list if r["name"] == entry["name"])
            o2_n_ctx_list.append(r["n_o2_tables"])

        print(f"| {entry['name']} | {n_distinct} | {n_sq} | {t4_n_ctx} | " +
              " | ".join(str(x) for x in o2_n_ctx_list) + " |")
    print()

    # ── AC-3: GO/NO-GO ────────────────────────────────────────────────────────
    print("## AC-3 — GO/NO-GO Verdict")
    print()
    print("### Summary: best aggregate ratio per threshold")
    print()
    print("| MIN_CTX_COUNT | aggregate bytes | ratio | delta vs T4 | GO? |")
    print("|---------------|-----------------|-------|-------------|-----|")

    best_ratio_overall = float("inf")
    best_threshold_overall = None

    for min_ctx in MIN_CTX_COUNT_VALUES:
        file_results = results_by_threshold[min_ctx]
        agg_clamped = sum(r["clamped"] for r in file_results)
        ratio = agg_clamped / CORPUS_TOTAL
        delta_pct = (agg_clamped - T4_BASELINE_TOTAL) / T4_BASELINE_TOTAL * 100
        go_this = ratio <= GO_THRESHOLD_RATIO
        sign = "+" if delta_pct > 0 else ""
        go_str = "YES" if go_this else "NO"
        print(f"| {min_ctx} | {agg_clamped} | {ratio:.6f} | {sign}{delta_pct:.4f}% | {go_str} |")
        if ratio < best_ratio_overall:
            best_ratio_overall = ratio
            best_threshold_overall = min_ctx

    print()
    best_file_results = results_by_threshold[best_threshold_overall]
    best_agg = sum(r["clamped"] for r in best_file_results)
    best_delta_pct = (best_agg - T4_BASELINE_TOTAL) / T4_BASELINE_TOTAL * 100

    if best_ratio_overall <= GO_THRESHOLD_RATIO:
        verdict = "GO"
        print(f"**Verdict: GO**")
        print()
        print(f"Best MIN_CTX_COUNT = {best_threshold_overall} achieves aggregate ratio "
              f"{best_ratio_overall:.6f} ({best_delta_pct:+.4f}% vs T4 {T4_BASELINE_AGGREGATE}). "
              f"Threshold {GO_THRESHOLD_RATIO} cleared.")
        print()
        print("Recommend: proceed to Rust implementation (AC-4). Stop here and report to operator.")
    else:
        verdict = "NO-GO"
        print(f"**Verdict: NO-GO**")
        print()
        print(f"Best MIN_CTX_COUNT = {best_threshold_overall} achieves aggregate ratio "
              f"{best_ratio_overall:.6f} ({best_delta_pct:+.4f}% vs T4 {T4_BASELINE_AGGREGATE}). "
              f"Does not clear GO threshold {GO_THRESHOLD_RATIO} (>= -2% improvement required).")
        print()
        print("Phase B (Rust implementation) is SKIPPED. AC-4 is n/a.")
        print()
        print("### Mechanism: why order-2 context does not improve vs T4")
        print()
        print("Two competing forces:")
        print()
        print("**A) Header explosion (dominant).**")
        print("  T4 header: 2 + n_ctx * (2 + n_distinct) bytes, where n_ctx ≤ n_distinct+1.")
        print("  Order-2 header: 2 + n_ctx2 * (4 + n_distinct) bytes.")
        print("  The order-2 key is 4 bytes vs T4's 2 bytes per entry, AND the number of")
        print("  qualifying (prev2, prev) pairs can vastly exceed T4's n_ctx (= n_distinct).")
        print("  Even at high MIN_CTX_COUNT the header surcharge is severe for files with")
        print("  moderate n_distinct (text/log_like: ~70 → up to ~4900 potential pairs).")
        print()
        print("**B) Entropy depth gain (insufficient).**")
        print("  H(X|prev2,prev) < H(X|prev) holds for text-like files — there IS a real")
        print("  entropy drop at the theoretical level. But the drop per symbol (bits) is")
        print("  too small to offset the header bytes added per qualifying context pair.")
        print("  For cube-stored files (only 3/7), the bitstream savings from the narrower")
        print("  distribution cannot overcome the header surcharge.")
        print()
        print("**C) Raw-store clamp (immutable for 4/7 files).**")
        print("  dense, binary_mixed, random_high, sparse_small are raw-stored by the real")
        print("  encoder — no value-scheme change can reduce their effective encoded size.")
        print("  These 4 files are clamped to actual_t4_bytes regardless of order-2 gains.")
        print("  The only files where order-2 could win are the 3 cube-stored files,")
        print("  and the header explosion cancels any bitstream gain even there.")

    print()
    print("---")
    print(f"*Generated by cubr_0026_order2_context_probe.py — code_sha {code_sha}*")

    return verdict, best_ratio_overall, best_threshold_overall, best_delta_pct, results_by_threshold, code_sha, manifest_sha


def emit_bench_json(verdict, best_ratio, best_threshold, best_delta_pct,
                    results_by_threshold, code_sha, manifest_sha):
    """Emit CUBR-0026-bench.json."""
    records = []
    for min_ctx, file_results in results_by_threshold.items():
        agg_clamped = sum(r["clamped"] for r in file_results)
        delta_pct = (agg_clamped - T4_BASELINE_TOTAL) / T4_BASELINE_TOTAL * 100
        ratio = agg_clamped / CORPUS_TOTAL
        per_file = [
            {
                "name": r["name"],
                "size": r["size"],
                "mode": r["mode"],
                "n_distinct": r["n_distinct"],
                "actual_t4_bytes": r["actual_t4"],
                "order2_clamped_bytes": r["clamped"],
                "order2_python_bytes": r["o2_python"],
                "order2_header_bytes": r["o2_header"],
                "order2_bitstream_bytes": r["o2_bitstream"],
                "delta_pct": round(r["delta_pct"], 4),
                "n_order2_tables": r["n_o2_tables"],
                "n_order1_fallback_tables": r["n_o1_fallback_tables"],
                "n_order0_fallback_positions": r["n_o0_fallback"],
            }
            for r in file_results
        ]
        records.append({
            "min_ctx_count": min_ctx,
            "aggregate_ratio": round(ratio, 6),
            "aggregate_clamped_bytes": agg_clamped,
            "delta_vs_t4_pct": round(delta_pct, 4),
            "per_file": per_file,
        })

    output = {
        "task": "CUBR-0026",
        "hypothesis": "R6_order2_context_key",
        "verdict": verdict,
        "best_min_ctx_count": best_threshold,
        "best_aggregate_ratio": round(best_ratio, 6),
        "best_delta_vs_t4_pct": round(best_delta_pct, 4),
        "go_threshold_ratio": GO_THRESHOLD_RATIO,
        "t4_baseline_aggregate": T4_BASELINE_AGGREGATE,
        "corpus_total_bytes": CORPUS_TOTAL,
        "t4_total_bytes": T4_BASELINE_TOTAL,
        "fallback_chain": "order2 → order1 → order0",
        "wire_header_formula": "2 + n_ctx * (4 + n_distinct) bytes [vs T4: 2 + n_ctx * (2 + n_distinct)]",
        "sweeps": records,
        "environment": {
            "code_sha": code_sha,
            "manifest_sha": manifest_sha,
            "t4_baseline_aggregate": T4_BASELINE_AGGREGATE,
            "t4_total_bytes": T4_BASELINE_TOTAL,
            "corpus_total_bytes": CORPUS_TOTAL,
            "min_ctx_count_values_tested": MIN_CTX_COUNT_VALUES,
        },
    }

    bench_path = os.path.join(os.path.dirname(__file__), "CUBR-0026-bench.json")
    with open(bench_path, "w") as f:
        json.dump(output, f, indent=2)
    return bench_path


def main():
    (verdict, best_ratio, best_threshold, best_delta_pct,
     results_by_threshold, code_sha, manifest_sha) = run_probe()

    bench_path = emit_bench_json(
        verdict, best_ratio, best_threshold, best_delta_pct,
        results_by_threshold, code_sha, manifest_sha
    )
    print()
    print(f"Bench JSON written to: {bench_path}")

    if verdict == "GO":
        print()
        print("Phase B (Rust implementation) is warranted. Stopping — report GO to operator.")
    else:
        print()
        print("Phase B (Rust implementation) SKIPPED — NO-GO.")
        print("AC-4 is n/a.")


if __name__ == "__main__":
    main()
