#!/usr/bin/env bash
# V-AC-6 static half: files containing 'zstd' must be a subset of
# {delta.rs, lite.rs} (file-level check — comments/renames cannot dodge it).
set -euo pipefail
SRC="${1:?usage: addr-zstd-gate.sh <src-dir>}"
BAD=$(grep -rl --include='*.rs' 'zstd' "$SRC" | grep -vE '/(delta|lite)\.rs$' || true)
if [ -n "$BAD" ]; then echo "FAIL: zstd outside delta.rs/lite.rs:"; echo "$BAD"; exit 1; fi
echo "zstd gate: clean"
