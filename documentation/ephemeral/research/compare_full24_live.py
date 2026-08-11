#!/usr/bin/env python3
"""Compare an independent full-24 TSV with the live world-benchmark API."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from collections import defaultdict
from pathlib import Path


CODECS = ("7z", "ppmd", "xz", "brotli", "zstd", "bzip2", "gzip", "rar", "lz4")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="https://api.cubrim.com/api/world-benchmark")
    args = parser.parse_args()

    with args.results.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    request = urllib.request.Request(
        args.url,
        headers={"User-Agent": "cubr-independent-verifier/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        live = json.load(response)

    by_type: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    failures = []
    seen = set()
    for row in rows:
        identity = (row["corpus"], row["file"], row["codec"])
        if identity in seen:
            failures.append({"duplicate": identity})
            continue
        seen.add(identity)
        if (int(row["encode_rc"]), int(row["decode_rc"]), int(row["cmp"])) != (0, 0, 0):
            failures.append({"failed_row": identity})
            continue
        bucket = by_type[row["type"]][row["codec"]]
        bucket[0] += int(row["compressed"])
        bucket[1] += int(row["orig"])

    aggregate = {}
    for kind, codecs in sorted(by_type.items()):
        aggregate[kind] = {}
        for codec in CODECS:
            compressed, original = codecs[codec]
            measured = compressed / original
            published = float(live["aggregate_by_type"][kind][codec])
            aggregate[kind][codec] = {
                "compressed": compressed,
                "orig": original,
                "measured": measured,
                "live": published,
                "delta": measured - published,
                "relative_delta": measured / published - 1.0,
            }

    live_files = {(row["corpus"], row["file"]): row for row in live["files"]}
    per_file_delta = defaultdict(list)
    for row in rows:
        published = float(live_files[(row["corpus"], row["file"])]["ratio"][row["codec"]])
        per_file_delta[row["codec"]].append(float(row["ratio"]) - published)

    summary = {
        "api_task": live["task"],
        "api_generated": live["generated"],
        "expected_rows": 24 * len(CODECS),
        "rows": len(rows),
        "unique_rows": len(seen),
        "failures": failures,
        "all_rt_cmp0": not failures and len(rows) == 24 * len(CODECS),
        "aggregate_by_type": aggregate,
        "per_file_delta_range": {
            codec: {"min": min(values), "max": max(values)}
            for codec, values in sorted(per_file_delta.items())
        },
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: summary[key] for key in ("api_task", "rows", "unique_rows", "all_rt_cmp0")}, sort_keys=True))
    return 0 if summary["all_rt_cmp0"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
