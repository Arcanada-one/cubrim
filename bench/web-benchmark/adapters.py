"""Exact argv codec adapters and GNU-time subprocess measurement."""

from __future__ import annotations

import errno
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from capabilities import PHASE_A_CODECS, require_phase_a_codec
from model import CODE_SHA_RE, SHA256_RE, hash_file, stable_fingerprint


MINIMAL_ENV = {
    "LC_ALL": "C",
    "LANG": "C",
    "PATH": "/usr/bin:/bin",
}
SYSTEMD_ENV = {
    **MINIMAL_ENV,
    **{
        key: os.environ[key]
        for key in ("DBUS_SESSION_BUS_ADDRESS", "HOME", "LOGNAME", "USER", "XDG_RUNTIME_DIR")
        if key in os.environ
    },
}
INNER_HELPER = Path(__file__).with_name("sandbox_exec.py").resolve()


@dataclass(frozen=True)
class ToolIdentity:
    name: str
    version: str
    binary_path: str
    binary_sha256: str
    flags: tuple[str, ...]
    binary_package: str
    binary_package_version: str
    source_package: str
    source_package_version: str
    upstream_release_sha: str
    upstream_source_reference: str
    codec_build_provenance_sha256: str

    def as_json(self, capabilities: dict[str, bool]) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "binary_path": self.binary_path,
            "binary_sha256": self.binary_sha256,
            "flags": list(self.flags),
            "capabilities": dict(sorted(capabilities.items())),
            "binary_package": self.binary_package,
            "binary_package_version": self.binary_package_version,
            "source_package": self.source_package,
            "source_package_version": self.source_package_version,
            "upstream_release_sha": self.upstream_release_sha,
            "upstream_source_reference": self.upstream_source_reference,
            "codec_build_provenance_sha256": self.codec_build_provenance_sha256,
        }


@dataclass(frozen=True)
class ReleasePin:
    cli_version: str
    binary_package: str
    binary_package_version: str
    source_package: str
    source_package_version: str
    upstream_release_sha: str
    upstream_source_reference: str


RELEASE_PINS = {
    "gzip": ReleasePin(
        cli_version="gzip 1.12",
        binary_package="gzip",
        binary_package_version="1.12-1ubuntu3.2",
        source_package="gzip",
        source_package_version="1.12-1ubuntu3.2",
        upstream_release_sha="80006351d3bb5d9099b74c41fefd6649424a9a28",
        upstream_source_reference=(
            "https://git.savannah.gnu.org/cgit/gzip.git/commit/"
            "?id=80006351d3bb5d9099b74c41fefd6649424a9a28"
        ),
    ),
    "brotli": ReleasePin(
        cli_version="brotli 1.1.0",
        binary_package="brotli",
        binary_package_version="1.1.0-2build2",
        source_package="brotli",
        source_package_version="1.1.0-2build2",
        upstream_release_sha="ed738e842d2fbdf2d6459e39267a633c4a9b2f5d",
        upstream_source_reference=(
            "https://github.com/google/brotli/commit/"
            "ed738e842d2fbdf2d6459e39267a633c4a9b2f5d"
        ),
    ),
    "zstd": ReleasePin(
        cli_version="*** Zstandard CLI (64-bit) v1.5.5, by Yann Collet ***",
        binary_package="zstd",
        binary_package_version="1.5.5+dfsg2-2build1.1",
        source_package="libzstd",
        source_package_version="1.5.5+dfsg2-2build1.1",
        upstream_release_sha="63779c798237346c2b245c546c40b72a5a5913fe",
        upstream_source_reference=(
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
        package = _package_provenance(self.name)
        expected_package = (
            pin.binary_package,
            pin.binary_package_version,
            pin.source_package,
            pin.source_package_version,
        )
        if package != expected_package:
            actual = " ".join(package)
            expected = " ".join(expected_package)
            raise ValueError(
                f"{self.name} package mismatch: expected {expected}, got {actual}"
            )
        if not CODE_SHA_RE.fullmatch(pin.upstream_release_sha):
            raise ValueError(f"{self.name} upstream release pin is invalid")
        identity_without_digest = {
            "name": self.name,
            "version": version,
            "binary_sha256": binary_sha256,
            "flags": list(self.flags),
            "binary_package": package[0],
            "binary_package_version": package[1],
            "source_package": package[2],
            "source_package_version": package[3],
            "upstream_release_sha": pin.upstream_release_sha,
            "upstream_source_reference": pin.upstream_source_reference,
        }
        build_digest = stable_fingerprint(identity_without_digest)
        return ToolIdentity(
            name=self.name,
            version=version,
            binary_path=str(resolved),
            binary_sha256=binary_sha256,
            flags=self.flags,
            binary_package=package[0],
            binary_package_version=package[1],
            source_package=package[2],
            source_package_version=package[3],
            upstream_release_sha=pin.upstream_release_sha,
            upstream_source_reference=pin.upstream_source_reference,
            codec_build_provenance_sha256=build_digest,
        )


def compute_build_provenance_sha256(identity: ToolIdentity) -> str:
    return stable_fingerprint(
        {
            "name": identity.name,
            "version": identity.version,
            "binary_sha256": identity.binary_sha256,
            "flags": list(identity.flags),
            "binary_package": identity.binary_package,
            "binary_package_version": identity.binary_package_version,
            "source_package": identity.source_package,
            "source_package_version": identity.source_package_version,
            "upstream_release_sha": identity.upstream_release_sha,
            "upstream_source_reference": identity.upstream_source_reference,
        }
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

    def compress(
        self,
        adapter: CodecAdapter,
        identity: ToolIdentity,
        source: Path,
        target: Path,
    ) -> ProcessMeasurement:
        return self._run(self.exact_argv(adapter.compress_argv(source), identity), target)

    def decompress(
        self,
        adapter: CodecAdapter,
        identity: ToolIdentity,
        source: Path,
        target: Path,
    ) -> ProcessMeasurement:
        return self._run(self.exact_argv(adapter.decompress_argv(source), identity), target)

    @staticmethod
    def exact_argv(argv: tuple[str, ...], identity: ToolIdentity) -> tuple[str, ...]:
        if not argv or argv[0] != identity.name:
            raise ValueError("codec argv does not match the measured tool identity")
        binary = Path(identity.binary_path).resolve(strict=True)
        if hash_file(binary) != identity.binary_sha256:
            raise ValueError("resolved codec binary changed after provenance capture")
        return (str(binary), *argv[1:])

    def sandbox_command(
        self,
        argv: tuple[str, ...],
        target: Path,
        status_path: Path,
        time_path: Path,
        stderr_path: Path,
    ) -> tuple[str, ...]:
        timeout = f"{self.timeout_seconds:g}s"
        return (
            "systemd-run",
            "--user",
            "--wait",
            "--collect",
            "--quiet",
            "--service-type=exec",
            "--property=PrivateNetwork=yes",
            "--property=KillMode=control-group",
            f"--property=RuntimeMaxSec={timeout}",
            "--property=TimeoutStopSec=2s",
            "--property=NoNewPrivileges=yes",
            "--",
            str(Path(sys.executable).resolve()),
            str(INNER_HELPER),
            "--output",
            str(target),
            "--status",
            str(status_path),
            "--time-report",
            str(time_path),
            "--stderr",
            str(stderr_path),
            "--max-output-bytes",
            str(self.max_output_bytes),
            "--",
            *argv,
        )

    def _run(self, argv: tuple[str, ...], target: Path) -> ProcessMeasurement:
        target.parent.mkdir(parents=True, exist_ok=True)
        time_path = target.parent / f".{target.name}.time"
        status_path = target.parent / f".{target.name}.status.json"
        stderr_path = target.parent / f".{target.name}.stderr"
        try:
            command = self.sandbox_command(
                argv,
                target,
                status_path,
                time_path,
                stderr_path,
            )
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout_seconds + 10,
                env=SYSTEMD_ENV,
            )
            if not status_path.is_file():
                if completed.returncode != 0:
                    raise TimeoutError("sandboxed codec exceeded its runtime or failed closed")
                raise RuntimeError("sandboxed codec omitted its status record")
            status = _load_status(status_path)
            if completed.returncode != 0 or status["returncode"] != 0:
                raise RuntimeError(f"codec exited {status['returncode']}")
            peak_rss_bytes = _parse_peak_rss(time_path.read_text(encoding="utf-8"))
            output_sha256 = hash_file(target, max_bytes=self.max_output_bytes)
            if output_sha256 != status["output_sha256"]:
                raise ValueError("sandbox helper output hash mismatch")
            return ProcessMeasurement(
                duration_ns=status["duration_ns"],
                peak_rss_bytes=peak_rss_bytes,
                output_sha256=output_sha256,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("systemd sandbox did not stop within its outer timeout") from exc
        finally:
            time_path.unlink(missing_ok=True)
            status_path.unlink(missing_ok=True)
            stderr_path.unlink(missing_ok=True)

    @staticmethod
    def verify_network_sandbox() -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
                pass
        except OSError as exc:
            raise PermissionError(
                "host cannot establish the unsandboxed socket baseline"
            ) from exc
        completed = subprocess.run(
            (
                "systemd-run",
                "--user",
                "--wait",
                "--collect",
                "--quiet",
                "--property=PrivateNetwork=yes",
                "--property=KillMode=control-group",
                "--property=RuntimeMaxSec=5s",
                "--property=NoNewPrivileges=yes",
                "--",
                "/usr/bin/true",
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
            env=SYSTEMD_ENV,
        )
        if completed.returncode != 0:
            raise PermissionError("user systemd PrivateNetwork sandbox is unavailable")
        network_probe = (
            "import errno,socket,sys\n"
            "try:\n"
            "    socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
            "except OSError as exc:\n"
            f"    sys.exit(0 if exc.errno == {errno.EPERM} else 8)\n"
            "sys.exit(7)\n"
        )
        with tempfile.TemporaryDirectory(prefix="network-sandbox-probe-") as directory:
            try:
                SubprocessExecutor(
                    timeout_seconds=2,
                    max_output_bytes=4096,
                )._run(
                    (
                        str(Path(sys.executable).resolve()),
                        "-c",
                        network_probe,
                    ),
                    Path(directory) / "output.bin",
                )
            except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                raise PermissionError(
                    "codec network sandbox failed its egress-denial probe"
                ) from exc


def _load_status(path: Path) -> dict[str, int | str]:
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != {"duration_ns", "output_sha256", "returncode"}:
        raise ValueError("sandbox status record has unexpected fields")
    if not isinstance(value["duration_ns"], int) or value["duration_ns"] < 0:
        raise ValueError("sandbox duration is invalid")
    if not isinstance(value["returncode"], int):
        raise ValueError("sandbox return code is invalid")
    if not SHA256_RE.fullmatch(str(value["output_sha256"])):
        raise ValueError("sandbox output hash is invalid")
    return value


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
        env=MINIMAL_ENV,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{name} --version exited {completed.returncode}")
    first_line = completed.stdout.decode("utf-8", errors="replace").splitlines()
    if not first_line or not first_line[0].strip():
        raise RuntimeError(f"{name} --version returned no version")
    return first_line[0].strip()


def _package_provenance(name: str) -> tuple[str, str, str, str]:
    completed = subprocess.run(
        (
            "dpkg-query",
            "-W",
            "-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}",
            name,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5,
        text=True,
        env=MINIMAL_ENV,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"cannot resolve package provenance for {name}")
    parts = completed.stdout.strip().split("\t")
    if len(parts) != 4 or not all(parts):
        raise RuntimeError(f"invalid package provenance for {name}")
    return parts[0], parts[1], parts[2], parts[3]
