#!/usr/bin/env bash
# V-AC-7: per-file regression property (+ --charged corpus aggregate).
set -euo pipefail
CORPUS="${1:?usage: addr-regression-proof.sh <corpus-dir> [--charged]}"
shift || true
BIN="${ADDR_BIN:-$(dirname "$0")/../target/release/cubrim-addr}"
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
"$BIN" --root "$ROOT" bench-regression "$CORPUS" "$@"
