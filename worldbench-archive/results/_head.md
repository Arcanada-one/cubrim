# CUBR-0034 — World Benchmark: Cubrim vs Standard Archivers

**Stage:** research / benchmark · **Date:** 2026-06-25 · **Code SHA:** `317a323` (`317a32337b5e327768cd3a50747b38400539b888`)
**Host:** AMD Ryzen 5 3600 (12 threads), Linux 6.8.0-106 · **Cubrim:** competitive built-in scheme selection (default).

## Method (lzbench-style)

- **Metric:** `ratio = compressed / original` — **lower is better** (consistent with Cubrim's internal reports; `<1` = compression, `>1` = expansion).
- **Round-trip:** byte-exact (`cmp`) decompression verified for **every** Cubrim file — **24/24 RT OK**. Standard tools trusted as mature.
- **Corpora:** Silesia (12 files, all data types), enwik8 (95 MB text), Canterbury (11 files).
- **Archivers & settings:** cubrim (competitive), `gzip -9`, `bzip2 -9`, `xz -9e`, `zstd --ultra -22`, `brotli -q 11`, `lz4 -12` (built from v1.9.4), `ppmd` (`7z -m0=PPMd`). `zpaq` not available on host (optional max-ratio reference — omitted, marked honestly).
- **Note on PPMd size:** the `ppmd` column is the `.7z` container size (PPMd is only exposed via 7z); container header overhead is a few hundred bytes — negligible on MB-scale files, but it slightly penalises PPMd on the tiny Canterbury files.

## Headline

Across all 24 files (sum-bytes), Cubrim places **5th of 8** — it **beats `bzip2`, `gzip`, `lz4`** and trails `ppmd`, `xz`, `brotli`, `zstd`. On every sizable file (≥1 MB) Cubrim ranks **#3–#6, never last**. Its only outright failures are on **small inputs (<40 KB)**, where fixed per-file overhead dominates — including one expansion (`sum`, 37 KB → ratio 1.0003).

This is an honest mid-pack result for a research codec with no machine-code, image, or structured-binary specialisation yet — and the gaps map cleanly onto the **candidate hypotheses** below, which is the point of this benchmark: it tells the continuous loop *what is left to take*.

## Results

