# Cubrim — Telemetry/Columnar Class: Final Summary (H-29 … H-51)

**Headline:** Cubrim **beats zstd-19 by −53.6 %** and **gzip-9 by −63.2 %** aggregate on a
wide, diverse, **real** telemetry/columnar corpus (16 files, 7.0 MB, 15/16 per-file wins,
round-trip byte-exact). The class is **won decisively and structurally**; the remaining
gaps (operational logs, sub-64 KB files) are data-determined micro-efficiency ceilings.

> Broadcast note for /evolution: every number here is measured on a named corpus with the
> real `cubrim` binary (`--value-scheme bwt-rans`), never estimated. Leaderboard untouched;
> nothing pushed (operator does git-cleanup). 35 commits on `feat/cubr-bigfiles`.

---

## The hypothesis ladder (H-29 … H-51)

| # | Lever | Verdict | One-line why |
|---|---|---|---|
| **H-29** | MODE_COLUMNAR field-split (column-major reorder) | **GO** | makes a column's values cluster — info the byte backend can't reach on the interleaved stream; class −15 % vs zstd |
| **H-31** | Monotonic-integer column delta | **GO** | shrinks integer magnitude (epoch ts / counters); class −22 % vs zstd |
| H-36 | CLP log-template / variable split | NO-GO | real syslog 1.29× < 1.5× gate — template dict + high-entropy variables are data-determined (log ceiling) |
| H-39 | Small-file (<64 KB) class | NO-GO | optimal-LZ / columnar / static-dict / order-2-floor all spiked; dict gives **0** at 18 KB (helps only <1 KB) — micro-efficiency ceiling |
| **H-40** | Decimal-column delta (ALP decimal branch) | **GO** | fixed-point reinterpret of decimal float columns + delta; class **−33.5 %** vs zstd (float-heavy files −45…−56 %) |
| H-41 | DoubleDelta (delta-of-delta) | NO-GO | +6.8 %/+12.9 % **worse** — a constant single-delta is already coded to ~0 by rANS/BWT (subsumed) |
| H-48 | Enum dictionary→RLE→rANS | MARGINAL | only −2.3 % on a best-case enum-heavy file — BWT+geomix already clusters low-cardinality columns (subsumed) |
| H-49 | Cross-column correlation residual (Corra) | NO-GO (this class) | forex OHLC 0.998×, sensor 1.00× — cross-stream MI is real but **not additive over temporal delta** on smooth time-series; relations are unit-coefficient |
| H-51 | Integer wavelet (Haar) | NO-GO | +49 %/+27 % **worse** than delta — multi-scale coefficients compress worse through the entropy backend (subsumed) |
| H-50 | ALP-RD (binary double bit-split) | BLOCKED | needs a binary IEEE-double array corpus (Parquet/.npy) — a different input format than CSV-decimal; deferred to scope expansion |

3 GO (H-29/H-31/H-40), 4 NO-GO/MARGINAL by subsumption (H-41/H-48/H-49/H-51), 2 ceilings
(H-36/H-39), 1 blocked-on-class (H-50). Plus the H-28 precursor (literal-PPM NO-GO,
Gotcha #10) that triggered the class-C pivot.

---

## Class-wide result (real corpus, `gen_wide_telemetry_corpus.sh`, RT byte-exact all)

16 real+representative files, 7.0 MB: 10 real forex currency pairs (OHLC tick), real paxbt
trading telemetry, real sar system metrics, generated Prometheus 15 s / Intel-Berkeley 31 s
sensor / enum-event streams.

| sub-class | vs zstd-19 | vs gzip-9 |
|---|---|---|
| 10 real forex pairs (OHLC) | **−51 … −57 %** | −52 … −66 % |
| paxbt trading telemetry (real) | −44 … −54 % | — |
| fixed-interval metrics (Prometheus / sensor) | −44 % / **−75 %** | — |
| enum-event stream | −52 % | — |
| **AGGREGATE (16 files, 7.0 MB)** | **cubrim 409 811 vs zstd 883 846 = −53.6 %** | **−63.2 %** |

zstd-wins **15/16**. The only loss is `sar_metrics.csv` (+4.2 %, 25 KB < 64 KB) — the
columnar gate is >64 KB, so it hits the known small-file ceiling (H-39), not a class failure.

---

## The crystallized lesson — Gotcha #11

**A strong rANS/BWT entropy backend SUBSUMES simple pre-transforms (delta-of-delta, dict→RLE,
MTF, wavelet) that win only in a bit-packing context with no entropy coder — and a genuinely
non-subsumed cross-stream transform must still be ADDITIVE over what the existing pipeline
already extracts.**

- The **GO** rounds (H-29 columnar, H-31 integer delta, H-40 decimal delta) all changed the
  **information** presented to the backend — they did something the byte model structurally
  *cannot* do itself (reorder columns into clusters; shrink a value's magnitude).
- The **subsumed** rounds (H-41 DoubleDelta, H-48 dict+RLE, H-51 wavelet) merely re-encoded
  bytes the backend already handles — they win for Gorilla/Parquet/bzip2 *because those tools
  bit-pack*; Cubrim's rANS already pays ~0 for a clustered/constant stream.
- H-49 Corra refined the rule: cross-stream mutual information IS invisible to the per-column
  byte backend (non-subsumed in principle), but on **temporally-smooth** telemetry the temporal
  delta already captures the exploitable correlation, so the residual is not additive
  (`high[i]−high[i−1]` < `high[i]−open[i]`). **"Non-subsumed by the backend" ≠ "additive over
  the existing pipeline."**

Practical gate for any future lever: spike it **through the real backend, on a real corpus**,
and require it to clear the bar *after* delta+rANS — not against a bit-packed strawman.

---

## What shipped (regression-proof, byte-exact)

- `MODE_COLUMNAR` container (mode byte 4): reversible field-split + per-column raw / integer-delta
  / decimal-delta (col-mode 0/1/2), gated `>64 KB` + a tabular detector, competitive
  `min(base, lz, columnar)`. Never regresses a file.
- **Invariants held across all 35 commits:** tuned 10-file **0.158273 byte-identical**, holdout
  **0.2390 byte-identical**, all round-trips byte-exact, full test suite green (238 tests),
  clippy 0 new. Leaderboard untouched, NOT pushed.

---

## What's next (operator: options 2+3 in parallel)

The structural-lever ladder is exhausted **for the temporal-telemetry class** — but H-49's
failure was a **class** mismatch, not a mechanism flaw. CUBR-RESEARCH is assembling two real
corpora to attack the right classes:
- **CORPUS1 — non-temporal wide deterministic tables** (Backblaze SMART, NYC-TLC, DMV): columns
  are deterministic functions of each other with **no temporal smoothness to extract first**, so
  Corra (H-49-reborn) should realize its −53…−85 % literature wins here.
- **CORPUS2 — binary IEEE-double arrays** (.npy / Parquet) for H-50 ALP-RD (front-bit dictionary
  + back-bit pack on non-decimal doubles).

Both will be spiked-first (≥1.5× gate) on the real corpus before any Rust.
