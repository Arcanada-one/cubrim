#!/usr/bin/env bash
# size-model.sh — Full-branch size model (Gotcha #6 + #7 gate).
#
# Asserts that a candidate scheme's size model charges one cost term per
# decoder branch — including any phi-map / permutation transmission (Gotcha #7).
# A model with fewer cost terms than decoder branches is UNSOUND → NO-GO.
#
# Also checks the closed-branch ledger for auto-reject of known-closed directions.
#
# Usage:
#   size-model.sh --model-json <path-to-size-model.json> [--ledger <closed-branches.md>]
#
# The size-model JSON must follow the schema:
#   {
#     "candidate_name": "...",
#     "mechanism": "...",
#     "decoder_branches": [
#       {"name": "branch1", "cost_bytes_estimate": 123},
#       ...
#     ],
#     "cost_terms": [
#       {"name": "term1", "cost_bytes_estimate": 123},
#       ...
#     ],
#     "phi_map_transmitted": false,
#     "closed_branch_check": false
#   }
#
# Exit 0   = PASS (model is sound: terms >= branches, phi-map charged if needed)
# Exit 1   = NO-GO (unsound model: terms < branches, OR phi-map not charged, OR closed branch)
# Exit 2   = error / invalid input
#
# Companion script: size-model.py (does the Python-level validation)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL_PY="$SCRIPT_DIR/size-model.py"
DEFAULT_LEDGER="$REPO_ROOT/consilium/closed-branches.md"

MODEL_JSON=""
LEDGER="$DEFAULT_LEDGER"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-json) MODEL_JSON="$2"; shift 2;;
        --ledger)     LEDGER="$2"; shift 2;;
        *) echo "size-model: unknown arg: $1" >&2; exit 2;;
    esac
done

die() { echo "size-model: ERROR: $*" >&2; exit 2; }

[ -n "$MODEL_JSON" ] || die "--model-json is required"
[ -f "$MODEL_JSON" ] || die "model JSON not found: $MODEL_JSON"
[ -f "$MODEL_PY" ] || die "size-model.py not found: $MODEL_PY"
command -v python3 >/dev/null 2>&1 || die "python3 required"

set +e
RESULT="$(python3 "$MODEL_PY" --model "$MODEL_JSON" --ledger "$LEDGER" 2>&1)"
RC=$?
set -e

echo "$RESULT"

if [ "$RC" -ne 0 ]; then
    echo "size-model: NO-GO — full-branch size model unsound (see above)" >&2
    exit 1
fi

echo "size-model: PASS — full-branch size model is sound"
exit 0
