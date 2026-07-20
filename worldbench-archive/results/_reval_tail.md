
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
