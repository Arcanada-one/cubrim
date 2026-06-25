#!/usr/bin/env python3
"""H-18 corpus-TOTAL size model: does a shipped shared-dictionary CDC dedup beat
what existing tools already extract on the SAME redundant corpus?

Compares, on the dedup-corpus (B), corpus-total compressed size of:
  (1) per-file gzip          — the per-file baseline (no inter-file sharing)
  (2) gzip on concatenation  — the cheap inter-file lever everyone already has
  (3) CDC shared-dict model  — unique chunks stored once (gzip'd) + per-file
                               reference lists (gzip'd). Dictionary charged ONCE.

A GO for the dedup IDEA requires (3) < (2): the bespoke shared-dict must beat
the trivial gzip-on-concat, otherwise the idea adds complexity for no win over
a tool that already ships in every OS."""
import gzip, hashlib, sys
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/dedup-corpus")
FILES = ["v1","v2","v3","v4","doc_a","doc_b","unique"]
GEAR=[(i*2654435761)&0xFFFFFFFFFFFFFFFF for i in range(256)]

def gz(b): return len(gzip.compress(b, 9))

def cdc(data, avg=64):
    min_sz,max_sz=max(16,avg//4),avg*4
    mask=(1<<(avg.bit_length()-1))-1
    chunks,n,start,h,i=[],len(data),0,0,0
    while i<n:
        h=((h<<1)+GEAR[data[i]])&0xFFFFFFFFFFFFFFFF
        sz=i-start+1
        if sz>=min_sz and ((h&mask)==0 or sz>=max_sz):
            chunks.append(bytes(data[start:i+1])); start=i+1; h=0
        i+=1
    if start<n: chunks.append(bytes(data[start:n]))
    return chunks

data={n:CORPUS.joinpath(f"{n}.bin").read_bytes() for n in FILES}
orig=sum(len(d) for d in data.values())

# (1) per-file gzip
m1=sum(gz(d) for d in data.values())

# (2) gzip on concatenation (deterministic order)
concat=b"".join(data[n] for n in FILES)
m2=gz(concat)

# (3) CDC shared-dict, dictionary charged once
for avg in (32,48,64,96,128):
    store={}            # hash -> chunk bytes (unique)
    refs={}             # file -> list of chunk hashes
    for n in FILES:
        hs=[]
        for c in cdc(data[n], avg):
            h=hashlib.sha1(c).digest()[:8]   # 8-byte ref id
            store.setdefault(h, c); hs.append(h)
        refs[n]=hs
    dict_blob=b"".join(store.values())                       # unique chunk bytes
    dict_gz=gz(dict_blob)
    # reference lists: 8 bytes per ref, gzip'd together
    ref_blob=b"".join(b"".join(refs[n]) for n in FILES)
    ref_gz=gz(ref_blob)
    # chunk-length table needed to reassemble dict (charge it): 2 bytes/unique chunk
    lentab=gz(b"".join(len(c).to_bytes(2,"big") for c in store.values()))
    m3=dict_gz+ref_gz+lentab
    print(f"avg={avg:4}  unique_chunks={len(store):4}  dict_gz={dict_gz:5}  ref_gz={ref_gz:5}  lentab={lentab:4}  TOTAL={m3:5}")

print()
print(f"original corpus                 : {orig:6} B")
print(f"(1) per-file gzip               : {m1:6} B  ratio {m1/orig:.4f}")
print(f"(2) gzip on concatenation       : {m2:6} B  ratio {m2/orig:.4f}   <-- the bar to beat")
# recompute best m3
best=None
for avg in (32,48,64,96,128):
    store={}; refs={}
    for n in FILES:
        hs=[]
        for c in cdc(data[n], avg):
            h=hashlib.sha1(c).digest()[:8]; store.setdefault(h,c); hs.append(h)
        refs[n]=hs
    m3=gz(b"".join(store.values()))+gz(b"".join(b"".join(refs[n]) for n in FILES))+gz(b"".join(len(c).to_bytes(2,"big") for c in store.values()))
    if best is None or m3<best[1]: best=(avg,m3)
print(f"(3) CDC shared-dict (best avg={best[0]:3}): {best[1]:6} B  ratio {best[1]/orig:.4f}")
print()
GO = best[1] < m2
print(f"VERDICT: dedup {'GO — beats gzip-on-concat' if GO else 'NO-GO — gzip-on-concat already does as well or better'}")
print(f"  shared-dict {best[1]} vs gzip-concat {m2}  (delta {best[1]-m2:+} B)")
sys.exit(0 if GO else 1)
