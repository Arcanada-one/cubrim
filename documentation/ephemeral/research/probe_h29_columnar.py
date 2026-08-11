#!/usr/bin/env python3
"""H-29 charged probe: does a reversible COLUMNAR field-split (+ optional monotonic
delta) preprocessing transform let Cubrim beat zstd-19 on the CSV/columnar sub-class?

Faithful: the transformed bytes are compressed by the REAL cubrim binary
(--value-scheme bwt-rans = competitive rail), so the number is what a shipped
MODE_COLUMNAR container would realize (modulo a tiny reversibility header that we
charge explicitly). Info-conservation safe: field boundaries are kept as separators,
so the transform is exactly invertible (Gotcha #8 — nothing re-transmitted hidden).

Variants per file:
  row   = current row-order (baseline, what cubrim ships today)
  col   = column-major reorder (all col0 cells, then col1, ...), separators kept
  cold  = col + first-order delta on columns detected monotonic-ish numeric

Header charged: 16 B fixed (n_rows u32, n_cols u32, flags). Compared to gzip-9 / zstd-19.
"""
import sys, subprocess, os, tempfile

BIN = sys.argv[1]
SCR = sys.argv[2]
FILES = sys.argv[3:]
HEADER = 16  # n_rows + n_cols + per-col delta-flag bitmap (charged, generous)

def comp(data: bytes, tag: str) -> int:
    p = os.path.join(SCR, f"_probe_{tag}.bin")
    with open(p, "wb") as f:
        f.write(data)
    out = p + ".cbr"
    subprocess.run([BIN, "compress", p, out, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(out)

def gz(path): return len(subprocess.run(["gzip","-9","-c",path],capture_output=True).stdout)
def zs(path):
    return len(subprocess.run(["zstd","-19","-c",path],capture_output=True).stdout)

def parse_csv(raw: bytes):
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    rows = [ln.split(b",") for ln in lines]
    ncol = max((len(r) for r in rows), default=0)
    return rows, ncol

def col_major(rows, ncol) -> bytes:
    cols = []
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        cols.append(b"\n".join(cells))
    return b"\x00".join(cols)

def is_num(b: bytes) -> bool:
    s = b.decode("latin1").strip()
    if not s: return False
    try:
        float(s); return True
    except ValueError:
        return False

def col_major_delta(rows, ncol):
    """Delta-code columns that are integer-ish and mostly monotonic (timestamps/ids).
    Reversible: store first value raw, then ascii deltas. Non-numeric cols unchanged."""
    cols_out = []
    delta_flags = []
    for c in range(ncol):
        cells = [r[c] if c < len(r) else b"" for r in rows]
        # detect integer monotonic-ish
        vals = []
        ok = True
        for cell in cells:
            s = cell.decode("latin1").strip()
            if s.lstrip("-").isdigit():
                vals.append(int(s))
            else:
                ok = False; break
        if ok and len(vals) >= 8:
            inc = sum(1 for i in range(1, len(vals)) if vals[i] >= vals[i-1])
            if inc >= 0.9 * (len(vals)-1):
                deltas = [str(vals[0]).encode()]
                for i in range(1, len(vals)):
                    deltas.append(str(vals[i]-vals[i-1]).encode())
                cols_out.append(b"\n".join(deltas)); delta_flags.append(1); continue
        cols_out.append(b"\n".join(cells)); delta_flags.append(0)
    return b"\x00".join(cols_out), delta_flags

print(f"{'file':<22}{'rowC':>8}{'colC':>8}{'colDC':>8}{'gzip':>8}{'zstd':>8}  best-vs-zstd")
for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    rows, ncol = parse_csv(raw)
    row_c = comp(raw, "row")
    col_c = comp(col_major(rows, ncol), "col") + HEADER
    cmd_bytes, flags = col_major_delta(rows, ncol)
    cold_c = comp(cmd_bytes, "cold") + HEADER
    g = gz(path); z = zs(path)
    best = min(col_c, cold_c)
    verdict = f"{100*(best-z)/z:+.1f}% (col {100*(col_c-z)/z:+.1f}, cold {100*(cold_c-z)/z:+.1f}; row {100*(row_c-z)/z:+.1f}); delta_cols={sum(flags)}"
    print(f"{name:<22}{row_c:>8}{col_c:>8}{cold_c:>8}{g:>8}{z:>8}  {verdict}")
