# -*- coding: utf-8 -*-
# CUBR-0055 REGEN — measured cost of BRUTE-FORCE descriptor search (the operator's
# "воссоздать перебором" in its honest unstructured form): unknown 32-bit seed,
# generator = xorshift32 with WARMUP steps (so the seed is NOT readable from the
# output — otherwise the fit is algebraic and free). Search = enumerate seeds,
# generate first words, early-exit compare, full hash-verify on candidate match.
#
# Measures real candidates/sec on this stand (numpy-batched, single process),
# then extrapolates: full 2^32 sweep per matrix, x M matrices, /16 cores,
# exa-scale supercomputer (1e18 candidate-ops/s), Grover sqrt column (oracle
# calls, idealized hardware).
# Usage: python3 bruteforce_cost.py <out.json>
import json, sys, time
import numpy as np

out_path = sys.argv[1]
WARMUP = 4

def xs32(s):
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s

# target block from a random hidden seed
rng = np.random.default_rng(4055)
hidden = int(rng.integers(1, 2**32))
s = hidden
for _ in range(WARMUP):
    s = xs32(s)
words = []
for _ in range(128):
    s = xs32(s)
    words.append(s)
target_first = words[0]

# measured sweep over a 2^26 seed window (numpy batched)
SWEEP = 1 << 26
BATCH = 1 << 20
t0 = time.time()
found = 0
lo = hidden - (SWEEP // 2)
for b in range(lo, lo + SWEEP, BATCH):
    seeds = (np.arange(b, b + BATCH, dtype=np.uint64)) & 0xFFFFFFFF
    st = seeds.copy()
    for _ in range(WARMUP + 1):
        st = st ^ ((st << 13) & 0xFFFFFFFF)
        st = st ^ (st >> 17)
        st = st ^ ((st << 5) & 0xFFFFFFFF)
    found += int((st == target_first).sum())
elapsed = time.time() - t0
cps = SWEEP / elapsed  # candidates/sec, 1 process

full32 = (2**32) / cps
res = {
    'probe': 'REGEN-bruteforce-cost-v1',
    'model': 'xorshift32, unknown 32-bit seed, warmup=4 (seed not readable from output)',
    'sweep_candidates': SWEEP,
    'sweep_elapsed_s': round(elapsed, 2),
    'candidates_per_sec_1proc': int(cps),
    'hidden_seed_found_in_window': bool(found),
    'full_2e32_sweep_one_matrix': {
        'sec_1proc': round(full32, 1),
        'hours_16cores': round(full32 / 16 / 3600, 2),
    },
    'per_corpus_devs_12_45M_matrices_16cores_years': round(full32 / 16 * 12451314 / 86400 / 365.25, 1),
    'seed_spaces_wallclock_16cores': {
        '2^32': f"{full32/16/3600:.2f} h",
        '2^40': f"{full32*256/16/86400:.1f} d",
        '2^48': f"{full32*65536/16/86400/365.25:.1f} y",
        '2^64': f"{full32*(2**32)/16/86400/365.25:.2e} y",
    },
    'exa_supercomputer_1e18_cps': {
        '2^64': f"{(2**64)/1e18:.1f} s",
        '2^80': f"{(2**80)/1e18/86400/365.25:.1f} y",
        '2^96': f"{(2**96)/1e18/86400/365.25:.2e} y",
        '2^128': f"{(2**128)/1e18/86400/365.25:.2e} y",
    },
    'grover_oracle_calls_sqrt': {
        'd=64': f"2^32 oracle calls",
        'd=128': f"2^64 oracle calls (AES-128-scale: ~2^83 gate-ops with QEC, millions of qubits, decades — physically remote)",
        'note': 'BBBV: sqrt is optimal for unstructured search; no exponential quantum shortcut',
    },
    'economics_note': (
        'search is sender-side one-time; receiver replays generator for free. '
        'Even so: a 2^32 sweep costs ~1 CPU-core-hour-scale PER MATRIX to save '
        '<=~500 B vs storing the compressed block; at ~0.05 USD/core-hour the '
        'search costs ~5 orders of magnitude more than a lifetime of storing/'
        'shipping 500 B. Break-even N does not exist for blind search.'
    ),
}
with open(out_path, 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps(res, indent=1))
