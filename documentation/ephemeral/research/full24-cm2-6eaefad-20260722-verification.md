# Independent full-24 verification of MODE_CM2 composition `6eaefad`

Date: 2026-07-22 UTC

Verdict: **phase-4 NO-GO for publication as-is**. The immutable candidate wins every type against the fresh external-codec baseline and all 24 rows round-trip byte-exact, but it regresses the already-published Cubrim binary aggregate by 0.542430% relative. Production DB/site remain on HARD HOLD.

## Immutable inputs

- Candidate commit: `6eaefad7e165cd74f7d660aeb6d0828bfbe12c41`
- Independently built release CLI SHA256: `e3da2f33ef7e9f0cfb4e07c4dbe4b406ba00ab17d8b9c40bf3aeb21abd1a546a`
- Corpus manifest SHA256: `fa88c6c12249c1261068112eb56c24d4ef3b60d1d89711aa97770f07f3c007e6`
- Corpus: Silesia 12 + full enwik8 + Canterbury 11, 24 files, 314,749,364 original bytes.
- Remote raw result TSV SHA256 (CRLF): `02e73f013fa33731ad374ae29c11b95d7aaa02ec04b20f83eba5f1793186fae2`
- Remote summary SHA256: `8f02888e1f7f5bdbed8a6693c02eb5d0d382c875f8fc191098915da1488ce2d7`
- Remote provenance SHA256: `2ae24f3832568d14d4f36900159a2bb9d8b0a7672303d56b2bc3cced6a791261`

The run produced 24 unique rows. Every row has encode RC 0, decode RC 0, and an external byte-for-byte compare result of 0. An independent recalculation directly from the TSV exactly matched `summary.json`; no summary-produced aggregate was accepted without this cross-check.

## Weighted per-type results

All ratios are `sum(compressed bytes) / sum(original bytes)` for the type. Competitor leaders come from the independent fresh 24-file, 9-codec run completed immediately before this candidate run. “vs live” compares against the current `aggregate_by_type.cubrim` API snapshot (`CUBR-0061-full24-fh10-recordcm`, generated 2026-07-18).

| Type | Candidate bytes / original | Candidate | Fresh competitor leader | vs leader | Current live Cubrim | vs live | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| text | 29,206,553 / 164,838,344 | 0.177183004217 | ppmd 0.201380019930 | -12.015599% | 0.212656537390 | -16.681139% | PASS, new #1 |
| exe | 14,239,330 / 57,372,672 | 0.248190113927 | 7z 0.274873967871 | -9.707669% | 0.293557793509 | -15.454429% | PASS, new #1 |
| binary | 3,901,918 / 8,319,928 | 0.468984587367 | 7z 0.537752610359 | -12.788041% | 0.466454397202 | **+0.542430%** | **FAIL non-regression** |
| code | 3,152,188 / 21,621,271 | 0.145791059184 | xz 0.173155777937 | -15.803526% | 0.161541335845 | -9.749998% | PASS |
| database | 3,871,803 / 43,639,129 | 0.088723196102 | xz 0.098393989486 | -9.828642% | 0.095777346977 | -7.365156% | PASS |
| image | 5,913,932 / 18,958,020 | 0.311948821660 | ppmd 0.327123032891 | -4.638686% | 0.312130458473 | -0.058193% | PASS |

Overall candidate output is 60,285,724 / 314,749,364 = `0.191535649934`.

## Binary regression localization

- `sao`: 7,251,944 -> 3,839,238, `0.529408114569`, mode 13, exactly equal to the live FH-10 record-CM result.
- `kennedy.xls`: 1,029,744 -> 24,427, `0.023721429792`, mode 16, improving the live 31,087-byte result.
- `sum`: 38,240 -> 38,253, `1.000339958159`, mode 1, versus the live 10,542-byte result (`0.275679916318`).

The `sum` loss is 27,711 bytes and the `kennedy.xls` win recovers 6,660 bytes, leaving the type 21,051 bytes worse than live. This is not an RT defect: `sum` also decoded byte-exactly.

An independent control build of exact FH-10 commit `9856eb31e10216a0057384c9a8389ed546206985` (CLI SHA256 `145835f9154d2ac0f086eface76b4f5e4dda65091fa499c4caf9f23dbd7b1c13`) produced the exact same `sum` archive: 38,253 bytes, mode 1, archive SHA256 `b3e9a402d8779b35c12c17370f21c620fb4978d1cd47f2b8505aaf3baf3599ea`, RT cmp=0. The loss is therefore not introduced by MODE_CM2 composition or a missing FH-10 commit. It exposes a pre-existing methodology/path mismatch: the live benchmark row used the value-codec rail for this sub-64-KiB file, while the real CLI archive path stores it raw. Other tiny Canterbury files show the same path mismatch, but only binary crosses the aggregate non-regression threshold.

## Required next gate

Resolve the benchmark-path mismatch before publication: either make real CLI preserve the value-codec small-file rail, or use an explicitly sanctioned per-file old/new competitive minimum that retains the already-verified live row for files where the new CLI path does not improve it. Then build/freeze the resulting candidate or result composition and independently rerun the affected proof plus the required aggregate/RT validation. The numbers above are valid measurements of `6eaefad`, but the raw all-CLI aggregate is not DB-admissible as the replacement Cubrim row because it violates the explicit non-regression gate.

For operator review, the deterministic per-file old/new minimum has also been calculated without writing it anywhere. Existing live compressed byte counts were reconstructed by `round(live_ratio * original_size)`; the largest rounding residual was 0.426 byte and the reconstructed per-type totals reproduce the exact live aggregates. Nine live rows would be retained (`sao`, `x-ray`, `alice29.txt`, `asyoulik.txt`, `cp.html`, `fields.c`, `grammar.lsp`, `sum`, and `xargs.1`); 15 new RT-verified rows would replace them.

| Type | Retained-min bytes / original | Retained-min ratio |
|---|---:|---:|
| text | 29,165,067 / 164,838,344 | 0.176931327337 |
| exe | 14,239,330 / 57,372,672 | 0.248190113927 |
| binary | 3,874,207 / 8,319,928 | 0.465653909505 |
| code | 3,142,557 / 21,621,271 | 0.145345618211 |
| database | 3,871,803 / 43,639,129 | 0.088723196102 |
| image | 5,913,930 / 18,958,020 | 0.311948716163 |

This retained-min table is a cross-rail publication candidate, not the output of one `6eaefad` CLI run. It closes the mathematical non-regression gate by construction, but it remains operator/methodology-gated and was not sent to the DB.

No DB write, backup transaction, site update, or production mutation was performed.
