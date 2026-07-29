from __future__ import annotations

import json
from pathlib import Path

import pytest

from freeze_expected import (
    PUBLIC_BINARY_SHA256,
    FreezeError,
    build_snapshot,
    evidence_from_timing_journal,
)


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


def meta_source() -> dict[str, object]:
    ratios = {archiver: 0.25 for archiver in ARCHIVERS}
    ratios["cubrim"] = 0.25
    return {
        "meta_count": 1,
        "meta": {
            "id": 35,
            "code_sha": "dfb195ef089db738e51153ad4532fdd583f247bf",
            "archivers": {archiver: archiver for archiver in ARCHIVERS},
        },
        "files": [
            {
                "corpus": "test",
                "file": "sample.bin",
                "type": "binary",
                "orig": 1000,
                "cubrim_rt": "OK",
                "n_archivers": 10,
                "ratio": ratios,
            }
        ],
        "aggregates": [
            {"scope": "overall", "archiver": archiver, "ratio": 0.25}
            for archiver in ARCHIVERS
        ],
    }


def evidence() -> list[dict[str, object]]:
    return [
        {
            "corpus": "test",
            "file": "sample.bin",
            "type": "binary",
            "orig": 1000,
            "archiver": archiver,
            "archive_bytes": 250,
            "encode_rc": 0,
            "decode_rc": 0,
            "cmp": 0,
        }
        for archiver in ARCHIVERS
    ]


def test_build_snapshot_requires_exact_identity_and_round_trips() -> None:
    snapshot = build_snapshot(
        meta_source(),
        evidence(),
        expected_file_count=1,
        expected_aggregate_count=10,
    )

    assert len(snapshot.cells) == 10
    assert snapshot.cells[0]["archive_bytes"] == 250
    assert len(snapshot.aggregates) == 10


@pytest.mark.parametrize("field", ("encode_rc", "decode_rc", "cmp"))
def test_build_snapshot_rejects_failed_evidence(field: str) -> None:
    rows = evidence()
    rows[0][field] = 1

    with pytest.raises(FreezeError, match=field):
        build_snapshot(
            meta_source(),
            rows,
            expected_file_count=1,
            expected_aggregate_count=10,
        )


def test_build_snapshot_rejects_missing_and_duplicate_cells() -> None:
    rows = evidence()
    with pytest.raises(FreezeError, match="evidence cell count"):
        build_snapshot(
            meta_source(),
            rows[:-1],
            expected_file_count=1,
            expected_aggregate_count=10,
        )

    rows.append(dict(rows[0]))
    with pytest.raises(FreezeError, match="duplicate evidence"):
        build_snapshot(
            meta_source(),
            rows,
            expected_file_count=1,
            expected_aggregate_count=10,
        )


def test_build_snapshot_rejects_ratio_that_exact_bytes_cannot_support() -> None:
    source = meta_source()
    source["files"][0]["ratio"]["gzip"] = 0.20

    with pytest.raises(FreezeError, match="ratio mismatch"):
        build_snapshot(
            source,
            evidence(),
            expected_file_count=1,
            expected_aggregate_count=10,
        )


def test_build_snapshot_rejects_noncanonical_cubrim_ratio() -> None:
    source = meta_source()
    source["files"][0]["ratio"]["cubrim"] = 0.2500001

    with pytest.raises(FreezeError, match="Cubrim ratio mismatch"):
        build_snapshot(
            source,
            evidence(),
            expected_file_count=1,
            expected_aggregate_count=10,
        )


def test_build_snapshot_rejects_unrelated_meta() -> None:
    source = meta_source()
    source["meta"]["id"] = 36

    with pytest.raises(FreezeError, match="meta id"):
        build_snapshot(
            source,
            evidence(),
            expected_file_count=1,
            expected_aggregate_count=10,
        )


def test_snapshot_write_is_canonical(tmp_path: Path) -> None:
    snapshot = build_snapshot(
        meta_source(),
        evidence(),
        expected_file_count=1,
        expected_aggregate_count=10,
    )
    paths = snapshot.write(tmp_path)

    for path in paths:
        body = path.read_text()
        assert body.endswith("\n")
        assert json.dumps(
            json.loads(body), sort_keys=True, separators=(",", ":")
        ) + "\n" == body


def test_timing_journal_supplies_exact_closed_measurements(tmp_path: Path) -> None:
    journal = tmp_path / "timing.jsonl"
    sidecar = tmp_path / "timing.sidecar.json"
    records = [
        {
            "kind": "run_meta",
            "meta_id": 35,
            "release_code_sha": "dfb195ef089db738e51153ad4532fdd583f247bf",
            "tools": {"cubrim": {"sha256": PUBLIC_BINARY_SHA256}},
        },
        {
            "archive_bytes": 250,
            "archiver": "gzip",
            "cmp_status": 0,
            "compress_status": "OK",
            "corpus": "test",
            "decompress_status": "OK",
            "file": "sample.bin",
            "kind": "measurement",
            "orig_bytes": 1000,
            "sample_count": 3,
            "type": "binary",
            "warmup_count": 1,
        },
    ]
    journal.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
    )
    import hashlib

    sidecar.write_text(
        json.dumps(
            {"journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )

    rows = evidence_from_timing_journal(
        journal, sidecar, expected_measurement_count=1
    )
    assert rows == [
        {
            "archive_bytes": 250,
            "archiver": "gzip",
            "cmp": 0,
            "corpus": "test",
            "decode_rc": 0,
            "encode_rc": 0,
            "file": "sample.bin",
            "orig": 1000,
            "type": "binary",
        }
    ]


def test_timing_journal_rejects_wrong_public_binary(tmp_path: Path) -> None:
    journal = tmp_path / "timing.jsonl"
    sidecar = tmp_path / "timing.sidecar.json"
    journal.write_text(
        json.dumps(
            {
                "kind": "run_meta",
                "meta_id": 35,
                "release_code_sha": "dfb195ef089db738e51153ad4532fdd583f247bf",
                "tools": {"cubrim": {"sha256": "0" * 64}},
            }
        )
        + "\n"
    )
    import hashlib

    sidecar.write_text(
        json.dumps(
            {"journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest()}
        )
        + "\n"
    )
    with pytest.raises(FreezeError, match="public release binary"):
        evidence_from_timing_journal(
            journal, sidecar, expected_measurement_count=0
        )
