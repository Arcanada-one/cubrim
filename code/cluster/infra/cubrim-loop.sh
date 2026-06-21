#!/usr/bin/env bash
# cubrim-loop.sh — Autonomous research loop driver.
#
# Runs one full iteration of the Cubrim compression-research cycle:
#
#   Phase 1  read STATE doc → determine resume point
#   Phase 2  consilium fanout  (reuses dr-orchestrate content_consilium_fanout.sh)
#   Phase 3  consilium judge   (reuses dr-orchestrate content_consilium_judge.sh)
#   Phase 4  deterministic arbiter gate (consilium/arbiter/)
#   Phase 5  implementation by workers (stub: signal workers via shared file)
#   Phase 6  AC-5 merge rail  (runs EXISTING code/cluster/gate/run-merge-rail.sh)
#   Phase 7  write updated STATE doc
#
# Reuse map:
#   Loop skeleton   — mirrors dr-fleet-evolution/evolution-loop.sh phases 1-4
#                     (vendored pattern; does NOT call evolution-loop.sh directly
#                     because fleet-evolution never auto-merges — the merge step
#                     in Phase 6 is new, conservative, behind the AC-5 rail)
#   Consilium       — /Users/ug/arcanada/Projects/Datarim/code/datarim/plugins/
#                     dr-orchestrate/scripts/content_consilium_{fanout,judge}.sh
#                     (called by absolute path; these are not installed as commands)
#   Arbiter         — consilium/arbiter/probe-entropy.sh + size-model.sh (local)
#   Merge rail      — code/cluster/gate/run-merge-rail.sh (EXISTING, pinned, DO NOT duplicate)
#   JSONL writer    — code/cluster/vendor/jsonl-write.sh (local vendor copy)
#
# STATE doc: CUBR-AUTONOMOUS-STATE.md at repo root (git-tracked, not under datarim/).
# Run log:   datarim/cubrim-run-log.jsonl (append-only, Law 5 audit trail).
#
# Usage:
#   cubrim-loop.sh                  # one full iteration
#   cubrim-loop.sh --dry-run        # trace phases without side-effects
#   CUBRIM_LOOP_DRYRUN=1 cubrim-loop.sh

set -euo pipefail

# ── resolve script location ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ── constants / paths ────────────────────────────────────────────────────────
STATE_DOC="$REPO_ROOT/CUBR-AUTONOMOUS-STATE.md"
RUNLOG="$REPO_ROOT/datarim/cubrim-run-log.jsonl"
GATE_SCRIPT="$REPO_ROOT/code/cluster/gate/run-merge-rail.sh"
JSONL_WRITER="$REPO_ROOT/code/cluster/vendor/jsonl-write.sh"

# Datarim framework paths (absolute — not installed as commands)
DATARIM_SCRIPTS="/Users/ug/arcanada/Projects/Datarim/code/datarim/plugins/dr-orchestrate/scripts"
FANOUT_SCRIPT="$DATARIM_SCRIPTS/content_consilium_fanout.sh"
JUDGE_SCRIPT="$DATARIM_SCRIPTS/content_consilium_judge.sh"

# Arbiter (local)
ARBITER_DIR="$REPO_ROOT/consilium/arbiter"
ENTROPY_PROBE="$ARBITER_DIR/probe-entropy.sh"
SIZE_MODEL="$ARBITER_DIR/size-model.sh"

ITER_BRIEF_TEMPLATE="$REPO_ROOT/consilium/iteration-brief.template.md"
LEADERBOARD="$REPO_ROOT/docs/leaderboard/cubrim-leaderboard.json"

# ── argument parsing ─────────────────────────────────────────────────────────
DRY_RUN="${CUBRIM_LOOP_DRYRUN:-0}"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) echo "cubrim-loop: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[cubrim-loop] $(date -u '+%H:%M:%SZ') $*"; }
die()  { echo "[cubrim-loop] ERROR: $*" >&2; exit 1; }

# Emit a structured run-log entry via the vendored JSONL writer.
# Usage: emit_event <event> [<key=value>...]
emit_event() {
    local event="$1"; shift
    local run_id="${RUN_ID:-unknown}"
    local ts; ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    mkdir -p "$(dirname "$RUNLOG")"
    touch "$RUNLOG"

    if command -v jq >/dev/null 2>&1; then
        local extra_json="{}"
        for kv in "$@"; do
            local k="${kv%%=*}" v="${kv#*=}"
            extra_json=$(printf '%s' "$extra_json" | \
                jq --arg k "$k" --arg v "$v" '. + {($k): $v}')
        done
        jq -cn \
            --arg ts "$ts" \
            --arg run_id "$run_id" \
            --arg event "$event" \
            --argjson extra "$extra_json" \
            '{ts:$ts, run_id:$run_id, event:$event} + $extra' \
            >> "$RUNLOG" 2>/dev/null || true
    fi
}

# Read a field from the STATE doc YAML frontmatter.
# Usage: state_get <field>
state_get() {
    local field="$1"
    grep "^${field}:" "$STATE_DOC" 2>/dev/null \
        | head -1 \
        | sed "s/^${field}:[[:space:]]*//" \
        | tr -d '"'
}

# Write a single field in the STATE doc YAML frontmatter.
# Uses sed in-place; creates STATE_DOC if absent.
# Usage: state_set <field> <value>
state_set() {
    local field="$1" value="$2"
    if grep -q "^${field}:" "$STATE_DOC" 2>/dev/null; then
        # shellcheck disable=SC2016  # literal $ in sed replacement is intentional
        sed -i.bak "s|^${field}:.*|${field}: \"${value}\"|" "$STATE_DOC"
        rm -f "${STATE_DOC}.bak"
    else
        echo "${field}: \"${value}\"" >> "$STATE_DOC"
    fi
}

# Check leaderboard for defend-mode trigger.
# Returns 0 (defend) or 1 (attack).
is_defend_mode() {
    if [ ! -f "$LEADERBOARD" ] || ! command -v python3 >/dev/null 2>&1; then
        return 1  # no leaderboard = attack mode
    fi
    python3 - <<'PYEOF'
import json, sys
try:
    lb = json.load(open("$LEADERBOARD"))
    best = lb.get("current_best", {}).get("aggregate", 1.0)
    target = lb.get("win_target", {}).get("gzip_aggregate", 0.159674)
    sys.exit(0 if best <= target else 1)
except Exception:
    sys.exit(1)
PYEOF
}

# Replace the leaderboard literal path in the python here-doc.
# (The here-doc above uses $LEADERBOARD in the outer shell scope.)
is_defend_mode() {
    if [ ! -f "$LEADERBOARD" ] || ! command -v python3 >/dev/null 2>&1; then
        return 1
    fi
    python3 - "$LEADERBOARD" <<'PYEOF'
import json, sys
try:
    lb = json.load(open(sys.argv[1]))
    best = lb.get("current_best", {}).get("aggregate", 1.0)
    target = lb.get("win_target", {}).get("gzip_aggregate", 0.159674)
    sys.exit(0 if best <= target else 1)
except Exception:
    sys.exit(1)
PYEOF
}

# ── main loop ────────────────────────────────────────────────────────────────
main() {
    # ── Phase 1: read STATE doc ──────────────────────────────────────────────
    log "Phase 1: reading STATE doc"

    [ -f "$STATE_DOC" ] || die "STATE doc not found: $STATE_DOC — run initial setup first"

    PREV_ITER="$(state_get iteration)"
    ITER_NUM=$(( ${PREV_ITER:-0} + 1 ))
    RUN_ID="iter-$(printf '%04d' "$ITER_NUM")-$(date -u '+%Y%m%dT%H%M%SZ')"
    LOOP_PHASE="$(state_get loop_phase)"
    MAIN_BASELINE="$(state_get main_baseline)"

    log "RUN_ID=$RUN_ID  prev_iter=$PREV_ITER  loop_phase=${LOOP_PHASE:-idle}  baseline=${MAIN_BASELINE:-unknown}"
    emit_event "iteration_start" "iteration=$ITER_NUM" "resumed_from=${LOOP_PHASE:-idle}"

    # Update STATE: mark as running
    if [ "$DRY_RUN" -eq 0 ]; then
        state_set "iteration" "$ITER_NUM"
        state_set "loop_phase" "consilium"
        state_set "last_run_id" "$RUN_ID"
    fi

    # ── Defend-mode check ────────────────────────────────────────────────────
    if is_defend_mode; then
        log "DEFEND MODE: current_best.aggregate <= win_target — running validation only"
        emit_event "defend_mode_active" "iteration=$ITER_NUM"
        # In defend mode: run gates only on main, do not generate new candidates
        if [ "$DRY_RUN" -eq 0 ]; then
            "$GATE_SCRIPT" --branch main --run-id "${RUN_ID}-defend" --dry-run || true
            state_set "loop_phase" "sleeping"
        fi
        log "Defend-mode iteration complete."
        return 0
    fi

    # ── Phase 2: consilium fanout ────────────────────────────────────────────
    log "Phase 2: consilium fanout (briefs workers)"

    WORK_DIR="$(mktemp -d)"
    trap 'rm -rf "$WORK_DIR"' EXIT

    ITER_BRIEF="$WORK_DIR/iter-brief.md"

    # Build the iteration brief from template (substitute current baseline)
    if [ -f "$ITER_BRIEF_TEMPLATE" ]; then
        sed "s/__BASELINE__/${MAIN_BASELINE:-unknown}/g;s/__ITER__/${ITER_NUM}/g" \
            "$ITER_BRIEF_TEMPLATE" > "$ITER_BRIEF"
    else
        # Minimal fallback brief
        cat > "$ITER_BRIEF" <<BRIEF
# Cubrim Research Iteration ${ITER_NUM}

Current baseline: ${MAIN_BASELINE:-unknown}
Goal: propose a compression improvement to code/cubrim-rs/src/codec.rs
that passes the AC-5 gate chain (corpus-hash, cargo-test, roundtrip, ratio, competitive).
BRIEF
    fi

    FANOUT_OUTPUT="$WORK_DIR/fanout-responses.jsonl"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY-RUN] would call: $FANOUT_SCRIPT --brief $ITER_BRIEF"
    elif [ -x "$FANOUT_SCRIPT" ]; then
        "$FANOUT_SCRIPT" \
            --brief "$ITER_BRIEF" \
            --output "$FANOUT_OUTPUT" \
            2>&1 | sed 's/^/  [fanout] /' || {
                log "WARNING: fanout failed — continuing with empty responses"
                touch "$FANOUT_OUTPUT"
            }
    else
        log "WARNING: fanout script not found at $FANOUT_SCRIPT — skipping consilium fanout"
        touch "$FANOUT_OUTPUT"
    fi

    emit_event "consilium_fanout_complete" "output=$FANOUT_OUTPUT"

    # ── Phase 3: consilium judge ─────────────────────────────────────────────
    log "Phase 3: consilium judge (selects best proposal)"

    JUDGE_OUTPUT="$WORK_DIR/judge-verdict.json"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY-RUN] would call: $JUDGE_SCRIPT --responses $FANOUT_OUTPUT"
        echo '{"verdict":"dry-run","selected_proposal":"none"}' > "$JUDGE_OUTPUT"
    elif [ -x "$JUDGE_SCRIPT" ] && [ -s "$FANOUT_OUTPUT" ]; then
        "$JUDGE_SCRIPT" \
            --responses "$FANOUT_OUTPUT" \
            --output "$JUDGE_OUTPUT" \
            2>&1 | sed 's/^/  [judge] /' || {
                log "WARNING: judge failed — skipping this iteration"
                emit_event "iteration_abort" "reason=judge_failed"
                state_set "loop_phase" "sleeping"
                return 0
            }
    else
        log "WARNING: judge not available or no responses — skipping iteration"
        emit_event "iteration_abort" "reason=no_responses"
        state_set "loop_phase" "sleeping"
        return 0
    fi

    SELECTED_PROPOSAL="$(jq -r '.selected_proposal // empty' "$JUDGE_OUTPUT" 2>/dev/null || true)"
    emit_event "consilium_judge_complete" "selected=${SELECTED_PROPOSAL:-none}"

    # ── Phase 4: deterministic arbiter ───────────────────────────────────────
    log "Phase 4: deterministic arbiter (entropy probe + size model)"

    if [ "$DRY_RUN" -eq 0 ] && [ -x "$ENTROPY_PROBE" ]; then
        "$ENTROPY_PROBE" \
            --corpus "$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json" \
            2>&1 | sed 's/^/  [arbiter-entropy] /' || {
                log "Arbiter entropy probe FAIL — discarding iteration"
                emit_event "arbiter_fail" "stage=entropy_probe"
                state_set "loop_phase" "sleeping"
                return 0
            }
        log "Arbiter entropy probe PASS"
    else
        log "[DRY-RUN or no probe] skipping entropy probe"
    fi

    if [ "$DRY_RUN" -eq 0 ] && [ -x "$SIZE_MODEL" ]; then
        "$SIZE_MODEL" \
            --proposal "$JUDGE_OUTPUT" \
            2>&1 | sed 's/^/  [arbiter-size] /' || {
                log "Arbiter size model FAIL — discarding iteration"
                emit_event "arbiter_fail" "stage=size_model"
                state_set "loop_phase" "sleeping"
                return 0
            }
        log "Arbiter size model PASS"
    fi

    emit_event "arbiter_pass" "iteration=$ITER_NUM"

    # ── Phase 5: worker implementation ───────────────────────────────────────
    # In the full cluster, the orchestrator signals workers via a shared
    # brief file; workers implement changes on feature branches.
    # This stub writes the brief and waits for the implementation branch.
    log "Phase 5: signalling workers for implementation"

    IMPL_BRANCH="feat/iter-${ITER_NUM}-$(date -u '+%Y%m%d')"
    IMPL_SIGNAL="$WORK_DIR/impl-signal.json"

    jq -cn \
        --arg run_id "$RUN_ID" \
        --arg branch "$IMPL_BRANCH" \
        --arg proposal "${SELECTED_PROPOSAL:-none}" \
        '{run_id:$run_id, branch:$branch, proposal:$proposal, status:"pending"}' \
        > "$IMPL_SIGNAL"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY-RUN] would signal workers: branch=$IMPL_BRANCH"
        emit_event "impl_signal_dry_run" "branch=$IMPL_BRANCH"
        state_set "loop_phase" "sleeping"
        log "Dry-run iteration complete. No changes made."
        return 0
    fi

    # Workers implement on IMPL_BRANCH. In production the orchestrator
    # polls until the branch exists or HANG_IDLE_SECS is exceeded.
    # For this loop driver stub we assert the branch exists before calling the rail.
    HANG_IDLE_SECS="${CUBRIM_HANG_IDLE_SECS:-7200}"  # 2h max wait
    POLL_INTERVAL=60
    ELAPSED=0

    log "Waiting for implementation branch $IMPL_BRANCH (max ${HANG_IDLE_SECS}s)"
    while ! git -C "$REPO_ROOT" branch --list "$IMPL_BRANCH" | grep -q "$IMPL_BRANCH"; do
        sleep "$POLL_INTERVAL"
        ELAPSED=$(( ELAPSED + POLL_INTERVAL ))
        if [ "$ELAPSED" -ge "$HANG_IDLE_SECS" ]; then
            log "Hang timeout ($HANG_IDLE_SECS s): branch $IMPL_BRANCH never appeared — aborting"
            emit_event "impl_timeout" "branch=$IMPL_BRANCH" "elapsed=$ELAPSED"
            state_set "loop_phase" "sleeping"
            return 0
        fi
        log "Waiting for $IMPL_BRANCH ... ${ELAPSED}/${HANG_IDLE_SECS}s"
    done

    log "Branch $IMPL_BRANCH ready"
    emit_event "impl_branch_ready" "branch=$IMPL_BRANCH"
    state_set "loop_phase" "gate"

    # ── Phase 6: AC-5 merge rail ─────────────────────────────────────────────
    # CALLS THE EXISTING gate/run-merge-rail.sh — do NOT duplicate the gate chain here.
    log "Phase 6: AC-5 merge rail"

    [ -x "$GATE_SCRIPT" ] || die "merge rail not found: $GATE_SCRIPT"

    set +e
    "$GATE_SCRIPT" --branch "$IMPL_BRANCH" --run-id "$RUN_ID"
    RAIL_EXIT=$?
    set -e

    if [ "$RAIL_EXIT" -eq 0 ]; then
        MERGED_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
        log "MERGE RAIL: GO — merged to main at $MERGED_SHA"
        emit_event "iteration_complete" \
            "verdict=GO" "branch=$IMPL_BRANCH" "merged_sha=$MERGED_SHA"
        state_set "loop_phase" "merged"
        state_set "main_baseline" "$MERGED_SHA"
    else
        log "MERGE RAIL: NO-GO — branch $IMPL_BRANCH discarded (exit $RAIL_EXIT)"
        emit_event "iteration_complete" "verdict=NO-GO" "branch=$IMPL_BRANCH"
        state_set "loop_phase" "discarded"
    fi

    # ── Phase 7: update STATE doc ────────────────────────────────────────────
    log "Phase 7: updating STATE doc"
    state_set "loop_phase" "sleeping"

    log "Iteration $ITER_NUM complete."
}

# ── entrypoint guard ─────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
