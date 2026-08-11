# Density-branch probe wave, 2026-08-09 — verdicts index

Seven open density hypotheses were probed in parallel (one agent per
hypothesis, own worktree off `main` d212c1c), probe-first per the project
gotchas: ceiling stated before probe, Gotcha #3/#6/#7 gates, per-file figures
only, current meta-36 standings override any stale numbers embedded in the
hypothesis rows. Full per-lane records in this directory.

| lane | verdict | one-line basis |
|---|---|---|
| NEW-04 LZMA-class backend | **NO-GO** | Target group evaporated: cubrim already leads samba/xml/mozilla/ooffice at meta 36 — the hypothesis's own best case (xz −3%) is *above* current cubrim. Ablation probe: the proposed mechanism (pos/state/rep contexts) carries −0.12…+0.27% on nci, the only surviving deficit; xz's real nci edge is parse/long-range, not contexts. |
| NEW-05 BWT+CM post-model | **NO-GO** (superseded) | All seven cited gaps inverted: cubrim beats ppmd on every cited file by 1.8–19.4%. The 64 KB BWT ceiling survives only in the value rail; CM2 codes text whole-file. Probe confirms BWT+large-block direction (−7.2% at whole-file vs 64 KB blocks) but the class tops out ≈ ppmd — below shipped cubrim. |
| NEW-06 LZP long-range | **NO-GO** | Target already met (enwik8 0.19553 < 0.215 goal). CM2's m1/m2/m3 ARE LZP with absolute u32 positions — no window to escape; eviction-survival at tbits=27 is 69–94% at the cited distances. Measured incremental ceiling Δratio ≤ 0.001. |
| NEW-08 SSE/APM layer | **ADVANCE-TO-PREREG (narrowed)** | Broad claim stale (cm2/geocm/ppmd/record_cm already carry SSE; sao shipped −0.760%). Live hole: the value-rail geomix/ctxmix coders (MED16 residuals of mr/x-ray) have no calibration stage. Probe: +4.4% (continuous) / +10.6% (production 64 KB-reset) on the mr analogue, transient charged. Correction of record: H-34 was MARGINAL/PLANNED, never NO-GO. |
| NEW-13 typed-column bank | **NO-GO** | Oracle version of the full bank (perfect choice, zero header) still loses to the shipped rail on all five targets (sao +17.1% … kennedy +398% worse). Routing criterion "float XOR-delta ≥+5% vs delta" fails on every real sao float column. Salvage: 4 KB-prefix competitive-min reaches 98–100% of oracle — plumbing for NEW-11/12 if they ever advance. |
| H-25i optimal parser | **NO-GO** (line complete) | Everything routed (DP, rep-price, BT finder) plus H-25k/H-25l landed on main and is active; DB's "integration incomplete" was wrong. The LZ rail loses the competitive pick to CM2 by 21–28% on probed slices — parser perfection changes 0 emitted bytes. nci deficit shown to be whole-file long-range on the CM2 rail (cubrim beats xz at 4 MB scale). |
| NEW-02 PPMd backend | **NO-GO** | Milestone already overshot: cubrim leads ppmd on all 11 text files AND osdb at meta 36 (row's '+30.7% osdb gap' is now −8.3% in cubrim's favor); same-slice real-vs-real, cubrim beats 7z PPMd var.H by 9.5% (dickens) / 10.3% (webster); a parked ~1700-line var.H model already exists in-tree (ppmd.rs, dead-code). Only cp.html (~85 B) and unmeasured literature-grade var.I on dickens even reach parity. |

Cross-lane findings worth their own lines:

1. **The density backlog's premises predate the CM2 flagship.** Five of six
   completed lanes closed because meta-36 standings invert the hypothesis's
   embedded numbers. Any future consilium round must start from live DB
   standings, not row text.
2. **The one sharp density residual is nci vs xz (+7.3%, ~105 KB), and it is
   a whole-file long-range effect on the CM2 rail** — cubrim beats xz on a
   4 MB nci slice (0.0481 vs 0.0610) and loses only at 33.5 MB. Combined
   with NEW-06's eviction analysis (m3 survival ~72% at 16 MB on nci-scale
   inputs, collision-evicted candidates uncharacterised on ultra-repetitive
   data), the next properly-framed hypothesis has a precise mechanism
   target: CM2 match-model capacity/eviction on large highly-repetitive
   inputs.
3. **geocm/ctxmix is the convergence point of both branches**: it is 98.2%
   of x-ray decode time (speed) and the uncalibrated coder the narrowed
   NEW-08 targets (density).
