#!/usr/bin/env bash
# gen-leaderboard-md.sh — Render cubrim-leaderboard.json → LEADERBOARD.md
#
# Reads docs/leaderboard/cubrim-leaderboard.json and generates
# docs/leaderboard/LEADERBOARD.md as a deterministic Markdown table.
# Run autonomously after each iteration that writes to the leaderboard.
#
# Usage: gen-leaderboard-md.sh [--json <path>] [--output <path>] [--dry-run]
#
# Exit 0 = success
# Exit 1 = JSON parse error or write error
# Exit 2 = missing dependency

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

JSON_PATH="$SCRIPT_DIR/cubrim-leaderboard.json"
OUTPUT_PATH="$SCRIPT_DIR/LEADERBOARD.md"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)     JSON_PATH="$2"; shift 2;;
        --output)   OUTPUT_PATH="$2"; shift 2;;
        --dry-run)  DRY_RUN=1; shift;;
        *) echo "gen-leaderboard-md: unknown arg: $1" >&2; exit 2;;
    esac
done

die() { echo "gen-leaderboard-md: ERROR: $*" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || die "python3 required"

[ -f "$JSON_PATH" ] || die "leaderboard JSON not found: $JSON_PATH"

# Generate markdown via Python (deterministic; no external deps beyond stdlib)
MD="$(python3 - "$JSON_PATH" << 'PYEOF'
import json, sys, datetime
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
lb = data

win_gzip = lb["win_target"]["gzip_aggregate"]
win_xz   = lb["win_target"]["xz_aggregate"]
best     = lb["current_best"]
runs     = lb.get("runs", [])

lines = []
lines.append("# Cubrim Compression Leaderboard")
lines.append("")
lines.append(f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
lines.append("")
lines.append("## Win Target")
lines.append("")
lines.append(f"Beat gzip -9 aggregate on the frozen 10-file corpus.")
lines.append("")
lines.append(f"| Archiever | Aggregate Ratio | Status |")
lines.append(f"|-----------|-----------------|--------|")
lines.append(f"| **gzip -9** | {win_gzip:.6f} | Target |")
lines.append(f"| **xz -9**   | {win_xz:.6f} | Target |")
lines.append(f"| **Cubrim (current best)** | {best['aggregate']:.6f} | {'WIN' if best['aggregate'] <= win_gzip else 'BEHIND'} |")
lines.append("")
gap = best['aggregate'] - win_gzip
lines.append(f"**Gap to gzip win:** {gap:+.6f} (current best {best['aggregate']:.6f} vs target {win_gzip:.6f})")
lines.append("")
lines.append("## Current Best")
lines.append("")
lines.append(f"| Field | Value |")
lines.append(f"|-------|-------|")
lines.append(f"| Scheme | `{best['scheme']}` |")
lines.append(f"| Aggregate | **{best['aggregate']:.6f}** |")
lines.append(f"| Code SHA | `{best['code_sha'][:12]}...` |")
lines.append(f"| Corpus SHA256 | `{best['corpus_manifest_sha256'][:16]}...` |")
lines.append(f"| Run Log Ref | `{best.get('run_log_ref', 'n/a')}` |")
lines.append("")

if best.get("per_file"):
    lines.append("### Per-File Baseline (non-regression bound for AC-5 gate)")
    lines.append("")
    lines.append("| File | Raw Bytes | BWT Bytes | T4 Bytes | Best |")
    lines.append("|------|-----------|-----------|----------|------|")
    for pf in best["per_file"]:
        lines.append(
            f"| {pf['file']} | {pf['size_bytes']} | {pf.get('bwt_bytes','?')} "
            f"| {pf.get('t4_bytes','?')} | **{pf['bytes']}** |"
        )
    lines.append("")

lines.append("## Run History")
lines.append("")
if not runs:
    lines.append("_No runs recorded yet._")
else:
    lines.append("| Run ID | Date | Scheme | Aggregate | vs T4 | vs gzip | vs xz | Verdict | Merged |")
    lines.append("|--------|------|--------|-----------|-------|---------|-------|---------|--------|")
    for run in reversed(runs):  # most recent first
        merged = "yes" if run.get("merged") else "no"
        verdict = run.get("verdict", "?")
        verdict_md = f"**{verdict}**" if verdict == "GO" else verdict
        lines.append(
            f"| `{run.get('run_id','?')[:20]}` | {run.get('date','?')} "
            f"| {run.get('candidate','?')} | {run.get('aggregate','?'):.6f} "
            f"| {run.get('vs_t4','?'):+.6f} | {run.get('vs_gzip','?'):+.6f} "
            f"| {run.get('vs_xz','?'):+.6f} | {verdict_md} | {merged} |"
        )

lines.append("")
lines.append("## Corpus (frozen)")
lines.append("")
lines.append("10 files, 117032 raw bytes total. Manifest SHA256: "
             f"`{best['corpus_manifest_sha256'][:24]}...`")
lines.append("")
lines.append("---")
lines.append("_This file is auto-generated from `docs/leaderboard/cubrim-leaderboard.json`._")
lines.append("_Do not edit manually — run `gen-leaderboard-md.sh` to regenerate._")

print("\n".join(lines))
PYEOF
)"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "gen-leaderboard-md: dry-run — output preview:"
    echo "$MD"
    echo ""
    echo "gen-leaderboard-md: would write to $OUTPUT_PATH"
    exit 0
fi

printf '%s\n' "$MD" > "$OUTPUT_PATH"
echo "gen-leaderboard-md: written to $OUTPUT_PATH"
exit 0
