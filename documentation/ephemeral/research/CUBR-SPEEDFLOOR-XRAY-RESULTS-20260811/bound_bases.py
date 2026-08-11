#!/usr/bin/env python3
"""Show that the attribution's published combined bounds use TWO different set
definitions, from its own committed raw symbols.tsv.

CM2 cells publish "per-bit machinery"  = sum(cm2_*)   MINUS cm2_decode_shell.
x-ray publishes  "geocm replay path"   = sum(geocm_*) INCLUDING geocm_decode.

Both are reported for x-ray so no cross-cell comparison is made on a hidden basis.
"""
import csv, subprocess, sys
SRC = "documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/symbols.tsv"
txt = subprocess.run(["git", "show", f"origin/main:{SRC}"], capture_output=True, text=True).stdout
if not txt:
    sys.exit(f"cannot read {SRC} from origin/main")
rows = list(csv.DictReader(txt.splitlines(), delimiter="\t"))

def calc(cell, fam, shell):
    sub = [r for r in rows if r["cell"] == cell]
    tot = sum(float(r["share_percent"]) for r in sub if r["bucket"].startswith(fam))
    sh = sum(float(r["share_percent"]) for r in sub if r["bucket"] == shell)
    return tot, sh

print(f"{'cell':<14}{'sum':>9}{'shell':>7}{'incl->bound':>16}{'excl->bound':>16}   published")
for cell, fam, shell, pub in (
        ("dickens/max", "cm2_", "cm2_decode_shell", "92.85% / 13.986x  (EXCLUDED)"),
        ("xml/max", "cm2_", "cm2_decode_shell", "90.66% / 10.707x  (EXCLUDED)"),
        ("x-ray/max", "geocm_", "geocm_decode", "98.20% / 55.556x  (INCLUDED)")):
    tot, sh = calc(cell, fam, shell)
    bi, be = 1 / (1 - tot / 100), 1 / (1 - (tot - sh) / 100)
    print(f"{cell:<14}{tot:>9.3f}{sh:>7.2f}{tot:>9.2f}/{bi:>6.3f}x{tot-sh:>9.2f}/{be:>6.3f}x   {pub}")
print("\nThe CM2 rows are labelled 'per-bit machinery', the x-ray row 'replay path',")
print("so the difference may be deliberate — but the bounds are NOT like-for-like.")
