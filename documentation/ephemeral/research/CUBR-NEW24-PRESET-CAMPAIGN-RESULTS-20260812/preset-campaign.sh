#!/usr/bin/env bash
# NEW-24 preset campaign runner. Prereg: CUBR-NEW24-PRESET-CAMPAIGN-20260811.md
# (main 563b94e). Runs detached on dev-ai. Journal-first; resumable (skips
# cells already marked cell_done). Voids to journal, never the DB.
set -u
ROOT=/root/cubr-new24-preset
BIN=$ROOT/cubrim-main
CORPUS=/root/corpus-full
MANIFEST=/root/phaseC/corpus_manifest.tsv
CANON=$ROOT/canonical-archives.tsv   # corpus<TAB>file<TAB>archive_sha256 from phaseC journal.max.jsonl
J=$ROOT/journal.jsonl
LOAD_MAX=8.0
export CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4
mkdir -p $ROOT/work

now(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
jlog(){ printf '%s\n' "$1" >> "$J"; }
sha(){ sha256sum "$1" | cut -d' ' -f1; }
quiet(){ local t=0; while :; do
  l=$(awk '{print $1}' /proc/loadavg)
  awk -v l="$l" -v m="$LOAD_MAX" 'BEGIN{exit !(l<m)}' && return 0
  t=$((t+1)); [ $t -gt 90 ] && return 1; sleep 60; done; }
done_already(){ grep -q "\"cell\":\"$1\",\"event\":\"cell_done\"" "$J" 2>/dev/null; }

run_arm(){ # corpus file arm mem tier_env...  -> encodes, gates, decodes x3
  local corpus=$1 file=$2 arm=$3 mem=$4; shift 4
  local cell="$file/$arm"
  done_already "$cell" && return 0
  local src=$CORPUS/$corpus/$file
  [ -f "$src" ] || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"void\",\"reason\":\"source missing\"}"; return 1; }
  local osha; osha=$(awk -F'\t' -v c="$corpus" -v f="$file" '$1==c&&$2==f{print $5}' "$MANIFEST")
  local orig;  orig=$(awk -F'\t' -v c="$corpus" -v f="$file" '$1==c&&$2==f{print $4}' "$MANIFEST")
  local etmo=$(( orig / 7000 + 600 ))   # ~3x at 0.02 MiB/s, floor 10 min
  local dtmo=$(( orig / 24000 + 300 ))  # ~3x at 0.07 MiB/s, floor 5 min
  local cub=$ROOT/work/$file.$arm.cub
  quiet || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"void\",\"reason\":\"never quiet\"}"; return 1; }
  jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"encode_start\"}"
  local e0=$(date +%s)
  env "$@" timeout ${etmo}s systemd-run --scope --quiet -p MemoryMax=14G -p MemorySwapMax=0 \
    nice -n 10 "$BIN" compress --preset max --quiet "$src" "$cub" > $ROOT/work/$file.$arm.enc.out 2> $ROOT/work/$file.$arm.enc.err
  local rc=$?; local e1=$(date +%s)
  [ $rc -ne 0 ] && { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"void\",\"reason\":\"encode rc=$rc\"}"; return 1; }
  local asha; asha=$(sha "$cub"); local abytes; abytes=$(stat -c%s "$cub")
  # control-arm canonical identity gate
  if [ "$arm" = full ]; then
    local want; want=$(awk -F'\t' -v c="$corpus" -v f="$file" '$1==c&&$2==f{print $3}' "$CANON")
    if [ -n "$want" ] && [ "$asha" != "$want" ]; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"gate_fail\",\"gate\":\"canonical\",\"got\":\"$asha\",\"want\":\"$want\"}"
      return 1
    fi
  fi
  jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"encoded\",\"bytes\":$abytes,\"sha\":\"$asha\",\"enc_s\":$((e1-e0))}"
  local i
  for i in 1 2 3; do
    quiet || { jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"void\",\"reason\":\"never quiet dec$i\"}"; return 1; }
    rm -f $ROOT/work/r.bin
    local t0=$(date +%s.%N)
    timeout ${dtmo}s systemd-run --scope --quiet -p MemoryMax=$mem -p MemorySwapMax=0 \
      /usr/bin/time -v -o $ROOT/work/$file.$arm.d$i.time \
      "$BIN" decompress --quiet "$cub" $ROOT/work/r.bin > /dev/null 2> $ROOT/work/$file.$arm.d$i.err
    rc=$?; local t1=$(date +%s.%N)
    local wall; wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
    if [ $rc -ne 0 ] || ! cmp -s "$src" $ROOT/work/r.bin || [ "$(sha $ROOT/work/r.bin)" != "$osha" ]; then
      jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"gate_fail\",\"gate\":\"rt\",\"rep\":$i,\"rc\":$rc}"; return 1
    fi
    local rss; rss=$(grep -oP 'Maximum resident set size \(kbytes\): \K[0-9]+' $ROOT/work/$file.$arm.d$i.time)
    jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"decode_ok\",\"rep\":$i,\"wall_s\":$wall,\"rss_kib\":$rss}"
  done
  rm -f $ROOT/work/r.bin
  [ "$arm" != full ] && rm -f "$cub"   # keep only control archives (disk)
  jlog "{\"t\":\"$(now)\",\"cell\":\"$cell\",\"event\":\"cell_done\"}"
}

jlog "{\"t\":\"$(now)\",\"event\":\"run_start\",\"binary_sha256\":\"$(sha $BIN)\",\"convention\":\"phaseC-timing-unpinned-quiet\",\"prereg\":\"563b94e\"}"
while IFS=$'\t' read -r corpus file type orig osha; do
  [ "$corpus" = corpus ] && continue
  [ -z "$corpus" ] && continue
  run_arm "$corpus" "$file" full 14G CUBR_DUMMY=
  run_arm "$corpus" "$file" f12  8G  CUBR_CM2_TIER=f12 CUBR_CM2_TIER_FORCE=1
  case "$file" in nci|osdb) run_arm "$corpus" "$file" m8s 8G CUBR_CM2_TIER=m8s CUBR_CM2_TIER_FORCE=1;; esac
done < "$MANIFEST"
jlog "{\"t\":\"$(now)\",\"event\":\"run_end\"}"
