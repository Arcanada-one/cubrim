#!/usr/bin/env bash
# V-AC-5: adaptive (delta/zigzag) ref coding <= 2.3 B/ref on the REAL store
# ref stream at catalog scale (not a hand-picked synthetic distribution).
set -euo pipefail
# args accepted-and-ignored: measurement regime is built into the test.
cd "$(dirname "$0")/.."
exec cargo test --release --test ref_and_catalog_scale real_ref_stream -- --nocapture
