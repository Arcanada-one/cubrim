#!/usr/bin/env python3
"""CUBR-SPEEDFLOOR-20260811 — per-file decode throughput and the Amdahl best case.

Regenerates every table in the results report from out/results.tsv and out/gates.tsv.
No figure in the report is hand-typed arithmetic.

Per-file only. No corpus aggregate is computed anywhere, by construction: every
table is keyed by file and nothing sums or averages across files.
"""
import csv, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SIZES = {"dickens": 10192446, "x-ray": 8474240}      # bytes, canonical Silesia
MIB = 1024 * 1024

# Landed G2 attribution: per-cell combined outer Amdahl bound (perfect named machinery).
# dickens/max and xml/max are the clean cells; x-ray/max is G3 instrument-perturbed and its
# bound is carried only as an upper marker, never as a decision number.
LANDED_BOUND = {"dickens": (13.986, "clean"), "x-ray": (55.556, "G3 instrument-perturbed")}
# Landed attribution plain pinned profiling wall (seconds) — NOT benchmark throughput.
LANDED_WALL = {"dickens": 142.860, "x-ray": 6.200}

FIELD_9TH = ("ppmd", 25.69)      # ninth place, world_benchmark_timing_aggregate d_max
CUBRIM_HEADLINE = 1.71           # d_max, a MAXIMUM over files


def load():
    with open(os.path.join(OUT, "results.tsv")) as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r["phase"] == "timed"]
    with open(os.path.join(OUT, "gates.tsv")) as f:
        gates = list(csv.DictReader(f, delimiter="\t"))
    return rows, gates


def check_gates(gates, rows):
    bad = [g for g in gates if g["verdict"] != "OK"]
    keyed = {(g["file"], g["tool"], g["sample"]) for g in gates if g["verdict"] == "OK"}
    unbacked = [r for r in rows if (r["file"], r["tool"], r["sample"]) not in keyed]
    print(f"GATES: {len(gates)} decode observations, {len(bad)} VOID, "
          f"{len(unbacked)} timing rows without a passing gate")
    if bad or unbacked:
        sys.exit("gate failure: refusing to report numbers for unverified decodes")
    return True


def medians(rows):
    agg = {}
    for r in rows:
        agg.setdefault((r["file"], r["tool"], r["setting"]), []).append(
            (float(r["wall_s"]), int(r["rss_kib"]), int(r["archive_bytes"])))
    out = {}
    for k, v in agg.items():
        wall = statistics.median(s[0] for s in v)
        out[k] = {"wall": wall, "n": len(v),
                  "rss": int(statistics.median(s[1] for s in v)),
                  "arch": v[0][2],
                  "walls": sorted(s[0] for s in v)}
    return out


def main():
    rows, gates = load()
    check_gates(gates, rows)
    med = medians(rows)
    files = sorted({k[0] for k in med})

    for f in files:
        n = SIZES[f]
        print(f"\n=== {f} ({n:,} B = {n/MIB:.4f} MiB) — same host, pin 0-15, median of 3 ===")
        print(f"{'tool':<8}{'setting':>8}{'ratio':>10}{'decode_s':>10}{'MiB/s':>10}"
              f"{'rss_kib':>10}{'vs cubrim':>11}")
        cub = med.get((f, "cubrim", "max"))
        cub_tp = (n / MIB) / cub["wall"] if cub else None
        ordered = sorted((k for k in med if k[0] == f),
                         key=lambda k: (n / MIB) / med[k]["wall"], reverse=True)
        for k in ordered:
            m = med[k]
            tp = (n / MIB) / m["wall"]
            ratio = m["arch"] / n
            rel = f"{tp/cub_tp:>9.0f}x" if cub_tp else "  n/a"
            print(f"{k[1]:<8}{k[2]:>8}{ratio:>10.6f}{m['wall']:>10.3f}{tp:>10.2f}"
                  f"{m['rss']:>10,}{rel:>11}")
        if not cub:
            print("  (cubrim cell not yet complete)")
            continue

        bound, note = LANDED_BOUND[f]
        best = cub_tp * bound
        lw = LANDED_WALL[f]
        implied = (n / MIB) / lw
        print(f"\n  landed profiling wall {lw:.3f}s -> implied {implied:.4f} MiB/s; "
              f"measured {cub_tp:.4f} MiB/s; ratio measured/implied = {cub_tp/implied:.3f}x")
        print(f"  perfect-CM2 best case = {cub_tp:.4f} x {bound} = {best:.3f} MiB/s   [{note}]")
        print(f"  ninth place {FIELD_9TH[0]} = {FIELD_9TH[1]} MiB/s -> "
              f"best case is {FIELD_9TH[1]/best:.1f}x short"
              if best < FIELD_9TH[1] else
              f"  best case REACHES the field")

        # predictions
        print("\n  PREREGISTERED PREDICTIONS")
        lo, hi = implied / 2, implied * 2
        p1 = lo <= cub_tp <= hi
        print(f"   P1 measured within 2x of implied [{lo:.4f},{hi:.4f}]: "
              f"{cub_tp:.4f} -> {'HOLDS' if p1 else 'REFUTED'}")
        if f == "dickens":
            xz = med.get((f, "xz", "-9"))
            if xz:
                xz_tp = (n / MIB) / xz["wall"]
                p2 = xz_tp / cub_tp >= 100
                print(f"   P2 cubrim >=100x slower than xz -9: {xz_tp/cub_tp:.0f}x -> "
                      f"{'HOLDS' if p2 else 'REFUTED'}")
        p3 = best < FIELD_9TH[1]
        print(f"   P3 perfect-CM2 best case < {FIELD_9TH[1]} MiB/s: {best:.3f} -> "
              f"{'HOLDS' if p3 else 'REFUTED'}")
        print(f"   (context: cubrim headline d_max {CUBRIM_HEADLINE} MiB/s is a MAXIMUM over files; "
              f"this file measures {cub_tp:.4f})")


def interleaved():
    """Same-window analysis: every tool decoded back-to-back within a round.
    Absolute MiB/s on a shared box is not comparable across windows; the
    tool-to-tool ratio WITHIN a round is. Reported as median over rounds."""
    path = os.path.join(OUT, "interleaved.tsv")
    if not os.path.exists(path):
        return
    rows = list(csv.DictReader(open(path), delimiter="\t"))
    bad = [r for r in rows if r["verdict"] != "OK"]
    print(f"\n=== interleaved same-window pass (dickens): {len(rows)} observations, "
          f"{len(bad)} VOID ===")
    if bad:
        sys.exit("gate failure in interleaved pass")
    per = {}
    for r in rows:
        per.setdefault(r["round"], {})[r["tool"]] = float(r["wall_s"])
    n = SIZES["dickens"] / MIB
    tools = [t for t in ("lz4", "zstd", "brotli", "gzip", "xz", "bzip2") ]
    print(f"{'tool':<8}{'ratio vs cubrim per round':>34}{'median':>10}")
    med_ratio = {}
    for t in tools:
        rs = [per[k]["cubrim"] / per[k][t] for k in sorted(per) if t in per[k] and "cubrim" in per[k]]
        med_ratio[t] = statistics.median(rs)
        print(f"{t:<8}{'  '.join(f'{x:8.0f}x' for x in rs):>34}{med_ratio[t]:>9.0f}x")
    cub = statistics.median(per[k]["cubrim"] for k in per)
    print(f"\ncubrim decode median across rounds: {cub:.1f}s = {n/cub:.4f} MiB/s "
          f"(load1 {min(float(r['load1_before']) for r in rows):.1f}-"
          f"{max(float(r['load1_before']) for r in rows):.1f} during the pass)")
    bound = LANDED_BOUND['dickens'][0]
    print(f"perfect-CM2 best case from this pass = {n/cub:.4f} x {bound} = {n/cub*bound:.3f} MiB/s"
          f"  -> {FIELD_9TH[1]/(n/cub*bound):.1f}x short of {FIELD_9TH[0]} at ninth place")
    print(f"even matching bzip2 (slowest competitor, {med_ratio['bzip2']:.0f}x faster here) "
          f"needs {med_ratio['bzip2']/bound:.0f}x BEYOND the perfect-CM2 bound")


if __name__ == "__main__":
    main()
    interleaved()
