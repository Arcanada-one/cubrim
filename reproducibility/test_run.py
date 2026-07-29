from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from run_benchmark import CommandError, Journal, build_commands, load_templates


PACKAGE_ROOT = Path(__file__).resolve().parent


def test_all_commands_are_argv_only_and_have_no_unresolved_placeholders(
    tmp_path: Path,
) -> None:
    templates = load_templates(PACKAGE_ROOT / "archiver_templates.json")
    source = tmp_path / "corpus" / "sample.txt"
    source.parent.mkdir()
    source.write_text("sample")
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("cubrim", "rar", "unrar"):
        (tools / name).write_text("")

    for archiver in templates:
        commands = build_commands(
            archiver,
            templates[archiver],
            source=source,
            archive=tmp_path / f"archive-{archiver}",
            restore_dir=tmp_path / f"restore-{archiver}",
            tools_dir=tools,
        )
        assert commands.compress
        assert commands.decompress
        for argument in (*commands.compress, *commands.decompress):
            assert isinstance(argument, str)
            assert argument == argument.strip()
            assert "{" not in argument and "}" not in argument


def test_build_commands_rejects_unknown_placeholder(tmp_path: Path) -> None:
    template = {
        "kind": "stream",
        "source_cwd": True,
        "archive_suffix": ".bad",
        "compress": ["tool", "{shell_payload}"],
        "decompress": ["tool", "{archive}"],
    }
    with pytest.raises(CommandError, match="placeholder"):
        build_commands(
            "bad",
            template,
            source=tmp_path / "source",
            archive=tmp_path / "archive",
            restore_dir=tmp_path / "restore",
            tools_dir=tmp_path / "tools",
        )


def test_journal_is_exclusive_append_flush_and_fsync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(os, "fsync", calls.append)
    path = tmp_path / "run.jsonl"

    with Journal(path) as journal:
        journal.append({"kind": "run_meta", "value": 1})
        journal.append({"kind": "sample", "value": 2})

    assert len(calls) == 2
    assert [json.loads(line)["kind"] for line in path.read_text().splitlines()] == [
        "run_meta",
        "sample",
    ]
    with pytest.raises(FileExistsError):
        Journal(path)


def test_journal_preserves_partial_evidence_without_summary(tmp_path: Path) -> None:
    path = tmp_path / "partial.jsonl"
    with Journal(path) as journal:
        journal.append({"kind": "run_meta"})
        journal.append({"kind": "sample_start"})

    kinds = [json.loads(line)["kind"] for line in path.read_text().splitlines()]
    assert kinds == ["run_meta", "sample_start"]
    assert "summary" not in kinds
