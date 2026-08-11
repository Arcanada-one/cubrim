#!/usr/bin/env bash
set -euo pipefail
umask 077
export LC_ALL=C

die() {
    printf 'G6 PREBUILD NO-ATTEMPT / NO-SELECT: %s\n' "$*" >&2
    exit 1
}

on_signal() {
    local signal=$1
    trap - HUP INT TERM
    printf 'G6 PREBUILD NO-ATTEMPT / NO-SELECT: interrupted by %s\n' "$signal" >&2
    case $signal in
        HUP) exit 129 ;;
        INT) exit 130 ;;
        TERM) exit 143 ;;
    esac
}

trap 'on_signal HUP' HUP
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM

readonly TEST_MODE="${CUBR_G6_TEST_MODE:-}"
readonly -a TEST_OVERRIDE_NAMES=(
    CUBR_G6_TEST_COMMAND_DIR
    CUBR_G6_TEST_ROOT
    CUBR_G6_TEST_SOURCE_REPO
)

configure_mode() {
    local name
    if [[ -n $TEST_MODE && $TEST_MODE != 1 ]]; then
        die 'CUBR_G6_TEST_MODE must be exactly 1 or unset'
    fi
    if [[ $TEST_MODE != 1 ]]; then
        for name in "${TEST_OVERRIDE_NAMES[@]}"; do
            if [[ -v $name ]]; then
                die "production mode rejects identity/path override $name"
            fi
        done
        SOURCE_REPO=/root/cubr-new24-full-binary-g6-instrument
        ROOT_PREFIX=/root
        COMMAND_DIR=
        return
    fi
    COMMAND_DIR=${CUBR_G6_TEST_COMMAND_DIR:?test mode requires injected command directory}
    ROOT_PREFIX=${CUBR_G6_TEST_ROOT:?test mode requires sandbox root}
    SOURCE_REPO=${CUBR_G6_TEST_SOURCE_REPO:?test mode requires sandbox repository}
    [[ $COMMAND_DIR == /* && -d $COMMAND_DIR && ! -L $COMMAND_DIR ]] || die 'invalid test command directory'
    [[ $ROOT_PREFIX == /* && -d $ROOT_PREFIX && ! -L $ROOT_PREFIX ]] || die 'invalid test root'
    [[ $SOURCE_REPO == /* && -d $SOURCE_REPO && ! -L $SOURCE_REPO ]] || die 'invalid test source repository'
}

configure_commands() {
    if [[ $TEST_MODE == 1 ]]; then
        GIT=$COMMAND_DIR/git
        CARGO=$COMMAND_DIR/cargo
        RUSTC=$COMMAND_DIR/rustc
        TASKSET=$COMMAND_DIR/taskset
        CMP=$COMMAND_DIR/cmp
        READELF=$COMMAND_DIR/readelf
        SHA256SUM=$COMMAND_DIR/sha256sum
        FIND=$COMMAND_DIR/find
        STAT=$COMMAND_DIR/stat
        CHMOD=$COMMAND_DIR/chmod
        SYSTEMCTL=$COMMAND_DIR/systemctl
    else
        GIT=/usr/bin/git
        CARGO=/root/.cargo/bin/cargo
        RUSTC=/root/.cargo/bin/rustc
        TASKSET=/usr/bin/taskset
        CMP=/usr/bin/cmp
        READELF=/usr/bin/readelf
        SHA256SUM=/usr/bin/sha256sum
        FIND=/usr/bin/find
        STAT=/usr/bin/stat
        CHMOD=/usr/bin/chmod
        SYSTEMCTL=/usr/bin/systemctl
    fi
    local command
    for command in "$GIT" "$CARGO" "$RUSTC" "$TASKSET" "$CMP" "$READELF" \
        "$SHA256SUM" "$FIND" "$STAT" "$CHMOD" "$SYSTEMCTL"; do
        [[ -x $command ]] || die "required command is not executable: $command"
    done
}

configure_mode
configure_commands

readonly SOURCE_REPO ROOT_PREFIX COMMAND_DIR
readonly GIT CARGO RUSTC TASKSET CMP READELF SHA256SUM FIND STAT CHMOD SYSTEMCTL
readonly SOURCE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly RUST_VERSION=1.96.1
readonly RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd
readonly LOCK_SHA=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
readonly BINARY_SHA=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78
readonly BINARY_BUILD_ID=789119db24ae1a28a24bcc0ecbec136c7e937d9a
readonly BUILD_CPUSET=0-15
readonly CARGO_PROFILE_RELEASE_DEBUG=1
readonly CUBR_THREADS=4
readonly RAYON_NUM_THREADS=4
readonly OMP_NUM_THREADS=4
readonly MKL_NUM_THREADS=4
readonly RECEIPT_MODE=0444

if [[ $TEST_MODE == 1 ]]; then
    SRC_A="$ROOT_PREFIX/cubr-new24-full-binary-g6-src-a"
    SRC_B="$ROOT_PREFIX/cubr-new24-full-binary-g6-src-b"
    TARGET_A="$ROOT_PREFIX/cubr-new24-full-binary-g6-target-a"
    TARGET_B="$ROOT_PREFIX/cubr-new24-full-binary-g6-target-b"
    RECEIPT_ROOT="$ROOT_PREFIX/cubr-new24-full-binary-g6-prebuild-receipt-20260811"
    PARTIAL="$ROOT_PREFIX/cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial"
    MAP_ROOT="$ROOT_PREFIX/cubr-new24-full-binary-g6-map-dryrun-20260811"
    CAMPAIGN_ROOT="$ROOT_PREFIX/cubr-new24-full-binary-g6-20260811"
    ADMISSION_INPUT="$ROOT_PREFIX/cubr-new24-full-binary-g6-admission-inputs-20260811.env"
else
    SRC_A=/root/cubr-new24-full-binary-g6-src-a
    SRC_B=/root/cubr-new24-full-binary-g6-src-b
    TARGET_A=/root/cubr-new24-full-binary-g6-target-a
    TARGET_B=/root/cubr-new24-full-binary-g6-target-b
    RECEIPT_ROOT=/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811
    PARTIAL=/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial
    MAP_ROOT=/root/cubr-new24-full-binary-g6-map-dryrun-20260811
    CAMPAIGN_ROOT=/root/cubr-new24-full-binary-g6-20260811
    ADMISSION_INPUT=/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env
fi
FINAL_RECEIPT="$RECEIPT_ROOT/receipt.env"
readonly SRC_A SRC_B TARGET_A TARGET_B RECEIPT_ROOT PARTIAL FINAL_RECEIPT
readonly ADMISSION_UNIT=cubr-new24-full-binary-g6-admission-20260811.service
readonly CAMPAIGN_UNIT=cubr-new24-full-binary-g6-20260811.service
readonly MAP_ROOT CAMPAIGN_ROOT ADMISSION_INPUT

readonly G5_INCIDENT_RECORD_BLOB=55e7b405209b1b48a19cf1066ef41f4673f44607
readonly G5_INCIDENT_MANIFEST_BLOB=49fb705f5230a35e43726d4f6a333e47c5cb1b29
readonly G5_INCIDENT_MANIFEST_BYTES=261
readonly G5_INCIDENT_MANIFEST_SHA=2d8cbdf7876644a69e176e9578c2b663a12ebe1872ecb1a1048b72c77eb99b15
readonly G5_JOURNAL_RAW_BYTES=6428
readonly G5_JOURNAL_RAW_SHA=b11d33ecde790f61e679494d9e48419688a1aef0e3a979de2eb5b65556597c25
readonly G5_JOURNAL_CANONICAL_BLOB=5ea61262dacd442fdf1676a7a7613c8e5534b6a3
readonly G5_JOURNAL_CANONICAL_BYTES=6428
readonly G5_JOURNAL_CANONICAL_SHA=926fdebe5690ce450ce6970c3260c54ce37bd095241f760d2acd9931b0586e4c
readonly G5_PREREG_BLOB=5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f
readonly G5_PREREG_REVIEWED_HEAD=e4f7efe84d6478d5f0c7286873910972f87b4d68
readonly G5_PREREG_RESULTING_MAIN=c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4

readonly HELPER_PATH=documentation/ephemeral/research/current-profile-g6-prebuild.sh
readonly TEST_PATH=documentation/ephemeral/research/current-profile-g6-prebuild-test.sh
readonly G5_INCIDENT_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811.md
readonly G5_MANIFEST_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv
readonly G5_JOURNAL_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl
readonly G5_PREREG_PATH=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md

sha256() {
    "$SHA256SUM" -- "$1" | awk '{print $1}'
}

bytes() {
    "$STAT" -c %s -- "$1"
}

git_blob() {
    "$GIT" hash-object -- "$1"
}

require_equal() {
    local label=$1
    local actual=$2
    local expected=$3
    [[ $actual == "$expected" ]] || die "$label mismatch: expected $expected, got $actual"
}

assert_path_absent() {
    local path=$1
    [[ ! -e $path && ! -L $path ]] || die "owned path collision: $path"
}

assert_owned_paths_absent() {
    local path
    for path in "$SRC_A" "$SRC_B" "$TARGET_A" "$TARGET_B" "$RECEIPT_ROOT" \
        "$PARTIAL" "$FINAL_RECEIPT"; do
        assert_path_absent "$path"
    done
}

authenticate_blob() {
    local path=$1
    local expected=$2
    local actual
    actual=$("$GIT" -C "$SOURCE_REPO" rev-parse "HEAD:$path")
    require_equal "Git blob $path" "$actual" "$expected"
}

authenticate_source_repository() {
    local repository_status
    [[ -d $SOURCE_REPO && ! -L $SOURCE_REPO ]] || die 'canonical source repository is not a real directory'
    [[ -f $SOURCE_REPO/$HELPER_PATH && ! -L $SOURCE_REPO/$HELPER_PATH ]] || die 'prebuild helper is not a regular canonical file'
    [[ -f $SOURCE_REPO/$TEST_PATH && ! -L $SOURCE_REPO/$TEST_PATH ]] || die 'prebuild test is not a regular canonical file'
    repository_status=$("$GIT" -C "$SOURCE_REPO" status --porcelain=v1 --untracked-files=all)
    [[ -z $repository_status ]] || die 'canonical source repository is dirty'
    "$GIT" -C "$SOURCE_REPO" cat-file -e "$SOURCE_COMMIT^{commit}"
    authenticate_blob "$G5_INCIDENT_PATH" "$G5_INCIDENT_RECORD_BLOB"
    authenticate_blob "$G5_MANIFEST_PATH" "$G5_INCIDENT_MANIFEST_BLOB"
    authenticate_blob "$G5_JOURNAL_PATH" "$G5_JOURNAL_CANONICAL_BLOB"
    authenticate_blob "$G5_PREREG_PATH" "$G5_PREREG_BLOB"
    PREBUILD_INSTRUMENT_MAIN=$("$GIT" -C "$SOURCE_REPO" rev-parse HEAD)
    PREBUILD_HELPER_BLOB=$("$GIT" -C "$SOURCE_REPO" rev-parse "HEAD:$HELPER_PATH")
    PREBUILD_TEST_BLOB=$("$GIT" -C "$SOURCE_REPO" rev-parse "HEAD:$TEST_PATH")
    PREBUILD_HELPER_SHA=$(sha256 "$SOURCE_REPO/$HELPER_PATH")
    PREBUILD_TEST_SHA=$(sha256 "$SOURCE_REPO/$TEST_PATH")
}

verify_toolchain() {
    local cargo_output rustc_output
    cargo_output=$("$CARGO" --version)
    rustc_output=$("$RUSTC" --version --verbose)
    CARGO_VERSION=$(awk 'NR == 1 {print $2}' <<<"$cargo_output")
    RUSTC_VERSION=$(awk 'NR == 1 && $1 == "rustc" {print $2}' <<<"$rustc_output")
    RUSTC_ACTUAL_COMMIT=$(awk '$1 == "commit-hash:" {print $2}' <<<"$rustc_output")
    require_equal 'Cargo version' "$CARGO_VERSION" "$RUST_VERSION"
    require_equal 'rustc version' "$RUSTC_VERSION" "$RUST_VERSION"
    require_equal 'rustc commit' "$RUSTC_ACTUAL_COMMIT" "$RUSTC_COMMIT"
}

verify_units_not_found() {
    local unit state
    for unit in "$ADMISSION_UNIT" "$CAMPAIGN_UNIT"; do
        state=$("$SYSTEMCTL" show "$unit" --property=LoadState --value)
        require_equal "unit $unit LoadState" "$state" not-found
    done
}

assert_cloned_root() {
    local root=$1
    [[ -d $root && ! -L $root ]] || die "clone root is not a real directory: $root" # MUTANT:reject-root-symlink
    [[ -d $root/.git && ! -L $root/.git ]] || die "clone object store is not a real directory: $root/.git"
    [[ ! -e $root/.git/objects/info/alternates && ! -L $root/.git/objects/info/alternates ]] || die "clone uses object alternates: $root"
}

clone_one() {
    local root=$1
    local source_status
    "$GIT" clone --no-local --no-checkout "$SOURCE_REPO" "$root"
    assert_cloned_root "$root"
    "$GIT" -C "$root" checkout --detach "$SOURCE_COMMIT"
    require_equal "detached source commit $root" "$("$GIT" -C "$root" rev-parse HEAD)" "$SOURCE_COMMIT"
    source_status=$("$GIT" -C "$root" status --porcelain=v1 --untracked-files=all)
    [[ -z $source_status ]] || die "source tree is dirty before lock generation: $root"
    [[ ! -e $root/code/cubrim-rs/Cargo.lock && ! -L $root/code/cubrim-rs/Cargo.lock ]] || die "lock exists before generation: $root"
}

common_object_store() {
    local root=$1
    local common
    common=$("$GIT" -C "$root" rev-parse --git-common-dir)
    if [[ $common == /* ]]; then
        (cd "$common" && pwd -P)
    else
        (cd "$root/$common" && pwd -P)
    fi
}

assert_independent_object_stores() {
    local common_a common_b
    common_a=$(common_object_store "$SRC_A")
    common_b=$(common_object_store "$SRC_B")
    [[ $common_a != "$common_b" ]] || die 'source clones alias one Git object store'
}

generate_lock() {
    local root=$1
    (
        cd "$root"
        "$CARGO" generate-lockfile --manifest-path code/cubrim-rs/Cargo.toml
    )
    local status
    status=$("$GIT" -C "$root" status --porcelain=v1 --untracked-files=all --ignored=matching)
    require_equal "post-lock source status $root" "$status" '!! code/cubrim-rs/Cargo.lock'
    [[ -f $root/code/cubrim-rs/Cargo.lock && ! -L $root/code/cubrim-rs/Cargo.lock ]] || die "generated lock is not regular: $root"
}

assert_lock_identity() {
    local lock=$1
    require_equal "lock SHA-256 $lock" "$(sha256 "$lock")" "$LOCK_SHA"
    [[ $(bytes "$lock") -gt 0 ]] || die "empty lock: $lock"
}

create_private_stage() {
    mkdir -m 0700 "$PARTIAL"
    STAGE=$(mktemp -d "$PARTIAL/stage.XXXXXXXXXX")
    [[ $STAGE == "$PARTIAL"/stage.* && -d $STAGE && ! -L $STAGE ]] || die 'private staging creation failed'
    require_equal 'private staging mode' "$("$STAT" -c %a -- "$STAGE")" 700
    # MUTANT_ANCHOR:after-partial-created
}

cargo_input_paths() {
    local root=$1
    "$GIT" -C "$root" ls-tree -r --name-only HEAD | awk '
        /(^|\/)Cargo\.toml$/ || /(^|\/)build\.rs$/ ||
        /(^|\/)\.cargo\/config[^\/]*$/ || /(^|\/)rust-toolchain[^\/]*$/ {print}
    ' | LC_ALL=C sort
    printf '%s\n' code/cubrim-rs/Cargo.lock
}

write_cargo_input_manifest() {
    local root=$1
    local output=$2
    local relative file
    local paths=$output.paths
    : >"$output"
    cargo_input_paths "$root" | LC_ALL=C sort -u >"$paths"
    while IFS= read -r relative; do
        [[ $relative =~ ^[A-Za-z0-9._/@+=,-]+$ ]] || die "unsafe Cargo input path: $relative"
        file=$root/$relative
        [[ -f $file && ! -L $file ]] || die "Cargo input is not a regular file: $relative"
        printf '%s\t%s\t%s\n' "$(sha256 "$file")" "$(bytes "$file")" "$relative" >>"$output"
    done <"$paths"
}

build_one() {
    local root=$1
    local target=$2
    /usr/bin/env CARGO_PROFILE_RELEASE_DEBUG=$CARGO_PROFILE_RELEASE_DEBUG \
        CUBR_THREADS=$CUBR_THREADS RAYON_NUM_THREADS=$RAYON_NUM_THREADS \
        OMP_NUM_THREADS=$OMP_NUM_THREADS MKL_NUM_THREADS=$MKL_NUM_THREADS \
        "$TASKSET" -c "$BUILD_CPUSET" "$CARGO" build --release --locked \
        --manifest-path "$root/code/cubrim-rs/Cargo.toml" --target-dir "$target"
    [[ -d $target && ! -L $target ]] || die "target root is incomplete: $target"
    [[ -f $target/release/cubrim && ! -L $target/release/cubrim ]] || die "release binary is incomplete: $target"
}

binary_build_id() {
    local binary=$1
    local id
    id=$("$READELF" -n -- "$binary" | awk '$1 == "Build" && $2 == "ID:" {print $3; exit}')
    [[ -n $id ]] || die "ELF build ID missing: $binary"
    printf '%s\n' "$id"
}

assert_binary_identity() {
    local binary=$1
    require_equal "binary SHA-256 $binary" "$(sha256 "$binary")" "$BINARY_SHA"
    require_equal "binary build ID $binary" "$(binary_build_id "$binary")" "$BINARY_BUILD_ID"
    [[ $(bytes "$binary") -gt 0 ]] || die "empty binary: $binary"
}

assert_no_forbidden_output() {
    local hit
    hit=$("$FIND" "$TARGET_A" "$TARGET_B" \
        \( -name perf.data -o -name '*.map' -o -name '*.cell' -o \
        -name 'timing.*' -o -name 'campaign.*' \) -print -quit)
    [[ -z $hit ]] || die "forbidden prebuild output: $hit"
    local path
    for path in "$MAP_ROOT" "$CAMPAIGN_ROOT" "$ADMISSION_INPUT"; do
        [[ ! -e $path && ! -L $path ]] || die "forbidden G6 output path exists: $path"
    done
}

validate_relative_path() {
    local relative=$1
    [[ $relative =~ ^[A-Za-z0-9._/@+=,-]+$ ]] || die "unsafe tree relative path: $relative"
}

reject_tree_kind() {
    local root=$1
    local path=$2
    local relative=$3
    local kind=$4
    case $kind in
        directory|'regular file'|'regular empty file') return ;;
        'symbolic link')
            if [[ $path == "$root" ]]; then
                die "root symlink rejected: $root" # MUTANT:reject-root-symlink
                # shellcheck disable=SC2317 # Reachable when the mutation test replaces die with a no-op.
                return
            fi
            die "nested symlink rejected: $relative" # MUTANT:reject-nested-symlink
            ;;
        fifo) die "FIFO rejected: $relative" # MUTANT:reject-fifo
            ;;
        socket) die "socket rejected: $relative" # MUTANT:reject-socket
            ;;
        'block special file'|'character special file')
            die "device rejected: $relative" # MUTANT:reject-device
            ;;
        *) die "unsupported tree entry type $kind: $relative" ;;
    esac
}

collect_tree_entries() {
    local root=$1
    local output=$2
    "$FIND" "$root" -mindepth 0 -print0 >"$output"
    LC_ALL=C sort -z -o "$output" "$output"
}

validate_tree() {
    local root=$1
    local entries=$2
    local path relative kind
    while IFS= read -r -d '' path; do
        relative=${path#"$root"}
        relative=${relative#/}
        if [[ -n $relative ]]; then
            validate_relative_path "$relative" # MUTANT:validate-relpath
        fi
        kind=$("$STAT" -c %F -- "$path")
        reject_tree_kind "$root" "$path" "$relative" "$kind"
    done <"$entries"
}

write_tree_manifest() {
    local root=$1
    local output=$2
    local entries=$3
    local path relative type mode uid gid size
    validate_tree "$root" "$entries"
    : >"$output"
    mode=$("$STAT" -c %a -- "$root")
    uid=$("$STAT" -c %u -- "$root")
    gid=$("$STAT" -c %g -- "$root")
    size=$("$STAT" -c %s -- "$root")
    printf '\t%s\t%s\t%s\t%s\t%s\n' d "$mode" "$uid" "$gid" "$size" >>"$output" # MUTANT:root-row
    while IFS= read -r -d '' path; do
        [[ $path != "$root" ]] || continue
        relative=${path#"$root"/}
        if [[ -d $path ]]; then type=d; else type=f; fi
        mode=$("$STAT" -c %a -- "$path")
        uid=$("$STAT" -c %u -- "$path")
        gid=$("$STAT" -c %g -- "$path")
        size=$("$STAT" -c %s -- "$path")
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$relative" "$type" "$mode" "$uid" "$gid" "$size" >>"$output"
    done <"$entries"
    while IFS= read -r -d '' path; do
        [[ -f $path && ! -L $path ]] || continue
        relative=${path#"$root"/}
        printf '%s\t%s\t%s\n' "$(sha256 "$path")" "$(bytes "$path")" "$relative" >>"$output"
    done <"$entries"
}

seal_and_manifest() {
    local root=$1
    local output=$2
    local entries=$3
    collect_tree_entries "$root" "$entries"
    validate_tree "$root" "$entries"
    "$CHMOD" -R a-w -- "$root"
    local writable
    writable=$("$FIND" "$root" \( -type f -o -type d \) -perm /222 -print -quit)
    [[ -z $writable ]] || die "tree remains writable after sealing: $root"
    collect_tree_entries "$root" "$entries"
    write_tree_manifest "$root" "$output" "$entries"
}

expected_receipt_keys() {
    printf '%s\n' \
        binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256 \
        binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256 \
        build_cpuset campaign_artifact_count cargo_build_args_sha256 \
        cargo_inputs_manifest_bytes cargo_inputs_manifest_sha256 cargo_lock_a_blob \
        cargo_lock_a_bytes cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes \
        cargo_lock_b_sha256 cargo_profile_release_debug cargo_version cubr_threads \
        cubrim_subtree_git_tree g5_incident_manifest_blob g5_incident_manifest_bytes \
        g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob \
        g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes \
        g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main \
        g5_prereg_reviewed_head map_artifact_count mkl_num_threads omp_num_threads \
        perf_data_count prebuild_helper_blob prebuild_helper_sha256 \
        prebuild_instrument_main prebuild_test_blob prebuild_test_sha256 \
        rayon_num_threads rustc_commit rustc_version schema service_count source_commit \
        source_tree_a_git_tree source_tree_a_manifest_bytes source_tree_a_manifest_sha256 \
        source_tree_b_git_tree source_tree_b_manifest_bytes source_tree_b_manifest_sha256 \
        target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes \
        target_b_manifest_sha256
}

write_receipt() {
    local output=$1
    {
        printf 'binary_a_build_id=%s\n' "$BINARY_A_BUILD_ID"
        printf 'binary_a_bytes=%s\n' "$BINARY_A_BYTES"
        printf 'binary_a_device=%s\n' "$BINARY_A_DEVICE"
        printf 'binary_a_inode=%s\n' "$BINARY_A_INODE"
        printf 'binary_a_sha256=%s\n' "$BINARY_A_SHA"
        printf 'binary_b_build_id=%s\n' "$BINARY_B_BUILD_ID"
        printf 'binary_b_bytes=%s\n' "$BINARY_B_BYTES"
        printf 'binary_b_device=%s\n' "$BINARY_B_DEVICE"
        printf 'binary_b_inode=%s\n' "$BINARY_B_INODE"
        printf 'binary_b_sha256=%s\n' "$BINARY_B_SHA"
        printf 'build_cpuset=%s\n' "$BUILD_CPUSET"
        printf 'campaign_artifact_count=0\n'
        printf 'cargo_build_args_sha256=%s\n' "$CARGO_BUILD_ARGS_SHA"
        printf 'cargo_inputs_manifest_bytes=%s\n' "$CARGO_INPUTS_BYTES"
        printf 'cargo_inputs_manifest_sha256=%s\n' "$CARGO_INPUTS_SHA"
        printf 'cargo_lock_a_blob=%s\n' "$LOCK_A_BLOB"
        printf 'cargo_lock_a_bytes=%s\n' "$LOCK_A_BYTES"
        printf 'cargo_lock_a_sha256=%s\n' "$LOCK_A_SHA"
        printf 'cargo_lock_b_blob=%s\n' "$LOCK_B_BLOB"
        printf 'cargo_lock_b_bytes=%s\n' "$LOCK_B_BYTES"
        printf 'cargo_lock_b_sha256=%s\n' "$LOCK_B_SHA"
        printf 'cargo_profile_release_debug=%s\n' "$CARGO_PROFILE_RELEASE_DEBUG"
        printf 'cargo_version=%s\n' "$CARGO_VERSION"
        printf 'cubr_threads=%s\n' "$CUBR_THREADS"
        printf 'cubrim_subtree_git_tree=%s\n' "$CUBRIM_SUBTREE_TREE"
        printf 'g5_incident_manifest_blob=%s\n' "$G5_INCIDENT_MANIFEST_BLOB"
        printf 'g5_incident_manifest_bytes=%s\n' "$G5_INCIDENT_MANIFEST_BYTES"
        printf 'g5_incident_manifest_sha256=%s\n' "$G5_INCIDENT_MANIFEST_SHA"
        printf 'g5_incident_record_blob=%s\n' "$G5_INCIDENT_RECORD_BLOB"
        printf 'g5_journal_canonical_blob=%s\n' "$G5_JOURNAL_CANONICAL_BLOB"
        printf 'g5_journal_canonical_bytes=%s\n' "$G5_JOURNAL_CANONICAL_BYTES"
        printf 'g5_journal_canonical_sha256=%s\n' "$G5_JOURNAL_CANONICAL_SHA"
        printf 'g5_journal_raw_bytes=%s\n' "$G5_JOURNAL_RAW_BYTES"
        printf 'g5_journal_raw_sha256=%s\n' "$G5_JOURNAL_RAW_SHA"
        printf 'g5_prereg_blob=%s\n' "$G5_PREREG_BLOB"
        printf 'g5_prereg_resulting_main=%s\n' "$G5_PREREG_RESULTING_MAIN"
        printf 'g5_prereg_reviewed_head=%s\n' "$G5_PREREG_REVIEWED_HEAD"
        printf 'map_artifact_count=0\n'
        printf 'mkl_num_threads=%s\n' "$MKL_NUM_THREADS"
        printf 'omp_num_threads=%s\n' "$OMP_NUM_THREADS"
        printf 'perf_data_count=0\n'
        printf 'prebuild_helper_blob=%s\n' "$PREBUILD_HELPER_BLOB"
        printf 'prebuild_helper_sha256=%s\n' "$PREBUILD_HELPER_SHA"
        printf 'prebuild_instrument_main=%s\n' "$PREBUILD_INSTRUMENT_MAIN"
        printf 'prebuild_test_blob=%s\n' "$PREBUILD_TEST_BLOB"
        printf 'prebuild_test_sha256=%s\n' "$PREBUILD_TEST_SHA"
        printf 'rayon_num_threads=%s\n' "$RAYON_NUM_THREADS"
        printf 'rustc_commit=%s\n' "$RUSTC_ACTUAL_COMMIT"
        printf 'rustc_version=%s\n' "$RUSTC_VERSION"
        printf 'schema=g6-prebuild-receipt-v1\n'
        printf 'service_count=0\n' # MUTANT:receipt-service-count
        printf 'source_commit=%s\n' "$SOURCE_COMMIT"
        printf 'source_tree_a_git_tree=%s\n' "$SOURCE_TREE_A"
        printf 'source_tree_a_manifest_bytes=%s\n' "$SOURCE_MANIFEST_A_BYTES"
        printf 'source_tree_a_manifest_sha256=%s\n' "$SOURCE_MANIFEST_A_SHA"
        printf 'source_tree_b_git_tree=%s\n' "$SOURCE_TREE_B"
        printf 'source_tree_b_manifest_bytes=%s\n' "$SOURCE_MANIFEST_B_BYTES"
        printf 'source_tree_b_manifest_sha256=%s\n' "$SOURCE_MANIFEST_B_SHA"
        printf 'target_a_manifest_bytes=%s\n' "$TARGET_MANIFEST_A_BYTES"
        printf 'target_a_manifest_sha256=%s\n' "$TARGET_MANIFEST_A_SHA"
        printf 'target_b_manifest_bytes=%s\n' "$TARGET_MANIFEST_B_BYTES"
        printf 'target_b_manifest_sha256=%s\n' "$TARGET_MANIFEST_B_SHA"
    } >"$output"
}

validate_receipt() {
    local receipt=$1
    local actual expected line
    [[ -f $receipt && ! -L $receipt ]] || die 'receipt is not a regular file'
    [[ $(wc -l <"$receipt") -eq 62 ]] || die 'receipt does not contain exactly 62 rows'
    while IFS= read -r line; do
        [[ $line =~ ^[a-z0-9_]+=[A-Za-z0-9._/@+=,:-]+$ ]] || die "malformed receipt row: $line"
    done <"$receipt"
    actual=$(cut -d= -f1 "$receipt")
    expected=$(expected_receipt_keys)
    [[ $actual == "$expected" ]] || die 'receipt key set is unknown, duplicate, missing, or unsorted'
}

publish_receipt() {
    local publish_dir
    publish_dir=$(mktemp -d "$PARTIAL/publish.XXXXXXXXXX")
    [[ $publish_dir == "$PARTIAL"/publish.* && -d $publish_dir && ! -L $publish_dir ]] || die 'private receipt staging creation failed'
    write_receipt "$publish_dir/receipt.env"
    "$CHMOD" "$RECEIPT_MODE" -- "$publish_dir/receipt.env"
    require_equal 'staged receipt mode' "$("$STAT" -c %a -- "$publish_dir/receipt.env")" "${RECEIPT_MODE#0}"
    validate_receipt "$publish_dir/receipt.env"
    [[ $STAGE == "$PARTIAL"/stage.* && -d $STAGE && ! -L $STAGE ]] || die 'unsafe work-stage cleanup target'
    /bin/rm -rf --one-file-system -- "$STAGE"
    mv -- "$publish_dir/receipt.env" "$PARTIAL/receipt.env"
    rmdir "$publish_dir"
    trap '' HUP INT TERM
    mv -Tn -- "$PARTIAL" "$RECEIPT_ROOT"
    [[ ! -e $PARTIAL && ! -L $PARTIAL ]] || die 'no-clobber receipt publication refused a collision'
}

capture_build_args_identity() {
    local args=$STAGE/cargo-build-args.bin
    printf '%s\0' "$TASKSET" -c "$BUILD_CPUSET" "$CARGO" build --release --locked \
        --manifest-path '<source>/code/cubrim-rs/Cargo.toml' --target-dir '<target>' >"$args"
    CARGO_BUILD_ARGS_SHA=$(sha256 "$args")
}

capture_runtime_identities() {
    local binary_a=$TARGET_A/release/cubrim
    local binary_b=$TARGET_B/release/cubrim
    LOCK_A_SHA=$(sha256 "$SRC_A/code/cubrim-rs/Cargo.lock")
    LOCK_B_SHA=$(sha256 "$SRC_B/code/cubrim-rs/Cargo.lock")
    LOCK_A_BYTES=$(bytes "$SRC_A/code/cubrim-rs/Cargo.lock")
    LOCK_B_BYTES=$(bytes "$SRC_B/code/cubrim-rs/Cargo.lock")
    LOCK_A_BLOB=$(git_blob "$SRC_A/code/cubrim-rs/Cargo.lock")
    LOCK_B_BLOB=$(git_blob "$SRC_B/code/cubrim-rs/Cargo.lock")
    BINARY_A_SHA=$(sha256 "$binary_a")
    BINARY_B_SHA=$(sha256 "$binary_b")
    BINARY_A_BYTES=$(bytes "$binary_a")
    BINARY_B_BYTES=$(bytes "$binary_b")
    BINARY_A_BUILD_ID=$(binary_build_id "$binary_a")
    BINARY_B_BUILD_ID=$(binary_build_id "$binary_b")
    BINARY_A_DEVICE=$("$STAT" -c %d -- "$binary_a")
    BINARY_B_DEVICE=$("$STAT" -c %d -- "$binary_b")
    BINARY_A_INODE=$("$STAT" -c %i -- "$binary_a")
    BINARY_B_INODE=$("$STAT" -c %i -- "$binary_b")
    SOURCE_TREE_A=$("$GIT" -C "$SRC_A" rev-parse 'HEAD^{tree}')
    SOURCE_TREE_B=$("$GIT" -C "$SRC_B" rev-parse 'HEAD^{tree}')
    CUBRIM_SUBTREE_TREE=$("$GIT" -C "$SRC_A" rev-parse HEAD:code/cubrim-rs)
}

seal_all_trees() {
    seal_and_manifest "$SRC_A" "$STAGE/source-tree-a-manifest.tsv" "$STAGE/source-tree-a.entries"
    seal_and_manifest "$SRC_B" "$STAGE/source-tree-b-manifest.tsv" "$STAGE/source-tree-b.entries"
    seal_and_manifest "$TARGET_A" "$STAGE/target-a-manifest.tsv" "$STAGE/target-a.entries"
    seal_and_manifest "$TARGET_B" "$STAGE/target-b-manifest.tsv" "$STAGE/target-b.entries"
    SOURCE_MANIFEST_A_SHA=$(sha256 "$STAGE/source-tree-a-manifest.tsv")
    SOURCE_MANIFEST_B_SHA=$(sha256 "$STAGE/source-tree-b-manifest.tsv")
    TARGET_MANIFEST_A_SHA=$(sha256 "$STAGE/target-a-manifest.tsv")
    TARGET_MANIFEST_B_SHA=$(sha256 "$STAGE/target-b-manifest.tsv")
    SOURCE_MANIFEST_A_BYTES=$(bytes "$STAGE/source-tree-a-manifest.tsv")
    SOURCE_MANIFEST_B_BYTES=$(bytes "$STAGE/source-tree-b-manifest.tsv")
    TARGET_MANIFEST_A_BYTES=$(bytes "$STAGE/target-a-manifest.tsv")
    TARGET_MANIFEST_B_BYTES=$(bytes "$STAGE/target-b-manifest.tsv")
}

main() {
    assert_owned_paths_absent # MUTANT:collision-gate
    authenticate_source_repository
    verify_toolchain
    verify_units_not_found
    clone_one "$SRC_A"
    clone_one "$SRC_B"
    assert_independent_object_stores # MUTANT:independent-object-stores
    generate_lock "$SRC_A"
    generate_lock "$SRC_B"
    assert_lock_identity "$SRC_A/code/cubrim-rs/Cargo.lock"
    assert_lock_identity "$SRC_B/code/cubrim-rs/Cargo.lock"
    "$CMP" -- "$SRC_A/code/cubrim-rs/Cargo.lock" "$SRC_B/code/cubrim-rs/Cargo.lock" # MUTANT:cmp-lock
    create_private_stage
    write_cargo_input_manifest "$SRC_A" "$STAGE/cargo-inputs-a.tsv"
    write_cargo_input_manifest "$SRC_B" "$STAGE/cargo-inputs-b.tsv"
    CARGO_INPUTS_SHA=$(sha256 "$STAGE/cargo-inputs-a.tsv")
    require_equal 'Cargo input manifests' "$(sha256 "$STAGE/cargo-inputs-b.tsv")" "$CARGO_INPUTS_SHA"
    CARGO_INPUTS_BYTES=$(bytes "$STAGE/cargo-inputs-a.tsv")
    require_equal 'Cargo input manifest bytes' "$(bytes "$STAGE/cargo-inputs-b.tsv")" "$CARGO_INPUTS_BYTES"
    capture_build_args_identity
    build_one "$SRC_A" "$TARGET_A"
    build_one "$SRC_B" "$TARGET_B"
    assert_no_forbidden_output # MUTANT:no-forbidden-output
    assert_binary_identity "$TARGET_A/release/cubrim"
    assert_binary_identity "$TARGET_B/release/cubrim"
    "$CMP" -- "$TARGET_A/release/cubrim" "$TARGET_B/release/cubrim" # MUTANT:cmp-binary
    require_equal 'binary byte count' "$(bytes "$TARGET_A/release/cubrim")" "$(bytes "$TARGET_B/release/cubrim")"
    capture_runtime_identities
    seal_all_trees
    assert_no_forbidden_output # MUTANT:no-forbidden-output
    publish_receipt
}

main "$@"
