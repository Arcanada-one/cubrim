# CUBR-SPEEDFLOOR-XRAY-20260811 — results: the geocm route reaches ninth place, and stops there

**The refutation is real, and smaller than it was reported.** A proper interleaved measurement puts
the perfect-path best case at **41.7–45.4 MiB/s**, not the 65.26 previously recorded — enough to
clear ninth place, **not** enough to clear eighth.

P1, P2 and P3 hold; **P4 is refuted**. Prereg merged as `8d6eb51` at 19:42:45Z; measurement began
19:43:16Z.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | measured/implied in [0.30, 1.00] | outside refutes | **0.627** | **HOLDS** |
| **P2** | same-round ratio vs `xz -9` **< 100×** | ≥100× refutes | **23×** | **HOLDS** |
| **P3** | best case ≥ 25.69 on **both** bases | either below refutes | **45.40 / 41.69** | **HOLDS** |
| **P4** | consistent-basis best case ≥ 52.71 (bzip2, 8th) | below refutes | **41.69** | **REFUTED** |

## Fixing the weak number changed the answer by 44%

The prior x-ray figure came from the first pass, before interleaving existed. Re-measured with the
same same-round harness every other cell used:

| | prior (non-interleaved) | this run (interleaved) |
|---|---:|---:|
| cubrim decode | 6.880 s | **9.890 s** |
| throughput | 1.1747 MiB/s | **0.8172 MiB/s** |
| best case (published basis) | 65.26 MiB/s | **45.40 MiB/s** |

The only refutation in the entire speed-floor series was inflated by **44%** by the method it was
taken with. It survives correction — but the margin it survives by is much thinner, and that is
exactly why the weak cell was worth redoing rather than leaving as a footnote.

This run also had the **quietest** window of the series (load1 11.9–14.4), so the lower number is not
a contention artefact; measured/implied was 0.627, in line with the calibrated band.

## The two bound bases, and both answers

`bound_bases.py` regenerates this from the attribution's committed raw `symbols.tsv`:

| cell | Σ family | shell | incl → bound | excl → bound | published |
|---|---:|---:|---|---|---|
| dickens/max | 93.310% | 0.46% | 93.31 / 14.948× | **92.85 / 13.986×** | 92.85% / 13.986× **(excluded)** |
| xml/max | 91.240% | 0.58% | 91.24 / 11.416× | **90.66 / 10.707×** | 90.66% / 10.707× **(excluded)** |
| x-ray/max | 98.200% | 0.16% | **98.20 / 55.556×** | 98.04 / 51.020× | 98.20% / 55.556× **(included)** |

The CM2 rows are labelled "per-bit machinery" and the x-ray row "replay path", so the difference may
be deliberate — but the bounds are **not like-for-like**, and the earlier P3 scoring compared 55.556×
against 13.986× as though they were. Carrying both:

| basis | bound | best case | vs ppmd 25.69 (9th) | vs bzip2 52.71 (8th) |
|---|---:|---:|---|---|
| as published (shell incl) | 55.556× | **45.40 MiB/s** | clears | **short** |
| consistent with CM2 (shell excl) | 51.020× | **41.69 MiB/s** | clears | **short** |

**The conclusion is basis-independent**: ninth place is reachable in principle, eighth is not.

## Per-file measurement — x-ray, median of 3 interleaved rounds

| tool | setting | ratio | decode s | MiB/s | RSS KiB | same-round × vs cubrim |
|---|---|---:|---:|---:|---:|---:|
| lz4 | -12 | 0.847311 | 0.020 | 404.08 | 9,216 | 494× |
| zstd | -19 | 0.608403 | 0.070 | 115.45 | 11,904 | 141× |
| gzip | -9 | 0.712478 | 0.100 | 80.82 | 3,456 | 105× |
| brotli | -q11 | 0.552587 | 0.130 | 62.17 | 11,520 | 76× |
| xz | -9 | 0.529825 | 0.430 | 18.79 | 10,368 | **23×** |
| bzip2 | -9 | 0.478050 | 0.790 | 10.23 | 4,864 | **12×** |
| **cubrim** | **max** | **0.429187** | **9.890** | **0.817** | **89,856** | **1×** |

**P2 is the structural finding.** cubrim is 23× slower than `xz` here, against **800×** on
dickens/web, **1256×** on dickens/max and **2098×** on xml/max. The two-to-three-order-of-magnitude
text gaps are a property of the **CM2 rail**, not of cubrim as a product. On the image class it is
merely one order of magnitude behind — and 12× from bzip2.

Density holds as everywhere else: **no tool beats cubrim** (0.429187 vs bzip2's 0.478050). Decode RSS
is 87.8 MiB, in the same class as the web preset rather than `max`'s 10.5 GiB, because x-ray runs the
geocm rail.

## Where this leaves the speed branch

| cell | rail | best case | position if perfected |
|---|---|---:|---|
| xml/max | CM2 | 0.323 | 79.6× short of 9th |
| dickens/max | CM2 | 0.634 | 40.5× short of 9th |
| dickens/web | CM2 | 3.373 | 7.6× short of 9th |
| **x-ray/max** | **geocm** | **41.69–45.40** | **9th, above ppmd, below bzip2** |

The CM2 rail is unreachable at any effort. **The geocm rail is the only measured path into the field,
and perfecting it entirely buys ninth place out of ten** — a marginal position, not competitiveness.
A lever that captures a realistic fraction of that headroom lands below ninth.

## What this lane does not claim

- It cannot repair the perturbation in the attribution's x-ray shares. That run recorded
  **G3 1.20161** against a ≤1.05 gate with cycle samples suppressed, and no measurement here changes
  the recorded shares. The 98.20% therefore carries an instrument caveat that flows into both bounds.
  What would settle it is a **clean, unperturbed attribution run on x-ray** — NEW-24-adjacent work
  owned by PROGRAM, not this lane.
- The 25.69 / 52.71 field markers are cross-meta, not same-host. This cell is the one where that
  matters most, because 41.69 sits *between* them: the ninth-place conclusion is robust, but the
  exact placement would need same-host competitor figures at those operating points.
- One file, one preset, per-file only. No corpus aggregate.

No encoder, wire format, preset, counter or `decode()` change; no candidate built, no lever selected.
No database write, no hypothesis row, no API, site or social action.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-SPEEDFLOOR-XRAY-RESULTS-20260811
python3 bound_bases.py   # the two set definitions, from the committed raw symbols.tsv
python3 analyze.py       # every table above; refuses to print for an ungated decode
```

21 gated decode observations, 0 VOID.

---

## Amendment 2026-08-11 — the rank language in this report is cross-meta, not same-host

Every "ninth place" / "eighth place" phrase above is measured against ppmd **25.69 MiB/s** and bzip2
**52.71**, taken from `world_benchmark_timing_aggregate`. Those markers were later measured on this
host and **they do not transfer** (`CUBR-SAMEHOST-FIELD-RESULTS-20260811.md`): same-host on x-ray,
interleaved and gated, ppmd decodes at **1.84 MiB/s** (14× lower) and bzip2 at **8.73** (6× lower).

Cause: `d_max` is a **maximum over files**, so 25.69 is ppmd's *best* file while x-ray is near its
worst; host load compounds it. cubrim's own discrepancy is only 2.0× precisely because its `d_max`
sits on x-ray — the same leaderboard column means "this file" for cubrim and "some other file" for
every competitor, which is what made the comparison feel valid while being invalid.

**No figure in this report changes, and its conclusions hold — conservatively.** The same-host margin
is *larger*, not smaller (the geocm floor clears same-host ppmd by 15.3× rather than 1.09×). But read
every rank phrase above as **"against the cross-meta leaderboard"**, never as a same-host claim.
Stated same-host, a perfected geocm rail at the 28.1 MiB/s floor ranks **5th of the 8 tools measured
on x-ray** — behind lz4/zstd/gzip/brotli, ahead of xz/bzip2/current cubrim.
