#!/usr/bin/env bash
# CUBR-0072: paired transparent-HTTP page proof on the pinned content_shell.
# This is a build-host evidence runner. It never changes production traffic.
set -euo pipefail

ROOT=${CUBRIM_CHROMIUM_ROOT:-/root/cubr-0079}
OUT=${CUBRIM_TRANSPARENT_PAGE_OUT:-$ROOT/demo/transparent-page-metrics}
TRIALS=${CUBRIM_TRANSPARENT_PAGE_TRIALS:-30}
WARMUPS=${CUBRIM_TRANSPARENT_PAGE_WARMUPS:-3}
PORT=${CUBRIM_TRANSPARENT_PAGE_PORT:-8078}
DOC=html-large-web-codec-v2.html
CS=$ROOT/chromium/src/out/cbm/content_shell
ARGS=$ROOT/chromium/src/out/cbm/args.gn
VERIFY=$ROOT/chromium/netlog_verify.py
EVIDENCE=$ROOT/chromium/transparent_page_evidence.mjs
BUNDLE=$ROOT/chromium/transparent_page_bundle.py
SITE=$ROOT/demo/site

: "${CUBRIM_SOURCE_SHA:?set CUBRIM_SOURCE_SHA to the exact Cubrim source commit}"
: "${CHROMIUM_SOURCE_SHA:?set CHROMIUM_SOURCE_SHA to the exact Chromium source commit}"

test -x "$CS" || { echo "content_shell not built yet" >&2; exit 1; }
test -r "$ARGS" || { echo "content_shell build args not installed" >&2; exit 1; }
test -r "$VERIFY" || { echo "netlog verifier not installed" >&2; exit 1; }
test -r "$EVIDENCE" || { echo "transparent page evidence probe not installed" >&2; exit 1; }
test -r "$BUNDLE" || { echo "transparent page bundle validator not installed" >&2; exit 1; }
test -r "$SITE/$DOC" || { echo "transparent page fixture not installed" >&2; exit 1; }

if grep -Eq '^[[:space:]]*use_libfuzzer[[:space:]]*=[[:space:]]*true([[:space:]]*#.*)?$' "$ARGS"; then
  echo "content_shell build uses use_libfuzzer=true; use the normal browser build" >&2
  exit 1
fi
if [ -e "$OUT" ]; then
  echo "refusing to overwrite existing evidence directory: $OUT" >&2
  exit 1
fi
mkdir -p "$OUT"

python3 - "$OUT/metadata.json" "$CS" "$CUBRIM_SOURCE_SHA" "$CHROMIUM_SOURCE_SHA" "$DOC" <<'PY'
import json
import sys
from pathlib import Path

out, browser, source_sha, chromium_sha, document = sys.argv[1:]
version_file = Path(browser).parents[2] / "chrome" / "VERSION"
version_fields = {}
for line in version_file.read_text().splitlines():
    key, value = line.split("=", 1)
    version_fields[key] = value.strip()
version = "Chromium " + ".".join(
    version_fields[key] for key in ("MAJOR", "MINOR", "BUILD", "PATCH")
)
import hashlib
browser_sha = hashlib.sha256(Path(browser).read_bytes()).hexdigest()
Path(out).write_text(json.dumps({
    "schema_version": 1,
    "source_sha": source_sha,
    "chromium_source_sha": chromium_sha,
    "browser_sha256": browser_sha,
    "browser_version": version,
    "document": document,
}, indent=2, sort_keys=True) + "\n")
PY

python3 - "$OUT/schedule.tsv" "$TRIALS" "$WARMUPS" <<'PY'
import random
import sys
from pathlib import Path

path, trials, warmups = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
tasks = [
    (kind, arm, number)
    for kind, count in (("warmup", warmups), ("trial", trials))
    for arm in ("cbm", "identity")
    for number in range(1, count + 1)
]
random.Random(72072).shuffle(tasks)
Path(path).write_text("".join(f"{kind}\t{arm}\t{number:02d}\n" for kind, arm, number in tasks))
PY

( cd "$SITE" && exec node serve.mjs "$SITE" "$PORT" >"$OUT/server.log" 2>&1 ) &
SERVER_PID=$!
CS_PID=
CS_MAIN_PID=
cleanup() {
  if [ -n "${CS_MAIN_PID:-}" ]; then kill -TERM "$CS_MAIN_PID" 2>/dev/null || true; fi
  if [ -n "${CS_PID:-}" ]; then kill "$CS_PID" 2>/dev/null || true; fi
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
sleep 2

curl -fsS --max-time 10 -o /dev/null -D "$OUT/control-cbm.headers" \
  -H 'Accept-Encoding: cbm, br, gzip' "http://127.0.0.1:$PORT/$DOC"
curl -fsS --max-time 10 -o /dev/null -D "$OUT/control-identity.headers" \
  -H 'Accept-Encoding: gzip, br' "http://127.0.0.1:$PORT/$DOC"
grep -qi '^content-encoding: cbm' "$OUT/control-cbm.headers"
if grep -qi '^content-encoding:' "$OUT/control-identity.headers"; then
  echo "identity control unexpectedly carried Content-Encoding" >&2
  exit 1
fi
grep -qi '^vary:.*accept-encoding' "$OUT/control-cbm.headers"
grep -qi '^vary:.*accept-encoding' "$OUT/control-identity.headers"

run_trial() {
  local kind=$1
  local arm=$2
  local number=$3
  local trial_port=$4
  local tag="$kind-$number"
  local page_url="http://127.0.0.1:$PORT/$DOC"
  local netlog="$OUT/$arm/netlogs/$tag.json"
  local screenshot="$OUT/$arm/screenshots/$tag.png"
  local row="$OUT/$arm/${kind}s/$tag.json"
  local log="$OUT/$arm/$tag.content-shell.log"
  local stdout_log="$OUT/$arm/$tag.evidence.log"
  local feature_flag=--disable-features=CbmContentEncoding
  local evidence_rc=0
  local cs_rc=0
  CS_MAIN_PID=
  mkdir -p "$(dirname "$netlog")" "$(dirname "$screenshot")" "$(dirname "$row")"
  if [ "$arm" = "cbm" ]; then feature_flag=--enable-features=CbmContentEncoding; fi
  set +e
  timeout 75 xvfb-run -a "$CS" \
    --no-sandbox --disable-gpu --disable-background-networking \
    --disable-cache --user-data-dir="$OUT/$arm/profile-$tag" \
    --remote-debugging-port="$trial_port" --log-net-log="$netlog" \
    --net-log-capture-mode=Everything "$feature_flag" about:blank \
    >"$log" 2>&1 &
  CS_PID=$!
  timeout 60 node "$EVIDENCE" "$trial_port" "$page_url" "$DOC" "$SITE/$DOC" "$screenshot" "$row" \
    >"$stdout_log" 2>&1
  evidence_rc=$?
  terminate_trial_processes "$trial_port"
  if kill -0 "$CS_PID" 2>/dev/null; then kill "$CS_PID" 2>/dev/null || true; fi
  if [ -n "${CS_MAIN_PID:-}" ]; then
    kill -TERM "$CS_MAIN_PID" 2>/dev/null || true
  else
    kill "$CS_PID" 2>/dev/null || true
  fi
  wait "$CS_PID"
  cs_rc=$?
  set -e
  if [ "$evidence_rc" -ne 0 ]; then
    echo "$arm $tag: browser evidence failed" >&2
    tail -40 "$stdout_log" >&2 || true
    tail -40 "$log" >&2 || true
    exit "$evidence_rc"
  fi
  if [ "$cs_rc" -ne 0 ] && [ "$evidence_rc" -eq 0 ]; then
    echo "$arm $tag: content_shell stopped after evidence (exit $cs_rc)" >&2
  elif [ "$cs_rc" -ne 0 ]; then
    echo "$arm $tag: content_shell failed (exit $cs_rc)" >&2
    exit "$cs_rc"
  fi
  python3 "$VERIFY" "$netlog" "$DOC" "$arm" >"$OUT/$arm/$tag.netlog-verdict.txt"
}

terminate_trial_processes() {
  local trial_port=$1
  local candidate
  local candidate_cmd
  for candidate in $(pgrep -x content_shell 2>/dev/null || true); do
    candidate_cmd=$(tr '\0' ' ' <"/proc/$candidate/cmdline" 2>/dev/null || true)
    case "$candidate_cmd" in
      *"--remote-debugging-port=$trial_port"*) kill -TERM "$candidate" 2>/dev/null || true ;;
    esac
  done
  sleep 1
  for candidate in $(pgrep -x content_shell 2>/dev/null || true); do
    candidate_cmd=$(tr '\0' ' ' <"/proc/$candidate/cmdline" 2>/dev/null || true)
    case "$candidate_cmd" in
      *"--remote-debugging-port=$trial_port"*) kill -KILL "$candidate" 2>/dev/null || true ;;
    esac
  done
}

run_index=0
while IFS=$'\t' read -r kind arm number; do
  run_index=$((run_index + 1))
  run_trial "$kind" "$arm" "$number" "$((PORT + run_index))"
done < "$OUT/schedule.tsv"

PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 "$BUNDLE" --root "$OUT" --origin "$SITE/$DOC" \
  --out "$OUT/transparent-page.json" --trials "$TRIALS" --warmups "$WARMUPS"
echo "transparent page evidence: $OUT/transparent-page.json"
