#!/usr/bin/env python3
"""Analyze the adaptation tbits sweep: model-split cycles/call vs working set."""
import json, re, os, sys

OUT = sys.argv[1]
rows = []
for f in ['dickens', 'nci']:
    for t in (['native', '22', '20', '18', '15'] if f == 'dickens' else ['native', '22', '20', '18', '15', '12']):
        tag = f'{f}.t{t}'
        j = json.load(open(f'{OUT}/{tag}.profile.json'))
        dp = j['decode_profile']
        assert dp.get('cycles_supported') and j.get('exact_roundtrip', dp.get('exact_roundtrip')), tag
        splits = {s['name']: s for s in dp['model_splits'] if s['applicable']}
        rss_kib = None
        for line in open(f'{OUT}/{tag}.time.txt'):
            m = re.search(r'Maximum resident set size.*?: (\d+)', line)
            if m: rss_kib = int(m.group(1))
        perf = {}
        for line in open(f'{OUT}/{tag}.perf.csv'):
            p = line.split(',')
            if len(p) > 3 and p[0].strip() and not line.startswith('#'):
                try: perf[p[2]] = int(p[0])
                except ValueError: pass
        comp = os.path.getsize(f'{OUT}/{tag}.cbr')
        ad = splits['model.adaptation']
        cs = splits['model.counter_state_lookup']
        dot = splits['model.dot_products']
        calls = ad['calls']
        rows.append(dict(file=f, tbits=t, comp=comp, rss_mib=rss_kib/1024 if rss_kib else 0,
                         calls=calls,
                         adapt_cpc=ad['cycles']/calls, lookup_cpc=cs['cycles']/calls,
                         dot_cpc=dot['cycles']/calls,
                         total_cyc=dp['total_cycles'], total_s=dp['total_nanos']/1e9,
                         llc_miss_pc=perf.get('LLC-load-misses', 0)/calls,
                         cache_miss_pc=perf.get('cache-misses', 0)/calls,
                         dtlb_miss_pc=perf.get('dTLB-load-misses', 0)/calls,
                         ipc=(perf.get('instructions', 0)/perf['cycles']) if perf.get('cycles') else 0))

print(f'{"file":8s} {"tbits":>6s} {"comp_B":>8s} {"rss_MiB":>8s} {"adapt":>8s} {"lookup":>8s} {"dot":>7s} '
      f'{"LLCm/c":>7s} {"TLBm/c":>7s} {"IPC":>5s} {"dec_s":>7s}')
for r in rows:
    print(f'{r["file"]:8s} {r["tbits"]:>6s} {r["comp"]:8d} {r["rss_mib"]:8.1f} {r["adapt_cpc"]:8.1f} '
          f'{r["lookup_cpc"]:8.1f} {r["dot_cpc"]:7.1f} {r["llc_miss_pc"]:7.2f} {r["dtlb_miss_pc"]:7.2f} '
          f'{r["ipc"]:5.2f} {r["total_s"]:7.2f}')

with open(f'{OUT}/sweep-summary.tsv', 'w') as fo:
    keys = list(rows[0].keys())
    fo.write('\t'.join(keys) + '\n')
    for r in rows:
        fo.write('\t'.join(str(r[k]) for k in keys) + '\n')
print('\nwrote sweep-summary.tsv')
