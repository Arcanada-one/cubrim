#!/usr/bin/env bash
# V-AC-8: threshold step at the exported DUP_THRESHOLD constant.
# The property is a cargo integration test (points constructed relative to
# the constant, ±1pp precision via tail-length tuning).
set -euo pipefail
# args accepted-and-ignored: the property is a cargo test on pinned
# fixtures/corpora built into the crate; --corpus/--check are consumed by
# the test itself, not this wrapper.
cd "$(dirname "$0")/.."
exec cargo test --release --test threshold -- --nocapture
