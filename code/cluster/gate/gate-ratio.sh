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

# Parse the candidate aggregate ratio from a bench JSON. Supports two schemas:
#   1. flat object with a precomputed `.bwt_aggregate` / `.aggregate` field;
#   2. run_bench.py's array-of-runs schema (no aggregate field) — compute it as
#      sum(cubrim_bytes)/sum(size_bytes) over the last run's per-file results.
# This only DERIVES the aggregate; it does not change the strict-improvement
# comparison, so the gate's bar is unchanged.
parse_candidate_aggregate() {
    local json="$1"
    python3 - "$json" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)

def flat(d):
    for k in ("bwt_aggregate", "aggregate"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None

agg = None
if isinstance(data, dict):
    agg = flat(data)
    if agg is None and isinstance(data.get("current_best"), dict):
        agg = flat(data["current_best"])
    runs = data.get("runs")
    if agg is None and isinstance(runs, list) and runs:
        results = runs[-1].get("results", [])
    else:
        results = data.get("results", []) if agg is None else []
elif isinstance(data, list) and data:
    # run_bench.py schema: list of run dicts, each with per-file `results`.
    results = data[-1].get("results", [])
else:
    results = []

if agg is None and results:
    c = sum(r.get("cubrim_bytes", 0) for r in results)
    s = sum(r.get("size_bytes", 0) for r in results)
    if s > 0:
        agg = c / s

if agg is not None:
    print(f"{agg:.6f}")
PYEOF
}

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

# ── corpus-version assertion (same-corpus comparison guard) ───────────────────
# The baseline aggregate is only comparable to the candidate aggregate when both
# are measured on the SAME frozen corpus. Assert the baseline's recorded
# corpus_manifest_sha256 matches the frozen manifest this gate will benchmark
# against (the hash gate-corpus-hash.sh anchors). A mismatch means the baseline
# was measured on a different corpus — comparing the two would be apples-to-pears
# and could falsely pass a candidate. Fail closed and self-document the cause.
BASELINE_CORPUS_SHA="$(echo "$MAIN_LEADERBOARD_JSON" | jq -r '.current_best.corpus_manifest_sha256 // ""')"
FROZEN_CORPUS_SHA="$(awk '{print $1}' "$GATE_DIR/corpus-baseline.sha256" 2>/dev/null || echo "")"

if [ -z "$FROZEN_CORPUS_SHA" ]; then
    die "frozen corpus manifest hash not found at $GATE_DIR/corpus-baseline.sha256"
fi
if [ -z "$BASELINE_CORPUS_SHA" ]; then
    die "baseline is missing current_best.corpus_manifest_sha256 — cannot prove same-corpus comparison"
fi
if [ "$BASELINE_CORPUS_SHA" != "$FROZEN_CORPUS_SHA" ]; then
    echo "gate-ratio: FAIL — baseline measured on a different corpus" >&2
    echo "  baseline corpus_manifest_sha256: $BASELINE_CORPUS_SHA" >&2
    echo "  frozen   corpus manifest sha256: $FROZEN_CORPUS_SHA" >&2
    echo "  the baseline aggregate is not comparable to a candidate benched on the frozen corpus" >&2
    exit 1
fi
echo "gate-ratio: corpus-version OK (baseline + candidate on the same frozen corpus $FROZEN_CORPUS_SHA)"

echo "gate-ratio: baseline = $BASELINE_SCHEME @ $BASELINE_AGG"

# ── same-scheme guard: bench the candidate with the SAME value-scheme the
#    baseline was measured with, else we compare the candidate's default
#    (bitpack-fixed ~0.56) against the BWT baseline (~0.30) and every candidate
#    falsely NO-GOs. Map the leaderboard scheme name → the run_bench.py flag.
case "$BASELINE_SCHEME" in
    BwtEntropy|bwt-entropy)             BASELINE_VALUE_SCHEME="bwt-entropy" ;;
    EntropyContext2|entropy-context-2)  BASELINE_VALUE_SCHEME="entropy-context-2" ;;
    EntropyContext|entropy-context)     BASELINE_VALUE_SCHEME="entropy-context" ;;
    Entropy|entropy)                    BASELINE_VALUE_SCHEME="entropy" ;;
    RleCodes|rle-codes)                 BASELINE_VALUE_SCHEME="rle-codes" ;;
    BitpackFixed|bitpack-fixed|unknown) BASELINE_VALUE_SCHEME="" ;;
    *)                                  BASELINE_VALUE_SCHEME="" ;;
esac
[ -n "$BASELINE_VALUE_SCHEME" ] \
    && echo "gate-ratio: benching candidate with --value-scheme $BASELINE_VALUE_SCHEME (matches baseline)"

# ── run bench (or use pre-computed result) ────────────────────────────────────
if [ -n "$BENCH_JSON" ] && [ -f "$BENCH_JSON" ]; then
    echo "gate-ratio: using pre-computed bench JSON: $BENCH_JSON"
    CANDIDATE_AGG="$(parse_candidate_aggregate "$BENCH_JSON")"
else
    echo "gate-ratio: running bench harness..."
    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT
    BENCH_OUT="$TMPDIR/candidate-bench.json"

    cd "$REPO_ROOT"
    BENCH_SCHEME_ARGS=()
    [ -n "$BASELINE_VALUE_SCHEME" ] && BENCH_SCHEME_ARGS=(--value-scheme "$BASELINE_VALUE_SCHEME")
    set +e
    python3 "$BENCH_PY" --report-id "gate-ratio-candidate" "${BENCH_SCHEME_ARGS[@]}" 2>&1
    BENCH_RC=$?
    set -e

    if [ "$BENCH_RC" -ne 0 ]; then
        die "bench harness failed (exit $BENCH_RC)"
    fi

    # Locate the output (bench writes to docs/ephemeral/research/)
    BENCH_OUT="$REPO_ROOT/docs/ephemeral/research/gate-ratio-candidate-bench.json"
    [ -f "$BENCH_OUT" ] || die "bench output not found: $BENCH_OUT"
    CANDIDATE_AGG="$(parse_candidate_aggregate "$BENCH_OUT")"
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
