#!/usr/bin/env bash
# V-AC-1: byte-exact round-trip of every corpus file through the CLI.
# Accepts either a positional dir or `--corpus <dir> --check`.
set -euo pipefail
CORPUS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --corpus) CORPUS="$2"; shift 2;;
        --check) shift;;
        *) CORPUS="${CORPUS:-$1}"; shift;;
    esac
done
[ -n "$CORPUS" ] && [ -d "$CORPUS" ] || { echo "usage: addr-roundtrip.sh [--corpus] <dir> [--check]" >&2; exit 2; }
BIN="${ADDR_BIN:-$(dirname "$0")/../target/release/cubrim-addr}"
ROOT=$(mktemp -d); trap 'rm -rf "$ROOT"' EXIT
FAIL=0; N=0
while IFS= read -r -d '' F; do
    ORD=$("$BIN" --root "$ROOT" store "$F" | awk '{print $1}')
    "$BIN" --root "$ROOT" retrieve "$ORD" -o "$ROOT/.out"
    cmp -s "$F" "$ROOT/.out" || { echo "DIFF: $F" >&2; FAIL=1; }
    N=$((N+1))
done < <(find "$CORPUS" -type f ! -name 'manifest.json' -print0)
[ "$N" -gt 0 ] || { echo "no files scanned — vacuous pass forbidden" >&2; exit 2; }
echo "roundtrip: $N files, fail=$FAIL"
exit $FAIL
