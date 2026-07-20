# CUBR-0028 Axis-1 — Distance-Map Contribution Probe

**Axis:** 1 — Distance-map (sparse gap mechanism, lever only for ρ<0.3 — Gotcha #1)
**code_sha:** `15b0ba6306febaa5f806fed51cdfe3ffa3ac2c21`
**Expected verdict:** NO-GO on canonical corpus (all positions positionally occupied)

## Rationale

Axis-1 (distance-map) is orthogonal to context-depth. However, on the canonical
7-file corpus with positional i-order phi mapping, every cube cell is occupied
(phi_inv(phi(i)) = i → all L positions used → all gaps = 1). The RLE-coded gap
stream is therefore near-zero bytes. The mechanism carries ~0% weight.

**Gotcha #1 guard:** this probe does NOT mutate the canonical corpus. The sparse
experiment (ρ<0.3 inputs) requires a separate `corpus-sparse/` directory and
reports per-file deltas only — never folded into the 7-file aggregate.

## Wire-Format Branches (Gotcha #6 Contract)

```
branches    = ["raw", "cube_huffman", "cube_huffman_with_distmap"]
extra_terms = ["distmap_rle_bytes", "selector_byte"]
assert len(cost_terms) == 5  # 5 == 5 PASS
```

## Distance-Map Measurements on Canonical Corpus

| File | Size | T4-bytes | distmap-RLE | distmap% of T4 | frac(gap=1) ax0 | frac(gap=1) ax1 |
|------|------|----------|-------------|---------------|----------------|----------------|
| sparse_clustered | 2048 | 502 | 4 | 0.80% | 1.000 | 1.000 |
| dense | 4096 | 4109 | 4 | 0.10% | 1.000 | 1.000 |
| text | 16384 | 5705 | 4 | 0.07% | 1.000 | 1.000 |
| log_like | 16384 | 7318 | 4 | 0.05% | 1.000 | 1.000 |
| binary_mixed | 8192 | 8205 | 4 | 0.05% | 1.000 | 1.000 |
| random_high | 4096 | 4109 | 4 | 0.10% | 1.000 | 1.000 |
| sparse_small | 256 | 269 | 2 | 0.74% | 1.000 | 1.000 |

## Size Model Results

| File | raw | cube | cube+distmap | total (with selector) |
|------|-----|------|-------------|----------------------|
| sparse_clustered | 2048 | 502 | 506.0 | 503.0 |
| dense | 4096 | 4109 | 4113.0 | 4097.0 |
| text | 16384 | 5705 | 5709.0 | 5706.0 |
| log_like | 16384 | 7318 | 7322.0 | 7319.0 |
| binary_mixed | 8192 | 8205 | 8209.0 | 8193.0 |
| random_high | 4096 | 4109 | 4113.0 | 4097.0 |
| sparse_small | 256 | 269 | 271.0 | 257.0 |

## Aggregate Verdict

| Metric | Value |
|--------|-------|
| T4 baseline aggregate | 0.58724 |
| Modelled aggregate | 0.586365 |
| Delta vs T4 | -0.149% |
| GO threshold | 0.575495 (−2%) |
| Total distmap RLE bytes | 26 |
| Distmap as % of T4 total | 0.09% |

## AXIS-1 VERDICT: NO-GO

**Why NO-GO on the canonical corpus:**
- Positional i-order phi assigns phi(i) = (i%256, i//256). Every cell [0..L-1] is
  occupied by construction (phi_inv(phi(i)) = i). All gaps = 1. The RLE-coded gap
  stream is near-zero bytes, contributing < 0.1% of T4 total size.
- Adding a `cube_huffman_with_distmap` branch to the wire format ADDS overhead
  (mode selector + distmap header) without any gain → aggregate increases.
- The lever for distance-map improvement requires ρ<0.3 inputs (Gotcha #1), which
  would require adding sparse inputs — those change the baseline and make
  comparison against 0.587240 invalid.

**Gotcha #1 confirmed:** distance-map is an improvement-inert axis on this corpus.
Any sparse-corpus experiment (optional Class-B follow-up) must use a separate
`corpus-sparse/` directory with its own manifest and report per-file deltas only.

