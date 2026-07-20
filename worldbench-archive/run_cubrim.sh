#!/usr/bin/env bash
# CUBR-0034 cubrim runner — per-file compress+RT, parallel over files.
set -u
CUB=/home/dev/cubrim-h19/code/cubrim-rs/target/release/cubrim
ROOT=/home/dev/cubrim-worldbench
OUT=$ROOT/results/cubrim
mkdir -p "$OUT" "$ROOT/tmp/cub"

resolve() { # corpus name -> path
  case "$1" in
    enwik8) echo "$ROOT/corpora/enwik8";;
    *)      echo "$ROOT/corpora/$1/$2";;
  esac
}

one() {
  local corpus="$1" name="$2" type="$3"
  local f; f=$(resolve "$corpus" "$name")
  local tag="${corpus}__${name}"
  local cz="$ROOT/tmp/cub/$tag.cub" dz="$ROOT/tmp/cub/$tag.out"
  local sz; sz=$(stat -c%s "$f")
  local t0 t1 t2 csz rt rc
  t0=$(date +%s.%N)
  "$CUB" compress "$f" "$cz" >/dev/null 2>"$OUT/$tag.err"; rc=$?
  t1=$(date +%s.%N)
  if [ $rc -ne 0 ]; then
    echo "{\"corpus\":\"$corpus\",\"file\":\"$name\",\"type\":\"$type\",\"orig\":$sz,\"comp\":null,\"ratio\":null,\"rt\":\"COMPRESS_FAIL\",\"comp_s\":null,\"decomp_s\":null}" > "$OUT/$tag.json"
    return
  fi
  csz=$(stat -c%s "$cz")
  "$CUB" decompress "$cz" "$dz" >/dev/null 2>>"$OUT/$tag.err"
  t2=$(date +%s.%N)
  if cmp -s "$f" "$dz"; then rt=OK; else rt=FAIL; fi
  local ratio comp_s decomp_s
  ratio=$(echo "scale=6;$csz/$sz"|bc)
  comp_s=$(echo "$t1-$t0"|bc)
  decomp_s=$(echo "$t2-$t1"|bc)
  echo "{\"corpus\":\"$corpus\",\"file\":\"$name\",\"type\":\"$type\",\"orig\":$sz,\"comp\":$csz,\"ratio\":0$ratio,\"rt\":\"$rt\",\"comp_s\":$comp_s,\"decomp_s\":$decomp_s}" > "$OUT/$tag.json"
  rm -f "$dz" "$cz"
  echo "[cubrim] $tag done ratio=0$ratio rt=$rt comp=${comp_s}s"
}
export -f one resolve
export CUB ROOT OUT

# Run in parallel, 8 at a time (single-threaded cubrim, 12 cores)
cat "$ROOT/manifest.tsv" | while IFS=$'\t' read -r c n t; do echo "$c|$n|$t"; done | \
  xargs -P 8 -I {} bash -c 'IFS="|" read -r c n t <<< "{}"; one "$c" "$n" "$t"'
echo "ALL CUBRIM DONE"
