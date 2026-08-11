set -u
BIN=/home/dev/.worktrees/cubrim/CUBR-REPRO-A/code/cubrim-rs/target/release/cubrim; ARCH=/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBR-0066/329ba9ea-bf85-479d-a0ae-061103fcbb18/scratchpad/xray/out/arch/x-ray.cubrim.cbr; IN=/home/dev/cubr-cubecore-research/corpus-silesia/x-ray; PIN=0-15
sha() { sha256sum "$1" | cut -d' ' -f1; }
ref=$(sha "$IN")
printf 'phase\tsample\twall_s\tgate\n' > timings.tsv
for s in 1 2 3; do
  st=$(date +%s.%N); taskset -c $PIN "$BIN" decompress "$ARCH" out.bin >/dev/null 2>&1; rc=$?
  en=$(date +%s.%N)
  g=VOID; [ $rc -eq 0 ] && cmp -s "$IN" out.bin && [ "$(sha out.bin)" = "$ref" ] && g=OK
  printf 'plain\t%s\t%s\t%s\n' "$s" "$(echo "$en - $st" | bc)" "$g" >> timings.tsv
  rm -f out.bin
done
for s in 1 2 3; do
  st=$(date +%s.%N)
  taskset -c $PIN perf record -q -F 99 -o perf.$s.data -- "$BIN" decompress "$ARCH" out.bin >/dev/null 2>&1; rc=$?
  en=$(date +%s.%N)
  g=VOID; [ $rc -eq 0 ] && cmp -s "$IN" out.bin && [ "$(sha out.bin)" = "$ref" ] && g=OK
  printf 'perf\t%s\t%s\t%s\n' "$s" "$(echo "$en - $st" | bc)" "$g" >> timings.tsv
  rm -f out.bin
done
echo ATTRIB-DONE
