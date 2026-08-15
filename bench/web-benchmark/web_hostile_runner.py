#!/usr/bin/env python3
"""Prove the Cubrim-Web CLI rejects bounded hostile frames.

This is a content-addressed capability probe for the candidate build.  It
uses the same ``cubrim-web`` executable that the resource benchmark measures,
checks an exact valid round trip first, then exercises malformed headers,
selected prefixes, and checksum mutation.  A hostile result is never accepted
because the process merely exited: a zero exit, a signal, a timeout, or output
from the non-streaming decoder is a failure.

The probe is deliberately separate from the database writer.  It emits a
small JSON evidence record; the benchmark adapter may only advertise
``hostile_input_hardened`` when that record matches the exact source commit
and candidate binary hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import tempfile
from pathlib import Path
from typing import Any


TASK_ID = "CUBR-0075"
PHASE = "web_decoder_hostile"
MAX_MEMORY_BYTES = 256 * 1024 * 1024
MAX_CPU_SECONDS = 2


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_hostile_cases(frame: bytes) -> list[dict[str, Any]]:
    """Return a deterministic schedule of frames that must be rejected."""

    if len(frame) < 8:
        raise ValueError("valid frame is too short for the hostile schedule")

    cases: list[dict[str, Any]] = [
        {"case_id": "empty", "payload": b"", "expect_reject": True},
        {"case_id": "short-header", "payload": frame[:3], "expect_reject": True},
    ]

    # The edges and quartiles catch parser state changes without turning the
    # capability probe into a benchmark of tens of thousands of subprocesses.
    offsets = sorted({0, 1, 2, 3, 4, 5, len(frame) // 4, len(frame) // 2, len(frame) - 1})
    for offset in offsets:
        cases.append(
            {
                "case_id": f"prefix-{offset:06d}",
                "payload": frame[:offset],
                "expect_reject": True,
            }
        )

    for case_id, index, value in (
        ("mutation-magic", 0, frame[0] ^ 0x01),
        ("mutation-version", 4, frame[4] ^ 0x01),
        ("mutation-mode", 5, frame[5] ^ 0x01),
        ("mutation-checksum", len(frame) - 1, frame[-1] ^ 0x01),
    ):
        mutated = bytearray(frame)
        mutated[index] = value
        cases.append({"case_id": case_id, "payload": bytes(mutated), "expect_reject": True})

    return cases


def summarize_results(results: list[dict[str, Any]], *, valid_roundtrip_exact: bool) -> dict[str, Any]:
    rejected_count = sum(1 for result in results if result.get("status") == "rejected")
    fault_count = sum(1 for result in results if result.get("fault") is True)
    status = "PASS" if (
        bool(results)
        and valid_roundtrip_exact
        and rejected_count == len(results)
        and fault_count == 0
    ) else "FAIL"
    return {
        "status": status,
        "case_count": len(results),
        "rejected_count": rejected_count,
        "fault_count": fault_count,
        "valid_roundtrip_exact": valid_roundtrip_exact,
    }


def _limit_child() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))


def _run_decode(binary: Path, frame_path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(binary), "decode", str(frame_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=MAX_CPU_SECONDS + 1,
            preexec_fn=_limit_child if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fault", "fault": True, "returncode": None, "stdout_bytes": 0}

    stdout_bytes = len(completed.stdout)
    if completed.returncode == 0:
        return {
            "status": "accepted",
            "fault": True,
            "returncode": completed.returncode,
            "stdout_bytes": stdout_bytes,
        }
    if completed.returncode < 0 or stdout_bytes != 0:
        return {
            "status": "fault",
            "fault": True,
            "returncode": completed.returncode,
            "stdout_bytes": stdout_bytes,
        }
    return {
        "status": "rejected",
        "fault": False,
        "returncode": completed.returncode,
        "stdout_bytes": stdout_bytes,
    }


def _git_sha(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
    )
    value = completed.stdout.strip()
    if len(value) not in (40, 64) or any(character not in "0123456789abcdef" for character in value):
        raise RuntimeError("source HEAD is not a lowercase Git SHA")
    return value


def run_probe(binary: Path, out: Path, repo_root: Path) -> dict[str, Any]:
    binary = binary.resolve(strict=True)
    if binary.name != "cubrim-web":
        raise ValueError(f"candidate binary must be named cubrim-web, got {binary.name}")
    source_sha = _git_sha(repo_root)
    runner_path = Path(__file__).resolve()
    payload = (
        b'<article data-family="hostile-web">'
        b"A deterministic valid Web Profile frame must round-trip exactly."
        b"</article>\n"
    ) * 128

    with tempfile.TemporaryDirectory(prefix="cubrim-web-hostile-") as directory:
        work_dir = Path(directory)
        payload_path = work_dir / "payload.bin"
        frame_path = work_dir / "valid.cbr"
        payload_path.write_bytes(payload)
        encoded = subprocess.run(
            [str(binary), "encode", "--block-size", "4096", str(payload_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=MAX_CPU_SECONDS + 1,
        )
        if encoded.returncode != 0:
            raise RuntimeError(f"candidate encode failed with {encoded.returncode}")
        frame = encoded.stdout
        frame_path.write_bytes(frame)

        valid = subprocess.run(
            [str(binary), "decode", str(frame_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=MAX_CPU_SECONDS + 1,
            preexec_fn=_limit_child if os.name == "posix" else None,
        )
        valid_roundtrip_exact = valid.returncode == 0 and valid.stdout == payload

        results: list[dict[str, Any]] = []
        for case in build_hostile_cases(frame):
            case_path = work_dir / f"{case['case_id']}.cbr"
            case_path.write_bytes(case["payload"])
            observed = _run_decode(binary, case_path)
            results.append({"case_id": case["case_id"], **observed})

    summary = summarize_results(results, valid_roundtrip_exact=valid_roundtrip_exact)
    evidence = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "phase": PHASE,
        "status": summary["status"],
        "source_sha": source_sha,
        "binary_sha256": sha256_file(binary),
        "runner_sha256": sha256_file(runner_path),
        "valid_roundtrip_exact": summary["valid_roundtrip_exact"],
        "case_count": summary["case_count"],
        "rejected_count": summary["rejected_count"],
        "fault_count": summary["fault_count"],
        "containment": {
            "address_space_bytes": MAX_MEMORY_BYTES,
            "cpu_seconds": MAX_CPU_SECONDS,
            "open_files": 1024,
            "network": "not_used",
        },
        "cases": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    evidence = run_probe(args.binary, args.out, args.repo_root.resolve())
    print(json.dumps({key: evidence[key] for key in ("status", "source_sha", "binary_sha256", "case_count", "rejected_count", "fault_count")}, sort_keys=True))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
