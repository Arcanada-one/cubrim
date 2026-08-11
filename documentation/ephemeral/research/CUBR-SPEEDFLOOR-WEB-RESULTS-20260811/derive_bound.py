#!/usr/bin/env python3
"""Derive the dickens/web combined outer bound from the G2 attribution's RAW symbols.tsv,
and VALIDATE the rule against the two bounds the attribution published.

Rule: sum the cm2_* buckets, excluding cm2_decode_shell (the outer shell is not per-bit
machinery). Refuses to emit the derived bound unless both controls reproduce exactly.
"""
import csv, subprocess, sys
SRC = "documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/symbols.tsv"
PUBLISHED = {"dickens/max": (92.85, 13.986), "xml/max": (90.66, 10.707)}

txt = subprocess.run(["git", "show", f"origin/main:{SRC}"], capture_output=True, text=True).stdout
if not txt:
    sys.exit(f"cannot read {SRC} from origin/main")
rows = list(csv.DictReader(txt.splitlines(), delimiter="\t"))

def per_bit(cell):
    sub = [r for r in rows if r["cell"] == cell]
    tot = sum(float(r["share_percent"]) for r in sub if r["bucket"].startswith("cm2_"))
    shell = sum(float(r["share_percent"]) for r in sub if r["bucket"] == "cm2_decode_shell")
    s = tot - shell
    return tot, shell, s, 1 / (1 - s / 100)

ok = True
for cell, (ps, pb) in PUBLISHED.items():
    tot, shell, s, b = per_bit(cell)
    good = abs(s - ps) < 0.005 and abs(b - pb) < 0.005
    ok &= good
    print(f"CONTROL {cell:<12} sum={tot:7.3f} shell={shell:4.2f} per-bit={s:6.2f} bound={b:8.3f}"
          f"  published {ps}/{pb}  {'EXACT' if good else 'MISMATCH'}")
if not ok:
    sys.exit("control failed: derivation rule does not reproduce published bounds; bound NOT emitted")
tot, shell, s, b = per_bit("dickens/web")
print(f"DERIVED dickens/web  sum={tot:7.3f} shell={shell:4.2f} per-bit={s:6.2f} bound={b:8.3f}")
