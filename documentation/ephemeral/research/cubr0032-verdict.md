# CUBR-0032 — Content-Derived φ Feasibility: Consilium Verdict

**Stage:** /dr-design (L3, multi-vendor consilium)
**Date:** 2026-06-21
**Verdict:** NO-GO (high confidence — two independent vendor arguments + deterministic measurement)

## Question

Can a φ derived from content (computed from value statistics, not input
position) place data sparsely in the cube so distance-map + value-stream beats
T4 (aggregate 0.587240; GO threshold 0.575495)?

## Panel

Real multi-vendor mode on the arcana-dev cluster. 2-of-3 healthy (degraded
panel per consilium rules):

| Slot | Vendor | Status | Candidate φ | Position |
|------|--------|--------|-------------|----------|
| A | claude (opus-4.8) | ok | Value-Stratified φ (transmitted permutation) | NO-GO |
| B | codex (gpt-5.x) | degraded — ChatGPT usage limit (retry 14:25) | — | — |
| C | cursor (composer) | ok | OIVR-φ (occurrence-indexed value routing, side-map) | NO-GO |

Both healthy vendors reasoned independently (identical brief, no cross-leak) and
converged on NO-GO via complementary arguments. Codex was unavailable; a third
vote would not change a unanimous NO-GO already confirmed by measurement.

## The two arguments (independent, converging)

**Vendor C — value-stream lock (OIVR-φ).** Place byte b[i] at coordinate
(value, occurrence-rank). The value stream stays strict i-order, so it PASSES
Gotcha #3 by construction (runs preserved, 42→42 not 42→1886). But because the
value stream is unchanged, it is *locked at T4*; the only lever left is the
distance-map, whose ceiling is ~8 bytes corpus-wide (CUBR-0012) — far below the
~608 bytes needed to clear −2%. And when any value occurs >256 times the side-map
overflows into kilobytes of spill. Predicted NO-GO.

**Vendor A — information conservation (Value-Stratified φ).** Any content-derived
φ that is a *transmitted bijection* over L positions conserves information: the
φ-map permutation P costs exactly H(order | value-multiset). The value-stream
saving ΔV and the φ-map cost M are positively coupled — both scale with the
i-order disorder φ removes — so M ≥ ΔV on every file. Net ≥ T4 + distance-map
overhead > T4, identically. A also surfaced the key trap: **Gotcha #3's narrow
entropy probe is insufficient here** — a sort-by-value φ passes the probe, but
the run-scatter penalty does not vanish, it *relocates* into the φ-map branch.
Only the Gotcha #6 full-branch model catches it.

## Deterministic arbiter (the GO/NO-GO decision)

Probe `cubr0032_content_phi_probe.py` measured the steel-man candidate (OIVR-φ —
the one that passes Gotcha #3) on the actual canonical 7-file corpus, Gotcha-#6
complete (4 cost terms = 4 decoder branches, asserted):

| file | L | ρ | cells | spill | distmap B | φ-spill B | OIVR B | T4 B | pick |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sparse_clustered | 2048 | 0.0289 | 1895 | 153 | 272 | 612 | 1387 | 502 | T4 |
| dense | 4096 | 0.0625 | 4096 | 0 | 292 | 0 | 4402 | 4109 | T4 |
| text | 16384 | 0.1055 | 6912 | 9472 | 287 | 37888 | 43881 | 5705 | T4 |
| log_like | 16384 | 0.1308 | 8571 | 7813 | 313 | 31252 | 38884 | 7318 | T4 |
| binary_mixed | 8192 | 0.1250 | 8192 | 0 | 447 | 0 | 8653 | 8205 | T4 |
| random_high | 4096 | 0.0625 | 4096 | 0 | 288 | 0 | 4398 | 4109 | T4 |
| sparse_small | 256 | 0.0039 | 256 | 0 | 99 | 0 | 369 | 269 | T4 |

- **OIVR-pure aggregate: 1.981771** (101974 B) — ~2× WORSE than T4.
- **Competitive min(OIVR,T4) aggregate: 0.587240** — floors at T4, zero gain.
- GO threshold 0.575495 not approached on any path.

Both kill conditions fired against the candidates: no file shows M < ΔV − D
(vendor A's falsifier), and the H[v]>256 overflow expands exactly as vendor C
predicted (text +37888 B, log_like +31252 B of φ-map).

## Why this is structural, not corpus-specific

The result generalizes beyond the corpus. Under positional φ the coordinate is
*free* (implied by order). Any content-derived φ must *pay* for the coordinate
information it adds — and that payment equals (by conservation) the disorder it
removes from the value stream. The cube principle's compression has to come from
the value-stream coder (T4 / BWT, Gotcha #4), not from the coordinate layout.
The distance-map lever is inert because making the cube sparse never costs less
than the sparsity buys.

## Recommendation

- **CUBR-0032: NO-GO.** The content-derived-φ distance-map line is closed by
  measurement and by an information-conservation argument that does not depend on
  the corpus. This closes the entire distance-map branch (CUBR-0028/29/30/31/32).
- The only confirmed value-stream lever remains **BWT** (CUBR-0028 GO, −14.1%) —
  it escapes the conservation trap precisely because it encodes its permutation
  implicitly (LF-mapping + one index), which a transmitted φ-map cannot.
- **Lesson for the rulebook (candidate Gotcha #7):** Gotcha #3's order-1 entropy
  probe is necessary but NOT sufficient for any φ that transmits a permutation —
  the scattered-run cost relocates into the φ-map branch and only a Gotcha-#6
  full-branch model exposes it. Add the φ-map (permutation) cost as a mandatory
  branch whenever a candidate stores coordinates.

## Artifacts

- docs/ephemeral/research/CUBR-0032-consilium-brief.md — vendor brief
- datarim/pub-consilium/CUBR-0032/draft-A-claude.md — vendor A verdict
- datarim/pub-consilium/CUBR-0032/draft-C-cursor.md — vendor C verdict
- datarim/pub-consilium/CUBR-0032/run-log.jsonl — provenance + degradation
- docs/ephemeral/research/cubr0032_content_phi_probe.py — deterministic arbiter
- docs/ephemeral/research/cubr0032-content-phi-verdict.json — measured numbers
