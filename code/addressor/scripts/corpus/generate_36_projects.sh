#!/usr/bin/env bash
# Pinned 36-project sectioned corpus: intra_project_dup share of each
# project's files are near-copies of its own donor; cross_project_dup share
# reuse a global donor. Parameters land in manifest.json (V-AC-4 derives
# its expectations from them).
set -euo pipefail
OUT="${1:?usage: generate_36_projects.sh <out-dir>}"; SEED="${SEED:-20260716}"
INTRA="${INTRA_PROJECT_DUP:-0.35}"; CROSS="${CROSS_PROJECT_DUP:-0.15}"
python3 - "$OUT" "$SEED" "$INTRA" "$CROSS" <<'PY'
import json, os, random, sys
out, seed, intra, cross = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
rng = random.Random(seed); os.makedirs(out, exist_ok=True)
global_donor = bytes(rng.getrandbits(8) for _ in range(60000))
for p in range(36):
    d = os.path.join(out, f"project{p:02d}"); os.makedirs(d, exist_ok=True)
    donor = bytes(rng.getrandbits(8) for _ in range(60000))
    for i in range(6):
        r = rng.random()
        if r < cross: body = global_donor + b"-g%d-%d" % (p, i)
        elif r < cross + intra: body = donor + b"-p%d-%d" % (p, i)
        else: body = bytes(rng.getrandbits(8) for _ in range(60000))
        open(os.path.join(d, f"f{i}.bin"), "wb").write(body)
json.dump({"seed": seed, "intra_project_dup": intra, "cross_project_dup": cross,
           "projects": 36, "files_per_project": 6},
          open(os.path.join(out, "manifest.json"), "w"))
print("36-projects corpus written")
PY
