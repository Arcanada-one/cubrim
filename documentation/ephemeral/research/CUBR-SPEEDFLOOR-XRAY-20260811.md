# CUBR-SPEEDFLOOR-XRAY-20260811 — preregistration: the one cell where the field looks reachable

**Committed to `main` BEFORE measurement.**

## Why this cell deserves better than the footnote it got

Across three CM2 cells the speed-floor work concluded the competitive field is unreachable by
optimisation: best cases 0.323 / 0.634 / 3.373 MiB/s, 7.6–79.6× short of ninth place. **`x-ray/max`
is the sole exception** — the only cell where P3 was ever refuted, at 65.26 MiB/s, which would place
cubrim *8th or better*.

That refutation was reported and then set aside in two sentences, on the grounds that its bound came
from a G3 cell flagged instrument-perturbed and that it measures the **geocm** rail rather than CM2.
Both grounds are true and neither justifies leaving it there. **If the geocm replay path really has
~50× headroom, it is the only route into the field this programme has measured**, and it sits on the
image class where cubrim's headline 1.71 MiB/s `d_max` already comes from. It deserves a direct test.

Two defects in the existing x-ray evidence are fixed here.

### Defect 1 — the number carrying the refutation is my least rigorous one

x-ray was measured in the **first** speed-floor pass, before interleaving was introduced. Its 6.880 s
came from a window where competitors had been measured ~40 minutes earlier at a different host load.
Every later cell used same-round interleaving precisely because that comparison is indefensible. The
one cell whose result contradicts the others is the one still resting on the discarded method.

### Defect 2 — the published bounds use two different set definitions

Re-deriving from the attribution's committed raw `symbols.tsv` shows the combined bounds are not
computed on a common basis:

| cell | Σ bucket family | shell | published combined | shell treatment |
|---|---:|---:|---|---|
| dickens/max | 93.310% | `cm2_decode_shell` 0.46% | **92.85%** → 13.986× | **excluded** |
| xml/max | 91.240% | `cm2_decode_shell` 0.58% | **90.66%** → 10.707× | **excluded** |
| x-ray/max | 98.200% | `geocm_decode` 0.16% | **98.20%** → 55.556× | **included** |

The CM2 rows are labelled "per-bit machinery" and the x-ray row "replay path", so the difference may
well be deliberate — but it means **55.556× and 13.986× are not like-for-like**, and the earlier P3
scoring compared them as if they were. On the CM2 cells' basis (shell excluded) x-ray is
98.04% → **51.020×**.

This lane reports **both** bases and lets neither pass silently.

## Ceiling, before measurement

x-ray is 8,474,240 B = 8.0817 MiB; landed pinned wall 6.200 s → implied **1.3035 MiB/s**.

| basis | bound | best case from the prior (weak) measurement |
|---|---:|---:|
| as published (shell included) | 55.556× | 65.26 MiB/s |
| consistent with CM2 cells (shell excluded) | 51.020× | 59.93 MiB/s |

Field markers: bzip2 **52.71** (8th), ppmd **25.69** (9th).

## Predictions (falsifiable)

- **P1 — calibrated transfer.** measured/implied falls in **[0.30, 1.00]**. *Refuted* outside. (Prior
  observations: 0.667× at load1 9.9–31.2, 0.343× at 40.5–60.0, 0.528× at 11.9–49.0.)
- **P2 — the image class is structurally different from text.** cubrim's same-round decode ratio
  against `xz -9` on x-ray is **< 100×**, versus 800× on dickens/web, 1256× on dickens/max and 2098×
  on xml/max. *Refuted* at ≥100×. This tests whether the enormous text gaps are a property of the CM2
  rail rather than of cubrim generally.
- **P3 — the refutation survives a proper measurement.** The perfect-path best case is **≥ 25.69
  MiB/s on both bases**. *Refuted* if either basis falls below. This is the decision-grade
  prediction: it asserts that the earlier refutation was real and not an artefact of the discarded
  non-interleaved method.
- **P4 — it clears eighth place too, on the consistent basis.** Best case on the shell-excluded
  51.020× basis is **≥ 52.71 MiB/s** (bzip2, 8th). *Refuted* below. P4 can fail while P3 holds; that
  outcome would say the geocm headroom reaches the field's lower rungs but not past bzip2.

## Method (fixed before running)

Identical harness to the dickens/web and xml cells, which is the point — the same-round interleaved
design that x-ray never received:

- **Binary**: the attribution's frozen commit `3a13f486` (sha256 `8947ea9b…`); behaviour equivalence
  checked by archive bytes against the landed x-ray figures (3,637,036 B, ratio 0.4291873).
- **Interleaved**: all seven tools decoded back-to-back within each of 3 rounds; the reportable
  quantity is the **median of same-round ratios**. Absolute MiB/s reported and labelled contaminated.
- **Competitors on the same host and pin**: xz -9, zstd -19, brotli -q11, gzip -9, bzip2 -9, lz4 -12.
- **Gates**: `cmp` **and** sha256 against the original before any timing row; a VOID aborts the cell.
- `systemd-run --scope MemoryMax=64G MemorySwapMax=0`, `taskset -c 0-15`, pin not widened.
- Ratio logged beside speed. Per-file only; x-ray is one file and stays one file.

## What this lane will NOT claim

It cannot repair the perturbation in the attribution's x-ray shares — that run recorded
G3 1.20161 against a ≤1.05 gate with cycle samples suppressed, and no measurement here changes those
recorded shares. If P3 holds, the correct conclusion is *"the geocm rail is the one measured path
with a plausible route into the field, on shares that are themselves instrument-perturbed"*, and the
thing that would settle it is a **clean, unperturbed attribution run on x-ray** — which is
NEW-24-adjacent work owned by PROGRAM, not this lane.

No encoder, wire format, preset, counter or `decode()` change. No candidate built, no lever selected.
No database write, no hypothesis row, no API, site or social action.
