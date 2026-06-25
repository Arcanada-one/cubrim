#!/usr/bin/env python3
"""H-20 CHARGED probe: order-2 context rANS vs the order-1 rANS champion (scheme 7).

Gotcha #6 discipline: charge EVERY decoder branch. The order-2 fallback chain is
order2 -> order1 -> order0; the decoder needs ALL THREE table levels serialized,
so the size model has one table-cost term per level.

We model the VALUE-STREAM blob only (primary u16 + rANS payload + all tables),
identical modelling for both order-1 and order-2, so the per-file DELTA is honest
(the outer codec header / value-dict is byte-identical between the two schemes and
cancels). GO criterion: order-2 value-stream < order-1 value-stream on SOME file by
enough to push aggregate below the champion 0.221726. If order-2 >= order-1 on every
file, it can never win the per-file competitive min => robust NO-GO.

rANS payload bits are estimated at the entropy bound under the SELECTED table's
normalized (M=4096) probabilities — the same M the real codec uses — plus the
4-byte state flush. Table cost mirrors rans_serialize_ctx_table EXACTLY:
2 bytes n_syms + 3 bytes (sym u8 + freq u16) per nonzero symbol, plus the ctx-id
key bytes per context (u16 for order-1, two u16 for order-2)."""
import math, sys
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]
# champion per-file value-stream-inclusive total bytes (final file), from the
# pinned leaderboard baseline (BwtRans wins or ties each file via competitive min).
BASELINE = {"sparse_clustered":443,"dense":4109,"text":3177,"log_like":1402,
            "binary_mixed":8205,"random_high":4109,"sparse_small":269,
            "both_sparse_16":29,"both_sparse_24":37,"block_bound_runs":4169}
ORIG = {"sparse_clustered":2048,"dense":4096,"text":16384,"log_like":16384,
        "binary_mixed":8192,"random_high":4096,"sparse_small":256,
        "both_sparse_16":16,"both_sparse_24":24,"block_bound_runs":65536}

SCALE_BITS = 12
M = 1 << SCALE_BITS
MIN_CTX_COUNT = 16

def value_codes(data):
    freq=Counter(data); order=sorted(freq,key=lambda v:(-freq[v],v))
    v2c={v:i for i,v in enumerate(order)}; return [v2c[b] for b in data]

def bwt_codes(seq):
    """Cyclic-rotation BWT via prefix doubling (O(n log^2 n)). Multiset of output
    matches the Rust naive rotation sort; tie-break among equal rotations may differ
    but does not affect the entropy/table estimate."""
    n=len(seq)
    if n==0: return []
    sa=list(range(n)); rank=list(seq); tmp=[0]*n; k=1
    while True:
        key=lambda i:(rank[i], rank[(i+k)%n])
        sa.sort(key=key)
        tmp[sa[0]]=0
        for j in range(1,n):
            tmp[sa[j]]=tmp[sa[j-1]]+(1 if key(sa[j])!=key(sa[j-1]) else 0)
        rank=tmp[:]
        if rank[sa[-1]]==n-1: break
        k<<=1
        if k>=n: break
    return [seq[(i+n-1)%n] for i in sa]

def normalize(counts):
    """Mirror rans_normalize: proportional alloc, floor nonzero to >=1, reconcile to M."""
    total=sum(counts.values())
    if total==0: return {}
    freq={}; allocated=0
    for s,c in counts.items():
        scaled=(c*M + total//2)//total
        f=max(scaled,1); freq[s]=f; allocated+=f
    if allocated<M:
        mx=max(freq,key=lambda s:freq[s]); freq[mx]+=M-allocated
    elif allocated>M:
        surplus=allocated-M
        while surplus>0:
            mx=max((s for s in freq if freq[s]>1),key=lambda s:freq[s])
            take=min(surplus,freq[mx]-1); freq[mx]-=take; surplus-=take
    return freq

def table_cost(nz):
    """rans_serialize_ctx_table: 2 (n_syms) + 3 per nonzero symbol."""
    return 2 + 3*nz

def payload_bits_for_symbol(norm_freq, s):
    """rANS ideal cost under normalized probs: -log2(freq[s]/M)."""
    f=norm_freq.get(s,0)
    if f==0: f=1  # never happens for a present symbol, but guard
    return -math.log2(f/M)

def order1_valuestream(bwt):
    """order-1 rANS value-stream bytes (champion proxy): primary(2) + scale(1)
    + fallback table + n_ctx(2) + per-ctx tables + rans_len(4) + state(4) + payload."""
    # build counts
    g=Counter(bwt)
    ctx_counts=defaultdict(Counter)
    prev=0
    for s in bwt:
        ctx_counts[prev][s]+=1
        prev=s
    # tables: fallback always; order-1 ctx with obs>=MIN_CTX_COUNT
    fb_norm=normalize(g)
    ctx_norm={}
    for ctx,cc in ctx_counts.items():
        if sum(cc.values())>=MIN_CTX_COUNT:
            ctx_norm[ctx]=normalize(cc)
    # table bytes
    tab=table_cost(len(fb_norm))
    for ctx,nf in ctx_norm.items():
        tab+= 2 + table_cost(len(nf))   # 2-byte ctx_id + table
    # payload bits
    bits=0.0; prev=0
    for s in bwt:
        nf=ctx_norm.get(prev, fb_norm)
        bits+=payload_bits_for_symbol(nf,s)
        prev=s
    payload=math.ceil(bits/8)+4   # +4 state flush
    overhead=2+1+2+4              # primary + scale + n_ctx + rans_len
    return overhead+tab+payload, len(ctx_norm)

def order2_valuestream(bwt):
    """order-2 rANS value-stream bytes. Fallback chain order2->order1->order0,
    ALL THREE table levels charged (Gotcha #6). Wire (modelled):
      primary(2) + scale(1)
      + fallback(order0) table
      + n_ctx1(2) + per order-1 table [ctx_id u16 + table]
      + n_ctx2(2) + per order-2 table [ctx_key 2*u16 + table]
      + rans_len(4) + state(4) + payload."""
    g=Counter(bwt)
    c1=defaultdict(Counter)      # prev1 -> counts
    c2=defaultdict(Counter)      # (prev2,prev1) -> counts
    p2=p1=0
    for s in bwt:
        c1[p1][s]+=1
        c2[(p2,p1)][s]+=1
        p2=p1; p1=s
    fb_norm=normalize(g)
    o1_norm={ctx:normalize(cc) for ctx,cc in c1.items() if sum(cc.values())>=MIN_CTX_COUNT}
    o2_norm={ctx:normalize(cc) for ctx,cc in c2.items() if sum(cc.values())>=MIN_CTX_COUNT}
    # table bytes — every level charged
    tab=table_cost(len(fb_norm))
    for nf in o1_norm.values(): tab+= 2 + table_cost(len(nf))
    for nf in o2_norm.values(): tab+= 4 + table_cost(len(nf))
    # payload bits with fallback chain selection
    bits=0.0; p2=p1=0
    for s in bwt:
        nf=o2_norm.get((p2,p1))
        if nf is None: nf=o1_norm.get(p1)
        if nf is None: nf=fb_norm
        bits+=payload_bits_for_symbol(nf,s)
        p2=p1; p1=s
    payload=math.ceil(bits/8)+4
    overhead=2+1+2+2+4
    return overhead+tab+payload, len(o1_norm), len(o2_norm)

def order0_valuestream(bwt):
    """order-0 rANS value-stream: single global table (no context). This is the
    real competitor the high-entropy files (random_high/dense) actually use via the
    champion's Entropy/bitpack schemes — the honest floor order-2 must also beat."""
    g=Counter(bwt)
    fb_norm=normalize(g)
    tab=table_cost(len(fb_norm))
    bits=0.0
    for s in bwt:
        bits+=payload_bits_for_symbol(fb_norm,s)
    payload=math.ceil(bits/8)+4
    overhead=2+1+2+4
    return overhead+tab+payload

def order2_no_o1_valuestream(bwt):
    """Sensitivity variant: order2 -> order0 fallback ONLY (drop the order-1 level,
    the 'Option B' design). Cheaper tables, but unqualified order-2 contexts fall
    straight to order-0 (worse payload). Two decoder branches => two table terms."""
    g=Counter(bwt)
    c2=defaultdict(Counter)
    p2=p1=0
    for s in bwt:
        c2[(p2,p1)][s]+=1
        p2=p1; p1=s
    fb_norm=normalize(g)
    o2_norm={ctx:normalize(cc) for ctx,cc in c2.items() if sum(cc.values())>=MIN_CTX_COUNT}
    tab=table_cost(len(fb_norm))
    for nf in o2_norm.values(): tab+= 4 + table_cost(len(nf))
    bits=0.0; p2=p1=0
    for s in bwt:
        nf=o2_norm.get((p2,p1), fb_norm)
        bits+=payload_bits_for_symbol(nf,s)
        p2=p1; p1=s
    payload=math.ceil(bits/8)+4
    overhead=2+1+2+4
    return overhead+tab+payload

print(f"{'file':16} {'orig':>7} {'o0':>7} {'o1':>7} {'o2full':>7} {'o2B':>7} {'o2best':>7} {'ref':>7} {'win?':>5}")
tot_o1=tot_o2=tot_orig=tot_base=0
tot_o2_final=0
per_file_final={}
for name in FILES:
    data=list(CORPUS.joinpath(f'{name}.bin').read_bytes())
    codes=value_codes(data)
    bwt=bwt_codes(codes)
    o0=order0_valuestream(bwt)
    o1,o1ctx=order1_valuestream(bwt)
    o2,o2c1,o2c2=order2_valuestream(bwt)
    o2b=order2_no_o1_valuestream(bwt)
    base=BASELINE[name]; orig=ORIG[name]
    # Honest reference = best value-stream order-2 must beat = min(order-0, order-1).
    # (These two are the schemes the champion already realizes; order-2 only earns a
    # slot if it strictly beats both.) order-2 best = min(full chain, Option B).
    ref=min(o0,o1)
    o2best=min(o2,o2b)
    win = o2best < ref
    # final file = champion baseline minus any genuine order-2 saving vs the ref.
    final = base + (o2best-ref if win else 0)
    per_file_final[name]=final
    tot_o1+=o1; tot_o2+=o2; tot_orig+=orig; tot_base+=base; tot_o2_final+=final
    print(f"{name:16} {orig:7} {o0:7} {o1:7} {o2:7} {o2b:7} {o2best:7} {ref:7} {str(win):>5}")

print(f"\n{'TOTAL':16} {tot_orig:7} {tot_o1:7} {tot_o2:7} {tot_o2-tot_o1:7}")
print(f"\n-- champion baseline total bytes = {tot_base}  aggregate = {tot_base/tot_orig:.6f}")
print(f"-- order-1 proxy total value-stream = {tot_o1} (calibration vs champion)")
print(f"-- order-2 competitive final total = {tot_o2_final}  aggregate = {tot_o2_final/tot_orig:.6f}")
wins=[n for n in FILES if per_file_final[n]<BASELINE[n]]
print(f"-- files where order-2 wins per-file competition: {wins if wins else 'NONE'}")
if tot_o2_final < tot_base:
    print(f"=> POTENTIAL GO: {tot_o2_final/tot_orig:.6f} < 0.221726 (verify in real Rust codec)")
else:
    print(f"=> NO-GO: order-2 never beats the per-file champion min; aggregate {tot_o2_final/tot_orig:.6f} >= 0.221726")
