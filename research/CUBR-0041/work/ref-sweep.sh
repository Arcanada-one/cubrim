#!/usr/bin/env bash
# CUBR-0041 reference-compressor sweep on the EXACT 11-file world corpus.
# Puts ppmd/xz/brotli/zstd/bzip2 on the same corpus as the cubrim oracle so all
# overall numbers are comparable. Emits TSV: tool<TAB>file<TAB>orig<TAB>comp<TAB>ratio
set -u
CORPUS_DIR=/root/corpus
OUT=/root/cubr0041/ref.tsv
: > "$OUT"
mapfile -t FILES < <(cd "$CORPUS_DIR" && find . -type f | sed 's#^\./##' | sort)
emit(){ printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$(awk -v c="$4" -v o="$3" 'BEGIN{printf "%.6f", c/o}')" >> "$OUT"; }
for f in "${FILES[@]}"; do
  in="$CORPUS_DIR/$f"; o=$(stat -c%s "$in")
  # 7z PPMd (order 16, 192m mem) — the leader class
  7z a -mx9 -m0=PPMd:o16:mem192m /tmp/r.7z "$in" >/dev/null 2>&1 && emit ppmd "$f" "$o" "$(stat -c%s /tmp/r.7z)"; rm -f /tmp/r.7z
  xz -9e -k -c "$in" 2>/dev/null | wc -c | { read c; emit xz "$f" "$o" "$c"; }
  brotli -q 11 -c "$in" 2>/dev/null | wc -c | { read c; emit brotli "$f" "$o" "$c"; }
  zstd -19 -c "$in" 2>/dev/null | wc -c | { read c; emit zstd "$f" "$o" "$c"; }
  bzip2 -9 -c "$in" 2>/dev/null | wc -c | { read c; emit bzip2 "$f" "$o" "$c"; }
done
echo "[ref] DONE rows=$(wc -l < "$OUT")" >&2
