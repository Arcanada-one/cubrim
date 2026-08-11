# CUBR-XRAY-ATTRIB-CLEAN-20260811 — preregistration: a gate-passing x-ray profile, with honest error bars

**Committed to `main` BEFORE measurement.**

## The void this closes

`CUBR-XRAY-ATTRIB-RESULTS-20260811.md` closed with one statement outstanding:

> A gate-passing profile (≤1.05) has still never been taken on x-ray. Reaching it would need a lower
> sampling frequency or a lighter instrument, **under its own preregistration**. Until then every
> x-ray share in the record — landed and this one — is perturbed.

This is that preregistration. The earlier lane deliberately refused to retune frequency after seeing
its 1.08705 result, because choosing a frequency to make a gate pass, after the fact, is
gate-shopping. Declaring the ladder in advance and reporting every rung is not.

## The tension this design exists to resolve

Passing the ≤1.05 perturbation gate requires a **lower** sampling frequency. But the quantity being
measured is a concentration near 0.99, and the Amdahl bound `1/(1-s)` amplifies error there
savagely:

| concentration | bound |
|---|---:|
| 97.87% | 46.9× |
| 98.87% | 88.5× |
| 99.87% | 769.2× |

So fewer samples do not merely blur the answer — at this concentration they destroy the ceiling's
determinacy. A single 8 s decode gives:

| frequency | samples | 95% CI on an ~88% symbol |
|---|---:|---|
| `-F 99` | ~792 | ±2.3 pp |
| `-F 25` | ~200 | ±4.5 pp |
| `-F 10` | ~80 | ±7.1 pp |

**Resolution: keep the frequency low and repeat the run.** Overhead is a per-run property; sample
count accumulates across runs. `-F 25 × 12 runs` yields ~2400 samples — a ±1.30 pp CI, *better* than
the refuted `-F 99` single run, while each individual run stays light enough to have a chance at the
gate.

## Method (fixed before running)

- **Frequency ladder, declared in advance**: `-F 25` first. If its perturbation exceeds 1.05, `-F 10`
  is run as the second rung. **Every rung attempted is reported**, pass or fail — nothing is dropped
  for being inconvenient.
- **12 instrumented runs** per rung, aggregated to one sample pool; **3 plain runs** for the baseline.
- **Perturbation ratio** = median instrumented wall / median plain wall, against **≤1.05**.
- **Shares** pooled across the 12 runs, with a **95% binomial CI** on the top symbol, and the bound
  reported as an **interval** derived from that CI — not a point estimate. This is the direct
  response to the ill-conditioning the prior lane found.
- Binary `8947ea9b…` (commit `3a13f486`), same x-ray archive (3,637,036 B, ratio 0.429187).
- `perf record -F <rung>` with **no** `--call-graph` flag (this perf build rejects `none`; the default
  already records no call graph — the correction the prior lane documented).
- `cmp` **and** sha256 on every decode before its timing is recorded; a VOID gate aborts the rung.
- `taskset -c 0-15`, pin not widened. `kernel.perf_event_paranoid` set 4 → 1 via `sudo -n` and
  **restored to 4** afterwards; shared host, temporary, recorded.

## Predictions (falsifiable)

- **P1 — the gate is reachable.** `-F 25` perturbation ≤ **1.05**. *Refuted* above, in which case the
  `-F 10` rung is run and reported.
- **P2 — concentration confirms under a passing gate.** Pooled total `geocm_*` ≥ **95%**. *Refuted*
  below.
- **P3 — precision is recovered by repetition.** The 95% CI half-width on `decode_stream_mix` is
  ≤ **2.0 pp**, i.e. better than the single `-F 99` run despite a quarter of the frequency.
  *Refuted* above 2.0 pp.
- **P4 — the conclusion survives honest error bars.** The bound interval implied by the CI, times
  this lane's measured 0.8172 MiB/s, has a **lower end ≥ 25.69 MiB/s** — ninth place at minimum.
  *Refuted* if the lower end falls below. This is the decision-grade prediction: it asks whether the
  geocm route survives being stated with error bars rather than as a point.

## What this cannot do

It cannot make the ceiling precise. Even a perfect share measurement leaves `1/(1-s)` steep near
0.99, so the honest output remains a **range**. P4 tests only whether the *floor* of that range keeps
the ninth-place conclusion — not whether the rung can be pinned.

Read-only profiling of an existing binary. No encoder, wire format, preset, counter or `decode()`
change; no candidate, no lever. No database write, no hypothesis row, no API, site or social action.
