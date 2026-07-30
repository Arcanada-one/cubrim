#!/usr/bin/env python3
"""H-50 spike: ALP-RD (real-double bit-split) on raw IEEE-754 float64 .npy (CORPUS 2).

Non-subsumable rationale (Gotcha #11 criterion i): in a float64 the sign+exponent+high
mantissa (low entropy across a column of related magnitudes) and the low mantissa bits
(near-random) SHARE the same 8 bytes. A byte-symbol backend (zstd / Cubrim BWT+rANS)
cannot separate them. ALP-RD cuts each 64-bit value into left = bits>>R (dictionary) and
right = low R bits (bitpacked) + an exception list — a sub-byte separation the backend
structurally cannot reach.

FAITHFUL + CHARGED (Gotcha #7): per column we pick the best right-bit-width R and an
8-entry left-dictionary; total = left-index stream (charged at its order-0 entropy, what a
real rANS reaches) + right bits (R·n, incompressible) + dictionary + exception list +
per-column header (R + dict). Compared to zstd-19 AND the real cubrim binary on the raw
double bytes. Gate: alprd <= zstd19 / 1.5 (>=1.5x vs zstd-19).
"""
import sys, subprocess, os, math
import numpy as np

NPY = sys.argv[1]
BIN = sys.argv[2]
SCR = sys.argv[3]
DICT_SIZE = 8          # ALP-RD canonical: 8-entry (3-bit) left dictionary
EXC_POS_BITS = 16      # charged per-exception position cost (~varint)

a = np.load(NPY).astype("<f8")
data_bytes = a.tobytes()
n_vals = a.size
bits = a.view("<u8").reshape(a.shape)
cols = bits.T  # column-major (each feature column = related magnitudes)

def order0_bits(idx, n):
    _, c = np.unique(idx, return_counts=True)
    p = c / n
    return float((-(p * np.log2(p)).sum()) * n)

total_bits = 0.0
header_bits = 0
tot_exc = 0
for col in cols:
    col = np.ascontiguousarray(col)
    n = col.shape[0]
    best = None
    for R in range(0, 58, 2):       # right-bit-width candidates
        left = col >> np.uint64(R)
        leftw = 64 - R
        vals, counts = np.unique(left, return_counts=True)
        order = np.argsort(-counts)
        dvals = vals[order[:DICT_SIZE]]
        in_dict = np.isin(left, dvals)
        n_exc = int((~in_dict).sum())
        # left-index stream: 0..DICT_SIZE-1 in-dict, DICT_SIZE = exception marker
        idx = np.full(n, DICT_SIZE, dtype=np.int64)
        for di, dv in enumerate(dvals):
            idx[left == dv] = di
        idx_bits = order0_bits(idx, n)
        right_bits = R * n
        dict_bits = min(DICT_SIZE, len(dvals)) * leftw
        exc_bits = n_exc * (leftw + EXC_POS_BITS)
        cost = idx_bits + right_bits + dict_bits + exc_bits
        if best is None or cost < best[0]:
            best = (cost, R, n_exc)
    total_bits += best[0]
    header_bits += 8 + 16            # charged per-column: R byte + dict-len/frame
    tot_exc += best[2]

alprd_bytes = math.ceil((total_bits + header_bits) / 8)

def comp(data, tag, tool):
    if tool == "zstd":
        return len(subprocess.run(["zstd", "-19", "-c"], input=data, capture_output=True).stdout)
    if tool == "gzip":
        return len(subprocess.run(["gzip", "-9", "-c"], input=data, capture_output=True).stdout)
    p = os.path.join(SCR, f"_h50_{tag}.bin"); open(p, "wb").write(data); o = p + ".cbr"
    subprocess.run([BIN, "compress", p, o, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r = os.path.getsize(o); os.remove(p); os.remove(o); return r

raw = len(data_bytes)
z = comp(data_bytes, "z", "zstd")
g = comp(data_bytes, "g", "gzip")
c = comp(data_bytes, "c", "cubrim")
print(f"{os.path.basename(NPY)}  raw={raw}  n_vals={n_vals}  exceptions={tot_exc} ({100*tot_exc/n_vals:.2f}%)")
print(f"  zstd-19={z}  gzip-9={g}  cubrim(bwt-rans)={c}  ALP-RD(charged est)={alprd_bytes}")
print(f"  ALP-RD vs zstd-19 = {z/alprd_bytes:.3f}x   {'GO(>=1.5x)' if z/alprd_bytes>=1.5 else 'below-1.5x'}")
print(f"  ALP-RD vs cubrim  = {c/alprd_bytes:.3f}x   ALP-RD vs gzip = {g/alprd_bytes:.3f}x")
