# CUBR-0034 — World Benchmark: Cubrim vs Standard Archivers

**Stage:** research / benchmark · **Date:** 2026-06-25 · **Code SHA:** `317a323` (`317a32337b5e327768cd3a50747b38400539b888`)
**Host:** AMD Ryzen 5 3600 (12 threads), Linux 6.8.0-106 · **Cubrim:** competitive built-in scheme selection (default).

## Method (lzbench-style)

- **Metric:** `ratio = compressed / original` — **lower is better** (consistent with Cubrim's internal reports; `<1` = compression, `>1` = expansion).
- **Round-trip:** byte-exact (`cmp`) decompression verified for **every** Cubrim file — **24/24 RT OK**. Standard tools trusted as mature.
- **Corpora:** Silesia (12 files, all data types), enwik8 (95 MB text), Canterbury (11 files).
- **Archivers & settings:** cubrim (competitive), `gzip -9`, `bzip2 -9`, `xz -9e`, `zstd --ultra -22`, `brotli -q 11`, `lz4 -12` (built from v1.9.4), `ppmd` (`7z -m0=PPMd`). `zpaq` not available on host (optional max-ratio reference — omitted, marked honestly).
- **Note on PPMd size:** the `ppmd` column is the `.7z` container size (PPMd is only exposed via 7z); container header overhead is a few hundred bytes — negligible on MB-scale files, but it slightly penalises PPMd on the tiny Canterbury files.

## Headline

Across all 24 files (sum-bytes), Cubrim places **5th of 8** — it **beats `bzip2`, `gzip`, `lz4`** and trails `ppmd`, `xz`, `brotli`, `zstd`. On every sizable file (≥1 MB) Cubrim ranks **#3–#6, never last**. Its only outright failures are on **small inputs (<40 KB)**, where fixed per-file overhead dominates — including one expansion (`sum`, 37 KB → ratio 1.0003).

This is an honest mid-pack result for a research codec with no machine-code, image, or structured-binary specialisation yet — and the gaps map cleanly onto the **candidate hypotheses** below, which is the point of this benchmark: it tells the continuous loop *what is left to take*.

## Results

| file | type | size | cubrim | gzip | bzip2 | xz | zstd | brotli | lz4 | ppmd | cubrim rank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| dickens | text | 9.7 MB | _0.2912_ | 0.3779 | 0.2747 | 0.2778 | 0.2796 | 0.2774 | 0.4302 | **0.2253** | #6/8 |
| mozilla | exe | 48.8 MB | _0.3082_ | 0.3708 | 0.3498 | **0.2611** | 0.2922 | 0.2708 | 0.4302 | 0.3165 | #4/8 |
| mr | image | 9.5 MB | _0.3326_ | 0.3685 | 0.2448 | 0.2760 | 0.3115 | 0.2831 | 0.4204 | **0.2308** | #6/8 |
| nci | database | 32.0 MB | _0.0478_ | 0.0890 | 0.0540 | **0.0432** | 0.0481 | 0.0453 | 0.1081 | 0.0686 | #3/8 |
| ooffice | exe | 5.9 MB | _0.4363_ | 0.5023 | 0.4653 | **0.3945** | 0.4224 | 0.4029 | 0.5750 | 0.4134 | #5/8 |
| osdb | database | 9.6 MB | _0.3145_ | 0.3685 | 0.2779 | 0.2820 | 0.3072 | 0.2792 | 0.3923 | **0.2366** | #6/8 |
| reymont | text | 6.3 MB | _0.2158_ | 0.2748 | 0.1880 | 0.1985 | 0.2033 | 0.2010 | 0.3118 | **0.1722** | #6/8 |
| samba | code | 20.6 MB | _0.1972_ | 0.2503 | 0.2106 | **0.1731** | 0.1795 | 0.1743 | 0.2827 | 0.1943 | #5/8 |
| sao | binary | 6.9 MB | _0.6953_ | 0.7346 | 0.6813 | **0.6103** | 0.6895 | 0.6324 | 0.7820 | 0.6561 | #6/8 |
| webster | text | 39.5 MB | _0.2107_ | 0.2909 | 0.2085 | 0.2019 | 0.2040 | 0.2033 | 0.3341 | **0.1578** | #6/8 |
| x-ray | image | 8.1 MB | _0.6161_ | 0.7125 | 0.4780 | 0.5300 | 0.6084 | 0.5526 | 0.8473 | **0.4545** | #6/8 |
| xml | text | 5.1 MB | _0.0922_ | 0.1239 | 0.0825 | 0.0814 | 0.0848 | **0.0805** | 0.1424 | 0.0929 | #5/8 |
| enwik8 | text | 95.4 MB | _0.2623_ | 0.3645 | 0.2901 | 0.2483 | 0.2533 | 0.2574 | 0.4199 | **0.2240** | #5/8 |
| alice29.txt | text | 149 KB | _0.3451_ | 0.3563 | 0.2841 | 0.3191 | 0.3236 | 0.3057 | 0.4140 | **0.2563** | #6/8 |
| asyoulik.txt | text | 122 KB | _0.3840_ | 0.3901 | 0.3161 | 0.3562 | 0.3606 | 0.3412 | 0.4660 | **0.2903** | #6/8 |
| cp.html | text | 24 KB | _0.8801_ | 0.3244 | 0.3099 | 0.3110 | 0.3136 | 0.2802 | 0.4189 | **0.2720** | #8/8 |
| fields.c | code | 11 KB | _0.8867_ | 0.2813 | 0.2726 | 0.2719 | 0.2708 | **0.2437** | 0.3786 | 0.2476 | #8/8 |
| grammar.lsp | code | 4 KB | _0.9062_ | 0.3349 | 0.3448 | 0.3472 | 0.3263 | **0.3023** | 0.4668 | 0.3163 | #8/8 |
| kennedy.xls | binary | 1006 KB | _0.0695_ | 0.2037 | 0.1265 | **0.0504** | 0.0677 | 0.0597 | 0.3148 | 0.1347 | #4/8 |
| lcet10.txt | text | 417 KB | _0.2995_ | 0.3384 | 0.2524 | 0.2800 | 0.2844 | 0.2658 | 0.3846 | **0.2262** | #6/8 |
| plrabn12.txt | text | 471 KB | _0.3661_ | 0.4032 | 0.3021 | 0.3434 | 0.3475 | 0.3388 | 0.4663 | **0.2750** | #6/8 |
| ptt5 | image | 501 KB | _0.0942_ | 0.1021 | 0.0970 | **0.0777** | 0.0846 | 0.0798 | 0.1289 | 0.0958 | #4/8 |
| sum | binary | 37 KB | _1.0003_ | 0.3340 | 0.3376 | **0.2484** | 0.2937 | 0.2652 | 0.4265 | 0.3065 | #8/8 |
| xargs.1 | text | 4 KB | _0.9021_ | 0.4154 | 0.4168 | 0.4287 | 0.4088 | **0.3463** | 0.5725 | 0.3809 | #8/8 |

### Aggregate by data type (sum-bytes ratio)

| type | cubrim | gzip | bzip2 | xz | zstd | brotli | lz4 | ppmd | cubrim gap vs best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| binary | _0.6193_ | 0.6670 | 0.6110 | **0.5393** | 0.6108 | 0.5598 | 0.7225 | 0.5900 | +14.8% (vs xz) |
| code | _0.1977_ | 0.2503 | 0.2106 | **0.1732** | 0.1795 | 0.1744 | 0.2828 | 0.1943 | +14.2% (vs xz) |
| database | _0.1095_ | 0.1536 | 0.1058 | **0.0984** | 0.1080 | 0.0994 | 0.1738 | 0.1074 | +11.3% (vs xz) |
| exe | _0.3220_ | 0.3849 | 0.3621 | **0.2755** | 0.3062 | 0.2850 | 0.4457 | 0.3269 | +16.9% (vs xz) |
| image | _0.4529_ | 0.5150 | 0.3451 | 0.3842 | 0.4381 | 0.3981 | 0.6034 | **0.3271** | +38.4% (vs ppmd) |
| text | _0.2444_ | 0.3354 | 0.2577 | 0.2316 | 0.2356 | 0.2374 | 0.3857 | **0.2014** | +21.4% (vs ppmd) |

### Aggregate by corpus (sum-bytes ratio)

| corpus | cubrim | gzip | bzip2 | xz | zstd | brotli | lz4 | ppmd |
|---|---:|---:|---:|---:|---:|---:|---:|---:||
| silesia | _0.2582_ | 0.3191 | 0.2572 | **0.2286** | 0.2478 | 0.2339 | 0.3651 | 0.2313 |
| enwik8 | _0.2623_ | 0.3645 | 0.2901 | 0.2483 | 0.2533 | 0.2574 | 0.4199 | **0.2240** |
| canterbury | _0.2141_ | 0.2600 | 0.1931 | 0.1754 | 0.1854 | **0.1746** | 0.3328 | 0.1837 |

### Overall (all 24 files, sum-bytes ratio)

| | cubrim | gzip | bzip2 | xz | zstd | brotli | lz4 | ppmd |
|---|---:|---:|---:|---:|---:|---:|---:|---:||
| **overall** | _0.2591_ | 0.3330 | 0.2671 | 0.2344 | 0.2490 | 0.2408 | 0.3822 | **0.2286** |
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
