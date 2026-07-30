#!/usr/bin/env python3
"""H-36 MANDATORY spike gate: does a CLP-style log-template / variable split reach
>=1.5x over zstd-19 on REAL log data? If not -> honest NO-GO, no Rust parser.

Faithful + fully charged (Gotcha #6 — every decoder stream is a cost term):
the transform decomposes each log line into
  - a TEMPLATE (static skeleton, digit-bearing tokens replaced by a placeholder),
  - a TEMPLATE-ID per line (references the template dictionary),
  - VARIABLE streams grouped COLUMNAR by (template-id, variable-position) so same-slot
    values cluster (CLP's core lever); numeric monotonic var-columns are delta-coded
    (H-31 lever — captures timestamps/counters).
Every stream is serialized and compressed by the REAL cubrim binary (bwt-rans rail),
plus a charged framing estimate. Total is compared to zstd-19 on the raw file.

GO gate: total_clp <= zstd19 / 1.5  (i.e. >=1.5x over zstd-19). Numbers per corpus file.
"""
import re, sys, subprocess, os
from collections import defaultdict

BIN, SCR = sys.argv[1], sys.argv[2]
FILES = sys.argv[3:]
PLACEHOLDER = b"\x01"
# A "variable" token = a whitespace-delimited run that contains a digit (timestamps,
# pids, ips, hex addrs, numbers, ids). Static tokens repeat -> become the template.
VAR = re.compile(rb"\S*\d\S*")

def comp(data: bytes, tag: str) -> int:
    if not data:
        return 0
    p = os.path.join(SCR, f"_h36_{tag}.bin"); open(p, "wb").write(data)
    out = p + ".cbr"
    subprocess.run([BIN, "compress", p, out, "--value-scheme", "bwt-rans"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return os.path.getsize(out)

def zstd19(path: str) -> int:
    return len(subprocess.run(["zstd", "-19", "-c", path], capture_output=True).stdout)

def gzip9(path: str) -> int:
    return len(subprocess.run(["gzip", "-9", "-c", path], capture_output=True).stdout)

def varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F; v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)

def canon_int(cell: bytes):
    try:
        v = int(cell.decode("latin1"))
    except (ValueError, UnicodeDecodeError):
        return None
    return v if str(v).encode() == cell else None

def col_serialize(values):
    """Serialize one variable column; delta-code if canonical non-decreasing ints."""
    ints = [canon_int(v) for v in values]
    if len(values) >= 3 and all(i is not None for i in ints) and all(
        ints[j] >= ints[j - 1] for j in range(1, len(ints))
    ):
        out = [values[0]]
        for j in range(1, len(values)):
            out.append(str(ints[j] - ints[j - 1]).encode())
        return b"\n".join(out)
    return b"\n".join(values)

# Leading timestamp: syslog "Mon DD HH:MM:SS" or ISO8601 "YYYY-MM-DDTHH:MM:SS".
TS_SYSLOG = re.compile(rb"^[A-Z][a-z]{2}\s+(\d+)\s+(\d{2}):(\d{2}):(\d{2})")
TS_ISO = re.compile(rb"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})")

def extract_ts(line):
    """Return (epoch_like_int, rest_bytes) if a leading timestamp parses, else (None,line)."""
    m = TS_SYSLOG.match(line)
    if m:
        d, h, mi, s = (int(x) for x in m.groups())
        return d * 86400 + h * 3600 + mi * 60 + s, line[m.end():]
    m = TS_ISO.match(line)
    if m:
        Y, Mo, D, h, mi, s = (int(x) for x in m.groups())
        return ((Y * 12 + Mo) * 31 + D) * 86400 + h * 3600 + mi * 60 + s, line[m.end():]
    return None, line

def clp_size(raw: bytes, ts_aware: bool):
    lines = raw.split(b"\n")
    ends_nl = raw.endswith(b"\n")
    if ends_nl:
        lines = lines[:-1]
    templates = {}
    tmpl_ids = []
    var_cols = defaultdict(list)  # (tid, pos) -> [value, ...]
    ts_vals = []  # extracted leading timestamps (delta-coded as its own stream)
    has_ts = []
    for line in lines:
        if ts_aware:
            ts, rest = extract_ts(line)
            if ts is not None:
                ts_vals.append(ts); has_ts.append(1)
                line = rest
            else:
                has_ts.append(0)
        vs = []
        templ = VAR.sub(lambda m: (vs.append(m.group(0)) or PLACEHOLDER), line)
        tid = templates.setdefault(bytes(templ), len(templates))
        tmpl_ids.append(tid)
        for i, v in enumerate(vs):
            var_cols[(tid, i)].append(v)
    tmpl_dict = b"\n".join(t for t, _ in sorted(templates.items(), key=lambda kv: kv[1]))
    id_stream = b"".join(varint(t) for t in tmpl_ids)
    var_blob = b"\x00".join(col_serialize(v) for _, v in sorted(var_cols.items()))
    s_dict = comp(tmpl_dict, "dict")
    s_ids = comp(id_stream, "ids")
    s_var = comp(var_blob, "var")
    s_ts = 0
    if ts_aware and ts_vals:
        # delta-code the timestamp column (monotone within a day; charge as ascii deltas)
        prev = ts_vals[0]; dts = [str(ts_vals[0]).encode()]
        for v in ts_vals[1:]:
            dts.append(str(v - prev).encode()); prev = v
        s_ts = comp(b"\n".join(dts), "ts") + comp(bytes(has_ts), "hasts")
    framing = 16 + 4 * 4
    total = s_dict + s_ids + s_var + s_ts + framing
    return total, (len(templates), len(lines), len(var_cols), s_dict, s_ids, s_var, s_ts)

print(f"{'file':<18}{'raw':>9}{'zstd19':>8}{'CLP':>8}{'CLP+ts':>8}{'best x':>8}  breakdown(d/i/v/ts ntmpl)")
for path in FILES:
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    z = zstd19(path)
    t0, _ = clp_size(raw, ts_aware=False)
    t1, (ntmpl, nlines, nvc, sd, si, sv, sts) = clp_size(raw, ts_aware=True)
    best = min(t0, t1)
    x = z / best if best else 0
    gate = "GO(>=1.5x)" if x >= 1.5 else "below-1.5x"
    print(f"{name:<18}{len(raw):>9}{z:>8}{t0:>8}{t1:>8}{x:>7.2f}x  "
          f"d={sd} i={si} v={sv} ts={sts} ntmpl={ntmpl}/{nlines}  {gate}")
for f in os.listdir(SCR):
    if f.startswith("_h36_"):
        os.remove(os.path.join(SCR, f))
