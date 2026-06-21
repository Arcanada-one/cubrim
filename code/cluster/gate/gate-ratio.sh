#!/usr/bin/env bash
# gate-ratio.sh — Gate 4: aggregate ratio strictly improves vs main leaderboard baseline.
#
# Reads current_best.aggregate from docs/leaderboard/cubrim-leaderboard.json
# (always from main branch state, never from the candidate branch).
# Runs run_bench.py on the candidate and compares aggregate ratios.
#
# Exit 0   = strict improvement (gate passes)
# Exit 1   = no improvement or regression (gate fails)
# Exit 2   = setup error
#
# Called by run-merge-rail.sh; runs from the REPO ROOT.
# Emits: CANDIDATE_AGGREGATE env var to stdout for downstream gates.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
BENCH_PY="$REPO_ROOT/code/bench/run_bench.py"

# Optional: caller may pass a pre-computed bench JSON to avoid re-running the bench
# Usage: gate-ratio.sh [--bench-json <path>]
BENCH_JSON=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bench-json) BENCH_JSON="$2"; shift 2;;
        *) shift;;
    esac
done

die() { echo "gate-ratio: ERROR: $*" >&2; exit 2; }

[ -f "$BENCH_PY" ] || die "bench harness not found: $BENCH_PY"
command -v python3 >/dev/null 2>&1 || die "python3 required"
command -v jq >/dev/null 2>&1 || die "jq required"
command -v git >/dev/null 2>&1 || die "git required"

# ── read baseline from main branch via git-object store (tamper-resistant) ───
# Baseline source priority (highest to lowest):
#   1. git show main:docs/leaderboard/cubrim-leaderboard.json  — resolves from
#      the main branch ref in the git object store; the candidate branch's
#      working-tree copy is never consulted, so a worker cannot lower its own bar
#      by editing the leaderboard in its branch.
#   2. Pinned fallback: $GATE_DIR/pinned-leaderboard-baseline.json  — used only
#      during bootstrap (before the leaderboard file is committed to main).
#      This file lives in the pinned gate dir alongside the gate scripts and
#      cannot be edited by a candidate branch.
LEADERBOARD_GIT_PATH="docs/leaderboard/cubrim-leaderboard.json"
PINNED_BASELINE="$GATE_DIR/pinned-leaderboard-baseline.json"
MAIN_LEADERBOARD_JSON="$(git -C "$REPO_ROOT" show "main:${LEADERBOARD_GIT_PATH}" 2>/dev/null || true)"

if [ -z "$MAIN_LEADERBOARD_JSON" ]; then
    # Leaderboard not yet committed to main — use pinned bootstrap baseline
    [ -f "$PINNED_BASELINE" ] || die "leaderboard not in main branch and no pinned baseline found at $PINNED_BASELINE"
    echo "gate-ratio: leaderboard not in main branch — using pinned baseline (bootstrap mode)"
    MAIN_LEADERBOARD_JSON="$(cat "$PINNED_BASELINE")"
fi

BASELINE_AGG="$(echo "$MAIN_LEADERBOARD_JSON" | jq -r '.current_best.aggregate')"
BASELINE_SCHEME="$(echo "$MAIN_LEADERBOARD_JSON" | jq -r '.current_best.scheme // "unknown"')"

if [ "$BASELINE_AGG" = "null" ] || [ -z "$BASELINE_AGG" ]; then
    die "leaderboard missing current_best.aggregate"
fi

echo "gate-ratio: baseline = $BASELINE_SCHEME @ $BASELINE_AGG"

# ── run bench (or use pre-computed result) ────────────────────────────────────
if [ -n "$BENCH_JSON" ] && [ -f "$BENCH_JSON" ]; then
    echo "gate-ratio: using pre-computed bench JSON: $BENCH_JSON"
    CANDIDATE_AGG="$(jq -r '.bwt_aggregate // .aggregate // .current_best.aggregate' "$BENCH_JSON" 2>/dev/null || echo "")"
    # Try multiple field names matching both old and new schema
    if [ -z "$CANDIDATE_AGG" ] || [ "$CANDIDATE_AGG" = "null" ]; then
        CANDIDATE_AGG="$(jq -r 'if .runs then (.runs | last | .aggregate) else .bwt_aggregate end' "$BENCH_JSON" 2>/dev/null || echo "")"
    fi
else
    echo "gate-ratio: running bench harness..."
    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT
    BENCH_OUT="$TMPDIR/candidate-bench.json"

    cd "$REPO_ROOT"
    set +e
    python3 "$BENCH_PY" --report-id "gate-ratio-candidate" 2>&1
    BENCH_RC=$?
    set -e

    if [ "$BENCH_RC" -ne 0 ]; then
        die "bench harness failed (exit $BENCH_RC)"
    fi

    # Locate the output (bench writes to docs/ephemeral/research/)
    BENCH_OUT="$REPO_ROOT/docs/ephemeral/research/gate-ratio-candidate-bench.json"
    [ -f "$BENCH_OUT" ] || die "bench output not found: $BENCH_OUT"
    CANDIDATE_AGG="$(jq -r '.bwt_aggregate // .aggregate' "$BENCH_OUT" 2>/dev/null || echo "")"
fi

if [ -z "$CANDIDATE_AGG" ] || [ "$CANDIDATE_AGG" = "null" ]; then
    die "could not parse candidate aggregate from bench output"
fi

echo "gate-ratio: candidate aggregate = $CANDIDATE_AGG"

# ── strict improvement check (python for float comparison) ────────────────────
IMPROVED="$(python3 -c "
import sys
candidate = float(sys.argv[1])
baseline  = float(sys.argv[2])
# Strictly LOWER ratio = better compression
print('YES' if candidate < baseline else 'NO')
print(f'delta = {candidate - baseline:+.6f}')
" "$CANDIDATE_AGG" "$BASELINE_AGG")"

VERDICT_LINE="$(echo "$IMPROVED" | head -1)"
DELTA_LINE="$(echo "$IMPROVED" | tail -1)"

echo "gate-ratio: $DELTA_LINE (baseline=$BASELINE_AGG, candidate=$CANDIDATE_AGG)"

if [ "$VERDICT_LINE" != "YES" ]; then
    echo "gate-ratio: FAIL — no strict aggregate improvement" >&2
    exit 1
fi

# Export for downstream gates (called by run-merge-rail.sh in the same shell)
export GATE_RATIO_CANDIDATE_AGG="$CANDIDATE_AGG"
echo "GATE_RATIO_CANDIDATE_AGG=$CANDIDATE_AGG"  # parseable by run-merge-rail.sh

echo "gate-ratio: PASS — strict aggregate improvement confirmed"
exit 0
