# CUBR Backend-Strengthening Spike — PPMd-class entropy backend (Option A)

**Status:** Spike **GO** (margin real, materialised by a PPMd-class model). Integration is a
genuine multi-day PPMd implementation — **plan, don't rush** (brief discipline). No code
this round; codec.rs untouched; invariants intact; NOT pushed.

**Date:** 2026-06-26 · consilium unanimous Option A (strengthen the entropy backend).

## Premise (from the honest re-eval)

Cubrim's *transforms* are best-in-class (LiDAR transform+ppmd beats LAZ 1.16×; columnar
beats universal 1.5–2×; PBWT beats xz/ppmd 1.4–1.7×). The recurring bottleneck is the
**downstream entropy backend** (BWT+rANS/geomix), which the consilium audit rated ~5/8 on
general data. Strengthening it is the highest lever: it lifts every class at once.

## Spike measurements (all real corpora, through real codecs)

### A. LiDAR float-delta streams — backend is the gap, PPMd closes it

Per-column on kitti.bin (the H-54 SoA+delta transform streams), measured size:

| stream | bytes | order0 | **ppmd6** | xz-9e | cub bwt-rans | cub default |
|---|---|---|---|---|---|---|
| xyz0_delta | 460944 | 344043 | **144296** | 156652 | 166816 | 192734 |
| xyz1_delta | 460944 | 336356 | **142811** | 153844 | 162487 | 190370 |
| xyz2_delta | 460944 | 265395 | **88395** | 98752 | 103441 | 122331 |
| refl_raw | 460944 | 269439 | **52431** | 61048 | 60148 | 71749 |
| **total** | | | **427933** | | 492892 | 577184 |

- **ppmd (PPMd var.H, order-6) beats Cubrim's bwt-rans backend by 1.152× per column.**
- transform+ppmd total **427933 < LAZ 495640 (1.16×)** — the margin the brief targets.
- Cubrim bwt-rans 492892 already < LAZ 495640 (the marginal win); ppmd makes it decisive.

### B. Config-mismatch correction (important honesty fix)

The re-eval's "LiDAR loses to LAZ −14%" used Cubrim's **default** scheme (BitpackFixed,
577217). With the champion `bwt-rans` (every leaderboard number uses it), all 5 KITTI scans
**beat LAZ** (aggregate Cubrim 2589882 vs LAZ 2660589 = **1.027×**, RT byte-exact). So LiDAR
already holds vs the domain codec; the backend upgrade turns a +2.7 % aggregate edge into a
~+16 % decisive one.

### C. General data (the universal-rank prize) — backend-limited, confirmed

ppmd vs Cubrim-champion on the holdout corpus (general text/binary, where Cubrim is ~5/8):

| file | Cubrim | xz-9e | **ppmd** | ppmd beats Cubrim |
|---|---|---|---|---|
| c_header.h | 7161 | 6476 | 5478 | 1.31× |
| config.json | 9278 | 8272 | 7016 | 1.32× |
| prose.txt | 6600 | 6452 | 5574 | 1.18× |
| rust_src.rs | 6987 | 6536 | 6088 | 1.15× |
| exe.bin | 14590 | 12628 | 13100 | 1.11× |
| data.csv | 3639 | 3324 | 3364 | 1.08× |

**ppmd beats Cubrim's current backend on every general file (1.08–1.32×)** — a PPMd-class
value-scheme would move the universal rank materially (5/8 → 2–3), the brief's main prize.

### D. A simple context model does NOT capture it (cost reality)

A naive pos-aware adaptive order-N model (Python, range-coder-accurate) on xyz0_delta:
order-1 ≈ 251562, order-2 ≈ 323206, order-3 ≈ 366835 — all **WORSE** than Cubrim's
bwt-rans (166816), let alone ppmd (144296). The learning-cost wall (Gotcha #9) means the
margin needs a *genuine* PPMd (escape method C/D + SEE + order blending), not a toy order-N.
**This is the multi-day algorithm the brief anticipated — no shortcut.**

### E. VCF BGZF honesty (chair's suspicion — resolved)

BGZF (htslib bgzip) is **deflate/gzip-blocked**, genuinely weak — the "3.3–4.1× vs BGZF"
is inflated by BGZF's gzip class. The honest strong-bar margin is **1.42–1.67× vs xz/ppmd**,
which Cubrim's PBWT+bwt-rans still wins (it even beats ppmd-on-raw), so VCF's backend is NOT
the bottleneck. Telemetry likewise wins via the columnar transform (1.84× vs ppmd), backend
not limiting. So the backend upgrade is **LiDAR + general-universal**, neutral-to-positive on
VCF/telemetry.

## Verdict — GO to plan a PPMd-class backend

The 1.16× LiDAR margin and the 1.08–1.32× general-data margin are **real and materialised by
a reference PPMd model**; they are NOT reachable by a simple order-N (cost confirmed). This
is a confirmed GO for the highest-leverage upgrade, with eyes open that it is a multi-day
implementation.

### Integration plan (brief step 2 — for operator review before the build)

1. **New value-scheme `ppmd` (scheme byte 13)** — a PPMd var.H-class model: order-4..6
   context tree, escape method C or D, SEE, with a deterministic **integer** range coder
   (RT byte-exact; the project's f64 schemes already prove range-coder determinism, but
   PPMd should use integer freqs to avoid any float drift).
2. **Competitive min() rail** — `ppmd` competes per-file/per-block like every other scheme;
   selected only where it wins. **Tuned 0.158273 + holdout invariants preserved by
   construction** (it can only be chosen when ≤ the current champion). Applies to the value
   stream AND inside MODE_BINFLOAT columns / MODE_VCF sub-blobs (where it should win on the
   delta-of-float / PBWT-RLE streams).
3. **Tests:** scheme-byte, direct round-trip battery (incl. high-order edge cases), full-codec
   RT, competitive-non-regress, truncated-no-panic; tuned/holdout byte-identical guard.
4. **Verify generalisation post-build:** (a) LiDAR decisive (~1.16× over LAZ); (b) holdout
   aggregate moves toward ppmd's level; (c) telemetry −53% held; (d) world-benchmark rank.
5. **Risks:** PPMd is large (context tree memory, escape/SEE tuning); determinism needs care;
   speed (PPMd is slower than rANS) — acceptable on the research/max-ratio path, gate by
   competitive selection. If the Rust PPMd underperforms the ppmd reference, fall back to a
   context-mixing rANS (order-3/4 with proper escape) before abandoning — but the spike says
   a naive order-N is insufficient, so budget for the real algorithm.

**Fallback (brief Option C):** if the build cannot realise the spike margin, harden telemetry
(already −31..−46 % vs strongest universal) — but the spike does not indicate NO-GO; the
margin is proven, the cost is the only caveat.

**Artefacts:** measurements in this report (probe scripts inline above; corpora: 5 KITTI scans
in research/, holdout corpus, VCF s400/s1000). codec.rs untouched. NOT pushed.
