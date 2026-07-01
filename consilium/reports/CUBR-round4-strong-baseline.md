# CUBR round-4 corpora — champion `bwt-rans` vs STRONG universals (not zstd strawman)

**Task (operator `.brief-research-revalidate.txt`, TASK 2).** Re-measure the round-4 corpora (CORPUS 1 non-temporal wide deterministic tables; CORPUS 2 raw IEEE-754 doubles) strictly on champion `--value-scheme bwt-rans`, with the GO-gate vs the **strongest universal** (min of xz-9e / 7z-PPMd / brotli-q11) — NOT vs the zstd-19 strawman. Round-trip byte-exact mandatory.

Tools: xz 5.4.5 (`-9e`), 7z PPMd (`-m0=PPMd -mmem=256m`), brotli 1.1.0 (`-q 11`), zstd 1.5.5 (`-19`, reference only). Codec untouched, NOT pushed. Harness: `/tmp/uci-dl/measure_round4.sh`. Provenance/SHAs of inputs: `/home/dev/cubrim-worldbench/*/MANIFEST.md`.

## Measured (bytes; **all round-trip byte-exact OK**)

| file | orig | cubrim champ | xz-9e | PPMd | brotli | zstd-19 | strongest | strong/cub |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| adult_census.csv | 1 500 091 | 89 152 | 115 908 | **81 761** | 116 398 | 119 657 | PPMd | **0.917** |
| covtype_cartographic.csv | 1 500 053 | **143 124** | 182 116 | 179 022 | 181 868 | 193 849 | PPMd | **1.251** |
| poker_hand.csv (class confirm) | 1 300 011 | **205 929** | 274 536 | 232 634 | 283 293 | 279 325 | PPMd | **1.130** |
| supercond_raw_f64.npy | 1 705 728 | 525 738 | **502 616** | 656 353 | 508 376 | 531 227 | xz | **0.956** |
| supercond_zscore_f64.npy | 1 705 728 | 559 742 | 565 248 | 705 233 | **556 763** | 570 576 | brotli | **0.995** |

(`strong/cub > 1` ⇒ Cubrim beats the strongest universal.)

## Findings

1. **CORPUS 1 covtype = genuine Cubrim WIN vs the strongest universal (1.251×).** The non-temporal wide one-hot/categorical CSV is crushed by Cubrim's **base champion** (columnar + `bwt-rans`) — 143 124 vs the best universal (PPMd 179 022; xz/brotli/zstd 20–26% larger). This is NOT the failed H-49-reborn cross-column transform (that added only +2–5%); it is the **existing shipped codec already winning the class**.

   **Class confirmation (n=3, added this run):** a second pure-categorical wide table — **poker_hand.csv (1.130×)** — also a Cubrim base-win (205 929 vs PPMd 232 634; xz/brotli/zstd 25–27% larger). So *non-temporal wide LOW-cardinality categorical/one-hot tables* are a Cubrim base-codec win class (2/2 pure cases), joining telemetry + VCF. Zero new code — the shipped columnar + `bwt-rans` already wins it.

2. **CORPUS 1 adult = mixed (sharpens the class boundary).** Cubrim (89 152) beats xz/brotli/zstd by ~23 % but loses to **PPMd (81 761) by 8.3 %**. Adult differs from covtype/poker by having **high-cardinality natural-language string columns** (`occupation`, `native_country`, `workclass`) where PPMd's high-order text model dominates. **Boundary:** Cubrim wins low-cardinality categorical/numeric wide tables; high-cardinality TEXT columns are PPMd territory — exactly the gap the CUBR-BACKEND-SPIKE PPMd-class backend (GO-to-plan) targets.

3. **CORPUS 2 both = entropy floor, no structural lever (confirms H-50 NO-GO vs the strong bar too).** raw_f64 Cubrim ≈ xz (−4.6 %, beats PPMd/zstd); zscore_f64 Cubrim ≈ brotli (−0.5 %, near-tie). PPMd is catastrophic on binary floats (656 K / 705 K). The z-score doubles are derived from ~7-digit-decimal sources → low-precision mantissa, no sub-byte slack — exactly the H-50 diagnosis, and it holds against xz/brotli, not just zstd. **ALP-RD's lit ×4.3 is for full-entropy scientific doubles, which this corpus is not.**

## Re-validation verdicts (vs STRONG universals)

- **H-49-reborn (cross-column transform): NO-GO HOLDS** — and the base champion already wins covtype without it, so the transform is not just non-additive, it is unnecessary on its own class.
- **H-50 (ALP-RD): NO-GO HOLDS vs xz/brotli too** — entropy floor, low-precision doubles; not a zstd-strawman artifact.
- **NEW: covtype-class (non-temporal wide one-hot/categorical) is a base-codec win vs strong universals** — candidate to characterise as a named class (like telemetry) rather than a hypothesis needing code.

## Discipline

Champion `bwt-rans` pinned on every Cubrim run; RT byte-exact verified on all 4 files; ceilings labelled lit-estimate vs measured; codec.rs untouched; not pushed.
