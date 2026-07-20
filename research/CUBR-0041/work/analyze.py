#!/usr/bin/env python3
"""CUBR-0041 oracle analysis. Reads oracle.tsv (RT-verified cubrim sweep) + ref.tsv
(reference compressors). Computes size-weighted overalls for:
  - each single cubrim scheme applied globally,
  - the per-file ORACLE (ideal per-type dispatcher over existing schemes),
  - each reference tool.
Only rt_ok=true cubrim rows count (an invalid RT => number invalid, excluded).
Prints per-file best-scheme map + the specialization-ceiling number.
"""
import sys, collections

ORACLE = sys.argv[1] if len(sys.argv) > 1 else "oracle.tsv"
REF    = sys.argv[2] if len(sys.argv) > 2 else "ref.tsv"

# --- cubrim oracle rows: scheme file orig comp ratio rt_ok ms
rows = collections.defaultdict(dict)   # file -> scheme -> (comp, ratio, orig)
orig_of = {}
with open(ORACLE) as f:
    for ln in f:
        p = ln.rstrip("\n").split("\t")
        if len(p) < 7: continue
        scheme, file, orig, comp, ratio, rt_ok, ms = p[:7]
        orig = int(orig);
        if rt_ok != "true":   # invalid round-trip -> not a real measurement
            continue
        comp = int(comp)
        if comp <= 0: continue
        rows[file][scheme] = (comp, comp/orig, orig)
        orig_of[file] = orig

files = sorted(rows)
TOTAL = sum(orig_of[f] for f in files)

# distinct cubrim schemes seen
schemes = sorted({s for f in files for s in rows[f]})

def weighted_overall_single(scheme):
    """size-weighted ratio if `scheme` applied to every file (skip files where it has no valid row)."""
    num = den = 0
    missing = []
    for f in files:
        if scheme in rows[f]:
            num += rows[f][scheme][0]; den += orig_of[f]
        else:
            missing.append(f)
    return (num/den if den else None, missing)

def oracle_overall():
    num = 0; picks = {}
    for f in files:
        best_s, best = min(rows[f].items(), key=lambda kv: kv[1][0])
        num += best[0]; picks[f] = (best_s, best[1])
    return num/TOTAL, picks

print(f"=== corpus: {len(files)} files, {TOTAL} bytes ===")
for f in files:
    print(f"  {f:28s} {orig_of[f]:>11,} B  weight={orig_of[f]/TOTAL:.4f}")

print("\n=== per-file valid schemes + best (oracle pick) ===")
oc, picks = oracle_overall()
for f in files:
    rr = sorted(rows[f].items(), key=lambda kv: kv[1][1])
    bs, br = picks[f]
    line = "  ".join(f"{s}={rows[f][s][1]:.4f}" for s,_ in rr[:4])
    print(f"  {f:28s} BEST={bs:16s} {br:.4f}  | {line}")

print("\n=== size-weighted overall per single global scheme ===")
res = []
for s in schemes:
    ov, missing = weighted_overall_single(s)
    res.append((ov, s, missing))
for ov, s, missing in sorted(res, key=lambda x: (x[0] is None, x[0])):
    m = f"  (MISSING {len(missing)}: {','.join(missing)})" if missing else ""
    print(f"  {s:18s} {ov:.6f}{m}" if ov is not None else f"  {s:18s} n/a{m}")

print(f"\n=== ORACLE (ideal per-type dispatcher over existing schemes) = {oc:.6f} ===")

# current competitive-min proxy = order2-rans (per research-log: benchmark == explicit order2-rans)
cur, _ = weighted_overall_single("order2-rans")
if cur:
    print(f"=== current competitive-min proxy (order2-rans global) = {cur:.6f} ===")
    print(f"=== specialization ceiling (existing schemes) = {cur-oc:.6f} abs  ({100*(cur-oc)/cur:.3f}% relative) ===")

# --- reference tools
print("\n=== reference compressors (same corpus) ===")
ref = collections.defaultdict(dict)
try:
    with open(REF) as f:
        for ln in f:
            p = ln.rstrip("\n").split("\t")
            if len(p) < 5: continue
            tool, file, orig, comp, ratio = p[:5]
            ref[tool][file] = (int(comp), int(orig))
    for tool in sorted(ref):
        num = sum(c for c,o in ref[tool].values())
        den = sum(o for c,o in ref[tool].values())
        nfiles = len(ref[tool])
        print(f"  {tool:10s} overall={num/den:.6f}  ({nfiles} files)")
except FileNotFoundError:
    print("  (ref.tsv not found)")
