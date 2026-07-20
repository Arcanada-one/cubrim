
## Where Cubrim already competes

Balance first — the codec is not uniformly behind:

- **`nci` (database, 32 MB): #3/8 — 0.0478**, beating bzip2/zstd/brotli/ppmd; only `xz` (0.0432) ahead.
- **`xml` (5.1 MB): #5 but 0.0922** vs leader 0.0805 — a 14% gap, tight.
- **`ptt5` (bilevel fax image): #4 — 0.0942**, ahead of zstd/brotli/ppmd — Cubrim's RLE-friendly path already handles bilevel raster well (contrast the continuous-tone medical images below).
- **All 13 files ≥1 MB rank #3–#6.** Cubrim is a credible general compressor; the losses are *specialisation gaps*, not a broken core.

## Where Cubrim loses — honest accounting

Two distinct failure modes:

1. **Transversal: small inputs (<40 KB).** Five Canterbury files (`cp.html`, `fields.c`, `grammar.lsp`, `xargs.1`, `sum`) place **#8/8** with ratios **0.88–1.0003** while every standard tool hits 0.24–0.35. `sum` (37 KB SPARC ELF) **expands** (1.0003). This is fixed-overhead domination, independent of data type, and is the single most damaging result.
2. **Per-type specialisation gaps** (sum-bytes, cubrim vs best-in-class):
   - **image +38.4%** (vs ppmd) — worst; continuous-tone medical scans `mr`/`x-ray`.
   - **text +21.4%** (vs ppmd) — PPM/order-N context depth.
   - **exe +16.9%** (vs xz) — no BCJ machine-code filter.
   - **binary +14.8%** (vs xz) — interleaved numeric records `sao`/`kennedy.xls`.
   - **code +14.2%** (vs xz).
   - **database +11.3%** (vs xz) — smallest gap.

## Weakest classes → candidate hypotheses

Each weakness is an **entry point for the next continuous-loop round** (as H-29 columnar field-split was born from a telemetry-CSV gap). Ranked by ROI.

### H-A — Small-input fallback & header diet *(transversal — HIGHEST ROI, also a correctness fix)*
- **Gap:** 5 files <40 KB at ratio 0.88–1.0003 vs pack 0.24–0.35; `sum` is the only **expansion** in the whole benchmark.
- **Root cause:** per-file structures (φ-map, distance-map, cube scaffolding, per-scheme tables) carry a fixed cost that dominates when the value count `L` is small; the competitive selector is not escaping to a tight direct path for tiny inputs.
- **Lever / mechanism:** (1) a true **stored-block escape** so output never exceeds `~orig + ε` (`sum` must not expand); (2) a **small-mode** that skips cube scaffolding and runs `lz-rans`/`entropy` directly with a minimal header; (3) shared/static default tables for tiny streams.
- **Potential:** very large — moves 5 files from 0.88–1.0 to ~0.27–0.35 (pack parity) and removes the expansion case. Structural, not a tuning knob.
- **Ref:** zstd/xz/brotli all ship stored-block fallback + small-window modes; brotli embeds a static dictionary for small inputs.

### H-B — BCJ-class machine-code filter for `exe` *(clean known lever; leapfrogs zstd)*
- **Gap:** exe +16.9% vs xz (`mozilla` 0.3082 vs 0.2611; `ooffice` 0.4363 vs 0.3945). Tell-tale: `xz` beats cubrim **and** zstd/brotli on exe specifically — the BCJ signature.
- **Lever / mechanism:** x86/ARM/SPARC relative `CALL`/`JMP` operands encode position-dependent targets; converting **rel→abs (or delta-vs-position)** collapses identical call sites into LZ-matchable repeats. Apply as a pre-LZ filter (architecture-detected).
- **Potential:** BCJ-x86 typically yields **5–15%** on executables — closes most of the mozilla/ooffice gap to xz, and since **zstd/brotli have no BCJ**, Cubrim could *overtake* them on this class.
- **Ref:** LZMA SDK BCJ/BCJ2 (`xz --x86`), the canonical executable filter.

### H-C — 2D spatial pixel predictor for continuous-tone images *(largest type gap)*
- **Gap:** image +38.4% vs ppmd. `mr` 0.3326 vs ppmd 0.2308 / bzip2 0.2448; `x-ray` 0.6161 vs ppmd 0.4545. (Bilevel `ptt5` already fine — the gap is specifically continuous-tone medical grayscale.)
- **Lever / mechanism:** `mr`/`x-ray` are 16-bit grayscale scans with strong 2D spatial correlation invisible to a 1D byte pipeline. A **MED/Paeth/GAP predictor over the pixel grid + entropy-coded residuals** (LOCO-I / JPEG-LS / CALIC) exploits neighbour correlation. Needs an image-geometry (row-stride) probe — a stride-autocorrelation search transform.
- **Potential:** large — JPEG-LS routinely beats general compressors **30–50%** on medical grayscale; could move `mr`→~0.23 and `x-ray`→~0.45, reaching bzip2/ppmd.
- **Ref:** JPEG-LS (ISO 14495, LOCO-I), CALIC; PNG Paeth as a cheap first step.

### H-D — Structured field-split / byte-plane shuffle for numeric records & floats
- **Gap:** binary +14.8% vs xz. `sao` (star catalog, fixed-width numeric records) 0.6953 vs 0.6103; `kennedy.xls` 0.0695 vs 0.0504 (+38%).
- **Lever / mechanism:** de-interleave fixed-width records into **per-column / per-byte-plane streams** (SoA transpose + byte shuffle) so slowly-varying high bytes of floats/ints cluster and become RLE/LZ-friendly; optional intra-column delta. Generalises **H-29 columnar field-split** to a stride-autocorrelation-detected record width.
- **Potential:** moderate-high — Blosc/SPDP byte-shuffle gets **10–40%** on float arrays; `sao`'s #6 placement with a +14% gap is the classic interleaved-record loss.
- **Ref:** Blosc byte-shuffle, SPDP, FPC float predictor; the project's own H-29 is direct precedent.

### H-E — Stronger text backend *(hardest, long-horizon)*
- **Gap:** text +21.4% vs ppmd (enwik8 0.2623 vs ppmd 0.2240 / xz 0.2483); Cubrim trails the PPM/order-N coders on all sizable text.
- **Lever / mechanism:** ppmd wins via high-order context mixing. The project's gotchas #9/#10 show naive context-modelling of the φ literal/value residue is a **mirage** — so the realistic lever is a stronger **LZ + entropy backend** (`lz-rans` with better literal/offset FSE modelling) and/or a **word-model static dictionary** for natural language, *not* deeper φ context.
- **Potential:** modest, high-effort. Catching `xz` (0.2483 on enwik8) is realistic; catching `ppmd` is not, near-term. Frame as backend-efficiency, not a structural quick win.
- **Ref:** PPMd (Shkarin PPMII), brotli static dictionary + context modelling; bounded by the project's H-25/H-28 literal-model NO-GOs.

### Priority for the roadmap ladder
**H-A** (correctness + biggest win) → **H-C** (largest type gap) and **H-B** (clean lever, overtakes zstd on exe) → **H-D** (moderate, reuses H-29) → **H-E** (long-horizon backend efficiency). Goal restated: lossless parity-or-better with the leaders on **every** data type — this benchmark scopes exactly what remains.

## Reproduction

- Corpora: Silesia `sun.aei.polsl.pl/~sdeor/corpus/silesia.zip`, enwik8 `mattmahoney.net/dc/enwik8.zip`, Canterbury `corpus.canterbury.ac.nz/resources/cantrbry.tar.gz`.
- Runners: `run_cubrim.sh` (per-file compress + byte-exact RT, 8-way parallel), `run_std.sh` (7 archivers), `aggregate.py`, `gen_report.py`.
- Machine-readable results: `results/CUBR-0034-benchmark.json` (publication block for cubrim.com `/evolution` — "Мировой бенчмарк").
- Caveat: all Cubrim numbers were produced by the **competitive default** scheme selector at SHA `317a323`; re-running on a newer SHA may shift them — record the SHA with any update.
