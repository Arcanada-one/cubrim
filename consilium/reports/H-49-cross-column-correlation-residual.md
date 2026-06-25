# H-49 — cross-column correlation residual (Corra-class)

**Status:** NO-GO (spike, no Rust). RANK #1 non-subsumable candidate, but it does NOT
reach the ≥1.5×-over-H-40 gate on the named real correlated telemetry — the cross-column
MI is real but NOT additive over Cubrim's existing temporal delta. Fallback: H-50/H-51.

**Class targeted:** columnar / telemetry (extends the PROVEN H-29/H-30/H-31 win). Composes with MODE_COLUMNAR + ALP.

## Hypothesis

After columnar transposition, encoding a correlated/derived column B as a residual `B − predict(A)` against a source column A (and feeding the residual to bwt-rans) reduces compressed size beyond what per-column compression can reach, because the mutual information between separate columns is unreachable by a per-column byte backend.

## Why it is NON-SUBSUMABLE (Gotcha #11 gate, criterion ii — cross-stream MI)

A strong BWT+rANS backend models order-N byte context, runs, and suffix-grouped contexts **within a single stream**. After MODE_COLUMNAR splits the table into per-column streams, each column is compressed INDEPENDENTLY — the backend has no mechanism to exploit that column B is a function of (or correlated with) column A. That mutual information is structurally invisible to it. A cross-column predictor extracts it by computing the residual, an operation the byte model cannot perform. This is why it is not another subsumed pre-pass (unlike DoubleDelta H-41 / dict+RLE H-48, which only re-arrange bytes the backend already sees).

Real telemetry is dense with this structure:
- **Backblaze** `smart_N_raw` ↔ `smart_N_normalized` — a deterministic function → residual ≈ 0.
- OHLC tick: bid↔ask, high ≥ low ≥ close.
- IoT sensor: temperature ↔ voltage.
- Trip/DMV: city ↔ zip, fare ↔ total_amount.

## Expected lever (estimate — NOT a Cubrim measurement)

Corra (VLDB 2024, TUM): correlation-aware encoding saves **−53.7%** (DMV zip_code), **−58.3%** (lineitem receiptdate), **−85.16%** (Taxi total_amount) *beyond* single-column encoding.

## Charged helper (MANDATORY decoder branch)

Per-correlated-pair predictor: which column predicts which + coefficients (linear) or value→value map (categorical) + an exception list for mispredictions. Small relative to the savings, but it MUST be charged in the spike (Gotcha #7 family — a transform that stores a predictor must pay for it). Competitive `min(independent, residual)` per column → regression-proof; columns with no exploitable correlation fall back to independent coding.

## Mandatory spike (before Rust)

1. On a real wide table (Backblaze raw/normalized pair, or OHLC bid/ask), fit a cheap predictor A→B; compute residual.
2. Run bwt-rans on (independent B) vs (residual + charged predictor + exceptions); compare bytes.
3. Confirm the saving survives charging the helper. Only then wire as a MODE_COLUMNAR sub-encoding.

## Refs

- Corra: Correlation-Aware Column Compression, Liu et al., VLDB CloudDB 2024 — https://arxiv.org/abs/2403.17229
- Lightweight Correlation-Aware Table Compression — https://arxiv.org/html/2410.14066

## Measured (faithful, charged — `probe_h49_crosscol.py` / `probe_h49_v2.py`)

Baseline = current H-40 path (every numeric column decimal/int-delta'd independently).
Corra = source = first decimal column; each same-scale decimal column coded as the
cubrim-smaller of {independent-delta, residual-delta}, predictor charged (source-index +
linear coefficients). Whole-file column-major stream through the real cubrim bwt-rans rail.

| corpus | baseline | corra (subtraction) | corra (fitted-linear) | ×/H-40 | gate ≥1.5× |
|---|---:|---:|---:|---:|---|
| forex_tick.csv (real OHLC) | 26315 | 26315 (0 res-cols) | 26361 | **0.998×** | ❌ |
| forex_GBPJPY.csv (real OHLC) | 31066 | 31066 (0 res-cols) | — | **1.00×** | ❌ |
| sensor_berkeley.csv (real multi-channel) | 11719 | 11719 / 12872 | — | **1.00×** | ❌ |
| synth_corr.csv (deterministic control: normalized=2·raw+13, total=a+b) | 54505 | 46975 | **41210** | **1.32×** | ❌ |

Even the **deterministic** control (a column that is an exact linear function of another)
reaches only 1.32× whole-file with a fitted-linear predictor — below the gate — because a
single perfectly-predicted column is a fraction of the file. On the named real telemetry
(forex OHLC, sensor) cross-column residual gives **0.998×–1.00× — no win at all**.

## Verdict

**NO-GO** (gate ≥1.5×-over-H-40 not met; forex OHLC 0.998×, sensor 1.00×). The
non-subsumption argument is correct in principle — cross-stream mutual information is
invisible to the per-column byte backend — **but it is NOT additive over Cubrim's existing
temporal delta (H-31/H-40).** Two structural reasons on the telemetry class:
1. **Temporal correlation dominates cross-column on smooth time-series.** Cubrim already
   delta-codes each column; for slowly-drifting OHLC, `high[i]−high[i−1]` (temporal delta)
   is *smaller* than `high[i]−open[i]` (cross-column residual). The residual the backend
   "can't see" is bigger than the delta it already exploits.
2. **OHLC/sensor cross-column relations are unit-coefficient** (high≈open, channels track),
   so the residual is just the intra-row spread — not crushed. Fitted-linear only helps
   *non-unit* deterministic pairs (Backblaze raw↔normalized, derived sums), which (a) are
   not in the temporal-telemetry class Cubrim wins and (b) still only reach 1.32× whole-file.

Corra's −53..−85% literature wins are on **non-temporal wide tables** (DMV, lineitem,
Backblaze) where columns are deterministic functions of each other and there is no temporal
smoothness to extract first. That is a different data shape from Cubrim's won time-series
telemetry. **Lesson (refines Gotcha #11): "non-subsumed by the backend" ≠ "additive over the
existing pipeline" — a cross-stream transform must beat what temporal delta ALREADY extracts,
not the raw column.** No Rust written; codec byte-identical. Next: H-50 (ALP-RD full double
bit-split) / H-51 (int-wavelet).

**Code SHA:** spike on `bee0549` (codec untouched). Leaderboard untouched, NOT pushed.
