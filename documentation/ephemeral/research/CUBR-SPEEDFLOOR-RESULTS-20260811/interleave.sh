#!/usr/bin/env bash
# Same-window interleaved decode pass on dickens.
# The first pass measured competitors at ~17:07 (load ~10-16) and cubrim at ~17:45 (load ~24).
# Wall-clock across different load windows is not comparable, so this pass decodes EVERY tool
# back-to-back inside one round and repeats 3 rounds. Within a round all tools see the same
# host condition, so the tool-to-tool RATIO is defensible even though absolute MiB/s is not.
set -uo pipefail
SP="$(cd "$(dirname "$0")" && pwd)"
BIN=/home/dev/.worktrees/cubrim/CUBR-SPEEDFLOOR/code/cubrim-rs/target/release/cubrim
CORPUS=/home/dev/cubr-cubecore-research/corpus-silesia
OUT="$SP/out"; PIN=0-15
RES="$OUT/interleaved.tsv"
[ -f "$RES" ] || printf 'round\tfile\ttool\twall_s\tload1_before\tcmp\tsha256\tverdict\n' > "$RES"
scoped() { systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0 -q "$@"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

f=dickens
input="$CORPUS/$f"; ref=$(sha "$input")
declare -A DEC=(
  [xz]='xz -d -T1 -c "$0" > "$1"'
  [zstd]='zstd -d -q -o "$1" "$0"'
  [brotli]='brotli -d -o "$1" "$0"'
  [gzip]='gzip -d -c "$0" > "$1"'
  [bzip2]='bzip2 -d -c "$0" > "$1"'
  [lz4]='lz4 -d -q -f "$0" "$1"'
  [cubrim]="$BIN"' decompress "$0" "$1"'
)
declare -A EXT=([xz]=xz [zstd]=zst [brotli]=br [gzip]=gz [bzip2]=bz2 [lz4]=lz4 [cubrim]=cbr)

for round in 1 2 3; do
  for tool in cubrim xz zstd brotli gzip bzip2 lz4; do
    arch="$OUT/arch/$f.$tool.${EXT[$tool]}"; back="$OUT/back/$f.$tool.ilv"
    [ -s "$arch" ] || { echo "MISSING-ARCHIVE $tool"; continue; }
    l1=$(cut -d' ' -f1 /proc/loadavg)
    rm -f "$back"
    s=$(date +%s.%N)
    scoped taskset -c "$PIN" timeout 1800 bash -c "${DEC[$tool]}" "$arch" "$back" >/dev/null 2>&1
    rc=$?
    e=$(date +%s.%N)
    w=$(echo "$e - $s" | bc)
    if [ $rc -ne 0 ]; then echo "DECODE-FAIL $tool round $round"; continue; fi
    if cmp -s "$input" "$back"; then c=PASS; else c=FAIL; fi
    if [ "$(sha "$back")" = "$ref" ]; then h=PASS; else h=FAIL; fi
    v=VOID; [ "$c" = PASS ] && [ "$h" = PASS ] && v=OK
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$round" "$f" "$tool" "$w" "$l1" "$c" "$h" "$v" >> "$RES"
    echo "[$(date -u +%T)] r$round $tool ${w}s load1=$l1 $v"
    rm -f "$back"
  done
done
echo "INTERLEAVE DONE"
