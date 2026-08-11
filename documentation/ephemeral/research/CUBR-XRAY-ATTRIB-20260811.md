# CUBR-XRAY-ATTRIB-20260811 — preregistration: is the 98.20% geocm share real, or the instrument?

**Committed to `main` BEFORE measurement.**

## The question, and why this lane is taking it rather than deferring it

`CUBR-SPEEDFLOOR-XRAY-RESULTS-20260811.md` established that the geocm rail is the **only measured
route into the competitive field** — perfecting the named replay path buys ninth place out of ten
(41.69–45.40 MiB/s against ppmd's 25.69 and bzip2's 52.71). That conclusion rests entirely on the G2
attribution's claim that the geocm path is **98.20%** of x-ray decode, of which
`geocm_decode_stream_mix` alone is **84.53%**.

Those shares come from a run the attribution itself flagged **instrument-perturbed**: G3 ratio
**1.20161** against its own ≤1.05 gate, with cycle samples suppressed. That lane closed by naming
the fix — *"a clean, unperturbed attribution run on x-ray"* — and deferring it as PROGRAM's.

**That deferral was wrong on the facts.** It rested on `perf_event_paranoid = 4` on this host making
profiling impossible. Re-probed properly: `sudo -n` is available here, the sysctl is writable, and
`perf` works immediately at `paranoid = 1`. Nothing was blocking the measurement except an
unverified assumption. It is taken here.

## Method (fixed before running)

The perturbation in the G3 run is the thing to beat, so the design targets low overhead directly:

- **Sampling**: `perf record -F 99 --call-graph none` — 99 Hz, no stack unwinding. Unwinding is the
  dominant cost in most perf configurations and is not needed for flat symbol shares.
- **Baseline**: 3 plain pinned decodes of x-ray; median wall.
- **Instrumented**: 3 decodes under `perf record`, identical pin and inputs; median wall.
- **Perturbation ratio** = instrumented median / plain median, compared against the attribution's own
  **≤1.05** gate. If the run does not meet that gate, its shares are reported as perturbed and the
  question stays open — the gate is not moved to fit the result.
- **Binary**: the attribution's frozen commit `3a13f486` (sha256 `8947ea9b…`), same archive
  (3,637,036 B, ratio 0.429187), so shares are comparable to the landed ones.
- `taskset -c 0-15`, pin not widened. Host load logged; x-ray decode is ~10 s so the whole matrix is
  cheap.
- **Symbol shares** from `perf report --stdio --no-children --percent-limit 0`, bucketed into
  `geocm_*` / `cm2_*` / kernel / other by demangled symbol name, mirroring the attribution's
  `bucket` scheme so the numbers are directly comparable.
- Host state: `perf_event_paranoid` is changed from 4 to 1 for this measurement and **restored to 4
  afterwards**. It is a shared box; the change is temporary and recorded.

## Predictions (falsifiable)

- **P1 — a clean run is achievable.** Perturbation ratio ≤ **1.05**, i.e. this configuration meets
  the gate the G3 run failed at 1.20161. *Refuted* above 1.05.
- **P2 — the geocm concentration is real, not an artefact.** Total `geocm_*` share ≥ **90%**
  (landed: 98.20%). *Refuted* below 90%.
- **P3 — the dominant symbol reproduces.** `geocm_decode_stream_mix` is the top user-space symbol and
  ≥ **70%** (landed: 84.53%). *Refuted* if it is not top, or below 70%.
- **P4 — the ninth-place conclusion survives.** The combined bound recomputed from *these* shares, on
  the shell-excluded basis, times this lane's measured 0.8172 MiB/s, still clears ppmd's 25.69 MiB/s.
  *Refuted* below.

If P2/P3 hold, the geocm headroom is confirmed on an unperturbed instrument and the ninth-place
ceiling becomes a firm result rather than one carrying an instrument caveat. If they fail, the only
route into the field this programme has measured dissolves, and the speed branch has no measured
route at all — which would be the more consequential finding.

## Boundaries

Read-only profiling of an existing binary. No encoder, wire format, preset, counter or `decode()`
change; no candidate built, no lever selected. No database write, no hypothesis row, no API, site or
social action. `perf_event_paranoid` restored to its found value.
