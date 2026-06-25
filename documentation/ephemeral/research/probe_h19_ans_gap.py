#!/usr/bin/env python3
"""H-19 go/no-go probe: Huffman→entropy gap = the ceiling on ANS/tANS gain.

ANS/range coding reaches the order-k entropy bound to within a fraction of a
bit total; Huffman pays an integer-bit rounding penalty per symbol (up to ~1
bit/symbol, worse for skewed alphabets). The MAX possible ANS win is therefore
(Huffman_bits - H_bound_bits) over the value-code stream, minus ANS's own table
overhead (same frequency table Huffman ships, so ~neutral). If that gap is tiny
relative to the leader's blob, ANS is NO-GO before any Rust — analogue of the
Gotcha #3 entropy probe.

We reconstruct the i-order value-code stream exactly as the codec does
(Gotcha #5): map each distinct value to a code by descending frequency, read
linearly in i-order. We then compare, on the BWT-transformed stream (the
leader's input to its order-1 Huffman) AND the plain i-order stream:
  - order-1 canonical Huffman cost (integer code lengths, per-context tables)
  - order-1 entropy bound  H(X_t|X_{t-1}) * N   (what ANS approaches)
"""
import math, sys
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]

def value_codes(data):
    """i-order value-code stream: code = rank of value by descending freq."""
    freq = Counter(data)
    order = sorted(freq, key=lambda v: (-freq[v], v))
    v2c = {v:i for i,v in enumerate(order)}
    return [v2c[b] for b in data]

def bwt(seq):
    """BWT of a symbol sequence; returns transformed sequence (codec uses this
    on the value-code stream for the leader scheme). O(n log n) via rotations."""
    n=len(seq)
    if n==0: return seq
    rot=sorted(range(n), key=lambda i: seq[i:]+seq[:i])
    return [seq[(i-1)%n] for i in rot]

def canonical_huffman_bits_order1(seq):
    """Cost of order-1 context Huffman: for each previous symbol, a separate
    Huffman code table over next symbols. Integer code lengths (canonical
    Huffman). Returns bitstream bits (excludes table headers — we compare the
    SAME tables for ANS, so table cost cancels in the gap)."""
    ctx = defaultdict(Counter)
    prev=None
    for s in seq:
        ctx[prev][s]+=1
        prev=s
    bits=0
    for c,counts in ctx.items():
        bits += huffman_cost(counts)
    return bits

def huffman_cost(counts):
    """Total bits to code a multiset under canonical Huffman (integer lengths)."""
    syms=list(counts.items())
    if len(syms)==1:
        return counts[syms[0][0]]*1  # single symbol still costs >=1 bit/sym in a stream
    import heapq
    heap=[[w,i] for i,(s,w) in enumerate(syms)]
    heapq.heapify(heap)
    # build code lengths via Huffman tree depth
    nodes={i:[w,None,None] for i,(s,w) in enumerate(syms)}
    nxt=len(syms)
    h=[(w,i) for i,(s,w) in enumerate(syms)]
    heapq.heapify(h)
    while len(h)>1:
        w1,a=heapq.heappop(h); w2,b=heapq.heappop(h)
        nodes[nxt]=[w1+w2,a,b]; heapq.heappush(h,(w1+w2,nxt)); nxt+=1
    root=h[0][1]
    lengths={}
    def walk(n,d):
        w,a,b=nodes[n]
        if a is None and b is None:
            lengths[n]=max(d,1)
        else:
            walk(a,d+1); walk(b,d+1)
    walk(root,0)
    return sum(counts[syms[i][0]]*lengths[i] for i in range(len(syms)))

def entropy_bits_order1(seq):
    """order-1 entropy bound: sum over contexts of -count*log2(p). This is the
    bits an ideal arithmetic/ANS coder approaches."""
    ctx=defaultdict(Counter); prev=None
    for s in seq:
        ctx[prev][s]+=1; prev=s
    bits=0.0
    for c,counts in ctx.items():
        tot=sum(counts.values())
        for s,n in counts.items():
            bits += -n*math.log2(n/tot)
    return bits

tot_huff=tot_ent=0.0
print(f"{'file':16} {'huff_B':>9} {'ent_B':>9} {'gap_B':>8} {'gap%':>7}")
for name in FILES:
    data=CORPUS.joinpath(f"{name}.bin").read_bytes()
    codes=value_codes(list(data))
    tcodes=bwt(codes)                       # leader feeds BWT stream to order-1 Huffman
    hb=canonical_huffman_bits_order1(tcodes)/8
    eb=entropy_bits_order1(tcodes)/8
    gap=hb-eb
    tot_huff+=hb; tot_ent+=eb
    pct = (gap/hb*100) if hb>0 else 0
    print(f"{name:16} {hb:9.1f} {eb:9.1f} {gap:8.1f} {pct:6.2f}%")

gap=tot_huff-tot_ent
pct=gap/tot_huff*100 if tot_huff>0 else 0
print()
print(f"TOTAL huffman bitstream: {tot_huff:.1f} B   entropy bound: {tot_ent:.1f} B")
print(f"Huffman→entropy gap (ANS ceiling): {gap:.1f} B = {pct:.2f}% of the Huffman bitstream")
# Leader aggregate is 0.299337 over corpus; gap% of the ENTROPY-coded portion is
# what ANS could shave. A gap below ~2% is NO-GO (table overhead + impl risk eat it).
GO = pct >= 2.0
print(f"VERDICT: {'GO (ANS worth a size model + Rust)' if GO else 'NO-GO — Huffman already near entropy'} "
      f"(threshold 2.00% of bitstream)")
sys.exit(0 if GO else 1)
