# H-40 — binary field-split / byte-plane (per-type grid, STEP 3)

**Status:** in progress — spike running on the binary type (sao star catalog, kennedy.xls).

> Disambiguation: this is the **byte-plane / SoA de-interleave** transform for the **binary** type (methodology STEP 3, "field-split / byte-plane for binary/numeric — sao/kennedy.xls"). It is distinct from the shipped telemetry `H-40` (decimal-float→scaled-int column delta, GO on CSV telemetry). Same number in the brief's re-eval order; different mechanism/type.

**Method.** Per-cell, champion `--value-scheme bwt-rans`, RT byte-exact. A = cubrim(raw); B = cubrim(byte-plane-shuffled at record width W); L = strongest universal (min xz-9e/PPMd/brotli-q11). self-gain=(A−B)/A. Subsumption-control = A vs B through the SAME backend. Byte-plane SHUFFLE = de-interleave so all byte-offset-p of every W-byte record are contiguous (Structure-of-Arrays); pure permutation, reversible (self-RT asserted; real RT = inverse-shuffle(decompress(B)) == raw). Spike `/tmp/uci-dl/spike_h40_byteplane.py`. Codec.rs untouched, NOT pushed.

**Corpus (real, version-locked World Benchmark).**
- `sao_700k_w28.bin` — Silesia `sao` (SAO star catalog), first 700 000 B = 25 000 records × **28 B/record** (full file 7 251 944 = 28×258 998, record width exact). sha256 `2e030f8f527f4e6500f471bc93e4a3f8c50ed98ab36fb7597dd6b5d96d272ece`. Fixed-width binary records → prime SoA candidate.
- `kennedy.xls` — Canterbury `kennedy.xls`, Excel BIFF spreadsheet, 1 029 744 B (÷8 and ÷16 exact). sha256 `9af47239ca29dfe20e633f80bbbb9a4cc9783d0803d7b2b5626f42e4c3790420`. Structured doc (cell records interleaved with metadata) → de-interleave alignment uncertain.

## Measured (RT byte-exact)

**sao_700k (raw):** A=cub 484 866 | xz 439 112 | ppmd 464 314 | brotli 454 916 → L=xz 439 112 (cubrim raw ~10% behind xz).

| width W | B=cub shuffle | self-gain | B/L | gap-closed | cell |
|---:|---:|---:|---:|---:|---|
| **28 (record)** | **459 034** | **+5.33%** | 1.045 | **56% of A→L** | **GO** (gate2: ≥50% gap) |
| 14 (½ record) | 488 991 | −0.85% | 1.114 | — | NO-GO (misaligned) |
| 7 (¼ record) | 539 752 | −11.32% | 1.229 | — | NO-GO (misaligned) |

(A→L gap = 484 866−439 112 = 45 754; W=28 closes 25 832 = 56% ≥ 50% → GO despite not overtaking xz.)

**Reading (sao):** the gain is **sharply peaked at the true 28-B record width** (+5.33%) and turns negative at sub-record strides (14: −0.85%, 7: −11.32%) — strong evidence this is a real Structure-of-Arrays alignment effect, NOT noise: de-interleaving at the actual field stride groups each star-record column (RA/Dec/mag high bytes vary smoothly across sorted stars → runs the backend captures); misaligned strides scramble fields and hurt. self-gain +5.33% ≫ +1.5% floor ⇒ NOT subsumed by the backend. cubrim+shuffle does not overtake xz (B/L 1.045) but closes 56% of the A→L gap, satisfying gate 2 ⇒ **GO(binary·fixed-width-records)**. Requires the correct record width (known/detected).

**kennedy.xls (raw):** A=cub 52 874 | xz 51 868 | ppmd 138 741 | brotli 61 498 → L=xz 51 868 (cubrim raw already ~2% off xz; ppmd catastrophic on xls).

| width W | B=cub shuffle | self-gain | B/L | cell |
|---:|---:|---:|---:|---|
| 8 | 103 924 | **−96.55%** | 2.004 | **NO-GO** (destroys structure) |
| 16 | 114 430 | −116.42% | 2.206 | NO-GO |
| 4 | 88 956 | −68.24% | 1.715 | NO-GO |

**Reading (kennedy.xls):** byte-plane is **catastrophic** (−96.55% at stride 8). kennedy.xls is BIFF (variable-length records, strings, metadata interleaved), NOT a fixed-width record stream — de-interleaving at any stride scrambles the document and doubles the size. cubrim already compresses it near xz (52 874 vs 51 868) with NO transform. Clean NO-GO — and it demonstrates the transform is sharply **input-shape-gated**: it requires genuine fixed-width records.

## Verdict vector

**H-40 byte-plane/SoA: GO{binary·fixed-width-records} · NO-GO{binary·structured-doc / database·xls} · NO-GO{misaligned-width}.**

- **GO on fixed-width binary records** (sao @ true 28-B width: self-gain **+5.33%**, non-subsumed, closes **56%** of the A→L gap → gate 2 met). Sharply peaked at the real record width (14→−0.85%, 7→−11.32%), confirming a real SoA alignment effect, not noise.
- **NO-GO on structured documents** (kennedy.xls −96.55%): no fixed record stride exists; de-interleave destroys the data; cubrim already ≈xz without it.
- **Type-gating requirement:** the transform needs the **correct record width**, known or detected (min-residual-entropy stride scan). It is cleanly gatable (apply only when a confident fixed-width stride is detected AND `min(raw,shuffle)` wins; byte-identical otherwise) → SHIPS for fixed-width binary records, never engages on docs/text.

**Honest scope.** sao @ W=28 does NOT overtake xz (B/L 1.045) — it closes 56% of the gap, which clears the methodology's gate-2 (≥50% gap), so it is a real GO, but a *weaker* one than H-45/exe (beat leader) or H-39/image (beat leader by 30%). The SoA lever is the same family as the shipped MODE_BINFLOAT (H-54 LiDAR) — confirms binary fixed-width arrays are a genuine cubrim transform class, here extended to integer/mixed records (star catalog), not just float arrays.

**Methodology validation: 3rd PASS** — the grid split a binary "field-split" idea into GO{fixed-width} vs catastrophic-NO-GO{xls}; a single mixed-binary corpus would have averaged +5.33% and −96.55% into a misleading global NO-GO and buried the sao win.

## Productionization notes (pre-Rust, when greenlit)
1. Detect fixed-width record stride (min-residual-entropy scan over candidate widths; require a clear minimum) — only engage when confident.
2. Byte-plane SoA + competitive `min(raw, shuffle_W)` + width byte → regression-proof; byte-identical on docs/text/non-record binary.
3. Overlaps shipped MODE_BINFLOAT (float arrays); generalise it to integer/mixed fixed-width records (the sao case is uint/mixed, not float).

Codec.rs untouched (spike only). NOT pushed.
