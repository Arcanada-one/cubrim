"""Exact argv codec adapters and GNU-time subprocess measurement."""

from __future__ import annotations

import errno
import json
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

from capabilities import (
    CANDIDATE_CODECS,
    PHASE_A_CODECS,
    require_candidate_codec,
    require_phase_a_codec,
)
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
# Same expression as run.REPO_ROOT, defined here rather than imported because
# run.py imports this module.
REPO_ROOT = Path(__file__).resolve().parents[2]
HARDENING_EVIDENCE_ENV = "CUBRIM_WEB_HARDENING_EVIDENCE"


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

    def as_json(self, capabilities: dict[str, object]) -> dict[str, object]:
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
    first_output_duration_ns: int | None = None


@dataclass(frozen=True)
class CodecAdapter:
    name: str
    binary_name: str
    flags: tuple[str, ...]
    capabilities: dict[str, object]
    _compress: Callable[[Path], tuple[str, ...]]
    _decompress: Callable[[Path], tuple[str, ...]]
    # Codecs we build ourselves have no distro package to be pinned against, so
    # they supply their own provenance instead of going through RELEASE_PINS.
    # Defaulted to None so every installed-release adapter is unchanged.
    _identity_factory: Callable[[], ToolIdentity] | None = None

    def compress_argv(self, path: Path) -> tuple[str, ...]:
        return self._compress(path)

    def decompress_argv(self, path: Path) -> tuple[str, ...]:
        return self._decompress(path)

    def identity(self) -> ToolIdentity:
        if self._identity_factory is not None:
            return self._identity_factory()
        binary = shutil.which(self.binary_name)
        if binary is None:
            raise FileNotFoundError(
                f"required Phase A tool is unavailable: {self.binary_name}"
            )
        resolved = Path(binary).resolve(strict=True)
        binary_sha256 = hash_file(resolved)
        version = _tool_version(self.binary_name, resolved)
        pin = RELEASE_PINS[self.binary_name]
        if version != pin.cli_version:
            raise ValueError(
                f"{self.name} version mismatch: expected {pin.cli_version!r}, got {version!r}"
            )
        package = _package_provenance(self.binary_name)
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


_WHOLE_BUFFER = {"whole_buffer_decode": True, "incremental_decode": False}


def _gzip_9() -> CodecAdapter:
    return CodecAdapter(
        "gzip-9",
        "gzip",
        ("-9", "-c"),
        dict(_WHOLE_BUFFER),
        lambda path: ("gzip", "-9", "-c", str(path)),
        lambda path: ("gzip", "-d", "-c", str(path)),
    )


def _brotli_11() -> CodecAdapter:
    return CodecAdapter(
        "brotli-11",
        "brotli",
        ("--quality=11", "--stdout"),
        dict(_WHOLE_BUFFER),
        lambda path: ("brotli", "--quality=11", "--stdout", str(path)),
        lambda path: ("brotli", "--decompress", "--stdout", str(path)),
    )


def _brotli_5() -> CodecAdapter:
    # The dynamic-response preset: what a server can afford per request.
    return CodecAdapter(
        "brotli-5",
        "brotli",
        ("--quality=5", "--stdout"),
        dict(_WHOLE_BUFFER),
        lambda path: ("brotli", "--quality=5", "--stdout", str(path)),
        lambda path: ("brotli", "--decompress", "--stdout", str(path)),
    )


def _zstd_19() -> CodecAdapter:
    return CodecAdapter(
        "zstd-19",
        "zstd",
        ("-19", "--quiet", "--stdout"),
        dict(_WHOLE_BUFFER),
        lambda path: ("zstd", "-19", "--quiet", "--stdout", str(path)),
        lambda path: ("zstd", "--decompress", "--quiet", "--stdout", str(path)),
    )


def _zstd_3() -> CodecAdapter:
    # zstd's own default, and the level most CDNs run on the fly.
    return CodecAdapter(
        "zstd-3",
        "zstd",
        ("-3", "--quiet", "--stdout"),
        dict(_WHOLE_BUFFER),
        lambda path: ("zstd", "-3", "--quiet", "--stdout", str(path)),
        lambda path: ("zstd", "--decompress", "--quiet", "--stdout", str(path)),
    )


def adapter_for(name: str) -> CodecAdapter:
    require_phase_a_codec(name)
    return {
        "gzip-9": _gzip_9,
        "brotli-11": _brotli_11,
        "brotli-5": _brotli_5,
        "zstd-19": _zstd_19,
        "zstd-3": _zstd_3,
    }[name]()


def phase_a_adapters() -> tuple[CodecAdapter, ...]:
    return tuple(adapter_for(name) for name in PHASE_A_CODECS)


# ---------------------------------------------------------------------------
# Candidate channel
#
# The five Phase A codecs are the published comparison. The candidate is our
# own codec and lives in a separate channel on purpose: adding it to
# PHASE_A_CODECS would silently redefine what every existing bundle, fingerprint
# and DB row means. Nothing above this line changes.
# ---------------------------------------------------------------------------

CUBRIM_WEB_CRATE = REPO_ROOT / "code" / "cubrim-web-cli"
CUBRIM_WEB_BUILD = "cargo build --locked --release"


def _cubrim_web_binary() -> Path:
    """Locate the candidate binary: explicit override, PATH, then the build dir."""
    override = os.environ.get("CUBRIM_WEB_BINARY")
    if override:
        return Path(override).resolve(strict=True)
    found = shutil.which("cubrim-web")
    if found:
        return Path(found).resolve(strict=True)
    built = CUBRIM_WEB_CRATE / "target" / "release" / "cubrim-web"
    if built.is_file():
        return built.resolve(strict=True)
    raise FileNotFoundError(
        "cubrim-web is not built: run "
        f"`{CUBRIM_WEB_BUILD}` in {CUBRIM_WEB_CRATE}, or set CUBRIM_WEB_BINARY"
    )


def _crate_version(manifest: Path) -> str:
    """The `version` of the first [package] table in a Cargo manifest."""
    in_package = False
    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            if in_package:
                break
            in_package = stripped == "[package]"
            continue
        if in_package and stripped.startswith("version"):
            _, _, raw = stripped.partition("=")
            return raw.strip().strip('"')
    raise ValueError(f"no [package] version in {manifest}")


def _hardening_evidence_reference() -> str | None:
    raw_path = os.environ.get(HARDENING_EVIDENCE_ENV)
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{HARDENING_EVIDENCE_ENV} must name a regular evidence file")
    if path.stat().st_size > 1 * 1024 * 1024:
        raise ValueError("Cubrim-Web hardening evidence is unexpectedly large")
    return f"CUBR-0075:web-decoder-hostile:{hash_file(path.resolve())[:32]}"


def _verify_hardening_evidence(path: Path, code_sha: str, binary_sha256: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Cubrim-Web hardening evidence must be a regular file")
    if path.stat().st_size > 1 * 1024 * 1024:
        raise ValueError("Cubrim-Web hardening evidence is unexpectedly large")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cubrim-Web hardening evidence is not valid JSON") from exc
    if not isinstance(evidence, dict):
        raise ValueError("Cubrim-Web hardening evidence must be an object")
    if evidence.get("schema_version") != 1 or evidence.get("task_id") != "CUBR-0075":
        raise ValueError("Cubrim-Web hardening evidence schema/task is invalid")
    if evidence.get("phase") != "web_decoder_hostile" or evidence.get("status") != "PASS":
        raise ValueError("Cubrim-Web hardening evidence is not a passing web probe")
    if evidence.get("source_sha") != code_sha or evidence.get("binary_sha256") != binary_sha256:
        raise ValueError("Cubrim-Web hardening evidence does not match the measured source/binary")
    case_count = evidence.get("case_count")
    if (
        evidence.get("valid_roundtrip_exact") is not True
        or not isinstance(case_count, int)
        or isinstance(case_count, bool)
        or case_count <= 0
        or evidence.get("rejected_count") != case_count
        or evidence.get("fault_count") != 0
    ):
        raise ValueError("Cubrim-Web hardening evidence is incomplete")
    runner_sha = evidence.get("runner_sha256")
    if not isinstance(runner_sha, str) or not SHA256_RE.fullmatch(runner_sha):
        raise ValueError("Cubrim-Web hardening evidence runner hash is invalid")
    return f"CUBR-0075:web-decoder-hostile:{hash_file(path.resolve())[:32]}"


def _cubrim_web_identity() -> ToolIdentity:
    """Provenance for a binary we build rather than install.

    An installed release is pinned by distro package plus upstream release SHA,
    which is what lets a third party reconstruct the exact tool. A first-party
    binary has no such package, so the reconstructible triple here is instead:
    the commit, the build command, and the resulting binary hash — all three
    recorded below.

    What this proves and what it does not: `binary_sha256` is the authoritative
    identity of the artefact actually measured, and the clean-tree requirement
    means the recorded commit is fetchable. It does not by itself prove the
    binary was produced by that commit — that is what a rebuild-and-compare
    establishes, and recording the exact build command is what makes such a
    rebuild possible. The version cross-check below is a cheap partial binding:
    a binary built from a different crate version is refused outright.
    """
    from run import _git_code_sha  # local import: run.py imports this module

    binary = _cubrim_web_binary()
    if binary.name != "cubrim-web":
        raise ValueError(f"candidate binary must be named cubrim-web, got {binary.name}")

    code_sha = _git_code_sha(require_clean=True)
    crate_version = _crate_version(CUBRIM_WEB_CRATE / "Cargo.toml")
    cubrim_version = _crate_version(REPO_ROOT / "code" / "cubrim-rs" / "Cargo.toml")

    version = _tool_version("cubrim-web", binary)
    if version != f"cubrim-web {crate_version}":
        raise ValueError(
            f"cubrim-web reports {version!r} but the tree at {code_sha} "
            f"declares {crate_version!r} — the binary is stale, rebuild it"
        )

    binary_sha256 = hash_file(binary)
    evidence_path_raw = os.environ.get(HARDENING_EVIDENCE_ENV)
    hardening_reference = None
    if evidence_path_raw:
        hardening_reference = _verify_hardening_evidence(
            Path(evidence_path_raw), code_sha, binary_sha256
        )
    package = ("cubrim-web-cli", crate_version, "cubrim", cubrim_version)
    source_reference = (
        f"https://github.com/Arcanada-one/cubrim@{code_sha} :: "
        f"{CUBRIM_WEB_BUILD} (cwd code/cubrim-web-cli)"
    )
    identity_without_digest = {
        "name": "cubrim-web",
        "version": version,
        "binary_sha256": binary_sha256,
        "flags": [],
        "binary_package": package[0],
        "binary_package_version": package[1],
        "source_package": package[2],
        "source_package_version": package[3],
        "upstream_release_sha": code_sha,
        "upstream_source_reference": source_reference,
    }
    return ToolIdentity(
        name="cubrim-web",
        version=version,
        binary_path=str(binary),
        binary_sha256=binary_sha256,
        flags=(),
        binary_package=package[0],
        binary_package_version=package[1],
        source_package=package[2],
        source_package_version=package[3],
        upstream_release_sha=code_sha,
        upstream_source_reference=source_reference,
        codec_build_provenance_sha256=stable_fingerprint(identity_without_digest),
    )


def _cubrim_web() -> CodecAdapter:
    hardening_reference = _hardening_evidence_reference()
    capabilities = {
        # Decoding goes through the reference decoder the WASM artefact
        # wraps, and that decoder is genuinely incremental — so
        # first-decoded-byte is measurable here, unlike for any incumbent.
        "whole_buffer_decode": True,
        "incremental_decode": True,
        "web_profile": True,
        "encode": True,
        "decode": True,
        "web_profile_version": "1",
    }
    if hardening_reference is not None:
        capabilities.update(
            {
                "hostile_input_hardened": True,
                "hardening_evidence": hardening_reference,
            }
        )
    return CodecAdapter(
        "cubrim-web",
        "cubrim-web",
        (),
        capabilities,
        lambda path: ("cubrim-web", "encode", str(path)),
        lambda path: (
            "cubrim-web",
            "decode",
            "--stream",
            "--chunk",
            "65536",
            str(path),
        ),
        _identity_factory=_cubrim_web_identity,
    )


def candidate_adapter_for(name: str) -> CodecAdapter:
    require_candidate_codec(name)
    return {"cubrim-web": _cubrim_web}[name]()


def candidate_adapters() -> tuple[CodecAdapter, ...]:
    return tuple(candidate_adapter_for(name) for name in CANDIDATE_CODECS)


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
        return self._run(
            self.exact_argv(adapter.decompress_argv(source), identity),
            target,
            measure_first_output=adapter.capabilities.get("incremental_decode") is True,
        )

    @staticmethod
    def exact_argv(argv: tuple[str, ...], identity: ToolIdentity) -> tuple[str, ...]:
        # The measurement identity is the preset (brotli-5); the program it
        # invokes is the binary (brotli). Compare argv against the executable
        # that provenance was actually captured from.
        binary = Path(identity.binary_path).resolve(strict=True)
        if not argv or argv[0] != binary.name:
            raise ValueError("codec argv does not match the measured tool identity")
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
        *,
        measure_first_output: bool = False,
    ) -> tuple[str, ...]:
        timeout = f"{self.timeout_seconds:g}s"
        command = (
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
        )
        if measure_first_output:
            command += ("--measure-first-output",)
        return command + (
            "--",
            *argv,
        )

    def _run(
        self,
        argv: tuple[str, ...],
        target: Path,
        *,
        measure_first_output: bool = False,
    ) -> ProcessMeasurement:
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
                measure_first_output=measure_first_output,
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
                first_output_duration_ns=status["first_output_duration_ns"],
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
    if set(value) != {
        "duration_ns",
        "first_output_duration_ns",
        "output_sha256",
        "returncode",
    }:
        raise ValueError("sandbox status record has unexpected fields")
    if not isinstance(value["duration_ns"], int) or value["duration_ns"] < 0:
        raise ValueError("sandbox duration is invalid")
    if not isinstance(value["returncode"], int):
        raise ValueError("sandbox return code is invalid")
    first_output = value["first_output_duration_ns"]
    if first_output is not None and (
        not isinstance(first_output, int) or first_output < 0
    ):
        raise ValueError("sandbox first-output duration is invalid")
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
