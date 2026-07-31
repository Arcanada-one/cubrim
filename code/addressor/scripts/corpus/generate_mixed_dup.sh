#!/usr/bin/env bash
# Pinned mixed-dup corpus: r1_fraction of blocks are unique-by-construction
# (seen once), the rest repeat across sibling files (r>=2). The V-AC-3
# assert derives its bound from the manifest's r1_fraction — not hardcoded.
set -euo pipefail
OUT="${1:?usage: generate_mixed_dup.sh <out-dir>}"
SEED="${SEED:-20260716}"
R1_FRACTION="${R1_FRACTION:-0.90}"
python3 - "$OUT" "$SEED" "$R1_FRACTION" <<'PY'
import json, os, random, sys
out, seed, r1 = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
rng = random.Random(seed)
os.makedirs(out, exist_ok=True)
hot_files, unique_files = 10, int(10 / (1 - r1) * r1 / 10)  # ≈90 at r1=0.9
hot_body = bytes(rng.getrandbits(8) for _ in range(80000))
for i in range(hot_files):
    open(os.path.join(out, f"hot{i:03d}.bin"), "wb").write(hot_body + b"-h%d" % i)
for i in range(unique_files):
    body = bytes(rng.getrandbits(8) for _ in range(80000))
    open(os.path.join(out, f"uniq{i:03d}.bin"), "wb").write(body)
json.dump({"seed": seed, "r1_fraction": r1, "hot_files": hot_files,
           "unique_files": unique_files},
          open(os.path.join(out, "manifest.json"), "w"))
print(f"mixed-dup: {hot_files} hot + {unique_files} unique")
PY
