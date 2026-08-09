# PROBE NEW-08 — SSE/APM layer over non-CM2 backends (notes)

Date: 2026-08-09. Worktree: /home/dev/.worktrees/cubrim/PROBE-NEW08 @ main d212c1c.

## Routing check (source-verified BEFORE probe)

Hypothesis text and consilium routing are BOTH stale in different ways:

1. Hypothesis targets are stale vs meta 36: it says "sao 0.6244 → ≤0.6087
   (7z gap +2.6%)". CURRENT meta 36: cubrim sao = 0.5254 — already #1 by
   +15.8% over 7z (0.6087). mr: cubrim 0.2078, #1 (next ppmd 0.2308).
   xml: cubrim 0.0633, #1. Only nci still trails (cubrim 0.04633 vs xz
   0.04319, brotli 0.04529).
2. Consilium routing ("same class as H-34 APM NO-GO; needs ≥256KB blocks;
   reopen only with FU-01 large-block mode") predates the CM2 flagship AND
   the FH-10/PORT-B record-CM work. Verified in source @ d212c1c:
   - cm2.rs: whole-file, apm1(256 ctx)+apm2(1024 ctx) SSE chain (lines
     620-622, 897-902). NOT 64KB-limited.
   - geocm.rs: apm+apm2+apm3 (per-offset SSE for record classes) already
     present (lines 681-700, 731-751).
   - ppmd.rs: PAQ-style Apm (SSE) already present (lines 355-380).
   - codec.rs CmPredictor (used by MODE_CM, MODE_RECORDCM, exe-CM): FOUR
     unconditional APM stages apm..apm4 (lines ~3936-3948) PLUS a fifth
     per-offset SSE apm5 gated on `record.sse` (lines 3940-3956), and
     build_record_cm_blob COMPETES sse=OFF vs sse=ON per file and keeps the
     min (lines 4478-4487, wire flag RECORD_CM_SSE_FLAG in width_field).
   - The 64KB ceiling survives ONLY in the cube/value-stream rail
     (config.rs cube_size_limit() = b*b = 65536): schemes BwtRans /
     Order2Rans / BwtAdaptive / BwtContextMix / BwtGeoMix / LzRans /
     Entropy* / Huffman. These are the ONLY probability-producing coders
     with NO SSE stage. ctxmix (cm_pure_o1/cm_mix) and geomix
     (gm_mix_encode: geometric o2/o1/o0 mix into a range coder) are
     adaptive SYMBOL-level coders, uncalibrated.

So NEW-08's residual scope after routing = SSE over the value-stream rail
coders only. Per-file attribution for the meta-36 targets:
   - sao → MODE_RECORDCM (FH-10 report; detector width=28). SSE already
     implemented AND competed there → residual scope on sao is EMPTY.
   - mr, x-ray → MODE_MED16 container; its residual stream goes through a
     NESTED 64KB-chunked value rail; FINDINGS F17/F18: nested winner on
     x-ray slices = geomix 384/384 blocks. THIS is the only live SSE gap.
   - nci, xml → cm2 (has SSE) → no residual scope.
(To be re-confirmed with a real CUBRIM_PROFILE=1 attribution run on 2 MB
slices once the d212c1c binary builds.)

## Ceilings (stated BEFORE probe)

Basis: SSE/APM corrects systematic miscalibration of an existing model's
probabilities; it cannot add new context information. Published PAQ-class
experience (lpaq/paq8 APM stages) and this repo's own cm2: 1-4% on top of
an UNcalibrated single mixer; near 0 on an already-calibrated chain.
Hypothesis's own claim: 2-5% cheap on all files → treat 5% as the claim
ceiling, test ≥2% as the GO bar.

- sao: 0.5254 → ceiling ≈ 0.5254 (no change; winning backend record_cm
  already banks 4 APM stages + competed per-offset SSE; anything further is
  hyper-parameter tuning outside this hypothesis). Mechanism ceiling for
  "ADD SSE" = ~0%.
- mr: 0.2078 → mechanism ceiling if SSE recovers the full claimed 5% on
  the med16-chain coded stream ≈ 0.1974; realistic PAQ-experience band
  1-3% ≈ 0.2016-0.2057. NOTE: rail resets per 64KB chunk; SSE learning
  transient is charged per chunk — the consilium's "≥256KB to train"
  concern applies to exactly this arm and is probed explicitly.
- x-ray: 0.4292 → same mechanism band as mr (same med16 chain):
  5% ceiling ≈ 0.4077, realistic 1-3%.
- nci: 0.04633 vs leader xz 0.04319. Winner backend cm2 already has SSE;
  the 7.3% gap is match/dictionary-class, not calibration-class. Ceiling
  for NEW-08 on nci ≈ 0%.

## Probe design (Gotcha gates)

Python model, 2 MB slices of mr and sao (labelled SLICE/PROBE):
- mr: reconstruct the med16 residual stream faithfully from source
  (med16_detect_width + med16_forward port), then code residual bytes with
  an adaptive order-1 bitwise model (analogue of the rail's adaptive
  CM-class coder; fidelity note: the real nested winner is BWT+geomix — a
  symbol-level coder; the bitwise analogue is the cheapest sound stand-in
  the lane brief prescribes). Arms:
    A base: order-1 bitwise counter model, ideal -log2(p) bits.
    B base+SSE: same model + 2D APM (quantized stretch(p) x 33 knots,
      small ctx), online, learning transient charged (no two-pass).
  Each in two regimes: continuous (whole slice) and 64KB-reset (models the
  production rail chunking).
- sao: control arm — order-1 + record-offset(28) context model with and
  without APM, same regimes. Expected to show APM>0 on a bare model —
  which is precisely what the shipped record_cm ALREADY contains; the
  routing conclusion (scope empty) does not depend on this number.
- Gotcha #6: wire format unchanged by SSE (adaptive, no side info); both
  arms decode with the same single branch; no extra cost terms needed.
- Gotcha #7: no coordinates/permutations transmitted.
- Gotcha #3: no reordering claimed — N/A.

GO bar (from hypothesis): SSE arm recovers ≥2% coded-size reduction on the
mr slice in the 64KB-reset regime (the regime the codec actually runs).

## Results (2026-08-09, all PROBE, slices labelled)

See probe-new08-results.txt (raw). Summary:
- mr med16-residual analogue (2MB slice @2MB, width 512 swept fallback —
  detector declined on slice):
  armA weak base:  cont +9.11%, 64KB-reset +14.42% (context-adding, upper-hint)
  armB strong base (APM ctx SUBSET of model ctx = pure calibration):
                   cont +4.38%, 64KB-reset +10.63%
- sao record-stream control (2MB slice @1MB, W=28, strong base):
                   cont -1.80% (SSE hurts under forced blend), reset +0.13%
  vs SHIPPED measured truth (commit ba0a271 PORT-B): per-offset SSE on sao
  = -0.760% full file, competitive-min, already banked in 0.5254.
- Reset regime GAIN > continuous: identity-init APM (no cold-start damage)
  adapts faster than the fresh 128K-cell counter model, so on 64KB blocks
  SSE RECOVERS transient rather than suffering it — refutes the routing's
  "negative ROI below 256KB" premise for identity-init competed SSE.
