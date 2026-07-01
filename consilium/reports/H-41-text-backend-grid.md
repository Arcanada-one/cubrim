# H-41 — text type: backend lever, not a transform (per-type grid, STEP 4)

**Status:** NO-GO(text·transform) — no structural transform applies to natural-language text; the only lever is a stronger entropy backend (PPMd-class), already GO-to-plan in CUBR-BACKEND-SPIKE. This grid cell QUANTIFIES the cubrim→ppmd text gap per-file.

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. Per file: A=cubrim(raw text) vs L=strongest universal (min xz-9e/PPMd/brotli-q11). No transform B — natural-language prose has no reversible structural pre-transform (unlike exe/image/binary): its redundancy is high-order *context*, which is a backend/model property, not something a permutation/filter can expose (Gotcha #11 — and the frequency-ordered-BPE front-end H-39-ladder is table-charged and loses on ≤MB blocks). So the text cell measures the gap and attributes the lever. Spike `/tmp/uci-dl/measure_h41_text.sh`. Codec.rs untouched, NOT pushed.

**Corpus (real, version-locked):** Canterbury `alice29.txt`, `lcet10.txt`, `plrabn12.txt` (full); Silesia `dickens` first 1 MB. English prose.

## Measured (RT byte-exact)

| file | bytes | cubrim | xz-9e | PPMd | brotli | L | cubrim/L |
|---|---:|---:|---:|---:|---:|---|---:|
| alice29.txt | 152 089 | 49 707 | 48 528 | **38 986** | 46 487 | ppmd | **1.275** |
| lcet10.txt | 426 754 | 126 476 | 119 488 | **96 553** | 113 416 | ppmd | **1.310** |
| plrabn12.txt | 481 861 | 175 221 | 165 456 | **132 529** | 163 267 | ppmd | **1.322** |
| dickens_1mb.txt | 1 000 000 | 309 771 | 294 516 | **235 007** | 289 644 | ppmd | **1.318** |
| **AGG(text)** | 2 060 704 | 661 175 | | (ppmd ≈503k) | | min | **1.314** |

## Reading

- **PPMd dominates text by ~1.27–1.32×** over cubrim champion on every prose file; cubrim also trails xz and brotli (cubrim/xz ≈ 1.02–1.06). cubrim's BWT+rANS/geomix is a mid-tier text model; PPMd's high-order context mixing (order-4..6 + SEE) is the text SOTA among universals.
- **No transform flips this.** Text redundancy is order-N context, not a permutation/alignment/address structure — there is nothing for a BCJ/MED/SoA-style reversible transform to expose. This is the methodology's expected NO-GO for the *transform* axis on text.

## Verdict vector

**H-41 text: NO-GO(transform) · LEVER = backend.** The text-type gap to the strong leader (PPMd, ~1.27–1.32×) is real and large but is **not addressable by a type-gated transform** — it is a backend-strength deficit. The fix is the **PPMd-class entropy backend** (CUBR-BACKEND-SPIKE: GO-to-plan, new value-scheme `ppmd`), which CUBR-BACKEND-SPIKE measured would lift cubrim to rank 2–3 on every holdout text file. This grid cell confirms and quantifies the target the backend plan must hit on text (~−24% to reach PPMd parity).

**Methodology note.** This cell is the honest *negative space* of the grid: not every type has a transform lever. exe/image/binary flipped via transforms (H-45/H-39/H-40); text does not — its lever is orthogonal (backend). Recording it prevents wasting spike budget hunting a text transform that cannot exist.

Codec.rs untouched (measurement only). NOT pushed.
