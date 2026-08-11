set -u
BIN=/home/dev/.worktrees/cubrim/CUBR-REPRO-A/code/cubrim-rs/target/release/cubrim; ARCH=/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBR-0066/329ba9ea-bf85-479d-a0ae-061103fcbb18/scratchpad/clean/../xray/out/arch/x-ray.cubrim.cbr; IN=/home/dev/cubr-cubecore-research/corpus-silesia/x-ray; PIN=0-15
sha() { sha256sum "$1" | cut -d' ' -f1; }
ref=$(sha "$IN")
printf 'rung\tpair\tphase\twall_s\tload1\tgate\n' > timings2.tsv
for F in 25 10; do
  for s in $(seq 1 12); do
    l=$(cut -d' ' -f1 /proc/loadavg)
    st=$(date +%s.%N); taskset -c $PIN "$BIN" decompress "$ARCH" o.bin >/dev/null 2>&1; rc=$?
    en=$(date +%s.%N); g=VOID
    [ $rc -eq 0 ] && cmp -s "$IN" o.bin && [ "$(sha o.bin)" = "$ref" ] && g=OK
    printf 'F%s\t%s\tplain\t%s\t%s\t%s\n' "$F" "$s" "$(echo "$en - $st"|bc)" "$l" "$g" >> timings2.tsv; rm -f o.bin
    st=$(date +%s.%N)
    taskset -c $PIN perf record -q -F $F -o p.$F.$s.data -- "$BIN" decompress "$ARCH" o.bin >/dev/null 2>&1; rc=$?
    en=$(date +%s.%N); g=VOID
    [ $rc -eq 0 ] && cmp -s "$IN" o.bin && [ "$(sha o.bin)" = "$ref" ] && g=OK
    printf 'F%s\t%s\tperf\t%s\t%s\t%s\n' "$F" "$s" "$(echo "$en - $st"|bc)" "$l" "$g" >> timings2.tsv; rm -f o.bin
  done
  echo "rung F$F done"
done
echo CLEAN2-DONE
