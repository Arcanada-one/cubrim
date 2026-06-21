#!/usr/bin/env bash
# gate-cargo-test.sh — Gate 2: run cargo test on the candidate branch (must be green).
#
# Runs `cargo test` in the cubrim-rs workspace. The candidate branch is expected
# to already be checked out by the orchestrator before calling this gate.
#
# Exit 0   = all tests pass
# Exit 1   = test failure
# Exit 2   = usage / toolchain error
#
# Called by run-merge-rail.sh; runs from the REPO ROOT.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
RUST_DIR="$REPO_ROOT/code/cubrim-rs"

die() { echo "gate-cargo-test: ERROR: $*" >&2; exit 2; }

[ -d "$RUST_DIR" ] || die "Rust workspace not found: $RUST_DIR"
command -v cargo >/dev/null 2>&1 || die "cargo not on PATH"

echo "gate-cargo-test: running cargo test in $RUST_DIR"
cd "$RUST_DIR"

# Run tests; capture exit code without set -e interfering
set +e
cargo test --quiet 2>&1
TEST_RC=$?
set -e

if [ "$TEST_RC" -ne 0 ]; then
    echo "gate-cargo-test: FAIL cargo test exited $TEST_RC" >&2
    exit 1
fi

echo "gate-cargo-test: PASS — cargo test green"
exit 0
