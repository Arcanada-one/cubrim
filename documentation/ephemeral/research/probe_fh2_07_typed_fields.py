#!/usr/bin/env python3
"""FH2-07 research probe: typed value-delta contexts over fixed records."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import time


_TOP = (1 << 32) - 1
_HALF = 1 << 31
_QUARTER = 1 << 30
_THREE_QUARTERS = 3 << 30
_COUNT_LIMIT = 1 << 15


class _BitWriter:
    def __init__(self) -> None:
        self.output = bytearray()
        self.byte = 0
        self.used = 0

    def write(self, bit: int) -> None:
        self.byte = (self.byte << 1) | bit
        self.used += 1
        if self.used == 8:
            self.output.append(self.byte)
            self.byte = 0
            self.used = 0

    def finish(self) -> bytes:
        if self.used:
            self.output.append(self.byte << (8 - self.used))
        return bytes(self.output)


class _BitReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.bit_pos = 0

    def read(self) -> int:
        byte_pos, bit_in_byte = divmod(self.bit_pos, 8)
        self.bit_pos += 1
        if byte_pos >= len(self.payload):
            return 0
        return (self.payload[byte_pos] >> (7 - bit_in_byte)) & 1


class _Counts:
    def __init__(self) -> None:
        self.cells: dict[Hashable, list[int]] = {}

    def get(self, context: Hashable) -> list[int]:
        return self.cells.setdefault(context, [1, 1])

    @staticmethod
    def update(counts: list[int], bit: int) -> None:
        counts[bit] += 1
        if counts[0] + counts[1] >= _COUNT_LIMIT:
            counts[0] = (counts[0] + 1) >> 1
            counts[1] = (counts[1] + 1) >> 1


class _ArithmeticEncoder:
    def __init__(self) -> None:
        self.low = 0
        self.high = _TOP
        self.pending = 0
        self.writer = _BitWriter()

    def _emit(self, bit: int) -> None:
        self.writer.write(bit)
        for _ in range(self.pending):
            self.writer.write(bit ^ 1)
        self.pending = 0

    def encode(self, bit: int, count0: int, count1: int) -> None:
        span = self.high - self.low + 1
        split = self.low + span * count0 // (count0 + count1) - 1
        if bit == 0:
            self.high = split
        else:
            self.low = split + 1
        while True:
            if self.high < _HALF:
                self._emit(0)
            elif self.low >= _HALF:
                self._emit(1)
                self.low -= _HALF
                self.high -= _HALF
            elif self.low >= _QUARTER and self.high < _THREE_QUARTERS:
                self.pending += 1
                self.low -= _QUARTER
                self.high -= _QUARTER
            else:
                break
            self.low = (self.low << 1) & _TOP
            self.high = ((self.high << 1) | 1) & _TOP

    def finish(self) -> bytes:
        self.pending += 1
        self._emit(0 if self.low < _QUARTER else 1)
        return self.writer.finish()


class _ArithmeticDecoder:
    def __init__(self, payload: bytes) -> None:
        self.reader = _BitReader(payload)
        self.low = 0
        self.high = _TOP
        self.value = 0
        for _ in range(32):
            self.value = ((self.value << 1) | self.reader.read()) & _TOP

    def decode(self, count0: int, count1: int) -> int:
        span = self.high - self.low + 1
        split = self.low + span * count0 // (count0 + count1) - 1
        if self.value <= split:
            bit = 0
            self.high = split
        else:
            bit = 1
            self.low = split + 1
        while True:
            if self.high < _HALF:
                pass
            elif self.low >= _HALF:
                self.low -= _HALF
                self.high -= _HALF
                self.value -= _HALF
            elif self.low >= _QUARTER and self.high < _THREE_QUARTERS:
                self.low -= _QUARTER
                self.high -= _QUARTER
                self.value -= _QUARTER
            else:
                break
            self.low = (self.low << 1) & _TOP
            self.high = ((self.high << 1) | 1) & _TOP
            self.value = ((self.value << 1) | self.reader.read()) & _TOP
        return bit


def encode_bits(bits: Iterable[int], contexts: Iterable[Hashable]) -> bytes:
    encoder = _ArithmeticEncoder()
    model = _Counts()
    for bit, context in zip(bits, contexts, strict=True):
        counts = model.get(context)
        encoder.encode(bit, counts[0], counts[1])
        model.update(counts, bit)
    return encoder.finish()


def decode_bits(payload: bytes, contexts: Sequence[Hashable], bit_count: int) -> list[int]:
    decoder = _ArithmeticDecoder(payload)
    model = _Counts()
    output: list[int] = []
    for context in contexts[:bit_count]:
        counts = model.get(context)
        bit = decoder.decode(counts[0], counts[1])
        model.update(counts, bit)
        output.append(bit)
    return output


_KIND_WIDTH = {"u8": 1, "u16le": 2, "u32le": 4, "f32le": 4}
_KIND_CODE = {"u8": 0, "u16le": 1, "u32le": 2, "f32le": 3}
_CODE_KIND = {code: kind for kind, code in _KIND_CODE.items()}
_MAGIC = b"FH207"
_VERSION = 1
_BASE_HEADER = 17
_SAO_SIZE = 7_251_944
_SAO_SHA256 = "c2d0ea2cc59d4c21b7fe43a71499342a00cbe530a1d5548770e91ecd6214adcc"


@dataclass(frozen=True)
class Field:
    offset: int
    kind: str

    @property
    def width(self) -> int:
        return _KIND_WIDTH[self.kind]


def detect_width(data: bytes, minimum_size: int = 8192) -> int:
    """Mirror FH-10's bounded lag-L1 stride detector."""
    if len(data) < minimum_size:
        raise ValueError("input is too small for width detection")
    sample_n = min(len(data), 1 << 18)
    costs: dict[int, int] = {}
    for width in range(4, 65):
        if len(data) // width < 8:
            continue
        total = sum(abs(data[pos] - data[pos - width]) for pos in range(width, sample_n))
        costs[width] = total // max(1, sample_n - width)
    if not costs:
        raise ValueError("no width candidates")
    best = min(costs.values())
    ordered = sorted(costs.values())
    median = ordered[len(ordered) // 2]
    if best * 100 >= median * 80:
        raise ValueError("no sharp fixed-record stride")
    threshold = best + best // 33 + 1
    return next(width for width in range(4, 65) if costs.get(width, 1 << 60) <= threshold)


def _validate_schema(schema: Sequence[Field], width: int) -> None:
    expected = 0
    for field in schema:
        if field.kind not in _KIND_WIDTH or field.offset != expected:
            raise ValueError("schema must cover the record contiguously")
        expected += field.width
    if expected != width:
        raise ValueError("schema width mismatch")


def _field_value(history: bytes | bytearray, record: int, width: int, field: Field):
    start = record * width + field.offset
    raw = bytes(history[start:start + field.width])
    if len(raw) != field.width:
        raise ValueError("field history is incomplete")
    if field.kind == "f32le":
        return struct.unpack("<f", raw)[0]
    return int.from_bytes(raw, "little")


def _delta_features(
    history: bytes | bytearray,
    record: int,
    width: int,
    field: Field,
) -> tuple[int, int, int]:
    """Return (bucket, sign, predicted raw bits), using completed records only."""
    raw_bits = field.width * 8
    mask = (1 << raw_bits) - 1
    if record < 2:
        return 0, 0, 0
    previous = _field_value(history, record - 1, width, field)
    before = _field_value(history, record - 2, width, field)
    if field.kind == "f32le":
        if not (math.isfinite(previous) and math.isfinite(before)):
            return 15, 0, 0
        delta = previous - before
        predicted = previous + delta
        if not math.isfinite(predicted):
            predicted_bits = 0
        else:
            try:
                predicted_bits = int.from_bytes(struct.pack("<f", predicted), "little")
            except (OverflowError, struct.error):
                predicted_bits = 0
        if delta == 0.0:
            bucket = 0
        elif math.isfinite(delta):
            bucket = max(1, min(15, math.frexp(abs(delta))[1] + 7))
        else:
            bucket = 15
        return bucket, int(delta < 0.0), predicted_bits
    previous_int = int(previous)
    before_int = int(before)
    delta = (previous_int - before_int) & mask
    if delta >= 1 << (raw_bits - 1):
        delta -= 1 << raw_bits
    predicted_bits = (previous_int + delta) & mask
    bucket = min(15, abs(delta).bit_length())
    return bucket, int(delta < 0), predicted_bits


def _field_map(schema: Sequence[Field], width: int) -> list[tuple[int, Field, int]]:
    mapping: list[tuple[int, Field, int] | None] = [None] * width
    for field_id, field in enumerate(schema):
        for byte_index in range(field.width):
            mapping[field.offset + byte_index] = (field_id, field, byte_index)
    if any(item is None for item in mapping):
        raise ValueError("schema leaves uncovered bytes")
    return [item for item in mapping if item is not None]


def _context(
    variant: str,
    history: bytearray,
    width: int,
    mapping: Sequence[tuple[int, Field, int]] | None,
    c0: int,
) -> Hashable:
    position = len(history)
    offset = position % width
    record = position // width
    if variant == "baseline":
        has_previous = record > 0
        previous = history[position - width] if has_previous else 0
        return (offset, has_previous, previous, c0)
    if variant != "typed" or mapping is None:
        raise ValueError(f"unknown variant: {variant}")
    field_id, field, byte_index = mapping[offset]
    bucket, sign, predicted = _delta_features(history, record, width, field)
    predicted_byte = (predicted >> (8 * byte_index)) & 0xFF
    bit_index = c0.bit_length() - 1
    predicted_bit = (predicted_byte >> (7 - bit_index)) & 1
    if byte_index == 0:
        lower_relation = 0
    else:
        start = record * width + field.offset
        current_lower = int.from_bytes(history[start:position], "little")
        lower_mask = (1 << (8 * byte_index)) - 1
        predicted_lower = predicted & lower_mask
        lower_relation = 0 if current_lower == predicted_lower else (1 if current_lower < predicted_lower else 2)
    return (field_id, byte_index, bucket, sign, lower_relation, predicted_bit, c0)


def context_trace(
    data: bytes,
    width: int,
    schema: Sequence[Field],
    variant: str,
    stop_position: int,
) -> list[Hashable]:
    if variant == "typed":
        _validate_schema(schema, width)
        mapping = _field_map(schema, width)
    else:
        mapping = None
    history = bytearray()
    trace: list[Hashable] = []
    for byte in data[:stop_position]:
        c0 = 1
        for shift in range(7, -1, -1):
            trace.append(_context(variant, history, width, mapping, c0))
            c0 = (c0 << 1) | ((byte >> shift) & 1)
        history.append(byte)
    return trace


def _candidate_cost(data: bytes, record_width: int, field: Field, records: int) -> float:
    sample = data[:records * record_width]
    schema = [Field(0, field.kind)]
    local = bytearray()
    counts = _Counts()
    cost = 8.0  # one transmitted schema byte
    for record in range(records):
        source = record * record_width + field.offset
        for byte_index in range(field.width):
            byte = sample[source + byte_index]
            c0 = 1
            for shift in range(7, -1, -1):
                context = _context("typed", local, field.width, _field_map(schema, field.width), c0)
                cell = counts.get(context)
                bit = (byte >> shift) & 1
                cost -= math.log2(cell[bit] / (cell[0] + cell[1]))
                counts.update(cell, bit)
                c0 = (c0 << 1) | bit
            local.append(byte)
    return cost


def detect_schema(data: bytes, width: int, training_records: int = 4096) -> list[Field]:
    """Choose a charged typed partition by held-prefix prequential bit cost."""
    records = min(training_records, len(data) // width)
    if records < 8:
        raise ValueError("too few complete records for schema detection")
    best: list[tuple[float, list[Field]] | None] = [None] * (width + 1)
    best[0] = (0.0, [])
    candidates = ("u8", "u16le", "u32le", "f32le")
    for offset in range(width):
        if best[offset] is None:
            continue
        base_cost, base_schema = best[offset]
        for kind in candidates:
            field = Field(offset, kind)
            end = offset + field.width
            if end > width:
                continue
            score = base_cost + _candidate_cost(data, width, field, records)
            current = best[end]
            candidate_schema = base_schema + [field]
            if current is None or score < current[0] - 1e-9:
                best[end] = (score, candidate_schema)
    if best[width] is None:
        raise ValueError("could not infer a complete schema")
    return best[width][1]


def _encode_model(data: bytes, width: int, schema: Sequence[Field], variant: str):
    mapping = _field_map(schema, width) if variant == "typed" else None
    history = bytearray()
    model = _Counts()
    encoder = _ArithmeticEncoder()
    for byte in data:
        c0 = 1
        for shift in range(7, -1, -1):
            context = _context(variant, history, width, mapping, c0)
            counts = model.get(context)
            bit = (byte >> shift) & 1
            encoder.encode(bit, counts[0], counts[1])
            model.update(counts, bit)
            c0 = (c0 << 1) | bit
        history.append(byte)
    return encoder.finish(), len(model.cells)


def encode_archive(
    data: bytes,
    width: int,
    schema: Sequence[Field],
    variant: str,
) -> tuple[bytes, dict[str, int]]:
    if not 4 <= width <= 64 or len(data) > (1 << 64) - 1:
        raise ValueError("invalid width or input length")
    if variant == "typed":
        _validate_schema(schema, width)
        schema_bytes = bytes(_KIND_CODE[field.kind] for field in schema)
        variant_code = 1
    elif variant == "baseline":
        schema_bytes = b""
        variant_code = 0
    else:
        raise ValueError(f"unknown variant: {variant}")
    payload, context_count = _encode_model(data, width, schema, variant)
    header = (
        _MAGIC
        + bytes((_VERSION, variant_code))
        + len(data).to_bytes(8, "big")
        + bytes((width, len(schema_bytes)))
        + schema_bytes
    )
    blob = header + payload
    stats = {
        "payload_size": len(payload),
        "header_size": len(header),
        "schema_bytes": len(schema_bytes),
        "charged_size": len(blob),
        "contexts": context_count,
    }
    return blob, stats


def _parse_header(blob: bytes):
    if len(blob) < _BASE_HEADER or blob[:5] != _MAGIC or blob[5] != _VERSION:
        raise ValueError("bad FH2-07 archive header")
    variant_code = blob[6]
    length = int.from_bytes(blob[7:15], "big")
    width = blob[15]
    field_count = blob[16]
    header_size = _BASE_HEADER + field_count
    if len(blob) < header_size:
        raise ValueError("truncated FH2-07 schema")
    if variant_code == 0:
        if field_count:
            raise ValueError("baseline archive must not carry a schema")
        return "baseline", length, width, [], header_size
    if variant_code != 1:
        raise ValueError("unknown FH2-07 model")
    schema: list[Field] = []
    offset = 0
    for code in blob[_BASE_HEADER:header_size]:
        kind = _CODE_KIND.get(code)
        if kind is None:
            raise ValueError("unknown FH2-07 field kind")
        schema.append(Field(offset, kind))
        offset += _KIND_WIDTH[kind]
    _validate_schema(schema, width)
    return "typed", length, width, schema, header_size


def decode_archive(blob: bytes) -> bytes:
    variant, length, width, schema, header_size = _parse_header(blob)
    mapping = _field_map(schema, width) if variant == "typed" else None
    decoder = _ArithmeticDecoder(blob[header_size:])
    model = _Counts()
    history = bytearray()
    for _ in range(length):
        byte = 0
        c0 = 1
        for _bit_index in range(8):
            context = _context(variant, history, width, mapping, c0)
            counts = model.get(context)
            bit = decoder.decode(counts[0], counts[1])
            model.update(counts, bit)
            byte = (byte << 1) | bit
            c0 = (c0 << 1) | bit
        history.append(byte)
    return bytes(history)


def run_probe(
    data: bytes,
    width: int,
    schema: Sequence[Field],
    archive_prefix: Path | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "input_size": len(data),
        "width": width,
        "schema": [{"offset": field.offset, "kind": field.kind} for field in schema],
    }
    archives: dict[str, bytes] = {}
    for variant in ("baseline", "typed"):
        started = time.monotonic()
        blob, stats = encode_archive(data, width, schema, variant)
        encode_seconds = time.monotonic() - started
        started = time.monotonic()
        decoded = decode_archive(blob)
        decode_seconds = time.monotonic() - started
        archives[variant] = blob
        result[variant] = {
            **stats,
            "archive_size": len(blob),
            "ratio": len(blob) / len(data) if data else 0.0,
            "roundtrip": decoded == data,
            "encode_seconds": encode_seconds,
            "decode_seconds": decode_seconds,
        }
    baseline_size = int(result["baseline"]["charged_size"])  # type: ignore[index]
    typed_size = int(result["typed"]["charged_size"])  # type: ignore[index]
    result["improvement_percent"] = 100.0 * (baseline_size - typed_size) / baseline_size
    result["screen_verdict"] = "PROMISING" if typed_size < baseline_size else "NO-GO"
    if archive_prefix is not None:
        archive_prefix.parent.mkdir(parents=True, exist_ok=True)
        for variant, blob in archives.items():
            archive_prefix.with_name(f"{archive_prefix.name}-{variant}.fh207").write_bytes(blob)
    return result


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--limit", type=int, default=1 << 20)
    parser.add_argument("--training-records", type=int, default=512)
    parser.add_argument("--archive-prefix", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    full_data = args.source.read_bytes()
    source_hash = hashlib.sha256(full_data).hexdigest()
    if len(full_data) != _SAO_SIZE or source_hash != _SAO_SHA256:
        parser.error(
            f"wrong sao corpus: size={len(full_data)} sha256={source_hash}; "
            f"expected size={_SAO_SIZE} sha256={_SAO_SHA256}"
        )
    data = full_data[:args.limit] if args.limit else full_data
    width = detect_width(data)
    schema_started = time.monotonic()
    schema = detect_schema(data, width, args.training_records)
    schema_seconds = time.monotonic() - schema_started
    result = run_probe(data, width, schema, args.archive_prefix)
    result.update(
        {
            "source_size": len(full_data),
            "source_sha256": source_hash,
            "screen_sha256": hashlib.sha256(data).hexdigest(),
            "schema_seconds": schema_seconds,
            "go_threshold_percent": 1.5,
            "priority_note": "binary is already world-benchmark rank #1; margin screen only",
        }
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        args.json_out.write_text(rendered + "\n")
    baseline_rt = bool(result["baseline"]["roundtrip"])  # type: ignore[index]
    typed_rt = bool(result["typed"]["roundtrip"])  # type: ignore[index]
    return 0 if baseline_rt and typed_rt else 2


if __name__ == "__main__":
    raise SystemExit(_main())
