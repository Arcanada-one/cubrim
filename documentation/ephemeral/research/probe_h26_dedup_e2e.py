#!/usr/bin/env python3
"""H-26 end-to-end dedup validation (Gotcha #6: charge the FULL serialization).

Reversible CDC exact-dedup pre-pass, then measure the REAL total:
  total = compress_cubrim(residual)         # unique chunks, first-occurrence order
        + flag_stream_bits                  # per-chunk new/dup, order-0 entropy
        + dup_ref_bits                      # canonical chunk-id per dup, order-1 entropy

Boundaries are FREE: CDC on the reconstructed residual re-derives unique-chunk
boundaries; the flag+ref stream interleaves new/dup. Dup chunks are EXACT copies of
an earlier unique chunk (no within-offset — the valid escape from Gotcha #7).

Compare total vs the current real cubrim size and vs zstd-19.
"""
import sys, math, subprocess, tempfile, os
from collections import Counter

BIN = "code/cubrim-rs/target/release/cubrim"

def ent_bits(counts, n):
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / n; h -= p * math.log2(p)
    return h

def cdc_chunks(data, avg):
    mask = (1 << max(1, avg.bit_length() - 1)) - 1
    h = 0; chunks = []; start = 0; minc = avg // 4; maxc = avg * 4
    for i, b in enumerate(data):
        h = ((h << 1) + b) & 0xFFFFFFFF
        ln = i - start + 1
        if (ln >= minc and (h & mask) == 0) or ln >= maxc:
            chunks.append(data[start:i + 1]); start = i + 1
    if start < len(data):
        chunks.append(data[start:])
    return chunks

def cubrim_size(blob, scheme="lz-rans"):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(blob); inp = f.name
    out = inp + ".cbr"
    subprocess.run([BIN, "compress", inp, out, "--value-scheme", scheme],
                   capture_output=True)
    sz = os.path.getsize(out)
    os.unlink(inp); os.unlink(out)
    return sz

def run(raw_path, cur_size, zstd_size):
    data = open(raw_path, "rb").read(); L = len(data)
    print(f"\n### {os.path.basename(raw_path)}  L={L}  current cubrim={cur_size}  zstd={zstd_size}")
    base = cubrim_size(data)
    print(f"  sanity: cubrim(full file) = {base} (should ~= current {cur_size})")
    for S in (256, 1024):
        chunks = cdc_chunks(data, S)
        seen = {}; flags = []; refs = []; residual = bytearray()
        for ch in chunks:
            key = ch  # exact match
            if key in seen:
                flags.append(1); refs.append(seen[key])
            else:
                seen[key] = len(seen); flags.append(0); residual += ch
        U = len(seen); T = len(chunks)
        res_size = cubrim_size(bytes(residual))
        flag_bits = ent_bits(Counter(flags).values(), T) * T
        # order-1 entropy of the ref-id stream (position-invariant ids)
        ctx = {}; prev = 0
        for r in refs:
            ctx.setdefault(prev, Counter())[r] += 1; prev = r
        ref_bits = sum(ent_bits(c.values(), sum(c.values())) * sum(c.values())
                       for c in ctx.values())
        total = res_size + math.ceil(flag_bits / 8) + math.ceil(ref_bits / 8)
        d = 100 * (total - zstd_size) / zstd_size
        print(f"  S={S:5d}: T={T} U={U} residual={len(residual)} ({100*len(residual)/L:.0f}%) "
              f"-> cubrim(res)={res_size} + flags={math.ceil(flag_bits/8)} + refs={math.ceil(ref_bits/8)} "
              f"= {total}  vs cur {cur_size} ({'WIN' if total<cur_size else 'lose'}) | vs zstd {zstd_size} = {d:+.1f}%")

if __name__ == "__main__":
    # args: raw_path cur_size zstd_size
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
