set -u
BIN=/home/dev/.worktrees/cubrim/CUBR-REPRO-A/code/cubrim-rs/target/release/cubrim; IN=/home/dev/cubr-cubecore-research/corpus-silesia/x-ray; CBR=/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBR-0066/329ba9ea-bf85-479d-a0ae-061103fcbb18/scratchpad/xray/out/arch/x-ray.cubrim.cbr; PIN=0-15
sha() { sha256sum "$1" | cut -d' ' -f1; }
ref=$(sha "$IN")
scoped() { systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0 -q "$@"; }
printf 'round\ttool\twall_s\tload1\tcmp\tsha256\tverdict\n' > results.tsv
for r in 1 2 3; do
 for t in ppmd bzip2 cubrim; do
  l=$(cut -d' ' -f1 /proc/loadavg); rm -f o.bin
  st=$(date +%s.%N)
  case $t in
   ppmd)   scoped taskset -c $PIN 7z e -so xr.7z > o.bin 2>/dev/null ;;
   bzip2)  scoped taskset -c $PIN bash -c 'bzip2 -d -c xr.bz2 > o.bin' ;;
   cubrim) scoped taskset -c $PIN "$BIN" decompress "$CBR" o.bin >/dev/null 2>&1 ;;
  esac
  rc=$?; en=$(date +%s.%N)
  c=FAIL; h=FAIL
  cmp -s "$IN" o.bin && c=PASS
  [ "$(sha o.bin 2>/dev/null)" = "$ref" ] && h=PASS
  v=VOID; [ $rc -eq 0 ] && [ "$c" = PASS ] && [ "$h" = PASS ] && v=OK
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$r" "$t" "$(echo "$en - $st"|bc)" "$l" "$c" "$h" "$v" >> results.tsv
  echo "[$(date -u +%T)] r$r $t $v"
  rm -f o.bin
 done
done
echo FIELD-DONE
