#!/usr/bin/env bash
# CUBR-0087 post-merge verification.
#
# Two requirements, both stated by the operator:
#   1. merged `main` must expose --preset from a FRESHLY BUILT CLI
#   2. `max` on the corpus must still reproduce 59,489,703 bytes / 0.189007
#
# Deliberately a fresh `git clone` of origin/main rather than the working
# worktree: the whole point is to prove that what a user gets from the default
# branch carries the feature, and a worktree can differ from origin in ways that
# are invisible until someone else clones it. This is the same failure the stale
# `target/release/cubrim` already caused once — the flag existed in source while
# the artefact a user would run did not have it.
set -uo pipefail
WORK="${1:?work dir}"
CORPUS="${2:-/home/dev/cubr-cubecore-research/corpus-silesia}"
rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK"

echo "=== 1. fresh clone of origin/main ==="
git clone -q --depth 1 https://github.com/Arcanada-one/cubrim.git repo || exit 1
cd repo
echo "cloned HEAD: $(git log --oneline -1)"

echo "=== 2. does main carry the preset source at all? ==="
for sym in cm2_max_tbits 'Preset::Web' CM2_TBITS_SHIFT; do
    n=$(grep -rc "$sym" code/cubrim-rs/src/ 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
    printf '  %-20s %s occurrences\n' "$sym" "$n"
done

echo "=== 3. build from scratch ==="
cargo build --release --manifest-path code/cubrim-rs/Cargo.toml 2>&1 | tail -2
BIN="$PWD/code/cubrim-rs/target/release/cubrim"
[ -x "$BIN" ] || { echo "FAIL: no binary"; exit 1; }

echo "=== 4. REQUIREMENT 1 — --preset exposed from the freshly built CLI ==="
for sub in compress a; do
    if "$BIN" "$sub" --help 2>&1 | grep -q -- "--preset"; then
        vals=$("$BIN" "$sub" --preset __bogus__ /dev/null /dev/null 2>&1 | grep -oE '\[possible values[^]]*\]' | head -1)
        echo "  $sub: --preset PRESENT $vals"
    else
        echo "  $sub: --preset MISSING — REQUIREMENT 1 FAILED"; exit 1
    fi
done

echo "=== 5. REQUIREMENT 2 — corpus max reproduction ==="
echo "  (full 24-file corpus; expect 59,489,703 bytes / ratio 0.189007)"
tot_o=0; tot_c=0; fails=0
for f in "$CORPUS"/*; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in SHA256SUMS.txt) continue;; esac
    o=$(stat -c%s "$f")
    "$BIN" compress --preset max --quiet "$f" "$WORK/a.cbr" >/dev/null 2>&1
    c=$(stat -c%s "$WORK/a.cbr" 2>/dev/null || echo 0)
    "$BIN" decompress "$WORK/a.cbr" "$WORK/a.out" >/dev/null 2>&1
    rt=FAIL; cmp -s "$f" "$WORK/a.out" && rt=PASS
    [ "$rt" = PASS ] || fails=$((fails+1))
    tot_o=$((tot_o+o)); tot_c=$((tot_c+c))
    printf '  %-14s %12s -> %12s  rt=%s\n' "$(basename "$f")" "$o" "$c" "$rt"
    rm -f "$WORK/a.cbr" "$WORK/a.out"
done
echo "  TOTAL orig=$tot_o comp=$tot_c ratio=$(awk -v c=$tot_c -v o=$tot_o 'BEGIN{printf "%.6f", c/o}') rt_failures=$fails"
echo "POST-MERGE-VERIFY-COMPLETE"
