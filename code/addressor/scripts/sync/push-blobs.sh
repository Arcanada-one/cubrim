#!/usr/bin/env bash
# Push new CAS blobs from this spoke into the hub's quarantine inbox.
# --ignore-existing is client-side politeness; the real controls are the
# hub's rrsync write-only confinement and the ingest re-verification.
set -euo pipefail

ROOT="${1:?usage: push-blobs.sh <spoke-store-root> <hub-inbox-target> <spoke-id>}"
HUB_INBOX="${2:?usage: push-blobs.sh <spoke-store-root> <hub-inbox-target> <spoke-id>}"
SPOKE_ID="${3:?usage: push-blobs.sh <spoke-store-root> <hub-inbox-target> <spoke-id>}"
case "$SPOKE_ID" in (*[!a-zA-Z0-9_-]*|"") echo "bad spoke id" >&2; exit 1;; esac

rsync -a -e ssh --ignore-existing \
    --include='*/' --include='*.chunk' --exclude='*' \
    "$ROOT/store/" "$HUB_INBOX/spoke_$SPOKE_ID/"
