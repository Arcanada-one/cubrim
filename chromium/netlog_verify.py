#!/usr/bin/env python3
"""Verify the browser-level cbm negotiation evidence in a Chromium netlog."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Evidence:
    request_logged: bool
    accepts_cbm: bool
    response_cbm: bool
    varies_on_accept_encoding: bool
    request_failed: bool

    @property
    def verdict(self) -> bool:
        return (
            self.request_logged
            and self.accepts_cbm
            and self.response_cbm
            and self.varies_on_accept_encoding
            and not self.request_failed
        )


def _event_types(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("constants", {}).get("logEventTypes", {})
    return {name: value for name, value in raw.items() if isinstance(value, int)}


def _headers(event: dict[str, Any]) -> list[str]:
    raw = event.get("params", {}).get("headers", [])
    if isinstance(raw, list):
        return [str(line) for line in raw]
    if isinstance(raw, str):
        return raw.splitlines()
    return []


def _header_value(headers: list[str], name: str) -> str | None:
    prefix = f"{name.lower()}:"
    for line in headers:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def _has_token(value: str | None, token: str) -> bool:
    if value is None:
        return False
    return token.lower() in {part.strip().lower() for part in value.split(",")}


def _document_sources(
    events: list[dict[str, Any]], event_types: dict[str, int], doc: str
) -> set[int]:
    start_type = event_types.get("URL_REQUEST_START_JOB")
    if start_type is None:
        return set()

    sources: set[int] = set()
    for event in events:
        if event.get("type") != start_type or event.get("phase") != 1:
            continue
        url = event.get("params", {}).get("url")
        source_id = event.get("source", {}).get("id")
        if not isinstance(url, str) or not isinstance(source_id, int):
            continue
        if urlsplit(url).path.rstrip("/") == f"/{doc}":
            sources.add(source_id)
    return sources


def verify_payload(payload: dict[str, Any], doc: str) -> Evidence:
    """Return evidence for the document request, failing closed on missing data."""

    events = payload.get("events", [])
    if not isinstance(events, list):
        events = []
    events = [event for event in events if isinstance(event, dict)]
    event_types = _event_types(payload)
    sources = _document_sources(events, event_types, doc)

    def of_type(name: str) -> list[dict[str, Any]]:
        event_type = event_types.get(name)
        if event_type is None:
            return []
        return [
            event
            for event in events
            if event.get("type") == event_type
            and event.get("source", {}).get("id") in sources
        ]

    request_headers = [
        header
        for event in of_type("HTTP_TRANSACTION_SEND_REQUEST_HEADERS")
        for header in [_header_value(_headers(event), "Accept-Encoding")]
        if header is not None
    ]
    response_headers = [
        _headers(event)
        for event in of_type("HTTP_TRANSACTION_READ_RESPONSE_HEADERS")
    ]
    failed_type = event_types.get("FAILED")
    request_failed = failed_type is not None and any(
        event.get("type") == failed_type
        and event.get("source", {}).get("id") in sources
        for event in events
    )

    return Evidence(
        request_logged=bool(sources),
        accepts_cbm=any(_has_token(value, "cbm") for value in request_headers),
        response_cbm=any(
            _has_token(_header_value(headers, "Content-Encoding"), "cbm")
            for headers in response_headers
        ),
        varies_on_accept_encoding=any(
            _has_token(_header_value(headers, "Vary"), "Accept-Encoding")
            for headers in response_headers
        ),
        request_failed=request_failed,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} NETLOG DOC", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[1]).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read valid netlog: {exc}", file=sys.stderr)
        return 2

    evidence = verify_payload(payload, argv[2])
    print(f"  request to /{argv[2]} logged        : {evidence.request_logged}")
    print(f"  Accept-Encoding includes cbm      : {evidence.accepts_cbm}")
    print(f"  Content-Encoding: cbm in netlog   : {evidence.response_cbm}")
    print(f"  Vary: Accept-Encoding in netlog   : {evidence.varies_on_accept_encoding}")
    print(f"  request FAILED event               : {evidence.request_failed}")
    print(f"  VERDICT: browser negotiated + decoded cbm without error: {evidence.verdict}")
    return 0 if evidence.verdict else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
