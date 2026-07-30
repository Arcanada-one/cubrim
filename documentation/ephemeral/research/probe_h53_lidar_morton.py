#!/usr/bin/env python3
"""H-53 LiDAR point-cloud Morton-order spike (cheap, no Rust) + H-54 spin-off.

Brief: raw float32 xyz -> quantize uint16 -> Morton-sort -> delta -> zstd-19.
Baseline = zstd-19 on the RAW .bin (NOT .laz). Gate = <66% baseline (>=1.5x).
Corpus = one real KITTI velodyne scan (azureology/kitti-velo2cam 000007.bin,
115236 points x 4 float32 = 1843776 B).

HONEST FRAMING
  Cubrim is LOSSLESS; quantize->uint16 is LOSSY (~2mm grid). A lossy result is
  a LOWER BOUND on any lossless scheme. We measure both, plus a column-split SoA
  baseline, plus a reversible integer-delta lossless transform (round-trip
  verified). All entropy backends: zstd-19 (the gate reference), xz-9e (strong
  proxy), and the REAL cubrim binary.

RESULTS (this corpus)
  H-53 Morton-order: NO-GO. Morton-sort is +17% WORSE than the native Velodyne
    scan order (morton/native = 1.169 on the wrap-delta xyz stream). The sensor's
    native order (laser-ring azimuth sweep) already encodes better 3D locality
    than a Z-order curve; sorting by Morton scatters consecutive points across
    power-of-two boundaries and destroys the run structure the backend exploits.
    Confirms the consilium honest signal + brief failure-mode #1.

  H-54 spin-off (native-order SoA + reversible wrapping-uint32 delta on the
    float32 bit pattern, reflectance kept RAW): LOSSLESS, round-trip verified,
    clears the 1.5x gate -- 1.63x (zstd backend) / 1.96x (xz) / 1.60x (real
    cubrim default scheme). Same lever family as the shipped telemetry-columnar
    wins (H-30/31/40: AoS->SoA reorder + integer delta), transplanted to a BINARY
    float-array input class Cubrim cannot currently ingest. Spike-GO; a Rust
    binary-float-array container is the proposed next-run IMPL (scope: new input
    class, operator-flagged at H-50). Generalisation: 1 real scan only.
"""
import sys, subprocess
import numpy as np

BIN = sys.argv[1] if len(sys.argv) > 1 else "kitti.bin"

def z19(b): return len(subprocess.run(["zstd", "-19", "-c"], input=b, stdout=subprocess.PIPE).stdout)
def xz9(b): return len(subprocess.run(["xz", "-9", "-e", "-c"], input=b, stdout=subprocess.PIPE).stdout)

raw = open(BIN, "rb").read()
pts = np.frombuffer(raw, dtype=np.float32).reshape(-1, 4)
N = pts.shape[0]
xyz, refl = pts[:, :3], pts[:, 3]
base = z19(raw)
gate = base * 0.66
print(f"corpus={BIN} bytes={len(raw)} points={N}")
print(f"BASELINE zstd-19 raw .bin = {base}  xz-9e = {xz9(raw)}  GATE(1.5x) < {gate:.0f}\n")

# ---- reversible wrapping-uint32 delta on float32 bits, per column ----
def wrap_delta_cols(arr):                     # arr (M,3) float32 -> list of 3 uint32 delta cols
    out = []
    for c in range(3):
        col = np.ascontiguousarray(arr[:, c]).view(np.uint32)
        d = np.empty_like(col); d[0] = col[0]; d[1:] = col[1:] - col[:-1]   # uint32 wraps
        out.append(d)
    return out

def wrap_undelta(d):
    return (np.cumsum(d.astype(np.uint64)) & np.uint64(0xFFFFFFFF)).astype(np.uint32)

# reversibility proof
dc = wrap_delta_cols(xyz)
orig = [np.ascontiguousarray(xyz[:, c]).view(np.uint32) for c in range(3)]
assert all(np.array_equal(wrap_undelta(dc[c]), orig[c]) for c in range(3)), "delta not reversible!"
print("reversibility: wrapping-uint32 delta round-trips byte-exact = True")

xyz_delta = b"".join(np.ascontiguousarray(c).tobytes() for c in dc)
refl_raw = np.ascontiguousarray(refl).tobytes()

# ---- Morton order (the assigned hypothesis) ----
q = np.clip(np.round((xyz.astype(np.float64) - xyz.min(0)) *
                     (65535.0 / np.maximum(xyz.max(0) - xyz.min(0), 1e-9))), 0, 65535).astype(np.uint64)
def spread(v):
    v = v & np.uint64(0xFFFF); o = np.zeros_like(v)
    for i in range(16): o |= ((v >> np.uint64(i)) & np.uint64(1)) << np.uint64(3 * i)
    return o
mor = np.argsort(spread(q[:, 0]) | (spread(q[:, 1]) << np.uint64(1)) | (spread(q[:, 2]) << np.uint64(2)), kind="stable")
morton_delta = b"".join(np.ascontiguousarray(c).tobytes() for c in wrap_delta_cols(pts[mor][:, :3]))
nat, mz = z19(xyz_delta), z19(morton_delta)
print(f"\nH-53 MORTON vs NATIVE (xyz wrap-delta, zstd-19): native={nat} morton={mz} -> morton/native={mz/nat:.3f}")
print(f"  => Morton {'HURTS (NO-GO)' if mz > nat else 'helps'}: native order already more local than Z-order\n")

# ---- H-54 lossless GO check (native order) ----
xyz_z, refl_z = z19(xyz_delta), z19(refl_raw)
xyz_x, refl_x = xz9(xyz_delta), xz9(refl_raw)
print("H-54 native-order SoA + wrap-delta (xyz) + RAW reflectance, LOSSLESS:")
print(f"  zstd backend: xyz {xyz_z} + refl {refl_z} = {xyz_z+refl_z}  -> {base/(xyz_z+refl_z):.3f}x  [{'PASS' if xyz_z+refl_z<gate else 'FAIL'}]")
print(f"  xz   backend: xyz {xyz_x} + refl {refl_x} = {xyz_x+refl_x}  -> {base/(xyz_x+refl_x):.3f}x  [{'PASS' if xyz_x+refl_x<gate else 'FAIL'}]")
print("  (reflectance kept RAW: delta on refl HURTS, 70028->181018 zstd)")

# within-scan consistency
print("\nwithin-scan consistency (zstd backend):")
for name, seg in [("third-1", pts[:N//3]), ("third-2", pts[N//3:2*N//3]), ("third-3", pts[2*N//3:])]:
    dz = z19(b"".join(np.ascontiguousarray(c).tobytes() for c in wrap_delta_cols(seg[:, :3])))
    rz = z19(np.ascontiguousarray(seg[:, 3]).tobytes())
    bz = z19(np.ascontiguousarray(seg).tobytes())
    print(f"  {name}: {bz/(dz+rz):.3f}x")

print("\nReal cubrim (default scheme, measured separately, RT byte-exact):")
print("  raw .bin 844403 | xyz_delta 494823 + refl 71749 = 566572 -> 1.599x  [PASS]")
