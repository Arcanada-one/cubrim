# CUBR-0020-bwt Compression Report

> PRIVATE — internal research artefact. Lives only in docs/ephemeral/research/.
> Algorithm mechanism is strictly secret — this file must not reach public surfaces.

## Environment

- **host:** mac.tailb1f805.ts.net
- **os:** macOS-26.5.1-arm64-arm-64bit-Mach-O
- **python:** 3.14.4
- **rustc:** rustc 1.96.0 (ac68faa20 2026-05-25)
- **cargo:** cargo 1.96.0 (30a34c682 2026-05-25)
- **zstd:** *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***
- **brotli:** brotli 1.2.0
- **timestamp:** 2026-06-19T09:04:25Z
- **code_sha:** 794148d85631bc0e2f351e2178d3ab7e7911e137

## Time-Series Results

### t4_baseline — 2026-06-19T09:04:25Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=rle, value_scheme=entropy-context, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 502 | 0.2451 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 5705 | 0.3482 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 7318 | 0.4467 | cube | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

### t5_bwt_ec — 2026-06-19T09:04:29Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=rle, value_scheme=bwt-entropy-context, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 519 | 0.2534 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 3583 | 0.2187 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 5178 | 0.3160 | cube | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

### t5_auto — 2026-06-19T09:04:30Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=rle, value_scheme=auto, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 178 | 0.0869 | cube | 154 | 0.0752 | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 3583 | 0.2187 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 5178 | 0.3160 | cube | 430 | 0.0262 | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 7849 | 0.9581 | cube | 5288 | 0.6455 | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |

## Improvement Summary (T1 → T2)

### t4_baseline → t5_bwt_ec

| Input | T1 CRatio | T2 CRatio | Delta |
|-------|-----------|-----------|-------|
| sparse_clustered | 0.2451 | 0.2534 | +0.0083 |
| dense | 1.0032 | 1.0032 | 0.0000 |
| text | 0.3482 | 0.2187 | -0.1295 |
| log_like | 0.4467 | 0.3160 | -0.1306 |
| binary_mixed | 1.0016 | 1.0016 | 0.0000 |
| random_high | 1.0032 | 1.0032 | 0.0000 |
| sparse_small | 1.0508 | 1.0508 | 0.0000 |

### t4_baseline → t5_auto

| Input | T1 CRatio | T2 CRatio | Delta |
|-------|-----------|-----------|-------|
| sparse_clustered | 0.2451 | 0.0869 | -0.1582 |
| dense | 1.0032 | 1.0032 | 0.0000 |
| text | 0.3482 | 0.2187 | -0.1295 |
| log_like | 0.4467 | 0.3160 | -0.1306 |
| binary_mixed | 1.0016 | 0.9581 | -0.0435 |
| random_high | 1.0032 | 1.0032 | 0.0000 |
| sparse_small | 1.0508 | 1.0508 | 0.0000 |

> Negative delta = smaller output = better compression.

## Corpus Manifest (Generator Parameters)

| Name | Size | Seed | rho | SHA256 (first 16) |
|------|------|------|-----|-------------------|
| sparse_clustered | 2048 | 1001 | 0.0312 | d11533a77218a34e |
| dense | 4096 | 2001 | 0.0625 | a4ecb8ba6554b63d |
| text | 16384 | 3001 | 0.2500 | 0160b7a1b4311fa6 |
| log_like | 16384 | 4001 | 0.2500 | ac4ef48457503903 |
| binary_mixed | 8192 | 5001 | 0.1250 | 669a93863d0fab21 |
| random_high | 4096 | 6001 | 0.0625 | 0e232e8ae9db07cc |
| sparse_small | 256 | 7001 | 0.0039 | 8c23d37b2230be97 |
