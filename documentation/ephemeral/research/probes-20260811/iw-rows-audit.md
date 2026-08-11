# Audit: stale in_progress IW rows vs current main + meta-36 (2026-08-11)

Adjudicated on already-measured data (source @ main, meta-36 standings,
CUBR-0087 FINDINGS) — no new runs.

## IW-01 (MED16 auto-width) — DONE, closing as shipped
The row's goal ("автодетект ширины + лестница кандидатов за competitive-min")
is implemented on main: `med16_detect_width` (codec.rs:2754) feeds a candidate
ladder {detected, 256, 512, 1024, 2048, 4096} × {plain, FH3-09 bias} under
strict competitive-min (codec.rs:2810-2830). Targets achieved at meta-36:
mr 0.20776 #1, x-ray 0.42919 #1. The image class is closed systemically, as
the row demanded.

## IW-03 (tiny text/code) — SUPERSEDED, closing
Every cited deficit is inverted at meta-36: xargs.1 0.38018 vs ppmd 0.38088
(leads), grammar.lsp 0.30207 vs brotli 0.30234 (leads), fields.c 0.23049 vs
brotli 0.24368 (leads), cp.html 0.26720 vs ppmd 0.27200 (leads). Cause: the
≤64 KB path was opened to whole-file CM2 (codec.rs, "single largest
small-file lever, measured −57..−76%"). The dedicated tiny-branch this row
proposed is moot; NEW-19/20 remain the open rows for any residual tiny-file
work.

## IW-06 (bwt-rans throughput) — RELOCATED, closing
The row's own corrected note (CUBR-0087 ↔ CUBR-0092) already records the
measured relocation: bwt-rans is not the throughput limit; the two real cost
centres are the CM2 column sweep (text band) and the discarded cube/BWT
candidate path (transform-won files). The one open measurement it names —
NEW-25 branch-and-bound encode speedup on image/binary — belongs on NEW-25
(status implemented-gated-full-scale) and is recorded there by reference.
