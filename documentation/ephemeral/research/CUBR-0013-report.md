# CUBR-0013 Per-Block Value-Scheme Measurement Report

> PRIVATE — internal research artefact. Lives only in documentation/ephemeral/research/.
> Algorithm mechanism is strictly secret — this file must not reach public surfaces.

## Environment

- **host:** mac.tailb1f805.ts.net
- **os:** macOS-26.5.1-arm64-arm-64bit-Mach-O
- **rustc:** rustc 1.96.0 (ac68faa20 2026-05-25)
- **cargo:** cargo 1.96.0 (30a34c682 2026-05-25)
- **timestamp:** 2026-06-18T03:00:00Z
- **branch:** feat/cubr-0013-value-stream-cleanup
- **HEAD commit (D3 measurement):** a5ce2ba

## Purpose

This report documents the D3 exploratory measurement from CUBR-0013: does a
per-block (chunked) value encoding scheme help inputs that fall to raw-store or
lose compression under a whole-stream run-encoding value scheme (e.g. text,
log_like), without regressing inputs that benefit from it (e.g. sparse_clustered)?

The question arose from CUBR-0012 results: whole-stream RleCodes cut
sparse_clustered dramatically (1076 → 72 bytes at default config) but text and
log_like expanded past raw-store threshold. The hypothesis was that splitting the
value stream into fixed-size chunks and applying run-encoding per chunk might
preserve short local runs in inputs where the global value sequence is not
run-heavy.

## Measurement: chunk_size = 64

The table below shows encoded sizes (bytes) for each input under four conditions:
raw store (no compression applied), bitpack-fixed (whole-stream, CUBR-0012 default),
whole-stream RleCodes (shipped in CUBR-0012), and per-block RleCodes with
chunk_size=64.

| Input | raw | bitpack-fixed | rle-codes (whole-stream) | rle-codes (chunk64) |
|-------|-----|---------------|--------------------------|---------------------|
| text_1kb | 1024 | 707 | 1037 | 1037 |
| random_1kb | 1024 | 1037 | 1037 | 1037 |
| sparse_clustered | 2048 | 816 | 72 | 72 |
| log_like | 1024 | 710 | 1037 | 1037 |
| small raw-store inputs (raw-bound) | — | raw | raw | raw |

Round-trip (all inputs): **PASS** (lossless, no data loss at any chunk size tested).

## Ship / No-Ship Decision: NOT SHIPPED

Per-block chunked RleCodes produces byte-identical output to whole-stream RleCodes
on every input. This is a by-construction result, not a corpus coincidence:

**Proof sketch.** A run at position i across the full value sequence either:
(a) fits entirely within one chunk → the run is encoded identically in both modes.
(b) spans a chunk boundary → the boundary forces an artificial run break, producing
    two or more triplets where the whole-stream encoder would produce one.

In case (b), the per-block encoder can only ADD triplets relative to the
whole-stream encoder — it never removes them. Therefore chunk_size ≥ rle_size
for any chunk_size and any input sequence. There is no chunk boundary size that
recovers the whole-stream optimum for a run spanning that boundary.

For inputs like text and log_like where the value sequence has no long runs
in index order, neither scheme achieves run-length gain; both correctly fall
back through the raw-store guard. Windowing does not manufacture runs.

**Conclusion:** per-block chunked run-encoding cannot outperform whole-stream
run-encoding; it can only match or lose. Since whole-stream RleCodes already
shipped in CUBR-0012 (sparse_clustered: 816 → 72 bytes), the per-block variant
adds complexity with no compression benefit. Decision: NOT SHIPPED. This is a
valid AC-3 outcome ("measured, no improvement, not shipped").

## Corpus Manifest (Generator Parameters)

| Name | Size | Seed | rho | SHA256 (first 16) |
|------|------|------|-----|-------------------|
| sparse_clustered | 2048 | 1001 | 0.0312 | d11533a77218a34e |
| text_1kb | 1024 | 3001 | 0.2500 | (subset of text corpus) |
| random_1kb | 1024 | 6001 | 0.0625 | (subset of random corpus) |
| log_like | 1024 | 4001 | 0.2500 | (subset of log corpus) |
