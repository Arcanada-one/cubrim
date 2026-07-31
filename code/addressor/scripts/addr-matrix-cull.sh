#!/usr/bin/env bash
# V-AC-3: r>=2 curation — entries_r1 == 0 and curated/naive ratio bounded by
# the corpus manifest's r1_fraction (assert derived, not hardcoded).
set -euo pipefail
CORPUS="${1:?usage: addr-matrix-cull.sh <mixed-dup-corpus-dir>}"
BIN="${ADDR_BIN:-$(dirname "$0")/../target/release/cubrim-addr}"
ROOT=$(mktemp -d); trap 'rm -rf "$ROOT"' EXIT
while IFS= read -r -d '' F; do "$BIN" --root "$ROOT" store "$F" >/dev/null; done \
    < <(find "$CORPUS" -type f ! -name manifest.json -print0)
STATS=$("$BIN" --root "$ROOT" stats)
echo "$STATS"
R1=$(echo "$STATS" | grep -oP 'entries_r1=\K[0-9]+')
MEMBERS=$(echo "$STATS" | grep -oP 'matrix_members=\K[0-9]+')
NAIVE=$(echo "$STATS" | grep -oP 'seen_distinct=\K[0-9]+')
R1F=$(python3 -c "import json;print(json.load(open('$CORPUS/manifest.json'))['r1_fraction'])")
python3 - "$R1" "$MEMBERS" "$NAIVE" "$R1F" <<'PY'
import sys
r1, members, naive, r1f = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
assert r1 == 0, f"entries_r1={r1} != 0"
ratio = members / max(naive, 1)
bound = (1 - r1f) + 0.02
print(f"curation ratio={ratio:.4f} bound={bound:.4f} (manifest r1_fraction={r1f})")
assert ratio <= bound, f"ratio {ratio:.4f} > bound {bound:.4f}"
print("matrix-cull: PASS")
PY
