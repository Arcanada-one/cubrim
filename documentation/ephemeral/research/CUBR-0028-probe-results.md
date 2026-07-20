# CUBR-0028 — Spike Probe Results

**code_sha:** `15b0ba6306febaa5f806fed51cdfe3ffa3ac2c21`
**Date:** 2026-06-20
**T4 baseline aggregate:** 0.587240 (30217 / 51456 bytes, 7-file canonical corpus)
**GO threshold:** 0.575495 (−2% vs T4, equivalent to ≤ 29612 bytes total)

---

## Summary

| Axis | Probe file | Modelled aggregate | Delta vs T4 | GO/NO-GO |
|------|-----------|-------------------|-------------|---------|
| 3 (pre-processing) | `cubr0028_axis3_pretransform_probe.py` | 0.586365 | −0.149% | **NO-GO** |
| 2 (BWT reorder) | `cubr0028_axis2_bwt_reorder_probe.py` | 0.464088 | −20.971% | **GO** |
| 1 (distance-map) | `cubr0028_axis1_distance_map_probe.py` | 0.586365 | −0.149% | **NO-GO** |

**Overall: GO (Axis-2 BWT).** Rust implementation warranted per plan Step 5.

---

## Axis-3 — Byte-Level Pre-processing

**Verdict: NO-GO** (aggregate 0.586365, −0.149% vs T4)

**Rationale (orthogonal to context-depth):** Transforms target n_distinct reduction before
Huffman coding — orthogonal to order-N context-key depth.

**Why NO-GO:** All three candidate transforms (delta, MTF, stride-2) fail to reduce the
modelled aggregate below the GO threshold:

- **delta/MTF**: Increase n_distinct on cube-mode files (text: 27→95, log_like: 53→82).
  T4's per-code Huffman serializes n_active × (2 + n_distinct) bytes of table overhead.
  Text n_distinct grows by 3.5×, inflating table overhead from ~814B to ~9314B — dwarfing
  the H1 reduction in the bitstream (delta saves ~1196 bits = ~150 bytes for text).

- **stride-2**: Preserves n_distinct, so same table overhead. But stride-2 INCREASES H1
  on all cube-mode files (sparse_clustered: +79%, text: +10%, log_like: +8%). All cube
  files cost more, not less.

- The −0.149% improvement vs T4 comes entirely from raw-mode files where raw_bytes <
  T4_actual (T4 raw-store overhead is 13 bytes; with selector, raw+1 < T4 for dense,
  random_high). This is NOT a preproc win.

**Wire-format branches (Gotcha #6):**
```
branches    = ["raw", "cube_huffman_original", "preproc_plus_cube_huffman"]
selector    = 1 byte per file
cost_terms  = [raw_bytes, cube_bytes, preproc_content, selector_bytes]  # 4 total
assert len(cost_terms) == len(branches) + 1  ← PASS (checked in probe)
```

**Class-B follow-up proposals:**
- A lossless transform that reduces BOTH n_distinct AND H1 would be needed. No standard
  transform achieves this for byte streams.
- Domain-aware symbol grouping (e.g., for numeric or log data) could reduce n_distinct
  but would be corpus-specific. Backlog item.

---

## Axis-2 — BWT-Style Value-Stream Reordering

**Verdict: GO** (aggregate 0.464088, −20.971% vs T4)

**Rationale (orthogonal to context-depth):** BWT reorders the VALUE-CODE stream by sorting
rotations — building its own locality INDEPENDENT of phi-coordinates. This is explicitly
NOT phi-sort (Gotcha #3). CUBR-0018 showed phi-sort destroys i-order runs; BWT creates
new run structure in a completely different way.

**Entropy pre-gate (Gotcha #3):** PASS. Max H1 reduction: 91.42% on log_like.

| File | H1(i-order) | H1(BWT) | Reduction | Gate |
|------|------------|---------|----------|------|
| sparse_clustered | 0.1779 | 0.3278 | −84.25% | fail (BWT WORSENS) |
| dense | 3.9849 | 3.9708 | +0.36% | fail (tiny) |
| text | 2.1257 | 0.7289 | +65.71% | PASS |
| log_like | 1.8348 | 0.1575 | +91.42% | PASS |
| binary_mixed | 3.2720 | 3.3627 | −2.77% | fail |
| random_high | 3.9877 | 3.9870 | +0.02% | fail (tiny) |
| sparse_small | 0.2743 | 0.4508 | −64.34% | fail (BWT WORSENS) |

BWT significantly improves structured data (text, log_like) but worsens sparse/random data.

**Size model (correct — avoids the Axis-3 n_distinct trap):**
BWT preserves n_distinct → T4 table overhead (cube header, gap RLE, Huffman tables)
is UNCHANGED. Only the bitstream changes:

```
bwt_cost = T4_actual + (H1_bwt − H1_orig) × L/8 + primary_index_bytes + selector
total    = min(raw + sel, T4_actual + sel, bwt_cost)
```

The `primary_index_bytes = ceil(log2(L+2)/8)` = 2 bytes for all corpus files — negligible.
This is the CUBR-0026 analogue: omitting it would slightly overstate the gain.

**Per-file modelled results:**

| File | Mode | raw | T4 | delta_bitstream | bwt_cost | total | chosen |
|------|------|-----|-----|----------------|---------|-------|--------|
| sparse_clustered | cube | 2048 | 502 | +38.4 | 543.4 | 503.0 | cube |
| dense | raw | 4096 | 4109 | −7.2 | 4104.8 | 4097.0 | raw |
| text | cube | 16384 | 5705 | −2860.6 | 2847.4 | 2847.4 | BWT |
| log_like | cube | 16384 | 7318 | −3435.2 | 3885.8 | 3885.8 | BWT |
| binary_mixed | raw | 8192 | 8205 | +92.9 | 8300.9 | 8193.0 | raw |
| random_high | raw | 4096 | 4109 | −0.3 | 4111.7 | 4097.0 | raw |
| sparse_small | raw | 256 | 269 | +5.6 | 277.6 | 257.0 | raw |

**Total modelled: 23881.6 bytes → aggregate 0.464088 (−20.971% vs T4)**

**Wire-format branches (Gotcha #6):**
```
branches    = ["raw", "cube_huffman_original", "bwt_plus_cube_huffman"]
extra_terms = ["bwt_primary_index", "selector_byte"]
cost_terms  = 5 total
assert len(cost_terms) == len(branches) + len(extra_terms)  ← PASS
```

**Why GO is sound:**
1. BWT H1 values verified against an independent correct BWT implementation (list suffix sort
   with Timsort, confirmed correct on sparse_clustered and text).
2. Size model uses T4_actual (measured real bytes) as base — no double-counting of overhead.
3. n_distinct preserved → no table overhead inflation (the Axis-3 trap avoided).
4. primary_index_bytes correctly charged (the CUBR-0026 omission guard).

**Next step:** Rust implementation per plan Step 5.

---

## Axis-1 — Distance-Map

**Verdict: NO-GO** (aggregate 0.586365, −0.149% vs T4)

**Rationale (orthogonal to context-depth):** Distance-map encodes gaps between occupied
cube positions — independent of value-stream coding. The lever requires sparse inputs ρ<0.3
(Gotcha #1).

**Measurements:**

| File | T4-bytes | distmap-RLE | distmap % | frac(gap=1) |
|------|----------|-------------|----------|------------|
| sparse_clustered | 502 | 4 | 0.80% | (positional: all gaps=1) |
| dense | 4109 | 4 | 0.10% | 1.000 |
| text | 5705 | 4 | 0.07% | 1.000 |
| log_like | 7318 | 4 | 0.05% | 1.000 |
| binary_mixed | 8205 | 4 | 0.05% | 1.000 |
| random_high | 4109 | 4 | 0.10% | 1.000 |
| sparse_small | 269 | 2 | 0.74% | (positional: all gaps=1) |

**Total distmap RLE: 26 bytes (0.09% of 30217 T4 bytes).**

With positional i-order phi, phi(i) = (i%256, i//256), every cell [0..L-1] is occupied by
construction (phi_inv(phi(i)) = i). All gaps = 1. The gap map is trivially compact.

The distance-map mechanism carries ~0% on this corpus. Any enhancement (e.g., "enhanced
distmap" branch) adds mode-selector overhead with zero benefit → aggregate increases.

**Gotcha #1 honoured:** canonical corpus NOT mutated. The −0.149% improvement vs T4
baseline comes from raw-mode files paying raw+1 instead of T4_actual+1.

**Wire-format branches (Gotcha #6):**
```
branches    = ["raw", "cube_huffman", "cube_huffman_with_distmap"]
extra_terms = ["distmap_rle_bytes", "selector_byte"]
cost_terms  = 5 total
assert len(cost_terms) == len(branches) + len(extra_terms)  ← PASS
```

**Gotcha #2 confirmed:** distance-map weight is inert under positional i-order phi.
Any distance-map improvement lever requires ρ<0.3 inputs (Gotcha #1 trap).

---

## Probe Execution Timestamps

All probes run on 2026-06-20 on the local Mac (arcana-dev remote connection not required —
this is Python-only research).

JSON result files:
- `CUBR-0028-axis3-probe.json`
- `CUBR-0028-axis2-probe.json`
- `CUBR-0028-axis1-probe.json`

Full per-axis reports:
- `CUBR-0028-axis3-probe-report.md`
- `CUBR-0028-axis2-probe-report.md`
- `CUBR-0028-axis1-probe-report.md`
