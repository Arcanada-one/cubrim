#!/usr/bin/env bash
# Frozen NEW-24 G6 full-binary attribution runner. No selection or DB mutation.
set -Eeuo pipefail
IFS=$'\n\t'
export LC_ALL=C
export CUBR_THREADS=4
export RAYON_NUM_THREADS=4
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

readonly ROOT=/root/phaseC
readonly CODE_DIR=/root/cubr-new24-full-binary-g6-src-a
readonly CODE_DIR_B=/root/cubr-new24-full-binary-g6-src-b
readonly PROFILE_TARGET=/root/cubr-new24-full-binary-g6-target-a
readonly PROFILE_TARGET_B=/root/cubr-new24-full-binary-g6-target-b
readonly CUBRIM=$PROFILE_TARGET/release/cubrim
readonly CUBRIM_B=$PROFILE_TARGET_B/release/cubrim
readonly PREBUILD_RECEIPT=/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811/receipt.env
readonly VALIDATION_MANIFEST=/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env
readonly VALIDATION_OUTPUT=/root/cubr-new24-full-binary-g6-validation-20260811
readonly ADMISSION_INPUTS_LITERAL=/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env
readonly G6_ADMISSION_UNIT=cubr-new24-full-binary-g6-admission-20260811.service
readonly G6_CAMPAIGN_UNIT=cubr-new24-full-binary-g6-20260811.service
readonly CODE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly CORPUS_MANIFEST=/root/phaseC/corpus_manifest.tsv
readonly CORPUS_ROOT=/root/corpus-full/silesia

case ${1:-} in
    --admission-feasibility|--self-test-mode-roots) RUN_MODE=admission ;;
    --campaign) RUN_MODE=campaign ;;
    --map-worker|--finalize-worker|--self-test*) RUN_MODE=internal ;;
    *) RUN_MODE=invalid ;;
esac
readonly RUN_MODE

ROOT_PREFIX=${CUBR_G6_TEST_ROOT_PREFIX:-}
if [[ -n $ROOT_PREFIX && ${1:-} != --self-test-mode-roots &&
      ${1:-} != --admission-feasibility && ${1:-} != --campaign ]]; then
    printf 'current_profile_g6_contract=HARNESS_INVALID reason=test root outside root self-test\n' >&2
    exit 2
fi
if [[ -n $ROOT_PREFIX ]]; then
    CAMPAIGN_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g6-20260811
    ADMISSION_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g6-map-dryrun-20260811
else
    CAMPAIGN_OUT=/root/cubr-new24-full-binary-g6-20260811
    ADMISSION_OUT=/root/cubr-new24-full-binary-g6-map-dryrun-20260811
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
readonly INSTRUMENT_REPO=/root/cubr-new24-full-binary-g6-instrument
readonly RUNNER_PATH=documentation/ephemeral/research/current-profile-g6-run.sh
readonly RUNNER_TEST_PATH=documentation/ephemeral/research/current-profile-g6-run-test.sh
readonly MAPPER_PATH=documentation/ephemeral/research/current_profile_g6_map.py
readonly MAPPER_TEST_PATH=documentation/ephemeral/research/test_current_profile_g6_map.py
readonly RUNNER_SOURCE=$INSTRUMENT_REPO/$RUNNER_PATH
readonly RUNNER_TEST_SOURCE=$INSTRUMENT_REPO/$RUNNER_TEST_PATH
readonly MAPPER_SOURCE=$INSTRUMENT_REPO/$MAPPER_PATH
readonly MAPPER_TEST_SOURCE=$INSTRUMENT_REPO/$MAPPER_TEST_PATH
readonly RUSTC=/root/.cargo/bin/rustc
readonly GENERATED_CARGO_LOCK=code/cubrim-rs/Cargo.lock
readonly RECEIPT_SCHEMA=g6-prebuild-receipt-v1
readonly VALIDATION_SCHEMA=g6-validation-manifest-v1
readonly ADMISSION_INPUT_SCHEMA=g6-admission-inputs-v1
readonly LAUNCH_SCHEMA=g6-protected-launch-identities-v1
readonly LAUNCH_IDENTITIES_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-LAUNCH-IDENTITIES-20260811.env
readonly G6_PREREG_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G6-20260811.md
readonly G6_PREREG_SOURCE=$INSTRUMENT_REPO/$G6_PREREG_PATH
readonly G6_LAUNCH_IDENTITIES_SOURCE=$INSTRUMENT_REPO/$LAUNCH_IDENTITIES_PATH
readonly EXPECTED_G6_PREREG_BLOB=832504025f715a7a8873bdb563509b946f914155
readonly RECEIPT_KEYS='binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 build_cpuset campaign_artifact_count cargo_build_args_sha256 cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256 cargo_profile_release_debug cargo_version cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head map_artifact_count mkl_num_threads omp_num_threads perf_data_count prebuild_helper_blob prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob prebuild_test_sha256 rayon_num_threads rustc_commit rustc_version schema service_count source_commit source_tree_a_git_tree source_tree_a_manifest_bytes source_tree_a_manifest_sha256 source_tree_b_git_tree source_tree_b_manifest_bytes source_tree_b_manifest_sha256 target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes target_b_manifest_sha256'
readonly VALIDATION_KEYS='binary_build_id binary_sha256 build_cpuset campaign_artifact_count cargo_lock_bytes cargo_lock_sha256 cargo_test_release_log_bytes cargo_test_release_log_sha256 cargo_version cubr_threads instrument_main map_artifact_count mkl_num_threads omp_num_threads output_tree_manifest_bytes output_tree_manifest_sha256 perf_data_count rayon_num_threads rustc_commit rustc_version schema scheme_roundtrip_log_bytes scheme_roundtrip_log_sha256 service_count source_commit source_tree_manifest_bytes source_tree_manifest_sha256 suite_commands_sha256 target_tree_manifest_bytes target_tree_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_test_blob validation_test_sha256'
readonly ADMISSION_INPUT_KEYS='admission_output_root admission_unit binary_a_build_id binary_a_sha256 binary_b_build_id binary_b_sha256 g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head g6_prereg_blob instrument_main mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256 prebuild_helper_blob prebuild_helper_sha256 prebuild_test_blob prebuild_test_sha256 receipt_bytes receipt_schema receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256 schema source_commit validation_helper_blob validation_helper_sha256 validation_manifest_bytes validation_manifest_sha256 validation_test_blob validation_test_sha256'
readonly LAUNCH_KEYS='admission_control_group admission_identity_set_bytes admission_identity_set_sha256 admission_input_bytes admission_input_sha256 admission_instrument_main admission_invocation_id admission_journal_bytes admission_journal_sha256 admission_main_pid admission_output_manifest_bytes admission_output_manifest_sha256 admission_unit admission_unit_properties_bytes admission_unit_properties_sha256 binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 build_cpuset campaign_output_root campaign_unit cargo_build_args_sha256 cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256 cargo_profile_release_debug cargo_version corpus_dickens_max_archive_sha256 corpus_dickens_max_bytes corpus_dickens_max_decode_timeout_seconds corpus_dickens_max_encode_timeout_seconds corpus_dickens_max_original_sha256 corpus_dickens_web_archive_sha256 corpus_dickens_web_bytes corpus_dickens_web_decode_timeout_seconds corpus_dickens_web_encode_timeout_seconds corpus_dickens_web_original_sha256 corpus_manifest_bytes corpus_manifest_sha256 corpus_xml_max_archive_sha256 corpus_xml_max_bytes corpus_xml_max_decode_timeout_seconds corpus_xml_max_encode_timeout_seconds corpus_xml_max_original_sha256 cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head g6_prereg_blob map_admission_seal_bytes map_admission_seal_sha256 map_gzip_manifest_bytes map_gzip_manifest_sha256 map_gzip_member_count map_instruction_row_count map_reverse_index_bytes map_reverse_index_sha256 map_reverse_row_count map_stream_bytes map_stream_sha256 mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256 mapping_schema_sha256 mkl_num_threads omp_num_threads prebuild_helper_blob prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob prebuild_test_sha256 rayon_num_threads receipt_bytes receipt_schema receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256 rustc_commit rustc_version sanitized_env_contract_sha256 schema source_commit source_tree_a_git_tree source_tree_a_manifest_bytes source_tree_a_manifest_sha256 source_tree_b_git_tree source_tree_b_manifest_bytes source_tree_b_manifest_sha256 target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes target_b_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_manifest_bytes validation_manifest_sha256 validation_test_blob validation_test_sha256'
SYSTEMD_UNIT=
ADMISSION_INPUTS=$ADMISSION_INPUTS_LITERAL
LAUNCH_IDENTITIES=
case $RUN_MODE in
    admission)
        SYSTEMD_UNIT=${CUBR_G6_ADMITTED_UNIT:-}
        ADMISSION_INPUTS=${CUBR_G6_ADMISSION_INPUTS:-}
        ;;
    campaign)
        SYSTEMD_UNIT=${CUBR_G6_ADMITTED_UNIT:-}
        LAUNCH_IDENTITIES=${CUBR_G6_LAUNCH_IDENTITIES:-}
        ;;
    internal) SYSTEMD_UNIT=${CUBR_G6_TEST_UNIT:-} ;;
esac
readonly SYSTEMD_UNIT ADMISSION_INPUTS LAUNCH_IDENTITIES
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
INSTRUMENT_COMMIT=
EXPECTED_RUNNER_SHA=
EXPECTED_MAPPER_SHA=
EXPECTED_TEST_SHA=
EXPECTED_MAPPER_TEST_SHA=
LAUNCH_MAIN=
LAUNCH_IDENTITIES_BLOB=
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
INSTRUMENT_SHA256=
MAPPING_SCHEMA_SHA256=
MAP_SEAL_SHA256=
RECEIPT_SHA256=
RECEIPT_BYTES=
VALIDATION_MANIFEST_SHA256=
VALIDATION_MANIFEST_BYTES=
ADMISSION_INPUT_SHA256=
ADMISSION_INPUT_BYTES=
PERF_EVENTS_CSV=cycles
FAILURE_REASON=
FAILURE_COMMAND=
FINALIZING=0
CONTROL_GROUP=
CGROUP_PROCS=
CGROUP_BASELINE_PIDS=
CGROUP_STOP_SENTINEL=${CUBR_CGROUP_STOP_SENTINEL:-}
CGROUP_SYSTEMCTL_USER=${CUBR_CGROUP_SYSTEMCTL_USER:-0}
CGROUP_EVIDENCE_INVOCATION_ID=
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
    printf 'current_profile_g6=VOID reason=%s\n' "$*" >&2
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

closed_env_validate() {
    local file=$1 schema=$2 keys=$3
    /usr/bin/python3 - "$file" "$schema" "$keys" <<'PY'
import os, re, stat, sys
from pathlib import Path

path, schema, expected_text = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
info = os.lstat(path)
if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
    raise SystemExit("closed identity input is not one regular file")
if stat.S_IMODE(info.st_mode) != 0o444:
    raise SystemExit("closed identity input mode is not 0444")
if not 0 < info.st_size <= 131072:
    raise SystemExit("closed identity input exceeds size bound")
raw = path.read_bytes()
try:
    text = raw.decode("utf-8", errors="strict")
except UnicodeDecodeError as error:
    raise SystemExit("closed identity input is not exact UTF-8") from error
if text.encode("utf-8") != raw or not text.endswith("\n") or "\r" in text or "\x00" in text:
    raise SystemExit("closed identity input is not canonical text")
rows = text[:-1].split("\n")
expected = expected_text.split()
if len(rows) != len(expected):
    raise SystemExit("closed identity key count mismatch")
parsed = []
for row in rows:
    if row.count("=") != 1:
        raise SystemExit("invalid closed identity row")
    key, value = row.split("=", 1)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise SystemExit("invalid closed identity key")
    if not value or not re.fullmatch(r"[\x21-\x3c\x3e-\x7e]+", value):
        raise SystemExit("invalid closed identity value")
    parsed.append((key, value))
keys = [key for key, _ in parsed]
if keys != expected or keys != sorted(keys) or len(keys) != len(set(keys)):
    raise SystemExit("unknown, duplicate, missing, or unsorted closed identity key")
values = dict(parsed)
if values.get("schema") != schema:
    raise SystemExit("closed identity schema mismatch")
PY
}

closed_env_value() {
    local file=$1 key=$2
    /usr/bin/awk -F= -v wanted="$key" '$1 == wanted { print substr($0, length($1) + 2); found++ }
        END { if (found != 1) exit 1 }' "$file"
}

assert_immutable_tree() {
    /usr/bin/python3 - "$1" <<'PY'
import os, stat, sys
from pathlib import Path

root = Path(sys.argv[1])
root_info = os.lstat(root)
if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
    raise SystemExit("immutable tree root is unsafe")
for path in [root, *sorted(root.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(root))))]:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise SystemExit("immutable tree contains a special or symlink node")
    if stat.S_IMODE(info.st_mode) & 0o222:
        raise SystemExit("immutable tree contains a writable entry")
PY
}

canonical_tree_manifest() {
    /usr/bin/python3 - "$1" <<'PY'
import hashlib, os, re, stat, sys
from pathlib import Path

root = Path(sys.argv[1])
root_info = os.lstat(root)
if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
    raise SystemExit("canonical manifest root is unsafe")
entries = [root, *sorted(root.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(root))))]
metadata, files = [], []
for path in entries:
    info = os.lstat(path)
    relative = "" if path == root else path.relative_to(root).as_posix()
    if relative:
        try:
            relative.encode("ascii")
        except UnicodeEncodeError as error:
            raise SystemExit("canonical manifest path is non-ASCII") from error
        if not re.fullmatch(r"[A-Za-z0-9._/@+=,-]+", relative):
            raise SystemExit("canonical manifest path is unsafe")
    if stat.S_ISDIR(info.st_mode):
        kind = "d"
    elif stat.S_ISREG(info.st_mode):
        kind = "f"
        files.append((relative, path, info.st_size))
    else:
        raise SystemExit("canonical manifest contains a special or symlink node")
    metadata.append(
        f"{relative}\t{kind}\t{stat.S_IMODE(info.st_mode):04o}\t"
        f"{info.st_uid}\t{info.st_gid}\t{info.st_size}\n"
    )
if sum(1 for row in metadata if row.startswith("\td\t")) != 1:
    raise SystemExit("canonical manifest root row mismatch")
for row in metadata:
    sys.stdout.write(row)
for relative, path, expected_size in files:
    digest = hashlib.sha256()
    count = 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        current = os.fstat(fd)
        if not stat.S_ISREG(current.st_mode) or current.st_size != expected_size:
            raise SystemExit("canonical manifest file changed during read")
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            count += len(block)
    finally:
        os.close(fd)
    if count != expected_size:
        raise SystemExit("canonical manifest file byte count mismatch")
    sys.stdout.write(f"{digest.hexdigest()}\t{count}\t{relative}\n")
PY
}

capture_tree_manifest_identity() {
    local root=$1 label=$2 target
    target=$PREFLIGHT_DIR/$label.tree-manifest.tsv
    canonical_tree_manifest "$root" | write_new_stdin "$target"
    printf '%s %s\n' "$(sha "$target")" "$(/usr/bin/stat -c %s -- "$target")"
}

verify_binary_receipt_identity() {
    local binary=$1 prefix=$2 expected_sha expected_build expected_bytes expected_device expected_inode
    [[ -f $binary && -x $binary && ! -L $binary ]] || die "sealed $prefix binary missing or unsafe"
    expected_sha=$(closed_env_value "$PREBUILD_RECEIPT" "${prefix}_sha256")
    expected_build=$(closed_env_value "$PREBUILD_RECEIPT" "${prefix}_build_id")
    expected_bytes=$(closed_env_value "$PREBUILD_RECEIPT" "${prefix}_bytes")
    expected_device=$(closed_env_value "$PREBUILD_RECEIPT" "${prefix}_device")
    expected_inode=$(closed_env_value "$PREBUILD_RECEIPT" "${prefix}_inode")
    [[ $(sha "$binary") == "$expected_sha" && $expected_sha == "$EXPECTED_BINARY_SHA" ]] ||
        die "sealed $prefix binary sha256 mismatch"
    [[ $(/usr/bin/stat -c %s -- "$binary") == "$expected_bytes" &&
       $(/usr/bin/stat -c %d -- "$binary") == "$expected_device" &&
       $(/usr/bin/stat -c %i -- "$binary") == "$expected_inode" ]] ||
        die "sealed $prefix binary metadata mismatch"
    local actual_build
    actual_build=$(/usr/bin/readelf -nW "$binary" | /usr/bin/awk '/Build ID:/ {print $3; exit}')
    [[ $actual_build == "$expected_build" && $expected_build == "$EXPECTED_BINARY_BUILD_ID" ]] ||
        die "sealed $prefix binary build ID mismatch"
}

authenticate_g6_receipt() {
    [[ -f $PREBUILD_RECEIPT && ! -L $PREBUILD_RECEIPT ]] ||
        die 'prebuild receipt missing or unsafe'
    closed_env_validate "$PREBUILD_RECEIPT" "$RECEIPT_SCHEMA" "$RECEIPT_KEYS" ||
        die 'prebuild receipt closed-schema validation failed'
    RECEIPT_SHA256=$(sha "$PREBUILD_RECEIPT")
    RECEIPT_BYTES=$(/usr/bin/stat -c %s -- "$PREBUILD_RECEIPT")
    [[ $(closed_env_value "$PREBUILD_RECEIPT" source_commit) == "$CODE_COMMIT" &&
       $(closed_env_value "$PREBUILD_RECEIPT" build_cpuset) == 0-15 &&
       $(closed_env_value "$PREBUILD_RECEIPT" cargo_profile_release_debug) == 1 &&
       $(closed_env_value "$PREBUILD_RECEIPT" cubr_threads) == 4 &&
       $(closed_env_value "$PREBUILD_RECEIPT" rayon_num_threads) == 4 &&
       $(closed_env_value "$PREBUILD_RECEIPT" omp_num_threads) == 4 &&
       $(closed_env_value "$PREBUILD_RECEIPT" mkl_num_threads) == 4 &&
       $(closed_env_value "$PREBUILD_RECEIPT" perf_data_count) == 0 &&
       $(closed_env_value "$PREBUILD_RECEIPT" service_count) == 0 &&
       $(closed_env_value "$PREBUILD_RECEIPT" map_artifact_count) == 0 &&
       $(closed_env_value "$PREBUILD_RECEIPT" campaign_artifact_count) == 0 ]] ||
        die 'prebuild receipt frozen value mismatch'
    [[ $(closed_env_value "$PREBUILD_RECEIPT" cargo_lock_a_sha256) == "$EXPECTED_CARGO_LOCK_SHA" &&
       $(closed_env_value "$PREBUILD_RECEIPT" cargo_lock_b_sha256) == "$EXPECTED_CARGO_LOCK_SHA" &&
       $(closed_env_value "$PREBUILD_RECEIPT" rustc_commit) == "$EXPECTED_RUSTC_COMMIT" ]] ||
        die 'prebuild receipt toolchain identity mismatch'
    assert_immutable_tree "$CODE_DIR"
    assert_immutable_tree "$CODE_DIR_B"
    assert_immutable_tree "$PROFILE_TARGET"
    assert_immutable_tree "$PROFILE_TARGET_B"
    local value bytes
    read -r value bytes < <(capture_tree_manifest_identity "$CODE_DIR" source-a)
    [[ $value == "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_a_manifest_sha256)" &&
       $bytes == "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_a_manifest_bytes)" ]] ||
        die 'source A manifest mismatch'
    read -r value bytes < <(capture_tree_manifest_identity "$CODE_DIR_B" source-b)
    [[ $value == "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_b_manifest_sha256)" &&
       $bytes == "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_b_manifest_bytes)" ]] ||
        die 'source B manifest mismatch'
    read -r value bytes < <(capture_tree_manifest_identity "$PROFILE_TARGET" target-a)
    [[ $value == "$(closed_env_value "$PREBUILD_RECEIPT" target_a_manifest_sha256)" &&
       $bytes == "$(closed_env_value "$PREBUILD_RECEIPT" target_a_manifest_bytes)" ]] ||
        die 'target A manifest mismatch'
    read -r value bytes < <(capture_tree_manifest_identity "$PROFILE_TARGET_B" target-b)
    [[ $value == "$(closed_env_value "$PREBUILD_RECEIPT" target_b_manifest_sha256)" &&
       $bytes == "$(closed_env_value "$PREBUILD_RECEIPT" target_b_manifest_bytes)" ]] ||
        die 'target B manifest mismatch'
    [[ $(/usr/bin/git -C "$CODE_DIR" rev-parse 'HEAD^{tree}') == \
           "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_a_git_tree)" &&
       $(/usr/bin/git -C "$CODE_DIR_B" rev-parse 'HEAD^{tree}') == \
           "$(closed_env_value "$PREBUILD_RECEIPT" source_tree_b_git_tree)" &&
       $(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD:code/cubrim-rs) == \
           "$(closed_env_value "$PREBUILD_RECEIPT" cubrim_subtree_git_tree)" &&
       $(/usr/bin/git -C "$CODE_DIR_B" rev-parse HEAD:code/cubrim-rs) == \
           "$(closed_env_value "$PREBUILD_RECEIPT" cubrim_subtree_git_tree)" ]] ||
        die 'sealed source Git tree identity mismatch'
    [[ $(/usr/bin/git -C "$CODE_DIR" hash-object --no-filters "$GENERATED_CARGO_LOCK") == \
           "$(closed_env_value "$PREBUILD_RECEIPT" cargo_lock_a_blob)" &&
       $(/usr/bin/git -C "$CODE_DIR_B" hash-object --no-filters "$GENERATED_CARGO_LOCK") == \
           "$(closed_env_value "$PREBUILD_RECEIPT" cargo_lock_b_blob)" ]] ||
        die 'sealed Cargo.lock Git blob mismatch'
    verify_binary_receipt_identity "$CUBRIM" binary_a
    verify_binary_receipt_identity "$CUBRIM_B" binary_b
    /usr/bin/cmp -- "$CUBRIM" "$CUBRIM_B" || die 'sealed prebuild binaries differ'
}

authenticate_g6_validation_manifest() {
    [[ -f $VALIDATION_MANIFEST && ! -L $VALIDATION_MANIFEST ]] ||
        die 'validation manifest missing or unsafe'
    closed_env_validate "$VALIDATION_MANIFEST" "$VALIDATION_SCHEMA" "$VALIDATION_KEYS" ||
        die 'validation manifest closed-schema validation failed'
    VALIDATION_MANIFEST_SHA256=$(sha "$VALIDATION_MANIFEST")
    VALIDATION_MANIFEST_BYTES=$(/usr/bin/stat -c %s -- "$VALIDATION_MANIFEST")
    [[ $(closed_env_value "$VALIDATION_MANIFEST" source_commit) == "$CODE_COMMIT" &&
       $(closed_env_value "$VALIDATION_MANIFEST" binary_sha256) == "$EXPECTED_BINARY_SHA" &&
       $(closed_env_value "$VALIDATION_MANIFEST" binary_build_id) == "$EXPECTED_BINARY_BUILD_ID" &&
       $(closed_env_value "$VALIDATION_MANIFEST" build_cpuset) == 0-15 &&
       $(closed_env_value "$VALIDATION_MANIFEST" perf_data_count) == 0 &&
       $(closed_env_value "$VALIDATION_MANIFEST" service_count) == 0 &&
       $(closed_env_value "$VALIDATION_MANIFEST" map_artifact_count) == 0 &&
       $(closed_env_value "$VALIDATION_MANIFEST" campaign_artifact_count) == 0 ]] ||
        die 'validation manifest frozen value mismatch'
    [[ $(closed_env_value "$VALIDATION_MANIFEST" instrument_main) == "$INSTRUMENT_COMMIT" ]] ||
        die 'validation instrument main mismatch'
}

derive_admission_instrument_authority() {
    [[ $ADMISSION_INPUTS == "$ADMISSION_INPUTS_LITERAL" ]] ||
        die 'CUBR_G6_ADMISSION_INPUTS must equal the frozen G6 admission input'
    [[ -f $ADMISSION_INPUTS && ! -L $ADMISSION_INPUTS ]] ||
        die 'admission input missing or unsafe'
    closed_env_validate "$ADMISSION_INPUTS" "$ADMISSION_INPUT_SCHEMA" "$ADMISSION_INPUT_KEYS" ||
        die 'admission input closed-schema validation failed'
    INSTRUMENT_COMMIT=$(closed_env_value "$ADMISSION_INPUTS" instrument_main)
    EXPECTED_RUNNER_SHA=$(closed_env_value "$ADMISSION_INPUTS" runner_sha256)
    EXPECTED_TEST_SHA=$(closed_env_value "$ADMISSION_INPUTS" runner_test_sha256)
    EXPECTED_MAPPER_SHA=$(closed_env_value "$ADMISSION_INPUTS" mapper_sha256)
    EXPECTED_MAPPER_TEST_SHA=$(closed_env_value "$ADMISSION_INPUTS" mapper_test_sha256)
    [[ $INSTRUMENT_COMMIT =~ ^[0-9a-f]{40}$ ]] ||
        die 'instrument commit derived from admission input is malformed'
    require_fixed_sha "$EXPECTED_RUNNER_SHA" 'runner SHA-256 derived from admission input'
    require_fixed_sha "$EXPECTED_TEST_SHA" 'runner test SHA-256 derived from admission input'
    require_fixed_sha "$EXPECTED_MAPPER_SHA" 'mapper SHA-256 derived from admission input'
    require_fixed_sha "$EXPECTED_MAPPER_TEST_SHA" 'mapper test SHA-256 derived from admission input'
}

authenticate_g6_admission_inputs() {
    [[ -f $ADMISSION_INPUTS && ! -L $ADMISSION_INPUTS ]] ||
        die 'admission input missing or unsafe'
    closed_env_validate "$ADMISSION_INPUTS" "$ADMISSION_INPUT_SCHEMA" "$ADMISSION_INPUT_KEYS" ||
        die 'admission input closed-schema validation failed'
    ADMISSION_INPUT_SHA256=$(sha "$ADMISSION_INPUTS")
    ADMISSION_INPUT_BYTES=$(/usr/bin/stat -c %s -- "$ADMISSION_INPUTS")
    [[ $(closed_env_value "$ADMISSION_INPUTS" admission_output_root) == "$ADMISSION_OUT" &&
       $(closed_env_value "$ADMISSION_INPUTS" admission_unit) == "$G6_ADMISSION_UNIT" &&
       $(closed_env_value "$ADMISSION_INPUTS" source_commit) == "$CODE_COMMIT" &&
       $(closed_env_value "$ADMISSION_INPUTS" receipt_schema) == "$RECEIPT_SCHEMA" &&
       $(closed_env_value "$ADMISSION_INPUTS" receipt_sha256) == "$RECEIPT_SHA256" &&
       $(closed_env_value "$ADMISSION_INPUTS" receipt_bytes) == "$RECEIPT_BYTES" &&
       $(closed_env_value "$ADMISSION_INPUTS" validation_manifest_sha256) == "$VALIDATION_MANIFEST_SHA256" &&
       $(closed_env_value "$ADMISSION_INPUTS" validation_manifest_bytes) == "$VALIDATION_MANIFEST_BYTES" &&
       $(closed_env_value "$ADMISSION_INPUTS" instrument_main) == "$INSTRUMENT_COMMIT" &&
       $(closed_env_value "$ADMISSION_INPUTS" g6_prereg_blob) == "$EXPECTED_G6_PREREG_BLOB" ]] ||
        die 'admission input authority mismatch'
    [[ $(closed_env_value "$ADMISSION_INPUTS" binary_a_sha256) == "$EXPECTED_BINARY_SHA" &&
       $(closed_env_value "$ADMISSION_INPUTS" binary_b_sha256) == "$EXPECTED_BINARY_SHA" &&
       $(closed_env_value "$ADMISSION_INPUTS" binary_a_build_id) == "$EXPECTED_BINARY_BUILD_ID" &&
       $(closed_env_value "$ADMISSION_INPUTS" binary_b_build_id) == "$EXPECTED_BINARY_BUILD_ID" ]] ||
        die 'admission input binary identity mismatch'
    [[ $(closed_env_value "$ADMISSION_INPUTS" runner_sha256) == "$EXPECTED_RUNNER_SHA" &&
       $(closed_env_value "$ADMISSION_INPUTS" runner_test_sha256) == "$EXPECTED_TEST_SHA" &&
       $(closed_env_value "$ADMISSION_INPUTS" mapper_sha256) == "$EXPECTED_MAPPER_SHA" &&
       $(closed_env_value "$ADMISSION_INPUTS" mapper_test_sha256) == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'admission input instrument identity mismatch'
    local key path blob_key sha_key expected_blob expected_sha
    while IFS='|' read -r key path; do
        blob_key=${key}_blob
        sha_key=${key}_sha256
        expected_blob=$(closed_env_value "$ADMISSION_INPUTS" "$blob_key")
        expected_sha=$(closed_env_value "$ADMISSION_INPUTS" "$sha_key")
        [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT:$path") == "$expected_blob" &&
           $(sha "$INSTRUMENT_REPO/$path") == "$expected_sha" ]] ||
            die "admission input instrument blob mismatch: $key"
    done <<'EOF'
prebuild_helper|documentation/ephemeral/research/current-profile-g6-prebuild.sh
prebuild_test|documentation/ephemeral/research/current-profile-g6-prebuild-test.sh
validation_helper|documentation/ephemeral/research/current-profile-g6-validate.sh
validation_test|documentation/ephemeral/research/current-profile-g6-validate-test.sh
runner|documentation/ephemeral/research/current-profile-g6-run.sh
runner_test|documentation/ephemeral/research/current-profile-g6-run-test.sh
mapper|documentation/ephemeral/research/current_profile_g6_map.py
mapper_test|documentation/ephemeral/research/test_current_profile_g6_map.py
EOF
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT:$G6_PREREG_PATH") == \
       "$EXPECTED_G6_PREREG_BLOB" ]] || die 'admission input G6 preregistration blob mismatch'
    for key in g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 \
        g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes \
        g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 \
        g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head; do
        [[ $(closed_env_value "$ADMISSION_INPUTS" "$key") == \
           "$(closed_env_value "$PREBUILD_RECEIPT" "$key")" ]] ||
            die "admission input G5 provenance mismatch: $key"
    done
    for key in prebuild_helper_blob prebuild_helper_sha256 prebuild_test_blob prebuild_test_sha256; do
        [[ $(closed_env_value "$ADMISSION_INPUTS" "$key") == \
           "$(closed_env_value "$PREBUILD_RECEIPT" "$key")" ]] ||
            die "admission input/prebuild receipt mismatch: $key"
    done
    for key in validation_helper_blob validation_helper_sha256 validation_test_blob validation_test_sha256; do
        [[ $(closed_env_value "$ADMISSION_INPUTS" "$key") == \
           "$(closed_env_value "$VALIDATION_MANIFEST" "$key")" ]] ||
            die "admission input/validation manifest mismatch: $key"
    done
}

authenticate_g6_pre_service_inputs() {
    derive_admission_instrument_authority
    authenticate_g6_receipt
    authenticate_g6_validation_manifest
    authenticate_g6_admission_inputs
}

verify_mode_unit() {
    local expected=$G6_CAMPAIGN_UNIT
    [[ $RUN_MODE == admission ]] && expected=$G6_ADMISSION_UNIT
    [[ $SYSTEMD_UNIT == "$expected" ]] ||
        die 'CUBR_G6_ADMITTED_UNIT must equal the mode-specific G6 unit'
    if [[ $RUN_MODE == admission ]]; then
        [[ $ADMISSION_INPUTS == "$ADMISSION_INPUTS_LITERAL" ]] ||
            die 'CUBR_G6_ADMISSION_INPUTS must equal the frozen G6 admission input'
        [[ -z ${CUBR_G6_LAUNCH_IDENTITIES:-} ]] ||
            die 'admission interface contains campaign launch authority'
    elif [[ $RUN_MODE == campaign ]]; then
        [[ $LAUNCH_IDENTITIES == "$G6_LAUNCH_IDENTITIES_SOURCE" ]] ||
            die 'CUBR_G6_LAUNCH_IDENTITIES must equal the protected instrument-checkout path'
        [[ -z ${CUBR_G6_ADMISSION_INPUTS:-} ]] ||
            die 'campaign interface contains admission-only authority'
    else
        die 'deployment interface used outside a deployment mode'
    fi
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
        jlog "cgroup_new_pid=$(IFS=,; printf '%s' "${new_pids[*]}") control_group=$CONTROL_GROUP${CGROUP_EVIDENCE_INVOCATION_ID:+ invocation_id=$CGROUP_EVIDENCE_INVOCATION_ID}"
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
    local repo_head origin_main
    run_bounded 120 /usr/bin/git -C "$INSTRUMENT_REPO" fetch --quiet origin main
    repo_head=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse HEAD)
    origin_main=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse origin/main)
    if [[ $RUN_MODE == admission ]]; then
        [[ $repo_head == "$INSTRUMENT_COMMIT" && $origin_main == "$INSTRUMENT_COMMIT" ]] ||
            die 'admission instrument checkout is not exact current origin/main'
    else
        [[ $LAUNCH_MAIN =~ ^[0-9a-f]{40}$ && $repo_head == "$LAUNCH_MAIN" &&
           $origin_main == "$LAUNCH_MAIN" ]] ||
            die 'campaign instrument checkout drifted from authenticated launch main'
    fi
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" cat-file -e "$INSTRUMENT_COMMIT^{commit}" || die 'instrument commit unavailable'
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" merge-base --is-ancestor "$INSTRUMENT_COMMIT" "$repo_head" ||
        die 'instrument commit is not contained in origin/main'

    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$RUNNER_PATH" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_RUNNER_SHA" ]] ||
        die 'instrument runner blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$MAPPER_PATH" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_SHA" ]] ||
        die 'instrument mapper blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$RUNNER_TEST_PATH" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_TEST_SHA" ]] ||
        die 'instrument test blob mismatch'
    [[ $(/usr/bin/git -C "$INSTRUMENT_REPO" show "$INSTRUMENT_COMMIT:$MAPPER_TEST_PATH" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'instrument mapper test blob mismatch'
    local asset_path
    for asset_path in "$RUNNER_PATH" "$RUNNER_TEST_PATH" "$MAPPER_PATH" "$MAPPER_TEST_PATH"; do
        [[ $(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$repo_head:$asset_path") == \
           "$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT:$asset_path")" &&
           $(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" hash-object --no-filters "$INSTRUMENT_REPO/$asset_path") == \
           "$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$repo_head:$asset_path")" ]] ||
            die "current instrument checkout asset mismatch: $asset_path"
    done
    [[ $(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}") == "$RUNNER_SOURCE" &&
       $(sha "$RUNNER_SOURCE") == "$EXPECTED_RUNNER_SHA" ]] ||
        die 'executed runner differs from frozen instrument blob'
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
    local snapshot=$1 output=$2 runner=${3:-$$} parent=${4:-$PPID}
    /usr/bin/awk -v runner="$runner" -v parent="$parent" -v g6_runner_path="$RUNNER_SOURCE" '
        $1 != runner && $1 != parent {
            comm=$3; args=$0
            g6_runner=(comm == "bash" && NF == 6 &&
                ($4 == "/usr/bin/bash" || $4 == "/bin/bash" || $4 == "bash") &&
                $5 == g6_runner_path &&
                ($6 == "--campaign" || $6 == "--admission-feasibility"))
            if (comm ~ /^(cargo|rustc|rustup|perf)$/ ||
                args ~ /(cubrim|current-profile-g[34]-run|current_profile_g6_map[.]py)/ ||
                g6_runner) print
        }
    ' "$snapshot" >"$output"
}

self_test_classify_process_snapshot() {
    (( $# == 4 )) || die 'process classifier self-test requires snapshot, output, runner PID, and parent PID'
    [[ $1 == /tmp/* && -f $1 && ! -L $1 && $2 == /tmp/* && ! -e $2 && ! -L $2 &&
       $3 =~ ^[1-9][0-9]*$ && $4 =~ ^[1-9][0-9]*$ ]] ||
        die 'unsafe process classifier self-test fixture'
    classify_process_snapshot "$1" "$2" "$3" "$4"
    printf 'current_profile_g6_process_classifier_test=PASS matches=%s\n' \
        "$(/usr/bin/wc -l <"$2")"
}

reject_orphan_processes() {
    local snapshot=$1 matches=$2
    /usr/bin/ps -eo pid=,ppid=,comm=,args= >"$snapshot"
    classify_process_snapshot "$snapshot" "$matches"
    [[ ! -s $matches ]] || die 'orphan candidate/perf process or competing Cubrim/Cargo/Rust/current-profile runner'
}

verify_systemd_contract() {
    [[ -n $SYSTEMD_UNIT ]] || die 'CUBR_G6_ADMITTED_UNIT must name the transient unit'
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
    {
        printf 'Unit=%s\n' "$SYSTEMD_UNIT"
        printf 'Contract=%s\n' "$SYSTEMD_CONTRACT"
        printf '%s\n' "$props"
        printf 'cgroup.procs=%s\n' "$CGROUP_PROCS"
    } >"$PREFLIGHT_DIR/systemd-contract.txt"
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
        /usr/bin/gzip /usr/bin/cmp /usr/bin/stat /usr/bin/systemctl /usr/bin/dpkg-query "$RUSTC"; do
        [[ -x $tool ]] || die "required tool unavailable: $tool"
    done
    [[ -f $MAPPER_SOURCE && ! -L $MAPPER_SOURCE ]] || die 'mapper missing or unsafe'
    [[ -f $MAPPER_TEST_SOURCE && ! -L $MAPPER_TEST_SOURCE ]] || die 'mapper test missing or unsafe'
    [[ -f $RUNNER_TEST_SOURCE && ! -L $RUNNER_TEST_SOURCE ]] || die 'runner test missing or unsafe'
    [[ -x $CUBRIM && ! -L $CUBRIM ]] || die 'prebuilt release binary missing or unsafe'
    [[ $(sha "$CUBRIM") == "$EXPECTED_BINARY_SHA" ]] || die 'prebuilt release binary sha256 mismatch'
    [[ -x $CUBRIM_B && ! -L $CUBRIM_B && $(sha "$CUBRIM_B") == "$EXPECTED_BINARY_SHA" ]] ||
        die 'second prebuilt release binary identity mismatch'
    /usr/bin/cmp -- "$CUBRIM" "$CUBRIM_B" ||
        die 'prebuilt release binaries are not byte-identical'
    [[ -f $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK &&
       -f $CODE_DIR_B/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR_B/$GENERATED_CARGO_LOCK ]] ||
        die 'generated Cargo.lock missing or unsafe'
    [[ $(sha "$CODE_DIR/$GENERATED_CARGO_LOCK") == "$EXPECTED_CARGO_LOCK_SHA" &&
       $(sha "$CODE_DIR_B/$GENERATED_CARGO_LOCK") == "$EXPECTED_CARGO_LOCK_SHA" ]] ||
        die 'generated Cargo.lock sha256 mismatch'
    /usr/bin/cmp -- "$CODE_DIR/$GENERATED_CARGO_LOCK" "$CODE_DIR_B/$GENERATED_CARGO_LOCK" ||
        die 'generated Cargo.lock copies differ'
    [[ $($RUSTC -vV | /usr/bin/awk -F': ' '$1=="release" {print $2}') == 1.96.1 ]] || die 'rustc release mismatch'
    [[ $($RUSTC -vV | /usr/bin/awk -F': ' '$1=="commit-hash" {print $2}') == "$EXPECTED_RUSTC_COMMIT" ]] ||
        die 'rustc commit mismatch'
    [[ $(/usr/bin/getconf PAGE_SIZE) == "$EXPECTED_PAGE_SIZE" ]] || die 'page size mismatch'
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
        printf 'cargo_version=%s\n' "$(closed_env_value "$PREBUILD_RECEIPT" cargo_version)"
        printf 'rustc_version=%s\n' "$($RUSTC -vV | /usr/bin/tr '\n' ';')"
    } >"$dir/identities.txt"
    /usr/bin/install -m 0444 -- "$MAPPER_SOURCE" "$dir/instrument-mapper.py"
    /usr/bin/install -m 0444 -- "$MAPPER_TEST_SOURCE" "$dir/instrument-mapper-test.py"
    /usr/bin/install -m 0444 -- "$RUNNER_TEST_SOURCE" "$dir/instrument-runner-test.sh"
    /usr/bin/install -m 0444 -- "${BASH_SOURCE[0]}" "$dir/instrument-runner.sh"
    /usr/bin/mkdir -- "$dir/mapper-test-runtime"
    /usr/bin/install -m 0444 -- "$MAPPER_SOURCE" "$dir/mapper-test-runtime/current_profile_g6_map.py"
    /usr/bin/install -m 0444 -- "$MAPPER_TEST_SOURCE" "$dir/mapper-test-runtime/test_current_profile_g6_map.py"
    require_deadline admission-mapper-tests
    (cd "$dir/mapper-test-runtime" && run_bounded 300 /usr/bin/env \
        PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 test_current_profile_g6_map.py) >"$dir/mapper-unit-test.txt"
    require_deadline admission-complete
}

authenticate_validation_suite_evidence() {
    local suite_dir=$PARTIAL/suites
    /usr/bin/mkdir -p -- "$suite_dir"
    local release_log=$VALIDATION_OUTPUT/cargo-test-release.log
    local roundtrip_log=$VALIDATION_OUTPUT/scheme-roundtrip.log
    local sealed_lock=$VALIDATION_OUTPUT/generated-Cargo.lock
    [[ -f $release_log && ! -L $release_log && -s $release_log &&
       -f $roundtrip_log && ! -L $roundtrip_log && -s $roundtrip_log &&
       -f $sealed_lock && ! -L $sealed_lock ]] ||
        die 'sealed validation suite evidence missing or unsafe'
    [[ $(sha "$release_log") == "$(closed_env_value "$VALIDATION_MANIFEST" cargo_test_release_log_sha256)" &&
       $(/usr/bin/stat -c %s -- "$release_log") == "$(closed_env_value "$VALIDATION_MANIFEST" cargo_test_release_log_bytes)" &&
       $(sha "$roundtrip_log") == "$(closed_env_value "$VALIDATION_MANIFEST" scheme_roundtrip_log_sha256)" &&
       $(/usr/bin/stat -c %s -- "$roundtrip_log") == "$(closed_env_value "$VALIDATION_MANIFEST" scheme_roundtrip_log_bytes)" &&
       $(sha "$sealed_lock") == "$EXPECTED_CARGO_LOCK_SHA" &&
       $(sha "$sealed_lock") == "$(closed_env_value "$VALIDATION_MANIFEST" cargo_lock_sha256)" ]] ||
        die 'sealed validation suite evidence identity mismatch'
    /usr/bin/install -m 0444 -- "$sealed_lock" "$suite_dir/generated-Cargo.lock"
    /usr/bin/install -m 0444 -- "$release_log" "$suite_dir/cargo-test-release.log"
    /usr/bin/install -m 0444 -- "$roundtrip_log" "$suite_dir/scheme-roundtrip.log"
    /usr/bin/mkdir -p -- "$PARTIAL/binary"
    /usr/bin/install -m 0555 -- "$CUBRIM" "$MEASURED_BINARY"
    [[ -x $CUBRIM && $(sha "$CUBRIM") == "$EXPECTED_BINARY_SHA" ]] || die 'release binary identity mismatch'
    /usr/bin/readelf -nW "$MEASURED_BINARY" >"$suite_dir/binary-notes.txt"
    BINARY_BUILD_ID=$(/usr/bin/awk '/Build ID:/ {print $3; exit}' "$suite_dir/binary-notes.txt")
    [[ $BINARY_BUILD_ID == "$EXPECTED_BINARY_BUILD_ID" ]] || die 'binary Build ID mismatch'
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
    (( $# == 4 )) || die 'map worker requires root and three authenticated identities'
    local worker_root=$1 instrument_sha=$2 expected_mapper_sha=$3 expected_mapper_test_sha=$4
    local worker_binary=$worker_root/binary/cubrim map_dir=$worker_root/map
    [[ $worker_root == "$ADMISSION_OUT.partial" && ! -L $worker_root ]] ||
        die 'map worker root is not the literal admission partial tree'
    [[ $instrument_sha =~ ^[0-9a-f]{64}$ ]] || die 'map worker instrument identity missing'
    [[ $expected_mapper_sha =~ ^[0-9a-f]{64}$ && $(sha "$MAPPER_SOURCE") == "$expected_mapper_sha" ]] ||
        die 'map worker mapper identity mismatch'
    [[ $expected_mapper_test_sha =~ ^[0-9a-f]{64}$ && $(sha "$MAPPER_TEST_SOURCE") == "$expected_mapper_test_sha" ]] ||
        die 'map worker mapper test identity mismatch'
    MAPPING_SCHEMA_SHA256=$({
        printf 'mapper_sha256=%s\n' "$expected_mapper_sha"
        printf 'mapper_test_sha256=%s\n' "$expected_mapper_test_sha"
    } | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')
    [[ -x $worker_binary && $(sha "$worker_binary") == "$EXPECTED_BINARY_SHA" ]] || die 'map worker binary identity mismatch'
    /usr/bin/mkdir -p -- "$map_dir"
    /usr/bin/readelf -W -l "$worker_binary" >"$map_dir/readelf-programs.txt"
    /usr/bin/readelf -W -S "$worker_binary" >"$map_dir/readelf-sections.txt"
    /usr/bin/python3 "$MAPPER" normalize-elf \
        --input-root "$worker_root" --output-root "$map_dir" \
        --readelf-programs map/readelf-programs.txt --readelf-sections map/readelf-sections.txt \
        --binary-sha256 "$EXPECTED_BINARY_SHA" --source-base-id "$CODE_COMMIT" \
        --instrument-sha256 "$instrument_sha" \
        --segments-out segments.tsv --sections-out sections.tsv \
        --summary-out elf-summary.json

    /usr/bin/objdump --disassemble --line-numbers --wide "$worker_binary" >"$map_dir/objdump.txt"
    /usr/bin/awk '/^[[:space:]]*[0-9a-f]+:/ {gsub(":", "", $1); print "0x" $1}' \
        "$map_dir/objdump.txt" >"$map_dir/instruction-addresses.txt"
    [[ -s $map_dir/instruction-addresses.txt ]] || die 'objdump yielded no instruction addresses'
    /usr/bin/addr2line -a -f -C -i -e "$worker_binary" <"$map_dir/instruction-addresses.txt" >"$map_dir/resolver-a.txt"
    /usr/bin/addr2line -a -f -C -i -e "$worker_binary" <"$map_dir/instruction-addresses.txt" >"$map_dir/resolver-b.txt"
    /usr/bin/cmp -- "$map_dir/resolver-a.txt" "$map_dir/resolver-b.txt" || die 'addr2line reproducibility mismatch'
    generate_prefix_table "$map_dir/prefix-table.tsv" "$map_dir/resolver-a.txt"
    audit_prefix_coverage "$map_dir/resolver-a.txt" "$map_dir/prefix-table.tsv" "$map_dir/prefix-coverage-audit.tsv"

    /usr/bin/python3 "$MAPPER" build-map \
        --input-root "$worker_root" --output-root "$map_dir" \
        --segments map/segments.tsv --sections map/sections.tsv --objdump map/objdump.txt \
        --resolver-a map/resolver-a.txt --resolver-b map/resolver-b.txt \
        --prefix-table map/prefix-table.tsv --binary-dso "$worker_binary" \
        --source-base-id "$CODE_COMMIT" --mapping-schema-sha256 "$MAPPING_SCHEMA_SHA256" \
        --map-part-prefix g6-full-instruction-map \
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
        /usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin \
            /usr/bin/bash "${BASH_SOURCE[0]}" --map-worker "$PARTIAL" \
            "$INSTRUMENT_SHA256" "$EXPECTED_MAPPER_SHA" "$EXPECTED_MAPPER_TEST_SHA" \
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
observed = {path.name for path in evidence_root.glob("g6-full-instruction-map.part-*.tsv.gz")}
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
        cubr-new24-g6-map-admission-seal-v1
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
    "schema": "cubr-new24-g6-address-smoke-v1",
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
    return (f"schema=current-profile-g6-publication-v1\nstatus={status}\n"
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
    return (f"schema=current-profile-g6-publication-v1\nstatus={status}\n"
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
    if (( rc != 0 )); then
        quarantine_late_final "${FAILURE_REASON:-unclassified failure rc=$rc}" >/dev/null 2>&1 || true
        freeze_failed_tree "$PUBLISHING" "${FAILURE_REASON:-unclassified failure rc=$rc}"
        freeze_failed_tree "$PARTIAL" "${FAILURE_REASON:-unclassified failure rc=$rc}"
    fi
    return "$rc"
}

self_test_fail() {
    printf 'current_profile_g6_self_test=FAIL reason=%s\n' "$1"
    exit 1
}

self_test_mode_roots() {
    [[ $RUN_MODE == admission && -n $ROOT_PREFIX ]] || {
        printf 'current_profile_g6_mode_root_test=FAIL unsafe-mode\n'
        exit 1
    }
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    /usr/bin/printf 'mode=admission\nperformance_sample=NO\n' |
        write_new_stdin "$PARTIAL/MODE-ROOT.PASS"
    /usr/bin/chmod 0555 -- "$PARTIAL"
    /usr/bin/mv -T --no-clobber -- "$PARTIAL" "$OUT"
    printf 'current_profile_g6_mode_root_test=PASS\n'
}

self_test_deployment_interface() {
    [[ -n $ROOT_PREFIX && $ROOT_PREFIX == /tmp/current-profile-g6-* ]] ||
        die 'deployment interface self-test requires an isolated test root'
    verify_mode_unit
    local authority=$LAUNCH_IDENTITIES
    [[ $RUN_MODE == admission ]] && authority=$ADMISSION_INPUTS
    printf 'current_profile_g6_deployment_interface=PASS mode=%s unit=%s authority=%s\n' \
        "$RUN_MODE" "$SYSTEMD_UNIT" "$authority"
}

self_test_snapshot_launch_inputs() {
    (( $# == 3 )) || die 'snapshot launch self-test requires two sources and one target directory'
    PREFLIGHT_DIR=$3
    snapshot_launch_inputs "$1" "$2" \
        "$PREFLIGHT_DIR/launch-preregistration.snapshot.md" \
        "$PREFLIGHT_DIR/launch-identities.snapshot.env"
    printf 'current_profile_g6_launch_snapshot_test=PASS\n'
}

verify_launch_identity_files() {
    local identity=$1
    (( $# == 1 )) || die 'protected launch parser requires exactly one standalone identity file'
    closed_env_validate "$identity" "$LAUNCH_SCHEMA" "$LAUNCH_KEYS" ||
        die 'protected launch identity closed-schema validation failed'
    /usr/bin/python3 - "$identity" "$LAUNCH_KEYS" "$CODE_COMMIT" \
        "$EXPECTED_G6_PREREG_BLOB" "$EXPECTED_BINARY_SHA" "$EXPECTED_BINARY_BUILD_ID" \
        "$G6_ADMISSION_UNIT" "$G6_CAMPAIGN_UNIT" "$CAMPAIGN_OUT" <<'PY'
import re, sys
from pathlib import Path

path = Path(sys.argv[1])
keys = sys.argv[2].split()
source_commit, prereg_blob, binary_sha, binary_build_id = sys.argv[3:7]
admission_unit, campaign_unit, campaign_root = sys.argv[7:10]
parsed = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())

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
for key in git40:
    if not re.fullmatch(r"[0-9a-f]{40}", parsed[key]):
        raise SystemExit(f"invalid immutable Git identity: {key}")
for key in sha256:
    if not re.fullmatch(r"[0-9a-f]{64}", parsed[key]):
        raise SystemExit(f"invalid SHA-256 identity: {key}")
for key in integers:
    if not re.fullmatch(r"0|[1-9][0-9]*", parsed[key]):
        raise SystemExit(f"invalid integer identity: {key}")
if not re.fullmatch(r"[0-9a-f]{32}", parsed["admission_invocation_id"]):
    raise SystemExit("invalid admission InvocationID")
if not re.fullmatch(r"/[A-Za-z0-9_.:@-]+(?:/[A-Za-z0-9_.:@-]+)*", parsed["admission_control_group"]):
    raise SystemExit("invalid admission control group")
if ".." in parsed["admission_control_group"]:
    raise SystemExit("unsafe admission control group")

fixed = {
    "schema": "g6-protected-launch-identities-v1",
    "source_commit": source_commit,
    "g6_prereg_blob": prereg_blob,
    "binary_a_sha256": binary_sha,
    "binary_b_sha256": binary_sha,
    "binary_a_build_id": binary_build_id,
    "binary_b_build_id": binary_build_id,
    "build_cpuset": "0-15",
    "cargo_profile_release_debug": "1",
    "cubr_threads": "4",
    "rayon_num_threads": "4",
    "omp_num_threads": "4",
    "mkl_num_threads": "4",
    "receipt_schema": "g6-prebuild-receipt-v1",
    "admission_unit": admission_unit,
    "campaign_unit": campaign_unit,
    "campaign_output_root": campaign_root,
}
for key, expected in fixed.items():
    if parsed[key] != expected:
        raise SystemExit(f"fixed launch identity mismatch: {key}")

for key, value in parsed.items():
    lowered = value.lower()
    forbidden = (
        "placeholder", "unknown", "mutable", "refs/heads", "origin/", "launch-identit",
        "cubr-new24-full-binary-" + "g" + "5-", "cubr-new24-" + "g" + "5-",
    )
    if key != "schema" and any(token in lowered for token in forbidden):
        raise SystemExit(f"placeholder, mutable reference, or G5 runtime value: {key}")
print(f"current_profile_g6_launch_identity_parser=PASS schema={parsed['schema']} keys={len(keys)}")
PY
}

persist_authenticated_admission_identity() {
    (( $# == 3 )) || die 'sealed admission identity persistence requires source, SHA, and bytes'
    local source=$1 expected_sha=$2 expected_bytes=$3
    local target=$PREFLIGHT_DIR/admission-sealed-identity-set.env
    [[ $source == "$ADMISSION_OUT/sealed-identity-set.env" ]] ||
        die 'sealed admission identity source is not the literal admission tree'
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
    printf 'current_profile_g6_remote_main_test=PASS remote_main=%s\n' "$2"
}

authenticate_campaign_scientific_identities() {
    local identity=$1 admission_root=$2 corpus_manifest=$3
    (( $# == 3 )) || die 'campaign scientific identity authentication requires identity, admission, and corpus artifacts'
    [[ $EXPECTED_MAPPER_SHA =~ ^[0-9a-f]{64}$ && $EXPECTED_MAPPER_TEST_SHA =~ ^[0-9a-f]{64}$ ]] ||
        die 'campaign scientific identity mapper constants are missing'
    /usr/bin/python3 - "$identity" "$admission_root" "$corpus_manifest" \
        "$EXPECTED_INSTRUCTION_COUNT" "$EXPECTED_MAPPER_SHA" "$EXPECTED_MAPPER_TEST_SHA" \
        "${CELLS[@]}" <<'PY'
import csv, hashlib, json, os, re, stat, sys, zlib
from pathlib import Path, PurePosixPath

identity_path, admission_root, corpus_manifest = map(Path, sys.argv[1:4])
expected_instruction_count = int(sys.argv[4])
expected_mapper_sha, expected_mapper_test_sha = sys.argv[5:7]
cell_args = sys.argv[7:]

def safe_dir(path, label):
    try:
        info = path.lstat()
    except OSError as error:
        raise SystemExit(f"unsafe campaign scientific directory: {label}") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o222:
        raise SystemExit(f"unsafe campaign scientific directory: {label}")

def read_regular(path, label, maximum):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise SystemExit(f"unsafe campaign scientific artifact: {label}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise SystemExit(f"unsafe campaign scientific artifact: {label}")
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
                raise SystemExit(f"campaign scientific artifact exceeds size bound: {label}")
        return b"".join(chunks)
    finally:
        os.close(fd)

def utf8(payload, label):
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SystemExit(f"campaign scientific artifact is not exact UTF-8: {label}") from error

def parse_json(payload, label):
    try:
        value = json.loads(utf8(payload, label))
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid campaign scientific JSON: {label}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"invalid campaign scientific JSON object: {label}")
    return value

identity_payload = read_regular(identity_path, "launch-identities", 65_536)
values = {}
for line in utf8(identity_payload, "launch-identities").splitlines():
    key, separator, value = line.partition("=")
    if (not separator or not re.fullmatch(r"[a-z][a-z0-9_]*", key) or
            not value or key in values):
        raise SystemExit("invalid campaign scientific identity source")
    values[key] = value

def compare(group, key, expected):
    if values.get(key) != str(expected):
        raise SystemExit(f"launch scientific identity mismatch: {group}:{key}")

safe_dir(admission_root, "admission-root")
map_dir = admission_root / "map"
preflight_dir = admission_root / "preflight"
safe_dir(map_dir, "map")
safe_dir(preflight_dir, "preflight")

cell_rows = []
manifest_expectations = {}
for cell in cell_args:
    fields = cell.split("|")
    if len(fields) != 8:
        raise SystemExit("invalid campaign scientific cell constant")
    corpus, filename, preset, byte_count, encode_timeout, decode_timeout, archive_sha, original_sha = fields
    if (corpus != "silesia" or not re.fullmatch(r"[a-z][a-z0-9-]*", filename) or
            preset not in {"max", "web"} or
            not all(re.fullmatch(r"[1-9][0-9]*", item) for item in
                    (byte_count, encode_timeout, decode_timeout)) or
            not all(re.fullmatch(r"[0-9a-f]{64}", item) for item in
                    (archive_sha, original_sha))):
        raise SystemExit("invalid campaign scientific cell constant")
    prefix = f"corpus_{filename}_{preset}"
    compare("corpus-row", f"{prefix}_bytes", byte_count)
    compare("corpus-row", f"{prefix}_encode_timeout_seconds", encode_timeout)
    compare("corpus-row", f"{prefix}_decode_timeout_seconds", decode_timeout)
    compare("corpus-row", f"{prefix}_archive_sha256", archive_sha)
    compare("corpus-row", f"{prefix}_original_sha256", original_sha)
    cell_rows.append((corpus, filename, "text", byte_count, original_sha))
    prior = manifest_expectations.setdefault((corpus, filename), (byte_count, original_sha))
    if prior != (byte_count, original_sha):
        raise SystemExit("inconsistent campaign scientific corpus constants")

corpus_payload = read_regular(corpus_manifest, "corpus-manifest", 1_048_576)
compare("corpus-manifest", "corpus_manifest_bytes", len(corpus_payload))
compare("corpus-manifest", "corpus_manifest_sha256", hashlib.sha256(corpus_payload).hexdigest())
corpus_lines = utf8(corpus_payload, "corpus-manifest").splitlines()
for (corpus, filename), (byte_count, original_sha) in manifest_expectations.items():
    expected_row = "\t".join((corpus, filename, "text", byte_count, original_sha))
    if sum(line == expected_row for line in corpus_lines[1:]) != 1:
        raise SystemExit(f"campaign scientific corpus manifest row mismatch: {corpus}/{filename}")

gzip_manifest_path = map_dir / "raw-stream-evidence.tsv"
gzip_manifest_payload = read_regular(gzip_manifest_path, "map-gzip-manifest", 1_048_576)
compare("map-gzip-manifest", "map_gzip_manifest_bytes", len(gzip_manifest_payload))
compare("map-gzip-manifest", "map_gzip_manifest_sha256", hashlib.sha256(gzip_manifest_payload).hexdigest())
try:
    gzip_rows = list(csv.DictReader(utf8(gzip_manifest_payload, "map-gzip-manifest").splitlines(), delimiter="\t"))
except csv.Error as error:
    raise SystemExit("invalid campaign scientific gzip manifest") from error
expected_header = ["source", "uncompressed_bytes", "uncompressed_sha256", "compressed",
                   "compressed_bytes", "compressed_sha256"]
if (not gzip_rows or list(gzip_rows[0]) != expected_header or
        any(None in row or None in row.values() for row in gzip_rows)):
    raise SystemExit("invalid campaign scientific gzip manifest")
compare("map-gzip-manifest", "map_gzip_member_count", len(gzip_rows))
compressed_names = set()
summary_payload = None
for row in gzip_rows:
    source_name, compressed_name = row["source"], row["compressed"]
    if (PurePosixPath(source_name).name != source_name or PurePosixPath(compressed_name).name != compressed_name or
            not compressed_name.endswith(".gz") or compressed_name in compressed_names or
            not re.fullmatch(r"0|[1-9][0-9]*", row["uncompressed_bytes"]) or
            not re.fullmatch(r"0|[1-9][0-9]*", row["compressed_bytes"]) or
            not re.fullmatch(r"[0-9a-f]{64}", row["uncompressed_sha256"]) or
            not re.fullmatch(r"[0-9a-f]{64}", row["compressed_sha256"])):
        raise SystemExit("invalid campaign scientific gzip manifest row")
    compressed_names.add(compressed_name)
    blob = read_regular(map_dir / compressed_name, f"map/{compressed_name}", 90_000_000)
    if (len(blob) != int(row["compressed_bytes"]) or
            hashlib.sha256(blob).hexdigest() != row["compressed_sha256"] or
            len(blob) < 10 or blob[4:8] != b"\0\0\0\0"):
        raise SystemExit(f"campaign scientific gzip evidence mismatch: {compressed_name}")
    stream = zlib.decompressobj(wbits=31)
    decoded = stream.decompress(blob, 128 * 1024 * 1024 + 1)
    if (not stream.eof or stream.unused_data or stream.unconsumed_tail or
            len(decoded) > 128 * 1024 * 1024 or
            len(decoded) != int(row["uncompressed_bytes"]) or
            hashlib.sha256(decoded).hexdigest() != row["uncompressed_sha256"]):
        raise SystemExit(f"campaign scientific gzip evidence mismatch: {compressed_name}")
    if source_name == "map-summary.json":
        if compressed_name != "map-summary.json.gz" or summary_payload is not None:
            raise SystemExit("campaign scientific map summary cardinality mismatch")
        summary_payload = decoded
if summary_payload is None:
    raise SystemExit("campaign scientific map summary is missing")

summary = parse_json(summary_payload, "map-summary")
if summary.get("schema") != "cubr-new24-g6-static-map-summary-v3":
    raise SystemExit("campaign scientific map summary schema mismatch")
reverse_index = summary.get("family_reverse_index")
if (not isinstance(reverse_index, dict) or set(reverse_index) != {"source", "emitted"} or
        not all(isinstance(reverse_index[key], dict) for key in ("source", "emitted"))):
    raise SystemExit("campaign scientific reverse-index schema mismatch")
reverse_payload = (json.dumps(reverse_index, sort_keys=True, separators=(",", ":")) + "\n").encode()
compare("map-reverse-index", "map_reverse_index_bytes", len(reverse_payload))
compare("map-reverse-index", "map_reverse_index_sha256", hashlib.sha256(reverse_payload).hexdigest())
compare("map-reverse-index", "map_reverse_row_count",
        len(reverse_index["source"]) + len(reverse_index["emitted"]))

map_manifest = parse_json(read_regular(map_dir / "map-parts-manifest.json", "map-parts-manifest", 1_048_576),
                          "map-parts-manifest")
if map_manifest.get("schema") != "cubr-new24-g6-map-parts-v1":
    raise SystemExit("campaign scientific map-parts schema mismatch")
if map_manifest.get("row_count") != expected_instruction_count:
    raise SystemExit("campaign scientific instruction count constant mismatch")
compare("map-stream", "map_instruction_row_count", map_manifest.get("row_count"))
compare("map-stream", "map_stream_bytes", map_manifest.get("full_uncompressed_bytes"))
compare("map-stream", "map_stream_sha256", map_manifest.get("full_uncompressed_sha256"))

mapping_schema = hashlib.sha256(
    f"mapper_sha256={expected_mapper_sha}\nmapper_test_sha256={expected_mapper_test_sha}\n".encode()
).hexdigest()
seal = parse_json(read_regular(map_dir / "map-admission-seal.json", "map-admission-seal", 1_048_576),
                  "map-admission-seal")
if (seal.get("schema") != "cubr-new24-g6-map-admission-seal-v1" or
        seal.get("mapping_schema_sha256") != mapping_schema or
        summary.get("mapping_schema_sha256") != mapping_schema):
    raise SystemExit("campaign scientific mapping-schema artifact mismatch")
compare("mapping-schema", "mapping_schema_sha256", mapping_schema)

sanitized_payload = read_regular(preflight_dir / "sanitized-environment-contract.txt",
                                 "sanitized-environment-contract", 65_536)
expected_sanitized = (
    "schema=g6-sanitized-environment-contract-v1\n"
    "deployment_mode=admission\n"
    "outer_user_systemd=LC_ALL,PATH,HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS\n"
    "service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS,CUBR_G6_ADMITTED_UNIT,CUBR_G6_ADMISSION_INPUTS\n"
    "child_boundary=env-i\n"
    "test_boundary=CUBR_G6_TEST_ROOT_PREFIX\n"
).encode()
if sanitized_payload != expected_sanitized:
    raise SystemExit("campaign scientific sanitized environment contract mismatch")
compare("sanitized-environment", "sanitized_env_contract_sha256",
        hashlib.sha256(sanitized_payload).hexdigest())
PY
}

self_test_campaign_scientific_identities() {
    (( $# == 5 )) ||
        die 'campaign scientific identity self-test requires identity, admission, corpus, and mapper identities'
    EXPECTED_MAPPER_SHA=$4
    EXPECTED_MAPPER_TEST_SHA=$5
    authenticate_campaign_scientific_identities "$1" "$2" "$3"
    printf 'current_profile_g6_campaign_scientific_identity_test=PASS fields=28\n'
}

authenticate_campaign_launch_inputs() {
    local parser_output actual_prereg_blob actual_identities_blob origin_main key
    local admission_identity_sha admission_identity_bytes
    local snapshot_prereg=$PREFLIGHT_DIR/launch-preregistration.snapshot.md
    local snapshot_identities=$PREFLIGHT_DIR/launch-identities.snapshot.env
    [[ $LAUNCH_IDENTITIES == "$G6_LAUNCH_IDENTITIES_SOURCE" &&
       -f $G6_PREREG_SOURCE && ! -L $G6_PREREG_SOURCE ]] ||
        die 'campaign launch sources are not the fixed instrument-checkout files'
    run_bounded 120 /usr/bin/git -C "$INSTRUMENT_REPO" fetch --quiet origin main
    LAUNCH_MAIN=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse HEAD)
    origin_main=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse origin/main)
    [[ $LAUNCH_MAIN =~ ^[0-9a-f]{40}$ && $origin_main == "$LAUNCH_MAIN" ]] ||
        die 'instrument checkout HEAD does not equal fetched origin/main'
    verify_launch_main_matches_remote "$INSTRUMENT_REPO" "$LAUNCH_MAIN" 30
    actual_prereg_blob=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$LAUNCH_MAIN:$G6_PREREG_PATH")
    actual_identities_blob=$(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$LAUNCH_MAIN:$LAUNCH_IDENTITIES_PATH")
    [[ $actual_prereg_blob == "$EXPECTED_G6_PREREG_BLOB" ]] ||
        die 'launch-main preregistration blob mismatch'
    [[ $(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" hash-object --no-filters "$G6_PREREG_SOURCE") == \
       "$actual_prereg_blob" &&
       $(run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" hash-object --no-filters "$LAUNCH_IDENTITIES") == \
       "$actual_identities_blob" ]] || die 'instrument checkout launch file differs from current main'
    LAUNCH_IDENTITIES_BLOB=$actual_identities_blob
    snapshot_launch_inputs "$G6_PREREG_SOURCE" "$LAUNCH_IDENTITIES" \
        "$snapshot_prereg" "$snapshot_identities"
    run_bounded 30 /usr/bin/git -C "$INSTRUMENT_REPO" merge-base --is-ancestor \
        "$INSTRUMENT_COMMIT" "$LAUNCH_MAIN" || die 'instrument is not ancestor of launch main'
    parser_output=$(run_bounded 30 /usr/bin/bash "${BASH_SOURCE[0]}" \
        --verify-launch-identity-files "$snapshot_identities")
    [[ $parser_output == 'current_profile_g6_launch_identity_parser=PASS schema=g6-protected-launch-identities-v1 keys=123' ]] ||
        die 'protected launch identity parser output mismatch'
    [[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_prereg") == "$EXPECTED_G6_PREREG_BLOB" ]] ||
        die 'launch preregistration blob mismatch'
    [[ $(run_bounded 30 /usr/bin/git hash-object --no-filters "$snapshot_identities") == "$LAUNCH_IDENTITIES_BLOB" ]] ||
        die 'launch identity blob mismatch'
    [[ $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value \
        "$snapshot_identities" admission_instrument_main) == "$INSTRUMENT_COMMIT" ]] ||
        die 'launch instrument commit mismatch'
    [[ $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" runner_sha256) == "$EXPECTED_RUNNER_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" runner_test_sha256) == "$EXPECTED_TEST_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" mapper_sha256) == "$EXPECTED_MAPPER_SHA" &&
       $(run_bounded 10 /usr/bin/bash "${BASH_SOURCE[0]}" --launch-identity-value "$snapshot_identities" mapper_test_sha256) == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'launch runtime asset identity mismatch'
    [[ $(run_bounded 30 /usr/bin/sha256sum -- "$RUNNER_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_RUNNER_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$RUNNER_TEST_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_TEST_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$MAPPER_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_SHA" &&
       $(run_bounded 30 /usr/bin/sha256sum -- "$MAPPER_TEST_SOURCE" | /usr/bin/awk '{print $1}') == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'installed runtime asset identity mismatch'
    admission_identity_sha=$(launch_identity_value "$snapshot_identities" admission_identity_set_sha256)
    admission_identity_bytes=$(launch_identity_value "$snapshot_identities" admission_identity_set_bytes)
    [[ $admission_identity_sha =~ ^[0-9a-f]{64}$ &&
       $admission_identity_bytes =~ ^(0|[1-9][0-9]*)$ ]] ||
        die 'launch admission identity expectation mismatch'
    [[ $(launch_identity_value "$snapshot_identities" receipt_sha256) == "$RECEIPT_SHA256" &&
       $(launch_identity_value "$snapshot_identities" receipt_bytes) == "$RECEIPT_BYTES" &&
       $(launch_identity_value "$snapshot_identities" validation_manifest_sha256) == "$VALIDATION_MANIFEST_SHA256" &&
       $(launch_identity_value "$snapshot_identities" validation_manifest_bytes) == "$VALIDATION_MANIFEST_BYTES" &&
       $(launch_identity_value "$snapshot_identities" admission_input_sha256) == "$ADMISSION_INPUT_SHA256" &&
       $(launch_identity_value "$snapshot_identities" admission_input_bytes) == "$ADMISSION_INPUT_BYTES" ]] ||
        die 'launch sealed pre-service identity mismatch'
    for key in binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 \
        binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 \
        build_cpuset cargo_build_args_sha256 cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 \
        cargo_lock_a_blob cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes \
        cargo_lock_b_sha256 cargo_profile_release_debug cargo_version cubr_threads cubrim_subtree_git_tree \
        g5_incident_manifest_blob g5_incident_manifest_bytes g5_incident_manifest_sha256 \
        g5_incident_record_blob g5_journal_canonical_blob g5_journal_canonical_bytes \
        g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256 g5_prereg_blob \
        g5_prereg_resulting_main g5_prereg_reviewed_head mkl_num_threads omp_num_threads \
        prebuild_helper_blob prebuild_helper_sha256 prebuild_test_blob prebuild_test_sha256 \
        rayon_num_threads rustc_commit rustc_version source_commit source_tree_a_git_tree \
        source_tree_a_manifest_bytes source_tree_a_manifest_sha256 source_tree_b_git_tree \
        source_tree_b_manifest_bytes source_tree_b_manifest_sha256 target_a_manifest_bytes \
        target_a_manifest_sha256 target_b_manifest_bytes target_b_manifest_sha256; do
        [[ $(launch_identity_value "$snapshot_identities" "$key") == \
           "$(closed_env_value "$PREBUILD_RECEIPT" "$key")" ]] ||
            die "launch/prebuild receipt mismatch: $key"
    done
    for key in mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256 runner_blob \
        runner_sha256 runner_test_blob runner_test_sha256 validation_helper_blob \
        validation_helper_sha256 validation_test_blob validation_test_sha256; do
        [[ $(launch_identity_value "$snapshot_identities" "$key") == \
           "$(closed_env_value "$ADMISSION_INPUTS" "$key")" ]] ||
            die "launch/admission input mismatch: $key"
    done
    [[ $(launch_identity_value "$snapshot_identities" prebuild_instrument_main) == \
       "$(closed_env_value "$PREBUILD_RECEIPT" prebuild_instrument_main)" ]] ||
        die 'launch prebuild instrument mismatch'
    printf '%s\n' "$parser_output" | write_new_stdin "$PREFLIGHT_DIR/launch-identity-parser.txt"
    persist_authenticated_admission_identity "$ADMISSION_OUT/sealed-identity-set.env" \
        "$admission_identity_sha" "$admission_identity_bytes"
    local admission_journal=$ADMISSION_OUT/preflight/journal.tsv
    local admission_manifest=$ADMISSION_OUT/evidence-sha256.tsv
    local admission_properties=$ADMISSION_OUT/preflight/systemd-contract.txt
    local admission_map_seal=$ADMISSION_OUT/map/map-admission-seal.json
    local path sha_key bytes_key
    while IFS='|' read -r path sha_key bytes_key; do
        [[ -f $path && ! -L $path ]] || die "sealed admission artifact is missing or unsafe: $path"
        [[ $(sha "$path") == "$(launch_identity_value "$snapshot_identities" "$sha_key")" &&
           $(/usr/bin/stat -c %s -- "$path") == \
               "$(launch_identity_value "$snapshot_identities" "$bytes_key")" ]] ||
            die "launch/admission artifact mismatch: $sha_key"
    done <<EOF
$PREFLIGHT_DIR/admission-sealed-identity-set.env|admission_identity_set_sha256|admission_identity_set_bytes
$admission_journal|admission_journal_sha256|admission_journal_bytes
$admission_manifest|admission_output_manifest_sha256|admission_output_manifest_bytes
$admission_properties|admission_unit_properties_sha256|admission_unit_properties_bytes
$admission_map_seal|map_admission_seal_sha256|map_admission_seal_bytes
EOF
    [[ $(/usr/bin/awk -F= '$1=="Unit" {print $2}' "$admission_properties") == \
           "$(launch_identity_value "$snapshot_identities" admission_unit)" &&
       $(/usr/bin/awk -F= '$1=="InvocationID" {print $2}' "$admission_properties") == \
           "$(launch_identity_value "$snapshot_identities" admission_invocation_id)" &&
       $(/usr/bin/awk -F= '$1=="MainPID" {print $2}' "$admission_properties") == \
           "$(launch_identity_value "$snapshot_identities" admission_main_pid)" &&
       $(/usr/bin/awk -F= '$1=="ControlGroup" {print $2}' "$admission_properties") == \
           "$(launch_identity_value "$snapshot_identities" admission_control_group)" ]] ||
        die 'launch/admission systemd identity mismatch'
    authenticate_campaign_scientific_identities "$snapshot_identities" "$ADMISSION_OUT" "$CORPUS_MANIFEST"
}

write_sanitized_environment_contract() {
local mode=$1 target=$2 mode_authority
[[ $mode == admission || $mode == campaign ]] ||
    die 'sanitized environment contract mode is invalid'
mode_authority=CUBR_G6_LAUNCH_IDENTITIES
[[ $mode == admission ]] && mode_authority=CUBR_G6_ADMISSION_INPUTS
{
  printf 'schema=g6-sanitized-environment-contract-v1\n'
  printf 'deployment_mode=%s\n' "$mode"
  printf 'outer_user_systemd=LC_ALL,PATH,HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS\n'
  printf 'service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS,CUBR_G6_ADMITTED_UNIT,%s\n' "$mode_authority"
  printf 'child_boundary=env-i\n'
  printf 'test_boundary=CUBR_G6_TEST_ROOT_PREFIX\n'
} | write_new_stdin "$target"
}

self_test_sanitized_environment_contract() {
    (( $# == 2 )) || die 'sanitized environment contract self-test requires mode and target'
    [[ $2 == /tmp/* && ! -e $2 && ! -L $2 ]] ||
        die 'sanitized environment contract self-test target is unsafe'
    write_sanitized_environment_contract "$1" "$2"
    printf 'current_profile_g6_sanitized_environment_contract_test=PASS mode=%s\n' "$1"
}

capture_g6_identity_inputs() {
/root/.cargo/bin/rustc -vV | write_new_stdin "$PREFLIGHT_DIR/rustc-version.txt"
printf '%s\n' "$(closed_env_value "$PREBUILD_RECEIPT" cargo_version)" |
  write_new_stdin "$PREFLIGHT_DIR/cargo-version.txt"
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
write_sanitized_environment_contract "$RUN_MODE" \
  "$PREFLIGHT_DIR/sanitized-environment-contract.txt"
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
            not re.fullmatch(r"g6-full-instruction-map\.part-[0-9]{5}\.tsv\.gz", name) or
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
    "preflight/mapper-help.txt", "preflight/mapper-test-runtime/current_profile_g6_map.py",
    "preflight/mapper-test-runtime/test_current_profile_g6_map.py",
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
        address.get("schema") != "cubr-new24-g6-address-smoke-v1" or
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

write_g6_admission_identity_set() {
    local root=$1 target=${2:-$1/sealed-identity-set.env}
    local instrument_tree source_tree cubrim_rs_tree runner_blob runner_test_blob
    local mapper_blob mapper_test_blob rustc_version cargo_version release_flags
    local binary_size binary_device binary_inode map_stream_sha map_manifest_sha
    local map_summary_sha map_row_count map_part_count map_seal_sha map_seal_bytes
    instrument_tree=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse "$INSTRUMENT_COMMIT^{tree}")
    source_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse 'HEAD^{tree}')
    cubrim_rs_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD:code/cubrim-rs)
    runner_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g6-run.sh")
    runner_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g6-run-test.sh")
    mapper_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current_profile_g6_map.py")
    mapper_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/test_current_profile_g6_map.py")
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
    map_seal_bytes=$(/usr/bin/stat -c %s -- "$root/map/map-admission-seal.json")
    {
        printf 'schema=g6-admission-identity-set-v1\n'
        printf 'instrument_resulting_main=%s\n' "$INSTRUMENT_COMMIT"
        printf 'instrument_tree=%s\n' "$instrument_tree"
        printf 'prebuild_instrument_main=%s\n' \
            "$(closed_env_value "$PREBUILD_RECEIPT" prebuild_instrument_main)"
        printf 'runner_blob=%s\nrunner_sha256=%s\n' "$runner_blob" "$EXPECTED_RUNNER_SHA"
        printf 'runner_test_blob=%s\nrunner_test_sha256=%s\n' "$runner_test_blob" "$EXPECTED_TEST_SHA"
        printf 'mapper_blob=%s\nmapper_sha256=%s\n' "$mapper_blob" "$EXPECTED_MAPPER_SHA"
        printf 'mapper_test_blob=%s\nmapper_test_sha256=%s\n' "$mapper_test_blob" "$EXPECTED_MAPPER_TEST_SHA"
        printf 'source_commit=%s\nsource_tree=%s\ncubrim_rs_tree=%s\n' "$CODE_COMMIT" "$source_tree" "$cubrim_rs_tree"
        printf 'receipt_sha256=%s\nreceipt_bytes=%s\n' "$RECEIPT_SHA256" "$RECEIPT_BYTES"
        printf 'validation_manifest_sha256=%s\nvalidation_manifest_bytes=%s\n' \
            "$VALIDATION_MANIFEST_SHA256" "$VALIDATION_MANIFEST_BYTES"
        printf 'admission_input_sha256=%s\nadmission_input_bytes=%s\n' \
            "$ADMISSION_INPUT_SHA256" "$ADMISSION_INPUT_BYTES"
        printf 'binary_a_sha256=%s\nbinary_a_build_id=%s\n' \
            "$(closed_env_value "$PREBUILD_RECEIPT" binary_a_sha256)" \
            "$(closed_env_value "$PREBUILD_RECEIPT" binary_a_build_id)"
        printf 'binary_b_sha256=%s\nbinary_b_build_id=%s\n' \
            "$(closed_env_value "$PREBUILD_RECEIPT" binary_b_sha256)" \
            "$(closed_env_value "$PREBUILD_RECEIPT" binary_b_build_id)"
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
        printf 'map_row_count=%s\nmap_part_count=%s\nmap_admission_seal_sha256=%s\nmap_admission_seal_bytes=%s\n' \
            "$map_row_count" "$map_part_count" "$map_seal_sha" "$map_seal_bytes"
        printf 'sanitized_env_contract_sha256=%s\n' \
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
    [[ $(/usr/bin/wc -l <"$target") == 58 ]] || die 'admission identity key count mismatch'
}

compare_g6_stable_identities() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import os, re, stat, sys

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
        "schema": "g6-admission-identity-set-v1", "performance_sample": "NO",
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
print(f"current_profile_g6_stable_identity_compare=PASS compared={len(stable)} excluded={len(excluded)}")
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
    printf 'current_profile_g6_admission_no_performance_test=PASS\n'
}

self_test_write_admission_manifest() {
    local fixture_root=$1
    [[ $fixture_root == /tmp/* && -d $fixture_root && ! -L $fixture_root ]] ||
        die 'unsafe admission manifest fixture root'
    [[ ! -e $fixture_root/preflight/admission-tree-manifest.tsv &&
       ! -L $fixture_root/preflight/admission-tree-manifest.tsv ]] ||
        die 'admission fixture manifest already exists'
    write_admission_tree_manifest "$fixture_root"
    printf 'current_profile_g6_admission_manifest_test=PASS\n'
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
        printf 'current_profile_g6_exclusive_write_test=FAIL\n'
        exit 1
    fi
    /usr/bin/chmod -R u+w -- "$root"
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g6_exclusive_write_test=PASS\n'
}

authenticate_protected_admission_manifest() {
    local root=$1
    /usr/bin/python3 - "$root" <<'PY'
import hashlib, os, re, stat, sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1])
manifest_name = "evidence-sha256.tsv"
marker_name = "TIMING-DONE.STAMP"

def relative_label(path):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)

def read_regular(path, maximum=90_000_000):
    label = relative_label(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise SystemExit(f"unsafe protected admission file: {label}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit(f"unsafe protected admission file: {label}")
        if info.st_mode & 0o222:
            raise SystemExit(f"protected admission node remains writable: {label}")
        if info.st_size > maximum:
            raise SystemExit(f"protected admission file exceeds size bound: {label}")
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
                raise SystemExit(f"protected admission file exceeds size bound: {label}")
        return b"".join(chunks)
    finally:
        os.close(fd)

try:
    root_info = root.lstat()
except OSError as error:
    raise SystemExit("unsafe protected admission root") from error
if not stat.S_ISDIR(root_info.st_mode):
    raise SystemExit("unsafe protected admission root")
if root_info.st_mode & 0o222:
    raise SystemExit("protected admission node remains writable: .")

manifest_payload = read_regular(root / manifest_name, 10_000_000)
try:
    manifest_text = manifest_payload.decode("utf-8", errors="strict")
except UnicodeDecodeError as error:
    raise SystemExit("protected admission manifest is not exact UTF-8") from error
if not manifest_text or not manifest_text.endswith("\n") or "\r" in manifest_text:
    raise SystemExit("protected admission manifest is not canonical text")

listed = {}
ordered_paths = []
for line in manifest_text.splitlines():
    fields = line.split("\t")
    if len(fields) != 3:
        raise SystemExit("protected admission manifest record is malformed")
    digest, size_text, relative = fields
    relative_path = PurePosixPath(relative)
    if (not re.fullmatch(r"[0-9a-f]{64}", digest) or
            not re.fullmatch(r"0|[1-9][0-9]*", size_text) or
            not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", relative) or
            relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts) or
            relative_path.as_posix() != relative or relative in listed or
            relative in {manifest_name, marker_name}):
        raise SystemExit("protected admission manifest record is unsafe")
    listed[relative] = (digest, int(size_text))
    ordered_paths.append(relative)
if ordered_paths != sorted(ordered_paths, key=os.fsencode):
    raise SystemExit("protected admission manifest is not path-sorted")

expected_files = set(listed) | {manifest_name, marker_name}
expected_dirs = set()
for relative in expected_files:
    parent = PurePosixPath(relative).parent
    while parent != PurePosixPath("."):
        expected_dirs.add(parent.as_posix())
        parent = parent.parent

actual_files, actual_dirs = set(), set()
for path in root.rglob("*"):
    relative = relative_label(path)
    try:
        info = path.lstat()
    except OSError as error:
        raise SystemExit(f"unsafe protected admission node: {relative}") from error
    if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise SystemExit(f"unsafe protected admission node: {relative}")
    if info.st_mode & 0o222:
        raise SystemExit(f"protected admission node remains writable: {relative}")
    if stat.S_ISDIR(info.st_mode):
        actual_dirs.add(relative)
    else:
        actual_files.add(relative)
if actual_files != expected_files or actual_dirs != expected_dirs:
    raise SystemExit("protected admission manifest file set mismatch")

for relative, expected in listed.items():
    payload = read_regular(root / relative)
    actual = (hashlib.sha256(payload).hexdigest(), len(payload))
    if actual != expected:
        raise SystemExit(f"protected admission manifest content mismatch: {relative}")
read_regular(root / marker_name, 65_536)
print(len(listed))
PY
}

self_test_authenticate_admission_manifest() {
    (( $# == 1 )) || die 'protected admission manifest self-test requires one root'
    [[ $1 == /tmp/* && -d $1 && ! -L $1 ]] ||
        die 'unsafe protected admission manifest self-test root'
    local count
    count=$(authenticate_protected_admission_manifest "$1")
    printf 'current_profile_g6_admission_manifest_auth_test=PASS files=%s\n' "$count"
}

reuse_admission_map() {
    local source=$ADMISSION_OUT/map target=$PARTIAL/map
    [[ -d $ADMISSION_OUT && ! -L $ADMISSION_OUT &&
       -d $source && ! -L $source && ! -e $target && ! -L $target ]] ||
        die 'sealed admission map is missing, unsafe, or colliding'
    authenticate_protected_admission_manifest "$ADMISSION_OUT" >/dev/null
    /usr/bin/python3 - "$source" "$target" <<'PY'
import hashlib, os, stat, sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
source_info = os.lstat(source)
if not stat.S_ISDIR(source_info.st_mode) or stat.S_ISLNK(source_info.st_mode):
    raise SystemExit("unsafe admission map root")
target.mkdir(mode=0o700)
source_rows = []
for path in sorted(source.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(source)))):
    relative = path.relative_to(source)
    info = os.lstat(path)
    destination = target / relative
    if stat.S_ISLNK(info.st_mode):
        raise SystemExit("admission map contains a symlink")
    if stat.S_ISDIR(info.st_mode):
        destination.mkdir(mode=0o700)
        source_rows.append((relative.as_posix(), "d", None, 0))
        continue
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SystemExit("admission map contains a special or multiply linked file")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256()
    payload = bytearray()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            digest.update(chunk)
    finally:
        os.close(fd)
    out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(out, view)
            if written <= 0:
                raise SystemExit("short admission map copy")
            view = view[written:]
        os.fsync(out)
    finally:
        os.close(out)
    source_rows.append((relative.as_posix(), "f", digest.hexdigest(), len(payload)))

target_rows = []
for path in sorted(target.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(target)))):
    relative = path.relative_to(target).as_posix()
    info = os.lstat(path)
    if stat.S_ISDIR(info.st_mode):
        target_rows.append((relative, "d", None, 0))
    elif stat.S_ISREG(info.st_mode):
        data = path.read_bytes()
        target_rows.append((relative, "f", hashlib.sha256(data).hexdigest(), len(data)))
    else:
        raise SystemExit("copied admission map contains a special node")
if target_rows != source_rows:
    raise SystemExit("campaign admission-map copy is not byte-identical")
for path in sorted(target.rglob("*"), key=lambda item: len(item.parts), reverse=True):
    os.chmod(path, 0o555 if path.is_dir() else 0o444, follow_symlinks=False)
os.chmod(target, 0o555)
PY
    MAP_MANIFEST=$target/map-parts-manifest.json
    [[ -f $MAP_MANIFEST && ! -L $MAP_MANIFEST &&
       -f $target/map-admission-seal.json && ! -L $target/map-admission-seal.json ]] ||
        die 'reused admission map is incomplete'
    MAP_SEAL_SHA256=$(sha "$target/map-admission-seal.json")
    MAPPING_SCHEMA_SHA256=$(json_value "$target/map-admission-seal.json" mapping_schema_sha256)
    jlog "admission_map_reused=YES seal_sha256=$MAP_SEAL_SHA256"
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
    verify_mode_unit
    authenticate_g6_pre_service_inputs
    admission "$PREFLIGHT_DIR" 1
    authenticate_validation_suite_evidence
    capture_g6_identity_inputs
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
    write_g6_admission_identity_set "$PARTIAL"
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
    printf 'current_profile_g6_self_test=PASS\n'
}

self_test_cgroup_environment() {
    local observed_unit
    observed_unit=${SYSTEMD_UNIT:-missing}
    if [[ -n ${CUBR_G6_PURE_MOCK_PARENT_CANARY+x} ]]; then
        printf 'current_profile_g6_cgroup_environment_test=FAIL canary=present unit=%s\n' "$observed_unit"
        exit 1
    fi
    printf 'current_profile_g6_cgroup_environment_test=PASS canary=absent unit=%s\n' "$observed_unit"
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
        printf 'current_profile_g6_cgroup_test=FAIL\n'
        exit 1
    fi
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g6_cgroup_test=PASS unit=mock.unit\n'
}

self_test_cgroup_live_worker() {
    local props main_pid control_group cgroup_file rc
    [[ $CGROUP_SYSTEMCTL_USER == 1 && -n $SYSTEMD_UNIT && -n ${CUBR_CGROUP_LIVE_RESULT:-} &&
       ${INVOCATION_ID:-} =~ ^[0-9a-f]{32}$ ]] ||
        die 'live cgroup worker identity is missing'
    JOURNAL=$CUBR_CGROUP_LIVE_RESULT
    CGROUP_EVIDENCE_INVOCATION_ID=$INVOCATION_ID
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
    local rc=${1:-} fixture_result=${2:-} fixture_unit=${3:-} systemd_output=${4:-}
    local export_dir=${5:-} sync_fd=${6:-} verification_error
    [[ $rc =~ ^[0-9]+$ && $fixture_unit =~ ^[A-Za-z0-9_.:@-]+[.]service$ &&
       $fixture_unit != *'..'* && -n $fixture_result && -n $systemd_output && -n $export_dir &&
       ( -z $sync_fd || $sync_fd =~ ^[0-9]+$ ) ]] ||
        die 'live fixture result verifier inputs are malformed'
    (( rc == 0 )) || die 'live fixture systemd-run status is not expected success'
    if ! verification_error=$(/usr/bin/python3 -I - "$fixture_result" "$fixture_unit" \
        "$systemd_output" "$export_dir" "$sync_fd" 2>&1 <<'PY'
import hashlib, os, re, stat, sys

result_path, unit, output_path, export_dir, sync_fd_arg = sys.argv[1:]
MAX_BYTES = 1_048_576
DESTINATIONS = (
    ("cgroup-live.tsv", result_path, "live fixture result"),
    ("systemd-run.output.txt", output_path, "live fixture systemd-run output"),
)

class VerificationError(Exception):
    pass

def identity(info):
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def open_regular(path, label):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise VerificationError(f"{label} is missing or unsafe") from error
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
        os.close(fd)
        raise VerificationError(f"{label} is missing or unsafe")
    return fd, info

def read_regular(fd, initial, label):
    chunks, total = [], 0
    while True:
        try:
            chunk = os.read(fd, min(65536, MAX_BYTES + 1 - total))
        except InterruptedError:
            continue
        except OSError as error:
            raise VerificationError(f"{label} is missing or unsafe") from error
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_BYTES:
            raise VerificationError(f"{label} is missing or unsafe")
    if identity(os.fstat(fd)) != identity(initial):
        raise VerificationError("live fixture source changed during verification")
    payload = b"".join(chunks)
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise VerificationError(f"{label} is not exact UTF-8") from error
    if not payload.endswith(b"\n") or b"\r" in payload:
        raise VerificationError(f"{label} is not canonical LF-terminated UTF-8")
    return payload, text[:-1].split("\n")

def source_changed(path, fd, initial):
    try:
        current_fd = os.fstat(fd)
        current_path = os.stat(path, follow_symlinks=False)
    except OSError:
        return True
    source_identity_changed = identity(current_fd) != identity(initial)
    source_identity_changed = source_identity_changed or identity(current_path) != identity(initial)
    return source_identity_changed

def write_all(fd, payload):
    offset = 0
    while offset < len(payload):
        try:
            written = os.write(fd, payload[offset:])
        except InterruptedError:
            continue
        if written <= 0:
            raise VerificationError("live fixture authenticated export write failed")
        offset += written

def read_all(fd, bound):
    os.lseek(fd, 0, os.SEEK_SET)
    chunks, total = [], 0
    while True:
        try:
            chunk = os.read(fd, min(65536, bound + 1 - total))
        except InterruptedError:
            continue
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > bound:
            raise VerificationError("live fixture authenticated export comparison exceeded bound")
    return b"".join(chunks)

source_fds = []
destination_fds = []
created = []
dir_fd = -1
success = False
try:
    result_fd, result_info = open_regular(result_path, "live fixture result")
    source_fds.append(result_fd)
    output_fd, output_info = open_regular(output_path, "live fixture systemd-run output")
    source_fds.append(output_fd)
    result_payload, result_lines = read_regular(result_fd, result_info, "live fixture result")
    output_payload, output_lines = read_regular(
        output_fd, output_info, "live fixture systemd-run output"
    )

    running = re.compile(
        rf"Running as unit: {re.escape(unit)}; invocation ID: (?P<invocation>[0-9a-f]{{32}})"
    )
    finished = "Finished with result: success"
    terminated = "Main processes terminated with: code=killed/status=TERM"
    optional = re.compile(
        r"(?:Service runtime|CPU time consumed|Memory peak|Memory swap peak): [ -~]+"
    )
    running_match = running.fullmatch(output_lines[0]) if output_lines else None
    if (len(output_lines) < 3 or running_match is None or output_lines[1] != finished or
            output_lines[2] != terminated or
            any(optional.fullmatch(line) is None for line in output_lines[3:])):
        raise VerificationError("live fixture systemd-run output authentication failed")
    invocation = running_match.group("invocation")

    if any("live_cgroup_guard_unexpected_return=" in line for line in result_lines):
        raise VerificationError("live cgroup guard unexpectedly returned")
    if len(result_lines) > 2:
        raise VerificationError("live fixture result contains unexpected evidence")
    if len(result_lines) != 2:
        raise VerificationError("live fixture result row order is not canonical")
    timestamp = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\t"
    new_pid = re.compile(
        timestamp + r"cgroup_new_pid=[1-9][0-9]*(?:,[1-9][0-9]*)* "
        r"control_group=(?P<cgroup>[^ ]+) invocation_id=(?P<invocation>[0-9a-f]{32})"
    )
    stop = re.compile(timestamp + rf"unit_stop_request={re.escape(unit)} scope=user")
    new_match = new_pid.fullmatch(result_lines[0])
    stop_match = stop.fullmatch(result_lines[1])
    if new_match is None or (stop.fullmatch(result_lines[0]) and new_pid.fullmatch(result_lines[1])):
        raise VerificationError("live fixture result row order is not canonical")
    if stop_match is None:
        raise VerificationError("live fixture did not request the exact fixture unit stop")
    result_invocation = new_match.group("invocation")
    if result_invocation != invocation:
        raise VerificationError("live fixture invocation evidence does not match systemd-run")
    cgroup = new_match.group("cgroup")
    components = cgroup[1:].split("/") if cgroup.startswith("/") else []
    component = re.compile(r"[A-Za-z0-9_.:@-]+")
    if (not components or "//" in cgroup or "\\" in cgroup or
            any(part in {".", ".."} or component.fullmatch(part) is None for part in components)):
        raise VerificationError("live fixture cgroup path is not canonical")
    if components[-1] != unit:
        raise VerificationError("live fixture cgroup is not bound to the exact fixture unit")

    if sync_fd_arg:
        sync_fd = int(sync_fd_arg)
        os.write(sync_fd, b"ready\n")
        if os.read(sync_fd, 32) != b"continue\n":
            raise VerificationError("live fixture source-swap test synchronization failed")
    if (source_changed(result_path, result_fd, result_info) or
            source_changed(output_path, output_fd, output_info)):
        raise VerificationError("live fixture source changed during verification")

    try:
        dir_fd = os.open(export_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as error:
        raise VerificationError("live fixture export directory is unsafe") from error
    dir_info = os.fstat(dir_fd)
    if not stat.S_ISDIR(dir_info.st_mode):
        raise VerificationError("live fixture export directory is unsafe")
    for destination, _source, _label in DESTINATIONS:
        try:
            os.stat(destination, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise VerificationError("live fixture export destination is unsafe") from error
        raise VerificationError("live fixture export destination already exists")

    metadata = []
    for destination, payload in (
        (DESTINATIONS[0][0], result_payload),
        (DESTINATIONS[1][0], output_payload),
    ):
        try:
            destination_fd = os.open(
                destination,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o444,
                dir_fd=dir_fd,
            )
        except OSError as error:
            raise VerificationError("live fixture export destination is unsafe") from error
        destination_fds.append(destination_fd)
        created.append((destination, destination_fd))
        destination_info = os.fstat(destination_fd)
        if not stat.S_ISREG(destination_info.st_mode) or destination_info.st_nlink != 1:
            raise VerificationError("live fixture export destination is unsafe")
        write_all(destination_fd, payload)
        os.fsync(destination_fd)
        if read_all(destination_fd, MAX_BYTES) != payload:
            raise VerificationError("live fixture authenticated export comparison failed")
        os.fchmod(destination_fd, 0o444)
        current_entry = os.stat(destination, dir_fd=dir_fd, follow_symlinks=False)
        current_fd = os.fstat(destination_fd)
        if ((current_entry.st_dev, current_entry.st_ino) != (current_fd.st_dev, current_fd.st_ino) or
                not stat.S_ISREG(current_fd.st_mode) or current_fd.st_nlink != 1):
            raise VerificationError("live fixture export destination changed during verification")
        metadata.extend((hashlib.sha256(payload).hexdigest(), str(len(payload))))

    if (source_changed(result_path, result_fd, result_info) or
            source_changed(output_path, output_fd, output_info)):
        raise VerificationError("live fixture source changed during verification")
    current_dir = os.stat(export_dir, follow_symlinks=False)
    if (current_dir.st_dev, current_dir.st_ino) != (dir_info.st_dev, dir_info.st_ino):
        raise VerificationError("live fixture export directory changed during verification")
    os.fsync(dir_fd)
    success = True
    print("\t".join(metadata))
except VerificationError as error:
    raise SystemExit(str(error)) from error
finally:
    if not success and dir_fd >= 0:
        for destination, destination_fd in reversed(created):
            try:
                current_entry = os.stat(destination, dir_fd=dir_fd, follow_symlinks=False)
                current_fd = os.fstat(destination_fd)
                if (current_entry.st_dev, current_entry.st_ino) == (current_fd.st_dev, current_fd.st_ino):
                    os.unlink(destination, dir_fd=dir_fd)
            except OSError:
                pass
    for fd in destination_fds:
        os.close(fd)
    if dir_fd >= 0:
        os.close(dir_fd)
    for fd in source_fds:
        os.close(fd)
PY
    ); then
        die "$verification_error"
    fi
    if [[ -n ${CUBR_G6_TEST_VERIFIER_METADATA_SUFFIX:-} ]]; then
        printf '%s\n%s\n' "$verification_error" "$CUBR_G6_TEST_VERIFIER_METADATA_SUFFIX"
    else
        printf '%s\n' "$verification_error"
    fi
}

parse_live_verifier_metadata() {
    local metadata=${1:-} pattern
    (( $# == 5 )) || die 'live result verifier metadata parser arguments are malformed'
    if [[ $metadata == *$'\n'* || $metadata == *$'\r'* ]]; then
        die 'live result verifier metadata is not exactly one canonical record'
    fi
    pattern=$'^([0-9a-f]{64})\t([1-9][0-9]*)\t([0-9a-f]{64})\t([1-9][0-9]*)$'
    [[ $metadata =~ $pattern ]] || die 'live result verifier metadata is malformed'
    printf -v "$2" '%s' "${BASH_REMATCH[1]}"
    printf -v "$3" '%s' "${BASH_REMATCH[2]}"
    printf -v "$4" '%s' "${BASH_REMATCH[3]}"
    printf -v "$5" '%s' "${BASH_REMATCH[4]}"
}

self_test_verify_cgroup_live_result() {
    local verification_metadata result_sha _result_size output_sha _output_size
    (( $# == 6 )) ||
        die 'live result self-test internal arguments are malformed'
    verification_metadata=$(verify_live_cgroup_fixture_result "$1" "$2" "$3" "$4" "$5" "$6")
    parse_live_verifier_metadata "$verification_metadata" \
        result_sha _result_size output_sha _output_size
    printf 'current_profile_g6_live_result_test=PASS result_sha256=%s test_output_sha256=%s\n' \
        "$result_sha" "$output_sha"
}

cleanup_live_cgroup_fixture_root() {
    local root=${1:-} owner=${2:-} marker root_uid root_mode marker_uid marker_links
    marker=$root/.current-profile-g6-live-owned
    [[ $root =~ ^/tmp/current-profile-g6-cgroup-live[.][A-Za-z0-9]+$ &&
       $owner =~ ^[1-9][0-9]*$ && -d $root && ! -L $root &&
       -f $marker && ! -L $marker ]] || return 1
    root_uid=$(/usr/bin/stat -Lc '%u' -- "$root")
    root_mode=$(/usr/bin/stat -Lc '%a' -- "$root")
    marker_uid=$(/usr/bin/stat -Lc '%u' -- "$marker")
    marker_links=$(/usr/bin/stat -Lc '%h' -- "$marker")
    [[ $root_uid == "$EUID" && $root_mode == 700 && $marker_uid == "$EUID" &&
       $marker_links == 1 && $(<"$marker") == "$owner" ]] || return 1
    /usr/bin/chmod -R u+w -- "$root" 2>/dev/null || return 1
    /usr/bin/rm -rf -- "$root"
    [[ ! -e $root && ! -L $root ]]
}

live_cgroup_fixture_cleanup_on_exit() {
    local rc=$?
    trap - EXIT
    if ! cleanup_live_cgroup_fixture_root \
        "$LIVE_CGROUP_FIXTURE_ROOT" "$LIVE_CGROUP_FIXTURE_OWNER"; then
        printf 'current_profile_g6=VOID reason=live fixture raw-root cleanup failed\n' >&2
        (( rc != 0 )) || rc=1
    fi
    exit "$rc"
}

self_test_cgroup_live() {
    local export_dir=${1:-}
    [[ -d $export_dir && ! -L $export_dir ]] || die 'live fixture export directory is unsafe'
    (
        local root fixture_owner owned_marker fixture_result fixture_unit runner_path systemd_output rc
        local verification_metadata result_sha _result_size output_sha _output_size
        local -a systemd_args
        root=$(/usr/bin/mktemp -d /tmp/current-profile-g6-cgroup-live.XXXXXXXXXX)
        fixture_owner=$BASHPID
        owned_marker=$root/.current-profile-g6-live-owned
        printf '%s\n' "$fixture_owner" >"$owned_marker"
        /usr/bin/chmod 0400 -- "$owned_marker"
        LIVE_CGROUP_FIXTURE_ROOT=$root
        LIVE_CGROUP_FIXTURE_OWNER=$fixture_owner
        trap live_cgroup_fixture_cleanup_on_exit EXIT
        if [[ ${CUBR_G6_TEST_FAIL_AFTER_ROOT:-0} == 1 ]]; then
            die "live fixture injected post-root failure root=$root marker=$owned_marker"
        fi
        [[ ${CUBR_G6_TEST_FAIL_AFTER_ROOT:-0} == 0 ]] ||
            die 'live fixture post-root failure selector is malformed'
        fixture_result=$root/cgroup-live.tsv
        fixture_unit=current-profile-g6-cgroup-selftest-$$.service
        runner_path=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
        systemd_output=$root/systemd-run.output.txt
        systemd_args=(
            /usr/bin/systemd-run --user --wait --collect
            --unit="$fixture_unit" --service-type=exec
            --property=Restart=no --property=KillMode=control-group
            --setenv=LC_ALL=C
            --setenv=PATH=/usr/bin:/bin
            --setenv=HOME=/root
            --setenv=XDG_RUNTIME_DIR=/run/user/0
            --setenv=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
            --setenv=CUBR_THREADS=4
            --setenv=RAYON_NUM_THREADS=4
            --setenv=OMP_NUM_THREADS=4
            --setenv=MKL_NUM_THREADS=4
            --setenv=CUBR_G6_TEST_UNIT="$fixture_unit"
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
        ! /usr/bin/grep -qF 'cubr-new24-full-binary-g6-20260811.service' "$root/systemd-run.argv" ||
            die 'live fixture argument vector contains campaign unit'
        ! /usr/bin/grep -Eq 'CUBR_ADMITTED_|INVOCATION_ID' "$root/systemd-run.argv" ||
            die 'live fixture argument vector contains admitted campaign authority'
        set +e
        "${systemd_args[@]}" >"$systemd_output" 2>&1
        rc=$?
        set -e
        verification_metadata=$(verify_live_cgroup_fixture_result "$rc" "$fixture_result" "$fixture_unit" "$systemd_output" "$export_dir")
        parse_live_verifier_metadata "$verification_metadata" \
            result_sha _result_size output_sha _output_size
        cleanup_live_cgroup_fixture_root "$root" "$fixture_owner" ||
            die 'live fixture raw-root cleanup failed'
        trap - EXIT
        printf 'current_profile_g6_cgroup_live_test=PASS result_sha256=%s test_output_sha256=%s\n' \
            "$result_sha" "$output_sha"
    )
}

self_test_cgroup_precommit() {
    local root partial publishing final late procs sentinel rc expected_stop validated_unit
    validated_unit=${SYSTEMD_UNIT:-missing}
    if [[ $validated_unit != precommit-disconnected.service ]]; then
        printf 'current_profile_g6_cgroup_precommit_test=FAIL unit=%s reason=unexpected-fixture-unit\n' "$validated_unit"
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
        printf 'current_profile_g6_cgroup_precommit_test=FAIL connected-publisher-rejected\n'
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
        printf 'current_profile_g6_cgroup_precommit_test=FAIL disconnected-publisher-accepted unit=%s\n' "$validated_unit"
        exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf -- "$root"
    printf 'current_profile_g6_cgroup_precommit_test=PASS unit=%s\n' "$validated_unit"
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
        printf 'current_profile_g6_publish_test=FAIL\n'
        exit 1
    }
    [[ -z $(/usr/bin/find "$final" -xdev -perm /0222 -print -quit) ]] || {
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
        printf 'current_profile_g6_publish_test=FAIL\n'
        exit 1
    }
    /usr/bin/chmod -R u+w "$root"
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g6_publish_test=PASS\n'
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
            printf 'current_profile_g6_publish_write_test=FAIL mode=%s\n' "$mode"; exit 1;
        }
        [[ -f $final/TIMING-DONE.STAMP ]] || {
            printf 'current_profile_g6_publish_write_test=FAIL mode=%s\n' "$mode"; exit 1;
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
        printf 'current_profile_g6_publish_write_test=FAIL mode=zero\n'; exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g6_publish_write_test=PASS\n'
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
            printf 'current_profile_g6_publish_tamper_test=FAIL mode=%s\n' "$mode"; exit 1
        fi
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
    done
    printf 'current_profile_g6_publish_tamper_test=PASS\n'
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
        printf 'current_profile_g6_timeout_tree_test=FAIL\n'
        exit 1
    fi
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g6_timeout_tree_test=PASS\n'
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
        (( rc != 0 )) || { printf 'current_profile_g6_publish_crash_test=FAIL point=%s\n' "$point"; exit 1; }
        [[ ! -e $partial/TIMING-DONE.STAMP ]] || {
            printf 'current_profile_g6_publish_crash_test=FAIL point=%s partial-marker\n' "$point"; exit 1;
        }
        accepted=0
        if [[ -f $final/TIMING-DONE.STAMP && -f $final/evidence-sha256.tsv &&
              -z $(/usr/bin/find "$final" -xdev -perm /0222 -print -quit 2>/dev/null) ]]; then
            accepted=1
        fi
        (( accepted == 0 )) || {
            printf 'current_profile_g6_publish_crash_test=FAIL point=%s accepted\n' "$point"; exit 1;
        }
        /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
        /usr/bin/rm -rf "$root"
    done
    printf 'current_profile_g6_publish_crash_test=PASS\n'
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
    (( rc != 0 )) || { printf 'current_profile_g6_hard_deadline_test=FAIL accepted\n'; exit 1; }
    [[ ! -e $final && ! -e $late ]] || {
        printf 'current_profile_g6_hard_deadline_test=FAIL final-visible\n'; exit 1;
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
        printf 'current_profile_g6_hard_deadline_test=FAIL partial-authoritative\n'; exit 1;
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
    (( rc != 0 )) || { printf 'current_profile_g6_hard_deadline_test=FAIL late-accepted\n'; exit 1; }
    [[ ! -e $final && -f $late/REJECTED-TIMING-DONE.STAMP && ! -e $late/TIMING-DONE.STAMP ]] || {
        /usr/bin/cat "$late_error" >&2
        printf 'current_profile_g6_hard_deadline_test=FAIL late-not-quarantined\n'; exit 1;
    }
    reject_and_freeze_tree "$late" "$late" "$final" \
        'late final quarantined by hard deadline self-test'
    [[ -f $late/REJECTED-TIMING-DONE.STAMP && ! -e $late/TIMING-DONE.STAMP &&
       -z $(/usr/bin/find "$late" -xdev -perm /0222 -print -quit) ]] || {
        printf 'current_profile_g6_hard_deadline_test=FAIL late-authoritative\n'; exit 1;
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
        printf 'current_profile_g6_hard_deadline_test=FAIL fallback-quarantine\n'; exit 1;
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
        printf 'current_profile_g6_hard_deadline_test=FAIL no-replace-collision\n'; exit 1
    fi
    /usr/bin/chmod -R u+w "$root" 2>/dev/null || true
    /usr/bin/rm -rf "$root"
    printf 'current_profile_g6_hard_deadline_test=PASS\n'
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
    verify_mode_unit
    authenticate_g6_pre_service_inputs
    require_deadline before-launch-authentication
    authenticate_campaign_launch_inputs
    require_deadline before-admission
    admission "$PREFLIGHT_DIR" 1
    require_deadline before-suites
    authenticate_validation_suite_evidence
    capture_g6_identity_inputs
    require_deadline before-admission-map-reuse
    reuse_admission_map
    require_deadline before-stable-identity-comparison
    write_g6_admission_identity_set "$PARTIAL"
    compare_g6_stable_identities "$PREFLIGHT_DIR/admission-sealed-identity-set.env" \
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
    --map-worker) build_full_instruction_map_worker "${@:2}" ;;
    --admission-feasibility)
        if [[ -n $ROOT_PREFIX ]]; then self_test_deployment_interface; else admission_feasibility_run; fi
        ;;
    --self-test) self_test ;;
    --self-test-mode-roots) self_test_mode_roots ;;
    --self-test-snapshot-launch-inputs) self_test_snapshot_launch_inputs "$2" "$3" "$4" ;;
    --self-test-verify-remote-main) self_test_verify_remote_main "$2" "$3" "$4" ;;
    --self-test-classify-process-snapshot) self_test_classify_process_snapshot "$2" "$3" "$4" "$5" ;;
    --self-test-authenticate-admission-manifest) self_test_authenticate_admission_manifest "$2" ;;
    --self-test-campaign-scientific-identities) self_test_campaign_scientific_identities "${@:2}" ;;
    --self-test-sanitized-environment-contract) self_test_sanitized_environment_contract "${@:2}" ;;
    --self-test-parse-remote-main) parse_remote_main_output "$2" "$3" >/dev/null ;;
    --self-test-admission-no-performance) self_test_admission_no_performance "$2" ;;
    --self-test-write-admission-manifest) self_test_write_admission_manifest "$2" ;;
    --verify-launch-identity-files) verify_launch_identity_files "$2" ;;
    --launch-identity-value) launch_identity_value "$2" "$3" ;;
    --compare-g6-stable-identities) compare_g6_stable_identities "$2" "$3" ;;
    --self-test-exclusive-writes) self_test_exclusive_writes ;;
    --self-test-cgroup-environment) self_test_cgroup_environment ;;
    --self-test-cgroup) self_test_cgroup ;;
    --self-test-cgroup-precommit) self_test_cgroup_precommit ;;
    --self-test-cgroup-live)
        (( $# == 2 )) || die 'live cgroup fixture requires exactly one export directory'
        self_test_cgroup_live "$2"
        ;;
    --self-test-verify-cgroup-live-result)
        (( $# == 6 )) ||
            die 'live result self-test requires exactly rc, result, unit, systemd output, and export directory'
        self_test_verify_cgroup_live_result \
            "$2" "$3" "$4" "$5" "$6" "${CUBR_G6_LIVE_VERIFY_SYNC_FD:-}"
        ;;
    --self-test-cgroup-live-worker) self_test_cgroup_live_worker ;;
    --self-test-publish) self_test_publish ;;
    --self-test-publish-writes) self_test_publish_writes ;;
    --self-test-publish-tamper) self_test_publish_tamper ;;
    --self-test-timeout-tree) self_test_timeout_tree ;;
    --self-test-publish-crashes) self_test_publish_crashes ;;
    --self-test-hard-deadline) self_test_hard_deadline ;;
    --finalize-worker) finalize_worker "$@" ;;
    --campaign)
        if [[ -n $ROOT_PREFIX ]]; then self_test_deployment_interface; else main_run; fi
        ;;
    *) printf 'usage: %s --admission-feasibility|--campaign (or an internal --self-test-* mode)\n' "$0" >&2; exit 2 ;;
esac
