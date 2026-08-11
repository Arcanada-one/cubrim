#!/usr/bin/env python3
"""H-21 probe: adaptive/streaming rANS (no transmitted freq table — the decoder
rebuilds the model symbol-by-symbol). The win is removing table overhead; the cost
is the adaptive "learning" penalty (early symbols coded under a diluted model).

Information-theoretic identity: adaptive_code_length ≈ static_payload + model_cost,
where model_cost ≈ what a static scheme pays as an explicit table. So adaptive only
wins when its IMPLICIT learning cost < the static EXPLICIT table cost. This probe
measures the adaptive code length directly (sum of -log2(p_adaptive)); a real
adaptive rANS reaches it to a negligible fraction of a bit.

We compare, on the BWT'd value-code stream (the champion's front-end), per file:
  - adaptive order-0 (single Laplace model over the known A-symbol alphabet)
  - adaptive order-1 (per-context Laplace model, context = prev code)
  - static order-1 rANS value-stream (the champion BwtRans coder — calibrated proxy)
vs the champion per-file TOTAL bytes (pinned leaderboard). For raw-stored files the
bar is the raw size; adaptive earns the file only if value_stream + cube overhead
beats it.

Laplace alpha is swept: a real adaptive rANS can pick alpha (init count) — small
alpha reduces dilution on sparse contexts but risks early-symbol cost; the alphabet
A is known up-front (transmitted in the cube header's inverse_dict), so the model
size is fixed, not estimated."""
import math
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]
BASELINE = {"sparse_clustered":443,"dense":4109,"text":3177,"log_like":1402,
            "binary_mixed":8205,"random_high":4109,"sparse_small":269,
            "both_sparse_16":29,"both_sparse_24":37,"block_bound_runs":4169}
RAW = {"dense","binary_mixed","random_high","sparse_small","both_sparse_16","both_sparse_24"}
ORIG = {"sparse_clustered":2048,"dense":4096,"text":16384,"log_like":16384,
        "binary_mixed":8192,"random_high":4096,"sparse_small":256,
        "both_sparse_16":16,"both_sparse_24":24,"block_bound_runs":65536}

SCALE_BITS = 12; M = 1 << SCALE_BITS; MIN_CTX_COUNT = 16

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

def adaptive_o0_bits(bwt, A, alpha):
    """Adaptive order-0: Laplace model over A symbols, init count alpha each."""
    cnt=[0]*A; total=0.0; bits=0.0; aA=alpha*A
    for s in bwt:
        p=(cnt[s]+alpha)/(total+aA)
        bits+=-math.log2(p)
        cnt[s]+=1; total+=1
    return bits

def adaptive_o1_bits(bwt, A, alpha):
    """Adaptive order-1: per-context Laplace model. Context = prev code (start 0)."""
    cnt=defaultdict(lambda:[0]*A); tot=defaultdict(float); bits=0.0; aA=alpha*A
    prev=0
    for s in bwt:
        c=cnt[prev]; t=tot[prev]
        p=(c[s]+alpha)/(t+aA)
        bits+=-math.log2(p)
        c[s]+=1; tot[prev]=t+1
        prev=s
    return bits

# static order-1 rANS value-stream proxy (calibrated to champion in H-20).
def normalize(counts):
    total=sum(counts.values())
    if total==0: return {}
    freq={}; alloc=0
    for s,c in counts.items():
        f=max((c*M+total//2)//total,1); freq[s]=f; alloc+=f
    if alloc<M: freq[max(freq,key=lambda s:freq[s])]+=M-alloc
    elif alloc>M:
        sp=alloc-M
        while sp>0:
            mx=max((s for s in freq if freq[s]>1),key=lambda s:freq[s])
            take=min(sp,freq[mx]-1); freq[mx]-=take; sp-=take
    return freq

def static_o1_valuestream(bwt):
    g=Counter(bwt); ctx=defaultdict(Counter); prev=0
    for s in bwt:
        ctx[prev][s]+=1; prev=s
    fb=normalize(g); cn={c:normalize(cc) for c,cc in ctx.items() if sum(cc.values())>=MIN_CTX_COUNT}
    tab=2+3*len(fb)
    for nf in cn.values(): tab+=2+2+3*len(nf)
    bits=0.0; prev=0
    for s in bwt:
        nf=cn.get(prev,fb); f=nf.get(s,1); bits+=-math.log2(f/M); prev=s
    payload=math.ceil(bits/8)+4
    return 2+1+2+4+tab+payload   # primary+scale+nctx+ranslen+tables+payload

def adaptive_o1_integer_bits(bwt, A, inc, rescale_at):
    """Faithful integer-count adaptive order-1 model with periodic rescaling — what a
    real cumulative-frequency range coder achieves (to <0.01%). init count = 1 per
    symbol (effective alpha = 1/inc), increment = inc per observation, rescale (halve,
    floor 1) when a context's total would exceed rescale_at. Deterministic both sides."""
    cnt=defaultdict(lambda:[1]*A); tot=defaultdict(lambda:A); bits=0.0
    prev=0
    for s in bwt:
        c=cnt[prev]; t=tot[prev]
        bits+=-math.log2(c[s]/t)
        c[s]+=inc; t+=inc
        if t>rescale_at:
            nt=0
            for i in range(A):
                c[i]=(c[i]+1)>>1
                if c[i]<1: c[i]=1
                nt+=c[i]
            t=nt
        tot[prev]=t
        prev=s
    return bits

ALPHAS=[1.0,0.5,0.25,0.125,1/16]
print(f"{'file':16} {'A':>4} {'stat_o1':>8} {'champ':>6} | adaptive value-stream (primary+ceil(bits/8)) by alpha")
print(f"{'':16} {'':>4} {'':>8} {'':>6} | " + " ".join(f"o0@{a:<5}/o1@{a:<5}" for a in [1.0,0.25,1/16]))
tot_champ=0; tot_orig=0; best_total=0
per_best={}
for name in FILES:
    data=list(CORPUS.joinpath(f'{name}.bin').read_bytes())
    codes=value_codes(data); A=len(set(codes)); bwt=bwt_codes(codes)
    so1=static_o1_valuestream(bwt)
    champ=BASELINE[name]; orig=ORIG[name]
    # estimate cube overhead: for the champion's coder, overhead = champ_total - static_o1_vs
    # (only meaningful where the champion is a cube/BWT file). Use it to convert adaptive
    # value-stream -> total. For raw files we don't know the cube overhead, so use a
    # conservative small overhead band and report whether adaptive beats raw.
    results={}
    for a in ALPHAS:
        vs_o0 = 2 + math.ceil(adaptive_o0_bits(bwt,A,a)/8)
        vs_o1 = 2 + math.ceil(adaptive_o1_bits(bwt,A,a)/8)
        results[('o0',a)]=vs_o0; results[('o1',a)]=vs_o1
    best_vs=min(results.values())
    # champion value-stream proxy = static_o1 (where it's the winner); overhead:
    overhead = max(0, champ - so1) if name not in RAW else None
    show=lambda a:(f"{results[('o0',a)]:5}/{results[('o1',a)]:5}")
    print(f"{name:16} {A:4} {so1:8} {champ:6} | {show(1.0)} {show(0.25)} {show(1/16)}")
    # decide best achievable total under adaptive:
    if name in RAW:
        # adaptive earns the file only if best_vs + cube_overhead < raw. We don't have the
        # exact cube overhead for raw files; approximate with the median cube overhead.
        per_best[name]=('raw-needs-codec', best_vs)
    else:
        # total = overhead + best adaptive value-stream, capped at champion (competitive min)
        cand_total = overhead + best_vs
        per_best[name]=(min(cand_total, champ), best_vs, overhead, so1)
    tot_champ+=champ; tot_orig+=orig

print(f"\nchampion aggregate = {tot_champ/tot_orig:.6f} (total {tot_champ})")

# ── Faithful integer-model simulation (what the real range coder achieves) ──────
# Sweep increment (effective alpha = 1/inc); rescale total at 1<<15 to keep < BOT=2^16.
print("\n=== FAITHFUL integer adaptive order-1 (with rescaling, range-coder-accurate) ===")
print(f"{'file':16} {'A':>4} {'champ':>6} {'best_o1_vs':>10} {'inc*':>5}  cube-overhead model -> cand_total [verdict]")
INCS=[8,16,32,64]
tot_cand=0
for name in FILES:
    data=list(CORPUS.joinpath(f'{name}.bin').read_bytes())
    codes=value_codes(data); A=len(set(codes)); bwt=bwt_codes(codes)
    best=None; bestinc=None
    for inc in INCS:
        vs=2+math.ceil(adaptive_o1_integer_bits(bwt,A,inc,1<<15)/8)  # +2 primary
        if best is None or vs<best: best=vs; bestinc=inc
    champ=BASELINE[name]
    # cube overhead: for cube-champion files use champ - static_o1; for raw files we must
    # add the same cube scaffolding the champion would build if it went cube. Estimate the
    # raw-file cube overhead from sibling cube files of similar size (conservative ~ a few %).
    so1=static_o1_valuestream(bwt)
    if name not in RAW:
        overhead=max(0, champ-so1)
        cand=min(champ, overhead+best)
    else:
        # raw file: needs the real codec to know cube overhead. Lower bound: best value-stream;
        # the file converts to cube only if best+overhead < raw. Mark for codec verification.
        overhead='?'
        cand=champ  # conservatively assume raw stays until codec proves otherwise
    tot_cand+=cand
    v='WIN' if (name not in RAW and cand<champ) else ('?' if name in RAW else 'no')
    print(f"{name:16} {A:4} {champ:6} {best:10} {bestinc:5}  overhead={overhead} cand_total={cand} [{v}]")
print(f"\nprojected aggregate (cube-file wins only, raw conservatively held) = {tot_cand/tot_orig:.6f}  vs champion 0.221726")
print("NOTE: raw files (binary_mixed/dense/random_high/...) may ALSO convert to cube under")
print("adaptive — only the real Rust codec settles their cube overhead. Probe is the GO signal,")
print("the round-trippable codec is the verdict.")
print("\nPer-file adaptive prospect (cube files: overhead+best_adaptive_vs vs champion):")
for name in FILES:
    if name in RAW:
        print(f"  {name:16} RAW champ={BASELINE[name]} best_adaptive_vs={per_best[name][1]} (needs real codec for cube overhead)")
    else:
        ct,bvs,ov,so1=per_best[name]
        verdict = "WIN" if ct<BASELINE[name] else "no"
        print(f"  {name:16} champ={BASELINE[name]} overhead~{ov} best_adaptive_vs={bvs} -> cand_total={ov+bvs} [{verdict}] (static_o1_vs={so1})")
