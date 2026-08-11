#!/usr/bin/env bash
# Frozen NEW-24 G5 full-binary attribution runner. No selection or DB mutation.
set -Eeuo pipefail
IFS=$'\n\t'
export LC_ALL=C
export CUBR_THREADS=4
export RAYON_NUM_THREADS=4
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

readonly ROOT=/root/phaseC
readonly CODE_DIR=/root/cubr-new24-full-binary-g5-src
readonly PROFILE_TARGET=/root/cubr-new24-full-binary-g5-target
readonly CUBRIM=$PROFILE_TARGET/release/cubrim
readonly CODE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly CORPUS_MANIFEST=/root/phaseC/corpus_manifest.tsv
readonly CORPUS_ROOT=/root/corpus-full/silesia

case ${1:-} in
    --admission-feasibility|--self-test-mode-roots) RUN_MODE=admission ;;
    *) RUN_MODE=campaign ;;
esac
readonly RUN_MODE

ROOT_PREFIX=${CUBR_G5_TEST_ROOT_PREFIX:-}
if [[ -n $ROOT_PREFIX && ${1:-} != --self-test-mode-roots ]]; then
    printf 'current_profile_g5_contract=HARNESS_INVALID reason=test root outside root self-test\n' >&2
    exit 2
fi
if [[ -n $ROOT_PREFIX ]]; then
    CAMPAIGN_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g5-20260810
    ADMISSION_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g5-map-dryrun-20260810
else
    CAMPAIGN_OUT=/root/cubr-new24-full-binary-g5-20260810
    ADMISSION_OUT=/root/cubr-new24-full-binary-g5-map-dryrun-20260810
fi
readonly ROOT_PREFIX CAMPAIGN_OUT ADMISSION_OUT
if [[ $RUN_MODE == admission ]]; then
    OUT=$ADMISSION_OUT
else
    OUT=$CAMPAIGN_OUT
fi
readonly OUT
readonly PARTIAL=$OUT.partial
readonly PUBLISHING=$OUT.publishing
readonly LATE=$OUT.late
readonly MEASURED_BINARY=$PARTIAL/binary/cubrim
readonly MAPPER_SOURCE=/root/cubr-new24-full-binary-g5-map.py
readonly MAPPER_TEST_SOURCE=/root/cubr-new24-full-binary-g5-map-test.py
readonly RUNNER_TEST_SOURCE=/root/cubr-new24-full-binary-g5-run-test.sh
readonly INSTRUMENT_REPO=${CUBR_INSTRUMENT_REPO:-/root/cubr-new24-full-binary-g5-instrument}
readonly CARGO=/root/.cargo/bin/cargo
readonly RUSTC=/root/.cargo/bin/rustc
readonly GENERATED_CARGO_LOCK=code/cubrim-rs/Cargo.lock
readonly SYSTEMD_UNIT=${CUBR_SYSTEMD_UNIT:-}
readonly SYSTEMD_CONTRACT='Type=exec Restart=no RuntimeMaxSec=4h KillMode=control-group KillSignal=SIGTERM FinalKillSignal=SIGKILL'
readonly CAMPAIGN_BUDGET_SECONDS=14400
readonly FINALIZATION_RESERVE_SECONDS=120
readonly PUBLICATION_COMMIT_MARGIN_SECONDS=5
readonly MAP_BUILD_TIMEOUT_SECONDS=1200
readonly EVIDENCE_PART_MAX_BYTES=90000000
readonly CYCLE_DISAGREEMENT_MAX=0.10
readonly RECORD_RATIO_MAX=1.10
readonly SHARE_DELTA_MAX=1.00
readonly SAMPLE_COUNT_MIN=4787
readonly ZERO_HIT_BOUND_MAX=0.001
readonly EXPECTED_INSTRUCTION_COUNT=739548
readonly EXPECTED_PAGE_SIZE=4096
readonly FEASIBILITY_FIXTURE_BYTES=65536
readonly FEASIBILITY_FIXTURE_SHA=de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31
readonly FEASIBILITY_ARCHIVE_SHA=352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3
readonly INSTRUMENT_COMMIT=${CUBR_INSTRUMENT_COMMIT:-}
readonly EXPECTED_RUNNER_SHA=${CUBR_EXPECTED_RUNNER_SHA256:-}
readonly EXPECTED_MAPPER_SHA=${CUBR_EXPECTED_MAPPER_SHA256:-}
readonly EXPECTED_TEST_SHA=${CUBR_EXPECTED_TEST_SHA256:-}
readonly EXPECTED_MAPPER_TEST_SHA=${CUBR_EXPECTED_MAPPER_TEST_SHA256:-}
readonly EXPECTED_BINARY_SHA=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78
readonly EXPECTED_BINARY_BUILD_ID=789119db24ae1a28a24bcc0ecbec136c7e937d9a
readonly EXPECTED_CARGO_LOCK_SHA=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd
readonly SYSTEM_HEADER=/usr/include/x86_64-linux-gnu/bits/string_fortified.h
readonly EXPECTED_SYSTEM_HEADER_SHA=0cfa3c530938891615ab64ab5dfb72ebd8d02077d29d4410774b8a8ceff628fb
readonly EXPECTED_SYSTEM_HEADER_OWNER=libc6-dev:amd64
readonly EXPECTED_SYSTEM_HEADER_PACKAGE=libc6-dev
readonly EXPECTED_SYSTEM_HEADER_VERSION=2.39-0ubuntu8.8
readonly -a PIN=(/usr/bin/taskset -c 0-15)
readonly LOAD_MAX=8.0
readonly -a PERF_EVENTS=(task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults)
readonly -a CELLS=(
    'silesia|dickens|max|10192446|1340|435|b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    'silesia|xml|max|5345280|520|175|d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37|0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c'
    'silesia|dickens|web|10192446|380|320|a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
)

JOURNAL=
PREFLIGHT_DIR=
HARD_DEADLINE_MONOTONIC_NS=0
WORK_DEADLINE_MONOTONIC_NS=0
CAMPAIGN_STATUS=VALID-ATTRIBUTION
P4_STATUS=SUPPORTED
P5_STATUS=SUPPORTED
CURRENT_CELL=
CELL_STATUS=VALID-ATTRIBUTION
MAPPER=$MAPPER_SOURCE
BINARY_BUILD_ID=
MAP_MANIFEST=
INSTRUMENT_SHA256=${CUBR_MAP_INSTRUMENT_SHA:-}
MAPPING_SCHEMA_SHA256=
MAP_SEAL_SHA256=
PERF_EVENTS_CSV=cycles
FAILURE_REASON=
FAILURE_COMMAND=
FINALIZING=0
CONTROL_GROUP=
CGROUP_PROCS=
CGROUP_BASELINE_PIDS=
CGROUP_STOP_SENTINEL=${CUBR_CGROUP_STOP_SENTINEL:-}
CGROUP_SYSTEMCTL_USER=${CUBR_CGROUP_SYSTEMCTL_USER:-0}
declare -Ag CGROUP_ALLOWED_PIDS=()

now() { /usr/bin/date -u +%Y-%m-%dT%H:%M:%SZ; }
sha() { /usr/bin/sha256sum -- "$1" | /usr/bin/awk '{print $1}'; }

json_value() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import json, os, stat, sys
path, key = sys.argv[1:]
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise SystemExit("JSON input is not regular")
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        value = json.load(handle).get(key)
    fd = -1
finally:
    if fd >= 0:
        os.close(fd)
if isinstance(value, (dict, list)) or value is None:
    raise SystemExit(f"missing or nonscalar JSON key: {key}")
print(str(value).lower() if isinstance(value, bool) else value)
PY
}

checked_write_new() {
    /usr/bin/python3 - "$1" "${2:--}" <<'PY'
import os, secrets, stat, sys
from pathlib import Path

target, source_name = Path(sys.argv[1]), sys.argv[2]
limit = 90_000_000

def read_all(fd, label):
    chunks, total = [], 0
    while True:
        try:
            chunk = os.read(fd, min(1024 * 1024, limit + 1 - total))
        except InterruptedError:
            continue
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise SystemExit(f"{label} exceeds size bound")

if source_name == "@stdin-fd3":
    stdin_fd = os.dup(3)
    try:
        payload = read_all(stdin_fd, "evidence payload")
    finally:
        os.close(stdin_fd)
    if len(payload) > limit:
        raise SystemExit("evidence payload exceeds size bound")
else:
    source_fd = os.open(source_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        source_stat = os.fstat(source_fd)
        if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_nlink != 1:
            raise SystemExit("unsafe evidence source")
        if source_stat.st_size > limit:
            raise SystemExit("evidence source exceeds size bound")
        payload = read_all(source_fd, "evidence source")
    finally:
        os.close(source_fd)

parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
temporary = "." + target.name + "." + secrets.token_hex(16)
temporary_exists = False
try:
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=parent_fd)
    temporary_exists = True
    try:
        view = memoryview(payload)
        while view:
            try:
                written = os.write(fd, view)
            except InterruptedError:
                continue
            if written <= 0:
                raise OSError("zero-progress identity write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.link(temporary, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
            follow_symlinks=False)
    os.unlink(temporary, dir_fd=parent_fd)
    temporary_exists = False
    os.fsync(parent_fd)
    readback_fd = os.open(target.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=parent_fd)
    try:
        target_stat = os.fstat(readback_fd)
        if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_nlink != 1:
            raise SystemExit("unsafe evidence target")
        if read_all(readback_fd, "evidence readback") != payload:
            raise SystemExit("identity readback mismatch")
        os.fchmod(readback_fd, 0o444)
        os.fsync(readback_fd)
    finally:
        os.close(readback_fd)
    os.fsync(parent_fd)
finally:
    if temporary_exists:
        try:
            os.unlink(temporary, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
    os.close(parent_fd)
PY
}

write_new_checked() { checked_write_new "$1" "$2"; }
write_new_stdin() { checked_write_new "$1" @stdin-fd3 3<&0; }
monotonic_ns() {
    /usr/bin/python3 - <<'PY'
import time
print(time.clock_gettime_ns(time.CLOCK_MONOTONIC))
PY
}
monotonic_seconds() { printf '%s\n' "$(( $(monotonic_ns) / 1000000000 ))"; }

jlog() {
    [[ -n $JOURNAL ]] || return 0
    printf '%s\t%s\n' "$(now)" "$*" >>"$JOURNAL"
}

die() {
    FAILURE_REASON=$*
    jlog "fatal=$* cell=${CURRENT_CELL:-none}"
    printf 'current_profile_g5=VOID reason=%s\n' "$*" >&2
    exit 1
}

on_error() {
    local rc=$?
    FAILURE_REASON="command failed rc=$rc"
    FAILURE_COMMAND=${BASH_COMMAND//$'\n'/ }
    FAILURE_COMMAND=${FAILURE_COMMAND//$'\t'/ }
    jlog "error_rc=$rc command=$FAILURE_COMMAND"
    return "$rc"
}

require_fixed_sha() {
    local value=$1 label=$2
    [[ $value =~ ^[0-9a-f]{64}$ ]] || die "$label is missing or malformed"
}

refuse_existing_output() {
    [[ ! -e $OUT && ! -L $OUT ]] || die "refuse_existing_output: $OUT exists"
    [[ ! -e $PARTIAL && ! -L $PARTIAL ]] || die "refuse_existing_output: $PARTIAL exists"
    [[ ! -e $PUBLISHING && ! -L $PUBLISHING ]] || die "refuse_existing_output: $PUBLISHING exists"
    [[ ! -e $LATE && ! -L $LATE ]] || die "refuse_existing_output: $LATE exists"
}

remaining_budget_seconds() {
    local now_mono remaining deadline
    now_mono=$(monotonic_ns)
    deadline=$HARD_DEADLINE_MONOTONIC_NS
    (( FINALIZING != 0 )) || deadline=$WORK_DEADLINE_MONOTONIC_NS
    remaining=$(( (deadline - now_mono) / 1000000000 ))
    (( now_mono < deadline && remaining > 0 )) || die 'campaign budget exhausted'
    printf '%s\n' "$remaining"
}

remaining_command_budget_seconds() {
    local remaining
    remaining=$(remaining_budget_seconds)
    printf '%s\n' "$remaining"
}

require_deadline() {
    local label=$1
    (( $(remaining_budget_seconds) > 0 )) || die "deadline exhausted before $label"
    jlog "deadline_gate=$label remaining=$(remaining_budget_seconds)"
}

capture_cgroup_baseline() {
    local procs=$1 pid csv=
    [[ -f $procs && ! -L $procs ]] || die 'bound cgroup.procs is missing or unsafe'
    CGROUP_ALLOWED_PIDS=()
    while IFS= read -r pid; do
        [[ $pid =~ ^[1-9][0-9]*$ ]] || die 'bound cgroup.procs contains a malformed PID'
        [[ -z ${CGROUP_ALLOWED_PIDS[$pid]+x} ]] || die 'bound cgroup.procs contains a duplicate PID'
        CGROUP_ALLOWED_PIDS[$pid]=1
        csv+="${csv:+,}$pid"
    done <"$procs"
    [[ -n ${CGROUP_ALLOWED_PIDS[$$]+x} ]] || die 'runner PID is absent from bound cgroup.procs'
    CGROUP_BASELINE_PIDS=$csv
    [[ -z $PREFLIGHT_DIR ]] || printf '%s\n' "${csv//,/$'\n'}" >"$PREFLIGHT_DIR/systemd-cgroup-baseline.pids"
}

request_bound_unit_stop() {
    if [[ -n $CGROUP_STOP_SENTINEL ]]; then
        printf 'systemctl --no-block stop %s\n' "${SYSTEMD_UNIT:-mock.unit}" >"$CGROUP_STOP_SENTINEL"
        return 0
    fi
    if [[ $CGROUP_SYSTEMCTL_USER == 1 ]]; then
        jlog "unit_stop_request=$SYSTEMD_UNIT scope=user"
        /usr/bin/systemctl --user --no-block stop "$SYSTEMD_UNIT"
        return
    fi
    jlog "unit_stop_request=$SYSTEMD_UNIT scope=system"
    /usr/bin/systemctl --no-block stop "$SYSTEMD_UNIT"
}

assert_cgroup_no_new_pids() {
    local pid new_pids=()
    [[ -n $CGROUP_PROCS ]] || return 0
    [[ -f $CGROUP_PROCS && ! -L $CGROUP_PROCS ]] || {
        FAILURE_REASON='bound cgroup.procs became missing or unsafe'
        jlog "cgroup_guard_failure=$FAILURE_REASON"
        request_bound_unit_stop || true
        return 125
    }
    while IFS= read -r pid; do
        [[ $pid =~ ^[1-9][0-9]*$ ]] || {
            FAILURE_REASON='bound cgroup.procs contains a malformed PID'
            jlog "cgroup_guard_failure=$FAILURE_REASON"
            request_bound_unit_stop || true
            return 125
        }
        [[ -n ${CGROUP_ALLOWED_PIDS[$pid]+x} ]] || new_pids+=("$pid")
    done <"$CGROUP_PROCS"
    if (( ${#new_pids[@]} != 0 )); then
        FAILURE_REASON="bounded call retained new PID(s) in exact systemd ControlGroup"
        jlog "cgroup_new_pid=$(IFS=,; printf '%s' "${new_pids[*]}") control_group=$CONTROL_GROUP"
        request_bound_unit_stop || true
        return 125
    fi
}

run_process_group_bounded() {
    local limit=$1
    shift
    local leader rc
    /usr/bin/setsid /usr/bin/timeout --signal=TERM --kill-after=10s "${limit}s" "$@" &
    leader=$!
    if wait "$leader"; then rc=0; else rc=$?; fi
    assert_cgroup_no_new_pids || return 125
    return "$rc"
}

run_bounded() {
    local requested=$1
    shift
    local remaining limit
    remaining=$(remaining_command_budget_seconds)
    limit=$requested
    (( remaining < limit )) && limit=$remaining
    run_process_group_bounded "$limit" "$@"
}

classify_cycle_agreement() {
    /usr/bin/awk -v a="$1" -v b="$2" -v max="$CYCLE_DISAGREEMENT_MAX" 'BEGIN {
        hi=(a>b?a:b); lo=(a>b?b:a); if (hi<=0) exit 2;
        exit ((hi-lo)/hi <= max ? 0 : 1)
    }'
}

classify_record_overhead() {
    /usr/bin/awk -v plain="$1" -v record="$2" -v max="$RECORD_RATIO_MAX" 'BEGIN {
        if (plain<=0) exit 2; exit (record/plain <= max ? 0 : 1)
    }'
}

classify_share_stability() {
    /usr/bin/awk -v a="$1" -v b="$2" -v min="$3" -v delta="$SHARE_DELTA_MAX" 'BEGIN {
        d=a-b; if (d<0) d=-d; material=(a>=min || b>=min); exit (!material || d<=delta ? 0 : 1)
    }'
}

classify_sample_count() {
    (( $1 >= SAMPLE_COUNT_MIN ))
}

mark_descriptive() {
    CAMPAIGN_STATUS=VALID-DESCRIPTIVE
    [[ -z $CURRENT_CELL ]] || CELL_STATUS=VALID-DESCRIPTIVE
    jlog "descriptive_only_reason=$*"
}

refute_p4() {
    P4_STATUS=REFUTED
    mark_descriptive "$*"
}

refute_p5() {
    P5_STATUS=REFUTED
    mark_descriptive "$*"
}

verify_instrument_provenance() {
    [[ $INSTRUMENT_COMMIT =~ ^[0-9a-f]{40}$ ]] ||
        die 'instrument resulting-main commit is missing or malformed'
    require_fixed_sha "$EXPECTED_RUNNER_SHA" 'expected runner sha256'
    require_fixed_sha "$EXPECTED_MAPPER_SHA" 'expected mapper sha256'
    require_fixed_sha "$EXPECTED_TEST_SHA" 'expected test sha256'
    require_fixed_sha "$EXPECTED_MAPPER_TEST_SHA" 'expected mapper test sha256'
    [[ -d $INSTRUMENT_REPO/.git || -f $INSTRUMENT_REPO/.git ]] || die 'instrument repository missing'
    run_bounded 120 /usr/bin/git -C "$INSTRUMENT_REPO" fetch --quiet origin main
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" cat-file -e "$INSTRUMENT_COMMIT^{commit}" || die 'instrument commit unavailable'
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" merge-base --is-ancestor "$INSTRUMENT_COMMIT" origin/main ||
        die 'instrument commit is not contained in origin/main'

    local runner_path mapper_path test_path mapper_test_path
    runner_path=documentation/ephemeral/research/current-profile-g5-run.sh
    mapper_path=documentation/ephemeral/research/current_profile_g5_map.py
    test_path=documentation/ephemeral/research/current-profile-g5-run-test.sh
    mapper_test_path=documentation/ephemeral/research/test_current_profile_g5_map.py
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$runner_path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_RUNNER_SHA" ]] ||
        die 'instrument runner blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$mapper_path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_SHA" ]] ||
        die 'instrument mapper blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$test_path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_TEST_SHA" ]] ||
        die 'instrument test blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$mapper_test_path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'instrument mapper test blob mismatch'
    [[ $(sha "${BASH_SOURCE[0]}") == "$EXPECTED_RUNNER_SHA" ]] || die 'executed runner differs from frozen instrument blob'
    [[ $(sha "$MAPPER_SOURCE") == "$EXPECTED_MAPPER_SHA" ]] || die 'executed mapper differs from frozen instrument blob'
    [[ $(sha "$RUNNER_TEST_SOURCE") == "$EXPECTED_TEST_SHA" ]] || die 'executed runner test differs from frozen instrument blob'
    [[ $(sha "$MAPPER_TEST_SOURCE") == "$EXPECTED_MAPPER_TEST_SHA" ]] || die 'executed mapper test differs from frozen instrument blob'
    INSTRUMENT_SHA256=$({
        printf 'instrument_commit=%s\n' "$INSTRUMENT_COMMIT"
        printf 'runner_sha256=%s\n' "$EXPECTED_RUNNER_SHA"
        printf 'mapper_sha256=%s\n' "$EXPECTED_MAPPER_SHA"
        printf 'test_sha256=%s\n' "$EXPECTED_TEST_SHA"
        printf 'mapper_test_sha256=%s\n' "$EXPECTED_MAPPER_TEST_SHA"
    } | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')
    MAPPING_SCHEMA_SHA256=$({
        printf 'mapper_sha256=%s\n' "$EXPECTED_MAPPER_SHA"
        printf 'mapper_test_sha256=%s\n' "$EXPECTED_MAPPER_TEST_SHA"
    } | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')
}

verify_source_checkout() {
    [[ $(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD) == "$CODE_COMMIT" ]] || die 'source checkout commit mismatch'
    [[ $(/usr/bin/git -C "$CODE_DIR" symbolic-ref -q HEAD || true) == '' ]] || die 'source checkout is not detached'
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain=v1 --untracked-files=all) ]] ||
        die 'source checkout tracked or untracked state is dirty'
    /usr/bin/git -C "$CODE_DIR" cat-file -e "$CODE_COMMIT^{commit}" || die 'source commit object unavailable'
}

verify_topology() {
    local model
    [[ $(/usr/bin/hostname) == dev-ai ]] || die 'hostname is not dev-ai'
    model=$(/usr/bin/lscpu | /usr/bin/awk -F: '$1 ~ /Model name/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}')
    [[ $model == 'AMD EPYC 7502P 32-Core Processor' ]] || die 'CPU model mismatch'
    /usr/bin/lscpu -p=CPU,CORE | /usr/bin/awk -F, '
        $1 !~ /^#/ {cpu=$1+0; core=$2+0; seen[cpu]=core; count++}
        END {
            if (count != 64) exit 1;
            for (i=0; i<32; i++) if (!(i in seen) || seen[i] != i) exit 1;
            for (i=32; i<64; i++) if (!(i in seen) || seen[i] != i-32) exit 1;
        }
    ' || die 'CPU topology mismatch'
    /usr/bin/awk -v max="$LOAD_MAX" '{exit !($1 < max)}' /proc/loadavg || die 'one-minute load is not below 8.0'
}

classify_process_snapshot() {
    local snapshot=$1 output=$2
    /usr/bin/awk -v runner="$$" -v parent="$PPID" '
        $1 != runner && $1 != parent {
            comm=$3; args=$0
            if (comm ~ /^(cargo|rustc|rustup|perf)$/ ||
                args ~ /(cubrim|current-profile-g[34]-run|current_profile_g5_map[.]py)/) print
        }
    ' "$snapshot" >"$output"
}

reject_orphan_processes() {
    local snapshot=$1 matches=$2
    /usr/bin/ps -eo pid=,ppid=,comm=,args= >"$snapshot"
    classify_process_snapshot "$snapshot" "$matches"
    [[ ! -s $matches ]] || die 'orphan candidate/perf process or competing Cubrim/Cargo/Rust/current-profile runner'
}

verify_systemd_contract() {
    [[ -n $SYSTEMD_UNIT ]] || die 'CUBR_SYSTEMD_UNIT must name the transient unit'
    local props invocation main_pid nrestarts control_group cgroup_file
    props=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p Type -p Restart -p RuntimeMaxUSec \
        -p KillMode -p KillSignal -p FinalKillSignal -p InvocationID -p MainPID -p NRestarts \
        -p ControlGroup)
    /usr/bin/grep -qx 'Type=exec' <<<"$props" || die 'systemd Type is not exec'
    /usr/bin/grep -qx 'Restart=no' <<<"$props" || die 'systemd Restart is not no'
    { /usr/bin/grep -qx 'RuntimeMaxUSec=4h' <<<"$props" ||
        /usr/bin/grep -qx 'RuntimeMaxUSec=4h 0us' <<<"$props"; } || die 'systemd RuntimeMaxSec is not 4h'
    /usr/bin/grep -qx 'KillMode=control-group' <<<"$props" || die 'systemd KillMode is not control-group'
    /usr/bin/grep -qx 'KillSignal=15' <<<"$props" || die 'systemd KillSignal is not SIGTERM'
    /usr/bin/grep -qx 'FinalKillSignal=9' <<<"$props" || die 'systemd FinalKillSignal is not SIGKILL'
    invocation=$(/usr/bin/awk -F= '$1=="InvocationID" {print $2}' <<<"$props")
    [[ -n $invocation && -r /proc/$$/environ ]] || die 'unit InvocationID does not match current process'
    /usr/bin/tr '\0' '\n' </proc/$$/environ | /usr/bin/grep -qx "INVOCATION_ID=$invocation" ||
        die 'unit InvocationID does not match current process'
    main_pid=$(/usr/bin/awk -F= '$1=="MainPID" {print $2}' <<<"$props")
    [[ $main_pid == "$$" ]] || die 'systemd MainPID does not match current process'
    nrestarts=$(/usr/bin/awk -F= '$1=="NRestarts" {print $2}' <<<"$props")
    [[ $nrestarts == 0 ]] || die 'NRestarts is not 0'
    control_group=$(/usr/bin/awk -F= '$1=="ControlGroup" {print $2}' <<<"$props")
    [[ $control_group =~ ^/[A-Za-z0-9_.:@-]+(/[A-Za-z0-9_.:@-]+)*$ && $control_group != *'..'* ]] ||
        die 'systemd ControlGroup path is malformed'
    cgroup_file=/sys/fs/cgroup$control_group/cgroup.procs
    [[ -f $cgroup_file && ! -L $cgroup_file ]] || die 'systemd ControlGroup cgroup.procs is missing or unsafe'
    [[ $(/usr/bin/readlink -f -- "$cgroup_file") == "$cgroup_file" ]] ||
        die 'systemd ControlGroup cgroup.procs path does not resolve exactly'
    CONTROL_GROUP=$control_group
    CGROUP_PROCS=$cgroup_file
    capture_cgroup_baseline "$CGROUP_PROCS"
    printf '%s\n' "$SYSTEMD_CONTRACT" >"$PREFLIGHT_DIR/systemd-contract.txt"
    printf 'ControlGroup=%s\ncgroup.procs=%s\n' "$CONTROL_GROUP" "$CGROUP_PROCS" >>"$PREFLIGHT_DIR/systemd-contract.txt"
}

verify_manifest_source() {
    [[ -f $CORPUS_MANIFEST && ! -L $CORPUS_MANIFEST ]] || die 'corpus manifest missing or unsafe'
    local cell corpus file bytes archive_sha source_sha actual_bytes actual_source row
    for cell in "${CELLS[@]}"; do
        IFS='|' read -r corpus file _preset bytes _enc _dec archive_sha source_sha <<<"$cell"
        [[ $corpus == silesia ]] || die 'unexpected corpus'
        row=$(/usr/bin/awk -F '\t' -v c="$corpus" -v f="$file" 'NR>1 && $1==c && $2==f {print}' "$CORPUS_MANIFEST")
        [[ $(/usr/bin/awk -F '\t' -v c="$corpus" -v f="$file" 'NR>1 && $1==c && $2==f {n++} END {print n+0}' "$CORPUS_MANIFEST") == 1 ]] ||
            die "manifest cardinality mismatch for $corpus/$file"
        [[ $row == "$corpus"$'\t'"$file"$'\t'text$'\t'"$bytes"$'\t'"$source_sha" ]] ||
            die "manifest exact row mismatch for $corpus/$file"
        actual_bytes=$(/usr/bin/stat -c %s -- "$CORPUS_ROOT/$file")
        actual_source=$(sha "$CORPUS_ROOT/$file")
        [[ $actual_bytes == "$bytes" && $actual_source == "$source_sha" ]] || die "source identity mismatch for $file"
        printf '%s\t%s\t%s\t%s\n' "$file" "$bytes" "$source_sha" "$archive_sha"
    done >"$PREFLIGHT_DIR/cell-inputs.tsv"
}

verify_tools() {
    local tool
    [[ -d $ROOT && ! -L $ROOT ]] || die 'phaseC root missing or unsafe'
    for tool in /usr/bin/git /usr/bin/python3 /usr/bin/perf /usr/bin/readelf /usr/bin/objdump \
        /usr/bin/addr2line /usr/bin/time /usr/bin/timeout /usr/bin/taskset /usr/bin/sha256sum \
        /usr/bin/gzip /usr/bin/cmp /usr/bin/stat /usr/bin/systemctl /usr/bin/dpkg-query "$CARGO" "$RUSTC"; do
        [[ -x $tool ]] || die "required tool unavailable: $tool"
    done
    [[ -f $MAPPER_SOURCE && ! -L $MAPPER_SOURCE ]] || die 'mapper missing or unsafe'
    [[ -f $MAPPER_TEST_SOURCE && ! -L $MAPPER_TEST_SOURCE ]] || die 'mapper test missing or unsafe'
    [[ -f $RUNNER_TEST_SOURCE && ! -L $RUNNER_TEST_SOURCE ]] || die 'runner test missing or unsafe'
    [[ -x $CUBRIM && ! -L $CUBRIM ]] || die 'prebuilt release binary missing or unsafe'
    [[ $(sha "$CUBRIM") == "$EXPECTED_BINARY_SHA" ]] || die 'prebuilt release binary sha256 mismatch'
    [[ -f $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] ||
        die 'generated Cargo.lock missing or unsafe'
    [[ $(sha "$CODE_DIR/$GENERATED_CARGO_LOCK") == "$EXPECTED_CARGO_LOCK_SHA" ]] ||
        die 'generated Cargo.lock sha256 mismatch'
    [[ $($RUSTC -vV | /usr/bin/awk -F': ' '$1=="release" {print $2}') == 1.96.1 ]] || die 'rustc release mismatch'
    [[ $($RUSTC -vV | /usr/bin/awk -F': ' '$1=="commit-hash" {print $2}') == "$EXPECTED_RUSTC_COMMIT" ]] ||
        die 'rustc commit mismatch'
    [[ $(/usr/bin/getconf PAGE_SIZE) == "$EXPECTED_PAGE_SIZE" ]] || die 'page size mismatch'
    [[ $($CARGO --version | /usr/bin/awk '{print $2}') == 1.96.1 ]] || die 'cargo release mismatch'
    /usr/bin/perf --version | /usr/bin/grep -qF '6.8.12' || die 'perf version mismatch'
}

discover_perf_events() {
    local event supported=()
    : >"$PREFLIGHT_DIR/perf-events.tsv"
    for event in "${PERF_EVENTS[@]}"; do
        if run_bounded 30 "${PIN[@]}" /usr/bin/perf stat -x, -e "$event" -o "$PREFLIGHT_DIR/perf-$event.csv" -- /usr/bin/true; then
            printf '%s\tsupported\n' "$event" >>"$PREFLIGHT_DIR/perf-events.tsv"
            supported+=("$event")
        else
            printf '%s\tunsupported\n' "$event" >>"$PREFLIGHT_DIR/perf-events.tsv"
        fi
    done
    /usr/bin/grep -q $'^cycles\tsupported$' "$PREFLIGHT_DIR/perf-events.tsv" || die 'cycles perf event unavailable'
    PERF_EVENTS_CSV=$(IFS=,; printf '%s' "${supported[*]}")
}

admission() {
    local dir=$1 attempt=$2
    (( attempt == 1 )) || die 'admission attempt must be exactly one'
    require_deadline admission-tools
    verify_tools
    require_deadline admission-systemd
    verify_systemd_contract
    require_deadline admission-instrument-provenance
    verify_instrument_provenance
    require_deadline admission-source-checkout
    verify_source_checkout
    require_deadline admission-topology
    verify_topology
    require_deadline admission-process-snapshot
    reject_orphan_processes "$dir/process-snapshot.txt" "$dir/process-conflicts.txt"
    require_deadline admission-corpus-manifest
    verify_manifest_source
    require_deadline admission-perf-events
    discover_perf_events
    require_deadline admission-runner-contract
    /usr/bin/mkdir -m 0700 -- "$PREFLIGHT_DIR/live-fixture"
    run_bounded 900 /usr/bin/env \
        RUNNER="${BASH_SOURCE[0]}" MAPPER="$MAPPER_SOURCE" SELF_MUTATION_TESTS=1 \
        CUBR_REMOTE_LIVE_FIXTURE=1 CUBR_ENFORCE_CAMPAIGN_REREAD=1 \
        CUBR_ADMITTED_SYSTEMD_UNIT="$SYSTEMD_UNIT" \
        CUBR_ADMITTED_INVOCATION_ID="$INVOCATION_ID" \
        CUBR_ADMITTED_MAIN_PID="$$" \
        CUBR_ADMITTED_CONTROL_GROUP="$CONTROL_GROUP" \
        /usr/bin/bash "$RUNNER_TEST_SOURCE" "$PREFLIGHT_DIR/live-fixture" \
        >"$PREFLIGHT_DIR/runner-contract-test.txt"
    /usr/bin/chmod 0444 -- "$PREFLIGHT_DIR/runner-contract-test.txt"
    run_bounded 30 /usr/bin/python3 "$MAPPER_SOURCE" --help >"$dir/mapper-help.txt"
    {
        printf 'source_commit=%s\n' "$CODE_COMMIT"
        printf 'source_tree=%s\n' "$(/usr/bin/git -C "$CODE_DIR" rev-parse "$CODE_COMMIT^{tree}")"
        printf 'instrument_commit=%s\n' "$INSTRUMENT_COMMIT"
        printf 'instrument_sha256=%s\n' "$INSTRUMENT_SHA256"
        printf 'mapping_schema_sha256=%s\n' "$MAPPING_SCHEMA_SHA256"
        printf 'runner_sha256=%s\n' "$EXPECTED_RUNNER_SHA"
        printf 'mapper_sha256=%s\n' "$EXPECTED_MAPPER_SHA"
        printf 'test_sha256=%s\n' "$EXPECTED_TEST_SHA"
        printf 'mapper_test_sha256=%s\n' "$EXPECTED_MAPPER_TEST_SHA"
        printf 'cubrim_subtree=%s\n' "$(/usr/bin/git -C "$CODE_DIR" rev-parse "$CODE_COMMIT:code/cubrim-rs")"
        printf 'cargo_toml_blob=%s\n' "$(/usr/bin/git -C "$CODE_DIR" rev-parse "$CODE_COMMIT:code/cubrim-rs/Cargo.toml")"
        printf 'cargo_version=%s\n' "$($CARGO --version)"
        printf 'rustc_version=%s\n' "$($RUSTC -vV | /usr/bin/tr '\n' ';')"
    } >"$dir/identities.txt"
    /usr/bin/install -m 0444 -- "$MAPPER_SOURCE" "$dir/instrument-mapper.py"
    /usr/bin/install -m 0444 -- "$MAPPER_TEST_SOURCE" "$dir/instrument-mapper-test.py"
    /usr/bin/install -m 0444 -- "$RUNNER_TEST_SOURCE" "$dir/instrument-runner-test.sh"
    /usr/bin/install -m 0444 -- "${BASH_SOURCE[0]}" "$dir/instrument-runner.sh"
    /usr/bin/mkdir -- "$dir/mapper-test-runtime"
    /usr/bin/install -m 0444 -- "$MAPPER_SOURCE" "$dir/mapper-test-runtime/current_profile_g5_map.py"
    /usr/bin/install -m 0444 -- "$MAPPER_TEST_SOURCE" "$dir/mapper-test-runtime/test_current_profile_g5_map.py"
    require_deadline admission-mapper-tests
    (cd "$dir/mapper-test-runtime" && run_bounded 300 /usr/bin/env \
        PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 test_current_profile_g5_map.py) >"$dir/mapper-unit-test.txt"
    require_deadline admission-complete
}

restore_suite_side_effects() {
    local fixture=code/cubrim-rs/tests/fixtures/large_roundtrip.cubr
    /usr/bin/git -C "$CODE_DIR" restore --worktree -- \
        documentation/ephemeral/research/CUBR-0028-bench.json \
        documentation/ephemeral/research/CUBR-0031-bench.json 2>/dev/null || true
    if /usr/bin/git -C "$CODE_DIR" cat-file -e "HEAD:$fixture" 2>/dev/null; then
        /usr/bin/git -C "$CODE_DIR" restore --worktree -- "$fixture" 2>/dev/null || true
    elif [[ -e $CODE_DIR/$fixture || -L $CODE_DIR/$fixture ]]; then
        [[ -f $CODE_DIR/$fixture && ! -L $CODE_DIR/$fixture ]] || return 1
        /usr/bin/rm -- "$CODE_DIR/$fixture"
    fi
}

cleanup_build_outputs() {
    if [[ -e $PARTIAL/cargo-test-target || -L $PARTIAL/cargo-test-target ]]; then
        [[ -d $PARTIAL/cargo-test-target && ! -L $PARTIAL/cargo-test-target ]] || die 'suite target became unsafe'
        /usr/bin/find "$PARTIAL/cargo-test-target" -xdev -depth -delete
    fi
    /usr/bin/git -C "$CODE_DIR" clean -fX -- "$GENERATED_CARGO_LOCK" >/dev/null
}

run_suites() {
    local suite_dir=$PARTIAL/suites
    /usr/bin/mkdir -p -- "$suite_dir"
    export CARGO_TARGET_DIR=$PARTIAL/cargo-test-target
    export CARGO_PROFILE_RELEASE_DEBUG=1
    export CUBR_THREADS=4
    export RAYON_NUM_THREADS=4
    export OMP_NUM_THREADS=4
    export MKL_NUM_THREADS=4
    /usr/bin/cp -- "$CODE_DIR/$GENERATED_CARGO_LOCK" "$suite_dir/generated-Cargo.lock"
    /usr/bin/mkdir -p -- "$PARTIAL/binary"
    /usr/bin/install -m 0555 -- "$CUBRIM" "$MEASURED_BINARY"
    (
        cd "$CODE_DIR/code/cubrim-rs"
        run_bounded 1800 "$CARGO" test --release
    ) >"$suite_dir/cargo-test-release.log" 2>&1 || die 'cargo test --release failed'
    (
        cd "$CODE_DIR/code/cubrim-rs"
        run_bounded 1800 "$CARGO" test --release --test scheme_roundtrip -- --nocapture
    ) >"$suite_dir/scheme-roundtrip.log" 2>&1 || die 'cargo test --release --test scheme_roundtrip -- --nocapture failed'
    restore_suite_side_effects || die 'suite side-effect restoration failed'
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain=v1 --untracked-files=all) ]] || die 'suite side effects were not fully restored'
    [[ -x $CUBRIM && $(sha "$CUBRIM") == "$EXPECTED_BINARY_SHA" ]] || die 'release binary identity mismatch'
    [[ -f $CODE_DIR/$GENERATED_CARGO_LOCK && $(sha "$CODE_DIR/$GENERATED_CARGO_LOCK") == "$EXPECTED_CARGO_LOCK_SHA" ]] ||
        die 'generated Cargo.lock identity mismatch'
    /usr/bin/readelf -nW "$MEASURED_BINARY" >"$suite_dir/binary-notes.txt"
    BINARY_BUILD_ID=$(/usr/bin/awk '/Build ID:/ {print $3; exit}' "$suite_dir/binary-notes.txt")
    [[ $BINARY_BUILD_ID == "$EXPECTED_BINARY_BUILD_ID" ]] || die 'binary Build ID mismatch'
    cleanup_build_outputs
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain=v1 --ignored --untracked-files=all) ]] ||
        die 'captured build side effects were not removed'
}

generate_prefix_table() {
    local out=$1 resolver=$2 rust_sysroot rust_commit header_package header_version
    rust_sysroot=$($RUSTC --print sysroot)
    rust_commit=$($RUSTC -vV | /usr/bin/awk -F': ' '$1=="commit-hash" {print $2}')
    {
        printf 'source_domain\tpackage_identity\tprefix\treplacement\n'
        printf 'workspace\tcubrim@%s\t%s\t%s\n' "$CODE_COMMIT" "$CODE_DIR" "\$WORKSPACE"
        printf 'rust-stdlib\trustc@%s\t/rustc/%s\t%s\n' "$rust_commit" "$rust_commit" "\$RUSTC_SOURCE"
        printf 'rust-sysroot\trustc@%s\t%s\t%s\n' "$rust_commit" "$rust_sysroot" "\$RUST_SYSROOT"
        printf 'rust-dep\trustc@%s:gimli@0.32.3\t/rust/deps/gimli-0.32.3\t%s\n' "$rust_commit" "\$RUST_DEP_GIMLI_0_32_3"
        printf 'rust-dep\trustc@%s:hashbrown@0.16.1\t/rust/deps/hashbrown-0.16.1\t%s\n' "$rust_commit" "\$RUST_DEP_HASHBROWN_0_16_1"
        printf 'rust-dep\trustc@%s:addr2line@0.25.1\t/rust/deps/addr2line-0.25.1\t%s\n' "$rust_commit" "\$RUST_DEP_ADDR2LINE_0_25_1"
        printf 'rust-dep\trustc@%s:object@0.37.3\t/rust/deps/object-0.37.3\t%s\n' "$rust_commit" "\$RUST_DEP_OBJECT_0_37_3"
        printf 'rust-dep\trustc@%s:memchr@2.7.6\t/rust/deps/memchr-2.7.6\t%s\n' "$rust_commit" "\$RUST_DEP_MEMCHR_2_7_6"
        printf 'rust-dep\trustc@%s:libc@0.2.183\t/rust/deps/libc-0.2.183\t%s\n' "$rust_commit" "\$RUST_DEP_LIBC_0_2_183"
        printf 'rust-dep\trustc@%s:miniz_oxide@0.8.9\t/rust/deps/miniz_oxide-0.8.9\t%s\n' "$rust_commit" "\$RUST_DEP_MINIZ_OXIDE_0_8_9"
    } >"$out"
    /usr/bin/python3 - "$PARTIAL/suites/generated-Cargo.lock" "$resolver" "$out" <<'PY'
import hashlib, pathlib, sys, tomllib
lock, resolver, output = map(pathlib.Path, sys.argv[1:])
doc = tomllib.loads(lock.read_text())
text = resolver.read_text(errors="strict") if resolver.exists() else ""
rows = []
for package in doc.get("package", []):
    checksum = package.get("checksum")
    if not checksum:
        continue
    name, version = package["name"], package["version"]
    for path in pathlib.Path("/root/.cargo/registry/src").glob(f"*/{name}-{version}"):
        prefix = str(path.resolve()) + "/"
        if prefix in text:
            rows.append(("cargo", f"{name}@{version}#{checksum}", prefix,
                         "$CARGO_" + hashlib.sha256(f"{name}@{version}#{checksum}".encode()).hexdigest()[:16]))
with output.open("a", encoding="utf-8", newline="") as handle:
    for row in sorted(set(rows), key=lambda item: (-len(item[2]), item)):
        handle.write("\t".join(row) + "\n")
PY
    require_fixed_sha "$EXPECTED_SYSTEM_HEADER_SHA" 'expected system header sha256'
    [[ -f $SYSTEM_HEADER && ! -L $SYSTEM_HEADER && $(sha "$SYSTEM_HEADER") == "$EXPECTED_SYSTEM_HEADER_SHA" ]] ||
        die 'frozen system header identity mismatch'
    header_package=$(/usr/bin/dpkg-query -S "$SYSTEM_HEADER" | /usr/bin/awk -F': ' 'NR==1 {print $1}')
    header_version=$(/usr/bin/dpkg-query -W -f='${Version}' "$header_package")
    [[ $header_package == "$EXPECTED_SYSTEM_HEADER_OWNER" ]] || die 'frozen system header owner mismatch'
    [[ ${header_package%%:*} == "$EXPECTED_SYSTEM_HEADER_PACKAGE" ]] || die 'frozen system header package mismatch'
    [[ -n $EXPECTED_SYSTEM_HEADER_VERSION && $header_version == "$EXPECTED_SYSTEM_HEADER_VERSION" ]] ||
        die 'frozen system header version mismatch'
    printf 'system-header\tdebian:%s@%s#sha256=%s\t%s\t%s\n' \
        "$header_package" "$header_version" "$EXPECTED_SYSTEM_HEADER_SHA" "$SYSTEM_HEADER" "\$SYSTEM_STRING_FORTIFIED" >>"$out"
}

audit_prefix_coverage() {
    local resolver=$1 prefixes=$2 summary=$3
    /usr/bin/python3 - "$resolver" "$prefixes" "$summary" <<'PY'
import csv, pathlib, posixpath, re, sys
resolver, prefixes, summary = map(pathlib.Path, sys.argv[1:])
with prefixes.open(newline="") as handle:
    rules = sorted((row["prefix"].rstrip("/") or "/", row["replacement"])
                   for row in csv.DictReader(handle, delimiter="\t"))
rules.sort(key=lambda item: (-len(item[0]), item[0]))
absolute = re.compile(r"^(/.*):(?:[0-9]+|\?)$")
counts = {prefix: 0 for prefix, _ in rules}
unknown = []
for number, line in enumerate(resolver.read_text().splitlines(), 1):
    match = absolute.fullmatch(line.strip())
    if not match:
        continue
    raw = match.group(1)
    candidates = [prefix for prefix, _ in rules
                  if raw == prefix or raw.startswith(prefix + "/")]
    if len(candidates) != 1:
        unknown.append((number, raw, "unclassified-or-ambiguous"))
        continue
    prefix = candidates[0]
    normalized, normalized_prefix = posixpath.normpath(raw), posixpath.normpath(prefix)
    if not (normalized == normalized_prefix or normalized.startswith(normalized_prefix + "/")):
        unknown.append((number, raw, "lexical-root-escape"))
        continue
    counts[prefix] += 1
if unknown:
    for item in unknown[:20]:
        print(f"prefix coverage failure line={item[0]} reason={item[2]} path={item[1]}", file=sys.stderr)
    raise SystemExit(f"unclassified or escaping absolute resolver locations: {len(unknown)}")
total = sum(counts.values())
if total == 0:
    raise SystemExit("resolver contains no classified absolute locations")
summary.write_text("prefix\tlocation_rows\n" + "".join(
    f"{prefix}\t{count}\n" for prefix, count in sorted(counts.items())) + f"TOTAL\t{total}\n")
PY
}

compress_map_artifact() {
    local source=$1 metadata=$2
    local compressed=$source.gz
    /usr/bin/gzip -n -9 -c -- "$source" >"$compressed"
    /usr/bin/python3 - "$source" "$compressed" >>"$metadata" <<'PY'
import hashlib, pathlib, sys, zlib
source, compressed = map(pathlib.Path, sys.argv[1:])
raw, blob = source.read_bytes(), compressed.read_bytes()
stream = zlib.decompressobj(wbits=31)
decoded = stream.decompress(blob, len(raw) + 1)
if decoded != raw or not stream.eof or stream.unused_data or stream.unconsumed_tail:
    raise SystemExit("deterministic gzip roundtrip/trailing-member failure")
if blob[4:8] != b"\0\0\0\0":
    raise SystemExit("deterministic gzip mtime failure")
print("\t".join((source.name, str(len(raw)), hashlib.sha256(raw).hexdigest(),
                 compressed.name, str(len(blob)), hashlib.sha256(blob).hexdigest())))
PY
    (( $(/usr/bin/stat -c %s -- "$compressed") <= EVIDENCE_PART_MAX_BYTES )) ||
        die 'map evidence part exceeds 90000000 bytes'
    /usr/bin/rm -- "$source"
}

build_full_instruction_map_worker() {
    local map_dir=$PARTIAL/map
    [[ $INSTRUMENT_SHA256 =~ ^[0-9a-f]{64}$ ]] || die 'map worker instrument identity missing'
    [[ $EXPECTED_MAPPER_SHA =~ ^[0-9a-f]{64}$ && $(sha "$MAPPER_SOURCE") == "$EXPECTED_MAPPER_SHA" ]] ||
        die 'map worker mapper identity mismatch'
    [[ $EXPECTED_MAPPER_TEST_SHA =~ ^[0-9a-f]{64}$ && $(sha "$MAPPER_TEST_SOURCE") == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'map worker mapper test identity mismatch'
    MAPPING_SCHEMA_SHA256=$({
        printf 'mapper_sha256=%s\n' "$EXPECTED_MAPPER_SHA"
        printf 'mapper_test_sha256=%s\n' "$EXPECTED_MAPPER_TEST_SHA"
    } | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')
    [[ -x $MEASURED_BINARY && $(sha "$MEASURED_BINARY") == "$EXPECTED_BINARY_SHA" ]] || die 'map worker binary identity mismatch'
    /usr/bin/mkdir -p -- "$map_dir"
    /usr/bin/readelf -W -l "$MEASURED_BINARY" >"$map_dir/readelf-programs.txt"
    /usr/bin/readelf -W -S "$MEASURED_BINARY" >"$map_dir/readelf-sections.txt"
    /usr/bin/python3 "$MAPPER" normalize-elf \
        --input-root "$PARTIAL" --output-root "$map_dir" \
        --readelf-programs map/readelf-programs.txt --readelf-sections map/readelf-sections.txt \
        --binary-sha256 "$EXPECTED_BINARY_SHA" --source-base-id "$CODE_COMMIT" \
        --instrument-sha256 "$INSTRUMENT_SHA256" \
        --segments-out segments.tsv --sections-out sections.tsv \
        --summary-out elf-summary.json

    /usr/bin/objdump --disassemble --line-numbers --wide "$MEASURED_BINARY" >"$map_dir/objdump.txt"
    /usr/bin/awk '/^[[:space:]]*[0-9a-f]+:/ {gsub(":", "", $1); print "0x" $1}' \
        "$map_dir/objdump.txt" >"$map_dir/instruction-addresses.txt"
    [[ -s $map_dir/instruction-addresses.txt ]] || die 'objdump yielded no instruction addresses'
    /usr/bin/addr2line -a -f -C -i -e "$MEASURED_BINARY" <"$map_dir/instruction-addresses.txt" >"$map_dir/resolver-a.txt"
    /usr/bin/addr2line -a -f -C -i -e "$MEASURED_BINARY" <"$map_dir/instruction-addresses.txt" >"$map_dir/resolver-b.txt"
    /usr/bin/cmp -- "$map_dir/resolver-a.txt" "$map_dir/resolver-b.txt" || die 'addr2line reproducibility mismatch'
    generate_prefix_table "$map_dir/prefix-table.tsv" "$map_dir/resolver-a.txt"
    audit_prefix_coverage "$map_dir/resolver-a.txt" "$map_dir/prefix-table.tsv" "$map_dir/prefix-coverage-audit.tsv"

    /usr/bin/python3 "$MAPPER" build-map \
        --input-root "$PARTIAL" --output-root "$map_dir" \
        --segments map/segments.tsv --sections map/sections.tsv --objdump map/objdump.txt \
        --resolver-a map/resolver-a.txt --resolver-b map/resolver-b.txt \
        --prefix-table map/prefix-table.tsv --binary-dso "$MEASURED_BINARY" \
        --source-base-id "$CODE_COMMIT" --mapping-schema-sha256 "$MAPPING_SCHEMA_SHA256" \
        --map-part-prefix g5-full-instruction-map \
        --map-manifest-out map-parts-manifest.json \
        --summary-out map-summary.json \
        --max-part-bytes "$EVIDENCE_PART_MAX_BYTES"
    printf 'source\tuncompressed_bytes\tuncompressed_sha256\tcompressed\tcompressed_bytes\tcompressed_sha256\n' >"$map_dir/raw-stream-evidence.tsv"
    compress_map_artifact "$map_dir/objdump.txt" "$map_dir/raw-stream-evidence.tsv"
    compress_map_artifact "$map_dir/instruction-addresses.txt" "$map_dir/raw-stream-evidence.tsv"
    compress_map_artifact "$map_dir/resolver-a.txt" "$map_dir/raw-stream-evidence.tsv"
    compress_map_artifact "$map_dir/resolver-b.txt" "$map_dir/raw-stream-evidence.tsv"
    compress_map_artifact "$map_dir/map-summary.json" "$map_dir/raw-stream-evidence.tsv"
}

build_full_instruction_map() {
    local map_dir=$PARTIAL/map evidence_root elapsed_file=$PARTIAL/map/full-map-resource.txt
    local start end elapsed remaining limit
    evidence_root=${map_dir%/map}
    /usr/bin/mkdir -p -- "$map_dir"
    start=$(monotonic_seconds)
    remaining=$(remaining_command_budget_seconds)
    limit=$MAP_BUILD_TIMEOUT_SECONDS
    (( remaining < limit )) && limit=$remaining
    local map_rc
    set +e
    run_process_group_bounded "$limit" /usr/bin/time -v -o "$elapsed_file" \
        /usr/bin/env CUBR_MAP_INSTRUMENT_SHA="$INSTRUMENT_SHA256" \
            CUBR_EXPECTED_MAPPER_SHA256="$EXPECTED_MAPPER_SHA" \
            CUBR_EXPECTED_MAPPER_TEST_SHA256="$EXPECTED_MAPPER_TEST_SHA" \
            /usr/bin/bash "${BASH_SOURCE[0]}" --map-worker \
            >"$map_dir/map-worker.stdout.txt" 2>"$map_dir/map-worker.stderr.txt"
    map_rc=$?
    set -e
    end=$(monotonic_seconds)
    elapsed=$((end - start))
    printf 'full_map_elapsed_seconds=%s\n' "$elapsed" >"$map_dir/full-map-admission.txt"
    /usr/bin/awk -F: '/Maximum resident set size/ {gsub(/[[:space:]]/,"",$2); print "full_map_peak_rss_kib=" $2}' \
        "$elapsed_file" >>"$map_dir/full-map-admission.txt"
    (( map_rc == 0 )) || die "full map construction failed with rc=$map_rc"
    (( elapsed <= MAP_BUILD_TIMEOUT_SECONDS )) || die 'full map dry run exceeded 1200 seconds'
    MAP_MANIFEST=$map_dir/map-parts-manifest.json
    /usr/bin/python3 - "$MAP_MANIFEST" "$map_dir/map-summary.json.gz" "$map_dir" "$EVIDENCE_PART_MAX_BYTES" "$EXPECTED_INSTRUCTION_COUNT" <<'PY'
import csv, gzip, hashlib, json, pathlib, sys, zlib
manifest_path, summary_path, evidence_root = map(pathlib.Path, sys.argv[1:4])
limit, expected = map(int, sys.argv[4:6])
manifest = json.loads(manifest_path.read_text())
summary_blob = summary_path.read_bytes()
summary_stream = zlib.decompressobj(wbits=31)
summary_payload = summary_stream.decompress(summary_blob, 512 * 1024 * 1024)
if (not summary_stream.eof or summary_stream.unused_data or summary_stream.unconsumed_tail or
        summary_blob[4:8] != b"\0\0\0\0"):
    raise SystemExit("map summary deterministic gzip readback mismatch")
with (evidence_root / "raw-stream-evidence.tsv").open(newline="") as handle:
    summary_rows = [row for row in csv.DictReader(handle, delimiter="\t")
                    if row["source"] == "map-summary.json"]
if len(summary_rows) != 1:
    raise SystemExit("map summary compression evidence cardinality mismatch")
summary_evidence = summary_rows[0]
if (int(summary_evidence["uncompressed_bytes"]) != len(summary_payload) or
        summary_evidence["uncompressed_sha256"] != hashlib.sha256(summary_payload).hexdigest() or
        int(summary_evidence["compressed_bytes"]) != len(summary_blob) or
        summary_evidence["compressed_sha256"] != hashlib.sha256(summary_blob).hexdigest() or
        len(summary_blob) > limit):
    raise SystemExit("map summary compression evidence mismatch")
summary = json.loads(summary_payload)
count = summary.get("instruction_count")
if count != expected:
    raise SystemExit("exact frozen instruction count mismatch")
parts = manifest.get("parts")
if not isinstance(parts, list) or not parts:
    raise SystemExit("map manifest has no parts")
assembled = bytearray()
expected_row = 0
previous_offset = None
for index, part in enumerate(parts):
    if part.get("part_index") != index:
        raise SystemExit("map part index is not contiguous")
    path = evidence_root / part["path"]
    if path.stat().st_size > limit:
        raise SystemExit("map evidence part exceeds 90000000 bytes")
    data = gzip.decompress(path.read_bytes())
    if part.get("first_row_index") != expected_row or part.get("last_row_index") != expected_row + part["row_count"] - 1:
        raise SystemExit("map part row range is not contiguous")
    if previous_offset is not None and int(part["first_dso_file_offset"]) <= previous_offset:
        raise SystemExit("map part offset is not contiguous")
    if hashlib.sha256(data).hexdigest() != part.get("uncompressed_sha256"):
        raise SystemExit("map part roundtrip hash mismatch")
    assembled.extend(data)
    expected_row += int(part["row_count"])
    previous_offset = int(part["last_dso_file_offset"])
if expected_row != manifest.get("row_count"):
    raise SystemExit("map part row range is not contiguous")
if hashlib.sha256(assembled).hexdigest() != manifest.get("full_uncompressed_sha256"):
    raise SystemExit("map full reconstruction mismatch")
if len(assembled) != manifest.get("full_uncompressed_bytes"):
    raise SystemExit("map full reconstruction mismatch")
if (summary.get("canonical_uncompressed_sha256") != manifest.get("full_uncompressed_sha256") or
        summary.get("canonical_uncompressed_bytes") != manifest.get("full_uncompressed_bytes")):
    raise SystemExit("map full reconstruction mismatch")
declared = {item["path"] for item in parts}
observed = {path.name for path in evidence_root.glob("g5-full-instruction-map.part-*.tsv.gz")}
if observed != declared:
    raise SystemExit("map manifest has extra or missing parts")
PY
    /usr/bin/python3 "$MAPPER" seal-admission \
        --input-root "$evidence_root" --output-root "$map_dir" \
        --binary-build-id "$BINARY_BUILD_ID" --binary-sha256 "$EXPECTED_BINARY_SHA" \
        --instrument-resulting-main "$INSTRUMENT_COMMIT" \
        --mapper-sha256 "$EXPECTED_MAPPER_SHA" --mapper-test-sha256 "$EXPECTED_MAPPER_TEST_SHA" \
        --mapping-schema-sha256 "$MAPPING_SCHEMA_SHA256" \
        --reuse-decision REJECTED_IDENTITY_MISMATCH \
        --source-tree "$(/usr/bin/git -C "$CODE_DIR" rev-parse 'HEAD^{tree}')" \
        --toolchain-json preflight/map-toolchain.json \
        --map-manifest map/map-parts-manifest.json \
        --map-summary map/map-summary.json.gz \
        --raw-stream-evidence map/raw-stream-evidence.tsv \
        --seal-out map-admission-seal.json
    test -f "$map_dir/map-admission-seal.json"
    test ! -e "$map_dir/map/map-admission-seal.json"
    test "$(json_value "$map_dir/map-admission-seal.json" schema)" = \
        cubr-new24-g5-map-admission-seal-v1
    test "$(json_value "$map_dir/map-admission-seal.json" reuse_decision)" = \
        REJECTED_IDENTITY_MISMATCH
    MAP_SEAL_SHA256=$(sha "$map_dir/map-admission-seal.json")
    freeze_admitted_binary_identity
}

freeze_admitted_binary_identity() {
    local stat_line
    stat_line=$(/usr/bin/stat -Lc '%s\t%d\t%i' -- "$MEASURED_BINARY")
    printf 'sha256\tsize\tdevice\tinode\tbuild_id\tsegments_sha256\n' >"$PARTIAL/binary/admitted-snapshot.tsv"
    printf '%s\t%s\t%s\t%s\n' "$EXPECTED_BINARY_SHA" "$stat_line" "$BINARY_BUILD_ID" "$(sha "$PARTIAL/map/segments.tsv")" >>"$PARTIAL/binary/admitted-snapshot.tsv"
}

binary_snapshot() {
    local label=$1 out=$2 data=$3
    local stat_line
    stat_line=$(/usr/bin/stat -Lc '%s\t%d\t%i' -- "$MEASURED_BINARY")
    printf 'label\tsha256\tsize\tdevice\tinode\tbuild_id\tsegments_sha256\n' >"$out"
    printf '%s\t%s\t%s\t%s\t%s\n' "$label" "$(sha "$MEASURED_BINARY")" "$stat_line" "$BINARY_BUILD_ID" "$(sha "$PARTIAL/map/segments.tsv")" >>"$out"
    [[ $(sha "$MEASURED_BINARY") == "$EXPECTED_BINARY_SHA" ]] || die 'binary changed around perf record'
    /usr/bin/cmp -- <(/usr/bin/cut -f2- "$out") "$PARTIAL/binary/admitted-snapshot.tsv" ||
        die 'binary snapshot differs from frozen admission identity'
    [[ -f $data || $label == binary-snapshot-before ]] || die 'perf data missing after record'
}

verify_perf_record_artifacts() {
    local data=$1 prefix=$2 decode_output=$3 expected=$4
    run_bounded 120 /usr/bin/perf buildid-list -i "$data" >"$prefix.buildid-list.txt"
    run_bounded 120 /usr/bin/perf script -i "$data" --show-mmap-events --show-lost-events -F period,ip,dso,dsoff >"$prefix.perf-script.txt"
    /usr/bin/grep -qi "$BINARY_BUILD_ID" "$prefix.buildid-list.txt" || die 'perf build-ID list omits benchmark binary'
    /usr/bin/cmp -- "$expected" "$decode_output" || die 'record decode output mismatch'
    [[ $(sha "$decode_output") == $(sha "$expected") ]] || die 'record decode sha roundtrip mismatch'
}

record_decode_a() {
    local archive=$1 output=$2 data=$3 prefix=$4 expected=$5 budget=$6
    local limit
    limit=$(remaining_command_budget_seconds)
    (( budget < limit )) && limit=$budget
    binary_snapshot binary-snapshot-before "$prefix.binary-snapshot-before.tsv" "$data"
    /usr/bin/time -v -o "$prefix.time.txt" \
        /usr/bin/timeout --kill-after=10s "${limit}s" \
        "${PIN[@]}" /usr/bin/perf record -q --buildid-all --buildid-mmap -F 997 -e cycles -o "$data" -- \
            "$MEASURED_BINARY" decode "$archive" "$output"
    binary_snapshot binary-snapshot-after "$prefix.binary-snapshot-after.tsv" "$data"
    /usr/bin/cmp -- <(/usr/bin/cut -f2- "$prefix.binary-snapshot-before.tsv") \
        <(/usr/bin/cut -f2- "$prefix.binary-snapshot-after.tsv") || die 'binary identity changed across record A'
    verify_perf_record_artifacts "$data" "$prefix" "$output" "$expected"
}

record_decode_b() {
    local archive=$1 output=$2 data=$3 prefix=$4 expected=$5 budget=$6
    local limit
    limit=$(remaining_command_budget_seconds)
    (( budget < limit )) && limit=$budget
    binary_snapshot binary-snapshot-before "$prefix.binary-snapshot-before.tsv" "$data"
    /usr/bin/time -v -o "$prefix.time.txt" \
        /usr/bin/timeout --kill-after=10s "${limit}s" \
        "${PIN[@]}" /usr/bin/perf record -q --buildid-all --buildid-mmap -F 997 -e cycles -o "$data" -- \
            "$MEASURED_BINARY" decode "$archive" "$output"
    binary_snapshot binary-snapshot-after "$prefix.binary-snapshot-after.tsv" "$data"
    /usr/bin/cmp -- <(/usr/bin/cut -f2- "$prefix.binary-snapshot-before.tsv") \
        <(/usr/bin/cut -f2- "$prefix.binary-snapshot-after.tsv") || die 'binary identity changed across record B'
    verify_perf_record_artifacts "$data" "$prefix" "$output" "$expected"
}

decode_checked() {
    local cell=$1 mode=$2 archive=$3 expected=$4 output=$5 budget=$6 cell_dir=$7
    local limit
    limit=$(remaining_command_budget_seconds)
    (( budget < limit )) && limit=$budget
    case $mode in
        plain)
            /usr/bin/time -v -o "$cell_dir/plain.time.txt" \
                /usr/bin/timeout --kill-after=10s "${limit}s" \
                "${PIN[@]}" "$MEASURED_BINARY" decode "$archive" "$output" ;;
        pstat1|pstat2)
            run_bounded "$budget" "${PIN[@]}" /usr/bin/perf stat -x, -e "$PERF_EVENTS_CSV" \
                -o "$cell_dir/$mode.perf-stat.csv" -- "$MEASURED_BINARY" decode "$archive" "$output" ;;
        prec1)
            record_decode_a "$archive" "$output" "$cell_dir/prec1.data" "$cell_dir/prec1" "$expected" "$budget" ;;
        prec2)
            record_decode_b "$archive" "$output" "$cell_dir/prec2.data" "$cell_dir/prec2" "$expected" "$budget" ;;
        *) die "unknown decode mode: $mode" ;;
    esac
    /usr/bin/cmp -- "$expected" "$output" || die "$cell $mode exact cmp roundtrip failed"
    [[ $(sha "$output") == $(sha "$expected") ]] || die "$cell $mode sha roundtrip failed"
    (( $(remaining_command_budget_seconds) >= 1 && budget > 0 )) || die 'decode exhausted budget'
}

parse_cycles() {
    local file=$1
    /usr/bin/awk -F, '$3=="cycles" {gsub(/[[:space:]]/, "", $1); if ($1 ~ /^[0-9]+$/) {print $1; exit}}' "$file"
}

parse_elapsed() {
    /usr/bin/python3 - "$1" <<'PY'
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text()
match = re.search(r"Elapsed \(wall clock\) time .*?:\s*((?:(\d+):)?(\d+):(\d+(?:\.\d+)?))\s*$", text, re.M)
if not match:
    raise SystemExit(1)
hours = int(match.group(2) or 0)
print(hours * 3600 + int(match.group(3)) * 60 + float(match.group(4)))
PY
}

evaluate_measurement_stability() {
    local cell=$1 dir=$2 cycles_a cycles_b plain record_a record_b
    local cycle_gate=SUPPORTED record_a_gate=SUPPORTED record_b_gate=SUPPORTED ratio_a ratio_b
    cycles_a=$(parse_cycles "$dir/pstat1.perf-stat.csv")
    cycles_b=$(parse_cycles "$dir/pstat2.perf-stat.csv")
    plain=$(parse_elapsed "$dir/plain.time.txt")
    record_a=$(parse_elapsed "$dir/prec1.time.txt")
    record_b=$(parse_elapsed "$dir/prec2.time.txt")
    [[ $cycles_a =~ ^[0-9]+$ && $cycles_b =~ ^[0-9]+$ ]] || die "$cell cycles parsing failed"
    [[ $plain =~ ^[0-9]+([.][0-9]+)?$ && $record_a =~ ^[0-9]+([.][0-9]+)?$ && $record_b =~ ^[0-9]+([.][0-9]+)?$ ]] ||
        die "$cell elapsed-time parsing failed"
    if ! classify_cycle_agreement "$cycles_a" "$cycles_b"; then
        cycle_gate=REFUTED
        refute_p5 "$cell cycle disagreement exceeds 0.10"
    fi
    if ! classify_record_overhead "$plain" "$record_a"; then
        record_a_gate=REFUTED
        refute_p5 "$cell record A/plain ratio exceeds 1.10"
    fi
    if ! classify_record_overhead "$plain" "$record_b"; then
        record_b_gate=REFUTED
        refute_p5 "$cell record B/plain ratio exceeds 1.10"
    fi
    ratio_a=$(/usr/bin/awk -v r="$record_a" -v p="$plain" 'BEGIN {printf "%.9f", r/p}')
    ratio_b=$(/usr/bin/awk -v r="$record_b" -v p="$plain" 'BEGIN {printf "%.9f", r/p}')
    {
        printf 'cell\tcycles_a\tcycles_b\tcycle_gate\tplain_wall\trecord_a_wall\trecord_a_ratio\trecord_a_gate\trecord_b_wall\trecord_b_ratio\trecord_b_gate\n'
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$cell" "$cycles_a" "$cycles_b" "$cycle_gate" "$plain" "$record_a" "$ratio_a" "$record_a_gate" \
            "$record_b" "$ratio_b" "$record_b_gate"
    } >"$dir/measurement-stability.tsv"
}

reduce_record() {
    local cell_dir=$1 repeat=$2
    local stat_device inode size device_label
    stat_device=$(/usr/bin/stat -Lc %d -- "$MEASURED_BINARY")
    inode=$(/usr/bin/stat -Lc %i -- "$MEASURED_BINARY")
    size=$(/usr/bin/stat -Lc %s -- "$MEASURED_BINARY")
    device_label=$(/usr/bin/python3 - "$MEASURED_BINARY" <<'PY'
import os, sys
device = os.stat(sys.argv[1]).st_dev
print(f"{os.major(device):02x}:{os.minor(device):02x}")
PY
)
    run_bounded 600 /usr/bin/python3 "$MAPPER" reduce-record \
        --input-root "$PARTIAL" --output-root "$cell_dir" \
        --map-manifest map/map-parts-manifest.json \
        --segments map/segments.tsv --page-size "$EXPECTED_PAGE_SIZE" \
        --perf-script "cells/$(/usr/bin/basename "$cell_dir")/$repeat.perf-script.txt" \
        --build-id-list "cells/$(/usr/bin/basename "$cell_dir")/$repeat.buildid-list.txt" \
        --binary-path binary/cubrim --binary-dso "$MEASURED_BINARY" --binary-build-id "$BINARY_BUILD_ID" \
        --binary-device "$device_label" --binary-inode "$inode" --binary-sha256 "$EXPECTED_BINARY_SHA" \
        --binary-size "$size" --binary-stat-device "$stat_device" \
        --source-base-id "$CODE_COMMIT" --instrument-sha256 "$INSTRUMENT_SHA256" \
        --record-out "$repeat.record.json"
}

evaluate_cell_attribution() {
    local cell=$1 dir=$2
    local rel=${dir#"$PARTIAL"/}
    local record_gate_rc summary_gate_rc
    run_bounded 120 /usr/bin/python3 "$MAPPER" summarize-file --input-root "$PARTIAL" --output-root "$dir" \
        --cell "$cell" --record-a "$rel/prec1.record.json" --record-b "$rel/prec2.record.json" \
        --summary-out attribution-summary.json
    set +e
    /usr/bin/python3 - "$dir/prec1.record.json" "$dir/prec2.record.json" \
        "$SAMPLE_COUNT_MIN" "$ZERO_HIT_BOUND_MAX" <<'PY'
import json, pathlib, sys
a, b = (json.loads(pathlib.Path(p).read_text()) for p in sys.argv[1:3])
minimum, bound = int(sys.argv[3]), float(sys.argv[4])
for record in (a, b):
    n = int(record["binary_sample_count"])
    if (n < minimum or float(record["binary_zero_hit_upper_bound"]) > bound or
            not record["attribution_grade_record_pass"] or record["lost_record_count"] != 0 or
            record["conservation"] != "PASS" or record["symbol_consulted"] is not False):
        raise SystemExit(3)
PY
    record_gate_rc=$?
    set -e
    case $record_gate_rc in
        0) ;;
        3) refute_p4 "$cell sample population or zero-hit gate" ;;
        *) die "$cell attribution record evidence failure rc=$record_gate_rc" ;;
    esac
    set +e
    /usr/bin/python3 - "$dir/attribution-summary.json" "$SHARE_DELTA_MAX" <<'PY'
import json, pathlib, sys
summary = json.loads(pathlib.Path(sys.argv[1]).read_text())
delta = float(sys.argv[2])
families = summary.get("material_families", {})
for family in families.values():
    shares = [float(value) for value in family["record_shares_percent"]]
    if max(shares) < 5.0:
        raise SystemExit(3)
    if abs(shares[0] - shares[1]) > delta or not family["repeatable"]:
        raise SystemExit(3)
if summary.get("cross_file_reduction_performed") is not False:
    raise SystemExit(3)
PY
    summary_gate_rc=$?
    set -e
    case $summary_gate_rc in
        0) ;;
        3) refute_p5 "$cell material-family stability gate" ;;
        *) die "$cell attribution summary evidence failure rc=$summary_gate_rc" ;;
    esac
}

run_cell() {
    local row=$1 corpus file preset bytes encode_budget decode_budget archive_sha source_sha
    IFS='|' read -r corpus file preset bytes encode_budget decode_budget archive_sha source_sha <<<"$row"
    local cell_name=${corpus}-${file}-${preset} cell_dir=$PARTIAL/cells/${corpus}-${file}-${preset}
    local source=$CORPUS_ROOT/$file archive1=$cell_dir/archive-1.cubr archive2=$cell_dir/archive-2.cubr
    CURRENT_CELL=$cell_name
    CELL_STATUS=VALID-ATTRIBUTION
    /usr/bin/mkdir -p -- "$cell_dir"
    [[ $(/usr/bin/stat -c %s -- "$source") == "$bytes" && $(sha "$source") == "$source_sha" ]] || die "$cell_name source changed"
    run_bounded "$encode_budget" "${PIN[@]}" "$MEASURED_BINARY" encode --preset "$preset" "$source" "$archive1"
    run_bounded "$encode_budget" "${PIN[@]}" "$MEASURED_BINARY" encode --preset "$preset" "$source" "$archive2"
    /usr/bin/cmp -- "$archive1" "$archive2" || die "$cell_name two-encode cmp mismatch"
    [[ $(sha "$archive1") == "$archive_sha" && $(sha "$archive2") == "$archive_sha" ]] || die "$cell_name two-encode sha mismatch"

    decode_checked "$cell_name" plain "$archive2" "$source" "$cell_dir/plain.out" "$decode_budget" "$cell_dir"
    decode_checked "$cell_name" pstat1 "$archive2" "$source" "$cell_dir/pstat1.out" "$decode_budget" "$cell_dir"
    decode_checked "$cell_name" pstat2 "$archive2" "$source" "$cell_dir/pstat2.out" "$decode_budget" "$cell_dir"
    decode_checked "$cell_name" prec1 "$archive2" "$source" "$cell_dir/prec1.out" "$decode_budget" "$cell_dir"
    decode_checked "$cell_name" prec2 "$archive2" "$source" "$cell_dir/prec2.out" "$decode_budget" "$cell_dir"
    evaluate_measurement_stability "$cell_name" "$cell_dir"
    reduce_record "$cell_dir" prec1
    reduce_record "$cell_dir" prec2
    evaluate_cell_attribution "$cell_name" "$cell_dir"
    printf 'cell=%s\tstatus=%s\tselection=NO-SELECT\n' "$cell_name" "$CELL_STATUS" >"$cell_dir/verdict.txt"
}

verify_feasibility_fixture() {
    local root=$1
    local fixture=$root/feasibility-zero.bin archive1=$root/feasibility-1.cubr archive2=$root/feasibility-2.cubr
    local decoded=$root/feasibility-decoded.bin
    /usr/bin/dd if=/dev/zero of="$fixture" bs="$FEASIBILITY_FIXTURE_BYTES" count=1 status=none
    [[ $(sha "$fixture") == "$FEASIBILITY_FIXTURE_SHA" ]] || die 'fixed feasibility fixture identity mismatch'
    run_bounded 120 "${PIN[@]}" "$MEASURED_BINARY" encode --preset max "$fixture" "$archive1"
    run_bounded 120 "${PIN[@]}" "$MEASURED_BINARY" encode --preset max "$fixture" "$archive2"
    /usr/bin/cmp -- "$archive1" "$archive2" || die 'fixed fixture encode reproducibility mismatch'
    [[ $(/usr/bin/stat -c %s -- "$archive1") == 50 && $(sha "$archive1") == "$FEASIBILITY_ARCHIVE_SHA" ]] ||
        die 'fixed fixture archive identity mismatch'
    run_bounded 120 "${PIN[@]}" "$MEASURED_BINARY" decode "$archive1" "$decoded"
    /usr/bin/cmp -- "$fixture" "$decoded" || die 'fixed fixture decode cmp mismatch'
    [[ $(sha "$decoded") == "$FEASIBILITY_FIXTURE_SHA" ]] || die 'fixed fixture decode sha mismatch'
}

verify_address_join_smoke() {
    local root=$1
    local archive=$root/feasibility-1.cubr output=$root/address-smoke.out data=$root/address-smoke.data
    local prefix=$root/address-smoke
    local smoke_limit
    smoke_limit=$(remaining_command_budget_seconds)
    (( smoke_limit > 120 )) && smoke_limit=120
    binary_snapshot binary-snapshot-before "$prefix.binary-snapshot-before.tsv" "$data"
    local -a smoke_record=(/usr/bin/perf record -q --buildid-all
        --buildid-mmap -F 997 -e cycles)
    /usr/bin/timeout --kill-after=10s "${smoke_limit}s" \
        "${PIN[@]}" "${smoke_record[@]}" -o "$data" -- "$MEASURED_BINARY" decode "$archive" "$output"
    binary_snapshot binary-snapshot-after "$prefix.binary-snapshot-after.tsv" "$data"
    verify_perf_record_artifacts "$data" "$prefix" "$output" "$root/feasibility-zero.bin"
    local stat_device inode size device_label
    stat_device=$(/usr/bin/stat -Lc %d -- "$MEASURED_BINARY")
    inode=$(/usr/bin/stat -Lc %i -- "$MEASURED_BINARY")
    size=$(/usr/bin/stat -Lc %s -- "$MEASURED_BINARY")
    device_label=$(/usr/bin/python3 - "$MEASURED_BINARY" <<'PY'
import os, sys
device = os.stat(sys.argv[1]).st_dev
print(f"{os.major(device):02x}:{os.minor(device):02x}")
PY
)
    run_bounded 600 /usr/bin/python3 "$MAPPER" reduce-record \
        --input-root "$PARTIAL" --output-root "$PARTIAL" --map-manifest map/map-parts-manifest.json \
        --segments map/segments.tsv --page-size "$EXPECTED_PAGE_SIZE" \
        --perf-script address-smoke.perf-script.txt --build-id-list address-smoke.buildid-list.txt \
        --binary-path binary/cubrim --binary-dso "$MEASURED_BINARY" --binary-build-id "$BINARY_BUILD_ID" \
        --binary-device "$device_label" --binary-inode "$inode" --binary-sha256 "$EXPECTED_BINARY_SHA" \
        --binary-size "$size" --binary-stat-device "$stat_device" \
        --source-base-id "$CODE_COMMIT" --instrument-sha256 "$INSTRUMENT_SHA256" \
        --record-out address-smoke.record.json
    /usr/bin/python3 - "$root/address-smoke.record.json" "$root/address-smoke-feasibility.json" <<'PY'
import json, pathlib, sys
record_path, output_path = map(pathlib.Path, sys.argv[1:])
record = json.loads(record_path.read_text())
if int(record.get("binary_sample_count", 0)) < 1 or int(record.get("binary_unresolved_sample_count", 1)) != 0:
    raise SystemExit("address smoke did not map a binary sample")
sanitized = {
    "schema": "cubr-new24-g5-address-smoke-v1",
    "purpose": "mechanical-address-join-feasibility-only",
    "performance_interpretation": "FORBIDDEN",
    "binary_identity": record["binary_identity"],
    "binary_snapshot": record["binary_snapshot"],
    "binary_sample_count": record["binary_sample_count"],
    "binary_unresolved_sample_count": record["binary_unresolved_sample_count"],
    "binary_resolution_gate_pass": record["binary_resolution_gate_pass"],
    "lost_record_count": record["lost_record_count"],
    "conservation": record["conservation"],
    "symbol_consulted": record["symbol_consulted"],
}
output_path.write_text(json.dumps(sanitized, sort_keys=True, separators=(",", ":")) + "\n")
PY
    /usr/bin/rm -- "$root/address-smoke.record.json"
}

write_manifests() {
    local root=${1:-$PARTIAL} file
    if /usr/bin/find "$root" -xdev \( -type l -o -type p -o -type s -o -type b -o -type c \) -print -quit | /usr/bin/grep -q .; then
        die 'special or symlink node found in evidence tree'
    fi
    if /usr/bin/find "$root" -xdev -type f -size +90000000c -print -quit | /usr/bin/grep -q .; then
        die 'evidence file exceeds 90000000 bytes'
    fi
    : >"$root/evidence-sha256.tsv"
    while IFS= read -r -d '' file; do
        [[ $file == "$root/evidence-sha256.tsv" || $file == "$root/TIMING-DONE.STAMP" ]] && continue
        printf '%s\t%s\t%s\n' "$(sha "$file")" "$(/usr/bin/stat -c %s -- "$file")" "${file#"$root"/}" >>"$root/evidence-sha256.tsv"
    done < <(/usr/bin/find "$root" -xdev -type f -print0 | /usr/bin/sort -z)
    /usr/bin/python3 - "$root" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
listed = {line.rstrip("\n").split("\t", 2)[2]
          for line in (root / "evidence-sha256.tsv").read_text().splitlines() if line}
actual = {path.relative_to(root).as_posix() for path in root.rglob("*")
          if path.is_file() and path.name != "evidence-sha256.tsv"}
if listed != actual:
    raise SystemExit("unlisted or missing evidence artifact")
PY
}

publish_campaign() {
    local source=$1 publishing=$2 destination=$3 late=$4 completed=$5
    local hard_deadline_ns=${6:-$(( $(monotonic_ns) + 60000000000 ))}
    local crash_at=${7:-} delay_before_final=${8:-0}
    local commit_margin_seconds=${9:-$PUBLICATION_COMMIT_MARGIN_SECONDS}
    if /usr/bin/python3 - "$source" "$publishing" "$destination" "$late" \
        "$CAMPAIGN_STATUS" "$CODE_COMMIT" "$INSTRUMENT_COMMIT" "$completed" \
        "$hard_deadline_ns" "$commit_margin_seconds" "$crash_at" \
        "$delay_before_final" "$CGROUP_PROCS" "$CGROUP_BASELINE_PIDS" \
        "${MAP_SEAL_SHA256:-NO-MAP-SEAL}" <<'PY'
import ctypes, hashlib, os, pathlib, stat, sys, time
source_path, publishing_path, destination_path, late_path = map(pathlib.Path, sys.argv[1:5])
status, source_commit, instrument_commit, completed = sys.argv[5:9]
hard_deadline_ns, commit_margin_seconds = int(sys.argv[9]), int(sys.argv[10])
crash_at, delay_before_final = sys.argv[11], float(sys.argv[12])
cgroup_procs = pathlib.Path(sys.argv[13]) if sys.argv[13] else None
baseline_pids = {int(value) for value in sys.argv[14].split(",") if value}
map_seal_sha256 = sys.argv[15]
commit_deadline_ns = hard_deadline_ns - commit_margin_seconds * 1_000_000_000
def monotonic_ns():
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)
def require_before(deadline, label):
    if monotonic_ns() >= deadline:
        raise SystemExit(f"hard monotonic deadline reached before {label}")
def crash(point):
    if crash_at == point:
        raise SystemExit(f"injected publish crash: {point}")
def write_all(fd, payload):
    publication_marker_bytes = memoryview(payload)
    offset = 0
    injected = os.environ.get("CUBR_PUBLISH_WRITE_TEST", "")
    interrupted = False
    while offset < len(publication_marker_bytes):
        try:
            if injected == "eintr" and not interrupted:
                interrupted = True
                raise InterruptedError
            chunk = publication_marker_bytes[offset:]
            if injected == "short":
                chunk = chunk[:3]
            if injected == "zero":
                written = 0
            else:
                written = os.write(fd, chunk)
        except InterruptedError:
            continue
        if written <= 0:
            raise SystemExit("publication marker checked write made no progress")
        offset += written
def read_regular_bytes(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe publication marker: {path}")
        chunks = []
        while True:
            try:
                chunk = os.read(fd, 1024 * 1024)
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)
def publication_marker_bytes(final_path):
    return (f"schema=current-profile-g5-publication-v1\nstatus={status}\n"
            f"selection=NO-SELECT\nsource_commit={source_commit}\n"
            f"instrument_commit={instrument_commit}\nmap_seal_sha256={map_seal_sha256}\n"
            f"final_path={final_path.absolute()}\ncompleted_at={completed}\n").encode()
def authenticate_marker(path, expected):
    if read_regular_bytes(path) != expected:
        raise SystemExit("marker payload authentication failed")
def authenticate_manifest(root):
    manifest = root / "evidence-sha256.tsv"
    listed = {}
    for line in read_regular_bytes(manifest).decode("utf-8").splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3:
            raise SystemExit("published manifest record is malformed")
        digest, size_text, relative = fields
        relative_path = pathlib.PurePosixPath(relative)
        if (not relative or relative_path.is_absolute() or ".." in relative_path.parts or
                relative in listed or len(digest) != 64 or not size_text.isdigit()):
            raise SystemExit("published manifest record is unsafe")
        listed[relative] = (digest, int(size_text))
    actual = set()
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise SystemExit(f"unsafe published node: {path}")
        if info.st_mode & 0o222:
            raise SystemExit(f"published node remains writable: {path}")
        if stat.S_ISREG(info.st_mode) and path.name not in {
                "evidence-sha256.tsv", "TIMING-DONE.STAMP", "REJECTED-TIMING-DONE.STAMP"}:
            relative = path.relative_to(root).as_posix()
            actual.add(relative)
            data = read_regular_bytes(path)
            if listed.get(relative) != (hashlib.sha256(data).hexdigest(), len(data)):
                raise SystemExit(f"published manifest content mismatch: {relative}")
    if actual != set(listed):
        raise SystemExit("published manifest file set mismatch")
def reject_cgroup(message):
    print(message, file=sys.stderr)
    raise SystemExit(125)
def precommit_cgroup_guard():
    if cgroup_procs is None:
        return
    fixture = os.environ.get("CUBR_PUBLISH_CGROUP_TEST", "")
    if fixture:
        if (fixture not in {"connected", "disconnected"} or
                completed != "1970-01-01T00:00:00Z" or
                str(cgroup_procs).startswith("/sys/fs/cgroup/")):
            reject_cgroup("unsafe publication cgroup fixture request")
        fixture_pids = sorted(baseline_pids | {os.getppid(), os.getpid()})
        fixture_fd = os.open(cgroup_procs, os.O_WRONLY | os.O_TRUNC |
                             getattr(os, "O_NOFOLLOW", 0))
        try:
            write_all(fixture_fd, ("".join(f"{pid}\n" for pid in fixture_pids)).encode())
            os.fsync(fixture_fd)
        finally:
            os.close(fixture_fd)
    if cgroup_procs.is_symlink() or not cgroup_procs.is_file():
        reject_cgroup("bound cgroup.procs became unsafe before final commit")
    if not baseline_pids:
        reject_cgroup("frozen cgroup baseline is empty before final commit")
    current_pids = set()
    for line in cgroup_procs.read_text().splitlines():
        if not line.isdigit() or int(line) <= 0 or int(line) in current_pids:
            reject_cgroup("bound cgroup.procs is malformed before final commit")
        current_pids.add(int(line))
    current = os.getpid()
    ancestry = set()
    reached_baseline = []
    while True:
        if current <= 1:
            reject_cgroup("publisher ancestry reached PID1 before frozen cgroup baseline")
        if current in ancestry:
            reject_cgroup("publisher ancestry cycle before frozen cgroup baseline")
        if current not in current_pids:
            reject_cgroup("publisher ancestry escaped bound cgroup before frozen baseline")
        ancestry.add(current)
        if current in baseline_pids:
            reached_baseline.append(current)
            break
        status_path = pathlib.Path("/proc") / str(current) / "status"
        parent = None
        try:
            status_lines = status_path.read_text().splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            reject_cgroup("publisher ancestry became unreadable before frozen cgroup baseline")
        for line in status_lines:
            if line.startswith("PPid:"):
                fields = line.split()
                if len(fields) != 2 or not fields[1].isdigit():
                    reject_cgroup("publisher ancestry has malformed parent before frozen baseline")
                parent = int(fields[1])
                break
        if parent is None:
            reject_cgroup("publisher ancestry lacks parent before frozen cgroup baseline")
        if parent <= 1:
            reject_cgroup("publisher ancestry reached PID1 before frozen cgroup baseline")
        if parent == current or parent in ancestry:
            reject_cgroup("publisher ancestry cycle before frozen cgroup baseline")
        current = parent
    if len(reached_baseline) != 1 or len(ancestry & baseline_pids) != 1:
        reject_cgroup("publisher ancestry did not reach exactly one frozen cgroup baseline PID")
    allowed = baseline_pids | ancestry
    if os.getpid() not in current_pids or current_pids - allowed:
        reject_cgroup("new cgroup PID exists immediately before final commit")
require_before(commit_deadline_ns, "publication preparation")
if not source_path.is_dir() or source_path.is_symlink():
    raise SystemExit("unsafe publish source")
for candidate in (publishing_path, destination_path, late_path):
    if candidate.exists() or candidate.is_symlink():
        raise SystemExit(f"publish destination exists: {candidate}")
if (source_path / "TIMING-DONE.STAMP").exists():
    raise SystemExit("partial tree contains authoritative completion marker")
pending = source_path / ".TIMING-DONE.STAMP.pending"
payload = publication_marker_bytes(destination_path)
fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
try:
    write_all(fd, payload)
    os.fsync(fd)
finally:
    os.close(fd)
authenticate_marker(pending, payload)
crash("pending-written")
for root, dirs, files in os.walk(source_path, topdown=False, followlinks=False):
    root_path = pathlib.Path(root)
    for name in files:
        path = root_path / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"nonregular publish artifact: {path}")
        file_fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.chmod(path, info.st_mode & ~0o222, follow_symlinks=False)
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
    for name in dirs:
        path = root_path / name
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"unsafe publish directory: {path}")
        os.chmod(path, info.st_mode & ~0o222, follow_symlinks=False)
        directory_fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
source_fd = os.open(source_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(source_fd)
finally:
    os.close(source_fd)
crash("tree-fsynced")
AT_FDCWD = -100
RENAME_NOREPLACE = 1
libc = ctypes.CDLL(None, use_errno=True)
renameat2 = libc.renameat2
renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
renameat2.restype = ctypes.c_int
def rename_noreplace(source, destination):
    if renameat2(AT_FDCWD, os.fsencode(source), AT_FDCWD, os.fsencode(destination), RENAME_NOREPLACE) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)
def fsync_parent(path):
    parent_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
rename_noreplace(source_path, publishing_path)
fsync_parent(publishing_path)
crash("publishing-renamed")
pending_publishing = publishing_path / pending.name
marker = publishing_path / "TIMING-DONE.STAMP"
rename_noreplace(pending_publishing, marker)
authenticate_marker(marker, payload)
os.chmod(publishing_path, publishing_path.stat().st_mode & ~0o222)
publishing_fd = os.open(publishing_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(publishing_fd)
finally:
    os.close(publishing_fd)
crash("marker-renamed")
if crash_at in {"tamper-marker", "tamper-content"}:
    tamper_path = marker if crash_at == "tamper-marker" else publishing_path / "payload.txt"
    tamper_data = bytearray(read_regular_bytes(tamper_path))
    if not tamper_data:
        raise SystemExit("tamper fixture is empty")
    tamper_data[0] ^= 1
    os.chmod(tamper_path, 0o644)
    tamper_fd = os.open(tamper_path, os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.lseek(tamper_fd, 0, os.SEEK_SET)
        write_all(tamper_fd, bytes(tamper_data))
        os.fsync(tamper_fd)
    finally:
        os.close(tamper_fd)
    os.chmod(tamper_path, 0o444)
    readonly_fd = os.open(tamper_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(readonly_fd)
    finally:
        os.close(readonly_fd)
if delay_before_final:
    time.sleep(delay_before_final)
require_before(commit_deadline_ns, "final rename acceptance")
authenticate_marker(marker, payload)
authenticate_manifest(publishing_path)
precommit_cgroup_guard()
rename_noreplace(publishing_path, destination_path)
fsync_parent(destination_path)
marker = destination_path / "TIMING-DONE.STAMP"
if crash_at == "delay-after-final":
    time.sleep(max(0.0, (hard_deadline_ns - monotonic_ns()) / 1_000_000_000) + 0.1)
if monotonic_ns() >= hard_deadline_ns:
    rename_noreplace(destination_path, late_path)
    fsync_parent(late_path)
    os.chmod(late_path, late_path.stat().st_mode | stat.S_IWUSR)
    late_marker = late_path / "TIMING-DONE.STAMP"
    authenticate_marker(late_marker, payload)
    rejected_marker = late_path / "REJECTED-TIMING-DONE.STAMP"
    rename_noreplace(late_marker, rejected_marker)
    authenticate_marker(rejected_marker, payload)
    rejected_fd = os.open(rejected_marker, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(rejected_fd)
    finally:
        os.close(rejected_fd)
    os.chmod(late_path, late_path.stat().st_mode & ~0o222)
    late_fd = os.open(late_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(late_fd)
    finally:
        os.close(late_fd)
    fsync_parent(late_path)
    raise SystemExit("late final quarantined")
crash("final-renamed")
parent_fd = os.open(destination_path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(parent_fd)
finally:
    os.close(parent_fd)
destination_fd = os.open(destination_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(destination_fd)
finally:
    os.close(destination_fd)
if not marker.is_file() or not (destination_path / "evidence-sha256.tsv").is_file():
    raise SystemExit("published tree lacks marker or manifest")
authenticate_marker(marker, payload)
authenticate_manifest(destination_path)
PY
    then
        return 0
    else
        local publish_rc=$?
        if (( publish_rc == 125 )); then
            request_bound_unit_stop || true
        fi
        return "$publish_rc"
    fi
}

reject_and_freeze_tree() {
    local source=$1 target=$2 expected_final=$3 reason=$4
    /usr/bin/python3 - "$source" "$target" "$expected_final" "$CAMPAIGN_STATUS" \
        "$CODE_COMMIT" "$INSTRUMENT_COMMIT" "${MAP_SEAL_SHA256:-NO-MAP-SEAL}" "$(now)" \
        "${CURRENT_CELL:-none}" "$reason" "${FAILURE_COMMAND:-none}" <<'PY'
import ctypes, os, pathlib, stat, sys
source, target, expected_final = map(pathlib.Path, sys.argv[1:4])
status, source_commit, instrument_commit, seal, failed_at, cell, reason, command = sys.argv[4:12]
if not source.is_dir() or source.is_symlink():
    raise SystemExit("unsafe rejection source")
if source != target and (target.exists() or target.is_symlink()):
    raise SystemExit("rejection destination already exists")
AT_FDCWD = -100
RENAME_NOREPLACE = 1
libc = ctypes.CDLL(None, use_errno=True)
renameat2 = libc.renameat2
renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
renameat2.restype = ctypes.c_int
def rename_noreplace(old, new):
    if renameat2(AT_FDCWD, os.fsencode(old), AT_FDCWD, os.fsencode(new), RENAME_NOREPLACE) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), new)
def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
def fsync_parent(path):
    fsync_dir(path.parent)
def write_all(fd, payload):
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        if written <= 0:
            raise SystemExit("rejection marker checked write made no progress")
        offset += written
def read_regular(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe rejection marker: {path}")
        chunks = []
        while True:
            try:
                chunk = os.read(fd, 1024 * 1024)
            except InterruptedError:
                continue
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(fd)
def expected_publication_payload(payload):
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise SystemExit("publication marker is not UTF-8") from error
    completed = [line.removeprefix("completed_at=") for line in lines
                 if line.startswith("completed_at=")]
    if len(completed) != 1 or not completed[0]:
        raise SystemExit("publication marker completion field is malformed")
    return (f"schema=current-profile-g5-publication-v1\nstatus={status}\n"
            f"selection=NO-SELECT\nsource_commit={source_commit}\n"
            f"instrument_commit={instrument_commit}\nmap_seal_sha256={seal}\n"
            f"final_path={expected_final.absolute()}\ncompleted_at={completed[0]}\n").encode()
if source != target:
    rename_noreplace(source, target)
    fsync_parent(target)
os.chmod(target, target.stat().st_mode | stat.S_IWUSR)
authoritative = target / "TIMING-DONE.STAMP"
rejected = target / "REJECTED-TIMING-DONE.STAMP"
marker = authoritative if authoritative.exists() else rejected if rejected.exists() else None
if marker is not None:
    payload = read_regular(marker)
    if payload != expected_publication_payload(payload):
        raise SystemExit("rejection publication marker authentication failed")
    if marker == authoritative:
        rename_noreplace(authoritative, rejected)
        marker = rejected
    if read_regular(marker) != payload:
        raise SystemExit("rejection marker readback mismatch")
pending = target / ".TIMING-DONE.STAMP.pending"
if pending.exists() or pending.is_symlink():
    info = pending.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SystemExit("unsafe pending publication marker")
    pending.unlink()
sanitize = lambda value: value.replace("\n", " ").replace("\r", " ").replace("\t", " ")
failure_payload = (f"status=VOID\nfailed_at={sanitize(failed_at)}\ncell={sanitize(cell)}\n"
                   f"reason={sanitize(reason)}\ncommand={sanitize(command)}\n").encode()
failure = target / "FAILED.STAMP"
failure_fd = os.open(failure, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o444)
try:
    write_all(failure_fd, failure_payload)
    os.fsync(failure_fd)
finally:
    os.close(failure_fd)
if read_regular(failure) != failure_payload:
    raise SystemExit("failure marker readback mismatch")
for root, dirs, files in os.walk(target, topdown=False, followlinks=False):
    root_path = pathlib.Path(root)
    for name in files:
        path = root_path / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"unsafe rejection file: {path}")
        os.chmod(path, info.st_mode & ~0o222, follow_symlinks=False)
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    for name in dirs:
        path = root_path / name
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"unsafe rejection directory: {path}")
        os.chmod(path, info.st_mode & ~0o222, follow_symlinks=False)
        fsync_dir(path)
os.chmod(target, target.stat().st_mode & ~0o222)
fsync_dir(target)
fsync_parent(target)
PY
}

freeze_failed_tree() {
    local tree=$1 reason=$2
    [[ -d $tree && ! -L $tree ]] || return 0
    reject_and_freeze_tree "$tree" "$tree" "$OUT" "$reason"
}

quarantine_late_final() {
    local reason=${1:-late final quarantined}
    [[ -d $OUT && ! -L $OUT ]] || return 0
    [[ ! -e $LATE && ! -L $LATE ]] || return 1
    reject_and_freeze_tree "$OUT" "$LATE" "$OUT" "$reason"
    printf 'late final quarantined\n' >&2
}

finalize_worker() {
    local source=$2 publishing=$3 destination=$4 late=$5 hard_deadline_ns=$6 completed=$7
    CAMPAIGN_STATUS=$8
    [[ $9 == "$INSTRUMENT_COMMIT" ]] || die 'terminal worker instrument identity mismatch'
    CGROUP_PROCS=${10:-}
    CGROUP_BASELINE_PIDS=${11:-}
    [[ -n $CGROUP_PROCS && -n $CGROUP_BASELINE_PIDS ]] ||
        [[ $completed == 1970-01-01T00:00:00Z ]] || die 'terminal worker cgroup identity is missing'
    write_manifests "$source"
    publish_campaign "$source" "$publishing" "$destination" "$late" "$completed" \
        "$hard_deadline_ns" "${12:-}" "${13:-0}"
}

run_terminal_finalization() {
    local now_ns remaining rc
    now_ns=$(monotonic_ns)
    (( now_ns < HARD_DEADLINE_MONOTONIC_NS - PUBLICATION_COMMIT_MARGIN_SECONDS * 1000000000 )) ||
        die 'hard deadline cannot admit terminal finalization'
    remaining=$(( (HARD_DEADLINE_MONOTONIC_NS - now_ns) / 1000000000 ))
    (( remaining > 0 )) || die 'hard deadline exhausted before terminal finalization'
    if run_process_group_bounded "$remaining" /usr/bin/bash "${BASH_SOURCE[0]}" \
        --finalize-worker "$PARTIAL" "$PUBLISHING" "$OUT" "$LATE" \
        "$HARD_DEADLINE_MONOTONIC_NS" "$(now)" "$CAMPAIGN_STATUS" "$INSTRUMENT_COMMIT" \
        "$CGROUP_PROCS" "$CGROUP_BASELINE_PIDS"; then
        rc=0
    else
        rc=$?
    fi
    now_ns=$(monotonic_ns)
    if (( rc != 0 || now_ns >= HARD_DEADLINE_MONOTONIC_NS )) ||
       [[ ! -f $OUT/TIMING-DONE.STAMP || ! -f $OUT/evidence-sha256.tsv ]]; then
        FAILURE_REASON="terminal finalization rejected rc=$rc"
        quarantine_late_final "$FAILURE_REASON" || true
        return 1
    fi
}

on_exit() {
    local rc=$?
    set +e
    restore_suite_side_effects >/dev/null 2>&1
    if [[ -d $PARTIAL/cargo-test-target && ! -L $PARTIAL/cargo-test-target ]]; then
        /usr/bin/find "$PARTIAL/cargo-test-target" -xdev -depth -delete >/dev/null 2>&1
    fi
    /usr/bin/git -C "$CODE_DIR" clean -fX -- "$GENERATED_CARGO_LOCK" >/dev/null 2>&1
    if (( rc != 0 )); then
        quarantine_late_final "${FAILURE_REASON:-unclassified failure rc=$rc}" >/dev/null 2>&1 || true
        freeze_failed_tree "$PUBLISHING" "${FAILURE_REASON:-unclassified failure rc=$rc}"
        freeze_failed_tree "$PARTIAL" "${FAILURE_REASON:-unclassified failure rc=$rc}"
    fi
    return "$rc"
}

self_test_fail() {
    printf 'current_profile_g5_self_test=FAIL reason=%s\n' "$1"
    exit 1
}

self_test_mode_roots() {
    [[ $RUN_MODE == admission && -n $ROOT_PREFIX ]] || {
        printf 'current_profile_g5_mode_root_test=FAIL unsafe-mode\n'
        exit 1
    }
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    /usr/bin/printf 'mode=admission\nperformance_sample=NO\n' |
        write_new_stdin "$PARTIAL/MODE-ROOT.PASS"
    /usr/bin/chmod 0555 -- "$PARTIAL"
    /usr/bin/mv -T --no-clobber -- "$PARTIAL" "$OUT"
    printf 'current_profile_g5_mode_root_test=PASS\n'
}

self_test_snapshot_launch_inputs() {
    (( $# == 3 )) || die 'snapshot launch self-test requires two sources and one target directory'
    PREFLIGHT_DIR=$3
    snapshot_launch_inputs "$1" "$2" \
        "$PREFLIGHT_DIR/launch-preregistration.snapshot.md" \
        "$PREFLIGHT_DIR/launch-identities.snapshot.env"
    printf 'current_profile_g5_launch_snapshot_test=PASS\n'
}

verify_launch_identity_files() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import os, re, stat, sys

def read_regular_text(path, byte_limit, row_limit, label):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise SystemExit(f"unsafe {label}: {error.strerror}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe {label}: not a single-link regular file")
        if info.st_size > byte_limit:
            raise SystemExit("launch identity input exceeds size bound")
        chunks, total = [], 0
        while True:
            try:
                chunk = os.read(fd, min(65536, byte_limit + 1 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > byte_limit:
                raise SystemExit("launch identity input exceeds size bound")
    finally:
        os.close(fd)
    try:
        text = b"".join(chunks).decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SystemExit("launch identity input is not exact UTF-8") from error
    if len(text.splitlines()) > row_limit:
        raise SystemExit("launch identity input exceeds row bound")
    return text

prereg, identity = sys.argv[1:]
begin = "<!-- g5-protected-launch-identities-v1-begin -->\n"
end = "<!-- g5-protected-launch-identities-v1-end -->"
text = read_regular_text(prereg, 1_048_576, 16_384, "launch preregistration")
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit("launch identity markers must occur exactly once")
block = text.split(begin, 1)[1].split(end, 1)[0]
canonical = read_regular_text(identity, 65_536, 59, "launch identity file")
if block != canonical:
    raise SystemExit("preregistration block and identity file differ")
keys = (
    "schema original_prereg_blob g4_terminal_journal_sha256 g4_terminal_journal_bytes "
    "g4_failure_manifest_sha256 g4_failure_manifest_bytes g4_capability_probe_count "
    "g4_perf_data_count g4_campaign_cell_count g4_campaign_sample_row_count g4_terminal_gate "
    "g4_verdict instrument_resulting_main instrument_tree runner_blob runner_sha256 "
    "runner_test_blob runner_test_sha256 mapper_blob mapper_sha256 mapper_test_blob "
    "mapper_test_sha256 source_commit source_tree cubrim_rs_tree cargo_inputs_manifest_sha256 "
    "generated_cargo_lock_sha256 rustc_commit rustc_version cargo_version release_flags "
    "binary_sha256 binary_build_id binary_size binary_device binary_inode mapping_schema_sha256 "
    "corpus_manifest_sha256 corpus_rows_sha256 map_stream_sha256 map_manifest_sha256 "
    "map_summary_sha256 map_row_count map_part_count map_seal_sha256 "
    "sanitized_allowlist_contract_sha256 runner_contract_test_sha256 runner_contract_test_bytes "
    "live_fixture_result_sha256 live_fixture_result_bytes live_fixture_test_output_sha256 "
    "live_fixture_test_output_bytes performance_sample campaign_cells retained_perf_data "
    "campaign_sample_rows selection admission_identity_set_sha256 admission_identity_set_bytes"
).split()
lines = canonical.splitlines()
if len(lines) != len(keys):
    raise SystemExit(f"launch identity key count mismatch: {len(lines)}")
parsed = {}
for expected, line in zip(keys, lines):
    key, sep, value = line.partition("=")
    if not sep or key != expected or key in parsed or not value:
        raise SystemExit(f"invalid or reordered launch identity: {line!r}")
    if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
        raise SystemExit(f"control or non-ASCII value: {key}")
    parsed[key] = value
hex40 = {k for k in keys if k.endswith(("_blob", "_tree", "_commit", "_main"))}
hex64 = {k for k in keys if k.endswith("_sha256")}
integers = {k for k in keys if k.endswith(("_bytes", "_count", "_size", "_device", "_inode"))}
hex40.add("binary_build_id")
for key in hex40:
    if not re.fullmatch(r"[0-9a-f]{40}", parsed[key]):
        raise SystemExit(f"invalid Git identity: {key}")
for key in hex64:
    if not re.fullmatch(r"[0-9a-f]{64}", parsed[key]):
        raise SystemExit(f"invalid SHA-256 identity: {key}")
for key in integers:
    if not re.fullmatch(r"0|[1-9][0-9]*", parsed[key]):
        raise SystemExit(f"invalid integer identity: {key}")
required_literals = {
    "schema": "g5-protected-launch-identities-v1",
    "original_prereg_blob": "5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f",
    "g4_capability_probe_count": "9", "g4_perf_data_count": "0",
    "g4_campaign_cell_count": "0", "g4_campaign_sample_row_count": "0",
    "g4_terminal_gate": "admission-runner-contract", "g4_verdict": "VOID-NO-SELECT",
    "source_commit": "830a9a31deb00926a97f3fa5bd74f58003573fc0",
    "performance_sample": "NO", "campaign_cells": "0", "retained_perf_data": "0",
    "campaign_sample_rows": "0", "selection": "NO-SELECT",
}
for key, expected in required_literals.items():
    if parsed[key] != expected:
        raise SystemExit(f"fixed launch identity mismatch: {key}")
print(f"current_profile_g5_launch_identity_parser=PASS schema={parsed['schema']} keys={len(keys)}")
PY
}

persist_authenticated_admission_identity() {
    local source=${CUBR_ADMISSION_IDENTITY_SET:?missing admission identity path}
    local expected_sha=${CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256:?missing admission identity SHA}
    local expected_bytes=${CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES:?missing admission identity bytes}
    local target=$PREFLIGHT_DIR/admission-sealed-identity-set.env
    [[ $expected_sha =~ ^[0-9a-f]{64}$ && $expected_bytes =~ ^(0|[1-9][0-9]*)$ ]] ||
        die 'invalid sealed admission identity expectation'
    [[ -f $source && ! -L $source ]] || die 'unsafe sealed admission identity source'
    [[ $(run_bounded 30 /usr/bin/sha256sum -- "$source" | /usr/bin/awk '{print $1}') == "$expected_sha" ]] ||
        die 'sealed admission identity SHA mismatch'
    [[ $(run_bounded 30 /usr/bin/stat -c %s -- "$source") == "$expected_bytes" ]] ||
        die 'sealed admission identity byte mismatch'
    write_new_checked "$target" "$source"
    [[ $(run_bounded 30 /usr/bin/sha256sum -- "$target" | /usr/bin/awk '{print $1}') == "$expected_sha" ]] ||
        die 'persisted admission identity SHA mismatch'
    [[ $(run_bounded 30 /usr/bin/stat -c %s -- "$target") == "$expected_bytes" ]] ||
        die 'persisted admission identity byte mismatch'
}

launch_identity_value() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import os, stat, sys
path, wanted = sys.argv[1:]
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
try:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65_536:
        raise SystemExit("unsafe launch identity value source")
    chunks, total = [], 0
    while True:
        try:
            chunk = os.read(fd, min(65536, 65_537 - total))
        except InterruptedError:
            continue
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > 65_536:
            raise SystemExit("launch identity value source exceeds size bound")
    payload = b"".join(chunks)
finally:
    os.close(fd)
try:
    lines = payload.decode("utf-8", errors="strict").splitlines()
except UnicodeDecodeError as error:
    raise SystemExit("launch identity value source is not exact UTF-8") from error
values = [line.partition("=")[2] for line in lines if line.partition("=")[0] == wanted]
if len(values) != 1 or not values[0]:
    raise SystemExit(f"launch identity value cardinality mismatch: {wanted}")
print(values[0])
PY
}

snapshot_launch_inputs() {
    local caller_prereg=$1 caller_identities=$2 snapshot_prereg=$3 snapshot_identities=$4
    [[ -f $caller_prereg && ! -L $caller_prereg &&
       -f $caller_identities && ! -L $caller_identities ]] ||
        die 'unsafe launch snapshot source'
    [[ -d $PREFLIGHT_DIR && ! -L $PREFLIGHT_DIR &&
       $(/usr/bin/stat -c %a -- "$PREFLIGHT_DIR") == 700 ]] ||
        die 'launch snapshot directory is not private'
    [[ $(/usr/bin/dirname -- "$snapshot_prereg") == "$PREFLIGHT_DIR" &&
       $(/usr/bin/dirname -- "$snapshot_identities") == "$PREFLIGHT_DIR" ]] ||
        die 'launch snapshot target escaped preflight directory'
    write_new_checked "$snapshot_prereg" "$caller_prereg"
    write_new_checked "$snapshot_identities" "$caller_identities"
}

parse_remote_main_output() {
    local expected=$1 output=$2 pattern remote_main
    pattern=$'^([0-9a-f]{40})\trefs/heads/main$'
    [[ $expected =~ ^[0-9a-f]{40}$ ]] || die 'expected launch main is malformed'
    [[ $output =~ $pattern ]] || die 'remote main response is malformed or ambiguous'
    remote_main=${BASH_REMATCH[1]}
    [[ $remote_main == "$expected" ]] || die 'launch main does not equal fresh remote main'
    printf '%s\n' "$remote_main"
}

verify_launch_main_matches_remote() {
    local repo=$1 expected=$2 timeout_seconds=$3 remote_output
    [[ -d $repo && ! -L $repo && $timeout_seconds =~ ^[1-9][0-9]*$ && $timeout_seconds -le 30 ]] ||
        die 'remote main query inputs are unsafe'
    if ! remote_output=$(run_bounded "$timeout_seconds" /usr/bin/git -C "$repo" ls-remote --exit-code origin refs/heads/main); then
        die 'fresh remote main query failed'
    fi
    parse_remote_main_output "$expected" "$remote_output" >/dev/null
}

self_test_verify_remote_main() {
    (( $# == 3 )) || die 'remote main self-test requires repository, expected commit, and timeout'
    local now_ns
    now_ns=$(monotonic_ns)
    HARD_DEADLINE_MONOTONIC_NS=$((now_ns + 60 * 1000000000))
    WORK_DEADLINE_MONOTONIC_NS=$HARD_DEADLINE_MONOTONIC_NS
    verify_launch_main_matches_remote "$1" "$2" "$3"
    printf 'current_profile_g5_remote_main_test=PASS remote_main=%s\n' "$2"
}

authenticate_campaign_launch_inputs() {
    local parser_output actual_prereg_blob actual_identities_blob
    local snapshot_prereg=$PREFLIGHT_DIR/launch-preregistration.snapshot.md
    local snapshot_identities=$PREFLIGHT_DIR/launch-identities.snapshot.env
    [[ $CUBR_LAUNCH_MAIN =~ ^[0-9a-f]{40}$ && $CUBR_EXPECTED_PREREG_BLOB =~ ^[0-9a-f]{40}$ &&
       $CUBR_EXPECTED_IDENTITIES_BLOB =~ ^[0-9a-f]{40}$ ]] || die 'invalid launch Git identity'
    snapshot_launch_inputs "$CUBR_LAUNCH_PREREG" "$CUBR_LAUNCH_IDENTITIES" \
        "$snapshot_prereg" "$snapshot_identities"
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" merge-base --is-ancestor \
        "$INSTRUMENT_COMMIT" "$CUBR_LAUNCH_MAIN" || die 'instrument is not ancestor of launch main'
    verify_launch_main_matches_remote "$INSTRUMENT_REPO" "$CUBR_LAUNCH_MAIN" 30
    actual_prereg_blob=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$CUBR_LAUNCH_MAIN:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md")
    actual_identities_blob=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$CUBR_LAUNCH_MAIN:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env")
    [[ $actual_prereg_blob == "$CUBR_EXPECTED_PREREG_BLOB" ]] ||
        die 'launch-main preregistration blob mismatch'
    [[ $actual_identities_blob == "$CUBR_EXPECTED_IDENTITIES_BLOB" ]] ||
        die 'launch-main identity blob mismatch'
    parser_output=$(run_bounded 30 /usr/bin/bash "${BASH_SOURCE[0]}" \
        --verify-launch-identity-files "$snapshot_prereg" "$snapshot_identities")
    [[ $parser_output == 'current_profile_g5_launch_identity_parser=PASS schema=g5-protected-launch-identities-v1 keys=59' ]] ||
        die 'protected launch identity parser output mismatch'
    [[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_prereg") == "$CUBR_EXPECTED_PREREG_BLOB" ]] ||
        die 'launch preregistration blob mismatch'
    [[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_identities") == "$CUBR_EXPECTED_IDENTITIES_BLOB" ]] ||
        die 'launch identity blob mismatch'
    [[ $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value \
        "$snapshot_identities" instrument_resulting_main) == "$INSTRUMENT_COMMIT" ]] ||
        die 'launch instrument commit mismatch'
    [[ $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" runner_sha256) == "$EXPECTED_RUNNER_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" runner_test_sha256) == "$EXPECTED_TEST_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" mapper_sha256) == "$EXPECTED_MAPPER_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" mapper_test_sha256) == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'launch runtime asset identity mismatch'
    [[ $(run_bounded 30 /usr/bin/sha256sum -- "${BASH_SOURCE[0]}" | /usr/bin/awk '{print $1}') == "$EXPECTED_RUNNER_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$RUNNER_TEST_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_TEST_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$MAPPER_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$MAPPER_TEST_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'installed runtime asset identity mismatch'
    [[ $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" admission_identity_set_sha256) == "$CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" admission_identity_set_bytes) == "$CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES" ]] ||
        die 'launch admission identity expectation mismatch'
    printf '%s\n' "$parser_output" | write_new_stdin "$PREFLIGHT_DIR/launch-identity-parser.txt"
    persist_authenticated_admission_identity
}

capture_g5_identity_inputs() {
/root/.cargo/bin/rustc -vV | write_new_stdin "$PREFLIGHT_DIR/rustc-version.txt"
/root/.cargo/bin/cargo -V | write_new_stdin "$PREFLIGHT_DIR/cargo-version.txt"
/usr/bin/find "$CODE_DIR/code/cubrim-rs" -xdev -type f \
  \( -name Cargo.toml -o -name Cargo.lock -o -name build.rs -o -name '*.rs' \) \
  -print0 | LC_ALL=C /usr/bin/sort -z | /usr/bin/xargs -0 /usr/bin/sha256sum \
  | write_new_stdin "$PREFLIGHT_DIR/cargo-inputs-manifest.tsv"
/usr/bin/python3 - "$PREFLIGHT_DIR/rustc-version.txt" \
  "$PREFLIGHT_DIR/cargo-version.txt" <<'PY' | write_new_stdin "$PREFLIGHT_DIR/map-toolchain.json"
import json, pathlib, sys
rustc, cargo = map(pathlib.Path, sys.argv[1:])
value = {"cargo": cargo.read_text().strip(), "release_debug": "1",
         "rustc": rustc.read_text().strip(), "taskset": "0-15", "threads": 4}
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
PY
{
  printf 'schema=g5-sanitized-environment-contract-v1\n'
  printf 'pure_mock=LC_ALL,PATH,CUBR_SYSTEMD_UNIT\n'
  printf 'outer_user_systemd=LC_ALL,PATH,HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS\n'
  printf 'service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS\n'
  printf 'child_boundary=env-i\n'
} | write_new_stdin "$PREFLIGHT_DIR/sanitized-environment-contract.txt"
}

admission_tree_schema() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import hashlib, json, os, re, stat, sys
from pathlib import Path, PurePosixPath

root, mode = Path(sys.argv[1]), sys.argv[2]
if mode not in {"emit", "verify"}:
    raise SystemExit("unknown admission tree schema mode")
if not root.is_dir() or root.is_symlink():
    raise SystemExit("unsafe admission tree root")

limit = 90_000_000
def read_regular(path, maximum=limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe admission file: {path.relative_to(root)}")
        if info.st_size > maximum:
            raise SystemExit(f"admission file exceeds size bound: {path.relative_to(root)}")
        chunks, total = [], 0
        while True:
            try:
                chunk = os.read(fd, min(1024 * 1024, maximum + 1 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise SystemExit(f"admission file exceeds size bound: {path.relative_to(root)}")
        return b"".join(chunks)
    finally:
        os.close(fd)

manifest_path = root / "map/map-parts-manifest.json"
try:
    map_manifest = json.loads(read_regular(manifest_path, 1_048_576).decode("utf-8", errors="strict"))
except (UnicodeDecodeError, json.JSONDecodeError) as error:
    raise SystemExit("invalid admission map manifest") from error
parts = map_manifest.get("parts")
if (not isinstance(parts, list) or not parts or map_manifest.get("part_count") != len(parts)):
    raise SystemExit("invalid admission map part schema")
part_names = []
for index, part in enumerate(parts):
    name = part.get("path") if isinstance(part, dict) else None
    if (not isinstance(name, str) or
            not re.fullmatch(r"g5-full-instruction-map\.part-[0-9]{5}\.tsv\.gz", name) or
            PurePosixPath(name).name != name or part.get("part_index") != index or
            name in part_names):
        raise SystemExit("invalid admission map part path")
    part_names.append(name)

expected_dirs = {
    "binary", "map", "preflight", "preflight/live-fixture",
    "preflight/mapper-test-runtime", "suites",
}
expected_files = {
    "address-smoke-feasibility.json", "address-smoke.binary-snapshot-after.tsv",
    "address-smoke.binary-snapshot-before.tsv", "address-smoke.out",
    "binary/admitted-snapshot.tsv", "binary/cubrim",
    "feasibility-1.cubr", "feasibility-2.cubr", "feasibility-decoded.bin",
    "feasibility-zero.bin",
    "map/elf-summary.json", "map/full-map-admission.txt", "map/full-map-resource.txt",
    "map/instruction-addresses.txt.gz", "map/map-admission-seal.json",
    "map/map-parts-manifest.json", "map/map-summary.json.gz",
    "map/map-worker.stderr.txt", "map/map-worker.stdout.txt", "map/objdump.txt.gz",
    "map/prefix-coverage-audit.tsv", "map/prefix-table.tsv",
    "map/raw-stream-evidence.tsv", "map/readelf-programs.txt", "map/readelf-sections.txt",
    "map/resolver-a.txt.gz", "map/resolver-b.txt.gz", "map/sections.tsv", "map/segments.tsv",
    "preflight/cargo-inputs-manifest.tsv", "preflight/cargo-version.txt",
    "preflight/cell-inputs.tsv", "preflight/identities.txt",
    "preflight/instrument-mapper-test.py", "preflight/instrument-mapper.py",
    "preflight/instrument-runner-test.sh", "preflight/instrument-runner.sh",
    "preflight/journal.tsv", "preflight/live-fixture/cgroup-live.tsv",
    "preflight/live-fixture/systemd-run.output.txt", "preflight/map-toolchain.json",
    "preflight/mapper-help.txt", "preflight/mapper-test-runtime/current_profile_g5_map.py",
    "preflight/mapper-test-runtime/test_current_profile_g5_map.py",
    "preflight/mapper-unit-test.txt", "preflight/perf-events.tsv",
    "preflight/process-conflicts.txt", "preflight/process-snapshot.txt",
    "preflight/runner-contract-test.txt", "preflight/rustc-version.txt",
    "preflight/sanitized-environment-contract.txt", "preflight/systemd-cgroup-baseline.pids",
    "preflight/systemd-contract.txt", "suites/binary-notes.txt",
    "suites/cargo-test-release.log", "suites/generated-Cargo.lock",
    "suites/scheme-roundtrip.log",
}
expected_files.update(f"map/{name}" for name in part_names)
events = ("task-clock", "cycles", "instructions", "branches", "branch-misses",
          "cache-references", "cache-misses", "dTLB-load-misses", "page-faults")
expected_files.update(f"preflight/perf-{event}.csv" for event in events)
tree_manifest = "preflight/admission-tree-manifest.tsv"
if mode == "verify":
    expected_files.add(tree_manifest)

actual_dirs, actual_files = set(), set()
for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
    base_path = Path(base)
    for name in dirs:
        path = base_path / name
        info = path.lstat()
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise SystemExit(f"unsafe admission node: {relative}")
        actual_dirs.add(relative)
    for name in files:
        path = base_path / name
        info = path.lstat()
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe admission node: {relative}")
        actual_files.add(relative)
if actual_dirs != expected_dirs:
    extra, missing = sorted(actual_dirs - expected_dirs), sorted(expected_dirs - actual_dirs)
    raise SystemExit(f"admission directory schema mismatch extra={extra} missing={missing}")
if actual_files != expected_files:
    extra, missing = sorted(actual_files - expected_files), sorted(expected_files - actual_files)
    raise SystemExit(f"admission file schema mismatch extra={extra} missing={missing}")

forbidden = re.compile(
    rb"(?:^|[\t ,{])(performance_sample|campaign_sample_rows|campaign_cells|selection|cell)="
    rb"(?:YES|[1-9][0-9]*|VALID|SUPPORTED)", re.MULTILINE)
for relative in (
        "preflight/journal.tsv", "preflight/identities.txt", "preflight/runner-contract-test.txt",
        "preflight/cell-inputs.tsv", "map/full-map-admission.txt", "map/raw-stream-evidence.tsv"):
    if forbidden.search(read_regular(root / relative, 8_388_608)):
        raise SystemExit(f"admission contains performance-like content: {relative}")

try:
    address = json.loads(read_regular(root / "address-smoke-feasibility.json", 1_048_576)
                         .decode("utf-8", errors="strict"))
except (UnicodeDecodeError, json.JSONDecodeError) as error:
    raise SystemExit("invalid address-smoke admission schema") from error
address_keys = {
    "schema", "purpose", "performance_interpretation", "binary_identity", "binary_snapshot",
    "binary_sample_count", "binary_unresolved_sample_count", "binary_resolution_gate_pass",
    "lost_record_count", "conservation", "symbol_consulted",
}
if (not isinstance(address, dict) or set(address) != address_keys or
        address.get("schema") != "cubr-new24-g5-address-smoke-v1" or
        address.get("purpose") != "mechanical-address-join-feasibility-only" or
        address.get("performance_interpretation") != "FORBIDDEN"):
    raise SystemExit("invalid address-smoke admission schema")

cell_rows = read_regular(root / "preflight/cell-inputs.tsv", 65_536).decode("utf-8", errors="strict").splitlines()
if len(cell_rows) != 3 or any(len(row.split("\t")) != 4 for row in cell_rows):
    raise SystemExit("invalid admission corpus-row schema")
perf_rows = read_regular(root / "preflight/perf-events.tsv", 65_536).decode("utf-8", errors="strict").splitlines()
parsed_events = [row.split("\t") for row in perf_rows]
if (len(parsed_events) != len(events) or {row[0] for row in parsed_events if len(row) == 2} != set(events) or
        any(len(row) != 2 or row[1] not in {"supported", "unsupported"} for row in parsed_events)):
    raise SystemExit("invalid admission perf-capability schema")

rows = []
for relative in sorted(expected_files - {tree_manifest}):
    payload = read_regular(root / relative)
    rows.append(f"{hashlib.sha256(payload).hexdigest()}\t{len(payload)}\t{relative}\n")
expected_manifest = "".join(rows).encode()
if mode == "emit":
    sys.stdout.buffer.write(expected_manifest)
else:
    if read_regular(root / tree_manifest, 1_048_576) != expected_manifest:
        raise SystemExit("admission tree manifest mismatch")
PY
}

write_admission_tree_manifest() {
    local root=$1
    admission_tree_schema "$root" emit | write_new_stdin "$root/preflight/admission-tree-manifest.tsv"
}

assert_admission_has_no_performance() {
    local root=$1 perf_count address_raw_count cell_dir_count max_min_summary_count
    local attribution_count pstat_count prec_count cell_journal_count
    perf_count=$(/usr/bin/find "$root" -type f -name perf.data -printf '.\n' | /usr/bin/wc -l)
    address_raw_count=$(/usr/bin/find "$root" -type f \
        \( -name address-smoke.data -o -name address-smoke.perf-script.txt \
        -o -name address-smoke.buildid-list.txt \) -printf '.\n' | /usr/bin/wc -l)
    cell_dir_count=$(/usr/bin/find "$root" -type d \
        -path "$root/cells/silesia-*" -printf '.\n' | /usr/bin/wc -l)
    max_min_summary_count=$(/usr/bin/find "$root" -type f \
        \( -path '*/silesia-*-max/attribution-summary.json' -o \
        -path '*/silesia-*-min/attribution-summary.json' \) -printf '.\n' | /usr/bin/wc -l)
    attribution_count=$(/usr/bin/find "$root" -type f -name attribution-summary.json \
        -printf '.\n' | /usr/bin/wc -l)
    pstat_count=$(/usr/bin/find "$root" -type f -name 'pstat*.perf-stat.csv' \
        -printf '.\n' | /usr/bin/wc -l)
    prec_count=$(/usr/bin/find "$root" -type f \
        \( -name 'prec*.data' -o -name 'prec*.perf-script.txt' \
        -o -name 'prec*.buildid-list.txt' -o -name 'prec*.record.json' \
        -o -name 'prec*.time.txt' \) -printf '.\n' | /usr/bin/wc -l)
    cell_journal_count=$(/usr/bin/awk -F '\t' \
        '{ for (i=1; i<=NF; i++) if ($i ~ /^cell=/) count++ } END { print count+0 }' \
        "$JOURNAL")
    [[ $perf_count == 0 ]] || die 'admission retained perf.data'
    [[ $address_raw_count == 0 ]] || die 'admission retained address-smoke raw artifact'
    [[ $max_min_summary_count == 0 ]] || die 'admission contains max/min attribution summary'
    [[ $attribution_count == 0 ]] || die 'admission contains attribution summary'
    [[ $pstat_count == 0 ]] || die 'admission contains pstat artifact'
    [[ $prec_count == 0 ]] || die 'admission contains prec artifact'
    [[ $cell_dir_count == 0 ]] || die 'admission contains campaign cell directory'
    [[ $cell_journal_count == 0 ]] || die 'admission journal contains cell row'
    admission_tree_schema "$root" verify || die 'admission tree schema or manifest mismatch'
}

write_g5_admission_identity_set() {
    local root=$1 target=${2:-$1/sealed-identity-set.env}
    local instrument_tree source_tree cubrim_rs_tree runner_blob runner_test_blob
    local mapper_blob mapper_test_blob rustc_version cargo_version release_flags
    local binary_size binary_device binary_inode map_stream_sha map_manifest_sha
    local map_summary_sha map_row_count map_part_count map_seal_sha
    instrument_tree=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT^{tree}")
    source_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse 'HEAD^{tree}')
    cubrim_rs_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD:code/cubrim-rs)
    runner_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g5-run.sh")
    runner_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g5-run-test.sh")
    mapper_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current_profile_g5_map.py")
    mapper_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/test_current_profile_g5_map.py")
    rustc_version=$(/usr/bin/tr '\n' ';' <"$PREFLIGHT_DIR/rustc-version.txt")
    cargo_version=$(/usr/bin/tr '\n' ';' <"$PREFLIGHT_DIR/cargo-version.txt")
    release_flags='CARGO_PROFILE_RELEASE_DEBUG=1;debug_assertions=false;CUBR_THREADS=4;RAYON_NUM_THREADS=4;OMP_NUM_THREADS=4;MKL_NUM_THREADS=4;taskset=0-15'
    binary_size=$(/usr/bin/stat -c %s -- "$MEASURED_BINARY")
    binary_device=$(/usr/bin/stat -c %d -- "$MEASURED_BINARY")
    binary_inode=$(/usr/bin/stat -c %i -- "$MEASURED_BINARY")
    map_stream_sha=$(json_value "$root/map/map-parts-manifest.json" full_uncompressed_sha256)
    map_manifest_sha=$(sha "$root/map/map-parts-manifest.json")
    map_summary_sha=$(sha "$root/map/map-summary.json.gz")
    map_row_count=$(json_value "$root/map/map-parts-manifest.json" row_count)
    map_part_count=$(json_value "$root/map/map-parts-manifest.json" part_count)
    map_seal_sha=$(sha "$root/map/map-admission-seal.json")
    {
        printf 'schema=g5-admission-identity-set-v1\n'
        printf 'instrument_resulting_main=%s\n' "$INSTRUMENT_COMMIT"
        printf 'instrument_tree=%s\n' "$instrument_tree"
        printf 'runner_blob=%s\nrunner_sha256=%s\n' "$runner_blob" "$EXPECTED_RUNNER_SHA"
        printf 'runner_test_blob=%s\nrunner_test_sha256=%s\n' "$runner_test_blob" "$EXPECTED_TEST_SHA"
        printf 'mapper_blob=%s\nmapper_sha256=%s\n' "$mapper_blob" "$EXPECTED_MAPPER_SHA"
        printf 'mapper_test_blob=%s\nmapper_test_sha256=%s\n' "$mapper_test_blob" "$EXPECTED_MAPPER_TEST_SHA"
        printf 'source_commit=%s\nsource_tree=%s\ncubrim_rs_tree=%s\n' "$CODE_COMMIT" "$source_tree" "$cubrim_rs_tree"
        printf 'cargo_inputs_manifest_sha256=%s\n' "$(sha "$PREFLIGHT_DIR/cargo-inputs-manifest.tsv")"
        printf 'generated_cargo_lock_sha256=%s\n' "$(sha "$root/suites/generated-Cargo.lock")"
        printf 'rustc_commit=%s\nrustc_version=%s\ncargo_version=%s\nrelease_flags=%s\n' \
            "$EXPECTED_RUSTC_COMMIT" "$rustc_version" "$cargo_version" "$release_flags"
        printf 'binary_sha256=%s\nbinary_build_id=%s\nbinary_size=%s\nbinary_device=%s\nbinary_inode=%s\n' \
            "$(sha "$MEASURED_BINARY")" "$BINARY_BUILD_ID" "$binary_size" "$binary_device" "$binary_inode"
        printf 'mapping_schema_sha256=%s\n' "$MAPPING_SCHEMA_SHA256"
        printf 'corpus_manifest_sha256=%s\ncorpus_rows_sha256=%s\n' \
            "$(sha "$CORPUS_MANIFEST")" "$(sha "$PREFLIGHT_DIR/cell-inputs.tsv")"
        printf 'map_stream_sha256=%s\nmap_manifest_sha256=%s\nmap_summary_sha256=%s\n' \
            "$map_stream_sha" "$map_manifest_sha" "$map_summary_sha"
        printf 'map_row_count=%s\nmap_part_count=%s\nmap_seal_sha256=%s\n' \
            "$map_row_count" "$map_part_count" "$map_seal_sha"
        printf 'sanitized_allowlist_contract_sha256=%s\n' \
            "$(sha "$PREFLIGHT_DIR/sanitized-environment-contract.txt")"
        printf 'runner_contract_test_sha256=%s\nrunner_contract_test_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/runner-contract-test.txt")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/runner-contract-test.txt")"
        printf 'live_fixture_result_sha256=%s\nlive_fixture_result_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/live-fixture/cgroup-live.tsv")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/live-fixture/cgroup-live.tsv")"
        printf 'live_fixture_test_output_sha256=%s\nlive_fixture_test_output_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/live-fixture/systemd-run.output.txt")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/live-fixture/systemd-run.output.txt")"
        printf 'performance_sample=NO\ncampaign_cells=0\nretained_perf_data=0\ncampaign_sample_rows=0\nselection=NO-SELECT\n'
    } | write_new_stdin "$target"
    [[ $(/usr/bin/wc -l <"$target") == 46 ]] || die 'admission identity key count mismatch'
}

compare_g5_stable_identities() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import os, re, stat, sys

keys = (
    "schema instrument_resulting_main instrument_tree runner_blob runner_sha256 "
    "runner_test_blob runner_test_sha256 mapper_blob mapper_sha256 mapper_test_blob "
    "mapper_test_sha256 source_commit source_tree cubrim_rs_tree cargo_inputs_manifest_sha256 "
    "generated_cargo_lock_sha256 rustc_commit rustc_version cargo_version release_flags "
    "binary_sha256 binary_build_id binary_size binary_device binary_inode mapping_schema_sha256 "
    "corpus_manifest_sha256 corpus_rows_sha256 map_stream_sha256 map_manifest_sha256 "
    "map_summary_sha256 map_row_count map_part_count map_seal_sha256 "
    "sanitized_allowlist_contract_sha256 runner_contract_test_sha256 runner_contract_test_bytes "
    "live_fixture_result_sha256 live_fixture_result_bytes live_fixture_test_output_sha256 "
    "live_fixture_test_output_bytes performance_sample campaign_cells retained_perf_data "
    "campaign_sample_rows selection"
).split()
excluded = {
    # Re-copying the same authenticated binary changes filesystem placement only.
    "binary_device", "binary_inode",
    # The systemd fixture binds a fresh invocation/PID/cgroup and is intentionally run-volatile.
    "live_fixture_result_sha256", "live_fixture_result_bytes",
    "live_fixture_test_output_sha256", "live_fixture_test_output_bytes",
}
stable = [key for key in keys if key not in excluded]

def parse(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise SystemExit(f"unsafe stable identity file: {error.strerror}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65_536:
            raise SystemExit("unsafe stable identity file")
        chunks, total = [], 0
        while True:
            try:
                chunk = os.read(fd, min(65536, 65_537 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > 65_536:
                raise SystemExit("stable identity file exceeds size bound")
    finally:
        os.close(fd)
    try:
        lines = b"".join(chunks).decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise SystemExit("stable identity file is not exact UTF-8") from error
    if len(lines) != len(keys):
        raise SystemExit(f"stable identity key count mismatch: {len(lines)}")
    parsed = {}
    for expected, line in zip(keys, lines):
        key, separator, value = line.partition("=")
        if not separator or key != expected or key in parsed or not value:
            raise SystemExit(f"invalid or reordered stable identity: {line!r}")
        if any(ord(char) < 0x20 or ord(char) > 0x7e for char in value):
            raise SystemExit(f"control or non-ASCII stable identity: {key}")
        parsed[key] = value
    hex40 = {key for key in keys if key.endswith(("_blob", "_tree", "_commit", "_main"))}
    hex40.add("binary_build_id")
    hex64 = {key for key in keys if key.endswith("_sha256")}
    integers = {key for key in keys if key.endswith(("_bytes", "_count", "_size", "_device", "_inode"))}
    for key in hex40:
        if not re.fullmatch(r"[0-9a-f]{40}", parsed[key]):
            raise SystemExit(f"invalid Git stable identity: {key}")
    for key in hex64:
        if not re.fullmatch(r"[0-9a-f]{64}", parsed[key]):
            raise SystemExit(f"invalid SHA-256 stable identity: {key}")
    for key in integers:
        if not re.fullmatch(r"0|[1-9][0-9]*", parsed[key]):
            raise SystemExit(f"invalid integer stable identity: {key}")
    fixed = {
        "schema": "g5-admission-identity-set-v1", "performance_sample": "NO",
        "campaign_cells": "0", "retained_perf_data": "0", "campaign_sample_rows": "0",
        "selection": "NO-SELECT",
    }
    for key, expected in fixed.items():
        if parsed[key] != expected:
            raise SystemExit(f"fixed stable identity mismatch: {key}")
    return parsed

admitted, current = map(parse, sys.argv[1:])
for key in stable:
    if admitted[key] != current[key]:
        raise SystemExit(f"stable admission identity mismatch: {key}")
print(f"current_profile_g5_stable_identity_compare=PASS compared={len(stable)} excluded={len(excluded)}")
PY
}

self_test_admission_no_performance() {
    local fixture_root=$1
    [[ $fixture_root == /tmp/* && -d $fixture_root && ! -L $fixture_root ]] ||
        die 'unsafe admission no-performance fixture root'
    PREFLIGHT_DIR=$fixture_root/preflight
    JOURNAL=$PREFLIGHT_DIR/journal.tsv
    [[ -f $JOURNAL && ! -L $JOURNAL ]] || die 'unsafe admission fixture journal'
    assert_admission_has_no_performance "$fixture_root"
    printf 'current_profile_g5_admission_no_performance_test=PASS\n'
}

self_test_write_admission_manifest() {
    local fixture_root=$1
    [[ $fixture_root == /tmp/* && -d $fixture_root && ! -L $fixture_root ]] ||
        die 'unsafe admission manifest fixture root'
    [[ ! -e $fixture_root/preflight/admission-tree-manifest.tsv &&
       ! -L $fixture_root/preflight/admission-tree-manifest.tsv ]] ||
        die 'admission fixture manifest already exists'
    write_admission_tree_manifest "$fixture_root"
    printf 'current_profile_g5_admission_manifest_test=PASS\n'
}

self_test_exclusive_writes() {
    local root target copied target_content replacement_rc symlink_rc
    root=$(/usr/bin/mktemp -d)
    target=$root/evidence.txt
    printf 'original\n' | write_new_stdin "$target"
    printf 'source\n' >"$root/source.txt"
    write_new_checked "$root/copied.txt" "$root/source.txt"
    set +e
    printf 'replacement\n' | write_new_stdin "$target" >/dev/null 2>&1
    replacement_rc=$?
    /usr/bin/ln -s -- "$target" "$root/symlink-target"
    printf 'symlink-replacement\n' | write_new_stdin "$root/symlink-target" >/dev/null 2>&1
    symlink_rc=$?
    set -e
    copied=$(/usr/bin/cat -- "$root/copied.txt")
    target_content=$(/usr/bin/cat -- "$target")
    if (( replacement_rc == 0 || symlink_rc == 0 )) ||
       [[ $target_content != original || $copied != source ]]; then
        printf 'current_profile_g5_exclusive_write_test=FAIL\n'
        exit 1
    fi
    /usr/bin/chmod -R u+w -- "$root"
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g5_exclusive_write_test=PASS\n'
}

admission_feasibility_run() {
    trap on_exit EXIT
    trap on_error ERR
    [[ $RUN_MODE == admission && $OUT == "$ADMISSION_OUT" ]] ||
        die 'admission root selection mismatch'
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    PREFLIGHT_DIR=$PARTIAL/preflight
    /usr/bin/mkdir -m 0700 -- "$PREFLIGHT_DIR"
    JOURNAL=$PREFLIGHT_DIR/journal.tsv
    local campaign_start_monotonic_ns
    campaign_start_monotonic_ns=$(monotonic_ns)
    readonly HARD_DEADLINE_MONOTONIC_NS=$((campaign_start_monotonic_ns + CAMPAIGN_BUDGET_SECONDS * 1000000000))
    readonly WORK_DEADLINE_MONOTONIC_NS=$((HARD_DEADLINE_MONOTONIC_NS - FINALIZATION_RESERVE_SECONDS * 1000000000))
    admission "$PREFLIGHT_DIR" 1
    run_suites
    capture_g5_identity_inputs
    build_full_instruction_map
    verify_feasibility_fixture "$PARTIAL"
    verify_address_join_smoke "$PARTIAL"
    for artifact in address-smoke.data address-smoke.perf-script.txt \
        address-smoke.buildid-list.txt; do
        [[ -f $PARTIAL/$artifact && ! -L $PARTIAL/$artifact ]] ||
            die "address-smoke artifact missing or unsafe: $artifact"
        /usr/bin/rm -- "$PARTIAL/$artifact"
    done
    write_admission_tree_manifest "$PARTIAL"
    assert_admission_has_no_performance "$PARTIAL"
    write_g5_admission_identity_set "$PARTIAL"
    /usr/bin/grep -qx 'performance_sample=NO' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity performance_sample mismatch'
    /usr/bin/grep -qx 'campaign_cells=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity campaign_cells mismatch'
    /usr/bin/grep -qx 'retained_perf_data=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity retained_perf_data mismatch'
    /usr/bin/grep -qx 'campaign_sample_rows=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity campaign_sample_rows mismatch'
    CAMPAIGN_STATUS=NO-PERFORMANCE-ADMISSION
    FINALIZING=1
    run_terminal_finalization
}

self_test() {
    local audit_dir audit_resolver audit_prefix audit_summary
    [[ $CYCLE_DISAGREEMENT_MAX == 0.10 ]] || self_test_fail cycle_threshold_boundary
    [[ $RECORD_RATIO_MAX == 1.10 ]] || self_test_fail record_threshold_boundary
    [[ $SHARE_DELTA_MAX == 1.00 ]] || self_test_fail share_threshold_boundary
    [[ $SAMPLE_COUNT_MIN == 4787 ]] || self_test_fail sample_count_boundary
    classify_cycle_agreement 100 90 || self_test_fail cycle_threshold_accept
    ! classify_cycle_agreement 100 89 || self_test_fail cycle_threshold_reject
    classify_record_overhead 100 110 || self_test_fail record_threshold_accept
    ! classify_record_overhead 100 111 || self_test_fail record_threshold_reject
    classify_share_stability 5.0 4.0 5.0 || self_test_fail share_threshold_accept
    ! classify_share_stability 5.0 3.99 5.0 || self_test_fail share_threshold_reject
    classify_sample_count 4787 || self_test_fail sample_count_accept
    ! classify_sample_count 4786 || self_test_fail sample_count_reject
    audit_dir=$(/usr/bin/mktemp -d)
    audit_resolver=$audit_dir/resolver.txt
    audit_prefix=$audit_dir/prefix.tsv
    audit_summary=$audit_dir/summary.tsv
    /usr/bin/printf '%s\n' '/src/a/../b.rs:1' >"$audit_resolver"
    /usr/bin/printf '%s\n' $'source_domain\tpackage_identity\tprefix\treplacement' \
        $'workspace\tfixture@1\t/src\t$SOURCE' >"$audit_prefix"
    audit_prefix_coverage "$audit_resolver" "$audit_prefix" "$audit_summary" || {
        /usr/bin/rm -rf -- "$audit_dir"
        self_test_fail prefix_coverage_positive
    }
    /usr/bin/printf '%s\n' '/src/../../etc/passwd:1' >>"$audit_resolver"
    if audit_prefix_coverage "$audit_resolver" "$audit_prefix" "$audit_summary" >/dev/null 2>&1; then
        /usr/bin/rm -rf -- "$audit_dir"
        self_test_fail prefix_coverage_escape_negative
    fi
    /usr/bin/rm -rf -- "$audit_dir"
    printf 'current_profile_g5_self_test=PASS\n'
}

self_test_fake_cargo() {
    local dir snapshot matches
    dir=$(/usr/bin/mktemp -d)
    snapshot=$dir/processes.txt
    matches=$dir/matches.txt
    printf '999999 1 cargo cargo build --release\n' >"$snapshot"
    classify_process_snapshot "$snapshot" "$matches"
    if [[ $(/usr/bin/wc -l <"$matches") != 1 ]] || ! /usr/bin/grep -qF 'cargo build --release' "$matches"; then
        /usr/bin/rm -rf -- "$dir"
        printf 'current_profile_g5_fake_cargo=FAIL\n'
        exit 1
    fi
    /usr/bin/rm -rf -- "$dir"
    printf 'current_profile_g5_fake_cargo=PASS\n'
}

self_test_cgroup_environment() {
    local observed_unit
    observed_unit=${SYSTEMD_UNIT:-missing}
    if [[ -n ${CUBR_G5_PURE_MOCK_PARENT_CANARY+x} ]]; then
        printf 'current_profile_g5_cgroup_environment_test=FAIL canary=present unit=%s\n' "$observed_unit"
        exit 1
    fi
    printf 'current_profile_g5_cgroup_environment_test=PASS canary=absent unit=%s\n' "$observed_unit"
}

self_test_cgroup() {
    local root procs sentinel rc
    root=$(/usr/bin/mktemp -d)
    procs=$root/cgroup.procs
    sentinel=$root/unit-stop.requested
    printf '%s\n' "$$" >"$procs"
    CONTROL_GROUP=/mock.slice/new24-g4-test.service
    CGROUP_PROCS=$procs
    CGROUP_STOP_SENTINEL=$sentinel
    capture_cgroup_baseline "$CGROUP_PROCS"
    set +e
    # PPID and $1 must expand in the bounded child.
    # shellcheck disable=SC2016
    run_process_group_bounded 5 /usr/bin/bash -c \
        '/usr/bin/printf "%s\n" "$PPID" 999999 >"$1"' fixture "$procs"
    rc=$?
    set -e
    if (( rc != 125 )) ||
       [[ $(<"$sentinel") != 'systemctl --no-block stop mock.unit' ]] ||
       [[ $FAILURE_REASON != *'exact systemd ControlGroup'* ]]; then
        /usr/bin/rm -rf -- "$root"
        printf 'current_profile_g5_cgroup_test=FAIL\n'
        exit 1
    fi
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g5_cgroup_test=PASS unit=mock.unit\n'
}

self_test_cgroup_live_worker() {
    local props main_pid control_group cgroup_file rc
    [[ $CGROUP_SYSTEMCTL_USER == 1 && -n $SYSTEMD_UNIT && -n ${CUBR_CGROUP_LIVE_RESULT:-} ]] ||
        die 'live cgroup worker identity is missing'
    JOURNAL=$CUBR_CGROUP_LIVE_RESULT
    props=$(/usr/bin/systemctl --user show "$SYSTEMD_UNIT" -p MainPID -p ControlGroup -p KillMode)
    /usr/bin/grep -qx 'KillMode=control-group' <<<"$props" || die 'live cgroup KillMode mismatch'
    main_pid=$(/usr/bin/awk -F= '$1=="MainPID" {print $2}' <<<"$props")
    [[ $main_pid == "$$" ]] || die 'live cgroup MainPID mismatch'
    control_group=$(/usr/bin/awk -F= '$1=="ControlGroup" {print $2}' <<<"$props")
    [[ $control_group =~ ^/[A-Za-z0-9_.:@-]+(/[A-Za-z0-9_.:@-]+)*$ && $control_group != *'..'* ]] ||
        die 'live systemd ControlGroup path is malformed'
    cgroup_file=/sys/fs/cgroup$control_group/cgroup.procs
    [[ -f $cgroup_file && ! -L $cgroup_file && $(/usr/bin/readlink -f -- "$cgroup_file") == "$cgroup_file" ]] ||
        die 'live systemd cgroup.procs binding is unsafe'
    CONTROL_GROUP=$control_group
    CGROUP_PROCS=$cgroup_file
    capture_cgroup_baseline "$CGROUP_PROCS"
    set +e
    run_process_group_bounded 5 /usr/bin/python3 -c \
        'import os, signal, time; p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork(); os._exit(0) if p else None; signal.signal(signal.SIGTERM, signal.SIG_IGN); null=os.open(os.devnull, os.O_RDWR); [os.dup2(null, fd) for fd in (0,1,2)]; time.sleep(30)'
    rc=$?
    set -e
    # The exact-unit stop should terminate this worker before the guard returns.
    printf 'live_cgroup_guard_unexpected_return=%s\n' "$rc" >>"$JOURNAL"
    exit 126
}

verify_live_cgroup_fixture_result() {
    local rc=$1 fixture_result=$2 fixture_unit=$3 systemd_output=$4 verification_error
    [[ $rc =~ ^[0-9]+$ && $fixture_unit =~ ^[A-Za-z0-9_.:@-]+[.]service$ &&
       $fixture_unit != *'..'* ]] ||
        die 'live fixture result verifier inputs are malformed'
    (( rc == 0 )) || die 'live fixture systemd-run status is not expected success'
    [[ -f $fixture_result && ! -L $fixture_result ]] || die 'live fixture result is missing or unsafe'
    [[ -f $systemd_output && ! -L $systemd_output ]] ||
        die 'live fixture systemd-run output is missing or unsafe'
    if ! verification_error=$(/usr/bin/python3 - "$fixture_result" "$fixture_unit" "$systemd_output" 2>&1 <<'PY'
import os, re, stat, sys

result_path, unit, output_path = sys.argv[1:]

def read_regular(path, label):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise SystemExit(f"{label} is missing or unsafe") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1_048_576:
            raise SystemExit(f"{label} is missing or unsafe")
        chunks, total = [], 0
        while True:
            try:
                chunk = os.read(fd, min(65536, 1_048_577 - total))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > 1_048_576:
                raise SystemExit(f"{label} exceeds size bound")
        payload = b"".join(chunks)
    finally:
        os.close(fd)
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SystemExit(f"{label} is not exact UTF-8") from error

output_lines = read_regular(output_path, "live fixture systemd-run output").splitlines()
running = re.compile(
    rf"Running as unit: {re.escape(unit)}; invocation ID: [0-9a-f]{{32}}"
)
finished = "Finished with result: success"
terminated = "Main processes terminated with: code=killed/status=TERM"
optional = re.compile(
    r"(?:Service runtime|CPU time consumed|Memory peak|Memory swap peak): [ -~]+"
)
if (sum(bool(running.fullmatch(line)) for line in output_lines) != 1 or
        output_lines.count(finished) != 1 or output_lines.count(terminated) != 1 or
        any(not (running.fullmatch(line) or line in {finished, terminated} or optional.fullmatch(line))
            for line in output_lines)):
    raise SystemExit("live fixture systemd-run output authentication failed")

result_lines = read_regular(result_path, "live fixture result").splitlines()
timestamp = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\t"
new_pid = re.compile(
    timestamp + r"cgroup_new_pid=[1-9][0-9]*(?:,[1-9][0-9]*)* "
    r"control_group=/[A-Za-z0-9_.:@/\\x-]+"
)
stop = re.compile(timestamp + rf"unit_stop_request={re.escape(unit)} scope=user")
if any("live_cgroup_guard_unexpected_return=" in line for line in result_lines):
    raise SystemExit("live cgroup guard unexpectedly returned")
if sum(bool(new_pid.fullmatch(line)) for line in result_lines) != 1:
    raise SystemExit("live fixture did not retain a new cgroup PID")
if sum(bool(stop.fullmatch(line)) for line in result_lines) != 1:
    raise SystemExit("live fixture did not request the exact fixture unit stop")
if len(result_lines) != 2:
    raise SystemExit("live fixture result contains unexpected evidence")
PY
    ); then
        die "$verification_error"
    fi
}

self_test_verify_cgroup_live_result() {
    (( $# == 4 )) || die 'live result self-test requires rc, result, unit, and systemd output'
    verify_live_cgroup_fixture_result "$1" "$2" "$3" "$4"
    printf 'current_profile_g5_live_result_test=PASS\n'
}

self_test_cgroup_live() {
    local export_dir=${1:-} root fixture_result fixture_unit runner_path systemd_output rc result_sha output_sha
    local -a systemd_args
    [[ -d $export_dir && ! -L $export_dir ]] || die 'live fixture export directory is unsafe'
    root=$(/usr/bin/mktemp -d)
    fixture_result=$root/cgroup-live.tsv
    fixture_unit=current-profile-g5-cgroup-selftest-$$.service
    runner_path=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
    systemd_output=$root/systemd-run.output.txt
    systemd_args=(
        /usr/bin/systemd-run --user --wait --collect
        --unit="$fixture_unit" --service-type=exec
        --property=Restart=no --property=KillMode=control-group
        --setenv=CUBR_SYSTEMD_UNIT="$fixture_unit"
        --setenv=CUBR_CGROUP_SYSTEMCTL_USER=1
        --setenv=CUBR_CGROUP_LIVE_RESULT="$fixture_result"
        /usr/bin/bash "$runner_path" --self-test-cgroup-live-worker
    )
    printf '%q ' "${systemd_args[@]}" >"$root/systemd-run.argv"
    printf '\n' >>"$root/systemd-run.argv"
    /usr/bin/grep -qF -- "--unit=$fixture_unit" "$root/systemd-run.argv" ||
        die 'live fixture argument vector is missing fresh unit authority'
    /usr/bin/grep -qF -- "--setenv=CUBR_CGROUP_LIVE_RESULT=$fixture_result" "$root/systemd-run.argv" ||
        die 'live fixture argument vector is missing fixture result authority'
    ! /usr/bin/grep -qF 'g4-live-authority-must-not-be-used.service' "$root/systemd-run.argv" ||
        die 'live fixture argument vector contains poisoned parent unit'
    ! /usr/bin/grep -qF 'cubr-new24-full-binary-g5-20260810.service' "$root/systemd-run.argv" ||
        die 'live fixture argument vector contains campaign unit'
    ! /usr/bin/grep -Eq 'CUBR_ADMITTED_|INVOCATION_ID' "$root/systemd-run.argv" ||
        die 'live fixture argument vector contains admitted campaign authority'
    set +e
    "${systemd_args[@]}" >"$systemd_output" 2>&1
    rc=$?
    set -e
    verify_live_cgroup_fixture_result "$rc" "$fixture_result" "$fixture_unit" "$systemd_output"
    /usr/bin/install -m 0444 -- "$fixture_result" "$export_dir/cgroup-live.tsv"
    /usr/bin/install -m 0444 -- "$systemd_output" "$export_dir/systemd-run.output.txt"
    result_sha=$(sha "$export_dir/cgroup-live.tsv")
    output_sha=$(sha "$export_dir/systemd-run.output.txt")
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g5_cgroup_live_test=PASS result_sha256=%s test_output_sha256=%s\n' \
        "$result_sha" "$output_sha"
}

self_test_cgroup_precommit() {
    local root partial publishing final late procs sentinel rc expected_stop validated_unit
    validated_unit=${SYSTEMD_UNIT:-missing}
    if [[ $validated_unit != precommit-disconnected.service ]]; then
        printf 'current_profile_g5_cgroup_precommit_test=FAIL unit=%s reason=unexpected-fixture-unit\n' "$validated_unit"
        exit 1
    fi
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    procs=$root/cgroup.procs
    sentinel=$root/unit-stop.requested
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    printf '%s\n' "$$" >"$procs"
    CONTROL_GROUP=/mock.slice/precommit-connected.service
    CGROUP_PROCS=$procs
    CGROUP_BASELINE_PIDS=$$
    CGROUP_STOP_SENTINEL=$sentinel
    set +e
    CUBR_PUBLISH_CGROUP_TEST=connected publish_campaign \
        "$partial" "$publishing" "$final" "$late" 1970-01-01T00:00:00Z \
        "$(( $(monotonic_ns) + 5000000000 ))" '' 0 0 >/dev/null 2>&1
    rc=$?
    set -e
    if (( rc != 0 )) || [[ ! -f $final/TIMING-DONE.STAMP ]] || [[ -e $sentinel ]]; then
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf -- "$root"
        printf 'current_profile_g5_cgroup_precommit_test=FAIL connected-publisher-rejected\n'
        exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf -- "$root"
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    procs=$root/cgroup.procs
    sentinel=$root/unit-stop.requested
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    printf '999998\n' >"$procs"
    CONTROL_GROUP=/mock.slice/precommit-disconnected.service
    CGROUP_PROCS=$procs
    CGROUP_BASELINE_PIDS=999998
    CGROUP_STOP_SENTINEL=$sentinel
    expected_stop='systemctl --no-block stop precommit-disconnected.service'
    set +e
    CUBR_PUBLISH_CGROUP_TEST=disconnected publish_campaign \
        "$partial" "$publishing" "$final" "$late" 1970-01-01T00:00:00Z \
        "$(( $(monotonic_ns) + 5000000000 ))" '' 0 0 >/dev/null 2>&1
    rc=$?
    set -e
    if (( rc != 125 )) || [[ -e $final ]] || [[ ! -f $sentinel ]] ||
       [[ $(<"$sentinel") != "$expected_stop" ]]; then
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf -- "$root"
        printf 'current_profile_g5_cgroup_precommit_test=FAIL disconnected-publisher-accepted unit=%s\n' "$validated_unit"
        exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g5_cgroup_precommit_test=PASS unit=%s\n' "$validated_unit"
}

self_test_publish() {
    local root partial publishing final late
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    publish_campaign "$partial" "$publishing" "$final" "$late" 1970-01-01T00:00:00Z
    [[ ! -e $partial && ! -e $publishing && -f $final/TIMING-DONE.STAMP && -f $final/evidence-sha256.tsv &&
       ! -e $final/.TIMING-DONE.STAMP.pending ]] || {
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
        printf 'current_profile_g5_publish_test=FAIL\n'
        exit 1
    }
    [[ -z $(/usr/bin/find "$final" -xdev -perm /0222 -print -quit) ]] || {
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
        printf 'current_profile_g5_publish_test=FAIL\n'
        exit 1
    }
    /usr/bin/chmod -R u+w "$root"
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g5_publish_test=PASS\n'
}

self_test_publish_writes() {
    local mode root partial publishing final late rc
    for mode in eintr short; do
        root=$(/usr/bin/mktemp -d)
        partial=$root/evidence.partial
        publishing=$root/evidence.publishing
        final=$root/evidence
        late=$root/evidence.late
        /usr/bin/mkdir "$partial"
        printf 'fixture\n' >"$partial/payload.txt"
        printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
        CUBR_PUBLISH_WRITE_TEST=$mode publish_campaign "$partial" "$publishing" "$final" "$late" \
            1970-01-01T00:00:00Z || {
            printf 'current_profile_g5_publish_write_test=FAIL mode=%s\n' "$mode"; exit 1;
        }
        [[ -f $final/TIMING-DONE.STAMP ]] || {
            printf 'current_profile_g5_publish_write_test=FAIL mode=%s\n' "$mode"; exit 1;
        }
        /usr/bin/chmod -R u+w "$root"
        /usr/bin/rm -rf "$root"
    done
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    set +e
    CUBR_PUBLISH_WRITE_TEST=zero publish_campaign "$partial" "$publishing" "$final" "$late" \
        1970-01-01T00:00:00Z >/dev/null 2>&1
    rc=$?
    set -e
    if (( rc == 0 )) || [[ -e $final ]]; then
        printf 'current_profile_g5_publish_write_test=FAIL mode=zero\n'; exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g5_publish_write_test=PASS\n'
}

self_test_publish_tamper() {
    local mode root partial publishing final late rc
    for mode in tamper-marker tamper-content; do
        root=$(/usr/bin/mktemp -d)
        partial=$root/evidence.partial
        publishing=$root/evidence.publishing
        final=$root/evidence
        late=$root/evidence.late
        /usr/bin/mkdir "$partial"
        printf 'fixture\n' >"$partial/payload.txt"
        printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
        set +e
        publish_campaign "$partial" "$publishing" "$final" "$late" \
            1970-01-01T00:00:00Z "" "$mode" >/dev/null 2>&1
        rc=$?
        set -e
        if (( rc == 0 )) || [[ -e $final ]]; then
            printf 'current_profile_g5_publish_tamper_test=FAIL mode=%s\n' "$mode"; exit 1
        fi
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
    done
    printf 'current_profile_g5_publish_tamper_test=PASS\n'
}

self_test_timeout_tree() {
    local root script rc parent_pid child_pid
    root=$(/usr/bin/mktemp -d)
    script=$root/ignore-term.sh
    # Variables below expand in the generated child, not this runner.
    # shellcheck disable=SC2016
    printf '%s\n' '#!/usr/bin/env bash' 'trap "" TERM' \
        'printf "%s\n" "$$" >"$1/parent.pid"' \
        'sleep 30 & printf "%s\n" "$!" >"$1/child.pid"; wait' >"$script"
    /usr/bin/chmod 0555 "$script"
    HARD_DEADLINE_MONOTONIC_NS=$(( $(monotonic_ns) + 10000000000 ))
    WORK_DEADLINE_MONOTONIC_NS=$HARD_DEADLINE_MONOTONIC_NS
    FINALIZING=1
    set +e
    run_bounded 1 /usr/bin/bash "$script" "$root"
    rc=$?
    set -e
    parent_pid=$(/usr/bin/cat "$root/parent.pid")
    child_pid=$(/usr/bin/cat "$root/child.pid")
    if (( rc == 0 )) || /usr/bin/kill -0 "$parent_pid" 2>/dev/null || /usr/bin/kill -0 "$child_pid" 2>/dev/null; then
        /usr/bin/rm -rf "$root"
        printf 'current_profile_g5_timeout_tree_test=FAIL\n'
        exit 1
    fi
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g5_timeout_tree_test=PASS\n'
}

self_test_publish_crashes() {
    local point root partial publishing final late rc accepted
    for point in pending-written tree-fsynced publishing-renamed marker-renamed; do
        root=$(/usr/bin/mktemp -d)
        partial=$root/evidence.partial
        publishing=$root/evidence.publishing
        final=$root/evidence
        late=$root/evidence.late
        /usr/bin/mkdir "$partial"
        printf 'fixture\n' >"$partial/payload.txt"
        printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
        set +e
        publish_campaign "$partial" "$publishing" "$final" "$late" \
            1970-01-01T00:00:00Z "" "$point" >/dev/null 2>&1
        rc=$?
        set -e
        (( rc != 0 )) || { printf 'current_profile_g5_publish_crash_test=FAIL point=%s\n' "$point"; exit 1; }
        [[ ! -e $partial/TIMING-DONE.STAMP ]] || {
            printf 'current_profile_g5_publish_crash_test=FAIL point=%s partial-marker\n' "$point"; exit 1;
        }
        accepted=0
        if [[ -f $final/TIMING-DONE.STAMP && -f $final/evidence-sha256.tsv &&
              -z $(/usr/bin/find "$final" -xdev -perm /0222 -print -quit 2>/dev/null) ]]; then
            accepted=1
        fi
        (( accepted == 0 )) || {
            printf 'current_profile_g5_publish_crash_test=FAIL point=%s accepted\n' "$point"; exit 1;
        }
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
    done
    printf 'current_profile_g5_publish_crash_test=PASS\n'
}

self_test_hard_deadline() {
    local root partial publishing final late hard rc failed_tree late_error
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    hard=$(( $(monotonic_ns) + 6000000000 ))
    if run_process_group_bounded 5 /usr/bin/bash "${BASH_SOURCE[0]}" \
        --finalize-worker "$partial" "$publishing" "$final" "$late" "$hard" \
        1970-01-01T00:00:00Z VALID-ATTRIBUTION '' '' '' '' 2 >/dev/null 2>&1; then
        rc=0
    else
        rc=$?
    fi
    (( rc != 0 )) || { printf 'current_profile_g5_hard_deadline_test=FAIL accepted\n'; exit 1; }
    [[ ! -e $final && ! -e $late ]] || {
        printf 'current_profile_g5_hard_deadline_test=FAIL final-visible\n'; exit 1;
    }
    if [[ -d $publishing ]]; then
        reject_and_freeze_tree "$publishing" "$publishing" "$final" \
            'hard deadline self-test rejection'
        failed_tree=$publishing
    else
        reject_and_freeze_tree "$partial" "$partial" "$final" \
            'hard deadline self-test rejection'
        failed_tree=$partial
    fi
    [[ ! -e $partial/TIMING-DONE.STAMP && ! -e $publishing/TIMING-DONE.STAMP &&
       -z $(/usr/bin/find "$failed_tree" -xdev -perm /0222 -print -quit) ]] || {
        printf 'current_profile_g5_hard_deadline_test=FAIL partial-authoritative\n'; exit 1;
    }
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    late_error=$root/late-error.txt
    hard=$(( $(monotonic_ns) + 1000000000 ))
    if publish_campaign "$partial" "$publishing" "$final" "$late" \
        1970-01-01T00:00:00Z "$hard" delay-after-final 0 0 >/dev/null 2>"$late_error"; then
        rc=0
    else
        rc=$?
    fi
    (( rc != 0 )) || { printf 'current_profile_g5_hard_deadline_test=FAIL late-accepted\n'; exit 1; }
    [[ ! -e $final && -f $late/REJECTED-TIMING-DONE.STAMP && ! -e $late/TIMING-DONE.STAMP ]] || {
        /usr/bin/cat "$late_error" >&2
        printf 'current_profile_g5_hard_deadline_test=FAIL late-not-quarantined\n'; exit 1;
    }
    reject_and_freeze_tree "$late" "$late" "$final" \
        'late final quarantined by hard deadline self-test'
    [[ -f $late/REJECTED-TIMING-DONE.STAMP && ! -e $late/TIMING-DONE.STAMP &&
       -z $(/usr/bin/find "$late" -xdev -perm /0222 -print -quit) ]] || {
        printf 'current_profile_g5_hard_deadline_test=FAIL late-authoritative\n'; exit 1;
    }
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    publish_campaign "$partial" "$publishing" "$final" "$late" \
        1970-01-01T00:00:00Z "$(( $(monotonic_ns) + 5000000000 ))" '' 0 0
    reject_and_freeze_tree "$final" "$late" "$final" \
        'post-return late quarantine self-test'
    [[ ! -e $final && -f $late/REJECTED-TIMING-DONE.STAMP &&
       -f $late/FAILED.STAMP && ! -e $late/TIMING-DONE.STAMP &&
       -z $(/usr/bin/find "$late" -xdev -perm /0222 -print -quit) ]] || {
        printf 'current_profile_g5_hard_deadline_test=FAIL fallback-quarantine\n'; exit 1;
    }
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    root=$(/usr/bin/mktemp -d)
    partial=$root/evidence.partial
    publishing=$root/evidence.publishing
    final=$root/evidence
    late=$root/evidence.late
    /usr/bin/mkdir "$partial"
    printf 'fixture\n' >"$partial/payload.txt"
    printf '%s\t%s\t%s\n' "$(sha "$partial/payload.txt")" 8 payload.txt >"$partial/evidence-sha256.tsv"
    publish_campaign "$partial" "$publishing" "$final" "$late" \
        1970-01-01T00:00:00Z "$(( $(monotonic_ns) + 5000000000 ))" '' 0 0
    /usr/bin/chmod u+w "$final"
    printf 'collision-sentinel\n' >"$final/REJECTED-TIMING-DONE.STAMP"
    /usr/bin/chmod a-w "$final/REJECTED-TIMING-DONE.STAMP"
    set +e
    reject_and_freeze_tree "$final" "$late" "$final" \
        'no-replace collision self-test' >/dev/null 2>&1
    rc=$?
    set -e
    if (( rc == 0 )) || [[ -e $final || ! -f $late/TIMING-DONE.STAMP ]] ||
       [[ $(<"$late/REJECTED-TIMING-DONE.STAMP") != collision-sentinel ]]; then
        printf 'current_profile_g5_hard_deadline_test=FAIL no-replace-collision\n'; exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g5_hard_deadline_test=PASS\n'
}

main_run() {
    trap on_exit EXIT
    trap on_error ERR
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    PREFLIGHT_DIR=$PARTIAL/preflight
    /usr/bin/mkdir -m 0700 -- "$PREFLIGHT_DIR"
    JOURNAL=$PREFLIGHT_DIR/journal.tsv
    local campaign_start_monotonic_ns
    campaign_start_monotonic_ns=$(monotonic_ns)
    readonly HARD_DEADLINE_MONOTONIC_NS=$((campaign_start_monotonic_ns + CAMPAIGN_BUDGET_SECONDS * 1000000000))
    readonly WORK_DEADLINE_MONOTONIC_NS=$((HARD_DEADLINE_MONOTONIC_NS - FINALIZATION_RESERVE_SECONDS * 1000000000))
    require_deadline before-launch-authentication
    authenticate_campaign_launch_inputs
    require_deadline before-admission
    admission "$PREFLIGHT_DIR" 1
    require_deadline before-suites
    run_suites
    capture_g5_identity_inputs
    require_deadline before-full-map
    build_full_instruction_map
    require_deadline before-stable-identity-comparison
    write_g5_admission_identity_set "$PARTIAL"
    compare_g5_stable_identities "$PREFLIGHT_DIR/admission-sealed-identity-set.env" \
        "$PARTIAL/sealed-identity-set.env"
    require_deadline before-feasibility-fixture
    verify_feasibility_fixture "$PARTIAL"
    require_deadline before-address-smoke
    verify_address_join_smoke "$PARTIAL"
    local cell
    for cell in "${CELLS[@]}"; do
        require_deadline "before-cell-$cell"
        run_cell "$cell"
    done
    CURRENT_CELL=
    require_deadline before-campaign-verdict
    printf 'status=%s\tselection=NO-SELECT\nP1=SUPPORTED\nP2=SUPPORTED\nP3=SUPPORTED\nP4=%s\nP5=%s\n' \
        "$CAMPAIGN_STATUS" "$P4_STATUS" "$P5_STATUS" >"$PARTIAL/campaign-verdict.tsv"
    FINALIZING=1
    run_terminal_finalization
}

case ${1:-} in
    --map-worker) build_full_instruction_map_worker ;;
    --admission-feasibility) admission_feasibility_run ;;
    --self-test) self_test ;;
    --self-test-mode-roots) self_test_mode_roots ;;
    --self-test-snapshot-launch-inputs) self_test_snapshot_launch_inputs "$2" "$3" "$4" ;;
    --self-test-verify-remote-main) self_test_verify_remote_main "$2" "$3" "$4" ;;
    --self-test-parse-remote-main) parse_remote_main_output "$2" "$3" >/dev/null ;;
    --self-test-admission-no-performance) self_test_admission_no_performance "$2" ;;
    --self-test-write-admission-manifest) self_test_write_admission_manifest "$2" ;;
    --verify-launch-identity-files) verify_launch_identity_files "$2" "$3" ;;
    --launch-identity-value) launch_identity_value "$2" "$3" ;;
    --compare-g5-stable-identities) compare_g5_stable_identities "$2" "$3" ;;
    --self-test-exclusive-writes) self_test_exclusive_writes ;;
    --self-test-fake-cargo) self_test_fake_cargo ;;
    --self-test-cgroup-environment) self_test_cgroup_environment ;;
    --self-test-cgroup) self_test_cgroup ;;
    --self-test-cgroup-precommit) self_test_cgroup_precommit ;;
    --self-test-cgroup-live)
        (( $# == 2 )) || die 'live cgroup fixture requires exactly one export directory'
        self_test_cgroup_live "$2"
        ;;
    --self-test-verify-cgroup-live-result)
        self_test_verify_cgroup_live_result "$2" "$3" "$4" "$5"
        ;;
    --self-test-cgroup-live-worker) self_test_cgroup_live_worker ;;
    --self-test-publish) self_test_publish ;;
    --self-test-publish-writes) self_test_publish_writes ;;
    --self-test-publish-tamper) self_test_publish_tamper ;;
    --self-test-timeout-tree) self_test_timeout_tree ;;
    --self-test-publish-crashes) self_test_publish_crashes ;;
    --self-test-hard-deadline) self_test_hard_deadline ;;
    --finalize-worker) finalize_worker "$@" ;;
    '') main_run ;;
    *) printf 'usage: %s [--self-test|--self-test-fake-cargo|--self-test-cgroup-environment|--self-test-cgroup|--self-test-cgroup-precommit|--self-test-cgroup-live|--self-test-publish|--self-test-timeout-tree|--self-test-publish-crashes|--self-test-hard-deadline]\n' "$0" >&2; exit 2 ;;
esac
