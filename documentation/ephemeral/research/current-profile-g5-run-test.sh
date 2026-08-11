#!/usr/bin/env bash
# Static, runtime, and mutation-sensitive contract tests for the NEW-24 G5 runner.
# shellcheck disable=SC2016
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly TEST_DIR
readonly SELF=$TEST_DIR/current-profile-g5-run-test.sh
RUNNER=${RUNNER:-$TEST_DIR/current-profile-g5-run.sh}
MAPPER=${MAPPER:-$TEST_DIR/current_profile_g5_map.py}
SELF_MUTATION_TESTS=${SELF_MUTATION_TESTS:-1}
readonly POISONED_PARENT_UNIT=g4-live-authority-must-not-be-used.service
readonly LIVE_G5_CAMPAIGN_UNIT=cubr-new24-full-binary-g5-20260810.service
readonly PURE_MOCK_PATH=/usr/bin:/bin
readonly PURE_MOCK_PARENT_CANARY=parent-environment-must-not-reach-pure-mock

export CUBR_SYSTEMD_UNIT=$POISONED_PARENT_UNIT
export INVOCATION_ID=g4-live-authority-must-not-be-used
export CUBR_CGROUP_SYSTEMCTL_USER=1
export CUBR_CGROUP_LIVE_RESULT=/tmp/g4-live-authority-must-not-be-used.result
export CUBR_G5_PURE_MOCK_PARENT_CANARY=$PURE_MOCK_PARENT_CANARY

fail() {
    printf 'current_profile_g5_contract=FAIL reason=%s\n' "$1" >&2
    exit 1
}

invalid() {
    printf 'current_profile_g5_contract=HARNESS_INVALID reason=%s\n' "$1" >&2
    exit 2
}

assert_mock_output_isolated() {
    local output=$1 expected_unit=$2
    [[ $output != *'canary=present'* ]] ||
        fail 'parent poison canary reached pure mock child'
    [[ $output != *"$POISONED_PARENT_UNIT"* ]] ||
        fail 'poisoned parent unit reached pure mock output'
    [[ $output != *"$LIVE_G5_CAMPAIGN_UNIT"* ]] ||
        fail 'live campaign unit reached pure mock output'
    [[ $output == *"unit=$expected_unit"* ]] ||
        invalid "pure mock output missing expected unit: $expected_unit output=$output"
}

run_pure_mock_cgroup() {
    local fixture_unit=$1 mode=$2
    /usr/bin/env -i LC_ALL=C PATH="$PURE_MOCK_PATH" CUBR_SYSTEMD_UNIT="$fixture_unit" /usr/bin/bash "$RUNNER" "$mode"
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

line_of_last() {
    local pattern=$1 line
    line=$({ /usr/bin/grep -nE -- "$pattern" "$RUNNER" || true; } |
        /usr/bin/tail -n 1 | /usr/bin/cut -d: -f1)
    [[ -n $line ]] || fail "missing ordered call: $pattern"
    printf '%s\n' "$line"
}

[[ -f $RUNNER && ! -L $RUNNER ]] || invalid "runner not found or unsafe: $RUNNER"
[[ -f $MAPPER && ! -L $MAPPER ]] || invalid "mapper not found or unsafe: $MAPPER"

live_fixture_helper=$(/usr/bin/awk '
    /^run_user_systemd_fixture\(\) \{/ {inside=1}
    inside {print}
    inside && /^}/ {exit}
' "$SELF")
[[ $live_fixture_helper != *'INVOCATION_ID'* ]] ||
    fail 'outer live-fixture allowlist admitted INVOCATION_ID'
[[ $live_fixture_helper != *'CUBR_SYSTEMD_UNIT'* &&
   $live_fixture_helper != *'CUBR_CGROUP_SYSTEMCTL_USER'* &&
   $live_fixture_helper != *'CUBR_CGROUP_LIVE_RESULT'* ]] ||
    fail 'outer live-fixture allowlist admitted fixture authority'

fresh_fixture_count=$({ /usr/bin/grep -F 'current-profile-g5-cgroup-selftest-' "$RUNNER" || true; } |
    /usr/bin/wc -l)
[[ $fresh_fixture_count == 1 ]] || fail 'live fixture fresh unit literal count is not exactly one'
live_fixture_vector=$(/usr/bin/awk '
    /^[[:space:]]*systemd_args=\($/ {inside=1}
    inside {print}
    inside && /^[[:space:]]*\)$/ {exit}
' "$RUNNER")
[[ $live_fixture_vector != *"$LIVE_G5_CAMPAIGN_UNIT"* ]] ||
    fail 'live fixture argument vector contains campaign unit'
/usr/bin/grep -qF \
    'p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork()' "$RUNNER" ||
    fail 'live fixture double-fork payload missing'

reread_call=verify_admitted_campaign_identity
reread_count=$({ /usr/bin/grep -E "^[[:space:]]*$reread_call$" "$SELF" || true; } |
    /usr/bin/wc -l)
[[ $reread_count == 14 ]] || fail 'campaign identity reread missing after self-test'

require_campaign_reread_after() {
    local anchor=$1 anchor_count anchor_line next_statement
    anchor_count=$(/usr/bin/grep -Fc -- "$anchor" "$SELF")
    [[ $anchor_count == 1 ]] || fail 'campaign identity reread missing after self-test'
    anchor_line=$(/usr/bin/grep -nF -- "$anchor" "$SELF" | /usr/bin/cut -d: -f1)
    next_statement=$(/usr/bin/awk -v start="$anchor_line" '
        NR <= start || /^[[:space:]]*$/ {next}
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
    "$reread_runner_prefix fake-cargo control failed:"
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
    '/root/cubr-new24-full-binary-g5-src'
    '/root/cubr-new24-full-binary-g5-target'
    '/root/cubr-new24-full-binary-g5-20260810'
    '/root/phaseC/corpus_manifest.tsv'
    '/root/corpus-full/silesia'
    '830a9a31deb00926a97f3fa5bd74f58003573fc0'
    'readonly CAMPAIGN_BUDGET_SECONDS=14400'
    'readonly MAP_BUILD_TIMEOUT_SECONDS=1200'
    'readonly EVIDENCE_PART_MAX_BYTES=90000000'
    'readonly EXPECTED_INSTRUCTION_COUNT=739548'
    'readonly EXPECTED_PAGE_SIZE=4096'
    'readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd'
    'readonly EXPECTED_MAPPING_SCHEMA_SHA=1c8f5be539eaaa94f3a64d071e859ee5eccf8f4314908e143246f47bd8760e12'
    'readonly EXPECTED_MAP_SEAL_SHA=565cce3c44c9fb8a228184e0af37270e0caeb2160f15c36b4690bc81aa139a6f'
    'readonly EXPECTED_MAP_PART_COUNT=1'
    'readonly EXPECTED_PREFIX_LOCATION_ROWS=2815329'
    'readonly EXPECTED_MAP_BYTES=1111781924'
    'readonly EXPECTED_MAP_SHA=8bd7b254793cb5a3bf84b7e7c995f8f65d55e04e2e69d86340b876cb2a9d03b7'
    'readonly EXPECTED_MAP_MANIFEST_SHA=db0bb37f8b96e73c6e39288e5224fd476cbf3abe4241d7e634b6e54de36859c4'
    'readonly EXPECTED_MAP_PART_COMPRESSED_BYTES=40287882'
    'readonly EXPECTED_MAP_PART_COMPRESSED_SHA=cb8674ded7be56a114873ad86ea75771955107a8013adcf9ead48c9a136dc668'
    'readonly EXPECTED_SUMMARY_BYTES=121941235'
    'readonly EXPECTED_SUMMARY_SHA=bfcd4c3d3dc3fcb652c5e49cdb8fb60b4bb082cb4de0264456ccfb303948c961'
    'readonly EXPECTED_SUMMARY_COMPRESSED_BYTES=27591662'
    'readonly EXPECTED_SUMMARY_COMPRESSED_SHA=5811308b6c98bbd730c61aa98a08619a1ab99346cf5aa9f32d79eeb88ac495fe'
    'readonly EXPECTED_SOURCE_REVERSE_COUNT=188054'
    'readonly EXPECTED_EMITTED_REVERSE_COUNT=5047'
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
    'CUBR_INSTRUMENT_COMMIT'
    'instrument mapper test blob mismatch'
    'CUBR_EXPECTED_MAPPER_TEST_SHA256'
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
    'cargo test --release'
    'cargo test --release --test scheme_roundtrip -- --nocapture'
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
    'map full reconstruction mismatch'
    'map-summary.json.gz'
    'compress_map_artifact "$map_dir/map-summary.json" "$map_dir/raw-stream-evidence.tsv"'
    'map summary deterministic gzip readback mismatch'
    'exact frozen instruction count mismatch'
    'fresh full map differs from reviewed attempt9 admission seal'
    'reviewed map admission seal hash mismatch'
    'map-admission-seal.json'
    'map manifest has extra or missing parts'
    'map evidence part exceeds 90000000 bytes'
    'full_map_elapsed_seconds'
    'full_map_peak_rss_kib'
    'map-worker.stderr.txt'
    'CUBR_EXPECTED_MAPPER_SHA256="$EXPECTED_MAPPER_SHA"'
    'CUBR_EXPECTED_MAPPER_TEST_SHA256="$EXPECTED_MAPPER_TEST_SHA"'
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
    '-v runner="$$" -v parent="$PPID"'
    '$1 != runner && $1 != parent'
    'orphan candidate/perf process or competing Cubrim/Cargo/Rust/current-profile runner'
    'current_profile_g5_fake_cargo=PASS'
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

require_runner_fixed '/root/cubr-new24-full-binary-g5-src'
require_runner_fixed '/root/cubr-new24-full-binary-g5-target'
require_runner_fixed '/root/cubr-new24-full-binary-g5-instrument'
require_runner_fixed '/root/cubr-new24-full-binary-g5-20260810'
reject_runner_fixed '/root/cubr-new24-full-binary-g4-20260809'
reject_runner_fixed 'cubr-new24-full-binary-g4.service'
reject_runner_fixed 'current_profile_g4_'
reject_runner_fixed 'config/credentials/'

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

mapper_commands=(normalize-elf build-map reduce-record summarize-file)
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

self_test_output=
self_test_rc=0
set +e
self_test_output=$(/usr/bin/bash "$RUNNER" --self-test 2>&1)
self_test_rc=$?
set -e
if ! { (( self_test_rc == 0 )) && [[ $self_test_output == 'current_profile_g5_self_test=PASS' ]]; }; then
    invalid "runner self-test positive control failed: rc=$self_test_rc output=$self_test_output"
fi
    verify_admitted_campaign_identity

fake_cargo_output=
fake_cargo_rc=0
set +e
fake_cargo_output=$(/usr/bin/bash "$RUNNER" --self-test-fake-cargo 2>&1)
fake_cargo_rc=$?
set -e
if ! { (( fake_cargo_rc == 0 )) && [[ $fake_cargo_output == 'current_profile_g5_fake_cargo=PASS' ]]; }; then
    invalid "runner fake-cargo control failed: rc=$fake_cargo_rc output=$fake_cargo_output"
fi
    verify_admitted_campaign_identity

publish_output=$(/usr/bin/bash "$RUNNER" --self-test-publish 2>&1) ||
    invalid "runner durable-publish positive control failed: $publish_output"
[[ $publish_output == 'current_profile_g5_publish_test=PASS' ]] ||
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
[[ $pure_mock_environment_output == 'current_profile_g5_cgroup_environment_test=PASS canary=absent unit=mock.unit' ]] ||
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
[[ $cgroup_output == 'current_profile_g5_cgroup_test=PASS unit=mock.unit' ]] ||
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
[[ $cgroup_precommit_output == 'current_profile_g5_cgroup_precommit_test=PASS unit=precommit-disconnected.service' ]] ||
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
[[ $unexpected_precommit_output == 'current_profile_g5_cgroup_precommit_test=FAIL unit=unexpected-authority.service reason=unexpected-fixture-unit' ]] ||
    invalid "unexpected precommit authority failed at unrelated assertion: rc=$unexpected_precommit_rc output=$unexpected_precommit_output"
    verify_admitted_campaign_identity

publish_write_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-writes 2>&1) ||
    invalid "runner checked publication write control failed: $publish_write_output"
[[ $publish_write_output == 'current_profile_g5_publish_write_test=PASS' ]] ||
    invalid "runner checked publication write output mismatch: $publish_write_output"
    verify_admitted_campaign_identity

publish_tamper_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-tamper 2>&1) ||
    invalid "runner publication tamper control failed: $publish_tamper_output"
[[ $publish_tamper_output == 'current_profile_g5_publish_tamper_test=PASS' ]] ||
    invalid "runner publication tamper output mismatch: $publish_tamper_output"
    verify_admitted_campaign_identity

hard_deadline_output=$(/usr/bin/bash "$RUNNER" --self-test-hard-deadline 2>&1) ||
    invalid "runner hard-deadline positive control failed: $hard_deadline_output"
[[ $hard_deadline_output == 'current_profile_g5_hard_deadline_test=PASS' ]] ||
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
        [[ $live_output =~ ^current_profile_g5_cgroup_live_test=PASS\ result_sha256=([0-9a-f]{64})\ test_output_sha256=([0-9a-f]{64})$ ]] ||
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
    [[ $timeout_tree_output == *'current_profile_g5_timeout_tree_test=PASS' ]] ||
        invalid "runner timeout-tree positive control output mismatch: $timeout_tree_output"
    verify_admitted_campaign_identity

    publish_crash_output=$(/usr/bin/bash "$RUNNER" --self-test-publish-crashes 2>&1) ||
        invalid "runner publish-crash controls failed: $publish_crash_output"
    [[ $publish_crash_output == 'current_profile_g5_publish_crash_test=PASS' ]] ||
        invalid "runner publish-crash control output mismatch: $publish_crash_output"
    verify_admitted_campaign_identity
fi

trap_line=$(line_of_last '^[[:space:]]{4}trap on_exit EXIT$')
partial_line=$(line_of_last '^[[:space:]]{4}/usr/bin/mkdir -m 0700 -- "\$PARTIAL"$')
admission_line=$(line_of_last '^[[:space:]]{4}admission "\$PREFLIGHT_DIR" 1$')
suites_line=$(line_of_last '^[[:space:]]{4}run_suites$')
map_line=$(line_of_last '^[[:space:]]{4}build_full_instruction_map$')
fixture_line=$(line_of_last '^[[:space:]]{4}verify_feasibility_fixture "\$PARTIAL"$')
smoke_line=$(line_of_last '^[[:space:]]{4}verify_address_join_smoke "\$PARTIAL"$')
cells_line=$(line_of_last '^[[:space:]]{4}for cell in "\$\{CELLS\[@\]\}"; do$')
(( trap_line < partial_line && partial_line < admission_line && admission_line < suites_line && suites_line < map_line &&
    map_line < fixture_line && fixture_line < smoke_line && smoke_line < cells_line )) ||
    fail 'main ordering must be trap -> admission -> suites -> full map -> fixture -> address smoke -> cells'

finalizing_line=$(line_of_last '^[[:space:]]*FINALIZING=1$')
terminal_line=$(line_of_last '^[[:space:]]*run_terminal_finalization$')
(( finalizing_line < terminal_line )) ||
    fail 'completion ordering must be finalization mode -> bounded terminal finalization'
next_after_terminal=$(/usr/bin/sed -n "$((terminal_line + 1))p" "$RUNNER")
[[ $next_after_terminal == '}' ]] || fail 'terminal finalization must be last fallible main-run operation'

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

    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$RUNNER" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'current_profile_g5_contract=PASS' ]]; }; then
        invalid "positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutation_root/missing.sh" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 2 )) && [[ $CHILD_OUTPUT == current_profile_g5_contract=HARNESS_INVALID\ reason=runner\ not\ found\ or\ unsafe:* ]]; }; then
        invalid "setup-negative control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    expect_runner_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutant" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g5_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "mutation emitted PASS: $label"
        /usr/bin/grep -qF "current_profile_g5_contract=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_self_test_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/bash "$mutant" --self-test
        (( CHILD_RC != 0 )) || fail "runner self-test mutation survived: $label"
        [[ $CHILD_OUTPUT == "current_profile_g5_self_test=FAIL reason=$expected_reason" ]] ||
            invalid "runner self-test mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
        verify_admitted_campaign_identity
    }

    expect_runtime_mutant_red() {
        local label=$1 expression=$2 expected_fragment=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutant" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "runtime mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g5_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "runtime mutation emitted PASS: $label"
        /usr/bin/grep -qF "$expected_fragment" <<<"$CHILD_OUTPUT" ||
            invalid "runtime mutation failed at unrelated control: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_contract_source_mutant_red() {
        local label=$1 expression=$2 expected_fragment=$3 mutant_dir mutant
        mutant_dir=$mutation_root/contract-$label
        mutant=$mutant_dir/current-profile-g5-run-test.sh
        /usr/bin/mkdir -p -- "$mutant_dir"
        /usr/bin/cp -- "$SELF" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$SELF" "$mutant" || fail "contract source mutation did not change test: $label"
        capture_child /usr/bin/env \
            CUBR_SYSTEMD_UNIT="$POISONED_PARENT_UNIT" \
            INVOCATION_ID=g4-live-authority-must-not-be-used \
            CUBR_CGROUP_SYSTEMCTL_USER=1 \
            CUBR_CGROUP_LIVE_RESULT=/tmp/g4-live-authority-must-not-be-used.result \
            CUBR_G5_PURE_MOCK_PARENT_CANARY="$PURE_MOCK_PARENT_CANARY" \
            SELF_MUTATION_TESTS=0 RUNNER="$RUNNER" MAPPER="$MAPPER" \
            /usr/bin/bash "$mutant"
        (( CHILD_RC != 0 )) || fail "contract source mutation survived: $label"
        ! /usr/bin/grep -qF 'current_profile_g5_contract=PASS' <<<"$CHILD_OUTPUT" ||
            invalid "contract source mutation emitted PASS: $label"
        /usr/bin/grep -qF -- "$expected_fragment" <<<"$CHILD_OUTPUT" ||
            invalid "contract source mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_contract_source_mutant_red helper_without_empty_environment \
        's#^    /usr/bin/env -i LC_ALL=C PATH=#    /usr/bin/env LC_ALL=C PATH=#' \
        'parent poison canary reached pure mock child'
    expect_contract_source_mutant_red helper_uses_parent_unit \
        's#CUBR_SYSTEMD_UNIT="\$fixture_unit" /usr/bin/bash#CUBR_SYSTEMD_UNIT="${CUBR_SYSTEMD_UNIT}" /usr/bin/bash#' \
        'poisoned parent unit reached pure mock output'

    expect_contract_source_mutant_red post_self_test_reread_removed \
        's/    verify_admitted_campaign_identity/    : # mutation removed campaign identity reread/' \
        'campaign identity reread missing after self-test'
    expect_contract_source_mutant_red compensated_post_self_test_reread_moved \
        '0,/^    verify_admitted_campaign_identity$/s//    : # mutation moved campaign identity reread/; 0,/^    verify_admitted_campaign_identity$/s//    verify_admitted_campaign_identity\n    verify_admitted_campaign_identity/' \
        'campaign identity reread missing after self-test'
    expect_runner_mutant_red fixture_uses_campaign_unit \
        's/--unit="\$fixture_unit"/--unit=cubr-new24-full-binary-g5-20260810.service/' \
        'live fixture argument vector contains campaign unit'
    expect_runner_mutant_red double_fork_removed \
        's/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork()/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=0/' \
        'live fixture double-fork payload missing'
    expect_contract_source_mutant_red inherited_invocation_passed \
        's#DBUS_SESSION_BUS_ADDRESS="\$host_dbus"#DBUS_SESSION_BUS_ADDRESS="$host_dbus" INVOCATION_ID="${INVOCATION_ID:-}"#' \
        'outer live-fixture allowlist admitted INVOCATION_ID'

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
    expect_runner_mutant_red same_count_map_byte_drift \
        's/8bd7b254793cb5a3bf84b7e7c995f8f65d55e04e2e69d86340b876cb2a9d03b7/8bd7b254793cb5a3bf84b7e7c995f8f65d55e04e2e69d86340b876cb2a9d03b8/g' \
        'runner missing literal: readonly EXPECTED_MAP_SHA=8bd7b254793cb5a3bf84b7e7c995f8f65d55e04e2e69d86340b876cb2a9d03b7'
    expect_runner_mutant_red summary_byte_drift \
        's/EXPECTED_SUMMARY_BYTES=121941235/EXPECTED_SUMMARY_BYTES=121941236/' \
        'runner missing literal: readonly EXPECTED_SUMMARY_BYTES=121941235'
    expect_runner_mutant_red resolver_count_drift \
        's/EXPECTED_PREFIX_LOCATION_ROWS=2815329/EXPECTED_PREFIX_LOCATION_ROWS=2815330/' \
        'runner missing literal: readonly EXPECTED_PREFIX_LOCATION_ROWS=2815329'
    expect_runner_mutant_red page_size 's/EXPECTED_PAGE_SIZE=4096/EXPECTED_PAGE_SIZE=8192/' \
        'runner missing literal: readonly EXPECTED_PAGE_SIZE=4096'
    expect_runner_mutant_red rustc_full_commit \
        's/31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd/31fca3ad00000000000000000000000000000000/g' \
        'runner missing literal: readonly EXPECTED_RUSTC_COMMIT=31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd'
    expect_runner_mutant_red summary_compression \
        's/compress_map_artifact "\$map_dir\/map-summary.json" "\$map_dir\/raw-stream-evidence.tsv"/\/usr\/bin\/true/' \
        'runner missing literal: compress_map_artifact "$map_dir/map-summary.json" "$map_dir/raw-stream-evidence.tsv"'
    expect_runner_mutant_red record_mode 's/--buildid-all --buildid-mmap/--buildid-all/' \
        'runner missing literal: --buildid-all --buildid-mmap'
    expect_runner_mutant_red source_sha \
        's/b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' \
        'runner missing literal: b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    expect_runner_mutant_red output_path \
        's/cubr-new24-full-binary-g5-20260810/cubr-new24-full-binary-g5-later/' \
        'runner missing literal: /root/cubr-new24-full-binary-g5-20260810'
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
    expect_runner_mutant_red mapper_test_identity \
        's/CUBR_EXPECTED_MAPPER_TEST_SHA256/CUBR_WRONG_MAPPER_TEST_SHA256/g' \
        'runner missing literal: CUBR_EXPECTED_MAPPER_TEST_SHA256'
    expect_runner_mutant_red mapper_worker_identity \
        's/CUBR_EXPECTED_MAPPER_SHA256="\$EXPECTED_MAPPER_SHA"/CUBR_EXPECTED_MAPPER_SHA256=""/' \
        'runner missing literal: CUBR_EXPECTED_MAPPER_SHA256="$EXPECTED_MAPPER_SHA"'
    expect_runner_mutant_red mapper_test_worker_identity \
        's/CUBR_EXPECTED_MAPPER_TEST_SHA256="\$EXPECTED_MAPPER_TEST_SHA"/CUBR_EXPECTED_MAPPER_TEST_SHA256=""/' \
        'runner missing literal: CUBR_EXPECTED_MAPPER_TEST_SHA256="$EXPECTED_MAPPER_TEST_SHA"'
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
        'runner cgroup precommit counterexample failed: current_profile_g5_cgroup_precommit_test=FAIL disconnected-publisher-accepted'
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

printf 'current_profile_g5_contract=PASS\n'
