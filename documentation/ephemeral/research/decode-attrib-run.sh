#!/usr/bin/env bash
# Decode-time attribution at the Phase C operating point.
# Preregistration: CUBR-DECODE-ATTRIB-20260809.md (same directory).
# Runs on the dev-ai stand as root. Writes everything under $OUT; never the DB.
set -u

ROOT=/root/phaseC
CUBRIM=$ROOT/cubrim-3a13f48
CUBRIM_SHA_EXPECT=d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb
CORPUS=/root/corpus
OUT=/root/cubr-decode-attrib-20260809
PIN="taskset -c 16-19"
LOAD_MAX=8.0
JOURNAL=$OUT/journal.jsonl

# cell list: corpus file preset canonical_archive_sha256(from phaseC journals)
CELLS=(
  "silesia dickens max b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82"
  "silesia xml max d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37"
  "silesia x-ray max 4ed8a550b2e05da471d33dd9f044c4e357fee45cfc77bbfcdb3f173a657953d7"
  "silesia dickens web a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341"
)

mkdir -p "$OUT"
export CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4

jlog() { printf '%s\n' "$1" >> "$JOURNAL"; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# refuse to run with the wrong binary
BSHA=$(sha256sum "$CUBRIM" | awk '{print $1}')
if [ "$BSHA" != "$CUBRIM_SHA_EXPECT" ]; then
  jlog "{\"t\":\"$(now)\",\"event\":\"abort\",\"reason\":\"binary sha mismatch: $BSHA\"}"
  exit 1
fi

quiet_wait() {
  local tries=0
  while :; do
    local load
    load=$(awk '{print $1}' /proc/loadavg)
    awk -v l="$load" -v m="$LOAD_MAX" 'BEGIN{exit !(l<m)}' && return 0
    tries=$((tries+1))
    if [ "$tries" -gt 60 ]; then return 1; fi
    sleep 60
  done
}

run_cell() {
  local corpus=$1 file=$2 preset=$3 want_sha=$4
  local d=$OUT/$file.$preset
  mkdir -p "$d"
  local src=$CORPUS/$corpus/$file
  [ -f "$src" ] || src=$CORPUS/$file
  if [ ! -f "$src" ]; then
    jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"void\",\"reason\":\"source file missing\"}"
    return
  fi
  local orig_sha; orig_sha=$(sha256sum "$src" | awk '{print $1}')

  quiet_wait || { jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"void\",\"reason\":\"host never quiet\"}"; return; }

  # G1: canonical archive identity
  jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"encode_start\"}"
  $PIN nice -n 10 "$CUBRIM" compress --preset "$preset" --quiet "$src" "$d/a.cub" \
    > "$d/enc.out" 2> "$d/enc.err"
  local asha; asha=$(sha256sum "$d/a.cub" 2>/dev/null | awk '{print $1}')
  if [ "$asha" != "$want_sha" ]; then
    jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"gate_fail\",\"gate\":\"G1\",\"got\":\"$asha\",\"want\":\"$want_sha\"}"
    return
  fi
  jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"G1_pass\",\"archive_sha256\":\"$asha\"}"

  decode_checked() { # $1 tag, rest: wrapper cmd prefix (may be empty)
    local tag=$1; shift
    rm -f "$d/r.bin"
    quiet_wait || { jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"void\",\"reason\":\"host never quiet before $tag\"}"; return 1; }
    local t0 t1
    t0=$(date +%s.%N)
    "$@" $PIN "$CUBRIM" decompress --quiet "$d/a.cub" "$d/r.bin" \
      > "$d/$tag.out" 2> "$d/$tag.err"
    local rc=$?
    t1=$(date +%s.%N)
    local wall; wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
    if [ $rc -ne 0 ]; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"gate_fail\",\"gate\":\"G2\",\"tag\":\"$tag\",\"rc\":$rc}"
      return 1
    fi
    if ! cmp -s "$src" "$d/r.bin"; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"gate_fail\",\"gate\":\"G2-cmp\",\"tag\":\"$tag\"}"
      return 1
    fi
    local rsha; rsha=$(sha256sum "$d/r.bin" | awk '{print $1}')
    if [ "$rsha" != "$orig_sha" ]; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"gate_fail\",\"gate\":\"G2-sha\",\"tag\":\"$tag\"}"
      return 1
    fi
    jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"decode_ok\",\"tag\":\"$tag\",\"wall_s\":$wall}"
    echo "$wall"
    return 0
  }

  # baseline plain decode (+ peak RSS)
  local base_wall
  base_wall=$(decode_checked plain /usr/bin/time -v -o "$d/plain.time") || return
  # perf stat x2
  decode_checked pstat1 perf stat -o "$d/pstat1.txt" -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,dTLB-load-misses,page-faults -- || return
  decode_checked pstat2 perf stat -o "$d/pstat2.txt" -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,dTLB-load-misses,page-faults -- || return
  # perf record
  local rec_wall
  rec_wall=$(decode_checked prec perf record -F 997 -e cycles -o "$d/perf.data" --) || return
  # G3: instrument overhead
  local ratio
  ratio=$(awk -v r="$rec_wall" -v b="$base_wall" 'BEGIN{printf "%.3f", r/b}')
  jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"G3\",\"plain_wall_s\":$base_wall,\"prec_wall_s\":$rec_wall,\"ratio\":$ratio}"
  perf report -i "$d/perf.data" --stdio --percent-limit 0.3 > "$d/perf-report.txt" 2> "$d/perf-report.err"
  jlog "{\"t\":\"$(now)\",\"cell\":\"$file/$preset\",\"event\":\"cell_done\"}"
}

jlog "{\"t\":\"$(now)\",\"event\":\"run_start\",\"binary_sha256\":\"$BSHA\",\"pin\":\"16-19\",\"env\":\"CUBR_THREADS=4\"}"
for c in "${CELLS[@]}"; do
  # shellcheck disable=SC2086
  run_cell $c
done
jlog "{\"t\":\"$(now)\",\"event\":\"run_end\"}"
