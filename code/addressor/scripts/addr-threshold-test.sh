#!/usr/bin/env bash
# V-AC-8: threshold step at the exported DUP_THRESHOLD constant.
# The property is a cargo integration test (points constructed relative to
# the constant, ±1pp precision via tail-length tuning).
set -euo pipefail
cd "$(dirname "$0")/.."
exec cargo test --release --test threshold -- --nocapture
