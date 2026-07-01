# H-48 — Enum column dictionary→RLE→rANS: MARGINAL (largely subsumed by BWT+geomix)

**Status:** MARGINAL (spike). Dict→RLE gains only −2.3 % over the existing columnar
BWT+geomix path on a best-case enum-heavy file — no Rust written; the win is mostly
subsumed by the strong entropy backend (Gotcha #11).

**Class targeted:** low-cardinality categorical / enum columns (level, service, status,
region) in event/log CSVs — research handoff, flagged as a structural strength.

## Hypothesis

A low-cardinality string column with run structure (slowly-changing categoricals) is
dictionary-encoded (distinct values → small indices) then RLE'd (runs of the same index)
before the rANS backend, beating the current column-major string clustering.

## Spike (faithful — real cubrim backend)

Generated a maximally enum-heavy, run-structured event CSV (12 000 rows: timestamp,
level{6}, service{5}, region{4}, status{7}, latency — categoricals change only every
~30–200 rows). Built the column-major stream two ways (current: delta on timestamp +
raw enum strings; H-48: same + dict→RLE on the 4 enum columns) and compressed each
through the real cubrim bwt-rans rail.

| file (corpus: generated enum-heavy events) | current columnar | dict→RLE | gain | zstd-19 |
|---|---:|---:|---:|---:|
| events.csv (455344 B) | 20285 | 19812 | **−2.3 %** | 42529 |
| vs zstd-19 | −52.3 % | −53.4 % | | — |

Baseline check: the *current* codec already crushes zstd-19 on this enum-heavy file
(20360 full-file vs 42529 = **−52.1 %**, mode columnar, RT byte-exact).

## Verdict

**MARGINAL.** Dict→RLE gains only −2.3 % even on a best-case run-structured enum file,
because BWT+geomix already clusters and codes the low-cardinality columns to near their
entropy (already −52 % vs zstd). The explicit dictionary+RLE is **largely subsumed by the
strong entropy backend** — the same lesson as H-41 DoubleDelta: transforms that win for
Parquet/bzip2 (dict+RLE, MTF) do so because those backends bit-pack; Cubrim's rANS/geomix
after BWT already pays ~0 for a clustered low-cardinality stream. On real numeric-heavy
telemetry (the won class) the enum columns are minor, so the aggregate gain is ~0.

Not implemented (the −2.3 % best-case does not move the already-won class and the wire
cost is not justified). Added **Gotcha #11** (strong entropy backend subsumes
delta-order / RLE / MTF pre-transforms — spike through the real backend). Reconsider only
if a dedicated CATEGORICAL/event-log class (mostly enum columns, little numeric) becomes a
target, where the −2.3 % could matter more.

**Code SHA:** spike on `36dc290` (codec untouched). Leaderboard untouched, NOT pushed.
