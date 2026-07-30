#!/usr/bin/env python3
"""H-26 charged probe v2: can a pre-LZ transform that reduces the number of distinct
cross-file offsets lower the DATA-DETERMINED offset-entropy floor BELOW the current
coder — AFTER charging every bit it must transmit to the decoder (Gotcha #7)?

Two models are charged honestly:

  M2 (grid dictionary): a match is coded as a source-bucket index of width W. The
  decoder still needs the EXACT source byte, so the within-bucket offset log2(W) is
  charged per match (the v1 probe omitted this and produced a phantom win — the
  classic Gotcha #7 relocation of disorder).

  CDC (content-defined exact dedup): split the RAW file into content-defined chunks
  (rolling hash, avg size S), dedup EXACT-equal chunks. Only exact duplicates are
  referenced by chunk-id (no within-offset). Compares the dup-mass reference cost of
  dedup vs the LZ offset cost LZ already pays for the same mass.

Inputs: parse dump `flag,len,dist` (winning MODE_LZ parse) + the raw file + the
REAL measured offset bytes of the current coder (so the GO bar is the real coder,
not the order-0 proxy).
"""
import sys, math
from collections import Counter

def ent_bits(counts, n):
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / n; h -= p * math.log2(p)
    return h

def order0_bytesplit_bits(dists):
    if not dists:
        return 0.0
    total = 0.0
    for k in range(4):
        s = [(d >> (8 * k)) & 0xFF for d in dists]
        total += ent_bits(Counter(s).values(), len(s)) * len(s)
    return total

def order1_bytesplit_bits(dists):
    """Match the real coder: per byte-position stream, order-1 (prev-byte context)
    conditional entropy. This is what lz_encode_token_streams' order-0/1 rANS gets."""
    if not dists:
        return 0.0
    total = 0.0
    for k in range(4):
        s = [(d >> (8 * k)) & 0xFF for d in dists]
        ctx = {}
        prev = 0
        for v in s:
            ctx.setdefault(prev, Counter())[v] += 1
            prev = v
        for cnt in ctx.values():
            n = sum(cnt.values())
            total += ent_bits(cnt.values(), n) * n
    return total

def load_matches(path):
    matches = []
    pos = 0
    for line in open(path):
        fl, ln, ds = (int(x) for x in line.strip().split(","))
        if fl == 0:
            pos += 1
        else:
            matches.append((pos, pos - ds, ln, ds)); pos += ln
    return matches

def cdc_chunks(data, avg):
    """Gear-style content-defined chunking. mask has ~log2(avg) bits set."""
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

def main(parse_path, raw_path, real_off_bytes):
    data = open(raw_path, "rb").read(); L = len(data)
    matches = load_matches(parse_path)
    R = len(matches); dists = [m[3] for m in matches]
    o0 = order0_bytesplit_bits(dists) / 8
    o1 = order1_bytesplit_bits(dists) / 8
    print(f"L={L}  R={R}  distinct_dist={len(set(dists))}  match_mass={sum(m[2] for m in matches)} ({100*sum(m[2] for m in matches)/L:.0f}% of file)")
    print(f"  offset coder: order-0 byte-split {o0:.0f} B | order-1 byte-split {o1:.0f} B (= real coder model) | hint {real_off_bytes} B")
    BAR = o1  # GO bar = the real coder's model (order-1 byte-split)

    print("  -- M2 grid dictionary, within-bucket precision CHARGED --")
    for W in (64, 256, 1024, 4096):
        buckets = [m[1] // W for m in matches]
        c = Counter(buckets); D = len(c)
        ref = ent_bits(c.values(), R) * R          # which source bucket
        dic = D * math.log2(max(L, 2))             # transmit D bucket posns
        within = R * math.log2(W)                  # EXACT pos inside bucket (Gotcha#7)
        tot = (ref + dic + within) / 8
        print(f"    W={W:5d} D={D:6d}: ref {ref/8:8.0f} + dict {dic/8:7.0f} + within {within/8:8.0f} = {tot:9.0f} B  ({'WIN' if tot<BAR else 'lose'} vs {BAR:.0f}, x{tot/BAR:.3f})")

    print("  -- CDC exact-dedup ceiling (only EXACT-equal chunks deduped) --")
    for S in (64, 256, 1024):
        chunks = cdc_chunks(data, S)
        T = len(chunks); seen = {}; refs = []; dup_mass = 0
        for ch in chunks:
            key = hash(ch)
            if key in seen:
                refs.append(seen[key]); dup_mass += len(ch)
            else:
                seen[key] = len(seen); refs.append(-1)  # -1 = new
        U = len(seen)
        dup_refs = [r for r in refs if r >= 0]
        ref_bits = ent_bits(Counter(dup_refs).values(), len(dup_refs)) * len(dup_refs) if dup_refs else 0
        # LZ already covers dup_mass with matches: dup_mass/avg_match_len matches * (real b/match)
        avg_ml = sum(m[2] for m in matches) / R
        lz_for_dupmass = (dup_mass / avg_ml) * (8 * real_off_bytes / R) / 8
        print(f"    S={S:5d}: chunks T={T} unique U={U} dup_chunks={len(dup_refs)} dup_mass={dup_mass} ({100*dup_mass/L:.1f}% of file)")
        print(f"             dedup ref-cost {ref_bits/8:8.0f} B  vs  LZ-offset-for-same-mass {lz_for_dupmass:8.0f} B  ({'dedup WINS' if ref_bits/8 < lz_for_dupmass else 'LZ already cheaper'})")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
