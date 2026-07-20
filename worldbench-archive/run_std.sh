#!/usr/bin/env bash
# CUBR-0034 standard archivers runner.
set -u
ROOT=/home/dev/cubrim-worldbench
LZ4=$ROOT/lz4
OUT=$ROOT/results/std
mkdir -p "$OUT" "$ROOT/tmp/std"

resolve() { case "$1" in enwik8) echo "$ROOT/corpora/enwik8";; *) echo "$ROOT/corpora/$1/$2";; esac; }

# size of compressor stdout
csize() { # cmd... < file  -> bytes
  "$@" 2>/dev/null | wc -c
}

run_arch() {
  local corpus="$1" name="$2" type="$3"
  local f; f=$(resolve "$corpus" "$name")
  local sz; sz=$(stat -c%s "$f")
  local tag="${corpus}__${name}"
  declare -A R
  local t0 t1
  # gzip -9
  t0=$(date +%s.%N); R[gzip]=$(gzip -9 -c "$f" 2>/dev/null | wc -c); t1=$(date +%s.%N); local tg=$(echo "$t1-$t0"|bc)
  # bzip2 -9
  R[bzip2]=$(bzip2 -9 -c "$f" 2>/dev/null | wc -c)
  # xz -9e
  R[xz]=$(xz -9e -c -T1 "$f" 2>/dev/null | wc -c)
  # zstd --ultra -22
  R[zstd]=$(zstd --ultra -22 -c -q "$f" 2>/dev/null | wc -c)
  # brotli -q 11
  R[brotli]=$(brotli -q 11 -c "$f" 2>/dev/null | wc -c)
  # lz4 -12
  R[lz4]=$("$LZ4" -12 -c "$f" 2>/dev/null | wc -c)
  # 7z PPMd
  local a7="$ROOT/tmp/std/$tag.7z"; rm -f "$a7"
  7z a -m0=PPMd -mmem=256m -bso0 -bsp0 -bd "$a7" "$f" >/dev/null 2>&1
  R[ppmd]=$(stat -c%s "$a7" 2>/dev/null || echo null); rm -f "$a7"

  # emit json
  {
    printf '{"corpus":"%s","file":"%s","type":"%s","orig":%s' "$corpus" "$name" "$type" "$sz"
    for k in gzip bzip2 xz zstd brotli lz4 ppmd; do
      local c=${R[$k]}
      if [ -z "$c" ] || [ "$c" = "null" ] || [ "$c" = "0" ]; then
        printf ',"%s_comp":null,"%s_ratio":null' "$k" "$k"
      else
        printf ',"%s_comp":%s,"%s_ratio":0%s' "$k" "$c" "$k" "$(echo "scale=6;$c/$sz"|bc)"
      fi
    done
    printf '}\n'
  } > "$OUT/$tag.json"
  echo "[std] $tag done (gzip=${R[gzip]} xz=${R[xz]} zstd=${R[zstd]} brotli=${R[brotli]} ppmd=${R[ppmd]})"
}
export -f run_arch resolve csize
export ROOT LZ4 OUT

cat "$ROOT/manifest.tsv" | while IFS=$'\t' read -r c n t; do echo "$c|$n|$t"; done | \
  xargs -P 4 -I {} bash -c 'IFS="|" read -r c n t <<< "{}"; run_arch "$c" "$n" "$t"'
echo "ALL STD DONE"
