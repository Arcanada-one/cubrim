#!/usr/bin/env python3
"""H-19 CHARGED probe (Gotcha #6 discipline): does the Huffman->entropy gap
survive once BOTH coders pay their REAL table cost?

Critical correction to the naive probe: order-1 coding splits the stream into
many tiny per-context distributions. On those, (a) Huffman's integer-rounding
penalty looks huge in % terms because each context has few symbols, BUT (b) the
ENTROPY bound is unreachable in practice because ANS must still ship a frequency
table per context — and with many sparse contexts the table cost dominates.

The fair comparison charges, for EACH coder, its table cost:
  - Huffman order-1: ships per-context code-length tables.
  - ANS order-1: ships per-context frequency (or normalized-freq) tables.
These tables are ~the same size, so the GAP (huff_bitstream - ent_bitstream)
is the honest ANS ceiling ONLY if we ALSO confirm a real gain at order-0
(single table, no context-proliferation artifact). We report both orders and
the per-coder TOTAL (bitstream + tables)."""
import math, sys
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]

def value_codes(data):
    freq=Counter(data); order=sorted(freq,key=lambda v:(-freq[v],v))
    v2c={v:i for i,v in enumerate(order)}; return [v2c[b] for b in data]

def bwt(seq):
    n=len(seq)
    if n==0: return seq
    rot=sorted(range(n),key=lambda i: seq[i:]+seq[:i])
    return [seq[(i-1)%n] for i in rot]

def huff_lengths(counts):
    syms=list(counts); 
    if len(syms)==1: return {syms[0]:1}
    import heapq
    nodes={}; 
    for i,s in enumerate(syms): nodes[i]=[counts[s],None,None,s]
    nxt=len(syms); h=[(counts[s],i) for i,s in enumerate(syms)]; heapq.heapify(h)
    while len(h)>1:
        w1,a=heapq.heappop(h); w2,b=heapq.heappop(h)
        nodes[nxt]=[w1+w2,a,b,None]; heapq.heappush(h,(w1+w2,nxt)); nxt+=1
    root=h[0][1]; L={}
    def walk(n,d):
        w,a,b,s=nodes[n]
        if a is None: L[s]=max(d,1)
        else: walk(a,d+1); walk(b,d+1)
    walk(root,0); return L

def costs(seq, order):
    """Return (huff_bitstream_B, ent_bitstream_B, n_contexts, n_distinct).
    Tables charged separately by caller using n_contexts/n_distinct."""
    if order==0:
        ctxs={None:Counter(seq)}
    else:
        ctxs=defaultdict(Counter); prev=None
        for s in seq: ctxs[prev][s]+=1; prev=s
    hb=eb=0.0; ndist=set()
    for c,counts in ctxs.items():
        L=huff_lengths(counts); tot=sum(counts.values())
        for s,n in counts.items():
            hb += n*L[s]; eb += -n*math.log2(n/tot); ndist.add(s)
    return hb/8, eb/8, len(ctxs), len(ndist)

# Table cost model: each context table lists (symbol, code_len) or (symbol,freq).
# Charitable to ANS: 1 byte per distinct symbol per context (freq table entry).
def table_bytes(ctxs_symbols):
    return ctxs_symbols  # ~1 byte per (context,symbol) entry — same for both coders

for order in (0,1):
    tot_hs=tot_es=tot_tab=0.0
    print(f"\n=== ORDER-{order} ===")
    print(f"{'file':16} {'huff_bs':>8} {'ent_bs':>8} {'tab_B':>7} {'gap_bs':>7} {'gap_after_tab%':>14}")
    for name in FILES:
        data=list(CORPUS.joinpath(f'{name}.bin').read_bytes())
        codes=value_codes(data); tcodes=bwt(codes)
        hb,eb,nctx,ndist=costs(tcodes,order)
        # count (context,symbol) entries for table sizing
        if order==0: entries=ndist
        else:
            cc=defaultdict(set); prev=None
            for s in tcodes: cc[prev].add(s); prev=s
            entries=sum(len(v) for v in cc.values())
        tab=table_bytes(entries)
        tot_hs+=hb; tot_es+=eb; tot_tab+=tab
        # gap AFTER charging: huffman ships tables too, so tables cancel in gap;
        # but we show gap relative to the FULL huffman size (bitstream+tables)
        gap=hb-eb
        full_huff=hb+tab
        pct=gap/full_huff*100 if full_huff>0 else 0
        print(f"{name:16} {hb:8.1f} {eb:8.1f} {tab:7.0f} {gap:7.1f} {pct:13.2f}%")
    gap=tot_hs-tot_es; full=tot_hs+tot_tab
    pct=gap/full*100 if full>0 else 0
    print(f"{'TOTAL':16} {tot_hs:8.1f} {tot_es:8.1f} {tot_tab:7.0f} {gap:7.1f} {pct:13.2f}%")
    print(f"  → ANS ceiling = {gap:.1f} B saved, but Huffman FULL size (bs+tables) = {full:.1f} B")
    print(f"  → realistic ANS win = {pct:.2f}% of the full entropy-coded payload")
