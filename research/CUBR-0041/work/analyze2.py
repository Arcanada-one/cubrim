#!/usr/bin/env python3
"""CUBR-0041 definitive analysis. Treats the rANS family as ONE competitive-min rail
(byte-identity verified empirically). Computes current==rail, oracle==per-file best of
{rail, each non-rANS scheme}, the specialization ceiling, and the per-file type map vs refs.
Only rt_ok=true rows count. Corpus: the 12-file world corpus (243,004,774 B), named at every number."""
import collections
RANS = {"bwt-rans","order2-rans","bwt-adaptive","bwt-ctxmix","bwt-geomix","lz-rans"}
NONRANS_DISTINCT = ["bitpack-fixed","rle-codes","entropy","entropy-context","entropy-context-2","bwt-entropy"]

rows = collections.defaultdict(dict); orig_of = {}
for ln in open("oracle.tsv"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 7 or p[5] != "true": continue
    scheme, file, orig, comp = p[0], p[1], int(p[2]), int(p[3])
    if comp <= 0: continue
    rows[file][scheme] = comp; orig_of[file] = orig
files = sorted(rows); TOTAL = sum(orig_of[f] for f in files)

def rail_comp(f):  # competitive-min rail = min over available rANS schemes (all identical)
    vals = [rows[f][s] for s in RANS if s in rows[f]]
    return min(vals) if vals else None

print(f"=== 12-file WORLD corpus, {TOTAL:,} B ===\n")
print("per-file:  rANS-rail   best-nonrANS(scheme)   oracle-pick   -> does a non-rANS EVER beat the rail?")
rail_num = 0; oracle_num = 0; flips = []
for f in files:
    rc = rail_comp(f)
    nonr = {s: rows[f][s] for s in NONRANS_DISTINCT if s in rows[f]}
    best_nr_s = min(nonr, key=nonr.get) if nonr else None
    best_nr = nonr[best_nr_s] if best_nr_s else None
    # oracle pick = smallest of {rail, all non-rANS}
    cand = {}
    if rc is not None: cand["rANS-rail"] = rc
    cand.update(nonr)
    o_s = min(cand, key=cand.get); o_c = cand[o_s]
    rail_num += rc; oracle_num += o_c
    beat = "NO"
    if best_nr is not None and rc is not None and best_nr < rc:
        beat = f"YES nonrANS {best_nr_s} {best_nr} < rail {rc}"; flips.append(f)
    print(f"  {f:26s} rail={rc/orig_of[f]:.4f}  bestNR={best_nr/orig_of[f]:.4f}({best_nr_s})  oracle={o_c/orig_of[f]:.4f}({o_s})  beat={beat}")

rail_ov = rail_num/TOTAL; oracle_ov = oracle_num/TOTAL
print(f"\n=== CURRENT competitive-min (rANS rail), 12-file world corpus = {rail_ov:.6f} ===")
print(f"=== ORACLE (ideal per-file pick over all 12 existing schemes)   = {oracle_ov:.6f} ===")
print(f"=== SPECIALIZATION CEILING (existing schemes) = {rail_ov-oracle_ov:.6f} abs  ({100*(rail_ov-oracle_ov)/rail_ov:.3f}% relative) ===")
print(f"=== files where a non-rANS scheme beats the rail: {flips if flips else 'NONE'} ===")

# references on the SAME 12-file corpus
ref = collections.defaultdict(dict)
for ln in open("ref.tsv"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 5: continue
    ref[p[0]][p[1]] = (int(p[3]), int(p[2]))
print("\n=== reference compressors, SAME 12-file world corpus (size-weighted overall) ===")
comp_tbl = {"cubrim(rail/oracle)": rail_ov}
for tool in ref:
    num = sum(c for c,o in ref[tool].values()); den = sum(o for c,o in ref[tool].values())
    comp_tbl[tool] = num/den
for name,ov in sorted(comp_tbl.items(), key=lambda x:x[1]):
    print(f"  {name:22s} {ov:.6f}")

print("\n=== TYPE MAP: per-file cubrim-best vs ppmd vs xz vs brotli (ratios) ===")
for f in files:
    rc = rail_comp(f)/orig_of[f]
    pp = ref.get('ppmd',{}).get(f); xz = ref.get('xz',{}).get(f); br = ref.get('brotli',{}).get(f)
    ppr = pp[0]/pp[1] if pp else float('nan'); xzr = xz[0]/xz[1] if xz else float('nan'); brr = br[0]/br[1] if br else float('nan')
    leader = min([('ppmd',ppr),('xz',xzr),('brotli',brr)], key=lambda x:x[1])
    gap = 100*(rc-leader[1])/leader[1]
    print(f"  {f:26s} cubrim={rc:.4f}  ppmd={ppr:.4f} xz={xzr:.4f} brotli={brr:.4f}  leader={leader[0]}({leader[1]:.4f})  cubrim gap={gap:+.1f}%")
