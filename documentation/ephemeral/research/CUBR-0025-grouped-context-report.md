# CUBR-0025 — Grouped-Context Key: Research Report

**Hypothesis:** R5' — grouped context key for order-1 Huffman  
**Code SHA (feature branch HEAD):** `794148d85631bc0e2f351e2178d3ab7e7911e137` (= main @ T4 merge, no Rust changes)  
**Branch:** `feat/cubr-0025-grouped-context`  
**Date:** 2026-06-20  
**Verdict: NO-GO**

---

## Context

T4 (`ValueScheme::EntropyContext`, `codec.rs`) keys its order-1 Huffman context on the **previous value-code**: `prev_ctx = code as u16` (set at `codec.rs:651` in `build_context_tables` and `codec.rs:740` in the encode loop). The code index is dense in `[0, n_distinct)`.

R5 proposed using the **raw byte** (0–255) as the context key instead of the dense code. R5' generalises: map the previous raw byte into a **small number of semantic groups**, yielding fewer context tables and more observations per table.

---

## AC-1 — Analytical: Naive R5 (raw-byte as context key 1:1) is a NO-OP

`build_value_dict` (`bitpack.rs:19-31`) constructs the value→code mapping by sorting distinct values in ascending order and assigning `code = rank`:

```rust
// bitpack.rs:20-29
let mut distinct: Vec<usize> = values.to_vec();
distinct.sort_unstable();
distinct.dedup();
let inverse_dict = distinct.clone();
let value_to_code: Vec<(usize, usize)> = distinct
    .iter()
    .enumerate()
    .map(|(code, &val)| (val, code))
    .collect();
```

This is a **monotonic bijection**: `code = rank(raw_value)`, equivalently `raw_value = inverse_dict[code]`. Every code corresponds to exactly one raw byte and vice-versa.

T4's context key (`codec.rs:651`, `:740`) is `prev_ctx = code as u16`. If it were instead `prev_ctx = raw_byte`, the context-equivalence partition of the sequence would be **identical**: each code↔raw-byte pair defines the same predecessor-equivalence class. The only change is the numeric label of each context: dense `[0, n_distinct)` → sparse `[0, 256)`. This relabeling:

- Does **not** change which symbols follow which predecessor class.
- **Inflates the header**: with sparse labels up to 255, the encoder may allocate slots for 256 contexts even though only `n_distinct ≤ 256` are populated. No compression gain; only extra overhead.

**Conclusion:** naive R5 (1:1 raw-byte key) is a pure relabeling of T4. Identical partition, identical bitstream cost, inflated header. Zero entropy gain. No empirical spike is warranted. This aligns with the original research note that acknowledged "same number of contexts."

---

## AC-2 — Grouped-Context Probe: ≥2 Schemes Tested

Three grouping schemes were probed on the SHA-pinned 7-file corpus.

### Grouping schemes

| ID | Groups | Description |
|----|--------|-------------|
| G1_ascii5 | 5 | ASCII semantic classes: {lower=0, upper=1, digit=2, whitespace=3, other=4} |
| G2_top3bits | 8 | Top-3 bits of raw byte (`byte >> 5`) → groups 0..7 |
| G3_top2bits | 4 | Top-2 bits of raw byte (`byte >> 6`) → groups 0..3 |

All groupings are pure deterministic functions of the previous decoded raw byte (reversible for decoder reconstruction).

### Wire format modelled (full cost accounting)

```
Header: 2 bytes (n_groups:u8 + scheme_id:u8)
        + n_qualifying_tables × (1 byte group_id + n_distinct bytes code_len)
Bitstream: ceil(total_bits / 8) bytes
```

MIN_CTX_COUNT=16 applies: groups with fewer than 16 observations fall back to the global order-0 table. The fallback table is always present (as a mandatory sentinel entry), identical to T4.

**Clamp rule (CUBR-0023 lesson applied):** 4/7 corpus files are raw-stored by the real encoder (dense, binary_mixed, random_high, sparse_small — their `actual_t4_mode == "raw"`). The real encoder selects `min(raw_size, encoded_size)` and chooses raw for these. A grouped-context value-scheme change cannot override this decision. These files are clamped to `actual_t4_bytes` in all grouped estimates.

For cube-stored files, the estimate is anchored to the real T4 measurement via relative delta from the Python model: `grouped_estimate = actual_t4_bytes × (grouped_python / t4_python)`.

### G1_ascii5 (5 groups — ASCII semantic classes)

| File | size | mode | n_dist | T4 actual | G-ctx clamped | delta vs T4 |
|------|------|------|--------|-----------|---------------|-------------|
| sparse_clustered | 2048 | cube | 12 | 502 | 748 | +49.00% |
| dense | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| text | 16384 | cube | 27 | 5705 | 8126 | +42.44% |
| log_like | 16384 | cube | 53 | 7318 | 7894 | +7.87% |
| binary_mixed | 8192 | raw | 256 | 8205 | 8205 | 0.00% |
| random_high | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| sparse_small | 256 | raw | 4 | 269 | 269 | 0.00% |
| **Aggregate** | **51456** | | | **30217** | **33460** | **+10.73%** |

Aggregate ratio: **0.650264** vs T4 0.587240.

### G2_top3bits (8 groups — top-3 bits of raw byte)

| File | size | mode | n_dist | T4 actual | G-ctx clamped | delta vs T4 |
|------|------|------|--------|-----------|---------------|-------------|
| sparse_clustered | 2048 | cube | 12 | 502 | 502 | 0.00% |
| dense | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| text | 16384 | cube | 27 | 5705 | 8126 | +42.44% |
| log_like | 16384 | cube | 53 | 7318 | 8510 | +16.29% |
| binary_mixed | 8192 | raw | 256 | 8205 | 8205 | 0.00% |
| random_high | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| sparse_small | 256 | raw | 4 | 269 | 269 | 0.00% |
| **Aggregate** | **51456** | | | **30217** | **33830** | **+11.96%** |

Aggregate ratio: **0.657455** vs T4 0.587240.

### G3_top2bits (4 groups — top-2 bits of raw byte)

| File | size | mode | n_dist | T4 actual | G-ctx clamped | delta vs T4 |
|------|------|------|--------|-----------|---------------|-------------|
| sparse_clustered | 2048 | cube | 12 | 502 | 552 | +9.96% |
| dense | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| text | 16384 | cube | 27 | 5705 | 8126 | +42.44% |
| log_like | 16384 | cube | 53 | 7318 | 9023 | +23.30% |
| binary_mixed | 8192 | raw | 256 | 8205 | 8205 | 0.00% |
| random_high | 4096 | raw | 256 | 4109 | 4109 | 0.00% |
| sparse_small | 256 | raw | 4 | 269 | 269 | 0.00% |
| **Aggregate** | **51456** | | | **30217** | **34393** | **+13.82%** |

Aggregate ratio: **0.668396** vs T4 0.587240.

### Context table counts (T4 vs grouped)

| File | n_dist | T4 n_ctx | G1 tables | G2 tables | G3 tables |
|------|--------|----------|-----------|-----------|-----------|
| sparse_clustered | 12 | 12 | 4 | 6 | 5 |
| dense | 256 | 136 | 6 | 9 | 5 |
| text | 27 | 27 | 3 | 3 | 3 |
| log_like | 53 | 53 | 6 | 5 | 3 |
| binary_mixed | 256 | 74 | 6 | 9 | 5 |
| random_high | 256 | 143 | 6 | 9 | 5 |
| sparse_small | 4 | 4 | 2 | 4 | 3 |

Grouped schemes do achieve fewer tables than T4 — as expected. But the header savings do not offset the bitstream degradation from context dilution.

---

## AC-3 — GO/NO-GO

**Verdict: NO-GO**

Best scheme (G1_ascii5) achieves aggregate ratio **0.650264** — **+10.73% worse** than T4 0.587240. No grouping scheme comes within the -2% improvement threshold required for GO. Not a single file in the corpus improves (on cube-stored files); raw-stored files are unchanged by construction.

### Mechanism: why grouped-context loses to T4

**(a) Header savings are modest.** Grouping reduces the number of tables from up to `n_distinct` to `n_groups` (3..8 in our tests). For `text` (n_distinct=27, T4 uses 27 tables), the header saving is `(27 - 3) × (2 + 27) = 696 bytes`. That is real, but small against the bitstream cost (T4 bitstream = ~5705 total — header is ~870 bytes, bitstream ~4835 bytes).

**(b) Context dilution dominates.** T4 has one Huffman table per distinct predecessor code. When predecessors are merged into a group, the resulting table must model an average of several distinct successor distributions. For `text`: after any lowercase letter, the successor distribution clusters around other lowercase letters and a few punctuation marks. After any uppercase letter, the distribution is different. G1's "letter" group (0) conflates these — the resulting Huffman table is a mixture, and every symbol's code length is suboptimal for any given predecessor. The per-token coding overhead grows with sequence length and far exceeds the header saving.

**(c) ASCII classes are irrelevant for binary files.** For `binary_mixed`, `random_high`, `dense`, and `sparse_small`, the file content has no ASCII semantic structure. The grouping provides zero correlation signal. Those files are also raw-stored already — the real encoder picked raw because even T4 cannot beat storage size. Grouping has no path to improvement here.

**(d) T4 is already the maximum-granularity order-1 scheme.** Using one context per distinct predecessor code is the finest possible order-1 partition (given the alphabet). There is no room for the grouped scheme to be MORE granular — only LESS granular. The trade-off (fewer tables + more observations vs coarser model) consistently favors T4's fine-grained partition for this corpus.

**Result:** per-code context T4 is at the trade-off optimum. Grouped context is Pareto-dominated: it sacrifices bitstream efficiency for header savings that are too small to compensate. This measurement closes the R5' hypothesis.

Phase B (Rust implementation) is **SKIPPED**. AC-4 is **n/a**.

---

## Follow-up candidates

- **R6 — order-2 context:** the natural next step in context-depth is `prev2_ctx + prev_ctx` as a 2D key. Header cost is quadratic in context count, but conditional entropy of the value stream under order-2 may justify it for moderate-alphabet files (text, log_like). Requires careful MIN_CTX_COUNT tuning to avoid sparse-context degradation.
- **BWT value-stream reorder (CUBR-0020):** already implemented on `feat/cubr-0020-bwt-prepass`, not yet merged. If merged into main, the new baseline changes; R5' should be re-evaluated against the BWT baseline if BWT is ever promoted.
- **Adaptive context threshold tuning:** T4 currently uses a fixed `MIN_CTX_COUNT=16`. A per-file adaptive threshold might squeeze a small additional gain for sparse-alphabet files.

---

*Probe: `docs/ephemeral/research/cubr_0025_grouped_context_probe.py`*  
*Bench JSON: `docs/ephemeral/research/CUBR-0025-bench.json`*  
*T4 Python twin: the **clamped whole-pipeline T4 aggregate is 30217 B / 0.587240**, matching the real Rust encoder and the CUBR-0023 archive. The pure-context-Huffman Python twin diverges absolutely per cube-file (e.g., text twin 6059 B vs actual 5705 B, +6.2%); it is used only for the within-model grouped/T4 ratio, where the absolute offset cancels. It is NOT byte-exact against the Rust encoder on a per-file basis.*
