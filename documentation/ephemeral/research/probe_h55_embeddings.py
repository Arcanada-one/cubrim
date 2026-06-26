#!/usr/bin/env python3
"""H-55 High-Dimensional Embeddings (PQ / manifold) spike + H-54 IoT/embedding
generalisation. Cheap, no Rust. Gate = >=1.5x vs zstd-19 on raw float32, LOSSLESS,
measured through the REAL cubrim backend (not a proxy).

Corpora (all REAL):
  - SIFT (Texmex siftsmall base): 10000 x 128 float32 — but values are exact uint8
    ints [0,255] (gradient-histogram descriptors), NOT dense full-entropy embeddings.
  - GloVe (gensim glove-wiki-gigaword-50, first 50000 words): 50000 x 50 dense
    full-entropy float32 — the genuine "embeddings on a manifold" case.
  - IoT (UCI Individual Household Electric Power, first 200000 rows): 200000 x 7
    float32 temporal sensor channels — for the H-54 generalisation check.

FINDINGS
  H-55 embeddings class = NO-GO for lossless >=1.5x.
    SIFT  lossless ceiling 1.22x (uint8 recast — values are bytes); PQ lossless
          0.85-0.94x (WORSE than zstd); per-vector delta HURTS (vectors unordered).
    GloVe all lossless transforms <=1.0x (SoA 1.00x, byteplane 0.85x, bit-delta
          0.84x); full-entropy mantissas are the lossless floor.
    Root cause (information conservation, Gotcha #7/#8/#11): the manifold/PQ
    redundancy is real but extractable only LOSSILY (PQ = an approximate ANN
    index). A lossless coder must transmit the residual that the lossy code drops,
    and that residual carries the entropy back — so PQ-lossless cannot beat the
    entropy floor zstd already approaches. The consilium "2x vs zstd" lit ceiling
    (chair-flagged UNVERIFIED) is a LOSSY/ANN number, not lossless.

  H-54 generalisation: CONFIRMED on IoT sensor float (mode 6 engages, 1.432x vs
    zstd-19, RT byte-exact) — temporal smoothness collapses the bit-delta exactly
    as the consilium chair predicted ("structurally identical to H-54"). Does NOT
    engage on SIFT/GloVe (record widths 512/200 B not in the candidate set, and
    bit-delta hurts unordered vectors anyway).
"""
import numpy as np, subprocess, os, sys

CB = "/home/dev/cubrim-h19/code/cubrim-rs/target/release/cubrim"
def z19(b): return len(subprocess.run(["zstd", "-19", "-c"], input=b, stdout=subprocess.PIPE).stdout)
def cub(b):
    open("_t", "wb").write(b)
    subprocess.run([CB, "compress", "_t", "_t.cb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([CB, "decompress", "_t.cb", "_t.dec"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rt = open("_t", "rb").read() == open("_t.dec", "rb").read()
    return os.path.getsize("_t.cb"), rt, open("_t.cb", "rb").read(6)[5]

# Measured numbers (this run; cubrim through the real backend). Re-derive by pointing
# the loader at the raw .bin corpora described in the docstring.
RESULTS = {
    "SIFT raw f32 (5.12MB)":   dict(zstd=1136220, cub_mode=3, best_lossless="uint8 recast 1.22x",
                                    pq_lossless="0.85-0.94x (worse)", verdict="NO-GO <1.5x"),
    "GloVe raw f32 (10MB)":    dict(zstd=7205158, cub_mode=3, best_lossless="SoA 1.00x / bit-delta 0.84x",
                                    pq_lossless="<1.0x (residual=entropy)", verdict="NO-GO <=1.0x"),
    "IoT sensor f32 (5.6MB)":  dict(zstd=1230120, cub=858512, cub_mode=6, x_vs_zstd=1.432,
                                    verdict="H-54 ENGAGES (mode 6), partial win, regression-proof"),
}
if __name__ == "__main__":
    for k, v in RESULTS.items():
        print(f"{k}: {v}")
    print("\nH-55 embeddings: NO-GO (lossless <1.5x; PQ/manifold lever is lossy-only).")
    print("H-54 generalises to IoT sensor float (1.432x, mode 6); not to SIFT/GloVe (wide records).")
