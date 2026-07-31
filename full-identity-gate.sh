#!/usr/bin/env bash
# CUBR-0087 L1 — byte-identity gate at real corpus scale.
#
# The 2 MB slices exercise ~32 blocks. The abandonment path races 16 worker
# threads against a shared counter, and a bound that has never met a
# thousand-block file has not been tested where that race is interesting. This
# runs the pre-change and post-change binaries over full Silesia files and
# requires sha256 equality plus a round-trip.
#
# Deliberately includes the two files where `base` loses the top-level
# competition (`ooffice` exe -> bcj_cm2, `x-ray` image -> med16), because those
# are the only ones where the bound actually fires. A gate made only of files
# where nothing is abandoned would pass without testing anything.
#
# Size comparisons are load-insensitive, so this may run on a busy host. It
# reports no timings for exactly that reason.
set -uo pipefail

REF_BIN="${REF_BIN:?pre-change binary}"
NEW_BIN="${NEW_BIN:?post-change binary}"
CORPUS="${CORPUS:-/home/dev/cubr-cubecore-research/corpus-silesia}"
OUT="${OUT:?output dir}"
FILES="${FILES:-x-ray ooffice xml samba}"
mkdir -p "$OUT"

printf 'file\torig\tref_bytes\tnew_bytes\tidentity\trt\n' | tee "$OUT/FULL-IDENTITY.tsv"
for name in $FILES; do
    src="$CORPUS/$name"
    if [ ! -f "$src" ]; then echo "$name SKIP (missing)"; continue; fi
    ref="$OUT/$name.ref.cbr"; new="$OUT/$name.new.cbr"; back="$OUT/$name.back"

    # Serialised on purpose: two concurrent encodes of a file this size put the
    # box into heavy oversubscription (see F6) and would slow the gate down, not
    # speed it up.
    "$REF_BIN" compress "$src" "$ref" >/dev/null 2>&1
    "$NEW_BIN" compress "$src" "$new" >/dev/null 2>&1
    "$NEW_BIN" decompress "$new" "$back" >/dev/null 2>&1

    rt=FAIL; cmp -s "$src" "$back" && rt=PASS
    a=$(sha256sum "$ref" 2>/dev/null | cut -d' ' -f1)
    b=$(sha256sum "$new" 2>/dev/null | cut -d' ' -f1)
    id=DIFFER; [ -n "$a" ] && [ "$a" = "$b" ] && id=IDENTICAL
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$name" "$(stat -c%s "$src")" \
        "$(stat -c%s "$ref" 2>/dev/null || echo 0)" \
        "$(stat -c%s "$new" 2>/dev/null || echo 0)" \
        "$id" "$rt" | tee -a "$OUT/FULL-IDENTITY.tsv"
    rm -f "$back" "$ref" "$new"
done
echo FULL-IDENTITY-GATE-COMPLETE
