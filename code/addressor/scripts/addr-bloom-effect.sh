#!/usr/bin/env bash
# V-AC-11: bloom lookup reduction >= 0.70 with fp <= 0.05 on the pinned
# negative-fraction stream (bloom_effect integration test).
set -euo pipefail
# args accepted-and-ignored: the property is a cargo test on pinned
# fixtures/corpora built into the crate; --corpus/--check are consumed by
# the test itself, not this wrapper.
cd "$(dirname "$0")/.."
exec cargo test --release --test bloom_effect -- --nocapture
