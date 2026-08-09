#!/usr/bin/env python3
"""PROBE NEW-13: typed-column codec bank, competitive-min per column -> order-0 rANS model.

Size model, NOT the codec. Cost of a byte stream = static order-0 entropy bits
+ MDL adaptive-model penalty (k-1)/2 * log2(n) bits (stands in for adaptive rANS /
frequency-table cost). Per Gotcha #6 every decoder branch is charged:
  MAGIC/ver/mode 6 B + orig_len 8 B + stride W 2 B + n_fields 2 B
  + 2 B per field (typed width + codec id + layout flag)  + raw tail bytes.
Gotcha #7: the transpose permutation is fully determined by W (charged, 2 B).

Two passes:
  ceiling : oracle — schema+codec chosen on FULL column stats, zero header.
  probe   : schema+codec chosen on a 4 KB PREFIX of each column, full header charged.
"""
import sys, math, json
import numpy as np

MAX_SLICE = 4 * 1024 * 1024

# ---------- cost model ----------
def h0_bits(b: np.ndarray) -> float:
    """b: uint8 array. static H0 bits + MDL penalty."""
    n = b.size
    if n == 0:
        return 0.0
    c = np.bincount(b, minlength=256).astype(np.float64)
    c = c[c > 0]
    bits = float(n * math.log2(n) - np.sum(c * np.log2(c)))
    k = c.size
    return bits + (k - 1) * 0.5 * math.log2(n + 1)

def stream_cost(b: np.ndarray, t: int) -> tuple[float, int]:
    """cost of a codec output that is m values of t bytes each (uint8 array).
    layout 0 = interleaved, 1 = planar (byte planes). Returns (bits, layout)."""
    if t == 1 or b.size % t != 0:
        return h0_bits(b), 0
    mixed = h0_bits(b)
    planes = b.reshape(-1, t)
    planar = sum(h0_bits(planes[:, i]) for i in range(t))
    return (planar, 1) if planar < mixed else (mixed, 0)

# ---------- codec bank ----------
def to_bytes(v: np.ndarray) -> np.ndarray:
    return np.frombuffer(v.tobytes(), dtype=np.uint8)

def wrapping_delta(v: np.ndarray) -> np.ndarray:
    d = v.copy()
    d[1:] = v[1:] - v[:-1]          # uint wraparound
    return d

def zigzag(v: np.ndarray) -> np.ndarray:
    bits = v.dtype.itemsize * 8
    s = v.view(np.dtype(v.dtype.str.replace('u', 'i')))
    with np.errstate(over='ignore'):
        z = (s.astype(s.dtype) << 1) ^ (s >> (bits - 1))
    return z.view(v.dtype)

def bank_costs(col_bytes: np.ndarray, t: int) -> dict:
    """col_bytes: uint8 (m*t,) column stream (record-major). Returns codec -> (bits, layout)."""
    m = col_bytes.size // t
    out = {}
    out['raw'] = stream_cost(col_bytes, t)
    if t == 1:
        v_le = col_bytes.copy()
    else:
        v_le = np.frombuffer(col_bytes.tobytes(), dtype=f'<u{t}').copy()
    # arithmetic delta LE
    d_le = wrapping_delta(v_le)
    out[f'delta-u{t*8}-le'] = stream_cost(to_bytes(d_le.astype(f'<u{t}')), t)
    if t > 1:
        v_be = np.frombuffer(col_bytes.tobytes(), dtype=f'>u{t}').astype(f'<u{t}')
        d_be = wrapping_delta(v_be)
        out[f'delta-u{t*8}-be'] = stream_cost(to_bytes(d_be.astype(f'<u{t}')), t)
    # zigzag(delta) (FOR-style small-magnitude mapping) on LE interpretation
    z = zigzag(d_le.astype(f'<u{t}'))
    out['zigzag-delta'] = stream_cost(to_bytes(z.astype(f'<u{t}')), t)
    # FOR: subtract min
    f = (v_le - v_le.min()).astype(f'<u{t}')
    out['for'] = stream_cost(to_bytes(f), t)
    # XOR-delta (float-style) for 4/8-byte columns
    if t in (4, 8):
        x = v_le.copy()
        x[1:] = v_le[1:] ^ v_le[:-1]
        out[f'xor-delta-f{t*8}'] = stream_cost(to_bytes(x.astype(f'<u{t}')), t)
    # dict
    uniq = np.unique(v_le)
    if uniq.size <= 256:
        idx = np.searchsorted(uniq, v_le).astype(np.uint8)
        bits = h0_bits(idx) + 8 * (t * uniq.size + 2)
        out['dict'] = (bits, 0)
    # RLE on the raw byte stream
    b = col_bytes
    if b.size:
        change = np.empty(b.size, dtype=bool)
        change[0] = True
        change[1:] = b[1:] != b[:-1]
        starts = np.flatnonzero(change)
        lens = np.diff(np.append(starts, b.size))
        vals = b[starts]
        # split runs > 255
        n_extra = int(np.sum((lens - 1) // 255))
        capped_lens = np.minimum(lens, 255).astype(np.uint8)  # model: capped + extras at cap cost
        bits = h0_bits(vals) + h0_bits(capped_lens) + n_extra * 16
        out['rle'] = (bits, 0)
    return out

# ---------- schema search ----------
def greedy_schema(recs: np.ndarray, W: int, prefix_records: int | None):
    """recs: (m, W) uint8. Greedy typed partition; codec picked per field.
    prefix_records: None = oracle (full column); else selection on that many records.
    Returns (fields, total_payload_bits). fields = [(o, t, codec, layout)]."""
    m = recs.shape[0]
    sel = recs if prefix_records is None else recs[:min(m, prefix_records)]
    fields = []
    total_bits = 0.0
    o = 0
    while o < W:
        best = None  # (cost_per_byte, t, codec)
        for t in (8, 4, 2, 1):
            if o + t > W:
                continue
            colb = sel[:, o:o + t].reshape(-1)
            costs = bank_costs(colb, t)
            codec, (bits, layout) = min(costs.items(), key=lambda kv: kv[1][0])
            cpb = bits / max(1, colb.size)
            if best is None or cpb < best[0]:
                best = (cpb, t, codec)
        _, t, codec = best
        # charge FULL column with the chosen codec (re-evaluate that codec on full data)
        colb_full = recs[:, o:o + t].reshape(-1)
        full_costs = bank_costs(colb_full, t)
        if prefix_records is None:
            codec, (bits, layout) = min(full_costs.items(), key=lambda kv: kv[1][0])
        else:
            bits, layout = full_costs[codec]
        fields.append((o, t, codec, layout))
        total_bits += bits
        o += t
    return fields, total_bits

# ---------- stride detection ----------
def detect_stride(data: np.ndarray, wmax=512):
    n = min(data.size, 1 << 19)
    x = data[:n].astype(np.int16)
    costs = {}
    for w in range(4, wmax + 1):
        if data.size // w < 8:
            break
        costs[w] = float(np.mean(np.abs(x[w:] - x[:-w])))
    if not costs:
        return None
    vals = sorted(costs.values())
    best = vals[0]
    median = vals[len(vals) // 2]
    if best >= 0.8 * median:
        return None
    thresh = best * 1.03
    for w in sorted(costs):
        if costs[w] <= thresh:
            return w
    return None

# ---------- main ----------
def run(path, name, force_w=None):
    raw = np.fromfile(path, dtype=np.uint8)
    orig = raw.size
    data = raw[:MAX_SLICE]
    sliced = data.size < orig
    W = force_w if force_w else detect_stride(data)
    res = {'file': name, 'orig': orig, 'slice': int(data.size), 'sliced': bool(sliced),
           'stride': W}
    if W is None:
        res['verdict'] = 'no-stride'
        print(json.dumps(res))
        return
    m = data.size // W
    recs = data[:m * W].reshape(m, W)
    tail = data.size - m * W

    # ceiling pass (oracle, zero header)
    f_o, bits_o = greedy_schema(recs, W, None)
    ceiling_bytes = bits_o / 8 + tail
    # probe pass (4KB prefix per column: 4096 values -> use 4096 records)
    f_p, bits_p = greedy_schema(recs, W, 4096)
    n_fields = len(f_p)
    header = 6 + 8 + 2 + 2 + 2 * n_fields
    probe_bytes = bits_p / 8 + header + tail

    res.update(n_fields=n_fields,
               oracle_fields=[(o, t, c, l) for o, t, c, l in f_o],
               probe_fields=[(o, t, c, l) for o, t, c, l in f_p],
               ceiling_bytes=round(ceiling_bytes),
               probe_bytes=round(probe_bytes),
               ceiling_ratio_slice=ceiling_bytes / data.size,
               probe_ratio_slice=probe_bytes / data.size)
    print(json.dumps(res))

def criteria(path, name, W, float_fields):
    """Routing criteria on real columns. float_fields: [(offset, t)] known float cols."""
    raw = np.fromfile(path, dtype=np.uint8)
    data = raw[:MAX_SLICE]
    m = data.size // W
    recs = data[:m * W].reshape(m, W)
    out = {'file': name, 'criteria': []}
    for o, t in float_fields:
        colb = recs[:, o:o + t].reshape(-1)
        costs = bank_costs(colb, t)
        xor = costs.get(f'xor-delta-f{t*8}', (float('inf'), 0))[0]
        delta = costs[f'delta-u{t*8}-le'][0]
        raw_c = costs['raw'][0]
        out['criteria'].append({'kind': 'float-xor-vs-delta', 'offset': o, 't': t,
                                'xor_bits': round(xor), 'delta_bits': round(delta),
                                'raw_bits': round(raw_c),
                                'xor_gain_vs_delta_pct': 100 * (1 - xor / delta)})
    # int8 RLE vs raw: scan all 1-byte columns, report best RLE gain
    best = None
    for o in range(W):
        colb = recs[:, o].reshape(-1)
        costs = bank_costs(colb, 1)
        r = costs['rle'][0]; rw = costs['raw'][0]
        gain = 100 * (1 - r / rw) if rw > 0 else 0
        if best is None or gain > best['rle_gain_vs_raw_pct']:
            best = {'kind': 'int8-rle-vs-raw', 'offset': o, 'rle_bits': round(r),
                    'raw_bits': round(rw), 'rle_gain_vs_raw_pct': gain}
    out['criteria'].append(best)
    print(json.dumps(out))

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'run':
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif mode == 'stride':
        d = np.fromfile(sys.argv[2], dtype=np.uint8)[:MAX_SLICE]
        print(sys.argv[3], detect_stride(d))
    elif mode == 'criteria':
        criteria(sys.argv[2], sys.argv[3], int(sys.argv[4]),
                 json.loads(sys.argv[5]))
