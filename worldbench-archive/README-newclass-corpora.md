# New-class corpora for the next research rounds (research agent 7aae20fd)

Two real, public corpora collected per `.brief-research-newclass.txt` — for the structurally-NEXT classes after telemetry-A was exhausted (−53.6% vs zstd class-wide). Both are disjoint from the tuned corpus, the host class corpus, and the world bench. All ceilings are **literature estimates, not Cubrim measurements**; every named transform helper is a **MANDATORY charged decoder branch** (Gotcha #7); **spike before Rust**.

| Corpus | Dir | Target hypothesis | Gotcha #11 criterion | Lit ceiling (estimate) |
|---|---|---|---|---|
| 1 — non-temporal wide deterministic tables | `corpus1-wide-deterministic/` | H-49 **reborn** (cross-column residual, on the RIGHT class) | (ii) cross-stream MI | Corra −53..−85% beyond single-column |
| 2 — raw IEEE-754 double arrays | `corpus2-raw-doubles/` | H-50 (ALP-RD full real-double bit-split) | (i) sub-byte field separation | ALP ×4.3 (vs Patas ×2.1 / Chimp ×2.4) |

Per-corpus provenance, SHAs, empirical structure checks, and reproduce steps: each dir's `MANIFEST.md`. Build script: `build_corpora.py`.

## Ranking — give A **CORPUS 2 first**

Ranked by *expected whole-file structural slack*, honouring A's own H-49 refinement ("non-subsumed ≠ additive; a single predicted column is a fraction of the file"):

1. **CORPUS 2 (raw doubles → ALP-RD) — FIRST.** The file is **100 % `float64`**, so the sub-byte slack applies to the *entire* file, not a correlated subset. The PRIMARY array (`…_zscore_f64.npy`) is **0.000 % short-decimal-representable** — measured, so ALP-decimal (H-40) is provably inapplicable and any win is genuinely ALP-RD's. No temporal-delta competitor (it's not a time series). Cleanest, largest, most certain non-subsumed slack → most likely to clear a GO gate. Lit ×4.3.

2. **CORPUS 1 (cross-column) — SECOND.** Directly unblocks the H-49 reborn (forex was temporal-smooth; these rows are independent records with no temporal delta to compete with). **Within it, hand `covtype_cartographic.csv` before `adult_census.csv`:** Covtype's 40 `Soil_Type` one-hots are perfectly mutually exclusive (verified 20 000/20 000 rows) → 40 columns collapse to one ~5.3-bit categorical, so the cross-column redundancy spans *many* columns at once (large whole-file slack), directly answering A's "single predicted column is a fraction of the file" objection. Adult's `education ↔ education_num` is an exact 1:1 bijection but is only one pair of 15 columns (smaller whole-file slack — keep as the clean determinism control).

## Honest caveat carried from A's H-49 NO-GO

A cross-stream / sub-byte transform must beat **what Cubrim's existing pipeline already extracts**, not the raw column. CORPUS 2 sidesteps this (no temporal delta on a static double matrix; decimal path provably off at 0 %). CORPUS 1 sidesteps the *temporal* part (independent records) but the spike must still charge the predictor/one-hot-index helper and clear the GO gate on the **whole file**, where the one-hot collapse (covtype) gives the best odds.
