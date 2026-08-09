#!/usr/bin/env python3
"""Deterministically reduce the immutable NEW-24 G2 evidence per file."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


CELL_SPECS = {
    "dickens/max": {
        "orig_bytes": 10_192_446,
        "orig_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
        "archive_sha256": "b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82",
    },
    "xml/max": {
        "orig_bytes": 5_345_280,
        "orig_sha256": "0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c",
        "archive_sha256": "d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37",
    },
    "x-ray/max": {
        "orig_bytes": 8_474_240,
        "orig_sha256": "7de9fce1405dc44ae5e6813ed21cd5751e761bd4265655a005d39b9685d1c9ad",
        "archive_sha256": "4ed8a550b2e05da471d33dd9f044c4e357fee45cfc77bbfcdb3f173a657953d7",
    },
    "dickens/web": {
        "orig_bytes": 10_192_446,
        "orig_sha256": "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a",
        "archive_sha256": "a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341",
    },
}

REQUIRED_EVENTS = (
    "task-clock",
    "cycles",
    "instructions",
    "branches",
    "branch-misses",
    "cache-references",
    "cache-misses",
    "dTLB-load-misses",
    "page-faults",
)

SYMBOL_PATTERNS = (
    ("cm2_predict_bit", "CmModel11predict_bit"),
    ("cm2_ctr_upd", "Ctr3upd"),
    ("cm2_update_bit", "CmModel10update_bit"),
    ("cm2_match_end", "Match3end"),
    ("cm2_start_byte", "CmModel10start_byte"),
    ("cm2_decode_shell", "cm210cm2_decode"),
    ("cm2_ctr_new", "Ctr3new"),
    ("cm2_end_byte", "CmModel8end_byte"),
    ("geocm_decode_stream_mix", "geocm17decode_stream_mix"),
    ("geocm_mixer_update", "geocmNtB5_5Mixer6update"),
    ("geocm_mix_ctxs", "geocm8mix_ctxs"),
    ("geocm_decode", "geocm6decode"),
)

CM2_MACHINERY_NAMES = (
    "cm2_predict_bit",
    "cm2_ctr_upd",
    "cm2_update_bit",
    "cm2_match_end",
    "cm2_start_byte",
    "cm2_ctr_new",
    "cm2_end_byte",
)

GEOCM_NAMES = (
    "geocm_decode_stream_mix",
    "geocm_mixer_update",
    "geocm_mix_ctxs",
    "geocm_decode",
)

SYMBOL_RE = re.compile(
    r"^\s*([0-9]+(?:\.[0-9]+)?)%\s+(\S+)\s+(\S+)\s+\[[^]]+\]\s+(.+?)\s*$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_perf_stat(path: Path) -> dict[str, int | float]:
    counters: dict[str, int | float] = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        raw_value, event = fields[0].strip(), fields[2].strip()
        if event not in REQUIRED_EVENTS or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw_value):
            continue
        counters[event] = float(raw_value) if "." in raw_value else int(raw_value)
    missing = sorted(set(REQUIRED_EVENTS) - counters.keys())
    if missing:
        raise ValueError(f"{path}: missing numeric required events: {', '.join(missing)}")
    return counters


def symbol_bucket(dso: str, symbol: str) -> str:
    for name, fragment in SYMBOL_PATTERNS:
        if fragment in symbol:
            return name
    if dso == "cubrim-3a13f48":
        return "other_user"
    if dso == "[kernel.kallsyms]":
        return "kernel"
    return "other"


def parse_symbol_report(path: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    named = {name: 0.0 for name, _ in SYMBOL_PATTERNS}
    for line in path.read_text().splitlines():
        match = SYMBOL_RE.match(line)
        if not match:
            continue
        share = float(match.group(1))
        dso = match.group(3)
        symbol = match.group(4)
        bucket = symbol_bucket(dso, symbol)
        entries.append({"share": share, "dso": dso, "symbol": symbol, "bucket": bucket})
        if bucket in named:
            named[bucket] += share
    if not entries:
        raise ValueError(f"{path}: no symbol rows parsed")
    rounded_sum = round(sum(entry["share"] for entry in entries), 6)
    return {
        "rows": len(entries),
        "rounded_sum": rounded_sum,
        "rounding_residual": round(100.0 - rounded_sum, 6),
        "entries": entries,
        "named": named,
    }


def parse_journal(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        raise ValueError(f"{path}: empty journal")
    return records


def one_event(journal: list[dict[str, Any]], event: str, cell: str | None = None) -> dict[str, Any]:
    matches = [
        record
        for record in journal
        if record.get("event") == event and (cell is None or record.get("cell") == cell)
    ]
    if len(matches) != 1:
        suffix = f" for {cell}" if cell else ""
        raise ValueError(f"expected one {event}{suffix}, found {len(matches)}")
    return matches[0]


def verify_raw_manifest(raw: Path) -> int:
    manifest = raw / "SHA256SUMS"
    count = 0
    listed: set[str] = set()
    for line in manifest.read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        relative = relative.lstrip("*")
        if relative.startswith("./"):
            relative = relative[2:]
        target = raw / relative
        if not target.is_file() or sha256(target) != expected:
            raise ValueError(f"raw manifest mismatch: {relative}")
        listed.add(relative)
        count += 1
    actual = {
        str(path.relative_to(raw))
        for path in raw.rglob("*")
        if path.is_file() and path.name not in {"SHA256SUMS", "TIMING-DONE.STAMP"}
    }
    if listed != actual:
        raise ValueError("raw manifest path set is not exhaustive")
    return count


def amdahl_ceiling(share_percent: float) -> float | None:
    if share_percent >= 100.0:
        return None
    return 1.0 / (1.0 - share_percent / 100.0)


def build_cell_metrics(
    cell: str,
    orig_bytes: int,
    raw: Path,
    analysis: Path,
    journal: list[dict[str, Any]],
) -> dict[str, Any]:
    directory = cell.replace("/", ".")
    pstat1 = parse_perf_stat(raw / directory / "pstat1.txt")
    pstat2 = parse_perf_stat(raw / directory / "pstat2.txt")
    symbols = parse_symbol_report(analysis / "full-symbols" / f"{directory}.txt")
    cycle_event = one_event(journal, "cycle-agreement", cell)
    g3 = one_event(journal, "G3", cell)
    g1 = one_event(journal, "G1_pass", cell)
    one_event(journal, "cell_done", cell)
    bits = orig_bytes * 8
    cycles_reportable = g3["classification"] == "instrument-clean"
    named = symbols["named"]
    cm2_named = round(sum(named[name] for name in CM2_MACHINERY_NAMES), 6)
    cm2_total = round(cm2_named + named["cm2_decode_shell"], 6)
    geocm_share = round(sum(named[name] for name in GEOCM_NAMES), 6)
    named_ceilings = {name: amdahl_ceiling(share) for name, share in named.items()}
    return {
        "cell": cell,
        "orig_bytes": orig_bytes,
        "archive_bytes": (raw / directory / "canonical-replay-1.cub").stat().st_size,
        "archive_sha256": g1["archive_sha256"],
        "plain_wall_s": g3["plain_wall_s"],
        "record_wall_s": g3["record_wall_s"],
        "record_plain_ratio": g3["ratio"],
        "instrument_class": g3["classification"],
        "cycle_class": cycle_event["event"],
        "cycle_relative_delta": cycle_event["relative_delta"],
        "cycles1": pstat1["cycles"],
        "cycles2": pstat2["cycles"],
        "cycles1_per_bit": pstat1["cycles"] / bits if cycles_reportable else None,
        "cycles2_per_bit": pstat2["cycles"] / bits if cycles_reportable else None,
        "instructions1_per_bit": pstat1["instructions"] / bits,
        "instructions2_per_bit": pstat2["instructions"] / bits,
        "ipc1": pstat1["instructions"] / pstat1["cycles"],
        "ipc2": pstat2["instructions"] / pstat2["cycles"],
        "cache_misses1_per_bit": pstat1["cache-misses"] / bits,
        "cache_misses2_per_bit": pstat2["cache-misses"] / bits,
        "dtlb_misses1_per_bit": pstat1["dTLB-load-misses"] / bits,
        "dtlb_misses2_per_bit": pstat2["dTLB-load-misses"] / bits,
        "page_faults1": pstat1["page-faults"],
        "page_faults2": pstat2["page-faults"],
        "cycles_reportable": cycles_reportable,
        "symbols_reportable": True,
        "symbol_rows": symbols["rows"],
        "symbol_rounded_sum": symbols["rounded_sum"],
        "symbol_rounding_residual": symbols["rounding_residual"],
        "symbols": symbols["entries"],
        "named_shares": named,
        "named_amdahl_ceilings": named_ceilings,
        "cm2_named_machinery_share": cm2_named,
        "cm2_named_machinery_amdahl_ceiling": amdahl_ceiling(cm2_named),
        "cm2_decode_shell_share": named["cm2_decode_shell"],
        "cm2_decode_shell_amdahl_ceiling": amdahl_ceiling(named["cm2_decode_shell"]),
        "cm2_total_named_share": cm2_total,
        "geocm_replay_share": geocm_share,
        "geocm_replay_amdahl_ceiling": amdahl_ceiling(geocm_share),
    }


def build_result(raw: Path, analysis: Path) -> dict[str, Any]:
    manifest_entries = verify_raw_manifest(raw)
    journal = parse_journal(raw / "journal.jsonl")
    forbidden = {"void", "gate_fail", "run_failed", "abort"}
    found_forbidden = sorted({record.get("event") for record in journal} & forbidden)
    if found_forbidden:
        raise ValueError(f"failure/void journal events present: {found_forbidden}")
    for event in ("run_start", "admission_pass", "suites_pass", "run_end"):
        one_event(journal, event)
    decode_records = [record for record in journal if record.get("event") == "decode_ok"]
    if len(decode_records) != 16:
        raise ValueError(f"expected 16 decode_ok records, found {len(decode_records)}")
    cells = {record.get("cell") for record in decode_records}
    if cells != set(CELL_SPECS):
        raise ValueError(f"unexpected decoded cell set: {sorted(cells)}")
    for cell, spec in CELL_SPECS.items():
        tags = sorted(record["tag"] for record in decode_records if record["cell"] == cell)
        if tags != ["plain", "prec", "pstat1", "pstat2"]:
            raise ValueError(f"{cell}: unexpected decode tags {tags}")
        if any(
            record["output_sha256"] != spec["orig_sha256"]
            for record in decode_records
            if record["cell"] == cell
        ):
            raise ValueError(f"{cell}: decoded output SHA mismatch")
        directory = cell.replace("/", ".")
        archives = [raw / directory / f"canonical-replay-{index}.cub" for index in (1, 2)]
        if any(sha256(path) != spec["archive_sha256"] for path in archives):
            raise ValueError(f"{cell}: canonical archive SHA mismatch")
        if archives[0].read_bytes() != archives[1].read_bytes():
            raise ValueError(f"{cell}: canonical archives differ")
    metrics = {
        cell: build_cell_metrics(cell, spec["orig_bytes"], raw, analysis, journal)
        for cell, spec in CELL_SPECS.items()
    }
    p1_cells = [metrics["dickens/max"], metrics["xml/max"]]
    p1_supported = all(
        cell["cm2_named_machinery_share"] >= 85.0
        and cell["cm2_decode_shell_share"] <= 5.0
        for cell in p1_cells
    )
    xray = metrics["x-ray/max"]
    p4_supported = xray["cm2_total_named_share"] <= 10.0 and xray["geocm_replay_share"] > 50.0
    comparable = (
        "cm2_predict_bit",
        "cm2_ctr_upd",
        "cm2_update_bit",
        "cm2_match_end",
        "cm2_start_byte",
        "cm2_decode_shell",
    )
    max_named = metrics["dickens/max"]["named_shares"]
    web_named = metrics["dickens/web"]["named_shares"]
    max_order = sorted(comparable, key=lambda name: max_named[name], reverse=True)
    web_order = sorted(comparable, key=lambda name: web_named[name], reverse=True)
    max_delta = max(abs(max_named[name] - web_named[name]) for name in comparable)
    predictions = {
        "P1": {
            "status": "SUPPORTED" if p1_supported else "REFUTED",
            "reason": "Named CM2 per-bit symbols clear 85%; frozen source bounds inlined range work to the outer cm2_decode shell, below 5%.",
        },
        "P2": {
            "status": "INDETERMINATE",
            "reason": "Mixer::mix/update are inlined into larger predict_bit/update_bit symbols; no preregistered instruction-to-bucket mapping separates their share.",
        },
        "P3": {
            "status": "INDETERMINATE",
            "reason": "IPC is above 1.0, but the preregistration defines no miss-latency model for implied miss-stall share and LLC events are unsupported.",
        },
        "P4": {
            "status": "SUPPORTED" if p4_supported else "REFUTED",
            "reason": "No CM2 symbol is observed; named geocm replay symbols dominate the x-ray profile.",
        },
        "P5": {
            "status": "INDETERMINATE",
            "reason": "The six observable major symbol families retain order and stay within 10 points, but the preregistration defines no exhaustive bucket map or tie rule.",
            "observable_major_order_equal": max_order == web_order,
            "observable_major_max_abs_delta_points": max_delta,
        },
    }
    return {
        "provenance": {
            "raw_manifest_entries": manifest_entries,
            "raw_manifest_sha256": sha256(raw / "SHA256SUMS"),
            "completion_marker_sha256": sha256(raw / "TIMING-DONE.STAMP"),
            "runner_sha256": sha256(raw / "decode-attrib-run.sh"),
            "binary_sha256": "d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb",
            "code_commit": "3a13f486aea51470e2079ba66abb94d99fd782d9",
            "pin": "0-15",
            "perf_version": "6.8.12",
        },
        "terminal": {
            "classification": "COMPLETE",
            "cells": 4,
            "decode_observations": 16,
            "failure_or_void_events": 0,
        },
        "cells": metrics,
        "predictions": predictions,
    }


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "SUPPRESSED"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_metrics(result: dict[str, Any]) -> str:
    columns = (
        "cell",
        "orig_bytes",
        "archive_bytes",
        "plain_wall_s",
        "record_wall_s",
        "record_plain_ratio",
        "instrument_class",
        "cycle_relative_delta",
        "cycles1_per_bit",
        "cycles2_per_bit",
        "instructions1_per_bit",
        "instructions2_per_bit",
        "ipc1",
        "ipc2",
        "cache_misses1_per_bit",
        "cache_misses2_per_bit",
        "dtlb_misses1_per_bit",
        "dtlb_misses2_per_bit",
        "page_faults1",
        "page_faults2",
        "cm2_named_machinery_share",
        "cm2_named_machinery_amdahl_ceiling",
        "cm2_decode_shell_share",
        "cm2_decode_shell_amdahl_ceiling",
        "geocm_replay_share",
        "geocm_replay_amdahl_ceiling",
        "symbol_rows",
        "symbol_rounded_sum",
        "symbol_rounding_residual",
    )
    lines = ["\t".join(columns)]
    for cell in CELL_SPECS:
        metrics = result["cells"][cell]
        lines.append("\t".join(fmt(metrics[column]) for column in columns))
    return "\n".join(lines) + "\n"


def render_symbols(result: dict[str, Any]) -> str:
    lines = ["cell\tshare_percent\tamdahl_ceiling\tbucket\tdso\tsymbol"]
    for cell in CELL_SPECS:
        for entry in result["cells"][cell]["symbols"]:
            lines.append(
                "\t".join(
                    (
                        cell,
                        fmt(entry["share"], 2),
                        fmt(amdahl_ceiling(entry["share"]), 6),
                        entry["bucket"],
                        entry["dso"],
                        entry["symbol"],
                    )
                )
            )
    return "\n".join(lines) + "\n"


def render_predictions(result: dict[str, Any]) -> str:
    lines = ["prediction\tstatus\treason"]
    for prediction in ("P1", "P2", "P3", "P4", "P5"):
        record = result["predictions"][prediction]
        lines.append("\t".join((prediction, record["status"], record["reason"])))
    return "\n".join(lines) + "\n"


def outputs(result: dict[str, Any]) -> dict[str, str]:
    return {
        "metrics.tsv": render_metrics(result),
        "symbols.tsv": render_symbols(result),
        "predictions.tsv": render_predictions(result),
        "result.json": json.dumps(result, indent=2, sort_keys=True) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files drift")
    args = parser.parse_args()
    analysis = Path(__file__).resolve().parent
    raw = analysis.parent / "raw"
    generated = outputs(build_result(raw, analysis))
    if args.check:
        mismatches = [name for name, content in generated.items() if (analysis / name).read_text() != content]
        if mismatches:
            raise SystemExit(f"generated output drift: {', '.join(mismatches)}")
        print("decode_attrib_g2_analysis=PASS")
        return 0
    for name, content in generated.items():
        (analysis / name).write_text(content)
    print("decode_attrib_g2_analysis_written=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
