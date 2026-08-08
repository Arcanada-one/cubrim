#!/usr/bin/env bash
# Decode-RSS comparison preregistered in CUBR-LEVERS-PRESET-RSS-20260808.md.
set -euo pipefail

ROOT=/root/cubr-levers/preset-rss
INPUT_ROOT=/root/cubr-levers/bench
BASE=/root/cubr-levers/baseline-e70/code/cubrim-rs/target/release/cubrim
CAND=/root/cubr-levers/code/cubrim-rs/target/release/cubrim
PIN=0-15
BASE_SHA=a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd
CAND_SHA=12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c
export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1

if [[ -e "$ROOT" ]]; then
  echo "REFUSED: output root already exists: $ROOT" >&2
  exit 2
fi
mkdir -p "$ROOT"
LOG=$ROOT/preset-rss.log
TSV=$ROOT/preset-rss.tsv
DONE=$ROOT/DONE.STAMP

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 3; }
actual_sha() { sha256sum "$1" | cut -d ' ' -f1; }
verify_sha() {
  local path=$1 expected=$2
  [[ "$(actual_sha "$path")" == "$expected" ]] || fail "sha256 mismatch: $path"
}
wall_rss() {
  python3 - "$1" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
wall = re.search(r"Elapsed \(wall clock\).*?: (.+)", text).group(1).strip()
parts = [float(value) for value in wall.split(":")]
seconds = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
rss = re.search(r"Maximum resident set size.*?: (\d+)", text).group(1)
print(f"{seconds:.2f}\t{rss}")
PY
}

verify_sha "$BASE" "$BASE_SHA"
verify_sha "$CAND" "$CAND_SHA"
verify_sha "$INPUT_ROOT/dickens.2m" df925056e0779c51cb2a27c014e8fc6d25d28ef2fac5b8ce4632d93b86860603
verify_sha "$INPUT_ROOT/nci.2m" 6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e
verify_sha "$INPUT_ROOT/ooffice.2m" 5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09

load1=$(cut -d ' ' -f1 /proc/loadavg)
python3 -c "import sys; sys.exit(0 if float('$load1') < 2.0 else 1)" \
  || fail "admission loadavg $load1 is not below 2.0"
if pgrep -x cubrim >/dev/null || pgrep -x cubrim-l1v2 >/dev/null || pgrep -x cubrim-sweep >/dev/null; then
  fail "foreign Cubrim process present"
fi
log "admission loadavg=$load1 pin=$PIN threads=4"
cat /proc/loadavg >> "$LOG"
ps aux --sort=-%cpu | sed -n '1,10p' >> "$LOG"

printf 'file\tpreset\tbuild\tsample\tarchive_sha256\tcomp_bytes\tdec_s\tdec_rss_kib\trt\n' > "$TSV"

for preset in max balanced web; do
  for file in dickens nci ooffice; do
    input=$INPUT_ROOT/$file.2m
    for build in base cand; do
      if [[ "$build" == base ]]; then binary=$BASE; else binary=$CAND; fi
      archive=$ROOT/$file.$preset.$build.cbr
      back=$ROOT/$file.$preset.$build.warm.back
      timeout 1800 taskset -c "$PIN" "$binary" compress --preset "$preset" --quiet "$input" "$archive"
      timeout 300 taskset -c "$PIN" "$binary" decompress "$archive" "$back" >/dev/null
      cmp -s "$input" "$back" || fail "warmup round-trip $file $preset $build"
      rm -f "$back"
    done

    base_archive=$ROOT/$file.$preset.base.cbr
    cand_archive=$ROOT/$file.$preset.cand.cbr
    cmp -s "$base_archive" "$cand_archive" || fail "archive identity $file $preset"
    archive_sha=$(actual_sha "$base_archive")
    comp_bytes=$(stat -c %s "$base_archive")
    log "$file $preset archive_identity=PASS sha256=$archive_sha bytes=$comp_bytes"

    for sample in 1 2 3; do
      for build in base cand; do
        if [[ "$build" == base ]]; then binary=$BASE; archive=$base_archive; else binary=$CAND; archive=$cand_archive; fi
        back=$ROOT/$file.$preset.$build.s$sample.back
        timing=$ROOT/time.tmp
        taskset -c "$PIN" /usr/bin/time -v timeout 300 "$binary" decompress "$archive" "$back" \
          >/dev/null 2> "$timing"
        read -r dec_s dec_rss <<< "$(wall_rss "$timing")"
        rt=FAIL
        cmp -s "$input" "$back" && rt=PASS
        [[ "$rt" == PASS ]] || fail "measured round-trip $file $preset $build sample=$sample"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
          "$file" "$preset" "$build" "$sample" "$archive_sha" "$comp_bytes" "$dec_s" "$dec_rss" "$rt" \
          | tee -a "$TSV" >> "$LOG"
        rm -f "$back"
      done
    done
  done
done

log "post-run $(cat /proc/loadavg)"
ps aux --sort=-%cpu | sed -n '1,10p' >> "$LOG"
date -u +%Y-%m-%dT%H:%M:%SZ > "$DONE"
log "PRESET-RSS-COMPLETE"
