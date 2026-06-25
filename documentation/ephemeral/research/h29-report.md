# H-29 — Class-C specialization (logs/telemetry/columnar): characterization + columnar-transform GO

**Strategy (operator 2026-06-24):** permanent continuous-improvement race until Cubrim
beats BOTH gzip-9 AND zstd-19; specialize on the class where Cubrim already structurally
beats zstd (BWT+geomix). H-29 = characterize the class, build a REAL corpus, find the
hardening lever, beat zstd reliably across the whole class (not one file).

## 1. Real class corpus (host-derived, DISJOINT from the tuned 10-file leaderboard)

`code/bench/gen_class_corpus.sh` — 9 real files: syslog (`journal.log`), app log
(`app_orchestrate.log`), package logs (`dpkg.log`, `alternatives.log`), build log
(`toolchain.log`), columnar numeric telemetry (`forex_tick.csv`, `forex_usdchf.csv`,
`status_timeseries.csv`), record CSV (`deals_record.csv`). Bytes are host-dependent
(like the holdout corpus); relative standing is the stable finding.

## 2. Baseline characterization (cubrim `--value-scheme bwt-rans` = competitive rail, RT PASS all)

| file | input | cubrim | gzip-9 | zstd-19 | vs zstd | vs gzip |
|---|---:|---:|---:|---:|---:|---:|
| app_orchestrate.log | 524288 | 19952 | 50846 | 23218 | **−14.1% WIN** | −60.8% |
| forex_tick.csv | 392274 | 58741 | 76885 | 61346 | **−4.2% WIN** | −23.6% |
| forex_usdchf.csv | 385131 | 55274 | 73842 | 55576 | **−0.5% WIN** | −25.1% |
| journal.log | 524288 | 19775 | 26303 | 18688 | +5.8% | −24.8% |
| status_timeseries.csv | 200000 | 22889 | 28761 | 21381 | +7.1% | −20.4% |
| deals_record.csv | 17796 | 3799 | 4290 | 3549 | +7.0% | −11.4% |
| dpkg.log | 109041 | 7303 | 8175 | 6764 | +8.0% | −10.7% |
| toolchain.log | 369191 | 30136 | 37120 | 27548 | +9.4% | −18.8% |
| alternatives.log | 18708 | 1238 | 1166 | 969 | +27.8% | +6.2% |
| **AGGREGATE** | 2540717 | **219107** | 307388 | 219039 | **+0.03%** | **−28.7%** |

**Honest characterization:** the `repeated.log −18%` win was a *specific* case (large,
maximally-repetitive), NOT the class. On a real diverse class corpus Cubrim **crushes
gzip (−28.7% aggregate, wins 8/9)** but only **ties zstd in aggregate** and **wins zstd
on just 3/9 files** (the wins — app_orchestrate, forex×2 — offset the losses). Goal:
flip the losses to wins.

> **CLI default trap (noted):** plain `cubrim compress` without `--value-scheme` uses a
> weak default (bitpack) and produced 14111/13447 on alternatives/deals (14× worse).
> All real benchmarking MUST pass `--value-scheme bwt-rans` (the competitive rail entry).

## 3. Hardening lever — columnar field-split transform (charged probe `probe_h29_columnar.py`)

Reversible column-major reorder (all col0 cells, then col1, …; delimiters kept →
exactly invertible, info-conservation-safe per Gotcha #8). Transformed bytes compressed
by the REAL cubrim binary (so the number is realizable); a 16 B reversibility header is
charged. This is research-agent hypothesis **H-30** (columnar pre-split), independently
confirmed by the data.

| file | row-order (current) | **col-major** | row vs zstd | **col vs zstd** |
|---|---:|---:|---:|---:|
| forex_tick.csv | 58741 | **44359** | −4.2% | **−27.7%** |
| forex_usdchf.csv | 55274 | **38457** | −0.5% | **−30.8%** |
| status_timeseries.csv | 22889 | **20710** | +7.1% LOSS | **−3.1% WIN (flipped)** |
| deals_record.csv | 3799 | **3702** | +7.0% | +4.3% (improved, not flipped) |

Columnar transposition moves the CSV/columnar sub-class from mostly-losing to **crushing
zstd by 27–31%** on the numeric telemetry files and **flips status_timeseries from +7.1%
loss to −3.1% win**. Only the tiny 18 KB string-heavy `deals_record.csv` stays behind
(small-block framing dominates; a future per-column delta / FSST string coder is the
follow-up — H-31/H-35). Timestamp-delta (H-31) did not fire in the probe (header row
poisons the naive monotonic detector); a real per-column detector would add more on the
forex epoch column.

## Verdict

**H-29 GO (probe-confirmed): columnar field-split is the class-C hardening lever.**
Realizes −27 to −31% vs zstd on numeric telemetry CSV and flips status_timeseries to a
win — regression-proof by construction (competitive `min(base, columnar)` + mode byte;
only emitted when strictly smaller and round-trips). **Next round = implement
MODE_COLUMNAR container** (byte-exact reversible field-split: dominant-delimiter detect,
per-row field-count side stream, column-major emit, competitive rail + RT/property
tests; tuned 0.158273 + holdout 0.2390 must stay byte-identical — guaranteed since the
transform only triggers on detected record-structured input and competes on size).

External research (`afa18d32` synthesis) seeded the H-30..H-36 candidate ladder for the
log sub-class (CLP-style template split is the high-ceiling log lever) — logged for the
evolution pipeline. The class is NOT a ceiling: columnar alone already turns aggregate
parity into clear per-file zstd wins on the columnar half.

Artefacts: `code/bench/gen_class_corpus.sh`, `probe_h29_columnar.py`, `h29-report.md`.

---

## H-29 IMPLEMENTATION — MODE_COLUMNAR shipped (codec change)

Implemented `MODE_COLUMNAR` (container mode byte 4): byte-exact reversible field-split.
Encode (`build_columnar_blob`/`encode_columnar`): split rows by `\n`, fields by a
detected delimiter (tries `, \t ; |`, keeps smallest), emit column-major; per-row
field-count side stream (LEB128) + the column-major byte stream are each nested-encoded
via `encode_base`. Decode (`decode_columnar`): reverse exactly, fail-closed. Wired into
`encode_with_config` as a competitive candidate `min(base, lz, columnar)` **gated on
`data.len() > cube_size_limit` (64KB)** + a tabular detector (≥16 rows, ≥2 cols, ≥90%
rows share the modal field count → excludes prose / JSON-lines). This gate makes every
≤64KB input byte-identical to v1 (frozen leaderboard untouched).

**Tests:** +5 (`test_mode_columnar_round_trips_and_shrinks_on_csv`, ragged/edge-cases,
not-selected-on-non-tabular, property random tables, truncated-no-panic). Full suite
**234 green** (220 lib + 14 integration, 0 failed); clippy 0 new warnings.

**Zero-regression VERIFIED:** tuned 10-file **0.158273 byte-identical** (18523/117032,
per-file = champion, RT 10/10); holdout **0.2390 byte-identical** (48255, RT 6/6 — config.json 66KB attempted columnar but tabular-gate rejected the JSON; data.csv 17KB <64KB untouched).

**Class corpus result (cubrim `--value-scheme bwt-rans`, RT PASS all):**

| file | before | **after** | vs zstd | mode |
|---|---:|---:|---:|---|
| forex_tick.csv | 58741 | **44397** | −4.2% → **−27.6% WIN** | columnar |
| forex_usdchf.csv | 55274 | **38514** | −0.5% → **−30.7% WIN** | columnar |
| status_timeseries.csv | 22889 | **20769** | +7.1% → **−2.9% WIN (flipped)** | columnar |
| **AGGREGATE** | 219107 | **185883** | **+0.03% → −15.1% (beats zstd)** | −39.5% vs gzip |

MODE_COLUMNAR flips the columnar sub-class to crush zstd by 27–31% and moves the WHOLE
class aggregate from a zstd tie to a decisive −15.1% zstd win. zstd-wins 3/9 → 4/9. The
remaining losses are the LOG files (journal +5.8%, toolchain +9.4%, dpkg +8.0%) and two
tiny <64KB files — the next levers are **H-31 (timestamp/monotonic-column delta, stacks
on columnar)** then **H-36 (CLP-style log-template split)**. The class is NOT a ceiling.
