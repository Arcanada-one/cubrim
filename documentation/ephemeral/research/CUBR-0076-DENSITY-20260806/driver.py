#!/usr/bin/env python3
"""CUBR-0076 density experiment driver.

Ratio-only, load-insensitive. For every observation (baseline or cubrim,
whole file or slice) a byte-exact round trip is performed; any failure aborts.
Outputs: baselines.tsv, slices.tsv, per-run raw profiler tables.
"""
import json, hashlib, subprocess, os, sys, re

CORPUS = '/home/dev/.worktrees/cubrim/CUBR-0087/bench/web-corpus'
BIN = sys.argv[1]
OUT = sys.argv[2]
BLOCK = 65536
STATIC = ['vs_bwt_rans', 'vs_bwt_huff', 'vs_t4_huff', 'vs_order2_rans', 'vs_lz_rans']
ADAPT = ['vs_adaptive', 'vs_ctxmix', 'vs_geomix']

os.makedirs(OUT + '/raw', exist_ok=True)
m = json.load(open(CORPUS + '/manifest.v2.json'))

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    assert r.returncode == 0, (cmd, r.stderr[-400:])
    return r

def parse_prof(stderr_text):
    rows = {}
    for line in stderr_text.splitlines():
        mm = re.match(r'^(\S+)\s+(\d+)\s+[\d.]+\s+[\d.]+\s+(\d+)\s+(\d+)\s*$', line)
        if mm:
            rows[mm.group(1)] = (int(mm.group(2)), int(mm.group(3)), int(mm.group(4)))
    return rows  # name -> (calls, wins, out_bytes)

bl = open(OUT + '/baselines.tsv', 'w')
bl.write('sample_id\torig\tbrotli11\tgzip9\tzstd19\tbr_rt\tgz_rt\tzs_rt\n')
sl = open(OUT + '/slices.tsv', 'w')
sl.write('sample_id\tslice\toffset\tslice_len\tslice_sha256\temitted_bytes\temitted_rt\t'
         'base_blob\twinner_stream\twinner_name\tstatic_min_stream\tstatic_min_name\t'
         'static_forced_blob\tcm2_small\n')

for s in m['samples']:
    p = os.path.join(CORPUS, s['path'])
    data = open(p, 'rb').read()
    assert hashlib.sha256(data).hexdigest() == s['sha256'], p
    sid = s['sample_id']

    # --- baselines, each with byte-exact round trip
    br = run(['/usr/bin/brotli', '-q', '11', '--stdout', p]).stdout
    br_back = run(['/usr/bin/brotli', '-d', '--stdout'], input=br).stdout
    gz = run(['/usr/bin/gzip', '-9', '-c', p]).stdout
    gz_back = run(['/usr/bin/gzip', '-d', '-c'], input=gz).stdout
    zs = run(['/usr/bin/zstd', '-19', '--quiet', '--stdout', p]).stdout
    zs_back = run(['/usr/bin/zstd', '-d', '--quiet', '--stdout'], input=zs).stdout
    assert br_back == data and gz_back == data and zs_back == data, sid
    bl.write(f'{sid}\t{len(data)}\t{len(br)}\t{len(gz)}\t{len(zs)}\tPASS\tPASS\tPASS\n')

    # --- cubrim per-slice profiled encodes (slice == chunked-path block size)
    n_slices = (len(data) + BLOCK - 1) // BLOCK
    for k in range(n_slices):
        chunk = data[k * BLOCK:(k + 1) * BLOCK]
        cpath = f'{OUT}/raw/{sid}.slice{k}.bin'
        open(cpath, 'wb').write(chunk)
        cbr = f'{OUT}/raw/{sid}.slice{k}.cbr'
        env = dict(os.environ, CUBRIM_PROFILE='1')
        r = subprocess.run([BIN, 'compress', '--value-scheme', 'bwt-rans', cpath, cbr],
                           capture_output=True, env=env)
        assert r.returncode == 0, (sid, k, r.stderr[-400:])
        open(f'{OUT}/raw/{sid}.slice{k}.prof.txt', 'wb').write(r.stderr)
        prof = parse_prof(r.stderr.decode())
        back = f'{OUT}/raw/{sid}.slice{k}.back'
        run([BIN, 'decompress', cbr, back])
        rt = open(back, 'rb').read() == chunk
        assert rt, (sid, k)
        os.remove(back)

        emitted = os.path.getsize(cbr)
        base_blob = prof.get('base', (0, 0, 0))[2]
        cm2_small = prof.get('cm2_small', prof.get('cm2', (0, 0, 0)))[2]
        streams = {n: prof[n][2] for n in STATIC + ADAPT if n in prof and prof[n][2] > 0}
        finals = [n for n in prof if n.startswith('FINAL:') and prof[n][1] > 0]
        if not finals:
            # rans-family rail did not run (raw-store / non-cube input): the static
            # answer for this slice is the emitted store-mode blob itself.
            sl.write(f'{sid}\t{k}\t{k * BLOCK}\t{len(chunk)}\t'
                     f'{hashlib.sha256(chunk).hexdigest()}\t{emitted}\tPASS\t'
                     f'{base_blob}\t0\tNONE(raw)\t0\tNONE(raw)\t{emitted}\t{cm2_small}\n')
            continue
        assert len(finals) == 1, (sid, k, finals)
        fmap = {'FINAL:bwt_rans': 'vs_bwt_rans', 'FINAL:bwt_huff': 'vs_bwt_huff',
                'FINAL:t4_huff': 'vs_t4_huff', 'FINAL:order2_rans': 'vs_order2_rans',
                'FINAL:adaptive': 'vs_adaptive', 'FINAL:ctxmix': 'vs_ctxmix',
                'FINAL:geomix': 'vs_geomix', 'FINAL:lz_rans': 'vs_lz_rans'}
        win_name = fmap[finals[0]]
        win_stream = streams[win_name]
        smin_name = min((n for n in STATIC if n in streams), key=lambda n: streams[n])
        smin = streams[smin_name]
        static_forced = base_blob - win_stream + smin
        sl.write(f'{sid}\t{k}\t{k * BLOCK}\t{len(chunk)}\t'
                 f'{hashlib.sha256(chunk).hexdigest()}\t{emitted}\t{"PASS" if rt else "FAIL"}\t'
                 f'{base_blob}\t{win_stream}\t{win_name}\t{smin}\t{smin_name}\t'
                 f'{static_forced}\t{cm2_small}\n')

bl.close(); sl.close()
print('driver complete')
