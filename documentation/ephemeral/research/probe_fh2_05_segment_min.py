#!/usr/bin/env python3
"""FH2-05 probe: charged per-tar-member Cubrim competitive-min."""

from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Sequence
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import time


TAR_BLOCK = 512
OUTER_HEADER_BYTES = 24
FRAME_LENGTH_BYTES = 4
MOZILLA_SIZE = 51_220_480
MOZILLA_SHA256 = "657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b"
MOZILLA_MEMBERS = 525
MOZILLA_CUBRIM_BASELINE = 15_788_540
MOZILLA_7Z = 13_342_812


@dataclass(frozen=True)
class Segment:
    index: int
    name: str
    offset: int
    end: int
    payload_size: int
    raw: bytes


@dataclass(frozen=True)
class RoundTripResult:
    label: str
    input_size: int
    blob_size: int
    mode: int
    cmp: int
    encode_seconds: float
    decode_seconds: float
    blob_path: Path
    restored_path: Path


def _tar_number(field: bytes) -> int:
    if field and field[0] & 0x80:
        value = int.from_bytes(field, "big")
        return value & ((1 << (len(field) * 8 - 1)) - 1)
    stripped = field.rstrip(b"\0 ").lstrip(b" ")
    if not stripped:
        return 0
    try:
        return int(stripped, 8)
    except ValueError as error:
        raise ValueError("invalid tar numeric field") from error


def _tar_name(header: bytes) -> str:
    name = header[:100].split(b"\0", 1)[0]
    prefix = header[345:500].split(b"\0", 1)[0]
    combined = prefix + (b"/" if prefix and name else b"") + name
    return combined.decode("utf-8", "surrogateescape")


def parse_tar_segments(data: bytes) -> list[Segment]:
    """Return contiguous raw member frames that reconstruct *data* exactly."""
    if len(data) < TAR_BLOCK:
        raise ValueError("truncated tar header")
    segments: list[Segment] = []
    offset = 0
    group_start = 0
    while offset + TAR_BLOCK <= len(data):
        header = data[offset:offset + TAR_BLOCK]
        if not any(header):
            if not segments:
                raise ValueError("tar contains no members")
            last = segments[-1]
            segments[-1] = replace(last, end=len(data), raw=data[last.offset:])
            return segments
        payload_size = _tar_number(header[124:136])
        padded_size = (payload_size + TAR_BLOCK - 1) // TAR_BLOCK * TAR_BLOCK
        end = offset + TAR_BLOCK + padded_size
        if end > len(data):
            raise ValueError("truncated tar member payload")
        type_flag = header[156:157]
        if type_flag in (b"\0", b"0"):
            segments.append(
                Segment(
                    index=len(segments),
                    name=_tar_name(header),
                    offset=group_start,
                    end=end,
                    payload_size=payload_size,
                    raw=data[group_start:end],
                )
            )
            group_start = end
        offset = end
    if offset != len(data):
        raise ValueError("truncated tar trailer")
    if not segments:
        raise ValueError("tar contains no members")
    return segments


def charged_size(blob_sizes: Sequence[int]) -> int:
    return OUTER_HEADER_BYTES + sum(FRAME_LENGTH_BYTES + size for size in blob_sizes)


def select_screen_prefix(
    segments: Sequence[Segment],
    min_bytes: int = 8 << 20,
    max_members: int = 64,
) -> list[Segment]:
    selected: list[Segment] = []
    total = 0
    for segment in segments:
        if len(selected) >= max_members:
            break
        selected.append(segment)
        total += len(segment.raw)
        if total >= min_bytes:
            break
    if not selected:
        raise ValueError("cannot screen an empty segment list")
    return selected


def run_cubrim_roundtrip(
    cubrim: Path,
    raw: bytes,
    work_dir: Path,
    label: str,
) -> RoundTripResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    source = work_dir / f"{label}.input"
    blob = work_dir / f"{label}.cubrim"
    restored = work_dir / f"{label}.restored"
    source.write_bytes(raw)
    started = time.monotonic()
    subprocess.run(
        [str(cubrim), "compress", "-q", str(source), str(blob)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    encode_seconds = time.monotonic() - started
    started = time.monotonic()
    subprocess.run(
        [str(cubrim), "decompress", str(blob), str(restored)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    decode_seconds = time.monotonic() - started
    blob_data = blob.read_bytes()
    restored_data = restored.read_bytes()
    return RoundTripResult(
        label=label,
        input_size=len(raw),
        blob_size=len(blob_data),
        mode=blob_data[5] if len(blob_data) > 5 else -1,
        cmp=0 if restored_data == raw else 1,
        encode_seconds=encode_seconds,
        decode_seconds=decode_seconds,
        blob_path=blob,
        restored_path=restored,
    )


def _result_dict(result: RoundTripResult) -> dict[str, object]:
    return {
        "label": result.label,
        "input_size": result.input_size,
        "blob_size": result.blob_size,
        "mode": result.mode,
        "cmp": result.cmp,
        "encode_seconds": result.encode_seconds,
        "decode_seconds": result.decode_seconds,
    }


def _relative_improvement(baseline: int, candidate: int) -> float:
    return 100.0 * (baseline - candidate) / baseline


def run_probe(
    data: bytes,
    cubrim: Path,
    work_dir: Path,
    *,
    expected_baseline_size: int,
    expected_members: int,
    jobs: int = 2,
    screen_min_bytes: int = 8 << 20,
    screen_max_members: int = 64,
) -> dict[str, object]:
    segments = parse_tar_segments(data)
    if len(segments) != expected_members:
        raise ValueError(f"member count mismatch: {len(segments)} != {expected_members}")
    baseline = run_cubrim_roundtrip(cubrim, data, work_dir / "whole", "full-baseline")
    if baseline.cmp != 0:
        raise ValueError("whole-file Cubrim baseline failed round-trip")
    if baseline.blob_size != expected_baseline_size:
        raise ValueError(
            f"whole-file baseline mismatch: {baseline.blob_size} != {expected_baseline_size}"
        )

    screen_segments = select_screen_prefix(segments, screen_min_bytes, screen_max_members)
    screen_raw = data[:screen_segments[-1].end]
    screen_baseline = run_cubrim_roundtrip(
        cubrim, screen_raw, work_dir / "screen", "screen-baseline"
    )
    cache: dict[int, RoundTripResult] = {}

    def encode_segment(segment: Segment) -> tuple[int, RoundTripResult]:
        result = run_cubrim_roundtrip(
            cubrim,
            segment.raw,
            work_dir / "segments",
            f"seg-{segment.index:04d}",
        )
        if result.cmp != 0:
            raise ValueError(f"segment {segment.index} failed round-trip")
        return segment.index, result

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for index, result in pool.map(encode_segment, screen_segments):
            cache[index] = result
    screen_charged = charged_size([cache[segment.index].blob_size for segment in screen_segments])
    screen_improvement = _relative_improvement(screen_baseline.blob_size, screen_charged)
    proceed_full = screen_improvement >= -5.0

    output: dict[str, object] = {
        "input_size": len(data),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "member_count": len(segments),
        "baseline": _result_dict(baseline),
        "seven_zip": {
            "blob_size": MOZILLA_7Z,
            "ratio": MOZILLA_7Z / len(data),
        },
        "screen": {
            "members": len(screen_segments),
            "input_size": len(screen_raw),
            "whole_blob_size": screen_baseline.blob_size,
            "segmented_charged_size": screen_charged,
            "improvement_percent": screen_improvement,
            "proceed_full": proceed_full,
        },
    }
    if not proceed_full:
        output["full"] = None
        output["verdict"] = "SCREEN NO-GO"
        return output

    remaining = [segment for segment in segments if segment.index not in cache]
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for index, result in pool.map(encode_segment, remaining):
            cache[index] = result
    ordered = [cache[segment.index] for segment in segments]
    reconstructed = b"".join(result.restored_path.read_bytes() for result in ordered)
    full_cmp = 0 if reconstructed == data else 1
    full_charged = charged_size([result.blob_size for result in ordered])
    full_improvement = _relative_improvement(baseline.blob_size, full_charged)
    verdict = "GO" if full_cmp == 0 and full_improvement >= 1.5 else "NO-GO"
    modes: dict[str, int] = {}
    for result in ordered:
        modes[str(result.mode)] = modes.get(str(result.mode), 0) + 1
    output["full"] = {
        "charged_size": full_charged,
        "ratio": full_charged / len(data),
        "improvement_percent": full_improvement,
        "cmp": full_cmp,
        "verdict": verdict,
        "mode_counts": modes,
        "segments": [
            {
                "index": segment.index,
                "name": segment.name,
                "offset": segment.offset,
                "input_size": len(segment.raw),
                **_result_dict(cache[segment.index]),
            }
            for segment in segments
        ],
    }
    output["verdict"] = verdict
    return output


def _write_tsv(path: Path, result: dict[str, object]) -> None:
    full = result.get("full")
    if not isinstance(full, dict) or not isinstance(full.get("segments"), list):
        return
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=("index", "name", "offset", "input_size", "blob_size", "mode", "cmp",
                        "encode_seconds", "decode_seconds", "label"),
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(full["segments"])


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cubrim", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--tsv-out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    data = args.source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != MOZILLA_SIZE or digest != MOZILLA_SHA256:
        parser.error(
            f"wrong mozilla corpus: size={len(data)} sha256={digest}; "
            f"expected size={MOZILLA_SIZE} sha256={MOZILLA_SHA256}"
        )
    result = run_probe(
        data,
        args.cubrim,
        args.work_dir,
        expected_baseline_size=MOZILLA_CUBRIM_BASELINE,
        expected_members=MOZILLA_MEMBERS,
        jobs=args.jobs,
    )
    result["cubrim_binary_sha256"] = hashlib.sha256(args.cubrim.read_bytes()).hexdigest()
    rendered = json.dumps(result, indent=2, sort_keys=True)
    args.json_out.write_text(rendered + "\n")
    _write_tsv(args.tsv_out, result)
    print(rendered)
    full = result.get("full")
    if isinstance(full, dict) and full.get("cmp") != 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
