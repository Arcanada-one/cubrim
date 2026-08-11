# Cubrim Compression Leaderboard

**Generated:** 2026-06-21 23:49 UTC

## Win Target

Beat gzip -9 aggregate on the frozen 10-file corpus.

| Archiever | Aggregate Ratio | Status |
|-----------|-----------------|--------|
| **gzip -9** | 0.159674 | Target |
| **xz -9**   | 0.162998 | Target |
| **Cubrim (current best)** | 0.299337 | BEHIND |

**Gap to gzip win:** +0.139663 (current best 0.299337 vs target 0.159674)

## Current Best

| Field | Value |
|-------|-------|
| Scheme | `BwtEntropy` |
| Aggregate | **0.299337** |
| Code SHA | `e476294879f8...` |
| Corpus SHA256 | `8e6cf6a743d0ff58...` |
| Run Log Ref | `CUBR-0028-bench` |

### Per-File Baseline (non-regression bound for AC-5 gate)

| File | Raw Bytes | BWT Bytes | T4 Bytes | Best |
|------|-----------|-----------|----------|------|
| sparse_clustered | 2048 | 502 | 502 | **502** |
| dense | 4096 | 4109 | 4109 | **4109** |
| text | 16384 | 3583 | 5705 | **3583** |
| log_like | 16384 | 5178 | 7318 | **5178** |
| binary_mixed | 8192 | 8205 | 8205 | **8205** |
| random_high | 4096 | 4109 | 4109 | **4109** |
| sparse_small | 256 | 269 | 269 | **269** |
| both_sparse_16 | 16 | 29 | 29 | **29** |
| both_sparse_24 | 24 | 37 | 37 | **37** |
| block_bound_runs | 65536 | 9011 | 9011 | **9011** |

## Run History

| Run ID | Date | Scheme | Aggregate | vs T4 | vs gzip | vs xz | Verdict | Merged |
|--------|------|--------|-----------|-------|---------|-------|---------|--------|
| `CUBR-0028-bench` | 2026-06-18 | BwtEntropy | 0.504412 | -0.082828 | +0.344738 | +0.341414 | **GO** | yes |

## Corpus (frozen)

10 files, 117032 raw bytes total. Manifest SHA256: `8e6cf6a743d0ff58f7666484...`

---
_This file is auto-generated from `documentation/leaderboard/cubrim-leaderboard.json`._
_Do not edit manually — run `gen-leaderboard-md.sh` to regenerate._
