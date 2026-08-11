#!/usr/bin/env bash
# CUBR mandate item 1 — independent eight-cell zero-representation matrix
# replication + lazy-pages mechanism verification (smaps residency).
# Host: arcana-devs, user dev. Every cubrim run memory-capped:
#   systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0
set -euo pipefail

S=/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBR-0066/7f295241-d406-40aa-a094-be158f1008f8/scratchpad/zerorep
OUT=$S/out
IN=$S/input
mkdir -p "$OUT/timing_logs" "$OUT/smaps"

BASE=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-BASE/code/cubrim-rs/target/release/cubrim
CURRENT=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-CURRENT/code/cubrim-rs/target/release/cubrim
ZERO=/home/dev/.worktrees/cubrim/CUBR-M1-ZR-ZERO/code/cubrim-rs/target/release/cubrim
PIN=0-15
export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1

# file preset canonical-bytes canonical-sha
CELLS=(
 'nci balanced 108014 c812943fd63414bf4ec185ee048b6550cc6b1a0a523dd3a63afe242bdf133066'
 'nci web 108624 2caaa78101082ccfb753909440a60e7381f94210fd8817ac89ccc02d7b6d6848'
 'dickens max 461437 c8aed8ae4c39d8a463e3d2bcb3fd082ec955d60fd320bbeec41af7a65922285e'
 'dickens balanced 472253 25378abf1cbe18e016143c0f0401aac055db8fb1c2964e5a4525371ba400a5ad'
 'dickens web 487506 0f3677eeadf937facb8c3b3fd79d6fc04677f19e0b648b983dd732db8a92ba0f'
 'ooffice max 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be'
 'ooffice balanced 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be'
 'ooffice web 704087 a8e04efd9c890c8f72a645571ebfd230774e638e9bef7c3118d22a5fffeb0be4'
)

die() { echo "FATAL: $*" >&2; exit 1; }
sha() { sha256sum "$1" | awk '{print $1}'; }
bin_for() { case "$1" in base) echo "$BASE";; current) echo "$CURRENT";; zero) echo "$ZERO";; esac; }
scoped() { systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 -q "$@"; }

wall_rss() { # parse /usr/bin/time -v log -> "wall_seconds rss_kib"
  local log=$1 wall rss
  wall=$(awk -F': ' '/Elapsed \(wall clock\) time/ {print $2}' "$log" | awk -F: '{ if (NF==3) print $1*3600+$2*60+$3; else print $1*60+$2 }')
  rss=$(awk -F': ' '/Maximum resident set size/ {print $2}' "$log")
  [[ -n $wall && -n $rss ]] || return 1
  echo "$wall $rss"
}

sample_order() { case "$1" in 1) printf 'base\ncurrent\nzero\n';; 2) printf 'current\nzero\nbase\n';; 3) printf 'zero\nbase\ncurrent\n';; esac; }

# smaps sampler: launches decode in background inside this (already-scoped)
# shell, samples large anon mappings until exit, writes last snapshot + VmHWM.
smaps_decode() { # binary archive back outprefix
  local binary=$1 archive=$2 back=$3 pref=$4
  taskset -c "$PIN" "$binary" decompress "$archive" "$back" >/dev/null 2>&1 &
  local pid=$!
  local last=""
  local hwm=""
  while kill -0 "$pid" 2>/dev/null; do
    if snap=$(awk '
      /^[0-9a-f]+-[0-9a-f]+ /{
        split($1,a,"-"); sz=(strtonum("0x" a[2])-strtonum("0x" a[1]))/1024;
        anon=($6=="")?1:0; cur=sz; curanon=anon; next }
      /^Rss:/{ if (curanon && cur>=1024) printf "%d %d\n", cur, $2 }
    ' /proc/$pid/smaps 2>/dev/null); then
      [[ -n $snap ]] && last=$snap
    fi
    h=$(awk '/VmHWM/{print $2}' /proc/$pid/status 2>/dev/null) && [[ -n $h ]] && hwm=$h
    sleep 0.2
  done
  wait "$pid" || return 1
  printf '%s\n' "$last" > "$pref.mappings.txt"
  printf '%s\n' "${hwm:-NA}" > "$pref.vmhwm.txt"
}

echo "=== provenance ==="
for b in base current zero; do echo "$b binary sha256: $(sha "$(bin_for "$b")")"; done
for f in nci dickens ooffice; do echo "input $f sha256: $(sha "$IN/$f")"; done
uptime

printf 'cell\tphase\tsample\tbuild\twall_s\trss_kib\n' > "$OUT/results.tsv"
printf 'cell\tphase\tsample\tbuild\tstatus\n' > "$OUT/roundtrips.tsv"

for line in "${CELLS[@]}"; do
  read -r f p bytes sum <<<"$line"; cell="$f/$p"; input="$IN/$f"
  echo "=== cell $cell ==="
  # 1) compress with each build; verify sha256+bytes vs canonical, then pairwise cmp
  for b in base current zero; do
    binary=$(bin_for "$b"); archive="$OUT/$f.$p.$b.cbr"
    if [[ -f $archive && $(sha "$archive") == "$sum" ]]; then echo "compress $cell/$b: cached"; else
      scoped taskset -c "$PIN" timeout 1800 "$binary" compress --preset "$p" --quiet "$input" "$archive" || die "compress $cell/$b"
    fi
    [[ $(sha "$archive") == "$sum" ]] || die "archive sha256 $cell/$b"
    [[ $(stat -c %s "$archive") == "$bytes" ]] || die "archive bytes $cell/$b"
  done
  cmp -s "$OUT/$f.$p.base.cbr" "$OUT/$f.$p.current.cbr" || die "cmp base/current $cell"
  cmp -s "$OUT/$f.$p.base.cbr" "$OUT/$f.$p.zero.cbr" || die "cmp base/zero $cell"
  echo "archives identical + canonical sha256 OK: $cell"
  # 2) warmup decode + roundtrip per build
  for b in base current zero; do
    binary=$(bin_for "$b"); back="$OUT/$f.$p.$b.warm.back"
    scoped taskset -c "$PIN" timeout 300 "$binary" decompress "$OUT/$f.$p.$b.cbr" "$back" >/dev/null 2>&1 || die "warmup $cell/$b"
    cmp -s "$input" "$back" || die "warmup roundtrip $cell/$b"
    printf '%s\twarmup\t1\t%s\tPASS\n' "$cell" "$b" >> "$OUT/roundtrips.tsv"; rm -f "$back"
  done
  # 3) three timed samples, rotated build order
  for s in 1 2 3; do
    mapfile -t order < <(sample_order "$s")
    for b in "${order[@]}"; do
      binary=$(bin_for "$b"); back="$OUT/$f.$p.$b.t$s.back"; tl="$OUT/timing_logs/$f.$p.$b.timed.$s.log"
      scoped taskset -c "$PIN" /usr/bin/time -v timeout 300 "$binary" decompress "$OUT/$f.$p.$b.cbr" "$back" >/dev/null 2>"$tl" || die "decode $cell/$b/$s"
      cmp -s "$input" "$back" || die "roundtrip $cell/$b/$s"
      read -r wall rss < <(wall_rss "$tl") || die "time parse $cell/$b/$s"
      printf '%s\ttimed\t%s\t%s\t%s\t%s\n' "$cell" "$s" "$b" "$wall" "$rss" >> "$OUT/results.tsv"
      printf '%s\ttimed\t%s\t%s\tPASS\n' "$cell" "$s" "$b" >> "$OUT/roundtrips.tsv"; rm -f "$back"
    done
  done
  # 4) smaps mechanism run (unmeasured for timing; roundtrip still verified)
  for b in base current zero; do
    binary=$(bin_for "$b"); back="$OUT/$f.$p.$b.smaps.back"; pref="$OUT/smaps/$f.$p.$b"
    export -f smaps_decode
    scoped bash -c "
      set -euo pipefail
      $(declare -f smaps_decode)
      PIN=$PIN
      smaps_decode '$binary' '$OUT/$f.$p.$b.cbr' '$back' '$pref'
    " || die "smaps decode $cell/$b"
    cmp -s "$input" "$back" || die "smaps roundtrip $cell/$b"
    printf '%s\tsmaps\t1\t%s\tPASS\n' "$cell" "$b" >> "$OUT/roundtrips.tsv"; rm -f "$back"
  done
done

echo "=== ALL CELLS COMPLETE ==="
wc -l "$OUT/results.tsv" "$OUT/roundtrips.tsv"
