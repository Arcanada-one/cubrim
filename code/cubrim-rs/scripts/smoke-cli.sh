#!/usr/bin/env bash
set -euo pipefail

BIN="${1:-target/release/cubrim}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/input/nested"
printf 'hello cubrim\n' > "$TMP/input/root.txt"
printf 'nested payload\n' > "$TMP/input/nested/child.txt"

"$BIN" compress "$TMP/input/root.txt" "$TMP/root.cub" -q
"$BIN" x "$TMP/root.cub" "$TMP/root.out" -q
cmp "$TMP/input/root.txt" "$TMP/root.out"

"$BIN" a "$TMP/archive.cbr" "$TMP/input" --force -q
"$BIN" l "$TMP/archive.cbr" >/dev/null
"$BIN" t "$TMP/archive.cbr" -q
"$BIN" x "$TMP/archive.cbr" -o "$TMP/out" -q
cmp "$TMP/input/root.txt" "$TMP/out/input/root.txt"
cmp "$TMP/input/nested/child.txt" "$TMP/out/input/nested/child.txt"

"$BIN" a "$TMP/secret.cbr" "$TMP/input" --password correct --force -q
if "$BIN" t "$TMP/secret.cbr" --password wrong -q 2>/dev/null; then
  echo "wrong password unexpectedly succeeded" >&2
  exit 1
fi
"$BIN" t "$TMP/secret.cbr" --password correct -q

echo "CLI_SMOKE_OK"
