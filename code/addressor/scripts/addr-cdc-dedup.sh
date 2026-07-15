#!/usr/bin/env bash
# V-AC-2: shared shifted chunks stored exactly once (exact blob accounting).
set -euo pipefail
cd "$(dirname "$0")/.."
exec cargo test --release --test cdc_dedup -- --nocapture
