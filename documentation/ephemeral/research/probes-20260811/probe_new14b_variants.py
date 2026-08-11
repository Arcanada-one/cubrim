#!/usr/bin/env python3
"""PROBE NEW-14b variants: class-best-case analysis.

Variants measured on real bytes:
  (a) per-byte nearest-prev predictor, context length G in {12,16,24}
  (b) pointer-following predictor (exact CM2 Match m3 semantics, idealized
      true nearest-prev lookup, no hash collisions) for G=12
For each: hit rate, run-length structure, per-bucket (runlen, capped 4095)
hit/miss tallies -> empirical binary entropy per bucket -> optimal trigger
threshold T maximizing savings = sum_{b>=T} n_b*(c_cov - H_b) under a c_cov
sensitivity band. All figures PROBE (model).
"""
import sys, numpy as np
from math import log2

def nearest_prev(data, G):
    n = len(data)
    ng = n - G + 1
    B = np.uint64(0x100000001B3)
    acc = np.zeros(ng, dtype=np.uint64)
    for j in range(G):
        acc = acc * B + data[j:j + ng].astype(np.uint64)
    order = np.argsort(acc, kind="stable")
    sfp = acc[order]
    same = sfp[1:] == sfp[:-1]
    prev = np.full(ng, -1, dtype=np.int64)
    prev[order[1:]] = np.where(same, order[:-1], -1)
    return prev

def perbyte_arrays(data, G):
    n = len(data)
    prev = nearest_prev(data, G)
    i0 = np.arange(0, n - G)
    p = prev[i0]
    has_pred = p >= 0
    pred = np.zeros(len(i0), dtype=np.uint8)
    pred[has_pred] = data[p[has_pred] + G]
    hit = has_pred & (data[G:] == pred)
    return has_pred, hit

def bucket_stats(has_pred, hit, cap=4095):
    """Per-runlen-bucket hit/miss tallies for the per-byte predictor."""
    n1 = [0] * (cap + 1); n0 = [0] * (cap + 1)
    idx = np.nonzero(has_pred)[0]
    hp = hit[idx].tolist(); pos_l = idx.tolist()
    prev_pos = -2; runlen = 0
    for k in range(len(pos_l)):
        pos = pos_l[k]
        if pos != prev_pos + 1:
            runlen = 0
        prev_pos = pos
        b = cap if runlen > cap else runlen
        if hp[k]:
            n1[b] += 1; runlen += 1
        else:
            n0[b] += 1; runlen = 0
    return n1, n0

def ptr_follow(data, G):
    """CM2 Match m3 semantics with idealized true nearest-prev lookup:
    lookup only when len==0; then follow ptr, verify per byte."""
    n = len(data)
    prev = nearest_prev(data, G)          # prev occurrence by gram START
    d = data.tolist()
    plist = prev.tolist()
    cap = 4095
    n1 = [0] * (cap + 1); n0 = [0] * (cap + 1)
    nolook = 0                            # positions with no predictor
    ptr = 0; ln = 0
    # process byte t given history ..t-1 ; after coding byte t, "end":
    # insert gram ending at t, and if ln==0 lookup gram ending at t.
    # gram ending at t starts at t-G+1 -> prev-start j means occurrence
    # ends at j+G-1, so ptr = j+G.
    for t in range(G, n):
        if ln == 0:
            j = plist[t - G]              # gram ending at t-1 starts t-G
            if j >= 0:
                ptr = j + G; ln = 1       # CM2 sets len=1 on fresh lookup
            else:
                nolook += 1
                continue
        b = ln if ln < cap else cap
        if d[t] == d[ptr]:
            n1[b] += 1; ptr += 1; ln += 1
        else:
            n0[b] += 1; ln = 0
    return n1, n0, nolook

def report(tag, n1, n0, nolook, total_pos, c_cov_band=(0.10, 0.18, 0.26)):
    N1 = sum(n1); N0 = sum(n0); NP = N1 + N0
    print(f"[{tag}] flagged={NP} hits={N1} ({N1/max(NP,1):.4%} of flagged) "
          f"no-pred={nolook}  hit-bytes/all-pos={N1/total_pos:.4%}")
    # empirical per-bucket entropy and cumulative-by-threshold savings
    Hbits = 0.0
    cum = []  # (threshold, hitbytes>=T, flagbits>=T)
    suffix_bits = 0.0; suffix_hits = 0; suffix_flags = 0
    per_b = []
    for b in range(len(n1)):
        a, c = n1[b], n0[b]
        m = a + c
        if m == 0:
            per_b.append((b, 0, 0, 0.0)); continue
        p = a / m
        h = 0.0 if p in (0.0, 1.0) else -(p*log2(p) + (1-p)*log2(1-p))
        Hbits += m * h
        per_b.append((b, a, c, h))
    print(f"  PROBE min flag-stream (empirical per-bucket entropy) = "
          f"{Hbits:.0f} bits = {Hbits/8:.0f} B  ({Hbits/max(N1,1):.5f} bits/hit-byte)")
    # threshold scan (savings under c_cov band); bytes below T stay in CM2
    best = {c: (None, -1e18) for c in c_cov_band}
    for T in [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4095]:
        hb = sum(a for b, a, c, h in per_b if b >= T)
        fb = sum((a+c) * h for b, a, c, h in per_b if b >= T)
        row = f"  T={T:>4}: bypassed-hit-bytes={hb:>9}  flagbits={fb:>12.0f}"
        for cc in c_cov_band:
            sav = hb * cc - fb
            row += f"  save@c_cov={cc:.2f}: {sav/8:>10.0f} B"
            if sav > best[cc][1]:
                best[cc] = (T, sav)
        print(row)
    for cc in c_cov_band:
        T, sav = best[cc]
        print(f"  BEST @c_cov={cc:.2f}: T={T} savings={sav/8:.0f} B")
    # run-length structure
    runs_end = sum(n0) + 0  # each miss ends a run (block-end runs ~negligible)
    print(f"  mean hit-run len ~= {N1/max(runs_end,1):.2f} (hits/misses)")

if __name__ == "__main__":
    which = sys.argv[1]
    path = {"nci": "/home/dev/cubr-cubecore-research/corpus-silesia/nci",
            "samba": "/home/dev/cubr-cubecore-research/corpus-silesia/samba"}[which]
    data = np.fromfile(path, dtype=np.uint8)
    total_pos = len(data)
    mode = sys.argv[2]  # perbyte12|perbyte16|perbyte24|ptr12
    if mode.startswith("perbyte"):
        G = int(mode[7:])
        hp, ht = perbyte_arrays(data, G)
        n1, n0 = bucket_stats(hp, ht)
        nolook = int((~hp).sum())
        report(f"{which} perbyte G={G}", n1, n0, nolook, total_pos)
    elif mode.startswith("ptr"):
        G = int(mode[3:])
        n1, n0, nolook = ptr_follow(data, G)
        report(f"{which} ptr-follow G={G}", n1, n0, nolook, total_pos)
