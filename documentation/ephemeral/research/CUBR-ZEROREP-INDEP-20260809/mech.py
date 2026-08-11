#!/usr/bin/env python3
"""Lazy-pages mechanism reconciliation per cell.

Mechanism under test: PR #41's packed Ctr initialises every slot to the
non-zero word 0x08000000, physically committing all table pages; the zero-rep
XOR-bias makes the stationary word 0x00000000 so calloc'd pages stay lazy
until first real update. Pre-PR41 committed only the 2-byte `t` array
(non-zero init) while 1-byte `c`/`st` stayed lazy. Therefore at decode peak:

  L_b       := sum(Size - Rss) over large anon mappings of build b
  L_zero - L_current  should reconcile with  R (packed->zero RSS reclaim)
  L_zero - L_base     should reconcile with  B (baseline->zero RSS drop)
  and L_base > 0 only from untouched c/st (+ match tables, lazy in all builds).

If those hold per cell, the below-pre-PR41 RSS is fully accounted for by
pages that pre-PR41 committed (t-array) but zero-rep never touches: the
lazy-pages explanation is CONFIRMED for that cell.
"""
import csv, statistics, os, sys

S = os.path.dirname(os.path.abspath(__file__))
CELLS = ["nci/balanced", "nci/web", "dickens/max", "dickens/balanced",
         "dickens/web", "ooffice/max", "ooffice/balanced", "ooffice/web"]
E_MIB = {"nci/balanced": 736, "nci/web": 46, "dickens/max": 768,
         "dickens/balanced": 736, "dickens/web": 46, "ooffice/max": 736,
         "ooffice/balanced": 736, "ooffice/web": 46}

# medians from timed runs
med = {}
with open(f"{S}/out/results.tsv") as f:
    rows = [r for r in csv.DictReader(f, delimiter="\t") if r["phase"] == "timed"]
for cell in CELLS:
    for b in ("base", "current", "zero"):
        v = [int(r["rss_kib"]) for r in rows if r["cell"] == cell and r["build"] == b]
        if v:
            med[(cell, b)] = int(statistics.median(v))

def peak(cell, b):
    f, p = cell.split("/")
    path = f"{S}/out/smaps2/{f}.{p}.{b}.peak-totals.txt"
    if not os.path.exists(path):
        return None
    size, rss = map(int, open(path).read().split())
    return size, rss

TOL_ABS = 40960  # 40 MiB in KiB: snapshot granularity + heap noise
print(f"{'cell':<18}{'L_base':>10}{'L_curr':>10}{'L_zero':>10}"
      f"{'Lz-Lc':>10}{'R':>10}{'Lz-Lb':>10}{'B':>10}{'B<=E':>6}  verdict")
for cell in CELLS:
    peaks = {b: peak(cell, b) for b in ("base", "current", "zero")}
    if any(v is None for v in peaks.values()) or (cell, "base") not in med:
        print(f"{cell:<18}  (smaps2 data not yet present)")
        continue
    L = {b: peaks[b][0] - peaks[b][1] for b in peaks}
    R = med[(cell, "current")] - med[(cell, "zero")]
    B = med[(cell, "base")] - med[(cell, "zero")]
    dRc = L["zero"] - L["current"]
    dRb = L["zero"] - L["base"]
    ok_R = abs(dRc - R) <= TOL_ABS
    ok_B = abs(dRb - B) <= TOL_ABS
    ok_E = B <= E_MIB[cell] * 1024
    verdict = "CONFIRMED" if (ok_R and ok_B and ok_E) else "NOT-RECONCILED"
    print(f"{cell:<18}{L['base']:>10,}{L['current']:>10,}{L['zero']:>10,}"
          f"{dRc:>10,}{R:>10,}{dRb:>10,}{B:>10,}{str(ok_E):>6}  {verdict}"
          f"{'' if ok_R else '  [R mismatch]'}{'' if ok_B else '  [B mismatch]'}")
print("\nAll figures KiB. L_b = size-rss deficit over >=1MiB anon mappings at peak-RSS snapshot.")
