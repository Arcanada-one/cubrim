# CUBR-XRAY-ATTRIB-20260811 — results: the geocm concentration is real; the ceiling built on it is not precise

**The 98.20% geocm share is not an instrument artefact.** An independent profile at a *lower*
perturbation reproduces it — and finds it slightly **higher**. The qualitative conclusion of the
speed branch stands.

**But the Amdahl ceiling derived from it is ill-conditioned**, and this run exposes that: the same
measurement family yields 51× or 88× depending on share differences of under one percentage point.
The route's *existence* is firm; its *size* is not.

P2, P3 and P4 hold. **P1 is refuted** — and the gate was not moved to fit it.

Prereg merged as `f18b8ea` at 22:22:03Z; measurement began 22:22:29Z.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | perturbation ≤ 1.05 | above refutes | **1.08705** | **REFUTED** |
| **P2** | total `geocm_*` ≥ 90% | below refutes | **98.99%** | **HOLDS** |
| **P3** | `decode_stream_mix` top and ≥ 70% | else refutes | **88.06%**, top | **HOLDS** |
| **P4** | best case clears ppmd 25.69 | below refutes | **72.32** | **HOLDS** |

### P1 refuted — a clean run was not achieved, only a cleaner one

| run | perturbation | gate |
|---|---:|---|
| G2/G3 attribution | 1.20161 | fails ≤1.05 |
| **this run**, `-F 99`, no call graph | **1.08705** | **fails ≤1.05** |

Halving the excess overhead was not enough. Per the preregistration, *"the gate is not moved to fit
the result"* — so the shares below are still **perturbed shares**, just less so. The frequency was
deliberately **not** retuned downward to chase a pass; that would be gate-shopping, and any such run
would need its own preregistration.

## The substantive answer: concentration is real, and the perturbation trend runs the *wrong way*

| bucket | s1 | s2 | s3 | median | landed (G2) |
|---|---:|---:|---:|---:|---:|
| `geocm::decode_stream_mix` | 88.06 | 88.06 | 88.19 | **88.06** | 84.53 |
| `geocm::Mixer::update` | 9.71 | 9.53 | 8.86 | **9.53** | 12.65 |
| `geocm::mix_ctxs` | 1.28 | 1.25 | 1.29 | **1.28** | 0.86 |
| `geocm::decode` (shell) | 0.12 | 0.12 | 0.00 | **0.12** | 0.16 |
| **total geocm** | | | | **98.99%** | **98.20%** |

Two profiles, taken on different hosts with different tooling and **different perturbation levels**,
agree that the geocm replay path is ~99% of x-ray decode and that a single symbol
(`decode_stream_mix`) is ~85–88% of it.

The decisive detail is the *direction*: the naive worry is that instrument overhead inflates the hot
symbol. **This run is less perturbed (1.087 vs 1.202) and reports a higher concentration (98.99 vs
98.20).** Overhead is therefore not inflating the concentration — if anything the landed 98.20%
*understates* it, and the true unperturbed value is ≥99%. The instrument caveat that
`CUBR-SPEEDFLOOR-XRAY-RESULTS-20260811.md` attached to its conclusion can be lifted in direction,
though not in precision.

## The ceiling is ill-conditioned, and that is the new finding

At these concentrations the Amdahl bound is extremely sensitive — `1/(1-s)` with `s ≈ 0.99`:

| source | shell-excluded share | bound | × measured 0.8172 MiB/s | field position |
|---|---:|---:|---:|---|
| landed G2 shares | 98.04% | 51.020× | **41.69 MiB/s** | 9th (above ppmd 25.69, below bzip2 52.71) |
| this run's shares | 98.87% | 88.496× | **72.32 MiB/s** | 8th (above bzip2 52.71) |

A **0.83 percentage-point** difference in share moves the ceiling by **73%** and shifts the predicted
field position by a rung. So the honest statement of the geocm route is a **range, not a number**:

> Perfecting the geocm replay path entirely buys somewhere between **ninth and eighth place** out of
> ten. It does not approach the leaders (zstd 809, lz4 1020 MiB/s), and no share measurement
> precise enough to pin the rung is available — nor would one change the conclusion that this is a
> marginal position, not competitiveness.

Prior lanes reported 41.69–45.40 as though the arithmetic were tight. It is not, and this record
corrects that impression. Any future work quoting an Amdahl ceiling above ~95% concentration should
publish the sensitivity alongside it.

## Method correction, recorded

The preregistration specified `perf record -F 99 --call-graph none`. This perf build rejects that
value (`Unknown --call-graph option value: none`, rc=129), and the first attempt produced **three
VOID gates in 8 ms each** — caught by the `cmp`+sha256 gates rather than silently recorded as
implausibly fast decodes. The flag was **dropped, not replaced**: `perf record`'s default records no
call graph, so the preregistered intent (no stack unwinding) is met exactly. Sampling frequency
stayed at `-F 99` as preregistered.

## Boundaries and voids

Read-only profiling of an existing binary. No encoder, wire format, preset, counter or `decode()`
change; no candidate built, no lever selected. No database write, no hypothesis row, no API, site or
social action.

`kernel.perf_event_paranoid` was changed 4 → 1 via `sudo -n` for this measurement and **restored to
4** afterwards (verified). It is a shared host; the change was temporary and is recorded here. The
prior lane deferred this measurement believing `paranoid=4` made it impossible — that was an
unverified assumption, and re-probing it is what made this record possible.

- **A gate-passing profile (≤1.05) has still never been taken on x-ray.** Reaching it would need a
  lower sampling frequency or a lighter instrument, under its own preregistration. Until then every
  x-ray share in the record — landed and this one — is perturbed.
  **CLOSED 2026-08-11** by `CUBR-XRAY-ATTRIB-CLEAN-RESULTS-20260811.md`: perturbation **1.00533** at
  `-F 25`, geocm 98.36%, `decode_stream_mix` 86.38%. Precision was recovered by *repetition* rather
  than frequency (12 runs pooled -> +/-1.20 pp, better than this report's single `-F 99` run). Three
  profiles at 1.202 / 1.087 / 1.005 agree, so the instrument caveat is retired. Note the follow-up
  also found the ceiling **unmeasurable from above** — quote only the floor (>=28.1 MiB/s, ninth
  place), never the point estimates in this report.
- The 25.69 / 52.71 field markers remain cross-meta, not same-host, and the ninth-vs-eighth
  distinction sits exactly between them.
- One file, one preset. Per-file only.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-XRAY-ATTRIB-RESULTS-20260811
cat timings.tsv          # plain vs instrumented walls, with gates
cat symbols-sample*.txt  # perf report output per sample
```

`perf` requires `kernel.perf_event_paranoid <= 1`; it is 4 by default on this host.

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
