#!/usr/bin/env bash
# Pinned key corpus for catalog-scale tests: 1M unique keys + a Zipf-skewed
# reference stream (AH-08 profile parameters in the manifest).
set -euo pipefail
OUT="${1:?usage: generate_1M_keys.sh <out-dir>}"; SEED="${SEED:-20260716}"
N="${N_KEYS:-1000000}"; HOT="${HOT_SET:-64}"; HOT_SHARE="${HOT_SHARE:-0.8}"
python3 - "$OUT" "$SEED" "$N" "$HOT" "$HOT_SHARE" <<'PY'
import json, os, random, sys, hashlib
out, seed, n, hot, hs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
rng = random.Random(seed); os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "keys.bin"), "wb") as f:
    for i in range(n):
        f.write(hashlib.blake2b(b"key-%d-%d" % (seed, i), digest_size=32).digest())
with open(os.path.join(out, "ref-stream.u64"), "wb") as f:
    for i in range(200000):
        if rng.random() < hs: ord_ = 1000000 - hot + rng.randrange(hot)
        else: ord_ = rng.randrange(n)
        f.write(ord_.to_bytes(8, "little"))
json.dump({"seed": seed, "n_keys": n, "hot_set": hot, "hot_share": hs},
          open(os.path.join(out, "manifest.json"), "w"))
print("1M-keys corpus written")
PY
