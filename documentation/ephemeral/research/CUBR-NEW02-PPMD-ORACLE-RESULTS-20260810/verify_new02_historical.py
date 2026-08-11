#!/usr/bin/env python3
"""Standalone, version-frozen historical validator for the NEW-02 raw publication.

Why this exists
---------------
The capture harness authenticates provenance with

    rev-parse HEAD == code_sha AND rev-parse origin/main == code_sha

That predicate is correct at *capture* time -- it stops a campaign running on
anything but exact main. It is wrong at *validation* time, because it binds
authentication to a moving branch ref: once `origin/main` advances past the
execution commit the check can never pass again, and it degrades further with
every merge.

This module replaces that single mutable predicate with a stable one. It asks
whether the frozen execution commit *exists* and whether its recorded objects
match their frozen identities -- properties that are monotone and true forever
once true. Everything else the harness proved about the immutable raw tree is
re-proven here directly, with no import of the capture harness.

Boundaries (unchanged from the capture contract)
------------------------------------------------
This validator authenticates *stored* claims. It never re-runs 7-Zip, decodes
an archive, compares source bytes, or reproduces GNU time. Fresh tool execution
remains a property of the original canonical harness only. It cannot make
supplemental evidence canonical, and it issues no product selection.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

SCHEMA_VERSION = "new02-ppmd-oracle-v1"
ORDERS = (4, 6, 8)
MEMORY_MIB = (16, 64, 256)
CPUSET = "0-15"
OBSERVATION_COUNT = 243

# --- frozen identities -----------------------------------------------------
# The execution commit is a FROZEN constant, never a branch ref. This is the
# whole point of the module.
EXECUTION_COMMIT = "708cda945a285526610371d812e4f54725eb6baf"
EXECUTION_TREE = "9cdad69314f94e0cc0323b1dd6fb64d34c0f677b"

SOURCE_BASENAME = "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
SOURCE_FINAL_NAMESPACE = (
    "/home/dev/cubr-new02-canonical-runs/"
    "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
)
SOURCE_RUN_ID = "4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba"
SOURCE_INVENTORY_SHA256 = (
    "77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda"
)
SOURCE_GRID_SHA256 = (
    "8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4"
)

# Repo-relative paths and their frozen Git blob ids / content hashes at the
# execution commit. Resolved through `git rev-parse <commit>:<path>`, never
# through the working tree and never through a branch ref.
PREREGISTRATION_REPO_PATH = (
    "documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md"
)
HARNESS_REPO_PATH = "documentation/ephemeral/research/new02_oracle_grid.py"
HARNESS_TEST_REPO_PATH = (
    "documentation/ephemeral/research/test_new02_oracle_grid.py"
)
FROZEN_OBJECTS = {
    PREREGISTRATION_REPO_PATH: {
        "blob": "d96df7e3478a6ba52b737ef30dea63d68b0e01ac",
        "size": 7651,
        "sha256": "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093",
    },
    HARNESS_REPO_PATH: {
        "blob": "3acaa4a5fc2b5622404f041a28575cbf9ad10bd5",
        "size": 84669,
        "sha256": "35c2f7eb7dc7f3ef5008136b7658607342273df36c8c9b13d3fdeda80f3143c5",
    },
    HARNESS_TEST_REPO_PATH: {
        "blob": "ccf6613b13aa178eb1bb6a0896e5ea8b0276e10b",
        "size": 58121,
        "sha256": "35be4a2cdcf5f09487eddd542966c3435bedf40874e6b081fe282b6edb8eb005",
    },
}

SOURCE_TOP_HASHES = {
    "COMPLETE": "9db58ad5bfa01bfeaff2f46807d0645baa2e002cd1ed930585fcefb2ce177d06",
    "MANIFEST.json": "4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c",
    "provenance.json": "42caafdbcf13c37e3f7b6f57f62a1923c35c470bf2c22bda04d645b3f1b6fc6b",
    "observations.jsonl": "7622bb1eed1199f98c599cdad588340fcffc3df74b03eef32f37b16c4eabe75c",
}

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SHA1_RE = re.compile(r"[0-9a-f]{40}")


class HistoricalValidationError(Exception):
    """Raised for every failed predicate. Never caught internally."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise HistoricalValidationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HistoricalValidationError(
            f"git {' '.join(args)} failed: {exc}"
        ) from exc
    return completed.stdout.strip()


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HistoricalValidationError(
            f"git {' '.join(args)} failed: {exc}"
        ) from exc
    return completed.stdout


# --- repository boundary ---------------------------------------------------


def authenticate_repository(repo_root: Path) -> Mapping[str, object]:
    """Authenticate the frozen execution objects without consulting any branch ref.

    The harness asked "is the current checkout exactly origin/main, and is that
    the code_sha?". That is unanswerable once main advances. This asks instead:

      * does the frozen execution commit still exist, with its frozen tree?
      * do its recorded blobs still carry their frozen ids, sizes and hashes?
      * is it still contained in the repository's history?

    All three are monotone: once true they stay true no matter how far main
    advances, which is exactly the property a historical validator needs.
    """
    repo_root = Path(repo_root).resolve()
    _require(
        repo_root.is_dir() and not repo_root.is_symlink(),
        "repository root is not a real directory",
    )
    _require(
        (repo_root / ".git").exists(),
        "repository root is not a Git repository",
    )

    commit_type = _git(repo_root, "cat-file", "-t", EXECUTION_COMMIT)
    _require(
        commit_type == "commit",
        f"frozen execution commit is not a commit object: {commit_type!r}",
    )
    tree = _git(repo_root, "rev-parse", f"{EXECUTION_COMMIT}^{{tree}}")
    _require(
        tree == EXECUTION_TREE,
        "frozen execution commit does not carry its frozen tree",
    )

    # Containment, not equality. An advanced main still contains the commit;
    # a repository that never had it, or that rewrote it away, does not.
    contained = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor",
         EXECUTION_COMMIT, "origin/main"],
        capture_output=True,
    )
    _require(
        contained.returncode == 0,
        "frozen execution commit is not contained in origin/main history",
    )

    resolved = {}
    for repo_path, frozen in sorted(FROZEN_OBJECTS.items()):
        blob = _git(repo_root, "rev-parse", f"{EXECUTION_COMMIT}:{repo_path}")
        _require(
            SHA1_RE.fullmatch(blob) is not None,
            f"frozen object id is not a Git blob id: {repo_path}",
        )
        _require(
            blob == frozen["blob"],
            f"frozen object blob id drifted at the execution commit: {repo_path}",
        )
        payload = _git_bytes(repo_root, "cat-file", "blob", blob)
        _require(
            len(payload) == frozen["size"],
            f"frozen object size drifted: {repo_path}",
        )
        _require(
            hashlib.sha256(payload).hexdigest() == frozen["sha256"],
            f"frozen object content hash drifted: {repo_path}",
        )
        resolved[repo_path] = blob

    return {
        "execution_commit": EXECUTION_COMMIT,
        "execution_tree": EXECUTION_TREE,
        "objects": resolved,
    }


# --- frozen contract recomputation -----------------------------------------


def inventory_identity(inventory: Sequence[Mapping[str, object]]) -> str:
    records = [
        [
            item["cohort"],
            item["name"],
            item["relative_path"],
            item["size_bytes"],
            item["sha256"],
        ]
        for item in inventory
    ]
    payload = json.dumps(records, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def grid_identity(inventory: Sequence[Mapping[str, object]]) -> str:
    records = [
        [
            item["cohort"],
            item["name"],
            item["relative_path"],
            item["size_bytes"],
            item["sha256"],
            order,
            memory,
            CPUSET,
        ]
        for item in inventory
        for order in ORDERS
        for memory in MEMORY_MIB
    ]
    payload = json.dumps(records, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def expected_ppmd_memory_exponent(input_bytes: int, requested_memory_mib: int) -> int:
    """Exact exponent 7-Zip records after its small-input memory cap."""
    _require(input_bytes > 0, "PPMd input must be non-empty")
    _require(
        requested_memory_mib > 0
        and not (requested_memory_mib & (requested_memory_mib - 1)),
        "PPMd memory must be a positive power of two MiB",
    )
    requested_exponent = 20 + requested_memory_mib.bit_length() - 1
    input_capped_exponent = max(16, (input_bytes * 16 - 1).bit_length())
    return min(requested_exponent, input_capped_exponent)


# --- immutable raw-publication boundary ------------------------------------


def _load_json_object(path: Path, label: str) -> Mapping[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalValidationError(f"{label} is not readable JSON") from exc
    _require(isinstance(document, dict), f"{label} is not a JSON object")
    return document


def validate_raw_publication(root: Path) -> Mapping[str, object]:
    """Fail-closed validation of the immutable raw tree, offline and read-only."""
    root = Path(root).resolve()
    _require(
        not root.is_symlink() and root.is_dir(),
        "publication root is not a regular directory",
    )
    _require(
        root.name == SOURCE_BASENAME and str(root) == SOURCE_FINAL_NAMESPACE,
        "publication is not in its registered final namespace",
    )

    # Top-level identities first: once these hold, everything parsed below is
    # authenticated by hash rather than trusted.
    for name, expected in sorted(SOURCE_TOP_HASHES.items()):
        path = root / name
        _require(path.is_file(), f"publication top-level file is missing: {name}")
        _require(
            sha256_file(path) == expected,
            f"publication top hash mismatch: {name}",
        )

    void_siblings = sorted(
        entry.name for entry in root.parent.iterdir() if "void" in entry.name.lower()
    )
    _require(
        not void_siblings,
        "publication parent contains a VOID-named record: " + ", ".join(void_siblings),
    )

    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    writable: list[str] = []
    for path in [root, *root.rglob("*")]:
        mode = path.lstat().st_mode
        if mode & 0o222:
            writable.append(path.relative_to(root).as_posix())
        if path == root:
            continue
        if stat.S_ISDIR(mode):
            actual_directories.add(path.relative_to(root).as_posix())
            continue
        _require(
            stat.S_ISREG(mode),
            f"publication contains a special file: {path.relative_to(root)}",
        )
        actual_files.add(path.relative_to(root).as_posix())
    _require(not writable, f"publication contains a writable node: {writable[:1]}")

    manifest = _load_json_object(root / "MANIFEST.json", "manifest")
    _require(
        set(manifest)
        == {"schema", "status", "observation_count", "directories", "entries"},
        "publication manifest has an inexact schema",
    )
    _require(
        manifest.get("schema") == SCHEMA_VERSION,
        "publication manifest has an invalid schema identity",
    )
    entries = manifest.get("entries")
    directories = manifest.get("directories")
    _require(isinstance(entries, list) and entries, "manifest entries are invalid")
    _require(isinstance(directories, list), "manifest directories are invalid")
    _require(
        directories == sorted(set(directories)),
        "manifest directories are not sorted and unique",
    )
    _require(
        actual_directories == set(directories),
        "manifest directory set does not match the tree",
    )

    expected_files = {"MANIFEST.json", "COMPLETE"}
    previous = ""
    for entry in entries:
        _require(
            isinstance(entry, dict) and set(entry) == {"path", "size_bytes", "sha256"},
            "manifest entry has an inexact schema",
        )
        relative = entry["path"]
        _require(
            isinstance(relative, str)
            and relative
            and relative > previous
            and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts,
            "manifest path order or shape is invalid",
        )
        _require(
            type(entry["size_bytes"]) is int and entry["size_bytes"] >= 0,
            f"manifest size is invalid: {relative}",
        )
        _require(
            isinstance(entry["sha256"], str)
            and SHA256_RE.fullmatch(entry["sha256"]) is not None,
            f"manifest hash is malformed: {relative}",
        )
        previous = relative
        path = root / relative
        _require(
            relative not in expected_files and path.is_file(),
            f"manifest file set is invalid: {relative}",
        )
        _require(
            path.stat().st_size == entry["size_bytes"]
            and sha256_file(path) == entry["sha256"],
            f"manifest hash/size mismatch: {relative}",
        )
        expected_files.add(relative)
    _require(
        actual_files == expected_files,
        "manifest file set does not match the directory",
    )

    observation_count = manifest.get("observation_count")
    _require(
        observation_count == OBSERVATION_COUNT,
        "manifest observation count is not the frozen 243",
    )

    try:
        rows = [
            json.loads(line)
            for line in (root / "observations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalValidationError("publication observations are invalid") from exc
    _require(
        len(rows) == OBSERVATION_COUNT,
        "observation row count does not match the frozen 243",
    )
    for row in rows:
        _require(
            isinstance(row, dict)
            and row.get("schema") == SCHEMA_VERSION
            and row.get("round_trip") is True,
            "an observation row is invalid or not round-trip true",
        )

    provenance = _load_json_object(root / "provenance.json", "provenance")
    _require(
        set(provenance)
        == {
            "schema",
            "provenance",
            "inventory",
            "orders",
            "memory_mib",
            "cpu_set",
            "observation_count",
            "publication",
        },
        "publication provenance has an inexact schema",
    )
    inventory = provenance.get("inventory")
    _require(isinstance(inventory, list) and inventory, "provenance inventory is invalid")
    _require(
        provenance.get("schema") == SCHEMA_VERSION
        and provenance.get("cpu_set") == CPUSET
        and provenance.get("publication") == "all-or-nothing"
        and provenance.get("observation_count") == OBSERVATION_COUNT
        and provenance.get("orders") == list(ORDERS)
        and provenance.get("memory_mib") == list(MEMORY_MIB),
        "provenance identity does not match the frozen contract",
    )
    _require(
        len(inventory) * len(ORDERS) * len(MEMORY_MIB) == OBSERVATION_COUNT,
        "provenance grid dimensions do not multiply to the observation count",
    )
    for item in inventory:
        _require(
            isinstance(item, dict)
            and set(item)
            == {"cohort", "name", "relative_path", "path", "size_bytes", "sha256"},
            "provenance inventory entry has an inexact schema",
        )
        _require(
            SHA256_RE.fullmatch(str(item["sha256"])) is not None
            and type(item["size_bytes"]) is int
            and item["size_bytes"] > 0
            and Path(str(item["path"])).is_absolute(),
            "provenance inventory entry is invalid",
        )

    # The preregistered contract, recomputed rather than trusted.
    _require(
        inventory_identity(inventory) == SOURCE_INVENTORY_SHA256,
        "inventory identity does not match the ordered frozen inventory",
    )
    _require(
        grid_identity(inventory) == SOURCE_GRID_SHA256,
        "grid identity does not match the ordered frozen 243-cell grid",
    )

    embedded = provenance.get("provenance")
    _require(isinstance(embedded, dict), "embedded provenance record is missing")
    _require(
        embedded.get("code_sha") == EXECUTION_COMMIT,
        "embedded code identity is not the frozen execution commit",
    )
    _require(
        embedded.get("run_id") == SOURCE_RUN_ID,
        "embedded run identity is not the frozen harness run id",
    )

    complete = _load_json_object(root / "COMPLETE", "completion marker")
    _require(
        set(complete)
        == {"schema", "status", "observation_count", "manifest_sha256", "final_namespace"},
        "completion marker has an inexact schema",
    )
    _require(
        complete.get("schema") == SCHEMA_VERSION
        and complete.get("status") == "COMPLETE"
        and complete.get("observation_count") == OBSERVATION_COUNT
        and complete.get("manifest_sha256") == sha256_file(root / "MANIFEST.json")
        and complete.get("final_namespace") == SOURCE_FINAL_NAMESPACE,
        "completion marker does not authenticate manifest/count/namespace",
    )

    return dict(complete)


def authenticated_inventory(raw_root: Path) -> list:
    """Return the frozen 27-entry inventory, authenticated by hash before use.

    Consumers previously reached into the capture harness for `_FROZEN_INVENTORY`.
    The same contract is available here without importing that module: the raw
    `provenance.json` is pinned by `SOURCE_TOP_HASHES`, and the inventory it
    carries is additionally re-checked against the preregistered inventory and
    grid identities, so reading it is not trusting it.
    """
    raw_root = Path(raw_root).resolve()
    path = raw_root / "provenance.json"
    _require(path.is_file(), "raw provenance.json is missing")
    _require(
        sha256_file(path) == SOURCE_TOP_HASHES["provenance.json"],
        "raw provenance.json does not match its frozen hash",
    )
    provenance = _load_json_object(path, "provenance")
    inventory = provenance.get("inventory")
    _require(isinstance(inventory, list) and inventory, "provenance inventory is invalid")
    _require(
        inventory_identity(inventory) == SOURCE_INVENTORY_SHA256,
        "inventory identity does not match the ordered frozen inventory",
    )
    _require(
        grid_identity(inventory) == SOURCE_GRID_SHA256,
        "grid identity does not match the ordered frozen 243-cell grid",
    )
    return list(inventory)


def validate_historical(repo_root: Path, raw_root: Path) -> Mapping[str, object]:
    """Both boundaries. Returns the authenticated completion marker."""
    repository = authenticate_repository(repo_root)
    marker = validate_raw_publication(raw_root)
    return {
        "HISTORICAL_VALIDATION_STATUS": "PASS",
        "repository": repository,
        "completion_marker": marker,
    }


def main(argv: Sequence[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Version-frozen historical validator for the NEW-02 raw publication"
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--raw-run", default=SOURCE_FINAL_NAMESPACE)
    args = parser.parse_args(list(argv[1:]))
    try:
        outcome = validate_historical(Path(args.repo_root), Path(args.raw_run))
    except HistoricalValidationError as failure:
        print(f"NEW02_HISTORICAL_VALIDATION=FAIL reason={failure}")
        return 1
    print(
        "NEW02_HISTORICAL_VALIDATION=PASS "
        f"execution_commit={outcome['repository']['execution_commit']} "
        f"observations={outcome['completion_marker']['observation_count']}"
    )
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
