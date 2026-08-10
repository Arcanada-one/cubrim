#!/usr/bin/env python3
"""Fail-closed runner for the frozen PPMd order/memory oracle grid.

This module contains no aggregate or winner-selection logic.  It produces one
observation for every file/order/memory cell and publishes a result directory
only after every cell has encoded, decoded, and passed both cmp and SHA-256.
Corpus execution is deliberately gated behind the CLI's explicit --execute.

The ignored executable holdout is a generated frozen input, never a runtime
fallback.  Before outcome access, materialize it explicitly with:
``new02_oracle_grid.py --materialize-holdout-exe --holdout-root PATH``.
That action authenticates /bin/cat against the frozen size and SHA-256, writes
PATH/exe.bin durably, and makes it read-only.  ``--execute`` only consumes the
already-materialized file and fails closed when it is absent or different.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import datetime as dt
import errno
import fcntl
import filecmp
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


ORDERS = (4, 6, 8)
MEMORY_MIB = (16, 64, 256)
CPUSET = "0-15"
SCHEMA_VERSION = "new02-ppmd-oracle-v1"
HOLDOUT_EXE_SIZE = 39384
HOLDOUT_EXE_SHA256 = "a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179"
PREREGISTRATION_REPO_PATH = (
    "documentation/ephemeral/research/"
    "CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md"
)
PREREGISTRATION_SHA256 = "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093"
PREREGISTRATION_GIT_BLOB = "d96df7e3478a6ba52b737ef30dea63d68b0e01ac"
TOOL_VERSION_ARGS = {
    "7z": ("i",),
    "taskset": ("--version",),
    "time": ("--version",),
    "cmp": ("--version",),
}


class HarnessError(RuntimeError):
    """A setup, child-process, or evidence-integrity failure."""


class JournaledHarnessError(HarnessError):
    """A failure whose durable VOID record has already been published."""


class SimulatedCrash(BaseException):
    """Test-only crash injection; a visible final is quarantined before escape."""


@dataclasses.dataclass(frozen=True)
class InventoryEntry:
    cohort: str
    name: str
    relative_path: str
    path: Path
    size_bytes: int
    sha256: str


@dataclasses.dataclass(frozen=True)
class GridCell:
    entry: InventoryEntry
    order: int
    memory_mib: int

    @property
    def identifier(self) -> str:
        return (
            f"{self.entry.cohort}/{self.entry.name}/"
            f"order={self.order}/mem={self.memory_mib}MiB"
        )

    @property
    def slug(self) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.entry.name)
        return f"{self.entry.cohort}-{safe_name}-o{self.order}-m{self.memory_mib}"


# cohort, logical name, relative path, exact bytes, exact SHA-256
_FROZEN_INVENTORY = (
    ("world", "dickens", "silesia/dickens", 10192446, "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a"),
    ("world", "reymont", "silesia/reymont", 6627202, "0eac0114a3dfe6e2ee1f345a0f79d653cb26c3bc9f0ed79238af4933422b7578"),
    ("world", "webster", "silesia/webster", 41458703, "6a68f69b26daf09f9dd84f7470368553194a0b294fcfa80f1604efb11143a383"),
    ("world", "xml", "silesia/xml", 5345280, "0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c"),
    ("world", "enwik8", "enwik8/enwik8", 100000000, "2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8"),
    ("world", "alice29.txt", "canterbury/alice29.txt", 152089, "7467306ee0feed4971260f3c87421154a05be571d944e9cb021a5713700c38f0"),
    ("world", "asyoulik.txt", "canterbury/asyoulik.txt", 125179, "eaa3526fe53859f34ecdf255712f9ecf0b2c903451d4755b2edaa2e2599cb0fc"),
    ("world", "cp.html", "canterbury/cp.html", 24603, "e0cd21cef5b6c4069461e949be100080c3ce887de6f1dd8626c480528efaaf61"),
    ("world", "lcet10.txt", "canterbury/lcet10.txt", 426754, "5314ba1dbb03f471df88bec6cd120a938ef60d0fd3511c5c1dce61bf7463245f"),
    ("world", "plrabn12.txt", "canterbury/plrabn12.txt", 481861, "07e2e0b461af78c7c647cb53dab39de560198e16f799b4516eccf0fbd69f764c"),
    ("world", "xargs.1", "canterbury/xargs.1", 4227, "c58aeb5d2d1e12751d47e7412b45784405fc30a5671b03d480fa05776e183619"),
    ("tuned", "binary_mixed.bin", "binary_mixed.bin", 8192, "669a93863d0fab21a599f70df7d8bc9ec98c9c933f60be5112612157622672d6"),
    ("tuned", "block_bound_runs.bin", "block_bound_runs.bin", 65536, "abcb2d5a7ea6c1e74f753c2a775998379568e79a13358cb52dfb48a956c040d5"),
    ("tuned", "both_sparse_16.bin", "both_sparse_16.bin", 16, "84c92eca52cc2721fbd3a0e285ecf16596756e1e7513bf4f4e314c0b7b9259e3"),
    ("tuned", "both_sparse_24.bin", "both_sparse_24.bin", 24, "ba3a1f0d984b45025c9a8ade0740d33355f430e48864bc7d83f26af579a2e510"),
    ("tuned", "dense.bin", "dense.bin", 4096, "a4ecb8ba6554b63d398076f1f00545c935d7b73b4e21988666185d6371c65c27"),
    ("tuned", "log_like.bin", "log_like.bin", 16384, "ac4ef4845750390362797bc33af63b3a3d480f827a8b7ff54090ce1c89a9543d"),
    ("tuned", "random_high.bin", "random_high.bin", 4096, "0e232e8ae9db07cc67194aa713d7a287876fec886ded19cffddb732a1094b415"),
    ("tuned", "sparse_clustered.bin", "sparse_clustered.bin", 2048, "d11533a77218a34e56285bf0df004ac06e845319e1ca07cb8d65f0911d75f7ce"),
    ("tuned", "sparse_small.bin", "sparse_small.bin", 256, "8c23d37b2230be9754c446b6cdef385fb4eb7dcac874905fcbb2e25b6f05672c"),
    ("tuned", "text.bin", "text.bin", 16384, "0160b7a1b4311fa6b273b63125f8cff4603205d8dc7fcc7cf9186691570c5415"),
    ("holdout", "rust_src.rs", "rust_src.rs", 26805, "27230e0c7ad1eb2b163b320debffbc4f5660d45ec931cdd3ffbe5cf3d7b13eb0"),
    ("holdout", "c_header.h", "c_header.h", 34649, "b4f6709d12c8493e2a42f740845abe2994deb27fc78fb85fcaa6e27228a87d62"),
    ("holdout", "config.json", "config.json", 66294, "259f831b18f3d1aecc130839ca075541b199f855570fb27a2f044309d2b7dc94"),
    ("holdout", "prose.txt", "prose.txt", 17774, "9026c001530a657fb8910a1d990325d07e19443ee898a65ae1b3ea3d2d9c9bf8"),
    ("holdout", "data.csv", "data.csv", 17029, "c9b1e70e718f33f7cd6433b98f123fcc2914a24d1974e1bcf53d73a2806b2860"),
    ("holdout", "exe.bin", "exe.bin", 39384, "a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179"),
)


Runner = Callable[[str, tuple[str, ...], Path | None], subprocess.CompletedProcess]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_inventory_sha256() -> str:
    payload = json.dumps(_FROZEN_INVENTORY, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def frozen_grid_records() -> tuple[tuple[object, ...], ...]:
    return tuple(
        (*entry, order, memory_mib, CPUSET)
        for entry in _FROZEN_INVENTORY
        for order in ORDERS
        for memory_mib in MEMORY_MIB
    )


def frozen_grid_sha256(records: Sequence[Sequence[object]] | None = None) -> str:
    payload = json.dumps(
        frozen_grid_records() if records is None else records,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        try:
            written = os.write(descriptor, view[offset:])
        except InterruptedError:
            continue
        if written <= 0:
            raise HarnessError("checked write made no progress")
        offset += written


def _require_safe_directory_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise HarnessError(f"unsafe parent component for holdout materialization: {current}")


def _require_single_link_regular(path: Path, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise HarnessError(f"{label} is missing") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise HarnessError(f"{label} is not a regular file")
    if metadata.st_nlink != 1:
        raise HarnessError(f"{label} link count must be exactly one")
    return metadata


def materialize_holdout_exe(
    holdout_root: Path,
    source: Path = Path("/bin/cat"),
) -> Path:
    _require_safe_directory_components(holdout_root)
    source = source.resolve(strict=True)
    canonical_source = Path("/bin/cat").resolve()
    _require_safe_directory_components(source.parent)
    if source != canonical_source:
        raise HarnessError("holdout exe source must be the canonical /bin/cat regular file")
    source_metadata = _require_single_link_regular(source, "holdout exe source")
    if source_metadata.st_size != HOLDOUT_EXE_SIZE or sha256_file(source) != HOLDOUT_EXE_SHA256:
        raise HarnessError("/bin/cat does not match the frozen holdout identity")

    holdout_root.mkdir(parents=True, exist_ok=True)
    _require_safe_directory_components(holdout_root)
    target = holdout_root / "exe.bin"
    if target.exists() or target.is_symlink():
        target_metadata = _require_single_link_regular(target, "existing holdout exe")
        if target_metadata.st_size != HOLDOUT_EXE_SIZE or sha256_file(target) != HOLDOUT_EXE_SHA256:
            raise HarnessError("existing holdout exe does not match the frozen identity")
        target.chmod(0o444)
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        directory = os.open(holdout_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return target

    descriptor, temporary_name = tempfile.mkstemp(prefix=".exe.bin.materialize-", dir=holdout_root)
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as input_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                _write_all(descriptor, chunk)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, target)
        temporary.unlink()
        directory = os.open(holdout_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    target_metadata = _require_single_link_regular(target, "materialized holdout exe")
    if target_metadata.st_size != HOLDOUT_EXE_SIZE or sha256_file(target) != HOLDOUT_EXE_SHA256:
        raise HarnessError("materialized holdout exe failed frozen identity verification")
    return target


def canonical_inventory(roots: Mapping[str, Path]) -> tuple[InventoryEntry, ...]:
    missing = {"world", "tuned", "holdout"} - set(roots)
    if missing:
        raise HarnessError(f"missing corpus roots: {', '.join(sorted(missing))}")
    return tuple(
        InventoryEntry(
            cohort=cohort,
            name=name,
            relative_path=relative_path,
            path=Path(roots[cohort]) / relative_path,
            size_bytes=size_bytes,
            sha256=expected_sha,
        )
        for cohort, name, relative_path, size_bytes, expected_sha in _FROZEN_INVENTORY
    )


def cohort_counts(entries: Iterable[InventoryEntry]) -> dict[str, int]:
    return dict(Counter(entry.cohort for entry in entries))


def plan_grid(
    entries: Sequence[InventoryEntry],
    orders: Sequence[int] = ORDERS,
    memories: Sequence[int] = MEMORY_MIB,
) -> tuple[GridCell, ...]:
    if not entries:
        raise HarnessError("inventory is empty")
    if not orders or not memories:
        raise HarnessError("order/memory grid is empty")
    return tuple(
        GridCell(entry=entry, order=order, memory_mib=memory)
        for entry in entries
        for order in orders
        for memory in memories
    )


def _tool_path(tools: Mapping[str, Mapping[str, str]], name: str) -> str:
    try:
        path = tools[name]["path"]
        version = tools[name]["version"]
    except KeyError as exc:
        raise HarnessError(f"tool provenance incomplete for {name}") from exc
    if not path or not version:
        raise HarnessError(f"tool provenance incomplete for {name}")
    return path


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise HarnessError(f"{label} must be an exact SHA-256")
    return value


def _git_output(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise HarnessError(
            f"git provenance command failed: git {' '.join(arguments)}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_blob_bytes(repo_root: Path, revision: str, repo_path: str) -> bytes:
    result = subprocess.run(
        ("git", "show", f"{revision}:{repo_path}"),
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise HarnessError(
            f"committed preregistration blob is unavailable: {_child_text(result.stderr).strip()}"
        )
    return bytes(result.stdout)


def recompute_run_id(provenance: Mapping[str, object]) -> str:
    required = (
        "code_sha",
        "repo_root",
        "harness_sha256",
        "test_sha256",
        "inventory_sha256",
        "grid_sha256",
        "preregistration",
        "tools",
        "environment",
    )
    try:
        material = {key: provenance[key] for key in required}
    except KeyError as exc:
        raise HarnessError(f"run identity material is missing {exc.args[0]}") from exc
    payload = json.dumps(
        {"schema": SCHEMA_VERSION, **material},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_provenance(provenance: Mapping[str, object]) -> None:
    code_sha = provenance.get("code_sha")
    if not isinstance(code_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise HarnessError("code identity must be an exact 40-character Git SHA")
    run_id = _require_sha256(provenance.get("run_id"), "run identity")
    repo_root_value = provenance.get("repo_root")
    if not isinstance(repo_root_value, str) or not Path(repo_root_value).is_absolute():
        raise HarnessError("repository identity root is invalid")
    repo_root = Path(repo_root_value)
    if repo_root.is_symlink() or not repo_root.is_dir() or str(repo_root.resolve()) != repo_root_value:
        raise HarnessError("repository identity root is invalid")
    if (
        _git_output(repo_root, "rev-parse", "HEAD") != code_sha
        or _git_output(repo_root, "rev-parse", "origin/main") != code_sha
    ):
        raise HarnessError("code identity is not the actual exact origin/main SHA")

    exact_files = {
        "harness identity": (provenance.get("harness_sha256"), Path(__file__).resolve()),
        "test identity": (
            provenance.get("test_sha256"),
            Path(__file__).resolve().with_name("test_new02_oracle_grid.py"),
        ),
    }
    for label, (claimed, path) in exact_files.items():
        expected = _require_sha256(claimed, label)
        if not path.is_file() or sha256_file(path) != expected:
            raise HarnessError(f"{label} does not match current bytes")

    inventory_identity = _require_sha256(
        provenance.get("inventory_sha256"), "inventory identity"
    )
    if inventory_identity != frozen_inventory_sha256():
        raise HarnessError("inventory identity does not match the ordered frozen inventory")
    grid_identity = _require_sha256(provenance.get("grid_sha256"), "grid identity")
    if grid_identity != frozen_grid_sha256():
        raise HarnessError("grid identity does not match the ordered frozen 243-cell grid")

    preregistration = provenance.get("preregistration")
    if not isinstance(preregistration, Mapping):
        raise HarnessError("preregistration identity is missing")
    prereg_path_value = preregistration.get("path")
    if not isinstance(prereg_path_value, str) or not prereg_path_value:
        raise HarnessError("preregistration identity path is missing")
    prereg_path = Path(prereg_path_value)
    prereg_sha = _require_sha256(preregistration.get("sha256"), "preregistration identity")
    prereg_repo_path = preregistration.get("repo_path")
    prereg_blob = preregistration.get("git_blob_sha")
    pinned_prereg_path = repo_root / PREREGISTRATION_REPO_PATH
    if (
        prereg_path != pinned_prereg_path
        or prereg_sha != PREREGISTRATION_SHA256
        or prereg_repo_path != PREREGISTRATION_REPO_PATH
        or prereg_blob != PREREGISTRATION_GIT_BLOB
        or not prereg_path.is_absolute()
        or prereg_path.is_symlink()
        or not prereg_path.is_file()
        or sha256_file(prereg_path) != prereg_sha
        or _git_output(repo_root, "rev-parse", f"{code_sha}:{PREREGISTRATION_REPO_PATH}")
        != PREREGISTRATION_GIT_BLOB
        or hashlib.sha256(
            _git_blob_bytes(repo_root, code_sha, PREREGISTRATION_REPO_PATH)
        ).hexdigest()
        != PREREGISTRATION_SHA256
    ):
        raise HarnessError("pinned preregistration identity does not match current bytes")

    tools = provenance.get("tools")
    if not isinstance(tools, Mapping) or set(tools) != {"7z", "taskset", "time", "cmp"}:
        raise HarnessError("tool identity set is incomplete or has extras")
    for name in ("7z", "taskset", "time", "cmp"):
        record = tools.get(name)
        if not isinstance(record, Mapping):
            raise HarnessError(f"tool identity is incomplete for {name}")
        path_value = record.get("path")
        version = record.get("version")
        binary_sha = _require_sha256(record.get("binary_sha256"), "tool binary hash")
        if not isinstance(path_value, str) or not path_value or not isinstance(version, str) or not version:
            raise HarnessError(f"tool identity is incomplete for {name}")
        path = Path(path_value)
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_file()
            or str(path.resolve()) != path_value
            or sha256_file(path) != binary_sha
        ):
            raise HarnessError(f"tool binary hash/path mismatch for {name}")
        if version != _command_output((path_value, *TOOL_VERSION_ARGS[name])):
            raise HarnessError(f"tool version output mismatch for {name}")
    environment = provenance.get("environment")
    if environment != {"LC_ALL": "C", "LANG": "C", "python": sys.version.split()[0]}:
        raise HarnessError("execution environment identity is invalid")
    if run_id != recompute_run_id(provenance):
        raise HarnessError("run identity does not bind the exact provenance material")


def encode_command(
    cell: GridCell,
    archive: Path,
    time_report: Path,
    tools: Mapping[str, Mapping[str, str]],
) -> tuple[str, ...]:
    return (
        _tool_path(tools, "time"),
        "-v",
        "-o",
        str(time_report),
        _tool_path(tools, "taskset"),
        "-c",
        CPUSET,
        _tool_path(tools, "7z"),
        "a",
        "-t7z",
        "-m0=PPMd",
        f"-mo={cell.order}",
        f"-mmem={cell.memory_mib}m",
        "-bd",
        "-y",
        str(archive),
        str(cell.entry.path),
    )


def decode_command(
    cell: GridCell,
    archive: Path,
    time_report: Path,
    tools: Mapping[str, Mapping[str, str]],
) -> tuple[str, ...]:
    del cell  # kept in the signature so both command builders bind a grid cell
    return (
        _tool_path(tools, "time"),
        "-v",
        "-o",
        str(time_report),
        _tool_path(tools, "taskset"),
        "-c",
        CPUSET,
        _tool_path(tools, "7z"),
        "x",
        "-so",
        "-y",
        str(archive),
    )


def _relative_artifact_paths(cell: GridCell) -> dict[str, str]:
    source_relative = Path(cell.entry.relative_path)
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+", cell.entry.cohort)
        or cell.entry.cohort in {".", ".."}
        or source_relative.is_absolute()
        or ".." in source_relative.parts
        or source_relative.as_posix() != cell.entry.relative_path
    ):
        raise HarnessError(f"input relative artifact is unsafe for {cell.identifier}")
    cell_root = Path("cells") / cell.slug
    return {
        "input": (Path(cell.entry.cohort) / source_relative).as_posix(),
        "archive": (cell_root / "payload.7z").as_posix(),
        "decoded": (cell_root / "decoded.bin").as_posix(),
        "encode_time": (cell_root / "encode.time").as_posix(),
        "decode_time": (cell_root / "decode.time").as_posix(),
    }


def _recorded_commands(
    cell: GridCell,
    tools: Mapping[str, Mapping[str, str]],
) -> dict[str, tuple[str, ...]]:
    paths = _relative_artifact_paths(cell)
    return {
        "encode": (
            _tool_path(tools, "time"),
            "-v",
            "-o",
            paths["encode_time"],
            _tool_path(tools, "taskset"),
            "-c",
            CPUSET,
            _tool_path(tools, "7z"),
            "a",
            "-t7z",
            "-m0=PPMd",
            f"-mo={cell.order}",
            f"-mmem={cell.memory_mib}m",
            "-bd",
            "-y",
            paths["archive"],
            paths["input"],
        ),
        "inspect": (
            _tool_path(tools, "7z"),
            "l",
            "-slt",
            paths["archive"],
        ),
        "decode": (
            _tool_path(tools, "time"),
            "-v",
            "-o",
            paths["decode_time"],
            _tool_path(tools, "taskset"),
            "-c",
            CPUSET,
            _tool_path(tools, "7z"),
            "x",
            "-so",
            "-y",
            paths["archive"],
        ),
        "cmp": (
            _tool_path(tools, "cmp"),
            "-s",
            paths["input"],
            paths["decoded"],
        ),
    }


def _artifact_identity(path: Path, relative_path: str, label: str) -> dict[str, object]:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise HarnessError(f"missing {label} artifact: {relative_path}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise HarnessError(f"{label} artifact is not a regular file: {relative_path}")
    return {
        "relative_path": relative_path,
        "size_bytes": info.st_size,
        "sha256": sha256_file(path),
    }


def _parse_duration(value: str) -> float:
    if not re.fullmatch(
        r"(?:[0-9]+:[0-5]?[0-9]|[0-9]+:[0-5]?[0-9]:[0-5]?[0-9])"
        r"(?:\.[0-9]+)?",
        value,
    ):
        raise HarnessError(f"invalid elapsed time value: {value}")
    pieces = value.split(":")
    try:
        if len(pieces) == 2:
            minutes, seconds = pieces
            return int(minutes) * 60 + float(seconds)
        if len(pieces) == 3:
            hours, minutes, seconds = pieces
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise HarnessError(f"invalid elapsed time value: {value}") from exc
    raise HarnessError(f"invalid elapsed time value: {value}")


def parse_gnu_time(text: str) -> dict[str, float | int]:
    field_patterns = {
        "Command being timed": r'"[^\r\n]*"',
        "User time (seconds)": r"[0-9]+(?:\.[0-9]+)?",
        "System time (seconds)": r"[0-9]+(?:\.[0-9]+)?",
        "Percent of CPU this job got": r"[0-9]+%",
        "Elapsed (wall clock) time (h:mm:ss or m:ss)": (
            r"(?:[0-9]+:[0-5]?[0-9]|[0-9]+:[0-5]?[0-9]:[0-5]?[0-9])"
            r"(?:\.[0-9]+)?"
        ),
        "Average shared text size (kbytes)": r"[0-9]+",
        "Average unshared data size (kbytes)": r"[0-9]+",
        "Average stack size (kbytes)": r"[0-9]+",
        "Average total size (kbytes)": r"[0-9]+",
        "Maximum resident set size (kbytes)": r"[0-9]+",
        "Average resident set size (kbytes)": r"[0-9]+",
        "Major (requiring I/O) page faults": r"[0-9]+",
        "Minor (reclaiming a frame) page faults": r"[0-9]+",
        "Voluntary context switches": r"[0-9]+",
        "Involuntary context switches": r"[0-9]+",
        "Swaps": r"[0-9]+",
        "File system inputs": r"[0-9]+",
        "File system outputs": r"[0-9]+",
        "Socket messages sent": r"[0-9]+",
        "Socket messages received": r"[0-9]+",
        "Signals delivered": r"[0-9]+",
        "Page size (bytes)": r"[0-9]+",
        "Exit status": r"[0-9]+",
    }
    if not text or "\r" in text or not text.endswith("\n"):
        raise HarnessError("GNU time report does not match the exact grammar")
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("\t"):
            raise HarnessError("GNU time report does not match the exact grammar")
        body = line[1:]
        matches = [
            (field, body[len(field) + 2 :])
            for field in field_patterns
            if body.startswith(f"{field}: ")
        ]
        if len(matches) != 1:
            raise HarnessError("GNU time report does not match the exact grammar")
        field, value = matches[0]
        if field in values or re.fullmatch(field_patterns[field], value) is None:
            raise HarnessError("GNU time report does not match the exact grammar")
        values[field] = value

    elapsed_field = "Elapsed (wall clock) time (h:mm:ss or m:ss)"
    rss_field = "Maximum resident set size (kbytes)"
    if elapsed_field not in values:
        raise HarnessError("GNU time report missing elapsed time")
    if rss_field not in values:
        raise HarnessError("GNU time report missing peak RSS")
    if list(values) != list(field_patterns):
        raise HarnessError("GNU time report does not match the exact grammar")
    return {
        "elapsed_seconds": _parse_duration(values[elapsed_field]),
        "peak_rss_kib": int(values[rss_field]),
    }


def expected_ppmd_memory_exponent(input_bytes: int, requested_memory_mib: int) -> int:
    """Return the exact exponent 7z records after its small-input memory cap."""
    if input_bytes <= 0:
        raise HarnessError("PPMd input must be non-empty")
    if requested_memory_mib <= 0 or requested_memory_mib & (requested_memory_mib - 1):
        raise HarnessError("PPMd memory must be a positive power of two MiB")
    requested_exponent = 20 + requested_memory_mib.bit_length() - 1
    input_capped_exponent = max(16, (input_bytes * 16 - 1).bit_length())
    return min(requested_exponent, input_capped_exponent)


def _parse_exact_member_method(inspection: str, cell: GridCell) -> tuple[str, list[str]]:
    lines = inspection.splitlines()
    if not any(re.fullmatch(r"[ \t]*Method[ \t]*=[ \t]*PPMD[ \t]*", line) for line in lines):
        raise HarnessError(f"archive method is not PPMd for {cell.identifier}")
    separators = [index for index, line in enumerate(lines) if line.strip() == "----------"]
    if len(separators) != 1:
        raise HarnessError(f"archive technical listing has ambiguous member boundary for {cell.identifier}")
    member_lines = lines[separators[0] + 1 :]

    def values(key: str) -> list[str]:
        expression = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*=[ \t]*(.*?)[ \t]*$")
        return [match.group(1) for line in member_lines if (match := expression.fullmatch(line))]

    paths = values("Path")
    sizes = values("Size")
    methods = values("Method")
    if len(paths) != 1 or len(sizes) != 1 or len(methods) != 1:
        raise HarnessError(
            f"archive member listing must contain exactly one Path/Size/Method for {cell.identifier}"
        )
    if paths[0] != cell.entry.name:
        raise HarnessError(f"archive does not contain exactly one expected file for {cell.identifier}")
    if sizes[0] != str(cell.entry.size_bytes):
        raise HarnessError(f"archive member size mismatch for {cell.identifier}")

    expected_method = (
        f"PPMD:o{cell.order}:mem"
        f"{expected_ppmd_memory_exponent(cell.entry.size_bytes, cell.memory_mib)}"
    )
    if methods[0] != expected_method:
        raise HarnessError(
            f"archive member method mismatch for {cell.identifier}: "
            f"expected {expected_method}, got {methods[0]}"
        )
    return expected_method, paths


def verify_inventory(entries: Sequence[InventoryEntry]) -> None:
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        identity = (entry.cohort, entry.name)
        if identity in seen:
            raise HarnessError(f"duplicate inventory identity: {entry.cohort}/{entry.name}")
        seen.add(identity)
        try:
            input_mode = entry.path.lstat().st_mode
        except FileNotFoundError:
            input_mode = 0
        if not stat.S_ISREG(input_mode):
            raise HarnessError(f"missing regular file: {entry.cohort}/{entry.name}: {entry.path}")
        actual_size = entry.path.stat().st_size
        if actual_size != entry.size_bytes:
            raise HarnessError(
                f"size mismatch for {entry.cohort}/{entry.name}: "
                f"expected {entry.size_bytes}, got {actual_size}"
            )
        actual_sha = sha256_file(entry.path)
        if actual_sha != entry.sha256:
            raise HarnessError(
                f"SHA-256 mismatch for {entry.cohort}/{entry.name}: "
                f"expected {entry.sha256}, got {actual_sha}"
            )


def _default_runner(
    phase: str,
    argv: tuple[str, ...],
    stdout_path: Path | None,
) -> subprocess.CompletedProcess:
    del phase
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C"})
    if stdout_path is None:
        return subprocess.run(
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    with stdout_path.open("wb") as output:
        return subprocess.run(
            argv,
            check=False,
            stdout=output,
            stderr=subprocess.PIPE,
            env=env,
        )


def _child_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _require_child_success(
    cell: GridCell,
    phase: str,
    result: subprocess.CompletedProcess,
) -> None:
    if result.returncode != 0:
        stderr = _child_text(result.stderr).strip()
        detail = f": {stderr}" if stderr else ""
        raise HarnessError(
            f"{phase} failed for {cell.identifier} with exit {result.returncode}{detail}"
        )
    combined = f"{_child_text(result.stdout)}\n{_child_text(result.stderr)}"
    if re.search(r"(?m)^\s*(?:ERROR|Error):", combined):
        raise HarnessError(f"{phase} emitted an error marker for {cell.identifier}")


def _inspect_live_publication_archive(
    publication_root: Path,
    cell: GridCell,
    command: tuple[str, ...],
) -> tuple[str, list[str]]:
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C"})
    try:
        result = subprocess.run(
            command,
            cwd=publication_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as exc:
        raise HarnessError(
            f"live archive inspection could not execute for {cell.identifier}"
        ) from exc
    try:
        _require_child_success(cell, "live archive inspection", result)
        return _parse_exact_member_method(
            f"{_child_text(result.stdout)}\n{_child_text(result.stderr)}",
            cell,
        )
    except HarnessError as exc:
        raise HarnessError(
            f"live archive inspection mismatch for {cell.identifier}: {exc}"
        ) from exc


def _phase_record(
    command: tuple[str, ...],
    result: subprocess.CompletedProcess,
    timing: Mapping[str, float | int],
) -> dict[str, object]:
    return {
        "command": list(command),
        "returncode": result.returncode,
        "elapsed_seconds": timing["elapsed_seconds"],
        "peak_rss_kib": timing["peak_rss_kib"],
        "stdout": _child_text(result.stdout),
        "stderr": _child_text(result.stderr),
    }


def _validate_observation(
    observation: Mapping[str, object],
    cell: GridCell,
    provenance: Mapping[str, object],
    *,
    publication_root: Path | None = None,
    manifest_entries: Mapping[str, Mapping[str, object]] | None = None,
) -> None:
    tools = provenance.get("tools")
    if not isinstance(tools, Mapping):
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")
    paths = _relative_artifact_paths(cell)
    commands = _recorded_commands(cell, tools)  # type: ignore[arg-type]
    expected_method = (
        f"PPMD:o{cell.order}:mem"
        f"{expected_ppmd_memory_exponent(cell.entry.size_bytes, cell.memory_mib)}"
    )
    inspection = observation.get("archive_inspection")
    encode = observation.get("encode")
    decode = observation.get("decode")
    artifacts = observation.get("artifacts")
    expected_keys = {
        "schema", "run_id", "cell", "cohort", "file", "relative_path",
        "input_bytes", "input_sha256", "order", "memory_mib", "cpu_set",
        "archive_bytes", "archive_sha256", "decoded_bytes", "decoded_sha256",
        "cmp_command", "cmp_returncode", "cmp_equal", "sha256_equal",
        "round_trip", "archive_inspection", "encode", "decode", "artifacts",
        "code_sha", "inventory_sha256", "grid_sha256", "tools",
        "preregistration",
    }
    if set(observation) != expected_keys:
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")
    critical = {
        "schema": SCHEMA_VERSION,
        "run_id": provenance.get("run_id"),
        "cell": cell.identifier,
        "cohort": cell.entry.cohort,
        "file": cell.entry.name,
        "relative_path": cell.entry.relative_path,
        "input_bytes": cell.entry.size_bytes,
        "input_sha256": cell.entry.sha256,
        "order": cell.order,
        "memory_mib": cell.memory_mib,
        "cpu_set": CPUSET,
        "decoded_bytes": cell.entry.size_bytes,
        "decoded_sha256": cell.entry.sha256,
        "cmp_returncode": 0,
        "cmp_equal": True,
        "sha256_equal": True,
        "round_trip": True,
        "code_sha": provenance.get("code_sha"),
        "inventory_sha256": provenance.get("inventory_sha256"),
        "grid_sha256": provenance.get("grid_sha256"),
        "tools": provenance.get("tools"),
        "preregistration": provenance.get("preregistration"),
    }
    if any(observation.get(key) != expected for key, expected in critical.items()):
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")

    def exact_nonnegative_integer(value: object, *, positive: bool = False) -> bool:
        return type(value) is int and value >= (1 if positive else 0)

    def finite_nonnegative(value: object) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            normalized = float(value)
        except (OverflowError, ValueError):
            return False
        return math.isfinite(normalized) and normalized >= 0.0

    def valid_child_text(value: object) -> bool:
        return isinstance(value, str) and not re.search(
            r"(?m)^\s*(?:ERROR|Error):", value
        )

    def validate_phase(
        phase: object,
        expected_command: tuple[str, ...],
    ) -> bool:
        return (
            isinstance(phase, Mapping)
            and set(phase) == {
                "command", "returncode", "elapsed_seconds", "peak_rss_kib",
                "stdout", "stderr",
            }
            and phase.get("command") == list(expected_command)
            and type(phase.get("returncode")) is int
            and phase.get("returncode") == 0
            and finite_nonnegative(phase.get("elapsed_seconds"))
            and exact_nonnegative_integer(phase.get("peak_rss_kib"))
            and valid_child_text(phase.get("stdout"))
            and valid_child_text(phase.get("stderr"))
        )

    if (
        not exact_nonnegative_integer(observation.get("archive_bytes"), positive=True)
        or not isinstance(observation.get("archive_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", str(observation.get("archive_sha256")))
        or not isinstance(inspection, Mapping)
        or set(inspection) != {
            "command", "returncode", "stdout", "stderr", "method", "member_paths"
        }
        or inspection.get("command") != list(commands["inspect"])
        or type(inspection.get("returncode")) is not int
        or inspection.get("returncode") != 0
        or inspection.get("method") != expected_method
        or inspection.get("member_paths") != [cell.entry.name]
        or not valid_child_text(inspection.get("stdout"))
        or not valid_child_text(inspection.get("stderr"))
        or not validate_phase(encode, commands["encode"])
        or not validate_phase(decode, commands["decode"])
    ):
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")
    try:
        parsed_method, parsed_paths = _parse_exact_member_method(
            f"{inspection['stdout']}\n{inspection['stderr']}", cell
        )
    except HarnessError as exc:
        raise HarnessError(
            f"observation semantics mismatch for {cell.identifier}: {exc}"
        ) from exc
    if parsed_method != expected_method or parsed_paths != [cell.entry.name]:
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")

    cmp_command = observation.get("cmp_command")
    if (
        cmp_command != list(commands["cmp"])
        or type(observation.get("cmp_returncode")) is not int
        or not exact_nonnegative_integer(observation.get("input_bytes"))
        or not exact_nonnegative_integer(observation.get("decoded_bytes"))
    ):
        raise HarnessError(f"observation semantics mismatch for {cell.identifier}")

    if not isinstance(artifacts, Mapping) or set(artifacts) != set(paths):
        raise HarnessError(f"observation artifact semantics mismatch for {cell.identifier}")
    expected_artifact_values = {
        "input": (paths["input"], cell.entry.size_bytes, cell.entry.sha256),
        "archive": (
            paths["archive"],
            observation.get("archive_bytes"),
            observation.get("archive_sha256"),
        ),
        "decoded": (paths["decoded"], cell.entry.size_bytes, cell.entry.sha256),
    }
    for name, expected in expected_artifact_values.items():
        record = artifacts.get(name)
        if (
            not isinstance(record, Mapping)
            or set(record) != {"relative_path", "size_bytes", "sha256"}
            or type(record.get("size_bytes")) is not int
            or not isinstance(record.get("sha256"), str)
            or (
                record.get("relative_path"), record.get("size_bytes"), record.get("sha256")
            ) != expected
        ):
            raise HarnessError(f"observation artifact semantics mismatch for {cell.identifier}")
    for name in ("encode_time", "decode_time"):
        record = artifacts.get(name)
        if (
            not isinstance(record, Mapping)
            or set(record) != {"relative_path", "size_bytes", "sha256"}
            or record.get("relative_path") != paths[name]
            or not exact_nonnegative_integer(record.get("size_bytes"), positive=True)
            or not isinstance(record.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
        ):
            raise HarnessError(f"observation artifact semantics mismatch for {cell.identifier}")

    if (publication_root is None) != (manifest_entries is None):
        raise HarnessError("publication artifact validation inputs are incomplete")
    if publication_root is None or manifest_entries is None:
        return
    input_identity = _artifact_identity(cell.entry.path, paths["input"], "input")
    if input_identity != artifacts["input"]:
        raise HarnessError(f"observation input artifact mismatch for {cell.identifier}")
    for name in ("archive", "decoded", "encode_time", "decode_time"):
        record = artifacts[name]
        relative = record["relative_path"]
        path = publication_root / relative
        actual = _artifact_identity(path, relative, name)
        if actual != record:
            raise HarnessError(f"observation {name} artifact mismatch for {cell.identifier}")
        manifest_record = manifest_entries.get(relative)
        if (
            not isinstance(manifest_record, Mapping)
            or manifest_record.get("path") != relative
            or manifest_record.get("size_bytes") != record["size_bytes"]
            or manifest_record.get("sha256") != record["sha256"]
        ):
            raise HarnessError(
                f"observation {name} artifact manifest binding mismatch for {cell.identifier}"
            )

    live_method, live_paths = _inspect_live_publication_archive(
        publication_root, cell, commands["inspect"]
    )
    if (
        live_method != expected_method
        or live_paths != [cell.entry.name]
        or inspection["method"] != live_method
        or inspection["member_paths"] != live_paths
    ):
        raise HarnessError(f"live archive inspection mismatch for {cell.identifier}")

    for phase_name, artifact_name, phase in (
        ("encode", "encode_time", encode),
        ("decode", "decode_time", decode),
    ):
        timing_path = publication_root / artifacts[artifact_name]["relative_path"]
        try:
            parsed_timing = parse_gnu_time(timing_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, HarnessError) as exc:
            raise HarnessError(
                f"{phase_name} timing artifact is invalid for {cell.identifier}: {exc}"
            ) from exc
        recorded_timing = {
            "elapsed_seconds": phase["elapsed_seconds"],
            "peak_rss_kib": phase["peak_rss_kib"],
        }
        if parsed_timing != recorded_timing:
            raise HarnessError(
                f"{phase_name} timing artifact does not equal row values for {cell.identifier}"
            )


def run_cell(
    cell: GridCell,
    workspace: Path,
    provenance: Mapping[str, object],
    *,
    runner: Runner = _default_runner,
) -> dict[str, object]:
    verify_inventory((cell.entry,))
    validate_provenance(provenance)
    tools = provenance.get("tools")
    if not isinstance(tools, Mapping):
        raise HarnessError("provenance missing tools")
    code_sha = provenance["code_sha"]

    workspace.mkdir(parents=True, exist_ok=False)
    archive = workspace / "payload.7z"
    decoded = workspace / "decoded.bin"
    encode_time_path = workspace / "encode.time"
    decode_time_path = workspace / "decode.time"
    relative_paths = _relative_artifact_paths(cell)
    recorded_commands = _recorded_commands(cell, tools)  # type: ignore[arg-type]
    encode_argv = encode_command(cell, archive, encode_time_path, tools)
    decode_argv = decode_command(cell, archive, decode_time_path, tools)
    inspect_argv = (
        _tool_path(tools, "7z"),
        "l",
        "-slt",
        str(archive),
    )
    cmp_argv = (
        _tool_path(tools, "cmp"),
        "-s",
        str(cell.entry.path),
        str(decoded),
    )

    encode_result = runner("encode", encode_argv, None)
    _require_child_success(cell, "encode", encode_result)
    if not archive.is_file() or archive.stat().st_size <= 0:
        raise HarnessError(f"encode produced no charged archive for {cell.identifier}")
    if not encode_time_path.is_file():
        raise HarnessError(f"encode produced no GNU time report for {cell.identifier}")
    encode_timing = parse_gnu_time(encode_time_path.read_text())

    inspect_result = runner("inspect", inspect_argv, None)
    _require_child_success(cell, "inspect", inspect_result)
    inspection = f"{_child_text(inspect_result.stdout)}\n{_child_text(inspect_result.stderr)}"
    member_method, member_paths = _parse_exact_member_method(inspection, cell)

    decode_result = runner("decode", decode_argv, decoded)
    _require_child_success(cell, "decode", decode_result)
    if not decoded.is_file():
        raise HarnessError(f"decode produced no output for {cell.identifier}")
    if not decode_time_path.is_file():
        raise HarnessError(f"decode produced no GNU time report for {cell.identifier}")
    decode_timing = parse_gnu_time(decode_time_path.read_text())

    cmp_result = runner("cmp", cmp_argv, None)
    _require_child_success(cell, "cmp", cmp_result)
    cmp_equal = filecmp.cmp(cell.entry.path, decoded, shallow=False)
    input_sha = sha256_file(cell.entry.path)
    decoded_sha = sha256_file(decoded)
    sha_equal = input_sha == decoded_sha == cell.entry.sha256
    if not cmp_equal or not sha_equal:
        raise HarnessError(f"round-trip mismatch for {cell.identifier}")

    artifacts = {
        "input": _artifact_identity(cell.entry.path, relative_paths["input"], "input"),
        "archive": _artifact_identity(archive, relative_paths["archive"], "archive"),
        "decoded": _artifact_identity(decoded, relative_paths["decoded"], "decoded"),
        "encode_time": _artifact_identity(
            encode_time_path, relative_paths["encode_time"], "encode timing"
        ),
        "decode_time": _artifact_identity(
            decode_time_path, relative_paths["decode_time"], "decode timing"
        ),
    }
    observation = {
        "schema": SCHEMA_VERSION,
        "run_id": provenance.get("run_id"),
        "cell": cell.identifier,
        "cohort": cell.entry.cohort,
        "file": cell.entry.name,
        "relative_path": cell.entry.relative_path,
        "input_bytes": cell.entry.size_bytes,
        "input_sha256": input_sha,
        "order": cell.order,
        "memory_mib": cell.memory_mib,
        "cpu_set": CPUSET,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "decoded_bytes": decoded.stat().st_size,
        "decoded_sha256": decoded_sha,
        "cmp_command": list(recorded_commands["cmp"]),
        "cmp_returncode": cmp_result.returncode,
        "cmp_equal": cmp_equal,
        "sha256_equal": sha_equal,
        "round_trip": cmp_equal and sha_equal,
        "archive_inspection": {
            "command": list(recorded_commands["inspect"]),
            "returncode": inspect_result.returncode,
            "stdout": _child_text(inspect_result.stdout),
            "stderr": _child_text(inspect_result.stderr),
            "method": member_method,
            "member_paths": member_paths,
        },
        "encode": _phase_record(recorded_commands["encode"], encode_result, encode_timing),
        "decode": _phase_record(recorded_commands["decode"], decode_result, decode_timing),
        "artifacts": artifacts,
        "code_sha": code_sha,
        "inventory_sha256": provenance.get("inventory_sha256"),
        "grid_sha256": provenance.get("grid_sha256"),
        "tools": tools,
        "preregistration": provenance.get("preregistration"),
    }
    _validate_observation(observation, cell, provenance)
    return observation


def _write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(descriptor, 1024 * 1024)
        except InterruptedError:
            continue
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _validate_void_journal(payload: bytes) -> None:
    if not payload:
        return
    if not payload.endswith(b"\n"):
        raise HarnessError("existing VOID journal has an incomplete final record")
    try:
        text = payload.decode("utf-8")
        records = [json.loads(line) for line in text.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError("existing VOID journal is not valid complete JSONL") from exc
    if any(
        not isinstance(record, dict)
        or record.get("schema") != SCHEMA_VERSION
        or record.get("status") != "VOID"
        for record in records
    ):
        raise HarnessError("existing VOID journal contains a non-VOID record")


def _append_void(path: Path, value: Mapping[str, object]) -> None:
    if value.get("schema") != SCHEMA_VERSION or value.get("status") != "VOID":
        raise HarnessError("refusing to append an incomplete VOID record")
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary: Path | None = None
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        try:
            current_descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            current = b""
        else:
            try:
                if not stat.S_ISREG(os.fstat(current_descriptor).st_mode):
                    raise HarnessError("existing VOID journal is not a regular file")
                current = _read_all(current_descriptor)
            finally:
                os.close(current_descriptor)
        _validate_void_journal(current)
        record = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for _ in range(128):
            temporary = path.parent / f".{path.name}.rewrite-{secrets.token_hex(16)}"
            try:
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o644,
                )
                break
            except FileExistsError:
                continue
        else:
            raise HarnessError("cannot reserve same-directory VOID journal temporary")
        try:
            _write_all(descriptor, current + record)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
        temporary = None
        os.fsync(directory)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        fcntl.flock(directory, fcntl.LOCK_UN)
        os.close(directory)


def _manifest_entries(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise HarnessError(f"publication contains special file: {relative}")
        if relative in {"MANIFEST.json", "COMPLETE", ".COMPLETE.pending"}:
            raise HarnessError(f"reserved publication path already exists: {relative}")
        entries.append(
            {"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    return entries


def _manifest_directories(root: Path) -> list[str]:
    directories: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            directories.append(path.relative_to(root).as_posix())
        elif not stat.S_ISREG(mode):
            raise HarnessError(f"publication contains special file: {path.relative_to(root)}")
    return directories


def _fsync_tree(root: Path) -> None:
    directories = [root]
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        elif stat.S_ISDIR(mode):
            directories.append(path)
        else:
            raise HarnessError(f"publication contains special file: {path.relative_to(root)}")
    for directory in reversed(directories):
        _fsync_directory(directory)


def _make_tree_read_only(root: Path) -> None:
    files: list[Path] = []
    directories = [root]
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            files.append(path)
        elif stat.S_ISDIR(mode):
            directories.append(path)
        else:
            raise HarnessError(f"publication contains special file: {path.relative_to(root)}")
    for path in files:
        path.chmod(0o444)
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555)
    _fsync_tree(root)


def _discard_tree(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for child in path.rglob("*"):
        try:
            if child.is_dir() and not child.is_symlink():
                child.chmod(0o755)
            else:
                child.chmod(0o644)
        except FileNotFoundError:
            pass
    try:
        path.chmod(0o755)
    except FileNotFoundError:
        return
    shutil.rmtree(path)


def _rename_noreplace(source: Path, target: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise HarnessError("renameat2(RENAME_NOREPLACE) is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise HarnessError(f"refusing to overwrite output directory: {target}")
        raise HarnessError(
            f"renameat2(RENAME_NOREPLACE) failed: {os.strerror(error_number)}"
        )


def _quarantine_visible_final(output_dir: Path) -> Path:
    quarantine = output_dir.parent / (
        f".{output_dir.name}.quarantine-{secrets.token_hex(16)}"
    )
    _rename_noreplace(output_dir, quarantine)
    _fsync_directory(output_dir.parent)
    return quarantine


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"publication {label} is invalid") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"publication {label} is not an object")
    return value


def _validate_publication_tree(
    root: Path,
    *,
    authoritative: bool,
    expected_final_namespace: Path | None = None,
    canonical: bool = True,
) -> dict[str, object]:
    if root.is_symlink() or not root.is_dir():
        raise HarnessError("publication root is not a regular directory")
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    writable_nodes: list[str] = []
    for path in [root, *root.rglob("*")]:
        mode = path.lstat().st_mode
        if mode & 0o222:
            writable_nodes.append(path.relative_to(root).as_posix())
        if path == root:
            continue
        if stat.S_ISDIR(mode):
            actual_directories.add(path.relative_to(root).as_posix())
            continue
        if not stat.S_ISREG(mode):
            raise HarnessError(f"publication contains special file: {path.relative_to(root)}")
        actual_files.add(path.relative_to(root).as_posix())

    manifest_path = root / "MANIFEST.json"
    complete_path = root / "COMPLETE"
    manifest = _load_json_object(manifest_path, "manifest")
    if set(manifest) != {
        "schema", "status", "observation_count", "directories", "entries"
    }:
        raise HarnessError("publication manifest has an inexact schema")
    if manifest.get("schema") != SCHEMA_VERSION or manifest.get("status") != "STAGED":
        raise HarnessError("publication manifest has invalid identity/status")
    entries = manifest.get("entries")
    directories = manifest.get("directories")
    if (
        not isinstance(entries, list)
        or not isinstance(directories, list)
        or any(
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            for relative in directories
        )
        or directories != sorted(set(directories))
    ):
        raise HarnessError("publication manifest entries are invalid")
    if actual_directories != set(directories):
        raise HarnessError("publication manifest file set does not match the directory")
    expected_files = {"MANIFEST.json", "COMPLETE"}
    manifest_by_path: dict[str, Mapping[str, object]] = {}
    previous = ""
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "size_bytes", "sha256"}:
            raise HarnessError("publication manifest entry is invalid")
        relative = entry.get("path")
        entry_size = entry.get("size_bytes")
        entry_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative <= previous
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or type(entry_size) is not int
            or entry_size < 0
            or not isinstance(entry_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", entry_sha) is None
        ):
            raise HarnessError("publication manifest path order is invalid")
        previous = relative
        path = root / relative
        if relative in expected_files or relative == ".COMPLETE.pending" or not path.is_file():
            raise HarnessError("publication manifest file set is invalid")
        if path.stat().st_size != entry.get("size_bytes") or sha256_file(path) != entry.get("sha256"):
            raise HarnessError(f"publication manifest hash/size mismatch: {relative}")
        expected_files.add(relative)
        manifest_by_path[relative] = entry
    if actual_files != expected_files:
        raise HarnessError("publication manifest file set does not match the directory")
    if writable_nodes:
        raise HarnessError(f"publication contains writable node: {writable_nodes[0]}")

    observation_count = manifest.get("observation_count")
    if type(observation_count) is not int or observation_count < 1:
        raise HarnessError("publication manifest observation count is invalid")
    observations = root / "observations.jsonl"
    try:
        lines = observations.read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError("publication observations are invalid") from exc
    if len(rows) != observation_count or any(
        not isinstance(row, dict)
        or row.get("schema") != SCHEMA_VERSION
        or row.get("round_trip") is not True
        for row in rows
    ):
        raise HarnessError("publication observation count/content is invalid")

    provenance_record = _load_json_object(root / "provenance.json", "provenance")
    if set(provenance_record) != {
        "schema",
        "provenance",
        "inventory",
        "orders",
        "memory_mib",
        "cpu_set",
        "observation_count",
        "publication",
    }:
        raise HarnessError("publication provenance has an inexact schema")
    inventory = provenance_record.get("inventory")
    orders = provenance_record.get("orders")
    memories = provenance_record.get("memory_mib")
    if (
        provenance_record.get("schema") != SCHEMA_VERSION
        or provenance_record.get("cpu_set") != CPUSET
        or provenance_record.get("publication") != "all-or-nothing"
        or provenance_record.get("observation_count") != observation_count
        or not isinstance(inventory, list)
        or not inventory
        or not isinstance(orders, list)
        or not orders
        or any(type(order) is not int or order <= 0 for order in orders)
        or orders != list(dict.fromkeys(orders))
        or not isinstance(memories, list)
        or not memories
        or any(type(memory) is not int or memory <= 0 for memory in memories)
        or memories != list(dict.fromkeys(memories))
        or len(inventory) * len(orders) * len(memories) != observation_count
    ):
        raise HarnessError("publication provenance/count is invalid")
    expected_cells: list[str] = []
    inventory_entries: list[InventoryEntry] = []
    for item in inventory:
        if not isinstance(item, dict) or set(item) != {
            "cohort", "name", "relative_path", "path", "size_bytes", "sha256"
        }:
            raise HarnessError("publication provenance inventory is invalid")
        cohort = item.get("cohort")
        name = item.get("name")
        if (
            not isinstance(cohort, str)
            or not isinstance(name, str)
            or not isinstance(item.get("relative_path"), str)
            or not isinstance(item.get("path"), str)
            or not Path(item["path"]).is_absolute()
            or type(item.get("size_bytes")) is not int
            or item["size_bytes"] < 0
            or not isinstance(item.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        ):
            raise HarnessError("publication provenance inventory identity is invalid")
        inventory_entries.append(
            InventoryEntry(
                cohort=cohort,
                name=name,
                relative_path=item["relative_path"],
                path=Path(item["path"]),
                size_bytes=item["size_bytes"],
                sha256=item["sha256"],
            )
        )
        expected_cells.extend(
            f"{cohort}/{name}/order={order}/mem={memory}MiB"
            for order in orders
            for memory in memories
        )
    verify_inventory(tuple(inventory_entries))
    observed_cells = [row.get("cell") for row in rows]
    embedded_provenance = provenance_record.get("provenance")
    if not isinstance(embedded_provenance, Mapping):
        raise HarnessError("publication embedded provenance is invalid")
    validate_provenance(embedded_provenance)
    if observed_cells != expected_cells or any(
        row.get("cpu_set") != CPUSET
        or row.get("order") not in orders
        or row.get("memory_mib") not in memories
        or row.get("run_id") != embedded_provenance.get("run_id")
        or row.get("code_sha") != embedded_provenance.get("code_sha")
        for row in rows
    ):
        raise HarnessError("publication observations do not match the exact declared grid")

    complete = _load_json_object(complete_path, "completion marker")
    if set(complete) != {
        "schema", "status", "observation_count", "manifest_sha256", "final_namespace"
    }:
        raise HarnessError("publication completion marker has an inexact schema")
    final_namespace = complete.get("final_namespace")
    expected_namespace = (
        str(expected_final_namespace.absolute())
        if expected_final_namespace is not None
        else final_namespace
    )
    if (
        complete.get("schema") != SCHEMA_VERSION
        or complete.get("status") != "COMPLETE"
        or complete.get("observation_count") != observation_count
        or complete.get("manifest_sha256") != sha256_file(manifest_path)
        or not isinstance(final_namespace, str)
        or final_namespace != expected_namespace
    ):
        raise HarnessError("publication completion marker does not authenticate manifest/count")
    if authoritative and str(root.absolute()) != final_namespace:
        raise HarnessError("publication is not in its registered final namespace")
    canonical_inventory_identity = [
        (cohort, name, relative_path, size_bytes, expected_sha)
        for cohort, name, relative_path, size_bytes, expected_sha in _FROZEN_INVENTORY
    ]
    recorded_inventory_identity = [
        (
            item["cohort"],
            item["name"],
            item["relative_path"],
            item["size_bytes"],
            item["sha256"],
        )
        for item in inventory
    ]
    if canonical and (
        recorded_inventory_identity != canonical_inventory_identity
        or orders != list(ORDERS)
        or memories != list(MEMORY_MIB)
        or observation_count != 243
        or embedded_provenance.get("inventory_sha256") != frozen_inventory_sha256()
        or embedded_provenance.get("grid_sha256") != frozen_grid_sha256()
    ):
        raise HarnessError("publication is not the exact frozen 27/243 canonical grid")

    row_index = 0
    required_manifest_paths = {"observations.jsonl", "provenance.json"}
    required_directories = {"cells"}
    for entry in inventory_entries:
        for order in orders:
            for memory in memories:
                row = rows[row_index]
                row_index += 1
                cell = GridCell(entry=entry, order=order, memory_mib=memory)
                _validate_observation(
                    row,
                    cell,
                    embedded_provenance,
                    publication_root=root,
                    manifest_entries=manifest_by_path,
                )
                artifact_paths = _relative_artifact_paths(cell)
                required_manifest_paths.update(
                    artifact_paths[name]
                    for name in ("archive", "decoded", "encode_time", "decode_time")
                )
                required_directories.add((Path("cells") / cell.slug).as_posix())
    if set(manifest_by_path) != required_manifest_paths:
        raise HarnessError("publication artifact manifest binding set is inexact")
    if actual_directories != required_directories:
        raise HarnessError("publication artifact directory set is inexact")
    return complete


def validate_publication(root: Path) -> dict[str, object]:
    return _validate_publication_tree(root, authoritative=True)


def is_authoritative_publication(root: Path) -> bool:
    try:
        validate_publication(root)
    except (HarnessError, OSError):
        return False
    return True


def execute_grid(
    *,
    entries: Sequence[InventoryEntry],
    output_dir: Path,
    void_journal: Path,
    provenance: Mapping[str, object],
    orders: Sequence[int] = ORDERS,
    memories: Sequence[int] = MEMORY_MIB,
    runner: Runner = _default_runner,
    crash_after: str | None = None,
    _test_only_allow_noncanonical: bool = False,
) -> None:
    failed_cell = "setup"
    stage: Path | None = None
    publishing: Path | None = None
    final_owned = False
    try:
        if crash_after not in {
            None,
            "stage_fsynced",
            "publishing_renamed",
            "marker_committed",
            "final_renamed_before_parent_fsync",
        }:
            raise HarnessError(f"unknown crash injection point: {crash_after}")
        entry_identities = tuple(
            (
                entry.cohort,
                entry.name,
                entry.relative_path,
                entry.size_bytes,
                entry.sha256,
            )
            for entry in entries
        )
        if _test_only_allow_noncanonical:
            if runner is _default_runner:
                raise HarnessError("test-only noncanonical execution requires an injected runner")
        elif (
            entry_identities != _FROZEN_INVENTORY
            or tuple(orders) != ORDERS
            or tuple(memories) != MEMORY_MIB
        ):
            raise HarnessError("execution is not the exact frozen 27/243 canonical grid")
        verify_inventory(entries)  # every input is frozen before the first child runs
        cells = plan_grid(entries, orders, memories)
        if output_dir.exists() or output_dir.is_symlink():
            raise HarnessError(f"refusing to overwrite output directory: {output_dir}")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        _fsync_directory(output_dir.parent)
        stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=output_dir.parent))
        _fsync_directory(output_dir.parent)
        observations_path = stage / "observations.jsonl"
        with observations_path.open("w", encoding="utf-8") as observations:
            for cell in cells:
                failed_cell = cell.identifier
                result = run_cell(
                    cell,
                    stage / "cells" / cell.slug,
                    provenance,
                    runner=runner,
                )
                observations.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            observations.flush()
            os.fsync(observations.fileno())

        inventory_record = [
            {
                "cohort": entry.cohort,
                "name": entry.name,
                "relative_path": entry.relative_path,
                "path": str(entry.path.absolute()),
                "size_bytes": entry.size_bytes,
                "sha256": entry.sha256,
            }
            for entry in entries
        ]
        _write_json(
            stage / "provenance.json",
            {
                "schema": SCHEMA_VERSION,
                "provenance": provenance,
                "inventory": inventory_record,
                "orders": list(orders),
                "memory_mib": list(memories),
                "cpu_set": CPUSET,
                "observation_count": len(cells),
                "publication": "all-or-nothing",
            },
        )
        manifest = {
            "schema": SCHEMA_VERSION,
            "status": "STAGED",
            "observation_count": len(cells),
            "directories": _manifest_directories(stage),
            "entries": _manifest_entries(stage),
        }
        _write_json(stage / "MANIFEST.json", manifest)
        _fsync_tree(stage)
        if crash_after == "stage_fsynced":
            raise SimulatedCrash(crash_after)

        publishing = output_dir.parent / f".{output_dir.name}.publishing-{secrets.token_hex(16)}"
        _rename_noreplace(stage, publishing)
        stage = None
        _fsync_directory(output_dir.parent)
        if crash_after == "publishing_renamed":
            raise SimulatedCrash(crash_after)

        marker = {
            "schema": SCHEMA_VERSION,
            "status": "COMPLETE",
            "observation_count": len(cells),
            "manifest_sha256": sha256_file(publishing / "MANIFEST.json"),
            "final_namespace": str(output_dir.absolute()),
        }
        pending_marker = publishing / ".COMPLETE.pending"
        _write_json(pending_marker, marker)
        os.replace(pending_marker, publishing / "COMPLETE")
        _fsync_directory(publishing)
        _make_tree_read_only(publishing)
        _validate_publication_tree(
            publishing,
            authoritative=False,
            expected_final_namespace=output_dir,
            canonical=not _test_only_allow_noncanonical,
        )
        if crash_after == "marker_committed":
            raise SimulatedCrash(crash_after)

        _rename_noreplace(publishing, output_dir)
        publishing = None
        final_owned = True
        if crash_after == "final_renamed_before_parent_fsync":
            raise SimulatedCrash(crash_after)
        _fsync_directory(output_dir.parent)
        if _test_only_allow_noncanonical:
            _validate_publication_tree(
                output_dir,
                authoritative=True,
                canonical=False,
            )
        else:
            validate_publication(output_dir)
    except SimulatedCrash:
        if final_owned and (output_dir.exists() or output_dir.is_symlink()):
            _quarantine_visible_final(output_dir)
            final_owned = False
        raise
    except Exception as exc:
        evidence_paths = [
            str(path)
            for path in (stage, publishing, output_dir if final_owned else None)
            if path is not None and (path.exists() or path.is_symlink())
        ]
        record = {
            "schema": SCHEMA_VERSION,
            "status": "VOID",
            "failure_phase": "PRIMARY",
            "failed_cell": failed_cell,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "code_sha": provenance.get("code_sha"),
            "evidence_paths": evidence_paths,
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        try:
            _append_void(void_journal, record)
        except Exception as journal_exc:
            raise HarnessError(
                f"harness failed ({exc}); durable VOID journal also failed ({journal_exc})"
            ) from journal_exc
        cleanup_errors: list[tuple[Path, Exception]] = []
        cleanup_targets = [
            path
            for path in (stage, publishing, output_dir if final_owned else None)
            if path is not None and (path.exists() or path.is_symlink())
        ]
        for cleanup_target in cleanup_targets:
            try:
                _discard_tree(cleanup_target)
            except Exception as cleanup_exc:
                cleanup_errors.append((cleanup_target, cleanup_exc))
                cleanup_record = {
                    "schema": SCHEMA_VERSION,
                    "status": "VOID",
                    "failure_phase": "CLEANUP",
                    "failed_cell": failed_cell,
                    "error_type": type(cleanup_exc).__name__,
                    "error": str(cleanup_exc),
                    "primary_error_type": type(exc).__name__,
                    "primary_error": str(exc),
                    "code_sha": provenance.get("code_sha"),
                    "evidence_paths": [str(cleanup_target)],
                    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
                try:
                    _append_void(void_journal, cleanup_record)
                except Exception as cleanup_journal_exc:
                    raise JournaledHarnessError(
                        f"harness failed ({exc}); cleanup failed ({cleanup_exc}); "
                        f"cleanup VOID journal failed ({cleanup_journal_exc}); "
                        "primary VOID is durable"
                    ) from cleanup_journal_exc
        if cleanup_errors:
            details = "; ".join(f"{path}: {error}" for path, error in cleanup_errors)
            raise JournaledHarnessError(
                f"{exc}; cleanup failed and evidence was preserved: {details}"
            ) from exc
        raise JournaledHarnessError(str(exc)) from exc


def _command_output(argv: Sequence[str]) -> str:
    result = subprocess.run(argv, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise HarnessError(f"tool provenance command failed ({result.returncode}): {' '.join(argv)}")
    output = f"{_child_text(result.stdout)}\n{_child_text(result.stderr)}".strip()
    if not output:
        raise HarnessError(f"tool provenance command returned empty output: {' '.join(argv)}")
    return output.splitlines()[0]


def discover_tools() -> dict[str, dict[str, str]]:
    commands = {name: (name, arguments) for name, arguments in TOOL_VERSION_ARGS.items()}
    records: dict[str, dict[str, str]] = {}
    for name, (executable, version_args) in commands.items():
        path = shutil.which(executable)
        if path is None:
            raise HarnessError(f"required tool not found: {executable}")
        resolved = str(Path(path).resolve())
        records[name] = {
            "path": resolved,
            "version": _command_output((resolved, *version_args)),
            "binary_sha256": sha256_file(Path(resolved)),
        }
    return records


def exact_clean_code_sha(repo_root: Path) -> str:
    code_sha = _git_output(repo_root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise HarnessError("cannot resolve exact code SHA")
    if _git_output(repo_root, "rev-parse", "origin/main") != code_sha:
        raise HarnessError("HEAD is not exact origin/main")
    dirty = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=repo_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if dirty.returncode != 0:
        raise HarnessError(f"cannot inspect worktree state: {dirty.stderr.strip()}")
    if dirty.stdout:
        raise HarnessError("refusing outcome access from a dirty worktree")
    return code_sha


def build_provenance(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    preregistration = repo_root / PREREGISTRATION_REPO_PATH
    if (
        preregistration.is_symlink()
        or not preregistration.is_file()
        or sha256_file(preregistration) != PREREGISTRATION_SHA256
    ):
        raise HarnessError("missing or drifted pinned preregistration")
    tools = discover_tools()
    code_sha = exact_clean_code_sha(repo_root)
    prereg_blob = _git_output(
        repo_root, "rev-parse", f"{code_sha}:{PREREGISTRATION_REPO_PATH}"
    )
    if prereg_blob != PREREGISTRATION_GIT_BLOB:
        raise HarnessError("committed preregistration blob identity is wrong")
    if hashlib.sha256(
        _git_blob_bytes(repo_root, code_sha, PREREGISTRATION_REPO_PATH)
    ).hexdigest() != PREREGISTRATION_SHA256:
        raise HarnessError("committed preregistration bytes are wrong")
    prereg = {
        "path": str(preregistration),
        "repo_path": PREREGISTRATION_REPO_PATH,
        "sha256": PREREGISTRATION_SHA256,
        "git_blob_sha": PREREGISTRATION_GIT_BLOB,
    }
    harness_sha = sha256_file(Path(__file__).resolve())
    test_sha = sha256_file(Path(__file__).resolve().with_name("test_new02_oracle_grid.py"))
    inventory_sha = frozen_inventory_sha256()
    grid_sha = frozen_grid_sha256()
    provenance: dict[str, object] = {
        "code_sha": code_sha,
        "repo_root": str(repo_root),
        "harness_sha256": harness_sha,
        "test_sha256": test_sha,
        "inventory_sha256": inventory_sha,
        "grid_sha256": grid_sha,
        "preregistration": prereg,
        "tools": tools,
        "environment": {"LC_ALL": "C", "LANG": "C", "python": sys.version.split()[0]},
    }
    provenance["run_id"] = recompute_run_id(provenance)
    validate_provenance(provenance)
    return provenance


class _RecoverableArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise HarnessError(f"argument parsing failed: {message}")


def _parser() -> argparse.ArgumentParser:
    parser = _RecoverableArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--execute", action="store_true", help="explicitly permit corpus outcome access")
    action.add_argument(
        "--materialize-holdout-exe",
        action="store_true",
        help="authenticate /bin/cat and durably create the frozen holdout exe.bin before outcomes",
    )
    parser.add_argument("--world-root", type=Path)
    parser.add_argument("--tuned-root", type=Path)
    parser.add_argument("--holdout-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--void-journal", type=Path)
    return parser


def _preparse_void_journal(argv: Sequence[str]) -> Path | None:
    for index, argument in enumerate(argv):
        if argument.startswith("--void-journal="):
            value = argument.partition("=")[2]
            return Path(value) if value else None
        if argument == "--void-journal" and index + 1 < len(argv):
            return Path(argv[index + 1])
    return None


def _journal_setup_failure(
    void_journal: Path,
    exc: Exception,
    *,
    failed_cell: str,
) -> None:
    _append_void(
        void_journal,
        {
            "schema": SCHEMA_VERSION,
            "status": "VOID",
            "failure_phase": "PRIMARY",
            "failed_cell": failed_cell,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "code_sha": None,
            "evidence_paths": [],
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    preparsed_journal = _preparse_void_journal(raw_argv)
    try:
        args = _parser().parse_args(raw_argv)
    except HarnessError as exc:
        if preparsed_journal is not None:
            try:
                _journal_setup_failure(
                    preparsed_journal,
                    exc,
                    failed_cell="argument-parse",
                )
            except Exception as journal_exc:
                raise HarnessError(
                    f"{exc}; durable VOID journal also failed ({journal_exc})"
                ) from journal_exc
            raise JournaledHarnessError(str(exc)) from exc
        raise
    try:
        if args.materialize_holdout_exe:
            materialize_holdout_exe(args.holdout_root)
            return 0
        required = {
            "--world-root": args.world_root,
            "--tuned-root": args.tuned_root,
            "--repo-root": args.repo_root,
            "--output-dir": args.output_dir,
            "--void-journal": args.void_journal,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise HarnessError(f"--execute missing required arguments: {', '.join(missing)}")
        roots = {"world": args.world_root, "tuned": args.tuned_root, "holdout": args.holdout_root}
        entries = canonical_inventory(roots)
        provenance = build_provenance(args.repo_root)
        execute_grid(
            entries=entries,
            output_dir=args.output_dir,
            void_journal=args.void_journal,
            provenance=provenance,
        )
        return 0
    except JournaledHarnessError:
        raise
    except Exception as exc:
        if args.void_journal is None:
            raise
        try:
            _journal_setup_failure(args.void_journal, exc, failed_cell="setup")
        except Exception as journal_exc:
            raise HarnessError(
                f"harness setup failed ({exc}); durable VOID journal also failed ({journal_exc})"
            ) from journal_exc
        raise JournaledHarnessError(str(exc)) from exc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
