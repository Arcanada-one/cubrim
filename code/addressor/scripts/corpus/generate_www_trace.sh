#!/usr/bin/env bash
# Lookup trace for the bloom-effect measurement. HONESTY: this is a
# SYNTHETIC-PROFILE trace with a pinned negative_fraction (no AH-10 raw
# stream is bundled with the repo); QA reports must call it synthetic.
set -euo pipefail
OUT="${1:?usage: generate_www_trace.sh <out-dir>}"; SEED="${SEED:-20260716}"
NEG="${NEGATIVE_FRACTION:-0.80}"
python3 - "$OUT" "$SEED" "$NEG" <<'PY'
import json, os, random, sys, hashlib
out, seed, neg = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
rng = random.Random(seed); os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "trace.bin"), "wb") as f:
    for i in range(50000):
        if rng.random() < neg: key = b"absent-%d" % i
        else: key = b"hub-%d" % rng.randrange(50000)
        f.write(hashlib.blake2b(key, digest_size=32).digest())
json.dump({"seed": seed, "negative_fraction": neg, "provenance": "synthetic-profile",
           "note": "reduction is bounded by negative_fraction; report as synthetic"},
          open(os.path.join(out, "manifest.json"), "w"))
print("www-lookup-trace (synthetic profile) written")
PY
