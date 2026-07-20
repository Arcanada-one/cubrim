#!/usr/bin/env bash
# CUBR-0034 re-validation — cubrim CHAMPION rail (--value-scheme bwt-rans), captures top-level mode byte.
set -u
CUB=/home/dev/cubrim-h19/code/cubrim-rs/target/release/cubrim
ROOT=/home/dev/cubrim-worldbench
OUT=$ROOT/results/cubrim_champ
mkdir -p "$OUT" "$ROOT/tmp/cubchamp"
resolve() { case "$1" in enwik8) echo "$ROOT/corpora/enwik8";; *) echo "$ROOT/corpora/$1/$2";; esac; }
# mode names by byte5
modename() { case "$1" in 0) echo CUBE;; 1) echo RAW;; 2) echo CHUNKED;; 3) echo LZ;; 4) echo COLUMNAR;; *) echo "UNK$1";; esac; }

one() {
  local corpus="$1" name="$2" type="$3"
  local f; f=$(resolve "$corpus" "$name")
  local tag="${corpus}__${name}"
  local cz="$ROOT/tmp/cubchamp/$tag.cub" dz="$ROOT/tmp/cubchamp/$tag.out"
  local sz; sz=$(stat -c%s "$f")
  local t0 t1 csz rt rc mode modn
  t0=$(date +%s.%N)
  "$CUB" compress "$f" "$cz" --value-scheme bwt-rans >/dev/null 2>"$OUT/$tag.err"; rc=$?
  t1=$(date +%s.%N)
  if [ $rc -ne 0 ]; then
    echo "{\"corpus\":\"$corpus\",\"file\":\"$name\",\"type\":\"$type\",\"orig\":$sz,\"comp\":null,\"ratio\":null,\"rt\":\"COMPRESS_FAIL\",\"mode\":null,\"comp_s\":null}" > "$OUT/$tag.json"
    return
  fi
  csz=$(stat -c%s "$cz")
  mode=$(od -An -tu1 -j5 -N1 "$cz" | tr -d ' ')
  modn=$(modename "$mode")
  "$CUB" decompress "$cz" "$dz" >/dev/null 2>>"$OUT/$tag.err"
  if cmp -s "$f" "$dz"; then rt=OK; else rt=FAIL; fi
  local ratio comp_s
  ratio=$(echo "scale=6;$csz/$sz"|bc); comp_s=$(echo "$t1-$t0"|bc)
  echo "{\"corpus\":\"$corpus\",\"file\":\"$name\",\"type\":\"$type\",\"orig\":$sz,\"comp\":$csz,\"ratio\":0$ratio,\"rt\":\"$rt\",\"mode\":$mode,\"mode_name\":\"$modn\",\"comp_s\":$comp_s}" > "$OUT/$tag.json"
  rm -f "$dz" "$cz"
  echo "[champ] $tag ratio=0$ratio mode=$modn rt=$rt"
}
export -f one resolve modename
export CUB ROOT OUT
cat "$ROOT/manifest.tsv" | while IFS=$'\t' read -r c n t; do echo "$c|$n|$t"; done | \
  xargs -P 8 -I {} bash -c 'IFS="|" read -r c n t <<< "{}"; one "$c" "$n" "$t"'
echo "ALL CHAMP DONE"
