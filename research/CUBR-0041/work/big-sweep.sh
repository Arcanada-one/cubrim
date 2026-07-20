#!/usr/bin/env bash
# CUBR-0041 big-file sweep — the 7 files >64KB, all 13 schemes, RT-verified.
# cubrim compress is internally block-parallel (~8MB blocks => ~6-12 threads/job),
# so outer -P must stay LOW (4) to avoid the load-960 thrash that killed run 1.
# Appends to the SAME oracle.tsv that already holds the 5 small canterbury files.
set -u
BIN=/root/cubrim-stand/cubrim-rs/target/release/cubrim
CORPUS_DIR=/root/corpus
WORK_DIR=/root/cubr0041/work
LOG_DIR=/root/cubr0041/logs
OUT_TSV=/root/cubr0041/oracle.tsv
CRASH_LOG=/root/cubr0041/crashes.log
JOBLIST=/root/cubr0041/big-joblist.txt
POUTER=4
TIMEOUT_S=3600

BIGFILES="dickens mr x-ray silesia/mozilla silesia/samba silesia/webster enwik8"
SCHEMES="auto bitpack-fixed rle-codes entropy entropy-context entropy-context-2 bwt-entropy bwt-rans order2-rans bwt-adaptive bwt-ctxmix bwt-geomix lz-rans"

mkdir -p "$WORK_DIR" "$LOG_DIR"; : > "$JOBLIST"
for f in $BIGFILES; do for s in $SCHEMES; do echo "${f}|${s}" >> "$JOBLIST"; done; done

run_one() {
  local pair="$1"; local relfile="${pair%%|*}"; local scheme="${pair##*|}"
  local infile="$CORPUS_DIR/$relfile"
  local safe_name; safe_name=$(echo "$relfile" | tr '/.' '__')
  local tag="${scheme}__${safe_name}"
  local comp="$WORK_DIR/${tag}.cm"; local decomp="$WORK_DIR/${tag}.out"
  local orig_bytes; orig_bytes=$(stat -c%s "$infile" 2>/dev/null || echo 0)
  local t0 t1 c_ms
  t0=$(date +%s%N)
  if [ "$scheme" = "auto" ]; then
    timeout -k 5 "${TIMEOUT_S}s" "$BIN" compress "$infile" "$comp" >>"$LOG_DIR/${tag}.c.log" 2>&1
  else
    timeout -k 5 "${TIMEOUT_S}s" "$BIN" compress "$infile" "$comp" --value-scheme "$scheme" >>"$LOG_DIR/${tag}.c.log" 2>&1
  fi
  local c_rc=$?; t1=$(date +%s%N); c_ms=$(( (t1-t0)/1000000 ))
  if [ $c_rc -ne 0 ] || [ ! -s "$comp" ]; then
    echo "[$tag] COMPRESS CRASH/TIMEOUT rc=$c_rc after ${c_ms}ms" >> "$CRASH_LOG"
    tail -n 4 "$LOG_DIR/${tag}.c.log" >> "$CRASH_LOG" 2>/dev/null
    printf '%s\t%s\t%s\t0\t0\tfalse\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$c_ms"
    rm -f "$comp" "$decomp"; return
  fi
  local comp_bytes; comp_bytes=$(stat -c%s "$comp")
  t0=$(date +%s%N)
  timeout -k 5 "${TIMEOUT_S}s" "$BIN" decompress "$comp" "$decomp" >>"$LOG_DIR/${tag}.d.log" 2>&1
  local d_rc=$?; t1=$(date +%s%N); local total_ms=$(( c_ms + (t1-t0)/1000000 ))
  local ratio; ratio=$(awk -v c="$comp_bytes" -v o="$orig_bytes" 'BEGIN{printf "%.6f", c/o}')
  if [ $d_rc -ne 0 ] || [ ! -s "$decomp" ]; then
    echo "[$tag] DECOMPRESS CRASH/TIMEOUT rc=$d_rc" >> "$CRASH_LOG"
    printf '%s\t%s\t%s\t%s\t%s\tfalse\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$comp_bytes" "$ratio" "$total_ms"
    rm -f "$comp" "$decomp"; return
  fi
  local rt_ok=false
  cmp -s "$infile" "$decomp" && rt_ok=true || echo "[$tag] RT MISMATCH" >> "$CRASH_LOG"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$scheme" "$relfile" "$orig_bytes" "$comp_bytes" "$ratio" "$rt_ok" "$total_ms"
  rm -f "$comp" "$decomp"
}
export -f run_one; export BIN CORPUS_DIR WORK_DIR LOG_DIR CRASH_LOG TIMEOUT_S
# enwik8 first (long pole), rest after; -P4 keeps ~48 internal threads on 64 cores.
{ grep '^enwik8|' "$JOBLIST"; grep -v '^enwik8|' "$JOBLIST"; } \
  | xargs -P "$POUTER" -I{} bash -c 'run_one "$@"' _ {} >> "$OUT_TSV"
echo "[big] DONE rows_total=$(wc -l < "$OUT_TSV")" >&2
