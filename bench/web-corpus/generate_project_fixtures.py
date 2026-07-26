#!/usr/bin/env python3
"""Generate the seven deterministic, project-authored Web Corpus fixtures."""

import argparse
import json
from pathlib import Path


CORPUS_ROOT = Path(__file__).resolve().parent
PAYLOADS_ROOT = CORPUS_ROOT / "payloads"


def pad_text(prefix, suffix, target_size, comment_open, comment_close):
    fixed_size = len(prefix) + len(suffix) + len(comment_open) + len(comment_close)
    if fixed_size > target_size:
        raise ValueError("fixture skeleton exceeds target size")
    return (
        prefix
        + comment_open
        + ("x" * (target_size - fixed_size))
        + comment_close
        + suffix
    ).encode("ascii")


def compact_json_at_size(document, target_size):
    document = dict(document)
    document["x_padding"] = ""
    baseline = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    padding_size = target_size - len(baseline)
    if padding_size < 0:
        raise ValueError("JSON fixture skeleton exceeds target size")
    document["x_padding"] = "x" * padding_size
    payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) != target_size:
        raise AssertionError("JSON padding calculation was not byte-exact")
    return payload


def html_payload():
    return pad_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Cubrim Web Corpus</title></head><body><main><h1>Fixture</h1>"
        "<p>Deterministic project-authored HTML benchmark payload.</p></main>",
        "</body></html>",
        4_096,
        "<!--",
        "-->",
    )


def css_payload():
    return pad_text(
        ":root{color-scheme:light dark;--space:1rem}"
        "*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui}"
        "main{display:grid;gap:var(--space);max-width:72rem;margin:auto}",
        "\n",
        16_384,
        "/*",
        "*/",
    )


def javascript_payload():
    return pad_text(
        "\"use strict\";\n"
        "const samples=[1,2,3,5,8,13];\n"
        "const total=samples.reduce((sum,value)=>sum+value,0);\n"
        "globalThis.cubrimFixture={samples,total};\n",
        "\n",
        8_192,
        "/*",
        "*/",
    )


def source_map_payload():
    return compact_json_at_size(
        {
            "file": "app.js",
            "mappings": "AAAA,MAAMA,QAAQ,CAAC,CAAC,CAAC,CAAC,CAAC,CAAC",
            "names": ["samples", "total"],
            "sources": ["app.source.js"],
            "sourcesContent": [
                "const samples=[1,2,3,5,8,13];\n"
                "const total=samples.reduce((sum,value)=>sum+value,0);\n"
            ],
            "version": 3,
        },
        6_144,
    )


def json_api_payload():
    records = [
        {
            "attributes": {
                "active": index % 3 != 0,
                "label": f"benchmark-record-{index:04d}",
                "rank": index,
            },
            "id": f"record-{index:04d}",
            "type": "web-corpus-sample",
        }
        for index in range(512)
    ]
    return compact_json_at_size(
        {
            "data": records,
            "jsonapi": {"version": "1.1"},
            "meta": {"fixture": "cubrim-web-corpus-v1", "record_count": len(records)},
        },
        300_000,
    )


def svg_payload():
    return pad_text(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 640 360\">"
        "<title>Cubrim benchmark fixture</title><defs><linearGradient id=\"g\">"
        "<stop stop-color=\"#2855ff\"/><stop offset=\"1\" stop-color=\"#8cf\"/>"
        "</linearGradient></defs><rect width=\"640\" height=\"360\" fill=\"url(#g)\"/>",
        "</svg>",
        12_288,
        "<!--",
        "-->",
    )


def unsigned_leb128(value):
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        encoded.append(byte)
        if not value:
            return bytes(encoded)


def wasm_payload():
    target_size = 2_048
    module_header = b"\x00asm\x01\x00\x00\x00"
    section_name = b"cubrim-fixture-padding"
    named_prefix = unsigned_leb128(len(section_name)) + section_name
    for padding_size in range(target_size):
        section_payload = named_prefix + (b"\x00" * padding_size)
        module = (
            module_header
            + b"\x00"
            + unsigned_leb128(len(section_payload))
            + section_payload
        )
        if len(module) == target_size:
            return module
    raise AssertionError("could not construct byte-exact WASM fixture")


def build_payloads():
    return {
        "api-response.large.json": json_api_payload(),
        "app.small.js": javascript_payload(),
        "app.small.js.map": source_map_payload(),
        "document.small.html": html_payload(),
        "module.small.wasm": wasm_payload(),
        "styles.medium.css": css_payload(),
        "vector.medium.svg": svg_payload(),
    }


def write_payloads(payloads):
    PAYLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (PAYLOADS_ROOT / name).write_bytes(payload)


def check_payloads(payloads):
    mismatches = []
    for name, expected in payloads.items():
        path = PAYLOADS_ROOT / name
        if not path.is_file() or path.read_bytes() != expected:
            mismatches.append(name)
    if mismatches:
        raise SystemExit(
            "project-authored fixtures are not reproducible: " + ", ".join(mismatches)
        )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    payloads = build_payloads()
    if args.write:
        write_payloads(payloads)
        print(f"wrote {len(payloads)} project-authored fixtures")
    else:
        check_payloads(payloads)
        print(f"verified {len(payloads)} reproducible project-authored fixtures")


if __name__ == "__main__":
    main()
