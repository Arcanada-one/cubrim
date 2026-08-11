# PROBE NEW-06 — LZP / long-range match layer for CM2 (notes)

Date: 2026-08-09. Worktree main = d212c1c. All figures below marked PROBE are
from scripts in this worktree; meta-36 numbers are the measured archive sizes
from the scratchpad standings file.

## Routing check (BEFORE probe)

Hypothesis text is stale on two counts, verified against current sources:

1. Target "enwik8 <=0.215 (ppmd 0.2240)": meta-36 current cubrim enwik8 =
   0.19552678 — the target is ALREADY surpassed by main. ppmd 0.22404 is the
   best competitor; cubrim leads the whole meta-36 field on enwik8.
2. Mechanism premise "дальние повторы вне LZ-окна": cm2.rs (the flagship that
   codes the whole file, no 64 KB ceiling — verified: header comment + no
   chunking in cm2 path; the 64 KB chunking is codec.rs cube rail only) already
   contains THREE LZP-style match models m1/m2/m3:
   - M1_MIN=6, M2_MIN=3, M3_MIN=12 (cm2.rs:487-489)
   - each: direct-mapped table `vec![0u32; 1<<tbits]`, tbits=27 on 100 MB
     (tbits_for = clamp(ceil(log2 len)+3, 18, 27), TBITS_MAX=27, cm2.rs:441-460)
   - table stores ABSOLUTE u32 position of the last occurrence of the
     minlen-gram (cm2.rs:577 `self.hash[hi] = t as u32`); lookup (cm2.rs:570-575)
     follows it with NO distance window.
   => Max representable match distance at tbits=27 on a 100 MB input:
   the full file (u32 caps at 4 GB). The effective limit is not a window but
   direct-mapped eviction: candidate at distance d survives ~exp(-d/2^27)
   (each intervening position writes 1 random slot/table). Survival:
   d=1 MB: 99.2%; 8 MB: 94%; 16 MB: 88%; 32 MB: 78%; 50 MB: 69%; 100 MB: 47%.
   Long-range prediction is effectively m3's job (12-byte key; 3- and 6-byte
   grams recur near constantly, so their "last occurrence" is almost always
   near).

## Ceiling model (committed BEFORE running the probe)

Gotcha #6 decoder-branch accounting for an ideal long-range match layer over
CM2 (branches: per-byte match/literal flag; matched byte; literal byte):

  bits/byte_new = (1-cov)*c + cov*f + H2(cov)

  c   = current CM2 bits/byte from meta-36 archive size (= 8*ratio)
  cov = fraction of bytes covered by matches len>=16 whose NEAREST previous
        occurrence is beyond the distance class of interest (measured by probe)
  f   = residual cost per covered byte (flag + slip), charged at 0.10 b/B
        (optimistic ideal)
  H2  = binary entropy of the flag (the decoder-branch charge)

Naive ceiling (pretends CM2 has no long-range model) uses cov directly.
Mechanism-honest incremental ceiling multiplies cov by the eviction
probability (1-exp(-d/2^27)) — the only long-range matches current m3 can
LOSE — because everything else is already reachable by m3 today.

Per-file c (meta-36): enwik8 1.5642 b/B; webster 1.1180 b/B; samba 1.1622 b/B.

## Probe method

probe_longrange.py: content-sampled exact-gram scan. 16-byte grams, numpy
rolling 64-bit hash, keep positions with (h & 15)==0 (~1/16 of positions,
content-based so ALL occurrences of a sampled gram are indexed => nearest
previous occurrence is exact for sampled grams). Dict gram-hash -> last pos,
verify 16 raw bytes equal (kills 64-bit collisions). Buckets of nearest-prev
distance: <=64K, 64K-1M, 1-8M, 8-16M, >16M. Coverage proxy: fraction of
sampled anchors with a >=16 exact match in bucket (position-fraction ~
byte-coverage for long matches). enwik8 input = 32 MB HEAD SAMPLE only.

## PROBE results (2026-08-09, commands in probe_longrange.py, run with nice -10)

Sampling: content-based (h&15)==0, exact-16-byte verification, 0 collisions
dropped on all 3 files. Sample fractions: enwik8-head 6.28%, webster 5.99%,
samba 12.69% (samba's repeated grams skew hash-mod density — content-based,
still unbiased over gram population; stated honestly).

Nearest-previous-occurrence coverage (len>=16 exact), PROBE:
  enwik8-head32m (HEAD SAMPLE, not enwik8): >1M 8.246%, >8M 3.010%, >16M 0.957%
  webster: >1M 10.072%, >8M 3.547%, >16M 1.469%
  samba:   >1M  2.334%, >8M 0.171%, >16M 0.030%

Ceilings (model committed above, f=0.10 b/B):
  enwik8: 0.19553 -> naive 0.18043; eviction-honest incremental 0.19460
  webster: 0.13974 -> naive 0.12693; incremental 0.13889
  samba:   0.14528 -> naive 0.14218; incremental 0.14516
Incremental = 3.7-6.6% of the naive ceiling. Naive ceiling itself overstates:
c is the file-average CM2 cost, and bytes inside long repeats already cost CM2
far less than c because m3 already fires on them (full-file reach).

Unmeasured second-order channel: LZP nearest-occurrence may truncate a match
that a farther candidate would extend (multi-candidate index needed) — noted
as a void, direction: would raise incremental slightly, bounded by bucket
mean-ext-len (~21-25 B on enwik8-head/webster long buckets, i.e., short).

VERDICT: NO-GO (see final message).
