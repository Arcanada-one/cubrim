#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly HERE
readonly HELPER=$HERE/current-profile-g6-validate.sh
readonly SOURCE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly LOCK_SHA=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
readonly BINARY_SHA=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78
readonly BUILD_ID=789119db24ae1a28a24bcc0ecbec136c7e937d9a
readonly VALIDATION_KEYS='binary_build_id binary_sha256 build_cpuset campaign_artifact_count cargo_lock_bytes cargo_lock_sha256 cargo_test_release_log_bytes cargo_test_release_log_sha256 cargo_version cubr_threads instrument_main map_artifact_count mkl_num_threads omp_num_threads output_tree_manifest_bytes output_tree_manifest_sha256 perf_data_count rayon_num_threads rustc_commit rustc_version schema scheme_roundtrip_log_bytes scheme_roundtrip_log_sha256 service_count source_commit source_tree_manifest_bytes source_tree_manifest_sha256 suite_commands_sha256 target_tree_manifest_bytes target_tree_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_test_blob validation_test_sha256'

TESTS=0
MUTANTS=0
LAST_RC=0
LAST_OUTPUT=
FIXTURE=
ROOT=
COMMANDS=
STATE=

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

pass() {
    TESTS=$((TESTS + 1))
    printf 'PASS: %s\n' "$*"
}

mutant_killed() {
    local name=$1 assertion=$2
    MUTANTS=$((MUTANTS + 1))
    printf 'MUTANT-KILLED: %s assertion=%s\n' "$name" "$assertion"
}

cleanup_fixture() {
    if [[ -n ${FIXTURE:-} && -d $FIXTURE ]]; then
        /usr/bin/chmod -R u+rwX -- "$FIXTURE"
        /usr/bin/rm -rf -- "$FIXTURE"
    fi
    FIXTURE=
}
trap cleanup_fixture EXIT

capture() {
    set +e
    LAST_OUTPUT=$("$@" 2>&1)
    LAST_RC=$?
    set -e
}

require_success() {
    local label=$1
    (( LAST_RC == 0 )) || fail "$label: rc=$LAST_RC output=$LAST_OUTPUT"
}

require_failure() {
    local label=$1 expected=$2
    (( LAST_RC != 0 )) || fail "$label: unexpectedly exited zero: $LAST_OUTPUT"
    [[ $LAST_OUTPUT == *"$expected"* ]] ||
        fail "$label: expected named failure '$expected', got: $LAST_OUTPUT"
}

write_mocks() {
    /usr/bin/mkdir -p -- "$COMMANDS"
    /usr/bin/cat >"$COMMANDS/git" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == clone ]]; then
    [[ $* == "clone --no-local --no-checkout $MOCK_INSTRUMENT $MOCK_SOURCE" ]] || {
        printf 'mock git: wrong clone: %s\n' "$*" >&2; exit 91; }
    printf '%s\n' "$*" >>"$MOCK_STATE/git-clone.calls"
    /usr/bin/mkdir -p "$MOCK_SOURCE/.git" "$MOCK_SOURCE/code/cubrim-rs" \
        "$MOCK_SOURCE/documentation/ephemeral/research"
    printf 'manifest\n' >"$MOCK_SOURCE/code/cubrim-rs/Cargo.toml"
    printf 'baseline-28\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0028-bench.json"
    printf 'baseline-31\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0031-bench.json"
    exit 0
fi
[[ ${1:-} == -C && $# -ge 3 ]] || { printf 'mock git: unsupported: %s\n' "$*" >&2; exit 92; }
repo=$2
shift 2
if [[ $repo == "$MOCK_INSTRUMENT" ]]; then
    case ${1:-} in
        rev-parse)
            case ${2:-} in
                HEAD) printf '%040d\n' 6 ;;
                *current-profile-g6-validate.sh) printf '%040d\n' 7 ;;
                *current-profile-g6-validate-test.sh) printf '%040d\n' 8 ;;
                *) printf 'mock git: unknown instrument rev-parse: %s\n' "$*" >&2; exit 93 ;;
            esac ;;
        show)
            case ${2:-} in
                *current-profile-g6-validate.sh) /usr/bin/cat "$MOCK_INSTRUMENT/documentation/ephemeral/research/current-profile-g6-validate.sh" ;;
                *current-profile-g6-validate-test.sh) /usr/bin/cat "$MOCK_INSTRUMENT/documentation/ephemeral/research/current-profile-g6-validate-test.sh" ;;
                *) exit 94 ;;
            esac ;;
        cat-file) exit 0 ;;
        *) printf 'mock git: unsupported instrument command: %s\n' "$*" >&2; exit 95 ;;
    esac
    exit 0
fi
[[ $repo == "$MOCK_SOURCE" ]] || { printf 'mock git: wrong repo: %s\n' "$repo" >&2; exit 96; }
case ${1:-} in
    checkout)
        [[ $* == "checkout --detach $MOCK_SOURCE_COMMIT" ]] || {
            printf 'mock git: wrong checkout: %s\n' "$*" >&2; exit 97; }
        : >"$MOCK_STATE/checked-out" ;;
    rev-parse)
        if [[ ${MOCK_SOURCE_DRIFT:-0} == 1 ]]; then printf '%040d\n' 9; else printf '%s\n' "$MOCK_SOURCE_COMMIT"; fi ;;
    symbolic-ref) exit 1 ;;
    cat-file) exit 0 ;;
    status)
        [[ " $* " == *' --ignored=matching '* ]] || { printf 'mock git: ignored status not requested\n' >&2; exit 99; }
        [[ ! -e $MOCK_SOURCE/code/cubrim-rs/Cargo.lock ]] || printf '!! code/cubrim-rs/Cargo.lock\n'
        [[ $(/usr/bin/cat "$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0028-bench.json") == baseline-28 ]] ||
            printf ' M documentation/ephemeral/research/CUBR-0028-bench.json\n'
        [[ $(/usr/bin/cat "$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0031-bench.json") == baseline-31 ]] ||
            printf ' M documentation/ephemeral/research/CUBR-0031-bench.json\n'
        [[ ! -e $MOCK_SOURCE/unexpected-suite-side-effect ]] || printf '?? unexpected-suite-side-effect\n'
        [[ ! -e $MOCK_SOURCE/perf.data ]] || printf '?? perf.data\n' ;;
    restore)
        printf 'baseline-28\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0028-bench.json"
        printf 'baseline-31\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0031-bench.json" ;;
    clean)
        /usr/bin/rm -f -- "$MOCK_SOURCE/unexpected-suite-side-effect" "$MOCK_SOURCE/perf.data" ;;
    *) printf 'mock git: unsupported source command: %s\n' "$*" >&2; exit 98 ;;
esac
MOCK

    /usr/bin/cat >"$COMMANDS/cargo" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == -V || ${1:-} == --version ]]; then
    [[ ${MOCK_TOOLCHAIN_DRIFT:-0} != 1 ]] && printf 'cargo 1.96.1 (mock 2026-01-01)\n' || printf 'cargo 1.95.0 (mock)\n'
    exit 0
fi
[[ ${1:-} == test ]] || { printf 'mock cargo: non-test invocation\n' >&2; exit 81; }
args=" $* "
[[ $args == *' --release '* ]] || { printf 'mock cargo: missing --release\n' >&2; exit 82; }
[[ $args == *' --locked '* ]] || { printf 'mock cargo: missing --locked\n' >&2; exit 83; }
[[ $args == *" --manifest-path $MOCK_SOURCE/code/cubrim-rs/Cargo.toml "* ]] || {
    printf 'mock cargo: wrong manifest path\n' >&2; exit 84; }
[[ $args == *" --target-dir $MOCK_TARGET "* ]] || { printf 'mock cargo: wrong target\n' >&2; exit 85; }
[[ ${CARGO_PROFILE_RELEASE_DEBUG:-} == 1 && ${CUBR_THREADS:-} == 4 &&
   ${RAYON_NUM_THREADS:-} == 4 && ${OMP_NUM_THREADS:-} == 4 && ${MKL_NUM_THREADS:-} == 4 ]] || {
    printf 'mock cargo: wrong environment\n' >&2; exit 86; }
printf '%s\n' "$*" >>"$MOCK_STATE/cargo.calls"
/usr/bin/mkdir -p "$MOCK_TARGET/release/deps"
printf 'compiled\n' >"$MOCK_TARGET/release/deps/mock-artifact"
if [[ $args == *' --test scheme_roundtrip -- --nocapture '* ]]; then
    printf 'suite=scheme_roundtrip\n'
elif [[ $args == *' --test '* ]]; then
    printf 'mock cargo: wrong suite\n' >&2
    exit 87
else
    printf 'changed-28\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0028-bench.json"
    printf 'changed-31\n' >"$MOCK_SOURCE/documentation/ephemeral/research/CUBR-0031-bench.json"
    [[ ${MOCK_SIDE_EFFECT_LEAK:-0} != 1 ]] || : >"$MOCK_SOURCE/unexpected-suite-side-effect"
    [[ ${MOCK_PERF_CREATE:-0} != 1 ]] || : >"$MOCK_SOURCE/perf.data"
    printf 'suite=release\n'
fi
MOCK

    /usr/bin/cat >"$COMMANDS/taskset" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} == -c && ${2:-} == 0-15 ]] || { printf 'mock taskset: wrong pin\n' >&2; exit 71; }
printf 'pin=%s release_debug=%s cubr=%s rayon=%s omp=%s mkl=%s command=%s\n' \
    "$2" "${CARGO_PROFILE_RELEASE_DEBUG:-}" "${CUBR_THREADS:-}" "${RAYON_NUM_THREADS:-}" \
    "${OMP_NUM_THREADS:-}" "${MKL_NUM_THREADS:-}" "${*:3}" >>"$MOCK_STATE/taskset.calls"
shift 2
exec "$@"
MOCK

    /usr/bin/cat >"$COMMANDS/systemctl" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
unit=${2:-}
printf '%s\n' "$*" >>"$MOCK_STATE/systemctl.calls"
if [[ ${MOCK_UNIT_PRESENT:-} == "$unit" ]]; then printf 'loaded\n'; else printf 'not-found\n'; fi
MOCK

    /usr/bin/cat >"$COMMANDS/rustc" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} == -vV ]] || exit 61
if [[ ${MOCK_TOOLCHAIN_DRIFT:-0} == 1 ]]; then
    printf 'rustc 1.95.0\nrelease: 1.95.0\ncommit-hash: badbadbadbadbadbadbadbadbadbadbadbadbadb\n'
else
    printf 'rustc 1.96.1\nrelease: 1.96.1\ncommit-hash: 31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd\n'
fi
MOCK

    /usr/bin/cat >"$COMMANDS/readelf" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${MOCK_BINARY_SUBSTITUTION:-0} == 1 ]]; then
    printf '    Build ID: 0000000000000000000000000000000000000000\n'
else
    printf '    Build ID: 789119db24ae1a28a24bcc0ecbec136c7e937d9a\n'
fi
MOCK

    /usr/bin/cat >"$COMMANDS/sha256sum" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} != -- ]] || shift
if (( $# == 1 )); then
    case $1 in
        */code/cubrim-rs/Cargo.lock|*/cubr-new24-full-binary-g6-validation-20260811/generated-Cargo.lock)
            [[ ${MOCK_LOCK_DRIFT:-0} != 1 ]] && printf '0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9  %s\n' "$1" ||
                printf '0000000000000000000000000000000000000000000000000000000000000000  %s\n' "$1"
            exit 0 ;;
        */cubr-new24-full-binary-g6-target-a/release/cubrim)
            [[ ${MOCK_BINARY_SUBSTITUTION:-0} != 1 ]] && printf '2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78  %s\n' "$1" ||
                printf '0000000000000000000000000000000000000000000000000000000000000000  %s\n' "$1"
            exit 0 ;;
    esac
fi
exec /usr/bin/sha256sum "$@"
MOCK
    /usr/bin/chmod 0755 "$COMMANDS"/*
}

new_fixture() {
    cleanup_fixture
    FIXTURE=$(/usr/bin/mktemp -d)
    ROOT=$FIXTURE/rootfs
    COMMANDS=$FIXTURE/commands
    STATE=$FIXTURE/state
    local instrument=$ROOT/root/cubr-new24-full-binary-g6-instrument
    local prebuild_source=$ROOT/root/cubr-new24-full-binary-g6-src-a
    local prebuild_target=$ROOT/root/cubr-new24-full-binary-g6-target-a
    /usr/bin/mkdir -p "$STATE" "$instrument/documentation/ephemeral/research" \
        "$prebuild_source/code/cubrim-rs" "$prebuild_target/release"
    /usr/bin/cp -- "$HELPER" "$instrument/documentation/ephemeral/research/current-profile-g6-validate.sh"
    /usr/bin/cp -- "${BASH_SOURCE[0]}" "$instrument/documentation/ephemeral/research/current-profile-g6-validate-test.sh"
    printf 'sealed-lock\n' >"$prebuild_source/code/cubrim-rs/Cargo.lock"
    printf 'sealed-binary\n' >"$prebuild_target/release/cubrim"
    /usr/bin/chmod -R a-w "$prebuild_source" "$prebuild_target"
    write_mocks
}

run_helper() {
    local script=${1:-$HELPER}
    shift || true
    capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin \
        CUBR_G6_TEST_MODE=1 CUBR_G6_TEST_ROOT="$ROOT" CUBR_G6_COMMAND_DIR="$COMMANDS" \
        MOCK_STATE="$STATE" MOCK_ROOT="$ROOT" \
        MOCK_INSTRUMENT="$ROOT/root/cubr-new24-full-binary-g6-instrument" \
        MOCK_SOURCE="$ROOT/root/cubr-new24-full-binary-g6-validation-src" \
        MOCK_TARGET="$ROOT/root/cubr-new24-full-binary-g6-validation-target" \
        MOCK_SOURCE_COMMIT="$SOURCE_COMMIT" "$@" /usr/bin/bash "$script"
}

manifest_value() {
    /usr/bin/awk -F= -v key="$2" '$1==key {print substr($0, index($0, "=")+1)}' "$1"
}

assert_manifest_closed() {
    local manifest=$1 actual
    actual=$(/usr/bin/cut -d= -f1 "$manifest" | /usr/bin/paste -sd' ' -)
    [[ $actual == "$VALIDATION_KEYS" ]] || fail "manifest keys are not exact/sorted: $actual"
    [[ $(/usr/bin/wc -l <"$manifest") == 34 ]] || fail 'manifest does not have exactly 34 keys'
    [[ $(manifest_value "$manifest" schema) == g6-validation-manifest-v1 ]] || fail 'manifest schema mismatch'
    [[ $(manifest_value "$manifest" source_commit) == "$SOURCE_COMMIT" ]] || fail 'manifest source commit mismatch'
    [[ $(manifest_value "$manifest" cargo_lock_sha256) == "$LOCK_SHA" ]] || fail 'manifest lock hash mismatch'
    [[ $(manifest_value "$manifest" binary_sha256) == "$BINARY_SHA" ]] || fail 'manifest binary hash mismatch'
    [[ $(manifest_value "$manifest" binary_build_id) == "$BUILD_ID" ]] || fail 'manifest build ID mismatch'
    [[ $(manifest_value "$manifest" build_cpuset) == 0-15 ]] || fail 'manifest cpuset mismatch'
    [[ $(manifest_value "$manifest" service_count) == 0 &&
       $(manifest_value "$manifest" perf_data_count) == 0 &&
       $(manifest_value "$manifest" map_artifact_count) == 0 &&
       $(manifest_value "$manifest" campaign_artifact_count) == 0 ]] || fail 'manifest no-effect counts mismatch'
}

[[ -x $HELPER ]] || fail "validation helper missing or non-executable: $HELPER"
pass 'helper exists and is executable'

for literal in \
    /root/cubr-new24-full-binary-g6-validation-src \
    /root/cubr-new24-full-binary-g6-validation-target \
    /root/cubr-new24-full-binary-g6-validation-20260811 \
    /root/cubr-new24-full-binary-g6-validation-manifest-20260811.partial \
    /root/cubr-new24-full-binary-g6-validation-manifest-20260811 \
    cubr-new24-full-binary-g6-admission-20260811.service \
    cubr-new24-full-binary-g6-20260811.service; do
    /usr/bin/grep -qF -- "$literal" "$HELPER" || fail "helper missing literal: $literal"
done
! /usr/bin/grep -Eq 'current-profile-g5|full-binary-g5-(src|target|validation|2026)|config/credentials/' "$HELPER" ||
    fail 'helper contains forbidden G5 runtime or credential namespace'
pass 'literal G6 namespace is closed'

capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin CUBR_G6_TEST_ROOT=/tmp/forbidden /usr/bin/bash "$HELPER"
require_failure 'production override rejection' 'production mode rejects test/identity/path overrides'
pass 'production override rejected before I/O'

new_fixture
run_helper
require_success 'happy-path validation'
[[ $LAST_OUTPUT == *'current_profile_g6_validation=PASS schema=g6-validation-manifest-v1 keys=34'* ]] ||
    fail "happy path lacks exact PASS marker: $LAST_OUTPUT"
readonly final_manifest=$ROOT/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env
[[ -f $final_manifest && ! -L $final_manifest ]] || fail 'final manifest missing or unsafe'
[[ ! -e $ROOT/root/cubr-new24-full-binary-g6-validation-manifest-20260811.partial ]] || fail 'partial manifest survived success'
[[ $(/usr/bin/stat -c %a "$final_manifest") == 444 ]] || fail 'final manifest mode is not 0444'
[[ $(/usr/bin/stat -c %a "${final_manifest%/*}") == 500 ]] || fail 'manifest root mode is not 0500'
assert_manifest_closed "$final_manifest"
[[ $(/usr/bin/wc -l <"$STATE/cargo.calls") == 2 ]] || fail 'did not execute exactly two cargo suites'
/usr/bin/grep -qxF "test --release --locked --manifest-path $ROOT/root/cubr-new24-full-binary-g6-validation-src/code/cubrim-rs/Cargo.toml --target-dir $ROOT/root/cubr-new24-full-binary-g6-validation-target" "$STATE/cargo.calls" || fail 'release suite command mismatch'
/usr/bin/grep -qxF "test --release --locked --manifest-path $ROOT/root/cubr-new24-full-binary-g6-validation-src/code/cubrim-rs/Cargo.toml --target-dir $ROOT/root/cubr-new24-full-binary-g6-validation-target --test scheme_roundtrip -- --nocapture" "$STATE/cargo.calls" || fail 'roundtrip suite command mismatch'
[[ $(/usr/bin/wc -l <"$STATE/taskset.calls") == 2 ]] || fail 'taskset did not wrap exactly two suites'
! /usr/bin/find "$ROOT/root/cubr-new24-full-binary-g6-validation-src" \
    "$ROOT/root/cubr-new24-full-binary-g6-validation-target" \
    "$ROOT/root/cubr-new24-full-binary-g6-validation-20260811" -perm /222 -print -quit | /usr/bin/grep -q . ||
    fail 'a covered validation tree remains writable'
[[ ! -e $ROOT/root/cubr-new24-full-binary-g6-validation-src/code/cubrim-rs/Cargo.lock ]] || fail 'generated lock survived in validation source'
[[ -f $ROOT/root/cubr-new24-full-binary-g6-validation-20260811/generated-Cargo.lock ]] || fail 'runner-facing generated-Cargo.lock was not copied to validation output'
[[ ! -e $ROOT/root/cubr-new24-full-binary-g6-validation-20260811/Cargo.lock &&
   ! -L $ROOT/root/cubr-new24-full-binary-g6-validation-20260811/Cargo.lock ]] || fail 'legacy validation-output Cargo.lock variant was published'
pass 'runner-facing generated-Cargo.lock filename is exact and legacy Cargo.lock is absent'
[[ $(/usr/bin/cat "$ROOT/root/cubr-new24-full-binary-g6-validation-src/documentation/ephemeral/research/CUBR-0028-bench.json") == baseline-28 &&
   $(/usr/bin/cat "$ROOT/root/cubr-new24-full-binary-g6-validation-src/documentation/ephemeral/research/CUBR-0031-bench.json") == baseline-31 ]] || fail 'suite side effects were not restored'
for forbidden in \
    "$ROOT/root/cubr-new24-full-binary-g6-map-dryrun-20260811" \
    "$ROOT/root/cubr-new24-full-binary-g6-20260811" \
    "$ROOT/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env"; do
    [[ ! -e $forbidden && ! -L $forbidden ]] || fail "forbidden service/performance/map/campaign artifact exists: $forbidden"
done
pass 'happy path validates, restores, seals, and publishes exact closed evidence'

capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin CUBR_G6_TEST_MODE=1 \
    CUBR_G6_TEST_ROOT="$ROOT" CUBR_G6_COMMAND_DIR="$COMMANDS" \
    CUBR_G6_TEST_ACTION=verify-manifest CUBR_G6_TEST_MANIFEST="$final_manifest" \
    MOCK_STATE="$STATE" MOCK_ROOT="$ROOT" \
    MOCK_INSTRUMENT="$ROOT/root/cubr-new24-full-binary-g6-instrument" \
    MOCK_SOURCE="$ROOT/root/cubr-new24-full-binary-g6-validation-src" \
    MOCK_TARGET="$ROOT/root/cubr-new24-full-binary-g6-validation-target" \
    MOCK_SOURCE_COMMIT="$SOURCE_COMMIT" /usr/bin/bash "$HELPER"
require_success 'published manifest self-check'
pass 'published manifest reauthentication succeeds without a self-hash key'

before_second=$(/usr/bin/wc -l <"$STATE/git-clone.calls")
run_helper
require_failure 'second invocation' 'owned path collision'
[[ $(/usr/bin/wc -l <"$STATE/git-clone.calls") == "$before_second" ]] || fail 'second invocation reached clone'
mutant_killed second_invocation 'owned path collision'
pass 'second invocation fails before clone'

for collision in validation-src validation-target validation-20260811 validation-manifest-20260811.partial validation-manifest-20260811; do
    for shape in file symlink; do
        new_fixture
        path=$ROOT/root/cubr-new24-full-binary-g6-$collision
        /usr/bin/mkdir -p -- "$(/usr/bin/dirname "$path")"
        if [[ $shape == symlink ]]; then
            /usr/bin/ln -s /nonexistent "$path"
        else
            : >"$path"
        fi
        run_helper
        require_failure "collision $collision $shape" 'owned path collision'
        [[ ! -e $STATE/git-clone.calls ]] || fail "collision $collision $shape reached clone"
        mutant_killed "collision_${collision}_$shape" 'owned path collision before clone'
    done
done
pass 'all fixed validation collisions, including broken symlink at each path, fail before clone'

for unit in cubr-new24-full-binary-g6-admission-20260811.service cubr-new24-full-binary-g6-20260811.service; do
    new_fixture
    run_helper "$HELPER" MOCK_UNIT_PRESENT="$unit"
    require_failure "unit collision $unit" 'G6 unit already exists'
    [[ ! -e $STATE/git-clone.calls ]] || fail "unit collision $unit reached clone"
    mutant_killed "unit_$unit" 'G6 unit already exists before clone'
done
pass 'both exact G6 units fail before clone'

for drift in MOCK_SOURCE_DRIFT MOCK_LOCK_DRIFT MOCK_TOOLCHAIN_DRIFT; do
    new_fixture
    run_helper "$HELPER" "$drift=1"
    case $drift in
        MOCK_SOURCE_DRIFT) require_failure "$drift" 'validation source commit mismatch' ;;
        MOCK_LOCK_DRIFT) require_failure "$drift" 'sealed Cargo.lock sha256 mismatch' ;;
        MOCK_TOOLCHAIN_DRIFT) require_failure "$drift" 'toolchain mismatch' ;;
    esac
    mutant_killed "${drift#MOCK_}" 'frozen identity drift rejected'
done
pass 'source, sealed-lock, and toolchain drift fail closed'

new_fixture
run_helper "$HELPER" MOCK_SIDE_EFFECT_LEAK=1
require_failure 'side-effect leak' 'unexpected suite side effect'
mutant_killed side_effect_leak 'unexpected suite side effect'
pass 'unexpected suite side effect is terminal'

new_fixture
run_helper "$HELPER" MOCK_BINARY_SUBSTITUTION=1
require_failure 'binary substitution' 'prebuild binary sha256 mismatch'
mutant_killed binary_substitution 'prebuild binary sha256 mismatch'
pass 'prebuild binary substitution is rejected'

new_fixture
run_helper "$HELPER" MOCK_PERF_CREATE=1
require_failure 'performance creation' 'performance/map/campaign artifact created'
mutant_killed performance_creation 'performance/map/campaign artifact created'
pass 'performance creation is rejected before cleanup can hide it'

new_fixture
tree=$FIXTURE/manifest-tree
/usr/bin/mkdir -p "$tree/nested"
printf 'payload\n' >"$tree/nested/file.txt"
/usr/bin/chmod -R a-w "$tree"
capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin CUBR_G6_TEST_MODE=1 \
    CUBR_G6_TEST_ROOT="$ROOT" CUBR_G6_COMMAND_DIR="$COMMANDS" \
    CUBR_G6_TEST_ACTION=emit-manifest CUBR_G6_TEST_TREE="$tree" /usr/bin/bash "$HELPER"
require_success 'canonical manifest emission'
[[ $(printf '%s\n' "$LAST_OUTPUT" | /usr/bin/awk -F '\t' '$1=="" {n++} END {print n+0}') == 1 ]] || fail 'canonical manifest lacks exactly one empty root row'
root_mode=$(printf '%04d' "$(/usr/bin/stat -c %a "$tree")")
[[ $(printf '%s\n' "$LAST_OUTPUT" | /usr/bin/head -1) == $'\tdirectory\t'"$root_mode"$'\t'* ]] || fail 'canonical manifest root row is not first, empty, and mode-exact'
pass 'canonical manifest has exactly one empty root row'

for unsafe in symlink fifo unsafe-path; do
    /usr/bin/chmod u+w "$tree" "$tree/nested"
    case $unsafe in
        symlink) /usr/bin/ln -s file.txt "$tree/nested/link" ;;
        fifo) /usr/bin/mkfifo "$tree/nested/pipe" ;;
        unsafe-path) printf x >"$tree/nested/not safe" ;;
    esac
    /usr/bin/chmod -R a-w "$tree"
    capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin CUBR_G6_TEST_MODE=1 \
        CUBR_G6_TEST_ROOT="$ROOT" CUBR_G6_COMMAND_DIR="$COMMANDS" \
        CUBR_G6_TEST_ACTION=emit-manifest CUBR_G6_TEST_TREE="$tree" /usr/bin/bash "$HELPER"
    require_failure "canonical manifest $unsafe" 'unsafe canonical tree'
    /usr/bin/chmod -R u+w "$tree"
    /usr/bin/rm -f "$tree/nested/link" "$tree/nested/pipe" "$tree/nested/not safe"
done
pass 'canonical manifest rejects unsafe nested types and paths'

new_fixture
run_helper
require_success 'manifest tamper fixture'
tampered=$ROOT/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env
/usr/bin/chmod u+w "${tampered%/*}" "$tampered"
/usr/bin/sed -i 's/^binary_sha256=.*/binary_sha256=0000000000000000000000000000000000000000000000000000000000000000/' "$tampered"
/usr/bin/chmod 0444 "$tampered"
/usr/bin/chmod 0500 "${tampered%/*}"
capture /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin CUBR_G6_TEST_MODE=1 \
    CUBR_G6_TEST_ROOT="$ROOT" CUBR_G6_COMMAND_DIR="$COMMANDS" \
    CUBR_G6_TEST_ACTION=verify-manifest CUBR_G6_TEST_MANIFEST="$tampered" \
    MOCK_STATE="$STATE" MOCK_ROOT="$ROOT" \
    MOCK_INSTRUMENT="$ROOT/root/cubr-new24-full-binary-g6-instrument" \
    MOCK_SOURCE="$ROOT/root/cubr-new24-full-binary-g6-validation-src" \
    MOCK_TARGET="$ROOT/root/cubr-new24-full-binary-g6-validation-target" \
    MOCK_SOURCE_COMMIT="$SOURCE_COMMIT" /usr/bin/bash "$HELPER"
require_failure 'final manifest tamper' 'validation manifest authentication failed'
mutant_killed final_manifest_tamper 'validation manifest authentication failed'
pass 'final manifest tampering is detected'

expect_mutant_red() {
    local name=$1 expression=$2 expected=$3 mutant
    new_fixture
    mutant=$FIXTURE/validate-mutant.sh
    /usr/bin/sed "$expression" "$HELPER" >"$mutant"
    /usr/bin/chmod 0755 "$mutant"
    /usr/bin/cp "$mutant" "$ROOT/root/cubr-new24-full-binary-g6-instrument/documentation/ephemeral/research/current-profile-g6-validate.sh"
    run_helper "$mutant"
    require_failure "mutant $name" "$expected"
    mutant_killed "$name" "$expected"
}

expect_mutant_red missing_locked '/TASKSET.*test --release --locked/ s/--locked//' 'cargo test --release --locked failed'
expect_mutant_red wrong_suite 's/scheme_roundtrip/wrong_roundtrip/g' 'cargo wrong_roundtrip suite failed'
expect_mutant_red source_commit 's/830a9a31deb00926a97f3fa5bd74f58003573fc0/930a9a31deb00926a97f3fa5bd74f58003573fc0/g' 'mock git: wrong checkout'
# shellcheck disable=SC2016 # The sed mutant must preserve literal $OUTPUT in the helper source.
expect_mutant_red output_lock_filename 's#readonly OUTPUT_LOCK=$OUTPUT/generated-Cargo.lock#readonly OUTPUT_LOCK=$OUTPUT/Cargo.lock#' 'validation output lock path is not runner-compatible'
pass 'behavior-driven command/source mutants are killed by named assertions'

printf 'current_profile_g6_validate_contract=PASS tests=%d mutants=%d\n' "$TESTS" "$MUTANTS"
