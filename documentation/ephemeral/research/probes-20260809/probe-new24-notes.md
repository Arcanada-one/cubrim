# NEW-24 Fast-CM probe notes — model-subset ladder (tier M / tier S)

Written BEFORE the probe ran (protocol step 1). Probe agent, 2026-08-09.
Worktree: /home/dev/.worktrees/cubrim/PROBE-NEW24 @ 4b8a03b (contains main d212c1c).

## Hypothesis restated

A wire-recorded model-set ladder (tier byte in the CM2 header) cuts decode
cycles roughly in proportion to probed-model count, because the decode map
(CUBR-DECODE-ATTRIB-20260809-results.md) shows ~50% dependent table-probe
latency + ~33% Ctr::upd write-back + ~7% mixer/APM — all three scale with
model count; fixed residue ~17% (coder, match hashing, kernel, loop).
The UNKNOWN is the density cost per tier per file class.

## Tier definitions (this probe's ladder, cumulative)

Full CM2 model inventory verified in code/cubrim-rs/src/cm2.rs @ HEAD:
12 orders (0..11), 6 sparse skip-grams g(1,3) g(1,4) g(2,4) g(2,3) g(1,5)
g(3,5), 1 indirect (order-2-keyed history-of-history, IBITS=20), 4 word
models (word, prev×word, case-folded word, case-folded bigram), 3 match
models (M1_MIN=6, M2_MIN=3, M3_MIN=12), 5 L1 mixers + L2, 2 APMs.
Probed models: 23 hashed-table + 3 match = 26.

Ladder: full(26) → −word2..4(23) → −sparse(17) → −indirect(16)
→ −orders8-11(12) → −orders5-7(9) → −m2(8)=TIER M {ord0-4, word1, m1, m3}
→ TIER S {ord0-3, m1}(5).

## Speed ceiling (from the measured decode map, stated before probe)

speedup(n) = 1 / (0.17 + 0.83·n/26)   [fixed 17% held out per hypothesis]

- tier M (n=8): predicted 2.35× (hypothesis text said ~2.0× at n≈9 → 2.19×;
  the map-derived formula is the binding prediction)
- tier S (n=5): predicted 3.03× (hypothesis said ~2.8×)

Amdahl outer bound for any model-count lever on CM2 cells: ~1/(0.17) ≈ 5.9×
if n→0 were possible (it is not; coder+match+loop remain).

## Density ceiling per file (meta-36 standings, whole-file, quoted reference)

Allowed ratio worsening before cubrim loses the per-file lead to the best
non-cubrim archiver (these are the CURRENT meta-36 numbers; any stale figure
in the hypothesis text yields to these):

| file | cubrim | best other | allowed worsening |
|---|---|---|---|
| silesia/dickens | 0.207263 | ppmd 0.225343 | +8.72% |
| silesia/xml | 0.063279 | brotli 0.080551 | +27.29% |
| silesia/samba | 0.145278 | xz 0.173075 | +19.13% |
| silesia/osdb | 0.216941 | ppmd 0.236641 | +9.08% |
| enwik8 (whole) | 0.195527 | ppmd 0.224036 | +14.58% |

Binding constraint for a lead-preserving tier: text/database classes
(dickens +8.7%, osdb +9.1%). Markup (xml +27%) and code (samba +19%) are
permissive. NB: a Fast-CM tier does NOT have to preserve the lead to ship
(it is a speed preset like `web`, which costs +3.32% and shipped), but
ADVANCE-vs-NO-GO per the task brief keys on the meta-36 lead on CM2-won
files.

## Gotcha gates

- Gotcha #3 (order-1 conditional-entropy probe): N/A — no reordering or
  traversal change; byte stream order unchanged.
- Gotcha #6 (one cost term per decoder branch): the wire change is ONE tier
  byte in the CM2 blob header selecting a fixed model set; the decoder
  branches once per archive, not per symbol. Cost charged: +2 bytes/archive
  (tier byte + header versioning slack) in every probe figure.
- Gotcha #7 (transmitted permutations): none transmitted.

## Probe design

Numba-jitted bitwise CM analogue, faithful in structure not constants:
MSB-first bit decomposition, hashed 2^22-slot counter tables (count-adaptive
12-bit probabilities), the SAME context sources as cm2.rs (order hashes,
the 6 exact sparse pairs, order-2-keyed indirect map, alnum word hashes with
case-folded variants, LZP match with minlen 6/3/12 and verified candidates),
2 context-selected L1 mixers (prev-byte view + match-state view) + L2 mixer,
1 APM, ideal code length -log2 p (coder measured at 0.45-0.59% — held out).
Structural simplifications vs cm2.rs, stated: single counter per probe (no
dual stationary+StateMap input), tbits=22 fixed (real codec derives 24 for
2 MiB), 2 L1 mixers not 5, 1 APM not 2, no FH4-03 column variants.

Calibration gate: real cubrim 0.3.2 `compress --preset max` bytes on the
SAME 2 MiB slices; analogue full-set must land within ~1.5× or deltas are
flagged as analogue-only.

Slices: first 2 MiB of dickens, xml, samba, osdb (silesia, SHA-verified
corpus) and of enwik8-head32m (LABELLED head sample, never "enwik8").

---

# RESULTS (written after the run; all figures PROBE, 1 MiB head slices)

Run: 2026-08-09 13:57-15:0x UTC, nice -n 10, 2 detached workers, numba 0.66.
Journal: probe-journal.jsonl (40/40 cells, no voids). Calibration: calib.log.

## Calibration gate (analogue full26 vs real cubrim 0.3.2 --preset max, SAME slice)

| slice | analogue full26 | real cubrim | factor |
|---|---|---|---|
| dickens.1m | 0.243632 | 0.221241 (231,988 B) | 1.10 |
| xml.1m | 0.101417 | 0.085992 (90,169 B) | 1.18 |
| samba.1m | 0.263925 | 0.236409 (247,893 B) | 1.12 |
| osdb.1m | 0.259109 | 0.231828 (243,089 B) | 1.12 |
| enwik8head.1m | 0.251405 | 0.223568 (234,428 B) | 1.12 |

All within the 1.5x gate -> deltas reportable as primary evidence.

## Ladder deltas vs full26 (PROBE, relative ratio worsening; allowance = meta-36
whole-file lead margin vs best non-cubrim archiver)

| tier (n models) | dickens (+8.72% allowed) | xml (+27.29%) | samba (+19.13%) | osdb (+9.08%) | enwik8head (+14.58%, head sample) |
|---|---|---|---|---|---|
| B -word234 (23) | +0.58% | +0.47% | +0.69% | -0.08% | +0.86% |
| C -sparse (17) | +0.49% | +1.41% | +1.62% | +5.13% | +1.54% |
| D -indirect (16) | +0.46% | +1.47% | +1.62% | +5.73% | +1.53% |
| E -ord8-11 (12) | +1.04% | +8.27% | +3.17% | +5.92% | +2.69% |
| F -ord5-7 (9) | +4.52% | +22.81% | +7.47% | +7.39% | +6.68% |
| G TIER M (8) | +4.52% (52% of allowance) | +22.83% (84%) | +7.52% (39%) | +7.40% (81%) | +6.68% (46%) |
| H TIER S (5) | +19.08% (219%) | +38.71% (142%) | +18.59% (97%) | +13.01% (143%) | +24.18% (166%) |

Predicted decode speedups from the attribution map, fixed 17% held out:
E(12) 1.81x, G/TIER M(8) 2.35x, H/TIER S(5) 3.03x.

## Class findings

- Sparse skip-grams are nearly free on text/markup/code (<=1.6%) but carry
  +5.1% on osdb — they encode fixed-stride database record structure. A
  database-aware tier must keep 1-2 sparse models (g(1,3), g(2,3)).
- Orders 5-7 are the single most expensive drop on text/markup (dickens
  +3.5pp, xml +14.5pp step F-E); orders 8-11 matter mostly on xml (+6.8pp).
- m2 (minlen-3 match) is free at tier M on every class (<=0.12pp step G-F).
- word2-4 cost <=0.9% everywhere (largest on wiki text).
- TIER S {ord0-3, m1} loses the meta-36 lead on 4/5 files -> dead as defined.
- TIER M (8) fits inside the lead margin on all 5 slices but consumes 81-84%
  of the allowance on osdb and xml.
- E(12) {ord0-7, word1, m1/m2/m3} costs <=8.3% of ratio and <=65% of
  allowance everywhere at predicted 1.81x — the safe tier.

## Honest caveats

- Analogue is 1.10-1.18x above the real codec (weaker: single counter per
  probe vs dual counter+StateMap, 2 L1 mixers vs 5, 1 APM vs 2, tbits 22 vs
  24). Real deltas may differ; the real full set extracts more from BOTH
  kept and dropped models, so per-tier deltas are indicative, not exact.
- Deltas measured on 1 MiB slices; allowances computed on whole files
  (10-100 MB). On longer files deep-order/word/sparse models get more
  training, so whole-file tier costs are plausibly HIGHER than slice costs
  (worst for enwik8 at 100 MB). The prereg must re-measure on whole files.
- enwik8 figures are from a labelled head sample, never whole enwik8.
- The 2 MiB ladder was subsampled to 1 MiB per the brief's timeout fallback
  (load-67 box); slices labelled .1m throughout.
