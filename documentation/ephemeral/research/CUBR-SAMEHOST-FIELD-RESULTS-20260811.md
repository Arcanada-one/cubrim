# CUBR-SAMEHOST-FIELD-20260811 — results: the field markers do not transfer, and "ninth place" was the wrong frame

All three predictions hold. **P1 holds so emphatically that it invalidates the frame this whole
series has been using**: same-host ppmd on x-ray decodes at **1.84 MiB/s** against the cross-meta
**25.69** the series has been quoting — a **14× discrepancy**.

The geocm conclusion survives, with a far larger margin than before. But the *language* it was
stated in — "ninth place of ten" — is borrowed from a leaderboard that cannot be compared with
same-host per-file measurement, and this record retires it.

Prereg merged as `eee2e59` at 23:01:48Z; measurement began 23:02:11Z.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | same-host ppmd differs from 25.69 by >20% | ≤20% refutes | **1.84 → 92.8% lower** | **HOLDS** |
| **P2** | the 28.1 floor exceeds same-host ppmd | ppmd ≥28.1 refutes | **28.1 vs 1.84** | **HOLDS** |
| **P3** | same-host bzip2 beats same-host ppmd | else refutes | **8.73 vs 1.84** | **HOLDS** |

## Same-host measurement, x-ray, interleaved, 3 rounds

| tool | ratio | decode s | MiB/s | cross-meta `d_max` | discrepancy |
|---|---:|---:|---:|---:|---:|
| bzip2 -9 | 0.478050 | 0.926 | **8.73** | 52.71 | **6.0× lower** |
| 7z PPMd | 0.454471 | 4.398 | **1.84** | 25.69 | **14.0× lower** |
| cubrim max | 0.429187 | 9.482 | **0.85** | 1.71 | 2.0× lower |

Load 30.5–45.2 throughout; all three tools share every window, so the *ratios* are sound even though
the absolutes carry the usual load penalty.

The PPMd archive came out at ratio **0.454471** — the same figure already sitting in the landed
record for x-ray PPMd, which is a useful independent check that the tool was driven correctly.

## Why the markers do not transfer, and what that means

Two distinct effects, and they compound:

1. **`d_max` is a maximum over files.** ppmd's 25.69 is its *best* file; x-ray is an image, which is
   close to its worst. Comparing a per-file measurement against another tool's best-file maximum is
   not a comparison at all.
2. **Host load.** Everything measured here carries the 1.5–3× penalty this series has already
   characterised.

Note cubrim's own discrepancy is only 2.0× (1.71 → 0.85) because 1.71 *is* essentially its x-ray
number — its `d_max` happens to sit on this file. That asymmetry is precisely the trap: the same
leaderboard column means "this file" for cubrim and "some other file" for ppmd.

### The corrected frame

Against the seven tools measured same-host on x-ray, a perfected geocm rail at the **28.1 MiB/s
floor** would sit here:

| faster than the floor | slower than the floor |
|---|---|
| lz4 404.08, zstd 115.45, gzip 80.82, brotli 62.17 | xz 18.79, bzip2 10.23, cubrim 0.82 |

**Rank 5 of 8** on this file — not "ninth of ten". The two statements are not translations of each
other; they are measurements of different things, and this series mixed them.

## What this changes, and what it does not

**Does not change:** the geocm route is real, and perfecting it is worth several places on this
file. The floor now clears same-host ppmd by **15.3×** rather than the cross-meta 1.09×, so P2 is
not merely satisfied but unthreatened. The CM2 conclusion is untouched — no CM2 cell came near any
marker under either frame.

**Does change:** every "ninth place" / "eighth place" phrase in this series
(`CUBR-SPEEDFLOOR-RESULTS`, `-XML-`, `-WEB-`, `-XRAY-`, `CUBR-XRAY-ATTRIB-*`, and F21 in
`FINDINGS.md`) is stated against cross-meta `d_max` markers that do not transfer to same-host
per-file numbers. Those conclusions remain **directionally correct and conservatively so** — the
same-host margin is larger, not smaller — but the *rank language* should be read as "against the
cross-meta leaderboard", never as a same-host claim.

The honest form of the headline result:

> On x-ray, perfecting the geocm replay path moves cubrim from last of the tools measured on that
> file to roughly mid-field among them. Against the cross-meta leaderboard the same headroom reads
> as "at least ninth of ten". Both are true of different quantities, and neither licenses the other.

## Boundaries

One file, per-file only, no corpus aggregate. Competitor tools run as installed. Compression
durations are not measured quantities in this lane. No encoder, wire format, preset, counter or
`decode()` change; no candidate, no lever. No database write, no hypothesis row, no API, site or
social action. 9 gated decode observations, 0 VOID.
