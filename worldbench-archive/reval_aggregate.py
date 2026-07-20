#!/usr/bin/env python3
"""CUBR-0034 re-validation aggregator: champion (bwt-rans) vs default vs std archivers on the world corpus."""
import json, glob, re, subprocess
ROOT = "/home/dev/cubrim-worldbench"
STD = ["gzip", "bzip2", "xz", "zstd", "brotli", "lz4", "ppmd"]
ALL = ["cubrim"] + STD  # cubrim = champion
CORPUS_ORDER = ["silesia", "enwik8", "canterbury"]

def lj(p):
    s = open(p).read()
    s = re.sub(r'([:,])(\.[0-9])', r'\g<1>0\g<2>', s)
    s = re.sub(r'([:,])0([0-9])', r'\g<1>\g<2>', s)
    return json.loads(s)

def load():
    rows = {}
    for p in glob.glob(f"{ROOT}/results/cubrim_champ/*.json"):
        d = lj(p); k = (d["corpus"], d["file"])
        rows.setdefault(k, {"corpus": d["corpus"], "file": d["file"], "type": d["type"], "orig": d["orig"]})
        rows[k]["cubrim_comp"] = d["comp"]; rows[k]["cubrim_ratio"] = d["ratio"]
        rows[k]["cubrim_rt"] = d["rt"]; rows[k]["mode"] = d.get("mode_name"); rows[k]["comp_s"] = d.get("comp_s")
    for p in glob.glob(f"{ROOT}/results/cubrim/*.json"):  # buggy default
        d = lj(p); k = (d["corpus"], d["file"])
        if k in rows: rows[k]["default_ratio"] = d["ratio"]; rows[k]["default_comp"] = d["comp"]
    for p in glob.glob(f"{ROOT}/results/std/*.json"):
        d = lj(p); k = (d["corpus"], d["file"])
        for a in STD:
            rows[k][f"{a}_comp"] = d.get(f"{a}_comp"); rows[k][f"{a}_ratio"] = d.get(f"{a}_ratio")
    return rows

def agg(rows, pred, arch):
    to = tc = 0
    for r in rows:
        if not pred(r): continue
        c = r.get(f"{arch}_comp")
        if c is None: continue
        to += r["orig"]; tc += c
    return round(tc/to, 6) if to else None

def code_sha():
    try: return subprocess.check_output(["git","-C","/home/dev/cubrim-h19","rev-parse","HEAD"]).decode().strip()
    except Exception: return "unknown"

def main():
    rows = list(load().values())
    rows.sort(key=lambda r: (CORPUS_ORDER.index(r["corpus"]) if r["corpus"] in CORPUS_ORDER else 9, r["file"]))
    types = sorted(set(r["type"] for r in rows))
    def aggset(pred): return {a: agg(rows, pred, a) for a in ALL}
    out = {
        "task":"CUBR-0034-revalidation","generated":"2026-06-25","code_sha":code_sha(),
        "note":"cubrim column = CHAMPION rail (--value-scheme bwt-rans); 'default' = buggy BitpackFixed CLI default",
        "by_corpus":{c: aggset(lambda r,c=c: r["corpus"]==c) for c in CORPUS_ORDER},
        "by_type":{t: aggset(lambda r,t=t: r["type"]==t) for t in types},
        "overall": aggset(lambda r: True),
        "files":[],
    }
    # also default overall
    out["default_overall"] = agg(rows, lambda r:True, "default")
    for r in rows:
        vals=[(a,r.get(f"{a}_ratio")) for a in ALL if r.get(f"{a}_ratio") is not None]
        vals.sort(key=lambda x:x[1]); order=[a for a,_ in vals]
        rank=order.index("cubrim")+1 if "cubrim" in order else None
        out["files"].append({"corpus":r["corpus"],"file":r["file"],"type":r["type"],"orig":r["orig"],
            "mode":r.get("mode"),"cubrim_rt":r.get("cubrim_rt"),"cubrim_rank":rank,"n":len(order),
            "default_ratio":r.get("default_ratio"),
            "ratio":{a:r.get(f"{a}_ratio") for a in ALL}})
    json.dump(out, open(f"{ROOT}/results/revalidation.json","w"), indent=2)
    # console summary
    print("OVERALL champion:", out["overall"])
    print("OVERALL default :", out["default_overall"])
    print("modes:", {})
    from collections import Counter
    print("modes:", dict(Counter(r.get("mode") for r in rows)))
    print("RT:", dict(Counter(r.get("cubrim_rt") for r in rows)))
    for t in types:
        rr=out["by_type"][t]; bv=min(v for v in rr.values() if v); ba=[a for a in ALL if rr[a]==bv][0]
        print(f"  {t:9} cubrim={rr['cubrim']:.4f} best={ba} {bv:.4f} gap=+{(rr['cubrim']-bv)/bv*100:.1f}%")

if __name__=="__main__": main()
