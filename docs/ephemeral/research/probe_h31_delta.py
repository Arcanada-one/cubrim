#!/usr/bin/env python3
"""H-31 charged probe: does first-order delta on monotonic integer columns (epoch
timestamps / ids / counters), stacked on the H-30 columnar field-split, improve the
columnar files beyond plain columnar? Faithful: the transformed stream is compressed
by the REAL cubrim binary.

Delta detection (canonical, reversible): a column is delta-eligible if cells[1..] (the
data cells after a possible text header row 0) are ALL canonical integers — i.e.
str(int(cell)) == cell (no leading zeros / signs / float noise that would break exact
re-rendering). Transform: keep cell[0] verbatim, cell[1] = anchor verbatim, cells[2..]
= signed delta from the previous cell. Exactly invertible by prefix-sum.
"""
import sys, subprocess, os

BIN = sys.argv[1]; SCR = sys.argv[2]; FILES = sys.argv[3:]

def comp(data: bytes, tag: str) -> int:
    p = os.path.join(SCR, f"_h31_{tag}.bin"); open(p, "wb").write(data)
    out = p + ".cbr"
    subprocess.run([BIN, "compress", p, out, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(out)

def zs(path): return len(subprocess.run(["zstd","-19","-c",path],capture_output=True).stdout)

def best_delim(rows):
    import collections
    best = None
    for d in (b',', b'\t', b';', b'|'):
        k = [r.count(d) + 1 for r in rows]
        modal, n = collections.Counter(k).most_common(1)[0]
        frac = n / len(k)
        if modal >= 2 and frac >= 0.9:
            if best is None or (frac, modal) > (best[1], best[2]):
                best = (d, frac, modal)
    return best[0] if best else None

def canonical_int(cell: bytes):
    s = cell.decode("latin1")
    try:
        v = int(s)
    except ValueError:
        return None
    return v if str(v) == s else None

def columnar(rows, delim, with_delta):
    ncol = max(r.count(delim) + 1 for r in rows)
    cols = []
    delta_cols = 0
    for c in range(ncol):
        cells = [r.split(delim)[c] if r.count(delim) + 1 > c else b"" for r in rows]
        if with_delta and len(cells) >= 3:
            ints = [canonical_int(x) for x in cells[1:]]
            if all(v is not None for v in ints) and all(ints[i] >= ints[i-1] for i in range(1, len(ints))):
                # delta-code: cell0 verbatim, cell1 anchor, rest signed deltas
                seq = [cells[0], cells[1]]
                prev = ints[0]
                for v in ints[1:]:
                    seq.append(str(v - prev).encode()); prev = v
                cols.append(b"\n".join(seq)); delta_cols += 1; continue
        cols.append(b"\n".join(cells))
    return b"\x00".join(cols), delta_cols

print(f"{'file':<22}{'colNoDelta':>12}{'colDelta':>10}{'zstd':>8}  result")
for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    rows = raw.split(b"\n")
    if rows and rows[-1] == b"": rows = rows[:-1]
    d = best_delim(rows)
    if d is None:
        print(f"{name:<22}{'—':>12}{'—':>10}{zs(path):>8}  NOT TABULAR (columnar/H-31 cannot apply)")
        continue
    s0, _ = columnar(rows, d, False)
    s1, ndc = columnar(rows, d, True)
    c0, c1, z = comp(s0, "nod"), comp(s1, "del"), zs(path)
    gain = 100 * (c1 - c0) / c0
    print(f"{name:<22}{c0:>12}{c1:>10}{z:>8}  delta_cols={ndc} gain={gain:+.1f}% "
          f"(col {100*(c0-z)/z:+.1f}%→delta {100*(c1-z)/z:+.1f}% vs zstd)")
