# CUBR-SPEEDFLOOR-20260811 — preregistration: can optimising CM2 ever make cubrim speed-competitive?

**Committed to `main` BEFORE any measurement.** The ceiling below is derived from *landed* evidence
(the G2 decode attribution) and arithmetic, not from the numbers this lane is about to take.

## Lane claim — coordination, so two lanes do not duplicate

PROGRAM holds **NEW-24** (Fast-CM time-budgeted tier ladder), currently at generation G6
(`NO-ATTEMPT/NO-SELECT`, terminated in prebuild on a `Cargo.lock` determinism issue). **This lane does
not enter NEW-24, does not build a candidate, and does not select a lever.** It asks a prior question
that NEW-24's own framing assumes an answer to:

> Is the CM2 decode path optimisable *into* the competitive field at all, or does the speed branch
> require not running CM2 at that operating point?

If the answer is "no", NEW-24's premise — that speed must come from a cheaper rail rather than a
faster CM2 — is established rather than assumed. That is support for PROGRAM's lane, not a duplicate
of it.

## What is already characterised, and the gap this lane fills

The mandate asks that the 1.71 MiB/s be characterised before anything is proposed. The G2 attribution
(`CUBR-DECODE-ATTRIB-RESULTS-20260809.md`) did that at the symbol level and is not repeated here:

| cell | `predict_bit` | `Ctr::upd` | named CM2 machinery | combined outer bound |
|---|---:|---:|---:|---:|
| dickens/max | 49.72% | 32.81% | 92.85% | **13.986×** |
| xml/max | 50.01% | 29.42% | 90.66% | **10.707×** |
| dickens/web | 54.32% | 32.40% | (per-component table) | — |
| x-ray/max | `decode_stream_mix` 84.53% | — | 98.20% (geocm path) | **55.556×** (G3 perturbed) |

That report states plainly that it "does not establish benchmark throughput". **That is the gap.**
Symbol shares alone cannot answer whether the field is reachable, because reaching the field is a
statement about MiB/s, not about percentages.

### A reconciliation the record does not yet contain

The mandate quotes cubrim at **1.71 MiB/s** `d_max` from `world_benchmark_timing_aggregate`. The
attribution's own pinned wall times imply something very different per file:

| cell | file MiB | plain wall s | implied MiB/s |
|---|---:|---:|---:|
| dickens/max | 9.7202 | 142.860 | **0.0680** |
| xml/max | 5.0977 | 58.000 | **0.0879** |
| dickens/web | 9.7202 | 105.710 | **0.0920** |
| x-ray/max | 8.0817 | 6.200 | **1.3035** |

`d_max` is a **maximum over files**. cubrim's headline speed is its *best* file — an image on the
geocm rail — while text on the CM2 rail runs roughly **19× slower than that headline**. Any statement
of the form "cubrim is 15× behind ninth place" is therefore true only of cubrim's best case; on text
the gap is far larger. This lane measures it rather than asserting it.

## Ceiling, derived from mechanism and landed shares

Amdahl on the landed combined bounds, applied to the landed per-file wall rates:

| cell | implied MiB/s | × combined bound | **perfect-CM2 best case** |
|---|---:|---:|---:|
| dickens/max | 0.0680 | 13.986 | **0.951 MiB/s** |
| xml/max | 0.0879 | 10.707 | **0.941 MiB/s** |

Ninth place in the field is ppmd at **25.69 MiB/s**; eighth is bzip2 at 52.71.

So the preregistered ceiling is stark: **driving every named CM2 component to zero cost still leaves
text decode below 1 MiB/s** — below cubrim's own 1.71 MiB/s headline, and ~27× below ninth place.
The combined bounds are, in the attribution's own words, "impossible whole-path bounds, not promised
speedups"; the real ceiling is lower still.

## Predictions (falsifiable, committed before measurement)

- **P1 — the profiling wall rate transfers to real throughput.** Measured cubrim decode throughput on
  `dickens/max`, gated and pinned, lands within 2× of the attribution-implied 0.0680 MiB/s
  (i.e. 0.034–0.136 MiB/s). *Refuted* outside that band — which would mean profiling wall and
  benchmark throughput are not interchangeable and the attribution's numbers cannot be projected.
- **P2 — the same-host gap on text is far worse than the headline 15×.** cubrim's decode throughput on
  dickens is **≥100×** slower than `xz -9` decoding the same file on the same host and pin.
  *Refuted* below 100×.
- **P3 — the decisive one: the field is unreachable by CM2 optimisation.** For every measured cell,
  (measured throughput × that cell's landed combined outer bound) stays **below ppmd's 25.69 MiB/s**.
  *Refuted* if any cell's perfect-CM2 best case reaches 25.69 MiB/s.

P3 is the decision-grade prediction. If it holds, optimising the CM2 decode path is not a route into
the field at any effort, and the speed branch's only live direction is a different rail or operating
point — which is what NEW-24 already targets.

## Method (fixed before running)

- **Binary:** built from the attribution's own frozen source commit `3a13f486`, so the landed
  per-file Amdahl bounds apply to *this* binary rather than being mixed across commits. Binary sha256
  recorded in provenance.
- **Cells:** `dickens/max` (text, the cleanest landed ceiling) and `x-ray/max` (image, cubrim's best
  class and the likely origin of the 1.71 headline). Per-file only — no corpus aggregate, and no
  corpus-wide average speedup, ever.
- **Competitors, same host, same pin, same files:** xz, zstd, brotli, gzip, bzip2, lz4 at their
  strong settings. Run here rather than read from a cross-meta table, so the comparison is
  same-host by construction and does not depend on the operating-point/timing-aggregate confusion the
  mandate flagged.
- **Both sides of the trade recorded.** Compression ratio is logged for every tool on every file
  alongside speed. A faster competitor at a worse ratio is not the same operating point, and this
  record will not let the two be read as one number.
- **Gates before measurement:** every decode output verified byte-exact against the original by both
  `cmp` **and** sha256. Any mismatch voids that cell. Archives are sha256-recorded on creation.
- **Resource discipline:** every compress/decode runs under
  `systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0`, pinned with `taskset -c 0-15`.
  The pin stays 0-15; it is not widened.
- **Timing honesty:** host load is logged throughout. If load is high, wall-derived throughput is
  reported as contaminated and the *ratio between tools measured in the same window* is the reportable
  quantity, not the absolute MiB/s. Compression duration is not a measured quantity in this lane.
- Decode is repeated 3× per cell per tool; the median is reported with all samples retained.

## Boundaries

No encoder, wire format, preset, counter or `decode()` change. No candidate is built and no lever is
selected — selection is NEW-24's, not this lane's. No database write, no API, site, or social action.
`evaluation` stays 0 and no hypothesis row is opened or closed.
