# H-41 — DoubleDelta (delta-of-delta) for fixed-interval columns: NO-GO (subsumed)

**Status:** NO-GO (spike). DoubleDelta is subsumed by Cubrim's rANS/BWT entropy backend —
no Rust written. The fixed-interval metric class is ALREADY won by single-delta + entropy.

**Class targeted:** fixed-interval time-series (Prometheus/OpenTelemetry scrapes, IoT/sensor
exports) — research Lever 2 from the new-class ladder.

## Hypothesis

After first-order delta, a fixed-interval timestamp/counter column's delta is constant, so
delta-of-delta is 0 → ~1 bit/value (Gorilla/ClickHouse DoubleDelta). Add a variance-gated
second delta to the columnar delta stage.

## Spike (faithful — `probe_h41_doubledelta.py`, real cubrim backend)

Generated faithful fixed-interval corpora (`gen_fixedinterval_corpus.py`): Prometheus 15s
scrape (timestamp + float gauge + int gauge + monotone counter) and Intel-Berkeley-Lab 31s
sensor (epoch + 4 float sensors). Built the column-major stream with single-delta vs
double-delta on the numeric columns; compressed each through the real cubrim bwt-rans rail.

| file (corpus: generated fixed-interval) | single-delta | double-delta | gain | ts-col stddev/mean |
|---|---:|---:|---:|---:|
| prometheus_metrics.csv (267559 B) | 27235 | 29096 | **+6.8% WORSE** | c0 = **0.00** (constant 15s) |
| sensor_berkeley.csv (252565 B) | 11730 | 13244 | **+12.9% WORSE** | c0 = **0.00** (constant 31s) |

The variance gate confirms the columns ARE fixed-interval (delta stddev/mean = 0.00 — the
best case for DoubleDelta), yet double-delta is consistently **worse**.

## Why NO-GO (mechanism)

A fixed-interval column's single-delta is a **constant stream** (`15,15,15,…`), which
rANS/BWT already code to near-zero (one repeated symbol). DoubleDelta turns it into
`15,0,0,…` — also near-zero entropy, but the extra transform mixes a `15` prefix into the
column-major stream and very slightly *raises* entropy, so it loses. **DoubleDelta is
subsumed by a strong entropy backend** — exactly as BWT subsumes MTF. Gorilla/ClickHouse
win with DoubleDelta because they bit-pack with NO entropy coder (storing `15` repeatedly
costs bits/value there); Cubrim's rANS already pays ~0 for the constant.

## Bonus finding

The current codec (H-31 integer-delta + H-40 decimal-delta) **already crushes zstd-19 on
this class**: prometheus_metrics 32821 vs zstd 58354 = **−43.8%**; sensor_berkeley 11821
vs zstd 47801 = **−75.3%** (RT byte-exact). The fixed-interval metric class is won
decisively WITHOUT DoubleDelta.

## Verdict

**NO-GO.** DoubleDelta gives no structural gain (worse on fixed-interval through Cubrim's
entropy backend); the single-delta + rANS/BWT path already reaches the floor and crushes
zstd-19 by 44–75% on the class. No code written; codec byte-identical. Honest subsumption
result — the Gorilla DoubleDelta lever does not transfer to an entropy-coded pipeline.

**Next:** H-48 (enum dictionary→RLE→rANS, research handoff, flagged as a structural
strength of Cubrim's columnar/low-cardinality path).

**Code SHA:** spike on `d11dac5` (codec untouched). Leaderboard untouched, NOT pushed.
