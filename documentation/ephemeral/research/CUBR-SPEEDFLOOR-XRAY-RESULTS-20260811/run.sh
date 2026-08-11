#!/usr/bin/env bash
# CUBR-SPEEDFLOOR-XML-20260811 — xml/max decode throughput, cubrim vs field, one host, pin 0-15.
# Interleaved by default: every tool decoded back-to-back within a round, 3 rounds.
# Gates: cmp AND sha256 vs the original before any timing row is written.
set -uo pipefail
SP="$(cd "$(dirname "$0")" && pwd)"
BIN=/home/dev/.worktrees/cubrim/CUBR-REPRO-A/code/cubrim-rs/target/release/cubrim
CORPUS=/home/dev/cubr-cubecore-research/corpus-silesia
OUT="$SP/out"; PIN=0-15; F=x-ray
mkdir -p "$OUT/arch" "$OUT/back" "$OUT/logs"
RES="$OUT/interleaved.tsv"; GATES="$OUT/gates.tsv"; META="$OUT/archives.tsv"
[ -f "$RES" ]   || printf 'round\tfile\ttool\twall_s\tload1_before\trss_kib\n' > "$RES"
[ -f "$GATES" ] || printf 'round\tfile\ttool\tcmp\tsha256\tverdict\n' > "$GATES"
[ -f "$META" ]  || printf 'file\ttool\tsetting\tarchive_bytes\tratio\tarchive_sha256\n' > "$META"

scoped() { systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0 -q "$@"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
input="$CORPUS/$F"; ref=$(sha "$input"); nbytes=$(stat -c %s "$input")

declare -A CMP=(
  [xz]='xz -9 -T1 -c "$0" > "$1"'            [zstd]='zstd -19 -T1 -q -o "$1" "$0"'
  [brotli]='brotli -q 11 -o "$1" "$0"'       [gzip]='gzip -9 -c "$0" > "$1"'
  [bzip2]='bzip2 -9 -c "$0" > "$1"'          [lz4]='lz4 -12 -q -f "$0" "$1"'
  [cubrim]="$BIN"' compress --preset max --quiet "$0" "$1"')
declare -A DEC=(
  [xz]='xz -d -T1 -c "$0" > "$1"'            [zstd]='zstd -d -q -o "$1" "$0"'
  [brotli]='brotli -d -o "$1" "$0"'          [gzip]='gzip -d -c "$0" > "$1"'
  [bzip2]='bzip2 -d -c "$0" > "$1"'          [lz4]='lz4 -d -q -f "$0" "$1"'
  [cubrim]="$BIN"' decompress "$0" "$1"')
declare -A EXT=([xz]=xz [zstd]=zst [brotli]=br [gzip]=gz [bzip2]=bz2 [lz4]=lz4 [cubrim]=cbr)
declare -A SET=([xz]=-9 [zstd]=-19 [brotli]=-q11 [gzip]=-9 [bzip2]=-9 [lz4]=-12 [cubrim]=max)
TOOLS="cubrim xz zstd brotli gzip bzip2 lz4"

loadlog() { while :; do echo "$(date -u +%FT%TZ) $(cut -d' ' -f1-3 /proc/loadavg)"; sleep 30; done; }
loadlog > "$OUT/loadlog.txt" & LP=$!; trap 'kill $LP 2>/dev/null' EXIT

# ---- compress once per tool (duration is NOT a measured quantity in this lane) ----
for t in $TOOLS; do
  arch="$OUT/arch/$F.$t.${EXT[$t]}"
  if [ ! -s "$arch" ]; then
    echo "[$(date -u +%T)] compress $t"
    scoped taskset -c "$PIN" timeout 21600 bash -c "${CMP[$t]}" "$input" "$arch" \
      > "$OUT/logs/$F.$t.compress.log" 2>&1 || { echo "COMPRESS-FAIL $t"; exit 1; }
  fi
  [ -s "$arch" ] || { echo "COMPRESS-EMPTY $t"; exit 1; }
  ab=$(stat -c %s "$arch")
  grep -q "^$F	$t	" "$META" 2>/dev/null || \
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$F" "$t" "${SET[$t]}" "$ab" \
      "$(python3 -c "print(f'{$ab/$nbytes:.6f}')")" "$(sha "$arch")" >> "$META"
done
echo "[$(date -u +%T)] all archives ready"

# ---- interleaved decode rounds ----
for round in 1 2 3; do
  for t in $TOOLS; do
    arch="$OUT/arch/$F.$t.${EXT[$t]}"; back="$OUT/back/$F.$t.out"
    l1=$(cut -d' ' -f1 /proc/loadavg); rm -f "$back"
    tl="$OUT/logs/$F.$t.r$round.time"
    scoped taskset -c "$PIN" /usr/bin/time -v timeout 1800 bash -c "${DEC[$t]}" "$arch" "$back" \
      >/dev/null 2>"$tl" || { echo "DECODE-FAIL $t r$round"; exit 1; }
    if cmp -s "$input" "$back"; then c=PASS; else c=FAIL; fi
    if [ "$(sha "$back")" = "$ref" ]; then h=PASS; else h=FAIL; fi
    v=VOID; [ "$c" = PASS ] && [ "$h" = PASS ] && v=OK
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$round" "$F" "$t" "$c" "$h" "$v" >> "$GATES"
    [ "$v" = OK ] || { echo "GATE-VOID $t r$round"; exit 1; }
    w=$(awk -F': ' '/Elapsed \(wall clock\)/ {print $2}' "$tl" | awk -F: '{if(NF==3)print $1*3600+$2*60+$3; else print $1*60+$2}')
    r=$(awk -F': ' '/Maximum resident set size/ {print $2}' "$tl")
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$round" "$F" "$t" "$w" "$l1" "$r" >> "$RES"
    echo "[$(date -u +%T)] r$round $t ${w}s load1=$l1 OK"
    rm -f "$back"
  done
done
echo "XML DONE"
