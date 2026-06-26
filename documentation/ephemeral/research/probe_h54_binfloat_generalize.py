#!/usr/bin/env python3
"""H-54 generalisation: binary float-array SoA + per-column competitive reversible
wrapping-uint32 delta, across 4 diverse real point clouds (KITTI / nuScenes /
ScanNet / SUN RGB-D). Confirms the 1.5x-over-zstd-19 spike-GO generalises beyond
the single KITTI scan before any Rust.

Design under test (= the proposed Rust container):
  AoS .bin -> reinterpret float32, record width W -> SoA (column-major) ->
  per column pick min(wrapping-uint32-delta, raw) competitively (a 1-byte
  col-mode flag) -> entropy backend. Reversible (delta round-trips byte-exact);
  competitive per-column so attribute columns (reflectance/rgb) that don't
  benefit from delta stay raw.
Gate: total < 66% of zstd-19 on the raw .bin (>=1.5x).
"""
import subprocess, numpy as np

def z19(b): return len(subprocess.run(["zstd", "-19", "-c"], input=b, stdout=subprocess.PIPE).stdout)

CB = "/home/dev/cubrim-h19/code/cubrim-rs/target/release/cubrim"
def cubrim(b):
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False) as f: f.write(b); inp=f.name
    out=inp+".cb"; dec=inp+".dec"
    subprocess.run([CB,"compress",inp,out],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run([CB,"decompress",out,dec],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    rt = open(inp,"rb").read()==open(dec,"rb").read()
    sz=os.path.getsize(out)
    for p in (inp,out,dec):
        try: os.unlink(p)
        except: pass
    return sz, rt

def wrap_delta(col_u32):
    d=np.empty_like(col_u32); d[0]=col_u32[0]; d[1:]=col_u32[1:]-col_u32[:-1]; return d
def wrap_undelta(d):
    return (np.cumsum(d.astype(np.uint64)) & np.uint64(0xFFFFFFFF)).astype(np.uint32)

def soa_competitive(b, W):
    """SoA split into W//4 columns; per col pick min(delta,raw) via zstd. Returns
    (blob_for_backend, per_col_modes, est_zstd_total). blob = concat of chosen cols."""
    fcount=W//4
    arr=np.frombuffer(b,dtype=np.uint32).reshape(-1,fcount)
    M=arr.shape[0]; blob=bytearray(); modes=[]; est=0
    for c in range(fcount):
        col=np.ascontiguousarray(arr[:,c])
        d=wrap_delta(col)
        assert np.array_equal(wrap_undelta(d), col), "delta not reversible"
        raw_b=col.tobytes(); del_b=d.tobytes()
        zr, zd = z19(raw_b), z19(del_b)
        if zd<=zr: blob+=del_b; modes.append('D'); est+=zd
        else:      blob+=raw_b; modes.append('R'); est+=zr
    return bytes(blob), modes, est

FILES=[("kitti.bin",16,"KITTI Velodyne 4xf32"),
       ("nuscenes.bin",20,"nuScenes LiDAR 5xf32"),
       ("scannet.bin",24,"ScanNet RGB-D 6xf32"),
       ("sunrgbd.bin",24,"SUN RGB-D 6xf32")]

print(f"{'file':12s} {'W':>3s} {'base_zstd':>10s} {'transf_z':>9s} {'x_zstd':>7s}  {'cub_raw':>8s} {'cub_tr':>8s} {'x_cub':>6s} modes")
gopass=0
for fn,W,desc in FILES:
    b=open(fn,"rb").read()
    base=z19(b)
    blob,modes,est=soa_competitive(b,W)
    # cubrim on raw vs on the per-column blob (concatenated chosen columns)
    cub_raw,rt1=cubrim(b)
    cub_tr,rt2=cubrim(blob)
    xz=base/est; xc=cub_raw/cub_tr  # cubrim self-improvement
    # honest gate is vs zstd-19 raw; cubrim-on-blob vs zstd-raw:
    xc_vs_zstd=base/cub_tr
    tag="PASS" if xc_vs_zstd>=1.5 else "fail"
    if xc_vs_zstd>=1.5: gopass+=1
    print(f"{fn:12s} {W:3d} {base:10d} {est:9d} {xz:6.3f}x  {cub_raw:8d} {cub_tr:8d} {xc_vs_zstd:5.3f}x {''.join(modes)} [{tag}] RT={rt1 and rt2}")

print(f"\n{gopass}/4 point clouds clear 1.5x vs zstd-19 (cubrim-on-transformed-blob).")
print("modes: D=delta column won, R=raw column won (per-column competitive).")
