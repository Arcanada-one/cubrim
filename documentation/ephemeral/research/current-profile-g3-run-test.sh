#!/usr/bin/env bash
# Static and mutation-sensitive contract tests for current-profile-g3-run.sh.
# shellcheck disable=SC2016
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly TEST_DIR
readonly SELF=$TEST_DIR/current-profile-g3-run-test.sh
RUNNER=${RUNNER:-$TEST_DIR/current-profile-g3-run.sh}
MAPPER=${MAPPER:-$TEST_DIR/current_profile_g3_map.py}
SELF_MUTATION_TESTS=${SELF_MUTATION_TESTS:-1}

fail() {
    printf 'current_profile_g3_contract=FAIL reason=%s\n' "$1" >&2
    exit 1
}

invalid() {
    printf 'current_profile_g3_contract=HARNESS_INVALID reason=%s\n' "$1" >&2
    exit 2
}

require_runner_fixed() {
    /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "runner missing literal: $1"
}

require_mapper_fixed() {
    /usr/bin/grep -qF -- "$1" "$MAPPER" || fail "mapper missing literal: $1"
}

reject_runner_fixed() {
    ! /usr/bin/grep -qF -- "$1" "$RUNNER" || fail "runner forbidden literal: $1"
}

reject_mapper_fixed() {
    ! /usr/bin/grep -qF -- "$1" "$MAPPER" || fail "mapper forbidden literal: $1"
}

[[ -f $RUNNER ]] || invalid "runner not found: $RUNNER"
[[ -f $MAPPER ]] || invalid "mapper not found: $MAPPER"

runner_literals=(
    '/root/cubr-new24-current-profile-g3-20260809'
    '/root/cubr-new24-current-profile-g3-src'
    '/root/phaseC/corpus_manifest.tsv'
    '/root/corpus-full/silesia'
    'e0e8bdb2c2df924877d9dcf8a1897810683a147a'
    'taskset -c 0-15'
    'readonly CAMPAIGN_BUDGET_SECONDS=14400'
    'readonly CYCLE_DISAGREEMENT_MAX=0.10'
    'readonly G3_RATIO_MAX=1.10'
    'readonly SHARE_DELTA_MAX=1.00'
    'readonly FEASIBILITY_FIXTURE_BYTES=65536'
    'de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'
    'readonly FEASIBILITY_FIXTURE_PRESET=max'
    '352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3'
    'CARGO_PROFILE_RELEASE_DEBUG=1'
    'cargo test --release'
    'cargo test --release --test scheme_roundtrip -- --nocapture'
    'b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82'
    'd64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37'
    'a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341'
    'b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    '0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c'
    'dickens|max|10192446|1340|435'
    'xml|max|5345280|520|175'
    'dickens|web|10192446|380|320'
    'encode1'
    'encode2'
    'plain'
    'pstat1'
    'pstat2'
    'prec1'
    'prec2'
    'perf1.data'
    'perf2.data'
    'perf record -q -F 997 -e cycles'
    'perf script -i'
    '--show-lost-events'
    'record-diagnostics.tsv'
    'VALID-DESCRIPTIVE-PROFILE'
    'NO-SELECT'
    'classify_record_pair'
    'parse_build_id'
    'binary_build_id'
    'objdump_version'
    'addr2line_version'
    'perf_version'
    'binary.readelf-notes.txt'
    'tool-versions.txt'
    '"$BINARY_BUILD_ID" "$lock_sha" "$CODE_COMMIT"'
    'tolower($1)==id && $2==dso { matches++ }'
    'discover_perf_events'
    'perf-events.tsv'
    'status\":\"unsupported'
    'cmp --'
    '[[ $(sha "$src") == "$want_sha" ]]'
    'verify_runner_provenance'
    'verify_binary_and_code'
    'verify_mapper_provenance'
    'verify_feasibility_fixture "$PREFLIGHT_DIR"'
    'verify_feasibility_fixture "$PARTIAL"'
    'event\":\"feasibility_fixture_pass'
    'feasibility round-trip mismatch'
    'build_instruction_map'
    'verify_instruction_map'
    'instruction-map.tsv'
    'instruction-map.sha256'
    'instruction-map-coverage.tsv'
    'NR>1 && $6==b'
    'objdump --disassemble --line-numbers --demangle'
    'objdump --disassemble --line-numbers "$CUBRIM"'
    'binary.objdump.raw.txt'
    'binary.objdump.demangled.txt'
    'filter --raw-full'
    'objdump-filter-summary.tsv'
    'full-disassembly-provenance.txt'
    'full_raw_sha256'
    'full_raw_lines'
    'full_demangled_sha256'
    'full_demangled_lines'
    'cleanup_disassembly_tmp'
    'addr2line -a -f -C -i'
    'symbol+offset'
    'TIMING-DONE.STAMP'
    '/usr/bin/rm -- "$PARTIAL/TIMING-DONE.STAMP"'
    'SHA256SUMS.tmp'
    'refuse_existing_output'
    'remaining_budget_seconds'
    'run_bounded_input'
    'monotonic_now'
    'DEADLINE_MONOTONIC'
    '/proc/uptime'
    '--kill-after=10s'
    'runner SHA mismatch'
    'binary SHA mismatch'
    'mapper SHA mismatch'
    'instruction map SHA mismatch'
    'orphan candidate/perf process'
    'CELL_RESULT'
    'DECODE_RESULT'
    '[[ $CELL_RESULT == PASS ]] || die "cell failed or void: $file/$preset"'
    '[[ ! -e $OUT && ! -L $OUT ]] || die '\''final output collision before rename'\'''
    'renameat2(AT_FDCWD, source, AT_FDCWD, destination, RENAME_NOREPLACE)'
    'event\":\"rename_failed\",\"reason\":\"$failure'
    'renameat2_errno=[0-9]+_name=EEXIST'
    'rename_noreplace "$PREFLIGHT_DIR" "$PARTIAL"'
    'rename_noreplace "$PARTIAL" "$OUT"'
    'self_test_fail rename_noreplace_collision'
    'self_test_fail rename_noreplace_journal'
    'self_test_fail rename_noreplace_success'
    '/usr/bin/chmod -R a-w -- "$PARTIAL"'
    'Type=exec Restart=no RuntimeMaxSec=4h5m'
    'Restart=no'
    'RuntimeMaxSec=4h5m'
    'NRestarts=0'
    'unit InvocationID does not match current process'
    'systemd MainPID does not match current process'
    'record${index}_buildid_list_rc_$LAST_RC'
    'record${index}_perf_script_rc_$LAST_RC'
    'record${index}_buildid_list_empty'
    'record${index}_perf_script_empty'
    'record${index}_binary_build_id_invalid'
    'record${index}_buildid_dso_identity_mismatch'
    'record${index}_mapper_reduce_rc_$LAST_RC'
    'record${index}_perf_report_rc_$LAST_RC'
    'record${index}_bucket_shares_missing'
    'record${index}_record_diagnostics_missing'
    'record${index}_perf_report_missing'
    'share_compare_failed'
    'row_type == text'
    'corpus_manifest_cells":"3/3'
    'journal_archive_cells":"3/3'
    'index($0,c) && index($0,f) && index($0,p) && index($0,h)'
    'journal archive identity read failed: $file/$preset'
    'journal archive identity mismatch: $file/$preset'
)
for literal in "${runner_literals[@]}"; do
    require_runner_fixed "$literal"
done

mapper_literals=(
    'state_map_predict'
    'range(235, 239)'
    'state_map_predict_call'
    '{296}'
    'state_map_update'
    'range(240, 249)'
    'state_map_update_call'
    '{314}'
    'sm_div'
    'range(97, 105)'
    'ctr_predict_stationary'
    'range(291, 300)'
    'ctr_update_stationary'
    'range(301, 314)'
    'ctr_next_state'
    '{315}'
    'ctr_record_store'
    '{316}'
    'object_address'
    'symbol_offset'
    'target_owner'
    'other_user'
    'other_dso'
    'unmapped binary sample'
    'filter_objdumps'
    'unknown_line_match'
    'target_unresolved'
    'PERF_RECORD_LOST'
    'sample_count'
    'sum_period_squared'
    'SHARE_DELTA_MAX = Decimal("1.00")'
    'EFFECTIVE_SAMPLE_MIN = Decimal("4787")'
    'SIMULTANEOUS_UPPER_BOUND_MAX = Decimal("0.001")'
    '"coverage_percent": "100.000000"'
    'candidate_gate'
    'state_map_total'
    'whole_update'
    'SHARE_DELTA_MAX'
)
for literal in "${mapper_literals[@]}"; do
    require_mapper_fixed "$literal"
done

/usr/bin/grep -qF 'runner_sha=$(verify_runner_provenance)' "$RUNNER" ||
    fail 'runner provenance call missing'
/usr/bin/grep -qE '^[[:space:]]{4}verify_binary_and_code$' "$RUNNER" ||
    fail 'binary provenance call missing'

map_header=$(/usr/bin/python3 - "$MAPPER" <<'PY'
import importlib.util
import sys

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("g3_contract_mapper", path)
if spec is None or spec.loader is None:
    raise SystemExit(2)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
row = module.InstructionRow(1, "raw+0x0", "/src/cm2.rs", 237, True, "state_map_predict", "/bin/cubrim")
print(module.render_instruction_map([row]).splitlines()[0])
PY
) || invalid 'mapper schema probe failed'
bucket_column=$(/usr/bin/awk -F '\t' '{ for (i=1; i<=NF; i++) if ($i=="bucket") print i }' <<<"$map_header")
[[ $bucket_column == 6 ]] || fail "mapper bucket column must be 6, got $bucket_column"
/usr/bin/grep -qF "NR>1 && \$$bucket_column==b" "$RUNNER" ||
    fail 'runner/mapper bucket schema mismatch'

reject_runner_fixed 'taskset -c 16-19'
reject_runner_fixed 'x-ray'
reject_runner_fixed 'Type=oneshot'
reject_runner_fixed '--resume'
reject_runner_fixed '/usr/bin/psql'
reject_runner_fixed '/usr/bin/curl'
reject_runner_fixed 'world_benchmark_'
reject_runner_fixed 'TEST_OVERLAY'
reject_runner_fixed 'decode-attrib-g2-test-overlay.patch'
reject_runner_fixed 'if ! run_cell'
reject_runner_fixed 'NO_SELECT'
reject_runner_fixed '/usr/bin/chmod -R a-w -- "$OUT"'
reject_runner_fixed 'record1_reduction_failed'
reject_runner_fixed 'record2_reduction_failed'
reject_runner_fixed 'final output collision during rename'
reject_runner_fixed '[[ $cycle_class == cycle-agreement ]] || return 0'
reject_runner_fixed '[[ $g3_class1 == instrument-clean || $g3_class2 == instrument-clean ]]'
reject_runner_fixed '/usr/bin/grep -F "\"corpus\":\"$corpus\""'
reject_mapper_fixed 'nearest'

cell_count=$({ /usr/bin/grep -E "^    'silesia\|(dickens|xml)\|(max|web)\|" "$RUNNER" || true; } | /usr/bin/wc -l)
[[ $cell_count == 3 ]] || fail 'cell set must contain exactly 3 rows'

decode_call_count=$({ /usr/bin/grep -E '^[[:space:]]*decode_checked "\$cell_name" (plain|pstat1|pstat2|prec1|prec2) ' "$RUNNER" || true; } | /usr/bin/wc -l)
[[ $decode_call_count == 5 ]] || fail 'each cell must define exactly five verified decodes'

record_call_count=$({ /usr/bin/grep -F '/usr/bin/perf record -q -F 997 -e cycles' "$RUNNER" || true; } | /usr/bin/wc -l)
[[ $record_call_count == 2 ]] || fail 'each cell must define exactly two record decodes'

map_recheck_count=$({ /usr/bin/grep -E '^[[:space:]]*verify_instruction_map$' "$RUNNER" || true; } | /usr/bin/wc -l)
[[ $map_recheck_count == 3 ]] || fail 'map must be rechecked before two records and finalization'

self_test_output=
self_test_rc=0
set +e
self_test_output=$(/usr/bin/bash "$RUNNER" --self-test 2>&1)
self_test_rc=$?
set -e
if ! { (( self_test_rc == 0 )) && [[ $self_test_output == 'current_profile_g3_self_test=PASS' ]]; }; then
    invalid "runner self-test positive control failed: rc=$self_test_rc output=$self_test_output"
fi

line_of_last() {
    local pattern=$1 line
    line=$({ /usr/bin/grep -nE -- "$pattern" "$RUNNER" || true; } | /usr/bin/tail -n 1 | /usr/bin/cut -d: -f1)
    [[ -n $line ]] || fail "missing ordered call: $pattern"
    printf '%s\n' "$line"
}

admission_line=$(line_of_last '^[[:space:]]{4}admission "\$PREFLIGHT_DIR" 1$')
failure_trap_line=$(line_of_last '^[[:space:]]{4}trap on_exit EXIT$')
suites_line=$(line_of_last '^[[:space:]]{4}run_suites$')
map_line=$(line_of_last '^[[:space:]]{4}build_instruction_map$')
cells_line=$(line_of_last '^[[:space:]]{4}for cell in "\$\{CELLS\[@\]\}"; do$')
fixture_line=$(line_of_last '^[[:space:]]{4}verify_feasibility_fixture "\$PARTIAL"$')
(( failure_trap_line < admission_line && admission_line < suites_line && suites_line < map_line && map_line < fixture_line && fixture_line < cells_line )) ||
    fail 'main ordering must be failure-trap -> admission -> suites -> map -> fixture -> cells'

manifest_line=$(line_of_last '^[[:space:]]*write_manifests$')
marker_line=$(line_of_last '^[[:space:]]*write_completion_marker$')
verify_map_line=$(line_of_last '^[[:space:]]*verify_instruction_map$')
rename_line=$(line_of_last '^[[:space:]]*rename_noreplace "\$PARTIAL" "\$OUT"$')
chmod_line=$(line_of_last '^[[:space:]]*/usr/bin/chmod -R a-w -- "\$PARTIAL"$')
(( verify_map_line < manifest_line && manifest_line < marker_line && marker_line < chmod_line && chmod_line < rename_line )) ||
    fail 'completion ordering must be map -> manifests -> marker -> chmod -> rename'
next_after_rename=$(/usr/bin/sed -n "$((rename_line + 1))p" "$RUNNER")
[[ $next_after_rename == '}' ]] ||
    fail 'final rename must be the last fallible main_run operation'

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
    if ! { (( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == 'current_profile_g3_contract=PASS' ]]; }; then
        invalid "positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
    fi

    capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$mutation_root/missing.sh" MAPPER="$MAPPER" /usr/bin/bash "$SELF"
    if ! { (( CHILD_RC == 2 )) && [[ $CHILD_OUTPUT == current_profile_g3_contract=HARNESS_INVALID\ reason=runner\ not\ found:* ]]; }; then
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
        ! /usr/bin/grep -qF 'current_profile_g3_contract=PASS' <<<"$CHILD_OUTPUT" || invalid "mutation emitted PASS: $label"
        /usr/bin/grep -qF "current_profile_g3_contract=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_mapper_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 mutant
        mutant=$mutation_root/$label.py
        /usr/bin/cp -- "$MAPPER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$MAPPER" "$mutant" || fail "mutation did not change mapper: $label"
        capture_child /usr/bin/env SELF_MUTATION_TESTS=0 RUNNER="$RUNNER" MAPPER="$mutant" /usr/bin/bash "$SELF"
        (( CHILD_RC != 0 )) || fail "mapper mutation survived: $label"
        /usr/bin/grep -qF "current_profile_g3_contract=FAIL reason=$expected_reason" <<<"$CHILD_OUTPUT" ||
            invalid "mapper mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_self_test_mutant_red() {
        local label=$1 expression=$2 expected_reason=$3 mutant
        mutant=$mutation_root/$label.sh
        /usr/bin/cp -- "$RUNNER" "$mutant"
        /usr/bin/sed -i "$expression" "$mutant"
        ! /usr/bin/cmp -s -- "$RUNNER" "$mutant" || fail "mutation did not change runner: $label"
        capture_child /usr/bin/bash "$mutant" --self-test
        (( CHILD_RC != 0 )) || fail "runner self-test mutation survived: $label"
        [[ $CHILD_OUTPUT == "current_profile_g3_self_test=FAIL reason=$expected_reason" ]] ||
            invalid "runner self-test mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
    }

    expect_runner_mutant_red pin 's/taskset -c 0-15/taskset -c 16-19/g' 'runner missing literal: taskset -c 0-15'
    expect_runner_mutant_red commit 's/e0e8bdb2c2df924877d9dcf8a1897810683a147a/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef/g' 'runner missing literal: e0e8bdb2c2df924877d9dcf8a1897810683a147a'
    expect_runner_mutant_red archive 's/b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/g' 'runner missing literal: b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82'
    expect_runner_mutant_red archive_xml 's/d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/g' 'runner missing literal: d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37'
    expect_runner_mutant_red archive_web 's/a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/g' 'runner missing literal: a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341'
    expect_runner_mutant_red source 's/b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/g' 'runner missing literal: b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    expect_runner_mutant_red source_xml 's/0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/g' 'runner missing literal: 0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c'
    expect_runner_mutant_red timeout 's/dickens|max|10192446|1340|435/dickens|max|10192446|1339|435/' 'runner missing literal: dickens|max|10192446|1340|435'
    expect_runner_mutant_red timeout_dickens_decode 's/dickens|max|10192446|1340|435/dickens|max|10192446|1340|434/' 'runner missing literal: dickens|max|10192446|1340|435'
    expect_runner_mutant_red timeout_xml_encode 's/xml|max|5345280|520|175/xml|max|5345280|519|175/' 'runner missing literal: xml|max|5345280|520|175'
    expect_runner_mutant_red timeout_xml_decode 's/xml|max|5345280|520|175/xml|max|5345280|520|174/' 'runner missing literal: xml|max|5345280|520|175'
    expect_runner_mutant_red timeout_web_encode 's/dickens|web|10192446|380|320/dickens|web|10192446|379|320/' 'runner missing literal: dickens|web|10192446|380|320'
    expect_runner_mutant_red timeout_web_decode 's/dickens|web|10192446|380|320/dickens|web|10192446|380|319/' 'runner missing literal: dickens|web|10192446|380|320'
    expect_runner_mutant_red bytes_xml 's/xml|max|5345280|520|175/xml|max|5345279|520|175/' 'runner missing literal: xml|max|5345280|520|175'
    expect_runner_mutant_red cell_xml 's/xml|max|5345280/x-ray|max|5345280/' 'runner missing literal: xml|max|5345280|520|175'
    expect_runner_mutant_red cycles 's/CYCLE_DISAGREEMENT_MAX=0.10/CYCLE_DISAGREEMENT_MAX=0.11/' 'runner missing literal: readonly CYCLE_DISAGREEMENT_MAX=0.10'
    expect_runner_mutant_red g3 's/G3_RATIO_MAX=1.10/G3_RATIO_MAX=1.11/' 'runner missing literal: readonly G3_RATIO_MAX=1.10'
    expect_runner_mutant_red shares 's/SHARE_DELTA_MAX=1.00/SHARE_DELTA_MAX=1.01/' 'runner missing literal: readonly SHARE_DELTA_MAX=1.00'
    expect_runner_mutant_red fixture_bytes 's/FEASIBILITY_FIXTURE_BYTES=65536/FEASIBILITY_FIXTURE_BYTES=65535/' 'runner missing literal: readonly FEASIBILITY_FIXTURE_BYTES=65536'
    expect_runner_mutant_red fixture_source_sha 's/de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' 'runner missing literal: de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'
    expect_runner_mutant_red fixture_archive_sha 's/352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/' 'runner missing literal: 352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3'
    expect_runner_mutant_red journal_identity_reason 's/journal archive identity mismatch: \$file\/\$preset/journal archive mismatch: $file\/$preset/' 'runner missing literal: journal archive identity mismatch: $file/$preset'
    expect_runner_mutant_red record2 's/decode_checked "$cell_name" prec2/decode_checked "$cell_name" precX/' 'runner missing literal: prec2'
    expect_runner_mutant_red systemd 's/Type=exec/Type=oneshot/g' 'runner missing literal: Type=exec Restart=no RuntimeMaxSec=4h5m'
    expect_runner_mutant_red runner_auth 's/verify_runner_provenance/verify_runner_provenance_disabled/g' 'runner provenance call missing'
    expect_runner_mutant_red binary_auth 's/verify_binary_and_code/verify_binary_and_code_disabled/g' 'binary provenance call missing'
    expect_runner_mutant_red map_recheck '0,/^[[:space:]]*verify_instruction_map$/s//    : # map check removed/' 'map must be rechecked before two records and finalization'
    expect_runner_mutant_red map_schema 's/NR>1 && $6==b/NR>1 \&\& $5==b/' 'runner missing literal: NR>1 && $6==b'
    expect_runner_mutant_red invocation_match 's/unit InvocationID does not match current process/unit InvocationID unchecked/' 'runner missing literal: unit InvocationID does not match current process'
    expect_runner_mutant_red manifest_type 's/row_type == text/row_type == binary/' 'runner missing literal: row_type == text'
    expect_runner_mutant_red build_id 's/binary_build_id/binary_note_id/g' 'runner missing literal: binary_build_id'
    expect_runner_mutant_red perf_version 's/perf_version/perf_tool_version/g' 'runner missing literal: perf_version'
    expect_runner_mutant_red provenance_order '0,/"\$BINARY_BUILD_ID" "\$lock_sha" "\$CODE_COMMIT"/s//"$lock_sha" "$BINARY_BUILD_ID" "$CODE_COMMIT"/' 'runner missing literal: "$BINARY_BUILD_ID" "$lock_sha" "$CODE_COMMIT"'
    expect_runner_mutant_red buildid_dso 's/tolower($1)==id && $2==dso { matches++ }/tolower($1)==id \&\& $2!=dso { matches++ }/' 'runner missing literal: tolower($1)==id && $2==dso { matches++ }'
    expect_mapper_mutant_red p12_boundary 's/range(235, 239)/range(236, 239)/' 'mapper missing literal: range(235, 239)'
    expect_mapper_mutant_red smdiv_boundary 's/range(97, 105)/range(98, 105)/' 'mapper missing literal: range(97, 105)'
    expect_mapper_mutant_red unresolved_bucket 's/target_unresolved/target_inferred/g' 'mapper missing literal: target_unresolved'
    expect_mapper_mutant_red lost_records 's/PERF_RECORD_LOST/PERF_RECORD_DROPPED/g' 'mapper missing literal: PERF_RECORD_LOST'
    expect_mapper_mutant_red coverage 's/"coverage_percent": "100.000000"/"coverage_percent": "99.000000"/' 'mapper missing literal: "coverage_percent": "100.000000"'
    expect_mapper_mutant_red target_owner 's/target_owner/owner_hint/g' 'mapper missing literal: target_owner'
    expect_mapper_mutant_red mapper_shares 's/SHARE_DELTA_MAX = Decimal("1.00")/SHARE_DELTA_MAX = Decimal("2.00")/' 'mapper missing literal: SHARE_DELTA_MAX = Decimal("1.00")'
    expect_mapper_mutant_red neff 's/EFFECTIVE_SAMPLE_MIN = Decimal("4787")/EFFECTIVE_SAMPLE_MIN = Decimal("4786")/' 'mapper missing literal: EFFECTIVE_SAMPLE_MIN = Decimal("4787")'
    expect_mapper_mutant_red upper_bound 's/SIMULTANEOUS_UPPER_BOUND_MAX = Decimal("0.001")/SIMULTANEOUS_UPPER_BOUND_MAX = Decimal("0.002")/' 'mapper missing literal: SIMULTANEOUS_UPPER_BOUND_MAX = Decimal("0.001")'
    expect_self_test_mutant_red cycles_runtime 's/CYCLE_DISAGREEMENT_MAX=0.10/CYCLE_DISAGREEMENT_MAX=0.11/' 'cycle_threshold_boundary'
    expect_self_test_mutant_red g3_runtime 's/G3_RATIO_MAX=1.10/G3_RATIO_MAX=1.11/' 'g3_threshold_boundary'
    expect_self_test_mutant_red share_runtime 's/SHARE_DELTA_MAX=1.00/SHARE_DELTA_MAX=1.01/' 'share_threshold_boundary'
    expect_self_test_mutant_red both_records 's/first == instrument-clean && \$second == instrument-clean/first == instrument-clean || $second == instrument-clean/' 'both_records_clean'
fi

printf 'current_profile_g3_contract=PASS\n'
