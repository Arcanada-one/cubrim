#!/usr/bin/env python3
"""PROBE NEW-14b: LZP-style deterministic long-run bypass wire model.

Per-position predictor: nearest previous occurrence of the exact 12-gram
context (64-bit poly fingerprint identity); predicted byte = byte that
followed that occurrence. Decoder-computable from decoded history (no
transmitted coordinates -> no pointer branch, Gotcha #7 satisfied).

Cost terms, one per decoder branch (Gotcha #6):
  Variant A: (1) flag stream (adaptive binary, run-length-bucket contexts,
             KT-ish counters; order-0 also reported), (2) literal stream at
             c_lit per literal byte, (3) mode byte.
  Variant B: (1) run-length stream (log-bucket symbol adaptively coded +
             raw bits; terminating miss implied), (2) literal stream,
             (3) mode byte.
All figures printed are PROBE (model, not codec).
"""
import sys, numpy as np
from math import log2

GRAM = 12

def lzp_arrays(data: np.ndarray):
    """Return has_pred (bool) and hit (bool) arrays over positions t in
    [GRAM, N): predictor = byte after nearest previous occurrence of the
    12-gram data[t-12:t]."""
    n = len(data)
    ng = n - GRAM + 1                      # grams start 0..n-12
    # 64-bit rolling poly fingerprint of each 12-gram (wraparound mod 2^64)
    B = np.uint64(0x100000001B3)           # FNV-ish odd multiplier
    fp = np.zeros(ng, dtype=np.uint64)
    acc = np.zeros(ng, dtype=np.uint64)
    for j in range(GRAM):
        acc = acc * B + data[j:j + ng].astype(np.uint64)
    fp = acc
    # nearest previous occurrence of same fp (stable sort trick)
    order = np.argsort(fp, kind="stable")
    sfp = fp[order]
    same = sfp[1:] == sfp[:-1]
    prev = np.full(ng, -1, dtype=np.int64)
    prev[order[1:]] = np.where(same, order[:-1], -1)
    # position t predicts byte data[t]; context gram starts at t-GRAM.
    # gram index i0 = t-GRAM in [0, n-GRAM-1] -> t in [GRAM, n-1] needs
    # i0 <= n-GRAM-1 i.e. t <= n-1. predicted byte = data[prev[i0]+GRAM].
    i0 = np.arange(0, n - GRAM)            # t = i0+GRAM in [GRAM, n)
    p = prev[i0]
    has_pred = p >= 0
    pred_byte = np.zeros(len(i0), dtype=np.uint8)
    pred_byte[has_pred] = data[p[has_pred] + GRAM]
    hit = has_pred & (data[GRAM:] == pred_byte)
    return has_pred, hit

def flag_cost_bucketed(has_pred, hit, ncap=63):
    """Variant A flag stream: adaptive binary counter per run-length bucket
    (bucket = min(current consecutive hit length, ncap)), KT estimator.
    Returns (bits_bucketed, bits_order0, run_length_list-summary)."""
    c1 = [0.5] * (ncap + 1); c0 = [0.5] * (ncap + 1)   # KT counters
    bits = 0.0
    o1 = 0.5; o0 = 0.5; bits0 = 0.0
    runlen = 0
    # iterate only over has_pred positions (flags exist only there)
    idx = np.nonzero(has_pred)[0]
    hp = hit[idx].tolist()
    pos_l = idx.tolist()
    # detect resets: run continues only across consecutive has_pred positions
    # positions in idx; if gap>1 the block broke -> reset runlen
    prev_pos = -2
    lg2 = log2
    for k in range(len(pos_l)):
        pos = pos_l[k]
        if pos != prev_pos + 1:
            runlen = 0
        prev_pos = pos
        b = ncap if runlen > ncap else runlen
        h = hp[k]
        p1 = c1[b] / (c1[b] + c0[b])
        bits += -lg2(p1 if h else 1.0 - p1)
        po = o1 / (o1 + o0)
        bits0 += -lg2(po if h else 1.0 - po)
        if h:
            c1[b] += 1; o1 += 1; runlen += 1
        else:
            c0[b] += 1; o0 += 1; runlen = 0
    return bits, bits0

def runlen_cost(has_pred, hit):
    """Variant B: maximal hit-runs inside has_pred blocks; symbol =
    bitlength(L+1) adaptively coded (KT over 64 symbols) + (symbol-1) raw
    bits. Terminating miss implied by the length code."""
    counts = [0.5] * 64
    tot = 32.0
    bits = 0.0
    nruns = 0
    idx = np.nonzero(has_pred)[0]
    hp = hit[idx].tolist()
    pos_l = idx.tolist()
    prev_pos = -2; L = 0
    def emit(L):
        nonlocal bits, nruns, tot
        s = (L + 1).bit_length()           # symbol >=1
        bits += -log2(counts[s] / tot) + (s - 1)
        counts[s] += 1
        tot += 1
        nruns += 1
    for k in range(len(pos_l)):
        pos = pos_l[k]
        if pos != prev_pos + 1:
            # block break: emit pending run (terminated by block end)
            emit(L); L = 0
        prev_pos = pos
        if hp[k]:
            L += 1
        else:
            emit(L); L = 0                 # run + implied miss
    emit(L)
    return bits, nruns

def analyze(path, name, half_split=None):
    data = np.fromfile(path, dtype=np.uint8)
    n = len(data)
    has_pred, hit = lzp_arrays(data)
    npos = len(has_pred)
    nH = int(hit.sum()); nP = int(has_pred.sum())
    nM = nP - nH; nX = npos - nP
    print(f"[{name}] N={n} positions={npos}")
    print(f"  has_pred={nP} ({nP/npos:.4%})  hits={nH} ({nH/npos:.4%})  "
          f"miss={nM}  no-pred={nX}  hit|pred={nH/nP:.4%}")
    if half_split:
        h = half_split - GRAM             # position array offset
        for label, sl in (("first-half", slice(0, h)), ("second-half", slice(h, npos))):
            hp = has_pred[sl]; ht = hit[sl]
            print(f"  {label}: pos={hp.shape[0]} hits={int(ht.sum())} "
                  f"pred={int(hp.sum())} hitfrac={ht.sum()/hp.shape[0]:.5f}")
    bitsA, bitsA0 = flag_cost_bucketed(has_pred, hit)
    bitsB, nruns = runlen_cost(has_pred, hit)
    print(f"  PROBE flagA bucketed bits={bitsA:.0f} ({bitsA/8:.0f} B, "
          f"{bitsA/nH:.5f} bits/hit-byte over hits, {bitsA/npos:.5f} b/pos)")
    print(f"  PROBE flagA order0  bits={bitsA0:.0f} ({bitsA0/8:.0f} B)")
    print(f"  PROBE runB bits={bitsB:.0f} ({bitsB/8:.0f} B) runs={nruns}")
    return dict(n=n, npos=npos, nH=nH, nM=nM, nX=nX,
                bitsA=bitsA, bitsA0=bitsA0, bitsB=bitsB,
                has_pred=has_pred, hit=hit)

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "nci"
    if which == "nci":
        r = analyze("/home/dev/cubr-cubecore-research/corpus-silesia/nci",
                    "nci", half_split=16777216)
        np.save("/tmp/new14b-nci-hit.npy", r["hit"])
        np.save("/tmp/new14b-nci-pred.npy", r["has_pred"])
    elif which == "samba":
        r = analyze("/home/dev/cubr-cubecore-research/corpus-silesia/samba",
                    "samba")
    elif which == "doubled":
        r = analyze(sys.argv[2], "nci-4m-doubled")
