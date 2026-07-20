#!/usr/bin/env bash
# CUBR-0041 oracle sweep — every world-corpus file x every value-scheme (all 12)
# plus `auto` (default = bitpack-fixed) for provenance. RT-verified per measurement.
# Emits TSV: scheme<TAB>file<TAB>orig<TAB>comp<TAB>ratio<TAB>rt_ok<TAB>ms
# NEVER fabricate a ratio: compress crash -> comp=0,ratio=0,rt_ok=false;
# decompress crash -> real comp/ratio but rt_ok=false. rt_ok=false => number INVALID.
set -u
BIN=/root/cubrim-stand/cubrim-rs/target/release/cubrim
CORPUS_DIR=/root/corpus
WORK_DIR=/root/cubr0041/work
LOG_DIR=/root/cubr0041/logs
OUT_TSV=/root/cubr0041/oracle.tsv
CRASH_LOG=/root/cubr0041/crashes.log
JOBLIST=/root/cubr0041/joblist.txt
CORES=$(nproc)
TIMEOUT_SMALL=600
TIMEOUT_LARGE=7200

SCHEMES="auto bitpack-fixed rle-codes entropy entropy-context entropy-context-2 bwt-entropy bwt-rans order2-rans bwt-adaptive bwt-ctxmix bwt-geomix lz-rans"

mkdir -p "$WORK_DIR" "$LOG_DIR"
: > "$CRASH_LOG"; : > "$JOBLIST"; : > "$OUT_TSV"

mapfile -t FILES < <(cd "$CORPUS_DIR" && find . -type f | sed 's#^\./##' | sort)
echo "[oracle] ${#FILES[@]} files x $(echo $SCHEMES | wc -w) schemes on $CORES cores" >&2
for f in "${FILES[@]}"; do for s in $SCHEMES; do echo "${f}|${s}" >> "$JOBLIST"; done; done

run_one() {
  local pair="$1"
  local relfile="${pair%%|*}"
  local scheme="${pair##*|}"
  local infile="$CORPUS_DIR/$relfile"
  local safe_name; safe_name=$(echo "$relfile" | tr '/.' '__')
  local tag="${scheme}__${safe_name}"
  local comp="$WORK_DIR/${tag}.cm"
  local decomp="$WORK_DIR/${tag}.out"
  local orig_bytes; orig_bytes=$(stat -c%s "$infile" 2>/dev/null || echo 0)
  if [ "$orig_bytes" -eq 0 ]; then
    printf '%s\t%s\t0\t0\t0\tfalse\t0\n' "$scheme" "$relfile"; return
  fi
  local timeout_s=$TIMEOUT_SMALL
  [ "$orig_bytes" -ge 20000000 ] && timeout_s=$TIMEOUT_LARGE

  local t0 t1 c_ms
  t0=$(date +%s%N)
  if [ "$scheme" = "auto" ]; then
    timeout -k 5 "${timeout_s}s" "$BIN" compress "$infile" "$comp" >>"$LOG_DIR/${tag}.c.log" 2>&1
  else
    timeout -k 5 "${timeout_s}s" "$BIN" compress "$infile" "$comp" --value-scheme "$scheme" >>"$LOG_DIR/${tag}.c.log" 2>&1
  fi
  local c_rc=$?
  t1=$(date +%s%N); c_ms=$(( (t1 - t0) / 1000000 ))
  if [ $c_rc -ne 0 ] || [ ! -s "$comp" ]; then
    echo "[$tag] COMPRESS CRASH/TIMEOUT rc=$c_rc after ${c_ms}ms" >> "$CRASH_LOG"
    tail -n 4 "$LOG_DIR/${tag}.c.log" >> "$CRASH_LOG" 2>/dev/null
    printf '%s\t%s\t%s\t0\t0\tfalse\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$c_ms"
    rm -f "$comp" "$decomp"; return
  fi
  local comp_bytes; comp_bytes=$(stat -c%s "$comp" 2>/dev/null || echo 0)
  t0=$(date +%s%N)
  timeout -k 5 "${timeout_s}s" "$BIN" decompress "$comp" "$decomp" >>"$LOG_DIR/${tag}.d.log" 2>&1
  local d_rc=$?
  t1=$(date +%s%N)
  local d_ms=$(( (t1 - t0) / 1000000 )); local total_ms=$(( c_ms + d_ms ))
  local ratio; ratio=$(awk -v c="$comp_bytes" -v o="$orig_bytes" 'BEGIN{ if(o>0) printf "%.6f", c/o; else print "0" }')
  if [ $d_rc -ne 0 ] || [ ! -s "$decomp" ]; then
    echo "[$tag] DECOMPRESS CRASH/TIMEOUT rc=$d_rc after ${d_ms}ms" >> "$CRASH_LOG"
    printf '%s\t%s\t%s\t%s\t%s\tfalse\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$comp_bytes" "$ratio" "$total_ms"
    rm -f "$comp" "$decomp"; return
  fi
  local rt_ok=false
  cmp -s "$infile" "$decomp" && rt_ok=true || echo "[$tag] RT MISMATCH" >> "$CRASH_LOG"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$comp_bytes" "$ratio" "$rt_ok" "$total_ms"
  rm -f "$comp" "$decomp"
}
export -f run_one
export BIN CORPUS_DIR WORK_DIR LOG_DIR CRASH_LOG TIMEOUT_SMALL TIMEOUT_LARGE

# enwik8 (long pole) first so its heavy rANS jobs run alongside small files.
{ grep '^enwik8|' "$JOBLIST"; grep -v '^enwik8|' "$JOBLIST"; } \
  | xargs -P "$CORES" -I{} bash -c 'run_one "$@"' _ {} >> "$OUT_TSV"
echo "[oracle] DONE. rows=$(wc -l < "$OUT_TSV")  crashes=$(wc -l < "$CRASH_LOG")" >&2
