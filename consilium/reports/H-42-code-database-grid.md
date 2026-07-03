# H-42 — code & database types (per-type grid, STEP 5: final 2 types)

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. code = backend-gap measurement (A=cubrim vs L=strong universal; like text, no reversible structural transform exists for source). database = byte-plane SoA spike (A=cubrim raw vs B=cubrim shuffled at candidate record widths; subsumption-control A vs B same backend; same protocol as sao H-40). Real version-locked corpora. Spikes `/tmp/uci-dl/measure_h41_text.sh` + `spike_h40_byteplane.py`. Codec.rs untouched, NOT pushed.

---

## (a) code type — backend lever, NO-GO(transform)

**Corpus (real):** Canterbury `grammar.lsp` (3 721), `fields.c` (11 150), `cp.html` (24 603); repo Rust source concat `cubrim_src_concat.rs` (533 116, version-locked). sha256 of the .rs: `41954233837ee92ddce9b6…`.

| file | bytes | cubrim | xz | ppmd | brotli | L | cubrim/L |
|---|---:|---:|---:|---:|---:|---|---:|
| grammar.lsp | 3 721 | 1 441 | 1 292 | 1 177 | 1 125 | brotli | 1.281 |
| fields.c | 11 150 | 3 408 | 3 032 | 2 761 | 2 717 | brotli | 1.254 |
| cp.html | 24 603 | 8 032 | 7 652 | 6 692 | 6 895 | ppmd | 1.200 |
| cubrim_src_concat.rs | 533 116 | 103 161 | 96 504 | **90 856** | 94 375 | ppmd | **1.135** |
| **AGG(code)** | 572 590 | 116 042 | | | | min | **1.145** |

**Reading.** Source code behaves like text: cubrim trails the strong leader (ppmd/brotli) by 13.5% (large .rs) to 28% (tiny files; small-file micro-efficiency inflates the gap). There is **no reversible structural transform** for source code — its redundancy is high-order token/context structure (a backend/model property), not a permutation/alignment/address pattern a BCJ/MED/SoA-style filter can expose. **Verdict: NO-GO(code·transform) · LEVER = backend** (PPMd-class, CUBR-BACKEND-SPIKE GO-to-plan). Identical conclusion to text (H-41).

---

## (b) database type — byte-plane SoA on osdb

**Corpus (real):** Silesia `osdb` (Open Source DB benchmark binary), first 1 048 576 B. sha256 `79c5f0f50af5dbb61368cf…`. Candidate record widths from a lag-equality autocorrelation scan (peaks at W≈4/8/100/200).

**osdb raw:** A=cub 341 396 | xz 314 072 | **ppmd 266 614** | brotli 312 387 → L=ppmd (cubrim raw 28% behind ppmd; ppmd dominates the text-heavy DB dump).

| width W | B=cub shuffle | self-gain | B/L | cell |
|---:|---:|---:|---:|---|
| 4 | 540 911 | **−58.44%** | 2.029 | **NO-GO** (destroys) |
| 8 | 673 478 | −97.27% | 2.526 | NO-GO |
| 100 | 861 940 | −152.48% | 3.233 | NO-GO |

**Reading (osdb).** Byte-plane is catastrophic (−58.44% at W=4) — the autocorrelation "peaks" were spurious; osdb is a **text-heavy DB dump with variable-length records**, NOT a fixed-width binary table like sao. De-interleave scrambles it. cubrim raw is already 28% behind ppmd (the lever is the backend, as for text/code), and no SoA stride helps. **NO-GO(database·transform) · LEVER = backend.** Distinct from sao (genuine 28-B fixed-width records → SoA GO); osdb proves the binary-SoA GO is record-structure-gated, not "database type" generally.

## Verdict vectors

- **H-42 code: NO-GO(transform) · LEVER = backend** — cubrim trails ppmd/brotli 1.135–1.281× (AGG 1.145); source redundancy is high-order context, no reversible structural transform; same family as text (H-41). Fix = PPMd-class backend.
- **H-42 database: NO-GO(transform·byte-plane) · LEVER = backend** — osdb byte-plane catastrophic (−58%); the DB dump is variable-record + text-heavy (ppmd dominates by 28%); the binary-SoA GO (sao H-40) requires genuine fixed-width records, which osdb lacks. Fix = PPMd-class backend (+ field-split only on truly tabular fixed-width DB exports, the sao/telemetry case).

**Methodology note.** code & database both fall in the grid's backend-lever negative space alongside text — three of six types share one orthogonal lever (PPMd-class backend), while exe/image/binary-fixed-width have type-gated transform levers. Recording the negatives prevents wasted spike budget.

Codec.rs untouched (spike only). NOT pushed.
