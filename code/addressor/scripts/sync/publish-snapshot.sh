#!/usr/bin/env bash
# Hub-side: publish a new epoch snapshot (bloom + catalog + matrix sections)
# as a self-contained directory with a sha256 manifest, then flip LATEST.
set -euo pipefail

STORE_ROOT="${1:?usage: publish-snapshot.sh <hub-store-root> <artifacts-dir>}"
ARTIFACTS="${2:?usage: publish-snapshot.sh <hub-store-root> <artifacts-dir>}"

EPOCH="epoch-$(date -u +%Y%m%dT%H%M%SZ)"
SNAPDIR="$STORE_ROOT/snapshots/$EPOCH"
mkdir -p "$SNAPDIR"
cp -a -- "$ARTIFACTS"/. "$SNAPDIR/"
( cd "$SNAPDIR" && find . -type f ! -name manifest.sha256 -printf '%P\n' \
    | sort | xargs -d '\n' sha256sum > manifest.sha256 )
printf '%s\n' "$EPOCH" > "$STORE_ROOT/snapshots/LATEST.tmp"
mv -T "$STORE_ROOT/snapshots/LATEST.tmp" "$STORE_ROOT/snapshots/LATEST"
echo "$EPOCH published"
