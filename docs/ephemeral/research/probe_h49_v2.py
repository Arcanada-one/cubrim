#!/usr/bin/env python3
"""H-49 spike v2: TRUE compress-compare per column (not uncompressed-length proxy) +
a synthetic deterministic-correlation control to confirm the mechanism works in cubrim.

baseline = all numeric cols decimal/int-delta'd independently (H-40 path).
corra    = source = first decimal col; each other same-scale decimal col coded as the
           cubrim-smaller of {independent-delta, residual(T-S)-delta}; charge 1 byte/res col.
Gate: baseline / corra >= 1.5 (>=1.5x over H-40). Charged.
"""
import sys, subprocess, os, re
BIN, SCR = sys.argv[1], sys.argv[2]
FILES = sys.argv[3:]
DEC = re.compile(rb"^-?\d+\.\d+$")

def comp(data, tag):
    p = os.path.join(SCR, f"_h49v2_{tag}.bin"); open(p, "wb").write(data); o = p + ".cbr"
    subprocess.run([BIN, "compress", p, o, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(o)

def scaled(cell):
    if DEC.match(cell):
        s = cell.decode(); neg = s.startswith("-"); ip, fp = s.lstrip("-").split(".")
        return (-1 if neg else 1) * int(ip + fp), len(fp)
    t = cell.lstrip(b"-")
    if t.isdigit() and (t == b"0" or t[0:1] != b"0"):
        return int(cell), 0
    return None

def dstream(vals, header):
    out = [header, str(vals[0]).encode()]
    out += [str(vals[i] - vals[i - 1]).encode() for i in range(1, len(vals))]
    return b"\n".join(out)

for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    rows = [r.split(b",") for r in raw.split(b"\n") if r]
    ncol = max(len(r) for r in rows)
    cs, sc, hd = {}, {}, {}
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        sv = [scaled(x) for x in cells[1:]]
        if len(sv) >= 3 and all(x is not None for x in sv) and len({s for _, s in sv}) == 1:
            cs[c] = [v for v, _ in sv]; sc[c] = sv[0][1]; hd[c] = cells[0]
    dec = [c for c in sorted(cs) if sc[c] > 0]
    base_streams, corra_streams = [], []
    n_res = 0
    src = dec[0] if dec else None
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        if c in cs:
            indep = dstream(cs[c], cells[0])
            base_streams.append(indep)
            if src is not None and c != src and c in dec and sc[c] == sc[src]:
                resid = [cs[c][i] - cs[src][i] for i in range(len(cs[c]))]
                res = dstream(resid, cells[0])
                # TRUE compress-compare per column
                if comp(res, "t") < comp(indep, "t2"):
                    corra_streams.append(res); n_res += 1
                else:
                    corra_streams.append(indep)
            else:
                corra_streams.append(indep)
        else:
            base_streams.append(b"\n".join(cells))
            corra_streams.append(b"\n".join(cells))
    base = comp(b"\x00".join(base_streams), "base")
    corra = comp(b"\x00".join(corra_streams), "corra") + n_res
    x = base / corra if corra else 0
    print(f"{name:<26} baseline={base} corra={corra} (src=c{src}, {n_res} res-cols) "
          f"=> {x:.3f}x  {'GO>=1.5' if x>=1.5 else 'below-1.5x'}", flush=True)
for f in os.listdir(SCR):
    if f.startswith("_h49v2_"):
        os.remove(os.path.join(SCR, f))
