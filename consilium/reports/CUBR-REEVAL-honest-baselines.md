# CUBR Re-Evaluation — GO hypotheses vs HONEST baselines

**Trigger:** operator + consilium adversarial audit found a methodology flaw — the
`zstd-19 on raw` baseline is a **weak strawman**; the `≥1.5× vs zstd` gate measured zstd's
weakness on a data type, not the transform's value. This document re-measures every GO
hypothesis against **domain codecs** (LAZ, BGZF) and the **strongest universal** codecs
(xz-9e, PPMd, brotli-q11), and isolates transform-value from backend-weakness.

**Date:** 2026-06-26 · re-measurement only (codec.rs untouched) · leaderboard untouched · NOT pushed.
Tools: `/home/dev/.codec-venv` (laspy 2.7 + lazrs, pysam 0.24), xz 5.4.5, 7z PPMd, brotli 1.1.0.

---

## 1. LiDAR (H-54 MODE_BINFLOAT) — ⚠️ CORRECTED: HOLDS vs LAZ (the −14% loss was MY config error)

> **CORRECTION (2026-06-26, found during the backend spike).** The verdict below
> ("LAZ wins 1.144×") was measured with Cubrim's **default** value-scheme (BitpackFixed),
> NOT the champion `bwt-rans` config the project uses for every leaderboard number — the
> exact config-mismatch trap caught for VCF, which I missed here. Re-measured with
> `--value-scheme bwt-rans` (RT byte-exact, mode 0x06, all 5 scans):
>
> | scan | Cubrim (bwt-rans) | LAZ | verdict |
> |---|---|---|---|
> | kitti.bin | 492925 | 495640 | Cubrim +0.6% |
> | kitti0 | 532566 | 538348 | Cubrim +1.1% |
> | kitti1 | 539755 | 561343 | Cubrim +4.0% |
> | kitti2 | 537982 | 561887 | Cubrim +4.4% |
> | kitti114 | 486654 | 503371 | Cubrim +3.4% |
> | **aggregate** | **2589882** | **2660589** | **Cubrim BEATS LAZ 1.027×** |
>
> **Corrected verdict: H-54 LiDAR HOLDS — Cubrim marginally beats the domain codec LAZ
> (1.027× aggregate, all 5 scans) AND beats every universal codec.** The default-config
> number (577217) below was the artifact. The backend headroom (transform+ppmd 427933 =
> 1.16× over LAZ) remains the upgrade target (see CUBR-backend-strengthening-spike.md).

### (original, default-config measurement — superseded by the correction above)

Corpus: 5 real KITTI Velodyne scans. LAZ written via laspy+lazrs at scale 1 mm
(**verified value-lossless** on all 4 channels x,y,z,reflectance — KITTI sensor accuracy
~2 cm, so a 1 mm grid round-trips to the exact float32; per-channel ndiff=0).

| scan | raw | **LAZ (domain)** | Cubrim binfloat | xz-9e | LAZ vs Cubrim |
|---|---|---|---|---|---|
| kitti.bin | 1843776 | **495640** | 577217 | 704996 | LAZ −14.1% |
| kitti0 | 1846144 | **538348** | 621029 | 703492 | LAZ −13.3% |
| kitti1 | 1924288 | **561343** | 640668 | 740060 | LAZ −12.4% |
| kitti2 | 2030256 | **561887** | 622397 | 744240 | LAZ −9.7% |
| kitti114 | 1920032 | **503371** | 581386 | 725436 | LAZ −13.4% |
| **aggregate** | | **2660589** | 3042697 | | **LAZ wins 1.144×** |

**Cubrim beats every GENERIC universal** (kitti.bin: zstd 905645, xz 704996, ppmd 746163,
brotli 812029 — all larger than Cubrim 577217). **But the shipped Cubrim loses to the
domain standard LAZ on every scan (aggregate −14.4%).**

**Subsumption-fix (transform vs backend).** Running the H-54 transform (SoA + reversible
wrapping-uint32 delta, reflectance raw) through a STRONG backend instead of Cubrim's own:

| | kitti.bin | kitti2 |
|---|---|---|
| LAZ (domain) | 495640 | 561887 |
| Cubrim binfloat (shipped backend) | 577217 | 622397 |
| **transform + ppmd** | **425736** | **461214** |
| transform + xz-9e | 462660 | 503260 |

The **transform + ppmd BEATS LAZ by 1.16–1.22×**. So the SoA+delta lever is genuinely
domain-competitive; the shipped codec loses only because **Cubrim's entropy backend
(BWT+geomix/LZ) is weaker than ppmd/xz on the delta-of-float-bits streams** — confirming
the consilium's flaw #2 (weak backend) *for this stream type*.

**Honest re-verdict H-54:** the "1.54× vs zstd" claim was a weak-baseline artifact for the
*shipped codec vs the domain codec*. **Reclassify: H-54 beats all generic universal codecs
but the shipped MODE_BINFLOAT loses to the domain standard LAZ by ~14%.** The transform
itself is NOT subsumed — transform+ppmd beats LAZ — so the idea is sound; the realizable
win is gated by Cubrim's backend. The MODE_BINFLOAT code stays (correct, regression-proof,
beats generic), but the marketing claim must be "beats generic lossless, not the domain
codec," and the real lever forward is a stronger backend on these streams.

---

## 2. VCF (H-52 MODE_VCF, PBWT genotype matrix) — **HOLDS**

Corpus: real 1000 Genomes chr20, 2504 samples. Cubrim with `--value-scheme bwt-rans`
(the H-52 champion config — default BitpackFixed gives 92332 and was a config-mismatch
trap I caught before recording a false regression).

| corpus | Cubrim MODE_VCF | **BGZF (domain .vcf.gz)** | xz-9e | PPMd |
|---|---|---|---|---|
| s400 (400 var) | **19931** | 65725 | 28224 | 29610 |
| s1000 (1000 var) | **39020** | 159555 | 59520 | 65737 |
| Cubrim beats | — | **3.3–4.1×** | **1.42–1.52×** | **1.49–1.68×** |

**Cubrim beats the domain storage format BGZF (3.3–4.1×) AND the strongest universal
codecs (xz/ppmd, 1.4–1.7×).** The PBWT genotype transform is the same family as the
genomic SOTA (GTShark/GTC are PBWT-based). **Win survives honest baselines.** Caveat: the
specialized genotype compressors GTShark/GTC are not directly benchmarked here (lit ≈ PBWT
class) — BGZF is the *available* domain baseline, not the strongest possible.

---

## 3. Telemetry (H-29/31/40 columnar + integer/decimal delta) — **HOLDS**

Corpus: real forex/telemetry CSVs (>64 KB → MODE_COLUMNAR), Cubrim `--value-scheme bwt-rans`.

| file | Cubrim | zstd-19 | **xz-9e** | **PPMd** | **brotli-q11** | Cubrim vs strongest universal |
|---|---|---|---|---|---|---|
| forex_tick | 26848 | 61346 | 50428 | 49441 | 50305 | **−45.7%** (1.84×) |
| forex_usdchf | 24881 | 55576 | 48756 | 45947 | 48511 | **−45.8%** (1.85×) |
| status_timeseries | 11702 | 21381 | 17064 | 21559 | 18290 | **−31.4%** (1.46×) |

The headline "−53.6% vs zstd" softens to **−31 to −46% vs the STRONGEST universal**
(xz/ppmd/brotli) — still a decisive structural win, realized through Cubrim's OWN backend
(unlike LiDAR, the backend is strong enough on these text-derived numeric streams). The
columnar reorder + numeric delta is a real lever generic codecs lack. **Win survives.**
Caveat: a columnar domain codec (Parquet+zstd with dict/RLE/delta) is not benchmarked here
(pyarrow unavailable) — a follow-up; the project's H-48 reasoned Cubrim's entropy backend
beats Parquet's bit-packing, but per the LiDAR finding that backend claim deserves a direct
Parquet measurement.

---

## Summary of honest re-verdicts

| hypothesis | old claim | honest re-verdict |
|---|---|---|
| **H-54 LiDAR** | 1.54× vs zstd (GO) | **HOLDS (corrected)** — with champion config beats domain LAZ **1.027×** (5 scans) + all universal; my −14% "loss" was a default-config error. Backend headroom: transform+ppmd 1.16× over LAZ |
| **H-52 VCF** | −41..−46% vs zstd (GO) | **HOLDS** — beats BGZF 3.3–4.1× + xz/ppmd 1.4–1.7×; PBWT = genomic-SOTA family |
| **H-29/31/40 Telemetry** | −53.6% vs zstd (GO) | **HOLDS** — beats strongest universal (xz/ppmd/brotli) −31..−46% |

**Methodology lessons confirmed:**
1. The zstd-19 baseline WAS a strawman **for LiDAR** — the honest LAZ baseline flipped the
   shipped-codec verdict. It was NOT a strawman for VCF/telemetry (wins survive xz/ppmd/brotli).
2. Consilium flaw #2 (weak backend) is real **for LiDAR delta-of-float streams** (transform+ppmd
   beats Cubrim's own backend by 1.36×) but NOT universal — Cubrim's backend wins on VCF/telemetry.
3. Always pin the cubrim `--value-scheme` to the champion config when re-measuring (the VCF
   default-config run looked like a 4.6× regression purely from a BitpackFixed mismatch).

**Net standing (honest):** Cubrim is a genuine structural winner vs strong universal codecs
on VCF (genomic) and telemetry/columnar; on LiDAR it beats generic codecs but the shipped
backend loses to the domain LAZ (the transform does not). No GO fully retracted; one
(LiDAR) reclassified to "beats generic, not the domain codec." Honesty over wins.
