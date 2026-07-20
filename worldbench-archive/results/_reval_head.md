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
