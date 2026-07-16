#!/usr/bin/env bash
# Pull the hub's epoch snapshot to this spoke. VERIFY-THEN-SWITCH:
# the manifest is checked BEFORE the current_snapshot symlink moves;
# a corrupt epoch never goes live and the old snapshot stays intact.
set -euo pipefail

HUB="${1:?usage: pull-snapshot.sh <hub-host-or-path> <spoke-store-root>}"
ROOT="${2:?usage: pull-snapshot.sh <hub-host-or-path> <spoke-store-root>}"

SNAPDIR="$ROOT/snapshots"
mkdir -p "$SNAPDIR"

# discover the hub's latest epoch name (a plain file next to the epochs)
rsync -e ssh "$HUB/snapshots/LATEST" "$SNAPDIR/.latest.tmp"
LATEST=$(cat "$SNAPDIR/.latest.tmp"); rm -f "$SNAPDIR/.latest.tmp"
case "$LATEST" in
    (*[!a-zA-Z0-9._-]*|""|.|..|-*|*/*) echo "unsafe epoch name: $LATEST" >&2; exit 1;;
esac

TMP="$SNAPDIR/$LATEST.tmp"
rm -rf "$TMP"
# directory pull — the manifest covers the files, no tarball ambiguity
rsync -a -e ssh --ignore-existing "$HUB/snapshots/$LATEST/" "$TMP/"

# 1. VERIFY manifest before anything becomes visible
( cd "$TMP" && sha256sum -c manifest.sha256 --quiet ) || {
    echo "snapshot $LATEST failed manifest verification — keeping old epoch" >&2
    rm -rf "$TMP"
    exit 2
}
# 2. epoch dir lands under its final name
rm -rf "$SNAPDIR/$LATEST"
mv "$TMP" "$SNAPDIR/$LATEST"
# 3. ATOMIC switch: temp symlink + rename (bare ln -sfn is not atomic)
ln -s "snapshots/$LATEST" "$ROOT/current_snapshot.tmp"
mv -T "$ROOT/current_snapshot.tmp" "$ROOT/current_snapshot"
echo "snapshot $LATEST live"
