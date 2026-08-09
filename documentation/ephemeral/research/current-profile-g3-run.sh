#!/usr/bin/env bash
# Fail-closed current-main G3 CM2 attribution runner for NEW-24.
# Protocol: CUBR-NEW24-CURRENT-PROFILE-G3-20260809.md.
set -euo pipefail
IFS=$'\n\t'
export LC_ALL=C

readonly ROOT=/root/phaseC
readonly CODE_DIR=/root/cubr-new24-current-profile-g3-src
readonly PROFILE_TARGET=/root/cubr-new24-current-profile-g3-target
readonly CUBRIM=$PROFILE_TARGET/release/cubrim
readonly CODE_COMMIT=e0e8bdb2c2df924877d9dcf8a1897810683a147a
readonly MAPPER_SOURCE=/root/cubr-new24-current-profile-g3-map.py
readonly GENERATED_CARGO_LOCK=code/cubrim-rs/Cargo.lock
readonly CORPUS_ROOT=/root/corpus-full/silesia
readonly CORPUS_MANIFEST=/root/phaseC/corpus_manifest.tsv
readonly OUT=/root/cubr-new24-current-profile-g3-20260809
readonly PARTIAL=$OUT.partial
readonly CARGO=/root/.cargo/bin/cargo
readonly RUSTC=/root/.cargo/bin/rustc
readonly G3_RATIO_MAX=1.10
readonly CYCLE_DISAGREEMENT_MAX=0.10
readonly SHARE_DELTA_MAX=1.00
readonly PERF_VALUE_RE='^[0-9]+([.][0-9]+)?$'
readonly CAMPAIGN_BUDGET_SECONDS=14400
readonly LOAD_MAX=8.0
readonly SYSTEMD_CONTRACT='Type=exec Restart=no RuntimeMaxSec=4h5m'
readonly -a PIN=(/usr/bin/taskset -c 0-15)
readonly FEASIBILITY_FIXTURE_BYTES=65536
readonly FEASIBILITY_FIXTURE_SHA=de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31
readonly FEASIBILITY_FIXTURE_PRESET=max
readonly FEASIBILITY_ARCHIVE_SHA=352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3
readonly EXPECTED_RUNNER_SHA=${CUBR_EXPECTED_RUNNER_SHA256:-}
readonly CUBRIM_SHA_EXPECT=${CUBR_EXPECTED_BINARY_SHA256:-}
readonly MAPPER_SHA_EXPECT=${CUBR_EXPECTED_MAPPER_SHA256:-}
readonly CARGO_LOCK_SHA_EXPECT=${CUBR_EXPECTED_CARGO_LOCK_SHA256:-}
readonly SYSTEMD_UNIT=${CUBR_SYSTEMD_UNIT:-}
readonly SIDE_EFFECT_28=documentation/ephemeral/research/CUBR-0028-bench.json
readonly SIDE_EFFECT_31=documentation/ephemeral/research/CUBR-0031-bench.json
readonly -a PERF_REQUESTED_EVENTS=(
    task-clock cycles instructions branches branch-misses cache-references cache-misses
    dTLB-load-misses page-faults L1-dcache-loads L1-dcache-load-misses
)

# corpus|file|preset|orig_bytes|encode_timeout_s|decode_timeout_s|archive_sha|orig_sha
readonly -a CELLS=(
    'silesia|dickens|max|10192446|1340|435|b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
    'silesia|xml|max|5345280|520|175|d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37|0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c'
    'silesia|dickens|web|10192446|380|320|a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341|b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a'
)

export CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4

JOURNAL=
DEADLINE_MONOTONIC=0
LAST_WALL=
LAST_RC=0
CURRENT_CELL=
PREFLIGHT_DIR=
CELL_RESULT=
CELL_SELECTION=
DECODE_RESULT=
MAPPER=$MAPPER_SOURCE
INSTRUCTION_MAP_SHA=
PERF_SUPPORTED_CSV=
DISASSEMBLY_TMP=
CAMPAIGN_SELECTION=ELIGIBLE
FINAL_PROFILE_STATUS=VALID-CURRENT-PROFILE
BINARY_BUILD_ID=
declare -a PERF_SUPPORTED_EVENTS=()

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
    /usr/bin/printf 'current-profile G3: %s\n' "$1" >&2
    exit 1
}

refuse_existing_output() {
    [[ ! -e $OUT && ! -L $OUT ]] || {
        /usr/bin/printf 'current-profile G3: output exists: %s\n' "$OUT" >&2
        return 1
    }
    [[ ! -e $PARTIAL && ! -L $PARTIAL ]] || {
        /usr/bin/printf 'current-profile G3: partial output exists: %s\n' "$PARTIAL" >&2
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

run_bounded_input() {
    local requested=$1 stdin=$2 stdout=$3 stderr=$4
    shift 4
    local remaining limit start_monotonic end_monotonic rc
    [[ -f $stdin && ! -L $stdin ]] || return 126
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
    /usr/bin/timeout --signal=TERM --kill-after=10s "${limit}s" "$@" \
        <"$stdin" >"$stdout" 2>"$stderr"
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

classify_share_stability() {
    local first_period=$1 first_total=$2 second_period=$3 second_total=$4
    /usr/bin/awk -v a="$first_period" -v at="$first_total" -v b="$second_period" -v bt="$second_total" -v m="$SHARE_DELTA_MAX" 'BEGIN {
        if (at<=0 || bt<=0) exit 2;
        d=(a/at-b/bt)*100; if (d<0) d=-d;
        if (d<=m) print "share-stable|" d; else print "share-unstable|" d;
    }'
}

classify_record_pair() {
    local first=$1 second=$2
    if [[ $first == instrument-clean && $second == instrument-clean ]]; then
        /usr/bin/printf 'records-clean\n'
    else
        /usr/bin/printf 'records-perturbed\n'
    fi
}

mark_no_select() {
    local reason=$1
    CELL_SELECTION=NO-SELECT
    CAMPAIGN_SELECTION=NO-SELECT
    jlog "{\"t\":\"$(now)\",\"cell\":\"$CURRENT_CELL\",\"event\":\"valid_descriptive\",\"selection\":\"NO-SELECT\",\"reason\":\"$reason\"}"
}

void_cell() {
    local reason=$1
    jlog "{\"t\":\"$(now)\",\"cell\":\"$CURRENT_CELL\",\"event\":\"void\",\"reason\":\"$reason\"}"
}

verify_runner_provenance() {
    local actual
    [[ $EXPECTED_RUNNER_SHA =~ ^[0-9a-f]{64}$ ]] || die 'reviewed runner SHA is missing or malformed'
    actual=$(sha "${BASH_SOURCE[0]}")
    [[ $actual == "$EXPECTED_RUNNER_SHA" ]] || die "runner SHA mismatch: expected $EXPECTED_RUNNER_SHA got $actual"
    /usr/bin/printf '%s\n' "$actual"
}

verify_mapper_provenance() {
    [[ $MAPPER_SHA_EXPECT =~ ^[0-9a-f]{64}$ ]] || die 'reviewed mapper SHA is missing or malformed'
    [[ -f $MAPPER_SOURCE && ! -L $MAPPER_SOURCE ]] || die 'mapper is missing or unsafe'
    [[ $(sha "$MAPPER_SOURCE") == "$MAPPER_SHA_EXPECT" ]] || die 'mapper SHA mismatch'
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
    local found snapshot matches
    snapshot=$(/usr/bin/mktemp /tmp/cubr-current-profile-g3-processes.XXXXXX) ||
        die 'process snapshot allocation failed'
    matches=$(/usr/bin/mktemp /tmp/cubr-current-profile-g3-process-matches.XXXXXX) || {
        /usr/bin/rm -f -- "$snapshot"
        die 'process match allocation failed'
    }
    if ! /usr/bin/ps -eo pid=,ppid=,comm=,args= >"$snapshot"; then
        /usr/bin/rm -f -- "$snapshot" "$matches"
        die 'process snapshot failed'
    fi
    if ! /usr/bin/awk -v runner="$$" -v parent="$PPID" '
        $1 != runner && $1 != parent &&
        ($3 ~ /^(cubrim|perf|cargo|rust|rustc)$/ ||
         ($3 == "bash" && $0 ~ /current-profile-g3-run[.]sh/)) { print }
    ' "$snapshot" >"$matches"; then
        /usr/bin/rm -f -- "$snapshot" "$matches"
        die 'process classification failed'
    fi
    found=$(<"$matches")
    /usr/bin/rm -f -- "$snapshot" "$matches"
    [[ -z $found ]] || {
        /usr/bin/printf '%s\n' "$found" >&2
        die 'orphan candidate/perf process or competing Cubrim/Cargo/Rust/current-profile runner'
    }
}

quiet_wait() {
    local load remaining
    while :; do
        reject_orphan_processes
        load=$(/usr/bin/awk '{print $1}' /proc/loadavg) || die 'load average read failed'
        [[ $load =~ ^[0-9]+([.][0-9]+)?$ ]] || die 'load average read failed'
        if /usr/bin/awk -v l="$load" -v m="$LOAD_MAX" 'BEGIN { exit !(l<m) }'; then
            return 0
        fi
        remaining=$(remaining_budget_seconds) || die 'monotonic budget read failed'
        (( remaining > 60 )) || return 1
        /usr/bin/sleep 60
    done
}

verify_systemd_contract() {
    local unit_type restart runtime restarts invocation unit_invocation main_pid
    [[ -n $SYSTEMD_UNIT ]] || die 'systemd unit is missing'
    invocation=${INVOCATION_ID:-}
    [[ $invocation =~ ^[0-9a-f]{32}$ ]] || die 'systemd invocation ID is missing or malformed'
    unit_type=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p Type --value) || die 'systemd Type read failed'
    restart=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p Restart --value) || die 'systemd Restart read failed'
    runtime=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p RuntimeMaxUSec --value) || die 'systemd RuntimeMaxSec read failed'
    restarts=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p NRestarts --value) || die 'systemd NRestarts read failed'
    unit_invocation=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p InvocationID --value) || die 'systemd InvocationID read failed'
    main_pid=$(/usr/bin/systemctl show "$SYSTEMD_UNIT" -p MainPID --value) || die 'systemd MainPID read failed'
    [[ $unit_type == exec ]] || die 'systemd Type is not exec'
    [[ $restart == no ]] || die 'systemd Restart is not no'
    [[ $runtime == '4h 5min' || $runtime == '4h 5min 0us' ]] || die 'systemd RuntimeMaxSec is not 4h5m'
    [[ $restarts == 0 ]] || die 'systemd NRestarts is not 0'
    [[ $unit_invocation == "$invocation" ]] || die 'unit InvocationID does not match current process'
    [[ $main_pid == "$$" ]] || die 'systemd MainPID does not match current process'
    jlog "{\"t\":\"$(now)\",\"event\":\"systemd_contract\",\"contract\":\"Type=exec Restart=no RuntimeMaxSec=4h5m\",\"unit\":\"$SYSTEMD_UNIT\",\"invocation_id\":\"$invocation\",\"main_pid\":$main_pid,\"NRestarts\":0}"
}

verify_binary_and_code() {
    local ignored
    [[ $CUBRIM_SHA_EXPECT =~ ^[0-9a-f]{64}$ ]] || die 'reviewed binary SHA is missing or malformed'
    [[ $CARGO_LOCK_SHA_EXPECT =~ ^[0-9a-f]{64}$ ]] || die 'generated Cargo lock SHA is missing or malformed'
    [[ -x $CUBRIM ]] || die 'campaign binary is not executable'
    [[ $(sha "$CUBRIM") == "$CUBRIM_SHA_EXPECT" ]] || die 'binary SHA mismatch'
    [[ -x $CARGO && -x $RUSTC ]] || die 'Cargo or rustc is not executable'
    [[ $(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD) == "$CODE_COMMIT" ]] || die 'code checkout commit mismatch'
    if /usr/bin/git -C "$CODE_DIR" symbolic-ref -q HEAD >/dev/null 2>&1; then
        die 'code checkout is not detached'
    fi
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain --untracked-files=all) ]] ||
        die 'code checkout tracked or untracked state is dirty'
    ignored=$(/usr/bin/git -C "$CODE_DIR" status --porcelain --ignored --untracked-files=all)
    [[ $ignored == "!! $GENERATED_CARGO_LOCK" ]] || die 'unexpected ignored build side effect before suites'
    [[ -f $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] ||
        die 'generated Cargo lock is missing or unsafe'
    [[ $(sha "$CODE_DIR/$GENERATED_CARGO_LOCK") == "$CARGO_LOCK_SHA_EXPECT" ]] ||
        die 'generated Cargo lock SHA mismatch'
}

verify_manifest_source() {
    local corpus=$1 file=$2 want_sha=$3 want_bytes=$4
    local -a rows
    local row_corpus row_file row_type row_bytes row_sha src
    mapfile -t rows < <(/usr/bin/awk -F '\t' -v c="$corpus" -v f="$file" 'NR>1 && $1==c && $2==f { print }' "$CORPUS_MANIFEST")
    [[ ${#rows[@]} == 1 ]] || die "manifest cardinality mismatch: $corpus/$file"
    IFS=$'\t' read -r row_corpus row_file row_type row_bytes row_sha <<<"${rows[0]}"
    [[ $row_type == text ]] || die "manifest row type mismatch: $corpus/$file"
    [[ $row_corpus == "$corpus" && $row_file == "$file" && $row_bytes == "$want_bytes" && $row_sha == "$want_sha" ]] ||
        die "manifest row mismatch: $corpus/$file"
    src=$CORPUS_ROOT/$file
    [[ -f $src && ! -L $src ]] || die "source missing or unsafe: $src"
    [[ $(/usr/bin/stat -c %s "$src") == "$want_bytes" ]] || die "source size mismatch: $src"
    [[ $(sha "$src") == "$want_sha" ]] || die "source SHA mismatch: $src"
    /usr/bin/printf '%s\n' "$src"
}

verify_feasibility_fixture() {
    local evidence=$1
    local src=$evidence/feasibility-zero-65536.bin
    local archive1=$evidence/feasibility-1.cub archive2=$evidence/feasibility-2.cub
    local restored=$evidence/feasibility-restored.bin sha1 sha2
    /usr/bin/dd if=/dev/zero of="$src" bs="$FEASIBILITY_FIXTURE_BYTES" count=1 status=none ||
        die 'feasibility fixture creation failed'
    [[ $(/usr/bin/stat -c %s "$src") == "$FEASIBILITY_FIXTURE_BYTES" ]] ||
        die 'feasibility fixture size mismatch'
    [[ $(sha "$src") == "$FEASIBILITY_FIXTURE_SHA" ]] ||
        die 'feasibility fixture SHA mismatch'
    run_bounded 60 "$evidence/feasibility-encode1.out" "$evidence/feasibility-encode1.err" \
        /usr/bin/nice -n 10 "${PIN[@]}" "$CUBRIM" compress --preset "$FEASIBILITY_FIXTURE_PRESET" \
        --quiet "$src" "$archive1" || die "feasibility encode1 failed: rc=$LAST_RC"
    run_bounded 60 "$evidence/feasibility-encode2.out" "$evidence/feasibility-encode2.err" \
        /usr/bin/nice -n 10 "${PIN[@]}" "$CUBRIM" compress --preset "$FEASIBILITY_FIXTURE_PRESET" \
        --quiet "$src" "$archive2" || die "feasibility encode2 failed: rc=$LAST_RC"
    sha1=$(sha "$archive1")
    sha2=$(sha "$archive2")
    [[ $sha1 == "$FEASIBILITY_ARCHIVE_SHA" && $sha2 == "$FEASIBILITY_ARCHIVE_SHA" ]] ||
        die "feasibility archive SHA mismatch: got1=$sha1 got2=$sha2"
    /usr/bin/cmp -- "$archive1" "$archive2" || die 'feasibility archives differ'
    run_bounded 60 "$evidence/feasibility-decode.out" "$evidence/feasibility-decode.err" \
        /usr/bin/nice -n 10 "${PIN[@]}" "$CUBRIM" decompress --quiet "$archive1" "$restored" ||
        die "feasibility decode failed: rc=$LAST_RC"
    /usr/bin/cmp -- "$src" "$restored" || die 'feasibility round-trip mismatch'
    /usr/bin/printf 'fixture_bytes=%s\nfixture_sha256=%s\npreset=%s\narchive_sha256=%s\narchive_bytes=%s\nencode_replays=2\nroundtrip=PASS\n' \
        "$FEASIBILITY_FIXTURE_BYTES" "$FEASIBILITY_FIXTURE_SHA" "$FEASIBILITY_FIXTURE_PRESET" \
        "$FEASIBILITY_ARCHIVE_SHA" "$(/usr/bin/stat -c %s "$archive1")" \
        >"$evidence/feasibility-fixture.txt"
    jlog "{\"t\":\"$(now)\",\"event\":\"feasibility_fixture_pass\",\"fixture_bytes\":$FEASIBILITY_FIXTURE_BYTES,\"fixture_sha256\":\"$FEASIBILITY_FIXTURE_SHA\",\"preset\":\"$FEASIBILITY_FIXTURE_PRESET\",\"archive_sha256\":\"$FEASIBILITY_ARCHIVE_SHA\",\"archive_bytes\":50,\"encode_replays\":2,\"roundtrip\":\"PASS\"}"
}

verify_journal_archive() {
    local corpus=$1 file=$2 preset=$3 want_sha=$4
    local journal=$ROOT/journal.$preset.jsonl match_count
    [[ -f $journal && ! -L $journal ]] || die "journal missing or unsafe: $journal"
    match_count=$(/usr/bin/awk \
        -v c="\"corpus\":\"$corpus\"" \
        -v f="\"file\":\"$file\"" \
        -v p="\"preset\":\"$preset\"" \
        -v h="\"archive_sha256\":\"$want_sha\"" \
        'index($0,c) && index($0,f) && index($0,p) && index($0,h) { count++ } END { print count+0 }' \
        "$journal") || die "journal archive identity read failed: $file/$preset"
    [[ $match_count == 1 ]] ||
        die "journal archive identity mismatch: $file/$preset"
}

parse_perf_event_probe() {
    local file=$1 event=$2 value
    value=$(/usr/bin/awk -F '\t' -v e="$event" '$3==e { print $1; exit }' "$file")
    if [[ $value =~ $PERF_VALUE_RE ]]; then
        /usr/bin/printf 'supported|%s\n' "$value"
    elif [[ $value == '<not supported>' ]]; then
        /usr/bin/printf 'unsupported|%s\n' "$value"
    else
        return 1
    fi
}

discover_perf_events() {
    local d=$1 event safe status value rc
    local -a supported=()
    : >"$d/perf-events.tsv"
    /usr/bin/printf 'event\tstatus\n' >"$d/perf-events.tsv"
    for event in "${PERF_REQUESTED_EVENTS[@]}"; do
        safe=${event//[^A-Za-z0-9]/_}
        rc=0
        run_bounded 10 "$d/perf-stat-$safe.out" "$d/perf-stat-$safe.err" \
            /usr/bin/perf stat -x $'\t' -e "$event" -o "$d/perf-stat-$safe.txt" -- \
            /usr/bin/taskset -c 0 /usr/bin/true || rc=$LAST_RC
        if IFS='|' read -r status value <<<"$(parse_perf_event_probe "$d/perf-stat-$safe.txt" "$event")"; then
            : "$value"
        else
            die "perf event discovery failed: $event rc=$rc"
        fi
        /usr/bin/printf '%s\t%s\n' "$event" "$status" >>"$d/perf-events.tsv"
        if [[ $status == supported ]]; then
            (( rc == 0 )) || die "supported perf event probe failed: $event rc=$rc"
            supported+=("$event")
        else
            jlog "{\"t\":\"$(now)\",\"event\":\"perf_event\",\"name\":\"$event\",\"status\":\"unsupported\"}"
        fi
    done
    (( ${#supported[@]} > 0 )) || die 'no supported perf stat events'
    /usr/bin/printf '%s\n' "${supported[@]}" | /usr/bin/grep -qx cycles || die 'cycles event is unsupported'
    PERF_SUPPORTED_EVENTS=("${supported[@]}")
    PERF_SUPPORTED_CSV=$(IFS=,; /usr/bin/printf '%s' "${supported[*]}")
}

perf_smoke() {
    local d=$1
    discover_perf_events "$d"
    run_bounded 10 "$d/perf-record-smoke.out" "$d/perf-record-smoke.err" \
        /usr/bin/perf record -q -F 99 -e cycles -o "$d/perf-record-smoke.data" -- \
        /usr/bin/taskset -c 0 /usr/bin/sleep 0.05 || die 'perf record smoke failed'
    [[ -s $d/perf-record-smoke.data ]] || die 'perf record smoke produced no data'
}

parse_build_id() {
    local file=$1
    local -a ids
    mapfile -t ids < <(/usr/bin/awk '/Build ID:/ { print $3 }' "$file")
    [[ ${#ids[@]} == 1 && ${ids[0]} =~ ^[0-9A-Fa-f]{32,128}$ ]] || return 1
    /usr/bin/printf '%s\n' "${ids[0],,}"
}

admission() {
    local evidence=$1 require_systemd=$2 runner_sha mapper_sha binary_sha lock_sha host load
    local cell corpus file preset orig_bytes enc_timeout dec_timeout archive_sha orig_sha
    local cargo_version rustc_version objdump_version addr2line_version perf_version readelf_version
    local admission_record
    host=$(/usr/bin/hostname -s)
    [[ $host == dev-ai ]] || die 'hostname admission failed'
    verify_topology || die 'CPU topology admission failed'
    runner_sha=$(verify_runner_provenance)
    verify_mapper_provenance
    verify_binary_and_code
    mapper_sha=$(sha "$MAPPER_SOURCE")
    binary_sha=$(sha "$CUBRIM")
    lock_sha=$(sha "$CODE_DIR/$GENERATED_CARGO_LOCK")
    cargo_version=$("$CARGO" --version)
    rustc_version=$("$RUSTC" --version)
    objdump_version=$(/usr/bin/objdump --version | /usr/bin/awk 'NR==1 { print }')
    addr2line_version=$(/usr/bin/addr2line --version | /usr/bin/awk 'NR==1 { print }')
    perf_version=$(/usr/bin/perf --version | /usr/bin/awk 'NR==1 { print }')
    readelf_version=$(/usr/bin/readelf --version | /usr/bin/awk 'NR==1 { print }')
    [[ -n $objdump_version && -n $addr2line_version && -n $perf_version && -n $readelf_version ]] ||
        die 'resolver/perf tool version capture failed'
    run_bounded 30 "$evidence/binary.readelf-notes.txt" "$evidence/binary.readelf-notes.err" \
        /usr/bin/readelf -n "$CUBRIM" || die 'binary build-ID note capture failed'
    BINARY_BUILD_ID=$(parse_build_id "$evidence/binary.readelf-notes.txt") ||
        die 'binary build ID is missing, duplicated, or malformed'
    /usr/bin/printf 'objdump_version=%s\naddr2line_version=%s\nperf_version=%s\nreadelf_version=%s\nobjdump_raw_command=/usr/bin/objdump --disassemble --line-numbers BINARY\nobjdump_demangled_command=/usr/bin/objdump --disassemble --line-numbers --demangle BINARY\naddr2line_command=/usr/bin/addr2line -a -f -C -i -e BINARY\nperf_script_command=/usr/bin/perf script --show-lost-events -F period,ip,sym,symoff,dso\n' \
        "$objdump_version" "$addr2line_version" "$perf_version" "$readelf_version" \
        >"$evidence/tool-versions.txt"
    reject_orphan_processes
    quiet_wait || die 'host did not become quiet before admission deadline'
    load=$(/usr/bin/awk '{print $1}' /proc/loadavg)
    (( require_systemd == 0 )) || verify_systemd_contract
    perf_smoke "$evidence"
    for cell in "${CELLS[@]}"; do
        IFS='|' read -r corpus file preset orig_bytes enc_timeout dec_timeout archive_sha orig_sha <<<"$cell"
        : "$enc_timeout" "$dec_timeout"
        verify_manifest_source "$corpus" "$file" "$orig_sha" "$orig_bytes" >/dev/null
        verify_journal_archive "$corpus" "$file" "$preset" "$archive_sha"
    done
    /usr/bin/printf 'host=%s\ntopology=%s\nload1=%s\npin=0-15\nthreads=4\nrunner_sha256=%s\nmapper_sha256=%s\nbinary_sha256=%s\nbinary_build_id=%s\ngenerated_lock_sha256=%s\ncode_commit=%s\ncode_detached=true\ncode_clean_except_generated_lock=true\nrelease_flags=CARGO_PROFILE_RELEASE_DEBUG=1\ncargo_version=%s\nrustc_version=%s\nobjdump_version=%s\naddr2line_version=%s\nperf_version=%s\nreadelf_version=%s\nsystemd_contract=%s\nperf_stat_smoke=PASS\nperf_record_smoke=PASS\ncorpus_manifest_cells=3/3\njournal_archive_cells=3/3\n' \
        "$host" 'cpu0-31=core0-31;cpu32-63=smt0-31' "$load" "$runner_sha" "$mapper_sha" "$binary_sha" \
        "$BINARY_BUILD_ID" "$lock_sha" "$CODE_COMMIT" "$cargo_version" "$rustc_version" "$objdump_version" \
        "$addr2line_version" "$perf_version" "$readelf_version" "$SYSTEMD_CONTRACT" >"$evidence/PROVENANCE.txt"
    printf -v admission_record '{"t":"%s","event":"admission_pass","host":"%s","topology":"cpu0-31=core0-31;cpu32-63=smt0-31","load1":%s,"pin":"0-15","threads":4,"runner_sha256":"%s","mapper_sha256":"%s","binary_sha256":"%s","binary_build_id":"%s","generated_lock_sha256":"%s","code_commit":"%s","release_flags":"CARGO_PROFILE_RELEASE_DEBUG=1","cargo_version":"%s","rustc_version":"%s","objdump_version":"%s","addr2line_version":"%s","perf_version":"%s","readelf_version":"%s","corpus_manifest_cells":"3/3","journal_archive_cells":"3/3"}' \
        "$(now)" "$host" "$load" "$runner_sha" "$mapper_sha" "$binary_sha" "$BINARY_BUILD_ID" \
        "$lock_sha" "$CODE_COMMIT" "$cargo_version" "$rustc_version" "$objdump_version" \
        "$addr2line_version" "$perf_version" "$readelf_version"
    jlog "$admission_record"
}

restore_suite_side_effects() {
    local status line path tmp
    status=$(/usr/bin/git -C "$CODE_DIR" status --porcelain --untracked-files=all)
    [[ -n $status ]] || return 0
    while IFS= read -r line; do
        case $line in
            " M $SIDE_EFFECT_28") path=$SIDE_EFFECT_28 ;;
            " M $SIDE_EFFECT_31") path=$SIDE_EFFECT_31 ;;
            *) die "unexpected suite side effect: $line" ;;
        esac
        [[ -f $CODE_DIR/$path && ! -L $CODE_DIR/$path ]] || die "unsafe suite side-effect path: $path"
        tmp=$CODE_DIR/$path.g3restore-tmp
        [[ ! -e $tmp && ! -L $tmp ]] || die "restore temp collision: $tmp"
        /usr/bin/git -C "$CODE_DIR" show "HEAD:$path" >"$tmp"
        /usr/bin/chmod --reference="$CODE_DIR/$path" "$tmp"
        /usr/bin/mv -- "$tmp" "$CODE_DIR/$path"
    done <<<"$status"
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain --untracked-files=all) ]] ||
        die 'code checkout dirty after suite restore'
    /usr/bin/printf '%s\n' "$status" >>"$PARTIAL/suite-side-effects-restored.txt"
}

cleanup_suite_outputs() {
    if [[ -e $PARTIAL/cargo-test-target || -L $PARTIAL/cargo-test-target ]]; then
        [[ -d $PARTIAL/cargo-test-target && ! -L $PARTIAL/cargo-test-target ]] || die 'Cargo test target is unsafe'
        /usr/bin/find "$PARTIAL/cargo-test-target" -depth -delete
    fi
    /usr/bin/git -C "$CODE_DIR" clean -fX -- "$GENERATED_CARGO_LOCK" >/dev/null
    [[ ! -e $CODE_DIR/$GENERATED_CARGO_LOCK && ! -L $CODE_DIR/$GENERATED_CARGO_LOCK ]] ||
        die 'generated Cargo lock cleanup failed'
    [[ ! -e $PARTIAL/cargo-test-target && ! -L $PARTIAL/cargo-test-target ]] || die 'Cargo test target cleanup failed'
    [[ -z $(/usr/bin/git -C "$CODE_DIR" status --porcelain --ignored --untracked-files=all) ]] ||
        die 'code checkout dirty after generated output cleanup'
    jlog "{\"t\":\"$(now)\",\"event\":\"suite_outputs_removed\",\"code_clean\":true}"
}

run_suites() {
    local remaining suite_rc
    [[ ! -e $PARTIAL/cargo-test-target && ! -L $PARTIAL/cargo-test-target ]] || die 'Cargo test target collision'
    /usr/bin/cp -- "$CODE_DIR/$GENERATED_CARGO_LOCK" "$PARTIAL/cargo-generated.lock"
    [[ $(sha "$PARTIAL/cargo-generated.lock") == "$CARGO_LOCK_SHA_EXPECT" ]] || die 'captured Cargo lock SHA mismatch'
    remaining=$(remaining_budget_seconds)
    (( remaining > 0 )) || die 'campaign budget expired before suites'
    # Required exact command: cargo test --release
    set +e
    (cd "$CODE_DIR/code/cubrim-rs" &&
        /usr/bin/timeout --signal=TERM --kill-after=10s "${remaining}s" \
        /usr/bin/env CARGO_TARGET_DIR="$PARTIAL/cargo-test-target" "$CARGO" test --release) \
        >"$PARTIAL/cargo-test-release.log" 2>&1
    suite_rc=$?
    set -e
    restore_suite_side_effects
    if (( suite_rc != 0 )); then
        cleanup_suite_outputs
        die 'cargo test --release failed'
    fi
    remaining=$(remaining_budget_seconds)
    if (( remaining == 0 )); then
        cleanup_suite_outputs
        die 'campaign budget expired before scheme-roundtrip suite'
    fi
    # Required exact command: cargo test --release --test scheme_roundtrip -- --nocapture
    set +e
    (cd "$CODE_DIR/code/cubrim-rs" &&
        /usr/bin/timeout --signal=TERM --kill-after=10s "${remaining}s" \
        /usr/bin/env CARGO_TARGET_DIR="$PARTIAL/cargo-test-target" "$CARGO" test --release --test scheme_roundtrip -- --nocapture) \
        >"$PARTIAL/cargo-test-scheme-roundtrip.log" 2>&1
    suite_rc=$?
    set -e
    restore_suite_side_effects
    cleanup_suite_outputs
    (( suite_rc == 0 )) || die 'scheme_roundtrip integration test failed'
    jlog "{\"t\":\"$(now)\",\"event\":\"suites_pass\"}"
}

cleanup_disassembly_tmp() {
    [[ -n $DISASSEMBLY_TMP ]] || return 0
    case $DISASSEMBLY_TMP in
        /tmp/cubr-current-profile-g3-disassembly.*)
            if [[ -d $DISASSEMBLY_TMP && ! -L $DISASSEMBLY_TMP ]]; then
                /usr/bin/find "$DISASSEMBLY_TMP" -depth -delete
            fi
            ;;
        *) die "unsafe disassembly temp path: $DISASSEMBLY_TMP" ;;
    esac
    DISASSEMBLY_TMP=
}

build_instruction_map() {
    local artifact_dir=${1:-$PARTIAL}
    local raw=$artifact_dir/binary.objdump.raw.txt human=$artifact_dir/binary.objdump.demangled.txt
    local addresses=$artifact_dir/binary.object-addresses.txt decoded=$artifact_dir/binary.addr2line.txt
    local summary=$artifact_dir/objdump-filter-summary.tsv provenance=$artifact_dir/full-disassembly-provenance.txt
    local coverage=$artifact_dir/instruction-map-coverage.tsv
    local full_raw full_human full_raw_sha full_human_sha full_raw_bytes full_human_bytes
    local full_raw_lines full_human_lines bucket path
    for path in "$raw" "$human" "$addresses" "$decoded" "$summary" "$provenance" "$coverage" \
        "$artifact_dir/instruction-map.tsv"; do
        [[ ! -e $path && ! -L $path ]] || die "instruction artifact collision: $path"
    done
    DISASSEMBLY_TMP=$(/usr/bin/mktemp -d /tmp/cubr-current-profile-g3-disassembly.XXXXXX)
    full_raw=$DISASSEMBLY_TMP/binary.objdump.raw.full.txt
    full_human=$DISASSEMBLY_TMP/binary.objdump.demangled.full.txt
    run_bounded 600 "$full_raw" "$artifact_dir/binary.objdump.raw.err" \
        /usr/bin/objdump --disassemble --line-numbers "$CUBRIM" || die 'raw objdump failed'
    run_bounded 600 "$full_human" "$artifact_dir/binary.objdump.demangled.err" \
        /usr/bin/objdump --disassemble --line-numbers --demangle "$CUBRIM" || die 'demangled objdump failed'
    [[ -s $full_raw && -s $full_human ]] || die 'full objdump produced no output'
    full_raw_sha=$(sha "$full_raw")
    full_human_sha=$(sha "$full_human")
    full_raw_bytes=$(/usr/bin/stat -c %s "$full_raw")
    full_human_bytes=$(/usr/bin/stat -c %s "$full_human")
    full_raw_lines=$(/usr/bin/wc -l <"$full_raw")
    full_human_lines=$(/usr/bin/wc -l <"$full_human")
    run_bounded 600 "$artifact_dir/objdump-filter.out" "$artifact_dir/objdump-filter.err" \
        /usr/bin/python3 "$MAPPER" filter --raw-full "$full_raw" \
        --demangled-full "$full_human" --raw-output "$raw" \
        --demangled-output "$human" --summary-output "$summary" || die 'objdump filter failed'
    [[ -s $raw && -s $human && -s $summary ]] || die 'objdump filter produced empty artifact'
    /usr/bin/printf 'full_raw_sha256=%s\nfull_raw_bytes=%s\nfull_raw_lines=%s\nfull_demangled_sha256=%s\nfull_demangled_bytes=%s\nfull_demangled_lines=%s\nfull_disassemblies_retained=false\n' \
        "$full_raw_sha" "$full_raw_bytes" "$full_raw_lines" \
        "$full_human_sha" "$full_human_bytes" "$full_human_lines" >"$provenance"
    /usr/bin/sed '1d;s/^/filter_/' "$summary" >>"$provenance"
    cleanup_disassembly_tmp
    /usr/bin/awk '/^[[:space:]]*[0-9A-Fa-f]+:/ { gsub(":", "", $1); print "0x" $1 }' "$raw" >"$addresses"
    [[ -s $addresses ]] || die 'compact objdump produced no instruction addresses'
    run_bounded_input 600 "$addresses" "$decoded" "$artifact_dir/binary.addr2line.err" \
        /usr/bin/addr2line -a -f -C -i -e "$CUBRIM" || die 'addr2line failed'
    /usr/bin/python3 "$MAPPER" build --objdump "$raw" --addr2line "$decoded" \
        --binary-dso "$CUBRIM" --output "$artifact_dir/instruction-map.tsv" \
        --coverage-output "$coverage" || die 'instruction mapper build failed'
    /usr/bin/grep -qxF $'coverage_percent\t100.000000' "$coverage" ||
        die 'target-owner instruction coverage is not 100 percent'
    for bucket in state_map_predict state_map_predict_call state_map_update state_map_update_call sm_div \
        ctr_predict_stationary ctr_update_stationary ctr_next_state ctr_record_store; do
        /usr/bin/awk -F '\t' -v b="$bucket" 'NR>1 && $6==b { found=1 } END { exit !found }' \
            "$artifact_dir/instruction-map.tsv" || die "instruction map bucket missing: $bucket"
    done
    INSTRUCTION_MAP_SHA=$(sha "$artifact_dir/instruction-map.tsv")
    /usr/bin/printf '%s\n' "$INSTRUCTION_MAP_SHA" >"$artifact_dir/instruction-map.sha256"
    (
        cd "$artifact_dir"
        /usr/bin/sha256sum binary.objdump.raw.txt binary.objdump.demangled.txt \
            binary.object-addresses.txt binary.addr2line.txt objdump-filter-summary.tsv \
            full-disassembly-provenance.txt instruction-map-coverage.tsv instruction-map.tsv
    ) >"$artifact_dir/instruction-artifacts.sha256"
    /usr/bin/chmod a-w -- "$raw" "$human" "$addresses" "$decoded" "$summary" "$provenance" "$coverage" \
        "$artifact_dir/instruction-map.tsv" \
        "$artifact_dir/instruction-map.sha256" "$artifact_dir/instruction-artifacts.sha256"
    jlog "{\"t\":\"$(now)\",\"event\":\"instruction_map_frozen\",\"sha256\":\"$INSTRUCTION_MAP_SHA\",\"join\":\"exact DSO symbol+offset\"}"
}

verify_instruction_map() {
    [[ $INSTRUCTION_MAP_SHA =~ ^[0-9a-f]{64}$ ]] || die 'instruction map SHA is unset'
    [[ $(sha "$PARTIAL/instruction-map.tsv") == "$INSTRUCTION_MAP_SHA" ]] || die 'instruction map SHA mismatch'
    [[ $(/usr/bin/head -n 1 "$PARTIAL/instruction-map.sha256") == "$INSTRUCTION_MAP_SHA" ]] ||
        die 'instruction map SHA record mismatch'
    (cd "$PARTIAL" && /usr/bin/sha256sum -c instruction-artifacts.sha256 >/dev/null) ||
        die 'instruction artifact manifest mismatch'
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
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-cmp\",\"tag\":\"$tag\"}"
        return 0
    }
    output_sha=$(sha "$output")
    [[ $output_sha == "$orig_sha" ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-sha\",\"tag\":\"$tag\"}"
        return 0
    }
    /usr/bin/rm -- "$output"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"decode_ok\",\"tag\":\"$tag\",\"wall_s\":$wall,\"output_sha256\":\"$output_sha\"}"
    DECODE_RESULT=PASS
}

parse_cycles() {
    local file=$1 value
    value=$(/usr/bin/awk -F '\t' '$3=="cycles" && $1 ~ /^[0-9]+$/ { print $1; exit }' "$file")
    [[ $value =~ ^[0-9]+$ && $value -gt 0 ]] || return 1
    /usr/bin/printf '%s\n' "$value"
}

verify_perf_events() {
    local file=$1 event
    for event in "${PERF_SUPPORTED_EVENTS[@]}"; do
        /usr/bin/awk -F '\t' -v e="$event" -v re="$PERF_VALUE_RE" '$3==e && $1 ~ re { found=1 } END { exit !found }' \
            "$file" || return 1
    done
}

reduce_record() {
    local d=$1 index=$2
    run_bounded 300 "$d/perf$index.buildid-list.txt" "$d/perf$index.buildid-list.err" \
        /usr/bin/perf buildid-list -i "$d/perf$index.data" || {
        void_cell "record${index}_buildid_list_rc_$LAST_RC"; return 1;
    }
    run_bounded 300 "$d/perf$index.script.txt" "$d/perf$index.script.err" \
        /usr/bin/perf script -i "$d/perf$index.data" --show-lost-events \
        -F period,ip,sym,symoff,dso || {
        void_cell "record${index}_perf_script_rc_$LAST_RC"; return 1;
    }
    [[ -s $d/perf$index.buildid-list.txt ]] || {
        void_cell "record${index}_buildid_list_empty"; return 1;
    }
    [[ -s $d/perf$index.script.txt ]] || {
        void_cell "record${index}_perf_script_empty"; return 1;
    }
    [[ $BINARY_BUILD_ID =~ ^[0-9a-f]{32,128}$ ]] || {
        void_cell "record${index}_binary_build_id_invalid"; return 1;
    }
    /usr/bin/awk -v id="$BINARY_BUILD_ID" -v dso="$CUBRIM" '
        tolower($1)==id && $2==dso { matches++ }
        END { exit !(matches==1) }
    ' "$d/perf$index.buildid-list.txt" || {
        void_cell "record${index}_buildid_dso_identity_mismatch"; return 1;
    }
    run_bounded 300 "$d/perf$index.map.out" "$d/perf$index.map.err" \
        /usr/bin/python3 "$MAPPER" reduce --map "$PARTIAL/instruction-map.tsv" \
        --perf-script "$d/perf$index.script.txt" --binary-dso "$CUBRIM" \
        --perf-script-stderr "$d/perf$index.script.err" \
        --output "$d/perf$index.bucket-shares.tsv" \
        --diagnostics-output "$d/perf$index.record-diagnostics.tsv" || {
        void_cell "record${index}_mapper_reduce_rc_$LAST_RC"; return 1;
    }
    run_bounded 300 "$d/perf$index.report.txt" "$d/perf$index.report.err" \
        /usr/bin/perf report -i "$d/perf$index.data" --stdio --percent-limit 0 || {
        void_cell "record${index}_perf_report_rc_$LAST_RC"; return 1;
    }
    [[ -s $d/perf$index.bucket-shares.tsv ]] || {
        void_cell "record${index}_bucket_shares_missing"; return 1;
    }
    [[ -s $d/perf$index.record-diagnostics.tsv ]] || {
        void_cell "record${index}_record_diagnostics_missing"; return 1;
    }
    [[ -s $d/perf$index.report.txt ]] || {
        void_cell "record${index}_perf_report_missing"; return 1;
    }
}

run_cell() {
    local corpus=$1 file=$2 preset=$3 orig_bytes=$4 enc_timeout=$5 dec_timeout=$6 archive_sha=$7 orig_sha=$8
    local cell_name=$file/$preset d=$PARTIAL/$file.$preset src archive1 archive2 sha1 sha2
    local plain_wall first_cycles second_cycles cycle_class cycle_ratio
    local record1_wall record2_wall g3_class1 g3_class2 g3_ratio1 g3_ratio2
    local record_gate1 record_gate2 record_pair share_class
    CELL_RESULT=FAIL
    CELL_SELECTION=ELIGIBLE
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
    sha1=$(sha "$archive1")
    sha2=$(sha "$archive2")
    [[ $sha1 == "$archive_sha" && $sha2 == "$archive_sha" ]] || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-sha\",\"got1\":\"$sha1\",\"got2\":\"$sha2\"}"; return 0;
    }
    /usr/bin/cmp -- "$archive1" "$archive2" || {
        jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"gate_fail\",\"gate\":\"G1-cmp\"}"; return 0;
    }

    decode_checked "$cell_name" plain "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/time -v -o "$d/plain.time"
    [[ $DECODE_RESULT == PASS ]] || return 0
    plain_wall=$LAST_WALL
    decode_checked "$cell_name" pstat1 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf stat -d -x $'\t' -o "$d/pstat1.txt" -e "$PERF_SUPPORTED_CSV" --
    [[ $DECODE_RESULT == PASS ]] || return 0
    decode_checked "$cell_name" pstat2 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf stat -d -x $'\t' -o "$d/pstat2.txt" -e "$PERF_SUPPORTED_CSV" --
    [[ $DECODE_RESULT == PASS ]] || return 0
    if ! { verify_perf_events "$d/pstat1.txt" && verify_perf_events "$d/pstat2.txt"; }; then
        void_cell perf_stat_event_validation_failed; return 0;
    fi
    first_cycles=$(parse_cycles "$d/pstat1.txt") || { void_cell pstat1_cycles_parse_failed; return 0; }
    second_cycles=$(parse_cycles "$d/pstat2.txt") || { void_cell pstat2_cycles_parse_failed; return 0; }
    IFS='|' read -r cycle_class cycle_ratio <<<"$(classify_cycle_agreement "$first_cycles" "$second_cycles")"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"$cycle_class\",\"cycles1\":$first_cycles,\"cycles2\":$second_cycles,\"relative_delta\":$cycle_ratio}"
    [[ $cycle_class == cycle-agreement ]] || mark_no_select cycle-disagreement

    verify_instruction_map
    decode_checked "$cell_name" prec1 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf record -q -F 997 -e cycles -o "$d/perf1.data" --
    [[ $DECODE_RESULT == PASS ]] || return 0
    record1_wall=$LAST_WALL
    reduce_record "$d" 1 || return 0
    record_gate1=$(/usr/bin/awk -F '\t' '$1=="candidate_gate" { print $2 }' \
        "$d/perf1.record-diagnostics.tsv")
    [[ $record_gate1 == SUPPORTED || $record_gate1 == REFUTED || $record_gate1 == INDETERMINATE ]] || {
        void_cell record1_diagnostics_parse_failed; return 0;
    }
    [[ $record_gate1 == SUPPORTED ]] || mark_no_select "record1-$record_gate1"
    verify_instruction_map
    decode_checked "$cell_name" prec2 "$dec_timeout" "$src" "$archive2" "$orig_sha" "$d" \
        /usr/bin/perf record -q -F 997 -e cycles -o "$d/perf2.data" --
    [[ $DECODE_RESULT == PASS ]] || return 0
    record2_wall=$LAST_WALL
    reduce_record "$d" 2 || return 0
    record_gate2=$(/usr/bin/awk -F '\t' '$1=="candidate_gate" { print $2 }' \
        "$d/perf2.record-diagnostics.tsv")
    [[ $record_gate2 == SUPPORTED || $record_gate2 == REFUTED || $record_gate2 == INDETERMINATE ]] || {
        void_cell record2_diagnostics_parse_failed; return 0;
    }
    [[ $record_gate2 == SUPPORTED ]] || mark_no_select "record2-$record_gate2"

    IFS='|' read -r g3_class1 g3_ratio1 <<<"$(classify_instrument_overhead "$plain_wall" "$record1_wall")"
    IFS='|' read -r g3_class2 g3_ratio2 <<<"$(classify_instrument_overhead "$plain_wall" "$record2_wall")"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"G3\",\"record\":1,\"classification\":\"$g3_class1\",\"plain_wall_s\":$plain_wall,\"record_wall_s\":$record1_wall,\"ratio\":$g3_ratio1}"
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"G3\",\"record\":2,\"classification\":\"$g3_class2\",\"plain_wall_s\":$plain_wall,\"record_wall_s\":$record2_wall,\"ratio\":$g3_ratio2}"
    record_pair=$(classify_record_pair "$g3_class1" "$g3_class2")
    [[ $record_pair == records-clean ]] || mark_no_select records-perturbed
    run_bounded 60 "$d/share-stability.out" "$d/share-stability.err" \
        /usr/bin/python3 "$MAPPER" compare --first "$d/perf1.bucket-shares.tsv" \
        --second "$d/perf2.bucket-shares.tsv" --max-percentage-points "$SHARE_DELTA_MAX" \
        --output "$d/share-stability.tsv" || { void_cell share_compare_failed; return 0; }
    [[ -s $d/share-stability.tsv ]] || { void_cell share_output_missing; return 0; }
    share_class=$(/usr/bin/awk -F '\t' '$1=="classification" { print $2 }' "$d/share-stability.tsv")
    [[ $share_class == share-stable || $share_class == share-unstable ]] || {
        void_cell share_classification_parse_failed; return 0;
    }
    [[ $share_class == share-stable ]] || mark_no_select share-unstable
    reject_orphan_processes
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell_name\",\"event\":\"cell_done\",\"cycle_class\":\"$cycle_class\",\"record1_class\":\"$g3_class1\",\"record2_class\":\"$g3_class2\",\"record1_gate\":\"$record_gate1\",\"record2_gate\":\"$record_gate2\",\"share_class\":\"$share_class\",\"selection\":\"$CELL_SELECTION\"}"
    CELL_RESULT=PASS
    CURRENT_CELL=
}

write_manifests() {
    local tmp
    tmp=$(/usr/bin/mktemp /tmp/cubr-current-profile-g3-SHA256SUMS.tmp.XXXXXX)
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
    /usr/bin/printf 'runner_sha256=%s\nmapper_sha256=%s\nbinary_sha256=%s\ninstruction_map_sha256=%s\ncode_commit=%s\npin=0-15\nsystemd=%s\ninvocation_id=%s\nNRestarts=0\nprofile_status=%s\nselection=%s\ncompleted_at=%s\n' \
        "$EXPECTED_RUNNER_SHA" "$MAPPER_SHA_EXPECT" "$CUBRIM_SHA_EXPECT" "$INSTRUCTION_MAP_SHA" "$CODE_COMMIT" \
        "$SYSTEMD_CONTRACT" "${INVOCATION_ID:-preflight}" "$FINAL_PROFILE_STATUS" \
        "$CAMPAIGN_SELECTION" "$(now)" >"$PARTIAL/TIMING-DONE.STAMP"
}

rename_noreplace() {
    local failure
    if failure=$(/usr/bin/python3 - "$1" "$2" 2>&1 <<'PY'
import ctypes
import errno
import os
import sys

AT_FDCWD = -100
RENAME_NOREPLACE = 1
source = os.fsencode(sys.argv[1])
destination = os.fsencode(sys.argv[2])
libc = ctypes.CDLL(None, use_errno=True)
renameat2 = libc.renameat2
renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
renameat2.restype = ctypes.c_int
if renameat2(AT_FDCWD, source, AT_FDCWD, destination, RENAME_NOREPLACE) != 0:
    error = ctypes.get_errno()
    print(f"renameat2_errno={error}_name={errno.errorcode.get(error, 'UNKNOWN')}", file=sys.stderr)
    raise SystemExit(1)
PY
    ); then
        return 0
    fi
    [[ $failure =~ ^renameat2_errno=[0-9]+_name=[A-Z0-9]+$ ]] || failure=renameat2_helper_failure
    if [[ -n ${JOURNAL:-} && -f $JOURNAL && ! -L $JOURNAL ]]; then
        /usr/bin/chmod u+w -- "$JOURNAL" 2>/dev/null || true
        jlog "{\"t\":\"$(now)\",\"event\":\"rename_failed\",\"reason\":\"$failure\"}" || true
        /usr/bin/chmod a-w -- "$JOURNAL" 2>/dev/null || true
    fi
    /usr/bin/printf '%s\n' "$failure" >&2
    return 1
}

on_exit() {
    local rc=$?
    cleanup_disassembly_tmp
    (( rc != 0 )) || return 0
    if [[ -d $PARTIAL && ! -L $PARTIAL ]]; then
        /usr/bin/chmod -R u+w -- "$PARTIAL" 2>/dev/null || true
        JOURNAL=$PARTIAL/journal.jsonl
        if [[ -e $PARTIAL/TIMING-DONE.STAMP || -L $PARTIAL/TIMING-DONE.STAMP ]]; then
            /usr/bin/rm -- "$PARTIAL/TIMING-DONE.STAMP"
        fi
        jlog "{\"t\":\"$(now)\",\"event\":\"run_failed\",\"rc\":$rc,\"cell\":\"$CURRENT_CELL\"}"
        /usr/bin/printf 'rc=%s\nfailed_at=%s\ncell=%s\n' "$rc" "$(now)" "$CURRENT_CELL" >"$PARTIAL/FAILED.STAMP"
        if [[ -n $PREFLIGHT_DIR && -d $PREFLIGHT_DIR && ! -L $PREFLIGHT_DIR ]]; then
            /usr/bin/cp -an -- "$PREFLIGHT_DIR/." "$PARTIAL/" 2>/dev/null || true
            /usr/bin/find "$PREFLIGHT_DIR" -depth -delete 2>/dev/null || true
            PREFLIGHT_DIR=
        fi
        /usr/bin/chmod -R a-w -- "$PARTIAL" 2>/dev/null || true
    elif [[ -n $PREFLIGHT_DIR && -d $PREFLIGHT_DIR && ! -L $PREFLIGHT_DIR && \
        ! -e $PARTIAL && ! -L $PARTIAL ]]; then
        JOURNAL=$PREFLIGHT_DIR/journal.jsonl
        jlog "{\"t\":\"$(now)\",\"event\":\"run_failed\",\"phase\":\"admission\",\"rc\":$rc}"
        /usr/bin/printf 'rc=%s\nfailed_at=%s\nphase=admission\n' "$rc" "$(now)" \
            >"$PREFLIGHT_DIR/FAILED.STAMP"
        /usr/bin/chmod -R a-w -- "$PREFLIGHT_DIR" 2>/dev/null || true
        if rename_noreplace "$PREFLIGHT_DIR" "$PARTIAL"; then
            PREFLIGHT_DIR=
        fi
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

self_test_fail() {
    /usr/bin/printf 'current_profile_g3_self_test=FAIL reason=%s\n' "$1" >&2
    return 1
}

self_test() {
    local d status value
    [[ $(classify_cycle_agreement 100 110) == cycle-agreement\|* ]] || { self_test_fail cycle_threshold_boundary; return 1; }
    [[ $(classify_cycle_agreement 100 112) == cycle-disagreement\|* ]] || { self_test_fail cycle_threshold_boundary; return 1; }
    [[ $(classify_instrument_overhead 100 110) == instrument-clean\|* ]] || { self_test_fail g3_threshold_boundary; return 1; }
    [[ $(classify_instrument_overhead 100 111) == instrument-perturbed\|* ]] || { self_test_fail g3_threshold_boundary; return 1; }
    [[ $(classify_share_stability 1000 10000 1100 10000) == share-stable\|* ]] || { self_test_fail share_threshold_boundary; return 1; }
    [[ $(classify_share_stability 1000 10000 1101 10000) == share-unstable\|* ]] || { self_test_fail share_threshold_boundary; return 1; }
    [[ $(classify_record_pair instrument-clean instrument-clean) == records-clean ]] || {
        self_test_fail both_records_clean; return 1;
    }
    [[ $(classify_record_pair instrument-clean instrument-perturbed) == records-perturbed ]] || {
        self_test_fail both_records_clean; return 1;
    }
    [[ $(classify_record_pair instrument-perturbed instrument-clean) == records-perturbed ]] || {
        self_test_fail both_records_clean; return 1;
    }
    d=$(/usr/bin/mktemp -d /tmp/cubr-current-profile-g3-self-test.XXXXXX)
    /usr/bin/printf 'Displaying notes\n    Build ID: AABBCCDDEEFF00112233445566778899\n' \
        >"$d/readelf-valid.txt"
    [[ $(parse_build_id "$d/readelf-valid.txt") == aabbccddeeff00112233445566778899 ]] || {
        /usr/bin/rm -rf -- "$d"; self_test_fail build_id_parser; return 1;
    }
    /usr/bin/printf 'Build ID: aabbccddeeff00112233445566778899\nBuild ID: 00112233445566778899aabbccddeeff\n' \
        >"$d/readelf-duplicate.txt"
    if parse_build_id "$d/readelf-duplicate.txt" >/dev/null; then
        /usr/bin/rm -rf -- "$d"; self_test_fail build_id_parser; return 1;
    fi
    /usr/bin/printf '1\t\tcycles\n' >"$d/supported.txt"
    /usr/bin/printf '<not supported>\t\tL1-dcache-load-misses\n' >"$d/unsupported.txt"
    IFS='|' read -r status value <<<"$(parse_perf_event_probe "$d/supported.txt" cycles)" || {
        /usr/bin/rm -rf -- "$d"; self_test_fail perf_event_supported; return 1;
    }
    [[ $status == supported && $value == 1 ]] || {
        /usr/bin/rm -rf -- "$d"; self_test_fail perf_event_supported; return 1;
    }
    IFS='|' read -r status value <<<"$(parse_perf_event_probe "$d/unsupported.txt" L1-dcache-load-misses)" || {
        /usr/bin/rm -rf -- "$d"; self_test_fail perf_event_unsupported; return 1;
    }
    [[ $status == unsupported && $value == '<not supported>' ]] || {
        /usr/bin/rm -rf -- "$d"; self_test_fail perf_event_unsupported; return 1;
    }
    /usr/bin/mkdir -- "$d/rename-source" "$d/rename-destination"
    JOURNAL=$d/rename-journal.jsonl
    : >"$JOURNAL"
    if rename_noreplace "$d/rename-source" "$d/rename-destination" 2>/dev/null; then
        /usr/bin/rm -rf -- "$d"; self_test_fail rename_noreplace_collision; return 1;
    fi
    [[ -d $d/rename-source && -d $d/rename-destination ]] || {
        /usr/bin/rm -rf -- "$d"; self_test_fail rename_noreplace_collision; return 1;
    }
    /usr/bin/grep -qE '"event":"rename_failed","reason":"renameat2_errno=[0-9]+_name=EEXIST"' "$JOURNAL" || {
        /usr/bin/rm -rf -- "$d"; self_test_fail rename_noreplace_journal; return 1;
    }
    /usr/bin/rmdir -- "$d/rename-destination"
    rename_noreplace "$d/rename-source" "$d/rename-destination" || {
        /usr/bin/rm -rf -- "$d"; self_test_fail rename_noreplace_success; return 1;
    }
    [[ ! -e $d/rename-source && -d $d/rename-destination ]] || {
        /usr/bin/rm -rf -- "$d"; self_test_fail rename_noreplace_success; return 1;
    }
    JOURNAL=
    /usr/bin/rm -rf -- "$d"
    /usr/bin/printf 'current_profile_g3_self_test=PASS\n'
}

preflight() {
    refuse_existing_output || exit 1
    PREFLIGHT_DIR=$(/usr/bin/mktemp -d /tmp/cubr-current-profile-g3-preflight.XXXXXX)
    trap 'cleanup_preflight "$?"' EXIT
    JOURNAL=$PREFLIGHT_DIR/journal.jsonl
    DEADLINE_MONOTONIC=$(( $(monotonic_seconds) + 300 ))
    admission "$PREFLIGHT_DIR" 0
    build_instruction_map "$PREFLIGHT_DIR"
    verify_feasibility_fixture "$PREFLIGHT_DIR"
    /usr/bin/printf 'current_profile_g3_preflight=PASS\n'
    cleanup_preflight 0
    trap - EXIT
}

main_run() {
    local cell corpus file preset orig_bytes enc_timeout dec_timeout archive_sha orig_sha
    refuse_existing_output || exit 1
    PREFLIGHT_DIR=$(/usr/bin/mktemp -d /tmp/cubr-current-profile-g3-admission.XXXXXX)
    JOURNAL=$PREFLIGHT_DIR/journal.jsonl
    trap on_exit EXIT
    DEADLINE_MONOTONIC=$(( $(monotonic_seconds) + CAMPAIGN_BUDGET_SECONDS ))
    admission "$PREFLIGHT_DIR" 1
    refuse_existing_output || exit 1
    /usr/bin/mkdir -- "$PARTIAL"
    /usr/bin/cp -- "$PREFLIGHT_DIR/journal.jsonl" "$PARTIAL/journal.jsonl"
    JOURNAL=$PARTIAL/journal.jsonl
    /usr/bin/cp -a -- "$PREFLIGHT_DIR/." "$PARTIAL/"
    cleanup_preflight 0
    JOURNAL=$PARTIAL/journal.jsonl
    /usr/bin/cp -- "${BASH_SOURCE[0]}" "$PARTIAL/current-profile-g3-run.sh"
    /usr/bin/cp -- "$MAPPER_SOURCE" "$PARTIAL/current_profile_g3_map.py"
    MAPPER=$PARTIAL/current_profile_g3_map.py
    /usr/bin/chmod a-w -- "$MAPPER"
    jlog "{\"t\":\"$(now)\",\"event\":\"run_start\",\"pin\":\"0-15\",\"threads\":4,\"budget_s\":$CAMPAIGN_BUDGET_SECONDS,\"deadline_monotonic_s\":$DEADLINE_MONOTONIC}"
    run_suites
    build_instruction_map
    verify_feasibility_fixture "$PARTIAL"
    for cell in "${CELLS[@]}"; do
        IFS='|' read -r corpus file preset orig_bytes enc_timeout dec_timeout archive_sha orig_sha <<<"$cell"
        (( $(remaining_budget_seconds) > 0 )) || die "campaign budget expired before $file/$preset"
        run_cell "$corpus" "$file" "$preset" "$orig_bytes" "$enc_timeout" "$dec_timeout" "$archive_sha" "$orig_sha"
        reject_orphan_processes
        [[ $CELL_RESULT == PASS ]] || die "cell failed or void: $file/$preset"
    done
    reject_orphan_processes
    if [[ $CAMPAIGN_SELECTION == NO-SELECT ]]; then
        FINAL_PROFILE_STATUS=VALID-DESCRIPTIVE-PROFILE
    fi
    jlog "{\"t\":\"$(now)\",\"event\":\"run_end\",\"profile_status\":\"$FINAL_PROFILE_STATUS\",\"selection\":\"$CAMPAIGN_SELECTION\"}"
    [[ ! -e $OUT && ! -L $OUT ]] || die 'final output collision before rename'
    verify_instruction_map
    write_manifests
    write_completion_marker
    /usr/bin/chmod -R a-w -- "$PARTIAL"
    rename_noreplace "$PARTIAL" "$OUT"
}

case ${1:-} in
    --self-test) self_test ;;
    --preflight) preflight ;;
    --run) main_run ;;
    *) /usr/bin/printf 'usage: %s --self-test|--preflight|--run\n' "$0" >&2; exit 2 ;;
esac
