#!/usr/bin/env python3
"""H-28 charged probe: can a higher-order / context-mixing / PPM literal model beat
the current order-0 rANS literal coder on the MODE_LZ literal residue?

The current MODE_LZ literal coder picks min over {nested cube/BWT/geomix, order-0
rANS, order-1 rANS}. On the mixed/near-duplicate fixtures the OPTIMAL-parse residue
is coded by order-0 rANS (lit_kind=1) -- order-1 (full-table) and BWT+geomix both
LOST. The brief asks whether an ADAPTIVE order-2+ / PPM model (online learning, no
transmitted tables) recovers the residual zstd gap.

Per Gotcha #9 the order-1 entropy probe is an ASYMPTOTIC floor; we must charge a
REAL online adaptive predictor (the bits an actual range coder pays while LEARNING
the distribution) and do a cell-count / stream-length sanity. We report, for the
ACTUAL literal stream the codec serialises:

  ideal  H0, H1, H2, H3   (knowledge-of-distribution lower bound, in bytes)
  real   adaptive order-0..3 (KT online predictor, NO table)         <- charged
  real   PPM-C-style escape blend (order-3 backoff, no table)         <- charged
  current order-0 rANS bytes (= lit_blob_len, charged with its table)

GO only if a charged real model beats the current bytes by a margin that meaningfully
dents the gap to zstd. Otherwise the literal floor is data-determined.
"""
import sys, math
from collections import defaultdict

def load(path):
    with open(path, "rb") as f:
        return f.read()

def ideal_Hk(data, k):
    """Ideal conditional entropy H(X_t | previous k bytes), total BITS (lower bound)."""
    ctx_counts = defaultdict(lambda: defaultdict(int))
    ctx_total = defaultdict(int)
    for i in range(len(data)):
        ctx = bytes(data[max(0, i - k):i])
        ctx_counts[ctx][data[i]] += 1
        ctx_total[ctx] += 1
    bits = 0.0
    for ctx, syms in ctx_counts.items():
        n = ctx_total[ctx]
        for c in syms.values():
            p = c / n
            bits -= c * math.log2(p)
    return bits

def adaptive_order_k(data, k, alpha=0.5):
    """REAL online cost: a KT-ish adaptive coder over a 256 alphabet, contexted on the
    previous k bytes, learning counts as it goes (no transmitted table). Returns BITS.
    This is what an actual adaptive range coder pays, learning cost included."""
    A = 256
    counts = defaultdict(lambda: [0] * A)
    totals = defaultdict(int)
    bits = 0.0
    for i in range(len(data)):
        ctx = bytes(data[max(0, i - k):i])
        sym = data[i]
        c = counts[ctx]
        t = totals[ctx]
        # KT estimator: p(sym) = (c[sym] + alpha) / (t + alpha*A)
        p = (c[sym] + alpha) / (t + alpha * A)
        bits -= math.log2(p)
        c[sym] += 1
        totals[ctx] += 1
    return bits

def adaptive_ppm(data, max_order=3, alpha=0.5):
    """PPM-C-ish escape blend: try highest order; if symbol unseen in that context,
    pay an escape (count of distinct syms as escape mass) and fall back. NO table.
    Approximation of a real PPM range coder's charged cost in BITS."""
    A = 256
    counts = [defaultdict(lambda: [0] * A) for _ in range(max_order + 1)]
    totals = [defaultdict(int) for _ in range(max_order + 1)]
    distinct = [defaultdict(int) for _ in range(max_order + 1)]  # PPM-C escape = #distinct
    bits = 0.0
    for i in range(len(data)):
        sym = data[i]
        excluded = set()
        coded = False
        for k in range(max_order, -1, -1):
            ctx = bytes(data[max(0, i - k):i])
            c = counts[k][ctx]
            t = totals[k][ctx]
            d = distinct[k][ctx]
            if t == 0:
                continue  # empty context -> implicit escape, no cost
            esc = d  # PPM-C escape count
            denom = t + esc
            # mass available to non-excluded seen symbols
            seen_mass = sum(c[s] for s in range(A) if c[s] > 0 and s not in excluded)
            if c[sym] > 0 and sym not in excluded:
                p = c[sym] / denom
                bits -= math.log2(p)
                coded = True
                break
            else:
                # pay escape
                if esc > 0:
                    p_esc = esc / denom
                    bits -= math.log2(p_esc)
                excluded.update(s for s in range(A) if c[s] > 0)
        if not coded:
            # order -1 uniform over remaining alphabet
            remaining = A - len(excluded)
            bits -= math.log2(1.0 / max(1, remaining))
        # update all orders
        for k in range(max_order + 1):
            ctx = bytes(data[max(0, i - k):i])
            if counts[k][ctx][sym] == 0:
                distinct[k][ctx] += 1
            counts[k][ctx][sym] += 1
            totals[k][ctx] += 1
    return bits

def cell_sanity(data, k):
    A = 256
    ctx_seen = set()
    for i in range(len(data)):
        ctx_seen.add(bytes(data[max(0, i - k):i]))
    n = len(data)
    nctx = len(ctx_seen)
    cells = nctx * A
    return nctx, cells, n, n / cells if cells else 0.0

def main():
    for label, path, cur_bytes, zstd_gap in [
        ("srctree.tar", sys.argv[1], int(sys.argv[2]), int(sys.argv[3])),
        ("multiversion.bin", sys.argv[4], int(sys.argv[5]), int(sys.argv[6])),
    ]:
        data = load(path)
        n = len(data)
        print(f"\n===== {label}  literal stream n={n}  current order-0 rANS={cur_bytes} B  "
              f"(gap to zstd on whole file = {zstd_gap} B) =====")
        # ideal lower bounds
        for k in (0, 1, 2, 3):
            ib = ideal_Hk(data, k) / 8.0
            print(f"  ideal  H{k}: {ib:9.1f} B")
        # real adaptive (charged, learning included)
        for k in (0, 1, 2, 3):
            rb = adaptive_order_k(data, k) / 8.0
            nctx, cells, _, obs = cell_sanity(data, k)
            mark = "  <-- current rANS pays %d" % cur_bytes if k <= 1 else ""
            print(f"  real adaptive o{k}: {rb:9.1f} B   "
                  f"[ctx_seen={nctx} cells={cells} obs/cell={obs:.3f}]{mark}")
        ppm = adaptive_ppm(data, 3) / 8.0
        print(f"  real PPM-C (o3 escape): {ppm:9.1f} B")
        # verdict math
        best_real = min(
            adaptive_order_k(data, 0) / 8.0,
            adaptive_order_k(data, 1) / 8.0,
            adaptive_order_k(data, 2) / 8.0,
            adaptive_order_k(data, 3) / 8.0,
            ppm,
        )
        save = cur_bytes - best_real
        print(f"  >>> best charged real model = {best_real:.1f} B  vs current {cur_bytes} B  "
              f"=> save {save:.1f} B ({100*save/cur_bytes:.1f}%); "
              f"closes {100*save/zstd_gap:.1f}% of the zstd gap")

if __name__ == "__main__":
    main()
