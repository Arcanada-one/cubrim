#!/usr/bin/env bash
# CUBR-0087 — memory/throughput/ratio sweep.
#
# Two knobs, swept independently against the same file so each effect is
# attributable:
#
#   CUBRIM_CM2_TBITS=<n>  caps the CM2 per-model hash-table exponent. Model
#                         footprint is 4 B x 2^n x 24 counters + 3 x 4 B x 2^n
#                         match tables, i.e. 13.5 GiB at the shipped cap of 27.
#                         Tests M3: if throughput rises as the tables shrink,
#                         the codec is memory-latency-bound and the entropy
#                         coder is not the lever.
#
#   CUBRIM_CM2_NO_COL=1   skips the FH4-03 column-model variant passes. Tests
#                         M2: prices the encode-side variant sweep that the
#                         decoder never replays.
#
# Every row round-trips. A row whose round-trip fails is not a measurement and
# is reported as FAIL rather than dropped.
#
# Timings are taken with the process pinned to a fixed core set (CPUSET), so
# rows are comparable on a shared host. The pin is identical for every row —
# it is not widened for any row, and no row is re-run to get a better number.
set -uo pipefail

BIN="${BIN:?set BIN}"
FILE="${FILE:?set FILE}"
OUT="${OUT:?set OUT}"
CPUSET="${CPUSET:-0-3}"
mkdir -p "$OUT"
base="$(basename "$FILE")"
orig=$(stat -c%s "$FILE")
TSV="$OUT/sweep-$base.tsv"

row() { # label, extra env assignments...
    local label="$1"; shift
    local blob="$OUT/$base.$label.cbr"
    local back="$OUT/$base.$label.back"
    env "$@" taskset -c "$CPUSET" /usr/bin/time -v "$BIN" compress "$FILE" "$blob" \
        > "$OUT/$base.$label.enc.out" 2> "$OUT/$base.$label.enc.err"
    local ew er
    ew=$(grep -F 'Elapsed (wall clock)' "$OUT/$base.$label.enc.err" | awk '{print $NF}')
    er=$(grep -F 'Maximum resident set size' "$OUT/$base.$label.enc.err" | grep -oE '[0-9]+')
    env "$@" taskset -c "$CPUSET" /usr/bin/time -v "$BIN" decompress "$blob" "$back" \
        > "$OUT/$base.$label.dec.out" 2> "$OUT/$base.$label.dec.err"
    local dw dr
    dw=$(grep -F 'Elapsed (wall clock)' "$OUT/$base.$label.dec.err" | awk '{print $NF}')
    dr=$(grep -F 'Maximum resident set size' "$OUT/$base.$label.dec.err" | grep -oE '[0-9]+')
    local rt=FAIL
    cmp -s "$FILE" "$back" && rt=PASS
    local comp; comp=$(stat -c%s "$blob" 2>/dev/null || echo 0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$label" "$orig" "$comp" \
        "$(awk -v c="$comp" -v o="$orig" 'BEGIN{printf "%.6f", c/o}')" \
        "$ew" "$dw" "$er" "$dr" "$rt" | tee -a "$TSV"
    rm -f "$back" "$blob"
}

printf 'label\torig\tcomp\tratio\tenc_wall\tdec_wall\tenc_rss_kib\tdec_rss_kib\trt\n' | tee "$TSV"
row native   CUBRIM_UNUSED=0
row tbits24  CUBRIM_CM2_TBITS=24
row tbits22  CUBRIM_CM2_TBITS=22
row tbits20  CUBRIM_CM2_TBITS=20
row tbits18  CUBRIM_CM2_TBITS=18
row nocol    CUBRIM_CM2_NO_COL=1
row nocol_tbits20 CUBRIM_CM2_NO_COL=1 CUBRIM_CM2_TBITS=20
echo "SWEEP-COMPLETE $base"
