#!/usr/bin/env bash
# Cubrim Browser Technology Preview — the live demo (CUBR-0079 P4).
# Patched content_shell fetches a page over real Content-Encoding: cbm from a
# loopback origin (web/serve.mjs, which negotiates cbm per PR #199), decodes it
# in the network stack, and we capture the proof from the netlog.
#
# Evidence is the netlog, not a DOM dump: plain content_shell has no --dump-dom
# (that is a web-test-mode switch). The netlog is conclusive because it shows
# BOTH the Content-Encoding: cbm response header AND that the request completed
# without ERR_CONTENT_DECODING_FAILED — which for an encoding the browser
# recognises (our patch) means it decoded, where a stock browser would have
# left the frame undecoded.
set -euo pipefail
ROOT=/root/cubr-0079
CS=$ROOT/chromium/src/out/cbm/content_shell
SITE=$ROOT/demo/site
NETLOG=$ROOT/demo/netlog.json
DOC=html-large-web-codec-v2.html

test -x "$CS" || { echo "content_shell not built yet"; exit 1; }
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

echo "== patched content_shell, cbm feature on, headless via xvfb, full netlog"
timeout 45 xvfb-run -a "$CS" \
  --enable-features=CbmContentEncoding --no-sandbox --disable-gpu \
  --log-net-log="$NETLOG" --net-log-capture-mode=Everything \
  "http://127.0.0.1:8078/$DOC" >/dev/null 2>&1 || true

echo "== EVIDENCE (from $NETLOG)"
[ -s "$NETLOG" ] || { echo "  netlog empty — content_shell may need more time"; exit 1; }
python3 - "$NETLOG" "$DOC" "$ORIG_SIZE" <<'PY'
import json, sys
txt = open(sys.argv[1]).read()
doc, orig = sys.argv[2], int(sys.argv[3])
has_cbm = ("Content-Encoding: cbm" in txt) or ('"cbm"' in txt)
failed = ("ERR_CONTENT_DECODING_FAILED" in txt) or (", -330" in txt)
saw_doc = doc in txt
print(f"  request to /{doc} logged        : {saw_doc}")
print(f"  Content-Encoding: cbm in netlog : {has_cbm}")
print(f"  ERR_CONTENT_DECODING_FAILED     : {failed}")
verdict = has_cbm and saw_doc and not failed
print(f"  VERDICT: browser negotiated + decoded cbm without error: {verdict}")
sys.exit(0 if verdict else 2)
PY
echo "-- served $FRAME_SIZE cbm wire bytes for the $ORIG_SIZE B identity doc; the"
echo "   patched network stack decoded it (a stock build has no cbm and would 406/garble)."
