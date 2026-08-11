#!/usr/bin/env python3
"""Run the CUBR-0076 charged size model over the 12 census samples.

Emits results.tsv (per sample per configuration), summary.tsv (aggregates and
the verdict against the frozen decision rule) and prints a short report.
Bytes only -- no timing claim is made or recorded anywhere.

Usage: python3 driver.py [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import size_model as sm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(RESEARCH)))
CORPUS = os.path.join(REPO, "bench", "web-corpus")
BASELINES = os.path.join(RESEARCH, "CUBR-0076-DENSITY-20260806", "baselines.tsv")
STATIC_DETAIL = os.path.join(RESEARCH, "CUBR-0076-DENSITY-20260806",
                             "static-detail.tsv")
CENSUS = os.path.join(RESEARCH, "CUBR-0076-WEBMODE-CENSUS-20260806",
                      "census.tsv")

# Frozen decision rule (CUBR-0076-SIZEMODEL-PREREG-20260811.md).
BAR_WIN = 108495     # brotli-11 aggregate
BAR_GO = 129193      # gzip-9 aggregate
BAR_STATIC = 158227  # today's best-static family aggregate

# Parse-quality axis. "opt<N>" is the shortest-path parse at chain N; it is the
# tier that decides whether a shortfall belongs to the scheme or to the parser.
CHAINS = [16, 128, 1024, "opt256"]
# (variant, block_size, context_split)
VARIANTS = [
    ("V1-whole-file", None, 1),
    ("V2-64KiB-blocks", 65536, 1),
    ("V3-whole-file-ctx2", None, 2),
    ("V3-whole-file-ctx3", None, 3),
    ("V4-64KiB-blocks-ctx2", 65536, 2),
]


def read_tsv(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_reference():
    baselines = {r["sample_id"]: r for r in read_tsv(BASELINES)}
    census = {r["sample_id"]: r for r in read_tsv(CENSUS)}
    # NOTE: static-detail.tsv's header is offset by one against its data rows;
    # the bytes of the best static scheme live in the field labelled
    # "static_stream", and the forced-scheme bytes in "static_forced".
    static_best: dict[str, int] = {}
    static_forced: dict[str, int] = {}
    for row in read_tsv(STATIC_DETAIL):
        sid = row["sample_id"]
        static_best[sid] = static_best.get(sid, 0) + int(row["static_stream"])
        static_forced[sid] = static_forced.get(sid, 0) + int(row["static_forced"])
    return baselines, census, static_best, static_forced


def load_samples():
    with open(os.path.join(CORPUS, "manifest.v2.json")) as handle:
        manifest = json.load(handle)
    samples = []
    for entry in manifest["samples"]:
        path = os.path.join(CORPUS, entry["path"])
        data = open(path, "rb").read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            raise SystemExit(
                f"PAYLOAD PROVENANCE FAILURE: {entry['sample_id']} sha256 "
                f"{digest} != manifest {entry['sha256']}")
        if len(data) != entry["byte_count"]:
            raise SystemExit(f"byte_count mismatch for {entry['sample_id']}")
        samples.append((entry["sample_id"], entry["media_family"], data,
                        digest))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=HERE)
    args = parser.parse_args()

    baselines, census, static_best, static_forced = load_reference()
    samples = load_samples()

    rows = []
    for sid, family, data, digest in samples:
        cache: dict[tuple, list] = {}
        for chain in CHAINS:
            for variant, block_size, split in VARIANTS:
                key = (block_size, chain)
                if key not in cache:
                    optimal = isinstance(chain, str)
                    depth = int(str(chain).removeprefix("opt")) if optimal \
                        else chain
                    cache[key] = sm.parse_blocks(data, block_size, depth,
                                                 optimal=optimal)
                result = sm.model_file(data, block_size, 0, split, cache[key])
                charge = result["charge_bits"]
                assert sum(charge.values()) == result["total_bits"], sid
                rows.append({
                    "sample_id": sid,
                    "media_family": family,
                    "variant": variant,
                    "parse_chain": chain,
                    "orig_bytes": len(data),
                    "modelled_bytes": result["modelled_bytes"],
                    "store_bytes": result["store_bytes"],
                    "chosen_bytes": result["chosen_bytes"],
                    "selected": result["selected"],
                    "blocks": result["blocks"],
                    **{f"bits_{k}": v for k, v in charge.items()},
                    "gzip9": int(baselines[sid]["gzip9"]),
                    "brotli11": int(baselines[sid]["brotli11"]),
                    "static_best_today": static_best[sid],
                    "cm2_champion": int(census[sid]["comp_bytes"]),
                })
        print(f"  modelled {sid}", file=sys.stderr)

    out_dir = args.out_dir
    with open(os.path.join(out_dir, "results.tsv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]),
                                delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    # ---- aggregates -----------------------------------------------------
    configs = {}
    for row in rows:
        key = (row["variant"], row["parse_chain"])
        configs.setdefault(key, []).append(row)

    summary = []
    for (variant, chain), group in sorted(configs.items(),
                                          key=lambda kv: (kv[0][0],
                                                          str(kv[0][1]))):
        total = sum(r["chosen_bytes"] for r in group)
        summary.append({
            "variant": variant,
            "parse_chain": chain,
            "samples": len(group),
            "total_bytes": total,
            "vs_gzip9": round(total / BAR_GO, 6),
            "vs_brotli11": round(total / BAR_WIN, 6),
            "vs_static_today": round(total / BAR_STATIC, 6),
            "beats_gzip9": total <= BAR_GO,
            "beats_brotli11": total <= BAR_WIN,
            "beats_static_today": total < BAR_STATIC,
        })

    # Per-sample best-of-all-configurations (the scheme byte picks per file).
    best_per_sample = {}
    for row in rows:
        sid = row["sample_id"]
        cur = best_per_sample.get(sid)
        if cur is None or row["chosen_bytes"] < cur["chosen_bytes"]:
            best_per_sample[sid] = row
    per_file_best_total = sum(r["chosen_bytes"] for r in best_per_sample.values())
    summary.append({
        "variant": "BEST-PER-FILE(scheme byte selects)",
        "parse_chain": "mixed",
        "samples": len(best_per_sample),
        "total_bytes": per_file_best_total,
        "vs_gzip9": round(per_file_best_total / BAR_GO, 6),
        "vs_brotli11": round(per_file_best_total / BAR_WIN, 6),
        "vs_static_today": round(per_file_best_total / BAR_STATIC, 6),
        "beats_gzip9": per_file_best_total <= BAR_GO,
        "beats_brotli11": per_file_best_total <= BAR_WIN,
        "beats_static_today": per_file_best_total < BAR_STATIC,
    })

    with open(os.path.join(out_dir, "summary.tsv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]),
                                delimiter="\t")
        writer.writeheader()
        writer.writerows(summary)

    best = min(summary, key=lambda s: s["total_bytes"])
    total = best["total_bytes"]
    if total <= BAR_WIN:
        verdict = "WIN-density"
    elif total <= BAR_GO:
        verdict = "GO-density"
    elif total < BAR_STATIC:
        verdict = "PARTIAL"
    else:
        verdict = "NO-GO at this parse quality"

    print()
    print(f"best configuration : {best['variant']} chain={best['parse_chain']}")
    print(f"aggregate bytes    : {total}")
    print(f"  vs brotli-11 WIN : {total / BAR_WIN:.4f}  (bar {BAR_WIN})")
    print(f"  vs gzip-9 GO     : {total / BAR_GO:.4f}  (bar {BAR_GO})")
    print(f"  vs static today  : {total / BAR_STATIC:.4f}  (bar {BAR_STATIC})")
    print(f"VERDICT            : {verdict}")

    # Parse-quality span, needed to interpret a near-miss honestly.
    v1 = {c: sum(r["chosen_bytes"] for r in rows
                 if r["variant"] == "V1-whole-file" and r["parse_chain"] == c)
          for c in CHAINS}
    span = (v1[CHAINS[0]] - v1[CHAINS[-1]]) / v1[CHAINS[0]]
    print(f"parse-quality span (V1 chain {CHAINS[0]} -> {CHAINS[-1]}): "
          f"{span * 100:.2f}%")
    for chain in CHAINS:
        print(f"  V1 chain={chain}: {v1[chain]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
