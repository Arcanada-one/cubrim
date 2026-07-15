#!/usr/bin/env bash
# V-AC-1: byte-exact round-trip of every corpus file through the CLI.
set -euo pipefail
CORPUS="${1:?usage: addr-roundtrip.sh <corpus-dir>}"
BIN="${ADDR_BIN:-$(dirname "$0")/../target/release/cubrim-addr}"
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
FAIL=0; N=0
while IFS= read -r -d '' F; do
    ORD=$("$BIN" --root "$ROOT" store "$F" | awk '{print $1}')
    "$BIN" --root "$ROOT" retrieve "$ORD" -o "$ROOT/.out"
    cmp -s "$F" "$ROOT/.out" || { echo "DIFF: $F" >&2; FAIL=1; }
    N=$((N+1))
done < <(find "$CORPUS" -type f ! -name manifest.json -print0)
echo "roundtrip: $N files, fail=$FAIL"
exit $FAIL
