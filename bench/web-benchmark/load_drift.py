#!/usr/bin/env python3
"""Report how much a bundle's timings drifted across its own measurement window.

Admission is recorded once, before the first trial. If the host stopped being
quiet afterwards, the bundle still says `accepted: true` beside the pre-ramp
load figure, and every downstream check — verify_bundle, the API's bundle
parser, the guarded writer — will accept it. This is the read that tells you
whether a run that passed everything is nevertheless a table of numbers about a
busy machine.

The signal: within one sample/codec cell the compressed size is a property of
the codec and the bytes, so it is constant across all 30 trials; the durations
are properties of the host at the moment they were taken. Order each cell's
trials by measurement time and compare the median of the first third to the
median of the last third. On a quiet host the ratio sits at 1.0 in both
directions. A ratio that climbs is the host, not the codec.

    python3 load_drift.py out/phase-a.json
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from datetime import datetime
from pathlib import Path

DURATION_METRICS = ("compression_duration", "decompression_duration")


def _epoch(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def drift_report(bundle: dict) -> dict:
    trials = bundle["resource_results"]
    cells: dict[tuple[str, str], list] = collections.defaultdict(list)
    sizes: dict[tuple[str, str], set] = collections.defaultdict(set)
    for trial in trials:
        key = (trial["sample_id"], trial["codec_key"])
        cells[key].append((_epoch(trial["measured_at"]), trial["metrics"]))
        sizes[key].add(trial["compressed_bytes"])

    report: dict[str, object] = {
        "trials": len(trials),
        "cells": len(cells),
        "window_seconds": round(
            max(_epoch(t["measured_at"]) for t in trials)
            - min(_epoch(t["measured_at"]) for t in trials),
            1,
        ),
        "admission": bundle["environment"]["admission"],
        # Nonzero means the premise is wrong somewhere and the rest of this
        # report should not be read as a load story.
        "cells_with_varying_compressed_bytes": sum(
            1 for values in sizes.values() if len(values) != 1
        ),
    }

    for metric in DURATION_METRICS:
        ratios = []
        for ordered in cells.values():
            ordered.sort(key=lambda pair: pair[0])
            third = len(ordered) // 3
            if third == 0:
                continue
            first = statistics.median(m[metric] for _, m in ordered[:third])
            last = statistics.median(m[metric] for _, m in ordered[-third:])
            if first > 0:
                ratios.append(last / first)
        ratios.sort()
        report[metric] = {
            "median_last_over_first": round(statistics.median(ratios), 4),
            "p10": round(ratios[len(ratios) // 10], 4),
            "p90": round(ratios[9 * len(ratios) // 10], 4),
            "cells_over_1_25x": sum(1 for r in ratios if r > 1.25),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    print(json.dumps(drift_report(bundle), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
