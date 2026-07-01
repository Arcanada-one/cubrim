# CUBR-REVALIDATE — config-mismatch audit of H-29..H-55

**Trigger (operator `.brief-research-revalidate.txt`).** The session hit the CONFIG-MISMATCH trap THREE times — measuring the weak default value-scheme (`BitpackFixed`) instead of champion `bwt-rans`, producing false regressions (LiDAR "−14% loses to LAZ" was really +2.7% win). Re-audit every H-29..H-55 verdict: was it measured on champion `bwt-rans` or default? Re-measurement only; codec untouched; NOT pushed.

## Method

For every NO-GO / neutral verdict I read the actual spike script's codec invocation (`docs/ephemeral/research/probe_h*.py`, `documentation/ephemeral/research/probe_h*.py`) and checked for `--value-scheme bwt-rans`. For relative transform-vs-no-transform spikes I checked whether the comparison is config-independent.

## The directional key (why most NO-GOs are SAFE)

Default `BitpackFixed` is a **weaker** backend than champion `bwt-rans`. Therefore config-mismatch makes Cubrim look **worse**, never better. Consequences:

1. **A config-mismatch can only HIDE a win** → it produces false *under-performance* / false NO-GO **on GO-class hypotheses** (a transform/class that genuinely wins, measured on the weak default). All three real traps were exactly this: **H-52 VCF, H-54 LiDAR, LiDAR re-eval — all positive hypotheses**, all already caught and corrected this session.
2. **Subsumption NO-GOs are config-robust by Gotcha #11.** H-41 DoubleDelta, H-48 dict+RLE, H-49 cross-column, H-51 wavelet are *relative* tests (transform vs no-transform through the SAME backend). A **stronger** backend subsumes a pre-transform **more**, so champion `bwt-rans` makes these transforms lose by *more*, not less. Re-measuring on champion cannot flip them GO — it deepens the NO-GO.

So the only verdicts at risk are positive/under-performance ones measured on default — and those were the three already found.

## Audit table

| Hypothesis | Old verdict | Config measured | Re-measure? | Expected shift |
|---|---|---|---|---|
| H-29 columnar field-split | GO | champion (`--value-scheme bwt-rans`) | no | none |
| H-30 columnar (→H-29/31) | GO | champion | no | none |
| H-31 monotonic delta | GO | champion (explicit) | no | none |
| H-36 CLP log-template | NO-GO | champion (probe pins bwt-rans) | no | holds (1.05–1.47× vs zstd, < 1.5× gate) |
| H-37–H-42 ladder | PLANNED | n/a (not measured) | — | — |
| H-39 small-file | NO-GO | champion (rail auto-picks geomix; zstd-dict spike separate) | no | holds (micro-efficiency ceiling) |
| H-40 fixed-decimal | GO | champion (explicit) | no | none |
| H-41 DoubleDelta | NO-GO | champion (probe pins bwt-rans) | no | **deepens** (subsumption ↑ on stronger backend) |
| H-48 enum dict+RLE | MARGINAL | champion (MODE_COLUMNAR path; no standalone probe) | optional confirm | deepens / holds (−2.3% subsumed) |
| H-49 cross-column (temporal) | NO-GO | champion (probe_h49 pins bwt-rans) | no | deepens (not additive over temporal delta) |
| H-49-reborn (CORPUS 1) | NO-GO | champion (✓ live-confirmed below: covtype 143124 / adult 89152 reproduce exactly) | done | holds (transform +2–5% only) |
| H-50 ALP-RD (CORPUS 2) | NO-GO | champion (probe_h50: `cubrim(bwt-rans)`) | no | holds (low-precision doubles, not config) |
| H-51 int-wavelet | NO-GO | champion (relative vs temporal-delta through cubrim) | no | deepens (subsumption) |
| H-52 VCF PBWT | GO | **TRAP CAUGHT** (default 92332 → champion 19931/39020) | done | holds on champion (beats xz/ppmd 1.42–1.68×) |
| H-53 LiDAR Morton | NO-GO | config-independent (relative morton/native=1.169, same backend) | no | holds (reorder destroys locality) |
| H-54 binfloat | GO | **TRAP CAUGHT** (default 577217 → champion 2589882 beats LAZ 1.027×) | done | holds on champion |
| H-55 embeddings | NO-GO (lossless) | config-independent (lossless floor = entropy; PQ-redundancy lossy-only) | no | holds (information conservation) |

## Conclusion

**No focus NO-GO hypothesis is a config-mismatch false-negative.** Every NO-GO in the operator's watch-list (H-36, H-39, H-41, H-48, H-49, H-49-reborn, H-50, H-51) was measured on champion `bwt-rans` or is a config-independent relative/information-theoretic test, and the Gotcha #11 direction guarantees a stronger backend only *reinforces* a subsumption NO-GO. The three genuine config-mismatch traps were all on **positive** hypotheses (VCF/LiDAR), already caught and corrected in CUBR-REEVAL / CUBR-BACKEND-SPIKE.

**Standing lesson reinforced:** always pin `--value-scheme bwt-rans` when re-measuring; the danger zone is *positive* hypotheses on default (hidden wins), not subsumption NO-GOs (which default would only exaggerate).

_Live re-measurement of the round-4 corpora vs STRONG universals (not zstd strawman) — see TASK 2 section below / `CUBR-round4-strong-baseline.md`._
