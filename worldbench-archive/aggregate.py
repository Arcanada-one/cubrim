#!/usr/bin/env python3
"""CUBR-0034 aggregator: merge cubrim + std results -> table, aggregates, publication JSON, markdown."""
import json, glob, os, subprocess, datetime, re

def _loadj(p):
    s = open(p).read()
    s = re.sub(r'([:,])(\.[0-9])', r'\g<1>0\g<2>', s)  # fix bc's leading-dot numbers (.5 -> 0.5)
    s = re.sub(r'([:,])0([0-9])', r'\g<1>\g<2>', s)    # fix spurious leading zero (01.2 -> 1.2)
    return json.loads(s)

ROOT = "/home/dev/cubrim-worldbench"
ARCHS = ["cubrim", "gzip", "bzip2", "xz", "zstd", "brotli", "lz4", "ppmd"]
CORPUS_ORDER = ["silesia", "enwik8", "canterbury"]

def load():
    rows = {}  # (corpus,file) -> dict
    for p in glob.glob(f"{ROOT}/results/cubrim/*.json"):
        d = _loadj(p)
        k = (d["corpus"], d["file"])
        rows.setdefault(k, {"corpus": d["corpus"], "file": d["file"], "type": d["type"], "orig": d["orig"]})
        rows[k]["cubrim_comp"] = d["comp"]
        rows[k]["cubrim_ratio"] = d["ratio"]
        rows[k]["cubrim_rt"] = d["rt"]
        rows[k]["cubrim_comp_s"] = d.get("comp_s")
        rows[k]["cubrim_decomp_s"] = d.get("decomp_s")
    for p in glob.glob(f"{ROOT}/results/std/*.json"):
        d = _loadj(p)
        k = (d["corpus"], d["file"])
        rows.setdefault(k, {"corpus": d["corpus"], "file": d["file"], "type": d["type"], "orig": d["orig"]})
        for a in ["gzip", "bzip2", "xz", "zstd", "brotli", "lz4", "ppmd"]:
            rows[k][f"{a}_comp"] = d.get(f"{a}_comp")
            rows[k][f"{a}_ratio"] = d.get(f"{a}_ratio")
    return rows

def code_sha():
    try:
        return subprocess.check_output(["git", "-C", "/home/dev/cubrim-h19", "rev-parse", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"

def agg(rows, pred):
    """sum-bytes aggregate ratio per archiver over rows matching pred."""
    out = {}
    for a in ARCHS:
        to = tc = 0
        for r in rows:
            if not pred(r):
                continue
            c = r.get(f"{a}_comp")
            if c is None:
                continue
            to += r["orig"]; tc += c
        out[a] = round(tc / to, 6) if to else None
    return out

def main():
    rows = list(load().values())
    rows.sort(key=lambda r: (CORPUS_ORDER.index(r["corpus"]) if r["corpus"] in CORPUS_ORDER else 9, r["file"]))
    types = sorted(set(r["type"] for r in rows))

    by_corpus = {c: agg(rows, lambda r, c=c: r["corpus"] == c) for c in CORPUS_ORDER}
    overall = agg(rows, lambda r: True)
    by_type = {t: agg(rows, lambda r, t=t: r["type"] == t) for t in types}

    # cubrim ranking per file
    def rank(r):
        vals = [(a, r.get(f"{a}_ratio")) for a in ARCHS if r.get(f"{a}_ratio") is not None]
        vals.sort(key=lambda x: x[1])
        order = [a for a, _ in vals]
        return order.index("cubrim") + 1 if "cubrim" in order else None, len(order)

    pub = {
        "task": "CUBR-0034",
        "title": "World benchmark — Cubrim vs standard archivers",
        "generated": DATESTAMP,
        "code_sha": code_sha(),
        "method": "ratio = compressed/original (lower is better); RT byte-exact verified for cubrim",
        "archivers": {
            "cubrim": "competitive (built-in scheme selection)",
            "gzip": "-9", "bzip2": "-9", "xz": "-9e", "zstd": "--ultra -22",
            "brotli": "-q 11", "lz4": "-12", "ppmd": "7z -m0=PPMd",
        },
        "archiver_order": ARCHS,
        "corpora": CORPUS_ORDER,
        "files": [],
        "aggregate_by_corpus": by_corpus,
        "aggregate_by_type": by_type,
        "aggregate_overall": overall,
    }
    for r in rows:
        rk, n = rank(r)
        fr = {"corpus": r["corpus"], "file": r["file"], "type": r["type"], "orig": r["orig"],
              "cubrim_rt": r.get("cubrim_rt"), "cubrim_rank": rk, "n_archivers": n, "ratio": {}, "comp": {}}
        for a in ARCHS:
            fr["ratio"][a] = r.get(f"{a}_ratio")
            fr["comp"][a] = r.get(f"{a}_comp")
        pub["files"].append(fr)

    json.dump(pub, open(f"{ROOT}/results/CUBR-0034-benchmark.json", "w"), indent=2)
    print("wrote results/CUBR-0034-benchmark.json")
    print("overall:", overall)
    return pub

DATESTAMP = "2026-06-25"
if __name__ == "__main__":
    main()
