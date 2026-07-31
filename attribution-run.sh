#!/usr/bin/env bash
# CUBR-0087 M2/M4 — encoder candidate attribution run.
#
# For each corpus slice: encode with CUBRIM_PROFILE=1 (attribution table to
# stderr), record wall time and peak RSS, then decode and assert byte-exact
# round-trip. A configuration whose round-trip fails is not a measurement.
set -uo pipefail

BIN="${BIN:?set BIN to the cubrim binary}"
CORPUS="${CORPUS:?set CORPUS to the slice directory}"
OUT="${OUT:?set OUT to the output directory}"
mkdir -p "$OUT"

for f in "$CORPUS"/*; do
    name="$(basename "$f")"
    blob="$OUT/$name.cbr"
    back="$OUT/$name.back"
    log="$OUT/$name.prof.txt"

    /usr/bin/time -v env CUBRIM_PROFILE=1 "$BIN" compress "$f" "$blob" \
        > "$OUT/$name.stdout" 2> "$log"
    enc_rss=$(grep -F 'Maximum resident set size' "$log" | grep -oE '[0-9]+' || echo "")
    enc_wall=$(grep -F 'Elapsed (wall clock)' "$log" | awk '{print $NF}')

    /usr/bin/time -v "$BIN" decompress "$blob" "$back" \
        > "$OUT/$name.dec.stdout" 2> "$OUT/$name.dec.txt"
    dec_rss=$(grep -F 'Maximum resident set size' "$OUT/$name.dec.txt" | grep -oE '[0-9]+' || echo "")
    dec_wall=$(grep -F 'Elapsed (wall clock)' "$OUT/$name.dec.txt" | awk '{print $NF}')

    if cmp -s "$f" "$back"; then rt=PASS; else rt=FAIL; fi
    orig=$(stat -c%s "$f")
    comp=$(stat -c%s "$blob" 2>/dev/null || echo 0)
    printf '%s\torig=%s\tcomp=%s\tratio=%s\tenc_wall=%s\tdec_wall=%s\tenc_rss_kib=%s\tdec_rss_kib=%s\trt=%s\n' \
        "$name" "$orig" "$comp" \
        "$(awk -v c="$comp" -v o="$orig" 'BEGIN{if(o>0)printf "%.6f", c/o; else print "NA"}')" \
        "$enc_wall" "$dec_wall" "$enc_rss" "$dec_rss" "$rt" \
        | tee -a "$OUT/SUMMARY.tsv"
    rm -f "$back"
done
echo "ATTRIBUTION-RUN-COMPLETE"
