# PROBE NEW-05 — BWT + CM post-model (bsc/mcm-class) — notes

Date: 2026-08-09. Worktree main = d212c1c. Standings = meta 36 (scratchpad meta36-ratios.txt).

## Routing check (source, before anything else)

- `codec.rs` value-stream rail: BWT family (BwtRans/BwtEntropy/BwtAdaptive/BwtContextMix/BwtGeoMix)
  still carries the v1 two-byte primary index — `bwt_wire_can_represent(len) = len <= 65536`
  (codec.rs:7070). So the 64 KB BWT ceiling DOES still exist in the value-scheme rail.
- BUT: `MODE_CM2` (cm2.rs `cm2_encode`) codes the WHOLE input in one pass (wire:
  `[orig_len u64 BE][bit-range-coded]`, no chunking), and the ≤64 KB path was opened to it
  (codec.rs ~:552, "single largest small-file lever, measured −57..−76% on the ≤64 KB corpus
  files"); `CM2_MIN_LEN` floor was dropped from 256 KiB to small inputs (codec.rs ~:4336).
  `MODE_LARGEBWT` (chunked large-BWT container) also exists (codec.rs ~:4697).
- Therefore the routing's premise — "chunked/small text suffer from the 64 KB BWT ceiling;
  need FU-01 (u32 block) + CM to close the ppmd gap" — is superseded: small/medium text is
  now served whole-file by the CM2 flagship, not by the 64 KB-chunked BWT rail.

## Current gaps on the cited files (meta 36; hypothesis numbers are STALE)

gap = (cubrim − ppmd)/ppmd; negative = cubrim already better. Hypothesis claimed cubrim
LOSES to ppmd by +32.2% (plrabn12) … +19.9% (asyoulik). Current:

| file      | cubrim   | ppmd     | gap     | best competitor overall |
|-----------|----------|----------|---------|-------------------------|
| plrabn12  | 0.26141  | 0.27504  | −4.95%  | cubrim wins outright |
| alice29   | 0.24270  | 0.25634  | −5.32%  | cubrim wins outright |
| asyoulik  | 0.27584  | 0.29034  | −4.99%  | cubrim wins outright |
| cp.html   | 0.26720  | 0.27200  | −1.76%  | cubrim wins outright |
| dickens   | 0.20726  | 0.22534  | −8.02%  | cubrim wins outright |
| lcet10    | 0.20859  | 0.22625  | −7.81%  | cubrim wins outright |
| reymont   | 0.13884  | 0.17224  | −19.39% | cubrim wins outright |

Every cited gap is GONE. Routing's own success criterion ("gap ≤0% vs ppmd on small text in
large-block mode") is already satisfied on current main — without FU-01 and without BWT+CM.

Residual losses anywhere in meta 36: nci (cubrim 0.04633 vs xz 0.04319; database class,
long-range-repeat dominated — BWT-track bzip2 is 0.05403 there, far worse, so BWT+CM is the
wrong lever) and xargs.1 (4,227 B Canterbury, fixed-overhead-dominated — excluded from
claims per protocol). Neither is in this hypothesis's class (chunked/small TEXT).

## CEILING (stated BEFORE probe)

Mechanism ceiling for a bsc/mcm-class track (BWT at large blocks + CM/SSE post-model): the
hypothesis's own target and the strongest measured CM-class reference in meta 36 is ppmd
(strongest non-cubrim archiver on every cited file). A BWT+CM post-model is upper-bounded in
this corpus-measured frame by ≈ ppmd's ratio per file (the BWT reordering loses a little
context information vs direct CM; bzip2 = BWT at 900 KB blocks + weak post-model is 9–24%
WORSE than ppmd on these files, so the CM post-model must recover all of that and more).

Per file ceiling (current cubrim → ceiling):
- plrabn12: 0.26141 → 0.27504 (ppmd reference) — ceiling is ABOVE current cubrim
- alice29:  0.24270 → 0.25634 (ppmd) — above current
- asyoulik: 0.27584 → 0.29034 (ppmd) — above current
- cp.html:  0.26720 → 0.27200 (ppmd) — above current
- dickens:  0.20726 → 0.22534 (ppmd) — above current
- lcet10:   0.20859 → 0.22625 (ppmd) — above current
- reymont:  0.13884 → 0.17224 (ppmd) — above current

i.e. the reference-derived ceiling of the proposed mechanism is WORSE than what current main
already ships on every cited file. Headroom is negative before any probe is run.

## Supporting probe (Gotcha #3 + #6/#7), run AFTER the ceiling above

Purpose: mechanism-ground the supersession verdict by testing the routing's counterfactual —
"BWT at large blocks (>64 KB) + CM post-model" — on cited files, whole-file BWT (the
large-block regime FU-01 would enable), order-1 conditional entropy of BWT output vs the
unreordered stream, plus a charged wire model (one cost term per decoder branch, primary
index charged per Gotcha #7). Script: probe-new05-bwt.py. Results appended below after run.

## Probe results (all PROBE figures; adaptive KT estimator, alphabet 256)

alice29 whole-file (152,089 B, 1 block — large-block regime):
  raw order-1 0.45415 | bwt order-1 0.36342 | raw order-2 0.44307 | bwt order-2 0.41532
  charged MODE_BIGBWT_CM (o1 payload) 0.36364 ; (o2) 0.41553
cp.html whole-file (24,603 B):
  raw order-1 0.54035 | bwt order-1 0.41878 ; charged (o1) 0.42012
plrabn12 64KB-blocks (8 blocks — the CURRENT rail ceiling regime):
  bwt order-1 0.40893 ; charged 0.40923
plrabn12 whole-file (1 block — FU-01 regime):
  bwt order-1 0.37943 ; charged 0.37950  (−7.2% vs 64KB blocks)

Gotcha #3: PASS as a mechanism — whole-file BWT reduces order-1 conditional entropy vs the
unreordered stream on every file (alice29 0.454→0.363; cp.html 0.540→0.419; plrabn12
0.432→0.379), and large blocks beat 64 KB blocks (plrabn12 0.409→0.379). The direction is
real. But the charged absolute level with the probe post-model is far ABOVE current cubrim
(alice29 0.364 vs shipped 0.243; plrabn12 0.380 vs 0.261), and the measured class ceiling
(ppmd) is itself above current cubrim on every cited file.

## Verdict: NO-GO (superseded by the CM2 whole-file flagship)

The hypothesis's success criterion (gap ≤0% vs ppmd on small text at large blocks) is
already met on main d212c1c without this track. Ceiling < current on all cited files.
