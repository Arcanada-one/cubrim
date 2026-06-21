#!/usr/bin/env bash
# probe-entropy.sh — Order-1 conditional-entropy probe (Gotcha #3 gate).
#
# Runs a ~50-LoC Python entropy probe on the candidate's resulting value stream
# to detect if the proposed transformation RAISES H(X_t | X_{t-1}) on corpus
# files with run structure (clustered). Raise in conditional entropy = NO-GO.
#
# Usage:
#   probe-entropy.sh --candidate-script <path.py> [--corpus <manifest.json>]
#
# The candidate script must accept --corpus <manifest.json> and write a JSON
# report to stdout with at least:
#   {"h1_iorder": <float>, "h1_candidate": <float>, "files": [...]}
# where h1_candidate > h1_iorder on any clustered file = auto-NO-GO.
#
# Alternatively (simpler), the probe can be run with --value-stream-bytes <path>
# directly for a pre-generated transformed byte sequence.
#
# Exit 0   = PASS (conditional entropy does not increase on clustered files)
# Exit 1   = NO-GO (conditional entropy raised on ≥1 clustered file)
# Exit 2   = error / missing input
#
# The probe is DETERMINISTIC and LOCAL — no model calls, no network.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="${CORPUS_MANIFEST:-$REPO_ROOT/docs/ephemeral/research/corpus/manifest.json}"
PROBE_PY="$SCRIPT_DIR/probe-entropy.py"

CANDIDATE_SCRIPT=""
VALUE_STREAM_BYTES=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --candidate-script)   CANDIDATE_SCRIPT="$2"; shift 2;;
        --corpus)             MANIFEST="$2"; shift 2;;
        --value-stream-bytes) VALUE_STREAM_BYTES="$2"; shift 2;;
        *) echo "probe-entropy: unknown arg: $1" >&2; exit 2;;
    esac
done

die() { echo "probe-entropy: ERROR: $*" >&2; exit 2; }

[ -f "$MANIFEST" ] || die "corpus manifest not found: $MANIFEST"
[ -f "$PROBE_PY" ] || die "probe script not found: $PROBE_PY"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# Arbiter bootstrap-check: the probe imports numpy. Fail with an actionable
# message instead of an opaque ModuleNotFoundError deep in the Python run.
if ! python3 -c "import numpy" >/dev/null 2>&1; then
    die "numpy is required for the arbiter probe but is not importable. Install it: 'pip install -r $SCRIPT_DIR/requirements.txt' (or 'pip install numpy')."
fi

if [ -n "$VALUE_STREAM_BYTES" ]; then
    # Direct mode: probe a pre-generated value stream
    [ -f "$VALUE_STREAM_BYTES" ] || die "value stream file not found: $VALUE_STREAM_BYTES"
    set +e
    RESULT="$(python3 "$PROBE_PY" --value-stream "$VALUE_STREAM_BYTES" --corpus "$MANIFEST" 2>&1)"
    RC=$?
    set -e
elif [ -n "$CANDIDATE_SCRIPT" ]; then
    [ -f "$CANDIDATE_SCRIPT" ] || die "candidate script not found: $CANDIDATE_SCRIPT"
    set +e
    RESULT="$(python3 "$PROBE_PY" --candidate "$CANDIDATE_SCRIPT" --corpus "$MANIFEST" 2>&1)"
    RC=$?
    set -e
else
    die "either --candidate-script or --value-stream-bytes required"
fi

echo "$RESULT"

if [ "$RC" -ne 0 ]; then
    echo "probe-entropy: NO-GO — conditional entropy raised (see above)" >&2
    exit 1
fi

echo "probe-entropy: PASS — conditional entropy probe OK"
exit 0
