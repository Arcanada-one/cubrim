#!/usr/bin/env bash
# V-AC-11: bloom lookup reduction >= 0.70 with fp <= 0.05 on the pinned
# negative-fraction stream (bloom_effect integration test).
set -euo pipefail
cd "$(dirname "$0")/.."
exec cargo test --release --test bloom_effect -- --nocapture
