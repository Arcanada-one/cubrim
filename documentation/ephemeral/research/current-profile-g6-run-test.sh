#!/usr/bin/env bash
# Static, runtime, and mutation-sensitive contract tests for the NEW-24 G6 runner.
# shellcheck disable=SC2016
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly TEST_DIR
SELF=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
readonly SELF
RUNNER=${RUNNER:-$TEST_DIR/current-profile-g6-run.sh}
MAPPER=${MAPPER:-$TEST_DIR/current_profile_g6_map.py}
SELF_MUTATION_TESTS=${SELF_MUTATION_TESTS:-1}
LIVE_BEHAVIOR_MUTATION_LANE=${CUBR_G6_LIVE_BEHAVIOR_MUTATION_LANE:-0}
SKIP_SCIENTIFIC_MATRIX=${CUBR_G6_SKIP_SCIENTIFIC_MATRIX:-0}
readonly POISONED_PARENT_UNIT=g4-live-authority-must-not-be-used.service
readonly LIVE_G6_CAMPAIGN_UNIT=cubr-new24-full-binary-g6-20260811.service
readonly G6_ADMISSION_UNIT=cubr-new24-full-binary-g6-admission-20260811.service
readonly G6_CAMPAIGN_UNIT=cubr-new24-full-binary-g6-20260811.service
readonly G6_ADMISSION_INPUTS=/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env
readonly G6_INSTRUMENT_REPO=/root/cubr-new24-full-binary-g6-instrument
readonly G6_LAUNCH_IDENTITIES=$G6_INSTRUMENT_REPO/documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env
readonly PURE_MOCK_PATH=/usr/bin:/bin
readonly PURE_MOCK_PARENT_CANARY=parent-environment-must-not-reach-pure-mock

export CUBR_G6_TEST_UNIT=$POISONED_PARENT_UNIT
export INVOCATION_ID=g4-live-authority-must-not-be-used
export CUBR_CGROUP_SYSTEMCTL_USER=1
export CUBR_CGROUP_LIVE_RESULT=/tmp/g4-live-authority-must-not-be-used.result
export CUBR_G6_PURE_MOCK_PARENT_CANARY=$PURE_MOCK_PARENT_CANARY

fail() {
    printf 'current_profile_g6_contract=FAIL reason=%s\n' "$1" >&2
    exit 1
}

invalid() {
    printf 'current_profile_g6_contract=HARNESS_INVALID reason=%s\n' "$1" >&2
    exit 2
}

[[ $LIVE_BEHAVIOR_MUTATION_LANE =~ ^[01]$ ]] ||
    invalid 'live behavior mutation lane selector is malformed'
[[ $SKIP_SCIENTIFIC_MATRIX =~ ^[01]$ ]] ||
    invalid 'scientific matrix selector is malformed'
if [[ $SKIP_SCIENTIFIC_MATRIX == 1 ]]; then
    [[ $SELF_MUTATION_TESTS == 0 && ( $RUNNER == /tmp/* || $SELF == /tmp/* ) ]] ||
        invalid 'scientific matrix skip escaped its nested mutant scope'
fi
if [[ $LIVE_BEHAVIOR_MUTATION_LANE == 1 ]]; then
    [[ $SELF_MUTATION_TESTS == 0 && $RUNNER == /tmp/* &&
       $RUNNER != "$TEST_DIR/current-profile-g6-run.sh" ]] ||
        invalid 'live behavior mutation lane escaped its nested mutant scope'
fi

assert_mock_output_isolated() {
    local output=$1 expected_unit=$2
    [[ $output != *'canary=present'* ]] ||
        fail 'parent poison canary reached pure mock child'
    [[ $output != *"$POISONED_PARENT_UNIT"* ]] ||
        fail 'poisoned parent unit reached pure mock output'
    [[ $output != *"$LIVE_G6_CAMPAIGN_UNIT"* ]] ||
        fail 'live campaign unit reached pure mock output'
    [[ $output == *"unit=$expected_unit"* ]] ||
        invalid "pure mock output missing expected unit: $expected_unit output=$output"
}

run_pure_mock_cgroup() {
    local fixture_unit=$1 mode=$2
    /usr/bin/env -i LC_ALL=C PATH="$PURE_MOCK_PATH" CUBR_G6_TEST_UNIT="$fixture_unit" /usr/bin/bash "$RUNNER" "$mode"
}

run_plan_deployment_interface() {
    local mode=$1 root_prefix=/tmp/current-profile-g6-interface-$$-$1
    case $mode in
        admission)
            /usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
                DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C \
                PATH=/usr/bin:/bin CUBR_THREADS=4 RAYON_NUM_THREADS=4 \
                OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
                CUBR_G6_ADMITTED_UNIT="$G6_ADMISSION_UNIT" \
                CUBR_G6_ADMISSION_INPUTS="$G6_ADMISSION_INPUTS" \
                CUBR_G6_TEST_ROOT_PREFIX="$root_prefix" \
                /usr/bin/bash "$RUNNER" --admission-feasibility
            ;;
        campaign)
            /usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
                DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C \
                PATH=/usr/bin:/bin CUBR_THREADS=4 RAYON_NUM_THREADS=4 \
                OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
                CUBR_G6_ADMITTED_UNIT="$G6_CAMPAIGN_UNIT" \
                CUBR_G6_LAUNCH_IDENTITIES="$G6_LAUNCH_IDENTITIES" \
                CUBR_G6_TEST_ROOT_PREFIX="$root_prefix" \
                /usr/bin/bash "$RUNNER" --campaign
            ;;
        *) invalid "unknown deployment interface fixture mode: $mode" ;;
    esac
}

run_user_systemd_fixture() {
    local host_home=$1 host_xdg=$2 host_dbus=$3 capture_dir=$4
    [[ -n $host_home ]] || fail 'live fixture host variable is empty: HOME'
    [[ -n $host_xdg ]] || fail 'live fixture host variable is empty: XDG_RUNTIME_DIR'
    [[ -n $host_dbus ]] || fail 'live fixture host variable is empty: DBUS_SESSION_BUS_ADDRESS'
    [[ -d $capture_dir && ! -L $capture_dir ]] || fail 'live fixture capture directory is unsafe'
    /usr/bin/env -i \
        LC_ALL=C \
        PATH=/usr/bin:/bin \
        HOME="$host_home" \
        XDG_RUNTIME_DIR="$host_xdg" \
        DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
        CUBR_THREADS=4 \
        RAYON_NUM_THREADS=4 \
        OMP_NUM_THREADS=4 \
        MKL_NUM_THREADS=4 \
        /usr/bin/bash "$RUNNER" --self-test-cgroup-live "$capture_dir"
}

verify_admitted_campaign_identity() {
    [[ ${CUBR_ENFORCE_CAMPAIGN_REREAD:-0} == 1 ]] || return 0
    local props
    props=$(/usr/bin/systemctl show "$CUBR_ADMITTED_SYSTEMD_UNIT" \
        -p InvocationID -p MainPID -p NRestarts -p ControlGroup)
    /usr/bin/grep -qx "InvocationID=$CUBR_ADMITTED_INVOCATION_ID" <<<"$props" ||
        fail 'admitted campaign InvocationID changed after self-test'
    /usr/bin/grep -qx "MainPID=$CUBR_ADMITTED_MAIN_PID" <<<"$props" ||
        fail 'admitted campaign MainPID changed after self-test'
    /usr/bin/grep -qx 'NRestarts=0' <<<"$props" ||
        fail 'admitted campaign restart count changed after self-test'
    /usr/bin/grep -qx "ControlGroup=$CUBR_ADMITTED_CONTROL_GROUP" <<<"$props" ||
        fail 'admitted campaign ControlGroup changed after self-test'
}

require_runner_fixed() {
    /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "runner missing literal: $1"
}

reject_runner_fixed() {
    ! /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "runner forbidden literal: $1"
}

require_runner_named() {
    /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "$2"
}

old_and_list_probe=$(/usr/bin/bash -c '
    set -e
    CHILD_RC=0
    CHILD_OUTPUT=unexpected-success
    ((CHILD_RC != 0)) && /usr/bin/grep -qF named-rejection <<<"$CHILD_OUTPUT"
    printf old-and-list-survived
') || invalid 'old AND-list false-green probe did not reproduce'
[[ $old_and_list_probe == old-and-list-survived ]] ||
    invalid 'old AND-list false-green probe output mismatch'

new_explicit_probe_rc=0
set +e
/usr/bin/bash -c '
    set -e
    CHILD_RC=0
    CHILD_OUTPUT=unexpected-success
    (( CHILD_RC != 0 )) || exit 97
    /usr/bin/grep -qF named-rejection <<<"$CHILD_OUTPUT"
' >/dev/null 2>&1
new_explicit_probe_rc=$?
set -e
[[ $new_explicit_probe_rc == 97 ]] ||
    invalid 'explicit child-status guard did not kill unexpected success'

contract_source_path=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
if /usr/bin/grep -Eq '^([[:space:]]*)\(\( CHILD_RC != 0 \)\) && /usr/bin/grep' "$contract_source_path"; then
    fail 'child rejection assertion still uses false-green AND-list'
fi
for campaign_state_label in empty-cell journal-cell; do
    /usr/bin/grep -qF \
        "(( CHILD_RC != 0 )) || fail \"admission campaign-state mutation survived: $campaign_state_label\"" \
        "$contract_source_path" || fail 'admission campaign-state negatives lack explicit child-status guards'
done

line_of_last() {
    local pattern=$1 line
    line=$({ /usr/bin/grep -nE -- "$pattern" "$RUNNER" || true; } |
        /usr/bin/tail -n 1 | /usr/bin/cut -d: -f1)
    [[ -n $line ]] || fail "missing ordered call: $pattern"
    printf '%s\n' "$line"
}

function_source() {
    local signature=$1
    /usr/bin/awk -v signature="$signature() {" '
        $0 == signature {inside=1}
        inside {print}
        inside && /^}/ {exit}
    ' "$RUNNER"
}

[[ -f $RUNNER && ! -L $RUNNER ]] || invalid "runner not found or unsafe: $RUNNER"
[[ -f $MAPPER && ! -L $MAPPER ]] || invalid "mapper not found or unsafe: $MAPPER"
canonical_self=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
[[ $SELF == "$canonical_self" ]] || fail 'contract SELF is not canonicalized from BASH_SOURCE'
[[ -f $SELF && ! -L $SELF ]] || invalid "contract self not found or unsafe: $SELF"

for deployment_mode in admission campaign; do
    deployment_output=
    deployment_rc=0
    set +e
    deployment_output=$(run_plan_deployment_interface "$deployment_mode" 2>&1)
    deployment_rc=$?
    set -e
    if [[ $deployment_mode == admission ]]; then
        deployment_expected="current_profile_g6_deployment_interface=PASS mode=admission unit=$G6_ADMISSION_UNIT authority=$G6_ADMISSION_INPUTS"
    else
        deployment_expected="current_profile_g6_deployment_interface=PASS mode=campaign unit=$G6_CAMPAIGN_UNIT authority=$G6_LAUNCH_IDENTITIES"
    fi
    (( deployment_rc == 0 )) ||
        fail "plan-shaped $deployment_mode interface failed: rc=$deployment_rc output=$deployment_output"
    [[ $deployment_output == "$deployment_expected" ]] ||
        fail "plan-shaped $deployment_mode interface output mismatch: $deployment_output"
    [[ $deployment_output != *'unbound variable'* ]] ||
        fail "plan-shaped $deployment_mode interface dereferenced an unset variable"
done

sanitized_fixture_root=$(/usr/bin/mktemp -d)
for deployment_mode in admission campaign; do
    sanitized_fixture=$sanitized_fixture_root/$deployment_mode.txt
    sanitized_output=$(/usr/bin/bash "$RUNNER" --self-test-sanitized-environment-contract \
        "$deployment_mode" "$sanitized_fixture") ||
        fail "sanitized $deployment_mode contract generation failed"
    [[ $sanitized_output == \
       "current_profile_g6_sanitized_environment_contract_test=PASS mode=$deployment_mode" ]] ||
        fail "sanitized $deployment_mode contract generation output mismatch"
    if [[ $deployment_mode == admission ]]; then
        sanitized_authority=CUBR_G6_ADMISSION_INPUTS
        rejected_authority=CUBR_G6_LAUNCH_IDENTITIES
    else
        sanitized_authority=CUBR_G6_LAUNCH_IDENTITIES
        rejected_authority=CUBR_G6_ADMISSION_INPUTS
    fi
    /usr/bin/grep -qx \
        "service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS,CUBR_G6_ADMITTED_UNIT,$sanitized_authority" \
        "$sanitized_fixture" || fail "sanitized $deployment_mode contract omitted exact service interface"
    ! /usr/bin/grep -qF "$rejected_authority" "$sanitized_fixture" ||
        fail "sanitized $deployment_mode contract admitted the other mode's authority"
    ! /usr/bin/grep -Eq 'CUBR_SYSTEMD_UNIT|CUBR_LAUNCH_|CUBR_EXPECTED_' "$sanitized_fixture" ||
        fail "sanitized $deployment_mode contract contains a legacy mutable interface"
done
/usr/bin/rm -rf -- "$sanitized_fixture_root"

for legacy_mode in admission campaign; do
    legacy_output=
    legacy_rc=0
    legacy_root=/tmp/current-profile-g6-legacy-interface-$$-$legacy_mode
    set +e
    if [[ $legacy_mode == admission ]]; then
        legacy_output=$(/usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
            DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C PATH=/usr/bin:/bin \
            CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
            CUBR_SYSTEMD_UNIT="$G6_ADMISSION_UNIT" CUBR_INSTRUMENT_COMMIT=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_RUNNER_SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_MAPPER_SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_TEST_SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_MAPPER_TEST_SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_G6_TEST_ROOT_PREFIX="$legacy_root" \
            /usr/bin/bash "$RUNNER" --admission-feasibility 2>&1)
    else
        legacy_output=$(/usr/bin/env -i HOME=/root XDG_RUNTIME_DIR=/run/user/0 \
            DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus LC_ALL=C PATH=/usr/bin:/bin \
            CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
            CUBR_SYSTEMD_UNIT="$G6_CAMPAIGN_UNIT" CUBR_INSTRUMENT_COMMIT=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_LAUNCH_MAIN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_LAUNCH_PREREG="$G6_INSTRUMENT_REPO/documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-20260811.md" \
            CUBR_LAUNCH_IDENTITIES="$G6_LAUNCH_IDENTITIES" \
            CUBR_EXPECTED_PREREG_BLOB=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_IDENTITIES_BLOB=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_ADMISSION_IDENTITY_SET=/root/cubr-new24-full-binary-g6-map-dryrun-20260811/sealed-identity-set.env \
            CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
            CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES=1 \
            CUBR_G6_TEST_ROOT_PREFIX="$legacy_root" \
            /usr/bin/bash "$RUNNER" --campaign 2>&1)
    fi
    legacy_rc=$?
    set -e
    (( legacy_rc != 0 )) || fail "legacy-only $legacy_mode interface survived"
    [[ $legacy_output == *'CUBR_G6_ADMITTED_UNIT must equal the mode-specific G6 unit'* ]] ||
        fail "legacy-only $legacy_mode interface failed elsewhere: rc=$legacy_rc output=$legacy_output"
    [[ $legacy_output != *'unbound variable'* ]] ||
        fail "legacy-only $legacy_mode interface used an unset-variable dereference"
done

remote_live_gate_name=CUBR_REMOTE_LIVE_FIXTURE
nested_contract_selector=SELF_MUTATION_TESTS
nested_gate0_assignment="${remote_live_gate_name}=0"
outer_gate1_assignment="${remote_live_gate_name}=1"
non_comment_contract_source=$(/usr/bin/grep -Ev '^[[:space:]]*#' "$SELF")
nested_contract_lines=$({
    /usr/bin/grep -F "${nested_contract_selector}=0" <<<"$non_comment_contract_source" || true
})
nested_contract_count=$(/usr/bin/wc -l <<<"$nested_contract_lines")
[[ $nested_contract_count == 7 ]] || fail 'nested self-contract gate0 scope count mismatch'
while IFS= read -r nested_contract_line; do
    [[ $nested_contract_line == *"$nested_gate0_assignment"* ]] ||
        fail 'nested self-contract inherited remote live gate'
done <<<"$nested_contract_lines"
nested_gate0_count=$({ /usr/bin/grep -F "$nested_gate0_assignment" <<<"$non_comment_contract_source" || true; } |
    /usr/bin/wc -l)
[[ $nested_gate0_count == 7 ]] || fail 'nested self-contract gate0 scope count mismatch'
outer_gate1_count=$({ /usr/bin/grep -F "$outer_gate1_assignment" <<<"$non_comment_contract_source" || true; } |
    /usr/bin/wc -l)
[[ $outer_gate1_count == 1 ]] || fail 'outer inherited-live simulation count mismatch'

live_fixture_helper=$(/usr/bin/awk '
    /^run_user_systemd_fixture\(\) \{/ {inside=1}
    inside {print}
    inside && /^}/ {exit}
' "$SELF")
[[ $live_fixture_helper != *'INVOCATION_ID'* ]] ||
    fail 'outer live-fixture allowlist admitted INVOCATION_ID'
[[ $live_fixture_helper != *'CUBR_G6_TEST_UNIT'* &&
   $live_fixture_helper != *'CUBR_CGROUP_SYSTEMCTL_USER'* &&
   $live_fixture_helper != *'CUBR_CGROUP_LIVE_RESULT'* ]] ||
    fail 'outer live-fixture allowlist admitted fixture authority'
for thread_assignment in CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4; do
    [[ $live_fixture_helper == *"$thread_assignment"* ]] ||
        fail "outer live-fixture allowlist omitted thread limit: $thread_assignment"
done

fresh_fixture_count=$({ /usr/bin/grep -F 'current-profile-g6-cgroup-selftest-' "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $fresh_fixture_count == 1 ]] || fail 'live fixture fresh unit literal count is not exactly one'
live_fixture_vector=$(/usr/bin/awk '
    /^[[:space:]]*systemd_args=\($/ {inside=1}
    inside {print}
    inside && /^[[:space:]]*\)$/ {exit}
' "$RUNNER")
[[ $live_fixture_vector != *"$LIVE_G6_CAMPAIGN_UNIT"* ]] ||
    fail 'live fixture argument vector contains campaign unit'
for environment_assignment in \
    '--setenv=LC_ALL=C' '--setenv=PATH=/usr/bin:/bin' '--setenv=HOME=/root' \
    '--setenv=XDG_RUNTIME_DIR=/run/user/0' \
    '--setenv=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus' \
    '--setenv=CUBR_THREADS=4' '--setenv=RAYON_NUM_THREADS=4' \
    '--setenv=OMP_NUM_THREADS=4' '--setenv=MKL_NUM_THREADS=4'; do
    [[ $live_fixture_vector == *"$environment_assignment"* ]] ||
        fail "live fixture sanitized environment omitted: $environment_assignment"
done
/usr/bin/grep -qF \
    'p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork()' "$RUNNER" ||
    fail 'live fixture double-fork payload missing'

reread_call=verify_admitted_campaign_identity
reread_count=$({ /usr/bin/grep -E "^[[:space:]]*$reread_call$" "$SELF" || true; } |
    /usr/bin/wc -l)
[[ $reread_count == 13 ]] || fail 'campaign identity reread missing after self-test'

require_campaign_reread_after() {
    local anchor=$1 anchor_count anchor_line next_statement
    anchor_count=$(/usr/bin/grep -Fc -- "$anchor" "$SELF")
    [[ $anchor_count == 1 ]] || fail 'campaign identity reread missing after self-test'
    anchor_line=$(/usr/bin/grep -nF -- "$anchor" "$SELF" | /usr/bin/cut -d: -f1)
    next_statement=$(/usr/bin/awk -v start="$anchor_line" '
        NR <= start || /^[[:space:]]*$/ {next}
        /^[[:space:]]*#/ {next}
        /^[[:space:]]*fi[[:space:]]*$/ {next}
        {print; exit}
    ' "$SELF")
    [[ $next_statement =~ ^[[:space:]]*verify_admitted_campaign_identity[[:space:]]*$ ]] ||
        fail 'campaign identity reread missing after self-test'
}

reread_runner_prefix=runner
reread_unexpected_prefix=unexpected
reread_live_prefix=live
campaign_reread_anchors=(
    "$reread_runner_prefix self-test positive control failed:"
    "$reread_runner_prefix durable-publish positive control output mismatch:"
    "$reread_runner_prefix pure-mock environment observation mismatch:"
    "$reread_runner_prefix cgroup containment output mismatch:"
    "$reread_runner_prefix cgroup precommit counterexample output mismatch:"
    "$reread_unexpected_prefix precommit authority failed at unrelated assertion:"
    "$reread_runner_prefix checked publication write output mismatch:"
    "$reread_runner_prefix publication tamper output mismatch:"
    "$reread_runner_prefix hard-deadline positive control output mismatch:"
    "$reread_live_prefix fixture test-output hash mismatch"
    "$reread_runner_prefix timeout-tree positive control output mismatch:"
    "$reread_runner_prefix publish-crash control output mismatch:"
    "$reread_runner_prefix self-test mutation failed at unrelated assertion:"
)
for anchor in "${campaign_reread_anchors[@]}"; do
    require_campaign_reread_after "$anchor"
done

runner_literals=(
    '/root/cubr-new24-full-binary-g6-src-a'
    '/root/cubr-new24-full-binary-g6-src-b'
    '/root/cubr-new24-full-binary-g6-target-a'
    '/root/cubr-new24-full-binary-g6-target-b'
    '/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811/receipt.env'
    '/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env'
    '/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env'
    '/root/cubr-new24-full-binary-g6-20260811'
    '/root/cubr-new24-full-binary-g6-map-dryrun-20260811'
    'cubr-new24-full-binary-g6-admission-20260811.service'
    'cubr-new24-full-binary-g6-20260811.service'
    '/root/phaseC/corpus_manifest.tsv'
    '/root/corpus-full/silesia'
    '830a9a31deb00926a97f3fa5bd74f58003573fc0'
    'readonly CAMPAIGN_BUDGET_SECONDS=14400'
    'readonly MAP_BUILD_TIMEOUT_SECONDS=1200'
    'readonly EVIDENCE_PART_MAX_BYTES=90000000'
    'readonly EXPECTED_INSTRUCTION_COUNT=739548'
    'readonly EXPECTED_PAGE_SIZE=4096'
    'readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd'
    'readonly CYCLE_DISAGREEMENT_MAX=0.10'
    'readonly RECORD_RATIO_MAX=1.10'
    'readonly SHARE_DELTA_MAX=1.00'
    'readonly SAMPLE_COUNT_MIN=4787'
    'readonly ZERO_HIT_BOUND_MAX=0.001'
    'readonly -a PIN=(/usr/bin/taskset -c 0-15)'
    'CUBR_THREADS=4'
    'RAYON_NUM_THREADS=4'
    'OMP_NUM_THREADS=4'
    'MKL_NUM_THREADS=4'
    'Type=exec Restart=no RuntimeMaxSec=4h KillMode=control-group KillSignal=SIGTERM FinalKillSignal=SIGKILL'
    'readonly PUBLISHING=$OUT.publishing'
    'readonly LATE=$OUT.late'
    'readonly PUBLICATION_COMMIT_MARGIN_SECONDS=5'
    'time.CLOCK_MONOTONIC'
    'run_terminal_finalization'
    '--finalize-worker'
    'late final quarantined'
    'unit InvocationID does not match current process'
    'systemd MainPID does not match current process'
    'NRestarts is not 0'
    'ControlGroup'
    'cgroup.procs'
    'cgroup_new_pid'
    'assert_cgroup_no_new_pids || return 125'
    'new cgroup PID exists immediately before final commit'
    'publisher ancestry escaped bound cgroup before frozen baseline'
    'publisher ancestry did not reach exactly one frozen cgroup baseline PID'
    'systemctl --no-block stop'
    'CUBR_G6_ADMITTED_UNIT'
    'CUBR_G6_ADMISSION_INPUTS'
    'CUBR_G6_LAUNCH_IDENTITIES'
    'derive_admission_instrument_authority'
    'instrument mapper test blob mismatch'
    'mapper test SHA-256 derived from admission input'
    'instrument resulting-main commit is missing or malformed'
    'instrument commit is not contained in origin/main'
    'instrument runner blob mismatch'
    'instrument mapper blob mismatch'
    'instrument test blob mismatch'
    'source checkout commit mismatch'
    'source checkout is not detached'
    'source checkout tracked or untracked state is dirty'
    'CARGO_PROFILE_RELEASE_DEBUG=1'
    '2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78'
    '789119db24ae1a28a24bcc0ecbec136c7e937d9a'
    '0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9'
    '/rust/deps/gimli-0.32.3'
    '/rust/deps/hashbrown-0.16.1'
    '/rust/deps/addr2line-0.25.1'
    '/rust/deps/object-0.37.3'
    '/rust/deps/memchr-2.7.6'
    '/rust/deps/libc-0.2.183'
    '/rust/deps/miniz_oxide-0.8.9'
    '/usr/include/x86_64-linux-gnu/bits/string_fortified.h'
    '0cfa3c530938891615ab64ab5dfb72ebd8d02077d29d4410774b8a8ceff628fb'
    'libc6-dev:amd64'
    'libc6-dev'
    '2.39-0ubuntu8.8'
    'prefix-coverage-audit.tsv'
    'unclassified or escaping absolute resolver locations'
    'hostname is not dev-ai'
    'AMD EPYC 7502P 32-Core Processor'
    'one-minute load is not below 8.0'
    'task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults'
    'dickens|max|10192446|1340|435'
    'xml|max|5345280|520|175'
    'dickens|web|10192446|380|320'
    'b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82'
    'd64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37'
    'a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341'
    'b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    '0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c'
    'de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'
    '352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3'
    'normalize-elf'
    'build-map'
    'seal-admission'
    'reduce-record'
    'summarize-file'
    '--buildid-all --buildid-mmap'
    '/usr/bin/addr2line -a -f -C -i'
    '/usr/bin/time -v -o'
    '/usr/bin/gzip -n -9 -c'
    '--output-root "$map_dir"'
    '--segments-out segments.tsv --sections-out sections.tsv'
    '--map-manifest map/map-parts-manifest.json'
    '--output-root "$cell_dir"'
    '--show-mmap-events'
    '-F period,ip,dso,dsoff'
    'perf buildid-list -i'
    'binary-snapshot-before'
    'binary-snapshot-after'
    'map-parts-manifest.json'
    '--map-part-prefix g6-full-instruction-map'
    'map full reconstruction mismatch'
    'map-summary.json.gz'
    'compress_map_artifact "$map_dir/map-summary.json" "$map_dir/raw-stream-evidence.tsv"'
    'map summary deterministic gzip readback mismatch'
    'exact frozen instruction count mismatch'
    'map-admission-seal.json'
    '--toolchain-json preflight/map-toolchain.json'
    '--map-manifest map/map-parts-manifest.json'
    '--map-summary map/map-summary.json.gz'
    '--raw-stream-evidence map/raw-stream-evidence.tsv'
    '--seal-out map-admission-seal.json'
    '--reuse-decision REJECTED_IDENTITY_MISMATCH'
    'cubr-new24-g6-map-admission-seal-v1'
    'map manifest has extra or missing parts'
    'map evidence part exceeds 90000000 bytes'
    'full_map_elapsed_seconds'
    'full_map_peak_rss_kib'
    'map-worker.stderr.txt'
    '/usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin'
    '/usr/bin/bash "${BASH_SOURCE[0]}" --map-worker "$PARTIAL"'
    'mapping_schema_sha256=%s'
    '--mapping-schema-sha256 "$MAPPING_SCHEMA_SHA256"'
    '--segments map/segments.tsv --page-size "$EXPECTED_PAGE_SIZE"'
    'attribution record evidence failure'
    'attribution summary evidence failure'
    'TIMING-DONE.STAMP'
    'FAILED.STAMP'
    'special or symlink node found in evidence tree'
    'evidence file exceeds 90000000 bytes'
    'rename_noreplace(publishing_path, destination_path)'
    'partial tree contains authoritative completion marker'
    '.TIMING-DONE.STAMP.pending'
    'def write_all(fd, payload):'
    'if written <= 0:'
    'publication_marker_bytes'
    'map_seal_sha256='
    'schema=g6-admission-identity-set-v1'
    '[[ $(/usr/bin/wc -l <"$target") == 58 ]]'
    'performance_sample=NO\ncampaign_cells=0\nretained_perf_data=0\ncampaign_sample_rows=0\nselection=NO-SELECT'
    'current_profile_g6_launch_identity_parser=PASS schema=g6-protected-launch-identities-v1 keys=123'
    'current_profile_g6_admission_no_performance_test=PASS'
    'os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK'
    'closed identity input exceeds size bound'
    'admission-tree-manifest.tsv'
    'current_profile_g6_stable_identity_compare=PASS'
    'write_new_stdin()'
    'admission retained perf.data'
    'admission retained address-smoke raw artifact'
    'admission contains max/min attribution summary'
    'admission contains attribution summary'
    'admission contains pstat artifact'
    'admission contains prec artifact'
    'admission contains campaign cell directory'
    'admission journal contains cell row'
    'final_path='
    'marker payload authentication failed'
    'authenticate_manifest(publishing_path)'
    'precommit_cgroup_guard()'
    'rename_noreplace(authoritative, rejected)'
    'rejection publication marker authentication failed'
    'os.fsync(parent_fd)'
    'require_before(commit_deadline_ns, "final rename acceptance")'
    'FINALIZATION_RESERVE_SECONDS=120'
    '/usr/bin/ps -eo pid=,ppid=,comm=,args= >"$snapshot"'
    '-v runner="$runner" -v parent="$parent"'
    '$1 != runner && $1 != parent'
    'orphan candidate/perf process or competing Cubrim/Cargo/Rust/current-profile runner'
    'refuse_existing_output'
    'remaining_budget_seconds'
    '--kill-after=10s'
    'cmp --'
    'NO-SELECT'
    'VALID-ATTRIBUTION'
    'VALID-DESCRIPTIVE'
    'mechanical-address-join-feasibility-only'
    'performance_interpretation'
    '/usr/bin/rm -- "$root/address-smoke.record.json"'
    'VOID'
)
for literal in "${runner_literals[@]}"; do
    require_runner_fixed "$literal"
done

require_runner_named '(( $# == 2 )) || die '\''live cgroup fixture requires exactly one export directory'\''' \
    'live cgroup dispatch does not validate its exact second argument'
require_runner_named 'self_test_cgroup_live "$2"' \
    'live cgroup dispatch drops its export-directory argument'
require_runner_named 'verify_live_cgroup_fixture_result "$rc" "$fixture_result" "$fixture_unit" "$systemd_output" "$export_dir"' \
    'live cgroup fixture does not authenticate the terminal systemd result'
require_runner_named '(( rc == 0 )) || die '\''live fixture systemd-run status is not expected success'\''' \
    'live cgroup fixture does not accept the authenticated rc=0 success form'
require_runner_named 'terminated = "Main processes terminated with: code=killed/status=TERM"' \
    'live cgroup fixture accepts an unauthenticated terminal process form'
require_runner_named 'if any("live_cgroup_guard_unexpected_return=" in line for line in result_lines):' \
    'live cgroup fixture does not reject an unexpected worker return'
if [[ $LIVE_BEHAVIOR_MUTATION_LANE == 0 ]]; then
    require_runner_named 'invocation_id=$CGROUP_EVIDENCE_INVOCATION_ID' \
        'live cgroup worker evidence is not bound to its systemd invocation'
    live_result_source=$(function_source verify_live_cgroup_fixture_result)
    for live_result_control in \
        'fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)' \
        'info.st_nlink != 1' \
        'not stat.S_ISREG(info.st_mode)' \
        'info.st_size > MAX_BYTES' \
        'payload.decode("utf-8", errors="strict")' \
        'not payload.endswith(b"\n") or b"\r" in payload' \
        'source_identity_changed' \
        'result_invocation != invocation' \
        'components[-1] != unit'; do
        [[ $live_result_source == *"$live_result_control"* ]] ||
            fail "live result verifier missing load-bearing control: $live_result_control"
    done
fi
reject_runner_fixed "(( rc != 0 )) || die 'live fixture unexpectedly returned success'"

launch_remote_source=$(function_source verify_launch_main_matches_remote)
[[ $launch_remote_source == *'run_bounded "$timeout_seconds" /usr/bin/git -C "$repo" ls-remote --exit-code origin refs/heads/main'* ]] ||
    fail 'campaign remote-main query is not bounded ls-remote origin'
remote_parser_source=$(function_source parse_remote_main_output)
[[ $remote_parser_source == *'pattern=$'\''^([0-9a-f]{40})\trefs/heads/main$'\'''* ]] ||
    fail 'remote main parser does not require exactly one canonical ref row'
[[ $remote_parser_source == *'[[ $remote_main == "$expected" ]]'* ]] ||
    fail 'fresh remote main equality comparison is missing'
launch_auth_source=$(function_source authenticate_campaign_launch_inputs)
scientific_auth_source=$(function_source authenticate_campaign_scientific_identities)
process_classifier_source=$(function_source classify_process_snapshot)
manifest_auth_source=$(function_source authenticate_protected_admission_manifest)
reuse_map_source=$(function_source reuse_admission_map)
remote_main_gate_offset=$(/usr/bin/awk 'index($0, "verify_launch_main_matches_remote") {print NR; exit}' <<<"$launch_auth_source")
launch_blob_offset=$(/usr/bin/awk 'index($0, "actual_prereg_blob=") {print NR; exit}' <<<"$launch_auth_source")
[[ -n $remote_main_gate_offset && -n $launch_blob_offset && $remote_main_gate_offset -lt $launch_blob_offset &&
   $launch_auth_source == *'verify_launch_main_matches_remote "$INSTRUMENT_REPO" "$LAUNCH_MAIN" 30'* ]] ||
    fail 'campaign launch must equal fresh remote main before blob use'
[[ $launch_auth_source == *'authenticate_campaign_scientific_identities "$snapshot_identities" "$ADMISSION_OUT" "$CORPUS_MANIFEST"'* ]] ||
    fail 'campaign launch scientific identity authentication missing'
for scientific_control in \
    '"corpus-row"' '"corpus-manifest"' '"map-gzip-manifest"' '"map-stream"' \
    '"map-reverse-index"' '"mapping-schema"' '"sanitized-environment"' \
    'map-parts-manifest.json' 'map-admission-seal.json' 'raw-stream-evidence.tsv' \
    'sanitized-environment-contract.txt' 'family_reverse_index' \
    'mapper_sha256={expected_mapper_sha}' 'mapper_test_sha256={expected_mapper_test_sha}' \
    'deployment_mode=admission' 'CUBR_G6_ADMITTED_UNIT,CUBR_G6_ADMISSION_INPUTS' \
    'campaign scientific sanitized environment contract mismatch'; do
    [[ $scientific_auth_source == *"$scientific_control"* ]] ||
        fail "campaign scientific identity authentication lost control: $scientific_control"
done
[[ $process_classifier_source == *'g6_runner=(comm == "bash" && NF == 6 &&'* &&
   $process_classifier_source == *'-v g6_runner_path="$RUNNER_SOURCE"'* &&
   $process_classifier_source == *'$5 == g6_runner_path'* &&
   $process_classifier_source == *'($6 == "--campaign" || $6 == "--admission-feasibility")'* &&
   $process_classifier_source == *'$1 != runner && $1 != parent'* ]] ||
    fail 'G6 process classifier production signature missing'
for manifest_control in \
    'manifest_name = "evidence-sha256.tsv"' 'marker_name = "TIMING-DONE.STAMP"' \
    'os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK' 'info.st_nlink != 1' \
    'info.st_mode & 0o222' 'stat.S_ISLNK(info.st_mode)' \
    'actual_files != expected_files or actual_dirs != expected_dirs' \
    'hashlib.sha256(payload).hexdigest()' 'protected admission manifest content mismatch'; do
    [[ $manifest_auth_source == *"$manifest_control"* ]] ||
        fail "protected admission manifest authentication lost control: $manifest_control"
done
manifest_replay_offset=$(/usr/bin/awk 'index($0, "authenticate_protected_admission_manifest") {print NR; exit}' <<<"$reuse_map_source")
map_copy_offset=$(/usr/bin/awk 'index($0, "/usr/bin/python3 -") {print NR; exit}' <<<"$reuse_map_source")
[[ -n $manifest_replay_offset && -n $map_copy_offset && $manifest_replay_offset -lt $map_copy_offset &&
   $reuse_map_source == *'authenticate_protected_admission_manifest "$ADMISSION_OUT" >/dev/null'* ]] ||
    fail 'campaign map reuse bypasses protected admission manifest authentication'
instrument_gate_source=$(function_source verify_instrument_provenance)
[[ $instrument_gate_source == *'fetch --quiet origin main'* &&
   $instrument_gate_source == *'merge-base --is-ancestor "$INSTRUMENT_COMMIT" "$repo_head"'* ]] ||
    fail 'Task9 instrument origin/main gate was removed'

full_map_source=$(function_source build_full_instruction_map)
[[ $full_map_source == *'run_process_group_bounded "$limit" /usr/bin/time -v -o "$elapsed_file"'* &&
   $full_map_source != *'/usr/bin/timeout --kill-after=10s'* ]] ||
    fail 'full-map worker is not bound to the cgroup-aware deadline wrapper'

perf_probe_source=$(function_source discover_perf_events)
[[ $perf_probe_source == *'run_bounded 30 "${PIN[@]}" /usr/bin/perf stat -x, -e "$event" -o "$PREFLIGHT_DIR/perf-$event.csv" -- /usr/bin/true'* &&
   $perf_probe_source != *'$CUBRIM'* && $perf_probe_source != *'$CORPUS_ROOT'* &&
   $perf_probe_source != *'$CORPUS_MANIFEST'* ]] ||
    fail 'admission perf capability probe target is not literal true'

post_launch_snapshot_source=$(/usr/bin/awk '
    seen {print}
    /snapshot_launch_inputs "\$G6_PREREG_SOURCE" "\$LAUNCH_IDENTITIES"/ {seen=1}
' <<<"$launch_auth_source")
post_snapshot_prereg_reopen=$({ /usr/bin/grep -E '\$G6_PREREG_SOURCE([^_A-Za-z0-9]|$)' \
    <<<"$post_launch_snapshot_source" || true; } | /usr/bin/wc -l)
post_snapshot_identity_reopen=$({ /usr/bin/grep -E '\$LAUNCH_IDENTITIES([^_A-Za-z0-9]|$)' \
    <<<"$post_launch_snapshot_source" || true; } | /usr/bin/wc -l)
[[ $launch_auth_source == *'snapshot_launch_inputs "$G6_PREREG_SOURCE" "$LAUNCH_IDENTITIES"'* &&
   $post_snapshot_prereg_reopen == 0 && $post_snapshot_identity_reopen == 0 &&
   $post_launch_snapshot_source == *'--verify-launch-identity-files "$snapshot_identities"'* ]] ||
    fail 'campaign launch authentication reopened caller input after snapshot'

main_source=$(function_source main_run)
[[ $main_source == *'write_g6_admission_identity_set "$PARTIAL"'* &&
   $main_source == *'        "$PARTIAL/sealed-identity-set.env"'* ]] ||
    fail 'campaign stable identity comparison is not bound to fresh sealed identity'
require_runner_named 'compare_g6_stable_identities "$PREFLIGHT_DIR/admission-sealed-identity-set.env"' \
    'campaign stable identity comparison is not bound to fresh sealed identity'

require_runner_named 'instrument_tree=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT^{tree}")' \
    'instrument tree is not commit-derived'

require_runner_named '--launch-identity-value "$snapshot_identities" runner_sha256) == "$EXPECTED_RUNNER_SHA"' \
    'campaign launch must compare runner SHA'
require_runner_named '--launch-identity-value "$snapshot_identities" runner_test_sha256) == "$EXPECTED_TEST_SHA"' \
    'campaign launch must compare runner test SHA'
require_runner_named '--launch-identity-value "$snapshot_identities" mapper_sha256) == "$EXPECTED_MAPPER_SHA"' \
    'campaign launch must compare mapper SHA'
require_runner_named '--launch-identity-value "$snapshot_identities" mapper_test_sha256) == "$EXPECTED_MAPPER_TEST_SHA"' \
    'campaign launch must compare mapper test SHA'
require_runner_named 'sha256sum -- "$RUNNER_SOURCE"' \
    'campaign launch must authenticate installed runner SHA'
require_runner_named 'sha256sum -- "$RUNNER_TEST_SOURCE"' \
    'campaign launch must authenticate installed runner test SHA'
require_runner_named 'sha256sum -- "$MAPPER_SOURCE"' \
    'campaign launch must authenticate installed mapper SHA'
require_runner_named 'sha256sum -- "$MAPPER_TEST_SOURCE"' \
    'campaign launch must authenticate installed mapper test SHA'
require_runner_named 'admission_identity_sha=$(launch_identity_value "$snapshot_identities" admission_identity_set_sha256)' \
    'campaign launch must compare admission identity SHA'
require_runner_named 'admission_identity_bytes=$(launch_identity_value "$snapshot_identities" admission_identity_set_bytes)' \
    'campaign launch must compare admission identity bytes'
require_runner_named '[[ $actual_prereg_blob == "$EXPECTED_G6_PREREG_BLOB" ]]' \
    'campaign launch must compare expected preregistration blob'
require_runner_named 'LAUNCH_IDENTITIES_BLOB=$actual_identities_blob' \
    'campaign launch must compare expected identity blob'
require_runner_named '[[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_prereg") == "$EXPECTED_G6_PREREG_BLOB" ]]' \
    'campaign launch must authenticate preregistration file blob'
require_runner_named '[[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_identities") == "$LAUNCH_IDENTITIES_BLOB" ]]' \
    'campaign launch must authenticate identity file blob'
require_runner_named 'sha256sum -- "$target"' \
    'campaign launch must read back persisted identity SHA'
require_runner_named 'run_bounded 30 /usr/bin/stat -c %s -- "$target"' \
    'campaign launch must read back persisted identity bytes'

reject_runner_fixed 'taskset -c 16-19'
reject_runner_fixed 'x-ray'
reject_runner_fixed 'Type=oneshot'
reject_runner_fixed '--resume'
reject_runner_fixed '--retry'
reject_runner_fixed '/usr/bin/psql'
reject_runner_fixed '/usr/bin/curl'
reject_runner_fixed 'world_benchmark_'
reject_runner_fixed 'corpus average'
reject_runner_fixed 'geometric mean'
reject_runner_fixed 'nearest instruction'
reject_runner_fixed '--foreground'
reject_runner_fixed '/usr/bin/mv -- "$OUT" "$LATE"'
reject_runner_fixed 'ps --sid'
reject_runner_fixed 'pgrep'
reject_runner_fixed 'EXPECTED_MAPPING_SCHEMA_SHA'
reject_runner_fixed 'EXPECTED_MAP_SEAL_SHA'
reject_runner_fixed 'EXPECTED_MAP_'
reject_runner_fixed 'EXPECTED_SUMMARY_'
reject_runner_fixed 'EXPECTED_PREFIX_LOCATION_ROWS'
reject_runner_fixed 'attempt": 9'
reject_runner_fixed '--seal-out map/map-admission-seal.json'
reject_runner_fixed '36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1'
reject_runner_fixed '97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314'
reject_runner_fixed '1c8f5be539eaaa94f3a64d071e859ee5eccf8f4314908e143246f47bd8760e12'
reject_runner_fixed '565cce3c44c9fb8a228184e0af37270e0caeb2160f15c36b4690bc81aa139a6f'
seal_out_count=$(/usr/bin/grep -Fc -- '--seal-out map-admission-seal.json' "$RUNNER")
[[ $seal_out_count == 1 ]] || fail 'runner seal output must be exactly one relative basename'
map_build_line=$(/usr/bin/grep -nF '/usr/bin/python3 "$MAPPER" build-map' "$RUNNER" | /usr/bin/cut -d: -f1)
map_seal_line=$(/usr/bin/grep -nF '/usr/bin/python3 "$MAPPER" seal-admission' "$RUNNER" | /usr/bin/cut -d: -f1)
[[ -n $map_build_line && -n $map_seal_line && $map_build_line -lt $map_seal_line ]] ||
    fail 'fresh map construction must precede G6 admission sealing'

require_runner_fixed '/root/cubr-new24-full-binary-g6-src-a'
require_runner_fixed '/root/cubr-new24-full-binary-g6-src-b'
require_runner_fixed '/root/cubr-new24-full-binary-g6-target-a'
require_runner_fixed '/root/cubr-new24-full-binary-g6-target-b'
require_runner_fixed '/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811/receipt.env'
require_runner_fixed '/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env'
require_runner_fixed '/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env'
require_runner_fixed '/root/cubr-new24-full-binary-g6-instrument'
require_runner_fixed 'readonly RUNNER_SOURCE=$INSTRUMENT_REPO/$RUNNER_PATH'
require_runner_fixed 'readonly RUNNER_TEST_SOURCE=$INSTRUMENT_REPO/$RUNNER_TEST_PATH'
require_runner_fixed 'readonly MAPPER_SOURCE=$INSTRUMENT_REPO/$MAPPER_PATH'
require_runner_fixed 'readonly MAPPER_TEST_SOURCE=$INSTRUMENT_REPO/$MAPPER_TEST_PATH'
require_runner_fixed 'readonly G6_PREREG_SOURCE=$INSTRUMENT_REPO/$G6_PREREG_PATH'
require_runner_fixed 'readonly G6_LAUNCH_IDENTITIES_SOURCE=$INSTRUMENT_REPO/$LAUNCH_IDENTITIES_PATH'
require_runner_fixed '/root/cubr-new24-full-binary-g6-20260811'
require_runner_fixed '/root/cubr-new24-full-binary-g6-map-dryrun-20260811'
require_runner_fixed 'cubr-new24-full-binary-g6-admission-20260811.service'
require_runner_fixed 'cubr-new24-full-binary-g6-20260811.service'
reject_runner_fixed '/root/cubr-new24-full-binary-g4-20260809'
reject_runner_fixed 'cubr-new24-full-binary-g4.service'
reject_runner_fixed 'current_profile_g4_'
reject_runner_fixed 'config/credentials/'
reject_runner_fixed '/root/cubr-new24-full-binary-g5-'
reject_runner_fixed 'cubr-new24-full-binary-g5-'
reject_runner_fixed 'cubr-new24-g5-'
for legacy_authority in CUBR_SYSTEMD_UNIT CUBR_INSTRUMENT_COMMIT \
    CUBR_EXPECTED_RUNNER_SHA256 CUBR_EXPECTED_MAPPER_SHA256 \
    CUBR_EXPECTED_TEST_SHA256 CUBR_EXPECTED_MAPPER_TEST_SHA256 \
    CUBR_LAUNCH_MAIN CUBR_LAUNCH_PREREG CUBR_LAUNCH_IDENTITIES \
    CUBR_EXPECTED_PREREG_BLOB CUBR_EXPECTED_IDENTITIES_BLOB \
    CUBR_ADMISSION_IDENTITY_SET CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256 \
    CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES; do
    reject_runner_fixed "$legacy_authority"
done
for standalone_asset in \
    /root/cubr-new24-full-binary-g6-run.sh \
    /root/cubr-new24-full-binary-g6-run-test.sh \
    /root/cubr-new24-full-binary-g6-map.py \
    /root/cubr-new24-full-binary-g6-map-test.py; do
    reject_runner_fixed "$standalone_asset"
done

sanitized_contract_source=$(function_source write_sanitized_environment_contract)
[[ $sanitized_contract_source == *'CUBR_G6_ADMITTED_UNIT,%s'* &&
   $sanitized_contract_source == *'mode_authority=CUBR_G6_ADMISSION_INPUTS'* &&
   $sanitized_contract_source == *'mode_authority=CUBR_G6_LAUNCH_IDENTITIES'* &&
   $sanitized_contract_source == *'test_boundary=CUBR_G6_TEST_ROOT_PREFIX'* ]] ||
    fail 'sanitized environment contract does not encode the exact mode-specific G6 interface'
require_runner_named 'SYSTEMD_UNIT=${CUBR_G6_ADMITTED_UNIT:-}' \
    'deployment interface does not consume CUBR_G6_ADMITTED_UNIT exactly'
require_runner_named 'ADMISSION_INPUTS=${CUBR_G6_ADMISSION_INPUTS:-}' \
    'admission interface falls back when CUBR_G6_ADMISSION_INPUTS is absent'
require_runner_named 'LAUNCH_IDENTITIES=${CUBR_G6_LAUNCH_IDENTITIES:-}' \
    'campaign interface falls back when CUBR_G6_LAUNCH_IDENTITIES is absent'
require_runner_named '[[ $SYSTEMD_UNIT == "$expected" ]]' \
    'deployment interface bypasses the exact mode-specific unit'
require_runner_named '[[ $ADMISSION_INPUTS == "$ADMISSION_INPUTS_LITERAL" ]]' \
    'admission interface bypasses the exact frozen input path'
require_runner_named '[[ $LAUNCH_IDENTITIES == "$G6_LAUNCH_IDENTITIES_SOURCE" ]]' \
    'campaign interface bypasses the exact protected launch path'
admission_input_exact_gate_count=$(/usr/bin/grep -Fc -- \
    '[[ $ADMISSION_INPUTS == "$ADMISSION_INPUTS_LITERAL" ]]' "$RUNNER")
[[ $admission_input_exact_gate_count == 2 ]] ||
    fail 'admission input does not have both interface and closed-input exact-path gates'
require_runner_named 'INSTRUMENT_COMMIT=$(closed_env_value "$ADMISSION_INPUTS" instrument_main)' \
    'instrument commit is not derived from the closed admission input'
require_runner_named 'EXPECTED_RUNNER_SHA=$(closed_env_value "$ADMISSION_INPUTS" runner_sha256)' \
    'runner SHA is not derived from the closed admission input'
require_runner_named 'local worker_root=$1 instrument_sha=$2 expected_mapper_sha=$3 expected_mapper_test_sha=$4' \
    'map worker does not consume authenticated positional identities'
require_runner_named '"$INSTRUMENT_SHA256" "$EXPECTED_MAPPER_SHA" "$EXPECTED_MAPPER_TEST_SHA"' \
    'map worker invocation does not pass all authenticated positional identities'

# G6 adds two immutable build trees, a sealed validation result, and separate
# admission/campaign authority.  These checks deliberately precede the
# behavior suite so the mechanical G5 fork is RED until the new boundaries
# exist.
require_runner_fixed 'readonly RECEIPT_SCHEMA=g6-prebuild-receipt-v1'
require_runner_fixed 'readonly VALIDATION_SCHEMA=g6-validation-manifest-v1'
require_runner_fixed 'readonly ADMISSION_INPUT_SCHEMA=g6-admission-inputs-v1'
require_runner_fixed 'readonly LAUNCH_SCHEMA=g6-protected-launch-identities-v1'
require_runner_fixed 'authenticate_g6_pre_service_inputs'
require_runner_fixed 'authenticate_g6_receipt'
require_runner_fixed 'authenticate_g6_validation_manifest'
require_runner_fixed 'authenticate_g6_admission_inputs'
require_runner_fixed 'assert_immutable_tree "$CODE_DIR"'
require_runner_fixed 'assert_immutable_tree "$CODE_DIR_B"'
require_runner_fixed 'assert_immutable_tree "$PROFILE_TARGET"'
require_runner_fixed 'assert_immutable_tree "$PROFILE_TARGET_B"'
require_runner_fixed 'reuse_admission_map'
require_runner_fixed 'if [[ -n $ROOT_PREFIX ]]; then self_test_deployment_interface; else main_run; fi'
reject_runner_fixed "'') main_run ;;"
reject_runner_fixed 'readonly CARGO=/root/.cargo/bin/cargo'
reject_runner_fixed 'run_suites'
reject_runner_fixed '--self-test-fake-cargo'

admission_source=$(function_source admission_feasibility_run)
campaign_source=$(function_source main_run)
pre_service_source=$(function_source authenticate_g6_pre_service_inputs)
receipt_auth_source=$(function_source authenticate_g6_receipt)
launch_parser_source=$(function_source verify_launch_identity_files)
[[ $admission_source == *'authenticate_g6_pre_service_inputs'* &&
   $admission_source == *'build_full_instruction_map'* &&
   $admission_source != *'run_cell '* &&
   $admission_source != *'reuse_admission_map'* ]] ||
    fail 'admission must authenticate and build one map without campaign sampling'
[[ $campaign_source == *'authenticate_g6_pre_service_inputs'* &&
   $campaign_source == *'authenticate_campaign_launch_inputs'* &&
   $campaign_source == *'reuse_admission_map'* &&
   $campaign_source != *'build_full_instruction_map'* &&
   $campaign_source != *'run_suites'* ]] ||
    fail 'campaign must authenticate and reuse the admission map without Cargo'
[[ $pre_service_source == *'authenticate_g6_receipt'* &&
   $pre_service_source == *'authenticate_g6_validation_manifest'* &&
   $pre_service_source == *'authenticate_g6_admission_inputs'* ]] ||
    fail 'pre-service authentication must consume receipt, validation, and admission inputs'
for immutable_control in \
    'assert_immutable_tree "$CODE_DIR"' \
    'assert_immutable_tree "$CODE_DIR_B"' \
    'assert_immutable_tree "$PROFILE_TARGET"' \
    'assert_immutable_tree "$PROFILE_TARGET_B"' \
    'source_tree_a_manifest_bytes' \
    'source_tree_b_manifest_bytes' \
    'target_a_manifest_bytes' \
    'target_b_manifest_bytes'; do
    [[ $receipt_auth_source == *"$immutable_control"* ]] ||
        fail "receipt authentication lost immutable-tree control: $immutable_control"
done
[[ $launch_parser_source == *'closed_env_validate "$identity" "$LAUNCH_SCHEMA" "$LAUNCH_KEYS"'* &&
   $launch_parser_source != *'launch-preregistration'* &&
   $launch_parser_source != *'protected-launch-identities-v1-begin'* ]] ||
    fail 'protected launch parser is not standalone and closed-schema'
[[ $campaign_source != *'/cargo'* && $campaign_source != *'$CARGO'* ]] ||
    fail 'campaign production path invokes Cargo'

receipt_keys='binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 build_cpuset campaign_artifact_count cargo_build_args_sha256 cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256 cargo_profile_release_debug cargo_version cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head map_artifact_count mkl_num_threads omp_num_threads perf_data_count prebuild_helper_blob prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob prebuild_test_sha256 rayon_num_threads rustc_commit rustc_version schema service_count source_commit source_tree_a_git_tree source_tree_a_manifest_bytes source_tree_a_manifest_sha256 source_tree_b_git_tree source_tree_b_manifest_bytes source_tree_b_manifest_sha256 target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes target_b_manifest_sha256'
validation_keys='binary_build_id binary_sha256 build_cpuset campaign_artifact_count cargo_lock_bytes cargo_lock_sha256 cargo_test_release_log_bytes cargo_test_release_log_sha256 cargo_version cubr_threads instrument_main map_artifact_count mkl_num_threads omp_num_threads output_tree_manifest_bytes output_tree_manifest_sha256 perf_data_count rayon_num_threads rustc_commit rustc_version schema scheme_roundtrip_log_bytes scheme_roundtrip_log_sha256 service_count source_commit source_tree_manifest_bytes source_tree_manifest_sha256 suite_commands_sha256 target_tree_manifest_bytes target_tree_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_test_blob validation_test_sha256'
admission_input_keys='admission_output_root admission_unit binary_a_build_id binary_a_sha256 binary_b_build_id binary_b_sha256 g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head g6_prereg_blob instrument_main mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256 prebuild_helper_blob prebuild_helper_sha256 prebuild_test_blob prebuild_test_sha256 receipt_bytes receipt_schema receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256 schema source_commit validation_helper_blob validation_helper_sha256 validation_manifest_bytes validation_manifest_sha256 validation_test_blob validation_test_sha256'
launch_keys='admission_control_group admission_identity_set_bytes admission_identity_set_sha256 admission_input_bytes admission_input_sha256 admission_instrument_main admission_invocation_id admission_journal_bytes admission_journal_sha256 admission_main_pid admission_output_manifest_bytes admission_output_manifest_sha256 admission_unit admission_unit_properties_bytes admission_unit_properties_sha256 binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 build_cpuset campaign_output_root campaign_unit cargo_build_args_sha256 cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256 cargo_profile_release_debug cargo_version corpus_dickens_max_archive_sha256 corpus_dickens_max_bytes corpus_dickens_max_decode_timeout_seconds corpus_dickens_max_encode_timeout_seconds corpus_dickens_max_original_sha256 corpus_dickens_web_archive_sha256 corpus_dickens_web_bytes corpus_dickens_web_decode_timeout_seconds corpus_dickens_web_encode_timeout_seconds corpus_dickens_web_original_sha256 corpus_manifest_bytes corpus_manifest_sha256 corpus_xml_max_archive_sha256 corpus_xml_max_bytes corpus_xml_max_decode_timeout_seconds corpus_xml_max_encode_timeout_seconds corpus_xml_max_original_sha256 cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head g6_prereg_blob map_admission_seal_bytes map_admission_seal_sha256 map_gzip_manifest_bytes map_gzip_manifest_sha256 map_gzip_member_count map_instruction_row_count map_reverse_index_bytes map_reverse_index_sha256 map_reverse_row_count map_stream_bytes map_stream_sha256 mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256 mapping_schema_sha256 mkl_num_threads omp_num_threads prebuild_helper_blob prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob prebuild_test_sha256 rayon_num_threads receipt_bytes receipt_schema receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256 rustc_commit rustc_version sanitized_env_contract_sha256 schema source_commit source_tree_a_git_tree source_tree_a_manifest_bytes source_tree_a_manifest_sha256 source_tree_b_git_tree source_tree_b_manifest_bytes source_tree_b_manifest_sha256 target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes target_b_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_manifest_bytes validation_manifest_sha256 validation_test_blob validation_test_sha256'
require_runner_fixed "$receipt_keys"
require_runner_fixed "$validation_keys"
require_runner_fixed "$admission_input_keys"
require_runner_fixed "$launch_keys"

cell_count=$({ /usr/bin/grep -E "^    'silesia\|(dickens|xml)\|(max|web)\|" "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $cell_count == 3 ]] || fail 'cell set must contain exactly 3 rows'

decode_call_count=$({ /usr/bin/grep -E '^[[:space:]]*decode_checked "\$cell_name" (plain|pstat1|pstat2|prec1|prec2) ' "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $decode_call_count == 5 ]] || fail 'each cell must define exactly five verified decodes'
profile_archive_count=$({ /usr/bin/grep -E '^[[:space:]]*decode_checked "\$cell_name" (plain|pstat1|pstat2|prec1|prec2) "\$archive2" ' "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $profile_archive_count == 5 ]] || fail 'all five profiled decodes must use the independently reproduced second archive'

record_call_count=$({ /usr/bin/grep -F '/usr/bin/perf record -q --buildid-all --buildid-mmap -F 997 -e cycles' "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $record_call_count == 2 ]] || fail 'each cell must define exactly two build-ID MMAP record decodes'

mapper_commands=(normalize-elf build-map seal-admission reduce-record summarize-file)
for command in "${mapper_commands[@]}"; do
    /usr/bin/python3 "$MAPPER" "$command" --help >/dev/null 2>&1 ||
        invalid "mapper CLI missing command: $command"
done

layout_root=$(/usr/bin/mktemp -d)
layout_cleanup() {
    /usr/bin/chmod -R u+w -- "$layout_root" 2>/dev/null || true
    /usr/bin/rm -rf -- "$layout_root"
}
trap layout_cleanup EXIT
/usr/bin/mkdir -p -- "$layout_root/map" "$layout_root/record" "$layout_root/bin"
/usr/bin/printf '#!/bin/sh\nexit 0\n' >"$layout_root/bin/cubrim"
/usr/bin/chmod 0555 -- "$layout_root/bin/cubrim"
/usr/bin/printf '%s\n' \
    'Elf file type is DYN (Position-Independent Executable file)' \
    'Program Headers:' \
    '  Type           Offset   VirtAddr           PhysAddr           FileSiz  MemSiz   Flg Align' \
    '  LOAD           0x000000 0x0000000000000000 0x0000000000000000 0x000100 0x000100 R   0x1000' \
    '  LOAD           0x002000 0x0000000000001000 0x0000000000001000 0x000010 0x000020 R E 0x1000' \
    >"$layout_root/map/readelf-programs.txt"
/usr/bin/printf '%s\n' \
    'Section Headers:' \
    '  [Nr] Name              Type            Address          Off    Size   ES Flg Lk Inf Al' \
    '  [ 0]                   NULL            0000000000000000 000000 000000 00      0   0  0' \
    '  [ 1] .text             PROGBITS        0000000000001000 002000 000010 00  AX  0   0 16' \
    >"$layout_root/map/readelf-sections.txt"
layout_binary_sha=$(/usr/bin/sha256sum "$layout_root/bin/cubrim" | /usr/bin/awk '{print $1}')
layout_instrument_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
/usr/bin/python3 "$MAPPER" normalize-elf \
    --input-root "$layout_root" --output-root "$layout_root/map" \
    --readelf-programs map/readelf-programs.txt --readelf-sections map/readelf-sections.txt \
    --binary-sha256 "$layout_binary_sha" --source-base-id fixture-source \
    --instrument-sha256 "$layout_instrument_sha" --segments-out segments.tsv \
    --sections-out sections.tsv --summary-out elf-summary.json
/usr/bin/printf '%s\n' \
    'Disassembly of section .text:' \
    '0000000000001000 <fixture_symbol>:' \
    $'    1000:\t90\t\tnop' \
    $'    1001:\tc3\t\tret' >"$layout_root/map/objdump.txt"
/usr/bin/printf '%s\n' '0x1000' fixture '/src/foo.rs:10' '0x1001' fixture '/src/foo.rs:11' \
    >"$layout_root/map/resolver-a.txt"
/usr/bin/cp -- "$layout_root/map/resolver-a.txt" "$layout_root/map/resolver-b.txt"
/usr/bin/printf '%s\n' $'source_domain\tpackage_identity\tprefix\treplacement' \
    $'workspace\tfixture@1\t/src\t$SOURCE' >"$layout_root/map/prefix-table.tsv"
/usr/bin/python3 "$MAPPER" build-map \
    --input-root "$layout_root" --output-root "$layout_root/map" \
    --segments map/segments.tsv --sections map/sections.tsv --objdump map/objdump.txt \
    --resolver-a map/resolver-a.txt --resolver-b map/resolver-b.txt \
    --prefix-table map/prefix-table.tsv --binary-dso "$layout_root/bin/cubrim" \
    --source-base-id fixture-source --mapping-schema-sha256 "$layout_instrument_sha" \
    --map-part-prefix fixture-map --map-manifest-out map-parts-manifest.json \
    --summary-out map-summary.json --max-part-bytes 90000000
layout_build_id=0123456789abcdef0123456789abcdef01234567
/usr/bin/printf '%s  %s\n' "$layout_build_id" "$layout_root/bin/cubrim" >"$layout_root/record/buildid.txt"
/usr/bin/printf 'PERF_RECORD_MMAP2 1/1: [0x400000(0x1000) @ 0x2000 <%s>]: r-xp %s\n100 0x400000 (%s+0x2000)\n' \
    "$layout_build_id" "$layout_root/bin/cubrim" "$layout_root/bin/cubrim" >"$layout_root/record/perf.txt"
layout_size=$(/usr/bin/stat -c %s -- "$layout_root/bin/cubrim")
layout_device=$(/usr/bin/stat -c %d -- "$layout_root/bin/cubrim")
layout_inode=$(/usr/bin/stat -c %i -- "$layout_root/bin/cubrim")
for record in record-a.json record-b.json; do
    /usr/bin/python3 "$MAPPER" reduce-record \
        --input-root "$layout_root" --output-root "$layout_root/record" \
        --map-manifest map/map-parts-manifest.json --perf-script record/perf.txt \
        --segments map/segments.tsv --page-size 4096 \
        --build-id-list record/buildid.txt --binary-path bin/cubrim \
        --binary-dso "$layout_root/bin/cubrim" --binary-build-id "$layout_build_id" \
        --binary-device 00:00 --binary-inode "$layout_inode" --binary-sha256 "$layout_binary_sha" \
        --binary-size "$layout_size" --binary-stat-device "$layout_device" \
        --source-base-id fixture-source --instrument-sha256 "$layout_instrument_sha" \
        --record-out "$record"
done
/usr/bin/python3 "$MAPPER" summarize-file \
    --input-root "$layout_root" --output-root "$layout_root/record" --cell fixture \
    --record-a record/record-a.json --record-b record/record-b.json --summary-out summary.json
[[ -f $layout_root/map/fixture-map.part-00000.tsv.gz &&
   -f $layout_root/record/record-a.json && -f $layout_root/record/summary.json ]] ||
    invalid 'mapper executable layout control did not create expected artifacts'
layout_cleanup
trap - EXIT

pre_self_test_root_refs=$(
    /usr/bin/awk '/^self_test_fail\(\)/ { exit } { print }' "$RUNNER" |
        /usr/bin/grep -Eo '\$(OUT|PARTIAL|PUBLISHING|MEASURED_BINARY)\b' |
        /usr/bin/wc -l
)
[[ $pre_self_test_root_refs == 69 ]] ||
    fail "transitive campaign-root inventory changed: $pre_self_test_root_refs"
admission_selection_count=$({
    /usr/bin/grep -F '    OUT=$ADMISSION_OUT' "$RUNNER" || true
} | /usr/bin/wc -l)
[[ $admission_selection_count == 1 ]] ||
    fail 'admission root selection must use ADMISSION_OUT'
mode_root_helper=$(/usr/bin/awk '
    /^self_test_mode_roots\(\) \{/ {inside=1}
    inside {print}
    inside && /^}/ {exit}
' "$RUNNER")
[[ $mode_root_helper == *'/usr/bin/mkdir -m 0700 -- "$PARTIAL"'* ]] ||
    fail 'root self-test must create selected PARTIAL only'
run_mode_readonly_line=$(/usr/bin/grep -nF 'readonly RUN_MODE' "$RUNNER" | /usr/bin/cut -d: -f1)
first_output_readonly_line=$(/usr/bin/grep -nE '^(readonly )?(OUT|PARTIAL|PUBLISHING|LATE|MEASURED_BINARY)=' \
    "$RUNNER" | /usr/bin/head -n 1 | /usr/bin/cut -d: -f1)
[[ -n $run_mode_readonly_line && -n $first_output_readonly_line &&
   $run_mode_readonly_line -lt $first_output_readonly_line ]] ||
    fail 'RUN_MODE must precede every readonly output path'

mode_root=$(/usr/bin/mktemp -d)
set +e
CUBR_G6_TEST_ROOT_PREFIX="$mode_root" \
    /usr/bin/bash "$RUNNER" --self-test-mode-roots \
    >"$mode_root/output.txt" 2>&1
mode_rc=$?
set -e
[[ $mode_rc == 0 ]] || fail "mode-root self-test failed rc=$mode_rc"
campaign_base=$mode_root/cubr-new24-full-binary-g6-20260811
admission_base=$mode_root/cubr-new24-full-binary-g6-map-dryrun-20260811
[[ -f $admission_base/MODE-ROOT.PASS ]] || fail 'admission test root was not created'
for path in "$campaign_base" "$campaign_base.partial" \
    "$campaign_base.publishing" "$campaign_base.late"; do
    [[ ! -e $path && ! -L $path ]] ||
        fail "admission created campaign path: $path"
done
/usr/bin/chmod -R u+w -- "$mode_root"
/usr/bin/rm -rf -- "$mode_root"

launch_parser_root=$(/usr/bin/mktemp -d)
if ! /usr/bin/python3 - "$RUNNER" "$launch_parser_root" "$launch_keys" <<'PY'
from pathlib import Path
import hashlib, os, shutil, subprocess, sys

runner, root_arg, keys_arg = sys.argv[1:]
root = Path(root_arg)
keys = keys_arg.split()
if len(keys) != 123 or keys != sorted(keys) or len(keys) != len(set(keys)):
    raise SystemExit("test fixture launch key schema is not the frozen 123-key set")

git40 = {
    key for key in keys
    if key.endswith(("_blob", "_git_tree", "_main"))
}
git40.update({
    "source_commit", "g5_prereg_reviewed_head", "g5_prereg_resulting_main",
    "binary_a_build_id", "binary_b_build_id",
})
sha256 = {key for key in keys if key.endswith("_sha256")}
integers = {
    key for key in keys
    if key.endswith(("_bytes", "_count", "_pid", "_seconds", "_device", "_inode"))
}
fixed = {
    "schema": "g6-protected-launch-identities-v1",
    "source_commit": "830a9a31deb00926a97f3fa5bd74f58003573fc0",
    "g6_prereg_blob": "832504025f715a7a8873bdb563509b946f914155",
    "binary_a_sha256": "2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78",
    "binary_b_sha256": "2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78",
    "binary_a_build_id": "789119db24ae1a28a24bcc0ecbec136c7e937d9a",
    "binary_b_build_id": "789119db24ae1a28a24bcc0ecbec136c7e937d9a",
    "build_cpuset": "0-15",
    "cargo_profile_release_debug": "1",
    "cubr_threads": "4",
    "rayon_num_threads": "4",
    "omp_num_threads": "4",
    "mkl_num_threads": "4",
    "receipt_schema": "g6-prebuild-receipt-v1",
    "admission_unit": "cubr-new24-full-binary-g6-admission-20260811.service",
    "campaign_unit": "cubr-new24-full-binary-g6-20260811.service",
    "campaign_output_root": "/root/cubr-new24-full-binary-g6-20260811",
    "admission_invocation_id": "1" * 32,
    "admission_control_group": "/user.slice/g6-admission.service",
}
rows = {}
for key in keys:
    if key in fixed:
        rows[key] = fixed[key]
    elif key in git40:
        rows[key] = hashlib.sha1(key.encode()).hexdigest()
    elif key in sha256:
        rows[key] = hashlib.sha256(key.encode()).hexdigest()
    elif key in integers:
        rows[key] = "1"
    else:
        rows[key] = "fixture-value"
identity_text = "".join(f"{key}={rows[key]}\n" for key in keys)
expected = (
    "current_profile_g6_launch_identity_parser=PASS "
    "schema=g6-protected-launch-identities-v1 keys=123\n"
)

def write_identity(label, payload, mode=0o444):
    path = root / f"{label}.env"
    path.write_bytes(payload)
    path.chmod(mode)
    return path

def run_identity(path):
    return subprocess.run(
        ["/usr/bin/bash", runner, "--verify-launch-identity-files", str(path)],
        text=True, capture_output=True, check=False, timeout=2,
    )

def reject(label, payload, expected_error=None, mode=0o444):
    result = run_identity(write_identity(label, payload, mode))
    if result.returncode == 0 or (expected_error and expected_error not in result.stderr):
        raise SystemExit(
            f"launch parser mutation failed elsewhere: {label} rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

try:
    identity = write_identity("identity", identity_text.encode())
    result = run_identity(identity)
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise SystemExit(
            f"launch identity parser positive control failed: rc={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    lines = identity_text.splitlines(keepends=True)
    swapped = lines[:]
    swapped[10], swapped[11] = swapped[11], swapped[10]
    reject("missing", "".join(lines[:-1]).encode(), "closed identity key count mismatch")
    reject("duplicate", (identity_text + lines[-1]).encode(), "closed identity key count mismatch")
    reject("unknown", (identity_text + "unknown_key=value\n").encode(), "closed identity key count mismatch")
    reject("unsorted", "".join(swapped).encode(), "unknown, duplicate, missing, or unsorted")
    reject("malformed-sha", identity_text.replace(
        rows["runner_sha256"], rows["runner_sha256"][:-1], 1).encode(),
        "invalid SHA-256 identity: runner_sha256")
    reject("schema", identity_text.replace(
        "schema=g6-protected-launch-identities-v1",
        "schema=g6-protected-launch-identities-v2", 1).encode(),
        "closed identity schema mismatch")
    reject("mutable-reference", identity_text.replace(
        "cargo_version=fixture-value", "cargo_version=origin/main", 1).encode(),
        "placeholder, mutable reference, or G5 runtime value")
    reject("g5-runtime", identity_text.replace(
        "cargo_version=fixture-value",
        "cargo_version=/root/cubr-new24-full-binary-g5-runtime", 1).encode(),
        "placeholder, mutable reference, or G5 runtime value")
    reject("self-reference", identity_text.replace(
        "cargo_version=fixture-value",
        "cargo_version=CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES.env", 1).encode(),
        "placeholder, mutable reference, or G5 runtime value")
    reject("mutable-mode", identity_text.encode(), "mode is not 0444", mode=0o644)
    reject("no-newline", identity_text.rstrip("\n").encode(), "not canonical text")
    reject("extra-equals", identity_text.replace(
        "cargo_version=fixture-value", "cargo_version=fixture=value", 1).encode(),
        "invalid closed identity row")
    reject("invalid-utf8", b"\xff\n", "not exact UTF-8")
    reject("oversize", b"x" * 131073, "exceeds size bound")

    for label, kind in (
        ("symlink", "symlink"),
        ("fifo", "fifo"),
        ("directory", "directory"),
    ):
        special = root / label
        if kind == "symlink":
            special.symlink_to(identity)
        elif kind == "fifo":
            os.mkfifo(special)
        else:
            special.mkdir()
        result = run_identity(special)
        if result.returncode == 0 or "closed identity input" not in result.stderr:
            raise SystemExit(
                f"special launch input did not fail safely: {label} rc={result.returncode} "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )

    prereg = root / "prereg.md"
    prereg.write_text("# immutable prereg fixture\n", encoding="utf-8")
    snapshot_dir = root / "private-snapshot"
    snapshot_dir.mkdir(mode=0o700)
    result = subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-snapshot-launch-inputs",
         str(prereg), str(identity), str(snapshot_dir)],
        text=True, capture_output=True, check=False, timeout=2,
    )
    if (result.returncode != 0 or
            result.stdout != "current_profile_g6_launch_snapshot_test=PASS\n" or
            result.stderr):
        raise SystemExit(f"launch snapshot positive control failed: {result}")
    snapshot_prereg = snapshot_dir / "launch-preregistration.snapshot.md"
    snapshot_identity = snapshot_dir / "launch-identities.snapshot.env"
    if (snapshot_prereg.read_bytes() != prereg.read_bytes() or
            snapshot_identity.read_bytes() != identity_text.encode()):
        raise SystemExit("launch snapshot bytes differ from caller input")

    attacker = root / "attacker.env"
    attacker.write_text("schema=attacker\n", encoding="utf-8")
    identity.unlink()
    identity.symlink_to(attacker)
    result = run_identity(snapshot_identity)
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise SystemExit(f"post-snapshot caller swap affected parser authentication: {result}")
    result = subprocess.run(
        ["/usr/bin/bash", runner, "--launch-identity-value",
         str(snapshot_identity), "runner_sha256"],
        text=True, capture_output=True, check=False, timeout=2,
    )
    if result.returncode != 0 or result.stdout != rows["runner_sha256"] + "\n" or result.stderr:
        raise SystemExit(f"post-snapshot caller swap affected identity authentication: {result}")

    rejected_dir = root / "rejected-snapshot"
    rejected_dir.mkdir(mode=0o700)
    result = subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-snapshot-launch-inputs",
         str(prereg), str(identity), str(rejected_dir)],
        text=True, capture_output=True, check=False, timeout=2,
    )
    if result.returncode == 0 or "unsafe launch snapshot source" not in result.stderr:
        raise SystemExit(f"pre-snapshot caller symlink was not rejected: {result}")
finally:
    shutil.rmtree(root)
PY
then
    fail 'launch identity parser matrix failed'
fi

if [[ $SKIP_SCIENTIFIC_MATRIX == 0 ]]; then
    process_classifier_root=$(/usr/bin/mktemp -d)
    if ! /usr/bin/python3 - "$RUNNER" "$process_classifier_root" <<'PY'
from pathlib import Path
import shutil, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)
snapshot = root / "snapshot.txt"
matches = root / "matches.txt"
self_pid, parent_pid = "9001", "9002"
production_runner = "/root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-run.sh"
rows = [
    f"9101 1 bash /usr/bin/bash {production_runner} --campaign",
    f"9102 1 bash bash {production_runner} --admission-feasibility",
    f"{self_pid} 1 bash /usr/bin/bash {production_runner} --campaign",
    f"{parent_pid} 1 bash /usr/bin/bash {production_runner} --admission-feasibility",
    f"9103 1 bash /usr/bin/bash -c echo {production_runner} --campaign",
    "9104 1 python3 python3 worker.py current-profile-g6-run.sh --campaign",
    "9105 1 bash /usr/bin/bash /tmp/current-profile-g6-run.sh --campaign",
    f"9106 1 bash /usr/bin/bash {production_runner} --self-test",
    f"9107 1 bash /usr/bin/bash {production_runner} --campaign-extra",
    f"9108 1 bash /usr/bin/bash {production_runner}.note --campaign",
]
snapshot.write_text("\n".join(rows) + "\n", encoding="ascii")
try:
    result = subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-classify-process-snapshot",
         str(snapshot), str(matches), self_pid, parent_pid],
        text=True, capture_output=True, check=False, timeout=5,
    )
    expected_stdout = "current_profile_g6_process_classifier_test=PASS matches=2\n"
    expected_matches = "\n".join(rows[:2]) + "\n"
    if (result.returncode != 0 or result.stdout != expected_stdout or result.stderr or
            not matches.is_file() or matches.read_text(encoding="ascii") != expected_matches):
        raise SystemExit(f"G6 process classifier fixture failed: {result}")
finally:
    shutil.rmtree(root)
PY
    then
        fail 'G6 process classifier behavior matrix failed'
    fi

    protected_manifest_root=$(/usr/bin/mktemp -d)
    if ! /usr/bin/python3 - "$RUNNER" "$protected_manifest_root" <<'PY'
from pathlib import Path
import hashlib, os, shutil, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)

payloads = {
    "map/segments.tsv": b"segment fixture\n",
    "map/sections.tsv": b"section fixture\n",
    "map/elf-summary.json": b'{"schema":"fixture"}\n',
    "preflight/admission-tree-manifest.tsv": b"inner admission manifest fixture\n",
}

def make_case(label, mutation=None):
    case = root / label
    (case / "map").mkdir(parents=True)
    (case / "preflight").mkdir()
    for relative, payload in payloads.items():
        (case / relative).write_bytes(payload)
    listed = dict(payloads)
    if mutation == "omitted-manifest-row":
        listed.pop("map/segments.tsv")
    rows = []
    for relative, payload in sorted(listed.items()):
        rows.append(f"{hashlib.sha256(payload).hexdigest()}\t{len(payload)}\t{relative}\n")
    (case / "evidence-sha256.tsv").write_text("".join(rows), encoding="ascii")
    (case / "TIMING-DONE.STAMP").write_text("fixture marker\n", encoding="ascii")
    if mutation == "segments-drift":
        (case / "map/segments.tsv").write_bytes(b"drifted segment fixture\n")
    elif mutation == "extra-file":
        (case / "map/unlisted.txt").write_text("extra\n", encoding="ascii")
    elif mutation == "deletion":
        (case / "map/sections.tsv").unlink()
    elif mutation == "symlink":
        (case / "map/link.tsv").symlink_to("segments.tsv")
    elif mutation == "nonregular":
        os.mkfifo(case / "map/nonregular.fifo", 0o444)
    for path in sorted(case.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            path.chmod(0o555 if path.is_dir() else 0o444)
    case.chmod(0o555)
    if mutation == "writable-file":
        (case / "map/segments.tsv").chmod(0o644)
    elif mutation == "writable-directory":
        (case / "map").chmod(0o755)
    return case

def invoke(case):
    return subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-authenticate-admission-manifest", str(case)],
        text=True, capture_output=True, check=False, timeout=5,
    )

mutations = {
    "segments-drift": "protected admission manifest content mismatch: map/segments.tsv",
    "extra-file": "protected admission manifest file set mismatch",
    "deletion": "protected admission manifest file set mismatch",
    "symlink": "unsafe protected admission node: map/link.tsv",
    "nonregular": "unsafe protected admission node: map/nonregular.fifo",
    "writable-file": "protected admission node remains writable: map/segments.tsv",
    "writable-directory": "protected admission node remains writable: map",
    "omitted-manifest-row": "protected admission manifest file set mismatch",
}
try:
    positive = make_case("positive")
    result = invoke(positive)
    expected = "current_profile_g6_admission_manifest_auth_test=PASS files=4\n"
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise SystemExit(f"protected admission manifest positive control failed: {result}")
    for label, expected_error in mutations.items():
        case = make_case(label, label)
        result = invoke(case)
        if result.returncode == 0 or expected_error not in result.stderr or result.stdout:
            raise SystemExit(
                f"protected admission manifest mutation failed elsewhere: {label} "
                f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
            )
finally:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            try:
                path.chmod(0o755 if path.is_dir() else 0o644)
            except FileNotFoundError:
                pass
    root.chmod(0o755)
    shutil.rmtree(root)
PY
    then
        fail 'protected admission manifest behavior matrix failed'
    fi

    scientific_identity_root=$(/usr/bin/mktemp -d)
    if ! /usr/bin/python3 - "$RUNNER" "$scientific_identity_root" <<'PY'
from pathlib import Path
import gzip, hashlib, io, json, os, shutil, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)
admission = root / "admission"
map_dir = admission / "map"
preflight = admission / "preflight"
map_dir.mkdir(parents=True)
preflight.mkdir()

def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()

def gz(payload):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=9, mtime=0) as handle:
        handle.write(payload)
    return output.getvalue()

summary = {
    "schema": "cubr-new24-g6-static-map-summary-v3",
    "mapping_schema_sha256": "pending",
    "family_reverse_index": {
        "source": {"alpha": {"crate": "fixture", "family": "alpha"}},
        "emitted": {"beta": {"crate": "fixture", "family": "beta"}},
    },
}
mapper_sha, mapper_test_sha = "a" * 64, "b" * 64
mapping_schema = hashlib.sha256(
    f"mapper_sha256={mapper_sha}\nmapper_test_sha256={mapper_test_sha}\n".encode()
).hexdigest()
summary["mapping_schema_sha256"] = mapping_schema
summary_payload = canonical_json(summary)
summary_gzip = gz(summary_payload)
(map_dir / "map-summary.json.gz").write_bytes(summary_gzip)
fixture_payload = b"fixture stream\n"
fixture_gzip = gz(fixture_payload)
(map_dir / "objdump.txt.gz").write_bytes(fixture_gzip)
gzip_manifest = (
    "source\tuncompressed_bytes\tuncompressed_sha256\tcompressed\tcompressed_bytes\tcompressed_sha256\n"
    f"map-summary.json\t{len(summary_payload)}\t{hashlib.sha256(summary_payload).hexdigest()}\t"
    f"map-summary.json.gz\t{len(summary_gzip)}\t{hashlib.sha256(summary_gzip).hexdigest()}\n"
    f"objdump.txt\t{len(fixture_payload)}\t{hashlib.sha256(fixture_payload).hexdigest()}\t"
    f"objdump.txt.gz\t{len(fixture_gzip)}\t{hashlib.sha256(fixture_gzip).hexdigest()}\n"
).encode()
(map_dir / "raw-stream-evidence.tsv").write_bytes(gzip_manifest)
map_manifest = canonical_json({
    "schema": "cubr-new24-g6-map-parts-v1",
    "row_count": 739548,
    "full_uncompressed_bytes": 123456,
    "full_uncompressed_sha256": "c" * 64,
})
(map_dir / "map-parts-manifest.json").write_bytes(map_manifest)
(map_dir / "map-admission-seal.json").write_bytes(canonical_json({
    "schema": "cubr-new24-g6-map-admission-seal-v1",
    "mapping_schema_sha256": mapping_schema,
}))
sanitized = (
    b"schema=g6-sanitized-environment-contract-v1\n"
    b"deployment_mode=admission\n"
    b"outer_user_systemd=LC_ALL,PATH,HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS\n"
    b"service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS,CUBR_G6_ADMITTED_UNIT,CUBR_G6_ADMISSION_INPUTS\n"
    b"child_boundary=env-i\n"
    b"test_boundary=CUBR_G6_TEST_ROOT_PREFIX\n"
)
(preflight / "sanitized-environment-contract.txt").write_bytes(sanitized)

corpus = root / "corpus-manifest.tsv"
corpus.write_text(
    "corpus\tfile\ttype\tbytes\tsha256\n"
    "silesia\tdickens\ttext\t10192446\tb24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a\n"
    "silesia\txml\ttext\t5345280\t0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c\n",
    encoding="ascii",
)
reverse_payload = canonical_json(summary["family_reverse_index"])
values = {
    "corpus_dickens_max_archive_sha256": "b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82",
    "corpus_dickens_max_bytes": "10192446",
    "corpus_dickens_max_decode_timeout_seconds": "435",
    "corpus_dickens_max_encode_timeout_seconds": "1340",
    "corpus_dickens_max_original_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
    "corpus_dickens_web_archive_sha256": "a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341",
    "corpus_dickens_web_bytes": "10192446",
    "corpus_dickens_web_decode_timeout_seconds": "320",
    "corpus_dickens_web_encode_timeout_seconds": "380",
    "corpus_dickens_web_original_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
    "corpus_manifest_bytes": str(corpus.stat().st_size),
    "corpus_manifest_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
    "corpus_xml_max_archive_sha256": "d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37",
    "corpus_xml_max_bytes": "5345280",
    "corpus_xml_max_decode_timeout_seconds": "175",
    "corpus_xml_max_encode_timeout_seconds": "520",
    "corpus_xml_max_original_sha256": "0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c",
    "map_gzip_manifest_bytes": str(len(gzip_manifest)),
    "map_gzip_manifest_sha256": hashlib.sha256(gzip_manifest).hexdigest(),
    "map_gzip_member_count": "2",
    "map_instruction_row_count": "739548",
    "map_reverse_index_bytes": str(len(reverse_payload)),
    "map_reverse_index_sha256": hashlib.sha256(reverse_payload).hexdigest(),
    "map_reverse_row_count": "2",
    "map_stream_bytes": "123456",
    "map_stream_sha256": "c" * 64,
    "mapping_schema_sha256": mapping_schema,
    "sanitized_env_contract_sha256": hashlib.sha256(sanitized).hexdigest(),
}
groups = {
    **{key: "corpus-row" for key in values if key.startswith("corpus_") and not key.startswith("corpus_manifest_")},
    "corpus_manifest_bytes": "corpus-manifest",
    "corpus_manifest_sha256": "corpus-manifest",
    "map_gzip_manifest_bytes": "map-gzip-manifest",
    "map_gzip_manifest_sha256": "map-gzip-manifest",
    "map_gzip_member_count": "map-gzip-manifest",
    "map_instruction_row_count": "map-stream",
    "map_stream_bytes": "map-stream",
    "map_stream_sha256": "map-stream",
    "map_reverse_index_bytes": "map-reverse-index",
    "map_reverse_index_sha256": "map-reverse-index",
    "map_reverse_row_count": "map-reverse-index",
    "mapping_schema_sha256": "mapping-schema",
    "sanitized_env_contract_sha256": "sanitized-environment",
}
if set(groups) != set(values):
    raise SystemExit("scientific identity fixture grouping is incomplete")

for path in sorted(admission.rglob("*"), key=lambda item: len(item.parts), reverse=True):
    path.chmod(0o555 if path.is_dir() else 0o444)
admission.chmod(0o555)
corpus.chmod(0o444)

def render(current):
    return "".join(f"{key}={current[key]}\n" for key in sorted(current)).encode()

def invoke(label, current):
    identity = root / f"identity-{label}.env"
    identity.write_bytes(render(current))
    identity.chmod(0o444)
    return subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-campaign-scientific-identities",
         str(identity), str(admission), str(corpus), mapper_sha, mapper_test_sha],
        text=True, capture_output=True, check=False, timeout=5,
    )

def drift(value):
    if value.isdigit():
        return str(int(value) + 1)
    if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        return ("0" if value[0] != "0" else "1") + value[1:]
    raise ValueError(value)

try:
    result = invoke("positive", values)
    expected = "current_profile_g6_campaign_scientific_identity_test=PASS fields=28\n"
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise SystemExit(f"scientific identity positive control failed: {result}")
    for key, group in groups.items():
        mutated = dict(values)
        mutated[key] = drift(mutated[key])
        result = invoke(key, mutated)
        expected_error = f"launch scientific identity mismatch: {group}:{key}"
        if result.returncode == 0 or expected_error not in result.stderr:
            raise SystemExit(
                f"scientific identity drift failed elsewhere: {key} rc={result.returncode} "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
finally:
    for path in sorted(admission.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o755 if path.is_dir() else 0o644)
    admission.chmod(0o755)
    corpus.chmod(0o644)
    shutil.rmtree(root)
PY
    then
        fail 'campaign scientific identity matrix failed'
    fi
fi

stable_identity_root=$(/usr/bin/mktemp -d)
if ! /usr/bin/python3 - "$RUNNER" "$stable_identity_root" <<'PY'
from pathlib import Path
import hashlib, shutil, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)
keys = (
    "schema instrument_resulting_main instrument_tree prebuild_instrument_main runner_blob runner_sha256 "
    "runner_test_blob runner_test_sha256 mapper_blob mapper_sha256 mapper_test_blob "
    "mapper_test_sha256 source_commit source_tree cubrim_rs_tree receipt_sha256 receipt_bytes "
    "validation_manifest_sha256 validation_manifest_bytes admission_input_sha256 admission_input_bytes "
    "binary_a_sha256 binary_a_build_id binary_b_sha256 binary_b_build_id cargo_inputs_manifest_sha256 "
    "generated_cargo_lock_sha256 rustc_commit rustc_version cargo_version release_flags "
    "binary_sha256 binary_build_id binary_size binary_device binary_inode mapping_schema_sha256 "
    "corpus_manifest_sha256 corpus_rows_sha256 map_stream_sha256 map_manifest_sha256 "
    "map_summary_sha256 map_row_count map_part_count map_admission_seal_sha256 map_admission_seal_bytes "
    "sanitized_env_contract_sha256 runner_contract_test_sha256 runner_contract_test_bytes "
    "live_fixture_result_sha256 live_fixture_result_bytes live_fixture_test_output_sha256 "
    "live_fixture_test_output_bytes performance_sample campaign_cells retained_perf_data "
    "campaign_sample_rows selection"
).split()
excluded = {
    "binary_device", "binary_inode", "live_fixture_result_sha256", "live_fixture_result_bytes",
    "live_fixture_test_output_sha256", "live_fixture_test_output_bytes",
}
fixed = {
    "schema": "g6-admission-identity-set-v1", "performance_sample": "NO",
    "campaign_cells": "0", "retained_perf_data": "0", "campaign_sample_rows": "0",
    "selection": "NO-SELECT",
}
rows = {}
for key in keys:
    if key in fixed:
        rows[key] = fixed[key]
    elif key.endswith(("_blob", "_tree", "_commit", "_main")) or key == "binary_build_id":
        rows[key] = hashlib.sha1(key.encode()).hexdigest()
    elif key.endswith("_sha256"):
        rows[key] = hashlib.sha256(key.encode()).hexdigest()
    elif key.endswith(("_bytes", "_count", "_size", "_device", "_inode")):
        rows[key] = "1"
    else:
        rows[key] = "fixture-value"

def render(values, ordered=keys):
    return "".join(f"{key}={values[key]}\n" for key in ordered)

admitted, current = root / "admitted.env", root / "current.env"
def run_pair(left_text, right_text):
    admitted.write_text(left_text, encoding="utf-8")
    current.write_text(right_text, encoding="utf-8")
    return subprocess.run(
        ["/usr/bin/bash", runner, "--compare-g6-stable-identities", str(admitted), str(current)],
        text=True, capture_output=True, check=False, timeout=2,
    )

def changed(key, value):
    if len(value) in {40, 64} and all(char in "0123456789abcdef" for char in value):
        return ("1" if value[0] != "1" else "2") + value[1:]
    if value.isdigit():
        return str(int(value) + 1)
    return value + "-changed"

try:
    baseline = render(rows)
    result = run_pair(baseline, baseline)
    expected = "current_profile_g6_stable_identity_compare=PASS compared=52 excluded=6\n"
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise SystemExit(f"stable identity positive control failed: {result}")
    for key in keys:
        mutated = dict(rows)
        mutated[key] = changed(key, mutated[key])
        result = run_pair(baseline, render(mutated))
        if key in excluded:
            if result.returncode != 0 or result.stdout != expected or result.stderr:
                raise SystemExit(f"justified volatile exclusion rejected: {key} result={result}")
        elif result.returncode == 0:
            raise SystemExit(f"stable identity field mutation survived: {key}")
    malformed = {
        "missing": render(rows, keys[:-1]),
        "duplicate": baseline + f"{keys[-1]}={rows[keys[-1]]}\n",
        "reordered": render(rows, [keys[1], keys[0], *keys[2:]]),
    }
    for label, text in malformed.items():
        result = run_pair(baseline, text)
        if result.returncode == 0 or not any(fragment in result.stderr for fragment in
                ("key count mismatch", "invalid or reordered stable identity")):
            raise SystemExit(f"malformed stable identity survived: {label} result={result}")
finally:
    shutil.rmtree(root)
PY
then
    fail 'stable admission identity comparison matrix failed'
fi

exclusive_write_output=$(/usr/bin/bash "$RUNNER" --self-test-exclusive-writes 2>&1) ||
    fail "exclusive evidence write control failed: $exclusive_write_output"
[[ $exclusive_write_output == current_profile_g6_exclusive_write_test=PASS ]] ||
    fail "exclusive evidence write output mismatch: $exclusive_write_output"

self_test_output=
self_test_rc=0
set +e
self_test_output=$(/usr/bin/bash "$RUNNER" --self-test 2>&1)
self_test_rc=$?
set -e
if ! { (( self_test_rc == 0 )) && [[ $self_test_output == 'current_profile_g6_self_test=PASS' ]]; }; then
    invalid "runner self-test positive control failed: rc=$self_test_rc output=$self_test_output"
fi
    verify_admitted_campaign_identity

publish_output=$(/usr/bin/bash "$RUNNER" --self-test-publish 2>&1) ||
    invalid "runner durable-publish positive control failed: $publish_output"
[[ $publish_output == 'current_profile_g6_publish_test=PASS' ]] ||
    invalid "runner durable-publish positive control output mismatch: $publish_output"
    verify_admitted_campaign_identity

pure_mock_environment_output=
pure_mock_environment_rc=0
set +e
pure_mock_environment_output=$(run_pure_mock_cgroup mock.unit \
    --self-test-cgroup-environment 2>&1)
pure_mock_environment_rc=$?
set -e
assert_mock_output_isolated "$pure_mock_environment_output" mock.unit
(( pure_mock_environment_rc == 0 )) ||
    invalid "runner pure-mock environment observation failed: rc=$pure_mock_environment_rc output=$pure_mock_environment_output"
[[ $pure_mock_environment_output == 'current_profile_g6_cgroup_environment_test=PASS canary=absent unit=mock.unit' ]] ||
    invalid "runner pure-mock environment observation mismatch: $pure_mock_environment_output"
    verify_admitted_campaign_identity

cgroup_output=
cgroup_rc=0
set +e
cgroup_output=$(run_pure_mock_cgroup mock.unit --self-test-cgroup 2>&1)
cgroup_rc=$?
set -e
assert_mock_output_isolated "$cgroup_output" mock.unit
(( cgroup_rc == 0 )) ||
    invalid "runner cgroup containment control failed: rc=$cgroup_rc output=$cgroup_output"
[[ $cgroup_output == 'current_profile_g6_cgroup_test=PASS unit=mock.unit' ]] ||
    invalid "runner cgroup containment output mismatch: $cgroup_output"
    verify_admitted_campaign_identity

cgroup_precommit_output=
cgroup_precommit_rc=0
set +e
cgroup_precommit_output=$(run_pure_mock_cgroup precommit-disconnected.service \
    --self-test-cgroup-precommit 2>&1)
cgroup_precommit_rc=$?
set -e
assert_mock_output_isolated "$cgroup_precommit_output" precommit-disconnected.service
(( cgroup_precommit_rc == 0 )) ||
    invalid "runner cgroup precommit counterexample failed: $cgroup_precommit_output rc=$cgroup_precommit_rc"
[[ $cgroup_precommit_output == 'current_profile_g6_cgroup_precommit_test=PASS unit=precommit-disconnected.service' ]] ||
    invalid "runner cgroup precommit counterexample output mismatch: $cgroup_precommit_output"
    verify_admitted_campaign_identity

unexpected_precommit_output=
unexpected_precommit_rc=0
set +e
unexpected_precommit_output=$(run_pure_mock_cgroup unexpected-authority.service \
    --self-test-cgroup-precommit 2>&1)
unexpected_precommit_rc=$?
set -e
(( unexpected_precommit_rc != 0 )) ||
    fail 'precommit self-test accepted unexpected fixture authority'
[[ $unexpected_precommit_output == 'current_profile_g6_cgroup_precommit_test=FAIL unit=unexpected-authority.service reason=unexpected-fixture-unit' ]] ||
    invalid "unexpected precommit authority failed at unrelated assertion: rc=$unexpected_precommit_rc output=$unexpected_precommit_output"
    verify_admitted_campaign_identity

publish_write_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-writes 2>&1) ||
    invalid "runner checked publication write control failed: $publish_write_output"
[[ $publish_write_output == 'current_profile_g6_publish_write_test=PASS' ]] ||
    invalid "runner checked publication write output mismatch: $publish_write_output"
    verify_admitted_campaign_identity

publish_tamper_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-tamper 2>&1) ||
    invalid "runner publication tamper control failed: $publish_tamper_output"
[[ $publish_tamper_output == 'current_profile_g6_publish_tamper_test=PASS' ]] ||
    invalid "runner publication tamper output mismatch: $publish_tamper_output"
    verify_admitted_campaign_identity

hard_deadline_output=$(/usr/bin/bash "$RUNNER" --self-test-hard-deadline 2>&1) ||
    invalid "runner hard-deadline positive control failed: $hard_deadline_output"
[[ $hard_deadline_output == 'current_profile_g6_hard_deadline_test=PASS' ]] ||
    invalid "runner hard-deadline positive control output mismatch: $hard_deadline_output"
    verify_admitted_campaign_identity

case ${CUBR_REMOTE_LIVE_FIXTURE:-0} in
    0)
        (( $# == 0 )) || invalid 'unexpected live fixture capture argument'
        ;;
    1)
        (( $# == 1 )) || invalid 'live fixture capture argument missing'
        live_output=$(run_user_systemd_fixture \
            "${HOME:-}" "${XDG_RUNTIME_DIR:-}" "${DBUS_SESSION_BUS_ADDRESS:-}" "$1") ||
            invalid "runner live cgroup containment control failed: $live_output"
        [[ $live_output =~ ^current_profile_g6_cgroup_live_test=PASS\ result_sha256=([0-9a-f]{64})\ test_output_sha256=([0-9a-f]{64})$ ]] ||
            invalid "runner live cgroup containment output mismatch: $live_output"
        [[ $(sha256sum "$1/cgroup-live.tsv" | awk '{print $1}') == "${BASH_REMATCH[1]}" ]] ||
            invalid 'live fixture result hash mismatch'
        [[ $(sha256sum "$1/systemd-run.output.txt" | awk '{print $1}') == "${BASH_REMATCH[2]}" ]] ||
            invalid 'live fixture test-output hash mismatch'
        verify_admitted_campaign_identity
        ;;
    *) invalid 'CUBR_REMOTE_LIVE_FIXTURE must be 0 or 1' ;;
esac

if [[ $SELF_MUTATION_TESTS == 1 ]]; then
    timeout_tree_output=$(/usr/bin/bash "$RUNNER" --self-test-timeout-tree 2>&1) ||
        invalid "runner timeout-tree positive control failed: $timeout_tree_output"
    [[ $timeout_tree_output == *'current_profile_g6_timeout_tree_test=PASS' ]] ||
        invalid "runner timeout-tree positive control output mismatch: $timeout_tree_output"
    verify_admitted_campaign_identity

    publish_crash_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-crashes 2>&1) ||
        invalid "runner publish-crash controls failed: $publish_crash_output"
    [[ $publish_crash_output == 'current_profile_g6_publish_crash_test=PASS' ]] ||
        invalid "runner publish-crash control output mismatch: $publish_crash_output"
    verify_admitted_campaign_identity
fi

trap_line=$(line_of_last '^[[:space:]]{4}trap on_exit EXIT$')
partial_line=$(line_of_last '^[[:space:]]{4}/usr/bin/mkdir -m 0700 -- "\$PARTIAL"$')
launch_auth_line=$(line_of_last '^[[:space:]]{4}authenticate_campaign_launch_inputs$')
admission_line=$(line_of_last '^[[:space:]]{4}admission "\$PREFLIGHT_DIR" 1$')
pre_service_line=$(line_of_last '^[[:space:]]{4}authenticate_g6_pre_service_inputs$')
validation_line=$(line_of_last '^[[:space:]]{4}authenticate_validation_suite_evidence$')
identity_capture_line=$(line_of_last '^[[:space:]]{4}capture_g6_identity_inputs$')
map_line=$(line_of_last '^[[:space:]]{4}reuse_admission_map$')
stable_identity_line=$(line_of_last '^[[:space:]]{4}compare_g6_stable_identities "\$PREFLIGHT_DIR/admission-sealed-identity-set.env" \\$')
fixture_line=$(line_of_last '^[[:space:]]{4}verify_feasibility_fixture "\$PARTIAL"$')
smoke_line=$(line_of_last '^[[:space:]]{4}verify_address_join_smoke "\$PARTIAL"$')
cells_line=$(line_of_last '^[[:space:]]{4}for cell in "\$\{CELLS\[@\]\}"; do$')
(( trap_line < partial_line && partial_line < pre_service_line && pre_service_line < launch_auth_line &&
    launch_auth_line < admission_line && admission_line < validation_line &&
    validation_line < identity_capture_line && identity_capture_line < map_line &&
    map_line < stable_identity_line && stable_identity_line < fixture_line &&
    fixture_line < smoke_line && smoke_line < cells_line )) ||
    fail 'main ordering must be sealed auth -> launch auth -> admission -> validation evidence -> capture -> map reuse -> stable identity compare -> fixture/perf -> cells'

finalizing_line=$(line_of_last '^[[:space:]]*FINALIZING=1$')
terminal_line=$(line_of_last '^[[:space:]]*run_terminal_finalization$')
(( finalizing_line < terminal_line )) ||
    fail 'completion ordering must be finalization mode -> bounded terminal finalization'
next_after_terminal=$(/usr/bin/sed -n "$((terminal_line + 1))p" "$RUNNER")
[[ $next_after_terminal == '}' ]] || fail 'terminal finalization must be last fallible main-run operation'

if ! /usr/bin/python3 - "$RUNNER" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
start = text.index("admission_feasibility_run() {")
end = text.index("\n}\n\nself_test()", start) + 2
body = text[start:end]
required = [
    'trap on_exit EXIT',
    '[[ $RUN_MODE == admission && $OUT == "$ADMISSION_OUT" ]]',
    'refuse_existing_output',
    '/usr/bin/mkdir -m 0700 -- "$PARTIAL"',
    'authenticate_g6_pre_service_inputs',
    'admission "$PREFLIGHT_DIR" 1',
    'authenticate_validation_suite_evidence',
    'capture_g6_identity_inputs',
    'build_full_instruction_map',
    'verify_feasibility_fixture "$PARTIAL"',
    'verify_address_join_smoke "$PARTIAL"',
    'assert_admission_has_no_performance "$PARTIAL"',
    'write_g6_admission_identity_set "$PARTIAL"',
    'CAMPAIGN_STATUS=NO-PERFORMANCE-ADMISSION',
    'FINALIZING=1',
    'run_terminal_finalization',
]
positions = [body.index(item) for item in required]
if positions != sorted(positions):
    raise SystemExit("admission feasibility sequence is reordered")
if "authenticate_campaign_launch_inputs" in body or "run_cell" in body or "reuse_admission_map" in body:
    raise SystemExit("admission feasibility reached campaign-only work")
if text.count("\n    capture_g6_identity_inputs\n") != 2:
    raise SystemExit("identity inputs must be captured in both modes")
PY
then
    fail 'admission feasibility sequence contract failed'
fi

live_result_root=$(/usr/bin/mktemp -d)
if ! /usr/bin/python3 - "$RUNNER" "$live_result_root" <<'PY'
from pathlib import Path
import hashlib, os, shutil, socket, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)
unit = "current-profile-g6-cgroup-selftest-4242.service"
other_unit = "current-profile-g6-cgroup-selftest-9999.service"
invocation = "a" * 32
other_invocation = "b" * 32
control_group = "/user.slice/user-1000.slice/user@1000.service/app.slice/" + unit
baseline_result = (
    f"2026-08-11T00:00:00Z\tcgroup_new_pid=4243 control_group={control_group} "
    f"invocation_id={invocation}\n"
    f"2026-08-11T00:00:01Z\tunit_stop_request={unit} scope=user\n"
).encode()
baseline_output = (
    f"Running as unit: {unit}; invocation ID: {invocation}\n"
    "Finished with result: success\n"
    "Main processes terminated with: code=killed/status=TERM\n"
    "Service runtime: 1.234s\n"
    "CPU time consumed: 10ms\n"
    "Memory peak: 1.0M\n"
    "Memory swap peak: 0B\n"
).encode()

def invoke(label, rc=0, result_bytes=baseline_result, output_bytes=baseline_output,
           result_arg=None, prepare=None, env_extra=None):
    case = root / label
    case.mkdir()
    export = case / "export"
    export.mkdir()
    result_file = case / "cgroup-live.tsv"
    output_file = case / "systemd-run.output.txt"
    result_file.write_bytes(result_bytes)
    output_file.write_bytes(output_bytes)
    if prepare is not None:
        prepare(result_file, output_file, export)
    env = os.environ.copy()
    env.update(env_extra or {})
    completed = subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-verify-cgroup-live-result", str(rc),
         str(result_arg or result_file), unit, str(output_file), str(export)],
        text=True, capture_output=True, check=False, timeout=3, env=env,
    )
    return completed, result_file, output_file, export

def expect_reject(label, expected_error, **kwargs):
    completed, _, _, export = invoke(label, **kwargs)
    if completed.returncode == 0 or expected_error not in completed.stderr:
        raise SystemExit(f"live result negative failed elsewhere: {label} result={completed}")
    if list(export.iterdir()):
        raise SystemExit(f"rejected live result exported evidence: {label}")

try:
    completed, result_file, output_file, export = invoke("positive")
    result_sha = hashlib.sha256(baseline_result).hexdigest()
    output_sha = hashlib.sha256(baseline_output).hexdigest()
    expected_stdout = (
        "current_profile_g6_live_result_test=PASS "
        f"result_sha256={result_sha} test_output_sha256={output_sha}\n"
    )
    if completed.returncode != 0 or completed.stdout != expected_stdout or completed.stderr:
        raise SystemExit(f"authenticated rc=0 live result was rejected: {completed}")
    if ((export / "cgroup-live.tsv").read_bytes() != baseline_result or
            (export / "systemd-run.output.txt").read_bytes() != baseline_output or
            (export / "cgroup-live.tsv").stat().st_mode & 0o777 != 0o444 or
            (export / "systemd-run.output.txt").stat().st_mode & 0o777 != 0o444):
        raise SystemExit("authenticated export is not the verified byte payload")

    completed, _, _, _ = invoke(
        "metadata-extra-record",
        env_extra={"CUBR_G6_TEST_VERIFIER_METADATA_SUFFIX": "unexpected"},
    )
    if (completed.returncode == 0 or
            "live result verifier metadata is not exactly one canonical record" not in completed.stderr or
            "current_profile_g6_live_result_test=PASS" in completed.stdout):
        raise SystemExit(f"newline-delimited verifier metadata survived: {completed}")

    cases = {
        "nonzero-status": dict(rc=1, expected_error=
            "live fixture systemd-run status is not expected success"),
        "false-success": dict(output_bytes=baseline_output.replace(
            b"code=killed/status=TERM", b"code=exited/status=0"), expected_error=
            "live fixture systemd-run output authentication failed"),
        "failed-result": dict(output_bytes=baseline_output.replace(
            b"Finished with result: success", b"Finished with result: failed"), expected_error=
            "live fixture systemd-run output authentication failed"),
        "wrong-output-unit": dict(output_bytes=baseline_output.replace(
            unit.encode(), other_unit.encode(), 1), expected_error=
            "live fixture systemd-run output authentication failed"),
        "cross-invocation": dict(result_bytes=baseline_result.replace(
            invocation.encode(), other_invocation.encode()), expected_error=
            "live fixture invocation evidence does not match systemd-run"),
        "unrelated-cgroup": dict(result_bytes=baseline_result.replace(
            control_group.encode(), control_group.replace(unit, other_unit).encode()), expected_error=
            "live fixture cgroup is not bound to the exact fixture unit"),
        "parent-cgroup": dict(result_bytes=baseline_result.replace(
            control_group.encode(), control_group.rsplit("/", 1)[0].encode()), expected_error=
            "live fixture cgroup is not bound to the exact fixture unit"),
        "dotdot-cgroup": dict(result_bytes=baseline_result.replace(
            control_group.encode(), (control_group.rsplit("/", 1)[0] + "/../" + unit).encode()),
            expected_error="live fixture cgroup path is not canonical"),
        "backslash-cgroup": dict(result_bytes=baseline_result.replace(
            control_group.encode(), control_group.replace("/app.slice/", "/app.slice\\").encode()),
            expected_error="live fixture cgroup path is not canonical"),
        "reverse-order": dict(result_bytes=b"".join(reversed(baseline_result.splitlines(keepends=True))),
            expected_error="live fixture result row order is not canonical"),
        "result-crlf": dict(result_bytes=baseline_result.replace(b"\n", b"\r\n"),
            expected_error="live fixture result is not canonical LF-terminated UTF-8"),
        "output-crlf": dict(output_bytes=baseline_output.replace(b"\n", b"\r\n"),
            expected_error="live fixture systemd-run output is not canonical LF-terminated UTF-8"),
        "result-no-final-lf": dict(result_bytes=baseline_result[:-1],
            expected_error="live fixture result is not canonical LF-terminated UTF-8"),
        "output-no-final-lf": dict(output_bytes=baseline_output[:-1],
            expected_error="live fixture systemd-run output is not canonical LF-terminated UTF-8"),
        "wrong-stop-unit": dict(result_bytes=baseline_result.replace(
            f"unit_stop_request={unit}".encode(), f"unit_stop_request={other_unit}".encode()),
            expected_error="live fixture did not request the exact fixture unit stop"),
        "missing-new-pid": dict(result_bytes=baseline_result.splitlines(keepends=True)[1],
            expected_error="live fixture result row order is not canonical"),
        "unexpected-return": dict(result_bytes=baseline_result + b"live_cgroup_guard_unexpected_return=125\n",
            expected_error="live cgroup guard unexpectedly returned"),
        "duplicate-terminal": dict(output_bytes=baseline_output + b"Finished with result: success\n",
            expected_error="live fixture systemd-run output authentication failed"),
        "extra-result-line": dict(result_bytes=baseline_result + b"arbitrary=extra\n",
            expected_error="live fixture result contains unexpected evidence"),
        "extra-output-line": dict(output_bytes=baseline_output + b"arbitrary extra output\n",
            expected_error="live fixture systemd-run output authentication failed"),
        "oversize-output": dict(output_bytes=baseline_output + b"Service runtime: " +
            b"A" * 1_048_576 + b"\n", expected_error="live fixture systemd-run output is missing or unsafe"),
        "invalid-utf8": dict(output_bytes=baseline_output.replace(b"1.234s", b"1.\xff234s"),
            expected_error="live fixture systemd-run output is not exact UTF-8"),
    }
    for label, kwargs in cases.items():
        expected_error = kwargs.pop("expected_error")
        expect_reject(label, expected_error, **kwargs)

    expect_reject("missing-evidence", "live fixture result is missing or unsafe",
                  prepare=lambda result, _output, _export: result.unlink())
    def make_symlink(result, _output, _export):
        target = result.with_name("symlink-target.tsv")
        result.replace(target)
        result.symlink_to(target)
    expect_reject("symlink-evidence", "live fixture result is missing or unsafe", prepare=make_symlink)
    expect_reject("hardlink-evidence", "live fixture result is missing or unsafe",
                  prepare=lambda result, _output, _export: os.link(result, result.with_name("second-link.tsv")))
    expect_reject("device-evidence", "live fixture result is missing or unsafe", result_arg=Path("/dev/null"))
    def make_fifo(result, _output, _export):
        result.unlink()
        os.mkfifo(result)
    expect_reject("fifo-evidence", "live fixture result is missing or unsafe", prepare=make_fifo)
    completed, _, _, export = invoke(
        "existing-export",
        prepare=lambda _result, _output, target: (target / "cgroup-live.tsv").write_bytes(b"old\n"),
    )
    if (completed.returncode == 0 or
            "live fixture export destination already exists" not in completed.stderr or
            sorted(path.name for path in export.iterdir()) != ["cgroup-live.tsv"] or
            (export / "cgroup-live.tsv").read_bytes() != b"old\n"):
        raise SystemExit(f"existing export destination was not preserved: {completed}")

    case = root / "source-swap"
    case.mkdir()
    export = case / "export"
    export.mkdir()
    result_file = case / "cgroup-live.tsv"
    output_file = case / "systemd-run.output.txt"
    result_file.write_bytes(baseline_result)
    output_file.write_bytes(baseline_output)
    parent_sock, child_sock = socket.socketpair()
    parent_sock.settimeout(2)
    env = os.environ.copy()
    env["CUBR_G6_LIVE_VERIFY_SYNC_FD"] = str(child_sock.fileno())
    proc = subprocess.Popen(
        ["/usr/bin/bash", runner, "--self-test-verify-cgroup-live-result", "0",
         str(result_file), unit, str(output_file), str(export)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        pass_fds=(child_sock.fileno(),),
    )
    child_sock.close()
    try:
        if parent_sock.recv(16) != b"ready\n":
            raise SystemExit("source-swap verifier did not expose its deterministic test seam")
        result_file.replace(case / "opened-source.tsv")
        result_file.write_bytes(baseline_result)
        parent_sock.sendall(b"continue\n")
        stdout, stderr = proc.communicate(timeout=2)
    except Exception:
        proc.kill()
        proc.communicate()
        raise
    finally:
        parent_sock.close()
    if (proc.returncode == 0 or "live fixture source changed during verification" not in stderr or
            stdout or list(export.iterdir())):
        raise SystemExit(f"source swap survived live result verification: rc={proc.returncode} "
                         f"stdout={stdout!r} stderr={stderr!r}")
finally:
    shutil.rmtree(root)
PY
then
    fail 'authenticated live cgroup result matrix failed'
fi

live_result_arity_root=$(/usr/bin/mktemp -d)
/usr/bin/mkdir -- "$live_result_arity_root/export"
for label in missing extra; do
    live_result_arity_output=
    live_result_arity_rc=0
    set +e
    case $label in
        missing)
            live_result_arity_output=$(/usr/bin/bash "$RUNNER" \
                --self-test-verify-cgroup-live-result 2>&1) ;;
        extra)
            live_result_arity_output=$(/usr/bin/bash "$RUNNER" \
                --self-test-verify-cgroup-live-result 0 missing.tsv fixture.service missing.output \
                "$live_result_arity_root/export" unexpected 2>&1) ;;
    esac
    live_result_arity_rc=$?
    set -e
    (( live_result_arity_rc != 0 )) || fail "live result dispatch arity survived: $label"
    [[ $live_result_arity_output == *'live result self-test requires exactly rc, result, unit, systemd output, and export directory'* ]] ||
        invalid "live result dispatch arity failed elsewhere: $label output=$live_result_arity_output"
done
/usr/bin/rm -rf -- "$live_result_arity_root"

live_cleanup_root=$(/usr/bin/mktemp -d)
/usr/bin/mkdir -- "$live_cleanup_root/export"
/usr/bin/printf 'preserve\n' >"$live_cleanup_root/unrelated.txt"
live_cleanup_output=
live_cleanup_rc=0
set +e
live_cleanup_output=$(/usr/bin/env CUBR_G6_TEST_FAIL_AFTER_ROOT=1 \
    /usr/bin/bash "$RUNNER" --self-test-cgroup-live "$live_cleanup_root/export" 2>&1)
live_cleanup_rc=$?
set -e
(( live_cleanup_rc != 0 )) || fail 'injected live cgroup failure unexpectedly passed'
[[ $live_cleanup_output =~ live\ fixture\ injected\ post-root\ failure\ root=([^[:space:]]+)\ marker=([^[:space:]]+) ]] ||
    invalid "injected live cgroup failure failed elsewhere: output=$live_cleanup_output"
leaked_live_root=${BASH_REMATCH[1]}
leaked_live_marker=${BASH_REMATCH[2]}
[[ $leaked_live_root =~ ^/tmp/current-profile-g6-cgroup-live[.][A-Za-z0-9]+$ &&
   $leaked_live_marker == "$leaked_live_root/.current-profile-g6-live-owned" ]] ||
    invalid 'injected live cgroup failure reported an unsafe cleanup target'
live_cleanup_leaked=0
if [[ -e $leaked_live_root || -L $leaked_live_root || -e $leaked_live_marker || -L $leaked_live_marker ]]; then
    live_cleanup_leaked=1
    /usr/bin/chmod -R u+w -- "$leaked_live_root" 2>/dev/null || true
    /usr/bin/rm -rf -- "$leaked_live_root"
fi
(( live_cleanup_leaked == 0 )) || fail 'live cgroup failure path leaked raw temp root'
[[ $(<"$live_cleanup_root/unrelated.txt") == preserve &&
   -z $(/usr/bin/find "$live_cleanup_root/export" -mindepth 1 -print -quit) ]] ||
    fail 'live cgroup raw-root cleanup touched caller-owned paths'
/usr/bin/rm -rf -- "$live_cleanup_root"

live_dispatch_root=$(/usr/bin/mktemp -d)
/usr/bin/mkdir -- "$live_dispatch_root/export"
/usr/bin/ln -s -- "$live_dispatch_root/export" "$live_dispatch_root/export-link"
for label in missing extra nonexistent symlink; do
    live_dispatch_output=
    live_dispatch_rc=0
    set +e
    case $label in
        missing) live_dispatch_output=$(/usr/bin/bash "$RUNNER" --self-test-cgroup-live 2>&1) ;;
        extra) live_dispatch_output=$(/usr/bin/bash "$RUNNER" --self-test-cgroup-live \
            "$live_dispatch_root/export" unexpected 2>&1) ;;
        nonexistent) live_dispatch_output=$(/usr/bin/bash "$RUNNER" --self-test-cgroup-live \
            "$live_dispatch_root/nonexistent" 2>&1) ;;
        symlink) live_dispatch_output=$(/usr/bin/bash "$RUNNER" --self-test-cgroup-live \
            "$live_dispatch_root/export-link" 2>&1) ;;
    esac
    live_dispatch_rc=$?
    set -e
    (( live_dispatch_rc != 0 )) || fail "unsafe live cgroup dispatch argument survived: $label"
    case $label in
        missing|extra)
            [[ $live_dispatch_output == *'live cgroup fixture requires exactly one export directory'* ]] ||
                invalid "live cgroup dispatch arity failed elsewhere: $label output=$live_dispatch_output" ;;
        nonexistent|symlink)
            [[ $live_dispatch_output == *'live fixture export directory is unsafe'* ]] ||
                invalid "live cgroup dispatch path failed elsewhere: $label output=$live_dispatch_output" ;;
    esac
done
/usr/bin/rm -rf -- "$live_dispatch_root"

remote_fixture_root=$(/usr/bin/mktemp -d)
if ! /usr/bin/python3 - "$RUNNER" "$remote_fixture_root" <<'PY'
from pathlib import Path
import os, shutil, subprocess, sys

runner, root_arg = sys.argv[1:]
root = Path(root_arg)
remote = root / "remote.git"
local = root / "local"
publisher = root / "publisher"

def git(*args, cwd=None):
    return subprocess.run(
        ["/usr/bin/git", *args], cwd=cwd, text=True, capture_output=True,
        check=True, timeout=5,
    ).stdout.strip()

def invoke(repo, expected, timeout="5", env=None):
    return subprocess.run(
        ["/usr/bin/bash", runner, "--self-test-verify-remote-main",
         str(repo), expected, timeout],
        text=True, capture_output=True, check=False, timeout=8,
        env=env,
    )

def commit(repo, label):
    (repo / "payload.txt").write_text(label + "\n", encoding="utf-8")
    git("add", "payload.txt", cwd=repo)
    git("-c", "user.name=G6 Fixture", "-c", "user.email=g6@example.invalid",
        "commit", "-m", label, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)

try:
    git("init", "--bare", str(remote))
    git("init", str(local))
    first = commit(local, "first")
    git("branch", "-M", "main", cwd=local)
    git("remote", "add", "origin", str(remote), cwd=local)
    git("push", "-u", "origin", "main", cwd=local)
    result = invoke(local, first)
    expected_pass = f"current_profile_g6_remote_main_test=PASS remote_main={first}\n"
    if result.returncode != 0 or result.stdout != expected_pass or result.stderr:
        raise SystemExit(f"fresh remote-main positive control failed: {result}")

    local_unmerged = commit(local, "local-unmerged")
    result = invoke(local, local_unmerged)
    if result.returncode == 0 or "launch main does not equal fresh remote main" not in result.stderr:
        raise SystemExit(f"local-unmerged launch main survived: {result}")

    git("clone", str(remote), str(publisher))
    git("checkout", "main", cwd=publisher)
    remote_advanced = commit(publisher, "remote-advanced")
    git("push", "origin", "main", cwd=publisher)
    result = invoke(local, first)
    if result.returncode == 0 or "launch main does not equal fresh remote main" not in result.stderr:
        raise SystemExit(f"stale local tracking ref survived: {result}")
    result = invoke(local, remote_advanced)
    expected_pass = f"current_profile_g6_remote_main_test=PASS remote_main={remote_advanced}\n"
    if result.returncode != 0 or result.stdout != expected_pass or result.stderr:
        raise SystemExit(f"fresh remote-main stale-tracking control failed: {result}")

    malformed_rows = (
        remote_advanced,
        f"{remote_advanced}\trefs/heads/main\n{remote_advanced}\trefs/heads/main",
    )
    for output in malformed_rows:
        result = subprocess.run(
            ["/usr/bin/bash", runner, "--self-test-parse-remote-main",
             remote_advanced, output],
            text=True, capture_output=True, check=False, timeout=2,
        )
        if result.returncode == 0 or "remote main response is malformed or ambiguous" not in result.stderr:
            raise SystemExit(f"malformed or multiple remote-main rows survived: {result}")

    timeout_repo = root / "timeout-repo"
    git("init", str(timeout_repo))
    git("remote", "add", "origin", "ssh://fixture.invalid/repo", cwd=timeout_repo)
    hang = root / "hang-ssh.sh"
    hang.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    hang.chmod(0o700)
    timeout_env = os.environ.copy()
    timeout_env["GIT_SSH_COMMAND"] = str(hang)
    result = invoke(timeout_repo, remote_advanced, timeout="1", env=timeout_env)
    if result.returncode == 0 or "fresh remote main query failed" not in result.stderr:
        raise SystemExit(f"remote-main timeout survived: {result}")
finally:
    shutil.rmtree(root)
PY
then
    fail 'fresh remote-main fixture matrix failed'
fi

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

    create_admission_schema_fixture() {
        local root=$1
        /usr/bin/python3 - "$root" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
dirs = {
    "binary", "map", "preflight", "preflight/live-fixture",
    "preflight/mapper-test-runtime", "suites",
}
files = {
    "address-smoke.binary-snapshot-after.tsv", "address-smoke.binary-snapshot-before.tsv",
    "address-smoke.out", "binary/admitted-snapshot.tsv", "binary/cubrim",
    "feasibility-1.cubr", "feasibility-2.cubr", "feasibility-decoded.bin", "feasibility-zero.bin",
    "map/elf-summary.json", "map/full-map-admission.txt", "map/full-map-resource.txt",
    "map/instruction-addresses.txt.gz", "map/map-admission-seal.json", "map/map-summary.json.gz",
    "map/map-worker.stderr.txt", "map/map-worker.stdout.txt", "map/objdump.txt.gz",
    "map/prefix-coverage-audit.tsv", "map/prefix-table.tsv", "map/raw-stream-evidence.tsv",
    "map/readelf-programs.txt", "map/readelf-sections.txt", "map/resolver-a.txt.gz",
    "map/resolver-b.txt.gz", "map/sections.tsv", "map/segments.tsv",
    "map/g6-full-instruction-map.part-00000.tsv.gz",
    "preflight/cargo-inputs-manifest.tsv", "preflight/cargo-version.txt", "preflight/cell-inputs.tsv",
    "preflight/identities.txt", "preflight/instrument-mapper-test.py",
    "preflight/instrument-mapper.py", "preflight/instrument-runner-test.sh",
    "preflight/instrument-runner.sh", "preflight/journal.tsv",
    "preflight/live-fixture/cgroup-live.tsv", "preflight/live-fixture/systemd-run.output.txt",
    "preflight/map-toolchain.json", "preflight/mapper-help.txt",
    "preflight/mapper-test-runtime/current_profile_g6_map.py",
    "preflight/mapper-test-runtime/test_current_profile_g6_map.py", "preflight/mapper-unit-test.txt",
    "preflight/perf-events.tsv", "preflight/process-conflicts.txt", "preflight/process-snapshot.txt",
    "preflight/runner-contract-test.txt", "preflight/rustc-version.txt",
    "preflight/sanitized-environment-contract.txt", "preflight/systemd-cgroup-baseline.pids",
    "preflight/systemd-contract.txt", "suites/binary-notes.txt", "suites/cargo-test-release.log",
    "suites/generated-Cargo.lock", "suites/scheme-roundtrip.log",
}
events = ("task-clock", "cycles", "instructions", "branches", "branch-misses",
          "cache-references", "cache-misses", "dTLB-load-misses", "page-faults")
files.update(f"preflight/perf-{event}.csv" for event in events)
for directory in sorted(dirs):
    (root / directory).mkdir(parents=True, exist_ok=True)
for relative in sorted(files):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture\n")
(root / "map/map-parts-manifest.json").write_text(json.dumps({
    "part_count": 1,
    "parts": [{"part_index": 0, "path": "g6-full-instruction-map.part-00000.tsv.gz"}],
}, sort_keys=True) + "\n", encoding="utf-8")
(root / "address-smoke-feasibility.json").write_text(json.dumps({
    "schema": "cubr-new24-g6-address-smoke-v1",
    "purpose": "mechanical-address-join-feasibility-only",
    "performance_interpretation": "FORBIDDEN",
    "binary_identity": {}, "binary_snapshot": {}, "binary_sample_count": 1,
    "binary_unresolved_sample_count": 0, "binary_resolution_gate_pass": True,
    "lost_record_count": 0, "conservation": {}, "symbol_consulted": False,
}, sort_keys=True) + "\n", encoding="utf-8")
(root / "preflight/cell-inputs.tsv").write_text(
    "dickens\t1\ta\tb\nxml\t1\tc\td\ndickens\t1\te\tf\n", encoding="utf-8")
(root / "preflight/perf-events.tsv").write_text(
    "".join(f"{event}\tsupported\n" for event in events), encoding="utf-8")
PY
        capture_child /usr/bin/bash "$RUNNER" --self-test-write-admission-manifest "$root"
        if ! { (( CHILD_RC == 0 )) &&
            [[ $CHILD_OUTPUT == current_profile_g6_admission_manifest_test=PASS ]]; }; then
            invalid "admission fixture manifest setup failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
        fi
    }

    expect_admission_artifact_red() {
        local label=$1 relative=$2 expected=$3 root
        root=$mutation_root/admission-$label
        /usr/bin/mkdir -p -- "$root/preflight" "$(/usr/bin/dirname -- "$root/$relative")"
        : >"$root/preflight/journal.tsv"
        printf 'mutation\n' >"$root/$relative"
        capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance "$root"
        (( CHILD_RC != 0 )) || fail "admission artifact mutation survived: $label"
        /usr/bin/grep -qF "current_profile_g6=VOID reason=$expected" <<<"$CHILD_OUTPUT" ||
            invalid "admission artifact mutation failed elsewhere: $label output=$CHILD_OUTPUT"
    }

    positive_root=$mutation_root/admission-positive
    create_admission_schema_fixture "$positive_root"
    capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance "$positive_root"
    if ! { (( CHILD_RC == 0 )) &&
        [[ $CHILD_OUTPUT == current_profile_g6_admission_no_performance_test=PASS ]]; }; then
      invalid "admission no-performance positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi
    for label in hidden-sample hidden-file hidden-dir performance-content; do
        mutation=$mutation_root/admission-strict-$label
        /usr/bin/cp -a -- "$positive_root" "$mutation"
        case $label in
            hidden-sample) printf 'campaign_sample_rows=1\n' >"$mutation/.campaign-sample-row.tsv" ;;
            hidden-file) printf 'unknown\n' >"$mutation/preflight/.unknown-evidence" ;;
            hidden-dir) /usr/bin/mkdir -- "$mutation/.unknown-directory" ;;
            performance-content) printf 'performance_sample=YES\n' >"$mutation/preflight/journal.tsv" ;;
        esac
        capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance "$mutation"
        (( CHILD_RC != 0 )) || fail "strict admission schema mutation survived: $label"
        case $label in
            performance-content)
                /usr/bin/grep -qF 'admission contains performance-like content' <<<"$CHILD_OUTPUT" ||
                    invalid "performance-content mutation failed elsewhere: $CHILD_OUTPUT" ;;
            *)
                /usr/bin/grep -Eq 'admission (file|directory) schema mismatch' <<<"$CHILD_OUTPUT" ||
                    invalid "strict admission path mutation failed elsewhere: $label output=$CHILD_OUTPUT" ;;
        esac
    done
    expect_admission_artifact_red retained_perf perf.data 'admission retained perf.data'
    for artifact in address-smoke.data address-smoke.perf-script.txt \
      address-smoke.buildid-list.txt; do
      expect_admission_artifact_red "address-${artifact//./-}" "$artifact" \
        'admission retained address-smoke raw artifact'
    done
    for cell in silesia-dickens-max silesia-xml-min; do
      expect_admission_artifact_red "summary-$cell" \
        "cells/$cell/attribution-summary.json" \
        'admission contains max/min attribution summary'
    done
    expect_admission_artifact_red generic-attribution \
      evidence/attribution-summary.json 'admission contains attribution summary'
    for sample in pstat1.perf-stat.csv pstat2.perf-stat.csv; do
      expect_admission_artifact_red "pstat-${sample//./-}" \
        "cells/silesia-xml-max/$sample" 'admission contains pstat artifact'
    done
    for repeat in prec1 prec2; do
      for suffix in data perf-script.txt buildid-list.txt record.json time.txt; do
        expect_admission_artifact_red "prec-$repeat-${suffix//./-}" \
          "cells/silesia-dickens-web/$repeat.$suffix" 'admission contains prec artifact'
      done
    done
    /usr/bin/mkdir -p -- "$mutation_root/admission-empty-cell/preflight" \
      "$mutation_root/admission-empty-cell/cells/silesia-dickens-max"
    : >"$mutation_root/admission-empty-cell/preflight/journal.tsv"
    capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance \
      "$mutation_root/admission-empty-cell"
    (( CHILD_RC != 0 )) || fail "admission campaign-state mutation survived: empty-cell"
    /usr/bin/grep -qF \
      'current_profile_g6=VOID reason=admission contains campaign cell directory' <<<"$CHILD_OUTPUT" ||
        invalid "empty-cell admission mutation failed elsewhere: rc=$CHILD_RC output=$CHILD_OUTPUT"
    /usr/bin/mkdir -p -- "$mutation_root/admission-journal/preflight"
    printf 'cell=mutation\n' >"$mutation_root/admission-journal/preflight/journal.tsv"
    capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance \
      "$mutation_root/admission-journal"
    (( CHILD_RC != 0 )) || fail "admission campaign-state mutation survived: journal-cell"
    /usr/bin/grep -qF \
      'current_profile_g6=VOID reason=admission journal contains cell row' <<<"$CHILD_OUTPUT" ||
        invalid "journal-cell admission mutation failed elsewhere: rc=$CHILD_RC output=$CHILD_OUTPUT"

    CUBR_REMOTE_LIVE_FIXTURE=1 capture_child /usr/bin/env \
        CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
        RUNNER="$RUNNER" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'current_profile_g6_contract=PASS' ]]; }; then
        invalid "positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    renamed_contract_dir=$mutation_root/deployed-basename
    renamed_contract=$renamed_contract_dir/cubr-new24-full-binary-g6-run-test.sh
    /usr/bin/mkdir -- "$renamed_contract_dir"
    /usr/bin/cp -- "$SELF" "$renamed_contract"
    capture_child /usr/bin/env CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
        RUNNER="$RUNNER" MAPPER="$MAPPER" /usr/bin/bash "$renamed_contract"
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'current_profile_g6_contract=PASS' ]]; }; then
        invalid "renamed deployed-basename control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    comment_variant_dir=$mutation_root/comment-only-adjacency
    comment_variant=$comment_variant_dir/current-profile-g6-run-test.sh
    /usr/bin/mkdir -- "$comment_variant_dir"
    /usr/bin/cp -- "$SELF" "$comment_variant"
    /usr/bin/sed -i \
        '0,/^    verify_admitted_campaign_identity$/s//    # harmless comment-only adjacency separator\n    verify_admitted_campaign_identity/' \
        "$comment_variant"
    /usr/bin/sed -i \
        "1a# harmless comment-only ${remote_live_gate_name}=0 ${nested_contract_selector}=0 example" \
        "$comment_variant"
    ! /usr/bin/cmp -s -- "$SELF" "$comment_variant" ||
        fail 'comment-only adjacency control did not change contract source'
    capture_child /usr/bin/env CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
        RUNNER="$RUNNER" MAPPER="$MAPPER" /usr/bin/bash "$comment_variant"
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'current_profile_g6_contract=PASS' ]]; }; then
        invalid "comment-only adjacency control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    capture_child /usr/bin/env CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
        RUNNER="$mutation_root/missing.sh" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 2 )) && [[ $CHILD_OUTPUT == current_profile_g6_contract=HARNESS_INVALID\ reason=runner\ not\ found\ or\ unsafe:* ]]; }; then
        invalid "setup-negative control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    expect_runner_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 behavior_lane=${4:-0} mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/env CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
            CUBR_G6_SKIP_SCIENTIFIC_MATRIX=1 \
            CUBR_G6_LIVE_BEHAVIOR_MUTATION_LANE="$behavior_lane" \
            RUNNER="$mutant" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g6_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "mutation emitted PASS: $label"
        /usr/bin/grep -qF "current_profile_g6_contract=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_live_behavior_mutant_red() {
        expect_runner_mutant_red "$1" "$2" "$3" 1
    }

    expect_self_test_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/bash "$mutant" --self-test
        (( CHILD_RC != 0 )) || fail "runner self-test mutation survived: $label"
        [[ $CHILD_OUTPUT == "current_profile_g6_self_test=FAIL reason=$expected_reason" ]] ||
            invalid "runner self-test mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
        verify_admitted_campaign_identity
    }

    expect_runtime_mutant_red() {
        local label=$1 expression=$2 expected_fragment=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/env CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 \
            CUBR_G6_SKIP_SCIENTIFIC_MATRIX=1 \
            RUNNER="$mutant" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "runtime mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g6_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "runtime mutation emitted PASS: $label"
        /usr/bin/grep -qF "$expected_fragment" <<<"$CHILD_OUTPUT" ||
            invalid "runtime mutation failed at unrelated control: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_contract_source_mutant_red() {
        local label=$1 expression=$2 expected_fragment=$3
        local basename=${4:-current-profile-g6-run-test.sh} mutant_dir mutant
        mutant_dir=$mutation_root/contract-$label
        mutant=$mutant_dir/$basename
        /usr/bin/mkdir -p -- "$mutant_dir"
        /usr/bin/cp -- "$SELF" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$SELF" "$mutant" || fail "contract source mutation did not change test: $label"
        capture_child /usr/bin/env \
            CUBR_G6_TEST_UNIT="$POISONED_PARENT_UNIT" \
            INVOCATION_ID=g4-live-authority-must-not-be-used \
            CUBR_CGROUP_SYSTEMCTL_USER=1 \
            CUBR_CGROUP_LIVE_RESULT=/tmp/g4-live-authority-must-not-be-used.result \
            CUBR_G6_PURE_MOCK_PARENT_CANARY="$PURE_MOCK_PARENT_CANARY" \
            CUBR_REMOTE_LIVE_FIXTURE=0 SELF_MUTATION_TESTS=0 CUBR_G6_SKIP_SCIENTIFIC_MATRIX=1 \
            RUNNER="$RUNNER" MAPPER="$MAPPER" \
            /usr/bin/bash "$mutant"
        (( CHILD_RC != 0 )) || fail "contract source mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g6_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "contract source mutation emitted PASS: $label"
        /usr/bin/grep -qF -- "$expected_fragment" <<<"$CHILD_OUTPUT" ||
            invalid "contract source mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_contract_source_mutant_red helper_without_empty_environment \
        's#^    /usr/bin/env -i LC_ALL=C PATH=#    /usr/bin/env LC_ALL=C PATH=#' \
        'parent poison canary reached pure mock child'
    expect_contract_source_mutant_red campaign_state_false_green_and_list \
        's#(( CHILD_RC != 0 )) || fail "admission campaign-state mutation survived: empty-cell"#(( CHILD_RC != 0 )) \&\& /usr/bin/grep -qF named-rejection <<<"$CHILD_OUTPUT"#' \
        'child rejection assertion still uses false-green AND-list'
    expect_contract_source_mutant_red helper_uses_parent_unit \
        's#CUBR_G6_TEST_UNIT="\$fixture_unit" /usr/bin/bash#CUBR_G6_TEST_UNIT="${CUBR_G6_TEST_UNIT}" /usr/bin/bash#' \
        'poisoned parent unit reached pure mock output'
    expect_contract_source_mutant_red self_hardcodes_original_basename \
        's#^SELF=.*#SELF=$TEST_DIR/current-profile-g6-run-test.sh#' \
        'contract SELF is not canonicalized from BASH_SOURCE' \
        'cubr-new24-full-binary-g6-run-test.sh'
    expect_contract_source_mutant_red nested_contract_inherits_remote_live_gate \
        '0,/CUBR_REMOTE_LIVE_FIXTURE[=]0 \(SELF_MUTATION_TESTS[=]0\)/s//\1/' \
        'nested self-contract inherited remote live gate'

    expect_contract_source_mutant_red post_self_test_reread_removed \
        's/    verify_admitted_campaign_identity/    : # mutation removed campaign identity reread/' \
        'campaign identity reread missing after self-test'
    expect_contract_source_mutant_red compensated_post_self_test_reread_moved \
        '0,/^    verify_admitted_campaign_identity$/s//    : # mutation moved campaign identity reread/; 0,/^    verify_admitted_campaign_identity$/s//    verify_admitted_campaign_identity\n    verify_admitted_campaign_identity/' \
        'campaign identity reread missing after self-test'
    expect_runner_mutant_red fixture_uses_campaign_unit \
        's/--unit="\$fixture_unit"/--unit=cubr-new24-full-binary-g6-20260811.service/' \
        'live fixture argument vector contains campaign unit'
    expect_runner_mutant_red double_fork_removed \
        's/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork()/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=0/' \
        'live fixture double-fork payload missing'
    expect_contract_source_mutant_red inherited_invocation_passed \
        's#DBUS_SESSION_BUS_ADDRESS="\$host_dbus"#DBUS_SESSION_BUS_ADDRESS="$host_dbus" INVOCATION_ID="${INVOCATION_ID:-}"#' \
        'outer live-fixture allowlist admitted INVOCATION_ID'

    expect_runner_mutant_red admission_selects_campaign \
        's/OUT=\$ADMISSION_OUT/OUT=\$CAMPAIGN_OUT/' \
        'admission root selection must use ADMISSION_OUT'
    expect_runner_mutant_red admission_creates_campaign_final \
        's#/usr/bin/mkdir -m 0700 -- "\$PARTIAL"#/usr/bin/mkdir -m 0700 -- "$CAMPAIGN_OUT"#' \
        'root self-test must create selected PARTIAL only'
    expect_runner_mutant_red mode_selected_after_readonly \
        's/readonly RUN_MODE/readonly OUT=\$CAMPAIGN_OUT\nreadonly RUN_MODE/' \
        'plan-shaped admission interface failed:'
    expect_runner_mutant_red live_dispatch_drops_export_directory \
        's/self_test_cgroup_live "\$2"/self_test_cgroup_live/' \
        'live cgroup dispatch drops its export-directory argument'
    expect_runner_mutant_red live_result_restores_rc_nonzero_assumption \
        's/(( rc == 0 )) || die '\''live fixture systemd-run status is not expected success'\''/(( rc != 0 )) || die '\''live fixture unexpectedly returned success'\''/' \
        'live cgroup fixture does not accept the authenticated rc=0 success form'
    expect_runner_mutant_red live_result_accepts_exited_zero \
        's/code=killed\/status=TERM/code=exited\/status=0/' \
        'live cgroup fixture accepts an unauthenticated terminal process form'
    expect_runner_mutant_red live_result_allows_unexpected_worker_return \
        's/if any("live_cgroup_guard_unexpected_return=" in line for line in result_lines):/if False:/' \
        'live cgroup fixture does not reject an unexpected worker return'
    expect_live_behavior_mutant_red live_result_drops_nofollow \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK/os.O_RDONLY | os.O_NONBLOCK/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_allows_hardlinks \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/info.st_nlink != 1/False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_allows_nonregular \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/not stat.S_ISREG(info.st_mode)/False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_relaxes_size_bound \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/MAX_BYTES = 1_048_576/MAX_BYTES = 2_048_576/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_ignores_invalid_utf8 \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/payload.decode("utf-8", errors="strict")/payload.decode("utf-8", errors="ignore")/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_allows_noncanonical_bytes \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/not payload.endswith(b"\\n") or b"\\r" in payload/False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_drops_source_identity_recheck \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/return source_identity_changed/return False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_allows_cross_invocation \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/result_invocation != invocation/False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_allows_cross_cgroup \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/components\[-1\] != unit/False/' \
        'authenticated live cgroup result matrix failed'
    expect_live_behavior_mutant_red live_result_accepts_multiline_metadata \
        '/^parse_live_verifier_metadata()/,/^}/s/if \[\[ \$metadata == .*; then/if false; then/' \
        'authenticated live cgroup result matrix failed'
    expect_runner_mutant_red live_result_failure_drops_raw_cleanup \
        's/trap live_cgroup_fixture_cleanup_on_exit EXIT/: # mutation removed raw-root cleanup/' \
        'live cgroup failure path leaked raw temp root'
    expect_runner_mutant_red live_result_allows_reverse_evidence_order \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/new_match = new_pid.fullmatch(result_lines\[0\])/new_match = new_pid.fullmatch(result_lines[0]) or new_pid.fullmatch(result_lines[1])/; /^verify_live_cgroup_fixture_result()/,/^}/s/stop_match = stop.fullmatch(result_lines\[1\])/stop_match = stop.fullmatch(result_lines[1]) or stop.fullmatch(result_lines[0])/; /^verify_live_cgroup_fixture_result()/,/^}/s/if new_match is None or (stop.fullmatch(result_lines\[0\]) and new_pid.fullmatch(result_lines\[1\])):/if new_match is None:/' \
        'authenticated live cgroup result matrix failed'
    expect_runner_mutant_red live_result_allows_extra_result_rows \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/if len(result_lines) > 2:/if False:/; /^verify_live_cgroup_fixture_result()/,/^}/s/if len(result_lines) != 2:/if False:/' \
        'authenticated live cgroup result matrix failed'
    expect_runner_mutant_red live_result_allows_arbitrary_output \
        '/^verify_live_cgroup_fixture_result()/,/^}/s/any(optional.fullmatch(line) is None for line in output_lines\[3:\])/False/' \
        'authenticated live cgroup result matrix failed'
    expect_runner_mutant_red remote_main_accepts_local_unmerged \
        's/\[\[ \$remote_main == "\$expected" \]\]/[[ -n $remote_main ]]/' \
        'fresh remote main equality comparison is missing'
    expect_runner_mutant_red remote_main_uses_stale_tracking_ref \
        's#ls-remote --exit-code origin refs/heads/main#show-ref --hash refs/remotes/origin/main#' \
        'campaign remote-main query is not bounded ls-remote origin'
    expect_runner_mutant_red remote_main_accepts_malformed_row \
        's#pattern=.*#pattern=$'\''^([0-9a-f]{40})$'\''#' \
        'remote main parser does not require exactly one canonical ref row'
    expect_runner_mutant_red remote_main_accepts_multiple_rows \
        's#pattern=.*#pattern=$'\''^([0-9a-f]{40})\\trefs/heads/main'\''#' \
        'remote main parser does not require exactly one canonical ref row'
    expect_runner_mutant_red remote_main_query_is_unbounded \
        's/run_bounded "\$timeout_seconds" \/usr\/bin\/git/\/usr\/bin\/git/' \
        'campaign remote-main query is not bounded ls-remote origin'
    expect_runner_mutant_red full_map_uses_raw_timeout \
        's#run_process_group_bounded "\$limit" /usr/bin/time#\/usr/bin/timeout --kill-after=10s "${limit}s" /usr/bin/time#' \
        'full-map worker is not bound to the cgroup-aware deadline wrapper'
    expect_runner_mutant_red admission_perf_probe_uses_campaign_binary \
        's#-o "\$PREFLIGHT_DIR/perf-\$event.csv" -- /usr/bin/true#-o "$PREFLIGHT_DIR/perf-$event.csv" -- "$CUBRIM"#' \
        'admission perf capability probe target is not literal true'
    expect_runner_mutant_red g6_process_classifier_removed \
        '/^classify_process_snapshot()/,/^}/s/g6_runner=(comm == "bash" && NF == 6 &&/g6_runner=(0 \&\&/' \
        'G6 process classifier production signature missing'
    expect_runner_mutant_red g6_process_classifier_wrong_runner_literal \
        's#-v g6_runner_path="\$RUNNER_SOURCE"#-v g6_runner_path="/root/cubr-new24-full-binary-g6-run.sh"#' \
        'G6 process classifier production signature missing'
    expect_runner_mutant_red admitted_unit_legacy_fallback \
        's/SYSTEMD_UNIT=${CUBR_G6_ADMITTED_UNIT:-}/SYSTEMD_UNIT=${CUBR_SYSTEMD_UNIT:-}/g' \
        'plan-shaped admission interface failed:'
    expect_runner_mutant_red admission_input_fixed_fallback \
        's/ADMISSION_INPUTS=${CUBR_G6_ADMISSION_INPUTS:-}/ADMISSION_INPUTS=${CUBR_G6_ADMISSION_INPUTS:-$ADMISSION_INPUTS_LITERAL}/' \
        'admission interface falls back when CUBR_G6_ADMISSION_INPUTS is absent'
    expect_runner_mutant_red launch_identity_fixed_fallback \
        's/LAUNCH_IDENTITIES=${CUBR_G6_LAUNCH_IDENTITIES:-}/LAUNCH_IDENTITIES=${CUBR_G6_LAUNCH_IDENTITIES:-$G6_LAUNCH_IDENTITIES_SOURCE}/' \
        'campaign interface falls back when CUBR_G6_LAUNCH_IDENTITIES is absent'
    expect_runner_mutant_red admitted_unit_exact_gate_bypassed \
        's/\[\[ \$SYSTEMD_UNIT == "\$expected" \]\]/[[ -n $SYSTEMD_UNIT ]]/' \
        'deployment interface bypasses the exact mode-specific unit'
    expect_runner_mutant_red admission_input_exact_gate_bypassed \
        '/^verify_mode_unit()/,/^}/s/\[\[ \$ADMISSION_INPUTS == "\$ADMISSION_INPUTS_LITERAL" \]\]/[[ -n $ADMISSION_INPUTS ]]/' \
        'admission input does not have both interface and closed-input exact-path gates'
    expect_runner_mutant_red launch_identity_exact_gate_bypassed \
        's/\[\[ \$LAUNCH_IDENTITIES == "\$G6_LAUNCH_IDENTITIES_SOURCE" \]\]/[[ -n $LAUNCH_IDENTITIES ]]/' \
        'campaign interface bypasses the exact protected launch path'
    expect_runner_mutant_red admission_instrument_legacy_fallback \
        's/INSTRUMENT_COMMIT=$(closed_env_value "\$ADMISSION_INPUTS" instrument_main)/INSTRUMENT_COMMIT=${CUBR_INSTRUMENT_COMMIT:-$(closed_env_value "$ADMISSION_INPUTS" instrument_main)}/' \
        'runner forbidden literal: CUBR_INSTRUMENT_COMMIT'
    expect_runner_mutant_red admission_runner_sha_legacy_fallback \
        's/EXPECTED_RUNNER_SHA=$(closed_env_value "\$ADMISSION_INPUTS" runner_sha256)/EXPECTED_RUNNER_SHA=${CUBR_EXPECTED_RUNNER_SHA256:-$(closed_env_value "$ADMISSION_INPUTS" runner_sha256)}/' \
        'runner forbidden literal: CUBR_EXPECTED_RUNNER_SHA256'
    expect_runner_mutant_red runner_uses_standalone_root \
        's#readonly RUNNER_SOURCE=\$INSTRUMENT_REPO/\$RUNNER_PATH#readonly RUNNER_SOURCE=/root/cubr-new24-full-binary-g6-run.sh#' \
        'runner missing literal: readonly RUNNER_SOURCE=$INSTRUMENT_REPO/$RUNNER_PATH'
    expect_runner_mutant_red runner_test_uses_standalone_root \
        's#readonly RUNNER_TEST_SOURCE=\$INSTRUMENT_REPO/\$RUNNER_TEST_PATH#readonly RUNNER_TEST_SOURCE=/root/cubr-new24-full-binary-g6-run-test.sh#' \
        'runner missing literal: readonly RUNNER_TEST_SOURCE=$INSTRUMENT_REPO/$RUNNER_TEST_PATH'
    expect_runner_mutant_red mapper_uses_standalone_root \
        's#readonly MAPPER_SOURCE=\$INSTRUMENT_REPO/\$MAPPER_PATH#readonly MAPPER_SOURCE=/root/cubr-new24-full-binary-g6-map.py#' \
        'runner missing literal: readonly MAPPER_SOURCE=$INSTRUMENT_REPO/$MAPPER_PATH'
    expect_runner_mutant_red mapper_test_uses_standalone_root \
        's#readonly MAPPER_TEST_SOURCE=\$INSTRUMENT_REPO/\$MAPPER_TEST_PATH#readonly MAPPER_TEST_SOURCE=/root/cubr-new24-full-binary-g6-map-test.py#' \
        'runner missing literal: readonly MAPPER_TEST_SOURCE=$INSTRUMENT_REPO/$MAPPER_TEST_PATH'
    expect_runner_mutant_red prereg_uses_standalone_root \
        's#readonly G6_PREREG_SOURCE=\$INSTRUMENT_REPO/\$G6_PREREG_PATH#readonly G6_PREREG_SOURCE=/root/CUBR-NEW24-FULL-BINARY-G6-20260811.md#' \
        'runner missing literal: readonly G6_PREREG_SOURCE=$INSTRUMENT_REPO/$G6_PREREG_PATH'
    expect_runner_mutant_red launch_identity_uses_standalone_root \
        's#readonly G6_LAUNCH_IDENTITIES_SOURCE=\$INSTRUMENT_REPO/\$LAUNCH_IDENTITIES_PATH#readonly G6_LAUNCH_IDENTITIES_SOURCE=/root/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env#' \
        'plan-shaped campaign interface failed:'
    expect_runner_mutant_red sanitized_contract_uses_legacy_unit \
        's/mode_authority=CUBR_G6_ADMISSION_INPUTS/mode_authority=CUBR_SYSTEMD_UNIT/' \
        'sanitized admission contract omitted exact service interface'
    expect_runner_mutant_red launch_auth_reopens_caller_identity \
        '0,/--verify-launch-identity-files "\$snapshot_identities"/s//--verify-launch-identity-files "$LAUNCH_IDENTITIES"/' \
        'campaign launch authentication reopened caller input after snapshot'
    expect_runner_mutant_red campaign_scientific_authentication_bypassed \
        '/^authenticate_campaign_launch_inputs()/,/^}/s#^    authenticate_campaign_scientific_identities "\$snapshot_identities" "\$ADMISSION_OUT" "\$CORPUS_MANIFEST"$#    :#' \
        'campaign launch scientific identity authentication missing'
    expect_runner_mutant_red protected_admission_manifest_authentication_bypassed \
        '/^reuse_admission_map()/,/^}/s#^    authenticate_protected_admission_manifest "\$ADMISSION_OUT" >/dev/null$#    :#' \
        'campaign map reuse bypasses protected admission manifest authentication'
    expect_runner_mutant_red stable_identity_self_comparison \
        's#^[[:space:]]*"\$PARTIAL/sealed-identity-set.env"$#        "$PREFLIGHT_DIR/admission-sealed-identity-set.env"#' \
        'campaign stable identity comparison is not bound to fresh sealed identity'
    expect_runner_mutant_red instrument_tree_uses_head \
        's/rev-parse "\$INSTRUMENT_COMMIT\^{tree}"/rev-parse '\''HEAD^{tree}'\''/' \
        'instrument tree is not commit-derived'
    expect_runner_mutant_red launch_runner_sha_field \
        's/launch-identity-value "\$snapshot_identities" runner_sha256/launch-identity-value "$snapshot_identities" wrong_runner_sha256/' \
        'campaign launch must compare runner SHA'
    expect_runner_mutant_red launch_runner_test_sha_field \
        's/launch-identity-value "\$snapshot_identities" runner_test_sha256/launch-identity-value "$snapshot_identities" wrong_runner_test_sha256/' \
        'campaign launch must compare runner test SHA'
    expect_runner_mutant_red launch_mapper_sha_field \
        's/launch-identity-value "\$snapshot_identities" mapper_sha256/launch-identity-value "$snapshot_identities" wrong_mapper_sha256/' \
        'campaign launch must compare mapper SHA'
    expect_runner_mutant_red launch_mapper_test_sha_field \
        's/launch-identity-value "\$snapshot_identities" mapper_test_sha256/launch-identity-value "$snapshot_identities" wrong_mapper_test_sha256/' \
        'campaign launch must compare mapper test SHA'
    expect_runner_mutant_red installed_runner_sha_field \
        's#sha256sum -- "\$RUNNER_SOURCE"#sha256sum -- "$snapshot_prereg"#' \
        'campaign launch must authenticate installed runner SHA'
    expect_runner_mutant_red installed_runner_test_sha_field \
        's/sha256sum -- "\$RUNNER_TEST_SOURCE"/sha256sum -- "$snapshot_prereg"/' \
        'campaign launch must authenticate installed runner test SHA'
    expect_runner_mutant_red installed_mapper_sha_field \
        's/sha256sum -- "\$MAPPER_SOURCE"/sha256sum -- "$snapshot_prereg"/' \
        'campaign launch must authenticate installed mapper SHA'
    expect_runner_mutant_red installed_mapper_test_sha_field \
        's/sha256sum -- "\$MAPPER_TEST_SOURCE"/sha256sum -- "$snapshot_prereg"/' \
        'campaign launch must authenticate installed mapper test SHA'
    expect_runner_mutant_red launch_admission_sha_field \
        's/launch_identity_value "\$snapshot_identities" admission_identity_set_sha256/launch_identity_value "$snapshot_identities" wrong_admission_identity_set_sha256/' \
        'campaign launch must compare admission identity SHA'
    expect_runner_mutant_red launch_admission_bytes_field \
        's/launch_identity_value "\$snapshot_identities" admission_identity_set_bytes/launch_identity_value "$snapshot_identities" wrong_admission_identity_set_bytes/' \
        'campaign launch must compare admission identity bytes'
    expect_runner_mutant_red launch_main_prereg_blob \
        's/\$actual_prereg_blob == "\$EXPECTED_G6_PREREG_BLOB"/\$actual_prereg_blob == "$LAUNCH_IDENTITIES_BLOB"/' \
        'campaign launch must compare expected preregistration blob'
    expect_runner_mutant_red launch_main_identity_blob \
        's/LAUNCH_IDENTITIES_BLOB=\$actual_identities_blob/LAUNCH_IDENTITIES_BLOB=$actual_prereg_blob/' \
        'campaign launch must compare expected identity blob'
    expect_runner_mutant_red launch_prereg_file_blob \
        's/hash-object --no-filters "\$snapshot_prereg"/hash-object --no-filters "$snapshot_identities"/' \
        'campaign launch must authenticate preregistration file blob'
    expect_runner_mutant_red launch_identity_file_blob \
        's/hash-object --no-filters "\$snapshot_identities"/hash-object --no-filters "$snapshot_prereg"/' \
        'campaign launch must authenticate identity file blob'
    expect_runner_mutant_red persisted_identity_sha_readback \
        's/sha256sum -- "\$target"/sha256sum -- "$source"/' \
        'campaign launch must read back persisted identity SHA'
    expect_runner_mutant_red persisted_identity_bytes_readback \
        's/stat -c %s -- "\$target"/stat -c %s -- "$source"/' \
        'campaign launch must read back persisted identity bytes'

    expect_runner_mutant_red receipt_authentication_bypassed \
        's/^    authenticate_g6_receipt$/    : # mutation bypassed receipt/' \
        'pre-service authentication must consume receipt, validation, and admission inputs'
    expect_runner_mutant_red source_a_writability_gate_removed \
        's/^    assert_immutable_tree "\$CODE_DIR"$/    : # mutation removed source A immutability/' \
        'runner missing literal: assert_immutable_tree "$CODE_DIR"'
    expect_runner_mutant_red target_b_writability_gate_removed \
        's/^    assert_immutable_tree "\$PROFILE_TARGET_B"$/    : # mutation removed target B immutability/' \
        'runner missing literal: assert_immutable_tree "$PROFILE_TARGET_B"'
    expect_runner_mutant_red campaign_regenerates_map \
        '/^main_run()/,/^}/s/reuse_admission_map/build_full_instruction_map/' \
        'campaign must authenticate and reuse the admission map without Cargo'
    expect_runner_mutant_red campaign_invokes_cargo \
        '/^main_run()/,/^}/s#reuse_admission_map#/root/.cargo/bin/cargo test --release\n    reuse_admission_map#' \
        'campaign production path invokes Cargo'
    expect_runner_mutant_red admission_creates_sample \
        '/^admission_feasibility_run()/,/^}/s/build_full_instruction_map/build_full_instruction_map\n    run_cell "$cell"/' \
        'admission must authenticate and build one map without campaign sampling'
    expect_runner_mutant_red receipt_schema_namespace \
        's/g6-prebuild-receipt-v1/g5-prebuild-receipt-v1/g' \
        'runner missing literal: readonly RECEIPT_SCHEMA=g6-prebuild-receipt-v1'
    expect_runner_mutant_red source_namespace_g5 \
        's#/root/cubr-new24-full-binary-g6-src-a#/root/cubr-new24-full-binary-g5-src-a#g' \
        'runner missing literal: /root/cubr-new24-full-binary-g6-src-a'
    expect_runner_mutant_red admission_unit_namespace_g5 \
        's/cubr-new24-full-binary-g6-admission-20260811.service/cubr-new24-full-binary-g5-admission-20260811.service/g' \
        'plan-shaped admission interface failed:'

    expect_runner_mutant_red source_base \
        's/830a9a31deb00926a97f3fa5bd74f58003573fc0/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef/' \
        'runner missing literal: 830a9a31deb00926a97f3fa5bd74f58003573fc0'
    expect_runner_mutant_red pin 's/taskset -c 0-15/taskset -c 16-19/g' \
        'runner missing literal: readonly -a PIN=(/usr/bin/taskset -c 0-15)'
    expect_runner_mutant_red budget 's/CAMPAIGN_BUDGET_SECONDS=14400/CAMPAIGN_BUDGET_SECONDS=14000/' \
        'runner missing literal: readonly CAMPAIGN_BUDGET_SECONDS=14400'
    expect_runner_mutant_red map_timeout 's/MAP_BUILD_TIMEOUT_SECONDS=1200/MAP_BUILD_TIMEOUT_SECONDS=1199/' \
        'runner missing literal: readonly MAP_BUILD_TIMEOUT_SECONDS=1200'
    expect_runner_mutant_red part_limit 's/EVIDENCE_PART_MAX_BYTES=90000000/EVIDENCE_PART_MAX_BYTES=100000000/' \
        'runner missing literal: readonly EVIDENCE_PART_MAX_BYTES=90000000'
    expect_runner_mutant_red instruction_count 's/EXPECTED_INSTRUCTION_COUNT=739548/EXPECTED_INSTRUCTION_COUNT=739549/' \
        'runner missing literal: readonly EXPECTED_INSTRUCTION_COUNT=739548'
    expect_runner_mutant_red page_size 's/EXPECTED_PAGE_SIZE=4096/EXPECTED_PAGE_SIZE=8192/' \
        'runner missing literal: readonly EXPECTED_PAGE_SIZE=4096'
    expect_runner_mutant_red rustc_full_commit \
        's/31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd/31fca3ad00000000000000000000000000000000/g' \
        'runner missing literal: readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd'
    expect_runner_mutant_red summary_compression \
        's/compress_map_artifact "\$map_dir\/map-summary.json" "\$map_dir\/raw-stream-evidence.tsv"/\/usr\/bin\/true/' \
        'runner missing literal: compress_map_artifact "$map_dir/map-summary.json" "$map_dir/raw-stream-evidence.tsv"'
    expect_runner_mutant_red g6_map_part_namespace \
        's/g6-full-instruction-map/g4-full-instruction-map/g' \
        'runner missing literal: --map-part-prefix g6-full-instruction-map'
    expect_runner_mutant_red seal_output_nested \
        's/--seal-out map-admission-seal.json/--seal-out map\/map-admission-seal.json/' \
        'runner missing literal: --seal-out map-admission-seal.json'
    expect_runner_mutant_red reuse_silently_accepted \
        's/--reuse-decision REJECTED_IDENTITY_MISMATCH/--reuse-decision REUSED_IDENTITY_MATCH/' \
        'runner missing literal: --reuse-decision REJECTED_IDENTITY_MISMATCH'
    expect_runner_mutant_red record_mode 's/--buildid-all --buildid-mmap/--buildid-all/' \
        'runner missing literal: --buildid-all --buildid-mmap'
    expect_runner_mutant_red source_sha \
        's/b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' \
        'runner missing literal: b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    expect_runner_mutant_red output_path \
        's/cubr-new24-full-binary-g6-20260811/cubr-new24-full-binary-g6-later/' \
        'plan-shaped campaign interface failed:'
    expect_runner_mutant_red systemd 's/Type=exec/Type=oneshot/g' \
        'runner missing literal: Type=exec Restart=no RuntimeMaxSec=4h KillMode=control-group KillSignal=SIGTERM FinalKillSignal=SIGKILL'
    expect_runner_mutant_red process_snapshot \
        's#/usr/bin/ps -eo pid=,ppid=,comm=,args= >"\$snapshot"#/usr/bin/ps -eo pid=,ppid=,comm=,args=#' \
        'runner missing literal: /usr/bin/ps -eo pid=,ppid=,comm=,args= >"$snapshot"'
    expect_runner_mutant_red addr2line_inline 's#/usr/bin/addr2line -a -f -C -i#/usr/bin/addr2line -a -f -C#g' \
        'runner missing literal: /usr/bin/addr2line -a -f -C -i'
    expect_runner_mutant_red verbose_time 's#/usr/bin/time -v -o#/usr/bin/time -o#g' \
        'runner missing literal: /usr/bin/time -v -o'
    expect_runner_mutant_red mapper_output_root 's/--output-root "\$map_dir"/--output-root "\$PARTIAL"/g' \
        'runner missing literal: --output-root "$map_dir"'
    expect_runner_mutant_red mapper_worker_identity \
        's/local worker_root=\$1 instrument_sha=\$2 expected_mapper_sha=\$3 expected_mapper_test_sha=\$4/local worker_root=$1 instrument_sha=$2 expected_mapper_sha=$4 expected_mapper_test_sha=$3/' \
        'map worker does not consume authenticated positional identities'
    expect_runner_mutant_red mapper_test_worker_identity \
        '/--map-worker "\$PARTIAL"/,+1 s/"\$EXPECTED_MAPPER_TEST_SHA"/"$EXPECTED_MAPPER_SHA"/' \
        'map worker invocation does not pass all authenticated positional identities'
    expect_runner_mutant_red final_deadline \
        's/PUBLICATION_COMMIT_MARGIN_SECONDS=5/PUBLICATION_COMMIT_MARGIN_SECONDS=0/' \
        'runner missing literal: readonly PUBLICATION_COMMIT_MARGIN_SECONDS=5'
    expect_runner_mutant_red terminal_finalization \
        's/^[[:space:]]*run_terminal_finalization$/    :/' \
        'missing ordered call: ^[[:space:]]*run_terminal_finalization$'
    expect_runner_mutant_red process_group_policy \
        's/KillMode=control-group/KillMode=process/' \
        'runner missing literal: Type=exec Restart=no RuntimeMaxSec=4h KillMode=control-group KillSignal=SIGTERM FinalKillSignal=SIGKILL'
    expect_runner_mutant_red cgroup_post_call_guard \
        's/assert_cgroup_no_new_pids || return 125/:/' \
        'runner missing literal: assert_cgroup_no_new_pids || return 125'
    expect_runner_mutant_red cgroup_precommit_guard \
        's/new cgroup PID exists immediately before final commit/new cgroup PID ignored before final commit/' \
        'runner missing literal: new cgroup PID exists immediately before final commit'
    expect_runtime_mutant_red disconnected_publisher_ancestry \
        's/if current not in current_pids:/if False and current not in current_pids:/; s/reject_cgroup("publisher ancestry reached PID1 before frozen cgroup baseline")/reached_baseline.append(next(iter(baseline_pids))); ancestry.add(next(iter(baseline_pids))); break/g' \
        'runner cgroup precommit counterexample failed: current_profile_g6_cgroup_precommit_test=FAIL disconnected-publisher-accepted'
    expect_runner_mutant_red checked_marker_zero_write \
        's/if written <= 0:/if written < 0:/g' \
        'runner missing literal: if written <= 0:'
    expect_runner_mutant_red publishing_manifest_auth \
        's/authenticate_manifest(publishing_path)/authenticate_manifest_removed(publishing_path)/g' \
        'runner missing literal: authenticate_manifest(publishing_path)'
    expect_runner_mutant_red late_marker_noreplace \
        's/rename_noreplace(authoritative, rejected)/os.rename(authoritative, rejected)/' \
        'runner missing literal: rename_noreplace(authoritative, rejected)'
    expect_runner_mutant_red attribution_evidence_void \
        's/attribution record evidence failure/attribution record descriptive failure/' \
        'runner missing literal: attribution record evidence failure'
    expect_runner_mutant_red frozen_binary \
        's/2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/' \
        'runner missing literal: 2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78'
    expect_runner_mutant_red profiled_archive 's/"\$archive2"/"\$archive1"/g' \
        'all five profiled decodes must use the independently reproduced second archive'
    expect_runner_mutant_red perf_population \
        's/task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults/cycles instructions/' \
        'runner missing literal: task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults'
    expect_runner_mutant_red rust_dep_root \
        's#/rust/deps/gimli-0.32.3#/rust/deps#g' \
        'runner missing literal: /rust/deps/gimli-0.32.3'
    expect_runner_mutant_red system_header_root \
        's#/usr/include/x86_64-linux-gnu/bits/string_fortified.h#/usr/include#g' \
        'runner missing literal: /usr/include/x86_64-linux-gnu/bits/string_fortified.h'
    expect_runner_mutant_red system_header_sha \
        's/0cfa3c530938891615ab64ab5dfb72ebd8d02077d29d4410774b8a8ceff628fb/cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/' \
        'runner missing literal: 0cfa3c530938891615ab64ab5dfb72ebd8d02077d29d4410774b8a8ceff628fb'
    expect_self_test_mutant_red cycles_runtime \
        's/CYCLE_DISAGREEMENT_MAX=0.10/CYCLE_DISAGREEMENT_MAX=0.11/' cycle_threshold_boundary
    expect_self_test_mutant_red record_runtime \
        's/RECORD_RATIO_MAX=1.10/RECORD_RATIO_MAX=1.11/' record_threshold_boundary
    expect_self_test_mutant_red share_runtime \
        's/SHARE_DELTA_MAX=1.00/SHARE_DELTA_MAX=1.01/' share_threshold_boundary
    expect_self_test_mutant_red sample_runtime \
        's/SAMPLE_COUNT_MIN=4787/SAMPLE_COUNT_MIN=4786/' sample_count_boundary
fi

printf 'current_profile_g6_contract=PASS\n'
