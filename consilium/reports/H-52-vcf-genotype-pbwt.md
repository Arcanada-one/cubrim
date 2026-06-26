# H-52 — VCF genotype-matrix PBWT transform: GO (spike, charged, non-subsumed)

**Status:** GO (spike-first, no Rust yet). The first genuinely-new-class structural win
since the telemetry class — PBWT on the genotype matrix beats zstd-19 by **2.60× (charged)**
and is **2.33× smaller than Cubrim's own BWT** on the raw matrix (NOT subsumed).

**Class:** genomic variant tables (VCF genotype matrix). Consilium round-3 RANK #1.
**Corpus:** real **1000 Genomes Phase 3, chr20** (`ftp.1000genomes.ebi.ac.uk/.../ALL.chr20...genotypes.vcf.gz`), 2504 samples; spiked on the first 3000 (and 300/1000) variants of a 15 MB BGZF prefix decompressed to raw VCF text. Baseline = zstd-19 on **raw VCF text** (NOT .vcf.gz — per the spike guidance, BGZF would be a fake baseline).

## Cheap gate first (spike guidance, <10 s)

2-bit/4-bit pack of the GT matrix vs zstd-19 on raw GT text (1000 var × 2504): **1.514×**
(≥1.2× threshold) → CONTINUE to the full transform.

## The lever — PBWT (Positional BWT, Durbin 2014)

Reorder the 5008 haplotypes at each variant by their reversed-prefix match; linkage
disequilibrium then makes each allele column form long runs (measured avg run **274**,
0.0036 runs/cell). The permutation is rebuilt incrementally by the decoder (like BWT's
LF-mapping), so it is **NOT transmitted** — the non-subsumable claim survives charging.

## Measured (real 1000G chr20, zstd-19 on raw VCF = gate baseline)

| | raw GT | PBWT (this lever) | ×/zstd-raw |
|---|---:|---:|---|
| 3000 var, zstd-19 | 132086 | **38198** (RLE) | **3.46×** |
| 3000 var, + charged multi-allelic exceptions (0.090 % of cells, 12682 B) | — | **50880** | **2.60×** |
| 300 var, cubrim (BWT+rANS) — SUBSUMPTION CHECK | 15137 | **6498** (RT byte-exact) | — |

**Subsumption check (decisive):** on the raw GT matrix, Cubrim's own BWT+rANS gets 15137
(only 1.07× better than zstd's 16196 — its global suffix sort does NOT capture the
position-dependent haplotype reorder). PBWT gets 6498 — **2.33× smaller than Cubrim's own
BWT**. So PBWT extracts structure the byte backend structurally cannot reach (Gotcha #11
criterion: a genuine information-changing transform, not a subsumed re-pack). Contrast the
SUBSUMED variants measured the same run: codes_smajor 1.17×, naive sparse 0.19× (worse).

## Verdict

**GO** (gate ≥1.5× vs zstd-19 cleared at 2.60× charged / 3.46× raw; non-subsumed vs
Cubrim's BWT at 2.33×; PBWT RLE round-trips byte-exact through cubrim). The consilium's
−71 % (≈3.4×) literature estimate is **confirmed by measurement**, not taken on faith
(project meta-lesson: models fabricate — verified). Multi-allelic is rare (0.090 %) and
charged; the win is robust.

**Implementation queued (next round, substantial):** a MODE_VCF container / genotype-matrix
value-scheme — detect VCF (## header + #CHROM + genotype FORMAT), split fixed-field columns
(POS via existing columnar delta) from the genotype matrix, PBWT-transform the phased
haplotypes + RLE + rANS, charge a multi-allelic exception list, reverse on decode.
Competitive `min(base, vcf)` + mode byte → regression-proof; tuned 0.158273 + holdout 0.2390
must stay byte-identical (VCF only engages on detected VCF input). Round-trip byte-exact +
property tests mandatory.

**Code SHA:** spike on `bf1eba1` (codec untouched). Leaderboard untouched, NOT pushed.

---

## H-52 IMPLEMENTATION — MODE_VCF shipped (codec change)

Implemented `MODE_VCF` (container mode 5): byte-exact PBWT genotype-matrix codec.
- `pbwt_encode`/`pbwt_decode`: PBWT over the binary haplotype matrix; per-variant alleles in
  the current permutation are RLE'd (alternating run-lengths from allele 0, summing to m). The
  permutation is rebuilt step-by-step by the decoder — never transmitted.
- `encode_vcf`/`decode_vcf`: detect `##fileformat=VCF` + `#CHROM` + `GT`-only rows; split the
  preamble, the 9 fixed fields, the PBWT-RLE genotype stream, and a charged multi-allelic /
  missing / unphased exception list — each nested-encoded via `encode_base`. Canonical cells
  are biallelic phased `X|Y`; everything else is an exception (literal, restored on decode).
- Wired as a competitive candidate `min(base, vcf)`; on a detected VCF the (slow, never-winning)
  LZ/columnar competitors are short-circuited. Non-VCF input pays only the cheap prefix check,
  so the whole tuned/holdout corpus is byte-identical.

**Tests:** +5 (`test_pbwt_round_trips_random_binary_matrix`, round-trips-and-shrinks,
edge-cases incl all-exception/no-trailing-newline/single-sample, not-selected-on-non-vcf,
truncated-no-panic). Full suite **229 lib + integration green**; clippy 0 new.

**Zero-regression VERIFIED:** tuned 10-file **0.158273 byte-identical** (RT 10/10), holdout
**0.2390 byte-identical** (RT 6/6) — VCF only engages on detected VCF input.

**Measured (real 1000 Genomes chr20, cubrim `--value-scheme bwt-rans`, RT byte-exact):**

| sample | input | cubrim | zstd-19 | gzip-9 | vs zstd | vs gzip | mode |
|---|---:|---:|---:|---:|---:|---:|---|
| 400 variants × 2504 | 4098362 | 19931 | 34010 | 53742 | **−41.4%** | −62.9% | VCF |
| 1000 variants × 2504 | 10192568 | 39020 | 72178 | 125526 | **−45.9%** | −68.9% | VCF |

The win grows with variant count (more linkage → longer PBWT runs), trending toward the
spike's 2.60× (−62%) at 3000 variants. RT byte-exact throughout.

**Known follow-up (perf, not correctness):** the competitive `base` floor runs the chunked
BWT+geomix pipeline on the whole multi-MB VCF (general big-file geomix slowness), so encode
is slow on large VCFs; a "trust VCF" fast path or the base-speed fix is a follow-up. The
genotype-matrix bit-packing (currently 1 byte/allele) is also a future memory optimization.

**Verdict:** GO shipped — MODE_VCF is a genuine new-class structural win (first since
telemetry), byte-exact, regression-proof, beating zstd-19 by 41–46% on real 1000 Genomes data.
