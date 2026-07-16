#!/usr/bin/env bash
# Pinned 7-class corpus generator. Deterministic: SEED fixed, python3 PRNG.
# Params (recorded in manifest.json): seed, files per class, size range,
# dup_injection fraction (share of files that are near-copies of a donor —
# gives the corpus a dup-fraction above the router threshold for charged
# aggregate runs).
set -euo pipefail
OUT="${1:?usage: generate_7class.sh <out-dir>}"
SEED="${SEED:-20260716}"
DUP_INJECTION="${DUP_INJECTION:-0.30}"
python3 - "$OUT" "$SEED" "$DUP_INJECTION" <<'PY'
import json, os, random, sys, hashlib
out, seed, dup_inj = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
rng = random.Random(seed)
classes = {
    "code":   (lambda n: ("\n".join("fn f%d() { let x = %d; }" % (rng.randrange(9999), rng.randrange(99)) for _ in range(n // 30))).encode()),
    "docs":   (lambda n: (" ".join(rng.choice(["fleet","router","chunk","matrix","ordinal","bloom","store","delta"]) for _ in range(n // 6))).encode()),
    "config": (lambda n: ("\n".join("key_%d = %d" % (rng.randrange(999), rng.randrange(10**6)) for _ in range(n // 15))).encode()),
    "www":    (lambda n: ("\n".join('10.0.0.%d - - [16/Jul/2026] "GET /p/%d" 200 %d' % (rng.randrange(255), rng.randrange(9999), rng.randrange(99999)) for _ in range(n // 50))).encode()),
    "media":  (lambda n: bytes(rng.getrandbits(8) for _ in range(n))),           # incompressible
    "archives":(lambda n: bytes(rng.getrandbits(8) for _ in range(n))),
    "other":  (lambda n: (b"MIXED" + bytes(rng.getrandbits(8) for _ in range(n // 2)) + ("pad " * (n // 8)).encode())),
}
os.makedirs(out, exist_ok=True)
manifest = {"seed": seed, "dup_injection": dup_inj, "files": []}
donors = {}
for cls, gen in classes.items():
    d = os.path.join(out, cls); os.makedirs(d, exist_ok=True)
    donors[cls] = gen(60000)
    for i in range(150):
        size = rng.choice([1, 300, 4096, 20000, 80000, 200000, 800000] + ([4_000_000] if i % 50 == 0 else []))
        if rng.random() < dup_inj and size >= 20000:
            body = donors[cls][:size] + b"-v%d" % i   # near-copy of the donor
        else:
            body = gen(size)[:max(size,1)]
        p = os.path.join(d, "f%03d.bin" % i)
        open(p, "wb").write(body)
        manifest["files"].append({"path": f"{cls}/f{i:03d}.bin", "size": len(body),
                                  "sha256": hashlib.sha256(body).hexdigest()})
json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=1)
print(f"7class: {len(manifest['files'])} files")
PY
