# h25k-tuned Compression Report

> PRIVATE — internal research artefact. Lives only in documentation/ephemeral/research/.
> Algorithm mechanism is strictly secret — this file must not reach public surfaces.

## Environment

- **host:** arcana-dev
- **os:** Linux-6.8.0-106-generic-x86_64-with-glibc2.39
- **python:** 3.12.3
- **rustc:** rustc 1.96.0 (ac68faa20 2026-05-25)
- **cargo:** cargo 1.96.0 (30a34c682 2026-05-25)
- **zstd:** *** Zstandard CLI (64-bit) v1.5.5, by Yann Collet ***
- **brotli:** brotli 1.1.0
- **code_sha:** 01617c8cf376fa24ffc6755b8cbcbe2e9391e454-dirty
- **timestamp:** 2026-06-24T12:00:03Z

## Time-Series Results

### t1_v1_default — 2026-06-24T12:00:03Z

Config: raw_store_bound=320, b=256, N=minimal, gap_scheme=rle, value_scheme=bwt-rans, use_square_limit=True

Round-trip (all inputs): **PASS**

| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |
|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|
| sparse_clustered | 2048 | 169 | 0.0825 | cube | 154 | 0.0752 | 105 | 0.0513 | 87 | 0.0425 | PASS |
| dense | 4096 | 4109 | 1.0032 | raw | 4129 | 1.0081 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| text | 16384 | 1525 | 0.0931 | cube | 1295 | 0.0790 | 1234 | 0.0753 | 1194 | 0.0729 | PASS |
| log_like | 16384 | 557 | 0.0340 | cube | 430 | 0.0262 | 426 | 0.0260 | 379 | 0.0231 | PASS |
| binary_mixed | 8192 | 5330 | 0.6506 | cube | 5288 | 0.6455 | 5238 | 0.6394 | 4803 | 0.5863 | PASS |
| random_high | 4096 | 4109 | 1.0032 | raw | 4135 | 1.0095 | 4110 | 1.0034 | 4101 | 1.0012 | PASS |
| sparse_small | 256 | 269 | 1.0508 | raw | 65 | 0.2539 | 41 | 0.1602 | 31 | 0.1211 | PASS |
| both_sparse_16 | 16 | 29 | 1.8125 | raw | 55 | 3.4375 | 29 | 1.8125 | 21 | 1.3125 | PASS |
| both_sparse_24 | 24 | 37 | 1.5417 | raw | 64 | 2.6667 | 37 | 1.5417 | 29 | 1.2083 | PASS |
| block_bound_runs | 65536 | 2389 | 0.0365 | cube | 3072 | 0.0469 | 2795 | 0.0426 | 2188 | 0.0334 | PASS |

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
| both_sparse_16 | 16 | 8001 | 0.0002 | 84c92eca52cc2721 |
| both_sparse_24 | 24 | 8002 | 0.0004 | ba3a1f0d984b4502 |
| block_bound_runs | 65536 | 8003 | 1.0000 | abcb2d5a7ea6c1e7 |
