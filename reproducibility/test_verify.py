from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from verify import VerificationError, verify_run


ARCHIVERS = (
    "cubrim",
    "gzip",
    "bzip2",
    "xz",
    "zstd",
    "brotli",
    "lz4",
    "ppmd",
    "7z",
    "rar",
)


def canonical_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    cells = [
        {
            "archiver": archiver,
            "archive_bytes": 250,
            "corpus": "test",
            "file": "sample.bin",
            "measured_ratio": 0.25,
            "orig": 1000,
            "published_ratio": 0.25,
            "type": "binary",
        }
        for archiver in ARCHIVERS
    ]
    aggregates = [
        {"archiver": archiver, "ratio": 0.25, "scope": "overall"}
        for archiver in ARCHIVERS
    ]
    records = [
        {
            "kind": "run_meta",
            "meta_id": 35,
            "release_commit": "dfb195ef089db738e51153ad4532fdd583f247bf",
            "schema_version": 1,
        },
        *[
            {
                "archive_bytes": 250,
                "archiver": archiver,
                "cmp": 0,
                "corpus": "test",
                "decode_rc": 0,
                "encode_rc": 0,
                "file": "sample.bin",
                "kind": "sample",
                "orig": 1000,
                "round_trip_ok": True,
                "type": "binary",
            }
            for archiver in ARCHIVERS
        ],
        {"kind": "summary", "sample_count": 10, "status": "OK"},
    ]
    cells_path = tmp_path / "expected_cells.json"
    aggregates_path = tmp_path / "expected_aggregates.json"
    journal_path = tmp_path / "journal.jsonl"
    sidecar_path = tmp_path / "journal.sha256.json"
    canonical_write(cells_path, cells)
    canonical_write(aggregates_path, aggregates)
    journal_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
    )
    canonical_write(
        sidecar_path,
        {
            "journal_sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest(),
            "schema_version": 1,
        },
    )
    return cells_path, aggregates_path, journal_path, sidecar_path


def verify_fixture(paths: tuple[Path, Path, Path, Path]) -> dict[str, object]:
    return verify_run(
        cells_path=paths[0],
        aggregates_path=paths[1],
        journal_path=paths[2],
        sidecar_path=paths[3],
        expected_cell_count=10,
        expected_aggregate_count=10,
    )


def rewrite_journal(
    journal: Path, sidecar: Path, mutate: callable
) -> None:
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    mutate(records)
    journal.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
    )
    canonical_write(
        sidecar,
        {
            "journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest(),
            "schema_version": 1,
        },
    )


def test_verify_accepts_exact_closed_run(tmp_path: Path) -> None:
    summary = verify_fixture(fixture(tmp_path))
    assert summary["status"] == "PASS"
    assert summary["cell_count"] == 10


@pytest.mark.parametrize(
    ("description", "mutation"),
    (
        (
            "archive byte mismatch",
            lambda records: records[1].__setitem__("archive_bytes", 251),
        ),
        ("missing sample", lambda records: records.pop(1)),
        (
            "failed round trip",
            lambda records: records[1].__setitem__("round_trip_ok", False),
        ),
        (
            "unexpected key",
            lambda records: records[1].__setitem__("file", "other.bin"),
        ),
        ("partial journal", lambda records: records.pop()),
        (
            "wrong meta",
            lambda records: records[0].__setitem__("meta_id", 36),
        ),
    ),
)
def test_verify_rejects_tampered_or_partial_run(
    tmp_path: Path, description: str, mutation: callable
) -> None:
    paths = fixture(tmp_path)
    rewrite_journal(paths[2], paths[3], mutation)
    with pytest.raises(VerificationError):
        verify_fixture(paths)


def test_verify_rejects_sidecar_hash_mismatch(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    paths[2].write_text(paths[2].read_text() + "\n")
    with pytest.raises(VerificationError, match="hash"):
        verify_fixture(paths)


def test_verify_rejects_corrupt_published_aggregate(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    aggregates = json.loads(paths[1].read_text())
    aggregates[0]["ratio"] = 0.20
    canonical_write(paths[1], aggregates)
    with pytest.raises(VerificationError, match="aggregate"):
        verify_fixture(paths)
