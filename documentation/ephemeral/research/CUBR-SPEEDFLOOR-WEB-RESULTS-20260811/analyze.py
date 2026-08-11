#!/usr/bin/env python3
"""CUBR-SPEEDFLOOR-XML-20260811 — regenerate every table in the results report.

Reads out/interleaved.tsv, out/gates.tsv, out/archives.tsv. Refuses to print any
number if a gate is VOID or a timing row lacks a passing gate.

Per-file only: xml is one file and nothing here aggregates across files.
"""
import csv, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
MIB = 1048576

N = 10192446                   # dickens, canonical Silesia
LANDED_WALL = 105.710          # G2 attribution, plain pinned profiling wall (dickens/web)
LANDED_BOUND = 69.444          # DERIVED from symbols.tsv, validated on the two published bounds
FIELD_9TH = ("ppmd", 25.69)    # cross-meta marker only
DICKENS_BEST = 0.634           # perfect-CM2 best case measured on dickens/max
ORDER = ["cubrim", "xz", "zstd", "brotli", "gzip", "bzip2", "lz4"]


def load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        sys.exit(f"missing {name}")
    return list(csv.DictReader(open(p), delimiter="\t"))


def main():
    rows, gates, meta = load("interleaved.tsv"), load("gates.tsv"), load("archives.tsv")

    bad = [g for g in gates if g["verdict"] != "OK"]
    ok = {(g["round"], g["tool"]) for g in gates if g["verdict"] == "OK"}
    unbacked = [r for r in rows if (r["round"], r["tool"]) not in ok]
    print(f"GATES: {len(gates)} decode observations, {len(bad)} VOID, "
          f"{len(unbacked)} timing rows without a passing gate")
    if bad or unbacked:
        sys.exit("gate failure: refusing to report numbers for unverified decodes")

    per = {}
    for r in rows:
        per.setdefault(r["round"], {})[r["tool"]] = (float(r["wall_s"]), int(r["rss_kib"]))
    ratio = {m["tool"]: (float(m["ratio"]), int(m["archive_bytes"])) for m in meta}
    mib = N / MIB
    loads = [float(r["load1_before"]) for r in rows]

    print(f"\n=== dickens/web ({N:,} B = {mib:.4f} MiB) — same host, pin 0-15, "
          f"median of 3 interleaved rounds; load1 {min(loads):.1f}-{max(loads):.1f} ===")
    print(f"{'tool':<8}{'setting':>8}{'ratio':>10}{'decode_s':>10}{'MiB/s':>10}{'rss_kib':>12}{'vs cubrim':>11}")
    med = {t: statistics.median(per[k][t][0] for k in per if t in per[k]) for t in ORDER if any(t in per[k] for k in per)}
    rss = {t: int(statistics.median(per[k][t][1] for k in per if t in per[k])) for t in med}
    cub = mib / med["cubrim"]
    for t in sorted(med, key=lambda x: mib / med[x], reverse=True):
        tp = mib / med[t]
        st = {"cubrim": "web", "xz": "-9", "zstd": "-19", "brotli": "-q11",
              "gzip": "-9", "bzip2": "-9", "lz4": "-12"}[t]
        print(f"{t:<8}{st:>8}{ratio[t][0]:>10.6f}{med[t]:>10.3f}{tp:>10.2f}{rss[t]:>12,}"
              f"{tp/cub:>10.0f}x")

    print("\n--- same-round ratios (the defensible quantity on a shared box) ---")
    print(f"{'tool':<8}{'per round':>30}{'median':>10}")
    medr = {}
    for t in ORDER[1:]:
        rs = [per[k]["cubrim"][0] / per[k][t][0] for k in sorted(per) if t in per[k]]
        medr[t] = statistics.median(rs)
        print(f"{t:<8}{'  '.join(f'{x:7.0f}x' for x in rs):>30}{medr[t]:>9.0f}x")

    implied = mib / LANDED_WALL
    best = cub * LANDED_BOUND
    print(f"\nlanded wall {LANDED_WALL}s -> implied {implied:.4f} MiB/s; measured {cub:.4f} MiB/s "
          f"(measured/implied = {cub/implied:.3f}x)")
    print(f"perfect-CM2 best case = {cub:.4f} x {LANDED_BOUND} = {best:.3f} MiB/s"
          f"  -> {FIELD_9TH[1]/best:.1f}x short of {FIELD_9TH[0]} at ninth place")

    print("\nPREREGISTERED PREDICTIONS")
    tr = cub / implied
    print(f"  P1 measured/implied in [0.30,1.00]: {tr:.3f} -> "
          f"{'HOLDS' if 0.30 <= tr <= 1.00 else 'REFUTED'}")
    print(f"  P2 >=100x slower than xz -9: {medr['xz']:.0f}x -> "
          f"{'HOLDS' if medr['xz'] >= 100 else 'REFUTED'}")
    print(f"  P3 best case < {FIELD_9TH[1]}: {best:.3f} -> "
          f"{'HOLDS' if best < FIELD_9TH[1] else 'REFUTED'}")
    p4lo, p4hi = DICKENS_BEST / 2, DICKENS_BEST * 2
    print(f"  P4 best case OUTSIDE 2x of dickens/max {DICKENS_BEST} [{p4lo:.3f},{p4hi:.3f}]: {best:.3f} -> "
          f"{'HOLDS' if not (p4lo <= best <= p4hi) else 'REFUTED'}")
    dens = [t for t in ratio if ratio[t][0] < ratio["cubrim"][0]]
    print(f"\ndensity: cubrim ratio {ratio['cubrim'][0]:.6f}; tools beating it: {dens if dens else 'none'}")


if __name__ == "__main__":
    main()
