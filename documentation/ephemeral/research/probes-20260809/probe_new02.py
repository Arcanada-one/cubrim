#!/usr/bin/env python3
"""PROBE NEW-02: PPM-with-SEE (arm A) vs bitwise context-mixing CM-analogue (arm B).

Size MODELS (sum of -log2 p over an arithmetic-stream-equivalent decomposition),
not codecs. Both arms charge every decoder branch through its probability in a
single stream (Gotcha #6): PPM charges each escape decision + the final symbol;
CM charges each of the 8 bits. No transmitted coordinates (Gotcha #7 n/a), no
reordering (Gotcha #3 n/a).

Usage: probe.py {ppm|cm} <file> <slice_bytes>
Prints: arm, file, slice bytes, model bytes, bits/byte, ratio.
"""
import math
import sys
from array import array


def run_ppm(data: bytes) -> float:
    """Order-4 PPM, escape method C prior + adaptive SEE-style escape buckets,
    full exclusion. Returns total code length in bits."""
    LOG2 = math.log(2.0)
    # contexts[k]: dict key(int of last k bytes) -> dict sym -> count
    ctxs = [dict() for _ in range(5)]  # k = 0..4
    # SEE buckets: key (order k 0..4, distinct-bucket 0..4, tot-bucket 0..2)
    # value: [escape_events + 1, total_events + 2]  (adaptive escape estimator)
    see = {}
    bits = 0.0
    c1 = c2 = c3 = c4 = 0  # rolling packed contexts
    n = len(data)
    for pos in range(n):
        s = data[pos]
        excl = set()
        found = False
        keys = (0, c1, c2, c3, c4)
        for k in (4, 3, 2, 1, 0):
            d = ctxs[k].get(keys[k])
            if not d:
                continue
            if excl:
                items = [(sym, c) for sym, c in d.items() if sym not in excl]
            else:
                items = list(d.items())
            if not items:
                continue  # fully excluded context carries no information
            tot = 0
            for _, c in items:
                tot += c
            distinct = len(items)
            db = 0 if distinct == 1 else (1 if distinct == 2 else
                                          (2 if distinct <= 4 else
                                           (3 if distinct <= 8 else 4)))
            tb = 0 if tot <= 4 else (1 if tot <= 32 else 2)
            bk = (k, db, tb)
            st = see.get(bk)
            if st is None:
                # init from escape method C prior for this bucket's first sight
                st = [1.0 + distinct / (tot + distinct), 3.0]
                see[bk] = st
            p_esc = st[0] / st[1]
            if p_esc < 1e-4:
                p_esc = 1e-4
            elif p_esc > 0.9999:
                p_esc = 0.9999
            cs = d.get(s)
            if cs is not None and s not in excl:
                bits += -math.log((1.0 - p_esc) * cs / tot) / LOG2
                st[1] += 1.0
                found = True
                break
            else:
                bits += -math.log(p_esc) / LOG2
                st[0] += 1.0
                st[1] += 1.0
                for sym, _ in items:
                    excl.add(sym)
        if not found:
            bits += math.log(256 - len(excl)) / LOG2
        # update all orders (no update exclusion — plain PPMC updates)
        for k in (0, 1, 2, 3, 4):
            d = ctxs[k].get(keys[k])
            if d is None:
                d = {}
                ctxs[k][keys[k]] = d
            c = d.get(s, 0) + 1
            if c >= 60000:  # rescale
                for q in list(d):
                    d[q] = max(1, d[q] >> 1)
                c = d.get(s, 0) + 1
            d[s] = c
        c4 = ((c3 << 8) | s) & 0xFFFFFFFF
        c3 = ((c2 << 8) | s) & 0xFFFFFF
        c2 = ((c1 << 8) | s) & 0xFFFF
        c1 = s
    return bits


def run_cm(data: bytes) -> float:
    """Bitwise logistic mixing of order-0..4 hashed contexts, adaptive 12-bit
    counters, per-bit-position mixer weights. Deliberately UNDERSTRENGTH vs
    cm2.rs (no SSE/APM, no match/word models, 5 orders not 26 models) — this
    biases the comparison IN FAVOUR of the PPM arm. Returns bits."""
    LOG2 = math.log(2.0)
    MASK = (1 << 22) - 1
    NM = 5
    base = array('H', [2048]) * 4096
    tabs = []
    for _ in range(NM):
        t = array('H')
        for _ in range((MASK + 1) // 4096):
            t.extend(base)
        tabs.append(t)
    STRETCH = [0.0] * 4096
    for p in range(1, 4095):
        STRETCH[p] = math.log(p / (4096.0 - p))
    STRETCH[0] = STRETCH[1]
    STRETCH[4095] = STRETCH[4094]
    # mixer: weights per bit position (8 sets), 5 inputs + bias
    W = [[0.3] * NM + [0.0] for _ in range(8)]
    LR = 0.02
    bits = 0.0
    c1 = c2 = c3 = c4 = 0
    exp = math.exp
    log = math.log
    t0, t1, t2, t3, t4 = tabs
    for s in data:
        h0 = 0x9E3779B1 & MASK
        h1 = (c1 * 0x2545F491) & MASK
        h2 = (c2 * 0x9E3779B1 + 0x7F4A7C15) & MASK
        h3 = ((c3 % 16777213) * 0x85EBCA6B + 5) & MASK
        h4 = ((c4 % 4294967291) * 0xC2B2AE35 + 9) & MASK
        cc = 1
        for i in (7, 6, 5, 4, 3, 2, 1, 0):
            y = (s >> i) & 1
            k = (cc * 0x1000193) & MASK
            i0 = h0 ^ k
            i1 = h1 ^ k
            i2 = h2 ^ k
            i3 = h3 ^ k
            i4 = h4 ^ k
            p0 = t0[i0]; p1 = t1[i1]; p2 = t2[i2]; p3 = t3[i3]; p4 = t4[i4]
            x0 = STRETCH[p0]; x1 = STRETCH[p1]; x2 = STRETCH[p2]
            x3 = STRETCH[p3]; x4 = STRETCH[p4]
            w = W[i]
            dot = (w[0] * x0 + w[1] * x1 + w[2] * x2 + w[3] * x3
                   + w[4] * x4 + w[5])
            if dot > 30.0:
                dot = 30.0
            elif dot < -30.0:
                dot = -30.0
            pf = 1.0 / (1.0 + exp(-dot))
            if y:
                q = pf if pf > 1e-6 else 1e-6
            else:
                q = (1.0 - pf) if pf < 0.999999 else 1e-6
            bits += -log(q) / LOG2
            err = (y - pf) * LR
            w[0] += err * x0; w[1] += err * x1; w[2] += err * x2
            w[3] += err * x3; w[4] += err * x4; w[5] += err
            yy = y << 12
            t0[i0] = p0 + ((yy - p0) >> 5) if 1 <= p0 + ((yy - p0) >> 5) <= 4095 else p0
            t1[i1] = p1 + ((yy - p1) >> 5) if 1 <= p1 + ((yy - p1) >> 5) <= 4095 else p1
            t2[i2] = p2 + ((yy - p2) >> 5) if 1 <= p2 + ((yy - p2) >> 5) <= 4095 else p2
            t3[i3] = p3 + ((yy - p3) >> 5) if 1 <= p3 + ((yy - p3) >> 5) <= 4095 else p3
            t4[i4] = p4 + ((yy - p4) >> 5) if 1 <= p4 + ((yy - p4) >> 5) <= 4095 else p4
            cc = (cc << 1) | y
        c4 = ((c3 << 8) | s) & 0xFFFFFFFF
        c3 = ((c2 << 8) | s) & 0xFFFFFF
        c2 = ((c1 << 8) | s) & 0xFFFF
        c1 = s
    return bits


def main():
    arm, path, sl = sys.argv[1], sys.argv[2], int(sys.argv[3])
    with open(path, 'rb') as f:
        data = f.read(sl)
    n = len(data)
    bits = run_ppm(data) if arm == 'ppm' else run_cm(data)
    by = bits / 8.0
    print(f"PROBE arm={arm} file={path} slice={n} model_bytes={by:.0f} "
          f"bpB={bits/n:.4f} ratio={by/n:.5f}")


if __name__ == '__main__':
    main()
