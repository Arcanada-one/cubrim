#!/usr/bin/env bash
# V-AC-4: section-first lookup mechanism (own-section hits >= 80% on the
# sectioned fixture; real-fleet percentages re-measured at bench stage).
set -euo pipefail
# args accepted-and-ignored: the property is a cargo test on pinned
# fixtures/corpora built into the crate; --corpus/--check are consumed by
# the test itself, not this wrapper.
cd "$(dirname "$0")/.."
exec cargo test --release --test section_hit -- --nocapture
