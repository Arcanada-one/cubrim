# CUBR-0021 — QA Report (Research NO-GO Verification)

**Task:** Per-axis alphabet partitioning & variable per-axis bit-width — deep N-selection research
**Stage:** /dr-qa (autonomous)
**Date:** 2026-06-19
**Verdict:** **PASS** — sound, honest, reproducible NO-GO. A rigorous NO-GO is the valid deliverable.

This task is a RESEARCH finding with no Rust implementation (AC-4 correctly not entered, since NO-GO). QA therefore validates the rigor, mathematical soundness, honesty, and reproducibility of the analysis — not code round-trip.

---

## 1. Verdict-correction math is sound (INDEPENDENTLY VERIFIED)

The orchestrator corrected the analysis subagent's "GO (conditional)" (driven by a per-axis-isolated 50% saving on `dense` N=2 axis-0) to NO-GO, on the grounds that a value lies on ALL N axes simultaneously, so its realisable invertible width = **max-over-axes** width, not the per-axis minimum.

**Independently confirmed correct — and the correction is if anything understated:**

- I recomputed per-axis max slice cardinality from the raw corpus (NOT via the probe) and reproduced the probe's axis widths exactly. On `dense` N=2: axis-0 width = 4 bits (the 50% isolated figure), axis-1 width = 8 bits. Realisable = max = 8 bits → 0% saving. Matches the probe.

- **Decisive invertibility test (counterexample).** The isolated 4-bit/value scheme on `dense` axis-0 requires the decoder to recover `data[i]` from 4 bits. Those 4 bits can only index *within* a slice's local alphabet (≤16 of 256 bytes). There are 256 axis-0 slices, each with its own ~16-symbol alphabet. Making it invertible costs a per-slice local-alphabet side table:
  - bitstream "saving" = (8−4)×4096 = 2048 bytes
  - side table to invert = Σ(local alphabet sizes)×8 = 3984 bytes
  - **NET = −1936 bytes (a LOSS) on a 4096-byte file.**

  So the per-axis-isolated narrow width is not merely "double-freeing across axes" — any honest attempt to realise it invertibly pays a side table that exceeds the saving. The max-over-axes model is the correct invertible floor, and the corrected verdict is mathematically sound.

- **Is there ANY invertible scheme that beats max-over-axes (which would flip to GO)?** No. phi coordinates derive from POSITION (`x_k=(i//B^k) mod B`), not from VALUE, so phi cannot induce a value-alphabet partition. The bit-width spent on a value is bounded below by the widest axis it occupies. No per-axis variable-width scheme reaches a lower per-value width without paying side information ≥ the saving. The verdict does NOT flip to GO.

## 2. Operator's key question answered with real measured evidence — YES

"Does phi spread the alphabet evenly across axes?" — answered with measured cardinality/CV tables on all 7 files × N={2,3,4,6,8,12}. On every real-data file the realisable (max-over-axes) per-axis width equals the base width → 0% narrowing. axis-0 slices (stride-B sampling) and at least one sibling axis are full/near-full on real data. Evidence is real and reproducible (manifest SHA `4ee979f3…`, byte-identical rerun).

Minor prose imprecision (non-blocking, see Findings): the report states axis-0 "ALWAYS captures the full alphabet" — true for narrow-alphabet files but on `dense`/`random_high` axis-0 max card is 16, not 256. The *operative* claim (realisable=max-over-axes=base because a sibling axis is full) is unaffected and correct; the verdict logic uses the realisable max, not the axis-0 prose.

## 3. Non-duplication of CUBR-0019 — CONFIRMED genuinely different

- **CUBR-0019:** H(X_t|X_{t-1}) of the i-order VALUE SEQUENCE — an entropy of a 1-D sequence; N-invariant by construction (`phi_inv(phi(i))==i`).
- **CUBR-0021:** per-axis slice cardinality — count of distinct byte values within positions sharing the k-th phi coordinate; a geometric/combinatorial quantity that varies per axis and per N. CUBR-0019 never computed this.

The probe measures slice cardinality (`measure_axis_alphabets`), not sequence entropy, and does not re-derive 0019's N-invariance. Same root cause (phi maps position not value) reached from a different measurement direction — that is convergent evidence, not duplication.

## 4. Honesty / real-numbers — PASS

- All numbers measured; manifest SHA-256 `4ee979f3…` and Code SHA `46c05ed4…` present in report header.
- Baseline is the current **0.587240** (CUBR-0020). The stale 0.489444 appears only in the task-description AC text and is correctly NOT used in the report or probe.
- Proxy caveat present (per-axis cardinality is necessary-not-sufficient; Rust bench is ground truth).
- No fabricated or estimated figures detected.

## 5. Reproducibility — PASS

Reran `code/bench/alphabet_axis_probe.py` against the corpus (venv `code/.venv`). Output is **byte-identical** to the committed report (ignoring nothing — even the Code SHA line matches `46c05ed4…`). Manifest SHA matches. Same NO-GO, same 25.0% realisable / 50.0% isolated headline, same numbers.

## 6. AC coverage

- **AC-1 (per-axis cardinality table):** MET — 7 files × N={2,3,4,6,8,12}, all axes, with max/min/mean/CV. Injectivity guard B^N≥L holds for all N≥2 (max L=16384 < B²=65536), so no skipped rows expected — guard respected.
- **AC-2 (theoretical savings):** MET — per-axis ceil(log2(max_slice_card)) vs base width, with realisable (max-over-axes) and isolated (min) both reported transparently.
- **AC-3 (honest go/no-go):** MET — NO-GO, answering the operator's key question with evidence. "Alphabet spread evenly across axes" is an explicitly valid result per the AC.
- **AC-4 (impl only if GO):** Correctly SKIPPED (NO-GO).

---

## Findings (non-blocking)

- **F1 (cosmetic, prose).** The report's "axis-0 ... ALWAYS see the full alphabet" overstates for `dense`/`random_high` (axis-0 max card = 16 there). The realisable verdict is unaffected (it binds on the full sibling axis), but a future do-stage edit could tighten the prose to "axis-0 and/or a sibling axis is full-alphabet on real data" for precision. Not a verdict-affecting flaw; documented for accuracy per the Cubrim disclosure truthfulness rule.

No blocking findings. Boundaries respected: probe and report were not modified; corpus/probe were rerun read-only for verification; no merge/push.
