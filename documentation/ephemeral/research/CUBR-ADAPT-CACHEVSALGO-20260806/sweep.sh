#!/usr/bin/env bash
# CUBR archival: adaptation cache-vs-algorithm discriminator.
# For each (file, tbits): encode + byte-exact RT with the main binary under
# CUBRIM_CM2_TBITS, then a pinned profiled decode (rdtsc attribution) and a
# pinned perf-stat run for hardware cache/TLB counters.
set -euo pipefail
S=/tmp/claude-1002/-home-dev--worktrees-cubrim-CUBR-0087/06cc380e-beaa-4b5b-a463-aae4e36a0628/scratchpad
BIN=$S/main-96485d1/code/cubrim-rs/target/release/cubrim
PROF=$S/profiler-cbdae7d/code/cubrim-rs/target/release/cubrim-decode-profile
OUT=$S/adapt/out
mkdir -p "$OUT"
EVENTS=cycles,instructions,cache-references,cache-misses,LLC-loads,LLC-load-misses,dTLB-load-misses

for f in dickens nci; do
  for t in native 22 20 18 15 12; do
    if [ "$t" = native ]; then ENVV=(env -u CUBRIM_CM2_TBITS); else ENVV=(env CUBRIM_CM2_TBITS=$t); fi
    tag="$f.t$t"
    if [ ! -s "$OUT/$tag.cbr" ]; then
      "${ENVV[@]}" "$BIN" compress "$S/adapt/$f.2m" "$OUT/$tag.cbr" >/dev/null 2>&1
      "${ENVV[@]}" "$BIN" decompress "$OUT/$tag.cbr" "$OUT/$tag.back" >/dev/null 2>&1
      cmp "$S/adapt/$f.2m" "$OUT/$tag.back"
      rm -f "$OUT/$tag.back"
    fi
    comp=$(stat -c%s "$OUT/$tag.cbr")
    mode=$(python3 -c "print(open('$OUT/$tag.cbr','rb').read(6)[5])")
    echo "$tag comp=$comp mode=$mode RT=PASS"
    if [ "$mode" != 16 ]; then
      echo "$tag profile SKIPPED (outer mode $mode is not CM2 — competitive rail dropped CM2 at this cap)"
      continue
    fi
    if [ ! -s "$OUT/$tag.profile.json" ]; then
      "${ENVV[@]}" taskset --cpu-list 0 /usr/bin/time -v \
        "$PROF" --input "$OUT/$tag.cbr" --original "$S/adapt/$f.2m" \
        --output "$OUT/$tag.profile.json" --affinity fixed-core \
        2> "$OUT/$tag.time.txt"
    fi
    sudo -n taskset --cpu-list 0 perf stat -e "$EVENTS" -x, \
      -o "$OUT/$tag.perf.csv" -- \
      "${ENVV[@]}" "$PROF" --input "$OUT/$tag.cbr" --original "$S/adapt/$f.2m" \
      --output "$OUT/$tag.profile2.json" --affinity fixed-core >/dev/null 2>&1 || \
      echo "$tag perf FAILED (non-fatal)"
    sudo -n chown "$(id -u):$(id -g)" "$OUT/$tag.perf.csv" "$OUT/$tag.profile2.json" 2>/dev/null || true
  done
done
echo SWEEP-COMPLETE
