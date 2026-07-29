#!/usr/bin/env python3
"""Run the ratio reproduction as an append-only journal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import string
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ARCHIVERS = frozenset(
    {"cubrim", "gzip", "bzip2", "xz", "zstd", "brotli", "lz4", "ppmd", "7z", "rar"}
)
ALLOWED_PLACEHOLDERS = frozenset(
    {
        "archive",
        "cubrim",
        "rar",
        "restore_dir",
        "restored",
        "source",
        "source_name",
        "unrar",
    }
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
META_ID = 35
RELEASE_COMMIT = "dfb195ef089db738e51153ad4532fdd583f247bf"


class CommandError(ValueError):
    """Raised for an unsafe or malformed command template."""


@dataclass(frozen=True)
class Commands:
    compress: tuple[str, ...]
    decompress: tuple[str, ...]
    cwd: Path | None
    kind: str
    restored: Path


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("x", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        self._handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_templates(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or data.get("meta_id") != META_ID
        or data.get("release_commit") != RELEASE_COMMIT
    ):
        raise CommandError("template identity mismatch")
    archivers = data.get("archivers")
    if not isinstance(archivers, dict) or set(archivers) != ARCHIVERS:
        raise CommandError("template archiver set mismatch")
    return archivers


def _render(arguments: object, values: dict[str, str]) -> tuple[str, ...]:
    if not isinstance(arguments, list) or not arguments:
        raise CommandError("command must be a nonempty argv list")
    rendered: list[str] = []
    formatter = string.Formatter()
    for argument in arguments:
        if not isinstance(argument, str) or not argument or argument != argument.strip():
            raise CommandError("command arguments must be nonempty trimmed strings")
        for _, field, _, _ in formatter.parse(argument):
            if field is not None and field not in ALLOWED_PLACEHOLDERS:
                raise CommandError(f"unknown placeholder: {field}")
        try:
            value = argument.format_map(values)
        except KeyError as error:
            raise CommandError(f"unknown placeholder: {error.args[0]}") from error
        if "{" in value or "}" in value:
            raise CommandError(f"unresolved placeholder in {value!r}")
        rendered.append(value)
    return tuple(rendered)


def build_commands(
    archiver: str,
    template: dict[str, Any],
    *,
    source: Path,
    archive: Path,
    restore_dir: Path,
    tools_dir: Path,
) -> Commands:
    kind = template.get("kind")
    if kind not in {"archive", "direct", "stream"}:
        raise CommandError(f"invalid kind for {archiver}")
    if template.get("source_cwd") not in {True, False}:
        raise CommandError(f"invalid source_cwd for {archiver}")
    values = {
        "archive": str(archive),
        "cubrim": str(tools_dir / "cubrim"),
        "rar": str(tools_dir / "rar"),
        "restore_dir": str(restore_dir),
        "restored": str(restore_dir / source.name),
        "source": str(source),
        "source_name": source.name,
        "unrar": str(tools_dir / "unrar"),
    }
    return Commands(
        compress=_render(template.get("compress"), values),
        decompress=_render(template.get("decompress"), values),
        cwd=source.parent if template["source_cwd"] else None,
        kind=kind,
        restored=restore_dir / source.name,
    )


def _run_command(
    arguments: tuple[str, ...],
    *,
    cwd: Path | None,
    stdout_path: Path | None,
    timeout: int,
) -> int:
    if stdout_path is None:
        completed = subprocess.run(
            arguments,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    else:
        with stdout_path.open("xb") as output:
            completed = subprocess.run(
                arguments,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
    return completed.returncode


def load_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 24:
        raise CommandError(f"manifest must contain 24 rows, got {len(rows)}")
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        if not SAFE_NAME.fullmatch(row["corpus"]) or not SAFE_NAME.fullmatch(row["file"]):
            raise CommandError("manifest contains an unsafe path component")
        identity = (row["corpus"], row["file"])
        if identity in seen:
            raise CommandError(f"duplicate manifest row: {identity!r}")
        seen.add(identity)
        result.append({**row, "orig": int(row["orig"])})
    return result


def run_benchmark(workspace: Path, package_root: Path, timeout: int) -> tuple[Path, Path]:
    workspace = workspace.resolve(strict=True)
    if workspace == Path("/"):
        raise CommandError("workspace cannot be the filesystem root")
    manifest_path = package_root / "corpus_manifest.tsv"
    templates_path = package_root / "archiver_templates.json"
    manifest = load_manifest(manifest_path)
    templates = load_templates(templates_path)
    tools_dir = workspace / "tools"
    for tool in ("cubrim", "rar", "unrar"):
        path = tools_dir / tool
        if not path.is_file() or not os.access(path, os.X_OK):
            raise CommandError(f"missing executable: {path}")

    run_id = datetime.now(UTC).strftime("cubr0069-%Y%m%dT%H%M%SZ")
    results_dir = workspace / "results"
    work_dir = results_dir / f"{run_id}.work"
    work_dir.mkdir(parents=True, exist_ok=False)
    journal_path = results_dir / f"{run_id}.journal.jsonl"
    sidecar_path = results_dir / f"{run_id}.journal.sha256.json"
    sample_count = 0
    with Journal(journal_path) as journal:
        journal.append(
            {
                "kind": "run_meta",
                "manifest_sha256": sha256(manifest_path),
                "meta_id": META_ID,
                "release_commit": RELEASE_COMMIT,
                "run_id": run_id,
                "schema_version": 1,
                "template_sha256": sha256(templates_path),
            }
        )
        for item in manifest:
            source = workspace / "corpus" / item["corpus"] / item["file"]
            if (
                not source.is_file()
                or source.stat().st_size != item["orig"]
                or sha256(source) != item["sha256"]
            ):
                raise CommandError(f"corpus manifest mismatch: {source}")
            for archiver in sorted(ARCHIVERS):
                row_dir = work_dir / item["corpus"] / item["file"] / archiver
                restore_dir = row_dir / "restored"
                restore_dir.mkdir(parents=True)
                archive = row_dir / f"archive{templates[archiver]['archive_suffix']}"
                commands = build_commands(
                    archiver,
                    templates[archiver],
                    source=source,
                    archive=archive,
                    restore_dir=restore_dir,
                    tools_dir=tools_dir,
                )
                identity = {
                    "archiver": archiver,
                    "corpus": item["corpus"],
                    "file": item["file"],
                }
                journal.append({"kind": "sample_start", **identity})
                encode_rc = _run_command(
                    commands.compress,
                    cwd=commands.cwd,
                    stdout_path=archive if commands.kind == "stream" else None,
                    timeout=timeout,
                )
                decode_rc = -1
                cmp_rc = -1
                if encode_rc == 0 and archive.is_file():
                    decode_rc = _run_command(
                        commands.decompress,
                        cwd=commands.cwd,
                        stdout_path=commands.restored
                        if commands.kind == "stream"
                        else None,
                        timeout=timeout,
                    )
                    if decode_rc == 0 and commands.restored.is_file():
                        cmp_rc = subprocess.run(
                            ("cmp", "--", str(source), str(commands.restored)),
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                            check=False,
                        ).returncode
                if (encode_rc, decode_rc, cmp_rc) != (0, 0, 0):
                    journal.append(
                        {
                            "cmp": cmp_rc,
                            "decode_rc": decode_rc,
                            "encode_rc": encode_rc,
                            "kind": "error",
                            **identity,
                        }
                    )
                    raise RuntimeError(f"benchmark failed for {identity!r}")
                journal.append(
                    {
                        "archive_bytes": archive.stat().st_size,
                        "archiver": archiver,
                        "cmp": 0,
                        "corpus": item["corpus"],
                        "decode_rc": 0,
                        "encode_rc": 0,
                        "file": item["file"],
                        "kind": "sample",
                        "orig": item["orig"],
                        "round_trip_ok": True,
                        "type": item["type"],
                    }
                )
                sample_count += 1
        journal.append({"kind": "summary", "sample_count": sample_count, "status": "OK"})

    sidecar_path.write_text(
        json.dumps(
            {"journal_sha256": sha256(journal_path), "schema_version": 1},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return journal_path, sidecar_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    journal, sidecar = run_benchmark(args.workspace, package_root, args.timeout)
    print(json.dumps({"journal": str(journal), "sidecar": str(sidecar)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
