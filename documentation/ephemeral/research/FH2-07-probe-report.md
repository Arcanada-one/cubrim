# FH2-07 typed-field submodel — 1 MiB margin screen

**Verdict:** `SCREEN GO, DEFERRED` — the charged typed model improved the
paired byte-record baseline by **2.349052%**, but binary is already rank #1 in
the live authoritative aggregate.  Per the operator's priority correction, no
full-`sao` run and no Rust/FH-10 integration were performed.

## Method

- Exact source: `/root/corpus-full/silesia/sao`, 7,251,944 bytes, SHA-256
  `c2d0ea2cc59d4c21b7fe43a71499342a00cbe530a1d5548770e91ecd6214adcc`.
- Screen: first 1,048,576 bytes, SHA-256
  `ac3e75948e2d88287758dd1e22bbe3ba45d92595b393202e300374a45559bc26`.
- Detected `W=28`; schema was chosen on the first 512 records by charged
  prequential cost.  It contained 14 contiguous fields: 6 `u8`, 6 `u16le`,
  1 `u32le`, and 2 `f32le`.
- Both candidates used the same deterministic 32-bit binary arithmetic coder
  and adaptive `(1,1)` counts.  Baseline context was record offset + previous
  same-offset byte + partial-bit prefix.  Typed context used only completed
  prior-record values/deltas and already decoded lower bytes of the current LE
  field.  Raw byte order was unchanged.
- Typed paid the transmitted schema: 14 extra header bytes.

## Exact result

| Variant | Payload | Header | Charged | Ratio | Contexts | RT |
|---|---:|---:|---:|---:|---:|---|
| byte baseline | 693,071 | 17 | **693,088** | 0.660980225 | 693,383 | `cmp=0` |
| typed delta/carry | 676,776 | 31 | **676,807** | 0.645453453 | 140,413 | `cmp=0` |

Delta: **-16,281 bytes / -2.349052%** versus the paired baseline.  The
pre-registered 1.5% screen threshold was crossed.  Wall time was 1:53.70,
maximum RSS 178,228 KiB.  A separate post-run decode of both charged archives
matched the screen source byte-for-byte; all three SHA-256 values were
`ac3e75948e2d88287758dd1e22bbe3ba45d92595b393202e300374a45559bc26`.

## Decision boundary

This is evidence that value-level typed contexts have reserve on `sao`; it is
not a codec or authoritative benchmark result.  It is deliberately not called
a research champion and was not extrapolated to full `sao`.  With binary
already #1 (`cubrim 0.46645` versus `7z 0.53775` in the live per-type
aggregate), the remaining build-axis priority is EXE.  FH2-07 is parked as a
measured integration option if binary margin later becomes strategically
useful.

No PPMd, Opus-axis, core, DB, site, or deployed codec file was changed.
