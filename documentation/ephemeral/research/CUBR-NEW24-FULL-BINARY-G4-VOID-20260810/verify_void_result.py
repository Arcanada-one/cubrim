#!/usr/bin/env python3
"""Fail-closed verifier for the immutable full-binary G4 VOID result."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


class EvidenceError(RuntimeError):
    """An identity, integrity, or result-boundary check failed."""


EXPECTED_INVOCATION = "27cba50809fb4066b8915510b33a2b30"
EXPECTED_UNIT = "cubr-new24-full-binary-g4.service"
EXPECTED_FAILURE_MESSAGE = (
    "current_profile_g4_contract=HARNESS_INVALID reason=runner cgroup containment "
    "control failed: current_profile_g4_cgroup_test=FAIL"
)
EXPECTED_INPUT_SHA256 = {
    "remote-tree-manifest.tsv": "6ab89a7d8c83e8341a71a43c4379dc66c103898c13d012365cce277e93a15958",
    "unit-properties.txt": "17f5383bd0d130df4e6af42343d9833a3089dbd22265ffa372ff7faac992e8a5",
    "unit-cubr-environment.txt": "127e9b364f75b8e811f3797c4fae4c06a9bd11f6d97c428a2568ff9d91de4216",
    "systemd-journal.jsonl": "8d57ceb1a2e53c8c715dd4bdcc17c05383494c83fbdbdfae4d16f91778acea74",
    "identities.tsv": "f03884d7f423c7679f3c6a8f338a32e91f836e953dea01ac68f0d1afd29c94e4",
    "local-isolation-reproduction.txt": "c7a907979e9870c3e0e03048fac4ec42f0be3027d4ef4ababec39fb35adc66c7",
}
EXPECTED_IDENTITIES = {
    "host": "dev-ai",
    "remote_evidence_root": "/root/cubr-new24-full-binary-g4-20260809.partial",
    "main_commit": "708cda945a285526610371d812e4f54725eb6baf",
    "main_tree": "9cdad69314f94e0cc0323b1dd6fb64d34c0f677b",
    "instrument_commit": "ced543590f7529721f894011829a9d0e8f91385d",
    "instrument_tree": "bb07cbb1fd40bc61e1ab4001c17a2d52870b8239",
    "instrument_ancestor_of_main": "yes",
    "source_commit": "830a9a31deb00926a97f3fa5bd74f58003573fc0",
    "source_tree": "a2638f1a20c7654e0efde9d09f9a8807ef7523b2",
    "runner_blob": "63fcf9b26d4ff54e6857e66a3b4b87cd425503ab",
    "runner_sha256": "9db371bfab3376785744d0a1399ab79e8f033cb8f29eb920315556a23e821f32",
    "runner_test_blob": "0e057269d64fe4ecca8099928c44d7fe9905c480",
    "runner_test_sha256": "1da8ac44536547d70ab769907954d6e4088618865584db0ed53b057fefb7c1b3",
    "mapper_blob": "b0ee509b1909c4f77dcd11490626f9d1d06773b6",
    "mapper_sha256": "36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1",
    "mapper_test_blob": "b6e546413ebd56d423abd6b24744476c0f6e2f6f",
    "mapper_test_sha256": "97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314",
}
EXPECTED_UNIT_PROPERTIES = {
    "Type": "exec",
    "Restart": "no",
    "RuntimeMaxUSec": "4h",
    "MainPID": "0",
    "Result": "exit-code",
    "NRestarts": "0",
    "ExecMainCode": "1",
    "ExecMainStatus": "2",
    "ExecStart": (
        "{ path=/root/cubr-new24-full-binary-g4-run.sh ; "
        "argv[]=/root/cubr-new24-full-binary-g4-run.sh ; ignore_errors=no ; "
        "start_time=[Mon 2026-08-10 04:01:34 CEST] ; "
        "stop_time=[Mon 2026-08-10 04:01:38 CEST] ; pid=2120492 ; "
        "code=exited ; status=2 }"
    ),
    "ControlGroup": "",
    "KillMode": "control-group",
    "KillSignal": "15",
    "FinalKillSignal": "9",
    "Id": EXPECTED_UNIT,
    "Names": EXPECTED_UNIT,
    "Description": "/root/cubr-new24-full-binary-g4-run.sh",
    "LoadState": "loaded",
    "ActiveState": "failed",
    "SubState": "failed",
    "FragmentPath": "/run/systemd/transient/cubr-new24-full-binary-g4.service",
    "UnitFileState": "transient",
    "Transient": "yes",
    "InvocationID": EXPECTED_INVOCATION,
}
EXPECTED_ENVIRONMENT = {
    "CUBR_EXPECTED_MAPPER_SHA256": EXPECTED_IDENTITIES["mapper_sha256"],
    "CUBR_EXPECTED_MAPPER_TEST_SHA256": EXPECTED_IDENTITIES["mapper_test_sha256"],
    "CUBR_EXPECTED_RUNNER_SHA256": EXPECTED_IDENTITIES["runner_sha256"],
    "CUBR_EXPECTED_TEST_SHA256": EXPECTED_IDENTITIES["runner_test_sha256"],
    "CUBR_INSTRUMENT_COMMIT": EXPECTED_IDENTITIES["instrument_commit"],
    "CUBR_INSTRUMENT_REPO": "/root/cubr-new24-full-binary-g4-instrument",
    "CUBR_SYSTEMD_UNIT": EXPECTED_UNIT,
}
EXPECTED_REPRODUCTION = {
    "schema": "current-profile-g4-isolation-reproduction-v1",
    "main_commit": EXPECTED_IDENTITIES["main_commit"],
    "runner_sha256": EXPECTED_IDENTITIES["runner_sha256"],
    "env_absent_command": (
        "env -u CUBR_SYSTEMD_UNIT bash current-profile-g4-run.sh --self-test-cgroup"
    ),
    "env_absent_rc": "0",
    "env_absent_output": "current_profile_g4_cgroup_test=PASS",
    "env_set_command": (
        "env CUBR_SYSTEMD_UNIT=cubr-new24-full-binary-g4.service bash "
        "current-profile-g4-run.sh --self-test-cgroup"
    ),
    "env_set_rc": "1",
    "env_set_output": "current_profile_g4_cgroup_test=FAIL",
    "root_cause": (
        "mock cgroup self-test inherited live CUBR_SYSTEMD_UNIT while asserting "
        "the sentinel for mock.unit"
    ),
}
MANIFEST_COLUMNS = ["type", "mode", "uid", "gid", "size_bytes", "sha256", "path"]
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
EXPECTED_PACKAGE_ROOT_FILES = set(EXPECTED_INPUT_SHA256) | {
    "result.json",
    "test_verify_void_result.py",
    "verify_void_result.py",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def read_regular_bytes(path: Path) -> bytes:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise EvidenceError(f"missing evidence file: {path.name}") from error
    require(stat.S_ISREG(mode) and not stat.S_ISLNK(mode), f"unsafe evidence file: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode), f"unsafe evidence file: {path.name}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_regular_bytes(path)).hexdigest()


def read_text(path: Path) -> str:
    return read_regular_bytes(path).decode("utf-8")


def read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(read_text(path).splitlines(), 1):
        require("=" in line, f"malformed key/value line: {path.name}:{number}")
        key, value = line.split("=", 1)
        require(key and key not in values, f"duplicate key in {path.name}: {key}")
        values[key] = value
    return values


def read_identities(path: Path) -> dict[str, str]:
    lines = read_text(path).splitlines()
    require(lines and lines[0] == "field\tvalue", "identity header mismatch")
    values: dict[str, str] = {}
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        require(len(fields) == 2, f"malformed identity row: {number}")
        key, value = fields
        require(key and key not in values, f"duplicate identity field: {key}")
        values[key] = value
    return values


def safe_relative_path(value: str) -> bool:
    if value == ".":
        return True
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def read_remote_manifest(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == MANIFEST_COLUMNS, "remote manifest header mismatch")
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), "malformed remote manifest row")
            rows.append({key: str(value) for key, value in row.items()})
    paths = [row["path"] for row in rows]
    require(paths == sorted(paths), "remote manifest paths are not sorted")
    require(len(paths) == len(set(paths)), "duplicate remote manifest path")
    for row in rows:
        relative = row["path"]
        require(safe_relative_path(relative), f"unsafe remote manifest path: {relative}")
        require(row["type"] in {"d", "f"}, f"unsupported remote manifest type: {relative}")
        expected_mode = "500" if row["type"] == "d" else "444"
        require(row["mode"] == expected_mode, f"remote manifest mode mismatch: {relative}")
        require(row["uid"] == "0" and row["gid"] == "0", f"remote manifest owner mismatch: {relative}")
        require(row["size_bytes"].isdigit(), f"remote manifest size is malformed: {relative}")
        if row["type"] == "d":
            require(row["sha256"] == "-", f"remote directory digest is not empty: {relative}")
        else:
            require(SHA256_PATTERN.fullmatch(row["sha256"]) is not None, f"remote file digest is malformed: {relative}")
    return rows


def enumerate_evidence_tree(root: Path) -> dict[str, tuple[str, Path]]:
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError as error:
        raise EvidenceError("remote evidence root is missing") from error
    require(stat.S_ISDIR(root_mode) and not stat.S_ISLNK(root_mode), "unsafe remote evidence root")
    entries: dict[str, tuple[str, Path]] = {".": ("d", root)}

    def walk(directory: Path) -> None:
        with os.scandir(directory) as children:
            for child in children:
                path = directory / child.name
                relative = path.relative_to(root).as_posix()
                mode = child.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    raise EvidenceError(f"remote evidence contains symlink: {relative}")
                if stat.S_ISDIR(mode):
                    entries[relative] = ("d", path)
                    walk(path)
                elif stat.S_ISREG(mode):
                    entries[relative] = ("f", path)
                else:
                    raise EvidenceError(f"remote evidence contains unsafe node: {relative}")

    walk(root)
    return entries


def is_prohibited_package_artifact(relative: str) -> bool:
    path = PurePosixPath(relative)
    name = path.name
    return (
        relative == "cells"
        or relative.startswith("cells/")
        or name in {"COMPLETE", "TIMING-DONE.STAMP", "evidence-sha256.tsv"}
        or name.startswith("campaign-performance")
        or name.startswith("db-")
        or name.endswith((".data", ".sql", ".record.json"))
        or ".perf-script." in name
    )


def validate_package_boundary(package: Path) -> None:
    rows = read_remote_manifest(package / "remote-tree-manifest.tsv")
    actual = enumerate_evidence_tree(package)
    for relative in sorted(actual):
        if relative != "." and not relative.startswith("remote-evidence/"):
            require(
                not is_prohibited_package_artifact(relative),
                f"prohibited package artifact present: {relative}",
            )
    expected: dict[str, str] = {".": "d", "remote-evidence": "d"}
    expected.update({name: "f" for name in EXPECTED_PACKAGE_ROOT_FILES})
    for row in rows:
        if row["path"] != ".":
            expected[f"remote-evidence/{row['path']}"] = row["type"]
    require(set(actual) == set(expected), "package path set mismatch")
    for relative, expected_type in expected.items():
        require(actual[relative][0] == expected_type, f"package node type mismatch: {relative}")


def is_campaign_performance_artifact(relative: str) -> bool:
    path = PurePosixPath(relative)
    name = path.name
    return (
        relative.startswith("cells/")
        or name.endswith(".data")
        or name in {"TIMING-DONE.STAMP", "evidence-sha256.tsv"}
        or ".perf-script." in name
        or name.endswith(".record.json")
    )


def validate_remote_evidence(package: Path) -> dict[str, Any]:
    manifest_path = package / "remote-tree-manifest.tsv"
    rows = read_remote_manifest(manifest_path)
    actual = enumerate_evidence_tree(package / "remote-evidence")
    for relative, (node_type, _) in sorted(actual.items()):
        if node_type == "f" and is_campaign_performance_artifact(relative):
            raise EvidenceError(f"campaign performance artifact present: {relative}")
    manifested = {row["path"]: row for row in rows}
    require(set(manifested) == set(actual), "remote evidence path set mismatch")
    for relative, row in manifested.items():
        actual_type, path = actual[relative]
        require(actual_type == row["type"], f"remote evidence type mismatch: {relative}")
        if actual_type == "f":
            size = path.stat().st_size
            require(size == int(row["size_bytes"]), f"remote evidence size mismatch: {relative}")
            require(sha256_file(path) == row["sha256"], f"remote evidence checksum mismatch: {relative}")
    files = [row for row in rows if row["type"] == "f"]
    directories = [row for row in rows if row["type"] == "d"]
    empty = sorted(row["path"] for row in files if row["size_bytes"] == "0")
    require(len(files) == 18, "remote evidence file count mismatch")
    require(len(directories) == 2, "remote evidence directory count mismatch")
    require(sum(int(row["size_bytes"]) for row in files) == 72_861, "remote evidence byte count mismatch")
    require(
        empty == ["preflight/process-conflicts.txt", "preflight/runner-contract-test.txt"],
        "remote evidence empty-file set mismatch",
    )
    raw = package / "remote-evidence"
    failure = read_kv(raw / "FAILED.STAMP")
    require(
        failure
        == {
            "status": "VOID",
            "failed_at": "2026-08-10T02:01:38Z",
            "cell": "none",
            "reason": "command failed rc=2",
            "command": 'return "$rc"',
        },
        "FAILED.STAMP mismatch",
    )
    journal_lines = read_text(raw / "preflight" / "journal.tsv").splitlines()
    require(
        journal_lines[-2:]
        == [
            "2026-08-10T02:01:37Z\tdeadline_gate=admission-runner-contract remaining=14277",
            '2026-08-10T02:01:38Z\terror_rc=2 command=return "$rc"',
        ],
        "preflight journal terminal records mismatch",
    )
    require(
        read_text(raw / "preflight" / "systemd-contract.txt")
        == "Type=exec Restart=no RuntimeMaxSec=4h KillMode=control-group KillSignal=SIGTERM FinalKillSignal=SIGKILL\n"
        "ControlGroup=/system.slice/cubr-new24-full-binary-g4.service\n"
        "cgroup.procs=/sys/fs/cgroup/system.slice/cubr-new24-full-binary-g4.service/cgroup.procs\n",
        "preflight systemd contract mismatch",
    )
    return {
        "file_count": len(files),
        "directory_count": len(directories),
        "total_file_bytes": sum(int(row["size_bytes"]) for row in files),
        "empty_files": empty,
        "failure": failure,
    }


def validate_unit(package: Path) -> tuple[dict[str, str], dict[str, str]]:
    properties = read_kv(package / "unit-properties.txt")
    for key, expected in EXPECTED_UNIT_PROPERTIES.items():
        require(properties.get(key) == expected, f"unit {key} mismatch")
    require(set(properties) == set(EXPECTED_UNIT_PROPERTIES), "unit property key set mismatch")
    environment = read_kv(package / "unit-cubr-environment.txt")
    for key, expected in EXPECTED_ENVIRONMENT.items():
        require(environment.get(key) == expected, f"unit environment {key} mismatch")
    require(set(environment) == set(EXPECTED_ENVIRONMENT), "unit environment key set mismatch")
    return properties, environment


def validate_journal(package: Path) -> dict[str, str]:
    lines = read_text(package / "systemd-journal.jsonl").splitlines()
    require(len(lines) == 1, "systemd journal record count mismatch")
    record = json.loads(lines[0])
    require(isinstance(record, dict), "systemd journal record is not an object")
    require(record.get("_SYSTEMD_INVOCATION_ID") == EXPECTED_INVOCATION, "journal invocation mismatch")
    require(record.get("_SYSTEMD_UNIT") == EXPECTED_UNIT, "journal unit mismatch")
    require(record.get("_HOSTNAME") == "dev-ai", "journal host mismatch")
    require(record.get("MESSAGE") == EXPECTED_FAILURE_MESSAGE, "journal failure message mismatch")
    return {key: str(value) for key, value in record.items()}


def validate_identities(package: Path, environment: dict[str, str]) -> dict[str, str]:
    identities = read_identities(package / "identities.tsv")
    for key, expected in EXPECTED_IDENTITIES.items():
        require(identities.get(key) == expected, f"identity {key} mismatch")
    require(set(identities) == set(EXPECTED_IDENTITIES), "identity key set mismatch")
    require(
        environment["CUBR_INSTRUMENT_COMMIT"] == identities["instrument_commit"],
        "instrument identity/environment mismatch",
    )
    for name in ("runner", "mapper", "runner_test", "mapper_test"):
        environment_key = "CUBR_EXPECTED_TEST_SHA256" if name == "runner_test" else f"CUBR_EXPECTED_{name.upper()}_SHA256"
        require(environment[environment_key] == identities[f"{name}_sha256"], f"{name} hash/environment mismatch")
    return identities


def validate_reproduction(package: Path) -> dict[str, str]:
    reproduction = read_kv(package / "local-isolation-reproduction.txt")
    for key, expected in EXPECTED_REPRODUCTION.items():
        require(reproduction.get(key) == expected, f"isolation reproduction {key} mismatch")
    require(set(reproduction) == set(EXPECTED_REPRODUCTION), "isolation reproduction key set mismatch")
    return reproduction


def expected_result(remote: dict[str, Any], identities: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "cubr-new24-full-binary-g4-void-result-v1",
        "verdict": {
            "profile_status": "VOID",
            "selection": "NO-SELECT",
            "failure_class": "HARNESS-ISOLATION-FAILURE",
            "reason_code": "RUNNER_MOCK_CGROUP_TEST_INHERITED_LIVE_UNIT",
            "reason": (
                "The mock cgroup self-test inherited the live CUBR_SYSTEMD_UNIT value, "
                "but asserted the mock.unit stop sentinel."
            ),
            "performance_conclusion_admissible": False,
        },
        "campaign_boundary": {
            "failure_phase": "admission-runner-contract",
            "failed_at_utc": remote["failure"]["failed_at"],
            "campaign_cell_count": 0,
            "performance_sample_count": 0,
            "performance_sample_artifact_count": 0,
            "authoritative_completion_marker_present": False,
            "preflight_event_support_probes_present": True,
        },
        "systemd": {
            "unit": EXPECTED_UNIT,
            "invocation_id": EXPECTED_INVOCATION,
            "result": "exit-code",
            "exec_main_status": 2,
            "nrestarts": 0,
            "service_type": "exec",
            "restart_policy": "no",
            "runtime_max": "4h",
            "kill_mode": "control-group",
        },
        "identities": {
            key: identities[key]
            for key in (
                "main_commit",
                "main_tree",
                "instrument_commit",
                "instrument_tree",
                "source_commit",
                "source_tree",
                "runner_sha256",
                "runner_test_sha256",
                "mapper_sha256",
                "mapper_test_sha256",
            )
        },
        "remote_evidence": {
            "host": identities["host"],
            "source_root": identities["remote_evidence_root"],
            "file_count": remote["file_count"],
            "directory_count": remote["directory_count"],
            "total_file_bytes": remote["total_file_bytes"],
            "empty_files": remote["empty_files"],
            "remote_directory_mode": "0500",
            "remote_file_mode": "0444",
        },
        "isolation_reproduction": {
            "environment_absent": {"exit_code": 0, "result": "PASS"},
            "live_unit_environment_set": {"exit_code": 1, "result": "FAIL"},
        },
        "publication_limits": {
            "scope": "failure identity, immutable evidence, and harness root cause only",
            "performance_interpretation_performed": False,
            "prediction_evaluation_performed": False,
            "database_mutation_performed": False,
            "api_mutation_performed": False,
            "site_mutation_performed": False,
            "backlog_mutation_performed": False,
            "campaign_rerun_performed": False,
        },
    }


def validate_input_hashes(package: Path) -> None:
    for name, expected in EXPECTED_INPUT_SHA256.items():
        require(sha256_file(package / name) == expected, f"evidence input checksum mismatch: {name}")


def verify(package: Path) -> dict[str, Any]:
    try:
        package_mode = package.lstat().st_mode
    except FileNotFoundError as error:
        raise EvidenceError("package directory is missing") from error
    require(stat.S_ISDIR(package_mode) and not stat.S_ISLNK(package_mode), "unsafe package directory")
    remote = validate_remote_evidence(package)
    validate_package_boundary(package)
    _, environment = validate_unit(package)
    validate_journal(package)
    identities = validate_identities(package, environment)
    validate_reproduction(package)
    result = expected_result(remote, identities)
    recorded = json.loads(read_text(package / "result.json"))
    require(recorded == result, "result.json drift")
    validate_input_hashes(package)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.package)
    except (EvidenceError, OSError, UnicodeError, csv.Error, json.JSONDecodeError, ValueError) as error:
        print(f"VOID EVIDENCE INVALID: {error}", file=sys.stderr)
        return 2
    print(f"{result['verdict']['profile_status']} / {result['verdict']['selection']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
