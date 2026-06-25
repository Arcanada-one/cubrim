#!/usr/bin/env python3
"""B — generate a SEPARATE dedup-corpus with genuine cross-file redundancy to
honestly re-test H-18 (corpus-local dedup vs charged shared dictionary).

This does NOT touch the frozen 10-file benchmark corpus (that would break the
0.299337 baseline / corpus-hash gate). It models the real-world case the naive
external-snapshot idea was reaching for: versioned snapshots and near-duplicate
documents — exactly where inter-file dedup is supposed to win.

Files:
  v1..v4        : 4 "versions" of a base document, each a small edit of the last
                  (the classic dedup win case — versioned snapshots).
  doc_a, doc_b  : two documents sharing large boilerplate blocks (headers/
                  footers/licence) with different bodies.
  unique        : an unrelated high-entropy file (dedup should find ~nothing).
"""
import os
from pathlib import Path

OUT = Path("docs/ephemeral/research/dedup-corpus")
OUT.mkdir(parents=True, exist_ok=True)

# Deterministic pseudo-content (no Math.random / Date — seeded LCG).
def lcg(seed, n):
    x=seed; out=bytearray()
    for _ in range(n):
        x=(1103515245*x+12345)&0x7fffffff
        out.append(x&0xFF)
    return bytes(out)

base = (b"INTRODUCTION\n"+b"the quick brown fox jumps over the lazy dog. "*40
        +b"\nSECTION-BODY\n"+lcg(1, 800)+b"\nCONCLUSION\n"+b"end of document. "*20)

def edit(buf, seed, n_edits=6):
    b=bytearray(buf)
    x=seed
    for _ in range(n_edits):
        x=(1103515245*x+12345)&0x7fffffff
        pos=x%(len(b)-10)
        b[pos:pos+5]=lcg(x, 5)   # small localized change — rest is identical
    return bytes(b)

v1=base
v2=edit(v1, 11)
v3=edit(v2, 22)
v4=edit(v3, 33)

boiler_head=b"=== ACME CORP CONFIDENTIAL HEADER BLOCK ===\n"+b"legal notice line. "*30+b"\n"
boiler_foot=b"\n=== STANDARD FOOTER / LICENCE APPENDIX ===\n"+b"all rights reserved. "*30
doc_a=boiler_head+b"BODY-A\n"+lcg(7, 600)+boiler_foot
doc_b=boiler_head+b"BODY-B\n"+lcg(99, 600)+boiler_foot

unique=lcg(424242, 2000)   # unrelated, high-entropy

files={"v1":v1,"v2":v2,"v3":v3,"v4":v4,"doc_a":doc_a,"doc_b":doc_b,"unique":unique}
for name,data in files.items():
    (OUT/f"{name}.bin").write_bytes(data)
    print(f"{name:8} {len(data):6} B")
print(f"total {sum(len(d) for d in files.values())} B across {len(files)} files")
