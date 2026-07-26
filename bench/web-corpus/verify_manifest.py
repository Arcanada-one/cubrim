#!/usr/bin/env python3
"""Verify the frozen Web Corpus v1 manifest and tracked payloads."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


CORPUS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = CORPUS_ROOT.parents[1]
MANIFEST_PATH = CORPUS_ROOT / "manifest.v1.json"
CHECKSUM_PATH = CORPUS_ROOT / "MANIFEST.sha256"
PAYLOADS_ROOT = (CORPUS_ROOT / "payloads").resolve()
MANIFEST_REPOSITORY_PATH = "bench/web-corpus/manifest.v1.json"

EXPECTED_MEDIA_FAMILIES = {
    "html",
    "css",
    "javascript",
    "source-map",
    "json-api",
    "svg",
    "wasm",
    "woff2",
}
SIZE_CLASS_BOUNDS = {
    "small": (1_024, 10_240),
    "medium": (10_241, 262_144),
    "large": (262_145, 2_097_152),
}
REQUIRED_FIELDS = {
    "sample_id",
    "path",
    "media_type",
    "media_family",
    "size_class",
    "byte_count",
    "sha256",
    "source_ref",
    "license_id",
    "redistributable",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class VerificationError(ValueError):
    """Raised when the frozen corpus violates its manifest contract."""


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def classify_size(byte_count):
    """Return the inclusive corpus size class for a byte count."""
    require(
        isinstance(byte_count, int) and not isinstance(byte_count, bool),
        "byte_count must be an integer",
    )
    for size_class, (lower, upper) in SIZE_CLASS_BOUNDS.items():
        if lower <= byte_count <= upper:
            return size_class
    raise VerificationError("byte_count is outside the supported size classes")


def load_manifest():
    try:
        manifest_bytes = MANIFEST_PATH.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read manifest: {error}") from error

    require(
        manifest_bytes == canonical_json_bytes(manifest),
        "manifest.v1.json is not canonical compact JSON",
    )
    require(isinstance(manifest, dict), "manifest root must be an object")
    require(manifest.get("schema_version") == 1, "schema_version must be 1")
    require(isinstance(manifest.get("samples"), list), "samples must be an array")
    require(manifest["samples"], "samples must not be empty")
    return manifest, manifest_bytes


def verify_checksum(manifest_bytes):
    try:
        checksum_line = CHECKSUM_PATH.read_text(encoding="ascii")
    except OSError as error:
        raise VerificationError(f"cannot read MANIFEST.sha256: {error}") from error

    expected_line = (
        f"{sha256_bytes(manifest_bytes)}  {MANIFEST_REPOSITORY_PATH}\n"
    )
    require(
        checksum_line == expected_line,
        "MANIFEST.sha256 does not match the canonical manifest bytes",
    )


def verify_sample(sample, index):
    label = f"sample[{index}]"
    require(isinstance(sample, dict), f"{label} must be an object")
    missing = REQUIRED_FIELDS - sample.keys()
    require(not missing, f"{label} missing fields: {', '.join(sorted(missing))}")

    for field in (
        "sample_id",
        "path",
        "media_type",
        "media_family",
        "size_class",
        "source_ref",
        "license_id",
    ):
        require(
            isinstance(sample[field], str) and bool(sample[field]),
            f"{label}.{field} must be a non-empty string",
        )
    require(
        sample["redistributable"] is True,
        f"{label}.redistributable must be true",
    )
    require(
        isinstance(sample["byte_count"], int)
        and not isinstance(sample["byte_count"], bool),
        f"{label}.byte_count must be an integer",
    )
    require(
        isinstance(sample["sha256"], str)
        and SHA256_PATTERN.fullmatch(sample["sha256"]) is not None,
        f"{label}.sha256 must be a lowercase SHA-256 digest",
    )
    expected_size_class = classify_size(sample["byte_count"])
    require(
        sample["size_class"] == expected_size_class,
        f"{label}.size_class does not match byte_count",
    )

    manifest_path = sample["path"]
    relative_path = PurePosixPath(manifest_path)
    require(not relative_path.is_absolute(), f"{label}.path must be relative")
    require(
        relative_path.parts
        and relative_path.parts[0] == "payloads"
        and ".." not in relative_path.parts
        and "." not in relative_path.parts
        and str(relative_path) == manifest_path,
        f"{label}.path must be a normalized path beneath payloads/",
    )

    unresolved_path = CORPUS_ROOT.joinpath(*relative_path.parts)
    try:
        payload_path = unresolved_path.resolve(strict=True)
    except OSError as error:
        raise VerificationError(f"{label}.path cannot be resolved: {error}") from error
    require(
        payload_path.is_relative_to(PAYLOADS_ROOT),
        f"{label}.path escapes payloads/",
    )
    require(payload_path.is_file(), f"{label}.path is not a regular file")

    try:
        payload = payload_path.read_bytes()
    except OSError as error:
        raise VerificationError(f"{label}.path cannot be read: {error}") from error
    require(
        len(payload) == sample["byte_count"],
        f"{label}.byte_count does not match payload",
    )
    require(
        sha256_bytes(payload) == sample["sha256"],
        f"{label}.sha256 does not match payload",
    )
    return payload_path


def verify():
    manifest, manifest_bytes = load_manifest()
    verify_checksum(manifest_bytes)

    samples = manifest["samples"]
    sample_ids = [sample.get("sample_id") for sample in samples if isinstance(sample, dict)]
    manifest_paths = [sample.get("path") for sample in samples if isinstance(sample, dict)]
    require(
        len(sample_ids) == len(set(sample_ids)),
        "sample_id values must be unique",
    )
    require(
        len(manifest_paths) == len(set(manifest_paths)),
        "path values must be unique",
    )

    resolved_paths = [verify_sample(sample, index) for index, sample in enumerate(samples)]
    require(
        len(resolved_paths) == len(set(resolved_paths)),
        "payload paths must resolve to unique files",
    )
    require(
        {sample["media_family"] for sample in samples} == EXPECTED_MEDIA_FAMILIES,
        "manifest must cover exactly the eight required media families",
    )
    require(
        {sample["size_class"] for sample in samples} == set(SIZE_CLASS_BOUNDS),
        "manifest must cover all three size classes",
    )
    return len(samples)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the frozen manifest and every tracked payload",
    )
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("--check is required")
    return args


def main(argv=None):
    parse_args(argv)
    try:
        sample_count = verify()
    except VerificationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"verified {sample_count} samples; manifest and payloads are frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
