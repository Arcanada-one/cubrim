#!/usr/bin/env bash
# CUBR-SPEEDFLOOR-20260811 — per-file decode throughput, cubrim vs field, one host, pin 0-15.
# Gates: every decode verified by cmp AND sha256 vs the original. Any mismatch voids the cell.
set -uo pipefail

BIN=/home/dev/.worktrees/cubrim/CUBR-SPEEDFLOOR/code/cubrim-rs/target/release/cubrim
CORPUS=/home/dev/cubr-cubecore-research/corpus-silesia
OUT="$(cd "$(dirname "$0")" && pwd)/out"
PIN=0-15
mkdir -p "$OUT/arch" "$OUT/back" "$OUT/logs"

RES="$OUT/results.tsv"
GATES="$OUT/gates.tsv"
[ -f "$RES" ]   || printf 'file\ttool\tsetting\tphase\tsample\twall_s\trss_kib\tarchive_bytes\n' > "$RES"
[ -f "$GATES" ] || printf 'file\ttool\tsetting\tsample\tcmp\tsha256\tverdict\n' > "$GATES"

scoped() { systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 -q "$@"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
wall_rss() { # /usr/bin/time -v log -> "wall rss"
  local log=$1 w r
  w=$(awk -F': ' '/Elapsed \(wall clock\)/ {print $2}' "$log" | awk -F: '{if(NF==3)print $1*3600+$2*60+$3; else print $1*60+$2}')
  r=$(awk -F': ' '/Maximum resident set size/ {print $2}' "$log")
  echo "${w:-NA} ${r:-NA}"
}

loadlog() { while :; do echo "$(date -u +%FT%TZ) $(cut -d' ' -f1-3 /proc/loadavg)"; sleep 30; done; }
loadlog > "$OUT/loadlog.txt" & LOADPID=$!
trap 'kill $LOADPID 2>/dev/null' EXIT

# tool decode/compress definitions: name|setting|compress_cmd|decompress_cmd|ext
run_cell() {
  local f=$1 tool=$2 setting=$3 ccmd=$4 dcmd=$5 ext=$6 ctimeout=$7 dtimeout=$8
  local input="$CORPUS/$f"
  local arch="$OUT/arch/$f.$tool.$ext"
  local back="$OUT/back/$f.$tool.out"
  local ref; ref=$(sha "$input")

  if [ ! -s "$arch" ]; then
    echo "[$(date -u +%T)] compress $f/$tool/$setting ..."
    # shellcheck disable=SC2086
    scoped taskset -c "$PIN" timeout "$ctimeout" bash -c "$ccmd" "$input" "$arch" \
      > "$OUT/logs/$f.$tool.compress.log" 2>&1 || { echo "COMPRESS-FAIL $f/$tool"; return 1; }
  fi
  [ -s "$arch" ] || { echo "COMPRESS-EMPTY $f/$tool"; return 1; }
  local abytes; abytes=$(stat -c %s "$arch")

  # warmup decode (also the first round-trip gate)
  scoped taskset -c "$PIN" timeout "$dtimeout" bash -c "$dcmd" "$arch" "$back" \
    > "$OUT/logs/$f.$tool.warmup.log" 2>&1 || { echo "WARMUP-FAIL $f/$tool"; return 1; }

  for s in 1 2 3; do
    local tl="$OUT/logs/$f.$tool.timed.$s.log"
    rm -f "$back"
    scoped taskset -c "$PIN" /usr/bin/time -v timeout "$dtimeout" bash -c "$dcmd" "$arch" "$back" \
      > /dev/null 2>"$tl" || { echo "DECODE-FAIL $f/$tool/$s"; return 1; }
    # GATES first — no number is recorded for an unverified decode
    local cmpr shar verdict
    if cmp -s "$input" "$back"; then cmpr=PASS; else cmpr=FAIL; fi
    if [ "$(sha "$back")" = "$ref" ]; then shar=PASS; else shar=FAIL; fi
    if [ "$cmpr" = PASS ] && [ "$shar" = PASS ]; then verdict=OK; else verdict=VOID; fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$f" "$tool" "$setting" "$s" "$cmpr" "$shar" "$verdict" >> "$GATES"
    if [ "$verdict" != OK ]; then echo "GATE-VOID $f/$tool/$s"; return 1; fi
    read -r w r < <(wall_rss "$tl")
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$f" "$tool" "$setting" timed "$s" "$w" "$r" "$abytes" >> "$RES"
  done
  echo "[$(date -u +%T)] done $f/$tool/$setting  archive=$abytes"
}

FILES="${FILES:-dickens x-ray}"
for f in $FILES; do
  # competitors first: cheap, and they establish the same-host field window
  run_cell "$f" xz     "-9"    'xz -9 -T1 -c "$0" > "$1"'            'xz -d -T1 -c "$0" > "$1"'        xz    3600 600
  run_cell "$f" zstd   "-19"   'zstd -19 -T1 -q -o "$1" "$0"'        'zstd -d -q -o "$1" "$0"'         zst   3600 600
  run_cell "$f" brotli "-q11"  'brotli -q 11 -o "$1" "$0"'           'brotli -d -o "$1" "$0"'          br    3600 600
  run_cell "$f" gzip   "-9"    'gzip -9 -c "$0" > "$1"'              'gzip -d -c "$0" > "$1"'          gz     900 600
  run_cell "$f" bzip2  "-9"    'bzip2 -9 -c "$0" > "$1"'             'bzip2 -d -c "$0" > "$1"'         bz2    900 600
  run_cell "$f" lz4    "-12"   'lz4 -12 -q -f "$0" "$1"'             'lz4 -d -q -f "$0" "$1"'          lz4    900 600
  # cubrim last: by far the most expensive compress
  run_cell "$f" cubrim "max"   "$BIN"' compress --preset max --quiet "$0" "$1"' "$BIN"' decompress "$0" "$1"' cbr 21600 1800
done
echo "[$(date -u +%T)] ALL DONE"
