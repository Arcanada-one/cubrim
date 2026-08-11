#!/usr/bin/env python3
"""FH2-04 probe: charged similarity reordering of tar file frames."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
import time


TAR_BLOCK = 512
PERMUTATION_HEADER_BYTES = 24
MOZILLA_SIZE = 51_220_480
MOZILLA_SHA256 = "657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b"
MOZILLA_MEMBERS = 525


@dataclass(frozen=True)
class Frame:
    index: int
    name: str
    offset: int
    end: int
    payload_size: int
    payload: bytes
    raw: bytes


@dataclass(frozen=True)
class TarLayout:
    frames: tuple[Frame, ...]
    trailer: bytes


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


def parse_tar_layout(data: bytes, allow_missing_trailer: bool = False) -> TarLayout:
    if len(data) < TAR_BLOCK:
        raise ValueError("truncated tar header")
    frames: list[Frame] = []
    offset = 0
    group_start = 0
    while offset + TAR_BLOCK <= len(data):
        header = data[offset:offset + TAR_BLOCK]
        if not any(header):
            if not frames:
                raise ValueError("tar contains no regular files")
            return TarLayout(tuple(frames), data[group_start:])
        payload_size = _tar_number(header[124:136])
        padded_size = (payload_size + TAR_BLOCK - 1) // TAR_BLOCK * TAR_BLOCK
        end = offset + TAR_BLOCK + padded_size
        if end > len(data):
            raise ValueError("truncated tar member payload")
        if header[156:157] in (b"\0", b"0"):
            payload_start = offset + TAR_BLOCK
            frames.append(
                Frame(
                    index=len(frames),
                    name=_tar_name(header),
                    offset=group_start,
                    end=end,
                    payload_size=payload_size,
                    payload=data[payload_start:payload_start + payload_size],
                    raw=data[group_start:end],
                )
            )
            group_start = end
        offset = end
    if allow_missing_trailer and offset == len(data) and frames:
        return TarLayout(tuple(frames), data[group_start:])
    raise ValueError("truncated tar trailer")


def _histogram(payload: bytes) -> tuple[int, ...]:
    counts = [0] * 256
    for byte in payload:
        counts[byte] += 1
    if not payload:
        return tuple(counts)
    total = len(payload)
    return tuple(count * 65535 // total for count in counts)


def similarity_order(frames: Sequence[Frame]) -> list[int]:
    if not frames:
        raise ValueError("cannot order zero frames")
    signatures = [_histogram(frame.payload) for frame in frames]
    current = min(range(len(frames)), key=lambda index: (-frames[index].payload_size, index))
    order = [current]
    remaining = set(range(len(frames)))
    remaining.remove(current)
    while remaining:
        signature = signatures[current]
        current = min(
            remaining,
            key=lambda index: (
                sum(abs(left - right) for left, right in zip(signature, signatures[index])),
                index,
            ),
        )
        remaining.remove(current)
        order.append(current)
    return order


def _validate_order(order: Sequence[int], count: int) -> None:
    if len(order) != count or sorted(order) != list(range(count)):
        raise ValueError("invalid frame permutation")


def apply_order(layout: TarLayout, order: Sequence[int]) -> bytes:
    _validate_order(order, len(layout.frames))
    return b"".join(layout.frames[index].raw for index in order) + layout.trailer


def restore_order(
    reordered: bytes,
    order: Sequence[int],
    allow_missing_trailer: bool = False,
) -> bytes:
    layout = parse_tar_layout(reordered, allow_missing_trailer)
    _validate_order(order, len(layout.frames))
    original: list[bytes | None] = [None] * len(order)
    for reordered_index, original_index in enumerate(order):
        original[original_index] = layout.frames[reordered_index].raw
    return b"".join(frame for frame in original if frame is not None) + layout.trailer


def permutation_charge(member_count: int) -> int:
    if member_count <= 1:
        return PERMUTATION_HEADER_BYTES
    bits_per_index = math.ceil(math.log2(member_count))
    return PERMUTATION_HEADER_BYTES + (member_count * bits_per_index + 7) // 8


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--screen-members", type=int, default=64)
    args = parser.parse_args()

    source = args.source.read_bytes()
    source_hash = _sha256(source)
    if len(source) != MOZILLA_SIZE or source_hash != MOZILLA_SHA256:
        parser.error(
            f"wrong mozilla corpus: size={len(source)} sha256={source_hash}; "
            f"expected size={MOZILLA_SIZE} sha256={MOZILLA_SHA256}"
        )
    started = time.monotonic()
    layout = parse_tar_layout(source)
    if len(layout.frames) != MOZILLA_MEMBERS:
        parser.error(f"regular-file count mismatch: {len(layout.frames)} != {MOZILLA_MEMBERS}")
    full_order = similarity_order(layout.frames)
    full_reordered = apply_order(layout, full_order)
    full_restored = restore_order(full_reordered, full_order)
    if full_restored != source:
        raise RuntimeError("full inverse permutation is not byte-exact")

    screen_count = min(args.screen_members, len(layout.frames))
    screen_layout = TarLayout(layout.frames[:screen_count], b"")
    screen_original = b"".join(frame.raw for frame in screen_layout.frames)
    screen_order = similarity_order(screen_layout.frames)
    screen_reordered = apply_order(screen_layout, screen_order)
    screen_restored = restore_order(screen_reordered, screen_order, allow_missing_trailer=True)
    if screen_restored != screen_original:
        raise RuntimeError("screen inverse permutation is not byte-exact")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "full-reordered.tar": full_reordered,
        "full-restored.tar": full_restored,
        "screen-original.tar": screen_original,
        "screen-reordered.tar": screen_reordered,
        "screen-restored.tar": screen_restored,
    }
    for name, data in outputs.items():
        (args.output_dir / name).write_bytes(data)
    (args.output_dir / "full-order.json").write_text(json.dumps(full_order) + "\n")
    (args.output_dir / "screen-order.json").write_text(json.dumps(screen_order) + "\n")
    summary = {
        "source_size": len(source),
        "source_sha256": source_hash,
        "members": len(layout.frames),
        "directory_headers": 318,
        "trailer_size": len(layout.trailer),
        "full": {
            "charge": permutation_charge(len(layout.frames)),
            "changed_positions": sum(index != value for index, value in enumerate(full_order)),
            "order_sha256": _sha256(json.dumps(full_order, separators=(",", ":")).encode()),
            "reordered_sha256": _sha256(full_reordered),
            "restored_sha256": _sha256(full_restored),
        },
        "screen": {
            "members": screen_count,
            "input_size": len(screen_original),
            "input_sha256": _sha256(screen_original),
            "charge": permutation_charge(screen_count),
            "changed_positions": sum(index != value for index, value in enumerate(screen_order)),
            "order_sha256": _sha256(json.dumps(screen_order, separators=(",", ":")).encode()),
            "reordered_sha256": _sha256(screen_reordered),
            "restored_sha256": _sha256(screen_restored),
        },
        "prepare_seconds": time.monotonic() - started,
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    (args.output_dir / "prepare.json").write_text(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
