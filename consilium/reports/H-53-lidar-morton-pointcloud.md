# H-53 — LiDAR point-cloud Morton-order: NO-GO (Morton) + H-54 spin-off GO

**Status:** Morton hypothesis **NO-GO** (spike, no Rust). Spin-off **H-54** (binary
float-array SoA + reversible integer delta) **spike-GO** (1 real scan), proposed as
next-run IMPL.

**Date:** 2026-06-26 · **Branch:** feat/cubr-bigfiles · spike-first, no Rust, leaderboard untouched.

## Hypothesis (assigned)

Consilium round-LiDAR RANK#2: map a LiDAR point cloud onto a Morton (Z-order) curve
to expose 3D locality the byte backend cannot see, then delta-code. Honest signal up
front (DeepSeek chair + 3 free): the class MAY be NO-GO — LAZ/Draco already do
Morton+prediction; realistic ceiling without a full geometric predictor 1.2–1.3×,
may miss the 1.5× gate. **Spike-first mandatory; close honestly if NO-GO.**

## Corpus

One real KITTI Velodyne scan (`azureology/kitti-velo2cam` `000007.bin`): 115 236
points × 4 float32 (x, y, z, reflectance) = **1 843 776 B**. Ranges match a real
HDL-64 sweep (x ∈ [−77, 77.5], y ∈ [−79.8, 45.1], z ∈ [−8.1, 2.9], refl ∈ [0, 0.99]).
Baseline = **zstd-19 on the raw .bin = 905 642** (xz-9e = 704 996). Gate < 597 724 (1.5×).

## Method

Faithful, charged, with reversibility proof. Backends: zstd-19 (gate reference),
xz-9e (strong proxy), and the **real cubrim binary** (Gotcha #11 — spike through the
real backend). Honest framing: Cubrim is **lossless**; quantize→uint16 is **lossy**
(~2 mm grid), so a lossy result is only a LOWER BOUND on any lossless scheme. Both
measured.

## Measured

**Lossy (brief's cheap gate, uint16 quantize + Morton + delta):** xyz-only 371 922,
+refl 450 836 = 2.01× — but this **discards precision**, not comparable to lossless
zstd. **Control without Morton-sort: 323 497 < 371 922 with Morton** — Morton already
hurts in the lossy path.

**Morton vs native order (xyz wrapping-uint32 delta, zstd-19):**
native = 484 118, **morton = 566 004 → morton/native = 1.169** — Morton is **+17 %
WORSE**. The native Velodyne order (laser-ring azimuth sweep) already encodes superior
3D locality; the Z-order curve scatters consecutive points across power-of-two
boundaries and **destroys** the run structure the entropy backend exploits.

**Lossless reversible transform (native order, round-trip verified byte-exact):**
per-column float32→uint32 wrapping delta, reflectance kept RAW (delta on refl HURTS:
70 028 → 181 018):

| backend | xyz | refl | total | vs zstd-19 raw | gate |
|---|---|---|---|---|---|
| zstd-19 | 484 118 | 70 028 | 554 146 | **1.634×** | PASS |
| xz-9e | 401 912 | 61 048 | 462 960 | **1.956×** | PASS |
| **real cubrim** (default) | 494 823 | 71 749 | **566 572** | **1.599×** | PASS (RT byte-exact) |

Within-scan consistency (thirds, zstd backend): 1.496× / 1.749× / 1.806×.
(bwt-rans backend on the transformed xyz times out — geomix slow on big blocks, the
known perf cap; default scheme already clears the gate.)

## Verdict

**H-53 Morton-order = NO-GO.** Morton-sort is +17 % worse than native order on real
KITTI data, in both the lossy and lossless paths. The cube / space-filling-curve
locality principle is **counterproductive** for LiDAR: the sensor's native scan order
is already more local than a Z-order curve. Confirms the consilium honest signal and
brief failure-mode #1 — and is a fresh data point for the general lesson that a
reorder only wins when it changes the information the backend can't already reach
(Gotcha #7/#11); here it *removes* reachable locality.

**H-54 spin-off = spike-GO (1 real scan).** What actually clears the 1.5× gate is the
**telemetry-columnar lever family transplanted to a binary float-array input**:
AoS→SoA reorder (H-30) + reversible per-column integer delta (H-31), reflectance
raw. 1.60× through the real cubrim default scheme, lossless, round-trip byte-exact.
This is a **new input class** (binary IEEE-float point cloud / array) that Cubrim
cannot currently ingest — exactly the scope expansion flagged at H-50. Caveats:
(a) only 1 real scan (a 2nd source needs auth — HuggingFace KITTI 401); (b) the win
is "SoA + delta", a known structural transform — Cubrim beats raw-zstd because zstd
doesn't reorder the .bin, the same legitimate framing as the shipped telemetry mode.

## Next

Proposed **H-54-IMPL** (next run, like H-29/H-52 spike→IMPL split): a binary
float-array container mode (detect fixed-width float record stream → SoA split →
per-column reversible delta vs raw, reflectance/attribute columns raw → competitive
min + mode byte → RT/property tests, tuned/holdout byte-identical). Strengthen first
with ≥1 more real scan. Leaderboard untouched, NOT pushed.

**Artefacts:** `documentation/ephemeral/research/probe_h53_lidar_morton.py` (+ real
KITTI scan `kitti.bin` 000007).
