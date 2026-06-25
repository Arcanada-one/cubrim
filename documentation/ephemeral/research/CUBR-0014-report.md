# CUBR-0014 Entropy Value-Scheme Measurement Report

> PRIVATE — internal research artefact. Lives only in `docs/ephemeral/research/`.
> The algorithm mechanism is strictly secret — this file must not reach public surfaces.

## Environment

| Field | Value |
|-------|-------|
| Host | mac.tailb1f805.ts.net |
| OS | macOS-26.5.1-arm64-arm-64bit-Mach-O |
| Rust | rustc 1.96.0 (ac68faa20 2026-05-25) |
| Cargo | cargo 1.96.0 (30a34c682 2026-05-25) |
| Python | 3.14.4 |
| gzip | system gzip (macOS) |
| zstd | v1.5.7 |
| brotli | 1.2.0 |
| Sweep code SHA | ba62852 (feat/cubr-0014-value-stream-entropy) |
| Measurement date | 2026-06-18T09:53Z |

## Corpus

| Name | Size | SHA256 (first 16) |
|------|------|-------------------|
| sparse_clustered | 2048 | see manifest |
| dense | 4096 | see manifest |
| text | 16384 | see manifest |
| log_like | 16384 | see manifest |
| binary_mixed | 8192 | see manifest |
| random_high | 4096 | see manifest |
| sparse_small | 256 | see manifest |

## Results

### T1 — BitpackFixed (baseline)

Config: value_scheme=bitpack-fixed, gap_scheme=rle, b=256, raw_store_bound=320

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 1076 | 0.5254 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 10307 | 0.6291 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 12381 | 0.7557 | cube | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

Round-trip (all inputs): **PASS**

### T2 — RleCodes

Config: value_scheme=rle-codes, gap_scheme=rle, b=256, raw_store_bound=320

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 178 | 0.0869 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 16397 | 1.0008 | raw | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 16397 | 1.0008 | raw | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

Round-trip (all inputs): **PASS**

### T3 — Entropy (order-0 Huffman on value-code stream)

Config: value_scheme=entropy, gap_scheme=rle, b=256, raw_store_bound=320

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 936 | 0.4570 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 9304 | 0.5679 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 10169 | 0.6207 | cube | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 7849 | 0.9581 | cube | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

Round-trip (all inputs): **PASS**

## Comparative Summary (T1 → T3)

| Input | BitpackFixed | RleCodes | Entropy | gzip-9 | Entropy vs gzip delta |
|-------|-------------|----------|---------|--------|-----------------------|
| sparse_clustered | 0.5254 | 0.0869 | 0.4570 | 0.0752 | +0.3818 (gzip wins) |
| dense | 1.0032 | 1.0032 | 1.0032 | 1.0081 | −0.0049 (raw-store tie) |
| text | 0.6291 | 1.0008 | 0.5679 | 0.0790 | +0.4889 (gzip wins) |
| log_like | 0.7557 | 1.0008 | 0.6207 | 0.0262 | +0.5945 (gzip wins) |
| binary_mixed | 1.0016 | 1.0016 | 0.9581 | 0.6455 | +0.3126 (gzip wins) |
| random_high | 1.0032 | 1.0032 | 1.0032 | 1.0095 | −0.0063 (raw-store tie) |
| sparse_small | 1.0508 | 1.0508 | 1.0508 | 0.2539 | +0.7969 (gzip wins) |

> Negative delta = Cubrim-Entropy produces smaller output than gzip-9.
> Raw-store inputs: both Cubrim and gzip near 1.0 ratio — these are incompressible blocks.

## Ship Decision

**Entropy scheme is WIRED (stays in the codebase). Competition gate vs gzip-9 on {text, code}: NOT MET.**

- text (16384 bytes): Entropy 0.5679 vs gzip-9 0.0790 — gzip wins by 7.2×
- log_like (16384 bytes): Entropy 0.6207 vs gzip-9 0.0262 — gzip wins by 23.7×
- sparse_clustered (2048 bytes): Entropy 0.4570 vs gzip-9 0.0752 — gzip wins by 6.1×

Order-0 Huffman improves over BitpackFixed on structured inputs (text: 0.6291 → 0.5679, sparse: 0.5254 → 0.4570) but cannot close the gap to gzip. The root cause: gzip applies order-1 LZ77 back-references before Huffman coding, capturing repeated substrings that order-0 statistics cannot exploit. On text, the dominant compression is substring matching, not symbol-frequency skew.

**Entropy stays wired**: correct implementation, byte-exact round-trip on all inputs, improves over BitpackFixed, and forms the foundation for the next level of compression.

**Follow-up backlog item filed: CUBR-0015** — add order-1 context-adaptive Huffman (condition the code table on the previous code) or Arithmetic/ANS coding over the value-code stream as the next lever toward gzip-competitive ratios on text/code.

## Default Byte-Identity Proof

The 7 default `.python_blob` fixture files are byte-unchanged by this branch:

```
git status code/cubrim-rs/tests/fixtures/
?? code/cubrim-rs/tests/fixtures/text_entropy.input       (new — Entropy fixture)
?? code/cubrim-rs/tests/fixtures/text_entropy.python_blob  (new — Entropy fixture)
```

All 7 existing fixtures show no modifications. `cargo test --test differential` → 9/9.
