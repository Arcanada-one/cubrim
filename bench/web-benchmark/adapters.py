"""Exact argv codec adapters and GNU-time subprocess measurement."""

from __future__ import annotations

import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from capabilities import PHASE_A_CODECS, require_phase_a_codec
from model import CODE_SHA_RE, hash_file


@dataclass(frozen=True)
class ToolIdentity:
    name: str
    version: str
    binary_path: str
    binary_sha256: str
    codec_code_sha: str
    flags: tuple[str, ...]
    source_reference: str = "test-fixture"
    package_version: str = "test-fixture"


@dataclass(frozen=True)
class ReleasePin:
    cli_version: str
    package_source: str
    package_version: str
    source_commit: str
    source_reference: str


RELEASE_PINS = {
    "gzip": ReleasePin(
        cli_version="gzip 1.12",
        package_source="gzip",
        package_version="1.12-1ubuntu3.2",
        source_commit="80006351d3bb5d9099b74c41fefd6649424a9a28",
        source_reference=(
            "https://git.savannah.gnu.org/cgit/gzip.git/commit/"
            "?id=80006351d3bb5d9099b74c41fefd6649424a9a28"
        ),
    ),
    "brotli": ReleasePin(
        cli_version="brotli 1.1.0",
        package_source="brotli",
        package_version="1.1.0-2build2",
        source_commit="ed738e842d2fbdf2d6459e39267a633c4a9b2f5d",
        source_reference=(
            "https://github.com/google/brotli/commit/"
            "ed738e842d2fbdf2d6459e39267a633c4a9b2f5d"
        ),
    ),
    "zstd": ReleasePin(
        cli_version="*** Zstandard CLI (64-bit) v1.5.5, by Yann Collet ***",
        package_source="libzstd",
        package_version="1.5.5+dfsg2-2build1.1",
        source_commit="63779c798237346c2b245c546c40b72a5a5913fe",
        source_reference=(
            "https://github.com/facebook/zstd/commit/"
            "63779c798237346c2b245c546c40b72a5a5913fe"
        ),
    ),
}


@dataclass(frozen=True)
class ProcessMeasurement:
    duration_ns: int
    peak_rss_bytes: int
    output_sha256: str


@dataclass(frozen=True)
class CodecAdapter:
    name: str
    flags: tuple[str, ...]
    capabilities: dict[str, bool]
    _compress: Callable[[Path], tuple[str, ...]]
    _decompress: Callable[[Path], tuple[str, ...]]

    def compress_argv(self, path: Path) -> tuple[str, ...]:
        return self._compress(path)

    def decompress_argv(self, path: Path) -> tuple[str, ...]:
        return self._decompress(path)

    def identity(self) -> ToolIdentity:
        binary = shutil.which(self.name)
        if binary is None:
            raise FileNotFoundError(f"required Phase A tool is unavailable: {self.name}")
        resolved = Path(binary).resolve(strict=True)
        binary_sha256 = hash_file(resolved)
        version = _tool_version(self.name, resolved)
        pin = RELEASE_PINS[self.name]
        if version != pin.cli_version:
            raise ValueError(
                f"{self.name} version mismatch: expected {pin.cli_version!r}, got {version!r}"
            )
        package_source, package_version = _package_provenance(self.name)
        if (package_source, package_version) != (
            pin.package_source,
            pin.package_version,
        ):
            raise ValueError(
                f"{self.name} package mismatch: expected "
                f"{pin.package_source} {pin.package_version}, got "
                f"{package_source} {package_version}"
            )
        if not CODE_SHA_RE.fullmatch(pin.source_commit):
            raise ValueError(f"{self.name} release pin has an invalid source commit")
        return ToolIdentity(
            name=self.name,
            version=version,
            binary_path=str(resolved),
            binary_sha256=binary_sha256,
            codec_code_sha=pin.source_commit,
            flags=self.flags,
            source_reference=pin.source_reference,
            package_version=package_version,
        )


def _gzip() -> CodecAdapter:
    return CodecAdapter(
        "gzip",
        ("-9", "-c"),
        {"whole_buffer_decode": True, "incremental_decode": False},
        lambda path: ("gzip", "-9", "-c", str(path)),
        lambda path: ("gzip", "-d", "-c", str(path)),
    )


def _brotli() -> CodecAdapter:
    return CodecAdapter(
        "brotli",
        ("--quality=11", "--stdout"),
        {"whole_buffer_decode": True, "incremental_decode": False},
        lambda path: ("brotli", "--quality=11", "--stdout", str(path)),
        lambda path: ("brotli", "--decompress", "--stdout", str(path)),
    )


def _zstd() -> CodecAdapter:
    return CodecAdapter(
        "zstd",
        ("-19", "--quiet", "--stdout"),
        {"whole_buffer_decode": True, "incremental_decode": False},
        lambda path: ("zstd", "-19", "--quiet", "--stdout", str(path)),
        lambda path: ("zstd", "--decompress", "--quiet", "--stdout", str(path)),
    )


def adapter_for(name: str) -> CodecAdapter:
    require_phase_a_codec(name)
    return {"gzip": _gzip, "brotli": _brotli, "zstd": _zstd}[name]()


def phase_a_adapters() -> tuple[CodecAdapter, ...]:
    return tuple(adapter_for(name) for name in PHASE_A_CODECS)


class SubprocessExecutor:
    def __init__(self, timeout_seconds: float, max_output_bytes: int = 64 * 1024 * 1024):
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def compress(self, adapter: CodecAdapter, source: Path, target: Path) -> ProcessMeasurement:
        return self._run(adapter.compress_argv(source), target)

    def decompress(self, adapter: CodecAdapter, source: Path, target: Path) -> ProcessMeasurement:
        return self._run(adapter.decompress_argv(source), target)

    def _run(self, argv: tuple[str, ...], target: Path) -> ProcessMeasurement:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="gnu-time-",
            suffix=".txt",
            dir=target.parent,
            delete=False,
        ) as time_handle:
            time_path = Path(time_handle.name)
        try:
            started_ns = time.monotonic_ns()
            with target.open("wb") as output:
                completed = subprocess.run(
                    (
                        "/usr/bin/time",
                        "--verbose",
                        "--output",
                        str(time_path),
                        "--",
                        *argv,
                    ),
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=self.timeout_seconds,
                    env={**os.environ, "LC_ALL": "C"},
                    preexec_fn=self._limit_output_file_size,
                )
            finished_ns = time.monotonic_ns()
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"codec exited {completed.returncode}: {stderr}")
            peak_rss_bytes = _parse_peak_rss(time_path.read_text(encoding="utf-8"))
            return ProcessMeasurement(
                duration_ns=finished_ns - started_ns,
                peak_rss_bytes=peak_rss_bytes,
                output_sha256=hash_file(target),
            )
        finally:
            time_path.unlink(missing_ok=True)

    def _limit_output_file_size(self) -> None:
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (self.max_output_bytes, self.max_output_bytes),
        )


def _parse_peak_rss(report: str) -> int:
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", report)
    if match is None:
        raise ValueError("GNU time report omitted peak RSS")
    return int(match.group(1)) * 1024


def _tool_version(name: str, binary: Path) -> str:
    command = (str(binary), "--version")
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=5,
        env={**os.environ, "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{name} --version exited {completed.returncode}")
    first_line = completed.stdout.decode("utf-8", errors="replace").splitlines()
    if not first_line or not first_line[0].strip():
        raise RuntimeError(f"{name} --version returned no version")
    return first_line[0].strip()


def _package_provenance(name: str) -> tuple[str, str]:
    completed = subprocess.run(
        (
            "dpkg-query",
            "-W",
            "-f=${source:Package}\t${Version}",
            name,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"cannot resolve package provenance for {name}")
    parts = completed.stdout.strip().split("\t")
    if len(parts) != 2 or not all(parts):
        raise RuntimeError(f"invalid package provenance for {name}")
    return parts[0], parts[1]
