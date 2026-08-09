#!/usr/bin/env bash
# Static and mutation-sensitive contract tests for decode-attrib-run.sh.
# Literal regex contracts intentionally contain shell-looking tokens.
# shellcheck disable=SC2016
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly TEST_DIR
readonly SELF=$TEST_DIR/decode-attrib-run-test.sh
RUNNER=${RUNNER:-$TEST_DIR/decode-attrib-run.sh}
SELF_MUTATION_TESTS=${SELF_MUTATION_TESTS:-1}

fail() {
    printf 'decode_attrib_contract=FAIL reason=%s\n' "$1" >&2
    exit 1
}

invalid() {
    printf 'decode_attrib_contract=HARNESS_INVALID reason=%s\n' "$1" >&2
    exit 2
}

require_fixed() {
    /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "missing literal: $1"
}

require_regex() {
    /usr/bin/grep -qE -- "$1" "$RUNNER" || fail "missing pattern: $2"
}

reject_fixed() {
    ! /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "forbidden literal: $1"
}

[[ -f $RUNNER ]] || invalid "runner not found: $RUNNER"

required_literals=(
    '/root/cubr-decode-attrib-g2-20260809'
    'taskset -c 0-15'
    '/root/corpus-full/silesia'
    'd4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb'
    '3a13f48'
    '/root/cubr-decode-attrib-g2-test-overlay.patch'
    'b0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec'
    'a3d399f57aa8ee5b7c172afd5322a7f7a1e14392'
    '8248283bcab58b4c4078b4a78425cd8717f165f7'
    'cargo test --release'
    'cargo test --release --test differential -- --nocapture'
    'cmp --'
    'corpus_manifest.tsv'
    'perf stat'
    'perf record'
    'SHA256SUMS'
    'TIMING-DONE.STAMP'
    'cycle-agreement'
    'cycle-disagreement'
    'instrument-perturbed'
    'instrument-clean'
    'readonly G3_RATIO_MAX=1.10'
    'readonly CYCLE_DISAGREEMENT_MAX=0.10'
    '--kill-after=10s'
    'runner SHA mismatch'
    'orphan candidate/perf process'
    'mapfile -t rows'
    'SHA256SUMS.tmp'
    'cleanup_preflight'
    'monotonic_now'
    'DEADLINE_MONOTONIC'
    '/proc/uptime'
    'run_bounded 10 "$d/perf-stat-smoke.out"'
    'run_bounded 10 "$d/perf-record-smoke.out"'
    'run_bounded 300 "$d/perf-report.txt"'
    'PROVENANCE.txt'
    '/usr/bin/git -C "$CODE_DIR" symbolic-ref -q HEAD'
    'quiet_wait || die '\''host did not become quiet before admission deadline'\'''
    '"topology":"cpu0-31=core0-31;cpu32-63=smt0-31"'
    '"perf_stat_smoke":"PASS"'
    '"perf_record_smoke":"PASS"'
    '"binary_sha256":"%s","code_commit":"%s"'
    '"$CUBRIM_SHA_EXPECT" "$CODE_COMMIT"'
    '"$CARGO" test --release)'
    '"$CARGO" test --release --test differential -- --nocapture)'
    '/usr/bin/git -C "$CODE_DIR" apply --check "$TEST_OVERLAY"'
    '/usr/bin/git -C "$CODE_DIR" diff --no-ext-diff --binary --unified=0 "$CODE_COMMIT" "$TEST_OVERLAY_SOURCE_COMMIT"'
    '/usr/bin/git -C "$CODE_DIR" apply "$TEST_OVERLAY"'
    '/usr/bin/git -C "$CODE_DIR" apply -R --check "$TEST_OVERLAY"'
    '/usr/bin/git -C "$CODE_DIR" apply -R "$TEST_OVERLAY"'
    'test overlay SHA mismatch'
    'test overlay source diff mismatch'
    'code checkout dirty after test overlay removal'
    '/usr/bin/git -C "$CODE_DIR" archive "$TEST_FIXTURE_COMMIT" -- "$TEST_FIXTURE_DIR"'
    '/usr/bin/git -C "$CODE_DIR" clean -fdX -- "$TEST_FIXTURE_DIR" "$GENERATED_CARGO_LOCK"'
    'test fixture tree mismatch'
    'test-fixtures.sha256'
    'cargo-generated.lock'
    'generated Cargo lock missing after suites'
    'code checkout dirty after test input cleanup'
    '[[ $(sha "$src") == "$want_sha" ]]'
    '[[ $actual == "$EXPECTED_RUNNER_SHA" ]]'
    'readonly PERF_VALUE_RE='\''^[0-9]+([.][0-9]+)?$'\'''
    '$1 ~ re'
    'AMD EPYC 7502P 32-Core Processor'
    'count != 64'
    '/usr/bin/rm -f -- "$output"'
    'CELL_RESULT'
    'DECODE_RESULT'
    '[[ ! -e $OUT && ! -L $OUT ]] || die '\''final output collision before rename'\'''
    '/usr/bin/mv -T -n -- "$PARTIAL" "$OUT"'
    '"corpus_manifest_cells":"4/4"'
    '"journal_archive_cells":"4/4"'
    '"deadline_monotonic_s":%s'
    'process scan failed'
    'load average read failed'
)
for literal in "${required_literals[@]}"; do
    require_fixed "$literal"
done

reject_fixed 'taskset -c 16-19'
reject_fixed '/usr/bin/mapfile'
reject_fixed '/usr/bin/date +%s'
reject_fixed '/usr/bin/psql'
reject_fixed 'if ! run_cell'
require_fixed "IFS=\$'\\n\\t'"
require_regex '^[[:space:]]*(readonly[[:space:]]+)?OUT=/root/cubr-decode-attrib-g2-20260809$' 'exact G2 OUT assignment'
require_regex '^[[:space:]]*local corpus=\$1 file=\$2 preset=\$3 want_sha=\$4$' 'journal inputs bind before journal path'
require_regex '^[[:space:]]*local journal=\$ROOT/journal\.\$preset\.jsonl$' 'journal path binds after preset'
if /usr/bin/grep -qE '^[[:space:]]*(readonly[[:space:]]+)?OUT=/root/cubr-decode-attrib-20260809$' "$RUNNER"; then
    fail 'G0 output path is assigned'
fi

require_fixed 'refuse_existing_output'
require_fixed 'remaining_budget_seconds'
require_fixed 'run_bounded'
require_fixed 'classify_cycle_agreement'
require_fixed 'classify_instrument_overhead'
require_fixed 'verify_runner_provenance'
require_fixed 'verify_manifest_source'
require_fixed 'reject_orphan_processes'

refusal_call_count=$({ /usr/bin/grep -F 'refuse_existing_output || exit 1' "$RUNNER" || true; } | /usr/bin/wc -l)
[[ $refusal_call_count == 2 ]] || fail 'output refusal call count must be 2'

post_cell_exit_gate_count=$(/usr/bin/awk '
    /^[[:space:]]*run_cell / { state=1; next }
    state==1 && /^[[:space:]]*reject_orphan_processes$/ { state=2; next }
    state==2 && /^[[:space:]]*if \[\[ \$CELL_RESULT != PASS \]\]; then$/ { count++; state=0 }
    END { print count+0 }
' "$RUNNER")
[[ $post_cell_exit_gate_count == 1 ]] || fail 'post-cell exit gate ordering must occur once'

# Every candidate encode/decode must be routed through the bounded-command seam.
if /usr/bin/grep -qE '^[[:space:]]*("?\$CUBRIM"?|\$\{CUBRIM\})[[:space:]]+(compress|decompress)' "$RUNNER"; then
    fail 'unbounded direct candidate invocation'
fi

line_of_call() {
    local pattern=$1
    local line
    line=$({ /usr/bin/grep -nE -- "$pattern" "$RUNNER" || true; } | /usr/bin/tail -n 1 | /usr/bin/cut -d: -f1)
    [[ -n $line ]] || fail "missing ordered call: $pattern"
    printf '%s\n' "$line"
}

manifest_line=$(line_of_call '^write_manifests$')
marker_line=$(line_of_call '^write_completion_marker$')
rename_line=$(line_of_call '^/usr/bin/mv -T -n -- "\$PARTIAL" "\$OUT"$')
chmod_line=$(line_of_call '^/usr/bin/chmod -R a-w -- "\$OUT"$')
(( manifest_line < marker_line && marker_line < rename_line && rename_line < chmod_line )) ||
    fail 'completion ordering must be manifests -> marker -> rename -> chmod'

if [[ $SELF_MUTATION_TESTS == 1 ]]; then
    mutation_root=$(/usr/bin/mktemp -d)
    cleanup() {
        /usr/bin/chmod -R u+w -- "$mutation_root" 2>/dev/null || true
        /usr/bin/rm -rf -- "$mutation_root"
    }
    trap cleanup EXIT

    CHILD_OUTPUT=
    CHILD_RC=0
    capture_child() {
        set +e
        CHILD_OUTPUT=$("$@" 2>&1)
        CHILD_RC=$?
        set -e
    }

    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$RUNNER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'decode_attrib_contract=PASS' ]]; }; then
        invalid "positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutation_root/missing.sh" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 2 )) &&
        [[ $CHILD_OUTPUT == decode_attrib_contract=HARNESS_INVALID\ reason=runner\ not\ found:* ]] &&
        ! /usr/bin/grep -qF 'decode_attrib_contract=FAIL' <<<"$CHILD_OUTPUT"; }; then
        invalid "setup-negative control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    expect_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3
        local mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change source: $label"
        capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutant" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "mutation survived: $label"
        ! /usr/bin/grep -qF 'decode_attrib_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "mutation emitted PASS: $label"
        /usr/bin/grep -qF "decode_attrib_contract=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_self_test_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3
        local mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change source: $label"
        capture_child /usr/bin/bash "$mutant" --self-test
        (( CHILD_RC != 0 )) || fail "runner self-test mutation survived: $label"
        ! /usr/bin/grep -qF 'decode_attrib_self_test=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "runner self-test mutation emitted PASS: $label"
        /usr/bin/grep -qF "decode_attrib_self_test=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "runner self-test mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_mutant_red pin 's/taskset -c 0-15/taskset -c 16-19/' 'missing literal: taskset -c 0-15'
    expect_mutant_red output 's/cubr-decode-attrib-g2-20260809/cubr-decode-attrib-20260809/g' 'missing literal: /root/cubr-decode-attrib-g2-20260809'
    expect_mutant_red manifest '/\[\[ \$(sha "\$src") == "\$want_sha" \]\]/c\    /usr/bin/true' 'missing literal: [[ $(sha "$src") == "$want_sha" ]]'
    expect_mutant_red cmp 's@/usr/bin/cmp --@/usr/bin/true --@g' 'missing literal: cmp --'
    expect_mutant_red timeout 's/--kill-after=10s/--kill-after=11s/g' 'missing literal: --kill-after=10s'
    expect_mutant_red g3 's/readonly G3_RATIO_MAX=1.10/readonly G3_RATIO_MAX=1.20/' 'missing literal: readonly G3_RATIO_MAX=1.10'
    expect_mutant_red cycles 's/readonly CYCLE_DISAGREEMENT_MAX=0.10/readonly CYCLE_DISAGREEMENT_MAX=0.20/' 'missing literal: readonly CYCLE_DISAGREEMENT_MAX=0.10'
    expect_mutant_red suite 's/"\$CARGO" test --release --test differential/"\$CARGO" test --release differential/' 'missing literal: "$CARGO" test --release --test differential -- --nocapture)'
    expect_mutant_red overlay-sha 's/b0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec/c0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec/' 'missing literal: b0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec'
    expect_mutant_red overlay-apply 's@/usr/bin/git -C "\$CODE_DIR" apply "\$TEST_OVERLAY"@/usr/bin/true@' 'missing literal: /usr/bin/git -C "$CODE_DIR" apply "$TEST_OVERLAY"'
    expect_mutant_red overlay-reverse 's@/usr/bin/git -C "\$CODE_DIR" apply -R "\$TEST_OVERLAY"@/usr/bin/true@' 'missing literal: /usr/bin/git -C "$CODE_DIR" apply -R "$TEST_OVERLAY"'
    expect_mutant_red fixture-tree 's/8248283bcab58b4c4078b4a78425cd8717f165f7/9248283bcab58b4c4078b4a78425cd8717f165f7/' 'missing literal: 8248283bcab58b4c4078b4a78425cd8717f165f7'
    expect_mutant_red fixture-clean 's@/usr/bin/git -C "\$CODE_DIR" clean -fdX -- "\$TEST_FIXTURE_DIR" "\$GENERATED_CARGO_LOCK"@/usr/bin/true@' 'missing literal: /usr/bin/git -C "$CODE_DIR" clean -fdX -- "$TEST_FIXTURE_DIR" "$GENERATED_CARGO_LOCK"'
    expect_mutant_red provenance 's@\[\[ \$actual == "\$EXPECTED_RUNNER_SHA" \]\]@/usr/bin/true@' 'missing literal: [[ $actual == "$EXPECTED_RUNNER_SHA" ]]'
    expect_mutant_red monotonic 's@/proc/uptime@/tmp/non-monotonic-clock@g' 'missing literal: /proc/uptime'
    expect_mutant_red refusal 's/refuse_existing_output || exit 1/:/g' 'output refusal call count must be 2'
    expect_mutant_red post-cell-exit '/^[[:space:]]*run_cell /{n;/reject_orphan_processes/d;}' 'post-cell exit gate ordering must occur once'
    expect_self_test_mutant_red perf-values "s@readonly PERF_VALUE_RE=.*@readonly PERF_VALUE_RE='.*'@" 'perf_events_non_numeric_accepted'

    marker_mutant=$mutation_root/marker-order.sh
    /usr/bin/awk '
        /^write_completion_marker$/ { held=$0; next }
        { print }
        /^\/usr\/bin\/mv -T -n -- "\$PARTIAL" "\$OUT"$/ { print held }
    ' "$RUNNER" >"$marker_mutant"
    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$marker_mutant" /usr/bin/bash "$SELF"
    (( CHILD_RC != 0 )) || fail 'mutation survived: completion-marker ordering'
    /usr/bin/grep -qF 'decode_attrib_contract=FAIL reason=completion ordering must be manifests -> marker -> rename -> chmod' <<<"$CHILD_OUTPUT" ||
        invalid "marker mutation failed at unrelated assertion: rc=$CHILD_RC output=$CHILD_OUTPUT"
fi

printf 'decode_attrib_contract=PASS\n'
