#!/usr/bin/env bash
# gate-roundtrip.sh — Gate 3: byte-exact round-trip on every corpus file.
#
# For each file in the frozen corpus: decode(encode(f)) == f byte-exact.
# Uses the cubrim binary from the candidate branch (must already be built).
#
# Exit 0   = all files round-trip correctly
# Exit 1   = any file fails round-trip
# Exit 2   = binary not found / corpus missing
#
# Called by run-merge-rail.sh; runs from the REPO ROOT.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
RUST_DIR="$REPO_ROOT/code/cubrim-rs"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
CUBRIM_BIN="$RUST_DIR/target/release/cubrim"

die() { echo "gate-roundtrip: ERROR: $*" >&2; exit 2; }

[ -f "$MANIFEST" ] || die "corpus manifest not found: $MANIFEST"
command -v python3 >/dev/null 2>&1 || die "python3 required"
command -v jq >/dev/null 2>&1 || die "jq required"

# ── build the binary if missing (candidate branch must be checked out) ────────
if [ ! -f "$CUBRIM_BIN" ]; then
    echo "gate-roundtrip: building cubrim binary..."
    cd "$RUST_DIR"
    cargo build --release --quiet
    cd "$REPO_ROOT"
fi

[ -f "$CUBRIM_BIN" ] || die "binary still missing after build: $CUBRIM_BIN"
echo "gate-roundtrip: using binary $CUBRIM_BIN"

# ── round-trip each corpus file ───────────────────────────────────────────────
FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    path="$(echo "$entry" | jq -r '.path')"

    # Resolve path portably
    if [ ! -f "$path" ]; then
        path="$REPO_ROOT/docs/ephemeral/research/corpus/$(basename "$path")"
    fi

    if [ ! -f "$path" ]; then
        echo "gate-roundtrip: FAIL $name — corpus file not found: $path" >&2
        FAIL=1
        continue
    fi

    compressed="$TMPDIR/${name}.cubrim"
    decompressed="$TMPDIR/${name}.dec"

    # Compress
    set +e
    "$CUBRIM_BIN" compress "$path" "$compressed" 2>/dev/null
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
        echo "gate-roundtrip: FAIL $name — compress exited $rc" >&2
        FAIL=1
        continue
    fi

    # Decompress
    set +e
    "$CUBRIM_BIN" decompress "$compressed" "$decompressed" 2>/dev/null
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
        echo "gate-roundtrip: FAIL $name — decompress exited $rc" >&2
        FAIL=1
        continue
    fi

    # Byte-exact comparison
    if ! python3 -c "
import sys, hashlib
a = open(sys.argv[1], 'rb').read()
b = open(sys.argv[2], 'rb').read()
sys.exit(0 if a == b else 1)
" "$path" "$decompressed"; then
        echo "gate-roundtrip: FAIL $name — round-trip NOT byte-exact" >&2
        FAIL=1
    else
        echo "gate-roundtrip: OK   $name"
    fi
done < <(jq -c '.[]' "$MANIFEST")

[ "$FAIL" -eq 0 ] || exit 1
echo "gate-roundtrip: PASS — all corpus files round-trip byte-exact"
exit 0
