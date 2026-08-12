#!/usr/bin/env python3
"""Lead-survival arm of C-2, which is the condition the adoption rule actually keys on.

The prereg's adoption rule reads: "If C-2's lead-survival AND C-3's median-speedup
conditions both hold: introduce a new preset `fast`". So the trigger is not the
per-class density ceilings — those are a separate C-2 clause — but whether cubrim's
meta-36 rank-1 survives on >= 80% of the files it currently leads.

A file "survives" when the f12 ratio still beats every other archiver on that file.
f12 ratio is derived from the measured density delta: r_f12 = r_full * (1 + d/100),
where r_full is meta-36's cubrim ratio and d the campaign's per-file byte delta.
Using meta-36's own cubrim ratio (rather than recomputing from bytes) keeps the
comparison inside one measurement frame.
"""
import json
import statistics
import sys
from collections import defaultdict

JOURNAL = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-1002/new24/journal.jsonl"
META = "/tmp/claude-1002/new24/meta36.psv"

cells = defaultdict(dict)
for line in open(JOURNAL):
    line = line.strip()
    if not line:
        continue
    d = json.loads(line)
    c = d.get("cell")
    if not c:
        continue
    f, arm = c.rsplit("/", 1)
    e = cells[(f, arm)]
    if d["event"] == "encoded":
        e["bytes"] = d["bytes"]
        e["sha"] = d["sha"]
    elif d["event"] == "decode_ok":
        e.setdefault("dec", []).append(d["wall_s"])
    elif d["event"] == "cell_done":
        e["done"] = True

meta = {}
for line in open(META):
    line = line.rstrip("\n")
    if not line or "|" not in line:
        continue
    file, typ, orig, ratio_json, rank = line.split("|", 4)
    meta[file] = {
        "type": typ,
        "orig": int(orig),
        "ratios": json.loads(ratio_json),
        "rank": int(rank),
    }

led = [f for f, m in meta.items() if m["rank"] == 1]
print(f"cubrim leads {len(led)} of {len(meta)} meta-36 files "
      f"(not led: {sorted(f for f in meta if meta[f]['rank'] != 1)})\n")

hdr = f"{'file':<14}{'class':<10}{'dens%':>8}{'r_full':>10}{'r_f12':>10}{'runner-up':>22}{'verdict':>10}"
print(hdr)
print("-" * len(hdr))

survived, lost, unmeasured = [], [], []
for f in sorted(led, key=lambda x: (meta[x]["type"], x)):
    full, f12 = cells.get((f, "full"), {}), cells.get((f, "f12"), {})
    if not (full.get("done") and f12.get("done")):
        unmeasured.append(f)
        continue
    d = (f12["bytes"] - full["bytes"]) / full["bytes"] * 100
    m = meta[f]
    r_full = m["ratios"]["cubrim"]
    r_f12 = r_full * (1 + d / 100)
    others = {k: v for k, v in m["ratios"].items() if k != "cubrim"}
    ru_name = min(others, key=others.get)
    ru = others[ru_name]
    ok = r_f12 < ru
    (survived if ok else lost).append(f)
    print(f"{f:<14}{m['type']:<10}{d:>+8.2f}{r_full:>10.5f}{r_f12:>10.5f}"
          f"{ru_name + ' ' + format(ru, '.5f'):>22}{'holds' if ok else 'LOST':>10}")

n = len(survived) + len(lost)
print(f"\nmeasured led-files: {n}   survived: {len(survived)}   lost: {len(lost)}")
if n:
    pct = len(survived) / n * 100
    print(f"survival rate on measured: {pct:.1f}%  (bar 80%)  -> "
          f"{'HOLDS' if pct >= 80 else 'FAILS'}")
if unmeasured:
    print(f"NOT YET MEASURED ({len(unmeasured)}): {sorted(unmeasured)}")
    worst = len(survived) / len(led) * 100
    best = (len(survived) + len(unmeasured)) / len(led) * 100
    print(f"bound over ALL {len(led)} led-files: worst case {worst:.1f}%, "
          f"best case {best:.1f}%  (bar 80%)")
    if worst >= 80:
        print("  -> already DECIDED: bar cleared regardless of the remaining files")
    elif best < 80:
        print("  -> already DECIDED: bar unreachable regardless of the remaining files")
    else:
        print("  -> UNDECIDED until the remaining files land")
