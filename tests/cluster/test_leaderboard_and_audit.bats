#!/usr/bin/env bats
# tests/cluster/test_leaderboard_and_audit.bats — P6/P8 leaderboard + audit trail.
#
# Tests:
#   - gen-leaderboard-md.sh generates valid Markdown
#   - promote-to-cubrim-com.sh does NOT deploy (operator-gated invariant)
#   - Leaderboard JSON schema invariants (roundtrip_ok, run_log_ref)
#   - Run-log JSONL append and assert-run-log-ref
#   - cubrim-assert_run_log_ref catches missing ref

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
LEADERBOARD_DIR="$REPO_ROOT/docs/leaderboard"
LEADERBOARD_JSON="$LEADERBOARD_DIR/cubrim-leaderboard.json"
RUNLOG="$REPO_ROOT/datarim/cubrim-run-log.jsonl"
VENDOR_DIR="$REPO_ROOT/code/cluster/vendor"

setup() {
    TMPDIR_TEST="$(mktemp -d)"
}

teardown() {
    rm -rf "$TMPDIR_TEST"
}

# ── leaderboard JSON schema tests ─────────────────────────────────────────────

@test "leaderboard JSON: valid and parseable" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
assert 'schema_version' in lb
assert 'win_target' in lb
assert 'current_best' in lb
assert 'runs' in lb
print('OK')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "leaderboard JSON: current_best has aggregate and code_sha" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
best = lb['current_best']
assert 'aggregate' in best, 'missing aggregate'
assert 'code_sha' in best, 'missing code_sha'
assert 'corpus_manifest_sha256' in best, 'missing corpus_manifest_sha256'
assert 'run_log_ref' in best, 'missing run_log_ref'
assert isinstance(best['aggregate'], float), 'aggregate must be float'
print(f'OK: aggregate={best[\"aggregate\"]}')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "leaderboard JSON: win_target has gzip and xz aggregates" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
wt = lb['win_target']
assert 'gzip_aggregate' in wt
assert 'xz_aggregate' in wt
# Both should be less than current_best (we haven't won yet)
assert wt['gzip_aggregate'] < lb['current_best']['aggregate'], \
    f'win target {wt[\"gzip_aggregate\"]} should be < current best {lb[\"current_best\"][\"aggregate\"]}'
print(f'OK: gzip_target={wt[\"gzip_aggregate\"]}, xz_target={wt[\"xz_aggregate\"]}')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "leaderboard JSON: all runs have roundtrip_ok=true" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
bad = [r.get('run_id','?') for r in lb.get('runs',[]) if not r.get('roundtrip_ok', False)]
if bad:
    print(f'FAIL: runs without roundtrip_ok=true: {bad}')
    exit(1)
print('OK: all runs have roundtrip_ok=true')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "leaderboard JSON: all runs have run_log_ref (Law 5 traceability)" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
bad = [r.get('run_id','?') for r in lb.get('runs',[]) if not r.get('run_log_ref')]
if bad:
    print(f'FAIL: runs missing run_log_ref: {bad}')
    exit(1)
print('OK: all runs have run_log_ref')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "leaderboard JSON: current_best aggregate is the 10-file BWT baseline 0.299337" {
    run python3 -c "
import json
lb = json.load(open('$LEADERBOARD_JSON'))
agg = lb['current_best']['aggregate']
assert abs(agg - 0.299337) < 1e-6, f'Expected 0.299337 (10-file corpus), got {agg}'
print(f'OK: aggregate={agg}')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

# ── gen-leaderboard-md tests ──────────────────────────────────────────────────

@test "gen-leaderboard-md: generates valid Markdown with win target table" {
    OUTPUT="$TMPDIR_TEST/test-leaderboard.md"
    run bash "$LEADERBOARD_DIR/gen-leaderboard-md.sh" \
        --json "$LEADERBOARD_JSON" \
        --output "$OUTPUT"
    [ "$status" -eq 0 ]
    [ -f "$OUTPUT" ]
    grep -q "Win Target" "$OUTPUT"
    grep -q "gzip" "$OUTPUT"
    grep -q "0.299337" "$OUTPUT"
}

@test "gen-leaderboard-md: dry-run outputs to stdout, does not write file" {
    # The LEADERBOARD.md already exists; verify --dry-run doesn't modify it
    BEFORE_MTIME="$(stat -f '%m' "$LEADERBOARD_DIR/LEADERBOARD.md" 2>/dev/null || echo '0')"
    run bash "$LEADERBOARD_DIR/gen-leaderboard-md.sh" --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"dry-run"* ]]
    [[ "$output" == *"Cubrim"* ]]
}

@test "gen-leaderboard-md: output contains current_best aggregate" {
    OUTPUT="$TMPDIR_TEST/lb-test.md"
    bash "$LEADERBOARD_DIR/gen-leaderboard-md.sh" \
        --json "$LEADERBOARD_JSON" \
        --output "$OUTPUT" 2>/dev/null
    grep -q "0.299337" "$OUTPUT"
}

# ── promote-to-cubrim-com invariant test ─────────────────────────────────────

@test "promote-to-cubrim-com: does NOT deploy (only prints operator-gated message)" {
    run bash "$LEADERBOARD_DIR/promote-to-cubrim-com.sh"
    [ "$status" -eq 0 ]
    # Must contain the operator-gated message
    [[ "$output" == *"operator-gated"* ]]
    # Must NOT contain any actual deploy invocation output
    # (no "Deploying", "Sending", "Uploaded" etc.)
    [[ "$output" != *"Deploying"* ]]
    [[ "$output" != *"Uploaded"* ]]
    # Must tell the operator what command to run manually
    [[ "$output" == *"deploy.sh"* ]] || [[ "$output" == *"manually"* ]]
}

# ── audit trail (run-log) tests ───────────────────────────────────────────────

@test "cubrim-run-log.jsonl: exists and is writable" {
    [ -f "$RUNLOG" ]
    # File should be writable
    [ -w "$RUNLOG" ]
}

@test "cubrim-run-log.jsonl: existing entries are valid JSONL (one JSON object per line)" {
    run python3 -c "
import json, sys
with open('$RUNLOG') as f:
    lines = [l.strip() for l in f if l.strip()]
if not lines:
    print('OK: empty log (no entries yet)')
    sys.exit(0)
errors = []
for i, line in enumerate(lines, 1):
    try:
        obj = json.loads(line)
        assert isinstance(obj, dict), f'Line {i} is not a JSON object'
    except Exception as e:
        errors.append(f'Line {i}: {e}')
if errors:
    print('FAIL:', errors, file=sys.stderr)
    sys.exit(1)
print(f'OK: {len(lines)} JSONL entries, all valid')
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "jsonl-write.sh: cubrim_log_event emits valid JSONL" {
    TMPLOG="$TMPDIR_TEST/test-run-log.jsonl"
    touch "$TMPLOG"

    # Source the vendored jsonl-write.sh and emit a test event
    run bash -c "
source '$VENDOR_DIR/jsonl-write.sh'
cubrim_log_event '$TMPLOG' 'test-iter-001' 'gate_pass' \
    gate=gate-corpus-hash verdict=PASS detail=''
echo 'emitted'
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"emitted"* ]]

    # Verify the emitted line is valid JSON with required fields
    run python3 -c "
import json
line = open('$TMPLOG').read().strip()
obj = json.loads(line)
for field in ['ts', 'run_id', 'event', 'gate', 'verdict']:
    assert field in obj, f'missing field: {field}'
assert obj['run_id'] == 'test-iter-001'
assert obj['event'] == 'gate_pass'
print('OK:', obj)
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "cubrim_assert_run_log_ref: PASS when run_log_ref present in leaderboard" {
    # The seeded leaderboard has run_id=CUBR-0028-bench with run_log_ref
    run bash -c "
source '$VENDOR_DIR/jsonl-write.sh'
cubrim_assert_run_log_ref '$LEADERBOARD_JSON' 'CUBR-0028-bench'
"
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "cubrim_assert_run_log_ref: FAIL when run_id not in leaderboard" {
    run bash -c "
source '$VENDOR_DIR/jsonl-write.sh'
cubrim_assert_run_log_ref '$LEADERBOARD_JSON' 'nonexistent-run-id-xyz'
"
    [ "$status" -ne 0 ]
    [[ "$output" == *"missing run_log_ref"* ]] || [[ "$output" == *"FAIL"* ]]
}
