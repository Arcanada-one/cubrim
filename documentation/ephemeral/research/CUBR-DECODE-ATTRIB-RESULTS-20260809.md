# Results: valid G2 decode-time attribution for NEW-24

**State:** `COMPLETE` characterization evidence; NEW-24 remains
`in_progress`. The original prediction was merged in PR #51 before any
measurement. The G2 amendment, authenticated runner, repair overlay and plan
were merged in PR #64 before this run. The valid campaign ran once on
`dev-ai` from 2026-08-09T15:28:00.319114Z to
2026-08-09T16:26:54.014145Z.

This report uses only G2 evidence pinned to CPUs `0-15`. PR #54's G0 result
used CPUs `16-19` and restarted a missing-source cell; PR #58 derived its tier
choice and `16-19` preregistration from that invalid result. Both remain
exploratory-only. The analyst had already seen them, so this analysis is not
claimed blind, but none of their measurements, verdicts or tier rankings is
used here.

## Provenance and terminal gates

- Frozen binary SHA-256:
  `d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb`.
- Frozen detached source: `3a13f486aea51470e2079ba66abb94d99fd782d9`,
  clean after authenticated test-only repairs were reversed.
- Runner SHA-256:
  `4ccfae3326a7c8678e31f7bdb4d46450e41dff727e2781fc3b313f6ab4cba9dc`.
- One invocation, ID `b67df18c0d7b40e5814525a32130e66f`, normal exit
  status 0, `NRestarts=0`, final directory present and `.partial` absent.
- Systemd recorded 2h02m55.223s CPU, 11.0 GiB peak memory and 0 B peak swap.
  Stand wall time was 3,533.695031 seconds.
- Systemd warned that `RuntimeMaxSec=4h5m` has no effect with
  `Type=oneshot`. This is a launch-contract defect, recorded rather than
  hidden. The runner's separate monotonic 14,400-second budget remained
  active, and this campaign completed normally well inside it.
- The immutable raw tree is read-only, contains only regular files and
  directories, and passes all 95 entries in `raw/SHA256SUMS`. Its manifest
  path set is exhaustive except for the manifest and completion marker. The
  completion marker SHA-256 is
  `3ab438a6f25f6c9a829ffd750de321c6ed5a9931d73185290b3051a2c3e90d37`.
- Admission, full release suite and focused differential suite passed. All
  four canonical archive pairs matched the registered archive SHA by
  SHA-256 and `cmp`; all 16 decode observations matched their source by
  `cmp` and original SHA-256. The journal has no void, gate-failure, abort or
  run-failure event.

The raw tree and deterministic reduction live in
`CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/`. `analysis/result.json` is the
machine-readable reduction; `metrics.tsv` is the per-file counter table;
`symbols.tsv` contains every zero-threshold symbol row and its Amdahl
ceiling. No corpus aggregate is computed anywhere.

## Per-file counters

Each row retains both independent `perf stat` samples. `wall` is the plain,
pinned profiling decode, not benchmark throughput. Cache events are the
generic supported counters; this CPU reported LLC-specific events as
unsupported.

| cell | plain wall s | G3 record/plain | cycles/bit sample 1 / 2 | IPC sample 1 / 2 | cache misses/bit sample 1 / 2 | dTLB misses/bit sample 1 / 2 | page faults sample 1 / 2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dickens/max | 142.860 | 1.01918 clean | 5,879.999756 / 5,925.440261 | 1.475333 / 1.464006 | 47.674905 / 46.120097 | 10.092587 / 10.087408 | 3,950,937 / 3,950,938 |
| xml/max | 58.000 | 1.02603 clean | 4,536.225599 / 4,576.866816 | 1.915722 / 1.898908 | 40.006490 / 39.643891 | 9.079704 / 8.973094 | 2,133,177 / 2,133,180 |
| x-ray/max | 6.200 | **1.20161 instrument-perturbed** | **suppressed / suppressed** | 2.378434 / 2.407199 | 2.874581 / 3.020976 | 0.206026 / 0.207094 | 21,830 / 21,828 |
| dickens/web | 105.710 | 1.02687 clean | 4,373.685379 / 4,346.351177 | 1.842458 / 1.853753 | 37.224364 / 36.439030 | 8.081868 / 8.080272 | 43,404 / 43,406 |

Cycle-sample relative deltas were 0.7669%, 0.8880%, 1.1882% and 0.6250%
respectively, all within the preregistered 10% agreement limit. The
`x-ray/max` counter samples remain descriptive, but its cycles/bit is not
quoted because G3 failed. Its symbol shares remain reportable under the
preregistered rule.

## Per-file symbol attribution and honest ceilings

The zero-threshold reports were generated from the preserved `perf.data` on
the same host with perf 6.8.12 and the authenticated frozen binary. This is a
derived view, not another decode. Two-decimal row rounding leaves residuals
of +0.13, +0.10, -0.10 and +0.25 points; no result depends on those
residuals.

### dickens/max

| named component | share | perfect-component Amdahl ceiling |
|---|---:|---:|
| `CmModel::predict_bit` | 49.72% | 1.989x |
| `Ctr::upd` | 32.81% | 1.488x |
| `CmModel::update_bit` | 6.39% | 1.068x |
| `Match::end` | 2.92% | 1.030x |
| `CmModel::start_byte` | 0.79% | 1.008x |
| outer `cm2_decode` shell | 0.46% | 1.005x |
| `Ctr::new` | 0.14% | 1.001x |
| `CmModel::end_byte` | 0.08% | 1.001x |
| named CM2 per-bit machinery, combined outer bound | 92.85% | 13.986x |

### xml/max

| named component | share | perfect-component Amdahl ceiling |
|---|---:|---:|
| `CmModel::predict_bit` | 50.01% | 2.000x |
| `Ctr::upd` | 29.42% | 1.417x |
| `CmModel::update_bit` | 8.50% | 1.093x |
| `Match::end` | 1.82% | 1.019x |
| `CmModel::start_byte` | 0.61% | 1.006x |
| outer `cm2_decode` shell | 0.58% | 1.006x |
| `Ctr::new` | 0.21% | 1.002x |
| `CmModel::end_byte` | 0.09% | 1.001x |
| named CM2 per-bit machinery, combined outer bound | 90.66% | 10.707x |

### dickens/web

| named component | share | perfect-component Amdahl ceiling |
|---|---:|---:|
| `CmModel::predict_bit` | 54.32% | 2.189x |
| `Ctr::upd` | 32.40% | 1.479x |
| `CmModel::update_bit` | 8.41% | 1.092x |
| `Match::end` | 2.02% | 1.021x |
| `CmModel::start_byte` | 1.33% | 1.013x |
| outer `cm2_decode` shell | 0.66% | 1.007x |
| `CmModel::end_byte` | 0.08% | 1.001x |

### x-ray/max — symbol shares only; G3 perturbed

| named component | share | perfect-component Amdahl ceiling |
|---|---:|---:|
| `geocm::decode_stream_mix` | 84.53% | 6.464x |
| `geocm::Mixer::update` | 12.65% | 1.145x |
| `geocm::mix_ctxs` | 0.86% | 1.009x |
| outer `geocm::decode` | 0.16% | 1.002x |
| named geocm replay path, combined outer bound | 98.20% | 55.556x |

The combined rows are impossible whole-path bounds, not promised speedups.
The exhaustive `symbols.tsv` gives the same ceiling calculation for every
sampled row, including kernel and sub-0.3% entries.

## Preregistered predictions

- **P1 — SUPPORTED.** Named per-bit CM2 machinery is 92.85% on
  `dickens/max` and 90.66% on `xml/max`, both above 85%. In the frozen source,
  `RangeDecoder::get_freq` and `decode` are called directly from the outer
  `cm2_decode` loop; any inlined coder work is therefore conservatively
  bounded by the 0.46% / 0.58% outer-shell symbols, below 5%.
- **P2 — INDETERMINATE.** `Mixer::mix` and `Mixer::update` are inlined into
  the larger `predict_bit` and `update_bit` symbols. The preregistration
  allowed `perf annotate` as a fallback but did not define an
  instruction-to-mixer map. The evidence therefore cannot decide the claimed
  30–50% mixer bucket without a post-hoc mapping. The directly observable
  facts are that `predict_bit` is largest at 49.72% / 50.01%, followed by the
  separable `Ctr::upd` at 32.81% / 29.42%.
- **P3 — INDETERMINATE.** IPC is above 1.0 in both samples of every cell, so
  that half of the prediction points away from the refutation branch. But the
  preregistration provides no miss-latency model or formula for its “implied
  miss-stall share,” and LLC events are unsupported. Generic cache and dTLB
  misses cannot be converted into a defensible percentage of stalled cycles
  after the run.
- **P4 — SUPPORTED.** No CM2 symbol appears on `x-ray/max`; named geocm replay
  symbols account for 98.20%, so the recorded-scheme path dominates and CM2
  is safely below 10%. This verdict uses reportable symbol shares only; no
  x-ray cycles/bit is quoted.
- **P5 — INDETERMINATE.** The six observable major symbol families keep the
  same order from `dickens/max` to `dickens/web`, and their largest absolute
  share shift is 4.60 points, inside ±10. The preregistration did not define
  an exhaustive bucket universe or a tie rule, however, so that observation
  cannot be promoted to a formal all-bucket verdict.

## Characterization boundary

This G2 run characterizes a single-threaded decode path under a pinned
profiling envelope. It does not establish benchmark throughput, does not
measure a candidate, and does not authorize a density/speed trade. The valid
mechanism map is per file:

- On the two max-mode CM2 files, about half the cycles land in
  `predict_bit`, another 29–33% in independently visible `Ctr::upd`, and the
  outer range-decoder shell is below 0.6%.
- On the same `dickens` bytes at `web`, the major observable order persists
  while the two cycle samples fall from about 5,880–5,925 to
  4,346–4,374 cycles/bit. The ratio cost of that preset is not measured here.
- `x-ray/max` is a distinct geocm replay path; its symbol profile is usable,
  but G3 prohibits a cycles/bit conclusion.

No lever is selected in this report. Selection must occur only after this
raw evidence, deterministic parser output, independent review and report land
on `main`, and it must be derived independently of the invalid PR #54/#58
path.

## Database boundary

This characterization creates no measurement or evaluation row and writes
nothing to `world_benchmark_*`. After independent review and landing, the
only authorized DB change is one idempotent pointer to this report in the
existing NEW-24 `measure_note`, while NEW-24 remains `in_progress`,
`measurements` stays empty and evaluation remains zero.
