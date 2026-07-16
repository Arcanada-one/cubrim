#!/usr/bin/env bash
# AH-15 pair-corpus replica: REAL versioned (old,new) blob pairs from the
# workspace git history — same source and selection as the research probe
# (REPO=/home/dev/arcanada, per-class caps). Writes pairs/NNNN/{old,new}
# + manifest.json with sha256 provenance.
set -euo pipefail
OUT="${1:?usage: extract_git_pairs.sh <out-dir> [repo] [max-pairs]}"
REPO="${2:-/home/dev/arcanada}"
MAX="${3:-339}"
python3 - "$OUT" "$REPO" "$MAX" <<'PY'
import hashlib, json, os, subprocess, sys
out, repo, cap = sys.argv[1], sys.argv[2], int(sys.argv[3])
def git(*a, binary=False):
    r = subprocess.run(['git', '-C', repo] + list(a), capture_output=True)
    return r.stdout if binary else r.stdout.decode('utf-8', 'replace')
log = git('log', '--diff-filter=M', '--pretty=%H', '-n', '4000')
pairs, seen = [], set()
for commit in log.split():
    if len(pairs) >= cap: break
    raw = git('diff-tree', '-r', '--no-renames', '--diff-filter=M', commit)
    for line in raw.splitlines():
        if len(pairs) >= cap: break
        parts = line.split()
        if len(parts) < 6: continue
        old_sha, new_sha, path = parts[2], parts[3], parts[5]
        if (old_sha, new_sha) in seen or old_sha.startswith('0'*7): continue
        seen.add((old_sha, new_sha))
        old = git('cat-file', 'blob', old_sha, binary=True)
        new = git('cat-file', 'blob', new_sha, binary=True)
        if not (64 <= len(old) <= 2_000_000 and 64 <= len(new) <= 2_000_000): continue
        pairs.append((old, new, path))
os.makedirs(out, exist_ok=True)
manifest = {"repo": repo, "pairs": []}
for i, (old, new, path) in enumerate(pairs):
    d = os.path.join(out, f"{i:04d}"); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "old"), "wb").write(old)
    open(os.path.join(d, "new"), "wb").write(new)
    manifest["pairs"].append({"i": i, "path": path,
        "old_sha256": hashlib.sha256(old).hexdigest(),
        "new_sha256": hashlib.sha256(new).hexdigest()})
json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"))
print(f"extracted {len(pairs)} real git pairs from {repo}")
PY
