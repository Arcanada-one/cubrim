#!/usr/bin/env bash
# V-AC-2: shared shifted chunks stored exactly once (exact blob accounting).
set -euo pipefail
# args accepted-and-ignored: the property is a cargo test on pinned
# fixtures/corpora built into the crate; --corpus/--check are consumed by
# the test itself, not this wrapper.
cd "$(dirname "$0")/.."
exec cargo test --release --test cdc_dedup -- --nocapture
