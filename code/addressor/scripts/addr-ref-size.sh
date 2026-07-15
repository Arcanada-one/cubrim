#!/usr/bin/env bash
# V-AC-5: adaptive ref coding — mean bytes/ref <= 2.3 on a skewed stream
# (refs::skewed_stream_mean_under_gate) + hot-refs-cost-1-byte property.
set -euo pipefail
cd "$(dirname "$0")/.."
exec cargo test --release --lib refs -- --nocapture
