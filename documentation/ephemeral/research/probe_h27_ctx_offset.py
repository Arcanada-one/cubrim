#!/usr/bin/env python3
"""H-27 charged probe: how much can CONTEXT-modelling the offset code save vs the
current context-free byte-split order-0 coder?

The current coder (lz_encode_token_streams) splits each NEW distance into bytes
b0..b3 and codes each stream order-0. zstd-class btultra2 contexts its offset-code
on recent state. We measure, on the ACTUAL new-distance sequence (rep-cache applied,
exactly what the coder serialises):

  - per byte-split stream: H0 (order-0), H1 (order-1 prev-byte), delta+H0
  - the offset-code (bucket) stream: H0, H1(|prev bucket), H1(|match-len class)

Gain ceiling = (context-free total) - (best-context total). The raw low bits inside
a bucket are incompressible; only the inter-symbol structure is contextable. Table
cost is NOT charged here (this is the optimistic ceiling — a GO must clear it with
margin so the real per-context rANS tables still net positive: Gotcha #6).
"""
import sys, math
from collections import Counter, defaultdict

REP_INIT = [1, 4, 8]

def ent(counts, n):
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / n; h -= p * math.log2(p)
    return h

def H0(stream):
    return ent(Counter(stream).values(), len(stream)) * len(stream) if stream else 0.0

def H1(stream, ctx):
    """Conditional bits of `stream` given parallel context list `ctx`."""
    groups = defaultdict(list)
    for v, c in zip(stream, ctx):
        groups[c].append(v)
    return sum(H0(g) for g in groups.values())

def bit_length(v):
    return v.bit_length()

def new_distances(path):
    """Replay rep-cache; return the NEW distances in serialisation order + the
    match-length of each new-distance match (for len-class context)."""
    rep = list(REP_INIT)
    new_d, new_len = [], []
    for line in open(path):
        fl, ln, ds = (int(x) for x in line.strip().split(","))
        if fl == 0:
            continue
        if ds == rep[0]:
            pass
        elif ds == rep[1]:
            rep[0], rep[1] = rep[1], rep[0]
        elif ds == rep[2]:
            rep[2], rep[1], rep[0] = rep[1], rep[0], rep[2]
        else:
            new_d.append(ds); new_len.append(ln)
            rep[2], rep[1], rep[0] = rep[1], rep[0], ds
    return new_d, new_len

def main(path, tag):
    nd, nl = new_distances(path)
    n = len(nd)
    print(f"### {tag}: new_distances={n}")
    b = [[(d >> (8 * k)) & 0xFF for d in nd] for k in range(4)]
    # context-free total (current coder model)
    cf = sum(H0(b[k]) for k in range(4))
    print(f"  context-free byte-split order-0 total = {cf/8:9.0f} B")
    # static order-1 table cost (mirror rans_order1_encode: per ctx with >=16 obs,
    # 2 + sum nonzero*(3) bytes + 2 ctx_id; plus one fallback table).
    def static_o1_table_bytes(stream):
        ctxg = defaultdict(Counter)
        prev = 0
        for v in stream:
            ctxg[prev][v] += 1; prev = v
        # fallback table = all nonzero syms
        allnz = len(set(stream))
        tb = 2 + 3 * allnz
        for c, cnt in ctxg.items():
            if sum(cnt.values()) >= 16:
                tb += 2 + (2 + 3 * len(cnt))   # ctx_id + table
        return tb

    # per-stream order-1 (prev byte) — IDEAL (no table) and STATIC (real rANS table)
    ctx_total = 0.0
    static_total = 0.0
    for k in range(4):
        h0 = H0(b[k])
        prev = [0] + b[k][:-1]
        h1 = H1(b[k], prev)
        ctx_total += min(h0, h1)
        tb = static_o1_table_bytes(b[k])
        static_total += min(h0 / 8, h1 / 8 + tb)
        if h0 > 0:
            print(f"    b{k}: H0 {h0/8:8.0f} B  H1|prev(ideal) {h1/8:8.0f} B  "
                  f"static-o1-table +{tb:6d} B -> real {h1/8+tb:8.0f} B  ({100*(h0-h1)/h0:+.1f}% ideal)")
    print(f"  byte-split order-1 IDEAL (adaptive, no tables)   = {ctx_total/8:9.0f} B  "
          f"({100*(cf-ctx_total)/cf:+.1f}% vs context-free)")
    print(f"  byte-split order-1 STATIC rANS (per-ctx tables)  = {static_total:9.0f} B  "
          f"({100*(cf/8-static_total)/(cf/8):+.1f}% vs context-free)")

    # delta-coding the high bytes (near-duplicate drift detector)
    delta_total = 0.0
    for k in range(4):
        prev = 0; dl = []
        for d in nd:
            v = (d >> (8 * k)) & 0xFF
            dl.append((v - prev) & 0xFF); prev = v
        delta_total += min(H0(b[k]), H0(dl))
    print(f"  byte-split delta-or-order0 best total   = {delta_total/8:9.0f} B  "
          f"({100*(cf-delta_total)/cf:+.1f}% vs context-free)")

    # REALISTIC adaptive coders (what an online range coder actually achieves,
    # learning cost included; KT +0.5 smoothing). This is the honest GO bar — the
    # ideal H1 above assumes perfect learning over 256x256 cells the stream is too
    # short to populate.
    def adaptive_bits(stream, ctx_of):
        """-sum log2 P(sym|ctx) with online KT(0.5) per-context counts (alphabet 256)."""
        from collections import defaultdict as dd
        counts = dd(lambda: [0.0] * 256)
        totals = dd(float)
        bits = 0.0
        prev = 0
        for v in stream:
            c = ctx_of(prev, v, stream)
            tab = counts[c]; tot = totals[c]
            p = (tab[v] + 0.5) / (tot + 128.0)  # KT, alphabet 256
            bits -= math.log2(p)
            tab[v] += 1.0; totals[c] = tot + 1.0
            prev = v
        return bits
    ad0 = sum(adaptive_bits(b[k], lambda pv, v, s: 0) for k in range(4))          # adaptive order-0
    ad1 = sum(adaptive_bits(b[k], lambda pv, v, s: pv) for k in range(4))         # adaptive order-1 prev-byte
    print(f"  ADAPTIVE order-0 (real)                 = {ad0/8:9.0f} B")
    print(f"  ADAPTIVE order-1 prev-byte (real GO bar)= {ad1/8:9.0f} B  "
          f"({100*(ad0-ad1)/ad0:+.1f}% vs adaptive o0 | {100*(cf-ad1)/cf:+.1f}% vs current order-0 {cf/8:.0f})")

    # offset-code (bucket) stream: H0 vs contexts. raw low bits are a fixed floor.
    oc = [bit_length(d) for d in nd]
    raw = sum(max(0, c - 1) for c in oc)
    h0 = H0(oc)
    h1p = H1(oc, [0] + oc[:-1])
    lenclass = [min(bit_length(l), 8) for l in nl]
    h1l = H1(oc, lenclass)
    print(f"  offcode: raw-low-bits floor {raw/8:8.0f} B + bucket H0 {h0/8:6.0f} "
          f"/ H1|prevbucket {h1p/8:6.0f} / H1|lenclass {h1l/8:6.0f} B")
    best_oc = (raw + min(h0, h1p, h1l)) / 8
    print(f"  offcode best total = {best_oc:9.0f} B  (byte-split is "
          f"{'better' if cf/8 < best_oc else 'worse'}: cf {cf/8:.0f})")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
