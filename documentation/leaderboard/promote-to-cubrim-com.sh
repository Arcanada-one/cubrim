#!/usr/bin/env bash
# promote-to-cubrim-com.sh — OPERATOR-GATED leaderboard promotion to cubrim.com.
#
# This script ONLY stages, diffs, and prints a review prompt — it NEVER deploys.
# Deployment requires explicit operator action (run deploy.sh manually after review).
#
# Context:
#   - The git-tracked leaderboard (documentation/leaderboard/) accumulates per-iteration
#     GO results autonomously.
#   - Promoting those results to the public cubrim.com site is an operator-gated
#     batch step (AC-6 decision: public surface under human control).
#   - This script prepares the promotion artefact and explains what to do next.
#
# Usage: promote-to-cubrim-com.sh [--dry-run]
#
# Exit 0 = artefact prepared, operator review required
# Exit 1 = error (leaderboard missing / invalid)
# Exit 2 = dependency error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
JSON="$SCRIPT_DIR/cubrim-leaderboard.json"
MD="$SCRIPT_DIR/LEADERBOARD.md"
GEN_MD="$SCRIPT_DIR/gen-leaderboard-md.sh"

DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift;;
        *) echo "promote-to-cubrim-com: unknown arg: $1" >&2; exit 2;;
    esac
done

die() { echo "promote-to-cubrim-com: ERROR: $*" >&2; exit 1; }

[ -f "$JSON" ] || die "leaderboard JSON not found: $JSON"
command -v python3 >/dev/null 2>&1 || die "python3 required"

# ── 1. Regenerate LEADERBOARD.md from current JSON ───────────────────────────
echo "promote-to-cubrim-com: regenerating LEADERBOARD.md..."
bash "$GEN_MD" --json "$JSON" --output "$MD"

# ── 2. Validate JSON (roundtrip_ok guard) ────────────────────────────────────
echo "promote-to-cubrim-com: validating leaderboard integrity..."
python3 -c "
import json, sys
lb = json.load(open('$JSON'))
runs = lb.get('runs', [])
bad = [r.get('run_id','?') for r in runs if not r.get('roundtrip_ok', False)]
if bad:
    print(f'ERROR: runs without roundtrip_ok=true: {bad}', file=sys.stderr)
    sys.exit(1)
no_ref = [r.get('run_id','?') for r in runs if not r.get('run_log_ref')]
if no_ref:
    print(f'ERROR: runs missing run_log_ref: {no_ref}', file=sys.stderr)
    sys.exit(1)
go_runs = [r for r in runs if r.get('verdict') == 'GO']
print(f'Leaderboard valid: {len(runs)} total runs, {len(go_runs)} GO runs')
"

# ── 3. Compute diff (what would change on cubrim.com) ────────────────────────
echo ""
echo "promote-to-cubrim-com: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "OPERATOR-GATED: Review the following before proceeding."
echo ""
echo "Files to promote to cubrim.com:"
echo "  documentation/leaderboard/cubrim-leaderboard.json  → site leaderboard data"
echo "  documentation/leaderboard/LEADERBOARD.md           → rendered table"
echo ""
echo "Current best: $(python3 -c "import json; lb=json.load(open('$JSON')); print(lb['current_best']['aggregate'])")"
echo "GO runs: $(python3 -c "import json; lb=json.load(open('$JSON')); print(len([r for r in lb.get('runs',[]) if r.get('verdict')=='GO']))")"
echo ""
echo "LEADERBOARD.md preview (first 30 lines):"
head -30 "$MD"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "operator-gated: review the diff above and deploy manually:"
echo ""
echo "  # To deploy to cubrim.com (run from the cubrim repo root):"
echo "  bash deploy.sh cubrim.com"
echo ""
echo "  # Or copy leaderboard files to the website content directory:"
echo "  # cp documentation/leaderboard/LEADERBOARD.md  <website-content-dir>/leaderboard.md"
echo "  # cp documentation/leaderboard/cubrim-leaderboard.json <website-content-dir>/leaderboard.json"
echo ""
echo "This script will NOT execute the deploy. It is purely informational."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
