"""
Holdout robustness benchmark — Cubrim vs gzip-9 vs zstd-19.

Runs the frozen holdout corpus (docs/ephemeral/research/holdout/) through:
  - Cubrim `compress` (competitive rail) with --value-scheme bwt-rans, and also
    --value-scheme bwt-geomix (the current champion scheme), round-trip verified
    byte-exact (sha256) per file;
  - gzip -9 (header bytes included — gzip's real on-disk cost);
  - zstd -19.

Reports per-file ratios and the aggregate metric used by the leaderboard:
    aggregate = sum(compressed_bytes) / sum(input_bytes)

This corpus is DISJOINT from the frozen leaderboard corpus. The point is to test
whether Cubrim's tuned-corpus parity with gzip generalises to unseen real data.

Usage:
  python3 code/bench/run_holdout_bench.py [--report-id h-robust]
"""

import argparse
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent
HOLDOUT_DIR = _PROJECT / "docs" / "ephemeral" / "research" / "holdout"
MANIFEST = HOLDOUT_DIR / "manifest.json"
RESEARCH_DIR = _PROJECT / "docs" / "ephemeral" / "research"
CUBRIM_BIN = _PROJECT / "code" / "cubrim-rs" / "target" / "release" / "cubrim"

SCHEMES = ["bwt-rans", "bwt-geomix"]


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cubrim_roundtrip(src: Path, scheme: str) -> tuple[int, bool]:
    """Compress src with the given value scheme + verify byte-exact round-trip.
    Returns (compressed_bytes, round_trip_ok)."""
    with tempfile.NamedTemporaryFile(suffix=".cub", delete=False) as t1, \
         tempfile.NamedTemporaryFile(suffix=".dec", delete=False) as t2:
        out_path, dec_path = Path(t1.name), Path(t2.name)
    try:
        c = subprocess.run(
            [str(CUBRIM_BIN), "compress", str(src), str(out_path),
             "--value-scheme", scheme],
            capture_output=True, text=True)
        if c.returncode != 0:
            raise RuntimeError(f"compress failed: {c.stderr}")
        compressed = out_path.read_bytes()
        d = subprocess.run(
            [str(CUBRIM_BIN), "decompress", str(out_path), str(dec_path)],
            capture_output=True, text=True)
        if d.returncode != 0:
            raise RuntimeError(f"decompress failed: {d.stderr}")
        ok = dec_path.read_bytes() == src.read_bytes()
        return len(compressed), ok
    finally:
        for p in (out_path, dec_path):
            try:
                p.unlink()
            except OSError:
                pass


def run_gzip(src: Path) -> int:
    r = subprocess.run(f"gzip -9 -c {shlex.quote(str(src))} | wc -c",
                       shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gzip failed: {r.stderr}")
    return int(r.stdout.strip())


def run_zstd(src: Path) -> int:
    if shutil.which("zstd") is None:
        return 0
    r = subprocess.run(f"zstd -19 -c -q {shlex.quote(str(src))} | wc -c",
                       shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        return 0
    return int(r.stdout.strip())


def gather_env() -> dict:
    def run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return r.stdout.strip() if r.returncode == 0 else "unavailable"
    code_sha = run("git rev-parse HEAD")
    dirty = run("git status --porcelain")
    if dirty and dirty != "unavailable":
        code_sha = f"{code_sha}-dirty"
    return {
        "host": platform.node(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "rustc": run("rustc --version"),
        "zstd": run("zstd --version | head -1"),
        "gzip": run("gzip --version | head -1"),
        "code_sha": code_sha,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-id", default="h-robust")
    args = parser.parse_args()

    if not CUBRIM_BIN.exists():
        raise SystemExit(f"cubrim binary not found: {CUBRIM_BIN} (run cargo build --release)")
    manifest = json.loads(MANIFEST.read_text())
    env = gather_env()

    print("Environment:")
    for k, v in env.items():
        print(f"  {k}: {v}")
    print(f"\nHoldout robustness benchmark ({len(manifest)} files)\n")

    results = []
    totals = {"size": 0, "gzip": 0, "zstd": 0}
    cub_totals = {s: 0 for s in SCHEMES}
    all_rt_ok = True

    header = f"{'file':14s} {'cat':18s} {'size':>7s}"
    for s in SCHEMES:
        header += f" {s:>11s} {'r':>6s}"
    header += f" {'gzip':>7s} {'r':>6s} {'zstd':>7s} {'r':>6s}  RT"
    print(header)
    print("-" * len(header))

    for e in manifest:
        src = HOLDOUT_DIR / e["name"]
        size = e["size_bytes"]
        row = {"name": e["name"], "category": e["category"], "size_bytes": size}
        cub_sizes = {}
        rt_file_ok = True
        for s in SCHEMES:
            cb, ok = run_cubrim_roundtrip(src, s)
            cub_sizes[s] = cb
            rt_file_ok = rt_file_ok and ok
            row[f"cubrim_{s}_bytes"] = cb
            row[f"cubrim_{s}_ratio"] = round(cb / size, 6)
            cub_totals[s] += cb
        if not rt_file_ok:
            all_rt_ok = False
        gz = run_gzip(src)
        zs = run_zstd(src)
        row["gzip_bytes"] = gz
        row["gzip_ratio"] = round(gz / size, 6)
        row["zstd_bytes"] = zs
        row["zstd_ratio"] = round(zs / size, 6) if zs else 0
        row["round_trip"] = "PASS" if rt_file_ok else "FAIL"
        results.append(row)
        totals["size"] += size
        totals["gzip"] += gz
        totals["zstd"] += zs

        line = f"{e['name']:14s} {e['category']:18s} {size:>7d}"
        for s in SCHEMES:
            line += f" {cub_sizes[s]:>11d} {cub_sizes[s]/size:>6.4f}"
        line += f" {gz:>7d} {gz/size:>6.4f} {zs:>7d} {(zs/size if zs else 0):>6.4f}  {row['round_trip']}"
        print(line)

    # Aggregates: sum(compressed)/sum(input)
    agg = {s: cub_totals[s] / totals["size"] for s in SCHEMES}
    agg_gzip = totals["gzip"] / totals["size"]
    agg_zstd = totals["zstd"] / totals["size"] if totals["zstd"] else 0
    print("-" * len(header))
    aggline = f"{'AGGREGATE':14s} {'':18s} {totals['size']:>7d}"
    for s in SCHEMES:
        aggline += f" {cub_totals[s]:>11d} {agg[s]:>6.4f}"
    aggline += f" {totals['gzip']:>7d} {agg_gzip:>6.4f} {totals['zstd']:>7d} {agg_zstd:>6.4f}"
    print(aggline)
    print(f"\nRound-trip (all files): {'PASS' if all_rt_ok else 'FAIL'}")

    out = {
        "report_id": args.report_id,
        "corpus": "holdout (diverse real-world; disjoint from leaderboard corpus)",
        "aggregate_metric": "sum(compressed_bytes)/sum(input_bytes)",
        "environment": env,
        "round_trip_all": "PASS" if all_rt_ok else "FAIL",
        "totals": {
            "input_bytes": totals["size"],
            **{f"cubrim_{s}_bytes": cub_totals[s] for s in SCHEMES},
            "gzip_bytes": totals["gzip"],
            "zstd_bytes": totals["zstd"],
        },
        "aggregate": {
            **{f"cubrim_{s}": round(agg[s], 6) for s in SCHEMES},
            "gzip": round(agg_gzip, 6),
            "zstd": round(agg_zstd, 6),
        },
        "results": results,
    }
    json_path = RESEARCH_DIR / f"{args.report_id}-bench.json"
    json_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nJSON written: {json_path}")

    if not all_rt_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
