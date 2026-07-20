#!/usr/bin/env python3
import numpy as np, hashlib, os, io

SRC = "/tmp/uci-dl"
WB = "/home/dev/cubrim-worldbench"
C1 = os.path.join(WB, "corpus1-wide-deterministic")
C2 = os.path.join(WB, "corpus2-raw-doubles")

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def slice_to_bytes(in_path, out_path, target_bytes, header=None):
    """Copy whole lines from in_path until ~target_bytes; optional header line prepended."""
    written = 0
    with open(in_path, "rb") as fi, open(out_path, "wb") as fo:
        if header is not None:
            hb = (header + "\n").encode()
            fo.write(hb); written += len(hb)
        for line in fi:
            if written >= target_bytes:
                break
            # skip blank / malformed trailing lines
            if line.strip() == b"":
                continue
            fo.write(line); written += len(line)
    return written

# ---------- CORPUS 1a: Adult / Census (non-temporal, education<->education-num deterministic) ----------
adult_header = ("age,workclass,fnlwgt,education,education_num,marital_status,occupation,"
                "relationship,race,sex,capital_gain,capital_loss,hours_per_week,native_country,income")
a_out = os.path.join(C1, "adult_census.csv")
a_bytes = slice_to_bytes(os.path.join(SRC, "adult/adult.data"), a_out, 1_500_000, header=adult_header)

# ---------- CORPUS 1b: Covertype (non-temporal cartographic; hillshade trig-correlated, soil/wilderness one-hot) ----------
cov_cols = (["Elevation","Aspect","Slope","Horizontal_Distance_To_Hydrology",
             "Vertical_Distance_To_Hydrology","Horizontal_Distance_To_Roadways",
             "Hillshade_9am","Hillshade_Noon","Hillshade_3pm",
             "Horizontal_Distance_To_Fire_Points"]
            + [f"Wilderness_Area_{i}" for i in range(1,5)]
            + [f"Soil_Type_{i}" for i in range(1,41)]
            + ["Cover_Type"])
cov_header = ",".join(cov_cols)
c_out = os.path.join(C1, "covtype_cartographic.csv")
c_bytes = slice_to_bytes(os.path.join(SRC, "covertype/covtype.data"), c_out, 1_500_000, header=cov_header)

# ---------- CORPUS 2: raw IEEE-754 double arrays from real Superconductivity features ----------
# Read first N data rows of train.csv (81 features + critical_temp). Values in the CSV are
# decimal-rounded (~7 digits) -> decimal-representable. We emit TWO arrays:
#   (raw)    real CSV values as float64  -> decimal-representable CONTRAST (H-40 already wins)
#   (zscore) per-column z-score standardized -> genuine full-mantissa doubles, ALP-decimal INAPPLICABLE
#            (exactly what an ML pipeline's StandardScaler emits, stored as .npy every day)
N_ROWS = 2600  # ~2600 x 82 x 8B ~= 1.7 MB per array
rows = []
with open(os.path.join(SRC, "supercond/train.csv"), "r") as f:
    header = f.readline()
    for i, line in enumerate(f):
        if i >= N_ROWS:
            break
        parts = line.rstrip("\n").split(",")
        rows.append([float(x) for x in parts])
raw = np.asarray(rows, dtype=np.float64)            # (N, 82)
raw_path = os.path.join(C2, "supercond_features_raw_f64.npy")
np.save(raw_path, raw)

mu = raw.mean(axis=0); sd = raw.std(axis=0); sd[sd == 0] = 1.0
z = (raw - mu) / sd                                 # full-mantissa doubles
z_path = os.path.join(C2, "supercond_features_zscore_f64.npy")
np.save(z_path, z)

# quick precision diagnostic: how many of the raw vs z values are short-decimal-representable
def short_decimal_frac(arr, max_dig=8):
    flat = arr.ravip() if False else arr.ravel()
    ok = 0; tot = min(len(flat), 200000);
    for v in flat[:tot]:
        s = repr(float(v))
        # representable as integer * 10^-k with k<=max_dig
        if "e" in s or "E" in s:
            continue
        frac = s.split(".")[1] if "." in s else ""
        if len(frac) <= max_dig:
            ok += 1
    return ok / tot

raw_short = short_decimal_frac(raw)
z_short = short_decimal_frac(z)

print("=== BUILT ===")
for p, n in [(a_out,a_bytes),(c_out,c_bytes)]:
    print(f"C1 {os.path.basename(p):28s} {os.path.getsize(p):>9d} B  sha256={sha256(p)[:16]}")
for p in [raw_path, z_path]:
    arr = np.load(p)
    print(f"C2 {os.path.basename(p):34s} {os.path.getsize(p):>9d} B  shape={arr.shape} dtype={arr.dtype} sha256={sha256(p)[:16]}")
print(f"short-decimal(<=8dp) fraction: raw={raw_short:.3f}  zscore={z_short:.3f}")
print("rows in adult slice:", sum(1 for _ in open(a_out))-1, " covtype slice:", sum(1 for _ in open(c_out))-1)
