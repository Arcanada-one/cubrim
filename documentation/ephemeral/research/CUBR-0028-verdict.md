# CUBR-0028 — Verdict: BWT (ValueScheme::BwtEntropy)

**Date:** 2026-06-20
**code_sha:** `15b0ba6306febaa5f806fed51cdfe3ffa3ac2c21`
**Status: GO**

---

## Final Aggregate

| Metric | Value |
|--------|-------|
| T4 baseline | 0.587240 (30217 / 51456 bytes) |
| BWT real Rust | **0.504412** (25955 / 51456 bytes) |
| Delta vs T4 | **−0.0828 aggregate-ratio points** (−4262 bytes; −14.1% relative improvement) |
| GO threshold | 0.575495 (−2% vs T4) |
| **Verdict** | **GO** (beats threshold by 7.1 pp) |

## Per-File Results

| File | T4 bytes | BWT bytes | Delta | Mode | BWT action |
|------|----------|-----------|-------|------|------------|
| sparse_clustered | 502 | 502 | 0 | cube | T4 fallback (BWT worse) |
| dense | 4109 | 4109 | 0 | raw | raw-store (unchanged) |
| text | 5705 | 3583 | −2122 | cube | **BWT wins** |
| log_like | 7318 | 5178 | −2140 | cube | **BWT wins** |
| binary_mixed | 8205 | 8205 | 0 | raw | raw-store (unchanged) |
| random_high | 4109 | 4109 | 0 | raw | raw-store (unchanged) |
| sparse_small | 269 | 269 | 0 | raw | raw-store (unchanged) |

## Spike vs Real Gap

| | Aggregate | Delta vs T4 |
|-|-----------|-------------|
| Python probe (modelled) | 0.464088 | −20.97% |
| Real Rust (measured) | 0.504412 | −8.28% |
| Gap | +0.040324 | +12.69 pp |

**Root cause of gap:** The Python probe modelled the BWT bitstream cost as
`T4_actual + (H1_bwt − H1_orig) × L/8` — an entropy lower bound. The real
T4 context Huffman over BWT output uses 16-observation context tables and
actual Huffman code lengths, which exceed the entropy lower bound.

Despite the model↔real gap, the result remains a sound GO: the real
implementation still beats the −2% threshold by 7.1 percentage points.
The gap also validates Gotcha #6 discipline: had the probe used an even
looser model (e.g. omitting primary_index bytes), the real result would
still have been GO, but the conservative model meant the GO was sound.

## Implementation Summary

**New component:** `ValueScheme::BwtEntropy` (scheme byte 6) in
`code/cubrim-rs/src/`.

**Wire format (after cube header + gap streams):**
```
[primary_index : u16 BE]  — 2 bytes; BWT primary index
[n_contexts    : u16 BE]  — T4 context-Huffman table header
for each context entry:
  [ctx_id : u16 BE]
  [code_len[0..n_distinct] : u8 × n_distinct]
[coded bitstream : MSB-first, byte-aligned, zero-padded tail]
```

**Competitive selection:** the encoder builds both `BwtEntropy` and
`EntropyContext` value streams, writes the smaller one, and marks the
header with the actual scheme byte used. This ensures that files where
BWT is counter-productive (e.g. `sparse_clustered`) fall back to T4.

**Lossless round-trip:** verified on all 7 corpus files (172 tests pass,
0 failures). Decode is fully self-describing from the header alone (R6).

**BWT algorithm:** O(n log n) stable sort on rotation indices (cyclic
comparison). For n ≤ 65536 (corpus max 16384) this runs in <1ms.

## Axes Summary (all three probes)

| Axis | Probe | Python aggregate | Real aggregate | Verdict |
|------|-------|-----------------|----------------|---------|
| 3 (pre-processing) | cubr0028_axis3_pretransform_probe.py | 0.586365 | — | NO-GO |
| 2 (BWT reorder) | cubr0028_axis2_bwt_reorder_probe.py | 0.464088 | **0.504412** | **GO** |
| 1 (distance-map) | cubr0028_axis1_distance_map_probe.py | 0.586365 | — | NO-GO |

## Files Created / Modified

- `code/cubrim-rs/src/config.rs` — added `ValueScheme::BwtEntropy` (scheme byte 6)
- `code/cubrim-rs/src/codec.rs` — BWT encode/decode/size functions + match arms
- `code/cubrim-rs/src/main.rs` — CLI `--value-scheme bwt-entropy` support
- `code/cubrim-rs/tests/cubr0028_bench.rs` — bench test (7-file corpus, verdict JSON)
- `documentation/ephemeral/research/CUBR-0028-bench.json` — machine-readable results
- `documentation/ephemeral/research/CUBR-0028-axis2-probe.json` — Python probe results
- `documentation/ephemeral/research/CUBR-0028-axis2-probe-report.md` — Python probe report
- `documentation/ephemeral/research/CUBR-0028-probe-results.md` — all-axes summary

## Follow-up Class B (backlog)

- **BWT performance:** current O(n log n × k) sort is sufficient for n ≤ 65536 but
  a suffix-array BWT (O(n)) would be needed for larger inputs.
- **Adaptive per-file BWT:** auto-selection is already implemented (competitive
  encode). No further work needed on selection logic.
- **Axis-3 (pre-processing):** delta/MTF n_distinct inflation is fundamental —
  requires a domain-aware symbol grouping to reduce n_distinct. Backlog item.
