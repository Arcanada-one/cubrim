"""Bounded holdout benchmark: Cubrim vs gzip-9 vs zstd-19.

Validate the frozen manifest before running any codec. Verify every restoration
byte-for-byte. Publish a complete report only: missing tools, changed inputs,
failed commands or timeouts are errors, never zero-byte measurements.

Usage: python3 code/bench/run_holdout_bench.py --report-id holdout-<revision>
See documentation/how-to/holdout-benchmark.md for limits and report semantics.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent
HOLDOUT_DIR = _PROJECT / "documentation" / "ephemeral" / "research" / "holdout"
MANIFEST = HOLDOUT_DIR / "manifest.json"
RESEARCH_DIR = _PROJECT / "documentation" / "ephemeral" / "research"
CUBRIM_BIN = _PROJECT / "code" / "cubrim-rs" / "target" / "release" / "cubrim"
SCHEMES = ["bwt-rans", "bwt-geomix"]
CHUNK_BYTES = 1024 * 1024


class BenchmarkError(RuntimeError):
    """The campaign cannot produce a complete, comparable measurement."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    """Streaming byte comparison, independent of cached hashes and filecmp."""
    if not right.is_file() or left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            chunk = a.read(CHUNK_BYTES)
            if chunk != b.read(CHUNK_BYTES):
                return False
            if not chunk:
                return True


def load_manifest() -> tuple[list[dict], str]:
    raw = MANIFEST.read_bytes()
    try:
        entries = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise BenchmarkError(f"invalid manifest: {exc}") from exc
    if not isinstance(entries, list) or not entries:
        raise BenchmarkError("manifest must be a non-empty list")
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BenchmarkError("each manifest entry must be an object")
        name = entry.get("name")
        if (not isinstance(name, str) or not name or name in {".", ".."}
                or "/" in name or "\\" in name or any(ord(c) < 32 for c in name)):
            raise BenchmarkError("manifest names must be single file names")
        if name in names:
            raise BenchmarkError(f"duplicate manifest name: {name}")
        names.add(name)
        size = entry.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise BenchmarkError(f"{name}: size_bytes must be a positive integer")
        if not isinstance(entry.get("category"), str) or not entry["category"]:
            raise BenchmarkError(f"{name}: category is required")
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise BenchmarkError(f"{name}: a lowercase sha256 is required")
        source = HOLDOUT_DIR / name
        if source.is_symlink() or not source.is_file():
            raise BenchmarkError(f"{name}: corpus entry must be a regular file")
        verify_input(source, entry)
    return entries, hashlib.sha256(raw).hexdigest()


def verify_input(source: Path, entry: dict) -> None:
    if source.stat().st_size != entry["size_bytes"]:
        raise BenchmarkError(f"{entry['name']}: manifest size mismatch")
    if file_sha256(source) != entry["sha256"]:
        raise BenchmarkError(f"{entry['name']}: manifest sha256 mismatch")


def resolve_tools() -> dict[str, str]:
    if not CUBRIM_BIN.is_file() or not os.access(CUBRIM_BIN, os.X_OK):
        raise BenchmarkError(f"executable Cubrim binary not found: {CUBRIM_BIN}")
    tools = {"cubrim": str(CUBRIM_BIN.resolve())}
    for name in ("gzip", "zstd"):
        binary = shutil.which(name)
        if binary is None:
            raise BenchmarkError(f"required comparator not found: {name}")
        tools[name] = str(Path(binary).resolve())
    return tools


class Runner:
    """Bound child processes; compressed bytes and stderr never accumulate in RAM."""

    def __init__(self, timeout_seconds: float, deadline: float):
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline
        self.commands = []

    def run(self, command: list[str], output: Path | None = None) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BenchmarkError("total campaign time limit reached")
        timeout = min(self.timeout_seconds, remaining)
        self.commands.append(command)
        with tempfile.TemporaryFile() as errors, (
            output.open("wb") if output is not None else tempfile.TemporaryFile()
        ) as stdout:
            started = time.perf_counter()
            try:
                process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=errors,
                    start_new_session=(os.name == "posix"),
                )
            except OSError as exc:
                raise BenchmarkError(f"cannot launch {command[0]}: {exc}") from exc
            try:
                process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                # On Unix also stop children that inherited this process group.
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.wait()
                if isinstance(exc, KeyboardInterrupt):
                    raise
                raise BenchmarkError(f"command timed out: {command[0]}") from exc
            elapsed = time.perf_counter() - started
            if process.returncode != 0:
                errors.seek(0, os.SEEK_END)
                errors.seek(max(0, errors.tell() - 4096))
                detail = errors.read().decode("utf-8", errors="replace").strip()
                raise BenchmarkError(
                    f"command failed ({process.returncode}): {command[0]}: {detail}"
                )
        return elapsed


def measure(src: Path, key: str, binary: str, runner: Runner) -> dict:
    with tempfile.TemporaryDirectory(prefix="cubrim-holdout-") as directory:
        packed = Path(directory) / "output.bin"
        decoded = Path(directory) / "decoded.bin"
        if key.startswith("cubrim_"):
            encode = [binary, "compress", str(src), str(packed),
                      "--value-scheme", key.removeprefix("cubrim_")]
            decode = [binary, "decompress", str(packed), str(decoded)]
            encode_seconds = runner.run(encode)
        else:
            level = "-9" if key == "gzip" else "-19"
            encode = [binary, level, "-c", "--", str(src)]
            decode = [binary, "-d", "-c", "--", str(packed)]
            encode_seconds = runner.run(encode, packed)
        if not packed.is_file() or packed.stat().st_size == 0:
            raise BenchmarkError(f"{key}: no compressed output for {src.name}")
        decode_seconds = runner.run(decode, None if key.startswith("cubrim_") else decoded)
        if not files_equal(src, decoded):
            raise BenchmarkError(f"{key}: round-trip mismatch for {src.name}")
        return {
            "bytes": packed.stat().st_size,
            "compression_seconds": encode_seconds,
            "decompression_seconds": decode_seconds,
            "round_trip": "PASS",
        }


def gather_env(tools: dict[str, str], manifest_sha: str) -> dict:
    def info(command: list[str], required: bool = False) -> str:
        try:
            result = subprocess.run(
                command, cwd=_PROJECT, capture_output=True, text=True, timeout=5,
                check=True, stdin=subprocess.DEVNULL,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            if required:
                raise BenchmarkError(f"cannot record repository provenance: {exc}") from exc
            return "unavailable"

    code_sha = info(["git", "rev-parse", "HEAD"], required=True)
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise BenchmarkError("repository HEAD must be a full commit SHA")
    return {
        "host": platform.node(), "os": platform.platform(),
        "python": sys.version.split()[0], "rustc": info(["rustc", "--version"]),
        "gzip": info([tools["gzip"], "--version"]),
        "zstd": info([tools["zstd"], "--version"]),
        "code_sha": code_sha,
        "working_tree_dirty": bool(info(["git", "status", "--porcelain"], required=True)),
        "manifest_sha256": manifest_sha,
        "runner_sha256": file_sha256(Path(__file__)),
        "binaries": {name: {"path": path, "sha256": file_sha256(Path(path)),
                              "size_bytes": Path(path).stat().st_size}
                     for name, path in tools.items()},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def publish_report(report: Path, payload: str) -> None:
    """Publish a whole file atomically, without replacing any previous run."""
    report.parent.mkdir(parents=True, exist_ok=True)
    staging = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=report.parent, prefix=".holdout-",
            suffix=".tmp", delete=False,
        ) as target:
            staging = Path(target.name)
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        # Same-directory hard link is atomic and refuses an existing destination.
        # Unlike os.replace it cannot erase a concurrent run's report.
        os.link(staging, report)
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("time limit must be finite and positive")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-id", default="h-robust")
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=120.0)
    parser.add_argument("--total-timeout-seconds", type=positive_seconds, default=600.0)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", args.report_id):
        parser.error("report-id must be 1–96 filename characters, starting with a letter or digit")
    report = RESEARCH_DIR / f"{args.report_id}-bench.json"
    started = time.monotonic()
    deadline = started + args.total_timeout_seconds
    try:
        if report.exists():
            raise BenchmarkError(f"report already exists; choose a new --report-id: {report}")
        entries, manifest_sha = load_manifest()
        tools = resolve_tools()
        env = gather_env(tools, manifest_sha)
        runner = Runner(args.timeout_seconds, deadline)
        keys = [f"cubrim_{scheme}" for scheme in SCHEMES] + ["gzip", "zstd"]
        totals = {key: 0 for key in keys}
        results = []
        for entry in entries:
            # Preserve the original basename/mtime used by gzip, but run every
            # codec against the same verified private copy, not a moving corpus.
            with tempfile.TemporaryDirectory(prefix="cubrim-input-") as directory:
                src = Path(directory) / entry["name"]
                shutil.copy2(HOLDOUT_DIR / entry["name"], src)
                verify_input(src, entry)
                row = {field: entry[field] for field in ("name", "category", "size_bytes", "sha256")}
                row["timings"] = {}
                for key in keys:
                    binary = tools["cubrim" if key.startswith("cubrim_") else key]
                    measured = measure(src, key, binary, runner)
                    verify_input(src, entry)
                    row[f"{key}_bytes"] = measured["bytes"]
                    row[f"{key}_ratio"] = round(measured["bytes"] / entry["size_bytes"], 6)
                    row["timings"][key] = measured
                    totals[key] += measured["bytes"]
                row["round_trip"] = "PASS"
                results.append(row)
                print(f"{entry['name']}: round-trip PASS (all codecs)")
        # Refuse to attribute a campaign to a binary replaced while it ran.
        for item in env["binaries"].values():
            if file_sha256(Path(item["path"])) != item["sha256"]:
                raise BenchmarkError("codec binary changed during campaign")
        if time.monotonic() > deadline:
            raise BenchmarkError("total campaign time limit reached")
        input_bytes = sum(entry["size_bytes"] for entry in entries)
        out = {
            "schema_version": 2, "status": "complete", "report_id": args.report_id,
            "corpus": "frozen holdout; inputs validated against manifest",
            "aggregate_metric": "sum(compressed_bytes)/sum(input_bytes)",
            "environment": env, "round_trip_all": "PASS",
            "limits": {"command_seconds": args.timeout_seconds, "campaign_seconds": args.total_timeout_seconds},
            "totals": {"input_bytes": input_bytes, **{f"{key}_bytes": value for key, value in totals.items()}},
            "aggregate": {key: round(value / input_bytes, 6) for key, value in totals.items()},
            "results": results, "commands": runner.commands,
        }
        payload = json.dumps(out, indent=2, allow_nan=False) + "\n"
        publish_report(report, payload)
        print(f"Complete report: {report}")
        return 0
    except (BenchmarkError, OSError) as exc:
        print(f"Benchmark aborted; no complete report written: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
