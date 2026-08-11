# PROBE NEW-14b (CM-side deterministic long-run bypass) — notes
# CEILING SECTION WRITTEN BEFORE ANY PROBE RUN.

Date: 2026-08-11. Workspace: fresh clone /home/dev/cubr-new14-bypass-probe
(main d212c1c). Lane extends NEW-14 (parent probe:
documentation/ephemeral/research/probes-20260811/probe-new14-nci-notes.md,
reconstructed copy also in probe scratchpad new14/). Question: can an
LZP-style deterministic long-run bypass wire (flag-per-byte or run-length
coded continuation of verified long matches, literals staying in CM2) close
the nci residual to xz -9e parity?

## 0. Routing / source check (verified in clone @ d212c1c before probe)

- `code/cubrim-rs/src/cm2.rs`: Match models (M1_MIN=6, M2_MIN=3, M3_MIN=12,
  MM_CAP=63) emit `lg.stretch(p)` with `prob[bucket]` CLAMPED to
  [1, PSCALE-1] = [1, 4095] (line ~563), fed into the adaptive Mixer
  (`fn mix`, weight-adaptive) then Apm(256) and Apm(1024) stages, all
  clamped to [1,4095]. There is NO deterministic pathway: even a perfectly
  predicting match at max length bucket pays 8 mixed arithmetic decisions
  per byte, and the mixer/APM adaptation dynamics keep the realized cost far
  above the clamp floor (-log2(4095/4096)*8 = 0.0028 b/B). The parent's
  measured second-half marginal 0.047088 B/B = 0.3767 b/B on ~95%-repeat
  data confirms the realized floor is ~2 orders above the clamp floor.
  The bypass pathway genuinely does not exist in CM2 → the hypothesis class
  is not already implemented (consilium_next constraint holds).
- No `lzp`/`bypass`/`run-mode` branch anywhere in cm2.rs (grep).
- CM2 codes the whole file (no 64 KB ceiling) — re-confirmed.
- MODE_LZ rail exists in codec.rs as competitive-min candidate (parent
  already showed it cannot reach -9e parity — offset-entropy floor).

## 1. CEILING (stated BEFORE probe)

File: nci 33,553,445 B, sha256 fc63a317... (verified in corpus dir).

(a) Mechanism ceiling = xz -9e parity:
    cubrim actual: meta-36 ratio 0.04633482 x N = 1,554,693 B; the parent's
    measured compress-rail blob = 1,554,682 B (11 B container delta; the
    delta math below uses the measured 1,554,682, the standings use meta-36).
    xz -9e = 1,449,272 B (0.043193, matches meta-36 to 6 decimals).
    CEILING: nci 0.046335 -> 0.043193, i.e. recover 105,410 B (105,421 B
    against the meta-36 byte count). Everything else: byte-identical or
    smaller via the per-file competitive rail (bypass must not regress).

(b) Tighter information-theoretic bound for THIS class (bypass touches only
    bytes inside verified long-match continuations):
    covered positions (12-gram repeat, full file, parent-measured) =
    31,741,052 (94.5985%). cubrim-vs-xz per-byte gap on covered-dominated
    data = second-half marginal gap = 0.047088 - 0.041046 = 0.006042 B/B
    = 0.0483 bits/byte.
    Max recoverable ≈ 31,741,052 x 0.006042 = 191,787 B (~186 KB... stated
    exactly: 191,787 B = 0.00572 ratio points).
    Caveat stated honestly: the 0.0483 b/B gap is measured on the second
    half (~95% covered) and attributed entirely to covered bytes; it is an
    upper attribution. Since 191,787 B > 105,410 B, the class is NOT
    information-starved — parity requires recovering ≈55% of the touchable
    gap. Whether the wire's own cost (flag/length streams) leaves that much
    is exactly what the probe must decide.

Falsifiable pre-run predictions:
- If the flag-stream adaptive cost on nci's covered runs is <= ~0.01 b/B
  amortized AND CM2's attributed covered-byte cost c_cov >= ~0.05 b/B, the
  modeled bypass lands at or below xz -9e (ADVANCE candidate).
- Calibration: the same model on samba (cubrim already -16% ahead of xz)
  must NOT predict a comparable relative win — samba's covered-run structure
  is less deterministic (lower hit rate, shorter runs -> flag cost per
  covered byte rises toward/above c_cov). A model predicting big wins on
  both files is broken (NEW-08 lesson) and voids the GO.

## 2. Probe design (before run)

PROBE = Python size model, one cost term per decoder branch (Gotcha #6):

Predictor: at position t, context = exact 12-gram data[t-12:t]; prediction =
data[j+12] where j = nearest previous start of the same 12-gram (64-bit poly
fingerprint identity, same method as parent; collision odds ~6e-5 over 33.5M
positions). Decoder-computable from decoded history — no transmitted
coordinates (Gotcha #7: no pointer branch to charge).

Variant A (per-byte flag): branches = (1) flag stream: adaptive binary,
context = run-length bucket min(len,63) mirroring CM2's Match bucketing,
KT-style adaptive counters, cost = sum -log2 p; ALSO order-0 single-counter
variant reported; (2) literal stream: every non-hit byte (miss, no-predictor,
first 12) charged at c_lit; (3) mode/tier signaling: +1 byte.

Variant B (run-length): branches = (1) length stream: maximal hit-runs
within has-predictor blocks, symbol = bitlength(L+1) adaptively coded (KT)
+ (bitlength-1) raw bits; terminating miss implied by length code (block
boundaries decoder-known, no flag branch); (2) literal stream at c_lit;
(3) mode byte.

c_cov / c_lit derivation (stated honestly): attribute cubrim's measured
bits via the 2x2 per-half system using probe-measured per-half hit counts:
  bits(first 16,777,216 B) = 764,716x8 = n_H1*c_cov + n_L1*c_lit
  bits(rest)              = 789,966x8 = n_H2*c_cov + n_L2*c_lit
Known bias: CM2 warmup makes first-half bytes dearer; conditioning of the
system depends on the hit-fraction difference between halves — report the
solved values AND a sensitivity band; cross-check c_cov against a DIRECT
measurement (below).

Direct floor measurement (real codec, not a model): compress
nci[0:4MB]+nci[0:4MB] (8 MB doubled input) with the parent's binary
cubrim-new24-fba3f88 (compress rail, CUBR_THREADS=4, nice 10). Second-copy
marginal = total - 201,576 B (parent's 4 MB anchor) = CM2's realized
per-byte cost on 100%-deterministic continuation at 4 MB distance =
lower bound for c_cov and the exact quantity the bypass eliminates.
xz -9e on the same doubled file for reference.

Calibration on samba (21,606,400 B, sha 93ba07bc...): identical model;
samba has no per-half cubrim anchors, so the decision instrument is
n_H_samba x c_cov (transfer: nci-derived c_cov, and the direct ε floor) vs
samba's flag-stream cost — predicted savings must be small relative to
samba's existing −16% margin, and per-covered-byte flag cost should sit
near/above c_cov (class-specificity check).

## 3. Probe results (PROBE — model figures, measured 2026-08-11)

### 3.1 xz -9e deterministic marginal (real tool, reference)
nci-4m doubled (nci[0:4MB] twice, 8,388,608 B): xz -9e = 228,156 B vs single
227,504 B -> second identical 4 MB copy costs 652 B = 0.00124 bits/byte.
xz's cost on a perfectly-predictable continuation is essentially zero.

### 3.2 Per-byte nearest-prev LZP predictor, G=12 (variant A wire, full stream)
nci: has_pred 31,741,052 (94.5985% — matches parent coverage exactly),
hits 28,587,363 (85.20% of all positions; hit|pred = 90.06%).
Per-half hit fractions: 0.84573 / 0.85826.
PROBE flag stream (bucketed adaptive, KT, buckets=min(runlen,63)):
12,622,449 bits = 1,577,806 B — ALREADY LARGER than cubrim's whole archive
(1,554,682 B) before any literal is charged. Order-0 flags: 1,852,700 B.
Run-length wire (variant B): 1,811,183 B over 3,353,489 runs (mean run 8.5).
=> Variant A/B FULL-STREAM wires are dead on arrival: per-byte nearest-prev
prediction is only 90% accurate and short-run dominated on nci.

### 3.3 The 2x2 per-half attribution is ILL-POSED (honest statement)
bits(first half)=6,117,728, bits(second)=6,319,728; hits 14.19M/14.40M.
Solving forces c_lit < 0: the second half has MORE hits yet costs MORE bits
— CM2's covered-byte cost is not constant (it RISES deeper into the file,
consistent with the parent's marginal finding). A homogeneous two-class
attribution cannot be extracted; c_cov is instead (i) bracketed by the
budget identity (c_lit <= 2.5 b/B forces c_cov in [0, 0.26] b/B) and
(ii) anchored by the DIRECT doubled-file measurement (3.5).

### 3.4 Pointer-following predictor (exact CM2 Match m3 semantics, idealized
true nearest-prev lookup) + trigger threshold T (bypass only on runs >= T)
nci: hit|flagged = 94.06%, hit-bytes 88.98% of positions, mean run 15.8.
PROBE min flag stream (per-bucket empirical entropy) = 1,003,896 B
(0.269 bits/hit-byte). Threshold scan (savings = bypassed_bytes*c_cov −
flagbits), c_cov sensitivity band:
  c_cov=0.10 b/B: best T=64,  savings  47,826 B  (45% of parity gap)
  c_cov=0.18 b/B: best T=64,  savings 119,279 B  (113% of gap)
  c_cov=0.26 b/B: best T=8,   savings 296,121 B  (281% of gap)
At T=64 the flag stream is only 331,918 bits over 7,145,288 bypassed bytes
(0.046 bits/byte) — the wire's own cost is NOT the binding constraint;
everything hinges on CM2's realized per-byte cost on long verified runs.

samba (calibration, same model): has_pred 63.1% of positions, hit-bytes
57.80%, hit|flagged 91.59%, flag floor 0.395 bits/hit-byte. Best savings:
20,175 B @0.10 / 52,060 B @0.18 / 101,005 B @0.26 — 0.6%/1.7%/3.2% of
samba's 3,138,978 B archive vs nci's 3.1%/7.7%/19.0%. Class-specific, not
universal (samba's existing −16% lead over xz is not overturned or
mimicked; gains scale with deterministic-run mass as the mechanism demands).

### 3.4b Secondary predictor variants (PROBE)
- per-byte nearest-prev G=16: hit|flagged 90.02%, flag floor 0.442
  bits/hit-byte, long runs essentially absent (bypassed bytes at T>=128 ~ 0,
  best savings ~0). Per-byte re-lookup switches sources constantly in nci's
  locally-periodic regions — the wrong wire for this class.
- ptr-follow G=24: hit|flagged 95.24%, mean run 20.0, flag floor 0.230
  bits/hit-byte; T=64: 7,829,513 bypassed bytes, 50,515 B flags; savings
  47,354 B @c_cov=0.10 / 125,649 B @0.18. Marginally better than G=12;
  parity boundary moves from c_cov ~ 0.1645 to ~ 0.159 b/B.

DECISION BOUNDARY derived from the scans: the bypass reaches the 105,410 B
parity gap iff CM2's realized per-byte cost on long verified-run bytes
(c_cov, the quantity ε measured next) is >= ~0.16 bits/byte.

### 3.5 DIRECT CM2 floor measurement (real codec, doubled input) — DECISIVE
nci[0:4MB]+nci[0:4MB] (8,388,608 B) through cubrim-new24-fba3f88 (=0.3.2,
byte-identical to main per parent lane), compress rail, CUBR_THREADS=4,
nice 10: 219,379 B (time 1450.7 s — loaded box; first attempt died at a
1500 s timeout). Blob mode byte (offset 5) = 16 = MODE_CM2 (verified via
od; not MODE_LZ — the competitive rail kept CM2). Round-trip decompress +
cmp OK.
  second-copy marginal = 219,379 − 201,576 (parent 4 MB anchor, same
  container) = 17,803 B over 4,194,304 B
  => ε_CM2 = 0.033957 bits/byte on 100%-deterministic continuation.
  xz -9e same experiment: 652 B = 0.0012 bits/byte (27x cheaper, but both
  are SMALL in absolute terms).
Implied literal/branch cost (budget identity, ptr-follow classes):
c_lit = (12,437,456 − 29,855,501x0.033957)/3,697,944 = 3.09 bits/byte —
coherent with the c_lit <= 3.36 bracket from 3.3.

### 3.6 Class-best savings under the MEASURED floor (PROBE)
savings_bits(T) = bypassed_hit_bytes(T) x c_cov − flagbits(T), c_cov = ε:
  ptr12: T=64: −11,161 B (flags cost MORE than CM2's own coding of those
         bytes); T=128: −2,232 B; T=256: +3,964 B; T=512: +3,861 B;
         T=1024: +2,213 B. BEST ≈ +3,964 B at T=256.
  ptr24: BEST ≈ +4,205 B at T=256.
  Stress band c_cov = 2ε = 0.068 (generous pre-miss-turbulence allowance):
         best ≈ +19,168 B at T=64 (18% of gap). Parity needs c_cov ≈ 0.16
         = 4.7ε — excluded by the direct measurement.
  samba @ε: best ≈ +2,537 B at T=512 (0.08% of its 3,138,978 B archive) —
         class-specific, near-nil, no false universal win.

### 4. Mechanism attribution (closes NEW-14's remaining scope honestly)
The parent's phrase "per-byte mixer/coder floor on match-covered data" is
now REFINED by direct measurement: that floor is only 0.034 b/B — CM2's
mixer DOES reach near-deterministic cost (p≈0.997/bit) on verified runs;
integrated over all 29.9M hit bytes it is ~127 KB, numerically close to the
105.4 KB residual, but it is NOT bypassable: the intrinsic information of
"where runs end" (the flag stream) costs ≥1,003,896 B at empirical
per-bucket entropy on nci's real 90-94%-predictable, mean-16-byte-run
structure — ~8x MORE than CM2's own mixed coding of the same bytes
(~127 KB). An LZP flag/run-length wire is a strictly WORSE predictor of
continue/miss than the CM2 mixer it would replace, except on the
ultra-deterministic tail (runs >= 256), which is worth only ~4 KB (3.8% of
the gap). The nci residual therefore lives at the ~3.15M miss/branch bytes
+ 1.8M novel bytes (~3.1 b/B in CM2), where xz -9e's globally-optimal
tokenized parse amortizes cost across long matches CM2 must re-earn
per-byte after every branch. That is the NEW-04 (LZMA-class tokenized
backend + optimal parse) axis, already NO-GO'd — an architecture-class
fact, not a recoverable bypass.

Files: probe_new14b_bypass.py, probe_new14b_variants.py (this directory);
run artifacts in probe scratchpad new14b/ (nci-4m-doubled.cub RT-verified,
cubrim-doubled.log, nci-4m.xz9e).
