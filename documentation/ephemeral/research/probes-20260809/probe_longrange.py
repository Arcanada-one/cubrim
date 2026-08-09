#!/usr/bin/env python3
"""PROBE NEW-06: long-range repeat coverage (matches len>=16) by nearest-prev distance.

Content-sampled exact-gram scan:
  - 16-byte grams, vectorized 64-bit polynomial hash over all positions (numpy)
  - sample grams with (h & 15) == 0  (~1/16 of positions; content-based, so every
    occurrence of a sampled gram is indexed -> nearest previous occurrence exact)
  - dict: gram-hash -> last position; verify raw 16 bytes equal (drop collisions)
  - bucket the distance to the nearest previous occurrence
Coverage proxy = fraction of sampled anchors whose 16-gram has an exact previous
occurrence in the bucket (position-fraction ~ byte-coverage for long matches).
Also: mean extended match length (forward extension) per bucket, on a sub-sample.
"""
import sys, numpy as np

GRAM = 16
MASK_SAMPLE = 15  # keep ~1/16
B = np.uint64(0x100000001B3)  # FNV-ish odd multiplier

def rolling_hash(buf: np.ndarray) -> np.ndarray:
    n = len(buf) - GRAM + 1
    h = np.zeros(n, dtype=np.uint64)
    for k in range(GRAM):
        h = h * B + buf[k:k + n].astype(np.uint64)
    return h

def main(path: str, label: str):
    data = open(path, 'rb').read()
    buf = np.frombuffer(data, dtype=np.uint8)
    n = len(buf) - GRAM + 1
    h = rolling_hash(buf)
    sampled = np.nonzero((h & np.uint64(MASK_SAMPLE)) == 0)[0]
    hs = h[sampled]
    print(f"# {label}: {len(data)} bytes, {n} gram positions, "
          f"{len(sampled)} sampled ({100.0*len(sampled)/n:.2f}%)")

    edges = [(0, 65536, '<=64K'), (65536, 1 << 20, '64K-1M'),
             ((1 << 20), 8 << 20, '1M-8M'), ((8 << 20), 16 << 20, '8M-16M'),
             ((16 << 20), 1 << 62, '>16M')]
    counts = {lbl: 0 for _, _, lbl in edges}
    lensum = {lbl: 0 for _, _, lbl in edges}
    lencnt = {lbl: 0 for _, _, lbl in edges}
    nomatch = 0
    falsecoll = 0
    last = {}
    LEN_SUB = 8  # extend match length on every 8th hit per bucket
    mv = memoryview(data)
    for pos, hh in zip(sampled.tolist(), hs.tolist()):
        prev = last.get(hh)
        last[hh] = pos
        if prev is None:
            nomatch += 1
            continue
        if mv[prev:prev + GRAM] != mv[pos:pos + GRAM]:
            falsecoll += 1
            continue
        d = pos - prev
        for lo, hi, lbl in edges:
            if lo < d <= hi or (lo == 0 and d <= hi):
                counts[lbl] += 1
                if counts[lbl] % LEN_SUB == 0:
                    L = GRAM
                    top = len(data) - pos
                    while L < min(top, 1 << 16) and data[prev + L] == data[pos + L]:
                        L += 1
                    lensum[lbl] += L
                    lencnt[lbl] += 1
                break
    tot = len(sampled)
    print(f"# no-prev-occurrence: {nomatch} ({100.0*nomatch/tot:.2f}%)  "
          f"hash-collisions dropped: {falsecoll}")
    cum = 0.0
    for lo, hi, lbl in edges:
        frac = counts[lbl] / tot
        ml = lensum[lbl] / lencnt[lbl] if lencnt[lbl] else float('nan')
        print(f"{label} PROBE bucket {lbl:>7}: anchors {counts[lbl]:>9} "
              f"frac {100*frac:6.3f}%  mean-ext-len {ml:8.1f}")
    beyond = [(1 << 20, '>1M'), (8 << 20, '>8M'), (16 << 20, '>16M')]
    for thr, lbl in beyond:
        c = sum(counts[l] for lo, hi, l in edges if lo >= thr)
        print(f"{label} PROBE coverage nearest-prev {lbl:>4}: {100.0*c/tot:6.3f}%")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
