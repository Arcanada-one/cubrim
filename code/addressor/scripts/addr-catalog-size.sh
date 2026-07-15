#!/usr/bin/env bash
# V-AC-10: fp16 2.0 B/slot + fp rate <= 0.045 on a LOADED table (>=10^5
# negative probes) + the D-REQ-09 confirmation invariant.
set -euo pipefail
# args accepted-and-ignored: measurement regime is built into the tests.
cd "$(dirname "$0")/.."
cargo test --release --test ref_and_catalog_scale fp16 -- --nocapture
exec cargo test --release --test fp_confirm -- --nocapture
