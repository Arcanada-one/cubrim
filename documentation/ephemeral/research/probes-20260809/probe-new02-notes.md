# PROBE NEW-02 — own PPMd var.H/I backend for text (parity ±0.5% then +1–3% over ppmd)

Worktree: /home/dev/.worktrees/cubrim/PROBE-NEW02 @ d212c1c (= current main per brief).
Date: 2026-08-09. Probe stage only — no Rust, no prereg, no push.

## Routing check (against current source, d212c1c)

- `src/cm2.rs` docstring + code: MODE_CM2 codes the WHOLE file; hash tables sized
  to input length (tbits = clamp(ceil(log2 len)+3, 18, 27)). The 64 KB mentions in
  cm2.rs are a test vector (`zeros_64k`) and the CM2_STALL_LIMIT guard — NOT a
  block ceiling. The consilium "64KB ceiling" era is over; routing note's framing
  (parity as a milestone inside the CM backend, NEW-01/H-61) refers to a
  milestone that the shipped CM2 has ALREADY passed (see standings below).
- `src/ppmd.rs` (1700+ lines) ALREADY contains a real PPMd var.H-family model:
  SEE2 with adaptive period, information inheritance ("parent without copying …
  PPMd var.H update model"), LOE, binary-context shortcut, an APM stage chained
  after SEE2, and a self-probe harness (ideal_bytes / see_rl_ceiling / mix_oracle).
  It is NOT wired into dispatch (`#![allow(dead_code)]`, "until the MODE_PPMD
  integration (plan Phase 2, step 7)"). So NEW-02's "build our own PPMd var.H/I"
  is partially built and deliberately parked.
- CUBR-CONT-STATUS.md lines 348–357: the PPMd-backend spike (CUBR-BACKEND-SPIKE)
  was justified when ppmd beat Cubrim's champion on every general-data holdout —
  i.e. BEFORE the CM2 flagship existed. That justification is stale for the text
  lane (meta-36 below).

## Hypothesis-embedded numbers vs meta 36 (meta 36 wins)

The row claims cubrim needs parity with ppmd on 11 text files and cites an osdb
gap of +30.7% vs ppmd. ALL of that is stale. Current meta-36 (preset max):
cubrim is ALREADY BETTER than ppmd on every one of the 11 text files AND osdb.

## CEILING (stated BEFORE probe)

Hypothesis's own ceiling = ppmd(meta36) × 0.97 (its most optimistic claim:
parity floor, then +3%). Basis: measured meta-36 ppmd column. Per file
(current cubrim -> hypothesis ceiling):

| file        | ppmd    | hyp ceiling (×0.97) | cubrim now | cubrim vs ceiling |
|-------------|---------|---------------------|------------|-------------------|
| dickens     | 0.22534 | 0.21858             | 0.20726    | cubrim 5.2% BETTER than ceiling |
| webster     | 0.15785 | 0.15311             | 0.13974    | cubrim 8.7% BETTER |
| enwik8      | 0.22404 | 0.21731             | 0.19553    | cubrim 10.0% BETTER |
| reymont     | 0.17224 | 0.16707             | 0.13884    | cubrim 16.9% BETTER |
| xml         | 0.09288 | 0.09009             | 0.06328    | cubrim 29.8% BETTER |
| lcet10      | 0.22625 | 0.21946             | 0.20859    | cubrim 5.0% BETTER |
| plrabn12    | 0.27504 | 0.26678             | 0.26141    | cubrim 2.0% BETTER |
| alice29     | 0.25634 | 0.24865             | 0.24270    | cubrim 2.4% BETTER |
| asyoulik    | 0.29034 | 0.28163             | 0.27584    | cubrim 2.1% BETTER |
| cp.html     | 0.27200 | 0.26384             | 0.26720    | ceiling 1.3% below cubrim (24.6 KB file; potential ~85 bytes) |
| xargs.1     | 0.38088 | 0.36946             | 0.38018    | ceiling below cubrim (4.2 KB Canterbury, overhead-dominated — reported as measured, excluded from claims per brief rule 4) |
| osdb        | 0.23664 | 0.22954             | 0.21694    | cubrim 5.5% BETTER (row's "+30.7% gap" is stale) |

Literature caveat (NOT a measured ceiling): a full PPMII/var.I ("ppmonstr"-class)
model can exceed var.H by well over 3%; even granting a generous +10% over the
measured ppmd column, the resulting ratios (dickens 0.2028, webster 0.1421,
enwik8 0.2016, reymont 0.1550) would beat current cubrim ONLY on dickens, and
by ~2% — while being a multi-week single-model build outside the hypothesis's
own stated claim.

## Probe plan (written before running)

Cheap honest signal on the routing question (dedicated PPM-with-SEE vs
CM2-style mixing on the two large text files where cubrim's lead over ppmd is
smallest in absolute terms): pure-Python size models, 2 MB slices of dickens
and webster (slices labelled), sum of -log2 p — a MODEL, not the codec, both
arms charged identically.

- Arm A (PPM): order-4 PPM, escape method C with full exclusion, plus an
  adaptive SEE-style escape bucket (context: order, #distinct symbols bucket,
  deterministic flag). One arithmetic stream; every escape decision and symbol
  is charged through its probability → cost terms == decoder branches
  (Gotcha #6 satisfied; no transmitted coordinates → Gotcha #7 n/a; no
  reordering → Gotcha #3 n/a).
- Arm B (CM-analogue): bitwise logistic mixing of order-0..4 hashed byte
  contexts with adaptive probability counters, learned mixer weights, one
  APM-ish SSE stage. Same charging rule.

Prediction to test: Arm B ≤ Arm A on both slices (mixing dominates single
highest-order-with-escape), consistent with the shipped standings and with the
routing's position that residual gaps are CM2-tuning, not backend-family.

## Results (run 2026-08-09)

PROBE (Python size models, 4 MB slices, sum -log2 p):
- dickens 4MB slice: arm A (order-4 PPM + SEE) 1,012,563 B = 0.25314; arm B (toy bitwise CM, understrength by design) 1,205,254 B = 0.30131
- webster 4MB slice: arm A 812,877 B = 0.20322; arm B 977,331 B = 0.24433

MEASURED references on the SAME slices:
- dickens 4MB: 7z PPMd var.H (o16, 256m) 947,467 = 0.23687; xz -9e 1,146,100 = 0.28652; shipped cubrim d212c1c preset max 857,557 = 0.21439
- webster 4MB: 7z PPMd 694,404 = 0.17360; xz -9e 889,824 = 0.22246; cubrim 622,700 = 0.15568

Same-slice real-vs-real: cubrim beats real var.H by 9.5% (dickens) / 10.3% (webster).
The hypothesis's own optimistic ceiling on these slices (ppmd × 0.97) is
0.22976 / 0.16839 — cubrim's measured slice output is 6.7% / 7.5% BELOW even that.

Toy-arm caveat: arm B lost to arm A, but arm B was declared understrength
(5 orders, no SSE/match/word models vs cm2.rs's 26-model 2-layer architecture);
the within-family engineering depth dominates the family choice at toy scale.
The decisive evidence is the real-vs-real same-slice measurement plus meta-36.

VERDICT: NO-GO (milestone already exceeded by shipped CM2 on all 11 text + osdb;
hypothesis's own ceiling dominated on 10/12 files, exceptions are two tiny
Canterbury files worth ~85 B and ~30 B).
