# H-31 — Monotonic-column first-order delta (stacks on H-30 columnar)

**Status:** GO — IMPLEMENTED + MEASURED. Shipped inside `MODE_COLUMNAR` (container mode 4).

**Class targeted:** columnar / telemetry CSV (epoch-timestamp / id / counter columns).
Continuous-improvement race, round after H-30 (columnar field-split).

## Hypothesis

After the H-30 columnar field-split, a column whose data cells are canonical
non-decreasing integers (Unix epoch timestamps, monotone ids, counters) is replaced by
its first-order deltas. Small near-constant deltas entropy-code far below the full-width
absolute values, deepening the columnar win on telemetry data.

## Why it might help (mechanism)

A monotone epoch column is ~10 digits per cell (`1357113600`, `1357113660`, …). Column-
major reorder already clusters them, but the *values* are still wide. First-order delta
turns them into ~2-digit near-constant steps (`60`, `60`, `61`), which the BWT+geomix /
rANS backend codes in a fraction of the bits. Fully reversible (store the first value as
the anchor; prefix-sum on decode), **zero learning cost** (a deterministic arithmetic
transform, not a probabilistic model — no Gotcha #9 exposure).

## Implementation

Per column, inside `build_columnar_blob`: `columnar_delta_encode` delta-codes a column
iff `cells[1..]` are all **canonical** integers (`v.to_string() == cell` — rejects
leading zeros / `+` signs / floats so re-rendering is byte-exact) AND non-decreasing.
First cell verbatim (header or first value), second cell the verbatim anchor, the rest
signed deltas. A per-column 1-byte `colmodes` stream + a `ends_nl` flag (strip the
trailing-newline empty row that would otherwise poison column-0 detection) are added to
the wire; `columnar_delta_decode` reverses by prefix-sum. Competitive by construction
(the whole `MODE_COLUMNAR` blob still competes `min(base, lz, columnar)` and is gated
`>64KB` + tabular), so it can never regress a file. +2 tests (canonical/monotonic unit,
shrink-on-monotonic-CSV); full suite **236 green**, clippy 0 new warnings.

## Measured (real class corpus, cubrim `--value-scheme bwt-rans`, RT byte-exact each)

| file | H-30 columnar | **H-31 +delta** | vs zstd-19 | vs gzip-9 |
|---|---:|---:|---:|---:|
| forex_tick.csv | 44397 | **36846** | −27.6% → **−39.9% WIN** | −52.1% |
| forex_usdchf.csv | 38514 | **31207** | −30.7% → **−43.8% WIN** | −57.7% |
| status_timeseries.csv | 20769 | **20398** | −2.9% → **−4.6% WIN** | −29.1% |
| **class AGGREGATE** | 185883 | **170654** | −15.1% → **−22.1% (beats zstd)** | **−44.5%** |

zstd-wins 4/9 (unchanged file set; the columnar wins deepen sharply). **Zero-regression
VERIFIED:** tuned 10-file **0.158273 byte-identical** (RT 10/10), holdout **0.2390
byte-identical** (RT 6/6).

## Honest scope (what H-31 does NOT do)

H-31 only acts on columns inside `MODE_COLUMNAR`, which engages **only on uniform
delimited tables**. The remaining class losses are the LOG files — `journal.log`
(+5.8%), `toolchain.log` (+9.4%), `dpkg.log` (+8.0%) — which are **not column-uniform**
(variable field counts: message length varies), so columnar/H-31 never engages on them
(measured: modal-field-count fraction with ≥2 cols fails the tabular gate). Flipping the
logs requires **H-36 (CLP-style log-template / variable split)**, the next round. H-31's
premise that it would "finish the logs" is corrected here: it finishes the *telemetry*
half, not the log half.

## Verdict

**GO.** Monotonic-column delta stacks cleanly on columnar, deepening the telemetry
sub-class from −15% to −22% below zstd (forex −40/−44%), regression-proof + byte-exact,
tuned/holdout byte-identical. The class is NOT a ceiling — logs are next via H-36.

**Code SHA:** committed on `feat/cubr-bigfiles` (this round's HEAD). Leaderboard untouched, NOT pushed.
