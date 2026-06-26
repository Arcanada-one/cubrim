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

---

## H-54-IMPL — MODE_BINFLOAT shipped (binary float-array SoA + reversible delta)

**Status:** GO, shipped (container mode 6). Greenlit after the spike GO; generalisation
hardened on 5 real KITTI scans first (operator condition).

**Generalisation (before Rust).** Found 4 more real point clouds. The win is **class-
bound**, not universal — it needs a spatially-smooth row order (consecutive points close):

| corpus | source | order (median consec. dist) | x vs zstd-19 |
|---|---|---|---|
| 5× KITTI Velodyne | azureology + kuixu + darylclimb | tight (0.03–0.04 m) | **1.46 / 1.50 / 1.56 / 1.57 / 1.62** (mean 1.54, 4/5 ≥1.5) |
| nuScenes LIDAR_TOP | mmdet3d demo | loose (0.53 m, re-ordered) | 1.03 |
| ScanNet / SUN RGB-D | mmdet3d demo | indoor RGB-D, no scan order | 1.06 / 1.00 |

Honest scope: Cubrim crushes zstd-19 only on **raw spinning-LiDAR in native firing
order**; cross-sensor clouds without that order get ~parity. The delta lever is an
ordering property of the input, not of "binary floats" in general.

**Built.** `MODE_BINFLOAT=6` (header.rs) + `encode_binfloat`/`decode_binfloat` (codec.rs):
AoS→SoA split at an auto-picked record width (order-0 proxy over candidates {12,16,20,24,
28,32}), each column competitively coded raw or reversible wrapping-uint32 delta of the
float bit pattern (1-byte per-column mode flag), each column nested through the full
LZ/columnar/base competition (`encode_with_config_inner(.., try_binfloat=false)` — the LZ
pass is what entropy-codes the delta streams; `encode_base` alone bitpacks them raw).
Activation gate: `len > 64KB` ∧ `len % 4 == 0` ∧ ≥75 % of sampled float32 are plausible
(finite, |v| in a sane band) — a performance guard; **ratio safety is the competitive
`min(base, binfloat, lz, columnar)`**, not the gate.

**Regression-proofing (measured, not assumed).** The first cut short-circuited LZ/columnar
when binfloat engaged — this **regressed** SUN RGB-D (702039 → 739956, LZ codes it better).
Fixed by competing binfloat *alongside* LZ/columnar via `min()`: SUN RGB-D now selects
MODE_LZ at 702039 (= pre-binfloat, byte-exact), all 8 clouds ≤ pre-binfloat output.

**Tests:** +6 (delta-column reversibility, RT+shrink, widths 16/20/24 + ragged tail,
not-selected-on-text/incompressible, property random float-arrays, truncated-no-panic);
**235 lib + 14 integration green**; clippy 0 new.

**Invariants (critical):** tuned 0.158273 **byte-identical** (RT 10/10), holdout 0.2390
**byte-identical** (RT 6/6) — binfloat is gated >64KB and the plausibility check rejects
config.json (JSON text), so the frozen leaderboard is untouched.

**Verdict GO** — first binary-input class; structural win on raw spinning-LiDAR
(mean 1.54× vs zstd-19, lossless, RT byte-exact), regression-proof on every tested cloud,
zero leaderboard movement. Perf follow-up: file-level LZ runs on big plausible-float files
(~12–29 s/scan) since the short-circuit was removed for safety. NOT pushed.

**Artefacts:** `codec.rs` MODE_BINFLOAT + `header.rs` + 6 tests;
`documentation/ephemeral/research/probe_h54_binfloat_generalize.py` + `h54-binfloat-bench.json`.
