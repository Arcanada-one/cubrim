#!/usr/bin/env python3
"""CUBR-0036: add 7z(LZMA2) + rar columns to the existing world-benchmark.json.

Real-numbers mandate: existing cubrim/gzip/bzip2/xz/zstd/brotli/lz4/ppmd numbers
and code_sha are preserved byte-for-byte from the deployed JSON. Only the two new
archivers are measured here; ranks + aggregates are recomputed with the exact
sum-bytes method aggregate.py uses, with a self-check that the 8 original
aggregates reproduce identically before anything is written.
"""
import json, os, subprocess, sys, shutil

ROOT = "/home/dev/cubrim-worldbench"
RAR = f"{ROOT}/tools/rar/rar"
SRC = "/home/dev/cubr-0036-work/cubrim-site/data/world-benchmark.json"
TMP = f"{ROOT}/tmp/rar7z"
os.makedirs(TMP, exist_ok=True)

NEW = ["7z", "rar"]  # appended after ppmd

def corpus_path(corpus, file):
    return f"{ROOT}/corpora/enwik8" if corpus == "enwik8" else f"{ROOT}/corpora/{corpus}/{file}"

def measure_7z(src, tag):
    out = f"{TMP}/{tag}.7z"
    if os.path.exists(out): os.remove(out)
    subprocess.run(["7z", "a", "-t7z", "-m0=LZMA2", "-mx=9", "-bso0", "-bsp0", "-bd", out, src],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sz = os.path.getsize(out); os.remove(out)
    return sz

def measure_rar(src, tag):
    out = f"{TMP}/{tag}.rar"
    if os.path.exists(out): os.remove(out)
    # -m5 best, -ep store no path, -o+ overwrite, -idq quiet
    subprocess.run([RAR, "a", "-m5", "-ep", "-o+", "-idq", out, src],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sz = os.path.getsize(out); os.remove(out)
    return sz

def agg(files, archs, pred):
    out = {}
    for a in archs:
        to = tc = 0
        for r in files:
            if not pred(r): continue
            c = r["comp"].get(a)
            if c is None: continue
            to += r["orig"]; tc += c
        out[a] = round(tc / to, 6) if to else None
    return out

def main():
    d = json.load(open(SRC))
    orig_archs = list(d["archiver_order"])  # 8
    files = d["files"]

    # --- self-check: recompute the 8-archiver overall aggregate, compare to stored ---
    chk = agg(files, orig_archs, lambda r: True)
    for a in orig_archs:
        stored = d["aggregate_overall"][a]
        if abs((chk[a] or 0) - (stored or 0)) > 1e-6:
            print(f"SELF-CHECK FAIL {a}: recomputed {chk[a]} != stored {stored}", file=sys.stderr)
            sys.exit(2)
    print("self-check OK: 8-archiver aggregate reproduces stored values")

    # --- measure 7z + rar for every file ---
    for r in files:
        c, f = r["corpus"], r["file"]
        src = corpus_path(c, f)
        if not os.path.isfile(src):
            print(f"MISSING corpus file: {src}", file=sys.stderr); sys.exit(3)
        tag = f"{c}__{f}"
        s7 = measure_7z(src, tag)
        sr = measure_rar(src, tag)
        r["comp"]["7z"] = s7
        r["comp"]["rar"] = sr
        r["ratio"]["7z"] = round(s7 / r["orig"], 6)
        r["ratio"]["rar"] = round(sr / r["orig"], 6)
        print(f"{tag}: 7z={s7} ({r['ratio']['7z']})  rar={sr} ({r['ratio']['rar']})", flush=True)

    archs = orig_archs + NEW  # 10

    # --- recompute cubrim_rank + n_archivers over all archivers present ---
    for r in files:
        vals = sorted([(a, r["ratio"][a]) for a in archs if r["ratio"].get(a) is not None],
                      key=lambda x: x[1])
        order = [a for a, _ in vals]
        r["cubrim_rank"] = order.index("cubrim") + 1 if "cubrim" in order else None
        r["n_archivers"] = len(order)

    # --- recompute aggregates ---
    CORP = d["corpora"]
    types = sorted(set(r["type"] for r in files))
    d["aggregate_by_corpus"] = {c: agg(files, archs, lambda r, c=c: r["corpus"] == c) for c in CORP}
    d["aggregate_by_type"] = {t: agg(files, archs, lambda r, t=t: r["type"] == t) for t in types}
    d["aggregate_overall"] = agg(files, archs, lambda r: True)

    # --- metadata: preserve code_sha; extend archivers + order ---
    d["archiver_order"] = archs
    d["archivers"]["7z"] = "-m0=LZMA2 -mx9"
    d["archivers"]["rar"] = "a -m5"
    # keep ppmd label "7z -m0=PPMd", code_sha 317a32..., task, generated unchanged

    out = f"{ROOT}/results/world-benchmark-cubr0036.json"
    json.dump(d, open(out, "w"), indent=2)
    print("\noverall:", json.dumps(d["aggregate_overall"]))
    print("wrote", out)

if __name__ == "__main__":
    main()
