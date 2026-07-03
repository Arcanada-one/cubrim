#!/usr/bin/env python3
"""Re-run the H-18 cross-file dedup probe on the SEPARATE dedup-corpus (B).
Same FastCDC logic as probe_h18_crossfile_dedup.py, pointed at the redundant
multi-file corpus to confirm the probe correctly distinguishes a GO case from
the frozen-corpus NO-GO."""
import hashlib, sys
from pathlib import Path

CORPUS = Path("documentation/ephemeral/research/dedup-corpus")
FILES = ["v1","v2","v3","v4","doc_a","doc_b","unique"]
GEAR = [(i*2654435761) & 0xFFFFFFFFFFFFFFFF for i in range(256)]

def cdc_chunks(data, min_sz, avg_sz, max_sz):
    mask=(1<<(avg_sz.bit_length()-1))-1
    chunks,n,start,h,i=[],len(data),0,0,0
    while i<n:
        h=((h<<1)+GEAR[data[i]])&0xFFFFFFFFFFFFFFFF
        sz=i-start+1
        if sz>=min_sz and ((h&mask)==0 or sz>=max_sz):
            chunks.append(bytes(data[start:i+1])); start=i+1; h=0
        i+=1
    if start<n: chunks.append(bytes(data[start:n]))
    return chunks

def run(avg_sz):
    min_sz,max_sz=max(16,avg_sz//4),avg_sz*4
    per={}; total=0
    for name in FILES:
        data=CORPUS.joinpath(f"{name}.bin").read_bytes(); total+=len(data)
        per[name]=[(hashlib.sha1(c).hexdigest(),len(c)) for c in cdc_chunks(data,min_sz,avg_sz,max_sz)]
    fph={}
    for name,lst in per.items():
        for h,_ in set((h,l) for h,l in lst): fph.setdefault(h,set()).add(name)
    xfh={h for h,fs in fph.items() if len(fs)>=2}
    seen=set(); redundant=0
    occ=[(h,l,name) for name in FILES for h,l in per[name]]
    for h,l,name in occ:
        if h in seen: redundant+=l
        else: seen.add(h)
    xfirst={}
    xred=0
    for h,l,name in occ:
        if h in xfh:
            if h in xfirst: xred+=l
            else: xfirst[h]=name
    return dict(avg=avg_sz,total=total,chunks=sum(len(v) for v in per.values()),
                distinct=len(seen),xfh=len(xfh),
                red_any=redundant,red_any_pct=redundant/total,
                xred=xred,xred_pct=xred/total)

print(f"{'avg':>6} {'chunks':>7} {'distinct':>9} {'xfile#':>7} {'dup_any%':>9} {'xfile_dup%':>11}")
res=[]
for avg in (64,128,256,512,1024):
    r=run(avg); res.append(r)
    print(f"{r['avg']:>6} {r['chunks']:>7} {r['distinct']:>9} {r['xfh']:>7} "
          f"{r['red_any_pct']*100:>8.3f}% {r['xred_pct']*100:>10.3f}%")
best=max(r['xred_pct'] for r in res)
print(f"\ntotal corpus bytes: {res[0]['total']}")
print(f"max cross-file redundant ratio: {best*100:.4f}%")
GO=best>=0.05
print(f"VERDICT: {'GO (worth a corpus-total size model)' if GO else 'NO-GO on this corpus'} (threshold 5.0000%)")
sys.exit(0 if GO else 1)
