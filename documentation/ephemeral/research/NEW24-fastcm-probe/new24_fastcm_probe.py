#!/usr/bin/env python3
"""NEW-24 Fast-CM probe: density cost of model-subset ablation (tier ladder).

Numba-jitted bitwise CM analogue, faithful IN STRUCTURE (information sources)
to code/cubrim-rs/src/cm2.rs, not in constants:
  - MSB-first binary decomposition of bytes, partial-byte context c0
  - 12 hashed order contexts (orders 0..11), count-adaptive 12-bit counters
  - 6 sparse skip-grams: exact cm2 pairs (1,3)(1,4)(2,4)(2,3)(1,5)(3,5)
  - 1 indirect model: history-of-history keyed by order-2 context (2^20 map)
  - 4 word models: word / prev-word x word / case-folded word / cf bigram
  - 3 LZP match models, minlen 6/3/12, verified candidates, per-len prob
  - 2 context-selected L1 logistic mixers (prev-byte view, match-state view)
    + L2 mixer (cm2 has 5 L1; stated simplification)
  - 1 APM/SSE on prev byte (cm2 has 2; stated simplification)
  - ideal code length -log2 p  (real coder measured at 0.45-0.59% of decode)
Single counter per probe (no dual stationary+StateMap) - stated simplification.

Model slot map (26 probed models):
  0..11  orders 0..11
  12..17 sparse 0..5
  18     indirect
  19..22 word1..word4
  23     m1 (minlen 6), 24 m2 (minlen 3), 25 m3 (minlen 12)
"""
import json
import sys
import time

import numpy as np
from numba import njit

TBITS = 22          # real codec derives 24 for 2 MiB; 22 keeps RSS ~0.4 GB (stated)
MBITS = 22          # match table bits
IBITS = 20          # indirect map bits (matches cm2 IBITS)
LIM = 250           # counter count limit
PSCALE = 4096
NMODELS = 26

STRETCH = np.zeros(PSCALE, dtype=np.int64)
for i in range(1, PSCALE):
    STRETCH[i] = int(np.clip(np.log(i / (PSCALE - i)) * 256.0, -2047, 2047))
STRETCH[0] = -2047


def squash12(x):
    return int(np.clip(1.0 / (1.0 + np.exp(-x / 256.0)) * PSCALE, 1, PSCALE - 1))


APM_INIT = np.array([squash12((i - 16) * 128) for i in range(33)], dtype=np.uint16)

M_MINLEN = np.array([6, 3, 12], dtype=np.int64)


@njit(cache=True)
def _run(data, active, stretch, apm_init, m_minlen):
    n = data.shape[0]
    mask32 = np.int64(0xFFFFFFFF)
    tmask = (1 << TBITS) - 1
    # counter tables: p(12 bits) | count<<12
    tabs = np.full((23, 1 << TBITS), 2048, dtype=np.uint32)
    ind_map = np.zeros(1 << IBITS, dtype=np.uint32)
    mtab = np.zeros((3, 1 << MBITS), dtype=np.int64)   # position+1, 0=empty
    mprob = np.full((3, 64), 3072, dtype=np.int64)     # per-len-bucket prob
    # mixers
    NIN = NMODELS + 1
    w1a = np.zeros((256, NIN), dtype=np.float64)   # ctx = prev byte
    w1b = np.zeros((64, NIN), dtype=np.float64)    # ctx = match-state view
    w2 = np.zeros((64, 3), dtype=np.float64)       # L2 over (p1a,p1b,bias)
    for c in range(256):
        for i in range(NIN):
            w1a[c, i] = 0.06
    for c in range(64):
        for i in range(NIN):
            w1b[c, i] = 0.06
        w2[c, 0] = 0.35
        w2[c, 1] = 0.35
    lr1 = 0.008
    lr2 = 0.004
    apm = np.zeros((256, 33), dtype=np.int64)
    apm_cnt = np.zeros((256, 33), dtype=np.int64)
    for c in range(256):
        for i in range(33):
            apm[c, i] = apm_init[i]
    # model state
    hk = np.zeros(12, dtype=np.int64)
    sph = np.zeros(6, dtype=np.int64)
    base = np.zeros(23, dtype=np.int64)   # per-table-model base hash for this byte
    idxs = np.zeros(23, dtype=np.int64)
    st = np.zeros(NIN, dtype=np.float64)
    word_hash = np.int64(0)
    word_lc = np.int64(0)
    prev_word = np.int64(0)
    prev_word_lc = np.int64(0)
    m_ptr = np.zeros(3, dtype=np.int64)
    m_len = np.zeros(3, dtype=np.int64)
    m_pred = np.full(3, -1, dtype=np.int64)
    m_ok = np.zeros(3, dtype=np.int64)     # mid-byte still consistent
    m_bucket = np.zeros(3, dtype=np.int64)
    total = 0.0
    for t in range(n):
        # ---- byte start: contexts (mirrors CmModel::start_byte) ----
        for k in range(12):
            if k == 0:
                hk[0] = 0
            elif t >= k:
                h = np.int64(0x9E3779B1 ^ k)
                for q in range(t - k, t):
                    h = (h * np.int64(0x85EBCA77) + np.int64(data[q])) & mask32
                    h ^= h >> 15
                hk[k] = h
            else:
                hk[k] = np.int64(0xDEAD ^ k)
        # sparse pairs
        pa = np.array([1, 1, 2, 2, 1, 3], dtype=np.int64)
        pb = np.array([3, 4, 4, 3, 5, 5], dtype=np.int64)
        for s in range(6):
            a = pa[s]
            b = pb[s]
            if t >= b:
                h = np.int64(0x10000193)
                h = (h * np.int64(0x85EBCA77) + np.int64(data[t - a])) & mask32
                h ^= h >> 15
                h = (h * np.int64(0x85EBCA77) + np.int64(data[t - b])) & mask32
                h ^= h >> 15
                sph[s] = h
            else:
                sph[s] = np.int64(0xBEEF ^ (a * 7 + b))
        # indirect
        if t >= 2:
            h = np.int64(0x22223333)
            for q in range(t - 2, t):
                h = (h * np.int64(0x85EBCA77) + np.int64(data[q])) & mask32
                h ^= h >> 15
            ind_key = h & ((1 << IBITS) - 1)
        else:
            ind_key = np.int64(0)
        ind_hist = np.int64(ind_map[ind_key])
        prev = np.int64(data[t - 1]) if t > 0 else np.int64(0)
        # base hashes per table model
        for k in range(12):
            base[k] = hk[k]
        for s in range(6):
            base[12 + s] = sph[s]
        base[18] = ind_hist
        base[19] = word_hash
        base[20] = (prev_word * np.int64(0x9E3779B1) + word_hash) & mask32
        base[21] = word_lc
        base[22] = (prev_word_lc * np.int64(0x9E3779B1) + word_lc) & mask32
        # match: candidate lookup at byte start if not continuing
        for m in range(3):
            if active[23 + m] == 0:
                continue
            ml = m_minlen[m]
            if m_len[m] == 0 and t >= ml:
                h = np.int64(0x517CC1B7 ^ m)
                for q in range(t - ml, t):
                    h = (h * np.int64(0x85EBCA77) + np.int64(data[q])) & mask32
                    h ^= h >> 15
                cand = mtab[m, h >> (32 - MBITS)]
                if cand > 0 and cand < t + 1:
                    p0 = cand - 1
                    # verify actual context bytes match (avoid hash junk)
                    good = True
                    if p0 >= ml:
                        for q in range(ml):
                            if data[p0 - ml + q] != data[t - ml + q]:
                                good = False
                                break
                    else:
                        good = False
                    if good:
                        m_ptr[m] = p0
                        m_len[m] = ml
            m_pred[m] = np.int64(data[m_ptr[m]]) if (m_len[m] > 0 and m_ptr[m] < t) else np.int64(-1)
            m_ok[m] = 1 if m_pred[m] >= 0 else 0
        mstate_ctx = ((min(m_len[0], 15) << 1) | (1 if m_ok[0] == 1 else 0)) & 63
        # ---- 8 bits MSB first ----
        byte = np.int64(data[t])
        c0 = np.int64(1)
        for j in range(7, -1, -1):
            y = (byte >> j) & 1
            # table model probes
            for m in range(23):
                if active[m] == 0:
                    st[m] = 0.0
                    continue
                cx = (base[m] * np.int64(0x2545F491) + c0) & mask32
                cx ^= cx >> 15
                cx = (cx * np.int64(0x85EBCA77)) & mask32
                idx = cx >> (32 - TBITS)
                idxs[m] = idx
                slot = np.int64(tabs[m, idx])
                p = slot & np.int64(0xFFF)
                st[m] = np.float64(stretch[p]) / 256.0
            # match inputs
            for m in range(3):
                mi = 23 + m
                if active[mi] == 0 or m_ok[m] == 0:
                    st[mi] = 0.0
                    m_bucket[m] = -1
                    continue
                eb = (m_pred[m] >> j) & 1
                bkt = min(m_len[m], 63)
                m_bucket[m] = bkt
                sv = np.float64(stretch[mprob[m, bkt]]) / 256.0
                st[mi] = sv if eb == 1 else -sv
            st[NMODELS] = 1.0  # bias
            # L1 mixers
            d1 = 0.0
            d2 = 0.0
            for i in range(NIN):
                d1 += w1a[prev, i] * st[i]
                d2 += w1b[mstate_ctx, i] * st[i]
            p1a = 1.0 / (1.0 + np.exp(-d1))
            p1b = 1.0 / (1.0 + np.exp(-d2))
            if p1a < 1e-6:
                p1a = 1e-6
            if p1a > 1.0 - 1e-6:
                p1a = 1.0 - 1e-6
            if p1b < 1e-6:
                p1b = 1e-6
            if p1b > 1.0 - 1e-6:
                p1b = 1.0 - 1e-6
            x2a = np.log(p1a / (1.0 - p1a))
            x2b = np.log(p1b / (1.0 - p1b))
            l2c = prev & 63
            dd = w2[l2c, 0] * x2a + w2[l2c, 1] * x2b + w2[l2c, 2]
            pm = 1.0 / (1.0 + np.exp(-dd))
            # APM on prev byte, 33 buckets over stretch domain
            stq = np.log(pm / (1.0 - pm)) * 256.0
            if stq < -2047.0:
                stq = -2047.0
            if stq > 2047.0:
                stq = 2047.0
            fidx = (stq + 2048.0) / 128.0
            i0 = int(fidx)
            if i0 > 31:
                i0 = 31
            fr = fidx - i0
            pa_ = (apm[prev, i0] * (1.0 - fr) + apm[prev, i0 + 1] * fr) / PSCALE
            pf = 0.75 * pm + 0.25 * pa_
            if pf < 1e-6:
                pf = 1e-6
            if pf > 1.0 - 1e-6:
                pf = 1.0 - 1e-6
            total += -np.log2(pf) if y == 1 else -np.log2(1.0 - pf)
            # ---- updates ----
            err2 = y - pm
            w2[l2c, 0] += lr2 * err2 * x2a
            w2[l2c, 1] += lr2 * err2 * x2b
            w2[l2c, 2] += lr2 * err2
            e1a = y - p1a
            e1b = y - p1b
            for i in range(NIN):
                if st[i] != 0.0 or i == NMODELS:
                    w1a[prev, i] += lr1 * e1a * st[i]
                    w1b[mstate_ctx, i] += lr1 * e1b * st[i]
            for m in range(23):
                if active[m] == 0:
                    continue
                slot = np.int64(tabs[m, idxs[m]])
                p = slot & np.int64(0xFFF)
                cnt = slot >> 12
                nn = cnt if cnt < LIM else LIM
                p = p + (((y << 12) - p) * 2) // (2 * nn + 3)
                if p < 1:
                    p = 1
                if p > PSCALE - 1:
                    p = PSCALE - 1
                if cnt < LIM:
                    cnt += 1
                tabs[m, idxs[m]] = np.uint32((cnt << 12) | p)
            for m in range(3):
                if m_bucket[m] >= 0:
                    eb = (m_pred[m] >> j) & 1
                    hit = 1 if eb == y else 0
                    bkt = m_bucket[m]
                    mprob[m, bkt] += ((hit << 12) - mprob[m, bkt]) // 32
                    if mprob[m, bkt] < 1:
                        mprob[m, bkt] = 1
                    if mprob[m, bkt] > PSCALE - 1:
                        mprob[m, bkt] = PSCALE - 1
                    if eb != y:
                        m_ok[m] = 0   # mid-byte break, like cm2 match
            # APM update
            tgt = y << 12
            ca = apm_cnt[prev, i0]
            cb = apm_cnt[prev, i0 + 1]
            ra = ca if ca < LIM else LIM
            rb = cb if cb < LIM else LIM
            apm[prev, i0] += ((tgt - apm[prev, i0]) * 2 * int((1.0 - fr) * 8 + 1)) // ((2 * ra + 3) * 9)
            apm[prev, i0 + 1] += ((tgt - apm[prev, i0 + 1]) * 2 * int(fr * 8 + 1)) // ((2 * rb + 3) * 9)
            apm_cnt[prev, i0] = ca + 1
            apm_cnt[prev, i0 + 1] = cb + 1
            c0 = (c0 << 1) | y
        # ---- byte end (mirrors CmModel::end_byte) ----
        b = byte
        ind_map[ind_key] = np.uint32((np.int64(ind_map[ind_key]) * np.int64(0x6F4A7C13) + b + 1) & mask32)
        isalnum = (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122)
        if isalnum:
            word_hash = (word_hash * np.int64(0x6F4A7C13) + b + 1) & mask32
            bl = b + 32 if 65 <= b <= 90 else b
            word_lc = (word_lc * np.int64(0x6F4A7C13) + bl + 1) & mask32
        else:
            if word_hash != 0:
                prev_word = word_hash
                prev_word_lc = word_lc
            word_hash = np.int64(0)
            word_lc = np.int64(0)
        # match advance + insert
        for m in range(3):
            if active[23 + m] == 0:
                continue
            if m_len[m] > 0 and m_ptr[m] < t and np.int64(data[m_ptr[m]]) == b:
                m_ptr[m] += 1
                m_len[m] += 1
            else:
                m_len[m] = 0
            ml = m_minlen[m]
            if t + 1 >= ml:
                h = np.int64(0x517CC1B7 ^ m)
                for q in range(t + 1 - ml, t + 1):
                    h = (h * np.int64(0x85EBCA77) + np.int64(data[q])) & mask32
                    h ^= h >> 15
                mtab[m, h >> (32 - MBITS)] = t + 1
    return total


TIERS = [
    ("full26", list(range(26))),
    ("B-drop-word234(23)", list(range(20)) + [23, 24, 25]),
    ("C-drop-sparse(17)", list(range(12)) + [18, 19, 23, 24, 25]),
    ("D-drop-indirect(16)", list(range(12)) + [19, 23, 24, 25]),
    ("E-drop-ord8-11(12)", list(range(8)) + [19, 23, 24, 25]),
    ("F-drop-ord5-7(9)", list(range(5)) + [19, 23, 24, 25]),
    ("G-TIER-M(8)", list(range(5)) + [19, 23, 25]),
    ("H-TIER-S(5)", list(range(4)) + [23]),
]


def main():
    fpath = sys.argv[1]
    name = sys.argv[2]
    tiersel = sys.argv[3:] if len(sys.argv) > 3 else None
    data = np.frombuffer(open(fpath, "rb").read(), dtype=np.uint8)
    out = []
    for tname, slots in TIERS:
        if tiersel and tname not in tiersel:
            continue
        active = np.zeros(26, dtype=np.int64)
        for s in slots:
            active[s] = 1
        t0 = time.time()
        bits = _run(data, active, STRETCH, APM_INIT, M_MINLEN)
        el = time.time() - t0
        bytes_ = bits / 8.0 + 2.0  # +2 B tier/header charge (Gotcha #6)
        ratio = bytes_ / len(data)
        nmod = len(slots)
        speedup = 1.0 / (0.17 + 0.83 * nmod / 26.0)
        rec = {"file": name, "tier": tname, "nmodels": nmod, "bits": round(bits, 1),
               "bytes": round(bytes_, 1), "ratio": round(ratio, 6),
               "pred_speedup": round(speedup, 2), "wall_s": round(el, 1)}
        print(json.dumps(rec), flush=True)
        out.append(rec)
    return out


if __name__ == "__main__":
    main()
