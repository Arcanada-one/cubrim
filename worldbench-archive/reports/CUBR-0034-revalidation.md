# CUBR-0034 — Champion Re-Validation on the World Corpus

**Stage:** research / re-validation · **Date:** 2026-06-25 · **Code SHA:** `317a323`
**Premise (operator):** the shipped binary already contains every GO scheme (H-13→H-29). The world benchmark on 24 unseen files (Silesia + enwik8 + Canterbury) is therefore the largest independent re-validation of the champion to date — a third witness after the tuned 10-file leaderboard and the 6-file holdout. This document asks: **which past GO/WIN verdicts were corpus-overfit to the tuned leaderboard and do not transfer?**

## 0. Methodology correction found during re-validation (important, honest)

The first world-benchmark pass invoked `cubrim compress <in> <out>` **without `--value-scheme bwt-rans`**. The CLI default is `ValueScheme::BitpackFixed` — the *weak* v1 path. The competitive BWT-family rail (BwtRans/Order2Rans/Adaptive/CtxMix/GeoMix/LzRans, `codec.rs:98–117`) is only engaged when the `bwt-rans` umbrella scheme is requested. This is exactly the **H-29 "CLI default trap"** ("plain `compress` uses weak bitpack default, 14× worse on small files; all bench MUST use `--value-scheme bwt-rans`").

Effect was severe and concentrated on small files (measured, RT-verified):

| file | size | default (BitpackFixed) | champion (bwt-rans) |
|---|---:|---:|---:|
| cp.html | 24 KB | 0.8801 | **0.3264** |
| sum | 37 KB | 1.0003 (expands!) | **0.3458** |
| grammar.lsp | 3.7 KB | 0.9062 | **0.387** |

**The "small-file catastrophe" reported in the first pass was a benchmark-harness bug, not a Cubrim weakness.** All champion numbers below are re-measured with `--value-scheme bwt-rans`, round-trip byte-exact. (The earlier `world-benchmark.json` must be regenerated before publication — see §4.)

## 1. GO/WIN hypothesis inventory (claimed corpus + number)

All champion-ladder numbers are **aggregate ratio on the tuned 10-file corpus** unless noted. Source: `consilium/hypothesis-log.md`, `CUBR-CONT-STATUS.md`.

| Hyp | Scheme / feature | Claimed corpus | Claimed number |
|---|---|---|---|
| H-13 / CUBR-0028 | BwtEntropy (scheme 6) | tuned (7→10 file) | 0.504412 (7f) → 0.299337 (10f leader) |
| H-19 | BwtRans (scheme 7) | tuned 10-file | **0.221726** (−25.9% vs BwtEntropy) |
| H-20 | Order2Rans (scheme 8) | tuned 10-file | 0.207618 (−6.36% rel) |
| H-21 | BwtAdaptive (scheme 9) | tuned 10-file | 0.177122 (−20.12% rel) |
| H-22 | BwtContextMix (scheme 10) | tuned 10-file | 0.168262 (−24.11% rel) |
| **H-24** | **BwtGeoMix (scheme 11) — CHAMPION** | tuned 10-file | **0.158273** (beats gzip 0.159674 by −0.88%) |
| H-25g | MODE_LZ combined sequence coder | synthetic 120 KB long-range | 5211 B ≈ zstd-19 5202 (ties on long-range) |
| H-25i/j-full | optimal parse + BT match finder | srctree.tar / multiversion.bin | narrows zstd gap to +7–8% |
| H-25k | offset-code (seq_format 2) | synthetic pure-duplicate | −11% on pure-dup only |
| H-29 | columnar field-split (MODE_COLUMNAR) | class-C telemetry CSV (host-derived) | −27…−31% vs zstd on forex/status CSV |

**Already-known non-transfer (the holdout, 6 diverse real files, disjoint from tuned):** Cubrim 0.2390 vs gzip 0.2359 vs zstd-19 0.2214 — **+1.3% behind gzip, +8.0% behind zstd, loses to zstd 6/6**. On all 6 holdout files `bwt-rans` output is **byte-identical to `bwt-geomix`** — the H-24 geomix aggregate edge does **not** reproduce per-file on unseen data. (The earlier "2.2× worse than gzip" holdout was the *pre-ceiling-fix* run — a separate 64 KB raw-store architectural bug, since fixed; not the geomix overfit.)

## 2. Structural invariants vs corpus-tuning

The re-validation hinges on one architectural fact: **the competitive `min()` rail (Gotcha #4).** Every value-scheme is emitted only when it is *strictly smaller* than every sibling for that file/block, with the winner's scheme byte in the header. So:

**STRUCTURAL invariants — correct on ANY corpus, rail self-selects, cannot regress:**
- **Round-trip byte-exactness** (R6 lossless) — corpus-independent; world RT = 24/24 OK.
- **The competitive rail itself** — adding a scheme can never worsen any file (min over a superset). Every H-19→H-29 scheme is, *as a rail member*, structurally safe.
- **BWT front-end** — builds its own locality (escapes Gotcha #3/#7); valid wherever run-structure exists.
- **rANS vs Huffman** (sparse freq tables + fractional coding) — a genuine, corpus-independent integer-rounding + table-size win.
- **MODE_LZ whole-file pre-pass + optimal/BT parse** — architecturally valid; *activates by size pick* only when cross-block long-range structure exists.
- **MODE_COLUMNAR field-split** — reversible; activates only when a columnar layout wins.

**CORPUS-TUNING — numbers to re-evaluate (do NOT transfer verbatim):**
- **The champion aggregate `0.158273` and the claim "Cubrim beats gzip."** This is a tuned-10-file artefact. Falsified once on the holdout (+1.3% behind gzip); the world corpus is the second, larger falsification.
- **The H-24 geomix distinct edge.** geomix == bwt-rans byte-for-byte on every unseen file measured (holdout 6/6 + world spot-checks) → geomix contributes nothing beyond the rail on unseen data; its −5.91%/−0.88% headline is tuned-corpus-only.
- **The intermediate ladder relative gains** (H-20 −6.36%, H-21 −20.12%, H-22 −24.11%) — these are tuned-aggregate deltas; the schemes hold as rail members, the percentages are corpus-specific.

## 3. Verdict table — does each GO/WIN transfer to the world corpus?

Ratio convention: compressed/original, lower = better. World numbers are champion-rail (`bwt-rans`), RT 24/24 byte-exact.

| Hypothesis | Tuned/claimed corpus + number | World-corpus result | Verdict |
|---|---|---|---|
| **H-13 BwtEntropy** (sch 6) | tuned: leader 0.299337 | rail member; RT-clean; selected where it wins | **holds** (structural) |
| **H-19 BwtRans** (sch 7) | tuned: 0.221726 | the umbrella rail; world overall 0.2524, RT 24/24 | **holds** (structural) |
| **H-20 Order2Rans** (sch 8) | tuned: 0.207618 (−6.36%) | rail member; tuned Δ is corpus-specific | **holds** (structural); number corpus-specific |
| **H-21 BwtAdaptive** (sch 9) | tuned: 0.177122 (−20.12%) | rail member; tuned Δ is corpus-specific | **holds** (structural); number corpus-specific |
| **H-22 BwtContextMix** (sch 10) | tuned: 0.168262 (−24.11%) | rail member; tuned Δ is corpus-specific | **holds** (structural); number corpus-specific |
| **H-24 BwtGeoMix — CHAMPION** (sch 11) | tuned: **0.158273**, "beats gzip −0.88%" | **byte-identical to bwt-rans on every unseen file** (holdout 6/6 + world); no independent per-file win | **corpus-specific** (headline overfit) |
| Champion "**beats gzip**" headline | tuned 10-file: 0.158273 < gzip 0.159674 | world: beats gzip **19/24 files** & aggregate (0.2524<0.3330) BUT loses small <40 KB files & **behind zstd** (beats zstd 6/24); holdout: **+1.3% behind gzip** | **overfit as a universal claim** |
| **H-25 MODE_LZ line** (whole-file LZ) | holdout: selected **0/6**, "NO-GO vs gzip" | world: **MODE_LZ selected 13/24**, every LZ/CHUNKED file beats gzip | **holds — generalises** (positive flip) |
| **H-29 columnar** (MODE_COLUMNAR) | class-C CSV: −27…−31% vs zstd | world: **selected 0/24** (no telemetry CSV present) | **corpus-specific** (narrow class — NOT a regression) |
| **Round-trip / competitive rail** | non-negotiable | **24/24 byte-exact**; no scheme ever regressed | **holds** (invariant) |

**Tally: holds = 6 hypotheses + the RT/competitive-rail invariant · corpus-specific = 2 (geomix edge, columnar) · overfit = 1 (the universal "beats gzip" headline).**

### Per-type: champion vs the buggy default (the CLI-trap impact), gap to best-in-class

| type | default-cubrim | champion-cubrim | best (who) | champion gap |
|---|---:|---:|---|---|
| image | 0.4529 | **0.3637** | 0.3271 (ppmd) | +11.2% (was +38.4%) |
| binary | 0.6193 | **0.6047** | 0.5393 (xz) | +12.1% (was +14.8%) |
| database | 0.1095 | **0.1082** | 0.0984 (xz) | +10.0% (was +11.3%) |
| code | 0.1977 | **0.1935** | 0.1732 (xz) | +11.8% (was +14.2%) |
| exe | 0.3220 | **0.3204** | 0.2755 (xz) | +16.3% (was +16.9%) |
| text | 0.2444 | **0.2440** | 0.2014 (ppmd) | +21.1% (was +21.4%) |

The CLI-trap fix is **decisive on small/image data** (image +38.4%→+11.2%) and marginal on the byte-dominant large text (enwik8 unchanged: it was already cube/BWT-pathed). World overall: champion **0.2524** vs default 0.2591; cubrim now beats gzip in aggregate and ranks **5/8** (between zstd and bzip2), with image's gap to the leaders collapsed.

## 4. What is genuinely still weak (real, not overfit)

- **Small inputs (<40 KB), mode=CUBE.** The 5 files cubrim loses to gzip (cp.html, fields.c, grammar.lsp, sum, xargs.1) are all single-block CUBE — residual per-block cube/header overhead. Far milder than the default-trap catastrophe (now 0.33–0.45, ranks #7/8, was 0.88–1.0) but still a genuine structural gap. This is the world-bench **H-A** candidate (small-input fallback / header diet), and it is real, not a measurement artefact.
- **Behind zstd-19 overall** (beats zstd on only 6/24): the per-type gaps to xz/ppmd/zstd (text +21%, exe +16%) are the genuine specialisation gaps — the world-bench candidate ladder (BCJ/H-37, pixel predictor/H-44, columnar already shipped/H-29) targets exactly these.

## 5. Flagged for /evolution (honest card updates for session B)

1. **Champion card** — change "beats gzip (0.158273)" to: *"GO on the tuned 10-file corpus (0.158273, −0.9% vs gzip). On the world corpus beats gzip on 19/24 files and in aggregate, but loses to zstd-19 (beats it 6/24) and still loses gzip on small <40 KB files. Not a universal gzip-beater."*
2. **H-24 geomix card** — note: *"On unseen data geomix produces byte-identical output to the bwt-rans rail; its tuned-corpus edge does not reproduce per-file."*
3. **H-29 columnar card** — scope honestly: *"−27…−31% vs zstd on telemetry-CSV class; does not activate on general-purpose data (0/24 on the world corpus). A real narrow-class win, not a general lever."*
4. **H-25 LZ card — POSITIVE correction** — the holdout 0/6 "NO-GO" undersold it: *"On the world corpus the whole-file LZ pre-pass (MODE_LZ) is selected on 13/24 files and lifts every large file above gzip. It generalises to real diverse data; the 6-file holdout simply lacked cross-block structure."*

## 6. Bottom line

The champion is **structurally sound and lossless everywhere** (RT 24/24); its scheme family and the competitive rail are corpus-independent invariants. What was **overfit** is the single headline *"beats gzip"* read as universal — it is true only on large/compressible data, false on small files and behind zstd. **H-29 columnar** is a genuine but **narrow-class** win (absent here). **H-25 LZ generalises** far better than its holdout suggested. The honest world-corpus standing: **cubrim 5/8 overall, beats gzip 19/24, behind zstd/xz/ppmd/brotli** — mid-pack, lossless, with the remaining gaps mapped to the candidate ladder.

## Reproduction & artefacts
- Champion runner: `run_cubrim_champ2.sh` (`--value-scheme bwt-rans`, mode-byte capture, RT verify, 8-way parallel).
- Aggregator: `reval_aggregate.py` → `results/revalidation.json` (per-file default+champion+8 archivers, modes, ranks).
- Publication JSON (corrected, champion numbers): `results/world-benchmark.json`.
- Caveat: numbers at SHA `317a323`; the champion rail is slow (MODE_LZ DP+BT match finder on large files — enwik8 ≈ tens of minutes). Re-running on a newer SHA may shift them — record the SHA.
