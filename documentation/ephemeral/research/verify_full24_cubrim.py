#!/usr/bin/env python3
"""Run one immutable Cubrim CLI over the manifest-locked full-24 corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_bytes(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            aa = a.read(1024 * 1024)
            bb = b.read(1024 * 1024)
            if aa != bb:
                return False
            if not aa:
                return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--binary-commit", required=True)
    parser.add_argument("--corpus", type=Path, default=Path("/root/corpus-full"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=14_400)
    args = parser.parse_args()

    binary = args.binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"binary is not executable: {binary}")
    args.output.mkdir(parents=True, exist_ok=False)
    work = args.output / "work"
    work.mkdir()

    binary_sha = sha256(binary)
    version = subprocess.run(
        [str(binary), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    provenance = {
        "binary": str(binary),
        "binary_sha256": binary_sha,
        "binary_commit": args.binary_commit,
        "binary_version_rc": version.returncode,
        "binary_version": version.stdout.strip(),
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": sha256(args.manifest),
    }
    (args.output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )

    with args.manifest.open(newline="") as handle:
        manifest = list(csv.DictReader(handle, delimiter="\t"))
    if len(manifest) != 24:
        raise RuntimeError(f"expected 24 manifest entries, found {len(manifest)}")

    columns = (
        "corpus", "file", "type", "orig", "compressed", "ratio", "mode",
        "encode_rc", "decode_rc", "cmp", "encode_seconds", "decode_seconds",
        "archive_sha256",
    )
    rows: list[dict[str, object]] = []
    env = os.environ.copy()
    env["CUBRIM_ACCEPT_LICENSE"] = "1"
    with (args.output / "results.tsv").open("w", newline="", buffering=1) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for item in manifest:
            source = args.corpus / item["corpus"] / item["file"]
            expected_size = int(item["orig"])
            if not source.is_file() or source.stat().st_size != expected_size:
                raise RuntimeError(f"size mismatch: {source}")
            if sha256(source) != item["sha256"]:
                raise RuntimeError(f"sha256 mismatch: {source}")

            row_dir = work / item["corpus"] / item["file"]
            row_dir.mkdir(parents=True)
            archive = row_dir / "data.cub"
            restored = row_dir / "restored"
            logs = args.output / "logs" / item["corpus"]
            logs.mkdir(parents=True, exist_ok=True)

            started = time.monotonic()
            with (logs / f"{item['file']}.encode.log").open("wb") as log:
                encoded = subprocess.run(
                    [str(binary), "compress", str(source), str(archive), "--quiet"],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=args.timeout,
                    check=False,
                )
            encode_seconds = time.monotonic() - started

            compressed = archive.stat().st_size if encoded.returncode == 0 and archive.is_file() else 0
            if compressed >= 6:
                with archive.open("rb") as archive_handle:
                    archive_handle.seek(5)
                    mode = archive_handle.read(1)[0]
            else:
                mode = -1
            decode_rc = -1
            decode_seconds = 0.0
            cmp0 = False
            if compressed:
                started = time.monotonic()
                with (logs / f"{item['file']}.decode.log").open("wb") as log:
                    decoded = subprocess.run(
                        [str(binary), "decompress", str(archive), str(restored), "--quiet"],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env=env,
                        timeout=args.timeout,
                        check=False,
                    )
                decode_seconds = time.monotonic() - started
                decode_rc = decoded.returncode
                cmp0 = decode_rc == 0 and restored.is_file() and same_bytes(source, restored)

            row = {
                "corpus": item["corpus"],
                "file": item["file"],
                "type": item["type"],
                "orig": expected_size,
                "compressed": compressed,
                "ratio": compressed / expected_size if compressed else "",
                "mode": mode,
                "encode_rc": encoded.returncode,
                "decode_rc": decode_rc,
                "cmp": 0 if cmp0 else 1,
                "encode_seconds": encode_seconds,
                "decode_seconds": decode_seconds,
                "archive_sha256": sha256(archive) if compressed else "",
            }
            writer.writerow(row)
            rows.append(row)
            print(
                f"{item['corpus']}/{item['file']} comp={compressed} "
                f"ratio={row['ratio']} mode={mode} cmp={row['cmp']}",
                flush=True,
            )
            shutil.rmtree(row_dir)

    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failures = []
    for row in rows:
        if (row["encode_rc"], row["decode_rc"], row["cmp"]) != (0, 0, 0):
            failures.append(f"{row['corpus']}/{row['file']}")
        by_type[str(row["type"])][0] += int(row["compressed"])
        by_type[str(row["type"])][1] += int(row["orig"])
    summary = {
        "binary_commit": args.binary_commit,
        "binary_sha256": binary_sha,
        "rows": len(rows),
        "all_rt_cmp0": not failures and len(rows) == 24,
        "failures": failures,
        "aggregate_by_type": {
            kind: {"compressed": values[0], "orig": values[1], "ratio": values[0] / values[1]}
            for kind, values in sorted(by_type.items())
        },
        "overall": {
            "compressed": sum(values[0] for values in by_type.values()),
            "orig": sum(values[1] for values in by_type.values()),
        },
    }
    summary["overall"]["ratio"] = summary["overall"]["compressed"] / summary["overall"]["orig"]
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["all_rt_cmp0"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
