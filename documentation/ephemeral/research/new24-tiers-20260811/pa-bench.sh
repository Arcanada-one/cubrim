#!/usr/bin/env bash
# NEW-24 P-A stand bench: decode wall, full vs tiered CM2 archives.
# Prereg: CUBR-NEW24-TIERS-20260809.md (P-A). Pin 16-19, quiet gate, campaign env.
# Inputs staged under /root/cubr-new24-pa/: {name}.cub archives + {name}.orig originals
# + manifest.tsv: name<TAB>archive_sha256<TAB>orig_sha256
set -u
ROOT=/root/cubr-new24-pa
BIN=$ROOT/cubrim-new24
JOURNAL=$ROOT/journal.jsonl
PIN="taskset -c 16-19"
export CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4
REPS=3
LOAD_MAX=8.0

jlog(){ printf '%s\n' "$1" >> "$JOURNAL"; }
now(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
quiet(){ local t=0; while :; do
  l=$(awk '{print $1}' /proc/loadavg)
  awk -v l="$l" -v m="$LOAD_MAX" 'BEGIN{exit !(l<m)}' && return 0
  t=$((t+1)); [ $t -gt 60 ] && return 1; sleep 60; done; }

jlog "{\"t\":\"$(now)\",\"event\":\"run_start\",\"binary_sha256\":\"$(sha256sum $BIN | cut -d' ' -f1)\",\"pin\":\"16-19\"}"
while IFS=$'\t' read -r name asha osha mem; do
  [ -z "$name" ] && continue
  cub=$ROOT/$name.cub; orig=$ROOT/$name.orig
  got=$(sha256sum "$cub" | cut -d' ' -f1)
  if [ "$got" != "$asha" ]; then jlog "{\"t\":\"$(now)\",\"cell\":\"$name\",\"event\":\"gate_fail\",\"gate\":\"archive-sha\"}"; continue; fi
  for i in $(seq 1 $REPS); do
    quiet || { jlog "{\"t\":\"$(now)\",\"cell\":\"$name\",\"event\":\"void\",\"reason\":\"never quiet\"}"; break; }
    rm -f $ROOT/r.bin
    t0=$(date +%s.%N)
    systemd-run --scope --quiet -p MemoryMax="$mem" -p MemorySwapMax=0 \
      $PIN "$BIN" decompress --quiet "$cub" $ROOT/r.bin > /dev/null 2> $ROOT/$name.$i.err
    rc=$?; t1=$(date +%s.%N)
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
    if [ $rc -ne 0 ] || ! cmp -s "$orig" $ROOT/r.bin; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$name\",\"event\":\"gate_fail\",\"gate\":\"rt\",\"rep\":$i,\"rc\":$rc}"; break
    fi
    rsha=$(sha256sum $ROOT/r.bin | cut -d' ' -f1)
    if [ "$rsha" != "$osha" ]; then jlog "{\"t\":\"$(now)\",\"cell\":\"$name\",\"event\":\"gate_fail\",\"gate\":\"rt-sha\",\"rep\":$i}"; break; fi
    jlog "{\"t\":\"$(now)\",\"cell\":\"$name\",\"event\":\"decode_ok\",\"rep\":$i,\"wall_s\":$wall}"
  done
done < $ROOT/manifest.tsv
jlog "{\"t\":\"$(now)\",\"event\":\"run_end\"}"
