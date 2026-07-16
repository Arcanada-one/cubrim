# -*- coding: utf-8 -*-
# CUBR-0055 REGEN — operator sub-hypothesis: lexicographic-index order bonus.
# Sort unique 512-B matrices as 4096-bit big-endian integers (lexicographic byte
# order == numeric order) and measure:
#   (a) delta-coding of the sorted CONTENTS list: sum of gap bit-lengths (+ Elias-delta
#       overhead) vs raw M*4096 vs the uniform-random bar M*(4096-log2 M);
#   (b) neighbor clustering: common-prefix-bit histogram, Hamming distance to the
#       lexicographic neighbor (share with < k differing bits);
#   (c) real-compressor front-coding check: zlib-9 of sorted vs hash-shuffled
#       concatenation (sampled window).
# Aggregate JSON only; payload stays on the host.
# Usage: python3 lex_order.py <uniq.bin> <out.json>
import json, math, sys, time, zlib
import numpy as np

CUBE = 512
uniq_path, out_path = sys.argv[1], sys.argv[2]
t0 = time.time()

raw = np.fromfile(uniq_path, dtype=np.uint8)
M = raw.size // CUBE
A = raw.reshape(M, CUBE)
del raw

# lexicographic sort via void-dtype memcmp
v = A.view(f'V{CUBE}').ravel()
order = np.argsort(v, kind='stable')
A = A[order]
del v, order
sort_s = round(time.time() - t0, 1)

# neighbor stats, chunked
prefix_hist = np.zeros(4097, dtype=np.int64)   # common prefix bits
gap_bits_sum = 0
gap_bits_hist = np.zeros(4097, dtype=np.int64)
hamming_lt = {k: 0 for k in (8, 16, 32, 64, 128, 256)}
hamming_sum = 0
elias_delta_bits = 0
CH = 200000
for s in range(0, M - 1, CH):
    e = min(s + CH, M - 1)
    X = A[s:e] ^ A[s + 1:e + 1]
    nz = X != 0
    first = nz.argmax(axis=1)                      # first differing byte (MSB side)
    lead = X[np.arange(e - s), first]
    lead_bits = np.floor(np.log2(lead)).astype(np.int64) + 1   # 1..8
    prefix_bits = first * 8 + (8 - lead_bits)
    np.add.at(prefix_hist, prefix_bits, 1)
    # gap bit-length: gap = B-A; leading differing byte dominates; exact within +-1,
    # validated below on an exact-bigint sample.
    gb = (CUBE - 1 - first) * 8 + lead_bits
    gap_bits_sum += int(gb.sum())
    np.add.at(gap_bits_hist, gb, 1)
    elias_delta_bits += int((gb + 2 * np.floor(np.log2(gb + 1)) + 1).astype(np.int64).sum())
    hm = np.bitwise_count(X).sum(axis=1).astype(np.int64)
    hamming_sum += int(hm.sum())
    for k in hamming_lt:
        hamming_lt[k] += int((hm < k).sum())

# exact big-int validation sample for the gap approximation
rng = np.random.default_rng(55)
idx = rng.choice(M - 1, size=min(100000, M - 1), replace=False)
err_max = 0
for i in idx[:100000]:
    a = int.from_bytes(A[i].tobytes(), 'big')
    b = int.from_bytes(A[i + 1].tobytes(), 'big')
    gexact = (b - a).bit_length()
    x = (A[i] ^ A[i + 1])
    nzp = np.flatnonzero(x)
    f = nzp[0]
    lb = int(x[f]).bit_length()
    gapprox = (CUBE - 1 - int(f)) * 8 + lb
    err_max = max(err_max, abs(int(gexact) - int(gapprox)))

# real-compressor front-coding: first 64 MiB worth of sorted vs shuffled
NS = min(M, 131072)
sel = rng.choice(M, size=NS, replace=False)
sel.sort()
sorted_blob = A[sel].tobytes()                    # sorted subsample (keeps order)
perm = rng.permutation(NS)
shuf_blob = A[sel][perm].tobytes()
z_sorted = len(zlib.compress(sorted_blob, 9))
z_shuf = len(zlib.compress(shuf_blob, 9))

log2M = math.log2(M)
res = {
    'probe': 'REGEN-lex-order-v1', 'unique_matrices': M,
    'sort_s': sort_s,
    'log2_M_bits': round(log2M, 2),
    'raw_list_bits_per_matrix': 4096,
    'uniform_bar_bits_per_matrix': round(4096 - log2M, 2),
    'measured_gap_bits_per_matrix': round(gap_bits_sum / (M - 1), 2),
    'measured_elias_delta_bits_per_matrix': round(elias_delta_bits / (M - 1), 2),
    'order_bonus_vs_raw_pct': round(100 * (1 - (gap_bits_sum / (M - 1)) / 4096), 3),
    'extra_bonus_vs_uniform_bits': round((4096 - log2M) - gap_bits_sum / (M - 1), 2),
    'gap_approx_err_max_bits_on_sample': err_max,
    'prefix_bits_quantiles': {q: int(np.searchsorted(prefix_hist.cumsum(), (M - 1) * q / 100.0))
                              for q in (50, 90, 99, 99.9)},
    'prefix_ge_64bits_count': int(prefix_hist[64:].sum()),
    'prefix_ge_128bits_count': int(prefix_hist[128:].sum()),
    'hamming_to_lex_neighbor_mean_bits': round(hamming_sum / (M - 1), 1),
    'hamming_lt_k_counts': {str(k): v for k, v in hamming_lt.items()},
    'zlib9_front_coding_sample': {'n_blocks': NS, 'sorted_bytes': z_sorted,
                                  'shuffled_bytes': z_shuf,
                                  'sorted_gain_pct': round(100 * (1 - z_sorted / z_shuf), 3)},
    'elapsed_s': round(time.time() - t0, 1),
}
with open(out_path, 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps(res, indent=1))
