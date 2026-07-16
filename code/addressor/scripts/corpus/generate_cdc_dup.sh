#!/usr/bin/env bash
# Pinned cdc-dup pair: two files sharing one region at DIFFERENT byte shifts.
set -euo pipefail
OUT="${1:?usage: generate_cdc_dup.sh <out-dir>}"; SEED="${SEED:-20260716}"
python3 - "$OUT" "$SEED" <<'PY'
import json, os, random, sys, hashlib
out, seed = sys.argv[1], int(sys.argv[2]); rng = random.Random(seed)
os.makedirs(out, exist_ok=True)
shared = bytes(rng.getrandbits(8) for _ in range(120000))
a = bytes(rng.getrandbits(8) for _ in range(5000)) + shared
b = bytes(rng.getrandbits(8) for _ in range(9137)) + shared
open(os.path.join(out, "a.bin"), "wb").write(a)
open(os.path.join(out, "b.bin"), "wb").write(b)
json.dump({"seed": seed, "shared_bytes": len(shared),
           "a_sha256": hashlib.sha256(a).hexdigest(),
           "b_sha256": hashlib.sha256(b).hexdigest()},
          open(os.path.join(out, "manifest.json"), "w"))
print("cdc-dup pair written")
PY
