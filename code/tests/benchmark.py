"""
Benchmark script — AC-2, AC-3, AC-4.

Runs:
  AC-2: ~1 MB random bytes → raw-store ratio measurement
  AC-3: gap=1 fraction + mean run-length on locality corpus
  AC-4: per-file + aggregate compression ratio on locality corpus

Writes results to:
  documentation/ephemeral/research/CUBR-0004-first-measurements.md

Usage:
  python tests/benchmark.py
  make benchmark
"""
import os
import sys
import hashlib
import struct
from pathlib import Path

import numpy as np

# Ensure package is importable when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cubrim_proto.codec import encode, decode, HEADER_OVERHEAD_BOUND
from cubrim_proto.header import parse_header
from cubrim_proto.distance_map import encode_axis_gaps
from cubrim_proto.cube import build_cube


# ---------------------------------------------------------------------------
# Corpus generators (same seeds as conftest.py)
# ---------------------------------------------------------------------------

def make_text_64kb() -> bytes:
    fragment = (
        b"the quick brown fox jumps over the lazy dog "
        b"pack my box with five dozen liquor jugs "
        b"how vexingly quick daft zebras jump "
    )
    size = 64 * 1024
    repetitions = (size // len(fragment)) + 1
    return (fragment * repetitions)[:size]


def make_random_64kb() -> bytes:
    rng = np.random.default_rng(777)
    return rng.integers(0, 256, size=64 * 1024, dtype=np.uint8).tobytes()


def make_log_16kb() -> bytes:
    templates = [
        b'{"ts":"2026-06-17T12:00:00Z","level":"INFO","msg":"request processed","latency_ms":42}\n',
        b'{"ts":"2026-06-17T12:00:01Z","level":"DEBUG","msg":"cache hit","key":"user:1234"}\n',
        b'{"ts":"2026-06-17T12:00:02Z","level":"WARN","msg":"slow query","duration_ms":512}\n',
        b'{"ts":"2026-06-17T12:00:03Z","level":"ERROR","msg":"connection timeout","host":"db-1"}\n',
    ]
    size = 16 * 1024
    buf = bytearray()
    rng = np.random.default_rng(99)
    while len(buf) < size:
        line = templates[rng.integers(len(templates))]
        buf.extend(line)
    return bytes(buf[:size])


def make_random_1mb() -> bytes:
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=1_048_576, dtype=np.uint8).tobytes()


# ---------------------------------------------------------------------------
# Gap=1 statistics for locality measurement (AC-3)
# ---------------------------------------------------------------------------

def measure_gap1_stats(data: bytes):
    """
    Build cube from data, collect all gap sequences per axis,
    compute fraction of gap=1 and mean run-length of consecutive gap=1.
    Returns: (fraction_gap1, mean_run_length_gap1, total_gaps)
    """
    cube_data = build_cube(data)
    populated = cube_data["populated"]  # list of (coord_x, coord_y) tuples
    b_k = cube_data["b_k"]             # [b_0, b_1] edge lengths

    if not populated:
        return 0.0, 0.0, 0

    N = len(b_k)
    all_gaps = []

    for axis in range(N):
        # Collect coords along this axis sorted; populated = list of (coords_tuple, value)
        # p[0] = coords_tuple, p[0][axis] = coordinate on this axis
        coords_on_axis = sorted(set(p[0][axis] for p in populated))
        if len(coords_on_axis) < 1:
            continue
        gaps = encode_axis_gaps(coords_on_axis, b_k[axis])
        all_gaps.extend(gaps)

    if not all_gaps:
        return 0.0, 0.0, 0

    total = len(all_gaps)
    gap1_count = sum(1 for g in all_gaps if g == 1)
    fraction = gap1_count / total

    # Mean run-length of consecutive gap=1
    runs = []
    run_len = 0
    for g in all_gaps:
        if g == 1:
            run_len += 1
        else:
            if run_len > 0:
                runs.append(run_len)
                run_len = 0
    if run_len > 0:
        runs.append(run_len)

    mean_run = (sum(runs) / len(runs)) if runs else 0.0
    return fraction, mean_run, total


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def run_benchmark():
    print("=" * 60)
    print("Cubrim v1 Python Prototype — First Measurements")
    print("=" * 60)

    results = {}

    # -- AC-2: Random 1MB raw-store test --
    print("\n[AC-2] DeepSeek test: raw-store fallback on 1 MB random input")
    data_1mb = make_random_1mb()
    blob_1mb = encode(data_1mb)
    hdr_1mb, _ = parse_header(blob_1mb)
    ratio_1mb = len(blob_1mb) / len(data_1mb)
    mode_1mb = hdr_1mb["mode"]
    recovered_1mb = decode(blob_1mb)
    rt_ok_1mb = recovered_1mb == data_1mb
    print(f"  Input:        {len(data_1mb):>10,} bytes")
    print(f"  Output:       {len(blob_1mb):>10,} bytes")
    print(f"  Ratio:        {ratio_1mb:.6f}")
    print(f"  Mode:         {mode_1mb} ({'raw-store' if mode_1mb == 1 else 'cube'})")
    print(f"  Round-trip:   {'OK' if rt_ok_1mb else 'FAIL'}")
    print(f"  Overhead:     {len(blob_1mb) - len(data_1mb)} bytes "
          f"(bound={HEADER_OVERHEAD_BOUND})")
    results["ac2_random_1mb"] = {
        "input_bytes": len(data_1mb),
        "output_bytes": len(blob_1mb),
        "ratio": ratio_1mb,
        "mode": mode_1mb,
        "round_trip_ok": rt_ok_1mb,
        "overhead": len(blob_1mb) - len(data_1mb),
    }

    # -- AC-3 + AC-4: Locality corpus --
    locality_corpus = [
        ("text_64kb", make_text_64kb()),
        ("random_64kb", make_random_64kb()),
        ("log_16kb", make_log_16kb()),
    ]

    print("\n[AC-3] Moonshot test: gap=1 fraction and mean run-length")
    print(f"  {'File':<15} {'TotalGaps':>10} {'Frac(gap=1)':>12} {'MeanRun':>10}")
    print(f"  {'-'*15} {'-'*10} {'-'*12} {'-'*10}")

    gap1_fractions = []
    gap1_mean_runs = []
    results["ac3"] = {}

    for name, data in locality_corpus:
        frac, mean_run, total = measure_gap1_stats(data)
        gap1_fractions.append(frac)
        gap1_mean_runs.append(mean_run)
        print(f"  {name:<15} {total:>10,} {frac:>12.4f} {mean_run:>10.2f}")
        results["ac3"][name] = {
            "total_gaps": total,
            "fraction_gap1": frac,
            "mean_run_length_gap1": mean_run,
        }

    mean_frac = sum(gap1_fractions) / len(gap1_fractions) if gap1_fractions else 0
    mean_run_all = sum(gap1_mean_runs) / len(gap1_mean_runs) if gap1_mean_runs else 0
    print(f"\n  Mean fraction(gap=1): {mean_frac:.4f}")
    print(f"  Mean run-length(gap=1): {mean_run_all:.2f}")
    if mean_run_all < 8:
        print("  NOTE: mean run-length < 8 — confirms consilium locality risk "
              "(justifies OQ-3/OQ-5 priority over OQ-2).")
    results["ac3"]["aggregate"] = {
        "mean_fraction_gap1": mean_frac,
        "mean_run_length_gap1": mean_run_all,
    }

    print("\n[AC-4] First compression ratio on locality corpus")
    print(f"  {'File':<15} {'Input':>10} {'Output':>10} {'Ratio':>8} {'Mode':>6} {'RT':>4}")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*8} {'-'*6} {'-'*4}")

    ratios_cube = []
    results["ac4"] = {}

    for name, data in locality_corpus:
        blob = encode(data)
        hdr, _ = parse_header(blob)
        ratio = len(blob) / len(data)
        mode = hdr["mode"]
        recovered = decode(blob)
        rt_ok = recovered == data
        mode_str = "raw" if mode == 1 else "cube"
        rt_str = "OK" if rt_ok else "FAIL"
        print(f"  {name:<15} {len(data):>10,} {len(blob):>10,} {ratio:>8.4f} {mode_str:>6} {rt_str:>4}")
        if mode == 0:
            ratios_cube.append(ratio)
        results["ac4"][name] = {
            "input_bytes": len(data),
            "output_bytes": len(blob),
            "ratio": ratio,
            "mode": mode,
            "round_trip_ok": rt_ok,
        }

    if ratios_cube:
        mean_ratio_cube = sum(ratios_cube) / len(ratios_cube)
        print(f"\n  Mean ratio (cube-mode files only): {mean_ratio_cube:.4f}")
    else:
        mean_ratio_cube = None
        print("\n  All files used raw-store — no cube-mode ratio to average.")
    results["ac4"]["aggregate_ratio_cube"] = mean_ratio_cube

    overall_ratios = [results["ac4"][n]["ratio"] for n, _ in locality_corpus]
    mean_ratio_all = sum(overall_ratios) / len(overall_ratios)
    print(f"  Mean ratio (all files):              {mean_ratio_all:.4f}")
    results["ac4"]["aggregate_ratio_all"] = mean_ratio_all

    # -- Write research report --
    _write_research_report(results)
    print("\n[DONE] Research report written to "
          "Projects/Cubrim/documentation/ephemeral/research/CUBR-0004-first-measurements.md")

    return results


def _write_research_report(results: dict):
    repo_root = Path(__file__).parent.parent.parent  # Projects/Cubrim/
    out_path = repo_root / "docs" / "ephemeral" / "research" / "CUBR-0004-first-measurements.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ac2 = results["ac2_random_1mb"]
    ac3_agg = results["ac3"]["aggregate"]
    ac4 = results["ac4"]
    ac4_agg_cube = ac4["aggregate_ratio_cube"]
    ac4_agg_all = ac4["aggregate_ratio_all"]

    # Per-file table rows for ac3
    ac3_rows = ""
    for key, val in results["ac3"].items():
        if key == "aggregate":
            continue
        ac3_rows += (
            f"| {key:<15} | {val['total_gaps']:>10,} "
            f"| {val['fraction_gap1']:>11.4f} "
            f"| {val['mean_run_length_gap1']:>9.2f} |\n"
        )

    # Per-file table rows for ac4
    ac4_rows = ""
    for key, val in ac4.items():
        if key.startswith("aggregate"):
            continue
        mode_str = "raw-store" if val["mode"] == 1 else "cube"
        rt_str = "OK" if val["round_trip_ok"] else "FAIL"
        ac4_rows += (
            f"| {key:<15} | {val['input_bytes']:>10,} "
            f"| {val['output_bytes']:>10,} "
            f"| {val['ratio']:>7.4f} | {mode_str:<9} | {rt_str} |\n"
        )

    content = f"""---
artifact: research-measurement
task_internal: prototype-first-measurements
created: 2026-06-17
status: measured
corpus: synthetic-fixed-seed
---

> 🔒 **СЕКРЕТНО — внутренний артефакт.** Результаты замеров Cubrim-прототипа.
> Живёт ТОЛЬКО в `documentation/ephemeral/research/` (приватный репо). Механизм НЕ публикуется.

# Cubrim v1 Python Prototype — First Measurements

Prototype: Python 3 + NumPy. Algorithm: rulebook v1 (R1–R8).
Corpus: synthetic, fixed seed, reproducible via `make benchmark`.

## AC-2: Raw-store fallback on 1 MB uniform-random input (DeepSeek test)

R7 mandatory: if cube_size >= raw_size + header_overhead → mode=1 (raw-store).

| Metric | Value |
|--------|-------|
| Input size | {ac2['input_bytes']:,} bytes |
| Output size | {ac2['output_bytes']:,} bytes |
| Ratio (output/input) | {ac2['ratio']:.6f} |
| Mode | {ac2['mode']} ({'raw-store' if ac2['mode'] == 1 else 'cube — R7 DID NOT FIRE'}) |
| Overhead bytes | {ac2['overhead']} |
| HEADER_OVERHEAD_BOUND | {HEADER_OVERHEAD_BOUND} bytes |
| Round-trip | {'PASS' if ac2['round_trip_ok'] else 'FAIL'} |

**H-09 verdict:** R7 raw-store {'confirmed' if ac2['mode'] == 1 else 'NOT TRIGGERED — BUG'}.
Expansion ratio {ac2['ratio']:.4f} {"<= 1.1x (within bound)" if ac2['ratio'] <= 1.1 else "> 1.1x (EXCEEDS BOUND — BUG)"}.

## AC-3: Gap=1 locality stats on baseline corpus (Moonshot test)

N=2 cube, mixed-radix Φ. Per-axis gap sequences measured.
If mean run-length < 8 → confirms consilium locality risk → OQ-3/OQ-5 prioritised over OQ-2.

| File | Total Gaps | Fraction(gap=1) | MeanRun(gap=1) |
|------|-----------|-----------------|----------------|
{ac3_rows}
| **aggregate** | — | **{ac3_agg['mean_fraction_gap1']:.4f}** | **{ac3_agg['mean_run_length_gap1']:.2f}** |

**H-02/H-04/H-06 evidence:**
- Mean fraction(gap=1): {ac3_agg['mean_fraction_gap1']:.4f}
- Mean run-length(gap=1): {ac3_agg['mean_run_length_gap1']:.2f}
- {"mean run-length < 8 → locality risk confirmed (OQ-3/OQ-5 > OQ-2)" if ac3_agg['mean_run_length_gap1'] < 8 else "mean run-length >= 8 → locality baseline acceptable"}

## AC-4: First compression ratio on locality corpus

| File | Input (B) | Output (B) | Ratio | Mode | RT |
|------|-----------|-----------|-------|------|-----|
{ac4_rows}
| **aggregate (cube only)** | — | — | **{f'{ac4_agg_cube:.4f}' if ac4_agg_cube else 'N/A (all raw-store)'}** | — | — |
| **aggregate (all)** | — | — | **{ac4_agg_all:.4f}** | — | — |

**H-01/H-03/H-08 evidence:**
- Mean ratio all files: {ac4_agg_all:.4f}
- {"ratio > 0.9 everywhere → cube v1-defaults give no compression on this corpus" if ac4_agg_all > 0.9 else "ratio <= 0.9 on some files → some compression benefit observed"}
- Mean ratio cube-mode only: {f'{ac4_agg_cube:.4f}' if ac4_agg_cube else 'N/A'}

## Reproducibility

```bash
cd Projects/Cubrim/code
make benchmark
```

Corpus: synthetic, numpy fixed seeds (text=fragment*rep, random=np.random.default_rng(777),
log=templates*rng(99)). No external files required.
"""
    out_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    run_benchmark()
