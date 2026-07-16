#!/usr/bin/env bash
# One-time layout for a hub or spoke store root. Hub deployment itself is
# OPERATOR-GATED (prod node) — see deploy/HUB-DEPLOY.md.
set -euo pipefail
ROOT="${1:?usage: setup.sh <store-root> [hub|spoke]}"
ROLE="${2:-spoke}"
mkdir -p "$ROOT/store" "$ROOT/snapshots"
if [ "$ROLE" = hub ]; then
    mkdir -p "$ROOT/inbox" "$ROOT/staging" "$ROOT/journal"
    [ "$(stat -c %d "$ROOT/staging")" = "$(stat -c %d "$ROOT/store")" ] \
        || { echo "staging/store must share a filesystem" >&2; exit 1; }
    chmod 700 "$ROOT/staging" "$ROOT/journal"
fi
echo "$ROLE layout ready at $ROOT"
