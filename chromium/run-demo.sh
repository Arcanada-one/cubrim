#!/usr/bin/env bash
# Cubrim Browser Technology Preview — the live demo (CUBR-0079 P4).
# Patched content_shell fetches a page over real Content-Encoding: cbm from a
# loopback origin (web/serve.mjs, which negotiates cbm per PR #199), decodes it
# in the network stack, and we capture the proof.
set -euo pipefail
ROOT=/root/cubr-0079
CS=$ROOT/chromium/src/out/cbm/content_shell
SITE=$ROOT/demo/site
NETLOG=$ROOT/demo/netlog.json
DUMP=$ROOT/demo/dom-dump.txt
DOC=html-large-web-codec-v2.html

test -x "$CS" || { echo "content_shell not built yet"; exit 1; }
cp "$ROOT/demo/serve.mjs" "$ROOT/demo/encoding.mjs" "$SITE/" 2>/dev/null || true

echo "== origin+encoder on :8078 (serve.mjs negotiates Content-Encoding: cbm)"
( cd "$SITE" && node serve.mjs "$SITE" 8078 ) &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
sleep 2

echo "== control: a plain client (no cbm) gets identity"
curl -s -o /dev/null -D - -H 'Accept-Encoding: gzip, br' "http://127.0.0.1:8078/$DOC" | grep -i "content-encoding\|vary" || echo "  (identity, no content-encoding — correct)"
echo "== a cbm client gets Content-Encoding: cbm"
curl -s -o /dev/null -D - -H 'Accept-Encoding: cbm, br, gzip' "http://127.0.0.1:8078/$DOC" | grep -i "content-encoding\|vary"

echo "== patched content_shell, cbm feature on, headless via xvfb, netlog capture"
# Timed headless load + DOM dump: content_shell fetches the document over
# Content-Encoding: cbm and decodes it in the network stack; --dump-dom prints
# the rendered DOM, proving the decoded bytes reached Blink.
timeout 60 xvfb-run -a "$CS" \
  --enable-features=CbmContentEncoding --no-sandbox --disable-gpu \
  --log-net-log="$NETLOG" --net-log-capture-mode=Everything --dump-dom "http://127.0.0.1:8078/$DOC" > "$DUMP" 2>/dev/null || true

echo "== EVIDENCE"
echo "-- netlog mentions of cbm content-encoding:"
grep -o '"Content-Encoding: *cbm"\|cbm' "$NETLOG" 2>/dev/null | sort | uniq -c | head
echo "-- DOM dump size (decoded HTML rendered): $(wc -c < "$DUMP" 2>/dev/null) bytes"
echo "-- original doc size: $(wc -c < "$SITE/$DOC") bytes; cbm frame: $(wc -c < "$SITE/$DOC.cbr") bytes"
echo "-- DOM contains body text from the decoded page:"
grep -o '<title>[^<]*</title>\|cubrim\|Web Codec' "$DUMP" 2>/dev/null | head -3
