#!/usr/bin/env bash
# run-merge-rail.sh — AC-5 deterministic merge rail.
#
# Chains five fail-closed gates in order. Exits non-zero on the first failure
# and discards the candidate branch. All-green → signed fast-forward merge to
# main + leaderboard append.
#
# Usage:
#   run-merge-rail.sh --branch <feat/branch> --run-id <run-id> [--dry-run]
#
#   --branch     Feature branch to test and merge (must be checked out locally)
#   --run-id     Unique iteration identifier (e.g. iter-001-20260621T120000Z)
#   --dry-run    Run all gates but stop before the actual git merge + leaderboard write
#   --bench-json Path to pre-computed bench JSON (skips bench re-run in gate-ratio/competitive)
#
# Exit 0   = all gates pass (+ merge executed unless --dry-run)
# Exit 1   = gate failure (branch discarded)
# Exit 2   = usage / environment error
#
# PINNED OUT-OF-TREE: this script lives in code/cluster/gate/ and is committed
# to main. Workers run this copy from main — they cannot edit their own gate.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
RUNLOG="$REPO_ROOT/datarim/cubrim-run-log.jsonl"

# ── argument parsing ──────────────────────────────────────────────────────────
BRANCH=""
RUN_ID=""
DRY_RUN=0
BENCH_JSON=""
VALUE_SCHEME="bwt-entropy"  # default: BWT is the current best scheme; override per iteration

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch)       BRANCH="$2"; shift 2;;
        --run-id)       RUN_ID="$2"; shift 2;;
        --dry-run)      DRY_RUN=1; shift;;
        --bench-json)   BENCH_JSON="$2"; shift 2;;
        --value-scheme) VALUE_SCHEME="$2"; shift 2;;
        *) echo "run-merge-rail: unknown arg: $1" >&2; exit 2;;
    esac
done

die() { echo "run-merge-rail: ERROR: $*" >&2; exit 2; }
log_gate() {
    # Append a gate result line to the run log (Law 5 audit trail)
    local gate="$1" verdict="$2" detail="${3:-}"
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    # reuse jq for safe JSON emission
    if command -v jq >/dev/null 2>&1; then
        jq -cn \
            --arg ts "$ts" --arg run_id "$RUN_ID" \
            --arg gate "$gate" --arg verdict "$verdict" \
            --arg detail "$detail" \
            '{ts:$ts, run_id:$run_id, event:"gate", gate:$gate, verdict:$verdict, detail:$detail}' \
            >> "$RUNLOG" 2>/dev/null || true
    fi
}

[ -n "$BRANCH" ] || die "--branch is required"
[ -n "$RUN_ID" ] || die "--run-id is required"

echo "run-merge-rail: starting rail for branch=$BRANCH run-id=$RUN_ID dry-run=$DRY_RUN"

# ── ensure we're in the repo root ────────────────────────────────────────────
cd "$REPO_ROOT"

# Ensure run-log directory exists
mkdir -p "$(dirname "$RUNLOG")"
touch "$RUNLOG"

# ── helper: run one gate, log result, fail-close ─────────────────────────────
run_gate() {
    local gate_script="$GATE_DIR/$1"
    local gate_name="${1%.sh}"
    shift
    local extra_args=("$@")

    [ -f "$gate_script" ] || { log_gate "$gate_name" "FAIL" "script not found"; die "$gate_name not found: $gate_script"; }
    chmod +x "$gate_script"

    echo ""
    echo "run-merge-rail: ── $gate_name ──────────────────────────────"
    set +e
    "$gate_script" "${extra_args[@]+"${extra_args[@]}"}"
    local rc=$?
    set -e

    if [ "$rc" -ne 0 ]; then
        log_gate "$gate_name" "FAIL" "exit $rc"
        echo "run-merge-rail: GATE FAILED: $gate_name (exit $rc)" >&2
        # Discard candidate branch
        if git branch --list "$BRANCH" | grep -q "$BRANCH"; then
            git branch -D "$BRANCH" 2>/dev/null || true
            echo "run-merge-rail: discarded branch: $BRANCH"
        fi
        # Record NO-GO in run log
        if command -v jq >/dev/null 2>&1; then
            local ts
            ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
            jq -cn \
                --arg ts "$ts" --arg run_id "$RUN_ID" \
                --arg branch "$BRANCH" --arg gate "$gate_name" \
                '{ts:$ts, run_id:$run_id, event:"merge_rail_fail", failed_gate:$gate, branch:$branch, verdict:"NO-GO"}' \
                >> "$RUNLOG" 2>/dev/null || true
        fi
        exit 1
    fi

    log_gate "$gate_name" "PASS" ""
}

# ── gate chain (fail-closed, ordered) ────────────────────────────────────────
# Check out the candidate branch
git checkout "$BRANCH" 2>/dev/null || die "could not checkout branch: $BRANCH"

BENCH_ARGS=()
[ -n "$BENCH_JSON" ] && BENCH_ARGS=(--bench-json "$BENCH_JSON")
SCHEME_ARGS=()
[ -n "$VALUE_SCHEME" ] && SCHEME_ARGS=(--value-scheme "$VALUE_SCHEME")

run_gate "gate-corpus-hash.sh"
run_gate "gate-cargo-test.sh"
run_gate "gate-roundtrip.sh"
run_gate "gate-ratio.sh" "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}"
run_gate "gate-competitive.sh" \
    "${BENCH_ARGS[@]+"${BENCH_ARGS[@]}"}" \
    "${SCHEME_ARGS[@]+"${SCHEME_ARGS[@]}"}"

echo ""
echo "run-merge-rail: ALL GATES PASSED — branch=$BRANCH"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "run-merge-rail: DRY-RUN mode — stopping before merge. Would merge $BRANCH → main."
    git checkout main 2>/dev/null || true
    exit 0
fi

# ── signed fast-forward merge to main ────────────────────────────────────────
CANDIDATE_SHA="$(git rev-parse HEAD)"
git checkout main
git merge --ff-only "$BRANCH"
MERGED_SHA="$(git rev-parse HEAD)"

echo "run-merge-rail: merged $BRANCH → main at $MERGED_SHA"

# ── delete candidate branch (clean up) ───────────────────────────────────────
git branch -D "$BRANCH" 2>/dev/null || true

# ── append GO entry to run log (Law 5) ───────────────────────────────────────
if command -v jq >/dev/null 2>&1; then
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    jq -cn \
        --arg ts "$ts" --arg run_id "$RUN_ID" \
        --arg branch "$BRANCH" --arg merged_sha "$MERGED_SHA" \
        --arg candidate_sha "$CANDIDATE_SHA" \
        '{ts:$ts, run_id:$run_id, event:"merge_rail_pass", branch:$branch,
          candidate_sha:$candidate_sha, merged_sha:$merged_sha, verdict:"GO"}' \
        >> "$RUNLOG" 2>/dev/null || true
fi

echo "run-merge-rail: COMPLETE — GO, merged to main ($MERGED_SHA), run_log_ref=$RUN_ID"
exit 0
