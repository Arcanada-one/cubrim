# CUBR-0012 Compression Report

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
- **timestamp:** 2026-06-18T01:23:43Z
- **sweep-code commit:** 1303e72 (feat/cubr-0012-axis-sweep)

## Time-Series Results

### t1_v1_default — 2026-06-18T01:23:43Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=rle, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 1076 | 0.5254 | cube | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 10307 | 0.6291 | cube | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 12381 | 0.7557 | cube | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 41 | 0.1602 | 31 | 0.1211 | PASS |

### t2_packed_nibble — 2026-06-18T01:23:51Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=packed_nibble, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 1332 | 0.6504 | cube | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 10619 | 0.6481 | cube | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 12693 | 0.7747 | cube | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 41 | 0.1602 | 31 | 0.1211 | PASS |

### t3_n3_default — 2026-06-18T01:26:36Z

Config: raw_store_bound=320, b=256, N=3, gap_scheme=rle, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 1084 | 0.5293 | cube | 102 | 0.0498 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 10315 | 0.6296 | cube | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 12389 | 0.7562 | cube | 427 | 0.0261 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 8205 | 1.0016 | raw | 5241 | 0.6398 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 41 | 0.1602 | 31 | 0.1211 | PASS |

## Improvement Summary (T1 → T2)

### t1_v1_default → t2_packed_nibble

| Input | T1 CRatio | T2 CRatio | Delta |
|-------|-----------|-----------|-------|
| sparse_clustered | 0.5254 | 0.6504 | +0.1250 |
| dense | 1.0032 | 1.0032 | 0.0000 |
| text | 0.6291 | 0.6481 | +0.0190 |
| log_like | 0.7557 | 0.7747 | +0.0190 |
| binary_mixed | 1.0016 | 1.0016 | 0.0000 |
| random_high | 1.0032 | 1.0032 | 0.0000 |
| sparse_small | 1.0508 | 1.0508 | 0.0000 |

### t1_v1_default → t3_n3_default

| Input | T1 CRatio | T2 CRatio | Delta |
|-------|-----------|-----------|-------|
| sparse_clustered | 0.5254 | 0.5293 | +0.0039 |
| dense | 1.0032 | 1.0032 | 0.0000 |
| text | 0.6291 | 0.6296 | +0.0005 |
| log_like | 0.7557 | 0.7562 | +0.0005 |
| binary_mixed | 1.0016 | 1.0016 | 0.0000 |
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
