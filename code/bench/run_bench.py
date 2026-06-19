"""
Benchmark harness for the Cubrim archiver.

For each corpus input:
  1. Runs cubrim-rs encode/decode (via library or CLI binary)
  2. Asserts byte-exact round-trip (sha256)
  3. Determines mode (cube vs raw-store) from header
  4. Runs zstd -19 and brotli -q 11
  5. Computes compressed/input size ratios

Writes:
  docs/ephemeral/research/{REPORT_ID}-bench.json  (machine-readable)
  docs/ephemeral/research/{REPORT_ID}-report.md   (human-readable, private)

Usage:
  python code/bench/run_bench.py [--config-label LABEL] [--report-id REPORT_ID]
  python code/bench/run_bench.py --config-label t1_v1_default --report-id my-report
  python code/bench/run_bench.py --config-label t2_packed_nibble --gap-scheme packed_nibble --report-id my-report

The harness reads the corpus from docs/ephemeral/research/corpus/manifest.json.
Run generate_corpus.py first to produce the corpus data.

This script is designed to run on the measurement host (arcana-dev or Mac-local).
The cubrim binary must be built with: cargo build --release
The binary is expected at: code/cubrim-rs/target/release/cubrim

Environment requirements:
  - cargo (to build the binary)
  - zstd (for reference runs)
  - brotli (for reference runs)
  - python3 + numpy (for corpus generation import)
"""

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Allow import of cubrim_proto regardless of cwd
_HERE = Path(__file__).resolve().parent
_CODE = _HERE.parent  # code/
_PROJECT = _CODE.parent  # Projects/Cubrim/
sys.path.insert(0, str(_CODE))

from cubrim_proto.header import parse_header

# Paths
CORPUS_MANIFEST = _PROJECT / "docs" / "ephemeral" / "research" / "corpus" / "manifest.json"
RESEARCH_DIR = _PROJECT / "docs" / "ephemeral" / "research"
CUBRIM_BIN = _CODE / "cubrim-rs" / "target" / "release" / "cubrim"

# Header mode constants (mirror from Rust)
MODE_CUBE = 0
MODE_RAW = 1
HEADER_OVERHEAD_BOUND = 320


def build_cubrim() -> None:
    """Build cubrim-rs in release mode."""
    print("Building cubrim-rs release binary...")
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=str(_CODE / "cubrim-rs"),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("STDERR:", result.stderr[-2000:])
        raise RuntimeError(f"cargo build --release failed: {result.returncode}")
    print(f"Binary: {CUBRIM_BIN}")


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cubrim(input_path: Path) -> tuple[bytes, str]:
    """
    Compress input_path with cubrim, return (compressed_bytes, mode_str).
    Reads the mode from the compressed blob header.
    Raises RuntimeError on failure.
    """
    with tempfile.NamedTemporaryFile(suffix=".cubrim", delete=False) as tmp:
        out_path = tmp.name

    try:
        result = subprocess.run(
            [str(CUBRIM_BIN), "compress", str(input_path), out_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"cubrim compress failed: {result.stderr}")

        compressed = Path(out_path).read_bytes()
        # Parse header to determine mode
        hdr, _ = parse_header(compressed)
        mode_str = "cube" if hdr["mode"] == MODE_CUBE else "raw"
        return compressed, mode_str
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def run_cubrim_roundtrip(
    input_data: bytes,
    input_path: Path,
    raw_store_bound: int | None = None,
    b: int | None = None,
    n: int | None = None,
    gap_scheme: str | None = None,
    value_scheme: str | None = None,
) -> tuple[bytes, bool, str]:
    """
    Compress + decompress input; assert byte-exact round-trip.
    Returns (compressed_bytes, round_trip_ok: bool, mode_str).
    Passes axis-sweep flags (--b, --n, --gap-scheme, --value-scheme) to the compress CLI.
    """
    with tempfile.NamedTemporaryFile(suffix=".cubrim", delete=False) as tmp_out, \
         tempfile.NamedTemporaryFile(suffix=".dec", delete=False) as tmp_dec:
        out_path = tmp_out.name
        dec_path = tmp_dec.name

    try:
        # Compress
        compress_cmd = [str(CUBRIM_BIN), "compress", str(input_path), out_path]
        if raw_store_bound is not None:
            compress_cmd += ["--raw-store-bound", str(raw_store_bound)]
        if b is not None:
            compress_cmd += ["--b", str(b)]
        if n is not None:
            compress_cmd += ["--n", str(n)]
        if gap_scheme is not None:
            compress_cmd += ["--gap-scheme", gap_scheme]
        if value_scheme is not None:
            compress_cmd += ["--value-scheme", value_scheme]
        result = subprocess.run(
            compress_cmd,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"cubrim compress failed: {result.stderr}")

        compressed = Path(out_path).read_bytes()

        # Parse mode from header
        hdr, _ = parse_header(compressed)
        mode_str = "cube" if hdr["mode"] == MODE_CUBE else "raw"

        # Decompress
        result2 = subprocess.run(
            [str(CUBRIM_BIN), "decompress", out_path, dec_path],
            capture_output=True, text=True,
        )
        if result2.returncode != 0:
            raise RuntimeError(f"cubrim decompress failed: {result2.stderr}")

        recovered = Path(dec_path).read_bytes()

        # Byte-exact round-trip assertion
        ok = recovered == input_data
        if not ok:
            print(f"  ROUND-TRIP FAIL: sha256_in={sha256_of(input_data)[:12]} sha256_out={sha256_of(recovered)[:12]}")

        return compressed, ok, mode_str
    finally:
        for p in (out_path, dec_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def run_zstd(input_path: Path) -> int:
    """Run zstd -19 on input, return compressed size."""
    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as tmp:
        out_path = tmp.name
    try:
        result = subprocess.run(
            ["zstd", "-19", "-f", "-q", str(input_path), "-o", out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"zstd failed: {result.stderr.decode()}")
        return Path(out_path).stat().st_size
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def run_brotli(input_path: Path) -> int:
    """Run brotli -q 11 on input, return compressed size."""
    with tempfile.NamedTemporaryFile(suffix=".br", delete=False) as tmp:
        out_path = tmp.name
    try:
        result = subprocess.run(
            ["brotli", "-q", "11", "-f", str(input_path), "-o", out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"brotli failed: {result.stderr.decode()}")
        return Path(out_path).stat().st_size
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def run_gzip(input_path: Path) -> int:
    """Run gzip -9 on input, return compressed size (excluding gzip header overhead)."""
    result = subprocess.run(
        f"gzip -9 -c {shlex.quote(str(input_path))} | wc -c",
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gzip -9 failed: {result.stderr}")
    return int(result.stdout.strip())


def gather_env() -> dict:
    """Collect environment info for reproducibility."""
    def run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return r.stdout.strip() if r.returncode == 0 else "unavailable"

    # Capture git HEAD SHA for reproducibility (CLAUDE.md: bench results must carry code_sha)
    code_sha = run(f"git -C {shlex.quote(str(_PROJECT))} rev-parse HEAD")

    return {
        "host": platform.node(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "rustc": run("rustc --version"),
        "cargo": run("cargo --version"),
        "zstd": run("zstd --version | head -1"),
        "brotli": run("brotli --version 2>&1 | head -1"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_sha": code_sha,
    }


def benchmark(
    config_label: str = "t1_v1_default",
    raw_store_bound: int | None = None,
    b: int | None = None,
    n: int | None = None,
    gap_scheme: str | None = None,
    value_scheme: str | None = None,
) -> dict:
    """Run the full benchmark for a given config label. Returns results dict."""
    manifest = json.loads(CORPUS_MANIFEST.read_text())
    env = gather_env()
    print(f"\nEnvironment:")
    for k, v in env.items():
        print(f"  {k}: {v}")

    results = []
    all_rt_ok = True

    print(f"\nBenchmark [{config_label}]:")
    print(f"{'Name':20s}  {'Size':>7s}  {'Cubrim':>7s}  {'CRatio':>6s}  {'Mode':5s}  {'gzip-9':>7s}  {'gRatio':>6s}  {'zstd':>7s}  {'zRatio':>6s}  {'brotli':>7s}  {'bRatio':>6s}  {'RT':4s}")
    print("-" * 115)

    for entry in manifest:
        name = entry["name"]
        size = entry["size_bytes"]
        corpus_path = Path(entry["path"])

        if not corpus_path.exists():
            print(f"  SKIP {name}: corpus file missing at {corpus_path}")
            continue

        input_data = corpus_path.read_bytes()
        assert len(input_data) == size, f"Corpus file size mismatch for {name}"

        # Cubrim compress + round-trip
        compressed, rt_ok, mode = run_cubrim_roundtrip(
            input_data, corpus_path,
            raw_store_bound=raw_store_bound,
            b=b,
            n=n,
            gap_scheme=gap_scheme,
            value_scheme=value_scheme,
        )
        cubrim_size = len(compressed)
        cubrim_ratio = cubrim_size / size

        if not rt_ok:
            all_rt_ok = False

        # Raw-store overhead check (V-AC-7)
        if mode == "raw":
            overhead = cubrim_size - size
            if overhead > HEADER_OVERHEAD_BOUND:
                print(f"  V-AC-7 FAIL {name}: raw-store overhead {overhead} > {HEADER_OVERHEAD_BOUND}")

        # gzip -9 reference
        gzip_size = run_gzip(corpus_path)
        gzip_ratio = gzip_size / size

        # zstd reference
        zstd_size = run_zstd(corpus_path)
        zstd_ratio = zstd_size / size

        # brotli reference
        brotli_size = run_brotli(corpus_path)
        brotli_ratio = brotli_size / size

        rt_str = "PASS" if rt_ok else "FAIL"
        print(f"{name:20s}  {size:>7d}  {cubrim_size:>7d}  {cubrim_ratio:>6.4f}  {mode:5s}  {gzip_size:>7d}  {gzip_ratio:>6.4f}  {zstd_size:>7d}  {zstd_ratio:>6.4f}  {brotli_size:>7d}  {brotli_ratio:>6.4f}  {rt_str}")

        results.append({
            "name": name,
            "size_bytes": size,
            "rho": entry["rho"],
            "cubrim_bytes": cubrim_size,
            "cubrim_ratio": round(cubrim_ratio, 6),
            "cubrim_mode": mode,
            "gzip_bytes": gzip_size,
            "gzip_ratio": round(gzip_ratio, 6),
            "zstd_bytes": zstd_size,
            "zstd_ratio": round(zstd_ratio, 6),
            "brotli_bytes": brotli_size,
            "brotli_ratio": round(brotli_ratio, 6),
            "round_trip": rt_str,
            "sha256_input": sha256_of(input_data),
        })

    print("-" * 100)
    round_trip_all = "PASS" if all_rt_ok else "FAIL"
    print(f"Round-trip (all inputs): {round_trip_all}")

    return {
        "config_label": config_label,
        "config_params": {
            "raw_store_bound": raw_store_bound if raw_store_bound is not None else 320,
            "b": b if b is not None else 256,
            "n_override": n,
            "gap_scheme": gap_scheme if gap_scheme is not None else "rle",
            "value_scheme": value_scheme if value_scheme is not None else "bitpack-fixed",
            "use_square_limit": True,
        },
        "timestamp": env["timestamp"],
        "environment": env,
        "round_trip_all": round_trip_all,
        "results": results,
    }


def load_existing_json(report_id: str = "bench") -> list[dict]:
    json_path = RESEARCH_DIR / f"{report_id}-bench.json"
    if json_path.exists():
        return json.loads(json_path.read_text())
    return []


def save_results(runs: list[dict], report_id: str = "bench") -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESEARCH_DIR / f"{report_id}-bench.json"
    json_path.write_text(json.dumps(runs, indent=2))
    print(f"\nJSON written: {json_path}")


def write_report(runs: list[dict], report_id: str = "bench") -> None:
    """Write human-readable markdown report with >=2 time-points."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESEARCH_DIR / f"{report_id}-report.md"

    lines = [
        f"# {report_id} Compression Report",
        "",
        "> PRIVATE — internal research artefact. Lives only in docs/ephemeral/research/.",
        "> Algorithm mechanism is strictly secret — this file must not reach public surfaces.",
        "",
        "## Environment",
        "",
    ]

    # Use environment from first run
    if runs:
        env = runs[0]["environment"]
        for k, v in env.items():
            lines.append(f"- **{k}:** {v}")
    lines.append("")

    lines.append("## Time-Series Results")
    lines.append("")

    for run in runs:
        label = run["config_label"]
        ts = run["timestamp"]
        rt_all = run["round_trip_all"]
        cfg = run.get("config_params", {})
        n_str = str(cfg.get("n_override")) if cfg.get("n_override") is not None else "minimal"
        lines.append(f"### {label} — {ts}")
        lines.append(f"")
        lines.append(
            f"Config: raw_store_bound={cfg.get('raw_store_bound', 320)}, "
            f"b={cfg.get('b', 256)}, N={n_str}, "
            f"gap_scheme={cfg.get('gap_scheme', 'rle')}, "
            f"value_scheme={cfg.get('value_scheme', 'bitpack-fixed')}, "
            f"use_square_limit={cfg.get('use_square_limit', True)}"
        )
        lines.append(f"")
        lines.append(f"Round-trip (all inputs): **{rt_all}**")
        lines.append(f"")
        lines.append(f"| Input | Size | Cubrim | CRatio | Mode | gzip-9 | gRatio | zstd | zRatio | brotli | bRatio | Round-trip |")
        lines.append(f"|-------|------|--------|--------|------|--------|--------|------|--------|--------|--------|------------|")
        for r in run["results"]:
            gzip_bytes = r.get("gzip_bytes", "n/a")
            gzip_ratio = f"{r['gzip_ratio']:.4f}" if "gzip_ratio" in r else "n/a"
            lines.append(
                f"| {r['name']} | {r['size_bytes']} | {r['cubrim_bytes']} | {r['cubrim_ratio']:.4f} "
                f"| {r['cubrim_mode']} | {gzip_bytes} | {gzip_ratio} "
                f"| {r['zstd_bytes']} | {r['zstd_ratio']:.4f} "
                f"| {r['brotli_bytes']} | {r['brotli_ratio']:.4f} | {r['round_trip']} |"
            )
        lines.append("")

    if len(runs) >= 2:
        lines.append("## Improvement Summary (T1 → T2)")
        lines.append("")
        t1 = {r["name"]: r for r in runs[0]["results"]}
        for run in runs[1:]:
            label = run["config_label"]
            lines.append(f"### {runs[0]['config_label']} → {label}")
            lines.append(f"")
            lines.append(f"| Input | T1 CRatio | T2 CRatio | Delta |")
            lines.append(f"|-------|-----------|-----------|-------|")
            for r in run["results"]:
                name = r["name"]
                if name in t1:
                    t1r = t1[name]["cubrim_ratio"]
                    t2r = r["cubrim_ratio"]
                    delta = t2r - t1r
                    sign = "+" if delta > 0 else ""
                    lines.append(f"| {name} | {t1r:.4f} | {t2r:.4f} | {sign}{delta:.4f} |")
            lines.append("")
        lines.append("> Negative delta = smaller output = better compression.")
        lines.append("")

    lines.append("## Corpus Manifest (Generator Parameters)")
    lines.append("")
    manifest = json.loads(CORPUS_MANIFEST.read_text())
    lines.append("| Name | Size | Seed | rho | SHA256 (first 16) |")
    lines.append("|------|------|------|-----|-------------------|")
    for e in manifest:
        lines.append(f"| {e['name']} | {e['size_bytes']} | {e['seed']} | {e['rho']:.4f} | {e['sha256'][:16]} |")
    lines.append("")

    report_path.write_text("\n".join(lines))
    print(f"Report written: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Cubrim benchmark harness")
    parser.add_argument("--config-label", default="t1_v1_default",
                        help="Label for this benchmark run (e.g. t1_v1_default, t2_tuned)")
    parser.add_argument("--skip-build", action="store_true",
                        help="Skip cargo build (use existing binary)")
    parser.add_argument("--raw-store-bound", type=int, default=None,
                        help="Override raw_store_bound for this run (default: 320 = v1_default)")
    parser.add_argument("--b", type=int, default=None,
                        help="Edge bound B (default: 256 = v1_default)")
    parser.add_argument("--n", type=int, default=None,
                        help="N dimensions override (default: minimal N)")
    parser.add_argument("--gap-scheme", default=None, choices=["rle", "packed_nibble"],
                        help="Gap encoding scheme: rle (default) or packed_nibble")
    parser.add_argument("--value-scheme", default=None,
                        choices=["bitpack-fixed", "rle-codes", "entropy", "entropy-context",
                                 "bwt-entropy-context", "auto"],
                        help="Value encoding scheme: bitpack-fixed (default), rle-codes, entropy, entropy-context, bwt-entropy-context, or auto (picks best per input)")
    parser.add_argument("--report-id", default="bench",
                        help="Report file prefix (e.g. bench, v1, axis-sweep; used in output filenames)")
    args = parser.parse_args()

    if not args.skip_build:
        build_cubrim()

    if not CUBRIM_BIN.exists():
        raise RuntimeError(f"cubrim binary not found: {CUBRIM_BIN}")

    run_result = benchmark(
        args.config_label,
        raw_store_bound=args.raw_store_bound,
        b=args.b,
        n=args.n,
        gap_scheme=args.gap_scheme,
        value_scheme=args.value_scheme,
    )

    # Load existing runs and append
    existing = load_existing_json(args.report_id)
    # Replace existing run with same label, or append
    existing = [r for r in existing if r["config_label"] != args.config_label]
    existing.append(run_result)

    save_results(existing, args.report_id)
    write_report(existing, args.report_id)

    if run_result["round_trip_all"] != "PASS":
        print("\nFATAL: Round-trip failed for one or more inputs.")
        sys.exit(1)

    print(f"\nBenchmark complete. Round-trip: PASS")


if __name__ == "__main__":
    main()
