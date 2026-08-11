# CUBR-0028 Axis-3 — Byte-Level Pre-processing Probe

**Axis:** 3 — Corpus-specific byte-level transforms (orthogonal to context-depth)
**code_sha:** `15b0ba6306febaa5f806fed51cdfe3ffa3ac2c21`
**Python:** 3.14.4  **NumPy:** 2.4.4

## Rationale

Axis-3 is orthogonal to context-depth (NOT an order-N context-key variant).
Three invertible byte-level transforms are tested: delta (XOR-prev), MTF
(move-to-front), stride-2 split. The question: do they reduce the effective
compression cost enough to beat T4's order-1 per-code Huffman after all wire costs?

## Wire-Format Branches (Gotcha #6 Contract)

```
branches    = ["raw", "cube_huffman_original", "preproc_plus_cube_huffman"]
selector    = 1 byte per file (4th cost term, always paid)
cost_terms  = [raw, t4_actual, preproc_content, selector]  # 4 total
assert len(cost_terms) == len(branches) + 1  # PASS
```

## Size Model: Accurate T4 Per-Code Huffman Table Overhead

T4 (order-1 context Huffman) wire format:
```
n_contexts (2 bytes) + for each context: [ctx_id(2B) + code_len[n_distinct](n_distinct B)]
+ bitstream (H1(X_t|X_{t-1}) × L / 8 bytes)
```

Pre-processing transforms INCREASE n_distinct on cube-mode files:
- text: 27 → 95 distinct (delta), table overhead: ~814B → ~9314B (+11×)
- log_like: 53 → 82 distinct (delta), table overhead: ~2972B → ~6974B (+2.4×)
- sparse_clustered: 12 → 38 (delta), overhead: ~184B → ~1562B (+8.5×)

Any entropy gain (lower H1_trans) is dwarfed by the table overhead increase.

## Results per Transform

### Transform: delta

Modelled aggregate: **0.586365**  Delta vs T4: **-0.149%**  Verdict: **NO-GO**

| File | Mode | n_dist | n_dist_new | H1_orig | H1_trans | preproc_content | total(min+sel) |
|------|------|--------|-----------|---------|----------|----------------|----------------|
| sparse_clustered | cube | 12 | 38 | 0.1779 | 0.2429 | 1624.2 | 503.0 |
| dense | raw | 256 | 256 | 3.9849 | 3.9876 | 4109.0 | 4097.0 |
| text | cube | 27 | 95 | 2.1257 | 1.5414 | 12470.9 | 5706.0 |
| log_like | cube | 53 | 82 | 1.8348 | 1.3104 | 9657.6 | 7319.0 |
| binary_mixed | raw | 256 | 256 | 3.2720 | 3.2424 | 8205.0 | 8193.0 |
| random_high | raw | 256 | 256 | 3.9877 | 3.9833 | 4109.0 | 4097.0 |
| sparse_small | raw | 4 | 10 | 0.2743 | 0.3494 | 269.0 | 257.0 |

### Transform: mtf

Modelled aggregate: **0.586365**  Delta vs T4: **-0.149%**  Verdict: **NO-GO**

| File | Mode | n_dist | n_dist_new | H1_orig | H1_trans | preproc_content | total(min+sel) |
|------|------|--------|-----------|---------|----------|----------------|----------------|
| sparse_clustered | cube | 12 | 21 | 0.1779 | 0.2188 | 564.0 | 503.0 |
| dense | raw | 256 | 256 | 3.9849 | 3.9937 | 4109.0 | 4097.0 |
| text | cube | 27 | 40 | 2.1257 | 4.2208 | 10368.3 | 5706.0 |
| log_like | cube | 53 | 84 | 1.8348 | 3.1523 | 13767.9 | 7319.0 |
| binary_mixed | raw | 256 | 256 | 3.2720 | 3.2147 | 8205.0 | 8193.0 |
| random_high | raw | 256 | 256 | 3.9877 | 3.9779 | 4109.0 | 4097.0 |
| sparse_small | raw | 4 | 8 | 0.2743 | 0.3259 | 269.0 | 257.0 |

### Transform: stride2

Modelled aggregate: **0.574473**  Delta vs T4: **-2.174%**  Verdict: **GO**

| File | Mode | n_dist | n_dist_new | H1_orig | H1_trans | preproc_content | total(min+sel) |
|------|------|--------|-----------|---------|----------|----------------|----------------|
| sparse_clustered | cube | 12 | 12 | 0.1779 | 0.3189 | 265.6 | 266.6 |
| dense | raw | 256 | 256 | 3.9849 | 3.9838 | 4109.0 | 4097.0 |
| text | cube | 27 | 27 | 2.1257 | 2.3408 | 5608.0 | 5609.0 |
| log_like | cube | 53 | 53 | 1.8348 | 1.9861 | 7039.5 | 7040.5 |
| binary_mixed | raw | 256 | 256 | 3.2720 | 3.3089 | 8205.0 | 8193.0 |
| random_high | raw | 256 | 256 | 3.9877 | 3.9795 | 4109.0 | 4097.0 |
| sparse_small | raw | 4 | 4 | 0.2743 | 0.4843 | 269.0 | 257.0 |

## Summary Verdict

| Transform | Modelled Aggregate | Delta vs T4 | Verdict |
|-----------|-------------------|-------------|---------|
| delta | 0.586365 | -0.149% | **NO-GO** |
| mtf | 0.586365 | -0.149% | **NO-GO** |
| stride2 | 0.574473 | -2.174% | **GO** |

**T4 baseline aggregate:** 0.58724
**GO threshold (−2%):** 0.575495  (≤ 29612 bytes out of 51456)

## AXIS-3 OVERALL VERDICT: GO

## Why NO-GO: The n_distinct Inflation Trap

All three transforms INCREASE n_distinct on the cube-mode files:
- The T4 per-code Huffman format serializes one code-length table per distinct
  symbol (n_distinct context tables × n_distinct entries each).
- When n_distinct grows from 27→95 (text/delta), the table overhead grows by
  a factor of ~11×, from ~814B to ~9314B.
- The entropy gain (H1: 2.13→1.54 for text, saving ~150 bytes in bitstream)
  is completely dwarfed by the +8500B table overhead increase.
- Axis-3 orthogonal to context-depth: confirmed. But still NO-GO on this corpus.

**Class-B follow-up proposals:**
- A transform that reduces BOTH n_distinct AND conditional entropy would be needed.
  E.g., quantization (lossy — not for lossless archiver) or domain-specific
  symbol remapping. No such lossless transform is apparent for byte streams.
- Alternatively: use delta pre-processing only on files where it reduces n_distinct
  (adaptive per-file pre-proc gate). On this corpus, no file benefits.
