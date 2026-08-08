# CUBR zero-representation result — 2026-08-08

## Verdict

**PASS.** The preregistered zero representation for packed Ctr eliminated the
observed packed-table RSS regression on `nci/max` and preserved the decode-speed
gain. The implementation is eligible to ship.

This was one complete valid run. The reviewed runner was executed once under
systemd; no parameter was widened, no sample was cut, and no restart occurred.

## Preregistered decision axes

| Build | Median decode | Median peak RSS |
| --- | ---: | ---: |
| pre-PR41 `e70d1cd` | 18.71 s | 1,430,016 KiB |
| current packed `49e429e` | 15.61 s | 1,710,592 KiB |
| zero representation `f047523` | 15.25 s | 998,912 KiB |

- Same-run packed penalty: 280,576 KiB (274 MiB).
- Reclaimed from current packed: 711,680 KiB (695 MiB).
- Reclaim fraction versus same-run penalty: 253.65%.
- Reclaimed fraction of the preregistered 768 MiB ceiling: 90.49%.
- Residual versus pre-PR41: -431,104 KiB (-421 MiB), passing the +65,536 KiB cap.
- Zero/current time ratio: 0.97694, passing the <=1.05 limit.
- Pre-PR41/zero speedup: 1.22689x, passing the >=1.10x floor.

The reclaim exceeds the same-run packed penalty because the zero word defers
physical commitment for untouched portions of the entire packed four-byte
record, not only the extra two-byte ceiling used to bound the PR #41 regression.
That mechanism is consistent with the preregistered 1,536 MiB total zero-word
storage opportunity; this one-file experiment does not generalize the amount to
other files or presets.

## Validity and provenance

- Input: 2 MiB `nci`, SHA-256 `6788fcc1...21e`.
- All three archives: 104,139 bytes, SHA-256 `1dcc11fa...925b`, mutually
  byte-identical and equal to the prior canonical archive.
- One warm-up per build and all nine timed decodes passed byte-exact `cmp`
  round-trip.
- Admission: load average 0.16, no Cubrim process, CPUs 0-15, four threads.
- Exact runner head: `e227b1e0d41541b8c40d4e5f4c60ba5f5484f3e7`.
- Runner SHA-256: `bb6c8893...8fca7`, equal to the committed blob.
- Candidate code: `f047523fcdc15561baa05fee597819fd6bdb53d3`;
  binary SHA-256 `771fdb0f...6e20`.
- Separate clean stand checkouts reproduced both preregistered comparison
  binaries and the candidate binary exactly.
- Unit result success, main status 0, runtime 9 minutes, 1.8 GiB unit memory
  peak, and zero swap.

Candidate verification before measurement included two focused tests with
mutation-sensitive RED/GREEN proof, the full release suite (322 library tests;
all 39 integration tests passed; 11 library tests ignored), the 7-test scheme
round-trip suite, and 12 reproducibility tests. Independent review of the final
code and runner returned READY with no findings.

## Publication readback

The live DB stores codec revision 10 and measurement rows 413-415 under the
unique run mode `zerorep-nci-max-pin0-15-t4`. All three rows have required
decode values, NULL encode duration/RSS, and distinct revisions. Evaluation
remains zero. Replaying the exact transaction produced zero inserts and zero
updates while re-running every assertion.

The public API returned NEW-30 with exactly three rows for the new run mode, and
the public hypothesis page rendered the extension, the 998,912 KiB median, and
the PASS conclusion.

## Scope

This result qualifies only the internal packed-Ctr representation change. It
does not change `decode()`, the archive wire format, encoder defaults,
`cube_size_limit`, `cm_should_try`, or existing `prof.rs` counters. It is a
per-file `nci/max` result, not a corpus-wide RSS claim.
