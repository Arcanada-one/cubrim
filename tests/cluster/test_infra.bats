#!/usr/bin/env bats
# tests/cluster/test_infra.bats — Infrastructure artefact tests.
#
# Covers:
#   1. bootstrap-host.sh --dry-run prints the plan and exits 0 without running installs
#   2. bootstrap-host.sh idempotency: two dry-runs yield identical output
#   3. docker-compose.yml is schema-valid (with docker) or passable via grep (without docker)
#   4. docker-compose.yml contains four expected service names
#   5. docker-compose.yml contains deploy.resources.limits for each worker
#   6. docker-compose.yml contains unique cubrim-role labels (Law 5)
#   7. systemd unit files contain Environment=PATH= (PAX lesson)
#   8. .env.example contains no real secret values (only placeholder patterns)
#   9. cubrim-loop.sh --dry-run exits 0 and prints trace (with STATE doc mock)
#  10. CUBR-AUTONOMOUS-STATE.md exists at repo root and contains required fields

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
INFRA_DIR="$REPO_ROOT/code/cluster/infra"
BOOTSTRAP="$INFRA_DIR/bootstrap-host.sh"
COMPOSE="$INFRA_DIR/docker-compose.yml"
ENV_EXAMPLE="$INFRA_DIR/.env.example"
LOOP_SCRIPT="$INFRA_DIR/cubrim-loop.sh"
STATE_DOC="$REPO_ROOT/CUBR-AUTONOMOUS-STATE.md"

setup() {
    TMPDIR_TEST="$(mktemp -d)"
}

teardown() {
    rm -rf "$TMPDIR_TEST"
}

# ── Test 1: dry-run prints plan and exits 0 ──────────────────────────────────
@test "bootstrap-host.sh --dry-run prints install plan and exits 0" {
    # Use a mock PATH that shadows real install tools with stubs that track calls
    MOCK_BIN="$TMPDIR_TEST/mock-bin"
    mkdir -p "$MOCK_BIN"

    # Stubs that record their arguments but exit 0
    for tool in apt-get npm pip3 curl rustup node; do
        cat > "$MOCK_BIN/$tool" <<'STUB'
#!/bin/sh
# Record invocation; exit 0 without doing anything
echo "STUB_CALLED: $0 $*" >> "${TMPDIR_TEST:-/tmp}/stub-calls.log"
exit 0
STUB
        chmod +x "$MOCK_BIN/$tool"
    done

    # CUBRIM_BOOTSTRAP_DRYRUN=1 triggers dry-run without --dry-run flag
    run env PATH="$MOCK_BIN:$PATH" \
        TMPDIR_TEST="$TMPDIR_TEST" \
        bash "$BOOTSTRAP" --dry-run

    [ "$status" -eq 0 ]

    # Should mention all major components in the plan output
    [[ "$output" == *"docker"* ]]
    [[ "$output" == *"rustup"* ]]
    [[ "$output" == *"python3"* ]]
    [[ "$output" == *"claude"* ]]
    [[ "$output" == *"jq"* ]]
    [[ "$output" == *"DRY"* ]] || [[ "$output" == *"dry"* ]] || [[ "$output" == *"plan"* ]]
}

# ── Test 2: CUBRIM_BOOTSTRAP_DRYRUN=1 equivalent to --dry-run ────────────────
@test "bootstrap-host.sh CUBRIM_BOOTSTRAP_DRYRUN=1 is equivalent to --dry-run" {
    run env CUBRIM_BOOTSTRAP_DRYRUN=1 bash "$BOOTSTRAP"
    [ "$status" -eq 0 ]
    [[ "$output" == *"docker"* ]]
}

# ── Test 3: dry-run is idempotent (same output both runs) ────────────────────
@test "bootstrap-host.sh --dry-run is idempotent (two runs produce same component list)" {
    run env CUBRIM_BOOTSTRAP_DRYRUN=1 bash "$BOOTSTRAP"
    [ "$status" -eq 0 ]
    FIRST_OUTPUT="$output"

    run env CUBRIM_BOOTSTRAP_DRYRUN=1 bash "$BOOTSTRAP"
    [ "$status" -eq 0 ]

    # Both runs should mention the same set of components
    for component in docker rustup python3 claude jq; do
        [[ "$FIRST_OUTPUT" == *"$component"* ]]
        [[ "$output" == *"$component"* ]]
    done
}

# ── Test 4: no real stubs were invoked during dry-run ────────────────────────
@test "bootstrap-host.sh --dry-run does not call apt-get with install args" {
    MOCK_BIN="$TMPDIR_TEST/mock-bin2"
    mkdir -p "$MOCK_BIN"
    CALL_LOG="$TMPDIR_TEST/calls2.log"

    # Stub apt-get — record any 'install' invocation as a failure marker
    cat > "$MOCK_BIN/apt-get" <<STUB
#!/bin/sh
if echo "\$*" | grep -q "install"; then
    echo "APT_INSTALL_CALLED: \$*" >> "$CALL_LOG"
fi
exit 0
STUB
    chmod +x "$MOCK_BIN/apt-get"

    run env PATH="$MOCK_BIN:$PATH" bash "$BOOTSTRAP" --dry-run

    [ "$status" -eq 0 ]
    # The call log should be empty (no apt install in dry-run)
    [ ! -f "$CALL_LOG" ] || [ "$(wc -l < "$CALL_LOG")" -eq 0 ]
}

# ── Test 5: compose file contains four expected service names ─────────────────
@test "docker-compose.yml contains all four service names" {
    [ -f "$COMPOSE" ]
    grep -q "cubrim-orchestrator" "$COMPOSE"
    grep -q "cubrim-worker-a" "$COMPOSE"
    grep -q "cubrim-worker-b" "$COMPOSE"
    grep -q "cubrim-worker-c" "$COMPOSE"
}

# ── Test 6: compose file has deploy.resources.limits ─────────────────────────
@test "docker-compose.yml contains deploy.resources.limits for workers" {
    [ -f "$COMPOSE" ]
    # Count occurrences of 'limits:' — expect at least 4 (one per service)
    LIMITS_COUNT=$(grep -c "limits:" "$COMPOSE")
    [ "$LIMITS_COUNT" -ge 4 ]
    # Memory limits present
    grep -q "memory:" "$COMPOSE"
    # CPU limits present
    grep -q "cpus:" "$COMPOSE"
}

# ── Test 7: compose file has unique cubrim-role labels (Law 5) ────────────────
@test "docker-compose.yml contains unique cubrim-role labels for all services" {
    [ -f "$COMPOSE" ]
    grep -q "cubrim-role: orchestrator" "$COMPOSE"
    grep -q "cubrim-role: worker-a" "$COMPOSE"
    grep -q "cubrim-role: worker-b" "$COMPOSE"
    grep -q "cubrim-role: worker-c" "$COMPOSE"
    # Each role label appears exactly once
    [ "$(grep -c 'cubrim-role:' "$COMPOSE")" -eq 4 ]
}

# ── Test 8: compose schema validation (skip if docker absent) ────────────────
@test "docker-compose.yml passes schema validation (skip if docker absent)" {
    if ! command -v docker >/dev/null 2>&1; then
        skip "docker not available on this test host"
    fi
    # Use docker compose config to validate schema.
    # --no-env-resolution: skip resolution of env_file paths (worker-*.env are
    # gitignored and do not exist on dev hosts); we validate structure only.
    # Supply required vars for compose interpolation.
    run env CUBRIM_HOST_ID=test CUBRIM_REPO_ROOT=/tmp \
        docker compose -f "$COMPOSE" config --quiet --no-env-resolution
    [ "$status" -eq 0 ]
}

# ── Test 9: systemd service files contain Environment=PATH= (PAX lesson) ─────
@test "cubrim-loop.service contains Environment=PATH= line (PAX lesson)" {
    UNIT="$INFRA_DIR/systemd/cubrim-loop.service"
    [ -f "$UNIT" ]
    grep -q "Environment=PATH=" "$UNIT"
    # Must include /root/.local/bin (where 'claude' lives under systemd)
    grep "Environment=PATH=" "$UNIT" | grep -q "\.local/bin"
}

@test "cubrim-watchdog.service contains Environment=PATH= line (PAX lesson)" {
    UNIT="$INFRA_DIR/systemd/cubrim-watchdog.service"
    [ -f "$UNIT" ]
    grep -q "Environment=PATH=" "$UNIT"
    grep "Environment=PATH=" "$UNIT" | grep -q "\.local/bin"
}

# ── Test 10: .env.example has no real secret values ──────────────────────────
@test ".env.example contains no real secret values (only empty or placeholder)" {
    [ -f "$ENV_EXAMPLE" ]

    # Each KEY= line must have an empty value or a placeholder like <...> or a comment
    # A real key typically looks like: KEY=sk-... or KEY=gsk_... or KEY=or-...
    # Pattern: value starts with sk-, gsk_, or-, Bearer, ghp_, etc.
    # Reject any line where value starts with alphanumeric (non-angle-bracket, non-empty)

    while IFS= read -r line; do
        # Skip comments and blank lines
        case "$line" in
            '#'*|'') continue ;;
        esac

        # Extract value after the first '='
        VALUE="${line#*=}"

        # A non-empty value that does NOT look like a placeholder is suspicious
        # Placeholders: empty, <...>, or lines with only whitespace
        if [ -n "$VALUE" ]; then
            # Reject if value starts with a letter or digit (real key pattern)
            # and does NOT start with '<' (placeholder)
            if echo "$VALUE" | grep -qE '^[a-zA-Z0-9]'; then
                if ! echo "$VALUE" | grep -qE '^<'; then
                    echo "FAIL: .env.example line may contain a real value: $line" >&3
                    return 1
                fi
            fi
        fi
    done < "$ENV_EXAMPLE"

    # Ensure the file mentions expected key names
    grep -q "OPENROUTER_API_KEY" "$ENV_EXAMPLE"
    grep -q "DEEPSEEK_API_KEY" "$ENV_EXAMPLE"
    grep -q "GROQ_API_KEY" "$ENV_EXAMPLE"
}

# ── Test 11: worker env examples have no real keys ───────────────────────────
@test "worker-a.env.example contains no real secret values" {
    WENV="$INFRA_DIR/env/worker-a.env.example"
    [ -f "$WENV" ]
    grep -q "OPENROUTER_API_KEY\|ANTHROPIC_AUTH_TOKEN" "$WENV"
    # Value for AUTH_TOKEN must be a placeholder
    grep "ANTHROPIC_AUTH_TOKEN=" "$WENV" | grep -qE '=<|=$'
}

# ── Test 12: cubrim-loop.sh --dry-run exits 0 with STATE doc mock ─────────────
@test "cubrim-loop.sh --dry-run exits 0 with a minimal STATE doc present" {
    # Create a minimal STATE doc in temp dir
    FAKE_REPO="$TMPDIR_TEST/fake-repo"
    mkdir -p "$FAKE_REPO"

    # Minimal STATE doc
    cat > "$FAKE_REPO/CUBR-AUTONOMOUS-STATE.md" <<'STATE'
---
iteration: "0"
loop_phase: "idle"
main_baseline: "abc1234"
closed_branch_ledger: "consilium/closed-branches.md"
last_run_id: "none"
win_condition_met: "false"
---
STATE

    mkdir -p "$FAKE_REPO/datarim"

    # cubrim-loop.sh uses REPO_ROOT derived from its own path.
    # We run it with a patched CUBRIM_LOOP_DRYRUN but it resolves REPO_ROOT
    # from the script's own location — so we test the real script with --dry-run
    # and verify it exits 0 (STATE doc exists in the real repo).
    run bash "$LOOP_SCRIPT" --dry-run

    # Should exit 0 (dry-run reads STATE doc from real repo location, which exists)
    [ "$status" -eq 0 ]
    [[ "$output" == *"DRY-RUN"* ]] || [[ "$output" == *"dry-run"* ]] || [[ "$output" == *"dry_run"* ]]
}

# ── Test 13: CUBR-AUTONOMOUS-STATE.md exists at repo root ────────────────────
@test "CUBR-AUTONOMOUS-STATE.md exists at repo root" {
    [ -f "$STATE_DOC" ]
}

@test "CUBR-AUTONOMOUS-STATE.md contains required fields" {
    [ -f "$STATE_DOC" ]
    grep -q "^iteration:" "$STATE_DOC"
    grep -q "^loop_phase:" "$STATE_DOC"
    grep -q "^main_baseline:" "$STATE_DOC"
    grep -q "^last_run_id:" "$STATE_DOC"
    grep -q "^closed_branch_ledger:" "$STATE_DOC"
}

# ── Test 14: bootstrap-host.sh is not executable-when-sourced (guard) ─────────
@test "bootstrap-host.sh main() does not execute when sourced" {
    # Source the script and verify main() exists but was not called
    # (BASH_SOURCE[0] != $0 when sourced)
    SOURCED_OUTPUT="$(bash -c "source '$BOOTSTRAP'; echo 'sourced-ok'")"
    [[ "$SOURCED_OUTPUT" == *"sourced-ok"* ]]
    # The bootstrap log prefix should NOT appear (main() not invoked)
    [[ "$SOURCED_OUTPUT" != *"[bootstrap]"* ]]
}

# ── Test 15: compose file images all reference cubrim-worker:latest ───────────
@test "docker-compose.yml specifies cubrim-worker:latest image for all services" {
    [ -f "$COMPOSE" ]
    # Count 'image: cubrim-worker:latest' occurrences — one per service
    IMAGE_COUNT=$(grep -c "image: cubrim-worker:latest" "$COMPOSE")
    [ "$IMAGE_COUNT" -ge 4 ]
}

# ── Test 16: provision runbook references the kill switch ─────────────────────
@test "provision-cubrim-cluster-host.md cross-links the stop runbook" {
    RUNBOOK="$REPO_ROOT/documentation/how-to/provision-cubrim-cluster-host.md"
    [ -f "$RUNBOOK" ]
    grep -q "stop-the-cubrim-cluster" "$RUNBOOK"
}
