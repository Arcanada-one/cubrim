#!/usr/bin/env python3
"""H-41 spike: does DoubleDelta (delta-of-delta) structurally beat single-delta on
FIXED-INTERVAL timestamp/counter/gauge columns, THROUGH Cubrim's rANS/BWT backend?

The risk this spike must settle (Gotcha-style subsumption): a fixed-interval column's
single-delta is a CONSTANT stream (60,60,60,...), which rANS/BWT already code to near
zero. DoubleDelta turns it into zeros (60,0,0,...). If the entropy backend already
crushes the constant, DoubleDelta adds nothing → NO-GO (subsumed, like BWT subsumes MTF).
Faithful: both column-major streams are compressed by the REAL cubrim binary.

For each numeric column (integer or fixed-decimal scaled-int), build the column field
list 3 ways and compress the whole column-major stream: raw, single-delta, double-delta.
Report which wins per file + the variance gate (is the single-delta constant?).
"""
import sys, subprocess, os, re
from statistics import pstdev, mean

BIN, SCR = sys.argv[1], sys.argv[2]
FILES = sys.argv[3:]
DEC = re.compile(rb"^-?\d+\.\d+$")

def comp(data, tag):
    p = os.path.join(SCR, f"_h41_{tag}.bin"); open(p, "wb").write(data); o = p + ".cbr"
    subprocess.run([BIN, "compress", p, o, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(o)

def zstd19(p): return len(subprocess.run(["zstd","-19","-c",p],capture_output=True).stdout)

def scaled(cell):
    if DEC.match(cell):
        s = cell.decode(); neg = s.startswith("-"); ip, fp = s.lstrip("-").split(".")
        return (-1 if neg else 1) * int(ip + fp), len(fp)
    if cell.lstrip(b"-").isdigit() and (cell == b"0" or not cell.lstrip(b"-").startswith(b"0")):
        return int(cell), 0
    return None

def col_variant(cells, order):
    """order 0=raw, 1=single-delta, 2=double-delta (on scaled-int); None if not numeric."""
    data = cells[1:]
    sv = [scaled(c) for c in data]
    if len(data) < 4 or any(x is None for x in sv) or len({s for _, s in sv}) != 1:
        return None if order else [b"\n".join(cells)]
    vals = [v for v, _ in sv]
    if order == 0:
        return None
    d1 = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    if order == 1:
        seq = [cells[0], cells[1]] + [str(x).encode() for x in d1]
        return seq, d1
    # order 2: double-delta
    d2 = [d1[i] - d1[i - 1] for i in range(1, len(d1))]
    seq = [cells[0], cells[1], str(d1[0]).encode()] + [str(x).encode() for x in d2]
    return seq, d1

def build(rows, ncol, order):
    cols = []
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        r = col_variant(cells, order)
        if r is None:
            cols.append(b"\n".join(cells))
        elif order == 0:
            cols.append(r[0] if isinstance(r, list) else b"\n".join(cells))
        else:
            cols.append(b"\n".join(r[0]))
    return b"\x00".join(cols)

print(f"{'file':<24}{'single':>9}{'double':>9}{'gain':>8}{'zstd':>8}  per-col-delta-stddev/mean")
for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    rows = [r.split(b",") for r in raw.split(b"\n") if r]
    ncol = max(len(r) for r in rows)
    s1 = comp(build(rows, ncol, 1), "s1")
    s2 = comp(build(rows, ncol, 2), "s2")
    z = zstd19(path)
    # variance gate diagnostics: for each numeric column, is single-delta constant?
    gates = []
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        r1 = col_variant(cells[:], 1)
        if isinstance(r1, tuple):
            d1 = r1[1]
            m = mean(d1) if d1 else 0
            cv = (pstdev(d1) / abs(m)) if m else (0 if pstdev(d1) == 0 else 99)
            gates.append(f"c{c}:{cv:.2f}")
    gain = 100 * (s2 - s1) / s1
    verdict = "DoubleDelta GO" if s2 < s1 * 0.98 else "no structural gain"
    print(f"{name:<24}{s1:>9}{s2:>9}{gain:>+7.1f}%{z:>8}  {' '.join(gates)}  {verdict}")
for f in os.listdir(SCR):
    if f.startswith("_h41_"):
        os.remove(os.path.join(SCR, f))
