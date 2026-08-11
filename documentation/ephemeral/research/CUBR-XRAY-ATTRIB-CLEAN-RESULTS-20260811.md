# CUBR-XRAY-ATTRIB-CLEAN-20260811 — results: the first gate-passing x-ray profile, and the ceiling's true shape

**A gate-passing profile now exists.** Perturbation **1.00533** at `-F 25` against the ≤1.05 gate —
the first x-ray attribution in this programme that meets its own instrument requirement. The geocm
concentration is confirmed on an essentially unperturbed instrument: **98.36%** total, with
`decode_stream_mix` at **86.38%**.

All four predictions hold at `-F 25`. The `-F 10` rung, run and reported as the preregistered ladder
required, **fails P3 and P4** — and that failure is the most useful result in this record, because it
demonstrates empirically what the prior lane could only argue.

Prereg merged as `4ed32a8` at 22:31:59Z; measurement began 22:32:24Z.

## Predictions, scored

| | prediction | `-F 25` | `-F 10` |
|---|---|---|---|
| **P1** | perturbation ≤ 1.05 | **1.00533 — PASS** | 0.98228 — PASS |
| **P2** | pooled `geocm_*` ≥ 95% | **98.36% — PASS** | 98.27% — PASS |
| **P3** | CI half-width ≤ 2.0 pp | **±1.20 pp — PASS** | ±2.16 pp — **FAIL** |
| **P4** | bound-interval lower end ≥ 25.69 | **28.1 — PASS** | 20.5 — **FAIL** |

## The instrument caveat is now fully lifted

Three independent profiles, at three perturbation levels, agree:

| run | perturbation | total geocm | `decode_stream_mix` |
|---|---:|---:|---:|
| G2/G3 attribution (landed) | 1.20161 | 98.20% | 84.53% |
| this lane, `-F 99` (#132) | 1.08705 | 98.99% | 88.06% |
| **this lane, `-F 25`, gate-passing** | **1.00533** | **98.36%** | **86.38%** |

The concentration does not move with the instrument. Every x-ray share in the record can now be
treated as real rather than provisional, and the qualifier attached to the speed-branch conclusion
since #127 is retired.

## The ceiling's true shape: a floor, and no measurable top

Even at the gate, with ~3123 effective samples and a ±1.20 pp CI, the bound is a **wide interval**:

| rung | shell-excluded share | 95% CI | bound interval | best case × 0.8172 MiB/s |
|---|---:|---|---|---|
| `-F 25` | 98.29% | [97.09, 99.50] | **[34.4×, 198.4×]** | **[28.1, 162.2] MiB/s** |
| `-F 10` | 98.18% | [96.01, 100.00] | [25.1×, 20000×] | [20.5, 16344] MiB/s |

The lower end at `-F 25` is **28.1 MiB/s**, which still clears ppmd's 25.69 — so **P4 holds and the
ninth-place-at-minimum conclusion survives honest error bars.** That is the durable result.

The upper end does not converge. `1/(1-s)` at `s ≈ 0.983` turns a ±1.2 pp measurement error into a
6× spread in the ceiling, and at `-F 10` the interval degenerates entirely (the CI touches 100%, so
the bound runs to infinity). **The geocm ceiling is not measurable from above by this method at all** —
not because the measurement is sloppy, but because Amdahl's formula is singular where this system
actually sits.

### What that means for the speed branch

- **Floor, firm:** perfecting the geocm replay path buys **at least ninth place** (≥28.1 MiB/s),
  on a gate-passing instrument with error bars.
- **Top, unmeasurable:** any figure above that — the 41.69, the 45.40, the 72.32 of earlier records,
  or the 162.2 here — is a point drawn from an interval that the method cannot narrow. **None of them
  should be quoted as the ceiling.**
- The honest characterisation is: *the geocm rail has real, large, but unbounded-from-above headroom;
  the only defensible number is the floor.*

This retires the framing in `CUBR-SPEEDFLOOR-XRAY-RESULTS-20260811.md` that the route reaches
"ninth to eighth place". The floor is ninth; the top is simply not known.

## Two method errors, both recorded

**Non-paired timing.** The first attempt ran all 3 plain decodes first and all 24 instrumented ones
after. It produced perturbation ratios **below 1.0** (0.913, 0.908) — instrumentation cannot make a
decode faster, so the baseline was taken in a different load window. This is the identical
cross-window error this lane had already fixed for *tool* comparisons, repeated here for
*plain-vs-instrumented*. Re-run with plain and perf interleaved as **same-window pairs**; perturbation
is the median of per-pair ratios. The discarded attempt is retained as
`timings-firstattempt-nonpaired.tsv`.

Worth stating plainly: a sub-1.0 perturbation is physically impossible, and that impossibility is what
exposed the error. A ratio of, say, 1.03 from the same broken design would have passed the gate and
been believed.

**Parser dropped a column.** The share parser ignored the `[.]`/`[k]` DSO field between period and
symbol, returning 0.00% for every bucket. Fixed; shares are pooled sample periods across 12 runs.

## Boundaries

Read-only profiling. No encoder, wire format, preset, counter or `decode()` change; no candidate, no
lever. No database write, no hypothesis row, no API, site or social action.
`kernel.perf_event_paranoid` set 4 → 1 for the run and **restored to 4** (verified). 48 gated decode
observations across both rungs, 0 VOID.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-XRAY-ATTRIB-CLEAN-RESULTS-20260811
cat timings2.tsv              # same-window plain/perf pairs, both rungs, with gates
cat symbols-F25-pooled.txt    # pooled perf report rows for the gate-passing rung
```

`perf` requires `kernel.perf_event_paranoid <= 1`; it is 4 by default on this host.
