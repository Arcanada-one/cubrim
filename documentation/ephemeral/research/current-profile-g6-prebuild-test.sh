#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly TEST_DIR
readonly DEFAULT_SCRIPT="$TEST_DIR/current-profile-g6-prebuild.sh"
readonly SCRIPT_TEMPLATE="${CUBR_G6_SCRIPT_UNDER_TEST:-$DEFAULT_SCRIPT}"
readonly SOURCE_COMMIT=830a9a31deb00926a97f3fa5bd74f58003573fc0
readonly LOCK_SHA=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9
readonly BINARY_SHA=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78
readonly BUILD_ID=789119db24ae1a28a24bcc0ecbec136c7e937d9a

pass_count=0
fail_count=0

report_test() {
    local name=$1
    shift
    local output status
    set +e
    output=$( {
        set -euo pipefail
        "$@"
    } 2>&1 )
    status=$?
    set -e
    if [[ $status -eq 0 ]]; then
        pass_count=$((pass_count + 1))
        printf 'ok %d - %s\n' "$((pass_count + fail_count))" "$name"
    else
        fail_count=$((fail_count + 1))
        printf 'not ok %d - %s\n' "$((pass_count + fail_count))" "$name"
        if [[ -n "$output" ]]; then
            printf '%s\n' "$output" | sed 's/^/  /'
        fi
    fi
}

expected_keys() {
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

write_mock_dispatcher() {
    cat >"$MOCK_BIN/mock-tool" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
tool=${0##*/}
printf '%s' "$tool" >>"$MOCK_STATE/commands.log"
printf '|%q' "$@" >>"$MOCK_STATE/commands.log"
if [[ $tool == cargo && ${1:-} == build ]]; then
    printf '|CARGO_PROFILE_RELEASE_DEBUG=%q|CUBR_THREADS=%q|RAYON_NUM_THREADS=%q|OMP_NUM_THREADS=%q|MKL_NUM_THREADS=%q' \
        "${CARGO_PROFILE_RELEASE_DEBUG:-}" "${CUBR_THREADS:-}" "${RAYON_NUM_THREADS:-}" \
        "${OMP_NUM_THREADS:-}" "${MKL_NUM_THREADS:-}" >>"$MOCK_STATE/commands.log"
fi
printf '\n' >>"$MOCK_STATE/commands.log"

inject_clone_entry() {
    local dest=$1
    case ${MOCK_INJECT_KIND:-none} in
        none) ;;
        root_symlink)
            link_target="$MOCK_STATE/root-link-target-${dest##*-}"
            mv "$dest" "$link_target"
            ln -s "$link_target" "$dest"
            ;;
        nested_symlink) ln -s code "$dest/nested-link" ;;
        fifo) mkfifo "$dest/nested-fifo" ;;
        socket)
            /usr/bin/python3 -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.close()' \
                "$dest/nested-socket"
            ;;
        device) : >"$dest/device-node" ;;
        unsafe) : >"$dest/unsafe path" ;;
        nonascii) : >"$dest/unsafe-µ" ;;
        control) printf -v bad 'unsafe\001path'; : >"$dest/$bad" ;;
        *) exit 98 ;;
    esac
}

case $tool in
    git)
        if [[ ${1:-} == clone ]]; then
            dest=${!#}
            mkdir -p "$dest/.git/objects/info" "$dest/code/cubrim-rs/fuzz" \
                "$dest/code/cubrim-rs" "$dest/.cargo"
            printf '[package]\nname="cubrim"\nversion="0.0.0"\n' >"$dest/code/cubrim-rs/Cargo.toml"
            printf '[package]\nname="fuzz"\nversion="0.0.0"\n' >"$dest/code/cubrim-rs/fuzz/Cargo.toml"
            printf 'fn main() {}\n' >"$dest/code/cubrim-rs/build.rs"
            printf '[build]\ntarget-dir="ignored"\n' >"$dest/.cargo/config.toml"
            printf '1.96.1\n' >"$dest/rust-toolchain.toml"
            inject_clone_entry "$dest"
            exit 0
        fi
        if [[ ${1:-} == hash-object ]]; then
            exec /usr/bin/git "$@"
        fi
        if [[ ${1:-} == -C ]]; then
            repo=$2
            shift 2
            case ${1:-} in
                cat-file) exit 0 ;;
                checkout) exit 0 ;;
                status)
                    if [[ -f "$repo/code/cubrim-rs/Cargo.lock" ]]; then
                        if [[ ${MOCK_POST_STATUS:-expected} == expected ]]; then
                            printf '!! code/cubrim-rs/Cargo.lock\n'
                        else
                            printf '%s\n' "$MOCK_POST_STATUS"
                        fi
                    elif [[ ${MOCK_DIRTY_BEFORE_LOCK:-0} == 1 ]]; then
                        printf '?? dirty-before-lock\n'
                    fi
                    exit 0
                    ;;
                ls-tree)
                    printf '%s\n' .cargo/config.toml code/cubrim-rs/Cargo.toml \
                        code/cubrim-rs/build.rs code/cubrim-rs/fuzz/Cargo.toml \
                        rust-toolchain.toml
                    exit 0
                    ;;
                rev-parse)
                    expr=${2:-}
                    if [[ $repo == "$MOCK_SOURCE_REPO" ]]; then
                        case $expr in
                            HEAD) printf '%s\n' 1111111111111111111111111111111111111111 ;;
                            HEAD:documentation/ephemeral/research/current-profile-g6-prebuild.sh)
                                printf '%s\n' 2222222222222222222222222222222222222222 ;;
                            HEAD:documentation/ephemeral/research/current-profile-g6-prebuild-test.sh)
                                printf '%s\n' 3333333333333333333333333333333333333333 ;;
                            HEAD:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811.md)
                                printf '%s\n' 55e7b405209b1b48a19cf1066ef41f4673f44607 ;;
                            HEAD:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv)
                                printf '%s\n' 49fb705f5230a35e43726d4f6a333e47c5cb1b29 ;;
                            HEAD:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl)
                                printf '%s\n' 5ea61262dacd442fdf1676a7a7613c8e5534b6a3 ;;
                            HEAD:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md)
                                printf '%s\n' 5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f ;;
                            *) exit 97 ;;
                        esac
                    else
                        case $expr in
                            HEAD) printf '%s\n' 830a9a31deb00926a97f3fa5bd74f58003573fc0 ;;
                            'HEAD^{tree}') printf '%s\n' 4444444444444444444444444444444444444444 ;;
                            HEAD:code/cubrim-rs) printf '%s\n' dc77e3b4a6b12913e4df065d5cdb19694ed83f54 ;;
                            --git-common-dir)
                                if [[ ${MOCK_ALIAS_OBJECTS:-0} == 1 && $repo == *-src-b ]]; then
                                    printf '%s\n' ../cubr-new24-full-binary-g6-src-a/.git
                                else
                                    printf '%s\n' .git
                                fi
                                ;;
                            *) exit 96 ;;
                        esac
                    fi
                    exit 0
                    ;;
            esac
        fi
        exit 95
        ;;
    cargo)
        if [[ ${1:-} == --version ]]; then
            printf 'cargo 1.96.1 (mock 2026-01-01)\n'
            exit 0
        fi
        if [[ ${1:-} == generate-lockfile ]]; then
            if [[ ${MOCK_PAUSE_CARGO:-0} == 1 ]]; then
                : >"$MOCK_STATE/cargo-paused"
                while [[ ! -e $MOCK_STATE/release-cargo ]]; do sleep 0.05; done
            fi
            if [[ ${MOCK_FAIL_COMMAND:-} == cargo_generate ]]; then exit 41; fi
            manifest=${3:?}
            lock=${manifest%/Cargo.toml}/Cargo.lock
            if [[ ${MOCK_LOCK_MISMATCH:-0} == 1 && $PWD == *-src-b ]]; then
                printf 'mismatched-lock\n' >"$lock"
            else
                printf 'frozen-lock\n' >"$lock"
            fi
            exit 0
        fi
        if [[ ${1:-} == build ]]; then
            if [[ ${MOCK_FAIL_COMMAND:-} == cargo_build ]]; then exit 42; fi
            target=
            while (($#)); do
                if [[ $1 == --target-dir ]]; then target=$2; shift 2; continue; fi
                shift
            done
            mkdir -p "$target/release"
            if [[ ${MOCK_INCOMPLETE_TARGET:-0} != 1 || $target == *-target-b ]]; then
                if [[ ${MOCK_BINARY_MISMATCH:-0} == 1 && $target == *-target-b ]]; then
                    printf 'mismatched-binary\n' >"$target/release/cubrim"
                else
                    printf 'frozen-binary\n' >"$target/release/cubrim"
                fi
                chmod 0755 "$target/release/cubrim"
            fi
            if [[ ${MOCK_INJECT_PERF:-0} == 1 ]]; then : >"$target/perf.data"; fi
            exit 0
        fi
        exit 94
        ;;
    rustc)
        printf 'rustc 1.96.1 (31fca3adb 2026-01-01)\n'
        printf 'binary: rustc\ncommit-hash: 31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd\n'
        ;;
    taskset)
        shift 2
        exec "$@"
        ;;
    cmp) exec /usr/bin/cmp "$@" ;;
    readelf)
        if [[ ${MOCK_FAIL_COMMAND:-} == readelf ]]; then exit 43; fi
        if [[ ${MOCK_BAD_BUILD_ID:-0} == 1 ]]; then
            printf '    Build ID: 0000000000000000000000000000000000000000\n'
        else
            printf '    Build ID: 789119db24ae1a28a24bcc0ecbec136c7e937d9a\n'
        fi
        ;;
    sha256sum)
        file=${!#}
        case ${file##*/} in
            Cargo.lock)
                if [[ ${MOCK_BAD_LOCK_HASH:-0} == 1 ]]; then hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; else hash=0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9; fi
                printf '%s  %s\n' "$hash" "$file"
                ;;
            cubrim)
                if [[ ${MOCK_BAD_BINARY_HASH:-0} == 1 ]]; then hash=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; else hash=2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78; fi
                printf '%s  %s\n' "$hash" "$file"
                ;;
            *-manifest.tsv)
                mkdir -p "$MOCK_STATE/captured"
                cp "$file" "$MOCK_STATE/captured/${file##*/}"
                exec /usr/bin/sha256sum "$file"
                ;;
            *) exec /usr/bin/sha256sum "$file" ;;
        esac
        ;;
    find) exec /usr/bin/find "$@" ;;
    stat)
        if [[ ${MOCK_INJECT_KIND:-none} == device && ${!#} == */device-node && "$*" == *%F* ]]; then
            printf 'character special file\n'
            exit 0
        fi
        exec /usr/bin/stat "$@"
        ;;
    chmod)
        if [[ ${MOCK_FAIL_COMMAND:-} == chmod ]]; then exit 44; fi
        if [[ ${MOCK_CORRUPT_RECEIPT:-0} == 1 && ${!#} == */receipt.env ]]; then
            printf 'unknown_key=bad\n' >>"${!#}"
        fi
        exec /usr/bin/chmod "$@"
        ;;
    systemctl)
        printf '%s\n' "${MOCK_UNIT_STATE:-not-found}"
        ;;
    *) exit 93 ;;
esac
MOCK
    chmod 0755 "$MOCK_BIN/mock-tool"
    local tool
    for tool in git cargo rustc taskset cmp readelf sha256sum find stat chmod systemctl; do
        ln -s mock-tool "$MOCK_BIN/$tool"
    done
}

new_fixture() {
    FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/cubr-g6-prebuild-test.XXXXXXXX")
    TEST_ROOT="$FIXTURE/owned"
    MOCK_BIN="$FIXTURE/bin"
    MOCK_STATE="$FIXTURE/state"
    MOCK_SOURCE_REPO="$FIXTURE/instrument"
    mkdir -p "$TEST_ROOT" "$MOCK_BIN" "$MOCK_STATE" \
        "$MOCK_SOURCE_REPO/documentation/ephemeral/research" "$MOCK_SOURCE_REPO/.git"
    cp "$SCRIPT_TEMPLATE" "$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild.sh"
    cp "$TEST_DIR/current-profile-g6-prebuild-test.sh" \
        "$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild-test.sh"
    chmod 0755 "$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild.sh"
    write_mock_dispatcher
    RECEIPT="$TEST_ROOT/cubr-new24-full-binary-g6-prebuild-receipt-20260811/receipt.env"
    COMMAND_LOG="$MOCK_STATE/commands.log"
    : >"$COMMAND_LOG"
}

cleanup_fixture() {
    if [[ ${CUBR_G6_KEEP_FIXTURES:-0} == 1 ]]; then
        printf '# retained fixture: %s\n' "$FIXTURE" >&2
        return
    fi
    if [[ -n ${FIXTURE:-} && -d ${FIXTURE:-} ]]; then
        chmod -R u+w "$FIXTURE" 2>/dev/null || true
        rm -rf -- "$FIXTURE"
    fi
}

run_prebuild() {
    local -a extra=("$@")
    set +e
    RUN_OUTPUT=$(env -i HOME="$FIXTURE/home" LC_ALL=C PATH=/usr/bin:/bin \
        CUBR_G6_TEST_MODE=1 CUBR_G6_TEST_COMMAND_DIR="$MOCK_BIN" \
        CUBR_G6_TEST_ROOT="$TEST_ROOT" CUBR_G6_TEST_SOURCE_REPO="$MOCK_SOURCE_REPO" \
        MOCK_STATE="$MOCK_STATE" MOCK_SOURCE_REPO="$MOCK_SOURCE_REPO" \
        "${extra[@]}" \
        "$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild.sh" 2>&1)
    RUN_STATUS=$?
    set -e
}

assert_no_clone() {
    ! grep -q '^git|clone|' "$COMMAND_LOG"
}

assert_no_final_receipt() {
    [[ ! -e "$RECEIPT" && ! -L "$RECEIPT" ]]
}

assert_manifest_contract() {
    local manifest=$1
    [[ -f $manifest ]]
    [[ $(awk -F '\t' 'NF == 6 && $1 == "" && $2 == "d" {n++} END {print n+0}' "$manifest") -eq 1 ]]
    awk -F '\t' '
        NF == 6 {
            if ($1 != "" && $1 !~ /^[A-Za-z0-9._\/@+=,-]+$/) exit 1
            if ($2 != "d" && $2 != "f") exit 1
            next
        }
        NF == 3 {
            if ($1 !~ /^[0-9a-f]{64}$/ || $2 !~ /^[0-9]+$/ || $3 !~ /^[A-Za-z0-9._\/@+=,-]+$/) exit 1
            next
        }
        { exit 1 }
    ' "$manifest"
}

assert_positive_contract() {
    [[ $RUN_STATUS -eq 0 && -f $RECEIPT && ! -L $RECEIPT ]]
    [[ -z $RUN_OUTPUT ]]
    [[ ! -e "$TEST_ROOT/cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial" ]]
    [[ $(find "${RECEIPT%/*}" -mindepth 1 -maxdepth 1 -printf '.\n' | wc -l) -eq 1 ]]
    [[ $(stat -c %a "$RECEIPT") == 444 ]]
    [[ $(wc -l <"$RECEIPT") -eq 62 ]]
    diff -u <(expected_keys) <(cut -d= -f1 "$RECEIPT")
    grep -qx 'schema=g6-prebuild-receipt-v1' "$RECEIPT"
    grep -qx "source_commit=$SOURCE_COMMIT" "$RECEIPT"
    grep -qx "cargo_lock_a_sha256=$LOCK_SHA" "$RECEIPT"
    grep -qx "cargo_lock_b_sha256=$LOCK_SHA" "$RECEIPT"
    grep -qx "binary_a_sha256=$BINARY_SHA" "$RECEIPT"
    grep -qx "binary_b_sha256=$BINARY_SHA" "$RECEIPT"
    grep -qx "binary_a_build_id=$BUILD_ID" "$RECEIPT"
    grep -qx "binary_b_build_id=$BUILD_ID" "$RECEIPT"
    grep -qx 'campaign_artifact_count=0' "$RECEIPT"
    grep -qx 'map_artifact_count=0' "$RECEIPT"
    grep -qx 'perf_data_count=0' "$RECEIPT"
    grep -qx 'service_count=0' "$RECEIPT"
    grep -qx 'build_cpuset=0-15' "$RECEIPT"
    grep -qx 'cargo_profile_release_debug=1' "$RECEIPT"
    grep -qx 'cargo_version=1.96.1' "$RECEIPT"
    grep -qx 'cubr_threads=4' "$RECEIPT"
    grep -qx 'rayon_num_threads=4' "$RECEIPT"
    grep -qx 'omp_num_threads=4' "$RECEIPT"
    grep -qx 'mkl_num_threads=4' "$RECEIPT"
    [[ $(grep -c '^git|clone|--no-local|--no-checkout|' "$COMMAND_LOG") -eq 2 ]]
    [[ $(grep -c "git|-C|.*|checkout|--detach|$SOURCE_COMMIT" "$COMMAND_LOG") -eq 2 ]]
    [[ $(grep -c '^cargo|generate-lockfile|--manifest-path|code/cubrim-rs/Cargo.toml' "$COMMAND_LOG") -eq 2 ]]
    [[ $(grep -c '^cmp|' "$COMMAND_LOG") -eq 2 ]]
    [[ $(grep -c '^taskset|-c|0-15|.*cargo|build|--release|--locked|' "$COMMAND_LOG") -eq 2 ]]
    [[ $(grep -c 'cargo|build|.*CARGO_PROFILE_RELEASE_DEBUG=1|CUBR_THREADS=4|RAYON_NUM_THREADS=4|OMP_NUM_THREADS=4|MKL_NUM_THREADS=4' "$COMMAND_LOG") -eq 2 ]]
    local first_clone last_unit
    first_clone=$(grep -n '^git|clone|' "$COMMAND_LOG" | head -1 | cut -d: -f1)
    last_unit=$(grep -n '^systemctl|' "$COMMAND_LOG" | tail -1 | cut -d: -f1)
    [[ $last_unit -lt $first_clone ]]
    local root
    for root in \
        "$TEST_ROOT/cubr-new24-full-binary-g6-src-a" \
        "$TEST_ROOT/cubr-new24-full-binary-g6-src-b" \
        "$TEST_ROOT/cubr-new24-full-binary-g6-target-a" \
        "$TEST_ROOT/cubr-new24-full-binary-g6-target-b"; do
        [[ -z $(find "$root" -perm /222 -print -quit) ]]
    done
    local manifest
    for manifest in source-tree-a-manifest.tsv source-tree-b-manifest.tsv \
        target-a-manifest.tsv target-b-manifest.tsv; do
        assert_manifest_contract "$MOCK_STATE/captured/$manifest"
    done
    [[ ! -e "$TEST_ROOT/cubr-new24-full-binary-g6-map-dryrun-20260811" ]]
    [[ ! -e "$TEST_ROOT/cubr-new24-full-binary-g6-20260811" ]]
    [[ -z $(find "$TEST_ROOT" -name perf.data -print -quit) ]]
}

test_positive() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild
    assert_positive_contract
}

test_collisions_before_clone() {
    local base
    trap cleanup_fixture EXIT
    for base in cubr-new24-full-binary-g6-src-a cubr-new24-full-binary-g6-src-b \
        cubr-new24-full-binary-g6-target-a cubr-new24-full-binary-g6-target-b \
        cubr-new24-full-binary-g6-prebuild-receipt-20260811 \
        cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial; do
        new_fixture
        mkdir -p "$TEST_ROOT/$base"
        run_prebuild
        [[ $RUN_STATUS -ne 0 ]]
        assert_no_clone
        assert_no_final_receipt
        cleanup_fixture
    done
}

test_final_path_collision() {
    new_fixture
    trap cleanup_fixture EXIT
    mkdir -p "${RECEIPT%/*}"
    : >"$RECEIPT"
    run_prebuild
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_clone
}

test_owned_symlink_collision() {
    new_fixture
    trap cleanup_fixture EXIT
    ln -s "$FIXTURE/nowhere" "$TEST_ROOT/cubr-new24-full-binary-g6-src-a"
    run_prebuild
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_clone
    assert_no_final_receipt
}

test_injected_tree_kind() {
    local kind=$1
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild "MOCK_INJECT_KIND=$kind"
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_final_receipt
}

test_units_guard() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild MOCK_UNIT_STATE=loaded
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_clone
    assert_no_final_receipt
}

test_command_failure() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild MOCK_FAIL_COMMAND=cargo_generate
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_final_receipt
}

test_incomplete_target() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild MOCK_INCOMPLETE_TARGET=1
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_final_receipt
}

test_receipt_mismatch() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild MOCK_CORRUPT_RECEIPT=1
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_final_receipt
}

run_prebuild_signal() {
    local pid waited=0
    set +e
    env -i HOME="$FIXTURE/home" LC_ALL=C PATH=/usr/bin:/bin \
        CUBR_G6_TEST_MODE=1 CUBR_G6_TEST_COMMAND_DIR="$MOCK_BIN" \
        CUBR_G6_TEST_ROOT="$TEST_ROOT" CUBR_G6_TEST_SOURCE_REPO="$MOCK_SOURCE_REPO" \
        MOCK_STATE="$MOCK_STATE" MOCK_SOURCE_REPO="$MOCK_SOURCE_REPO" MOCK_PAUSE_CARGO=1 \
        "$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild.sh" \
        >"$MOCK_STATE/signal.out" 2>&1 &
    pid=$!
    while [[ ! -e $MOCK_STATE/cargo-paused && $waited -lt 200 ]]; do
        sleep 0.01
        waited=$((waited + 1))
    done
    [[ -e $MOCK_STATE/cargo-paused ]] || { kill "$pid" 2>/dev/null || true; return 89; }
    kill -TERM "$pid"
    : >"$MOCK_STATE/release-cargo"
    wait "$pid"
    RUN_STATUS=$?
    set -e
}

test_signal() {
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild_signal
    [[ $RUN_STATUS -eq 143 ]]
    assert_no_final_receipt
}

test_runtime_negative() {
    local setting=$1
    new_fixture
    trap cleanup_fixture EXIT
    run_prebuild "$setting"
    [[ $RUN_STATUS -ne 0 ]]
    assert_no_final_receipt
}

test_literal_contract() {
    local literal
    for literal in \
        /root/cubr-new24-full-binary-g6-src-a \
        /root/cubr-new24-full-binary-g6-src-b \
        /root/cubr-new24-full-binary-g6-target-a \
        /root/cubr-new24-full-binary-g6-target-b \
        /root/cubr-new24-full-binary-g6-prebuild-receipt-20260811 \
        /root/cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial \
        cubr-new24-full-binary-g6-admission-20260811.service \
        cubr-new24-full-binary-g6-20260811.service; do
        grep -qF "$literal" "$SCRIPT_TEMPLATE"
    done
    ! grep -qF 'cubr-new24-full-binary-g5-' "$SCRIPT_TEMPLATE"
}

test_production_rejects_override() {
    local output status
    set +e
    output=$(env -i HOME="$HOME" PATH=/usr/bin:/bin \
        CUBR_G6_TEST_ROOT=/tmp/forbidden "$SCRIPT_TEMPLATE" 2>&1)
    status=$?
    set -e
    [[ $status -ne 0 && $output == *"production mode rejects"* ]]
}

apply_mutation() {
    local name=$1
    local script=$2
    case $name in
        cmp-lock) sed -i '/MUTANT:cmp-lock$/d' "$script" ;;
        cmp-binary) sed -i '/MUTANT:cmp-binary$/d' "$script" ;;
        source-commit) sed -i "s/$SOURCE_COMMIT/930a9a31deb00926a97f3fa5bd74f58003573fc0/" "$script" ;;
        lock-hash) sed -i "s/$LOCK_SHA/1080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9/" "$script" ;;
        binary-hash) sed -i "s/$BINARY_SHA/3afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78/" "$script" ;;
        build-id) sed -i "s/$BUILD_ID/889119db24ae1a28a24bcc0ecbec136c7e937d9a/" "$script" ;;
        rust-pin) sed -i 's/readonly RUST_VERSION=1\.96\.1/readonly RUST_VERSION=1.96.2/' "$script" ;;
        cubr-thread) sed -i 's/readonly CUBR_THREADS=4/readonly CUBR_THREADS=5/' "$script" ;;
        rayon-thread) sed -i 's/readonly RAYON_NUM_THREADS=4/readonly RAYON_NUM_THREADS=5/' "$script" ;;
        omp-thread) sed -i 's/readonly OMP_NUM_THREADS=4/readonly OMP_NUM_THREADS=5/' "$script" ;;
        mkl-thread) sed -i 's/readonly MKL_NUM_THREADS=4/readonly MKL_NUM_THREADS=5/' "$script" ;;
        locked) sed -i 's/ --release --locked / --release /' "$script" ;;
        release-debug) sed -i 's/readonly CARGO_PROFILE_RELEASE_DEBUG=1/readonly CARGO_PROFILE_RELEASE_DEBUG=0/' "$script" ;;
        receipt-mode) sed -i 's/readonly RECEIPT_MODE=0444/readonly RECEIPT_MODE=0644/' "$script" ;;
        root-drop) sed -i '/MUTANT:root-row$/d' "$script" ;;
        root-rename) sed -i "s/printf '\\\\t%s/printf '.\\\\t%s/" "$script" ;;
        root-duplicate) sed -i '/MUTANT:root-row$/p' "$script" ;;
        root-symlink) sed -i '/MUTANT:reject-root-symlink$/ s/die .* # MUTANT:reject-root-symlink/: # MUTANT:reject-root-symlink/' "$script" ;;
        nested-symlink) sed -i '/MUTANT:reject-nested-symlink$/ s/die .* # MUTANT:reject-nested-symlink/: # MUTANT:reject-nested-symlink/' "$script" ;;
        fifo) sed -i '/MUTANT:reject-fifo$/ s/die .* # MUTANT:reject-fifo/: # MUTANT:reject-fifo/' "$script" ;;
        socket) sed -i '/MUTANT:reject-socket$/ s/die .* # MUTANT:reject-socket/: # MUTANT:reject-socket/' "$script" ;;
        device) sed -i '/MUTANT:reject-device$/ s/die .* # MUTANT:reject-device/: # MUTANT:reject-device/' "$script" ;;
        unsafe-path) sed -i '/MUTANT:validate-relpath$/ s/validate_relative_path .* # MUTANT:validate-relpath/: # MUTANT:validate-relpath/' "$script" ;;
        collision) sed -i '/MUTANT:collision-gate$/d' "$script" ;;
        alias) sed -i '/MUTANT:independent-object-stores$/d' "$script" ;;
        perf-data) sed -i '/MUTANT:no-forbidden-output$/d' "$script" ;;
        omit-key) sed -i '/MUTANT:receipt-service-count$/d' "$script" ;;
        partial-receipt)
            # shellcheck disable=SC2016 # Preserve literal receipt variables in the mutated helper source.
            sed -i '/MUTANT_ANCHOR:after-partial-created/a\\    mkdir -p "$RECEIPT_ROOT"; printf "schema=g6-prebuild-receipt-v1\\n" >"$FINAL_RECEIPT"' "$script"
            ;;
        *) return 90 ;;
    esac
}

assert_mutated_behavior_contract() {
    local name=$1
    case $name in
        root-symlink) run_prebuild MOCK_INJECT_KIND=root_symlink ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        nested-symlink) run_prebuild MOCK_INJECT_KIND=nested_symlink ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        fifo) run_prebuild MOCK_INJECT_KIND=fifo ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        socket) run_prebuild MOCK_INJECT_KIND=socket ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        device) run_prebuild MOCK_INJECT_KIND=device ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        unsafe-path) run_prebuild MOCK_INJECT_KIND=unsafe ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        collision)
            mkdir -p "$TEST_ROOT/cubr-new24-full-binary-g6-src-a"
            run_prebuild
            [[ $RUN_STATUS -ne 0 ]]; assert_no_clone; assert_no_final_receipt
            ;;
        alias) run_prebuild MOCK_ALIAS_OBJECTS=1 ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        perf-data) run_prebuild MOCK_INJECT_PERF=1 ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        partial-receipt) run_prebuild MOCK_FAIL_COMMAND=cargo_build ; [[ $RUN_STATUS -ne 0 ]]; assert_no_final_receipt ;;
        *)
            run_prebuild
            assert_positive_contract
            ;;
    esac
}

test_mutant() {
    local name=$1
    new_fixture
    trap cleanup_fixture EXIT
    local script="$MOCK_SOURCE_REPO/documentation/ephemeral/research/current-profile-g6-prebuild.sh"
    local before after contract_status
    before=$(sha256sum "$script" | awk '{print $1}')
    apply_mutation "$name" "$script"
    after=$(sha256sum "$script" | awk '{print $1}')
    [[ $before != "$after" ]]
    set +e
    (
        set -euo pipefail
        assert_mutated_behavior_contract "$name"
    )
    contract_status=$?
    set -e
    [[ $contract_status -ne 0 ]]
}

if [[ ! -x $SCRIPT_TEMPLATE ]]; then
    printf 'not ok 1 - prebuild helper exists and is executable\n'
    exit 1
fi

if [[ ${CUBR_G6_TEST_ONLY:-} == positive ]]; then
    report_test 'positive: independent builds seal and publish the exact receipt' test_positive
    printf '1..%d\n' "$((pass_count + fail_count))"
    printf '# pass=%d fail=%d\n' "$pass_count" "$fail_count"
    ((fail_count == 0))
    exit
fi

if [[ ${CUBR_G6_TEST_ONLY:-} == mutant:* ]]; then
    only_mutant=${CUBR_G6_TEST_ONLY#mutant:}
    report_test "mutant killed: $only_mutant" test_mutant "$only_mutant"
    printf '1..%d\n' "$((pass_count + fail_count))"
    printf '# pass=%d fail=%d\n' "$pass_count" "$fail_count"
    ((fail_count == 0))
    exit
fi

report_test 'positive: independent builds seal and publish the exact receipt' test_positive
report_test 'collision: every owned path fails before clone' test_collisions_before_clone
report_test 'collision: final receipt path fails before clone' test_final_path_collision
report_test 'collision: owned symlink fails before clone' test_owned_symlink_collision
for kind in root_symlink nested_symlink fifo socket device unsafe nonascii control; do
    report_test "tree gate: $kind fails closed" test_injected_tree_kind "$kind"
done
report_test 'unit gate: both exact G6 units must remain not-found' test_units_guard
report_test 'failure gate: nonzero child never publishes a receipt' test_command_failure
report_test 'failure gate: incomplete target never publishes a receipt' test_incomplete_target
report_test 'failure gate: receipt mismatch never publishes a receipt' test_receipt_mismatch
report_test 'failure gate: TERM never publishes a receipt' test_signal
for setting in \
    MOCK_DIRTY_BEFORE_LOCK=1 'MOCK_POST_STATUS=?? unexpected' \
    MOCK_LOCK_MISMATCH=1 MOCK_BAD_LOCK_HASH=1 MOCK_BINARY_MISMATCH=1 \
    MOCK_BAD_BINARY_HASH=1 MOCK_BAD_BUILD_ID=1 MOCK_ALIAS_OBJECTS=1 \
    MOCK_INJECT_PERF=1; do
    report_test "negative identity gate: $setting" test_runtime_negative "$setting"
done
report_test 'production mode rejects test/path overrides' test_production_rejects_override
report_test 'production literals use only the exact G6 namespaces' test_literal_contract

mutants=(
    cmp-lock cmp-binary source-commit lock-hash binary-hash build-id rust-pin
    cubr-thread rayon-thread omp-thread mkl-thread locked release-debug receipt-mode
    root-drop root-rename root-duplicate root-symlink nested-symlink fifo socket device
    unsafe-path collision alias perf-data omit-key partial-receipt
)
for mutant in "${mutants[@]}"; do
    report_test "mutant killed: $mutant" test_mutant "$mutant"
done

printf '1..%d\n' "$((pass_count + fail_count))"
printf '# pass=%d fail=%d\n' "$pass_count" "$fail_count"
((fail_count == 0))
