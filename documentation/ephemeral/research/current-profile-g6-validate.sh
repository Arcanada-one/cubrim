#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export LC_ALL=C

readonly SOURCE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly EXPECTED_LOCK_SHA=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
readonly EXPECTED_BINARY_SHA=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78
readonly EXPECTED_BINARY_BUILD_ID=789119db24ae1a28a24bcc0ecbec136c7e937d9a
readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd
readonly EXPECTED_RUSTC_VERSION=1.96.1
readonly EXPECTED_CARGO_VERSION=1.96.1
readonly VALIDATION_SCHEMA=g6-validation-manifest-v1
readonly VALIDATION_KEYS='binary_build_id binary_sha256 build_cpuset campaign_artifact_count cargo_lock_bytes cargo_lock_sha256 cargo_test_release_log_bytes cargo_test_release_log_sha256 cargo_version cubr_threads instrument_main map_artifact_count mkl_num_threads omp_num_threads output_tree_manifest_bytes output_tree_manifest_sha256 perf_data_count rayon_num_threads rustc_commit rustc_version schema scheme_roundtrip_log_bytes scheme_roundtrip_log_sha256 service_count source_commit source_tree_manifest_bytes source_tree_manifest_sha256 suite_commands_sha256 target_tree_manifest_bytes target_tree_manifest_sha256 validation_helper_blob validation_helper_sha256 validation_test_blob validation_test_sha256'

readonly PROD_SOURCE=/root/cubr-new24-full-binary-g6-validation-src
readonly PROD_TARGET=/root/cubr-new24-full-binary-g6-validation-target
readonly PROD_OUTPUT=/root/cubr-new24-full-binary-g6-validation-20260811
readonly PROD_MANIFEST_PARTIAL=/root/cubr-new24-full-binary-g6-validation-manifest-20260811.partial
readonly PROD_MANIFEST_ROOT=/root/cubr-new24-full-binary-g6-validation-manifest-20260811
readonly PROD_INSTRUMENT=/root/cubr-new24-full-binary-g6-instrument
readonly PROD_PREBUILD_SOURCE=/root/cubr-new24-full-binary-g6-src-a
readonly PROD_PREBUILD_TARGET=/root/cubr-new24-full-binary-g6-target-a
readonly PROD_ADMISSION_INPUT=/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env
readonly PROD_ADMISSION_OUTPUT=/root/cubr-new24-full-binary-g6-map-dryrun-20260811
readonly PROD_CAMPAIGN_OUTPUT=/root/cubr-new24-full-binary-g6-20260811
readonly ADMISSION_UNIT=cubr-new24-full-binary-g6-admission-20260811.service
readonly CAMPAIGN_UNIT=cubr-new24-full-binary-g6-20260811.service
readonly HELPER_REL=documentation/ephemeral/research/current-profile-g6-validate.sh
readonly TEST_REL=documentation/ephemeral/research/current-profile-g6-validate-test.sh
readonly GENERATED_LOCK_REL=code/cubrim-rs/Cargo.lock
readonly MANIFEST_REL=code/cubrim-rs/Cargo.toml

die() {
    printf 'current_profile_g6_validation=NO-ATTEMPT error=%s\n' "$*" >&2
    exit 1
}

if [[ ${CUBR_G6_TEST_MODE:-} != 1 ]]; then
    while IFS='=' read -r name _value; do
        [[ $name != CUBR_G6_* ]] || die 'production mode rejects test/identity/path overrides'
    done < <(/usr/bin/env)
    TEST_MODE=0
    TEST_ROOT=
    COMMAND_DIR=
else
    TEST_MODE=1
    TEST_ROOT=${CUBR_G6_TEST_ROOT:-}
    COMMAND_DIR=${CUBR_G6_COMMAND_DIR:-}
    [[ $TEST_ROOT == /* && $TEST_ROOT != / && -d $TEST_ROOT && ! -L $TEST_ROOT ]] ||
        die 'unsafe CUBR_G6_TEST_ROOT'
    [[ $COMMAND_DIR == /* && $COMMAND_DIR != / && -d $COMMAND_DIR && ! -L $COMMAND_DIR ]] ||
        die 'unsafe CUBR_G6_COMMAND_DIR'
fi
readonly TEST_MODE TEST_ROOT COMMAND_DIR

rooted() {
    if (( TEST_MODE == 1 )); then
        printf '%s%s\n' "$TEST_ROOT" "$1"
    else
        printf '%s\n' "$1"
    fi
}

tool_path() {
    local name=$1 production=$2 candidate
    if (( TEST_MODE == 1 )); then
        candidate=$COMMAND_DIR/$name
        [[ -x $candidate && ! -L $candidate ]] || die "missing injected command: $name"
        printf '%s\n' "$candidate"
    else
        [[ -x $production && ! -L $production ]] || die "required production command unavailable: $production"
        printf '%s\n' "$production"
    fi
}

SOURCE=$(rooted "$PROD_SOURCE")
TARGET=$(rooted "$PROD_TARGET")
OUTPUT=$(rooted "$PROD_OUTPUT")
MANIFEST_PARTIAL=$(rooted "$PROD_MANIFEST_PARTIAL")
MANIFEST_ROOT=$(rooted "$PROD_MANIFEST_ROOT")
INSTRUMENT=$(rooted "$PROD_INSTRUMENT")
PREBUILD_SOURCE=$(rooted "$PROD_PREBUILD_SOURCE")
PREBUILD_TARGET=$(rooted "$PROD_PREBUILD_TARGET")
ADMISSION_INPUT=$(rooted "$PROD_ADMISSION_INPUT")
ADMISSION_OUTPUT=$(rooted "$PROD_ADMISSION_OUTPUT")
CAMPAIGN_OUTPUT=$(rooted "$PROD_CAMPAIGN_OUTPUT")
readonly SOURCE TARGET OUTPUT MANIFEST_PARTIAL MANIFEST_ROOT INSTRUMENT
readonly PREBUILD_SOURCE PREBUILD_TARGET ADMISSION_INPUT ADMISSION_OUTPUT CAMPAIGN_OUTPUT
readonly SEALED_LOCK=$PREBUILD_SOURCE/$GENERATED_LOCK_REL
readonly PREBUILD_BINARY=$PREBUILD_TARGET/release/cubrim
readonly VALIDATION_LOCK=$SOURCE/$GENERATED_LOCK_REL
readonly CARGO_MANIFEST=$SOURCE/$MANIFEST_REL
readonly RELEASE_LOG=$OUTPUT/cargo-test-release.log
readonly ROUNDTRIP_LOG=$OUTPUT/scheme-roundtrip.log
readonly OUTPUT_LOCK=$OUTPUT/generated-Cargo.lock
readonly FINAL_MANIFEST=$MANIFEST_ROOT/manifest.env

GIT=$(tool_path git /usr/bin/git)
CARGO=$(tool_path cargo /root/.cargo/bin/cargo)
RUSTC=$(tool_path rustc /root/.cargo/bin/rustc)
TASKSET=$(tool_path taskset /usr/bin/taskset)
SYSTEMCTL=$(tool_path systemctl /usr/bin/systemctl)
READELF=$(tool_path readelf /usr/bin/readelf)
SHA256SUM=$(tool_path sha256sum /usr/bin/sha256sum)
readonly GIT CARGO RUSTC TASKSET SYSTEMCTL READELF SHA256SUM
readonly CMP=/usr/bin/cmp
readonly STAT=/usr/bin/stat
readonly CHMOD=/usr/bin/chmod
readonly CP=/usr/bin/cp
readonly MKDIR=/usr/bin/mkdir
readonly RM=/usr/bin/rm
readonly MV=/usr/bin/mv

sha_file() {
    "$SHA256SUM" -- "$1" | /usr/bin/awk '{print $1}'
}

file_bytes() {
    "$STAT" -c %s -- "$1"
}

require_regular() {
    local path=$1 label=$2
    [[ -f $path && ! -L $path ]] || die "$label missing or unsafe"
    [[ $("$STAT" -c %h -- "$path") == 1 ]] || die "$label has multiple hard links"
}

require_no_write_bits() {
    local path=$1 label=$2 mode
    mode=$("$STAT" -c %a -- "$path")
    (( (8#$mode & 0222) == 0 )) || die "$label remains writable"
}

reject_unsafe_tree() {
    /usr/bin/python3 - "$1" <<'PY'
import os, re, stat, sys

root = os.fsencode(sys.argv[1])
allowed = re.compile(rb"[A-Za-z0-9._/@+=,-]+")
try:
    root_info = os.lstat(root)
except OSError as error:
    raise SystemExit(f"unsafe canonical tree root: {error}") from error
if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
    raise SystemExit("unsafe canonical tree root")
root_device = root_info.st_dev
for current, directories, files in os.walk(root, topdown=True, followlinks=False):
    names = directories + files
    for name in names:
        path = os.path.join(current, name)
        relative = os.path.relpath(path, root).replace(os.fsencode(os.sep), b"/")
        if (not allowed.fullmatch(relative) or relative.startswith(b"/") or
                b".." in relative.split(b"/")):
            raise SystemExit("unsafe canonical tree path")
        info = os.lstat(path)
        if info.st_dev != root_device:
            raise SystemExit("unsafe canonical tree crossed filesystem")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise SystemExit("unsafe canonical tree nested type")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise SystemExit("unsafe canonical tree hard link")
PY
}

canonical_tree_manifest() {
    /usr/bin/python3 - "$1" <<'PY'
import hashlib, os, re, stat, sys

root = os.fsencode(sys.argv[1])
allowed = re.compile(rb"[A-Za-z0-9._/@+=,-]+")
try:
    root_info = os.lstat(root)
except OSError as error:
    raise SystemExit(f"unsafe canonical tree root: {error}") from error
if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
    raise SystemExit("unsafe canonical tree root")
root_device = root_info.st_dev
entries = [(b"", root, root_info)]
for current, directories, files in os.walk(root, topdown=True, followlinks=False):
    directories.sort()
    files.sort()
    for name in directories + files:
        path = os.path.join(current, name)
        relative = os.path.relpath(path, root).replace(os.fsencode(os.sep), b"/")
        if (not allowed.fullmatch(relative) or relative.startswith(b"/") or
                b".." in relative.split(b"/")):
            raise SystemExit("unsafe canonical tree path")
        info = os.lstat(path)
        if info.st_dev != root_device:
            raise SystemExit("unsafe canonical tree crossed filesystem")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise SystemExit("unsafe canonical tree nested type")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise SystemExit("unsafe canonical tree hard link")
        entries.append((relative, path, info))
entries.sort(key=lambda row: row[0])
for relative, _path, info in entries:
    if info.st_mode & 0o222:
        raise SystemExit("unsafe canonical tree remains writable")
    kind = b"directory" if stat.S_ISDIR(info.st_mode) else b"regular"
    mode = f"{stat.S_IMODE(info.st_mode):04o}".encode()
    fields = (relative, kind, mode, str(info.st_uid).encode(),
              str(info.st_gid).encode(), str(info.st_size).encode())
    sys.stdout.buffer.write(b"\t".join(fields) + b"\n")
for relative, path, before in entries:
    if not stat.S_ISREG(before.st_mode):
        continue
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        identity = (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_size)
        expected = (before.st_dev, before.st_ino, before.st_mode, before.st_size)
        if identity != expected or opened.st_nlink != 1:
            raise SystemExit("unsafe canonical tree file changed during read")
        digest = hashlib.sha256()
        total = 0
        while True:
            try:
                chunk = os.read(fd, 1024 * 1024)
            except InterruptedError:
                continue
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    finally:
        os.close(fd)
    after = os.lstat(path)
    if (after.st_dev, after.st_ino, after.st_mode, after.st_size) != identity:
        raise SystemExit("unsafe canonical tree file changed after read")
    fields = (digest.hexdigest().encode(), str(total).encode(), relative)
    sys.stdout.buffer.write(b"\t".join(fields) + b"\n")
PY
}

tree_manifest_sha() {
    canonical_tree_manifest "$1" | "$SHA256SUM" | /usr/bin/awk '{print $1}'
}

tree_manifest_bytes() {
    canonical_tree_manifest "$1" | /usr/bin/wc -c | /usr/bin/tr -d '[:space:]'
}

assert_owned_paths_absent() {
    local path
    for path in "$SOURCE" "$TARGET" "$OUTPUT" "$MANIFEST_PARTIAL" "$MANIFEST_ROOT"; do
        [[ ! -e $path && ! -L $path ]] || die "owned path collision: $path"
    done
}

assert_forbidden_fixed_paths_absent() {
    local base suffix path
    [[ ! -e $ADMISSION_INPUT && ! -L $ADMISSION_INPUT ]] ||
        die "forbidden service/performance/map/campaign artifact exists: $ADMISSION_INPUT"
    for base in "$ADMISSION_OUTPUT" "$CAMPAIGN_OUTPUT"; do
        for suffix in '' .partial .publishing .late; do
            path=$base$suffix
            [[ ! -e $path && ! -L $path ]] ||
                die "forbidden service/performance/map/campaign artifact exists: $path"
        done
    done
}

assert_units_absent() {
    local unit state
    for unit in "$ADMISSION_UNIT" "$CAMPAIGN_UNIT"; do
        state=$("$SYSTEMCTL" show "$unit" -p LoadState --value)
        [[ $state == not-found ]] || die "G6 unit already exists: $unit LoadState=$state"
    done
}

assert_no_fresh_tree_artifacts() {
    /usr/bin/python3 - "$TARGET" "$OUTPUT" <<'PY'
import os, pathlib, stat, sys
for root_text in sys.argv[1:]:
    root = pathlib.Path(root_text)
    if not root.exists():
        continue
    for path in root.rglob("*"):
        info = path.lstat()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise SystemExit("performance/map/campaign artifact created: unsafe fresh-tree node")
        relative = path.relative_to(root)
        name = path.name
        if (name == "perf.data" or name.endswith(".perf.data") or
                name.endswith(".perf-stat.csv") or name == "map" or
                name.startswith("cell-") or name.startswith("campaign")):
            raise SystemExit(f"performance/map/campaign artifact created: {relative}")
PY
}

verify_toolchain() {
    local cargo_version rustc_version rustc_commit
    cargo_version=$("$CARGO" -V | /usr/bin/awk '{print $2}')
    rustc_version=$("$RUSTC" -vV | /usr/bin/awk -F': ' '$1=="release" {print $2}')
    rustc_commit=$("$RUSTC" -vV | /usr/bin/awk -F': ' '$1=="commit-hash" {print $2}')
    [[ $cargo_version == "$EXPECTED_CARGO_VERSION" &&
       $rustc_version == "$EXPECTED_RUSTC_VERSION" &&
       $rustc_commit == "$EXPECTED_RUSTC_COMMIT" ]] || die 'toolchain mismatch'
    CARGO_VERSION=$cargo_version
    RUSTC_VERSION=$rustc_version
    RUSTC_COMMIT=$rustc_commit
}

authenticate_instrument() {
    require_regular "${BASH_SOURCE[0]}" 'executed validation helper'
    require_regular "$INSTRUMENT/$TEST_REL" 'validation test'
    INSTRUMENT_MAIN=$("$GIT" -C "$INSTRUMENT" rev-parse HEAD)
    [[ $INSTRUMENT_MAIN =~ ^[0-9a-f]{40}$ ]] || die 'instrument main is malformed'
    VALIDATION_HELPER_BLOB=$("$GIT" -C "$INSTRUMENT" rev-parse "$INSTRUMENT_MAIN:$HELPER_REL")
    VALIDATION_TEST_BLOB=$("$GIT" -C "$INSTRUMENT" rev-parse "$INSTRUMENT_MAIN:$TEST_REL")
    [[ $VALIDATION_HELPER_BLOB =~ ^[0-9a-f]{40}$ && $VALIDATION_TEST_BLOB =~ ^[0-9a-f]{40}$ ]] ||
        die 'validation asset blob identity is malformed'
    VALIDATION_HELPER_SHA=$(sha_file "${BASH_SOURCE[0]}")
    VALIDATION_TEST_SHA=$(sha_file "$INSTRUMENT/$TEST_REL")
    [[ $("$GIT" -C "$INSTRUMENT" show "$INSTRUMENT_MAIN:$HELPER_REL" | "$SHA256SUM" | /usr/bin/awk '{print $1}') == "$VALIDATION_HELPER_SHA" ]] ||
        die 'executed validation helper differs from instrument blob'
    [[ $("$GIT" -C "$INSTRUMENT" show "$INSTRUMENT_MAIN:$TEST_REL" | "$SHA256SUM" | /usr/bin/awk '{print $1}') == "$VALIDATION_TEST_SHA" ]] ||
        die 'validation test differs from instrument blob'
}

authenticate_prebuild_inputs() {
    local build_id
    require_regular "$SEALED_LOCK" 'sealed Cargo.lock'
    require_regular "$PREBUILD_BINARY" 'prebuild binary'
    require_no_write_bits "$SEALED_LOCK" 'sealed Cargo.lock'
    require_no_write_bits "$PREBUILD_BINARY" 'prebuild binary'
    [[ $(sha_file "$SEALED_LOCK") == "$EXPECTED_LOCK_SHA" ]] || die 'sealed Cargo.lock sha256 mismatch'
    [[ $(sha_file "$PREBUILD_BINARY") == "$EXPECTED_BINARY_SHA" ]] || die 'prebuild binary sha256 mismatch'
    build_id=$("$READELF" -n -- "$PREBUILD_BINARY" | /usr/bin/awk '/Build ID:/ {print $3}')
    [[ $build_id == "$EXPECTED_BINARY_BUILD_ID" ]] || die 'prebuild binary build ID mismatch'
}

verify_detached_clean_source() {
    [[ $("$GIT" -C "$SOURCE" rev-parse HEAD) == "$SOURCE_COMMIT" ]] || die 'validation source commit mismatch'
    [[ -z $("$GIT" -C "$SOURCE" symbolic-ref -q HEAD || true) ]] || die 'validation source is not detached'
    [[ -z $("$GIT" -C "$SOURCE" status --porcelain=v1 --untracked-files=all --ignored=matching) ]] ||
        die 'validation source is dirty before lock install'
}

verify_lock_only_status() {
    local status
    status=$("$GIT" -C "$SOURCE" status --porcelain=v1 --untracked-files=all --ignored=matching)
    [[ $status == "!! $GENERATED_LOCK_REL" ]] || die 'generated lock is not the only validation-source change'
}

assert_suite_side_effects_known() {
    local status line path
    status=$("$GIT" -C "$SOURCE" status --porcelain=v1 --untracked-files=all --ignored=matching)
    while IFS= read -r line; do
        [[ -n $line ]] || continue
        path=${line:3}
        case $path in
            "$GENERATED_LOCK_REL"|documentation/ephemeral/research/CUBR-0028-bench.json|documentation/ephemeral/research/CUBR-0031-bench.json) ;;
            *perf.data|*.perf-stat.csv|map|map/*|cell-*|campaign*)
                die "performance/map/campaign artifact created: $path" ;;
            *) die "unexpected suite side effect: $path" ;;
        esac
    done <<<"$status"
}

restore_suite_side_effects() {
    "$GIT" -C "$SOURCE" restore --source="$SOURCE_COMMIT" --staged --worktree -- .
    "$RM" -f -- "$VALIDATION_LOCK"
    "$GIT" -C "$SOURCE" clean -ffd -- . >/dev/null
    [[ ! -e $VALIDATION_LOCK && ! -L $VALIDATION_LOCK ]] || die 'generated lock survived cleanup'
    [[ -z $("$GIT" -C "$SOURCE" status --porcelain=v1 --untracked-files=all --ignored=matching) ]] ||
        die 'validation source is not clean after suite-side-effect restore'
}

suite_commands() {
    printf '%s\n' \
        'CARGO_PROFILE_RELEASE_DEBUG=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo test --release --locked --manifest-path /root/cubr-new24-full-binary-g6-validation-src/code/cubrim-rs/Cargo.toml --target-dir /root/cubr-new24-full-binary-g6-validation-target' \
        'CARGO_PROFILE_RELEASE_DEBUG=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo test --release --locked --manifest-path /root/cubr-new24-full-binary-g6-validation-src/code/cubrim-rs/Cargo.toml --target-dir /root/cubr-new24-full-binary-g6-validation-target --test scheme_roundtrip -- --nocapture'
}

seal_tree() {
    local root=$1
    reject_unsafe_tree "$root" || die 'unsafe canonical tree'
    "$CHMOD" -R a-w -- "$root"
    canonical_tree_manifest "$root" >/dev/null || die 'unsafe canonical tree'
}

compute_manifest_values() {
    SOURCE_MANIFEST_SHA=$(tree_manifest_sha "$SOURCE")
    SOURCE_MANIFEST_BYTES=$(tree_manifest_bytes "$SOURCE")
    TARGET_MANIFEST_SHA=$(tree_manifest_sha "$TARGET")
    TARGET_MANIFEST_BYTES=$(tree_manifest_bytes "$TARGET")
    OUTPUT_MANIFEST_SHA=$(tree_manifest_sha "$OUTPUT")
    OUTPUT_MANIFEST_BYTES=$(tree_manifest_bytes "$OUTPUT")
    LOCK_BYTES=$(file_bytes "$OUTPUT_LOCK")
    RELEASE_LOG_SHA=$(sha_file "$RELEASE_LOG")
    RELEASE_LOG_BYTES=$(file_bytes "$RELEASE_LOG")
    ROUNDTRIP_LOG_SHA=$(sha_file "$ROUNDTRIP_LOG")
    ROUNDTRIP_LOG_BYTES=$(file_bytes "$ROUNDTRIP_LOG")
    SUITE_COMMANDS_SHA=$(suite_commands | "$SHA256SUM" | /usr/bin/awk '{print $1}')
}

render_manifest() {
    printf 'binary_build_id=%s\n' "$EXPECTED_BINARY_BUILD_ID"
    printf 'binary_sha256=%s\n' "$EXPECTED_BINARY_SHA"
    printf 'build_cpuset=0-15\n'
    printf 'campaign_artifact_count=0\n'
    printf 'cargo_lock_bytes=%s\n' "$LOCK_BYTES"
    printf 'cargo_lock_sha256=%s\n' "$EXPECTED_LOCK_SHA"
    printf 'cargo_test_release_log_bytes=%s\n' "$RELEASE_LOG_BYTES"
    printf 'cargo_test_release_log_sha256=%s\n' "$RELEASE_LOG_SHA"
    printf 'cargo_version=%s\n' "$CARGO_VERSION"
    printf 'cubr_threads=4\n'
    printf 'instrument_main=%s\n' "$INSTRUMENT_MAIN"
    printf 'map_artifact_count=0\n'
    printf 'mkl_num_threads=4\n'
    printf 'omp_num_threads=4\n'
    printf 'output_tree_manifest_bytes=%s\n' "$OUTPUT_MANIFEST_BYTES"
    printf 'output_tree_manifest_sha256=%s\n' "$OUTPUT_MANIFEST_SHA"
    printf 'perf_data_count=0\n'
    printf 'rayon_num_threads=4\n'
    printf 'rustc_commit=%s\n' "$RUSTC_COMMIT"
    printf 'rustc_version=%s\n' "$RUSTC_VERSION"
    printf 'schema=%s\n' "$VALIDATION_SCHEMA"
    printf 'scheme_roundtrip_log_bytes=%s\n' "$ROUNDTRIP_LOG_BYTES"
    printf 'scheme_roundtrip_log_sha256=%s\n' "$ROUNDTRIP_LOG_SHA"
    printf 'service_count=0\n'
    printf 'source_commit=%s\n' "$SOURCE_COMMIT"
    printf 'source_tree_manifest_bytes=%s\n' "$SOURCE_MANIFEST_BYTES"
    printf 'source_tree_manifest_sha256=%s\n' "$SOURCE_MANIFEST_SHA"
    printf 'suite_commands_sha256=%s\n' "$SUITE_COMMANDS_SHA"
    printf 'target_tree_manifest_bytes=%s\n' "$TARGET_MANIFEST_BYTES"
    printf 'target_tree_manifest_sha256=%s\n' "$TARGET_MANIFEST_SHA"
    printf 'validation_helper_blob=%s\n' "$VALIDATION_HELPER_BLOB"
    printf 'validation_helper_sha256=%s\n' "$VALIDATION_HELPER_SHA"
    printf 'validation_test_blob=%s\n' "$VALIDATION_TEST_BLOB"
    printf 'validation_test_sha256=%s\n' "$VALIDATION_TEST_SHA"
}

assert_closed_manifest() {
    local path=$1 expected_mode=$2
    require_regular "$path" 'validation manifest'
    [[ $("$STAT" -c %a -- "$path") == "$expected_mode" ]] || die 'validation manifest mode mismatch'
    /usr/bin/python3 - "$path" "$VALIDATION_KEYS" <<'PY'
import os, re, stat, sys
path, expected_text = sys.argv[1:]
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
try:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
        raise SystemExit("unsafe validation manifest")
    data = os.read(fd, 65537)
finally:
    os.close(fd)
if len(data) != info.st_size or not data.endswith(b"\n"):
    raise SystemExit("malformed validation manifest framing")
try:
    lines = data.decode("ascii", errors="strict").splitlines()
except UnicodeDecodeError as error:
    raise SystemExit("validation manifest is not ASCII") from error
keys, values = [], []
for line in lines:
    if line.count("=") != 1:
        raise SystemExit("malformed validation manifest row")
    key, value = line.split("=", 1)
    if (not re.fullmatch(r"[a-z][a-z0-9_]*", key) or
            not re.fullmatch(r"[A-Za-z0-9._/@+=,:-]+", value)):
        raise SystemExit("unsafe validation manifest key or value")
    keys.append(key)
    values.append(value)
expected = expected_text.split()
if keys != expected or len(keys) != 34 or len(set(keys)) != 34:
    raise SystemExit("validation manifest closed schema mismatch")
PY
    "$CMP" -s -- <(render_manifest) "$path" || die 'validation manifest authentication failed'
}

prepare_existing_manifest_authentication() {
    verify_toolchain
    authenticate_instrument
    authenticate_prebuild_inputs
    require_regular "$OUTPUT_LOCK" 'validation output generated Cargo.lock'
    require_regular "$RELEASE_LOG" 'cargo test release log'
    require_regular "$ROUNDTRIP_LOG" 'scheme roundtrip log'
    [[ $(sha_file "$OUTPUT_LOCK") == "$EXPECTED_LOCK_SHA" ]] || die 'validation output generated Cargo.lock sha256 mismatch'
    compute_manifest_values
}

test_action=${CUBR_G6_TEST_ACTION:-}
if (( TEST_MODE == 1 )) && [[ -n $test_action ]]; then
    (( $# == 0 )) || die 'test action accepts no arguments'
    case $test_action in
        emit-manifest)
            [[ ${CUBR_G6_TEST_TREE:-} == /* && ${CUBR_G6_TEST_TREE:-} != / ]] || die 'unsafe test manifest tree'
            canonical_tree_manifest "$CUBR_G6_TEST_TREE" || die 'unsafe canonical tree'
            exit 0 ;;
        verify-manifest)
            [[ ${CUBR_G6_TEST_MANIFEST:-} == /* ]] || die 'unsafe test manifest path'
            prepare_existing_manifest_authentication
            assert_closed_manifest "$CUBR_G6_TEST_MANIFEST" 444
            printf 'current_profile_g6_validation_manifest_auth=PASS\n'
            exit 0 ;;
        *) die 'unknown CUBR_G6_TEST_ACTION' ;;
    esac
fi

(( $# == 0 )) || die 'validation helper accepts no arguments'
[[ $OUTPUT_LOCK == "$OUTPUT/generated-Cargo.lock" ]] || die 'validation output lock path is not runner-compatible'
assert_owned_paths_absent
assert_forbidden_fixed_paths_absent
assert_units_absent
verify_toolchain
authenticate_instrument
authenticate_prebuild_inputs

"$GIT" clone --no-local --no-checkout "$INSTRUMENT" "$SOURCE"
"$GIT" -C "$SOURCE" checkout --detach "$SOURCE_COMMIT"
verify_detached_clean_source
require_regular "$CARGO_MANIFEST" 'validation Cargo manifest'

"$CP" -- "$SEALED_LOCK" "$VALIDATION_LOCK"
"$CHMOD" u=rw,go=r -- "$VALIDATION_LOCK"
require_regular "$VALIDATION_LOCK" 'installed Cargo.lock'
"$CMP" -s -- "$SEALED_LOCK" "$VALIDATION_LOCK" || die 'installed Cargo.lock bytes mismatch'
[[ $(sha_file "$VALIDATION_LOCK") == "$EXPECTED_LOCK_SHA" ]] || die 'installed Cargo.lock sha256 mismatch'
verify_lock_only_status

"$MKDIR" -m 0700 -- "$OUTPUT"
if ! CARGO_PROFILE_RELEASE_DEBUG=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    "$TASKSET" -c 0-15 "$CARGO" test --release --locked \
        --manifest-path "$CARGO_MANIFEST" --target-dir "$TARGET" >"$RELEASE_LOG" 2>&1; then
    die 'cargo test --release --locked failed'
fi
if ! CARGO_PROFILE_RELEASE_DEBUG=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    "$TASKSET" -c 0-15 "$CARGO" test --release --locked \
        --manifest-path "$CARGO_MANIFEST" --target-dir "$TARGET" \
        --test scheme_roundtrip -- --nocapture >"$ROUNDTRIP_LOG" 2>&1; then
    die 'cargo scheme_roundtrip suite failed'
fi

require_regular "$RELEASE_LOG" 'cargo test release log'
require_regular "$ROUNDTRIP_LOG" 'scheme roundtrip log'
[[ -d $TARGET && ! -L $TARGET ]] || die 'literal validation target was not produced'
assert_suite_side_effects_known
assert_no_fresh_tree_artifacts || die 'performance/map/campaign artifact created'
"$CP" -- "$VALIDATION_LOCK" "$OUTPUT_LOCK"
"$CHMOD" u=rw,go=r -- "$OUTPUT_LOCK"
"$CMP" -s -- "$SEALED_LOCK" "$OUTPUT_LOCK" || die 'validation output generated Cargo.lock bytes mismatch'
[[ $(sha_file "$OUTPUT_LOCK") == "$EXPECTED_LOCK_SHA" ]] || die 'validation output generated Cargo.lock sha256 mismatch'
restore_suite_side_effects

assert_forbidden_fixed_paths_absent
assert_units_absent
verify_toolchain
authenticate_instrument
authenticate_prebuild_inputs
verify_detached_clean_source
seal_tree "$SOURCE"
seal_tree "$TARGET"
seal_tree "$OUTPUT"
compute_manifest_values

assert_owned_paths_absent_for_publication() {
    [[ ! -e $MANIFEST_PARTIAL && ! -L $MANIFEST_PARTIAL && ! -e $MANIFEST_ROOT && ! -L $MANIFEST_ROOT ]] ||
        die 'owned path collision before manifest publication'
}
assert_owned_paths_absent_for_publication
"$MKDIR" -m 0700 -- "$MANIFEST_PARTIAL"
render_manifest >"$MANIFEST_PARTIAL/manifest.env"
assert_closed_manifest "$MANIFEST_PARTIAL/manifest.env" 600
"$CHMOD" 0444 -- "$MANIFEST_PARTIAL/manifest.env"
assert_closed_manifest "$MANIFEST_PARTIAL/manifest.env" 444
[[ $(/usr/bin/find "$MANIFEST_PARTIAL" -mindepth 1 -maxdepth 1 -printf '%f\n') == manifest.env ]] ||
    die 'validation manifest partial contains unexpected files'
"$CHMOD" 0500 -- "$MANIFEST_PARTIAL"

assert_forbidden_fixed_paths_absent
assert_units_absent
[[ ! -e $MANIFEST_ROOT && ! -L $MANIFEST_ROOT ]] || die 'owned path collision before final manifest rename'
"$MV" -T -n -- "$MANIFEST_PARTIAL" "$MANIFEST_ROOT"
[[ ! -e $MANIFEST_PARTIAL && ! -L $MANIFEST_PARTIAL && -d $MANIFEST_ROOT && ! -L $MANIFEST_ROOT ]] ||
    die 'no-clobber validation manifest publication failed'
[[ $("$STAT" -c %a -- "$MANIFEST_ROOT") == 500 ]] || die 'validation manifest root mode mismatch'
compute_manifest_values
assert_closed_manifest "$FINAL_MANIFEST" 444
assert_forbidden_fixed_paths_absent
assert_units_absent
printf 'current_profile_g6_validation=PASS schema=%s keys=34\n' "$VALIDATION_SCHEMA"
