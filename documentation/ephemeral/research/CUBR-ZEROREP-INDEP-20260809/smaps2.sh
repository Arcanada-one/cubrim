#!/usr/bin/env bash
# Corrected smaps pass: per (cell,build) one unmeasured decode, sampling
# /proc/pid/smaps every 0.2s; keeps the snapshot with MAX total anon RSS
# (>=1 MiB mappings), plus a growth series and VmHWM. Round-trip verified.
set -euo pipefail

S=/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBR-0066/7f295241-d406-40aa-a094-be158f1008f8/scratchpad/zerorep
OUT=$S/out
IN=$S/input
SM=$OUT/smaps2
mkdir -p "$SM"

BASE=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-BASE/code/cubrim-rs/target/release/cubrim
CURRENT=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-CURRENT/code/cubrim-rs/target/release/cubrim
ZERO=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-ZERO/code/cubrim-rs/target/release/cubrim
PIN=0-15
export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1

CELLS='nci balanced
nci web
dickens max
dickens balanced
dickens web
ooffice max
ooffice balanced
ooffice web'

die() { echo "FATAL: $*" >&2; exit 1; }
bin_for() { case "$1" in base) echo "$BASE";; current) echo "$CURRENT";; zero) echo "$ZERO";; esac; }

sample_one() { # binary archive back prefix
  local binary=$1 archive=$2 back=$3 pref=$4
  taskset -c "$PIN" "$binary" decompress "$archive" "$back" >/dev/null 2>&1 &
  local pid=$!
  local best_rss=-1
  : > "$pref.series.txt"
  while kill -0 "$pid" 2>/dev/null; do
    local snap tot
    snap=$(awk '
      /^[0-9a-f]+-[0-9a-f]+ /{
        split($1,a,"-"); sz=(strtonum("0x" a[2])-strtonum("0x" a[1]))/1024;
        curanon=($6=="")?1:0; cur=sz; next }
      /^Rss:/{ if (curanon && cur>=1024) printf "%d %d\n", cur, $2 }
    ' /proc/$pid/smaps 2>/dev/null) || snap=""
    if [[ -n $snap ]]; then
      tot=$(awk '{s+=$1; r+=$2} END{printf "%d %d", s, r}' <<<"$snap")
      read -r tsize trss <<<"$tot"
      printf '%s %s %s\n' "$(date +%s.%N)" "$tsize" "$trss" >> "$pref.series.txt"
      if (( trss > best_rss )); then
        best_rss=$trss
        printf '%s\n' "$snap" > "$pref.peak-mappings.txt"
        printf '%s %s\n' "$tsize" "$trss" > "$pref.peak-totals.txt"
      fi
    fi
    h=$(awk '/VmHWM/{print $2}' /proc/$pid/status 2>/dev/null) && [[ -n $h ]] && echo "$h" > "$pref.vmhwm.txt"
    sleep 0.2
  done
  wait "$pid" || return 1
}

for f_p in $(echo "$CELLS" | tr ' ' '/'); do
  f=${f_p%/*}; p=${f_p#*/}
  for b in base current zero; do
    binary=$(bin_for "$b"); archive="$OUT/$f.$p.$b.cbr"; back="$SM/$f.$p.$b.back"; pref="$SM/$f.$p.$b"
    [[ -f $archive ]] || die "missing archive $archive"
    systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 -q bash -c "
      set -euo pipefail
      $(declare -f sample_one)
      PIN=$PIN
      sample_one '$binary' '$archive' '$back' '$pref'
    " || die "smaps2 decode $f/$p/$b"
    cmp -s "$IN/$f" "$back" || die "smaps2 roundtrip $f/$p/$b"
    rm -f "$back"
    echo "smaps2 done $f/$p/$b peak=$(cat "$pref.peak-totals.txt" 2>/dev/null || echo NA) vmhwm=$(cat "$pref.vmhwm.txt" 2>/dev/null || echo NA)"
  done
done
echo "=== SMAPS2 COMPLETE ==="
