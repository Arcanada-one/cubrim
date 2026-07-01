# CUBR per-type grid — summary (all 6 types closed)

Per-type grid methodology (`CUBR-METHODOLOGY-per-type-grid.md`) applied to every hypothesis × the 6 World-Benchmark data types. champion `--value-scheme bwt-rans`, RT byte-exact, subsumption-control (transform vs no-transform through ONE backend), gate vs strong universals (xz-9e / 7z-PPMd / brotli-q11) — NOT zstd. All measurements on real version-locked corpora (provenance+SHA in the per-type reports). Codec.rs untouched throughout; nothing pushed (operator-gated).

## The grid (type × verdict × lever)

| Type | Sub-type | Verdict | Lever / transform | Headline measurement (champion, RT byte-exact) |
|---|---|---|---|---|
| **exe** | x86/x64 dense code | **GO (transform)** | **BCJ** E8/E9 rel→abs | ooffice +10.53% self-gain, **beats PPMd** (B/L 0.988); libc +1.96% (GO-self-only) |
| exe | code-sparse / tar | NO-GO | (BCJ over-triggers) | mozilla slice −0.47% |
| **image** | continuous-tone raster | **GO (transform)** | **MED** 2D predictor | kodim23 RGB **+24.49%**, **beats xz by 30%** (B/L 0.768) |
| image | bilevel/fax | NO-GO (subsumed) | XOR-up | ptt5 −2.21% |
| **binary** | fixed-width records | **GO (transform)** | **byte-plane SoA** | sao@28 +5.33%, closes **56%** of gap to xz |
| binary | doc / variable-record | NO-GO | (de-interleave destroys) | kennedy.xls −96.55% |
| **text** | natural-language prose | NO-GO (transform) | **backend** (PPMd-class) | cub/ppmd **1.314** aggregate |
| **code** | source code | NO-GO (transform) | **backend** (PPMd-class) | cub/L **1.145** aggregate (1.135 large .rs) |
| **database** | DB dump (osdb) | NO-GO (transform) | **backend** (PPMd-class) | byte-plane −58%; cub/ppmd 1.281 |

## Two lever families

1. **Type-gated structural transforms (3 GO types).** exe (BCJ), continuous-tone image (MED), fixed-width binary (byte-plane SoA). Each exposes structure the 1-D byte backend structurally cannot reach (sub-byte address relocation / 2D spatial / record-stride de-interleave). All are **type-gated** — engage only on the detected sub-type, byte-identical elsewhere — so each SHIPS for its GO type with zero regression risk on the others (competitive `min(raw, transform)` + id byte). exe and image **beat the strong universal leader outright**; binary closes 56% of the gap (gate-2).

2. **Orthogonal backend lever (3 NO-GO-transform types).** text, code, database share ONE lever: a **PPMd-class entropy backend** (high-order context + SEE). Their redundancy is high-order context, NOT a permutation/alignment/address pattern — no reversible transform can expose it (Gotcha #11). cubrim trails PPMd ~1.14–1.31× on these. This is the grid's honest negative space; the fix is `CUBR-BACKEND-SPIKE` (new value-scheme `ppmd`, GO-to-plan), which lifts ALL THREE at once.

## What the grid bought (vs the old global verdict)

Single/mixed-corpus testing buried type-specific wins by averaging opposite-sign cells:
- exe: a mixed corpus (mozilla-style code-sparse −0.47% + ooffice +10.53%) would have recorded a global NO-GO.
- image: bilevel −2.21% would have muddied continuous-tone +24.49%.
- binary: kennedy −96.55% would have drowned sao +5.33%.

The grid recovered three shippable transform wins (BCJ/MED/SoA) that the prior global-verdict approach had filed as NO-GO, and cleanly separated "no transform exists → backend lever" (text/code/database) from "transform exists but mis-applied" (bilevel/doc/code-sparse). **Methodology validated 3/3 transform flips + 3 honest backend-lever closures.**

## Next-action map

- **Ship-candidates (type-gated transforms, when greenlit, in priority order):** MED continuous-tone image (largest win, beats leader +30%) → BCJ exe (beats leader, +10.5%) → byte-plane SoA fixed-width binary (closes 56% gap). Each needs: detector (PE/ELF machine; raster geometry; fixed-width stride) + the standard mask/competitive-min + RT/property tests. codec.rs change gated on per-type GO (already have it).
- **Backend program:** PPMd-class value-scheme (`CUBR-BACKEND-SPIKE`, GO-to-plan) closes text/code/database simultaneously.
- **Standing rule:** every NEW hypothesis is computed as the full 6-type grid from the start; no global verdicts.

Per-type reports: `H-45-BCJ-exe-grid.md`, `H-39-image-2dpredictor-grid.md`, `H-40-binary-fieldsplit-grid.md`, `H-41-text-backend-grid.md`, `H-42-code-database-grid.md`. Corpora: `worldbench/{exe,image,binary,text,code,database}-corpus/`.
