#!/usr/bin/env python3
"""Per-cell medians + decision axes for the independent zero-rep matrix run,
with side-by-side comparison against the programme session's G3 stand medians."""
import csv, statistics, sys, os

S = os.path.dirname(os.path.abspath(__file__))
RES = f"{S}/out/results.tsv"

# G3 stand medians (dev-ai): cell -> build -> (wall_s, rss_kib)
G3 = {
 "nci/balanced": {"base": (18.17, 1385472), "current": (15.07, 1645056), "zero": (14.68, 991744)},
 "nci/web": {"base": (15.77, 108032), "current": (13.39, 111616), "zero": (13.08, 92672)},
 "dickens/max": {"base": (26.94, 1543680), "current": (19.95, 1719808), "zero": (20.06, 1154560)},
 "dickens/balanced": {"base": (25.71, 1486848), "current": (19.25, 1654272), "zero": (19.33, 1135104)},
 "dickens/web": {"base": (22.54, 110080), "current": (17.17, 113152), "zero": (17.08, 104960)},
 "ooffice/max": {"base": (25.53, 1635328), "current": (19.08, 1708544), "zero": (19.21, 1474048)},
 "ooffice/balanced": {"base": (25.54, 1635328), "current": (19.07, 1708032), "zero": (19.34, 1474048)},
 "ooffice/web": {"base": (22.29, 112640), "current": (17.12, 115200), "zero": (16.80, 108032)},
}
ORDER = list(G3.keys())

data = {}
with open(RES) as f:
    for row in csv.DictReader(f, delimiter="\t"):
        if row["phase"] != "timed":
            continue
        cell, b = row["cell"], row["build"]
        data.setdefault(cell, {}).setdefault(b, []).append(
            (float(row["wall_s"]), int(row["rss_kib"])))

print(f"{'cell':<18}{'build':<9}{'n':>2} {'wall_med':>9} {'rss_med_kib':>12}"
      f" {'g3_wall':>8} {'g3_rss':>10} {'rss_delta_kib':>13}")
for cell in ORDER:
    if cell not in data:
        continue
    for b in ("base", "current", "zero"):
        samples = data[cell].get(b, [])
        if not samples:
            continue
        w = statistics.median(s[0] for s in samples)
        r = int(statistics.median(s[1] for s in samples))
        g3w, g3r = G3[cell][b]
        print(f"{cell:<18}{b:<9}{len(samples):>2} {w:>9.2f} {r:>12,}"
              f" {g3w:>8.2f} {g3r:>10,} {r-g3r:>+13,}")

print("\nDecision axes per cell (this run, arcana-devs — timing under load, see loadlog):")
print(f"{'cell':<18}{'P_kib':>10}{'R_kib':>10}{'R/P':>7}{'resid_kib':>11}"
      f"{'z/c_time':>9}{'b/z_time':>9}  RSS-axes  vs-G3-RSS-axes")
for cell in ORDER:
    if cell not in data or len(data[cell]) < 3:
        continue
    med = {b: (statistics.median(s[0] for s in data[cell][b]),
               statistics.median(s[1] for s in data[cell][b]))
           for b in ("base", "current", "zero")}
    P = med["current"][1] - med["base"][1]
    R = med["current"][1] - med["zero"][1]
    resid = P - R
    zc = med["zero"][0] / med["current"][0]
    bz = med["base"][0] / med["zero"][0]
    rss_ok = P > 0 and R / P >= 0.75 and resid <= 65536
    g3 = G3[cell]
    g3P = g3["current"][1] - g3["base"][1]
    g3R = g3["current"][1] - g3["zero"][1]
    agree = "agrees" if (P > 0) == (g3P > 0) and abs(R - g3R) < 32768 else "DIVERGES"
    print(f"{cell:<18}{P:>10,}{R:>10,}{R/P:>7.3f}{resid:>+11,}"
          f"{zc:>9.3f}{bz:>9.3f}  {'PASS' if rss_ok else 'CHECK':<8}  {agree}")
