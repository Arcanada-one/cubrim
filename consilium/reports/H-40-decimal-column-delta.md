# H-40 — Fixed-decimal column delta (ALP decimal-branch subset; stacks on H-30/H-31)

**Status:** GO — IMPLEMENTED + MEASURED. Shipped inside `MODE_COLUMNAR` (column mode 2).
This is external research's **#1 best bet** (Lever 1): decimal float → integer delta.

**Class targeted:** scientific / financial / sensor float-column CSV (the proven
columnar/telemetry class, extended from integer columns to decimal columns).

## Hypothesis

A columnar field whose data cells are canonical fixed-decimals with a consistent scale
(e.g. forex prices `1.30970000`, scale 8) is reinterpreted as a scaled integer
(`130970000`) and signed-delta-coded. Slowly-drifting prices → tiny signed deltas →
collapse under the entropy backend. Pure-integer columns already use H-31 delta; H-40
covers the decimal columns H-31 left as strings.

## Why it might help (mechanism)

This is the **decimal branch of ALP** (Adaptive Lossless floating-Point, SIGMOD 2024,
the SOTA columnar float codec): multiply by 10^scale to recover the exact integer, then
delta. Fully reversible (scale derived losslessly from the data's own digit count; 1
scale-byte per column; canonical `render(parse(cell)) == cell` guarantees byte-exact
re-rendering — rejects leading zeros / mixed scale / `+`). Zero learning cost; prices
oscillate so deltas are signed (no monotonic gate, unlike H-31).

## Implementation

`columnar_decimal_encode` / `columnar_decimal_decode` + helpers (`decimal_scale`,
`fixed_decimal_value`, `parse_fixed_decimal`, `render_fixed_decimal`). Per-column the
build loop now tries integer-delta (mode 1) → decimal-delta (mode 2) → raw (mode 0); a
`col_scales` byte stream (1/column) is added to the wire. Competitive by construction
(the whole `MODE_COLUMNAR` blob still competes `min(base, lz, columnar)`, gated >64KB +
tabular), so it can never regress a file. +2 tests; full suite **238 green**, clippy 0 new.

## Measured (real class corpus, cubrim `--value-scheme bwt-rans`, RT byte-exact each)

| file | H-31 | **H-40 +decimal** | vs zstd-19 | vs gzip-9 |
|---|---:|---:|---:|---:|
| forex_tick.csv | 36846 | **26848** | −39.9% → **−56.2% WIN** | −65.1% |
| forex_usdchf.csv | 31207 | **24881** | −43.8% → **−55.2% WIN** | −66.3% |
| status_timeseries.csv | 20398 | **11702** | −4.6% → **−45.3% WIN** | −59.3% |
| **class AGGREGATE** | 170654 | **145634** | −22.1% → **−33.5% (beats zstd)** | **−52.6%** |

`status_timeseries` (many float telemetry columns — balance/equity/margin) jumped
−4.6% → −45.3%. Zero-regression VERIFIED: tuned **0.158273 byte-identical** (RT 10/10),
holdout **0.2390 byte-identical** (RT 6/6).

## Verdict

**GO.** Decimal-column delta (ALP decimal-branch subset) deepens the telemetry/columnar
class from −22% to **−33.5% below zstd-19** (float-heavy files −45 to −56%), regression-
proof + byte-exact, tuned/holdout byte-identical. The new-class hunt succeeded: Cubrim
now structurally crushes zstd on scientific/financial/sensor float-column data.

**Remaining class losers** are unchanged (logs at the H-36 ceiling, 2 tiny <64KB files at
the H-39 ceiling). **Next lever (research Lever 2): H-41 DoubleDelta** for fixed-interval
timestamp/counter columns (delta-of-delta → ~1 bit/value on constant-rate metric exports;
neutral on irregular forex ticks via a variance gate).

**Code SHA:** committed on `feat/cubr-bigfiles` (this round's HEAD). Leaderboard untouched, NOT pushed.
