#!/usr/bin/env bash
# V-AC-10: fp16 2.0 B/slot by construction + measured negative-probe fp rate
# <= 0.045 + the integrity confirmation invariant (fp_confirm tests).
set -euo pipefail
cd "$(dirname "$0")/.."
cargo test --release --lib catalog -- --nocapture
exec cargo test --release --test fp_confirm -- --nocapture
