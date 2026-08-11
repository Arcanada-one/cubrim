#!/usr/bin/env python3
"""H-18 go/no-go probe: cross-file duplicate-chunk ratio on the frozen corpus.

Content-defined chunking (Gear rolling hash, FastCDC-style) over every corpus
file, then measure how many chunk bytes are duplicated ACROSS different files.
If the cross-file duplicate ratio is ~0, corpus-local dedup against a shared
dictionary cannot beat BWT on this corpus regardless of implementation
(analogue of the Gotcha #3 entropy probe). Decision is corpus-bound, not
algorithm-bound. No Rust required.
"""
import hashlib, os, sys
from pathlib import Path

CORPUS = Path("documentation/ephemeral/research/corpus")
FILES = ["sparse_clustered","dense","text","log_like","binary_mixed",
         "random_high","sparse_small","both_sparse_16","both_sparse_24",
         "block_bound_runs"]

# Gear table for the rolling hash (deterministic, seeded by index).
GEAR = [(i*2654435761) & 0xFFFFFFFFFFFFFFFF for i in range(256)]

def cdc_chunks(data, min_sz, avg_sz, max_sz):
    """FastCDC-ish: cut when low MASK bits of the rolling hash are zero."""
    mask = (1 << (avg_sz.bit_length()-1)) - 1   # ~avg_sz expected chunk
    chunks, n, start, h = [], len(data), 0, 0
    i = 0
    while i < n:
        h = ((h << 1) + GEAR[data[i]]) & 0xFFFFFFFFFFFFFFFF
        sz = i - start + 1
        if sz >= min_sz and ((h & mask) == 0 or sz >= max_sz):
            chunks.append(bytes(data[start:i+1])); start = i+1; h = 0
        i += 1
    if start < n:
        chunks.append(bytes(data[start:n]))
    return chunks

def run(avg_sz):
    min_sz, max_sz = max(16, avg_sz//4), avg_sz*4
    per_file_hashes = {}     # file -> list of (hash, len)
    total_bytes = 0
    for name in FILES:
        p = CORPUS / f"{name}.bin"
        data = p.read_bytes()
        total_bytes += len(data)
        chs = cdc_chunks(data, min_sz, avg_sz, max_sz)
        per_file_hashes[name] = [(hashlib.sha1(c).hexdigest(), len(c)) for c in chs]

    # which chunk-hashes appear in >=2 distinct files?
    files_per_hash = {}
    for name, lst in per_file_hashes.items():
        for h,_ in set((h,l) for h,l in lst):
            files_per_hash.setdefault(h, set()).add(name)
    crossfile_hashes = {h for h,fs in files_per_hash.items() if len(fs) >= 2}

    # bytes that are cross-file duplicates (count every occurrence beyond the
    # first global store; i.e. redundant bytes a shared dict could remove).
    seen = set(); redundant = 0; uniq_store = 0
    occ = []  # (hash,len) in deterministic file order
    for name in FILES:
        for h,l in per_file_hashes[name]:
            occ.append((h,l,name))
    for h,l,name in occ:
        if h in seen:
            redundant += l            # duplicate occurrence — dict would dedup it
        else:
            seen.add(h); uniq_store += l
    crossfile_redundant = sum(
        l for h,l,name in occ
        if h in crossfile_hashes and (h, name) != min(((h2,n2) for h2,_,n2 in occ if h2==h), default=(h,name))
    )

    return {
        "avg_chunk": avg_sz,
        "total_bytes": total_bytes,
        "total_chunks": sum(len(v) for v in per_file_hashes.values()),
        "distinct_chunks": len(seen),
        "crossfile_dup_hashes": len(crossfile_hashes),
        "redundant_bytes_any": redundant,
        "redundant_ratio_any": round(redundant/total_bytes, 6),
        "crossfile_redundant_bytes": crossfile_redundant,
        "crossfile_redundant_ratio": round(crossfile_redundant/total_bytes, 6),
    }

print(f"{'avg':>6} {'chunks':>7} {'distinct':>9} {'xfile#':>7} "
      f"{'dup_any%':>9} {'xfile_dup%':>11}")
results = []
for avg in (64, 128, 256, 512, 1024):
    r = run(avg); results.append(r)
    print(f"{r['avg_chunk']:>6} {r['total_chunks']:>7} {r['distinct_chunks']:>9} "
          f"{r['crossfile_dup_hashes']:>7} {r['redundant_ratio_any']*100:>8.3f}% "
          f"{r['crossfile_redundant_ratio']*100:>10.3f}%")

best_xfile = max(r['crossfile_redundant_ratio'] for r in results)
print()
print(f"total corpus bytes: {results[0]['total_bytes']}")
print(f"max cross-file redundant ratio across chunk sizes: {best_xfile*100:.4f}%")
# Decision: a shared dict needs the cross-file redundancy to exceed its own
# overhead (dict header + per-reference cost). Even a generous threshold:
GO = best_xfile >= 0.05  # 5% cross-file redundancy is a charitable floor
print(f"VERDICT: {'GO (worth a corpus-total size model)' if GO else 'NO-GO on this corpus'} "
      f"(threshold 5.0000%)")
sys.exit(0 if GO else 1)
