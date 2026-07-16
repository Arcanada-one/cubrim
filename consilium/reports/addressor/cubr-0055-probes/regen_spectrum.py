# -*- coding: utf-8 -*-
# CUBR-0055 REGEN — generator-compressibility spectrum of UNIQUE 512-B matrices.
# For every unique matrix: fit cheap generator families (const / arith / xor-delta /
# periodic<=64 / RLE / xorshift32 / xorshift64 / LCG-NR32), record the shortest
# generator descriptor, and compare against an entropy-coding bar (zlib-9 deflate,
# devs additionally calibrated with real zstd-19 + Cubrim-1 on a sample by a
# separate script). Emits aggregate JSON only — payload never leaves the host.
#
# Charged accounting (store-side, per matrix):
#   generator descriptor = 1 B family id + params (+2 B length field where variable);
#   entropy bar          = raw deflate stream size (zlib header/adler stripped: -6 B);
#   catalog entry + integrity hash are IDENTICAL for both schemes -> cancel out.
# Usage: python3 regen_spectrum.py <uniq.bin> <out.json> [batch]
import json, sys, time, zlib
import numpy as np

CUBE = 512
W32 = CUBE // 4
uniq_path, out_path = sys.argv[1], sys.argv[2]
BATCH = int(sys.argv[3]) if len(sys.argv) > 3 else 262144

def xs32_step(s):
    s = s ^ ((s << 13) & 0xFFFFFFFF)
    s = s ^ (s >> 17)
    s = s ^ ((s << 5) & 0xFFFFFFFF)
    return s

def xs64_step(s):
    s = s ^ ((s << 13) & 0xFFFFFFFFFFFFFFFF)
    s = s ^ (s >> 7)
    s = s ^ ((s << 17) & 0xFFFFFFFFFFFFFFFF)
    return s

def classify_batch(B):
    """B: (n,512) uint8. Returns per-row: class id, descriptor bytes."""
    n = B.shape[0]
    cls = np.full(n, -1, dtype=np.int8)
    desc = np.full(n, 10 ** 9, dtype=np.int64)

    # 0 const
    is_const = (B == B[:, 0:1]).all(axis=1)
    cls[is_const] = 0
    desc[is_const] = 2  # id + value

    # 1 arith (constant additive step, includes step=0 -> claimed by const first)
    d8 = (B[:, 1:].astype(np.int16) - B[:, :-1].astype(np.int16)) % 256
    is_arith = (d8 == d8[:, 0:1]).all(axis=1) & ~is_const
    cls[is_arith] = 1
    desc[is_arith] = 3  # id + start + step

    # 2 xor-delta constant
    x8 = B[:, 1:] ^ B[:, :-1]
    is_xd = (x8 == x8[:, 0:1]).all(axis=1) & (cls == -1)
    cls[is_xd] = 2
    desc[is_xd] = 3  # id + start + xor-const

    # 3 periodic, smallest p in 2..64 (p=1 == const)
    per_desc = np.full(n, 10 ** 9, dtype=np.int64)
    per_hit = np.zeros(n, dtype=bool)
    todo = cls == -1
    for p in range(2, 65):
        if not todo.any():
            break
        ok = (B[todo][:, p:] == B[todo][:, :-p]).all(axis=1)
        idx = np.flatnonzero(todo)[ok]
        per_hit[idx] = True
        per_desc[idx] = 2 + p  # id + p + pattern
        todo[idx] = False
    cls[per_hit] = 3
    desc[per_hit] = per_desc[per_hit]

    # 4/5/6 full-state PRNG fits (seed = first word; honest: exact stream match)
    w = B.view('<u4').reshape(n, W32).astype(np.uint64)
    rem = cls == -1
    if rem.any():
        st = w[rem, 0].copy()
        ok = np.ones(st.shape[0], dtype=bool)
        for i in range(1, W32):
            st = xs32_step(st) & 0xFFFFFFFF
            ok &= st == w[rem, i]
            if not ok.any():
                break
        idx = np.flatnonzero(rem)[ok]
        cls[idx] = 4
        desc[idx] = 6  # id + gen-id + 4B seed
    rem = cls == -1
    if rem.any():
        w64 = B.view('<u8').reshape(n, CUBE // 8)
        st = w64[rem, 0].astype(object)  # python ints for 64-bit safety
        ok = np.ones(st.shape[0], dtype=bool)
        cur = np.array([xs64_step(int(s)) for s in st], dtype=np.uint64)
        for i in range(1, CUBE // 8):
            ok &= cur == w64[rem, i]
            if not ok.any():
                break
            if i + 1 < CUBE // 8:
                cur = np.array([xs64_step(int(s)) for s in cur], dtype=np.uint64)
        idx = np.flatnonzero(rem)[ok]
        cls[idx] = 5
        desc[idx] = 10  # id + gen-id + 8B seed
    rem = cls == -1
    if rem.any():
        st = w[rem, 0].copy()
        ok = np.ones(st.shape[0], dtype=bool)
        for i in range(1, W32):
            st = (st * 1664525 + 1013904223) & 0xFFFFFFFF
            ok &= st == w[rem, i]
            if not ok.any():
                break
        idx = np.flatnonzero(rem)[ok]
        cls[idx] = 6
        desc[idx] = 6
    # 7 RLE (only if beats 512 raw; lower-bound 2 B per run — generous to REGEN)
    rem = cls == -1
    if rem.any():
        runs = 1 + (B[rem, 1:] != B[rem, :-1]).sum(axis=1)
        rle = 1 + 2 * runs.astype(np.int64)
        ok = rle < 512
        idx = np.flatnonzero(rem)[ok]
        cls[idx] = 7
        desc[idx] = rle[ok] + 2  # + length field
    # 8 none
    rem = cls == -1
    cls[rem] = 8
    desc[rem] = 512
    return cls, desc

CLS_NAMES = ['const', 'arith', 'xor_delta', 'periodic<=64', 'xorshift32',
             'xorshift64', 'lcg_nr32', 'rle', 'none']

t0 = time.time()
agg = {name: {'count': 0, 'desc_bytes': 0, 'zlib_bytes': 0,
              'desc_lt_zlib': 0, 'desc_lt_half_zlib': 0} for name in CLS_NAMES}
total = 0
zlib_time = 0.0
with open(uniq_path, 'rb') as f:
    while True:
        buf = f.read(BATCH * CUBE)
        if not buf:
            break
        m = len(buf) // CUBE
        B = np.frombuffer(buf[:m * CUBE], dtype=np.uint8).reshape(m, CUBE)
        cls, desc = classify_batch(B)
        tz = time.time()
        zs = np.empty(m, dtype=np.int64)
        for i in range(m):
            zs[i] = max(len(zlib.compress(B[i].tobytes(), 9)) - 6, 1)
        zlib_time += time.time() - tz
        zs = np.minimum(zs, 512)  # store-raw fallback cap
        for ci, name in enumerate(CLS_NAMES):
            mask = cls == ci
            if not mask.any():
                continue
            a = agg[name]
            a['count'] += int(mask.sum())
            a['desc_bytes'] += int(desc[mask].sum())
            a['zlib_bytes'] += int(zs[mask].sum())
            a['desc_lt_zlib'] += int((desc[mask] < zs[mask]).sum())
            a['desc_lt_half_zlib'] += int((desc[mask] * 2 < zs[mask]).sum())
        total += m

elapsed = time.time() - t0
res = {'probe': 'REGEN-spectrum-v1', 'unique_matrices': total,
       'classes': agg,
       'generator_fit_share_pct': round(100 * sum(agg[c]['count'] for c in CLS_NAMES[:8]) / total, 4) if total else 0,
       'regen_wins_vs_zlib9': int(sum(agg[c]['desc_lt_zlib'] for c in CLS_NAMES[:8])),
       'elapsed_s': round(elapsed, 1), 'zlib_time_s': round(zlib_time, 1),
       'classify_cpu_us_per_matrix': round(1e6 * (elapsed - zlib_time) / total, 2) if total else 0}
with open(out_path, 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps(res, indent=1))
