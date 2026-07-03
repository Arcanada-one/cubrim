# H-45/H-37 — BCJ x86 filter for executables (per-type grid, STEP 1 spike)

**Status:** GO(exe) — **flip CONFIRMED** false-NO-GO → GO on dense x86 code. First validation of the per-type grid methodology (`CUBR-METHODOLOGY-per-type-grid.md`).

**Method.** Per-cell, champion `--value-scheme bwt-rans`, RT byte-exact. A = cubrim(raw); B = cubrim(BCJ-filtered); L = strongest universal on the type (min of xz-9e / 7z-PPMd / brotli-q11). self-gain = (A−B)/A. GO(type) ⟺ self-gain ≥ +1.5% AND B ranks up vs L (or closes ≥50% of the A→L gap). Gate is NOT vs zstd-19.

**BCJ filter.** Reversible x86 E8/E9 rel↔abs conversion, non-overlapping skip-5, modular arithmetic — opcode bytes never modified ⇒ identical trigger positions on encode/decode ⇒ provably invertible (self-roundtrip verified on random 10 KB). Unconditional (no 0x00/0xFF mask) — i.e. a *pessimistic* BCJ that over-triggers on non-code bytes; the real LZMA x86 mask would only improve non-code regions. Spike script: `/tmp/uci-dl/spike_h45_bcj.py`.

**Corpus (real, version-locked World Benchmark — Silesia + system).**
- `ooffice_640k.bin` — Silesia `ooffice` first 640 KB, PE32 x86 DLL (dense .text). sha256 `0b1bf46e8e8c111e9da04f5b6a7028c88f153676afa4de6be5a24e25983e45f8`
- `mozilla_640k.bin` — Silesia `mozilla` @2 MB +640 KB (tar of x86 executables; this slice is code-sparse). sha256 `d5efd6f85219187a3f8d18ad45c9a4ce1dd9496237c6a3b6201315edcc88a1b6`
- `libc_640k.bin` — `/usr/lib/x86_64-linux-gnu/libc.so.6` @128 KB +640 KB, ELF-64 dense .text. sha256 `8021744eac7b879abb23c2549297e32578c0273d1088cc118c3fb05e47a0bbaa`

## Measured (bytes, all RT byte-exact OK)

| file | A=cub raw | B=cub+BCJ | self-gain | xz-9e | PPMd | brotli | L | B/L | cell |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| ooffice_640k (PE x86, dense) | 322 674 | **288 710** | **+10.53%** | 300 056 | 292 159 | 305 315 | ppmd | **0.988** | **GO** |
| libc_640k (ELF-64 PIC, dense) | 288 357 | 282 706 | **+1.96%** | 267 384 | 268 632 | 271 768 | xz | 1.057 | GO(self-only) |
| mozilla_640k (tar, code-sparse) | 472 749 | 474 957 | −0.47% | 468 608 | 478 008 | 464 167 | brotli | 1.023 | NO-GO (slice) |

## Reading

- **ooffice = clean GO(exe):** self-gain +10.53% (≫ +1.5% noise floor → NOT subsumed by the backend), and B (288 710) **beats the strongest universal** PPMd (292 159), B/L 0.988. Without BCJ, cubrim was ~10% behind PPMd (A/L = 1.104); with BCJ it **takes the lead**. Full rank-up + >100% gap closed. RT byte-exact.
- **libc = GO(self-only):** self-gain +1.96% is above the +1.5% non-subsumption floor (BCJ is a REAL gain here too), but B (282 706) does not overtake the leader xz (267 384, B/L 1.057) and closes only 27% of the A→L gap (<50%), so gate 2 fails. Lower self-gain than ooffice because libc is a **PIC shared object** — heavy PLT/GOT *indirect* calls, fewer direct E8 rel32 targets for BCJ to canonicalise. Still non-subsumed, ship-gated, low priority.
- **mozilla = NO-GO on this slice, and it is honest WHY:** the @2 MB slice of the mozilla tar is dominated by data/resources, not x86 code, so the unconditional E8/E9 filter mostly converts false-positive bytes → +noise (−0.47%). This is the methodology's exact thesis in reverse — a mixed/code-sparse region *drowns* the exe gain — and motivates (a) running BCJ only on detected code sections and (b) adding the standard 0x00/0xFF mask.

## Verdict vector

**H-45 BCJ: GO{exe·PE-dense} · GO-self-only{exe·ELF-PIC} · NO-GO{code-sparse}.** The mechanism is real and **non-subsumed on every dense-code exe** (self-gain ooffice +10.53%, libc +1.96% — both > the +1.5% floor), strongly winning on PE (beats the strong leader PPMd) and modestly on PIC ELF (real gain, doesn't overtake xz). Since BCJ is cleanly **type-gated** (apply only on detected x86/x64 exe/PE/ELF; byte-identical elsewhere), it SHIPS for the exe type per the methodology's shipping rule, regardless of non-exe cells.

**Methodology validation: PASS.** The grid flipped a false global-NO-GO into a measured GO(exe) — single-corpus/mixed-corpus testing had buried this type-specific win (mozilla's code-sparse −0.47% is exactly how a mixed corpus would have recorded a global NO-GO). Proceeding to STEP 2+ (H-39 image 2D predictor, H-40 binary field-split, H-41 text backend) per the brief.

## Productionization notes (pre-Rust, when greenlit)

1. Add the real LZMA x86 mask (convert only when post-transform top byte ∈ {00,FF}) — protects code-sparse/non-code bytes (would lift mozilla toward neutral/positive).
2. Detect target type (PE/ELF machine field) and apply the arch-correct BCJ (x86 E8/E9; ARM/ARM64/RISC-V variants for those machines).
3. Competitive `min(raw, bcj)` + 1 filter-id byte ⇒ regression-proof; non-exe inputs byte-identical.

Codec.rs untouched (spike only). NOT pushed.
