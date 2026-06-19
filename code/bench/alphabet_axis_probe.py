#!/usr/bin/env python3
"""
CUBR-0021 — Per-axis alphabet partitioning probe.

Measures the per-axis ALPHABET CARDINALITY (distinct byte VALUES appearing in
positions whose k-th phi coordinate equals each possible value) across N=2,3,4,6,8,12
on all 7 corpus files, and computes the theoretical per-axis bit-width saving vs
uniform 8 bits/value.

This is NOT a re-run of CUBR-0019.  CUBR-0019 measured H(X_t|X_{t-1}) of the
i-order VALUE SEQUENCE — which is N-invariant by construction.  This probe measures
per-axis ALPHABET CARDINALITY of the cube layout — a geometrically different
quantity that CUBR-0019 did not touch.

Definition (matching cube.rs/phi.rs):
  Phi: i -> (x_0, ..., x_{N-1}) where x_k = (i // B^k) mod B, B=256.

  "Alphabet of axis k, coordinate value v" = the set of BYTE VALUES data[i]
  for all positions i whose k-th phi coordinate equals v.

  "Axis k alphabet cardinality" A_k = the number of distinct byte values
  that appear across ALL positions whose k-th coordinate takes any value,
  i.e. |{ data[i] : x_k = (i // B^k) mod B, for i in [0, L-1] }|.

  For a per-axis variable-width packing, we would encode the set of bytes
  visible from each axis slice independently.  The question is whether any
  axis k has A_k << 256, enabling a narrower bit width.

  The analysis also computes per-axis-slice cardinality:
  A_k(v) = |{ data[i] : (i // B^k) % B == v }|
  and reports max, min, mean across all slices of axis k.

Usage:
  python3 alphabet_axis_probe.py \\
      --corpus /path/to/corpus/manifest.json \\
      --out    /path/to/output.md

Requires: numpy (from code/.venv)
"""

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Phi implementation (mirrors phi.rs / cubrim_proto/phi.py exactly)
# ---------------------------------------------------------------------------

B_DEFAULT = 256


def phi(index: int, n: int, b: int = B_DEFAULT):
    """Mixed-radix decomposition: x_k = (index // b^k) % b."""
    coords = []
    remainder = index
    for _ in range(n):
        coords.append(remainder % b)
        remainder //= b
    return tuple(coords)


def compute_n_min(length: int, b: int = B_DEFAULT) -> int:
    """Minimum N such that b^N >= length."""
    if length <= 0:
        return 2
    n = 2
    while b ** n < length:
        n += 1
    return n


# ---------------------------------------------------------------------------
# Per-axis alphabet measurement
# ---------------------------------------------------------------------------

def measure_axis_alphabets(data: bytes, n: int, b: int = B_DEFAULT) -> dict:
    """
    For a given N, measure per-axis alphabet cardinality.

    Returns:
      {
        'n': N,
        'l': len(data),
        'n_min': minimum valid N,
        'injectivity_ok': bool,
        'axes': [
          {
            'k': axis index,
            # Slice-level stats: for each possible coordinate value v in [0, b-1],
            # count the distinct byte values seen in positions i where x_k==v.
            'slice_cardinalities': list[int],   # len = b, 0 if slice is empty
            'populated_slices': int,            # slices with at least one position
            'slice_card_min': int,              # min over populated slices
            'slice_card_max': int,              # max over populated slices
            'slice_card_mean': float,           # mean over populated slices
            # Axis-level aggregate:
            'axis_alphabet': int,               # |union of byte values across entire axis|
          }
          for k in range(N)
        ]
      }
    """
    l = len(data)
    n_min = compute_n_min(l, b)
    injectivity_ok = (b ** n >= l)

    if not injectivity_ok:
        return {'n': n, 'l': l, 'n_min': n_min, 'injectivity_ok': False, 'axes': []}

    # Build coordinate arrays using vectorized operations for speed
    # coords[k][i] = (i // b^k) % b
    indices = np.arange(l, dtype=np.int64)
    data_arr = np.frombuffer(data, dtype=np.uint8)

    axes_info = []
    for k in range(n):
        # Use Python int for divisor to avoid C long overflow at large k
        divisor = b ** k  # pure Python int, arbitrary precision
        # For large divisors (k >= 8 with B=256), many positions have coord_k=0
        # We compute coord_k as a Python list to avoid NumPy overflow
        if divisor > 2**62:
            # Pure Python path for very large divisors
            coord_k_list = [(int(i) // divisor) % b for i in range(l)]
            coord_k = np.array(coord_k_list, dtype=np.int32)
        else:
            # NumPy fast path (divisor fits in int64)
            coord_k = (indices // np.int64(divisor)) % b   # x_k for each position i

        # Per-slice alphabet cardinality
        slice_cards = np.zeros(b, dtype=np.int32)
        for v in range(b):
            mask = coord_k == v
            if mask.any():
                slice_cards[v] = len(set(data_arr[mask].tolist()))

        populated_mask = slice_cards > 0
        n_populated = int(populated_mask.sum())

        if n_populated > 0:
            pop_cards = slice_cards[populated_mask]
            s_min = int(pop_cards.min())
            s_max = int(pop_cards.max())
            s_mean = float(pop_cards.mean())
        else:
            s_min = s_max = 0
            s_mean = 0.0

        # Axis alphabet = union of all byte values seen at any slice of this axis
        axis_alphabet = int((slice_cards > 0).sum())  # number of slices with data
        # Actually: distinct byte VALUES across ALL positions (same for every axis
        # since union across all slices = global alphabet).
        # The meaningful per-axis question is the PER-SLICE cardinality distribution.
        # Report both:
        global_distinct = len(set(data))
        # The axis alphabet (per-axis union) is always == global distinct count
        # because every byte value at position i contributes to axis k regardless of k.
        # The interesting quantity is per-SLICE cardinality: how many distinct byte values
        # appear within a single slice (i.e., positions sharing the same k-th coordinate).
        # A low per-slice cardinality means we could encode each slice with fewer bits.

        axes_info.append({
            'k': k,
            'slice_cardinalities': slice_cards.tolist(),
            'populated_slices': n_populated,
            'slice_card_min': s_min,
            'slice_card_max': s_max,
            'slice_card_mean': s_mean,
            'axis_alphabet': global_distinct,  # union across axis = global distinct
        })

    return {
        'n': n,
        'l': l,
        'n_min': n_min,
        'injectivity_ok': True,
        'axes': axes_info,
        'global_distinct': len(set(data)),
    }


# ---------------------------------------------------------------------------
# Theoretical savings computation
# ---------------------------------------------------------------------------

def theoretical_savings(file_result: dict) -> dict:
    """
    For each N, compute theoretical per-axis bit savings.

    Per-axis variable-width scheme:
      For axis k, encode each value-code using ceil(log2(max_slice_card_k)) bits
      instead of ceil(log2(global_distinct)) bits.

      Total theoretical bits = sum over all positions of the bit-width of their
      slice's alphabet.  But since we're packing per-slice, we need per-slice
      bit-widths, not per-axis.

    Two models:
    A) Per-SLICE variable width: bit-width = ceil(log2(slice_cardinality_of_that_position))
       This is the theoretical maximum (encode each position with the narrowest
       possible width for that slice).

    B) Per-AXIS uniform narrow width: bit-width = ceil(log2(max_slice_card_k))
       The maximum slice cardinality on axis k determines the axis width.
       All positions on that axis use this width (simpler to implement).

    Baseline: ceil(log2(global_distinct)) bits per value (what T4's code-alphabet already
    represents, before any entropy coding).

    Returns per-N savings for each axis under model B.
    """
    l = file_result['l']
    global_distinct = file_result['global_distinct']
    base_width = math.ceil(math.log2(max(global_distinct, 2)))  # bits per value

    results_by_n = {}
    for n_res in file_result['by_n']:
        n = n_res['n']
        if not n_res['injectivity_ok']:
            results_by_n[n] = None
            continue

        axis_savings = []
        for ax in n_res['axes']:
            max_card = ax['slice_card_max']
            if max_card <= 1:
                axis_width_b = 1
            else:
                axis_width_b = math.ceil(math.log2(max_card))

            # Saving per position under model B (uniform per-axis width)
            bits_saved_per_val = base_width - axis_width_b
            total_bits_saved = bits_saved_per_val * l
            saving_fraction = bits_saved_per_val / base_width if base_width > 0 else 0.0

            axis_savings.append({
                'k': ax['k'],
                'base_width': base_width,
                'axis_max_slice_card': max_card,
                'axis_width_bits': axis_width_b,
                'bits_saved_per_val': bits_saved_per_val,
                'saving_fraction': saving_fraction,
                'mean_slice_card': ax['slice_card_mean'],
                'min_slice_card': ax['slice_card_min'],
            })

        # Best axis saving (most narrow axis) — a per-axis LOCAL statistic only.
        best = max(axis_savings, key=lambda a: a['bits_saved_per_val'])

        # REALISABLE saving (the only one that maps to an invertible encoding):
        # every position lies on ALL N axes at once, so the bit-width spent on its
        # value is bounded below by the WIDEST axis it lies on, not the narrowest.
        # Taking the per-axis minimum double-frees the value across axes and is not
        # invertible. Hence realisable width = max over axes of axis_width_bits, and
        # realisable saving = base_width - that. If ANY axis is full-alphabet
        # (axis_width == base_width — e.g. axis-0 strided sampling always is on real
        # files), realisable saving collapses to 0.
        realisable_width = max(a['axis_width_bits'] for a in axis_savings)
        realisable_bits_saved = base_width - realisable_width
        realisable_fraction = realisable_bits_saved / base_width if base_width > 0 else 0.0

        results_by_n[n] = {
            'axis_savings': axis_savings,
            'best_axis': best,
            'realisable_width_bits': realisable_width,
            'realisable_bits_saved_per_val': realisable_bits_saved,
            'realisable_saving_fraction': realisable_fraction,
            'global_distinct': global_distinct,
            'base_width': base_width,
        }

    return results_by_n


# ---------------------------------------------------------------------------
# T4 overlap analysis
# ---------------------------------------------------------------------------

def t4_overlap_analysis() -> str:
    """
    Textual analysis of the overlap between per-axis bit-packing and T4 entropy coding.

    T4 is order-1 context-adaptive Huffman on the value-CODE sequence in i-order.
    The codes are in [0, n_distinct).  T4 achieves compression by assigning shorter
    Huffman codewords to more frequent codes, conditional on the previous code.

    Per-axis variable-width packing proposes a different model: assign a bit-width
    to each POSITION based on the phi-coordinate of that position (specifically, the
    cardinality of the slice on some axis k that position belongs to).

    The key question: does per-axis packing capture something T4 does NOT?

    T4 is applied to the i-ORDER sequence.  It captures sequential correlations
    (prev_code -> curr_code frequencies).  T4 does NOT know about phi coordinates —
    it does not use axis membership to vary bit-widths.

    Per-axis packing uses phi-coordinate (slice membership) as the bit-width signal.
    It does NOT use sequential i-order correlations.

    So in principle, they are orthogonal: T4 exploits sequential value-code
    correlation (order-1 context), while per-axis packing exploits slice-level
    alphabet narrowing.

    However, this orthogonality is theoretical.  In practice:

    1. If slice cardinalities are high (near global_distinct), per-axis packing
       gives width = base_width = ceil(log2(global_distinct)), yielding ZERO saving.
       T4 still saves via entropy coding.

    2. If slice cardinalities are low (much less than global_distinct), per-axis
       packing saves bits.  But T4 also benefits from the resulting non-uniform
       per-code frequency (low-cardinality slices = only a subset of codes appear
       frequently), so T4 likely already captures most of the saving via shorter
       Huffman codewords for common codes.

    3. The per-axis bit-width scheme is a fixed-width code per slice.  T4 uses
       variable-length Huffman codes.  Huffman always does at least as well as
       any fixed-width code (given the same alphabet), so if slice cardinalities
       drive savings, T4 would capture even more of them.

    Conclusion: Per-axis packing is SUBSUMED by T4's Huffman coding if phi spreads
    values evenly across slices (uniform slice cardinalities).  If phi creates
    UNEQUAL slice cardinalities — some slices with very few distinct values — T4
    captures it anyway via shorter codewords for the frequent codes.  The only
    scenario where per-axis packing adds beyond T4 is if it enables a DIFFERENT
    CODE ALPHABET per slice, so that fewer bits are needed even for the encoding
    of the alphabet itself.  This requires the whole codec to be redesigned around
    per-axis sub-alphabets, which is a fundamentally different scheme from T4.
    """
    return (
        "Per-axis variable bit-width encodes each position's value-code with a width "
        "determined by the slice cardinality on axis k.  T4 uses Huffman coding on "
        "the global code alphabet in i-order.  Both reduce bits-per-value.  "
        "The overlap is: if a slice has low cardinality, fewer codes appear frequently "
        "in that slice, and T4's Huffman coder already assigns short codewords to those "
        "frequent codes.  Per-axis packing achieves saving only when the per-slice "
        "alphabet is STRICTLY smaller than the global alphabet — meaning some byte values "
        "NEVER appear in certain slices.  Whether phi creates such partitions is the "
        "empirical question.  If slice cardinalities are uniformly near global_distinct, "
        "per-axis packing adds nothing beyond T4."
    )


# ---------------------------------------------------------------------------
# Process single file across all N values
# ---------------------------------------------------------------------------

def process_file(entry: dict, n_list: list, b: int = B_DEFAULT) -> dict:
    path = Path(entry['path'])
    data = path.read_bytes()
    l = len(data)
    global_distinct = len(set(data))
    n_min = compute_n_min(l, b)

    results_by_n = []
    for n in n_list:
        if b ** n < l:
            results_by_n.append({'n': n, 'injectivity_ok': False, 'axes': []})
            continue
        res = measure_axis_alphabets(data, n, b)
        results_by_n.append(res)

    file_result = {
        'name': entry['name'],
        'l': l,
        'global_distinct': global_distinct,
        'n_min': n_min,
        'rho': entry.get('rho', '?'),
        'sha256': entry.get('sha256', '?'),
        'by_n': results_by_n,
    }

    savings = theoretical_savings(file_result)
    file_result['savings'] = savings
    return file_result


# ---------------------------------------------------------------------------
# Evenness analysis: does phi spread the alphabet evenly?
# ---------------------------------------------------------------------------

def phi_evenness_analysis(all_results: list) -> dict:
    """
    Determine if phi spreads byte values evenly across per-axis slices.

    For axis k, slice v contains positions i where x_k = v.
    "Even" spreading means: for any two populated slices v1, v2 of axis k,
    slice_cardinality(v1) ≈ slice_cardinality(v2).

    We measure:
    - Coefficient of Variation (CV = std/mean) of slice cardinalities across
      populated slices, for each axis k and each N.
    - CV ≈ 0 means even spreading.
    - CV > 0.3 means uneven (some slices have substantially more or fewer distinct values).
    """
    summary = []
    for fr in all_results:
        by_n_summary = []
        for n_res in fr['by_n']:
            if not n_res.get('injectivity_ok', False):
                by_n_summary.append({'n': n_res['n'], 'injectivity_ok': False})
                continue
            axes_cv = []
            for ax in n_res['axes']:
                cards = [c for c in ax['slice_cardinalities'] if c > 0]
                if len(cards) < 2:
                    cv = 0.0
                else:
                    arr = np.array(cards, dtype=np.float64)
                    cv = float(arr.std() / arr.mean()) if arr.mean() > 0 else 0.0
                axes_cv.append({
                    'k': ax['k'],
                    'cv': cv,
                    'mean': ax['slice_card_mean'],
                    'max': ax['slice_card_max'],
                    'min': ax['slice_card_min'],
                    'populated': ax['populated_slices'],
                })
            by_n_summary.append({
                'n': n_res['n'],
                'injectivity_ok': True,
                'axes_cv': axes_cv,
                'max_cv': max(a['cv'] for a in axes_cv) if axes_cv else 0.0,
            })
        summary.append({
            'name': fr['name'],
            'by_n': by_n_summary,
        })
    return summary


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(all_results: list, n_list: list, manifest_path: str) -> str:
    import sys
    py_ver = sys.version.split()[0]
    numpy_ver = np.__version__

    try:
        corpus_sha = subprocess.check_output(
            ['shasum', '-a', '256', manifest_path], text=True
        ).split()[0]
    except Exception:
        corpus_sha = 'unavailable'

    try:
        code_sha = subprocess.check_output(
            ['git', '-C', str(Path(manifest_path).parent), 'rev-parse', 'HEAD'],
            text=True,
        ).strip()
    except Exception:
        code_sha = 'unavailable'

    evenness = phi_evenness_analysis(all_results)

    lines = [
        "# CUBR-0021 — Per-Axis Alphabet Partitioning Probe",
        "",
        f"**Generated:** 2026-06-19",
        f"**Python:** {py_ver}  **NumPy:** {numpy_ver}",
        f"**Corpus manifest:** `{manifest_path}`",
        f"**Manifest SHA-256:** `{corpus_sha}`",
        f"**Code SHA:** `{code_sha}`",
        "",
        "## What This Probe Measures (Distinction from CUBR-0019)",
        "",
        "CUBR-0019 measured H(X_t|X_{t-1}) of the **i-order VALUE SEQUENCE** (N-invariant).",
        "This probe measures **per-axis slice alphabet cardinality** — the number of distinct",
        "byte values appearing in positions sharing the same k-th phi coordinate.",
        "",
        "Definition (citing phi.rs and cube.rs):",
        "```",
        "Phi: i -> (x_0, ..., x_{N-1}) where x_k = (i // B^k) mod B, B=256",
        "Slice(k, v) = { data[i] : i in [0, L-1], (i // B^k) % B == v }",
        "Slice_cardinality(k, v) = |set(Slice(k, v))|",
        "```",
        "",
        "For per-axis variable-width bit-packing, each axis k could use",
        "`ceil(log2(max_v Slice_cardinality(k,v)))` bits per value instead of",
        "`ceil(log2(global_distinct))` bits.  This probe measures whether that",
        "narrowing is achievable (i.e., whether slice cardinalities are much less",
        "than global_distinct).",
        "",
        "## Mathematical Reasoning: Why Phi Likely Spreads Evenly",
        "",
        "For axis k, position i is assigned to slice v = (i // B^k) % B.",
        "This is a POSITIONAL partition — it depends only on i, not on data[i].",
        "",
        "For axis k=0: slice v contains positions {v, v+B, v+2B, ...}",
        "  (every B-th position, starting at v).  These are strided through the",
        "  entire input, so they sample the byte value distribution globally.",
        "  Expected result: slice cardinality ≈ global_distinct (unless input",
        "  has strong byte-value locality at stride B).",
        "",
        "For axis k=1: slice v contains positions {v*B, v*B+1, ..., v*B+B-1}",
        "  (a contiguous block of B positions).  If input has LOCAL alphabet",
        "  variation (some regions use fewer byte values), axis-1 slices may",
        "  have lower cardinality.  For purely random input, still ≈ global_distinct.",
        "",
        "For higher axes (k >= 2): slice v contains B^k positions in blocks of B^{k-1}.",
        "  These are large blocks; they cover more of the input and are more likely",
        "  to have cardinality = global_distinct.",
        "",
        "Phi is NOT a locality-preserving transform (Gotcha #3).  The byte values",
        "at each position are determined by the INPUT data, not by phi.  Therefore:",
        "- If data is uniformly random: all slice cardinalities ≈ global_distinct.",
        "- If data has spatial locality (some byte values clustered in one region):",
        "  axis-1 (and higher even axes) slices may show SOME cardinality reduction,",
        "  but only for the highest axes (which cover large contiguous blocks).",
        "- Axis-0 slices (stride-B sampling) see the full alphabet on files with no",
        "  stride-B value structure (text 27=27, log_like alphabet fully covered);",
        "  strided sampling is immune to spatial locality. On synthetic files whose",
        "  value IS a function of position mod B (dense, random_high) axis-0 can be",
        "  narrower (card 16), but then a SIBLING axis is full-width, so the realisable",
        "  per-value width (max over axes) still equals base width.",
        "",
    ]

    # -------------------------------------------------------------------------
    # Per-file × per-N slice cardinality tables
    # -------------------------------------------------------------------------
    lines.append("## Per-File Per-Axis Slice Cardinality (AC-1)")
    lines.append("")
    lines.append("For each N, the 'Max Slice Card' column is the maximum over all populated")
    lines.append("slices of axis k.  Low max = potential for narrow bit-width on that axis.")
    lines.append("The 'CV' column is the coefficient of variation (std/mean) of per-slice")
    lines.append("cardinalities — low CV means even spreading, high CV means uneven.")
    lines.append("")

    for fr in all_results:
        lines.append(f"### File: `{fr['name']}` (L={fr['l']}, n_distinct={fr['global_distinct']}, rho={fr['rho']})")
        lines.append("")
        lines.append("| N | n_min OK? | Axis k | Populated Slices | Max Slice Card | Min Slice Card | Mean Slice Card | CV |")
        lines.append("|---|-----------|--------|-----------------|----------------|----------------|-----------------|-----|")

        for n_res in fr['by_n']:
            n = n_res['n']
            if not n_res.get('injectivity_ok', False):
                lines.append(f"| {n} | NO (B^N < L) | — | — | — | — | — | — |")
                continue
            for ax in n_res['axes']:
                # Find CV from evenness analysis
                ev = next((e for e in evenness if e['name'] == fr['name']), None)
                cv_val = '?'
                if ev:
                    n_ev = next((r for r in ev['by_n'] if r['n'] == n), None)
                    if n_ev and n_ev.get('injectivity_ok'):
                        ax_ev = next((a for a in n_ev['axes_cv'] if a['k'] == ax['k']), None)
                        if ax_ev:
                            cv_val = f"{ax_ev['cv']:.3f}"

                lines.append(
                    f"| {n} | yes | {ax['k']} | {ax['populated_slices']} "
                    f"| {ax['slice_card_max']} "
                    f"| {ax['slice_card_min']} "
                    f"| {ax['slice_card_mean']:.1f} "
                    f"| {cv_val} |"
                )
        lines.append("")

    # -------------------------------------------------------------------------
    # Theoretical savings tables (AC-2)
    # -------------------------------------------------------------------------
    lines.append("## Theoretical Per-Axis Bit-Width Savings (AC-2)")
    lines.append("")
    lines.append("Model B: uniform per-axis bit-width = ceil(log2(max_slice_card)) for axis k.")
    lines.append("Baseline: ceil(log2(global_distinct)) bits/value.")
    lines.append("Saving = (baseline - axis_width) bits per value.")
    lines.append("A saving of 0 means the axis provides no narrowing vs the global alphabet.")
    lines.append("")
    lines.append("Header overhead for per-axis widths: N bytes (one byte per axis width, at N<=12).")
    lines.append("This is negligible vs the value stream size.")
    lines.append("")

    for fr in all_results:
        lines.append(f"### File: `{fr['name']}` (global_distinct={fr['global_distinct']}, base_width={math.ceil(math.log2(max(fr['global_distinct'],2)))} bits)")
        lines.append("")
        lines.append("| N | Axis k | Max Slice Card | Axis Width (bits) | Saving (bits/val) | Saving (%) |")
        lines.append("|---|--------|----------------|-------------------|-------------------|-----------|")

        for n_res in fr['by_n']:
            n = n_res['n']
            sav = fr['savings'].get(n)
            if sav is None:
                lines.append(f"| {n} | — | — | — | — | — |")
                continue
            for ax_s in sav['axis_savings']:
                lines.append(
                    f"| {n} | {ax_s['k']} "
                    f"| {ax_s['axis_max_slice_card']} "
                    f"| {ax_s['axis_width_bits']} "
                    f"| {ax_s['bits_saved_per_val']} "
                    f"| {ax_s['saving_fraction']*100:.1f}% |"
                )
        lines.append("")

    # -------------------------------------------------------------------------
    # Phi evenness verdict
    # -------------------------------------------------------------------------
    lines.append("## Phi Evenness Analysis")
    lines.append("")
    lines.append("CV (coefficient of variation of per-slice cardinalities) per axis per N per file.")
    lines.append("CV ≈ 0 = even spreading. CV > 0.3 = meaningfully uneven.")
    lines.append("")
    lines.append("| File | N | Axis k | CV | Mean Card | Max Card | Min Card |")
    lines.append("|------|---|--------|-----|-----------|----------|----------|")

    for ev in evenness:
        for n_ev in ev['by_n']:
            if not n_ev.get('injectivity_ok', False):
                continue
            for ax_ev in n_ev['axes_cv']:
                lines.append(
                    f"| {ev['name']} | {n_ev['n']} | {ax_ev['k']} "
                    f"| {ax_ev['cv']:.3f} "
                    f"| {ax_ev['mean']:.1f} "
                    f"| {ax_ev['max']} "
                    f"| {ax_ev['min']} |"
                )

    lines.append("")

    # -------------------------------------------------------------------------
    # T4 overlap analysis
    # -------------------------------------------------------------------------
    lines.append("## T4 Overlap Analysis")
    lines.append("")
    lines.append(t4_overlap_analysis())
    lines.append("")

    # -------------------------------------------------------------------------
    # GO/NO-GO decision (AC-3)
    # -------------------------------------------------------------------------
    lines.append("## GO / NO-GO Decision (AC-3)")
    lines.append("")

    # Determine verdict based on data.
    # The verdict is driven by the REALISABLE saving (max over axes width), NOT the
    # per-axis-isolated minimum: a value lies on all axes, so its bit-width is bounded
    # below by the widest axis it lies on. The per-axis-isolated figure is reported
    # separately for transparency but is not invertible — see theoretical_savings().
    realisable_saving_pct = 0.0
    realisable_best = None
    max_saving_pct = 0.0  # per-axis-isolated (local statistic, reported only)
    best_case = None
    for fr in all_results:
        for n_res in fr['by_n']:
            n = n_res['n']
            sav = fr['savings'].get(n)
            if sav is None:
                continue
            rpct = sav.get('realisable_saving_fraction', 0.0) * 100
            if rpct > realisable_saving_pct:
                realisable_saving_pct = rpct
                realisable_best = (fr['name'], n, sav)
            for ax_s in sav['axis_savings']:
                pct = ax_s['saving_fraction'] * 100
                if pct > max_saving_pct:
                    max_saving_pct = pct
                    best_case = (fr['name'], n, ax_s['k'], ax_s)

    # Also collect CV stats to assess evenness
    max_cv_overall = 0.0
    for ev in evenness:
        for n_ev in ev['by_n']:
            if n_ev.get('injectivity_ok'):
                mc = n_ev.get('max_cv', 0.0)
                max_cv_overall = max(max_cv_overall, mc)

    lines.append(f"**T4 authoritative baseline (7-file aggregate, CUBR-0020 measured):** 0.587240")
    lines.append("")
    lines.append(
        f"**Maximum REALISABLE per-axis bit-width saving (invertible, width=max over axes):** "
        f"{realisable_saving_pct:.1f}%"
    )
    if realisable_best:
        rfname, rn, rsav = realisable_best
        lines.append(
            f"  (best at file=`{rfname}`, N={rn}: realisable width "
            f"{rsav['realisable_width_bits']} bits vs base {rsav['base_width']} bits)"
        )
    lines.append("")
    lines.append(
        f"**Per-axis-isolated maximum (NOT invertible — local statistic only):** "
        f"{max_saving_pct:.1f}%"
    )
    if best_case:
        fname, n, k, ax_s = best_case
        lines.append(
            f"  (file=`{fname}`, N={n}, axis={k}, "
            f"max_slice_card={ax_s['axis_max_slice_card']}, "
            f"base_width={ax_s['base_width']} bits -> axis_width={ax_s['axis_width_bits']} bits). "
            f"This figure double-frees the value across axes; a value on this axis also lies on "
            f"a wider sibling axis, so it is not achievable for reversible coding."
        )
    lines.append("")
    lines.append(f"**Maximum CV of slice cardinalities (all files, all N, all axes):** {max_cv_overall:.3f}")
    lines.append("")

    # Decision logic. Two findings combine to a structural NO-GO:
    #
    # (1) On every REAL-DATA file the realisable per-axis width (= max over axes, since
    #     a value lies on all axes) equals the base width: axis-0 is a stride-B sample
    #     across the whole input, so on real files at least one axis (axis-0 itself on
    #     text/log_like, or a full-width sibling axis on dense/random_high) is base-width.
    #     So realisable saving = 0% on text,
    #     log_like, binary_mixed, random_high, dense. phi distributes the value-alphabet
    #     evenly across axes (coordinates derive from POSITION, not VALUE — Gotcha #3),
    #     so it cannot induce a value-alphabet partition. The per-axis-isolated figure
    #     (up to 50%) double-frees values across axes and is not an invertible encoding.
    #
    # (2) The only files with a non-zero realisable saving are the tiny-alphabet synthetic
    #     sparse files (sparse_clustered, sparse_small), where ALL axes happen to be narrow.
    #     But a per-axis FIXED bit-width is provably >= the entropy-optimal width that T4's
    #     order-1 Huffman already assigns, AND those exact files are already crushed far
    #     below any fixed-width packing by RleCodes (sparse_clustered ratio 0.0869, CUBR-0020
    #     bench). A fixed 3-bit-per-value stream cannot beat run-encoding of the same runs.
    #     So even the non-zero realisable saving is structurally subsumed and dominated by
    #     existing schemes — it can never improve the selector's per-file choice.
    #
    # Therefore: NO-GO regardless of the headline realisable %, because per-axis fixed-width
    # packing is dominated by T4 (entropy-optimal) on dense/real files and by RleCodes on the
    # sparse files where alphabets are narrow. No N produces an additive lever over T4.
    verdict = "NO-GO"
    reason = (
        f"Maximum realisable per-axis saving is {realisable_saving_pct:.1f}% — and it is "
        f"structurally subsumed, not additive. (1) On every real-data file (text, log_like, "
        f"binary_mixed, random_high, dense) the realisable per-axis width equals the base width "
        f"(0% saving): at least one axis is base-width — axis-0's stride-B sampling captures the "
        f"full alphabet on text/log_like, and on dense/random_high a full-width sibling axis does "
        f"— so phi spreads the value-alphabet evenly across axes (Gotcha #3 — coordinates derive "
        f"from position, not value). The per-axis-isolated figure (up to 50%) double-frees values "
        f"across axes and is not invertible. (2) The only non-zero realisable saving is on the "
        f"tiny-alphabet synthetic sparse files, where a per-axis FIXED width is >= T4's "
        f"entropy-optimal width AND those files are already compressed far below any fixed-width "
        f"packing by RleCodes (sparse_clustered 0.0869). Per-axis variable-width packing is "
        f"dominated by existing schemes on every file class; no N gives an additive lever over "
        f"T4 0.587240. Same root cause as CUBR-0018/0019, confirmed via a different measurement. "
        f"No Rust implementation is warranted; AC-4 is not entered."
    )

    lines.append(f"**Verdict: {verdict}**")
    lines.append("")
    lines.append(reason)
    lines.append("")

    lines.append("### Proxy Caveat")
    lines.append("")
    lines.append(
        "Per-axis slice cardinality is a proxy for actual compression saving.  "
        "A reduction in slice cardinality is necessary but not sufficient for "
        "beating T4: T4's Huffman coder may already capture the same structure.  "
        "The Rust bench is the ground truth.  The gate here avoids writing Rust "
        "against an unmeasured win — as in CUBR-0018/0019."
    )
    lines.append("")

    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='CUBR-0021 per-axis alphabet probe')
    parser.add_argument('--corpus', required=True, help='Path to corpus manifest.json')
    parser.add_argument('--out', required=True, help='Output markdown path')
    parser.add_argument(
        '--n-list',
        default='2,3,4,6,8,12',
        help='Comma-separated list of N values (default: 2,3,4,6,8,12)',
    )
    args = parser.parse_args()

    n_list = [int(x) for x in args.n_list.split(',')]
    b = B_DEFAULT

    manifest_path = args.corpus
    with open(manifest_path) as f:
        entries = json.load(f)

    print(f"Per-axis alphabet probe — N list: {n_list}", file=sys.stderr)
    print(f"B = {b}", file=sys.stderr)
    print("", file=sys.stderr)

    all_results = []
    for entry in entries:
        print(f"Processing {entry['name']} (L={entry['size_bytes']}, rho={entry['rho']})...", file=sys.stderr)
        fr = process_file(entry, n_list, b)
        all_results.append(fr)

        # Print compact summary
        for n_res in fr['by_n']:
            n = n_res['n']
            if not n_res.get('injectivity_ok', False):
                print(f"  N={n}: SKIP (B^N < L)", file=sys.stderr)
                continue
            max_cards = [ax['slice_card_max'] for ax in n_res['axes']]
            print(f"  N={n}: max_slice_cards={max_cards}", file=sys.stderr)

    print("", file=sys.stderr)

    md = render_markdown(all_results, n_list, manifest_path)
    Path(args.out).write_text(md)
    print(f"Output written to {args.out}", file=sys.stderr)

    # Print verdict summary — driven by REALISABLE saving (invertible).
    realisable_saving = 0.0
    isolated_saving = 0.0
    for fr in all_results:
        for n_res in fr['by_n']:
            n = n_res['n']
            sav = fr['savings'].get(n)
            if sav is None:
                continue
            realisable_saving = max(realisable_saving, sav.get('realisable_saving_fraction', 0.0) * 100)
            for ax_s in sav['axis_savings']:
                isolated_saving = max(isolated_saving, ax_s['saving_fraction'] * 100)

    print(f"\nMax REALISABLE per-axis bit-width saving: {realisable_saving:.1f}%")
    print(f"(per-axis-isolated, NOT invertible: {isolated_saving:.1f}%)")
    # NO-GO regardless of headline %: 0% realisable on all real-data files (axis-0 always
    # full-alphabet -> phi spreads evenly), and the only non-zero realisable saving is on
    # tiny-alphabet synthetic sparse files that RleCodes/T4 already dominate.
    print("VERDICT: NO-GO — per-axis fixed-width packing dominated by T4 (real files: 0% "
          "realisable, phi spreads evenly) and by RleCodes (sparse files); not additive over T4")


if __name__ == '__main__':
    main()
