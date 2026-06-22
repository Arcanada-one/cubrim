#!/usr/bin/env bash
# cubrim-loop.sh — Autonomous research loop driver (docker-native consilium).
#
# Runs one full iteration of the Cubrim compression-research cycle:
#
#   Phase 1  read STATE doc → determine resume point
#   Phase 2  consilium fanout  — brief every live docker worker via its
#            OpenAI-compatible free-model API; collect structured proposals
#   Phase 3  consilium judge   — deterministic scoring + closed-branch reject;
#            select one proposal
#   Phase 4  deterministic arbiter gate (consilium/arbiter/) — best-effort
#   Phase 5  implementation     — a capable worker emits a concrete edit for
#            the selected candidate; the orchestrator applies it on a feature
#            branch and builds it (cargo build --release, one repair round)
#   Phase 6  AC-5 merge rail    — EXISTING code/cluster/gate/run-merge-rail.sh
#   Phase 7  write updated STATE doc
#
# Topology:
#   The driver runs on the HOST (arcana-db) as root. The research workers run
#   in docker containers labelled `cubrim-role` and are reached via `docker exec`.
#   Each worker container carries ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN /
#   ANTHROPIC_MODEL pointing at a free OpenAI-compatible model. The workers do
#   NOT have repo write access — the orchestrator (this script) is the only
#   process that writes branches and commits. Workers only emit text (proposals
#   and edits) over their model API.
#
# Reuse map:
#   Loop skeleton  — mirrors dr-fleet-evolution/evolution-loop.sh phases 1-4;
#                    the auto-merge step (Phase 6) is new, behind the AC-5 rail.
#   Merge rail     — code/cluster/gate/run-merge-rail.sh (EXISTING, pinned).
#   Arbiter        — consilium/arbiter/probe-entropy.sh + size-model.sh (local).
#
# STATE doc: CUBR-AUTONOMOUS-STATE.md at repo root (git-tracked, not under datarim/).
# Run log:   datarim/cubrim-run-log.jsonl (append-only, Law 5 audit trail).
#
# Usage:
#   cubrim-loop.sh                  # one full iteration
#   cubrim-loop.sh --dry-run        # trace phases without side-effects / model calls
#   CUBRIM_LOOP_DRYRUN=1 cubrim-loop.sh

set -euo pipefail

# ── resolve script location ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ── constants / paths ────────────────────────────────────────────────────────
STATE_DOC="$REPO_ROOT/CUBR-AUTONOMOUS-STATE.md"
RUNLOG="$REPO_ROOT/datarim/cubrim-run-log.jsonl"
GATE_SCRIPT="$REPO_ROOT/code/cluster/gate/run-merge-rail.sh"

# Arbiter (local). The order-1 entropy probe needs a candidate Python script,
# which free-model text proposals do not supply, so Phase 4 uses the size-model
# (Gotcha #6/#7) as the cheap pre-filter; the merge rail is the absolute gate.
ARBITER_DIR="$REPO_ROOT/consilium/arbiter"
SIZE_MODEL="$ARBITER_DIR/size-model.sh"

ITER_BRIEF_TEMPLATE="$REPO_ROOT/consilium/iteration-brief.template.md"
LEADERBOARD="$REPO_ROOT/docs/leaderboard/cubrim-leaderboard.json"
CLOSED_LEDGER="$REPO_ROOT/consilium/closed-branches.md"
DEFAULT_TARGET_FILE="code/cubrim-rs/src/codec.rs"

# Docker worker discovery + model-call tuning.
WORKER_LABEL="${CUBRIM_WORKER_LABEL:-cubrim-role}"
WORKER_MIN="${CUBRIM_WORKER_MIN:-2}"          # consilium minimum responders
CALL_TIMEOUT="${CUBRIM_CALL_TIMEOUT:-120}"    # per model-call wall-clock seconds
MAX_REPAIR_ROUNDS="${CUBRIM_MAX_REPAIR_ROUNDS:-1}"

# Phase 5 now implements the selected proposal with the HOST's authenticated
# `claude` CLI (operator's personal subscription) rather than a free worker —
# free models reliably PROPOSE but cannot implement the 3400-line Rust codec
# (every candidate failed `cargo build`). Budget guard: this is the paid sub,
# so exactly ONE claude attempt per iteration with a wall-clock timeout.
CLAUDE_BIN="${CUBRIM_CLAUDE_BIN:-claude}"
CLAUDE_TIMEOUT="${CUBRIM_CLAUDE_TIMEOUT:-1200}"  # wall-clock seconds for the impl call (complex schemes need headroom)

# Cargo lives under /root/.cargo/bin on the host; the EnvironmentFile already
# adds it to PATH, but make the loop robust when invoked directly.
case ":$PATH:" in *":/root/.cargo/bin:"*) ;; *) PATH="$PATH:/root/.cargo/bin" ;; esac
export PATH

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

# Emit a structured run-log entry. Usage: emit_event <event> [<key=value>...]
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

# Read a field from the STATE doc YAML frontmatter. Usage: state_get <field>
state_get() {
    local field="$1"
    grep "^${field}:" "$STATE_DOC" 2>/dev/null \
        | head -1 \
        | sed "s/^${field}:[[:space:]]*//" \
        | tr -d '"'
}

# Write a single field in the STATE doc YAML frontmatter. Usage: state_set <field> <value>
state_set() {
    local field="$1" value="$2"
    if grep -q "^${field}:" "$STATE_DOC" 2>/dev/null; then
        sed -i.bak "s|^${field}:.*|${field}: \"${value}\"|" "$STATE_DOC"
        rm -f "${STATE_DOC}.bak"
    else
        echo "${field}: \"${value}\"" >> "$STATE_DOC"
    fi
}

# Check leaderboard for defend-mode trigger. Returns 0 (defend) or 1 (attack).
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

# ── docker-native consilium primitives ───────────────────────────────────────

# Discover UP worker container names (one per line).
discover_workers() {
    docker ps --filter "label=$WORKER_LABEL" --format '{{.Names}}' 2>/dev/null \
        | grep -v -- '-orchestrator$' || true
}

# Read a single env var from inside a worker container. NEVER logged for tokens.
worker_env() {
    local container="$1" var="$2"
    docker exec "$container" printenv "$var" 2>/dev/null || true
}

# Call a worker's OpenAI-compatible chat/completions endpoint.
# Args: <container> <system_prompt_file> <user_prompt_file> <out_file> [max_tokens]
# Returns 0 + writes the model's text content to <out_file> on success.
# Returns 1 on transport / rate-limit (429) / parse failure (caller skips worker).
# The auth token is read into a var and passed via docker exec env — never via
# the host process table and never echoed (no `set -x` in this function).
worker_chat() {
    local container="$1" sys_file="$2" usr_file="$3" out_file="$4"
    local max_tokens="${5:-2048}"
    local base model token
    base="$(worker_env "$container" ANTHROPIC_BASE_URL)"
    model="$(worker_env "$container" ANTHROPIC_MODEL)"
    token="$(worker_env "$container" ANTHROPIC_AUTH_TOKEN)"
    if [ -z "$base" ] || [ -z "$model" ] || [ -z "$token" ]; then
        log "  [$container] missing API env (base/model/token) — skipping"
        return 1
    fi

    # Build the request body on the host with jq (safe JSON escaping), then
    # stream it into the container's curl over stdin so the token and payload
    # never appear in the host or container process table.
    local req_file resp_file http_code
    req_file="$(mktemp)"; resp_file="$(mktemp)"
    jq -n \
        --arg model "$model" \
        --argjson maxtok "$max_tokens" \
        --rawfile sys "$sys_file" \
        --rawfile usr "$usr_file" \
        '{model:$model, max_tokens:$maxtok, temperature:0.4,
          messages:[{role:"system",content:$sys},{role:"user",content:$usr}]}' \
        > "$req_file"

    # `--data-binary @-` reads the body from stdin; token is exported into the
    # container env via `sh -c` reading $TOKEN (passed with `-e`), so it is not
    # an argv element. http code is captured separately from the body.
    set +e
    http_code="$(
        docker exec -i -e "CB_TOKEN=$token" "$container" sh -c \
            "curl -s -o /tmp/cb_resp.json -w '%{http_code}' --max-time $CALL_TIMEOUT \
                 -X POST '$base/chat/completions' \
                 -H \"Authorization: Bearer \$CB_TOKEN\" \
                 -H 'Content-Type: application/json' \
                 --data-binary @-" < "$req_file"
    )"
    local rc=$?
    set -e

    if [ "$rc" -ne 0 ]; then
        log "  [$container] curl transport error (rc=$rc) — skipping"
        rm -f "$req_file" "$resp_file"
        return 1
    fi
    if [ "$http_code" = "429" ]; then
        log "  [$container] HTTP 429 rate-limited — backing off, skipping this round"
        rm -f "$req_file" "$resp_file"
        return 1
    fi
    if [ "$http_code" != "200" ]; then
        log "  [$container] HTTP $http_code (non-200) — skipping"
        rm -f "$req_file" "$resp_file"
        return 1
    fi

    docker exec "$container" cat /tmp/cb_resp.json > "$resp_file" 2>/dev/null || true
    local content
    content="$(jq -r '.choices[0].message.content // empty' "$resp_file" 2>/dev/null || true)"
    rm -f "$req_file" "$resp_file"
    if [ -z "$content" ]; then
        log "  [$container] empty / unparseable model response — skipping"
        return 1
    fi
    printf '%s' "$content" > "$out_file"
    return 0
}

# Extract the first JSON object found in arbitrary model text (handles fenced
# ```json blocks and prose-wrapped objects). Writes JSON to stdout, exits 1 if none.
extract_json() {
    local in_file="$1"
    python3 - "$in_file" <<'PYEOF'
import sys, json, re
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
# 1. fenced ```json ... ``` block
m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
candidates = []
if m:
    candidates.append(m.group(1))
# 2. greedy brace scan: every balanced {...} region
depth = 0; start = None
for i, ch in enumerate(text):
    if ch == '{':
        if depth == 0:
            start = i
        depth += 1
    elif ch == '}':
        if depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start:i+1])
for c in candidates:
    try:
        obj = json.loads(c)
        if isinstance(obj, dict):
            print(json.dumps(obj))
            sys.exit(0)
    except Exception:
        continue
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

    if [ "$DRY_RUN" -eq 0 ]; then
        state_set "iteration" "$ITER_NUM"
        state_set "loop_phase" "consilium"
        state_set "last_run_id" "$RUN_ID"
        # Persist the iteration increment immediately. Later NO-GO paths run
        # `git checkout -- .` to clean the tree before the rail switches branches;
        # that reverts any UNCOMMITTED STATE write (the iteration field is tracked).
        # Without this commit the next run re-reads the previously-committed
        # iteration and the branch name never advances (the "always feat/iter-7"
        # bug). Commit the increment now so it survives a build-fail discard.
        git -C "$REPO_ROOT" add -- "$(basename "$STATE_DOC")" 2>/dev/null || true
        if ! git -C "$REPO_ROOT" diff --cached --quiet 2>/dev/null; then
            git -C "$REPO_ROOT" commit -q -m "loop: iteration $ITER_NUM start ($RUN_ID)" 2>&1 | tail -1 || true
        fi
    fi

    # ── Defend-mode check ────────────────────────────────────────────────────
    if is_defend_mode; then
        log "DEFEND MODE: current_best.aggregate <= win_target — running validation only"
        emit_event "defend_mode_active" "iteration=$ITER_NUM"
        if [ "$DRY_RUN" -eq 0 ]; then
            "$GATE_SCRIPT" --branch main --run-id "${RUN_ID}-defend" --dry-run || true
            state_set "loop_phase" "sleeping"
        fi
        log "Defend-mode iteration complete."
        return 0
    fi

    WORK_DIR="$(mktemp -d)"
    trap 'rm -rf "$WORK_DIR"' EXIT

    # Build the iteration brief from template (best-effort substitution).
    ITER_BRIEF="$WORK_DIR/iter-brief.md"
    CODE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
    CLOSED_SUMMARY="$(grep -A0 '^### ' "$CLOSED_LEDGER" 2>/dev/null | sed 's/^### /- CLOSED: /' || true)"
    if [ -f "$ITER_BRIEF_TEMPLATE" ]; then
        python3 - "$ITER_BRIEF_TEMPLATE" "$ITER_BRIEF" \
            "$ITER_NUM" "$(date -u '+%Y-%m-%d')" "${MAIN_BASELINE:-unknown}" \
            "$CODE_SHA" "$CLOSED_SUMMARY" <<'PYEOF'
import sys
tmpl, out, iter_num, date, baseline, code_sha, closed = sys.argv[1:8]
t = open(tmpl, encoding="utf-8").read()
repl = {
    "{{ITERATION_ID}}": f"iter-{int(iter_num):04d}",
    "{{DATE}}": date,
    "{{VENDOR_SLOT}}": "your assigned vendor slot",
    "{{CURRENT_SCHEME}}": "BwtEntropy",
    "{{CURRENT_AGGREGATE}}": "0.299337 (full 10-file corpus)",
    "{{DELTA_VS_T4}}": "-14.1% rel on the 7-file subset",
    "{{VS_GZIP}}": "behind gzip (target: beat it)",
    "{{VS_XZ}}": "behind xz",
    "{{WIN_TARGET_GZIP}}": "0.159674",
    "{{CODE_SHA}}": code_sha,
    "{{CORPUS_MANIFEST_SHA256}}": "8e6cf6a743d0ff58f7666484006392029cd04c0fb7f86ec99cdc0a66a186f2b3",
    "{{CLOSED_BRANCHES_SUMMARY}}": closed or "(see consilium/closed-branches.md)",
}
for k, v in repl.items():
    t = t.replace(k, v)
open(out, "w", encoding="utf-8").write(t)
PYEOF
    else
        cat > "$ITER_BRIEF" <<BRIEF
# Cubrim Research Iteration ${ITER_NUM}
Current baseline: ${MAIN_BASELINE:-unknown}
Propose ONE compression improvement to $DEFAULT_TARGET_FILE that beats
the BWT leader and passes the AC-5 gate chain.
BRIEF
    fi

    # Strong machine-readable output contract appended to the brief so workers
    # return a parseable JSON proposal (in addition to the prose PROPOSAL block).
    cat >> "$ITER_BRIEF" <<'CONTRACT'

---

## MACHINE OUTPUT (REQUIRED)

CLOSED branches (auto-rejected): distance-map / content-derived phi, N-sweep on
the T4 stream, order-2 (and higher) context fallback chains, dedicated RLE
pre-pass, AND external-address / global-snapshot lookup (any universal
fixed-width reference into an external store — refuted by information
conservation / pigeonhole; an uncharged dictionary or external server is an
auto-reject). Do NOT propose any of these. LIVE directions worth proposing:
block BWT with separate sub-block Huffman tables, arithmetic / range coding
replacing Huffman (fractional-bit savings), PPM on the value-code stream,
order-1 context-mixing of order-1 and order-0 predictions with learned weights.
NOTE: corpus-local / shared-dictionary deduplication (content-defined chunking
across the corpus) was probed on the frozen corpus and is NO-GO here —
cross-file redundancy measured ~0% (the 10 files share no content); do NOT
propose inter-file dedup on this corpus.

After your prose, emit EXACTLY ONE fenced JSON block (```json ... ```) with
this schema and nothing else inside it:

{
  "candidate_name": "<short-id>",
  "target_file": "code/cubrim-rs/src/codec.rs",
  "mechanism": "<one paragraph: what it does and why H(compressed) drops>",
  "decoder_branches": ["<branch1+cost>", "<branch2+cost>"],
  "gotcha_self_checks": {"g3":"yes|no","g6":"yes|no","g7":"yes|no"},
  "closed_branch_check": "<does this match any CLOSED branch? quote it or 'none'>",
  "predicted_verdict": "GO|NO-GO + one sentence"
}
CONTRACT

    # ── Phase 2: docker-native consilium fanout ──────────────────────────────
    log "Phase 2: consilium fanout to live docker workers"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY-RUN] would discover workers (label=$WORKER_LABEL) and brief them"
        log "[DRY-RUN] workers currently UP: $(discover_workers | tr '\n' ' ')"
        emit_event "consilium_fanout_dry_run"
    fi

    PROPOSALS_JSONL="$WORK_DIR/proposals.jsonl"
    : > "$PROPOSALS_JSONL"

    SYS_PROMPT="$WORK_DIR/sys.txt"
    cat > "$SYS_PROMPT" <<'SYS'
You are a compression-research vendor on a multi-vendor consilium. You propose
ONE novel, round-trip-correct improvement to the Cubrim lossless archiver.
Honour the Gotcha checklist and the closed-branch ledger in the brief: a
proposal matching a CLOSED branch is auto-rejected. Be concise. End with the
required fenced JSON block exactly as specified.
SYS

    RESPONDERS=0
    if [ "$DRY_RUN" -eq 0 ]; then
        WORKERS="$(discover_workers)"
        [ -n "$WORKERS" ] || { log "no workers discovered — aborting iteration"; emit_event "iteration_abort" "reason=no_workers"; state_set "loop_phase" "sleeping"; return 0; }
        log "discovered workers: $(echo "$WORKERS" | tr '\n' ' ')"

        while IFS= read -r w; do
            [ -n "$w" ] || continue
            log "  briefing $w ..."
            RESP="$WORK_DIR/resp-$w.txt"
            if worker_chat "$w" "$SYS_PROMPT" "$ITER_BRIEF" "$RESP"; then
                PJSON="$WORK_DIR/prop-$w.json"
                if extract_json "$RESP" > "$PJSON" 2>/dev/null && [ -s "$PJSON" ]; then
                    MODEL="$(worker_env "$w" ANTHROPIC_MODEL)"
                    jq -cn --arg slot "$w" --arg model "$MODEL" \
                        --slurpfile p "$PJSON" \
                        '{slot:$slot, model:$model, proposal_json:$p[0]}' \
                        >> "$PROPOSALS_JSONL"
                    RESPONDERS=$(( RESPONDERS + 1 ))
                    local_name="$(jq -r '.candidate_name // "?"' "$PJSON")"
                    log "  [$w] proposal accepted: $local_name"
                else
                    log "  [$w] response had no parseable JSON proposal — dropped"
                fi
            fi
        done <<< "$WORKERS"
    fi

    log "fanout complete: $RESPONDERS responding worker(s)"
    emit_event "consilium_fanout_complete" "responders=$RESPONDERS"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "[DRY-RUN] skipping judge / arbiter / implementation / rail"
        state_set "loop_phase" "sleeping"
        log "Dry-run iteration complete. No model calls, no branches."
        return 0
    fi

    if [ "$RESPONDERS" -lt "$WORKER_MIN" ]; then
        log "fewer than $WORKER_MIN responders ($RESPONDERS) — below consilium minimum, aborting cleanly"
        emit_event "iteration_abort" "reason=insufficient_responders" "responders=$RESPONDERS"
        state_set "loop_phase" "sleeping"
        return 0
    fi
    if [ "$RESPONDERS" -lt 3 ]; then
        log "DEGRADED: only $RESPONDERS/3 workers responded (proceeding — likely a worker rate-limited)"
        emit_event "consilium_degraded" "responders=$RESPONDERS"
    fi

    # ── Phase 3: deterministic judge ─────────────────────────────────────────
    log "Phase 3: judge (closed-branch reject + deterministic scoring)"
    state_set "loop_phase" "arbiter"

    SELECTED_JSON="$WORK_DIR/selected.json"
    set +e
    python3 - "$PROPOSALS_JSONL" "$CLOSED_LEDGER" "$SELECTED_JSON" <<'PYEOF'
import sys, json, re
proposals_path, ledger_path, out_path = sys.argv[1:4]

props = []
for line in open(proposals_path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        props.append(json.loads(line))
    except Exception:
        continue

# Closed-branch phrases drawn from the ledger CLOSED auto-reject triggers.
# Multi-word phrases (not single tokens) so incidental prose mentions of a term
# that ALSO appears in a LIVE direction (e.g. "context" is LIVE context-mixing)
# do not over-reject. These match the ledger's "Auto-reject trigger" wording.
ledger = open(ledger_path, encoding="utf-8").read().lower()
closed_phrases = [
    "distance-map", "content-derived phi", "content-derived φ",
    "coordinate-storing", "transmit a permutation", "transmitted permutation",
    "sorted-value placement", "stored mapping", "phi-map", "φ-map",
    "sweep n", "n-sweep", "vary n", "varying n",
    "order-2 context", "order-3", "order-k", "higher-order context fallback",
    "rle pre-pass", "rle prepass", "dedicated rle pass",
    # naive external-address / global-snapshot lookup (info-conservation CLOSED).
    # Phrases are specific to the universal-reference form so the LIVE
    # "charged shared dictionary" dedup branch is NOT over-rejected.
    "external server", "external store", "external library", "global snapshot",
    "snapshot library", "universal reference", "16-byte reference",
    "fixed-width reference", "global address", "server id", "fetch the snapshot",
    "uncharged dictionary", "dictionary not charged",
    # inter-file dedup CLOSED on the frozen corpus (cross-file redundancy ~0).
    "inter-file dedup", "cross-file dedup", "shared dictionary",
    "content-defined chunking", "chunk reference", "deduplication across",
]

def is_closed(p):
    cbc = str(p.get("closed_branch_check", "")).lower().strip()
    # 1. Trust the worker's self-declaration first.
    if cbc and cbc not in ("none", "no", "n/a", "no.", ""):
        if "closed" in cbc or "yes" in cbc[:6] or any(k in cbc for k in closed_phrases):
            return True, f"self-declared: {cbc[:80]}"
    # 2. Otherwise match closed PHRASES in name + mechanism.
    hay = (str(p.get("candidate_name", "")) + " " + str(p.get("mechanism", ""))).lower()
    for k in closed_phrases:
        if k in hay:
            return True, f"matches closed phrase '{k}'"
    return False, ""

def score(p):
    s = 0.0
    pv = str(p.get("predicted_verdict", "")).upper()
    if pv.startswith("GO"):
        s += 3.0
    g = p.get("gotcha_self_checks", {}) or {}
    # g3/g7 "yes" means it sorts-by-phi / transmits a map → auto-NO-GO traps.
    if str(g.get("g3", "")).lower().startswith("n"):
        s += 1.0
    if str(g.get("g7", "")).lower().startswith("n"):
        s += 1.0
    if str(g.get("g6", "")).lower().startswith("n") or str(g.get("g6","")).lower().startswith("y"):
        s += 0.5  # has an answer
    tf = str(p.get("target_file", ""))
    if tf.endswith("codec.rs"):
        s += 1.0
    br = p.get("decoder_branches", [])
    if isinstance(br, list) and len(br) >= 1:
        s += 0.5
    if p.get("candidate_name"):
        s += 0.5
    return s

eligible = []
for entry in props:
    p = entry.get("proposal_json", entry)
    closed, why = is_closed(p)
    if closed:
        print(f"judge: REJECT {entry.get('slot','?')} ({p.get('candidate_name','?')}): {why}", file=sys.stderr)
        continue
    eligible.append((score(p), entry))

if not eligible:
    print("judge: no eligible proposals after closed-branch filtering", file=sys.stderr)
    sys.exit(3)

eligible.sort(key=lambda t: t[0], reverse=True)
best_score, best = eligible[0]
sel = best.get("proposal_json", best)
sel["_selected_from_slot"] = best.get("slot")
sel["_selected_model"] = best.get("model")
sel["_judge_score"] = best_score
json.dump(sel, open(out_path, "w"))
print(f"judge: selected '{sel.get('candidate_name','?')}' from {best.get('slot')} (score {best_score})", file=sys.stderr)
sys.exit(0)
PYEOF
    JUDGE_RC=$?
    set -e

    if [ "$JUDGE_RC" -ne 0 ] || [ ! -s "$SELECTED_JSON" ]; then
        log "judge: no eligible proposal (all closed-branch or empty) — clean NO-GO, no branch created"
        emit_event "iteration_abort" "reason=no_eligible_proposal"
        state_set "loop_phase" "sleeping"
        return 0
    fi

    SELECTED_NAME="$(jq -r '.candidate_name // "candidate"' "$SELECTED_JSON")"
    SELECTED_SLOT="$(jq -r '._selected_from_slot // "?"' "$SELECTED_JSON")"
    TARGET_FILE="$(jq -r '.target_file // empty' "$SELECTED_JSON")"
    [ -n "$TARGET_FILE" ] || TARGET_FILE="$DEFAULT_TARGET_FILE"
    log "judge selected: $SELECTED_NAME (from $SELECTED_SLOT), target=$TARGET_FILE"
    emit_event "consilium_judge_complete" "selected=$SELECTED_NAME" "slot=$SELECTED_SLOT"

    # ── Phase 4: deterministic arbiter (best-effort pre-filter) ──────────────
    # The arbiter is the cheap pre-filter; the merge rail is the absolute gate.
    # The free-model proposal rarely carries a full size-model JSON, so a missing
    # model is logged and the iteration continues to the rail (which is the real
    # safety gate). Arbiter only HARD-stops on an explicit NO-GO it can compute.
    log "Phase 4: deterministic arbiter (best-effort)"

    SIZE_MODEL_JSON="$WORK_DIR/size-model.json"
    if jq -e '.decoder_branches and .cost_terms' "$SELECTED_JSON" >/dev/null 2>&1; then
        cp "$SELECTED_JSON" "$SIZE_MODEL_JSON"
        if [ -x "$SIZE_MODEL" ]; then
            set +e
            "$SIZE_MODEL" --model-json "$SIZE_MODEL_JSON" 2>&1 | sed 's/^/  [arbiter-size] /'
            ARB_RC=${PIPESTATUS[0]}
            set -e
            if [ "$ARB_RC" -eq 1 ]; then
                log "arbiter size-model NO-GO — discarding before implementation (cheap reject)"
                emit_event "arbiter_fail" "stage=size_model" "candidate=$SELECTED_NAME"
                state_set "loop_phase" "sleeping"
                return 0
            fi
            log "arbiter size-model PASS"
        fi
    else
        log "selected proposal lacks a full size-model JSON — skipping arbiter (rail is the real gate)"
        emit_event "arbiter_skipped" "reason=no_size_model_json"
    fi

    # ── Phase 5: implementation by the orchestrator's authenticated claude ────
    # The selected proposal comes from a FREE worker (Phase 2/3), but the actual
    # code-writing is delegated to the HOST's authenticated `claude` CLI — the
    # operator's personal Claude subscription, logged in on arcana-db. Free models
    # reliably propose ideas yet cannot implement a compilable change in the
    # 3400-line Rust codec; the strong model can. claude edits the files in place
    # with its own Edit/Write/Bash tools.
    log "Phase 5: implementation (orchestrator claude writes the codec edit)"
    state_set "loop_phase" "impl"

    IMPL_BRANCH="feat/iter-${ITER_NUM}-$(date -u '+%Y%m%d')"

    # Create the feature branch from current main.
    git -C "$REPO_ROOT" checkout -q main 2>/dev/null || git -C "$REPO_ROOT" checkout main
    git -C "$REPO_ROOT" branch -D "$IMPL_BRANCH" 2>/dev/null || true
    git -C "$REPO_ROOT" checkout -q -b "$IMPL_BRANCH"
    log "created branch $IMPL_BRANCH"
    emit_event "impl_branch_created" "branch=$IMPL_BRANCH"

    # Confirm the host claude CLI is present (the loop runs on the HOST, where
    # claude is authenticated as root). If it is missing, fail this iteration as a
    # clean NO-GO rather than silently falling back to a free worker.
    if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
        log "host '$CLAUDE_BIN' CLI not found — cannot implement; clean NO-GO"
        emit_event "iteration_complete" "verdict=NO-GO" "reason=claude_cli_missing" "branch=$IMPL_BRANCH"
        git -C "$REPO_ROOT" checkout -q -- . 2>/dev/null || true
        git -C "$REPO_ROOT" checkout -q main
        git -C "$REPO_ROOT" branch -D "$IMPL_BRANCH" 2>/dev/null || true
        state_set "loop_phase" "sleeping"
        return 0
    fi

    # Build the implementation prompt. Hand claude the selected proposal verbatim
    # plus the architectural constraints; let it read the codec itself (cwd =
    # repo root, so its Read/Grep tools see code/cubrim-rs/src/*). The prompt is
    # explicit that the change MUST compile and stay round-trip-correct, and that
    # the competitive selector means a new scheme need only win on SOME files.
    SELECTED_PRETTY="$(jq . "$SELECTED_JSON" 2>/dev/null || cat "$SELECTED_JSON")"
    CLAUDE_PROMPT="$WORK_DIR/claude-impl-prompt.txt"
    cat > "$CLAUDE_PROMPT" <<CPROMPT
You are implementing a single compression-research candidate in the Cubrim
lossless archiver (a Rust workspace; the codec lives at code/cubrim-rs/src/).
Your cwd is the repo root. Use your Read/Grep/Edit/Write/Bash tools directly on
the files. Do NOT ask questions — implement autonomously.

## Selected proposal (chosen by the consilium judge)
${SELECTED_PRETTY}

## Target
Primary file: ${TARGET_FILE}
You MAY also touch code/cubrim-rs/src/config.rs and other code/cubrim-rs/src/*.rs
files as needed, but keep the change SMALL and self-contained. The mechanism
should be expressed as a new or modified ValueScheme variant where that fits the
proposal.

## Hard requirements
1. The change MUST compile: \`cargo build --release\` from code/cubrim-rs must be
   clean (no errors) before you finish. Run it yourself to verify.
2. Round-trip correctness is enforced downstream by a byte-exact decode(encode(x))
   == x gate. A lossy change will be rejected as NO-GO, so keep decode able to
   exactly reconstruct the input. Preserve existing public function signatures and
   existing ValueScheme variants.
3. The encoder uses COMPETITIVE per-file scheme selection (it writes
   min(new_scheme, T4) plus a scheme byte in the header). A new scheme is
   regression-proof: it only needs to WIN on some files, never on all — so favour
   a clean, correct implementation over chasing every file.
4. Make exactly ONE focused attempt. If you determine the proposal cannot be
   implemented as a small COMPILING, round-trip-correct change, REVERT every edit
   you made (leave the tree exactly as you found it) and end your reply with the
   single line: IMPL_RESULT: NO-EDIT
   Otherwise, after \`cargo build --release\` is clean, end your reply with:
   IMPL_RESULT: BUILT
CPROMPT

    # Invoke the host's authenticated claude NON-interactively, cwd = repo root,
    # ONE attempt, bounded wall-clock. -p prints the final result; claude uses its
    # own tools to edit the files. Output is captured for the run log/journal.
    CLAUDE_OUT="$WORK_DIR/claude-impl-out.txt"
    log "invoking host claude (timeout ${CLAUDE_TIMEOUT}s, one attempt) ..."
    emit_event "impl_claude_start" "branch=$IMPL_BRANCH" "candidate=$SELECTED_NAME" "timeout=$CLAUDE_TIMEOUT"
    # The loop runs as root; `--dangerously-skip-permissions` and
    # `--permission-mode bypassPermissions` are both refused under root for
    # security. `acceptEdits` + an explicit --allowedTools allow-list grants the
    # tools claude needs (read codec, edit files, run cargo) without the bypass
    # guard, and stays non-interactive.
    set +e
    ( cd "$REPO_ROOT" && timeout "$CLAUDE_TIMEOUT" "$CLAUDE_BIN" -p "$(cat "$CLAUDE_PROMPT")" \
        --permission-mode acceptEdits \
        --allowedTools "Bash Edit Write Read Grep Glob MultiEdit" ) > "$CLAUDE_OUT" 2>&1
    CLAUDE_RC=$?
    set -e
    # Log the tail of claude's own report (no secrets — it is just its prose).
    log "claude returned (rc=$CLAUDE_RC); tail of its report:"
    tail -n 8 "$CLAUDE_OUT" 2>/dev/null | sed 's/^/  [claude] /' || true
    CLAUDE_VERDICT="$(grep -Eo 'IMPL_RESULT:[[:space:]]*(BUILT|NO-EDIT)' "$CLAUDE_OUT" 2>/dev/null | tail -1 | awk '{print $2}')"
    emit_event "impl_claude_done" "rc=$CLAUDE_RC" "self_verdict=${CLAUDE_VERDICT:-none}"

    # A wall-clock timeout (rc=124) means claude was killed mid-edit: the tree may
    # hold a half-written, non-compiling change. Do NOT attempt to build a torn
    # edit — treat it as a clean NO-GO immediately (revert + discard + continue),
    # never a loop failure. This is a normal outcome for an over-ambitious
    # candidate, not an error.
    if [ "$CLAUDE_RC" -eq 124 ]; then
        log "claude hit the ${CLAUDE_TIMEOUT}s wall-clock timeout — discarding torn edit, clean NO-GO"
        emit_event "iteration_complete" "verdict=NO-GO" "reason=impl_timeout" "branch=$IMPL_BRANCH"
        git -C "$REPO_ROOT" checkout -q -- . 2>/dev/null || true
        git -C "$REPO_ROOT" checkout -q main 2>/dev/null || true
        git -C "$REPO_ROOT" branch -D "$IMPL_BRANCH" 2>/dev/null || true
        state_set "loop_phase" "discarded"
        return 0
    fi

    # The orchestrator is the source of truth for build status — never claude's
    # self-report. Verify with a real build regardless of what claude said.
    BUILD_OK=0
    if git -C "$REPO_ROOT" diff --quiet -- "$REPO_ROOT/code/cubrim-rs" 2>/dev/null \
       && git -C "$REPO_ROOT" diff --cached --quiet -- "$REPO_ROOT/code/cubrim-rs" 2>/dev/null; then
        log "claude made no change under code/cubrim-rs (self-verdict=${CLAUDE_VERDICT:-none}) — clean NO-GO"
    else
        log "claude edited the codec; verifying with cargo build --release"
        BUILD_LOG="$WORK_DIR/build.log"
        set +e
        ( cd "$REPO_ROOT/code/cubrim-rs" && cargo build --release ) > "$BUILD_LOG" 2>&1
        BUILD_RC=$?
        set -e
        if [ "$BUILD_RC" -eq 0 ]; then
            BUILD_OK=1
            log "cargo build --release: clean"
        else
            log "cargo build --release: FAILED — single-attempt budget spent, clean NO-GO"
            log "build error tail:"
            tail -n 20 "$BUILD_LOG" 2>/dev/null | sed 's/^/  [build] /' || true
        fi
    fi

    if [ "$BUILD_OK" -ne 1 ]; then
        log "implementation did not produce a buildable branch — discarding, clean NO-GO"
        emit_event "iteration_complete" "verdict=NO-GO" "reason=build_failed" "branch=$IMPL_BRANCH"
        git -C "$REPO_ROOT" checkout -q -- . 2>/dev/null || true
        git -C "$REPO_ROOT" checkout -q main
        git -C "$REPO_ROOT" branch -D "$IMPL_BRANCH" 2>/dev/null || true
        state_set "loop_phase" "discarded"
        state_set "loop_phase" "sleeping"
        return 0
    fi

    # Commit the candidate source edit on the branch. claude may have touched more
    # than the primary target (e.g. config.rs), so scope the add to the Rust crate
    # source tree (code/cubrim-rs) — this captures every code change while keeping
    # transient bench/STATE artefacts out; the rail checks out + tests this branch.
    git -C "$REPO_ROOT" add -- "$REPO_ROOT/code/cubrim-rs"
    git -C "$REPO_ROOT" commit -q -m "candidate: $SELECTED_NAME ($RUN_ID)" 2>&1 | tail -1 || true
    CAND_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
    log "branch $IMPL_BRANCH built + committed at $CAND_SHA"
    emit_event "impl_branch_ready" "branch=$IMPL_BRANCH" "candidate_sha=$CAND_SHA"
    git -C "$REPO_ROOT" checkout -q main
    state_set "loop_phase" "gate"

    # The rail does `git checkout $BRANCH`, which fails if main's working tree is
    # dirty with conflicting TRACKED changes. The STATE doc (tracked) is mutated
    # by state_set every phase — commit it to main so the tree is clean before the
    # rail switches branches. Untracked/ignored transient files do not block it.
    git -C "$REPO_ROOT" add -- "$(basename "$STATE_DOC")" 2>/dev/null || true
    if ! git -C "$REPO_ROOT" diff --cached --quiet 2>/dev/null; then
        git -C "$REPO_ROOT" commit -q -m "loop: STATE checkpoint before rail ($RUN_ID)" 2>&1 | tail -1 || true
    fi
    # Belt-and-braces: discard any other stray tracked changes on main so the
    # rail's checkout cannot be blocked (never touches the candidate branch).
    git -C "$REPO_ROOT" checkout -q -- . 2>/dev/null || true

    # ── Phase 6: AC-5 merge rail ─────────────────────────────────────────────
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
        log "MERGE RAIL: NO-GO — branch $IMPL_BRANCH discarded by rail (exit $RAIL_EXIT)"
        emit_event "iteration_complete" "verdict=NO-GO" "branch=$IMPL_BRANCH"
        state_set "loop_phase" "discarded"
    fi

    # Always return to main and clean up. On a gate failure the rail checks out
    # the candidate branch then tries to delete it — deleting the *current* branch
    # fails, leaving HEAD on the discarded branch. Force back to main and drop any
    # leftover candidate branch + stray tracked edits so the next iteration starts
    # from a clean main.
    git -C "$REPO_ROOT" checkout -q -f main 2>/dev/null || true
    git -C "$REPO_ROOT" branch -D "$IMPL_BRANCH" 2>/dev/null || true
    git -C "$REPO_ROOT" checkout -q -- . 2>/dev/null || true

    # ── Phase 7: update STATE doc ────────────────────────────────────────────
    log "Phase 7: updating STATE doc"
    state_set "loop_phase" "sleeping"

    log "Iteration $ITER_NUM complete."
}

# ── entrypoint guard ─────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
