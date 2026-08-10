#!/usr/bin/env python3
"""Contract tests for the NEW-02 PPMd oracle-grid harness."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import new02_oracle_grid as oracle


TOOLS = {
    name: {
        "path": str(Path(path).resolve()),
        "version": version,
        "binary_sha256": oracle.sha256_file(Path(path).resolve()),
    }
    for name, path, version in (
        ("7z", "/usr/bin/7z", oracle._command_output(("/usr/bin/7z", "i"))),
        ("taskset", "/usr/bin/taskset", oracle._command_output(("/usr/bin/taskset", "--version"))),
        ("time", "/usr/bin/time", oracle._command_output(("/usr/bin/time", "--version"))),
        ("cmp", "/usr/bin/cmp", oracle._command_output(("/usr/bin/cmp", "--version"))),
    )
}

EXPECTED_FROZEN_INVENTORY_SHA256 = "77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda"
EXPECTED_FROZEN_GRID_SHA256 = "8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4"
PREREG_PATH = Path(oracle.__file__).resolve().parents[3] / oracle.PREREGISTRATION_REPO_PATH
_FIXTURE_REPOSITORY_TEMPORARY: tempfile.TemporaryDirectory[str] | None = None
_FIXTURE_REPOSITORY: tuple[Path, str] | None = None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fake_gnu_time_report(elapsed: str, peak_rss_kib: int) -> str:
    return (
        '\tCommand being timed: "/usr/bin/true"\n'
        "\tUser time (seconds): 0.00\n"
        "\tSystem time (seconds): 0.00\n"
        "\tPercent of CPU this job got: 100%\n"
        f"\tElapsed (wall clock) time (h:mm:ss or m:ss): {elapsed}\n"
        "\tAverage shared text size (kbytes): 0\n"
        "\tAverage unshared data size (kbytes): 0\n"
        "\tAverage stack size (kbytes): 0\n"
        "\tAverage total size (kbytes): 0\n"
        f"\tMaximum resident set size (kbytes): {peak_rss_kib}\n"
        "\tAverage resident set size (kbytes): 0\n"
        "\tMajor (requiring I/O) page faults: 0\n"
        "\tMinor (reclaiming a frame) page faults: 0\n"
        "\tVoluntary context switches: 0\n"
        "\tInvoluntary context switches: 0\n"
        "\tSwaps: 0\n"
        "\tFile system inputs: 0\n"
        "\tFile system outputs: 0\n"
        "\tSocket messages sent: 0\n"
        "\tSocket messages received: 0\n"
        "\tSignals delivered: 0\n"
        "\tPage size (bytes): 4096\n"
        "\tExit status: 0\n"
    )


def fixture_entry(path: Path, cohort: str = "tuned") -> oracle.InventoryEntry:
    data = path.read_bytes()
    return oracle.InventoryEntry(
        cohort=cohort,
        name=path.name,
        relative_path=path.name,
        path=path,
        size_bytes=len(data),
        sha256=sha(data),
    )


def fixture_repository() -> tuple[Path, str]:
    global _FIXTURE_REPOSITORY_TEMPORARY, _FIXTURE_REPOSITORY
    if _FIXTURE_REPOSITORY is not None:
        return _FIXTURE_REPOSITORY
    _FIXTURE_REPOSITORY_TEMPORARY = tempfile.TemporaryDirectory()
    root = Path(_FIXTURE_REPOSITORY_TEMPORARY.name).resolve()
    preregistration = root / oracle.PREREGISTRATION_REPO_PATH
    preregistration.parent.mkdir(parents=True)
    shutil.copyfile(PREREG_PATH, preregistration)
    commands = (
        ("git", "init", "-q"),
        ("git", "config", "user.email", "new02-test@example.invalid"),
        ("git", "config", "user.name", "NEW-02 test fixture"),
        ("git", "add", oracle.PREREGISTRATION_REPO_PATH),
        ("git", "commit", "-q", "-m", "synthetic prereg fixture"),
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    code_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    subprocess.run(
        ("git", "update-ref", "refs/remotes/origin/main", code_sha),
        cwd=root,
        check=True,
    )
    _FIXTURE_REPOSITORY = (root, code_sha)
    return _FIXTURE_REPOSITORY


def fixture_provenance(**overrides: object) -> dict[str, object]:
    repo_root, code_sha = fixture_repository()
    preregistration = repo_root / oracle.PREREGISTRATION_REPO_PATH
    value: dict[str, object] = {
        "code_sha": code_sha,
        "repo_root": str(repo_root),
        "harness_sha256": oracle.sha256_file(Path(oracle.__file__).resolve()),
        "test_sha256": oracle.sha256_file(Path(__file__).resolve()),
        "inventory_sha256": EXPECTED_FROZEN_INVENTORY_SHA256,
        "grid_sha256": EXPECTED_FROZEN_GRID_SHA256,
        "tools": TOOLS,
        "preregistration": {
            "path": str(preregistration),
            "repo_path": oracle.PREREGISTRATION_REPO_PATH,
            "sha256": oracle.PREREGISTRATION_SHA256,
            "git_blob_sha": oracle.PREREGISTRATION_GIT_BLOB,
        },
        "environment": {"LC_ALL": "C", "LANG": "C", "python": sys.version.split()[0]},
    }
    value.update(overrides)
    if "run_id" not in overrides:
        value["run_id"] = oracle.recompute_run_id(value)
    return value


class FakeRunner:
    """Small command seam: no compressor or corpus outcome is accessed."""

    def __init__(self, source_by_name: dict[str, bytes], fail_on_call: int | None = None):
        self.source_by_name = source_by_name
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.archive_sources: dict[str, bytes] = {}
        self.archive_names: dict[str, str] = {}
        self.archive_methods: dict[str, str] = {}

    def __call__(self, phase: str, argv: tuple[str, ...], stdout_path: Path | None):
        self.calls.append((phase, argv))
        if self.fail_on_call == len(self.calls):
            return subprocess.CompletedProcess(argv, 17, "", "injected child failure")

        if phase == "encode":
            report = Path(argv[argv.index("-o") + 1])
            archive = Path(argv[-2])
            source = Path(argv[-1])
            report.write_text(fake_gnu_time_report("0:01.25", 4321))
            self.archive_sources[str(archive)] = self.source_by_name[source.name]
            self.archive_names[str(archive)] = source.name
            command = " ".join(argv)
            inline = re.search(r"PPMd:o=(\d+):mem=(\d+)m", command)
            separate_order = re.search(r"(?:^| )-mo=(\d+)(?: |$)", command)
            separate_memory = re.search(r"(?:^| )-mmem=(\d+)m(?: |$)", command)
            if inline:
                order, memory_mib = map(int, inline.groups())
            elif separate_order and separate_memory:
                order = int(separate_order.group(1))
                memory_mib = int(separate_memory.group(1))
            else:
                raise AssertionError(f"missing PPMd order/memory switches: {argv}")
            subprocess.run(
                (
                    TOOLS["7z"]["path"], "a", "-t7z", "-m0=PPMd",
                    f"-mo={order}", f"-mmem={memory_mib}m", "-bd", "-y",
                    str(archive), str(source),
                ),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            )
            source_size = len(self.source_by_name[source.name])
            requested_exponent = 20 + (memory_mib.bit_length() - 1)
            effective_exponent = min(
                requested_exponent,
                max(16, (source_size * 16 - 1).bit_length()),
            )
            self.archive_methods[str(archive)] = f"PPMD:o{order}:mem{effective_exponent}"
        elif phase == "inspect":
            archive = Path(argv[-1])
            listing = (
                "Method = PPMD\n"
                "----------\n"
                f"Path = {self.archive_names[str(archive)]}\n"
                f"Size = {len(self.archive_sources[str(archive)])}\n"
                f"Method = {self.archive_methods[str(archive)]}\n"
            )
            return subprocess.CompletedProcess(argv, 0, listing, "")
        elif phase == "decode":
            report = Path(argv[argv.index("-o") + 1])
            archive = Path(argv[-1])
            report.write_text(fake_gnu_time_report("0:00.50", 3210))
            assert stdout_path is not None
            stdout_path.write_bytes(self.archive_sources[str(archive)])
        elif phase == "cmp":
            return subprocess.CompletedProcess(argv, 0, "", "")
        else:  # pragma: no cover - makes unexpected phases loudly fail the test
            raise AssertionError(f"unexpected phase {phase}")
        return subprocess.CompletedProcess(argv, 0, "", "")


def make_publication_writable(root: Path) -> None:
    for path in sorted(
        [root, *root.rglob("*")], key=lambda item: len(item.parts)
    ):
        path.chmod(0o755 if path.is_dir() else 0o644)


def reseal_publication(root: Path, observation_count: int) -> None:
    for reserved in (root / "COMPLETE", root / "MANIFEST.json"):
        reserved.unlink()
    manifest = {
        "schema": oracle.SCHEMA_VERSION,
        "status": "STAGED",
        "observation_count": observation_count,
        "directories": oracle._manifest_directories(root),
        "entries": oracle._manifest_entries(root),
    }
    oracle._write_json(root / "MANIFEST.json", manifest)
    oracle._write_json(
        root / "COMPLETE",
        {
            "schema": oracle.SCHEMA_VERSION,
            "status": "COMPLETE",
            "observation_count": observation_count,
            "manifest_sha256": oracle.sha256_file(root / "MANIFEST.json"),
            "final_namespace": str(root.absolute()),
        },
    )
    oracle._make_tree_read_only(root)


class CanonicalContractTests(unittest.TestCase):
    def test_exact_inventory_and_grid_are_frozen(self):
        roots = {
            "world": Path("/corpus/world"),
            "tuned": Path("/repo/tuned"),
            "holdout": Path("/repo/holdout"),
        }
        entries = oracle.canonical_inventory(roots)

        self.assertEqual((4, 6, 8), oracle.ORDERS)
        self.assertEqual((16, 64, 256), oracle.MEMORY_MIB)
        self.assertEqual("0-15", oracle.CPUSET)
        self.assertEqual({"world": 11, "tuned": 10, "holdout": 6}, oracle.cohort_counts(entries))
        self.assertEqual(27, len(entries))
        self.assertTrue(hasattr(oracle, "frozen_inventory_sha256"), "missing exact inventory identity")
        self.assertEqual(EXPECTED_FROZEN_INVENTORY_SHA256, oracle.frozen_inventory_sha256())
        self.assertEqual(EXPECTED_FROZEN_GRID_SHA256, oracle.frozen_grid_sha256())
        grid = oracle.plan_grid(entries)
        self.assertEqual(243, len(grid))
        self.assertEqual("world/dickens/order=4/mem=16MiB", grid[0].identifier)
        self.assertEqual("holdout/exe.bin/order=8/mem=256MiB", grid[-1].identifier)

        world_names = {entry.name for entry in entries if entry.cohort == "world"}
        self.assertEqual(
            {
                "dickens",
                "reymont",
                "webster",
                "xml",
                "enwik8",
                "alice29.txt",
                "asyoulik.txt",
                "cp.html",
                "lcet10.txt",
                "plrabn12.txt",
                "xargs.1",
            },
            world_names,
        )
        holdout = {entry.name: entry for entry in entries if entry.cohort == "holdout"}
        self.assertEqual(39384, holdout["exe.bin"].size_bytes)
        self.assertEqual(
            "a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179",
            holdout["exe.bin"].sha256,
        )

        original_inventory = oracle._FROZEN_INVENTORY
        try:
            for row_index, row in enumerate(original_inventory):
                for field_index in range(len(row)):
                    mutation = list(row)
                    mutation[field_index] = (
                        mutation[field_index] + 1
                        if isinstance(mutation[field_index], int)
                        else f"{mutation[field_index]}-mutated"
                    )
                    changed = list(original_inventory)
                    changed[row_index] = tuple(mutation)
                    oracle._FROZEN_INVENTORY = tuple(changed)
                    self.assertNotEqual(
                        EXPECTED_FROZEN_INVENTORY_SHA256,
                        oracle.frozen_inventory_sha256(),
                        f"inventory row {row_index} field {field_index} was not identity-bound",
                    )
        finally:
            oracle._FROZEN_INVENTORY = original_inventory

        records = oracle.frozen_grid_records()
        self.assertEqual(243, len(records))
        for cell_index, record in enumerate(records):
            changed_records = list(records)
            changed_record = list(record)
            changed_record[-1] = "0-14"
            changed_records[cell_index] = tuple(changed_record)
            self.assertNotEqual(
                EXPECTED_FROZEN_GRID_SHA256,
                oracle.frozen_grid_sha256(changed_records),
                f"grid cell {cell_index} was not position-bound",
            )

    def test_commands_charge_container_and_pin_every_observation(self):
        entry = oracle.InventoryEntry(
            cohort="world",
            name="xargs.1",
            relative_path="canterbury/xargs.1",
            path=Path("/corpus/world/canterbury/xargs.1"),
            size_bytes=4227,
            sha256="c58aeb5d2d1e12751d47e7412b45784405fc30a5671b03d480fa05776e183619",
        )
        cell = oracle.GridCell(entry=entry, order=4, memory_mib=16)
        archive = Path("/tmp/cell.7z")
        encode_time = Path("/tmp/encode.time")
        decode_time = Path("/tmp/decode.time")

        self.assertEqual(
            (
                "/usr/bin/time", "-v", "-o", str(encode_time),
                "/usr/bin/taskset", "-c", "0-15",
                "/usr/bin/7z", "a", "-t7z", "-m0=PPMd", "-mo=4", "-mmem=16m",
                "-bd", "-y", str(archive), str(entry.path),
            ),
            oracle.encode_command(cell, archive, encode_time, TOOLS),
        )
        self.assertEqual(
            (
                "/usr/bin/time", "-v", "-o", str(decode_time),
                "/usr/bin/taskset", "-c", "0-15",
                "/usr/bin/7z", "x", "-so", "-y", str(archive),
            ),
            oracle.decode_command(cell, archive, decode_time, TOOLS),
        )

    def test_time_parser_requires_elapsed_and_rss(self):
        valid = fake_gnu_time_report("1:02:03.50", 9876)
        parsed = oracle.parse_gnu_time(valid)
        self.assertEqual(3723.5, parsed["elapsed_seconds"])
        self.assertEqual(9876, parsed["peak_rss_kib"])
        with self.assertRaisesRegex(oracle.HarnessError, "peak RSS"):
            oracle.parse_gnu_time(
                valid.replace("\tMaximum resident set size (kbytes): 9876\n", "")
            )
        target_only = (
            "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.00\n"
            "Maximum resident set size (kbytes): 9876\n"
        )
        invalid_reports = (
            valid + "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.00\n",
            valid + "unrecognized trailing text\n",
            valid.replace("9876", "1.5"),
            valid.rstrip("\n"),
            target_only,
            valid.replace("\tSwaps: 0\n", ""),
            valid.replace("\t", ""),
        )
        for report in invalid_reports:
            with self.subTest(report=report):
                with self.assertRaisesRegex(oracle.HarnessError, "exact grammar"):
                    oracle.parse_gnu_time(report)


class FailClosedExecutionTests(unittest.TestCase):
    def test_void_journal_is_transactional_complete_and_covers_setup_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = root / "void.jsonl"
            first = {"schema": oracle.SCHEMA_VERSION, "status": "VOID", "error": "first"}
            oracle._append_void(journal, first)

            real_write = oracle.os.write
            calls = 0

            def interrupted_then_short(descriptor: int, payload: bytes | memoryview) -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise InterruptedError
                if calls == 2:
                    return real_write(descriptor, payload[:7])
                return real_write(descriptor, payload)

            oracle.os.write = interrupted_then_short
            try:
                try:
                    oracle._append_void(
                        journal,
                        {"schema": oracle.SCHEMA_VERSION, "status": "VOID", "error": "second"},
                    )
                except InterruptedError:
                    self.fail("VOID journal did not retry an interrupted checked write")
            finally:
                oracle.os.write = real_write

            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(["first", "second"], [row["error"] for row in rows])

            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            output = root / "existing-output"
            output.mkdir()
            with self.assertRaises(oracle.HarnessError):
                oracle.execute_grid(
                    entries=(fixture_entry(source),),
                    output_dir=output,
                    void_journal=journal,
                    provenance=fixture_provenance(),
                    runner=FakeRunner({source.name: source.read_bytes()}),
                    _test_only_allow_noncanonical=True,
                )
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual("setup", rows[-1]["failed_cell"])
            self.assertIn("overwrite", rows[-1]["error"])

            with self.assertRaises(oracle.HarnessError):
                oracle.main(
                    [
                        "--execute",
                        "--holdout-root",
                        str(root),
                        "--void-journal",
                        str(journal),
                    ]
                )
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual("setup", rows[-1]["failed_cell"])
            self.assertIn("missing required arguments", rows[-1]["error"])

            corrupt = root / "corrupt.jsonl"
            corrupt.write_bytes(b"not-json\n")
            with self.assertRaisesRegex(oracle.HarnessError, "existing VOID journal"):
                oracle._append_void(corrupt, first)
            self.assertEqual(b"not-json\n", corrupt.read_bytes())

    def test_provenance_rejects_missing_or_drifted_exact_identities(self):
        mutations: list[tuple[str, dict[str, object]]] = []

        missing_tool_hash = fixture_provenance()
        missing_tool_hash["tools"] = copy.deepcopy(TOOLS)
        missing_tool_hash["tools"]["7z"].pop("binary_sha256")  # type: ignore[index]
        mutations.append(("tool binary hash", missing_tool_hash))

        mutations.extend(
            (
                ("preregistration identity", fixture_provenance(preregistration=None)),
                ("harness identity", fixture_provenance(harness_sha256="0" * 64)),
                ("test identity", fixture_provenance(test_sha256="0" * 64)),
                ("inventory identity", fixture_provenance(inventory_sha256="0" * 64)),
                ("grid identity", fixture_provenance(grid_sha256="0" * 64)),
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            cell = oracle.GridCell(entry=fixture_entry(source), order=4, memory_mib=16)
            for index, (label, provenance) in enumerate(mutations):
                with self.subTest(identity=label):
                    with self.assertRaisesRegex(oracle.HarnessError, label):
                        oracle.run_cell(
                            cell,
                            root / f"work-{index}",
                            provenance,
                            runner=FakeRunner({source.name: source.read_bytes()}),
                        )

    def test_bin_cat_materialization_is_explicit_authenticated_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            try:
                target = oracle.materialize_holdout_exe(root)
            except AttributeError:
                self.fail("missing explicit /bin/cat holdout materialization recipe")
            self.assertEqual(root / "exe.bin", target)
            self.assertEqual(39384, target.stat().st_size)
            self.assertEqual(
                "a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179",
                oracle.sha256_file(target),
            )
            self.assertEqual(0, target.stat().st_mode & 0o222)
            self.assertEqual(target, oracle.materialize_holdout_exe(root))

        help_text = oracle._parser().format_help()
        self.assertIn("--materialize-holdout-exe", help_text)
        self.assertIn("/bin/cat", help_text)

    def test_preflight_rejects_tampering_before_any_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.bin"
            path.write_bytes(b"original")
            entry = fixture_entry(path)
            path.write_bytes(b"tampered")
            runner = FakeRunner({path.name: path.read_bytes()})

            with self.assertRaisesRegex(oracle.HarnessError, "SHA-256 mismatch"):
                oracle.verify_inventory((entry,))
            self.assertEqual([], runner.calls)

    def test_cell_records_both_times_rss_cmp_sha_and_full_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"byte-exact fixture")
            entry = fixture_entry(source)
            cell = oracle.GridCell(entry=entry, order=6, memory_mib=64)
            runner = FakeRunner({source.name: source.read_bytes()})
            provenance = fixture_provenance()

            result = oracle.run_cell(cell, root / "work", provenance, runner=runner)

            self.assertTrue(result["round_trip"])
            self.assertTrue(result["cmp_equal"])
            self.assertTrue(result["sha256_equal"])
            self.assertGreater(result["archive_bytes"], 0)
            self.assertEqual(
                result["artifacts"]["archive"]["size_bytes"],
                result["archive_bytes"],
            )
            self.assertEqual(1.25, result["encode"]["elapsed_seconds"])
            self.assertEqual(4321, result["encode"]["peak_rss_kib"])
            self.assertEqual(0.5, result["decode"]["elapsed_seconds"])
            self.assertEqual(3210, result["decode"]["peak_rss_kib"])
            self.assertEqual(provenance["code_sha"], result["code_sha"])
            self.assertEqual(TOOLS, result["tools"])
            self.assertEqual("0-15", result["cpu_set"])
            self.assertEqual(
                ["encode", "inspect", "decode", "cmp"],
                [phase for phase, _ in runner.calls],
            )
            self.assertNotIn("average", json.dumps(result).lower())

    def test_child_failure_is_named_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            cell = oracle.GridCell(entry=fixture_entry(source), order=4, memory_mib=16)
            runner = FakeRunner({source.name: source.read_bytes()}, fail_on_call=1)

            with self.assertRaisesRegex(oracle.HarnessError, "encode.*tuned/fixture.bin.*exit 17"):
                oracle.run_cell(
                    cell,
                    root / "work",
                    fixture_provenance(),
                    runner=runner,
                )
            self.assertEqual(1, len(runner.calls))

    def test_exit_zero_without_archive_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            cell = oracle.GridCell(entry=fixture_entry(source), order=4, memory_mib=16)
            calls: list[str] = []

            def empty_success(phase: str, argv: tuple[str, ...], stdout_path: Path | None):
                del argv, stdout_path
                calls.append(phase)
                return subprocess.CompletedProcess((), 0, "", "")

            with self.assertRaisesRegex(oracle.HarnessError, "no charged archive"):
                oracle.run_cell(
                    cell,
                    root / "work",
                    fixture_provenance(),
                    runner=empty_success,
                )
            self.assertEqual(["encode"], calls)

    def test_non_ppmd_archive_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            cell = oracle.GridCell(entry=fixture_entry(source), order=4, memory_mib=16)
            runner = FakeRunner({source.name: source.read_bytes()})

            def wrong_method(phase: str, argv: tuple[str, ...], stdout_path: Path | None):
                result = runner(phase, argv, stdout_path)
                if phase == "inspect":
                    return subprocess.CompletedProcess(argv, 0, "Method = LZMA2\n", "")
                return result

            with self.assertRaisesRegex(oracle.HarnessError, "not PPMd"):
                oracle.run_cell(
                    cell,
                    root / "work",
                    fixture_provenance(),
                    runner=wrong_method,
                )
            self.assertEqual(["encode", "inspect"], [phase for phase, _ in runner.calls])

    def test_generic_ppmd_header_does_not_authenticate_lzma2_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            cell = oracle.GridCell(entry=fixture_entry(source), order=4, memory_mib=16)
            runner = FakeRunner({source.name: source.read_bytes()})

            def wrong_member(phase: str, argv: tuple[str, ...], stdout_path: Path | None):
                result = runner(phase, argv, stdout_path)
                if phase == "inspect":
                    return subprocess.CompletedProcess(
                        argv,
                        0,
                        "Method = PPMD\n----------\n"
                        "Path = fixture.bin\nSize = 7\nMethod = LZMA2\n",
                        "",
                    )
                return result

            with self.assertRaisesRegex(oracle.HarnessError, "member method mismatch"):
                oracle.run_cell(
                    cell,
                    root / "work",
                    fixture_provenance(),
                    runner=wrong_member,
                )

    def test_member_ppmd_order_and_effective_memory_are_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"x" * 8192)
            cell = oracle.GridCell(entry=fixture_entry(source), order=6, memory_mib=64)
            runner = FakeRunner({source.name: source.read_bytes()})

            valid = oracle.run_cell(
                cell,
                root / "valid",
                fixture_provenance(),
                runner=runner,
            )
            self.assertEqual("PPMD:o6:mem17", valid["archive_inspection"]["method"])

            for index, wrong_method in enumerate(("PPMD:o4:mem17", "PPMD:o6:mem16")):
                bad_runner = FakeRunner({source.name: source.read_bytes()})

                def wrong_member(
                    phase: str,
                    argv: tuple[str, ...],
                    stdout_path: Path | None,
                    *,
                    method: str = wrong_method,
                    base: FakeRunner = bad_runner,
                ):
                    result = base(phase, argv, stdout_path)
                    if phase == "inspect":
                        return subprocess.CompletedProcess(
                            argv,
                            0,
                            "Method = PPMD\n----------\n"
                            f"Path = fixture.bin\nSize = 8192\nMethod = {method}\n",
                            "",
                        )
                    return result

                with self.subTest(method=wrong_method):
                    with self.assertRaisesRegex(oracle.HarnessError, "member method mismatch"):
                        oracle.run_cell(
                            cell,
                            root / f"invalid-{index}",
                            fixture_provenance(),
                            runner=wrong_member,
                        )

    def test_complete_grid_is_published_only_after_all_cells_pass(self):
        self.assertTrue(hasattr(oracle, "validate_publication"), "missing publication validator")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            entry = fixture_entry(source)
            output = root / "result"
            journal = root / "void.jsonl"
            runner = FakeRunner({source.name: source.read_bytes()})

            oracle.execute_grid(
                entries=(entry,),
                orders=(4, 6),
                memories=(16,),
                output_dir=output,
                void_journal=journal,
                provenance=fixture_provenance(),
                runner=runner,
                _test_only_allow_noncanonical=True,
            )

            self.assertTrue((output / "COMPLETE").is_file())
            self.assertTrue((output / "MANIFEST.json").is_file())
            self.assertEqual(2, len((output / "observations.jsonl").read_text().splitlines()))
            self.assertFalse(journal.exists())
            provenance = json.loads((output / "provenance.json").read_text())
            self.assertEqual(2, provenance["observation_count"])
            self.assertNotIn("average", json.dumps(provenance).lower())
            accepted = oracle._validate_publication_tree(
                output, authoritative=True, canonical=False
            )
            self.assertEqual(2, accepted["observation_count"])
            self.assertFalse(any(path.stat().st_mode & 0o222 for path in [output, *output.rglob("*")]))
            self.assertFalse(any(output.parent.glob(f".{output.name}.stage-*")))
            self.assertFalse(any(output.parent.glob(f".{output.name}.publishing-*")))

    def test_publication_validator_rejects_extra_writable_and_tampered_state(self):
        self.assertTrue(hasattr(oracle, "validate_publication"), "missing publication validator")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            output = root / "result"
            oracle.execute_grid(
                entries=(fixture_entry(source),),
                orders=(4,),
                memories=(16,),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner({source.name: source.read_bytes()}),
                _test_only_allow_noncanonical=True,
            )
            oracle._validate_publication_tree(
                output, authoritative=True, canonical=False
            )

            output.chmod(0o755)
            extra = output / "extra.txt"
            extra.write_text("not manifested\n")
            with self.assertRaisesRegex(oracle.HarnessError, "manifest file set"):
                oracle.validate_publication(output)
            extra.unlink()
            output.chmod(0o555)

            manifest = output / "MANIFEST.json"
            output.chmod(0o755)
            manifest.chmod(0o644)
            manifest.write_text("{}\n")
            manifest.chmod(0o444)
            output.chmod(0o555)
            with self.assertRaisesRegex(oracle.HarnessError, "manifest"):
                oracle.validate_publication(output)

    def test_crash_points_never_expose_a_pre_final_authoritative_result(self):
        self.assertTrue(hasattr(oracle, "SimulatedCrash"), "missing crash-injection seam")
        for crash_after in ("stage_fsynced", "publishing_renamed", "marker_committed"):
            with self.subTest(crash_after=crash_after), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "fixture.bin"
                source.write_bytes(b"fixture")
                output = root / "result"
                with self.assertRaises(oracle.SimulatedCrash):
                    oracle.execute_grid(
                        entries=(fixture_entry(source),),
                        orders=(4,),
                        memories=(16,),
                        output_dir=output,
                        void_journal=root / "void.jsonl",
                        provenance=fixture_provenance(),
                        runner=FakeRunner({source.name: source.read_bytes()}),
                        crash_after=crash_after,
                        _test_only_allow_noncanonical=True,
                    )
                self.assertFalse(output.exists())
                self.assertFalse(oracle.is_authoritative_publication(output))

    def test_grid_failure_publishes_no_partial_result_and_journals_void(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            entry = fixture_entry(source)
            output = root / "result"
            journal = root / "void.jsonl"
            # Cell 1 takes encode/inspect/decode/cmp calls; cell 2 fails on encode.
            runner = FakeRunner({source.name: source.read_bytes()}, fail_on_call=5)

            with self.assertRaisesRegex(oracle.HarnessError, "encode"):
                oracle.execute_grid(
                    entries=(entry,),
                    orders=(4, 6),
                    memories=(16,),
                    output_dir=output,
                    void_journal=journal,
                    provenance=fixture_provenance(),
                    runner=runner,
                    _test_only_allow_noncanonical=True,
                )

            self.assertFalse(output.exists())
            self.assertEqual(5, len(runner.calls))
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(1, len(rows))
            self.assertEqual("VOID", rows[0]["status"])
            self.assertIn("order=6", rows[0]["failed_cell"])


class FinalReviewRepairTests(unittest.TestCase):
    def test_resealed_real_lzma2_archive_cannot_reuse_ppmd_inspection_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture live archive authority")
            output = root / "result"
            oracle.execute_grid(
                entries=(fixture_entry(source),),
                orders=(4,),
                memories=(16,),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner({source.name: source.read_bytes()}),
                _test_only_allow_noncanonical=True,
            )
            observations = output / "observations.jsonl"
            row = json.loads(observations.read_text())
            archive_record = row["artifacts"]["archive"]
            archive = output / archive_record["relative_path"]

            make_publication_writable(output)
            archive.unlink()
            subprocess.run(
                (
                    TOOLS["7z"]["path"], "a", "-t7z", "-m0=LZMA2", "-bd", "-y",
                    str(archive), str(source),
                ),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            )
            lzma2_listing = subprocess.run(
                (TOOLS["7z"]["path"], "l", "-slt", str(archive)),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            ).stdout
            self.assertIn("Method = LZMA2", lzma2_listing)
            self.assertNotIn("PPMD", lzma2_listing)
            archive_record.update(
                size_bytes=archive.stat().st_size,
                sha256=oracle.sha256_file(archive),
            )
            row["archive_bytes"] = archive_record["size_bytes"]
            row["archive_sha256"] = archive_record["sha256"]
            observations.write_text(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            )
            reseal_publication(output, 1)

            with self.assertRaisesRegex(oracle.HarnessError, "live archive|archive member method"):
                oracle._validate_publication_tree(
                    output, authoritative=True, canonical=False
                )

    def test_rehashed_time_artifact_drift_cannot_reuse_recorded_row_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture timing authority")
            output = root / "result"
            oracle.execute_grid(
                entries=(fixture_entry(source),),
                orders=(4,),
                memories=(16,),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner({source.name: source.read_bytes()}),
                _test_only_allow_noncanonical=True,
            )
            observations = output / "observations.jsonl"
            row = json.loads(observations.read_text())
            timing_record = row["artifacts"]["encode_time"]
            timing = output / timing_record["relative_path"]

            make_publication_writable(output)
            timing.write_text(fake_gnu_time_report("0:09.75", 9999))
            timing_record.update(
                size_bytes=timing.stat().st_size,
                sha256=oracle.sha256_file(timing),
            )
            self.assertEqual(
                {"elapsed_seconds": 9.75, "peak_rss_kib": 9999},
                oracle.parse_gnu_time(timing.read_text()),
            )
            self.assertEqual(1.25, row["encode"]["elapsed_seconds"])
            self.assertEqual(4321, row["encode"]["peak_rss_kib"])
            observations.write_text(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            )
            reseal_publication(output, 1)

            with self.assertRaisesRegex(oracle.HarnessError, "encode timing artifact"):
                oracle._validate_publication_tree(
                    output, authoritative=True, canonical=False
                )

    def test_forged_full_grid_cannot_replace_authoritative_row_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = []
            source_by_name = {}
            for index in range(27):
                source = root / f"fixture-{index:02d}.bin"
                payload = f"prospective fixture {index}\n".encode()
                source.write_bytes(payload)
                entries.append(fixture_entry(source, cohort=f"cohort-{index // 9}"))
                source_by_name[source.name] = payload
            output = root / "forged-full-grid"
            oracle.execute_grid(
                entries=tuple(entries),
                orders=(4, 6, 8),
                memories=(16, 64, 256),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner(source_by_name),
                _test_only_allow_noncanonical=True,
            )
            observations_path = output / "observations.jsonl"
            rows = [json.loads(line) for line in observations_path.read_text().splitlines()]
            self.assertEqual(27 * 3 * 3, len(rows))

            make_publication_writable(output)
            for row in rows:
                row["archive_inspection"]["stdout"] = (
                    "Method = LZMA2\n"
                    "----------\n"
                    f"Path = {row['file']}\n"
                    f"Size = {row['input_bytes']}\n"
                    "Method = LZMA2\n"
                )
                row["encode"]["elapsed_seconds"] = -1.0
                row["encode"]["command"][0] = "/bin/true"
                row["cmp_command"][3] = row["cmp_command"][2]
            observations_path.write_text(
                "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
            )
            reseal_publication(output, len(rows))

            with self.assertRaisesRegex(oracle.HarnessError, "observation semantics"):
                oracle._validate_publication_tree(
                    output, authoritative=True, canonical=False
                )

    def test_rehashed_artifact_tamper_cannot_pass_row_manifest_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture artifact binding")
            output = root / "result"
            oracle.execute_grid(
                entries=(fixture_entry(source),),
                orders=(4,),
                memories=(16,),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner({source.name: source.read_bytes()}),
                _test_only_allow_noncanonical=True,
            )
            row = json.loads((output / "observations.jsonl").read_text())
            decoded = output / "cells" / "tuned-fixture.bin-o4-m16" / "decoded.bin"
            make_publication_writable(output)
            decoded.write_bytes(b"tampered but re-manifested")
            reseal_publication(output, 1)

            with self.assertRaisesRegex(oracle.HarnessError, "artifact"):
                oracle._validate_publication_tree(
                    output, authoritative=True, canonical=False
                )
            self.assertEqual(source.name, row["file"])

    def test_post_final_rename_crash_is_quarantined_and_parent_fsynced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture crash quarantine")
            output = root / "result"
            events: list[tuple[str, Path]] = []
            real_rename = oracle._rename_noreplace
            real_fsync = oracle._fsync_directory

            def recording_rename(source_path: Path, target_path: Path) -> None:
                real_rename(source_path, target_path)
                events.append(("rename", target_path))

            def recording_fsync(path: Path) -> None:
                real_fsync(path)
                events.append(("fsync", path))

            oracle._rename_noreplace = recording_rename
            oracle._fsync_directory = recording_fsync
            try:
                observed_error: BaseException | None = None
                try:
                    oracle.execute_grid(
                        entries=(fixture_entry(source),),
                        orders=(4,),
                        memories=(16,),
                        output_dir=output,
                        void_journal=root / "void.jsonl",
                        provenance=fixture_provenance(),
                        runner=FakeRunner({source.name: source.read_bytes()}),
                        crash_after="final_renamed_before_parent_fsync",
                        _test_only_allow_noncanonical=True,
                    )
                except BaseException as exc:
                    observed_error = exc
            finally:
                oracle._rename_noreplace = real_rename
                oracle._fsync_directory = real_fsync

            self.assertIsInstance(observed_error, oracle.SimulatedCrash)
            quarantines = list(root.glob(".result.quarantine-*"))
            self.assertFalse(output.exists())
            self.assertEqual(1, len(quarantines))
            self.assertFalse(oracle.is_authoritative_publication(quarantines[0]))
            self.assertEqual(
                [("rename", quarantines[0]), ("fsync", root)],
                events[-2:],
            )

    def test_authoritative_validation_rejects_noncanonical_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            output = root / "result"
            oracle.execute_grid(
                entries=(fixture_entry(source),),
                orders=(4,),
                memories=(16,),
                output_dir=output,
                void_journal=root / "void.jsonl",
                provenance=fixture_provenance(),
                runner=FakeRunner({source.name: source.read_bytes()}),
                _test_only_allow_noncanonical=True,
            )
            with self.assertRaisesRegex(oracle.HarnessError, "exact frozen 27/243"):
                oracle.validate_publication(output)
            self.assertFalse(oracle.is_authoritative_publication(output))

    def test_provenance_recomputes_code_tool_prereg_and_run_id(self):
        mutations: list[tuple[str, dict[str, object]]] = []
        bad_run = fixture_provenance(run_id="0" * 64)
        mutations.append(("run identity", bad_run))

        bad_code = fixture_provenance(code_sha="a" * 40)
        bad_code["run_id"] = oracle.recompute_run_id(bad_code)
        mutations.append(("actual exact origin/main", bad_code))

        bad_tool = fixture_provenance()
        bad_tool["tools"] = copy.deepcopy(bad_tool["tools"])
        bad_tool["tools"]["7z"]["version"] = "fabricated"  # type: ignore[index]
        bad_tool["run_id"] = oracle.recompute_run_id(bad_tool)
        mutations.append(("tool version output", bad_tool))

        bad_prereg = fixture_provenance()
        bad_prereg["preregistration"] = copy.deepcopy(bad_prereg["preregistration"])
        bad_prereg["preregistration"]["git_blob_sha"] = "a" * 40  # type: ignore[index]
        bad_prereg["run_id"] = oracle.recompute_run_id(bad_prereg)
        mutations.append(("pinned preregistration", bad_prereg))

        for label, provenance in mutations:
            with self.subTest(label=label):
                with self.assertRaisesRegex(oracle.HarnessError, label):
                    oracle.validate_provenance(provenance)

    def test_preregistration_is_pinned_to_the_canonical_committed_path_and_hash(self):
        self.assertEqual(
            "documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md",
            oracle.PREREGISTRATION_REPO_PATH,
        )
        self.assertEqual(
            "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093",
            oracle.PREREGISTRATION_SHA256,
        )
        self.assertEqual(
            "d96df7e3478a6ba52b737ef30dea63d68b0e01ac",
            oracle.PREREGISTRATION_GIT_BLOB,
        )
        arbitrary = fixture_provenance(
            preregistration={
                "path": str(Path(__file__).resolve()),
                "sha256": oracle.sha256_file(Path(__file__).resolve()),
            }
        )
        with self.assertRaisesRegex(oracle.HarnessError, "pinned preregistration"):
            oracle.validate_provenance(arbitrary)

    def test_argparse_failure_is_recoverable_and_durably_journaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "void.jsonl"
            with self.assertRaises(oracle.HarnessError):
                oracle.main(
                    [
                        "--execute",
                        "--holdout-root",
                        tmp,
                        "--void-journal",
                        str(journal),
                        "--unknown-final-review-flag",
                    ]
                )
            row = json.loads(journal.read_text().strip())
            self.assertEqual("VOID", row["status"])
            self.assertEqual("argument-parse", row["failed_cell"])

    def test_hidden_publishing_namespace_can_never_be_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            output = root / "registered-final"
            with self.assertRaises(oracle.SimulatedCrash):
                oracle.execute_grid(
                    entries=(fixture_entry(source),),
                    orders=(4,),
                    memories=(16,),
                    output_dir=output,
                    void_journal=root / "void.jsonl",
                    provenance=fixture_provenance(),
                    runner=FakeRunner({source.name: source.read_bytes()}),
                    crash_after="marker_committed",
                    _test_only_allow_noncanonical=True,
                )
            publishing = next(root.glob(".registered-final.publishing-*"))
            self.assertFalse(oracle.is_authoritative_publication(publishing))
            with self.assertRaisesRegex(oracle.HarnessError, "final namespace"):
                oracle.validate_publication(publishing)

    def test_primary_void_is_durable_before_cleanup_failure_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture")
            journal = root / "void.jsonl"
            original_discard = oracle._discard_tree

            def cleanup_failure(path: Path | None) -> None:
                raise OSError("injected cleanup failure")

            oracle._discard_tree = cleanup_failure
            try:
                with self.assertRaises(oracle.HarnessError):
                    oracle.execute_grid(
                        entries=(fixture_entry(source),),
                        orders=(4,),
                        memories=(16,),
                        output_dir=root / "result",
                        void_journal=journal,
                        provenance=fixture_provenance(),
                        runner=FakeRunner({source.name: source.read_bytes()}, fail_on_call=1),
                        _test_only_allow_noncanonical=True,
                    )
            finally:
                oracle._discard_tree = original_discard
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(["PRIMARY", "CLEANUP"], [row["failure_phase"] for row in rows])
            self.assertIn("evidence_paths", rows[0])
            self.assertTrue(any(Path(path).exists() for path in rows[0]["evidence_paths"]))

    def test_holdout_rejects_hardlinked_target_and_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = oracle.materialize_holdout_exe(root)
            alias = root / "alias.bin"
            os.link(target, alias)
            with self.assertRaisesRegex(oracle.HarnessError, "link count"):
                oracle.materialize_holdout_exe(root)

            synthetic_source = root / "synthetic-source"
            synthetic_source.write_bytes(b"source")
            synthetic_alias = root / "synthetic-source-alias"
            os.link(synthetic_source, synthetic_alias)
            with self.assertRaisesRegex(oracle.HarnessError, "link count"):
                oracle._require_single_link_regular(synthetic_source, "holdout exe source")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(oracle.HarnessError, "unsafe parent"):
                oracle.materialize_holdout_exe(linked)

    def test_observation_semantics_reject_every_authority_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.bin"
            source.write_bytes(b"fixture semantics")
            entry = fixture_entry(source)
            cell = oracle.GridCell(entry=entry, order=4, memory_mib=16)
            provenance = fixture_provenance()
            row = oracle.run_cell(
                cell,
                root / "work",
                provenance,
                runner=FakeRunner({source.name: source.read_bytes()}),
            )
            oracle._validate_observation(row, cell, provenance)
            fake_encode = list(row["encode"]["command"])
            fake_encode[0] = "/bin/true"
            wrong_inspect = list(row["archive_inspection"]["command"])
            wrong_inspect[-1] = "cells/wrong/payload.7z"
            wrong_decode = list(row["decode"]["command"])
            wrong_decode[-1] = "cells/wrong/payload.7z"
            mutations = {
                "member path": ("archive_inspection", "member_paths", ["other.bin"]),
                "member method": ("archive_inspection", "method", "PPMD:o6:mem16"),
                "inspect command": ("archive_inspection", "command", wrong_inspect),
                "encode command": ("encode", "command", fake_encode),
                "decode command": ("decode", "command", wrong_decode),
                "negative elapsed": ("encode", "elapsed_seconds", -0.01),
                "nonfinite elapsed": ("decode", "elapsed_seconds", float("nan")),
                "fractional RSS": ("encode", "peak_rss_kib", 1.5),
                "relative path": (None, "relative_path", "other.bin"),
                "input command path": ("cmp_command", 2, "/tmp/other.bin"),
                "decoded cmp operand": ("cmp_command", 3, "tuned/fixture.bin"),
                "input bytes": (None, "input_bytes", entry.size_bytes + 1),
                "input hash": (None, "input_sha256", "0" * 64),
                "archive bytes": (None, "archive_bytes", 1.5),
                "archive artifact": (
                    "artifacts",
                    "archive",
                    {
                        "relative_path": "cells/wrong/payload.7z",
                        "size_bytes": row["archive_bytes"],
                        "sha256": row["archive_sha256"],
                    },
                ),
                "order": (None, "order", 6),
                "memory": (None, "memory_mib", 64),
                "tools": (None, "tools", {}),
                "preregistration": (None, "preregistration", {}),
                "inventory identity": (None, "inventory_sha256", "0" * 64),
                "grid identity": (None, "grid_sha256", "0" * 64),
                "run id": (None, "run_id", "0" * 64),
            }
            for label, (container, key, changed) in mutations.items():
                candidate = copy.deepcopy(row)
                if container is None:
                    candidate[key] = changed
                else:
                    candidate[container][key] = changed
                with self.subTest(label=label):
                    with self.assertRaisesRegex(oracle.HarnessError, "observation.*semantics"):
                        oracle._validate_observation(candidate, cell, provenance)


_REAL_TOOLS_AVAILABLE = all(shutil.which(name) for name in ("7z", "taskset", "time", "cmp"))
_PIN_AVAILABLE = hasattr(os, "sched_getaffinity") and set(range(16)).issubset(
    os.sched_getaffinity(0) if hasattr(os, "sched_getaffinity") else set()
)


@unittest.skipUnless(_REAL_TOOLS_AVAILABLE and _PIN_AVAILABLE, "requires 7z/GNU time and CPUs 0-15")
class RealToolSeamTests(unittest.TestCase):
    def test_synthetic_fixture_is_repeatable_with_real_ppmd_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "synthetic.txt"
            source.write_bytes((b"deterministic ppmd seam\n" * 128) + bytes(range(64)))
            entry = fixture_entry(source)
            cell = oracle.GridCell(entry=entry, order=4, memory_mib=16)
            tools = oracle.discover_tools()
            provenance = fixture_provenance(tools=tools)

            first = oracle.run_cell(cell, root / "run-1", provenance)
            second = oracle.run_cell(cell, root / "run-2", provenance)

            self.assertTrue(first["round_trip"])
            self.assertTrue(second["round_trip"])
            self.assertEqual(first["archive_bytes"], second["archive_bytes"])
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])


if __name__ == "__main__":
    unittest.main()
