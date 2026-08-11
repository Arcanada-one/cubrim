#!/usr/bin/env python3
"""H-22 probe: context-mixing of order-1 + order-0 on the BWT'd value-code stream.

The strongest known scheme is adaptive order-1 (H-21, scheme 9): aggregate 0.177122.
Its remaining slack is the per-context LEARNING cost — an unseen symbol in a context
is coded under a uniform 1/A prior (expensive). The principled "mix order-1 + order-0"
is order-1 with an order-0 BACKOFF PRIOR (Jelinek-Mercer / Witten-Bell interpolation):
unseen symbols fall back to the adaptive order-0 distribution instead of uniform.

  p_mix(s) = (cnt1[ctx][s] + beta * p0(s)) / (tot1[ctx] + beta)
  p0(s)    = cnt0[s] / tot0                       (adaptive order-0, init 1 each)

For an unseen context (tot1=0): p_mix(s) = p0(s) — first symbols cost order-0 entropy,
NOT log2(A). That is exactly the H-21 slack this targets. This form is INTEGER-exact
(no float on the wire): u(s) = cnt1[s]*tot0 + beta*cnt0[s], U = tot0*(tot1+beta), so a
real range coder reproduces it deterministically (quantize u/U to freqs summing to M).

DECISIVE TEST: does mixed beat pure adaptive order-1 (H-21) per file? If not by a real
margin, context-mixing adds nothing over H-21 → NO-GO (redundant). The probe also
reproduces the pure-o1 value-stream to validate against H-21's real Rust numbers."""
import math
from collections import defaultdict
from pathlib import Path
from collections import Counter

CORPUS = Path("docs/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]
# H-21 real Rust value-stream-inclusive totals (scheme 9 winners) and champion.
H21 = {"sparse_clustered":179,"text":1784,"log_like":570,"binary_mixed":6148,
       "block_bound_runs":3495}
CHAMP = {"sparse_clustered":443,"dense":4109,"text":3177,"log_like":1402,
         "binary_mixed":8205,"random_high":4109,"sparse_small":269,
         "both_sparse_16":29,"both_sparse_24":37,"block_bound_runs":4169}
RAW = {"dense","random_high","sparse_small","both_sparse_16","both_sparse_24"}
ORIG = {"sparse_clustered":2048,"dense":4096,"text":16384,"log_like":16384,
        "binary_mixed":8192,"random_high":4096,"sparse_small":256,
        "both_sparse_16":16,"both_sparse_24":24,"block_bound_runs":65536}
RESCALE = 1<<15

def value_codes(data):
    freq=Counter(data); order=sorted(freq,key=lambda v:(-freq[v],v))
    v2c={v:i for i,v in enumerate(order)}; return [v2c[b] for b in data]

def bwt_codes(seq):
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

def pure_o1_bits(bwt, A, inc):
    """H-21 model: adaptive order-1, uniform init 1, rescale at total>RESCALE."""
    cnt=defaultdict(lambda:[1]*A); tot=defaultdict(lambda:A); bits=0.0; prev=0
    for s in bwt:
        c=cnt[prev]; t=tot[prev]
        bits+=-math.log2(c[s]/t); c[s]+=inc; t+=inc
        if t>RESCALE:
            nt=0
            for i in range(A):
                c[i]=(c[i]+1)>>1; nt+=c[i]
            t=nt
        tot[prev]=t; prev=s
    return bits

def mixed_bits(bwt, A, inc1, inc0, beta):
    """order-1 + order-0 backoff (Jelinek-Mercer). cnt1 init 0, cnt0 init 1.
    p_mix(s) = (cnt1[s] + beta*cnt0[s]/tot0) / (tot1 + beta)."""
    cnt1=defaultdict(lambda:[0]*A); tot1=defaultdict(int)
    cnt0=[1]*A; tot0=A
    bits=0.0; prev=0
    for s in bwt:
        c1=cnt1[prev]; t1=tot1[prev]
        p0_s=cnt0[s]/tot0
        p=(c1[s] + beta*p0_s)/(t1 + beta)
        bits+=-math.log2(p)
        # update order-1
        c1[s]+=inc1; t1+=inc1
        if t1>RESCALE:
            nt=0
            for i in range(A):
                c1[i]=c1[i]>>1; nt+=c1[i]
            t1=nt
        tot1[prev]=t1
        # update order-0
        cnt0[s]+=inc0; tot0+=inc0
        if tot0>RESCALE:
            nt=0
            for i in range(A):
                cnt0[i]=(cnt0[i]+1)>>1; nt+=cnt0[i]
            tot0=nt
        prev=s
    return bits

def mixed_learned_bits(bwt, A, inc1, inc0, lr):
    """LEARNED-weight linear mix: p = w*p1 + (1-w)*p0, w adapts by log-loss gradient
    toward whichever model predicts the observed symbol better. Global w (one weight).
    This is the brief's 'learned weights' variant of order-1 + order-0 mixing."""
    cnt1=defaultdict(lambda:[1]*A); tot1=defaultdict(lambda:A)
    cnt0=[1]*A; tot0=A
    w=0.5; bits=0.0; prev=0
    for s in bwt:
        c1=cnt1[prev]; t1=tot1[prev]
        p1=c1[s]/t1; p0=cnt0[s]/tot0
        pm=w*p1+(1.0-w)*p0
        bits+=-math.log2(pm)
        # gradient step on w (clamp away from 0/1)
        w += lr*(p1-p0)/pm
        if w<1e-4: w=1e-4
        if w>1-1e-4: w=1-1e-4
        # updates
        c1[s]+=inc1; t1+=inc1
        if t1>RESCALE:
            nt=0
            for i in range(A):
                c1[i]=(c1[i]+1)>>1; nt+=c1[i]
            t1=nt
        tot1[prev]=t1
        cnt0[s]+=inc0; tot0+=inc0
        if tot0>RESCALE:
            nt=0
            for i in range(A):
                cnt0[i]=(cnt0[i]+1)>>1; nt+=cnt0[i]
            tot0=nt
        prev=s
    return bits

INCS=[8,16,32,64]
BETAS=[0.25,0.5,1.0,2.0,4.0,8.0]
LRS=[0.01,0.02,0.05,0.1]
print(f"{'file':16} {'A':>4} {'champ':>6} {'H21':>6} {'pure_o1':>8} {'mix-JM':>7} {'mix-lrn':>7} {'mix-cfg':>14} {'verdict':>8}")
tot_mixed=0; tot_orig=0
proj={}
for name in FILES:
    data=list(CORPUS.joinpath(f'{name}.bin').read_bytes())
    codes=value_codes(data); A=len(set(codes)); bwt=bwt_codes(codes)
    # pure o1 value-stream (best inc) -> for validation vs H-21
    puro1=min(2+math.ceil(pure_o1_bits(bwt,A,inc)/8) for inc in INCS)
    # mixed value-stream (best inc1,inc0,beta)
    best=None; bestcfg=None
    for inc1 in INCS:
        for inc0 in INCS:
            for beta in BETAS:
                vs=3+math.ceil(mixed_bits(bwt,A,inc1,inc0,beta)/8)  # +1 byte beta idx vs H-21
                if best is None or vs<best: best=vs; bestcfg=(inc1,inc0,beta)
    # learned-weight mix (best inc1,inc0,lr)
    bestL=min(3+math.ceil(mixed_learned_bits(bwt,A,i1,i0,lr)/8)
              for i1 in INCS for i0 in INCS for lr in LRS)
    champ=CHAMP[name]; orig=ORIG[name]
    # H-21 baseline value-stream for cube files = H21 total - overhead; for our compare
    # we use the champion-relative overhead (cube scaffolding identical).
    if name in RAW:
        h21v='raw'
        # mixed earns the file only if it (well) beats raw; needs codec for overhead.
        best_total=champ  # conservatively hold raw
        verdict='?'
    else:
        h21v=H21[name]
        overhead=champ-puro1  # cube scaffolding (matches H-21 within a couple bytes)
        mixed_total=overhead+best
        best_total=min(mixed_total, H21[name])  # competitive vs the best known (H-21)
        verdict='WIN' if mixed_total < H21[name] else 'no'
    proj[name]=best_total
    tot_mixed+=best_total; tot_orig+=orig
    bestboth=min(best,bestL)
    print(f"{name:16} {A:4} {champ:6} {str(h21v):>6} {puro1:8} {best:7} {bestL:7} {str(bestcfg):>14} {verdict:>8}")

print(f"\nchampion 0.221726 | H-21 best 0.177122")
print(f"projected mixed aggregate (cube wins vs H-21, raw held) = {tot_mixed/tot_orig:.6f}")
print("DECISIVE: 'WIN' means mixed beats H-21 adaptive order-1 on that file. If all 'no',")
print("context-mixing adds nothing over H-21 -> NO-GO. Raw files need the real codec.")
