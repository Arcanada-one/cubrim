#!/usr/bin/env python3
"""Generate CUBR-0034-world-benchmark.md tables from the benchmark JSON (real numbers only)."""
import json
ROOT = "/home/dev/cubrim-worldbench"
d = json.load(open(f"{ROOT}/results/CUBR-0034-benchmark.json"))
A = d["archiver_order"]
HDR = {"cubrim":"cubrim","gzip":"gzip","bzip2":"bzip2","xz":"xz","zstd":"zstd","brotli":"brotli","lz4":"lz4","ppmd":"ppmd"}

def cell(v):
    return f"{v:.4f}" if v is not None else "—"

def best_of(r):
    bv = min(v for v in r.values() if v is not None)
    ba = [a for a in A if r[a] == bv][0]
    return ba, bv

def bold_row(r):
    ba, bv = best_of(r)
    out = []
    for a in A:
        v = r[a]
        s = cell(v)
        if a == ba: s = f"**{s}**"
        elif a == "cubrim": s = f"_{s}_"
        out.append(s)
    return out

lines = []
ap = lines.append

# Per-file table
ap("| file | type | size | " + " | ".join(HDR[a] for a in A) + " | cubrim rank |")
ap("|---|---|---:|" + "---:|"*len(A) + "---|")
for f in d["files"]:
    r = f["ratio"]
    row = bold_row(r)
    sz = f"{f['orig']/1024:.0f} KB" if f['orig'] < 1024*1024 else f"{f['orig']/1024/1024:.1f} MB"
    ap(f"| {f['file']} | {f['type']} | {sz} | " + " | ".join(row) + f" | #{f['cubrim_rank']}/{f['n_archivers']} |")

ap("")
ap("### Aggregate by data type (sum-bytes ratio)")
ap("")
ap("| type | " + " | ".join(HDR[a] for a in A) + " | cubrim gap vs best |")
ap("|---|" + "---:|"*len(A) + "---|")
for t, r in sorted(d["aggregate_by_type"].items()):
    ba, bv = best_of(r)
    gap = (r["cubrim"]-bv)/bv*100
    ap(f"| {t} | " + " | ".join(bold_row(r)) + f" | +{gap:.1f}% (vs {ba}) |")

ap("")
ap("### Aggregate by corpus (sum-bytes ratio)")
ap("")
ap("| corpus | " + " | ".join(HDR[a] for a in A) + " |")
ap("|---|" + "---:|"*len(A) + "|")
for c, r in d["aggregate_by_corpus"].items():
    ap(f"| {c} | " + " | ".join(bold_row(r)) + " |")
ap("")
ap("### Overall (all 24 files, sum-bytes ratio)")
ap("")
ap("| | " + " | ".join(HDR[a] for a in A) + " |")
ap("|---|" + "---:|"*len(A) + "|")
ap("| **overall** | " + " | ".join(bold_row(d["aggregate_overall"])) + " |")

open(f"{ROOT}/results/_tables.md", "w").write("\n".join(lines))
print("wrote results/_tables.md")
