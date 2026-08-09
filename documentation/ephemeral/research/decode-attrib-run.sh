#!/usr/bin/env bash
# Fail-closed Generation G2 decode-time attribution runner for NEW-24.
# Protocol: CUBR-DECODE-ATTRIB-20260809.md plus its 2026-08-09 amendment.
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

readonly ROOT=/root/phaseC
readonly CUBRIM=$ROOT/cubrim-3a13f48
readonly CUBRIM_SHA_EXPECT=d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb
readonly CODE_DIR=/root/cubr-decode-attrib-g2-code
readonly CODE_COMMIT=3a13f486aea51470e2079ba66abb94d99fd782d9
readonly TEST_OVERLAY=/root/cubr-decode-attrib-g2-test-overlay.patch
readonly TEST_OVERLAY_SHA_EXPECT=b0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec
readonly TEST_OVERLAY_SOURCE_COMMIT=3c06a213ce0c45ee16e1452fbe9ab2346ccb6a2a
readonly TEST_FIXTURE_COMMIT=a3d399f57aa8ee5b7c172afd5322a7f7a1e14392
readonly TEST_FIXTURE_TREE_EXPECT=8248283bcab58b4c4078b4a78425cd8717f165f7
readonly TEST_FIXTURE_DIR=documentation/ephemeral/research/corpus
readonly GENERATED_CARGO_LOCK=code/cubrim-rs/Cargo.lock
readonly CORPUS_ROOT=/root/corpus-full/silesia
readonly CORPUS_MANIFEST=$ROOT/corpus_manifest.tsv
readonly OUT=/root/cubr-decode-attrib-g2-20260809
readonly PARTIAL=$OUT.partial
readonly CARGO=/root/.cargo/bin/cargo
readonly G3_RATIO_MAX=1.10
readonly CYCLE_DISAGREEMENT_MAX=0.10
readonly PERF_VALUE_RE='^[0-9]+([.][0-9]+)?$'
readonly CAMPAIGN_BUDGET_SECONDS=14400
readonly LOAD_MAX=8.0
readonly -a PIN=(/usr/bin/taskset -c 0-15)
readonly EXPECTED_RUNNER_SHA=${CUBR_EXPECTED_RUNNER_SHA256:-}
readonly SIDE_EFFECT_28=documentation/ephemeral/research/CUBR-0028-bench.json
readonly SIDE_EFFECT_31=documentation/ephemeral/research/CUBR-0031-bench.json

# corpus|file|preset|archive_sha|orig_sha|orig_bytes|encode_timeout_s|decode_timeout_s
readonly -a CELLS=(
    'silesia|dickens|max|b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a|10192446|1340|435'
    'silesia|xml|max|d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37|0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c|5345280|520|175'
    'silesia|x-ray|max|4ed8a550b2e05da471d33dd9f044c4e357fee45cfc77bbfcdb3f173a657953d7|7de9fce1405dc44ae5e6813ed21cd5751e761bd4265655a005d39b9685d1c9ad|8474240|940|20'
    'silesia|dickens|web|a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a|10192446|380|320'
)

export CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4

JOURNAL=
DEADLINE_MONOTONIC=0
LAST_WALL=
LAST_RC=0
CURRENT_CELL=
PREFLIGHT_DIR=
CELL_RESULT=
DECODE_RESULT=
TEST_OVERLAY_ACTIVE=0

now() { /usr/bin/date -u +%Y-%m-%dT%H:%M:%SZ; }
sha() { /usr/bin/sha256sum "$1" | /usr/bin/awk '{print $1}'; }
monotonic_now() { /usr/bin/awk '{print $1}' /proc/uptime; }
monotonic_seconds() {
    local value
    value=$(monotonic_now)
    /usr/bin/printf '%s\n' "${value%%.*}"
}

jlog() {
    [[ -n $JOURNAL ]] || return 0
    /usr/bin/printf '%s\n' "$1" >>"$JOURNAL"
}

die() {
    jlog "{\"t\":\"$(now)\",\"event\":\"abort\",\"reason\":\"$1\"}"
    /usr/bin/printf 'decode-attrib G2: %s\n' "$1" >&2
    exit 1
}

refuse_existing_output() {
    [[ ! -e $OUT && ! -L $OUT ]] || {
        /usr/bin/printf 'decode-attrib G2: output exists: %s\n' "$OUT" >&2
        return 1
    }
    [[ ! -e $PARTIAL && ! -L $PARTIAL ]] || {
        /usr/bin/printf 'decode-attrib G2: partial output exists: %s\n' "$PARTIAL" >&2
        return 1
    }
}

remaining_budget_seconds() {
    local now_monotonic remaining
    now_monotonic=$(monotonic_now) || return 1
    [[ $now_monotonic =~ ^[0-9]+([.][0-9]+)?$ ]] || return 1
    now_monotonic=${now_monotonic%%.*}
    remaining=$((DEADLINE_MONOTONIC - now_monotonic))
    (( remaining > 0 )) || remaining=0
    /usr/bin/printf '%s\n' "$remaining"
}

run_bounded() {
    local requested=$1 stdout=$2 stderr=$3
    shift 3
    local remaining limit start_monotonic end_monotonic rc
    if ! remaining=$(remaining_budget_seconds); then
        LAST_RC=125
        LAST_WALL=0.000
        return 125
    fi
    (( remaining > 0 )) || { LAST_RC=124; LAST_WALL=0.000; return 124; }
    limit=$requested
    (( remaining < limit )) && limit=$remaining
    start_monotonic=$(monotonic_now)
    set +e
    /usr/bin/timeout --signal=TERM --kill-after=10s "${limit}s" "$@" >"$stdout" 2>"$stderr"
    rc=$?
    set -e
    end_monotonic=$(monotonic_now)
    LAST_RC=$rc
    LAST_WALL=$(/usr/bin/awk -v a="$start_monotonic" -v b="$end_monotonic" 'BEGIN { printf "%.3f", b-a }')
    return "$rc"
}

classify_cycle_agreement() {
    local first=$1 second=$2
    /usr/bin/awk -v a="$first" -v b="$second" -v m="$CYCLE_DISAGREEMENT_MAX" 'BEGIN {
        d=a-b; if (d<0) d=-d; largest=(a>b?a:b); ratio=(largest>0?d/largest:1);
        if (ratio<=m) print "cycle-agreement|" ratio; else print "cycle-disagreement|" ratio;
    }'
}

classify_instrument_overhead() {
    local plain=$1 record=$2
    /usr/bin/awk -v p="$plain" -v r="$record" -v m="$G3_RATIO_MAX" 'BEGIN {
        ratio=(p>0?r/p:999); if (ratio<=m) print "instrument-clean|" ratio;
        else print "instrument-perturbed|" ratio;
    }'
}

verify_runner_provenance() {
    local actual
    [[ $EXPECTED_RUNNER_SHA =~ ^[0-9a-f]{64}$ ]] || die 'reviewed runner SHA is missing or malformed'
    actual=$(sha "${BASH_SOURCE[0]}")
    [[ $actual == "$EXPECTED_RUNNER_SHA" ]] || die "runner SHA mismatch: expected $EXPECTED_RUNNER_SHA got $actual"
    /usr/bin/printf '%s\n' "$actual"
}

verify_topology() {
    local model
    model=$(/usr/bin/lscpu | /usr/bin/awk -F: '$1 ~ /Model name/ { sub(/^[ \t]+/, "", $2); print $2; exit }')
    [[ $model == 'AMD EPYC 7502P 32-Core Processor' ]] || return 1
    /usr/bin/lscpu -p=CPU,CORE | /usr/bin/awk -F, '
        $1 !~ /^#/ {
            if ($1 !~ /^[0-9]+$/ || $2 !~ /^[0-9]+$/ || ($1 in core)) exit 1;
            core[$1]=$2; count++;
        }
        END {
            if (count != 64) exit 1;
            for (i=0; i<32; i++) if (!(i in core) || core[i] != i) exit 1;
            for (i=32; i<64; i++) if (!(i in core) || core[i] != i-32) exit 1;
        }
    '
}

reject_orphan_processes() {
    local found
    if ! found=$(/usr/bin/ps -eo pid=,ppid=,comm=,args= | /usr/bin/awk -v self="$$" -v parent="$PPID" '
        $1 != self && $1 != parent &&
        ($3 == "cubrim-3a13f48" || $3 == "perf" || ($3 == "bash" && $0 ~ /cubr-decode-attrib-run[.]sh/)) { print }
    '); then
        die 'process scan failed'
    fi
    [[ -z $found ]] || {
        /usr/bin/printf '%s\n' "$found" >&2
        die 'orphan candidate/perf process or competing attribution runner'
    }
}

quiet_wait() {
    local load remaining
    while :; do
        reject_orphan_processes
        if ! load=$(/usr/bin/awk '{print $1}' /proc/loadavg); then
            die 'load average read failed'
        fi
        [[ $load =~ ^[0-9]+([.][0-9]+)?$ ]] || die 'load average read failed'
        if /usr/bin/awk -v l="$load" -v m="$LOAD_MAX" 'BEGIN { exit !(l<m) }'; then
            return 0
        fi
        remaining=$(remaining_budget_seconds) || die 'monotonic budget read failed'
        (( remaining > 60 )) || return 1
        /usr/bin/sleep 60
    done
}

verify_binary_and_code() {
    [[ -x $CUBRIM ]] || die 'campaign binary is not executable'
    [[ $(sha "$CUBRIM") == "$CUBRIM_SHA_EXPECT" ]] || die 'campaign binary SHA mismatch'
    [[ -x $CARGO ]] || die 'cargo is not executable'
    [[ $(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD) == "$CODE_COMMIT" ]] || die 'code checkout commit mismatch'
    if /usr/bin/git -C "$CODE_DIR" symbolic-ref -q HEAD >/dev/null 2>&1; then
        die 'code checkout is not detached'
    fi
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain) ]] || die 'code checkout is dirty before suites'
    [[ -f $TEST_OVERLAY && ! -L $TEST_OVERLAY ]] || die 'test overlay is missing or unsafe'
    [[ $(sha "$TEST_OVERLAY") == "$TEST_OVERLAY_SHA_EXPECT" ]] || die 'test overlay SHA mismatch'
    /usr/bin/git -C "$CODE_DIR" diff --no-ext-diff --binary --unified=0 "$CODE_COMMIT" "$TEST_OVERLAY_SOURCE_COMMIT" -- \
        code/cubrim-rs/src/config.rs code/cubrim-rs/tests/differential.rs |
        /usr/bin/cmp -s -- "$TEST_OVERLAY" - || die 'test overlay source diff mismatch'
    /usr/bin/git -C "$CODE_DIR" apply --check "$TEST_OVERLAY" || die 'test overlay does not apply to frozen code'
    [[ $(/usr/bin/git -C "$CODE_DIR" rev-parse "$TEST_FIXTURE_COMMIT:$TEST_FIXTURE_DIR") == "$TEST_FIXTURE_TREE_EXPECT" ]] ||
        die 'test fixture tree mismatch'
    [[ ! -e $CODE_DIR/$TEST_FIXTURE_DIR && ! -L $CODE_DIR/$TEST_FIXTURE_DIR ]] || die 'test fixture path exists before preparation'
    [[ ! -e $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] || die 'generated Cargo lock path exists before preparation'
}

verify_manifest_source() {
    local corpus=$1 file=$2 want_sha=$3 want_bytes=$4
    local -a rows
    local row_corpus row_file row_type row_bytes row_sha src
    mapfile -t rows < <(/usr/bin/awk -F '\t' -v c="$corpus" -v f="$file" 'NR>1 && $1==c && $2==f { print }' "$CORPUS_MANIFEST")
    [[ ${#rows[@]} == 1 ]] || die "manifest cardinality mismatch: $corpus/$file"
    IFS=$'\t' read -r row_corpus row_file row_type row_bytes row_sha <<<"${rows[0]}"
    : "$row_type"
    [[ $row_corpus == "$corpus" && $row_file == "$file" && $row_bytes == "$want_bytes" && $row_sha == "$want_sha" ]] ||
        die "manifest row mismatch: $corpus/$file"
    src=$CORPUS_ROOT/$file
    [[ -f $src && ! -L $src ]] || die "source missing or unsafe: $src"
    [[ $(/usr/bin/stat -c %s "$src") == "$want_bytes" ]] || die "source size mismatch: $src"
    [[ $(sha "$src") == "$want_sha" ]] || die "source SHA mismatch: $src"
    /usr/bin/printf '%s\n' "$src"
}

verify_journal_archive() {
    local corpus=$1 file=$2 preset=$3 want_sha=$4
    local journal=$ROOT/journal.$preset.jsonl
    local matches
    matches=$(/usr/bin/grep -F "\"corpus\":\"$corpus\"" "$journal" |
        /usr/bin/grep -F "\"file\":\"$file\"" |
        /usr/bin/grep -F "\"preset\":\"$preset\"" |
        /usr/bin/grep -F "\"archive_sha256\":\"$want_sha\"")
    [[ $(/usr/bin/printf '%s\n' "$matches" | /usr/bin/grep -c .) == 1 ]] ||
        die "journal archive identity mismatch: $file/$preset"
}

perf_smoke() {
    local d=$1
    run_bounded 10 "$d/perf-stat-smoke.out" "$d/perf-stat-smoke.err" \
        /usr/bin/perf stat -e cycles -o "$d/perf-stat-smoke.txt" -- \
        /usr/bin/taskset -c 0 /usr/bin/true || die 'perf stat smoke failed'
    run_bounded 10 "$d/perf-record-smoke.out" "$d/perf-record-smoke.err" \
        /usr/bin/perf record -q -F 99 -e cycles -o "$d/perf-record-smoke.data" -- \
        /usr/bin/taskset -c 0 /usr/bin/sleep 0.05 || die 'perf record smoke failed'
    [[ -s $d/perf-record-smoke.data ]] || die 'perf record smoke produced no data'
}

admission() {
    local evidence=$1 runner_sha host load cell corpus file preset archive_sha orig_sha orig_bytes enc_timeout dec_timeout admission_record
    host=$(/usr/bin/hostname -s)
    [[ $host == dev-ai ]] || die 'hostname admission failed'
    verify_topology || die 'CPU topology admission failed'
    runner_sha=$(verify_runner_provenance)
    verify_binary_and_code
    reject_orphan_processes
    quiet_wait || die 'host did not become quiet before admission deadline'
    load=$(/usr/bin/awk '{print $1}' /proc/loadavg)
    perf_smoke "$evidence"
    for cell in "${CELLS[@]}"; do
        IFS='|' read -r corpus file preset archive_sha orig_sha orig_bytes enc_timeout dec_timeout <<<"$cell"
        : "$enc_timeout" "$dec_timeout"
        verify_manifest_source "$corpus" "$file" "$orig_sha" "$orig_bytes" >/dev/null
        verify_journal_archive "$corpus" "$file" "$preset" "$archive_sha"
    done
    /usr/bin/printf 'host=%s\ntopology=%s\nload1=%s\npin=0-15\nrunner_sha256=%s\nbinary_sha256=%s\ncode_commit=%s\ncode_detached=true\ncode_clean=true\ntest_overlay_sha256=%s\ntest_overlay_source_commit=%s\ntest_overlay_apply_check=PASS\ntest_fixture_commit=%s\ntest_fixture_tree=%s\nperf_stat_smoke=PASS\nperf_record_smoke=PASS\ncorpus_manifest_cells=4/4\njournal_archive_cells=4/4\n' \
        "$host" 'cpu0-31=core0-31;cpu32-63=smt0-31' "$load" "$runner_sha" \
        "$CUBRIM_SHA_EXPECT" "$CODE_COMMIT" "$TEST_OVERLAY_SHA_EXPECT" "$TEST_OVERLAY_SOURCE_COMMIT" \
        "$TEST_FIXTURE_COMMIT" "$TEST_FIXTURE_TREE_EXPECT" >"$evidence/PROVENANCE.txt"
    printf -v admission_record '{"t":"%s","event":"admission_pass","host":"%s","topology":"cpu0-31=core0-31;cpu32-63=smt0-31","load1":%s,"pin":"0-15","runner_sha256":"%s","binary_sha256":"%s","code_commit":"%s","code_detached":true,"code_clean":true,"test_overlay_sha256":"%s","test_overlay_source_commit":"%s","test_overlay_apply_check":"PASS","test_fixture_commit":"%s","test_fixture_tree":"%s","perf_stat_smoke":"PASS","perf_record_smoke":"PASS","corpus_manifest_cells":"4/4","journal_archive_cells":"4/4"}' \
        "$(now)" "$host" "$load" "$runner_sha" "$CUBRIM_SHA_EXPECT" "$CODE_COMMIT" "$TEST_OVERLAY_SHA_EXPECT" "$TEST_OVERLAY_SOURCE_COMMIT" \
        "$TEST_FIXTURE_COMMIT" "$TEST_FIXTURE_TREE_EXPECT"
    jlog "$admission_record"
}

verify_test_fixtures() {
    local -a paths
    local path
    mapfile -t paths < <(/usr/bin/git -C "$CODE_DIR" ls-tree -r --name-only "$TEST_FIXTURE_COMMIT" -- "$TEST_FIXTURE_DIR")
    [[ ${#paths[@]} == 10 ]] || die 'test fixture count mismatch'
    for path in "${paths[@]}"; do
        [[ -f $CODE_DIR/$path && ! -L $CODE_DIR/$path ]] || die "test fixture missing or unsafe: $path"
        /usr/bin/git -C "$CODE_DIR" cat-file blob "$TEST_FIXTURE_COMMIT:$path" |
            /usr/bin/cmp -s -- - "$CODE_DIR/$path" || die "test fixture bytes mismatch: $path"
    done
}

prepare_test_inputs() {
    [[ ! -e $CODE_DIR/$TEST_FIXTURE_DIR && ! -L $CODE_DIR/$TEST_FIXTURE_DIR ]] || die 'test fixture path collision'
    [[ ! -e $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] || die 'generated Cargo lock path collision'
    /usr/bin/git -C "$CODE_DIR" archive "$TEST_FIXTURE_COMMIT" -- "$TEST_FIXTURE_DIR" |
        /usr/bin/tar -x -C "$CODE_DIR"
    verify_test_fixtures
    jlog "{\"t\":\"$(now)\",\"event\":\"test_fixtures_prepared\",\"commit\":\"$TEST_FIXTURE_COMMIT\",\"tree\":\"$TEST_FIXTURE_TREE_EXPECT\"}"
}

cleanup_test_inputs() {
    local -a paths
    local path
    verify_test_fixtures
    mapfile -t paths < <(/usr/bin/git -C "$CODE_DIR" ls-tree -r --name-only "$TEST_FIXTURE_COMMIT" -- "$TEST_FIXTURE_DIR")
    : >"$PARTIAL/test-fixtures.sha256"
    for path in "${paths[@]}"; do
        /usr/bin/printf '%s  %s\n' "$(sha "$CODE_DIR/$path")" "$path" >>"$PARTIAL/test-fixtures.sha256"
    done
    [[ -e $CODE_DIR/$GENERATED_CARGO_LOCK || -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] ||
        die 'generated Cargo lock missing after suites'
    [[ -f $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] || die 'generated Cargo lock is unsafe'
    /usr/bin/cp -- "$CODE_DIR/$GENERATED_CARGO_LOCK" "$PARTIAL/cargo-generated.lock"
    /usr/bin/git -C "$CODE_DIR" clean -fdX -- "$TEST_FIXTURE_DIR" "$GENERATED_CARGO_LOCK"
    [[ ! -e $CODE_DIR/$TEST_FIXTURE_DIR && ! -L $CODE_DIR/$TEST_FIXTURE_DIR ]] || die 'test fixture cleanup failed'
    [[ ! -e $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] || die 'generated Cargo lock cleanup failed'
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain) ]] || die 'code checkout dirty after test input cleanup'
    jlog "{\"t\":\"$(now)\",\"event\":\"test_inputs_removed\",\"code_clean\":true}"
}

verify_test_overlay_applied() {
    local status expected
    status=$(/usr/bin/git -C "$CODE_DIR" status --porcelain)
    expected=$' M code/cubrim-rs/src/config.rs\n M code/cubrim-rs/tests/differential.rs'
    [[ $status == "$expected" ]] || die "test overlay status mismatch: $status"
    /usr/bin/git -C "$CODE_DIR" diff --no-ext-diff --binary --unified=0 -- \
        code/cubrim-rs/src/config.rs code/cubrim-rs/tests/differential.rs |
        /usr/bin/cmp -s -- "$TEST_OVERLAY" - || die 'applied test overlay bytes mismatch'
}

apply_test_overlay() {
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain) ]] || die 'code checkout dirty before test overlay'
    /usr/bin/git -C "$CODE_DIR" apply --check "$TEST_OVERLAY" || die 'test overlay apply check failed'
    /usr/bin/git -C "$CODE_DIR" apply "$TEST_OVERLAY" || die 'test overlay apply failed'
    TEST_OVERLAY_ACTIVE=1
    verify_test_overlay_applied
    jlog "{\"t\":\"$(now)\",\"event\":\"test_overlay_applied\",\"sha256\":\"$TEST_OVERLAY_SHA_EXPECT\"}"
}

remove_test_overlay() {
    verify_test_overlay_applied
    /usr/bin/git -C "$CODE_DIR" apply -R --check "$TEST_OVERLAY" || die 'test overlay reverse check failed'
    /usr/bin/git -C "$CODE_DIR" apply -R "$TEST_OVERLAY" || die 'test overlay reverse failed'
    TEST_OVERLAY_ACTIVE=0
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain) ]] || die 'code checkout dirty after test overlay removal'
    jlog "{\"t\":\"$(now)\",\"event\":\"test_overlay_removed\",\"code_clean\":true}"
}

restore_suite_side_effects() {
    local status line path tmp
    status=$(/usr/bin/git -C "$CODE_DIR" status --porcelain)
    [[ -n $status ]] || return 0
    while IFS= read -r line; do
        case $line in
            " M code/cubrim-rs/src/config.rs" | " M code/cubrim-rs/tests/differential.rs")
                (( TEST_OVERLAY_ACTIVE == 1 )) || die "unexpected test overlay state: $line"
                continue
                ;;
            " M $SIDE_EFFECT_28") path=$SIDE_EFFECT_28 ;;
            " M $SIDE_EFFECT_31") path=$SIDE_EFFECT_31 ;;
            *) die "unexpected suite side effect: $line" ;;
        esac
        [[ -f $CODE_DIR/$path && ! -L $CODE_DIR/$path ]] || die "unsafe suite side-effect path: $path"
        tmp=$CODE_DIR/$path.g2restore-tmp
        [[ ! -e $tmp && ! -L $tmp ]] || die "restore temp collision: $tmp"
        /usr/bin/git -C "$CODE_DIR" show "HEAD:$path" >"$tmp"
        /usr/bin/chmod --reference="$CODE_DIR/$path" "$tmp"
        /usr/bin/mv -- "$tmp" "$CODE_DIR/$path"
    done <<<"$status"
    if (( TEST_OVERLAY_ACTIVE == 1 )); then
        verify_test_overlay_applied
    else
        [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain) ]] || die 'code checkout dirty after suite restore'
    fi
    /usr/bin/printf '%s\n' "$status" >>"$PARTIAL/suite-side-effects-restored.txt"
}

run_suites() {
    local remaining suite_rc
    remaining=$(remaining_budget_seconds)
    (( remaining > 0 )) || die 'campaign budget expired before suites'
    prepare_test_inputs
    apply_test_overlay
    # Required exact commands: cargo test --release
    set +e
    (cd "$CODE_DIR/code/cubrim-rs" &&
        /usr/bin/timeout --signal=TERM --kill-after=10s "${remaining}s" "$CARGO" test --release) \
        >"$PARTIAL/cargo-test-release.log" 2>&1
    suite_rc=$?
    set -e
    restore_suite_side_effects
    if (( suite_rc != 0 )); then
        remove_test_overlay
        cleanup_test_inputs
        die 'cargo test --release failed'
    fi
    remaining=$(remaining_budget_seconds)
    if (( remaining == 0 )); then
        remove_test_overlay
        cleanup_test_inputs
        die 'campaign budget expired before differential suite'
    fi
    # Required exact command: cargo test --release --test differential -- --nocapture
    set +e
    (cd "$CODE_DIR/code/cubrim-rs" &&
        /usr/bin/timeout --signal=TERM --kill-after=10s "${remaining}s" "$CARGO" test --release --test differential -- --nocapture) \
        >"$PARTIAL/cargo-test-differential.log" 2>&1
    suite_rc=$?
    set -e
    restore_suite_side_effects
    remove_test_overlay
    cleanup_test_inputs
    (( suite_rc == 0 )) || die 'differential integration test failed'
    jlog "{\"t\":\"$(now)\",\"event\":\"suites_pass\"}"
}

decode_checked() {
    local cell_name=$1 tag=$2 timeout_s=$3 src=$4 archive=$5 orig_sha=$6 d=$7
    shift 7
    local output=$d/$tag.bin rc wall output_sha
    DECODE_RESULT=FAIL
    quiet_wait || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"reason\":\"host_not_quiet_before_$tag\"}"; return 0; }
    /usr/bin/rm -f -- "$output"
    if run_bounded "$timeout_s" "$d/$tag.out" "$d/$tag.err" "$@" "${PIN[@]}" "$CUBRIM" decompress --quiet "$archive" "$output"; then
        rc=0
    else
        rc=$LAST_RC
    fi
    wall=$LAST_WALL
    [[ $rc == 0 ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"tag\":\"$tag\",\"reason\":\"decode_rc_$rc\"}"
        return 0
    }
    /usr/bin/cmp -- "$src" "$output" || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G2-cmp\",\"tag\":\"$tag\"}"
        return 0
    }
    output_sha=$(sha "$output")
    [[ $output_sha == "$orig_sha" ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G2-sha\",\"tag\":\"$tag\"}"
        return 0
    }
    /usr/bin/rm -- "$output"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"decode_ok\",\"tag\":\"$tag\",\"wall_s\":$wall,\"output_sha256\":\"$output_sha\"}"
    DECODE_RESULT=PASS
    return 0
}

parse_cycles() {
    local file=$1 value
    value=$(/usr/bin/awk -F '\t' '$3=="cycles" && $1 ~ /^[0-9]+$/ { print $1; exit }' "$file")
    [[ $value =~ ^[0-9]+$ && $value -gt 0 ]] || return 1
    /usr/bin/printf '%s\n' "$value"
}

verify_perf_events() {
    local file=$1 event
    local -a events=(task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults)
    for event in "${events[@]}"; do
        /usr/bin/awk -F '\t' -v e="$event" -v re="$PERF_VALUE_RE" '$3==e && $1 ~ re { found=1 } END { exit !found }' "$file" || return 1
    done
}

run_cell() {
    local corpus=$1 file=$2 preset=$3 archive_sha=$4 orig_sha=$5 orig_bytes=$6 enc_timeout=$7 dec_timeout=$8
    local cell_name=$file/$preset d=$PARTIAL/$file.$preset src archive1 archive2 sha1 sha2
    local plain_wall record_wall first_cycles second_cycles cycle_class cycle_ratio g3_class g3_ratio
    CELL_RESULT=FAIL
    CURRENT_CELL=$cell_name
    /usr/bin/mkdir -- "$d"
    src=$(verify_manifest_source "$corpus" "$file" "$orig_sha" "$orig_bytes")
    verify_journal_archive "$corpus" "$file" "$preset" "$archive_sha"
    archive1=$d/canonical-replay-1.cub
    archive2=$d/canonical-replay-2.cub

    quiet_wait || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"reason\":\"host_not_quiet_before_encode1\"}"; return 0; }
    run_bounded "$enc_timeout" "$d/encode1.out" "$d/encode1.err" /usr/bin/nice -n 10 "${PIN[@]}" "$CUBRIM" compress --preset "$preset" --quiet "$src" "$archive1" || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"reason\":\"encode1_rc_$LAST_RC\"}"; return 0;
    }
    quiet_wait || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"reason\":\"host_not_quiet_before_encode2\"}"; return 0; }
    run_bounded "$enc_timeout" "$d/encode2.out" "$d/encode2.err" /usr/bin/nice -n 10 "${PIN[@]}" "$CUBRIM" compress --preset "$preset" --quiet "$src" "$archive2" || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"void\",\"reason\":\"encode2_rc_$LAST_RC\"}"; return 0;
    }
    sha1=$(sha "$archive1"); sha2=$(sha "$archive2")
    [[ $sha1 == "$archive_sha" && $sha2 == "$archive_sha" ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-sha\",\"got1\":\"$sha1\",\"got2\":\"$sha2\"}"; return 0;
    }
    /usr/bin/cmp -- "$archive1" "$archive2" || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-cmp\"}"; return 0;
    }
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"G1_pass\",\"archive_sha256\":\"$sha1\"}"

    decode_checked "$cell_name" plain "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/time -v -o "$d/plain.time"
    [[ $DECODE_RESULT == PASS ]] || return 0
    plain_wall=$LAST_WALL
    decode_checked "$cell_name" pstat1 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf stat -d -x $'\t' -o "$d/pstat1.txt" -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,dTLB-load-misses,page-faults --
    [[ $DECODE_RESULT == PASS ]] || return 0
    decode_checked "$cell_name" pstat2 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf stat -d -x $'\t' -o "$d/pstat2.txt" -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,dTLB-load-misses,page-faults --
    [[ $DECODE_RESULT == PASS ]] || return 0
    if ! verify_perf_events "$d/pstat1.txt" || ! verify_perf_events "$d/pstat2.txt"; then
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"perf-events\"}"; return 0;
    fi
    first_cycles=$(parse_cycles "$d/pstat1.txt") || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"cycles-parse-1\"}"; return 0; }
    second_cycles=$(parse_cycles "$d/pstat2.txt") || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"cycles-parse-2\"}"; return 0; }
    IFS='|' read -r cycle_class cycle_ratio <<<"$(classify_cycle_agreement "$first_cycles" "$second_cycles")"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"$cycle_class\",\"cycles1\":$first_cycles,\"cycles2\":$second_cycles,\"relative_delta\":$cycle_ratio}"

    decode_checked "$cell_name" prec "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf record -q -F 997 -e cycles -o "$d/perf.data" --
    [[ $DECODE_RESULT == PASS ]] || return 0
    record_wall=$LAST_WALL
    IFS='|' read -r g3_class g3_ratio <<<"$(classify_instrument_overhead "$plain_wall" "$record_wall")"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"G3\",\"classification\":\"$g3_class\",\"plain_wall_s\":$plain_wall,\"record_wall_s\":$record_wall,\"ratio\":$g3_ratio}"
    run_bounded 300 "$d/perf-report.txt" "$d/perf-report.err" \
        /usr/bin/perf report -i "$d/perf.data" --stdio --percent-limit 0.3 || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"perf-report\",\"rc\":$LAST_RC}"
        return 0
    }
    [[ -s $d/perf-report.txt ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"perf-report-empty\"}"
        return 0
    }
    reject_orphan_processes
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"cell_done\",\"cycle_class\":\"$cycle_class\",\"instrument_class\":\"$g3_class\"}"
    CELL_RESULT=PASS
    CURRENT_CELL=
    return 0
}

write_manifests() {
    local tmp
    tmp=$(/usr/bin/mktemp /tmp/cubr-decode-attrib-SHA256SUMS.tmp.XXXXXX)
    if ! (
        cd "$PARTIAL"
        /usr/bin/find . -type f ! -name SHA256SUMS ! -name TIMING-DONE.STAMP -print0 |
            /usr/bin/sort -z |
            /usr/bin/xargs -0 /usr/bin/sha256sum
    ) >"$tmp"; then
        /usr/bin/rm -f -- "$tmp"
        die 'checksum manifest generation failed'
    fi
    /usr/bin/mv -- "$tmp" "$PARTIAL/SHA256SUMS"
}

write_completion_marker() {
    /usr/bin/printf 'runner_sha256=%s\nbinary_sha256=%s\ncode_commit=%s\npin=0-15\ncompleted_at=%s\n' \
        "$EXPECTED_RUNNER_SHA" "$CUBRIM_SHA_EXPECT" "$CODE_COMMIT" "$(now)" >"$PARTIAL/TIMING-DONE.STAMP"
}

on_exit() {
    local rc=$?
    if (( rc != 0 )) && [[ -d $PARTIAL && -n $JOURNAL ]]; then
        jlog "{\"t\":\"$(now)\",\"event\":\"run_failed\",\"rc\":$rc,\"cell\":\"$CURRENT_CELL\"}"
        /usr/bin/printf 'rc=%s\nfailed_at=%s\ncell=%s\n' "$rc" "$(now)" "$CURRENT_CELL" >"$PARTIAL/FAILED.STAMP"
    fi
}

cleanup_preflight() {
    local rc=${1:-0}
    if [[ -n $PREFLIGHT_DIR && -d $PREFLIGHT_DIR ]]; then
        /usr/bin/rm -rf -- "$PREFLIGHT_DIR" || true
    fi
    PREFLIGHT_DIR=
    JOURNAL=
    return "$rc"
}

self_test() {
    local d event
    local -a events=(task-clock cycles instructions branches branch-misses cache-references cache-misses dTLB-load-misses page-faults)
    [[ $(classify_cycle_agreement 100 109) == cycle-agreement\|* ]]
    [[ $(classify_cycle_agreement 100 112) == cycle-disagreement\|* ]]
    [[ $(classify_instrument_overhead 100 110) == instrument-clean\|* ]]
    [[ $(classify_instrument_overhead 100 111) == instrument-perturbed\|* ]]
    d=$(/usr/bin/mktemp -d /tmp/cubr-decode-attrib-g2-self-test.XXXXXX)
    for event in "${events[@]}"; do
        /usr/bin/printf '1\t\t%s\n' "$event" >>"$d/perf-good.txt"
    done
    verify_perf_events "$d/perf-good.txt" || {
        /usr/bin/printf 'decode_attrib_self_test=FAIL reason=perf_events_numeric_rejected\n' >&2
        /usr/bin/rm -rf -- "$d"
        return 1
    }
    /usr/bin/awk -F '\t' 'BEGIN { OFS=FS } $3=="cache-misses" { $1="<not supported>" } { print }' \
        "$d/perf-good.txt" >"$d/perf-bad.txt"
    if verify_perf_events "$d/perf-bad.txt"; then
        /usr/bin/printf 'decode_attrib_self_test=FAIL reason=perf_events_non_numeric_accepted\n' >&2
        /usr/bin/rm -rf -- "$d"
        return 1
    fi
    /usr/bin/rm -rf -- "$d"
    /usr/bin/printf 'decode_attrib_self_test=PASS\n'
}

preflight() {
    refuse_existing_output || exit 1
    PREFLIGHT_DIR=$(/usr/bin/mktemp -d /tmp/cubr-decode-attrib-g2-preflight.XXXXXX)
    trap 'cleanup_preflight "$?"' EXIT
    JOURNAL=$PREFLIGHT_DIR/journal.jsonl
    DEADLINE_MONOTONIC=$(( $(monotonic_seconds) + 300 ))
    admission "$PREFLIGHT_DIR"
    /usr/bin/printf 'decode_attrib_preflight=PASS\n'
    cleanup_preflight 0
    trap - EXIT
}

main_run() {
    local cell corpus file preset archive_sha orig_sha orig_bytes enc_timeout dec_timeout run_start_record
    refuse_existing_output || exit 1
    /usr/bin/mkdir -- "$PARTIAL"
    JOURNAL=$PARTIAL/journal.jsonl
    DEADLINE_MONOTONIC=$(( $(monotonic_seconds) + CAMPAIGN_BUDGET_SECONDS ))
    trap on_exit EXIT
    /usr/bin/cp -- "${BASH_SOURCE[0]}" "$PARTIAL/decode-attrib-run.sh"
    /usr/bin/cp -- "$TEST_OVERLAY" "$PARTIAL/decode-attrib-g2-test-overlay.patch"
    printf -v run_start_record '{"t":"%s","event":"run_start","pin":"0-15","threads":4,"budget_s":%s,"deadline_monotonic_s":%s}' \
        "$(now)" "$CAMPAIGN_BUDGET_SECONDS" "$DEADLINE_MONOTONIC"
    jlog "$run_start_record"
    admission "$PARTIAL"
    run_suites
    for cell in "${CELLS[@]}"; do
        IFS='|' read -r corpus file preset archive_sha orig_sha orig_bytes enc_timeout dec_timeout <<<"$cell"
        if (( $(remaining_budget_seconds) == 0 )); then
            jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"void\",\"reason\":\"campaign_budget_expired\"}"
            continue
        fi
        run_cell "$corpus" "$file" "$preset" "$archive_sha" "$orig_sha" "$orig_bytes" "$enc_timeout" "$dec_timeout"
        reject_orphan_processes
        if [[ $CELL_RESULT != PASS ]]; then
            jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"cell_failed_or_void\"}"
            CURRENT_CELL=
        fi
    done
    reject_orphan_processes
    jlog "{\"t\":\"$(now)\",\"event\":\"run_end\"}"
    [[ ! -e $OUT && ! -L $OUT ]] || die 'final output collision before rename'
write_manifests
write_completion_marker
/usr/bin/mv -T -n -- "$PARTIAL" "$OUT"
    [[ ! -e $PARTIAL && -d $OUT && ! -L $OUT ]] || die 'final output collision during rename'
/usr/bin/chmod -R a-w -- "$OUT"
    trap - EXIT
}

case ${1:-} in
    --self-test) self_test ;;
    --preflight) preflight ;;
    --run) main_run ;;
    *) /usr/bin/printf 'usage: %s --self-test|--preflight|--run\n' "$0" >&2; exit 2 ;;
esac
