#!/usr/bin/env python3
"""Independent full-24 competitor baseline with byte-exact round trips."""

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
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusFile:
    corpus: str
    name: str
    kind: str
    size: int

    @property
    def relative(self) -> str:
        return f"{self.corpus}/{self.name}"


MANIFEST = (
    CorpusFile("silesia", "dickens", "text", 10_192_446),
    CorpusFile("silesia", "mozilla", "exe", 51_220_480),
    CorpusFile("silesia", "mr", "image", 9_970_564),
    CorpusFile("silesia", "nci", "database", 33_553_445),
    CorpusFile("silesia", "ooffice", "exe", 6_152_192),
    CorpusFile("silesia", "osdb", "database", 10_085_684),
    CorpusFile("silesia", "reymont", "text", 6_627_202),
    CorpusFile("silesia", "samba", "code", 21_606_400),
    CorpusFile("silesia", "sao", "binary", 7_251_944),
    CorpusFile("silesia", "webster", "text", 41_458_703),
    CorpusFile("silesia", "x-ray", "image", 8_474_240),
    CorpusFile("silesia", "xml", "text", 5_345_280),
    CorpusFile("enwik8", "enwik8", "text", 100_000_000),
    CorpusFile("canterbury", "alice29.txt", "text", 152_089),
    CorpusFile("canterbury", "asyoulik.txt", "text", 125_179),
    CorpusFile("canterbury", "cp.html", "text", 24_603),
    CorpusFile("canterbury", "fields.c", "code", 11_150),
    CorpusFile("canterbury", "grammar.lsp", "code", 3_721),
    CorpusFile("canterbury", "kennedy.xls", "binary", 1_029_744),
    CorpusFile("canterbury", "lcet10.txt", "text", 426_754),
    CorpusFile("canterbury", "plrabn12.txt", "text", 481_861),
    CorpusFile("canterbury", "ptt5", "image", 513_216),
    CorpusFile("canterbury", "sum", "binary", 38_240),
    CorpusFile("canterbury", "xargs.1", "text", 4_227),
)

CODECS = ("7z", "ppmd", "xz", "brotli", "zstd", "bzip2", "gzip", "rar", "lz4")


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


def command_pair(codec: str, source: Path, archive: Path, restored: Path) -> tuple[list[str], list[str]]:
    if codec == "7z":
        return (
            ["7z", "a", "-bd", "-y", "-t7z", "-m0=LZMA2", "-mx9", str(archive), source.name],
            ["7z", "x", "-bd", "-y", str(archive), f"-o{restored.parent}"],
        )
    if codec == "ppmd":
        # Reverse-verified against live rows on grammar.lsp, dickens, and
        # webster, and mozilla: the published generic `7z -m0=PPMd` label
        # corresponds to order 6 with a 256 MiB model.  Do not inherit 7z's
        # level-dependent defaults (mx5 uses much less memory on large files).
        return (
            ["7z", "a", "-bd", "-y", "-t7z", "-m0=PPMd:o6:mem256m", str(archive), source.name],
            ["7z", "x", "-bd", "-y", str(archive), f"-o{restored.parent}"],
        )
    if codec == "rar":
        return (
            ["rar", "a", "-idq", "-y", "-m5", "-ep", str(archive), source.name],
            ["rar", "x", "-idq", "-y", "-o+", str(archive), f"{restored.parent}/"],
        )
    stream = {
        "xz": (["xz", "-9e", "-c", source.name], ["xz", "-d", "-c", str(archive)]),
        "brotli": (["brotli", "-q", "11", "-c", source.name], ["brotli", "-d", "-c", str(archive)]),
        "zstd": (["zstd", "--ultra", "-22", "-q", "-c", source.name], ["zstd", "-d", "-q", "-c", str(archive)]),
        "bzip2": (["bzip2", "-9", "-c", source.name], ["bzip2", "-d", "-c", str(archive)]),
        "gzip": (["gzip", "-9", "-c", source.name], ["gzip", "-d", "-c", str(archive)]),
        "lz4": (["lz4", "-12", "-q", "-c", source.name], ["lz4", "-d", "-q", "-c", str(archive)]),
    }
    return stream[codec]


def run_one(codec: str, source: Path, work: Path, logs: Path, timeout: int) -> dict[str, object]:
    row_dir = work / codec
    restored_dir = row_dir / "restored"
    restored_dir.mkdir(parents=True, exist_ok=True)
    extension = {"7z": "7z", "ppmd": "7z", "rar": "rar"}.get(codec, codec)
    archive = row_dir / f"archive.{extension}"
    restored = restored_dir / source.name
    encode, decode = command_pair(codec, source, archive, restored)
    encode_log = logs / f"{codec}.encode.log"
    decode_log = logs / f"{codec}.decode.log"
    archive_codec = codec in {"7z", "ppmd", "rar"}

    started = time.monotonic()
    with encode_log.open("wb") as err:
        if archive_codec:
            encoded = subprocess.run(
                encode,
                cwd=source.parent,
                stdout=subprocess.DEVNULL,
                stderr=err,
                timeout=timeout,
                check=False,
            )
        else:
            with archive.open("wb") as out:
                encoded = subprocess.run(
                    encode,
                    cwd=source.parent,
                    stdout=out,
                    stderr=err,
                    timeout=timeout,
                    check=False,
                )
    encode_seconds = time.monotonic() - started
    compressed = archive.stat().st_size if encoded.returncode == 0 and archive.is_file() else 0

    decode_rc = -1
    decode_seconds = 0.0
    cmp0 = False
    if compressed:
        started = time.monotonic()
        with decode_log.open("wb") as err:
            if archive_codec:
                decoded = subprocess.run(
                    decode,
                    cwd=source.parent,
                    stdout=subprocess.DEVNULL,
                    stderr=err,
                    timeout=timeout,
                    check=False,
                )
            else:
                with restored.open("wb") as out:
                    decoded = subprocess.run(
                        decode,
                        cwd=source.parent,
                        stdout=out,
                        stderr=err,
                        timeout=timeout,
                        check=False,
                    )
        decode_seconds = time.monotonic() - started
        decode_rc = decoded.returncode
        cmp0 = decode_rc == 0 and restored.is_file() and same_bytes(source, restored)

    result = {
        "codec": codec,
        "compressed": compressed,
        "ratio": compressed / source.stat().st_size if compressed else None,
        "encode_rc": encoded.returncode,
        "decode_rc": decode_rc,
        "cmp": 0 if cmp0 else 1,
        "encode_seconds": encode_seconds,
        "decode_seconds": decode_seconds,
        "archive_sha256": sha256(archive) if compressed else "",
    }
    shutil.rmtree(row_dir)
    return result


def capture_versions(output: Path) -> None:
    probes = {
        "7z": ["7z"],
        "rar": ["rar"],
        "xz": ["xz", "--version"],
        "brotli": ["brotli", "--version"],
        "zstd": ["zstd", "--version"],
        "bzip2": ["bzip2", "--help"],
        "gzip": ["gzip", "--version"],
        "lz4": ["lz4", "--version"],
    }
    with output.open("w") as handle:
        for name, command in probes.items():
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            first = proc.stdout.decode(errors="replace").splitlines()[:5]
            handle.write(f"[{name}] rc={proc.returncode}\n")
            handle.write("\n".join(first) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("/root/corpus-full"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", help="optional exact corpus/file smoke selection")
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=False)
    work = args.output / "work"
    work.mkdir()
    capture_versions(args.output / "versions.txt")
    manifest = [item for item in MANIFEST if args.only in (None, item.relative)]
    if not manifest:
        parser.error(f"--only did not match: {args.only}")

    manifest_rows = []
    for item in manifest:
        source = args.corpus / item.corpus / item.name
        actual = source.stat().st_size if source.is_file() else -1
        if actual != item.size:
            raise RuntimeError(f"manifest mismatch {source}: {actual} != {item.size}")
        manifest_rows.append((item.corpus, item.name, item.kind, item.size, sha256(source)))
    with (args.output / "manifest.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("corpus", "file", "type", "orig", "sha256"))
        writer.writerows(manifest_rows)

    columns = (
        "corpus", "file", "type", "orig", "codec", "compressed", "ratio",
        "encode_rc", "decode_rc", "cmp", "encode_seconds", "decode_seconds", "archive_sha256",
    )
    rows: list[dict[str, object]] = []
    with (args.output / "results.tsv").open("w", newline="", buffering=1) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for item in manifest:
            source = args.corpus / item.corpus / item.name
            for codec in CODECS:
                logs = args.output / "logs" / item.corpus / item.name
                logs.mkdir(parents=True, exist_ok=True)
                result = run_one(codec, source, work / item.corpus / item.name, logs, args.timeout)
                row = {
                    "corpus": item.corpus,
                    "file": item.name,
                    "type": item.kind,
                    "orig": item.size,
                    **result,
                }
                rows.append(row)
                writer.writerow(row)
                print(
                    f"ROW {item.relative} {codec} orig={item.size} comp={result['compressed']} "
                    f"ratio={result['ratio']} cmp={result['cmp']}",
                    flush=True,
                )

    by_type: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        if row["encode_rc"] != 0 or row["decode_rc"] != 0 or row["cmp"] != 0:
            continue
        bucket = by_type[str(row["type"])][str(row["codec"])]
        bucket[0] += int(row["compressed"])
        bucket[1] += int(row["orig"])
    aggregates = {
        kind: {
            codec: {"compressed": values[0], "orig": values[1], "ratio": values[0] / values[1]}
            for codec, values in sorted(codecs.items())
        }
        for kind, codecs in sorted(by_type.items())
    }
    (args.output / "aggregate_by_type.json").write_text(json.dumps(aggregates, indent=2, sort_keys=True) + "\n")
    failures = [row for row in rows if row["encode_rc"] != 0 or row["decode_rc"] != 0 or row["cmp"] != 0]
    summary = {
        "files": len(manifest),
        "expected_rows": len(manifest) * len(CODECS),
        "rows": len(rows),
        "failures": failures,
        "all_rt_cmp0": not failures,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
