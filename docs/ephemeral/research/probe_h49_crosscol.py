#!/usr/bin/env python3
"""H-49 spike: does cross-column correlation residual (Corra-class) beat the current
per-column decimal-delta (H-40) by >=1.5x on REAL correlated telemetry (forex OHLC)?

Non-subsumable rationale: after MODE_COLUMNAR each column is a separate stream; the
byte BWT+rANS backend cannot see that column B = f(A). A residual B - predict(A)
extracts that mutual information. We measure FAITHFULLY through the real cubrim binary:

  baseline  = every numeric column decimal-delta'd independently (= H-40 shipped path)
  corra     = pick a source column S; code each correlated target T as residual
              (T_scaled - S_scaled), then delta that residual; per-column keep the
              smaller of {independent-delta, residual-delta}. Charge the predictor
              (1 source-index byte per residual-coded column; exact arithmetic residual
              => NO exception list).

Gate: corra <= baseline / 1.5 on the column-major stream (>=1.5x over H-40). Charged.
"""
import sys, subprocess, os, re
BIN, SCR = sys.argv[1], sys.argv[2]
FILES = sys.argv[3:]
DEC = re.compile(rb"^-?\d+\.\d+$")

def comp(data, tag):
    p = os.path.join(SCR, f"_h49_{tag}.bin"); open(p, "wb").write(data); o = p + ".cbr"
    subprocess.run([BIN, "compress", p, o, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(o)

def scaled(cell):
    if DEC.match(cell):
        s = cell.decode(); neg = s.startswith("-"); ip, fp = s.lstrip("-").split(".")
        return (-1 if neg else 1) * int(ip + fp), len(fp)
    if cell.lstrip(b"-").isdigit() and (cell == b"0" or not cell.lstrip(b"-").lstrip(b"0") == b""
                                        ) and not (len(cell.lstrip(b"-")) > 1 and cell.lstrip(b"-")[0:1] == b"0"):
        return int(cell), 0
    return None

def delta_stream(vals, header):
    # [header, anchor, d1, d2, ...] as a single \n-joined byte blob
    out = [header, str(vals[0]).encode()]
    for i in range(1, len(vals)):
        out.append(str(vals[i] - vals[i - 1]).encode())
    return b"\n".join(out)

for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    rows = [r.split(b",") for r in raw.split(b"\n") if r]
    ncol = max(len(r) for r in rows)
    # parse numeric columns (scaled int + scale); header = row0
    cols_scaled = {}
    scales = {}
    headers = {}
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        sv = [scaled(x) for x in cells[1:]]
        if len(sv) >= 3 and all(x is not None for x in sv) and len({s for _, s in sv}) == 1:
            cols_scaled[c] = [v for v, _ in sv]
            scales[c] = sv[0][1]
            headers[c] = cells[0]
    numcols = sorted(cols_scaled)
    # baseline: every numeric column independent delta; non-numeric raw
    base_streams = []
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        if c in cols_scaled:
            base_streams.append(delta_stream(cols_scaled[c], cells[0]))
        else:
            base_streams.append(b"\n".join(cells))
    base = comp(b"\x00".join(base_streams), "base")

    # corra: source = first DECIMAL column (scale>0); residual the other same-scale
    # decimal columns (the correlated group, e.g. forex OHLC / sensor channels). Single
    # source (no expensive search) — representative for OHLC where any leg predicts the
    # others. Per-column competitive: keep min(independent-delta, residual-delta).
    dec_cols = [c for c in numcols if scales[c] > 0]
    if not dec_cols:
        print(f"{name:<22} no decimal columns — skipped")
        continue
    src = dec_cols[0]
    streams = []; n_res = 0
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        if c in cols_scaled and c != src and c in dec_cols and scales[c] == scales[src]:
            resid = [cols_scaled[c][i] - cols_scaled[src][i] for i in range(len(cols_scaled[c]))]
            indep = delta_stream(cols_scaled[c], cells[0])
            res = delta_stream(resid, cells[0])
            streams.append(res if len(res) <= len(indep) else indep)
            if len(res) <= len(indep):
                n_res += 1
        elif c in cols_scaled:
            streams.append(delta_stream(cols_scaled[c], cells[0]))
        else:
            streams.append(b"\n".join(cells))
    best_corra = comp(b"\x00".join(streams), "corra") + n_res  # +1 source-index byte/residual col
    best_src = src
    x = base / best_corra if best_corra else 0
    gate = "GO(>=1.5x)" if x >= 1.5 else "below-1.5x"
    print(f"{name:<22} baseline={base} corra={best_corra} (src=c{best_src}, {n_res} residual-cols) "
          f"=> {x:.2f}x over H-40  {gate}")
for f in os.listdir(SCR):
    if f.startswith("_h49_"):
        os.remove(os.path.join(SCR, f))
