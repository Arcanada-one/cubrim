#!/usr/bin/env python3
"""Adjudicate the NEW-24 preset campaign against its preregistered predictions.

Reads the campaign journal and emits, per file, both sides of the trade plus the
C-1..C-4 verdicts and the pre-committed adoption rule. Prereg:
CUBR-NEW24-PRESET-CAMPAIGN-20260811.md (main 563b94e).

Deliberately does NOT compute corpus-wide averages: the prereg forbids them.
Canterbury files are reported but excluded from class-level claims.
"""
import json
import sys
import statistics
from collections import defaultdict

JOURNAL = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-1002/new24/journal.jsonl"

# File classes come from the meta-36 dataset itself, never a hand-typed table.
# The first version of this script hard-coded them and had `samba` as "exe" while
# the dataset says "code" — a hand-typed table beside a machine-readable one drifts
# from it, and here it would have applied the wrong C-2 ceiling.
META = "/tmp/claude-1002/new24/meta36.psv"


def load_classes(path):
    cls = {}
    try:
        for line in open(path):
            line = line.rstrip("\n")
            if not line or "|" not in line:
                continue
            f, typ, _rest = line.split("|", 2)
            cls[f] = typ
    except OSError:
        pass
    return cls


CLASS = load_classes(META)
# Canterbury members are reported but excluded from class-level claims per protocol.
CANTERBURY = {
    "alice29.txt", "asyoulik.txt", "cp.html", "fields.c", "grammar.lsp",
    "kennedy.xls", "lcet10.txt", "plrabn12.txt", "ptt5", "sum", "xargs.1",
}

# C-1 names these as the image/binary class where CM2 is expected not to win.
C1_FILES = ["mr", "x-ray", "sao", "ptt5", "kennedy.xls"]
# C-2 per-class worsening ceilings.
C2_CEIL = {"text": 5.0, "code": 5.0, "exe": 6.0, "database": 10.0}
# image/binary intentionally absent: C-1 covers them, and the tier should not move them.

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
        e["enc_s"] = d["enc_s"]
    elif d["event"] == "decode_ok":
        e.setdefault("dec", []).append(d["wall_s"])
        e.setdefault("rss", []).append(d["rss_kib"])
    elif d["event"] == "cell_done":
        e["done"] = True
    elif d["event"] in ("void", "gate_fail"):
        e["failed"] = d

files = sorted({f for (f, _a) in cells}, key=lambda x: (CLASS.get(x, "zz"), x))


def med(xs):
    return statistics.median(xs) if xs else None


rows = []
for f in files:
    full = cells.get((f, "full"), {})
    f12 = cells.get((f, "f12"), {})
    if not (full.get("done") and f12.get("done")):
        continue
    identical = full.get("sha") == f12.get("sha")
    dfull, df12 = med(full.get("dec", [])), med(f12.get("dec", []))
    rfull, rf12 = med(full.get("rss", [])), med(f12.get("rss", []))
    rows.append({
        "file": f, "cls": CLASS.get(f, "?"),
        "identical": identical,
        "b_full": full.get("bytes"), "b_f12": f12.get("bytes"),
        "dens_pct": (f12["bytes"] - full["bytes"]) / full["bytes"] * 100
        if full.get("bytes") and f12.get("bytes") else None,
        "d_full": dfull, "d_f12": df12,
        "speedup": (dfull / df12) if dfull and df12 else None,
        "rss_full": rfull, "rss_f12": rf12,
        "rss_pct": (rf12 / rfull * 100) if rfull and rf12 else None,
        "orig_mb": None,
    })

print(f"=== cells complete: {sum(1 for k, v in cells.items() if v.get('done'))} "
      f"| files with both arms: {len(rows)} ===\n")
hdr = (f"{'file':<14}{'class':<10}{'ident':<7}{'dens%':>8}{'dec_full':>10}"
       f"{'dec_f12':>10}{'speedup':>9}{'rss_full_M':>12}{'rss_f12_M':>11}{'rss%':>8}")
print(hdr)
print("-" * len(hdr))


def fmt(v, spec, width, scale=1.0):
    if v is None:
        return "-".rjust(width)
    return format(v * scale, spec).rjust(width)


for r in rows:
    print(
        f"{r['file']:<14}{r['cls']:<10}{'YES' if r['identical'] else 'no':<7}"
        + fmt(r["dens_pct"], "+.2f", 8)
        + fmt(r["d_full"], ".1f", 10)
        + fmt(r["d_f12"], ".1f", 10)
        + (fmt(r["speedup"], ".2f", 8) + "x" if r["speedup"] else "-".rjust(9))
        + fmt(r["rss_full"], ".0f", 12, 1 / 1024)
        + fmt(r["rss_f12"], ".0f", 11, 1 / 1024)
        + (fmt(r["rss_pct"], ".0f", 7) + "%" if r["rss_pct"] else "-".rjust(8))
    )

cm2_won = [r for r in rows if not r["identical"]]
cm2_lost = [r for r in rows if r["identical"]]
print(f"\nCM2-won (f12 changed the archive): {[r['file'] for r in cm2_won]}")
print(f"CM2 not decisive (byte-identical):  {[r['file'] for r in cm2_lost]}")

print("\n=== C-1 scope of effect ===")
print("predicts: on image/binary files the f12 archive is byte-identical AND decode within +/-10%")
for f in C1_FILES:
    r = next((r for r in rows if r["file"] == f), None)
    if not r:
        print(f"  {f:<14} NOT YET MEASURED")
        continue
    dev = abs(r["speedup"] - 1) * 100 if r["speedup"] else None
    ok = r["identical"] and dev is not None and dev <= 10
    print(f"  {f:<14} identical={'YES' if r['identical'] else 'NO'} "
          f"decode_dev={dev:.1f}% -> {'HOLDS' if ok else 'FAILS'}")

print("\n=== C-2 density (CM2-won files only) ===")
print("ceilings: text/code <= +5%, exe <= +6%, database <= +10%; M8S on nci/osdb <= +8%")
for r in cm2_won:
    ceil = None if r["file"] in CANTERBURY else C2_CEIL.get(r["cls"])
    if ceil is None:
        print(f"  {r['file']:<14} {r['cls']:<10} {r['dens_pct']:+.2f}%  (excluded from class-level claims)")
        continue
    print(f"  {r['file']:<14} {r['cls']:<10} {r['dens_pct']:+.2f}%  ceiling +{ceil}%  "
          f"-> {'within' if r['dens_pct'] <= ceil else 'EXCEEDS'}")
for f in ("nci", "osdb"):
    full, m8s = cells.get((f, "full"), {}), cells.get((f, "m8s"), {})
    if full.get("bytes") and m8s.get("bytes"):
        p = (m8s["bytes"] - full["bytes"]) / full["bytes"] * 100
        dm, dfl = med(m8s.get("dec", [])), med(full.get("dec", []))
        print(f"  {f + '/M8S':<14} database   {p:+.2f}%  ceiling +8%   "
              f"-> {'within' if p <= 8 else 'EXCEEDS'}"
              f"   speedup {dfl / dm:.2f}x" if dm and dfl else "")

print("\n=== C-3 speed (CM2-won files) ===")
print("predicts: median decode speedup >= 1.5x; >= 2.0x on files >= 8MB with tbits >= 26")
sp = [r["speedup"] for r in cm2_won if r["speedup"]]
for r in cm2_won:
    if r["speedup"]:
        print(f"  {r['file']:<14} {r['speedup']:.2f}x")
if sp:
    print(f"  MEDIAN over CM2-won: {statistics.median(sp):.2f}x "
          f"-> {'HOLDS' if statistics.median(sp) >= 1.5 else 'FAILS'} (bar 1.5x)")

print("\n=== C-4 memory ===")
print("predicts: f12 decode peak RSS <= 60% of full on CM2-won files >= 16MB")
for r in cm2_won:
    if r["rss_pct"]:
        print(f"  {r['file']:<14} {r['rss_pct']:.1f}% of full "
              f"({r['rss_full'] / 1024:.0f}M -> {r['rss_f12'] / 1024:.0f}M)")
