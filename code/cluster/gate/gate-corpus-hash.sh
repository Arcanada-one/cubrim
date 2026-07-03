#!/usr/bin/env bash
# gate-corpus-hash.sh — Gate 1: assert corpus manifest and per-file hashes unchanged.
#
# Reads documentation/ephemeral/research/corpus/manifest.json (frozen at cluster init),
# recomputes each corpus file's sha256, and asserts the manifest-level hash
# matches the frozen baseline in gate/corpus-baseline.sha256.
#
# Exit 0   = corpus clean (gate passes)
# Exit 1   = hash mismatch (gate fails — caller discards candidate branch)
# Exit 2   = usage error or missing file
#
# Called by run-merge-rail.sh; runs from the REPO ROOT.
# The gate directory is pinned out-of-tree: the worker cannot edit this file.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"

MANIFEST="$REPO_ROOT/documentation/ephemeral/research/corpus/manifest.json"
BASELINE="$GATE_DIR/corpus-baseline.sha256"

die() { echo "gate-corpus-hash: ERROR: $*" >&2; exit 2; }

# ── pre-flight ────────────────────────────────────────────────────────────────
[ -f "$MANIFEST" ] || die "manifest not found: $MANIFEST"
[ -f "$BASELINE" ] || die "baseline not found: $BASELINE"

command -v python3 >/dev/null 2>&1 || die "python3 required"
command -v jq      >/dev/null 2>&1 || die "jq required"

# ── 1. Verify manifest-level sha256 vs frozen baseline ───────────────────────
FROZEN_HASH="$(awk '{print $1}' "$BASELINE")"
ACTUAL_HASH="$(python3 -c "
import hashlib, sys
data = open(sys.argv[1], 'rb').read()
print(hashlib.sha256(data).hexdigest())
" "$MANIFEST")"

if [ "$ACTUAL_HASH" != "$FROZEN_HASH" ]; then
    echo "gate-corpus-hash: FAIL manifest hash mismatch" >&2
    echo "  frozen:  $FROZEN_HASH" >&2
    echo "  actual:  $ACTUAL_HASH" >&2
    exit 1
fi
echo "gate-corpus-hash: manifest hash OK ($FROZEN_HASH)"

# ── 2. Verify each corpus file sha256 against manifest entries ───────────────
FAIL=0
while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    expected="$(echo "$entry" | jq -r '.sha256')"
    path="$(echo "$entry" | jq -r '.path')"

    # path in manifest is absolute; make portable across machines by resolving
    # relative to corpus dir when the absolute path doesn't exist
    if [ ! -f "$path" ]; then
        rel_path="$REPO_ROOT/documentation/ephemeral/research/corpus/$(basename "$path")"
        if [ ! -f "$rel_path" ]; then
            echo "gate-corpus-hash: FAIL corpus file missing: $path" >&2
            FAIL=1
            continue
        fi
        path="$rel_path"
    fi

    actual="$(python3 -c "
import hashlib, sys
data = open(sys.argv[1], 'rb').read()
print(hashlib.sha256(data).hexdigest())
" "$path")"

    if [ "$actual" != "$expected" ]; then
        echo "gate-corpus-hash: FAIL $name hash mismatch" >&2
        echo "  expected: $expected" >&2
        echo "  actual:   $actual" >&2
        FAIL=1
    else
        echo "gate-corpus-hash: OK   $name"
    fi
done < <(jq -c '.[]' "$MANIFEST")

[ "$FAIL" -eq 0 ] || exit 1
echo "gate-corpus-hash: PASS — all corpus files intact"
exit 0
