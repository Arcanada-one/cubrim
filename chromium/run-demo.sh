#!/usr/bin/env bash
# Cubrim Browser Technology Preview — the live demo (CUBR-0079 P4).
# Patched content_shell fetches a page over real Content-Encoding: cbm from a
# loopback origin (web/serve.mjs, which negotiates cbm per PR #199), decodes it
# in the network stack, and we capture the proof from the netlog.
#
# Evidence is the netlog, not a DOM dump: plain content_shell has no --dump-dom
# (that is a web-test-mode switch). The verifier follows the document's
# URLRequest source through request headers, response headers, and terminal
# events. It must not scan the whole JSON text: Chromium's constants table
# contains every net error name, including ERR_CONTENT_DECODING_FAILED.
set -euo pipefail
ROOT=/root/cubr-0079
CS=$ROOT/chromium/src/out/cbm/content_shell
VERIFY=$ROOT/chromium/netlog_verify.py
SITE=$ROOT/demo/site
NETLOG=$ROOT/demo/netlog.json
DOC=html-large-web-codec-v2.html

test -x "$CS" || { echo "content_shell not built yet"; exit 1; }
test -r "$VERIFY" || { echo "netlog verifier not installed"; exit 1; }
cp "$ROOT/demo/serve.mjs" "$ROOT/demo/encoding.mjs" "$SITE/" 2>/dev/null || true
ORIG_SIZE=$(wc -c < "$SITE/$DOC"); FRAME_SIZE=$(wc -c < "$SITE/$DOC.cbr")

echo "== origin+encoder on :8078 (serve.mjs negotiates Content-Encoding: cbm)"
( cd "$SITE" && node serve.mjs "$SITE" 8078 >/tmp/srv.log 2>&1 ) &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
sleep 2

echo "== control: a plain client (no cbm) gets identity"
curl -s -o /dev/null -D - -H 'Accept-Encoding: gzip, br' "http://127.0.0.1:8078/$DOC" | grep -iE "content-encoding|vary" || echo "  (no content-encoding -> identity, correct)"
echo "== a cbm client gets Content-Encoding: cbm (wire $FRAME_SIZE B for a $ORIG_SIZE B doc)"
curl -s -o /dev/null -D - -H 'Accept-Encoding: cbm, br, gzip' "http://127.0.0.1:8078/$DOC" | grep -iE "content-encoding|vary|content-length"

echo "== patched content_shell, cbm feature on, rendered test page via xvfb, full netlog"
rm -f "$NETLOG"
CS_LOG=$(mktemp /tmp/cubr-content-shell.XXXXXX.log)
set +e
timeout 60 xvfb-run -a "$CS" \
  --run-web-tests \
  --enable-features=CbmContentEncoding --no-sandbox --disable-gpu \
  --disable-background-networking \
  --log-net-log="$NETLOG" --net-log-capture-mode=Everything \
  "http://127.0.0.1:8078/$DOC" >"$CS_LOG" 2>&1
CS_RC=$?
set -e
if [ "$CS_RC" -ne 0 ]; then
  echo "content_shell failed (exit $CS_RC); last output:" >&2
  tail -40 "$CS_LOG" >&2
  exit "$CS_RC"
fi

echo "== EVIDENCE (from $NETLOG)"
[ -s "$NETLOG" ] || { echo "  netlog empty — content_shell may need more time"; exit 1; }
python3 "$VERIFY" "$NETLOG" "$DOC"
echo "-- served $FRAME_SIZE cbm wire bytes for the $ORIG_SIZE B identity doc; the"
echo "   patched network stack decoded it (a stock build has no cbm and would 406/garble)."
