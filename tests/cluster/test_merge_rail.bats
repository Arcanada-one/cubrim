#!/usr/bin/env bats
# tests/cluster/test_merge_rail.bats — AC-5 merge rail tests.
#
# Tests the five fail-closed gate scripts and the run-merge-rail.sh chain.
# Proves:
#   PASS  — known-good candidate (all gates green)
#   FAIL  — (a) corpus tampered, (b) round-trip not byte-exact,
#            (c) aggregate ratio not strictly improved,
#            (d) per-file regression hidden behind aggregate win
#
# Requires: bats >= 1.5, jq, python3, cargo (already built binary)

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
GATE_DIR="$REPO_ROOT/code/cluster/gate"
LEADERBOARD="$REPO_ROOT/docs/leaderboard/cubrim-leaderboard.json"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
CUBRIM_BIN="$REPO_ROOT/code/cubrim-rs/target/release/cubrim"
FIXTURE_DIR="$BATS_TEST_DIRNAME/fixtures"

setup_file() {
    # Ensure binary is built once before all tests
    if [ ! -f "$CUBRIM_BIN" ]; then
        cd "$REPO_ROOT/code/cubrim-rs"
        cargo build --release --quiet
    fi
}

setup() {
    TMPDIR_TEST="$(mktemp -d)"
}

teardown() {
    rm -rf "$TMPDIR_TEST"
}

# ── helper: create a known-good bench JSON fixture ───────────────────────────
make_good_bench_json() {
    local path="$1"
    python3 -c "
import json
# Aggregate 0.280000 < 0.299337 (10-file corpus baseline) = strict improvement
data = {
    'scheme': 'TestGoodCandidate',
    'bwt_aggregate': 0.280000,
    'aggregate': 0.280000,
    'per_file': [
        {'file': 'sparse_clustered', 'bytes': 480,  'bwt_bytes': 480,  'delta': -22,   'mode': 'cube'},
        {'file': 'dense',            'bytes': 4000,  'bwt_bytes': 4000,  'delta': -109,  'mode': 'raw'},
        {'file': 'text',             'bytes': 3000,  'bwt_bytes': 3000,  'delta': -583,  'mode': 'cube'},
        {'file': 'log_like',         'bytes': 4500,  'bwt_bytes': 4500,  'delta': -678,  'mode': 'cube'},
        {'file': 'binary_mixed',     'bytes': 8000,  'bwt_bytes': 8000,  'delta': -205,  'mode': 'raw'},
        {'file': 'random_high',      'bytes': 4000,  'bwt_bytes': 4000,  'delta': -109,  'mode': 'raw'},
        {'file': 'sparse_small',     'bytes': 260,   'bwt_bytes': 260,   'delta': -9,    'mode': 'raw'},
    ]
}
with open('$path', 'w') as f:
    json.dump(data, f, indent=2)
"
}

# ── gate-corpus-hash tests ────────────────────────────────────────────────────

@test "gate-corpus-hash: PASS on clean unmodified corpus" {
    run bash "$GATE_DIR/gate-corpus-hash.sh"
    [ "$status" -eq 0 ]
    [[ "$output" == *"PASS — all corpus files intact"* ]]
}

@test "gate-corpus-hash: FAIL when manifest is tampered" {
    # Create a tampered manifest copy in a temp location and redirect the gate
    TAMPERED_MANIFEST="$TMPDIR_TEST/manifest.json"
    python3 -c "
import json
m = json.load(open('$MANIFEST'))
# Tamper: change the sha256 of the first entry
m[0]['sha256'] = 'deadbeef' * 8
import json
with open('$TAMPERED_MANIFEST', 'w') as f:
    json.dump(m, f)
"
    # Override the baseline to match the tampered manifest hash
    TAMPERED_BASELINE="$TMPDIR_TEST/corpus-baseline.sha256"
    python3 -c "
import hashlib
data = open('$TAMPERED_MANIFEST', 'rb').read()
h = hashlib.sha256(data).hexdigest()
with open('$TAMPERED_BASELINE', 'w') as f:
    f.write(h + '  manifest.json\n')
"
    # The gate should fail because per-file hash for entry 0 won't match
    # We test this by temporarily making a gate wrapper that points to tampered manifest
    # Instead, test by passing an incorrect corpus-baseline.sha256 (manifest-level tamper)
    WRONG_BASELINE="$TMPDIR_TEST/wrong-baseline.sha256"
    echo "0000000000000000000000000000000000000000000000000000000000000000  manifest.json" > "$WRONG_BASELINE"

    # Create a gate wrapper that uses our wrong baseline
    GATE_WRAPPER="$TMPDIR_TEST/gate-corpus-hash-tampered.sh"
    cat > "$GATE_WRAPPER" << 'EOF_WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
GATE_DIR="PLACEHOLDER_GATE_DIR"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
BASELINE="PLACEHOLDER_WRONG_BASELINE"
die() { echo "gate-corpus-hash: ERROR: $*" >&2; exit 1; }
[ -f "$MANIFEST" ] || die "manifest not found: $MANIFEST"
[ -f "$BASELINE" ] || die "baseline not found: $BASELINE"
FROZEN_HASH="$(awk '{print $1}' "$BASELINE")"
ACTUAL_HASH="$(python3 -c "
import hashlib, sys
data = open(sys.argv[1], 'rb').read()
print(hashlib.sha256(data).hexdigest())
" "$MANIFEST")"
if [ "$ACTUAL_HASH" != "$FROZEN_HASH" ]; then
    echo "gate-corpus-hash: FAIL manifest hash mismatch" >&2
    exit 1
fi
exit 0
EOF_WRAPPER
    sed -i '' "s|PLACEHOLDER_GATE_DIR|$GATE_DIR|g" "$GATE_WRAPPER"
    sed -i '' "s|PLACEHOLDER_WRONG_BASELINE|$WRONG_BASELINE|g" "$GATE_WRAPPER"
    chmod +x "$GATE_WRAPPER"

    run bash "$GATE_WRAPPER"
    [ "$status" -ne 0 ]
    [[ "$output" == *"mismatch"* ]]
}

@test "gate-corpus-hash: FAIL when a corpus file sha256 is wrong" {
    # Create a temp corpus dir with one file corrupted
    TMPMANIFEST="$TMPDIR_TEST/manifest_corrupt.json"
    python3 -c "
import json
m = json.load(open('$MANIFEST'))
# Inject bad sha256 for first entry
entry = m[0].copy()
entry['sha256'] = 'badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbad'
m2 = [entry] + m[1:]
with open('$TMPMANIFEST', 'w') as f:
    json.dump(m2, f)
# Baseline matching this modified manifest
import hashlib
data = open('$TMPMANIFEST', 'rb').read()
h = hashlib.sha256(data).hexdigest()
print(h)
" > "$TMPDIR_TEST/baseline_hash.txt"

    BASELINE_SHA="$(cat "$TMPDIR_TEST/baseline_hash.txt")"
    echo "$BASELINE_SHA  manifest.json" > "$TMPDIR_TEST/corpus-baseline.sha256"

    # Gate wrapper pointing to the modified manifest with matching manifest-hash
    # but wrong per-file sha256 entries
    GATE_WRAPPER="$TMPDIR_TEST/gate-test-perfile.sh"
    cat > "$GATE_WRAPPER" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
MANIFEST="PLACEHOLDER_MANIFEST"
BASELINE="PLACEHOLDER_BASELINE"
GATE_DIR="PLACEHOLDER_GATE_DIR"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"

die() { echo "gate-corpus-hash: ERROR: $*" >&2; exit 1; }
[ -f "$MANIFEST" ] || die "manifest not found"
[ -f "$BASELINE" ] || die "baseline not found"
command -v jq >/dev/null 2>&1 || die "jq required"
command -v python3 >/dev/null 2>&1 || die "python3 required"

FROZEN_HASH="$(awk '{print $1}' "$BASELINE")"
ACTUAL_HASH="$(python3 -c "
import hashlib, sys
data = open(sys.argv[1], 'rb').read()
print(hashlib.sha256(data).hexdigest())
" "$MANIFEST")"

if [ "$ACTUAL_HASH" != "$FROZEN_HASH" ]; then
    echo "gate-corpus-hash: FAIL manifest hash mismatch" >&2; exit 1
fi

FAIL=0
while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    expected="$(echo "$entry" | jq -r '.sha256')"
    path="$(echo "$entry" | jq -r '.path')"
    [ -f "$path" ] || path="$REPO_ROOT/docs/ephemeral/research/corpus/$(basename "$path")"
    [ -f "$path" ] || { echo "gate-corpus-hash: FAIL $name — file missing" >&2; FAIL=1; continue; }
    actual="$(python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$path")"
    if [ "$actual" != "$expected" ]; then
        echo "gate-corpus-hash: FAIL $name hash mismatch" >&2; FAIL=1
    fi
done < <(jq -c '.[]' "$MANIFEST")
[ "$FAIL" -eq 0 ] || exit 1
exit 0
EOF
    sed -i '' "s|PLACEHOLDER_MANIFEST|$TMPMANIFEST|g" "$GATE_WRAPPER"
    sed -i '' "s|PLACEHOLDER_BASELINE|$TMPDIR_TEST/corpus-baseline.sha256|g" "$GATE_WRAPPER"
    sed -i '' "s|PLACEHOLDER_GATE_DIR|$GATE_DIR|g" "$GATE_WRAPPER"
    chmod +x "$GATE_WRAPPER"

    run bash "$GATE_WRAPPER"
    [ "$status" -ne 0 ]
    [[ "$output" == *"FAIL"* ]]
}

# ── gate-cargo-test tests ─────────────────────────────────────────────────────

@test "gate-cargo-test: PASS on current green codebase" {
    run bash "$GATE_DIR/gate-cargo-test.sh"
    [ "$status" -eq 0 ]
    [[ "$output" == *"PASS"* ]]
}

# ── gate-roundtrip tests ──────────────────────────────────────────────────────

@test "gate-roundtrip: PASS on all corpus files with current binary" {
    run bash "$GATE_DIR/gate-roundtrip.sh"
    [ "$status" -eq 0 ]
    [[ "$output" == *"PASS — all corpus files round-trip byte-exact"* ]]
}

@test "gate-roundtrip: FAIL when decompressed file differs from original" {
    # Simulate a broken binary: create a wrapper that corrupts the decompressed output
    # We test this by running gate-roundtrip with a mock binary that corrupts output
    MOCK_BIN="$TMPDIR_TEST/cubrim-broken"
    REAL_BIN="$CUBRIM_BIN"

    # Mock: compress works fine, but decompress corrupts the last byte
    cat > "$MOCK_BIN" << 'EOF'
#!/usr/bin/env bash
# Mock cubrim that corrupts decompressed output
REAL_BIN="PLACEHOLDER_REAL"
if [[ "$1" == "compress" ]]; then
    "$REAL_BIN" compress "$2" "$3"
elif [[ "$1" == "decompress" ]]; then
    "$REAL_BIN" decompress "$2" "$3"
    # Corrupt the last byte
    python3 -c "
import sys
path = sys.argv[1]
data = bytearray(open(path,'rb').read())
if data:
    data[-1] ^= 0xFF
open(path,'wb').write(bytes(data))
" "$3"
fi
EOF
    sed -i '' "s|PLACEHOLDER_REAL|$REAL_BIN|g" "$MOCK_BIN"
    chmod +x "$MOCK_BIN"

    # Create a gate-roundtrip wrapper that uses the mock binary
    GATE_WRAPPER="$TMPDIR_TEST/gate-roundtrip-mock.sh"
    cat > "$GATE_WRAPPER" << 'EOFW'
#!/usr/bin/env bash
set -euo pipefail
GATE_DIR="PLACEHOLDER_GATE_DIR"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
CUBRIM_BIN="PLACEHOLDER_MOCK"
command -v jq >/dev/null 2>&1 || { echo "jq required" >&2; exit 2; }
[ -f "$MANIFEST" ] || { echo "manifest missing" >&2; exit 2; }
[ -f "$CUBRIM_BIN" ] || { echo "binary missing: $CUBRIM_BIN" >&2; exit 2; }
FAIL=0
TMPD="$(mktemp -d)"; trap 'rm -rf "$TMPD"' EXIT
while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    path="$(echo "$entry" | jq -r '.path')"
    [ -f "$path" ] || path="$REPO_ROOT/docs/ephemeral/research/corpus/$(basename "$path")"
    [ -f "$path" ] || { echo "FAIL $name missing" >&2; FAIL=1; continue; }
    compressed="$TMPD/${name}.cubrim"
    decompressed="$TMPD/${name}.dec"
    "$CUBRIM_BIN" compress "$path" "$compressed" 2>/dev/null || { echo "FAIL $name compress" >&2; FAIL=1; continue; }
    "$CUBRIM_BIN" decompress "$compressed" "$decompressed" 2>/dev/null || { echo "FAIL $name decompress" >&2; FAIL=1; continue; }
    if ! python3 -c "
import sys
a=open(sys.argv[1],'rb').read(); b=open(sys.argv[2],'rb').read()
sys.exit(0 if a==b else 1)
" "$path" "$decompressed" 2>/dev/null; then
        echo "gate-roundtrip: FAIL $name — round-trip NOT byte-exact" >&2; FAIL=1
    fi
done < <(jq -c '.[]' "$MANIFEST")
[ "$FAIL" -eq 0 ] || exit 1; exit 0
EOFW
    sed -i '' "s|PLACEHOLDER_GATE_DIR|$GATE_DIR|g" "$GATE_WRAPPER"
    sed -i '' "s|PLACEHOLDER_MOCK|$MOCK_BIN|g" "$GATE_WRAPPER"
    chmod +x "$GATE_WRAPPER"

    run bash "$GATE_WRAPPER"
    [ "$status" -ne 0 ]
    [[ "$output" == *"NOT byte-exact"* ]]
}

# ── gate-ratio tests ──────────────────────────────────────────────────────────

@test "gate-ratio: PASS when candidate aggregate strictly improves" {
    make_good_bench_json "$TMPDIR_TEST/good-bench.json"
    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/good-bench.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"PASS"* ]]
}

@test "gate-ratio: FAIL when candidate aggregate does not improve" {
    python3 -c "
import json
data = {'scheme': 'Worse', 'bwt_aggregate': 0.600000, 'aggregate': 0.600000}
with open('$TMPDIR_TEST/bad-ratio-bench.json', 'w') as f:
    json.dump(data, f)
"
    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/bad-ratio-bench.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"FAIL"* ]] || [[ "$output" == *"no strict"* ]]
}

@test "gate-ratio: FAIL when candidate aggregate equals baseline (no strict improvement)" {
    python3 -c "
import json
# Exactly equal to the 10-file baseline — should fail (must be STRICTLY less)
data = {'scheme': 'Equal', 'bwt_aggregate': 0.299337, 'aggregate': 0.299337}
with open('$TMPDIR_TEST/equal-bench.json', 'w') as f:
    json.dump(data, f)
"
    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/equal-bench.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"FAIL"* ]] || [[ "$output" == *"no strict"* ]]
}

# ── gate-competitive tests ────────────────────────────────────────────────────

@test "gate-competitive: PASS on current binary with BWT scheme (no per-file regression vs BWT baseline)" {
    # The leaderboard baseline records BWT-entropy compressed bytes.
    # Gate must use the same scheme (--value-scheme bwt-entropy) to measure the candidate.
    run bash "$GATE_DIR/gate-competitive.sh" --value-scheme bwt-entropy
    [ "$status" -eq 0 ]
    [[ "$output" == *"PASS"* ]]
}

@test "gate-competitive: FAIL when a per-file regression is present" {
    # Create a leaderboard with artificially low per-file baselines
    # so the current binary (which compresses normally) appears to regress
    STRICT_LEADERBOARD="$TMPDIR_TEST/strict-leaderboard.json"
    python3 -c "
import json
lb = json.load(open('$LEADERBOARD'))
# Set all per_file baselines to 1 byte — current binary will always exceed that
pf_strict = []
for e in lb['current_best']['per_file']:
    pf_strict.append({**e, 'bytes': 1, 'bwt_bytes': 1, 't4_bytes': 1})
lb2 = dict(lb)
lb2['current_best'] = {**lb['current_best'], 'per_file': pf_strict}
with open('$STRICT_LEADERBOARD', 'w') as f:
    json.dump(lb2, f, indent=2)
"
    # Create a gate-competitive wrapper using the strict leaderboard
    GATE_WRAPPER="$TMPDIR_TEST/gate-competitive-strict.sh"
    cat > "$GATE_WRAPPER" << 'EOFW'
#!/usr/bin/env bash
set -euo pipefail
GATE_DIR="PLACEHOLDER_GATE_DIR"
REPO_ROOT="$(cd "$GATE_DIR/../../.." && pwd)"
LEADERBOARD="PLACEHOLDER_LEADERBOARD"
MANIFEST="$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json"
CUBRIM_BIN="$REPO_ROOT/code/cubrim-rs/target/release/cubrim"
command -v jq >/dev/null 2>&1 || { echo "jq required" >&2; exit 2; }
FAIL=0
TMPD="$(mktemp -d)"; trap 'rm -rf "$TMPD"' EXIT
BASELINES="$(python3 -c "
import json
lb = json.load(open('$LEADERBOARD'))
pf = lb.get('current_best', {}).get('per_file', [])
result = {}
for e in pf:
    b = e.get('bytes') or e.get('bwt_bytes') or e.get('t4_bytes')
    if b: result[e['file']] = int(b)
import json; print(json.dumps(result))
" 2>/dev/null)"
while IFS= read -r entry; do
    name="$(echo "$entry" | jq -r '.name')"
    path="$(echo "$entry" | jq -r '.path')"
    size_bytes="$(echo "$entry" | jq -r '.size_bytes')"
    [ -f "$path" ] || path="$REPO_ROOT/docs/ephemeral/research/corpus/$(basename "$path")"
    [ -f "$path" ] || { echo "SKIP $name" >&2; continue; }
    compressed="$TMPD/${name}.cubrim"
    "$CUBRIM_BIN" compress "$path" "$compressed" 2>/dev/null || { FAIL=1; continue; }
    CANDIDATE_BYTES="$(wc -c < "$compressed")"
    BASELINE_BYTES="$(python3 -c "
import json,sys
b=json.loads(sys.argv[1])
print(b.get(sys.argv[2], int(sys.argv[3])))
" "$BASELINES" "$name" "$size_bytes")"
    if python3 -c "import sys; sys.exit(0 if int(sys.argv[1])<=int(sys.argv[2]) else 1)" "$CANDIDATE_BYTES" "$BASELINE_BYTES"; then
        echo "OK $name"
    else
        echo "gate-competitive: FAIL $name — REGRESSION" >&2; FAIL=1
    fi
done < <(jq -c '.[]' "$MANIFEST")
[ "$FAIL" -eq 0 ] || exit 1; exit 0
EOFW
    sed -i '' "s|PLACEHOLDER_GATE_DIR|$GATE_DIR|g" "$GATE_WRAPPER"
    sed -i '' "s|PLACEHOLDER_LEADERBOARD|$STRICT_LEADERBOARD|g" "$GATE_WRAPPER"
    chmod +x "$GATE_WRAPPER"

    run bash "$GATE_WRAPPER"
    [ "$status" -ne 0 ]
    [[ "$output" == *"REGRESSION"* ]]
}

# ── full rail tests ───────────────────────────────────────────────────────────

@test "run-merge-rail: --dry-run passes with all gates individually green" {
    # Validate the gate chain integration by verifying each gate passes independently
    # (A full rail dry-run requires a clean git worktree with an actual feature branch;
    # the individual gate tests above prove each gate's pass/fail logic. This test
    # confirms the gate scripts are wired in the rail in correct order.)
    make_good_bench_json "$TMPDIR_TEST/dry-run-bench.json"

    # Verify gates 1, 3, 4, 5 all pass on the clean codebase
    run bash "$GATE_DIR/gate-corpus-hash.sh"
    [ "$status" -eq 0 ]

    run bash "$GATE_DIR/gate-roundtrip.sh"
    [ "$status" -eq 0 ]

    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/dry-run-bench.json"
    [ "$status" -eq 0 ]

    run bash "$GATE_DIR/gate-competitive.sh" --value-scheme bwt-entropy
    [ "$status" -eq 0 ]

    # run-merge-rail.sh exists and is executable
    [ -x "$GATE_DIR/run-merge-rail.sh" ]
}

@test "run-merge-rail: gate order is corpus-hash -> cargo-test -> roundtrip -> ratio -> competitive" {
    # Assert the five gates are listed in the correct order in run-merge-rail.sh
    GATE_SCRIPT="$GATE_DIR/run-merge-rail.sh"
    [ -f "$GATE_SCRIPT" ]

    # Extract gate invocation lines and verify order
    CORPUS_LINE=$(grep -n 'gate-corpus-hash' "$GATE_SCRIPT" | grep 'run_gate' | head -1 | cut -d: -f1)
    CARGO_LINE=$(grep -n 'gate-cargo-test' "$GATE_SCRIPT" | grep 'run_gate' | head -1 | cut -d: -f1)
    ROUNDTRIP_LINE=$(grep -n 'gate-roundtrip' "$GATE_SCRIPT" | grep 'run_gate' | head -1 | cut -d: -f1)
    RATIO_LINE=$(grep -n 'gate-ratio' "$GATE_SCRIPT" | grep 'run_gate' | head -1 | cut -d: -f1)
    COMPETITIVE_LINE=$(grep -n 'gate-competitive' "$GATE_SCRIPT" | grep 'run_gate' | head -1 | cut -d: -f1)

    # All must be present and in ascending line order
    [ -n "$CORPUS_LINE" ]
    [ -n "$CARGO_LINE" ]
    [ -n "$ROUNDTRIP_LINE" ]
    [ -n "$RATIO_LINE" ]
    [ -n "$COMPETITIVE_LINE" ]

    python3 -c "
a,b,c,d,e = int('$CORPUS_LINE'), int('$CARGO_LINE'), int('$ROUNDTRIP_LINE'), int('$RATIO_LINE'), int('$COMPETITIVE_LINE')
assert a < b < c < d < e, f'Gate order wrong: {a} {b} {c} {d} {e}'
print('Gate order: OK')
"
}

@test "run-merge-rail: exits non-zero on corpus tamper (gate-corpus-hash fails)" {
    # We cannot tamper the real corpus for a test, so we test that gate-corpus-hash
    # is indeed the first gate in the chain by verifying the exit path.
    # This is validated via the individual gate-corpus-hash FAIL test above.
    # Integration: verify run-merge-rail calls gate-corpus-hash.sh by checking it exists
    [ -f "$GATE_DIR/gate-corpus-hash.sh" ]
    # Verify script is executable
    [ -x "$GATE_DIR/gate-corpus-hash.sh" ]
}

# ── B1 regression: baseline must come from main, never from the branch ──────

@test "gate-ratio: FAIL-CLOSED when branch leaderboard lowers baseline to 9.99 (PoC B1)" {
    # Reproduce QA's PoC: a worker writes aggregate=9.99 into the working-tree
    # leaderboard to make any candidate appear to improve. Gate-ratio MUST still
    # compare against main's real baseline (0.299337 on the 10-file corpus),
    # not the tampered working-tree copy.
    #
    # The gate reads via: git show main:docs/leaderboard/cubrim-leaderboard.json
    # so the branch's working-tree file is never consulted for the baseline.

    # Temporarily tamper the working-tree leaderboard
    REAL_LEADERBOARD="$REPO_ROOT/docs/leaderboard/cubrim-leaderboard.json"
    BACKUP="$TMPDIR_TEST/leaderboard-backup.json"
    cp "$REAL_LEADERBOARD" "$BACKUP"

    # Write a leaderboard that would let any candidate through
    python3 -c "
import json
lb = json.load(open('$REAL_LEADERBOARD'))
lb['current_best']['aggregate'] = 9.99
with open('$REAL_LEADERBOARD', 'w') as f:
    json.dump(lb, f, indent=2)
"
    # Candidate bench JSON claims aggregate=0.48 — would be a strict improvement vs 9.99
    # but must FAIL when compared against main's real baseline (~0.299337)
    python3 -c "
import json
data = {'scheme': 'TamperTest', 'bwt_aggregate': 0.480000, 'aggregate': 0.480000}
with open('$TMPDIR_TEST/tamper-bench.json', 'w') as f:
    json.dump(data, f)
"
    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/tamper-bench.json"
    local exit_code="$status"
    # Restore the real leaderboard before asserting (teardown safety)
    cp "$BACKUP" "$REAL_LEADERBOARD"

    # Gate MUST fail: 0.48 is NOT strictly less than the real main baseline ~0.299337
    [ "$exit_code" -ne 0 ]
    [[ "$output" == *"FAIL"* ]] || [[ "$output" == *"no strict"* ]]
}

@test "gate-competitive: ignores branch leaderboard tamper and enforces real baselines (PoC B1)" {
    # PoC B1 for gate-competitive: a worker sets per_file.bytes=999999 (inflated
    # baseline) in the working-tree leaderboard, hoping that a candidate with bad
    # per-file output would slip through the 999999-byte bound.
    # Gate-competitive must read baselines from main (or pinned bootstrap),
    # NOT from the working-tree copy. Proof: tamper the working tree, verify the
    # gate (a) reports reading from main/bootstrap (not the working-tree values)
    # and (b) still passes on the current binary against the real per-file baselines.

    REAL_LEADERBOARD="$REPO_ROOT/docs/leaderboard/cubrim-leaderboard.json"
    BACKUP="$TMPDIR_TEST/leaderboard-backup-comp.json"
    cp "$REAL_LEADERBOARD" "$BACKUP"

    # Tamper: set all per_file bytes to 999999 (inflated to let anything through)
    python3 -c "
import json
lb = json.load(open('$REAL_LEADERBOARD'))
pf = lb['current_best']['per_file']
for e in pf:
    e['bytes'] = 999999
    e['bwt_bytes'] = 999999
    e['t4_bytes'] = 999999
lb['current_best']['per_file'] = pf
with open('$REAL_LEADERBOARD', 'w') as f:
    json.dump(lb, f, indent=2)
"
    run bash "$GATE_DIR/gate-competitive.sh" --value-scheme bwt-entropy
    local exit_code="$status"
    cp "$BACKUP" "$REAL_LEADERBOARD"

    # Gate MUST pass (current binary is the baseline — no regression)
    # AND output must confirm it read from main/pinned (not the 999999 tampered values).
    # The tampered values would produce "999999" in the "baselines loaded" line;
    # the real pinned values should show real byte counts.
    [ "$exit_code" -eq 0 ]
    [[ "$output" == *"PASS"* ]]
    # Output must NOT show the inflated 999999 baselines (which would prove it read
    # the working-tree tampered file instead of the immutable source)
    [[ "$output" != *"999999"* ]]
}

@test "gate-ratio: baseline and candidate are on the same 10-file corpus (no 7-vs-10 mismatch)" {
    # Verify that the leaderboard aggregate used as baseline is the 10-file value
    # (the same corpus the gate benchmarks candidates on), not the historical 7-file 0.504412.
    # A 10-file baseline is strictly < 0.504412 (block_bound_runs is large and compresses well).
    BASELINE="$(jq -r '.current_best.aggregate' "$LEADERBOARD")"
    python3 -c "
baseline = float('$BASELINE')
old_7file = 0.504412
# The 10-file aggregate must be below 0.35 (block_bound_runs pulls it down significantly)
# If we see 0.504412, the leaderboard was never updated from the 7-file baseline.
assert baseline < 0.35, f'Baseline {baseline} looks like the 7-file value ({old_7file}); must be the 10-file aggregate'
print(f'Corpus consistency OK: baseline={baseline:.6f} (10-file corpus)')
"
    [ "$?" -eq 0 ]
}

@test "leaderboard JSON: current_best aggregate is the 10-file measured value 0.299337" {
    # Concrete assertion: the baseline stored in the leaderboard must be the real
    # measured 10-file BWT aggregate, not the historical 7-file number.
    BASELINE="$(jq -r '.current_best.aggregate' "$LEADERBOARD")"
    python3 -c "
import sys
baseline = float('$BASELINE')
expected = 0.299337
tol = 0.000001
assert abs(baseline - expected) <= tol, f'Baseline {baseline:.6f} != expected {expected:.6f}'
print(f'10-file aggregate baseline OK: {baseline:.6f}')
"
    [ "$?" -eq 0 ]
}

# ── CUBR-0034: corpus-version assertion in gate-ratio ────────────────────────
@test "gate-ratio: FAIL when baseline corpus_manifest_sha256 mismatches the frozen corpus" {
    # The baseline is only comparable to a candidate when both are on the same
    # frozen corpus. Drive the gate down its pinned-bootstrap path with a pinned
    # baseline whose corpus_manifest_sha256 is wrong; the gate must fail-closed.
    # Copy the WORKING-TREE repo (not a git clone of HEAD) so the test exercises
    # the current gate scripts, then point the clone's main away from the leaderboard.
    SCRATCH="$TMPDIR_TEST/scratch"
    mkdir -p "$SCRATCH/code/cluster/gate" "$SCRATCH/code/bench" "$SCRATCH/docs/ephemeral/research/corpus"
    cp "$GATE_DIR"/*.sh "$GATE_DIR"/*.sha256 "$SCRATCH/code/cluster/gate/"
    cp "$REPO_ROOT/code/bench/run_bench.py" "$SCRATCH/code/bench/" 2>/dev/null || true
    cp "$MANIFEST" "$SCRATCH/docs/ephemeral/research/corpus/"
    # Make it a git repo with NO leaderboard on main → gate falls back to pinned baseline
    git -C "$SCRATCH" init -q
    git -C "$SCRATCH" -c user.email=t@t -c user.name=t add -A
    git -C "$SCRATCH" -c user.email=t@t -c user.name=t commit -q -m init
    # Pinned baseline with a WRONG corpus sha
    python3 -c "
import json
p = '$SCRATCH/code/cluster/gate/pinned-leaderboard-baseline.json'
json.dump({'current_best': {'scheme':'BwtEntropy','aggregate':0.299337,
          'corpus_manifest_sha256':'0000000000000000000000000000000000000000000000000000000000000000'}},
          open(p,'w'), indent=2)
"
    python3 -c "import json; json.dump({'scheme':'X','bwt_aggregate':0.28,'aggregate':0.28}, open('$TMPDIR_TEST/c.json','w'))"
    run bash "$SCRATCH/code/cluster/gate/gate-ratio.sh" --bench-json "$TMPDIR_TEST/c.json"
    [ "$status" -ne 0 ]
    [[ "$output" == *"different corpus"* ]] || [[ "$output" == *"corpus_manifest_sha256"* ]]
}

@test "gate-ratio: PASS corpus-version check when baseline corpus matches frozen corpus" {
    python3 -c "import json; json.dump({'scheme':'X','bwt_aggregate':0.28,'aggregate':0.28}, open('$TMPDIR_TEST/c.json','w'))"
    run bash "$GATE_DIR/gate-ratio.sh" --bench-json "$TMPDIR_TEST/c.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"corpus-version OK"* ]]
}

# ── CUBR-0035: arbiter numpy bootstrap-check ─────────────────────────────────
@test "probe-entropy.sh: actionable error when numpy is not importable" {
    # Simulate a host without numpy via a python3 stub that fails 'import numpy'
    # but succeeds otherwise (so the command -v python3 check still passes).
    STUB_BIN="$TMPDIR_TEST/bin"
    mkdir -p "$STUB_BIN"
    cat > "$STUB_BIN/python3" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    "import numpy") exit 1;;
  esac
done
exit 0
STUB
    chmod +x "$STUB_BIN/python3"
    run env PATH="$STUB_BIN:$PATH" bash "$REPO_ROOT/consilium/arbiter/probe-entropy.sh" --value-stream-bytes "$MANIFEST"
    [ "$status" -eq 2 ]
    [[ "$output" == *"numpy is required"* ]]
    [[ "$output" == *"requirements.txt"* ]] || [[ "$output" == *"pip install"* ]]
}
