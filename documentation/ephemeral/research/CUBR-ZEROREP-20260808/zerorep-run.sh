#!/usr/bin/env bash
# Preregistered nci/max zero-representation decode RSS and speed comparison.
set -euo pipefail

ROOT=/root/cubr-levers/zerorep-20260808
INPUT=/root/cubr-levers/bench/nci.2m
CANON=/root/cubr-levers/preset-rss/nci.max.base.cbr
BASE_ROOT=/root/cubr-levers/baseline-e70
CURRENT_ROOT=/root/cubr-levers
ZERO_ROOT=/root/cubr-levers/zerorep-code
BASE=$BASE_ROOT/code/cubrim-rs/target/release/cubrim
CURRENT=$CURRENT_ROOT/code/cubrim-rs/target/release/cubrim
ZERO=$ZERO_ROOT/code/cubrim-rs/target/release/cubrim
PIN=0-15
FILE=nci
PRESET=max
RUN_MODE=zerorep-nci-max-pin0-15-t4

BASE_SOURCE=e70d1cdca6226e994c0393149e364f252f7c0a1f
CURRENT_SOURCE=49e429e58722f730c4f3cbb0a69731fec430bb56
ZERO_SOURCE=f047523fcdc15561baa05fee597819fd6bdb53d3
BASE_SHA=a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd
CURRENT_SHA=12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c
ZERO_SHA=771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20
ZERO_CM2_SHA=1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf
TEST_EVIDENCE_SHA=0207ddcc07a36e67ba8e5c64adaeaa25873ab3e1b71b628f0d2de9e101f4f37b
INPUT_SHA=6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e
ARCHIVE_SHA=1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b
ARCHIVE_BYTES=104139
RUNNER_REL=documentation/ephemeral/research/CUBR-ZEROREP-20260808/zerorep-run.sh
TEST_EVIDENCE_REL=documentation/ephemeral/research/CUBR-ZEROREP-20260808/tdd-local-gates.md

export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1

LOG=/dev/stderr
log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 3; }
invalid() { log "HARNESS_INVALID: $*"; exit 4; }

# Controlled Gate-9 seam. Unset in the preregistered live invocation.
case "${CUBR_ZEROREP_CONTROL:-}" in
    positive)
        /bin/true || fail "positive control child"
        printf 'CONTROL_PASS\n'
        exit 0
        ;;
    negative)
        if /bin/false; then
            invalid "negative control child unexpectedly passed"
        fi
        fail "EXPECTED_RED: negative control child"
        ;;
    setup-negative)
        [[ -e /definitely-missing-cubr-zerorep-fixture ]] \
            || invalid "missing synthetic setup fixture"
        fail "setup-negative reached child unexpectedly"
        ;;
    "") ;;
    *) invalid "unknown control mode" ;;
esac

if [[ -e "$ROOT" ]]; then
    fail "output root already exists: $ROOT"
fi
mkdir -p "$ROOT"
LOG=$ROOT/zerorep.log
TSV=$ROOT/zerorep.tsv
MEDIANS=$ROOT/medians.tsv
VERDICT=$ROOT/verdict.json
HASHES=$ROOT/HASHES.tsv
DONE=$ROOT/DONE.STAMP

actual_sha() { sha256sum "$1" | cut -d ' ' -f1; }
verify_sha() {
    local path=$1 expected=$2
    [[ -f "$path" ]] || fail "missing file: $path"
    [[ "$(actual_sha "$path")" == "$expected" ]] || fail "sha256 mismatch: $path"
}
wall_rss() {
    python3 - "$1" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
wall_match = re.search(r"Elapsed \(wall clock\).*?: (.+)", text)
rss_match = re.search(r"Maximum resident set size.*?: (\d+)", text)
if wall_match is None or rss_match is None:
    raise SystemExit("missing GNU time fields")
parts = [float(value) for value in wall_match.group(1).strip().split(":")]
seconds = (
    parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 3
    else parts[0] * 60 + parts[1]
)
print(f"{seconds:.2f}\t{rss_match.group(1)}")
PY
}

verify_sha "$BASE" "$BASE_SHA"
verify_sha "$CURRENT" "$CURRENT_SHA"
verify_sha "$ZERO" "$ZERO_SHA"
verify_sha "$ZERO_ROOT/code/cubrim-rs/src/cm2.rs" "$ZERO_CM2_SHA"
verify_sha "$ZERO_ROOT/$TEST_EVIDENCE_REL" "$TEST_EVIDENCE_SHA"
verify_sha "$INPUT" "$INPUT_SHA"
verify_sha "$CANON" "$ARCHIVE_SHA"
[[ "$(stat -c %s "$CANON")" == "$ARCHIVE_BYTES" ]] || fail "canonical archive size"

[[ "$(git -C "$BASE_ROOT" rev-parse HEAD)" == "$BASE_SOURCE" ]] || fail "baseline source"
[[ "$(git -C "$CURRENT_ROOT" rev-parse HEAD)" == "$CURRENT_SOURCE" ]] || fail "current source"
git -C "$ZERO_ROOT" merge-base --is-ancestor "$ZERO_SOURCE" HEAD \
    || fail "zero source is not an ancestor of runner head"
git -C "$ZERO_ROOT" diff --quiet "$ZERO_SOURCE"..HEAD -- code/cubrim-rs \
    || fail "codec changed after pinned zero source"
[[ -z "$(git -C "$ZERO_ROOT" status --porcelain)" ]] || fail "zero checkout is dirty"
runner_sha=$(actual_sha "$ZERO_ROOT/$RUNNER_REL")
committed_runner_sha=$(git -C "$ZERO_ROOT" show "HEAD:$RUNNER_REL" | sha256sum | cut -d ' ' -f1)
[[ "$runner_sha" == "$committed_runner_sha" ]] || fail "runner differs from HEAD blob"

load1=$(cut -d ' ' -f1 /proc/loadavg)
python3 -c "import sys; sys.exit(0 if float('$load1') < 2.0 else 1)" \
    || fail "admission loadavg $load1 is not below 2.0"
if pgrep -x cubrim >/dev/null \
    || pgrep -x cubrim-l1v2 >/dev/null \
    || pgrep -x cubrim-sweep >/dev/null; then
    fail "foreign Cubrim process present"
fi

printf 'kind\tname\tvalue\n' > "$HASHES"
printf 'source\tbase\t%s\nsource\tcurrent\t%s\nsource\tzero\t%s\n' \
    "$BASE_SOURCE" "$CURRENT_SOURCE" "$ZERO_SOURCE" >> "$HASHES"
printf 'source\trunner-head\t%s\nrunner\tcommitted-blob\t%s\n' \
    "$(git -C "$ZERO_ROOT" rev-parse HEAD)" "$committed_runner_sha" >> "$HASHES"
printf 'binary\tbase\t%s\nbinary\tcurrent\t%s\nbinary\tzero\t%s\n' \
    "$BASE_SHA" "$CURRENT_SHA" "$ZERO_SHA" >> "$HASHES"
printf 'input\t%s\t%s\narchive\t%s/%s\t%s\n' \
    "$FILE" "$INPUT_SHA" "$FILE" "$PRESET" "$ARCHIVE_SHA" >> "$HASHES"
printf 'test-evidence\tlocal-gates\t%s\n' "$TEST_EVIDENCE_SHA" >> "$HASHES"
cp "$ZERO_ROOT/$TEST_EVIDENCE_REL" "$ROOT/tdd-local-gates.md"
log "admission loadavg=$load1 pin=$PIN threads=4 run_mode=$RUN_MODE"
log "runner_head=$(git -C "$ZERO_ROOT" rev-parse HEAD) runner_sha=$runner_sha zero_source=$ZERO_SOURCE"

printf 'file\tpreset\tbuild\tsample\tarchive_sha256\tcomp_bytes\tdec_s\tdec_rss_kib\trt\n' > "$TSV"

for build in base current zero; do
    case "$build" in
        base) binary=$BASE ;;
        current) binary=$CURRENT ;;
        zero) binary=$ZERO ;;
        *) invalid "unknown build: $build" ;;
    esac
    archive=$ROOT/$FILE.$PRESET.$build.cbr
    if ! timeout 1800 taskset -c "$PIN" "$binary" compress --preset "$PRESET" --quiet "$INPUT" "$archive"; then
        fail "compression $build"
    fi
    verify_sha "$archive" "$ARCHIVE_SHA"
    [[ "$(stat -c %s "$archive")" == "$ARCHIVE_BYTES" ]] || fail "archive size $build"
    cmp -s "$archive" "$CANON" || fail "canonical archive identity $build"
done

cmp -s "$ROOT/$FILE.$PRESET.base.cbr" "$ROOT/$FILE.$PRESET.current.cbr" \
    || fail "base/current archive identity"
cmp -s "$ROOT/$FILE.$PRESET.base.cbr" "$ROOT/$FILE.$PRESET.zero.cbr" \
    || fail "base/zero archive identity"
log "archive_identity=PASS sha256=$ARCHIVE_SHA bytes=$ARCHIVE_BYTES"

for build in base current zero; do
    case "$build" in
        base) binary=$BASE ;;
        current) binary=$CURRENT ;;
        zero) binary=$ZERO ;;
    esac
    archive=$ROOT/$FILE.$PRESET.$build.cbr
    back=$ROOT/$FILE.$PRESET.$build.warm.back
    if ! timeout 300 taskset -c "$PIN" "$binary" decompress "$archive" "$back" >/dev/null; then
        fail "warmup decode $build"
    fi
    cmp -s "$INPUT" "$back" || fail "warmup round-trip $build"
    rm -f "$back"
done
log "warmups=PASS"

for sample in 1 2 3; do
    for build in base current zero; do
        case "$build" in
            base) binary=$BASE ;;
            current) binary=$CURRENT ;;
            zero) binary=$ZERO ;;
        esac
        archive=$ROOT/$FILE.$PRESET.$build.cbr
        back=$ROOT/$FILE.$PRESET.$build.s$sample.back
        timing=$ROOT/time.$build.s$sample.txt
        if ! taskset -c "$PIN" /usr/bin/time -v timeout 300 \
            "$binary" decompress "$archive" "$back" >/dev/null 2> "$timing"; then
            fail "measured decode build=$build sample=$sample"
        fi
        read -r dec_s dec_rss <<< "$(wall_rss "$timing")"
        cmp -s "$INPUT" "$back" || fail "measured round-trip build=$build sample=$sample"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tPASS\n' \
            "$FILE" "$PRESET" "$build" "$sample" "$ARCHIVE_SHA" "$ARCHIVE_BYTES" \
            "$dec_s" "$dec_rss" | tee -a "$TSV" >> "$LOG"
        rm -f "$back"
    done
done

python3 - "$TSV" "$MEDIANS" "$VERDICT" <<'PY'
import csv
import json
import statistics
import sys

tsv_path, medians_path, verdict_path = sys.argv[1:]
groups = {name: {"seconds": [], "rss_kib": []} for name in ("base", "current", "zero")}
with open(tsv_path, encoding="utf-8", newline="") as source:
    for row in csv.DictReader(source, delimiter="\t"):
        if row["rt"] != "PASS" or row["build"] not in groups:
            raise SystemExit("invalid sample row")
        groups[row["build"]]["seconds"].append(float(row["dec_s"]))
        groups[row["build"]]["rss_kib"].append(int(row["dec_rss_kib"]))
if any(len(values["seconds"]) != 3 for values in groups.values()):
    raise SystemExit("expected exactly three samples per build")

medians = {
    name: {
        "seconds": statistics.median(values["seconds"]),
        "rss_kib": statistics.median(values["rss_kib"]),
    }
    for name, values in groups.items()
}
base = medians["base"]
current = medians["current"]
zero = medians["zero"]
packed_penalty_kib = current["rss_kib"] - base["rss_kib"]
reclaimed_kib = current["rss_kib"] - zero["rss_kib"]
residual_kib = zero["rss_kib"] - base["rss_kib"]
reclaim_fraction = reclaimed_kib / packed_penalty_kib if packed_penalty_kib > 0 else None
ceiling_fraction = reclaimed_kib / (768 * 1024)
zero_current_ratio = zero["seconds"] / current["seconds"]
base_zero_speedup = base["seconds"] / zero["seconds"]
rss_pass = residual_kib <= 65536 and reclaim_fraction is not None and reclaim_fraction >= 0.75
speed_pass = zero_current_ratio <= 1.05 and base_zero_speedup >= 1.10
verdict = {
    "base_zero_speedup": base_zero_speedup,
    "ceiling_fraction_reclaimed": ceiling_fraction,
    "compound_pass": rss_pass and speed_pass,
    "packed_penalty_kib": packed_penalty_kib,
    "reclaim_fraction": reclaim_fraction,
    "reclaimed_kib": reclaimed_kib,
    "residual_kib": residual_kib,
    "rss_pass": rss_pass,
    "speed_pass": speed_pass,
    "zero_current_time_ratio": zero_current_ratio,
}
with open(medians_path, "w", encoding="utf-8", newline="") as target:
    target.write("build\tdec_s_median\tdec_rss_kib_median\n")
    for name in ("base", "current", "zero"):
        target.write(f"{name}\t{medians[name]['seconds']:.2f}\t{medians[name]['rss_kib']}\n")
with open(verdict_path, "w", encoding="utf-8") as target:
    json.dump(verdict, target, indent=2, sort_keys=True)
    target.write("\n")
PY

compound=$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["compound_pass"]).upper())' "$VERDICT")
printf 'completed_at=%s\nrun_mode=%s\ncompound_pass=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RUN_MODE" "$compound" > "$DONE"
log "post-run $(cat /proc/loadavg)"
log "ZEROREP-COMPLETE compound_pass=$compound"
