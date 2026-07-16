# -*- coding: utf-8 -*-
# CUBR-0055 REGEN — dump UNIQUE B=4096-bit matrices (512-B cubes, 1D tiling,
# identical to matrix_scan_dump.py d=1: files truncated to 4096-byte rows) into a
# flat binary file of 512-byte records. Payload NEVER leaves the host: downstream
# probes read this file locally and emit aggregate JSON only.
# Usage: python3 scan_unique.py <out.bin> <root>...
import hashlib, json, os, pathlib, sys, time

R, CUBE = 4096, 512
MAX_FILE = 64 * 1024 * 1024

out, roots = sys.argv[1], sys.argv[2:]
t0 = time.time()
seen = set()
total = 0
processed = 0
with open(out, 'wb') as f:
    for root in roots:
        for dp, dns, fns in os.walk(root):
            if '.git' in dns:
                dns.remove('.git')
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    st = os.stat(p, follow_symlinks=False)
                except OSError:
                    continue
                if not os.path.isfile(p) or os.path.islink(p) or st.st_size < R or st.st_size > MAX_FILE:
                    continue
                try:
                    data = pathlib.Path(p).read_bytes()
                except OSError:
                    continue
                n = len(data) - len(data) % R
                if n < R:
                    continue
                processed += n
                for off in range(0, n, CUBE):
                    blk = data[off:off + CUBE]
                    total += 1
                    h = hashlib.blake2b(blk, digest_size=12).digest()
                    if h not in seen:
                        seen.add(h)
                        f.write(blk)
stats = {'cubes_total': total, 'unique': len(seen), 'bytes_processed': processed,
         'elapsed_s': round(time.time() - t0, 1), 'roots': roots}
pathlib.Path(out + '.stats.json').write_text(json.dumps(stats))
print(json.dumps(stats))
