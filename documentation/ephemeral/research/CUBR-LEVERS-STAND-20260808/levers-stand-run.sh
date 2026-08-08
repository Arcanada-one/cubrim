#!/usr/bin/env bash
# Stand wall-clock comparison: L1v2 (codec_revisions 7) vs main 49e429e.
# Protocol mirrors the phaseC timing pass: pin 0-15, CUBR_THREADS=4,
# one warmup + three measured samples, GNU time wall+RSS, cmp after every
# decode. Builds interleaved within each sample round.
set -uo pipefail
ROOT=/root/cubr-levers/bench
OLD=/root/cubr0087/cubrim-l1v2
NEW=/root/cubr-levers/code/cubrim-rs/target/release/cubrim
PIN="0-15"
export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1
TSV=$ROOT/levers-timing.tsv
LOG=$ROOT/levers-timing.log
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

load1=$(cut -d' ' -f1 /proc/loadavg)
if ! python3 -c "import sys; sys.exit(0 if float('$load1') < 2.0 else 1)"; then
  log "admission REFUSED: loadavg $load1"; echo ADMISSION-REFUSED; exit 3
fi
if pgrep -x cubrim >/dev/null || pgrep -x cubrim-l1v2 >/dev/null || pgrep -x cubrim-sweep >/dev/null; then
  log "admission REFUSED: foreign cubrim process"; echo ADMISSION-REFUSED; exit 3
fi
log "admission: loadavg $load1, no foreign cubrim; pin=$PIN threads=4"
cat /proc/loadavg >> "$LOG"; ps aux --sort=-%cpu | head -8 >> "$LOG"

wall_rss() { # $1 = time -v stderr file -> "seconds<TAB>rss_kib"
  python3 - "$1" <<'EOF'
import re, sys
txt = open(sys.argv[1]).read()
w = re.search(r'Elapsed \(wall clock\).*?: (.+)', txt).group(1).strip()
p = [float(x) for x in w.split(':')]
secs = p[0]*3600 + p[1]*60 + p[2] if len(p) == 3 else p[0]*60 + p[1]
rss = re.search(r'Maximum resident set size.*?: (\d+)', txt).group(1)
print(f"{secs:.2f}\t{rss}")
EOF
}

printf 'file\tbuild\tsample\tcomp_bytes\tenc_s\tenc_rss_kib\tdec_s\tdec_rss_kib\trt\n' > "$TSV"
for f in dickens nci ooffice; do
  # warmup (uncounted) + cross-build archive identity
  for b in old new; do
    BIN=$([ $b = old ] && echo $OLD || echo $NEW)
    taskset -c $PIN "$BIN" compress "$ROOT/$f.2m" "$ROOT/$f.$b.warm.cbr" >/dev/null 2>&1
    taskset -c $PIN "$BIN" decompress "$ROOT/$f.$b.warm.cbr" "$ROOT/$f.warm.back" >/dev/null 2>&1
    cmp -s "$ROOT/$f.2m" "$ROOT/$f.warm.back" || { log "WARMUP RT FAIL $f $b"; echo RT-FAIL; exit 4; }
    rm -f "$ROOT/$f.warm.back"
  done
  if cmp -s "$ROOT/$f.old.warm.cbr" "$ROOT/$f.new.warm.cbr"; then
    log "$f: cross-build archives BYTE-IDENTICAL"
  else
    log "$f: cross-build archives DIFFER ($(stat -c%s "$ROOT/$f.old.warm.cbr") vs $(stat -c%s "$ROOT/$f.new.warm.cbr"))"
  fi
  for s in 1 2 3; do
    for b in old new; do
      BIN=$([ $b = old ] && echo $OLD || echo $NEW)
      taskset -c $PIN /usr/bin/time -v "$BIN" compress "$ROOT/$f.2m" "$ROOT/$f.run.cbr" >/dev/null 2> "$ROOT/e.tmp"
      read -r es er <<< "$(wall_rss "$ROOT/e.tmp")"
      comp=$(stat -c%s "$ROOT/$f.run.cbr")
      taskset -c $PIN /usr/bin/time -v "$BIN" decompress "$ROOT/$f.run.cbr" "$ROOT/$f.run.back" >/dev/null 2> "$ROOT/d.tmp"
      read -r ds dr <<< "$(wall_rss "$ROOT/d.tmp")"
      rt=FAIL; cmp -s "$ROOT/$f.2m" "$ROOT/$f.run.back" && rt=PASS
      [ $rt = PASS ] || { log "SAMPLE RT FAIL $f $b s$s"; echo RT-FAIL; exit 4; }
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$f" "$b" "$s" "$comp" "$es" "$er" "$ds" "$dr" "$rt" | tee -a "$TSV" >> "$LOG"
      rm -f "$ROOT/$f.run.cbr" "$ROOT/$f.run.back"
    done
  done
done
log "post-run: $(cat /proc/loadavg)"
ps aux --sort=-%cpu | head -8 >> "$LOG"
echo LEVERS-TIMING-COMPLETE
