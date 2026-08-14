#!/usr/bin/env python3
"""Inner codec executor for a network-isolated transient user unit."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path


CODEC_ENV = {
    "LC_ALL": "C",
    "LANG": "C",
    "PATH": "/usr/bin:/bin",
}
MANDATORY_NETWORK_SYSCALLS = (
    b"socket",
    b"socketpair",
    b"connect",
    b"bind",
    b"listen",
    b"accept",
    b"accept4",
    b"sendto",
    b"sendmsg",
    b"recvfrom",
    b"recvmsg",
    b"shutdown",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--time-report", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    parser.add_argument("--measure-first-output", action="store_true")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.argv[:1] != ["--"] or len(args.argv) < 2:
        parser.error("an exact codec argv is required after --")
    args.argv = args.argv[1:]
    if args.max_output_bytes <= 0:
        parser.error("max output bytes must be positive")
    return args


def _limit_files(max_bytes: int) -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_bytes, max_bytes))


def _install_network_seccomp() -> None:
    library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    allow = 0x7FFF0000
    deny = 0x00050000 | errno.EPERM
    context = library.seccomp_init(allow)
    if not context:
        raise OSError("cannot initialize seccomp network policy")
    try:
        for syscall in MANDATORY_NETWORK_SYSCALLS:
            number = library.seccomp_syscall_resolve_name(syscall)
            if number < 0:
                raise OSError(
                    "cannot resolve mandatory network syscall "
                    f"{syscall.decode('ascii')}"
                )
            if library.seccomp_rule_add(context, deny, number, 0) != 0:
                raise OSError(f"cannot deny network syscall {syscall.decode('ascii')}")
        if library.seccomp_load(context) != 0:
            raise OSError("cannot load seccomp network policy")
    finally:
        library.seccomp_release(context)


def _sandbox_limits(max_bytes: int) -> None:
    _limit_files(max_bytes)
    _install_network_seccomp()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_status(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    args = _parse_args()
    for path in (args.output, args.status, args.time_report, args.stderr):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as output, args.stderr.open("wb") as stderr:
        started_ns = time.monotonic_ns()
        command = (
            "/usr/bin/time",
            "--verbose",
            "--output",
            str(args.time_report),
            "--",
            *args.argv,
        )
        first_output_duration_ns = None
        if args.measure_first_output:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=stderr,
                env=CODEC_ENV,
                preexec_fn=lambda: _sandbox_limits(args.max_output_bytes),
            )
            output_bytes = 0
            assert process.stdout is not None
            while chunk := process.stdout.read(64 * 1024):
                if first_output_duration_ns is None:
                    first_output_duration_ns = time.monotonic_ns() - started_ns
                output_bytes += len(chunk)
                if output_bytes > args.max_output_bytes:
                    process.kill()
                    process.wait()
                    raise RuntimeError("codec output exceeded configured maximum")
                output.write(chunk)
            process.stdout.close()
            returncode = process.wait()
        else:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=stderr,
                check=False,
                env=CODEC_ENV,
                preexec_fn=lambda: _sandbox_limits(args.max_output_bytes),
            )
            returncode = completed.returncode
        duration_ns = time.monotonic_ns() - started_ns
    output_sha256 = _sha256(args.output)
    _atomic_status(
        args.status,
        {
            "duration_ns": duration_ns,
            "first_output_duration_ns": first_output_duration_ns,
            "output_sha256": output_sha256,
            "returncode": returncode,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
