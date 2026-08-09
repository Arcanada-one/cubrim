# CUBR zero-representation eight-cell matrix result — 2026-08-09

## Verdict

**PASS in all eight preregistered cells.** The zero representation reclaimed the
same-run packed-Ctr RSS penalty, stayed within 1.05× of current decode time, and
retained at least a 1.10× speedup over the baseline in every file/preset cell.
Every cell is also `ACCOUNTING_CONSISTENT` against its preregistered storage
ceilings.

This was one complete, valid campaign. The reviewed runner was launched once
under systemd; no parameter was widened, no sample was removed, and no restart
occurred. These are eight per-cell results, not a cross-cell aggregate.

## Per-cell preregistered decision axes

Wall time is the median of three timed decodes. RSS is median peak RSS in KiB.
`P = current - base`, `R = current - zero`, and residual is `P - R`.

| Cell | Base wall / RSS | Current wall / RSS | Zero wall / RSS | R/P | Residual KiB | Zero/current | Base/zero | Product | Accounting |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `nci/balanced` | 18.17 s / 1,385,472 | 15.07 s / 1,645,056 | 14.68 s / 991,744 | 2.516765 | -393,728 | 0.974121 | 1.237738× | PASS | ACCOUNTING_CONSISTENT |
| `nci/web` | 15.77 s / 108,032 | 13.39 s / 111,616 | 13.08 s / 92,672 | 5.285714 | -15,360 | 0.976848 | 1.205657× | PASS | ACCOUNTING_CONSISTENT |
| `dickens/max` | 26.94 s / 1,543,680 | 19.95 s / 1,719,808 | 20.06 s / 1,154,560 | 3.209302 | -389,120 | 1.005514 | 1.342971× | PASS | ACCOUNTING_CONSISTENT |
| `dickens/balanced` | 25.71 s / 1,486,848 | 19.25 s / 1,654,272 | 19.33 s / 1,135,104 | 3.100917 | -351,744 | 1.004156 | 1.330057× | PASS | ACCOUNTING_CONSISTENT |
| `dickens/web` | 22.54 s / 110,080 | 17.17 s / 113,152 | 17.08 s / 104,960 | 2.666667 | -5,120 | 0.994758 | 1.319672× | PASS | ACCOUNTING_CONSISTENT |
| `ooffice/max` | 25.53 s / 1,635,328 | 19.08 s / 1,708,544 | 19.21 s / 1,474,048 | 3.202797 | -161,280 | 1.006813 | 1.328995× | PASS | ACCOUNTING_CONSISTENT |
| `ooffice/balanced` | 25.54 s / 1,635,328 | 19.07 s / 1,708,032 | 19.34 s / 1,474,048 | 3.218310 | -161,280 | 1.014158 | 1.320579× | PASS | ACCOUNTING_CONSISTENT |
| `ooffice/web` | 22.29 s / 112,640 | 17.12 s / 115,200 | 16.80 s / 108,032 | 2.800000 | -4,608 | 0.981308 | 1.326786× | PASS | ACCOUNTING_CONSISTENT |

For every row, `P > 0`, `R/P >= 0.75`, residual is at most 65,536 KiB,
zero/current time is at most 1.05, and base/zero speedup is at least 1.10.
Accounting checks independently confirm `R <= T` and `B <= E`, using the
cell-specific preregistered ceilings. Negative residuals mean zero
representation used less peak RSS than the same-run baseline; they are not
clamped or reinterpreted.

## Validity and provenance

- Resulting main and measured candidate:
  `368bc17df4a6b2f91d5896c86d963eba7acfe256` (PR #50), with reviewed runner
  parent `6373e7f948cb84fea6b66d97af8b6ee059b9a13b`.
- Runner SHA-256:
  `57596e44421ffb07726f0a8c614859dd2eae32ad5b6d623813301638892d6efc`.
- Candidate binary SHA-256:
  `771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20`;
  `cm2.rs` SHA-256:
  `1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf`.
- Unit `cubr-zerorep-matrix-g3-20260809.service`, invocation
  `3b671580c4e24e59990965dd008ad1d4`: result success, main exit status 0,
  runtime 1h 6min 41.094s, 4.7 GiB memory peak, and 0 B swap peak.
- Admission load1 was 1.29. After both release suites passed, the fixed
  stabilization gate obtained two quiet samples at 121 seconds with load1 1.29.
- The suites modified exactly the two preregistered tracked benchmark JSON
  files. The runner restored their exact HEAD blobs atomically, then proved a
  clean checkout and rechecked the candidate binary, `cm2.rs`, runner, HEAD,
  FETCH_HEAD, and zero-code identity before measurement.
- Completion marker: candidate `368bc17df4a6b2f91d5896c86d963eba7acfe256`,
  UTC `2026-08-09T11:47:09Z`, 72 results, 96 roundtrips, 8 verdicts.
- Exact evidence structure: 72 timed logs, 24 warmup logs, 24 canonical
  archives, 72 timed rows, 96 unique PASS roundtrips, 8 verdict rows, no
  remaining `.back` files, and no temporary completion marker.
- Post-run checkout HEAD, FETCH_HEAD, and freshly read remote main were equal;
  the checkout was clean.

An independent parser separately verified the exact 72/96 schedule, unique
keys and all PASS comparisons, the complete timing-log name set, exit status
and wall/RSS parity for every timed log, every median and formula, all product
and accounting thresholds, and exact TSV/JSON verdict parity.

## Instrument generations

Generation 1 stopped before measurement because systemd's PATH did not include
the pinned Cargo executable. Generation 2 passed both suites and then stopped
fail-closed when the suites changed two tracked benchmark JSON files. Their
header-only tables and immutable manifests remain instrument-failure evidence,
not scientific observations. Generation 3 changed only the harness handling of
those known suite side effects and preserved the preregistered scientific
design.

## Database status

The database is **not yet mutated** by this result lane. The required atomic,
idempotent 24-row NEW-30 transaction must be generated from these medians and
independently reviewed before execution. `web_benchmark_hypothesis_evaluation`
must remain at zero rows. No API, site, social, or publication action has been
taken.

## Scope

This result covers only the eight preregistered `nci`, `dickens`, and `ooffice`
file/preset cells on `dev-ai`, with CPUs 0-15 and four threads. It does not
change or qualify the archive wire format, encoder defaults, `decode()`,
`cube_size_limit`, `cm_should_try`, or `prof.rs` counters. It does not justify a
cross-corpus average, an unmeasured preset claim, or a production-readiness
claim outside these cells.
