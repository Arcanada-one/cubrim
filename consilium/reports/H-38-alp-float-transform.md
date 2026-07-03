# H-38 — ALP-style decimal-float→int transform for numeric float columns

**Status:** PLANNED (research candidate, round-2 ladder). No Cubrim measurement yet — numbers below are literature estimates.

**Class targeted:** floating-point telemetry columns (forex/price/sensor CSV). Stacks on H-29/H-30 columnar field-split. H-29 already flipped numeric telemetry to crush zstd by 27–31% via transposition; this attacks the residual float-mantissa entropy the integer path leaves on the table.

## Hypothesis

Encoding decimal-representable float columns as `(integer = value × 10^e, exponent e stored once, exception list for the rest)` before the `bwt-rans` backend reduces the column's compressed size, because it replaces incompressible IEEE-754 mantissa noise with low-magnitude integers the FOR+rANS path codes near entropy.

## Why it might help (mechanism)

Most real-world doubles are decimals (`1.0938`, `42.50`), exactly representable as `int × 10^-e` with a small per-column `e`. The integer stream is smooth and low-magnitude → Frame-of-Reference + rANS code it tightly, where the raw IEEE-754 bytes are near-random in the mantissa. Reversible: store `e` plus a verbatim exception list for non-decimal-representable values.

## Expected lever (estimate — NOT a Cubrim measurement)

- ALP (SIGMOD 2024) is float SOTA on ratio AND 1–2 orders of magnitude faster than Chimp/Gorilla/Patas/Elf.
- **Honest caveat from the literature:** Gorilla/Chimp128/Elf float coders do NOT beat zstd on ratio standalone. So the value here is ALP as a reversible FRONT-END transform feeding Cubrim's BWT+geomix/rANS — never as a standalone coder.

## Mandatory gate (charged probe — faithful, info-conservation-safe per Gotcha #7)

1. Detect decimal-representable float columns in `forex_*` / `status_timeseries`.
2. ALP-encode, run `bwt-rans`, compare vs the H-29 columnar baseline (real codec on transformed bytes).
3. Charge the 16-B header + per-column `e` + **the exception list as a MANDATORY decoder branch** — non-decimal values stored verbatim. Omitting it reproduces the φ-map false-GO (Gotcha #7).
4. Competitive `min(base, alp)` per column.

## Refs

- ALP: Adaptive Lossless Floating-Point Compression, Afroozeh & Boncz, ACM SIGMOD 2024 — https://dl.acm.org/doi/10.1145/3626717 ; code https://github.com/cwida/ALP ; DuckDB writeup https://duckdb.org/science/alp/
- Chimp, VLDB 2022 — https://www.vldb.org/pvldb/vol15/p3058-liakos.pdf
- Pcodec (binning numerical compressor).

## Measured

_Pending — to be filled by the implementing session with cubrim vs gzip-9 vs zstd-19, RT result, and code SHA._

## Verdict

_Pending._
