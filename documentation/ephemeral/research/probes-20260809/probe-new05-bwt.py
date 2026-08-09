#!/usr/bin/env python3
"""PROBE NEW-05: whole-file / large-block BWT + conditional-entropy model.

Gotcha #3 gate: order-1 conditional entropy of the BWT-reordered stream vs the
unreordered stream (identical adaptive KT estimator both sides).
Gotcha #6/#7: charged size model for a hypothetical MODE_BIGBWT_CM wire — one
cost term per decoder branch; the BWT primary index (a transmitted permutation
anchor) is charged as its own branch per block.

All figures this script prints are PROBE figures (models, not the codec).
"""
import math
import sys
import time


def suffix_array(s):
    """Prefix-doubling suffix array over list of ints (sentinel already appended)."""
    n = len(s)
    rank = list(s)
    sa = list(range(n))
    k = 1
    tmp = [0] * n
    while True:
        def key(i):
            return (rank[i], rank[i + k] if i + k < n else -1)
        sa.sort(key=key)
        tmp[sa[0]] = 0
        prev = key(sa[0])
        for j in range(1, n):
            cur = key(sa[j])
            tmp[sa[j]] = tmp[sa[j - 1]] + (1 if cur != prev else 0)
            prev = cur
        rank, tmp = tmp, rank
        if rank[sa[-1]] == n - 1:
            return sa
        k *= 2


def bwt(data):
    """Return (bwt_bytes, primary_index). Sentinel = 256 (not emitted)."""
    s = list(data) + [256]
    sa = suffix_array(s)
    out = []
    primary = -1
    for r, p in enumerate(sa):
        if p == 0:
            primary = r  # row of the sentinel-preceded rotation; not emitted
            continue
        out.append(s[p - 1])
    # drop the sentinel symbol itself (it appears as predecessor of suffix 1... it
    # appears where p-1 == n-1 i.e. the sentinel byte); filter it:
    out = [c for c in out if c != 256]
    return bytes(out), primary


def order_n_adaptive_bits(data, order):
    """Adaptive KT-style estimator, alphabet 256, ctx = previous `order` bytes.

    cost = sum -log2((c+0.5)/(t+128)). Same estimator for both streams -> fair
    Gotcha #3 comparison.
    """
    counts = {}
    bits = 0.0
    ctx = b"\x00" * order
    for b in data:
        tbl = counts.get(ctx)
        if tbl is None:
            tbl = [0, {}]  # [total, {sym: count}]
            counts[ctx] = tbl
        c = tbl[1].get(b, 0)
        bits += -math.log2((c + 0.5) / (tbl[0] + 128.0))
        tbl[1][b] = c + 1
        tbl[0] += 1
        ctx = (ctx + bytes([b]))[-order:] if order else ctx
    return bits


def charged_size(payload_bits, n_blocks):
    """Gotcha #6 charged wire model for MODE_BIGBWT_CM.

    Decoder branches / cost terms:
      1. mode byte                     : 1 B
      2. orig_len u64                  : 8 B
      3. block_size u32 + n_blocks u32 : 8 B
      4. per block primary_index u32   : 4 B  (Gotcha #7: transmitted permutation anchor)
      5. per block comp_len u32        : 4 B
      6. per block range-coder flush   : 8 B
      7. CM payload                    : payload_bits / 8
    """
    return 17 + n_blocks * 16 + payload_bits / 8.0


def run(path, label, block_size=None, slice_bytes=None):
    data = open(path, "rb").read()
    sliced = False
    if slice_bytes and len(data) > slice_bytes:
        data = data[:slice_bytes]
        sliced = True
    n = len(data)
    if block_size is None:
        block_size = n  # whole-file = large-block regime FU-01 would enable
    t0 = time.time()
    blocks = [data[i:i + block_size] for i in range(0, n, block_size)]
    bwt_stream = bytearray()
    for blk in blocks:
        out, _ = bwt(blk)
        bwt_stream += out
    t_bwt = time.time() - t0
    raw_o1 = order_n_adaptive_bits(data, 1)
    bwt_o1 = order_n_adaptive_bits(bytes(bwt_stream), 1)
    bwt_o2 = order_n_adaptive_bits(bytes(bwt_stream), 2)
    raw_o2 = order_n_adaptive_bits(data, 2)
    nb = len(blocks)
    print(f"== {label}{' [SLICE]' if sliced else ''} n={n} blocks={nb} block_size={block_size} bwt_time={t_bwt:.1f}s")
    for name, bits in (("raw order-1", raw_o1), ("bwt order-1", bwt_o1),
                       ("raw order-2", raw_o2), ("bwt order-2", bwt_o2)):
        print(f"  PROBE {name}: {bits/8:.0f} B  ({bits/n:.4f} bpc)  ratio {bits/8/n:.5f}")
    for name, bits in (("bwt order-1", bwt_o1), ("bwt order-2", bwt_o2)):
        ch = charged_size(bits, nb)
        print(f"  PROBE charged MODE_BIGBWT_CM ({name} payload): {ch:.0f} B  ratio {ch/n:.5f}")
    sys.stdout.flush()


if __name__ == "__main__":
    corp_cant = "/home/dev/cubr-cubecore-research"  # not used; canterbury lives in worktree? resolved by args
    for spec in sys.argv[1:]:
        path, label, bs, sl = spec.split(",")
        run(path, label, int(bs) if bs != "-" else None, int(sl) if sl != "-" else None)
