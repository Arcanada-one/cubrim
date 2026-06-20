# CUBR-0028 Axis-2 — BWT-Style Value-Stream Reordering Probe

**Axis:** 2 — BWT-style reordering of the value stream (NOT phi-sort — Gotcha #3)
**code_sha:** `15b0ba6306febaa5f806fed51cdfe3ffa3ac2c21`
**Python:** 3.14.4  **NumPy:** 2.4.4

## Rationale

Axis-2 is orthogonal to context-depth. BWT builds its own locality on the value-code
stream by sorting rotations — grouping identical symbols and creating long runs.
This reduces H(X_t|X_{t-1}) significantly on structured data.

**Critically NOT phi-sort (Gotcha #3):** BWT acts on the value stream directly,
not on phi-coordinates. CUBR-0018 showed phi-sort destroys i-order runs. BWT creates
new run structure independent of the original coordinate system.

## Size Model: Conservative and Correct

BWT preserves n_distinct (same symbol set, reordered). Therefore T4 overhead
(cube header, gap RLE map, Huffman tables) is UNCHANGED. Only the Huffman bitstream
changes by (H1_bwt - H1_orig) × L/8 bytes.

```
bwt_cost = T4_actual + (H1_bwt - H1_orig)*L/8 + primary_index_bytes + selector
```

The `primary_index_bytes` is the CUBR-0026 analogue: the decoder needs the BWT
primary index to reconstruct the original sequence. Cost: ceil(log2(L+2)/8) bytes.

## Wire-Format Branches (Gotcha #6 Contract)

```
branches    = ["raw", "cube_huffman_original", "bwt_plus_cube_huffman"]
extra_terms = ["bwt_primary_index", "selector_byte"]
assert len(cost_terms) == 5  # 5 == 5 PASS
```

## Entropy Pre-Gate (Gotcha #3)

**Result: PASS**  Max reduction: 91.42%  (threshold: 1%)

| File | H1(i-order) | H1(BWT) | Entropy reduction | Gate |
|------|------------|---------|------------------|------|
| sparse_clustered | 0.1779 | 0.3278 | -84.25% | fail |
| dense | 3.9849 | 3.9708 | +0.36% | fail |
| text | 2.1257 | 0.7289 | +65.71% | PASS |
| log_like | 1.8348 | 0.1575 | +91.42% | PASS |
| binary_mixed | 3.2720 | 3.3627 | -2.77% | fail |
| random_high | 3.9877 | 3.9870 | +0.02% | fail |
| sparse_small | 0.2743 | 0.4508 | -64.34% | fail |

## Size Model Results

| File | Mode | raw | T4-bytes | delta_bitstream | bwt_content | idx | sel | bwt_total | chosen |
|------|------|-----|----------|----------------|------------|-----|-----|-----------|--------|
| sparse_clustered | cube | 2048 | 502 | +38.4 | 540.4 | 2 | 1 | 543.4 | cube |
| dense | raw | 4096 | 4109 | -7.2 | 4101.8 | 2 | 1 | 4104.8 | raw |
| text | cube | 16384 | 5705 | -2860.6 | 2844.4 | 2 | 1 | 2847.4 | bwt |
| log_like | cube | 16384 | 7318 | -3435.2 | 3882.8 | 2 | 1 | 3885.8 | bwt |
| binary_mixed | raw | 8192 | 8205 | +92.9 | 8297.9 | 2 | 1 | 8300.9 | raw |
| random_high | raw | 4096 | 4109 | -0.3 | 4108.7 | 2 | 1 | 4111.7 | raw |
| sparse_small | raw | 256 | 269 | +5.6 | 274.6 | 2 | 1 | 277.6 | raw |

## Aggregate Verdict

| Metric | Value |
|--------|-------|
| T4 baseline aggregate | 0.58724 |
| Modelled aggregate | 0.464088 |
| Delta vs T4 | -20.971% |
| GO threshold | 0.575495 (−2%) |
| Entropy pre-gate | PASS |

## AXIS-2 VERDICT: GO

Entropy pre-gate PASS (max reduction: 91.42%). Size model applied. Aggregate ≤ GO threshold.

**Key findings:**
- BWT dramatically reduces H1 on structured files (text: 2.1257→0.7289, log_like: 1.8348→0.1575).
- BWT preserves n_distinct → T4 overhead unchanged → entropy savings flow directly to wire size.
- primary_index cost (2 bytes per file) is negligible vs the entropy savings.
- Modelled aggregate well below −2% GO threshold.
- This result warrants a Rust implementation (Step 5 per plan).
