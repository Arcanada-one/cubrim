#!/usr/bin/env bash
# gate-competitive.sh — Gate 5: per-file competitive selection — no file may regress.
#
# Every corpus file's compressed size under the candidate scheme (with competitive
# min(new, T4) + 1 scheme byte selection) must be <= its T4+BWT baseline from the
# leaderboard's current_best per_file record.
#
# Design note: the codec's competitive-selection architecture (encoder writes
# min(new, T4) + scheme byte in header) is structurally regression-proof per
# file — this gate verifies that property holds on the current binary.
#
# Exit 0   = all files pass competitive check
# Exit 1   = any file regresses (gate fails — candidate discarded)
# Exit 2   = setup error
#
# Called by run-merge-rail.sh; runs from the REPO ROOT.
# Optional env: GATE_RATIO_CANDIDATE_BENCH_JSON path to pre-computed bench output.

set -euo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
CUBRIM_BIN="$REPO_ROOT/code/cubrim-rs/target/release/cubrim"

# Optional arguments
BENCH_JSON="${GATE_RATIO_CANDIDATE_BENCH_JSON:-}"
VALUE_SCHEME=""  # e.g. bwt-entropy; if empty, use default codec scheme
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bench-json)     BENCH_JSON="$2"; shift 2;;
        --value-scheme)   VALUE_SCHEME="$2"; shift 2;;
        *) shift;;
    esac
done

die() { echo "gate-competitive: ERROR: $*" >&2; exit 2; }

[ -f "$MANIFEST" ] || die "corpus manifest not found: $MANIFEST"
command -v python3 >/dev/null 2>&1 || die "python3 required"
command -v jq >/dev/null 2>&1 || die "jq required"
command -v git >/dev/null 2>&1 || die "git required"

# ── read per-file baselines from main branch via git-object store (tamper-resistant) ──
# Baseline source priority (highest to lowest):
#   1. git show main:docs/leaderboard/cubrim-leaderboard.json  — resolves from
#      the main branch ref in the git object store; the candidate branch's
#      working-tree copy is never consulted.
#   2. Pinned fallback: $GATE_DIR/pinned-leaderboard-baseline.json  — bootstrap
#      mode (before the leaderboard file is committed to main).
LEADERBOARD_GIT_PATH="docs/leaderboard/cubrim-leaderboard.json"
PINNED_BASELINE="$GATE_DIR/pinned-leaderboard-baseline.json"
MAIN_LEADERBOARD_JSON="$(git -C "$REPO_ROOT" show "main:${LEADERBOARD_GIT_PATH}" 2>/dev/null || true)"

if [ -z "$MAIN_LEADERBOARD_JSON" ]; then
    [ -f "$PINNED_BASELINE" ] || die "leaderboard not in main branch and no pinned baseline found at $PINNED_BASELINE"
    echo "gate-competitive: leaderboard not in main branch — using pinned baseline (bootstrap mode)"
    MAIN_LEADERBOARD_JSON="$(cat "$PINNED_BASELINE")"
fi

# per_file lives on current_best or the most recent GO run (legacy shape fallback)
echo "gate-competitive: reading per-file baselines from main branch leaderboard..."

# Build a Python dict: {name: baseline_bytes}
BASELINES="$(echo "$MAIN_LEADERBOARD_JSON" | python3 -c "
import json, sys
lb = json.load(sys.stdin)
# per_file lives on current_best or the most recent GO run
pf = lb.get('current_best', {}).get('per_file', [])
if not pf:
    # fall back to most recent merged run
    for run in reversed(lb.get('runs', [])):
        if run.get('merged') and run.get('per_file'):
            pf = run['per_file']
            break
result = {}
for e in pf:
    # candidate bytes = min(new_bytes, t4_bytes) — baseline IS t4+BWT competitive
    # Use 'bytes' if present, else 'bwt_bytes' / 't4_bytes' fallback
    b = e.get('bytes') or e.get('bwt_bytes') or e.get('t4_bytes')
    if b:
        result[e['file']] = int(b)
print(json.dumps(result))
")"

echo "gate-competitive: baselines loaded: $BASELINES"

# ── measure candidate per-file compressed sizes ───────────────────────────────
FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# Build binary if needed
if [ ! -f "$CUBRIM_BIN" ]; then
    echo "gate-competitive: building cubrim binary..."
    cd "$REPO_ROOT/code/cubrim-rs"
    cargo build --release --quiet
    cd "$REPO_ROOT"
fi

while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    path="$(echo "$entry" | jq -r '.path')"
    size_bytes="$(echo "$entry" | jq -r '.size_bytes')"

    # Resolve path portably
    if [ ! -f "$path" ]; then
        path="$REPO_ROOT/docs/ephemeral/research/corpus/$(basename "$path")"
    fi
    [ -f "$path" ] || { echo "gate-competitive: SKIP $name (corpus file not found)" >&2; continue; }

    compressed="$TMPDIR/${name}.cubrim"
    COMPRESS_ARGS=("$path" "$compressed")
    [ -n "$VALUE_SCHEME" ] && COMPRESS_ARGS+=(--value-scheme "$VALUE_SCHEME")
    set +e
    "$CUBRIM_BIN" compress "${COMPRESS_ARGS[@]}" 2>/dev/null
    rc=$?
    set -e

    if [ "$rc" -ne 0 ]; then
        echo "gate-competitive: FAIL $name — compress failed (exit $rc)" >&2
        FAIL=1
        continue
    fi

    CANDIDATE_BYTES="$(wc -c < "$compressed")"

    # Look up baseline; if missing from leaderboard, use raw size as safe bound
    BASELINE_BYTES="$(python3 -c "
import json, sys
baselines = json.loads(sys.argv[1])
name = sys.argv[2]
safe_bound = int(sys.argv[3])
# If no baseline recorded, allow candidate <= raw size (safe conservative bound)
print(baselines.get(name, safe_bound))
" "$BASELINES" "$name" "$size_bytes")"

    if python3 -c "
import sys
candidate = int(sys.argv[1])
baseline  = int(sys.argv[2])
sys.exit(0 if candidate <= baseline else 1)
" "$CANDIDATE_BYTES" "$BASELINE_BYTES"; then
        echo "gate-competitive: OK   $name (${CANDIDATE_BYTES}B <= ${BASELINE_BYTES}B baseline)"
    else
        echo "gate-competitive: FAIL $name — REGRESSION: ${CANDIDATE_BYTES}B > ${BASELINE_BYTES}B baseline" >&2
        FAIL=1
    fi
done < <(jq -c '.[]' "$MANIFEST")

[ "$FAIL" -eq 0 ] || exit 1
echo "gate-competitive: PASS — no per-file regression detected"
exit 0
