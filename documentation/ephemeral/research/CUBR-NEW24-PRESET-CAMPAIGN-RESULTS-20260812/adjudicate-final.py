#!/usr/bin/env python3
"""Adjudicate NEW-24 preset campaign C-1..C-4 + the pre-committed adoption rule.

Inputs are the campaign's own artefacts only: journal.jsonl (48 cells), the phaseC
corpus manifest, meta36.psv (Phase C DB snapshot), and the container-mode byte read
off each control archive. No figure is carried over from the partial-journal record.
"""
import json
import statistics as st
import sys

S = "/tmp/claude-1002/-home-dev--worktrees-arcanada-CUBRIM-PROGRAM/8fa4c7fe-5add-4526-871d-6642d37e317d/scratchpad"

# container mode byte (offset 5) of each control archive, read on dev-ai
MODE = {
    "alice29.txt": 16, "asyoulik.txt": 16, "cp.html": 16, "dickens": 16,
    "fields.c": 16, "grammar.lsp": 16, "kennedy.xls": 16, "lcet10.txt": 16,
    "mozilla": 16, "mr": 17, "nci": 16, "ooffice": 8, "osdb": 16,
    "plrabn12.txt": 16, "ptt5": 17, "reymont": 16, "samba": 16, "sao": 13,
    "sum": 16, "webster": 16, "xargs.1": 16, "xml": 16, "x-ray": 17,
}

CANTERBURY = set()
CLASS, ORIG, CORPUS = {}, {}, {}
for ln in open(f"{S}/corpus_manifest.tsv"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 4 or p[0] == "corpus":
        continue
    CORPUS[p[1]] = p[0]
    CLASS[p[1]] = p[2]
    ORIG[p[1]] = int(p[3])
    if p[0] == "canterbury":
        CANTERBURY.add(p[1])

RATIOS, RANK = {}, {}
for ln in open(f"{S}/meta36.psv"):
    p = ln.rstrip("\n").split("|")
    if len(p) < 5:
        continue
    RATIOS[p[0]] = json.loads(p[3])
    RANK[p[0]] = int(p[4])

cells = {}
voids = []
for ln in open(f"{S}/journal.jsonl"):
    ln = ln.strip()
    if not ln:
        continue
    r = json.loads(ln)
    ev = r.get("event")
    if ev == "void":
        voids.append((r["cell"], r["reason"]))
        continue
    if "cell" not in ev if False else "cell" not in r:
        continue
    c = cells.setdefault(r["cell"], {"walls": [], "rss": []})
    if ev == "encoded":
        c["bytes"], c["sha"], c["enc_s"] = r["bytes"], r["sha"], r["enc_s"]
    elif ev == "decode_ok":
        c["walls"].append(r["wall_s"])
        c["rss"].append(r["rss_kib"])
    elif ev == "cell_done":
        c["done"] = True

done = {k: v for k, v in cells.items() if v.get("done")}
files = sorted({k.rsplit("/", 1)[0] for k in done})
arms = lambda f: {k.rsplit("/", 1)[1] for k in done if k.startswith(f + "/")}
paired = [f for f in files if {"full", "f12"} <= arms(f)]

print(f"cells done={len(done)}  files paired={len(paired)}  voids={voids}")
print()

cm2 = [f for f in paired if MODE[f] == 16]
noncm2 = [f for f in paired if MODE[f] != 16]
print(f"CM2-won (mode 16): {len(cm2)} -> {cm2}")
print(f"non-CM2:           {len(noncm2)} -> {[(f, MODE[f]) for f in noncm2]}")
print()

med = lambda xs: st.median(xs)


def cell(f, a):
    return done[f"{f}/{a}"]


# ---------------- C-1 : scope of effect on non-CM2 files ----------------
print("=" * 78)
print("C-1  non-CM2 files: F12 archive byte-identical to full, decode wall within +/-10%")
print("=" * 78)
c1_rows, c1_pass = [], True
for f in noncm2:
    a, b = cell(f, "full"), cell(f, "f12")
    same = a["sha"] == b["sha"]
    wa, wb = med(a["walls"]), med(b["walls"])
    dpct = (wb - wa) / wa * 100.0
    ok = same and abs(dpct) <= 10.0
    c1_pass &= ok
    c1_rows.append((f, MODE[f], same, a["bytes"], b["bytes"], wa, wb, dpct, ok))
    print(f"  {f:<14} mode {MODE[f]:<3} sha_identical={str(same):<5} "
          f"bytes {a['bytes']:>10} vs {b['bytes']:>10}  "
          f"wall {wa:>8.2f}s vs {wb:>8.2f}s  {dpct:+6.1f}%  {'PASS' if ok else 'FAIL'}")
print(f"  => C-1 {'PASS' if c1_pass else 'FAIL'}")
print()

# ---------------- C-2 : density on CM2-won files ----------------
print("=" * 78)
print("C-2  CM2-won: ratio worsening <= +5% text/code, +6% exe, +10% database")
print("     and cubrim meta-36 rank-1 survives on >= 80% of files it currently leads")
print("=" * 78)
THRESH = {"text": 5.0, "code": 5.0, "exe": 6.0, "database": 10.0,
          "image": None, "binary": None}
worse = {}
for f in cm2:
    a, b = cell(f, "full"), cell(f, "f12")
    w = (b["bytes"] - a["bytes"]) / a["bytes"] * 100.0
    worse[f] = w
    tag = "canterbury(excluded from class claim)" if f in CANTERBURY else ""
    print(f"  {f:<14} {CLASS[f]:<9} {a['bytes']:>10} -> {b['bytes']:>10}  {w:+6.2f}%  {tag}")

print()
print("  per-class worst case, Silesia only (canterbury excluded per protocol):")
c2_density = True
byclass = {}
for f in cm2:
    if f in CANTERBURY:
        continue
    byclass.setdefault(CLASS[f], []).append((f, worse[f]))
for cl, rows in sorted(byclass.items()):
    wf, wv = max(rows, key=lambda r: r[1])
    th = THRESH.get(cl)
    ok = th is None or wv <= th
    c2_density &= ok
    print(f"    {cl:<9} worst {wv:+6.2f}% ({wf})  threshold "
          f"{('<= +%.0f%%' % th) if th else 'n/a'}  {'PASS' if ok else 'FAIL' if th else '-'}")

# lead survival: cubrim rank-1 among archivers, before vs after
print()
print("  lead survival (files cubrim leads at meta-36, does it still lead with F12 bytes):")
led = [f for f in cm2 if RANK.get(f) == 1]
survived, lost = [], []
for f in led:
    r = dict(RATIOS[f])
    base = r["cubrim"]
    new = base * (1 + worse[f] / 100.0)
    others = min(v for k, v in r.items() if k != "cubrim")
    (survived if new < others else lost).append((f, base, new, others))
rate = len(survived) / len(led) * 100.0 if led else 0.0
c2_lead = rate >= 80.0
for f, base, new, oth in sorted(lost):
    print(f"    LOST  {f:<14} cubrim {base:.6f} -> {new:.6f}  vs best-other {oth:.6f}")
print(f"    survived {len(survived)}/{len(led)} = {rate:.1f}%  (need >= 80%)  "
      f"{'PASS' if c2_lead else 'FAIL'}")

# M8S arm on nci/osdb
print()
print("  M8S arm (nci, osdb): worsening <= +8%")
c2_m8s = True
for f in ("nci", "osdb"):
    if f"{f}/m8s" in done:
        a, m = cell(f, "full"), cell(f, "m8s")
        w = (m["bytes"] - a["bytes"]) / a["bytes"] * 100.0
        ok = w <= 8.0
        c2_m8s &= ok
        print(f"    {f:<6} {a['bytes']:>10} -> {m['bytes']:>10}  {w:+6.2f}%  "
              f"{'PASS' if ok else 'FAIL'}")
print(f"  => C-2 density {'PASS' if c2_density else 'FAIL'}, "
      f"lead-survival {'PASS' if c2_lead else 'FAIL'}, "
      f"M8S {'PASS' if c2_m8s else 'FAIL'}")
print()

# ---------------- C-3 : speed ----------------
print("=" * 78)
print("C-3  median F12 decode speedup on CM2-won files >= 1.5x")
print("=" * 78)
sp = []
for f in cm2:
    a, b = cell(f, "full"), cell(f, "f12")
    s = med(a["walls"]) / med(b["walls"])
    sp.append((f, med(a["walls"]), med(b["walls"]), s))
for f, wa, wb, s in sorted(sp, key=lambda r: -r[3]):
    big = " >=8MB" if ORIG[f] >= 8 * 1024 * 1024 else ""
    print(f"  {f:<14} {wa:>9.2f}s -> {wb:>9.2f}s   {s:>6.3f}x{big}")
median_sp = med([r[3] for r in sp])
c3 = median_sp >= 1.5
print(f"  => median speedup {median_sp:.3f}x (need >= 1.50x)  {'PASS' if c3 else 'FAIL'}")
big = [r for r in sp if ORIG[r[0]] >= 8 * 1024 * 1024]
print(f"  sub-clause '>=2.0x on files >=8MB with tbits>=26': NOT EVALUABLE - the runner")
print(f"    invoked cubrim with --quiet, so no tbits was recorded anywhere in the")
print(f"    campaign artefacts. Files >=8MB present: {[r[0] for r in big]}")
for f, wa, wb, s in big:
    print(f"      {f:<14} {s:.3f}x")
print()

# ---------------- C-4 : memory ----------------
print("=" * 78)
print("C-4  F12 decode peak RSS <= 60% of full, on CM2-won files >= 16 MB")
print("=" * 78)
c4_rows = [f for f in cm2 if ORIG[f] >= 16 * 1024 * 1024]
c4 = True
for f in c4_rows:
    a, b = cell(f, "full"), cell(f, "f12")
    ra, rb = max(a["rss"]), max(b["rss"])
    pct = rb / ra * 100.0
    ok = pct <= 60.0
    c4 &= ok
    print(f"  {f:<14} {ra/1048576:>7.2f} GiB -> {rb/1048576:>7.2f} GiB   {pct:>5.1f}%  "
          f"{'PASS' if ok else 'FAIL'}")
if not c4_rows:
    print("  (no CM2-won file >= 16 MB)")
print(f"  => C-4 {'PASS' if c4 else 'FAIL'}  (n={len(c4_rows)})")
print()

# ---------------- adoption rule ----------------
print("=" * 78)
print("PRE-COMMITTED ADOPTION RULE")
print("=" * 78)
print(f"  C-2 lead-survival  : {'PASS' if c2_lead else 'FAIL'}  ({rate:.1f}% >= 80%)")
print(f"  C-3 median-speedup : {'PASS' if c3 else 'FAIL'}  ({median_sp:.3f}x >= 1.50x)")
fires = c2_lead and c3
print()
print(f"  RULE {'FIRES -> introduce new preset `fast` (F12 + M8S on database class)' if fires else 'DOES NOT FIRE -> no preset change; tier stays knob-only'}")
