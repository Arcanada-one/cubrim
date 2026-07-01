# H-55 — High-Dimensional Embeddings (PQ / manifold): NO-GO (lossless) + H-54 IoT generalisation

**Status:** Embeddings class **NO-GO** for lossless ≥1.5× (spike, no Rust). H-54
MODE_BINFLOAT **generalises to IoT sensor float** (1.432× vs zstd-19, mode 6 engages).

**Date:** 2026-06-26 · **Branch:** feat/cubr-bigfiles · spike-first, no Rust, leaderboard untouched.

## Hypothesis (consilium RANK after H-54)

High-Dimensional Sparse Embeddings (LLM/ML vectors). Transform: product quantization →
integer centroid codes → delta on centroid indices. Claimed non-subsumable: manifold
clustering (vectors lie on a low-dim manifold) is invisible to the byte stream; rANS/BWT
see raw float as opaque entropy-noise. Lit ceiling 2× vs zstd — **chair-flagged
UNVERIFIED, verify by spike.** NO-GO risk rated low.

## Corpora (all real)

| corpus | shape | nature |
|---|---|---|
| SIFT (Texmex siftsmall base) | 10000 × 128 f32 (5.12 MB) | values are **exact uint8 ints [0,180]** — gradient-histogram descriptors, NOT dense embeddings |
| GloVe (gensim glove-wiki-gigaword-50, 50k words) | 50000 × 50 f32 (10 MB) | **dense full-entropy** float — the genuine manifold case |
| IoT (UCI Household Electric Power, 200k rows) | 200000 × 7 f32 (5.6 MB) | temporal sensor channels — H-54 generalisation check |

Baseline = zstd-19 on raw float32. Gate < 66 % (≥1.5×), lossless, through the **real
cubrim backend** (not a proxy).

## Measured

**SIFT** (zstd-19 = 1 136 220; gate < 749 905; cubrim raw = mode 3 LZ):

| lossless transform | result |
|---|---|
| uint8 recast (values are bytes) | **1.22×** (best) |
| uint8 SoA by-dim | 1.22× |
| uint8 SoA + delta | 1.00× (delta HURTS — vectors unordered) |
| float32 SoA by-dim | 0.93× |
| **PQ lossless** (codes + integer residual + codebook, m∈{8,16,32}, k=256, RT verified) | **0.85 / 0.94 / 0.88×** — WORSE than zstd |

**GloVe** (zstd-19 = 7 205 158, ratio 0.72 — barely compressible; cubrim raw = mode 3):
SoA by-dim **1.00×**, byteplane 0.85×, **bit-delta (H-54 style) 0.84×** — every lossless
transform ≤1.0×. Full-entropy mantissas are the floor.

## Verdict

**H-55 embeddings = NO-GO for lossless ≥1.5×.** Root cause is information conservation
(Gotcha #7/#8/#11): the manifold/PQ redundancy is real but extractable **only lossily** —
PQ is an approximate ANN index, not a lossless transform. A lossless coder must transmit
the residual the lossy code drops, and (measured) that residual carries the entropy back:
PQ-lossless is 0.85–0.94× on SIFT, i.e. WORSE than plain zstd. The consilium "2× vs zstd"
ceiling is a **lossy/ANN** number, not lossless — the chair's UNVERIFIED flag was correct,
now resolved: lossy-only. On dense full-entropy embeddings (GloVe) nothing beats zstd at
all. Per-vector delta HURTS on both (raw vector order is not manifold-smooth — clustering
is a vector-geometry property, not byte adjacency). Lossless point-cloud-style ordering
gains (H-54) do not transfer because embeddings have no spatial firing order to exploit.

**H-54 generalisation — CONFIRMED on IoT sensor float.** Real UCI household-power sensor
array (200k × 7 f32, 28 B/record, temporal order): cubrim selects **MODE_BINFLOAT (mode 6)**
at **858 512 vs zstd-19 1 230 120 = 1.432×**, RT byte-exact. Temporal smoothness collapses
the bit-delta exactly as the consilium chair predicted ("structurally identical to H-54");
the already-shipped codec partially covers the IoT-sensor-float class with zero new code.
Below the 1.5× gate but a real, regression-proof win over zstd. H-54 does NOT engage on
SIFT/GloVe (record widths 512 / 200 B are outside the {12,16,20,24,28,32} candidate set,
and bit-delta hurts unordered vectors regardless).

## Next

Embeddings class closed (lossless ceiling is the entropy floor; the only ≥1.5× path is
lossy PQ = a different product). H-54 already partially covers IoT-sensor-float (1.43×);
optionally a future run could push it past 1.5× with per-channel decimal/integer delta
(the H-40 lever) on binary float input — a small extension, not a new class. Leaderboard
untouched, NOT pushed.

**Artefacts:** `documentation/ephemeral/research/probe_h55_embeddings.py`
(+ real corpora: SIFT siftsmall, GloVe glove-wiki-gigaword-50, UCI household-power).
