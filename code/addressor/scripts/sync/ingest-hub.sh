#!/usr/bin/env bash
# Hub-side ingest: quarantine inbox -> private staging -> verified -> store.
# Anti-TOCTOU: the blob is rename()d into hub-private staging FIRST, then
# verified there — a spoke rewriting its inbox copy after verification can
# no longer affect what lands in the store.
set -euo pipefail

STORE_ROOT="${1:?usage: ingest-hub.sh <hub-store-root>}"
INBOX="$STORE_ROOT/inbox"
STAGING="$STORE_ROOT/staging"     # NOT inside the rrsync-confined tree
STORE="$STORE_ROOT/store"
JOURNAL_DIR="$STORE_ROOT/journal" # NOT inside the rrsync-confined tree
JOURNAL="$JOURNAL_DIR/ingest.jsonl"
QUOTA_BYTES="${ADDR_SPOKE_QUOTA_BYTES:-10737418240}" # 10 GiB default

mkdir -p "$STAGING" "$STORE" "$JOURNAL_DIR"
# staging and store MUST share a filesystem (atomic rename)
[ "$(stat -c %d "$STAGING")" = "$(stat -c %d "$STORE")" ] || {
    echo "staging and store on different filesystems" >&2; exit 1; }

json_escape() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

journal() { # journal <event> <spoke> <name>
    printf '{"ts":"%s","event":%s,"spoke":%s,"name":%s}\n' \
        "$(date -u +%FT%TZ)" "$(json_escape "$1")" "$(json_escape "$2")" \
        "$(json_escape "$3")" >> "$JOURNAL"
}

[ -d "$INBOX" ] || exit 0
for SPOKE_DIR in "$INBOX"/spoke_*/; do
    [ -d "$SPOKE_DIR" ] || continue
    SPOKE=$(basename "$SPOKE_DIR")
    # per-spoke quota: reject processing while over cap (D-REQ-13 p.4)
    USED=$(du -sb -- "$SPOKE_DIR" | cut -f1)
    if [ "$USED" -gt "$QUOTA_BYTES" ]; then
        journal "quota-exceeded" "$SPOKE" "$USED"
        continue
    fi
    # null-delimited, -- discipline; rsync temp dotfiles skipped silently
    find "$SPOKE_DIR" -type f ! -name '.*' -print0 | while IFS= read -r -d '' F; do
        REL="${F#"$SPOKE_DIR"}"
        NAME=$(basename -- "$F")
        # names must be shard-form hex chunk files — reject anything else
        if ! printf '%s' "$REL" | grep -qE '^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}\.chunk$'; then
            journal "rejected-name" "$SPOKE" "$REL"
            rm -f -- "$F"
            continue
        fi
        HEX="${NAME%.chunk}"
        # 1. rename into private staging (same fs as store) — spoke loses reach
        STAGED="$STAGING/$HEX.chunk"
        mv -- "$F" "$STAGED"
        # 2. verify BLAKE3 in staging (b3sum if present, else cubrim-addr hash)
        if command -v b3sum >/dev/null 2>&1; then
            ACTUAL=$(b3sum --no-names -- "$STAGED")
        else
            ACTUAL=$("${ADDR_BIN:-cubrim-addr}" hash "$STAGED")
        fi
        if [ "$ACTUAL" != "$HEX" ]; then
            journal "rejected-hash" "$SPOKE" "$REL"
            rm -f -- "$STAGED"
            continue
        fi
        # 3. rename into the store (atomic within one fs); write-once
        DEST="$STORE/${HEX:0:2}/${HEX:2:2}/$HEX.chunk"
        mkdir -p -- "$(dirname -- "$DEST")"
        if [ -e "$DEST" ]; then
            rm -f -- "$STAGED" # already present: write-once keeps the original
            journal "duplicate" "$SPOKE" "$REL"
        else
            mv -- "$STAGED" "$DEST"
            journal "accepted" "$SPOKE" "$REL"
        fi
    done
    # ingest-driven cleanup only: empty shard dirs of processed blobs
    find "$SPOKE_DIR" -type d -empty -delete 2>/dev/null || true
done
