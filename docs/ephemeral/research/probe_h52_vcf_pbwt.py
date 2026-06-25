#!/usr/bin/env python3
"""H-52 spike: VCF genotype-matrix transform — does a domain-aware transform beat zstd-19
by >=1.5x on a real 1000 Genomes genotype matrix? Skeptical (project meta-lesson: models
fabricate; verify faithfully).

The honest domain lever is PBWT (Positional BWT, Durbin 2014): reorder haplotypes at each
variant by their reversed-prefix match, so linkage-disequilibrium makes the allele column
form long runs. The permutation is rebuilt incrementally by the decoder (like BWT's
LF-mapping), so it is NOT transmitted — the only non-subsumable claim that survives charging.

We compare, on the same real genotype matrix, the zstd-19 size of:
  raw_text      — the raw "0|0\\t0|1\\t..." matrix (what zstd/cubrim naturally get)
  codes_vmajor  — 1 byte/genotype code, variant-major
  codes_smajor  — 1 byte/genotype code, sample-major (transpose)
  sparse        — store only non-ref cells (variant-delta, sample-delta, code)
  pbwt          — PBWT-reordered binary allele columns (the domain lever), zstd-19
Also report PBWT run statistics (total runs vs cells) — the information-theoretic floor.
Gate: best_transform <= zstd19(raw) / 1.5.
"""
import sys, subprocess
import numpy as np

GT = sys.argv[1]          # gt_raw.tsv (variant-major genotype matrix, tab-sep)
NVAR = int(sys.argv[2]) if len(sys.argv) > 2 else 3000

def z(data: bytes) -> int:
    return len(subprocess.run(["zstd", "-19", "-c"], input=data, capture_output=True).stdout)

# --- parse genotype matrix into codes + binary haplotypes ---
rows = []
with open(GT, "rb") as f:
    for i, line in enumerate(f):
        if i >= NVAR:
            break
        rows.append(line.rstrip(b"\n").split(b"\t"))
nvar = len(rows)
nsamp = len(rows[0])
print(f"genotype matrix: {nvar} variants x {nsamp} samples = {nvar*nsamp} cells")

# distinct genotype codes
alphabet = {}
def code(g):
    c = alphabet.get(g)
    if c is None:
        c = len(alphabet); alphabet[g] = c
    return c
codes = np.empty((nvar, nsamp), dtype=np.uint8)
for i, r in enumerate(rows):
    for j, g in enumerate(r):
        codes[i, j] = code(g)
print(f"distinct genotypes: {len(alphabet)} -> {list(alphabet)[:8]}")

raw_text = b"\n".join(b"\t".join(r) for r in rows)
zraw = z(raw_text)
zv = z(codes.tobytes())
zs = z(np.ascontiguousarray(codes.T).tobytes())

# sparse: non-ref (code != 0, where 0 = the most common = "0|0")
# remap so 0 = most frequent genotype
freq = np.bincount(codes.ravel(), minlength=len(alphabet))
ref = int(freq.argmax())
nz = np.argwhere(codes != ref)
sp = bytearray()
prev = 0
for (vi, sj) in nz:
    sp += int(vi).to_bytes(3, "big") + int(sj).to_bytes(2, "big") + bytes([codes[vi, sj]])
zsp = z(bytes(sp))
print(f"non-ref cells: {len(nz)} ({100*len(nz)/(nvar*nsamp):.3f}%)  ref-genotype={list(alphabet)[ref]!r}")

# --- PBWT on binary haplotypes (phased "a|b" -> two haplotypes) ---
# Build haplotype matrix Hap[hap, variant], hap in 0..2*nsamp, binary allele (0/1; >1 -> 1).
def split_hap(g):
    s = g.decode("latin1")
    if "|" in s or "/" in s:
        a, b = s.replace("/", "|").split("|")[:2]
        ai = 0 if a in ("0", ".") else 1
        bi = 0 if b in ("0", ".") else 1
        return ai, bi
    return 0, 0
H = np.zeros((2 * nsamp, nvar), dtype=np.uint8)
for i, r in enumerate(rows):
    for j, g in enumerate(r):
        a, b = split_hap(g)
        H[2 * j, i] = a; H[2 * j + 1, i] = b
M = 2 * nsamp
ppa = np.arange(M)
total_runs = 0
pbwt_cols = bytearray()      # the reordered allele columns (bit-packed per variant)
run_lengths = bytearray()
for k in range(nvar):
    col = H[ppa, k]
    # count runs
    changes = int(np.count_nonzero(np.diff(col))) + 1
    total_runs += changes
    pbwt_cols += np.packbits(col).tobytes()
    # RLE run-lengths (varint) — the realizable PBWT payload
    idx = np.flatnonzero(np.diff(col))
    starts = np.concatenate(([0], idx + 1))
    lens = np.diff(np.concatenate((starts, [M])))
    for L in lens:
        v = int(L)
        while True:
            b = v & 0x7F; v >>= 7
            run_lengths.append(b | (0x80 if v else 0))
            if not v: break
    # PBWT update: stable partition by allele
    a0 = ppa[col == 0]; a1 = ppa[col == 1]
    ppa = np.concatenate((a0, a1))
zpbwt_packed = z(bytes(pbwt_cols))         # packed reordered columns through zstd
zpbwt_rle = z(bytes(run_lengths))          # RLE run-lengths through zstd
cells_hap = M * nvar
print(f"PBWT: {total_runs} runs over {cells_hap} hap-cells = {total_runs/cells_hap:.4f} runs/cell "
      f"(avg run {cells_hap/total_runs:.1f})")

print("\n--- zstd-19 sizes (gate baseline = zstd raw) ---")
print(f"  raw_text          {zraw}")
print(f"  codes_vmajor      {zv}   ({zraw/zv:.2f}x)")
print(f"  codes_smajor      {zs}   ({zraw/zs:.2f}x)")
print(f"  sparse(non-ref)   {zsp}  ({zraw/zsp:.2f}x)")
print(f"  PBWT packed cols  {zpbwt_packed}  ({zraw/zpbwt_packed:.2f}x)")
print(f"  PBWT RLE runs     {zpbwt_rle}  ({zraw/zpbwt_rle:.2f}x)")
best = min(zv, zs, zsp, zpbwt_packed, zpbwt_rle)
print(f"\n  BEST transform = {best}  vs zstd-raw {zraw}  => {zraw/best:.2f}x  "
      f"{'GO(>=1.5x)' if zraw/best >= 1.5 else 'below-1.5x'}")
