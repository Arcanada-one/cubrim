# Telemetry / columnar class-wide validation — world-corpus acquisition plan

**Track 1 (harden the proven win).** H-29/H-30 measured Cubrim's columnar field-split beating zstd-19 by **−22% aggregate** (forex_tick −27.7%, forex_usdchf −30.8%, status_timeseries flipped +7.1% loss → −3.1% win) on a **host-derived** 9-file class corpus, and beating gzip everywhere. To claim a **class-wide** win (not a host-corpus artefact) Cubrim must reproduce it on **representative public real-world telemetry**, disjoint from both the tuned 10-file corpus and the host-derived class corpus. This note specifies (a) the structural reason the win generalises, (b) the public datasets to acquire per sub-class, (c) the architectural caveat the ≤64 KB envelope imposes on wide tables.

All ceilings below are **literature estimates, not Cubrim measurements**. No Rust until a Python spike confirms the win on the acquired sample (project discipline). Hard gate untouched.

---

## 1. Why the columnar win generalises (mechanism, corpus-independent)

Column-major transposition (H-30) lays the i-th field of every record contiguously. Per column, values share a type and a narrow range, and are frequently monotonic (timestamps, counters) or low-cardinality (status, symbol, model). After transposition:

- **BWT** sees long runs / low local entropy per column → **geomix + rANS** code near the per-column entropy.
- The **row-major** byte stream zstd-19 sees has adjacent bytes from *different* fields (a timestamp byte beside a price byte beside a volume byte) = high local entropy; zstd's 32–128 KB window must re-learn the interleaving every record.

**Win condition (the generalisation):** *per-column self-similarity > per-record byte self-similarity*. This holds for **any regular-schema tabular / time-series / telemetry data**, which is exactly why the H-29 result is structural, not a forex quirk.

**Fair-comparison protocol (must match cubrim.com's claim):** the real-world claim is "Cubrim as a drop-in archiver on **raw** telemetry CSV/JSONL beats zstd-19 on the **same raw bytes**." Do NOT hand zstd the transposed layout — a user feeds raw CSV to both. This is the H-29 protocol; keep it.

---

## 2. Sub-classes + public datasets to acquire (all open/public, disjoint from existing corpora)

| Sub-class | Why Cubrim should win (mechanism) | Public source (raw CSV/text) | Lit-estimate ceiling |
|---|---|---|---|
| **Wide numeric telemetry CSV** | extreme width (170+ cols) + low-cardinality/zero SMART fields → columnar + dict + RLE crushes; row-major interleaving defeats zstd window | **Backblaze Drive Stats** — `YYYY-MM-DD.csv`, 87 SMART attrs × raw+normalized. HuggingFace `backblaze/Drive_Stats`, Kaggle `backblaze/hard-drive-test-data`, quarterly ZIP on B2 | dict+RLE 10–50× on low-card cols (BtrBlocks/Parquet) |
| **IoT / sensor time-series** | slowly-varying floats (temp/humidity/light/voltage) + monotonic 31 s timestamps → ALP + delta + BWT runs | **Intel Berkeley Lab** sensor data, MIT CSAIL `db.csail.mit.edu/labdata/labdata.html` (permissive: reuse with acknowledgement) | ALP float SOTA (SIGMOD'24); Gorilla ~12× on TS |
| **Financial tick data** | monotonic ts + slowly-varying price floats + volume; confirmed sub-class (forex −27%) | **CryptoDataDownload** OHLCV CSV (no login / no paywall — most reproducible) or **Dukascopy** free tick via `dukascopy-node` CLI | confirmed −27..−31% vs zstd (H-29, host forex) |
| **Urban / trip wide CSV** | mixed numeric + low-card categorical (payment_type, rate_code, location_id) | **NYC TLC trip records** — data.gov, AWS Open Data `nyc-tlc-trip-records-pds`, ClickHouse example dataset | dict+RLE on categoricals; delta on ids |
| **Prometheus / OpenTelemetry metrics** | repeated metric names + label sets + float values + timestamps; pivots to dense columns | scrape **node_exporter** `localhost:9100/metrics` (reproducible snapshot) — Prometheus text exposition format | columnar after label-pivot; delta-of-delta ts |
| *(optional)* **Climate/weather** | per-station daily numeric series | **NOAA GHCN-Daily** CSV | delta/FOR on numeric |

**Selection rules for A:** (1) each file ≥1 sub-class, ≥3 sub-classes total for a credible class claim; (2) DISJOINT from tuned + host class corpus; (3) commit the exact slice + a `gen_*.sh`/manifest with source URL + SHA so the bench is reproducible (CLAUDE.md: bench carries code SHA; corpus carries provenance); (4) run `--value-scheme bwt-rans` (the CLI default bitpack is 14× worse — H-29 trap).

---

## 3. Architectural caveat the ≤64 KB envelope imposes (IMPORTANT — affects whether the win reproduces)

Wide tables break naïve per-block transposition. Backblaze rows are ~1–2 KB each → a 64 KB block holds only ~30–60 rows → after a *per-block* transpose each column has only ~30–60 values, far too few for BWT to build runs. **The win requires per-column-GLOBAL transposition** (Parquet-style column chunks): transpose the WHOLE file's columns first, *then* chunk each column stream independently into ≤64 KB cube blocks. A per-64KB-row-block transpose (the easy implementation) will UNDER-deliver on wide tables and could read as "the win doesn't generalise" when it is really an implementation artefact.

→ **MODE_COLUMNAR must transpose globally per column, not per row-block.** Flag for the implementing session (A). This is the single highest-risk design decision for reproducing the H-29 win at scale.

---

## 4. Handoff to A (CUBR-CONT, variant 4): the dict+RLE low-cardinality column cascade

A is implementing ALP (H-38) for the **float** columns. The telemetry schema needs a **complete cascade** to win class-wide; ALP alone covers only floats. The strongest complementary structural class — where BWT+rANS already crushes by construction — is **low-cardinality categorical/enum columns via dictionary + RLE** (logged as **H-48** below). Full cascade per column type:

| Column type | Encoding | Hypothesis |
|---|---|---|
| timestamp | delta-of-delta (Gorilla) → rANS | H-31 (delta) + DoD refinement |
| float measurement | ALP decimal→int → FOR → rANS | **H-38 (A's current)** |
| **enum / categorical** | **dictionary → RLE → rANS** | **H-48 (handoff — Cubrim's structural strength)** |
| counter / id | FOR / PFOR | H-42 |

This is the BtrBlocks/Parquet two-stage stack (column-aware encoding *below* the entropy coder), proven to beat zstd on numeric data while decompressing ~10× faster.

---

## Refs

- Backblaze Drive Stats — https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data ; HuggingFace https://huggingface.co/datasets/backblaze/Drive_Stats
- Intel Berkeley Lab sensor data — https://db.csail.mit.edu/labdata/labdata.html
- NYC TLC trip records — https://registry.opendata.aws/nyc-tlc-trip-records-pds/ ; https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- CryptoDataDownload — https://www.cryptodatadownload.com/ ; dukascopy-node — https://github.com/Leo4815162342/dukascopy-node
- Prometheus text exposition / OpenTelemetry — https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/prometheus/
- BtrBlocks: Efficient Columnar Compression for Data Lakes (SIGMOD 2023) — https://www.cs.cit.tum.de/fileadmin/w00cfj/dis/papers/btrblocks.pdf
- ClickHouse database compression (encodings, dict/RLE cardinality thresholds) — https://clickhouse.com/resources/engineering/database-compression
