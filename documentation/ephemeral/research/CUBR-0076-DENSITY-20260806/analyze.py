#!/usr/bin/env python3
"""Analyze captured profiler tables: static-forced blob per slice, aggregates."""
import json, re, os, sys, hashlib, subprocess

CORPUS = '/home/dev/.worktrees/cubrim/CUBR-0087/bench/web-corpus'
OUT = sys.argv[1]
BIN = sys.argv[2]
BLOCK = 65536
RAIL_ORDER = ['vs_bwt_rans', 'vs_bwt_huff', 'vs_t4_huff', 'vs_order2_rans',
              'vs_adaptive', 'vs_ctxmix', 'vs_geomix', 'vs_lz_rans']
STATIC = ['vs_bwt_rans', 'vs_bwt_huff', 'vs_t4_huff', 'vs_order2_rans', 'vs_lz_rans']
RAW_OVERHEAD = 13  # measured: woff2 23,664 -> 23,677 census RAW blob

def parse_prof(path):
    rows = {}
    for line in open(path):
        mm = re.match(r'^(\S+)\s+(\d+)\s+[\d.]+\s+[\d.]+\s+(\d+)\s+(\d+)\s*$', line)
        if mm:
            rows[mm.group(1)] = (int(mm.group(2)), int(mm.group(3)), int(mm.group(4)))
    return rows

def rail_min(streams, names):
    best = None
    for n in names:  # earlier-listed wins ties, matching the encoder
        if n in streams and (best is None or streams[n] < streams[best]):
            best = n
    return best

m = json.load(open(CORPUS + '/manifest.v2.json'))
census = {}  # current emitted sizes, from stock whole-file encodes (mode census)
for line in open('/home/dev/.worktrees/cubrim/CUBR-0076/documentation/ephemeral/research/CUBR-0076-WEBMODE-CENSUS-20260806/census.tsv'):
    f = line.strip().split('\t')
    if f[0] != 'sample_id':
        census[f[0]] = int(f[4])

print(f'{"sample":38s} {"cur(CM2)":>9s} {"staticF":>9s} {"delta%":>8s} {"b11":>7s} {"gz9":>7s} {"zs19":>7s}')
agg = dict(cur=0, static=0, b11=0, gz9=0, zs19=0, orig=0)
bl = {r[0]: r for r in [l.strip().split('\t') for l in open(OUT + '/baselines.tsv')][1:]}
detail = open(OUT + '/static-detail.tsv', 'w')
detail.write('sample_id\tslice\tbase_blob\twinner\twinner_stream\tstatic_min\tstatic_stream\tstatic_forced\traw_clamp\n')

for s in m['samples']:
    sid = s['sample_id']
    orig = s['byte_count']
    n_slices = (orig + BLOCK - 1) // BLOCK
    static_total = 0
    for k in range(n_slices):
        prof = parse_prof(f'{OUT}/raw/{sid}.slice{k}.prof.txt')
        slice_len = min(BLOCK, orig - k * BLOCK)
        streams = {n: prof[n][2] for n in RAIL_ORDER if n in prof and prof[n][2] > 0}
        raw_cost = slice_len + RAW_OVERHEAD
        if not streams:
            sf = min(os.path.getsize(f'{OUT}/raw/{sid}.slice{k}.cbr'), raw_cost)
            detail.write(f'{sid}\t{k}\t-\tNONE\t0\tNONE\t0\t{sf}\t{raw_cost}\n')
        else:
            base = prof['base'][2]
            win = rail_min(streams, RAIL_ORDER)
            smin = rail_min(streams, STATIC)
            sf = base - streams[win] + streams[smin]
            clamped = min(sf, raw_cost)
            detail.write(f'{sid}\t{k}\t{base}\t{win}\t{streams[win]}\t{smin}\t{streams[smin]}\t{sf}\t{raw_cost}\n')
            sf = clamped
        static_total += sf
    cur = census[sid]
    b11, gz9, zs19 = int(bl[sid][2]), int(bl[sid][3]), int(bl[sid][4])
    d = 100.0 * (static_total - cur) / cur
    print(f'{sid:38s} {cur:9d} {static_total:9d} {d:+8.1f} {b11:7d} {gz9:7d} {zs19:7d}')
    for key, v in [('cur', cur), ('static', static_total), ('b11', b11), ('gz9', gz9), ('zs19', zs19), ('orig', orig)]:
        agg[key] += v

detail.close()
print('-' * 90)
print(f'AGGREGATE orig={agg["orig"]} cur={agg["cur"]} staticF={agg["static"]} b11={agg["b11"]} gz9={agg["gz9"]} zs19={agg["zs19"]}')
print(f'cur/b11        = {agg["cur"]/agg["b11"]:.6f}')
print(f'staticF/b11    = {agg["static"]/agg["b11"]:.6f}   (WIN bar: <= 1.0)')
print(f'staticF/gz9    = {agg["static"]/agg["gz9"]:.6f}   (GO bar:  <= 1.0)')
print(f'staticF/zs19   = {agg["static"]/agg["zs19"]:.6f}')
print(f'staticF vs cur = {100.0*(agg["static"]-agg["cur"])/agg["cur"]:+.2f}%  (headroom to b11 parity: +{100.0*(agg["b11"]-agg["cur"])/agg["cur"]:.2f}%)')
