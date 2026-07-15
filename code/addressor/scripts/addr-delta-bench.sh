#!/usr/bin/env bash
# V-AC-9: Core B delta vs the STRONGEST allowed baseline.
# Baselines (all three, min ratio wins — NEVER zstd-19):
#   B1 = zstd level 22, window_log 27, LDM      (--ultra -22 equivalent)
#   B2 = B1 + trained dictionary 110 KiB        (the exact AH-15 bar form)
#   B3 = pure Cubrim-1 container (cubrim-addr pure-size)
# Gate: strongest_baseline_ratio / delta_ratio >= 4.2. code_sha recorded.
set -euo pipefail
PAIRS="${1:?usage: addr-delta-bench.sh <pairs-dir> [--check]}"
BIN="${ADDR_BIN:-$(dirname "$0")/../target/release/cubrim-addr}"
GATE="${GATE:-4.2}"
git -C "$(dirname "$0")/.." rev-parse HEAD > "$(dirname "$0")/../COMMIT_SHA" 2>/dev/null || true

DELTA_OUT=$("$BIN" bench-delta "$PAIRS")
echo "$DELTA_OUT"
DELTA_BYTES=$(echo "$DELTA_OUT" | grep -oP 'delta_bytes=\K[0-9]+')
NEW_BYTES=$(echo "$DELTA_OUT" | grep -oP 'new_bytes=\K[0-9]+')

BASE_OUT=$(python3 - "$PAIRS" "$BIN" <<'PY'
import os, subprocess, sys
import zstandard as zstd
pairs_dir, bin_path = sys.argv[1], sys.argv[2]
params = zstd.ZstdCompressionParameters.from_level(22, window_log=27, enable_ldm=True)
c22 = zstd.ZstdCompressor(compression_params=params)
dirs = sorted(d for d in os.listdir(pairs_dir) if os.path.isdir(os.path.join(pairs_dir, d)))
olds = [open(os.path.join(pairs_dir, d, "old"), "rb").read() for d in dirs]
train = [o for o in olds[: len(olds) // 2] if len(o) >= 8]
dic = None
try:
    dic = zstd.train_dictionary(110 * 1024, train, level=22) if len(train) >= 8 else None
except Exception:
    dic = None
c22d = zstd.ZstdCompressor(compression_params=params, dict_data=dic) if dic else None
b1 = b2 = b3 = 0
for d in dirs:
    new = open(os.path.join(pairs_dir, d, "new"), "rb").read()
    b1 += len(c22.compress(new))
    b2 += len(c22d.compress(new)) if c22d else len(c22.compress(new))
    b3 += int(subprocess.run([bin_path, "pure-size", os.path.join(pairs_dir, d, "new")],
                             capture_output=True, text=True).stdout.strip())
print(f"b1_ultra22={b1} b2_ultra22_dict={b2} b3_cubrim={b3}")
print(f"strongest={min(b1, b2, b3)}")
PY
)
echo "$BASE_OUT"
STRONGEST=$(echo "$BASE_OUT" | grep -oP 'strongest=\K[0-9]+')
FACTOR=$(python3 -c "print(f'{$STRONGEST / $DELTA_BYTES:.4f}')")
echo "factor_vs_strongest_baseline=${FACTOR} gate=${GATE}"
python3 -c "import sys; sys.exit(0 if $FACTOR >= $GATE else 1)" \
  && echo "DELTA GATE: PASS" || { echo "DELTA GATE: FAIL" >&2; exit 1; }
