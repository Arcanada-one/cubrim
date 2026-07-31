#!/usr/bin/env bash
# Threshold-step corpus points are constructed AGAINST the exported constant
# at test runtime (tests/threshold.rs — donor prefixes + tail tuning). This
# generator records the construction parameters for reproducibility.
set -euo pipefail
OUT="${1:?usage: generate_dup_fraction_steps.sh <out-dir>}"
mkdir -p "$OUT"
T=$(grep -oP 'pub const DUP_THRESHOLD: f64 = \K[0-9.]+' "$(dirname "$0")/../../src/router.rs")
python3 -c "
import json; t=float('$T')
json.dump({'threshold_source': 'router::DUP_THRESHOLD', 'threshold': t,
           'points': [round(t-0.05,4), round(t-0.01,4), t, round(t+0.01,4), round(t+0.05,4), round(t+0.10,4)],
           'tolerance_pp': 0.2,
           'construction': 'chunk-aligned donor prefix + tail-length tuning (tests/threshold.rs)'},
          open('$OUT/manifest.json','w'))
print('dup-fraction-steps manifest written (points built at test runtime)')"
