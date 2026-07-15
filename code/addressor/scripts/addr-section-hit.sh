#!/usr/bin/env bash
# V-AC-4: section-first lookup mechanism (own-section hits >= 80% on the
# sectioned fixture; real-fleet percentages re-measured at bench stage).
set -euo pipefail
cd "$(dirname "$0")/.."
exec cargo test --release --test section_hit -- --nocapture
