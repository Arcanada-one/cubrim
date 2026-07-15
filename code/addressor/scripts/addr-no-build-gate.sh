#!/usr/bin/env bash
# NO-BUILD gate: the seven closed mechanisms must not appear in src/ —
# identifier-boundary grep over the WHOLE file (comments included; same
# file-level philosophy as the zstd gate: rename the comment, not the gate).
# Exception: 'dictionary' inside src/delta.rs (the trained-dict BASELINE of
# Core B is legal). The gate FAILS on an empty/missing src/ (no vacuous pass).
set -euo pipefail
SRC="${1:?usage: addr-no-build-gate.sh <src-dir>}"
[ -d "$SRC" ] && [ -n "$(find "$SRC" -name '*.rs' -print -quit)" ] || {
    echo "FAIL: src dir empty or missing — vacuous pass forbidden" >&2; exit 2; }
TERMS='fragment|signature|phi_key|phikey|generated_matrix|histogram|occupancy|size_routing'
FAIL=0
if grep -rnE --include='*.rs' "\b($TERMS)\b" "$SRC"; then FAIL=1; fi
if grep -rnE --include='*.rs' '\bdictionary\b' "$SRC" | grep -v '/delta\.rs:'; then FAIL=1; fi
if [ "$FAIL" -eq 1 ]; then echo "FAIL: NO-BUILD mechanism term present" >&2; exit 1; fi
echo "no-build gate: clean"
