#!/usr/bin/env bash
# H-39 small-file dictionary spike: does a shipped static dictionary help 18KB
# structured files? Trains a zstd dict on OTHER logs (cross-file, realistic) and on
# alternatives-inclusive (overfit ceiling); compares to no-dict. Corpus: gen_class_corpus.sh.
# RESULT (2026-06-25): alternatives.log zstd-19 no-dict=969, +cross-file-dict=970 (ZERO),
# +overfit-dict=966 (-0.3%). Dictionary is DEAD at 18KB (only helps <1KB cold-start).
set -u; C="${1:?class corpus dir}"; D=$(mktemp -d); mkdir -p "$D/s"
for f in journal.log toolchain.log dpkg.log app_orchestrate.log; do split -l 20 -a4 "$C/$f" "$D/s/${f}_"; done
zstd --train "$D/s"/* -o "$D/log.dict" --maxdict=8192 >/dev/null 2>&1
echo "alternatives: nodict=$(zstd -19 -c "$C/alternatives.log"|wc -c) +dict=$(zstd -19 -D "$D/log.dict" -c "$C/alternatives.log" 2>/dev/null|wc -c)"
rm -rf "$D"
