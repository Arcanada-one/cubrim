#!/usr/bin/env python3
"""Fail-closed verifier for the NEW-24 full-binary G6 terminal result package.

Every predicate below must hold. Any missing file, unreadable field, unexpected
value, or hash disagreement is a hard failure: the verifier exits non-zero and
names the predicate. Absence is never converted to N/A or PASS.

Usage: verify_result.py [package-directory]
Exit 0 = the package is internally consistent and states a terminal route.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

FROZEN_SOURCE_COMMIT = "830a9a31deb00926a97f3fa5bd74f58003573fc0"
EXPECTED_LOCK_SHA = (
    "0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9"
)
INSTRUMENT_MAIN = "756ff160814cb1a8b452df68ad844514e8cf54a6"
TERMINAL_VERDICTS = (
    "NO-ATTEMPT / NO-SELECT",
    "VOID / NO-SELECT",
    "VALID-DESCRIPTIVE / NO-SELECT",
    "VALID-ATTRIBUTION / NO-SELECT",
)
INSTRUMENT_BLOBS = {
    "instrument_blob_run_sh": "8c5ed11b28b948d9ef03a1f6d427738199393fc0",
    "instrument_blob_run_test_sh": "4559c1c861152961fe2e25e7d7a7fc1a9741abb4",
    "instrument_blob_prebuild_sh": "1a9541ba8e7bf04fd1f296b173ee5748ad5e4a26",
    "instrument_blob_prebuild_test_sh": "72f1aa864c12af0cd29c205c97ef0ee6910d0108",
    "instrument_blob_validate_sh": "9d254278952dd6682f611d7edc25223c224af8aa",
    "instrument_blob_validate_test_sh": "fdee6fb4254034524b21c3dc3e2ec584222fdf3c",
    "instrument_blob_map_py": "310240da582f6ade3e69c99f6b93e8031adfebab",
    "instrument_blob_map_test_py": "1bdb0a69f6fd55a3967cf1ec377e0e859253569f",
}
REQUIRED_FILES = (
    "result.json",
    "identities.tsv",
    "remote-tree-manifest.tsv",
    "unit-properties.txt",
    "systemd-journal.canonical.jsonl",
    "remote-evidence/prebuild-console.log",
    "remote-evidence/Cargo.lock.src-a",
    "remote-evidence/Cargo.lock.src-b",
)
# Owned remote paths that a prebuild-only route must prove were never created.
MUST_BE_ABSENT = (
    "cubr-new24-full-binary-g6-target-a",
    "cubr-new24-full-binary-g6-target-b",
    "cubr-new24-full-binary-g6-prebuild-receipt-20260811",
    "cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial",
    "cubr-new24-full-binary-g6-map-dryrun-20260811",
    "cubr-new24-full-binary-g6-20260811",
    "cubr-new24-full-binary-g6-admission-inputs-20260811.env",
)
ZERO_COUNT_KEYS = (
    "targets_built",
    "receipt_published",
    "admission_submitted",
    "campaign_submitted",
    "campaign_cells",
    "perf_data",
    "stat_artifacts",
    "record_artifacts",
    "attribution_artifacts",
    "timing_artifacts",
    "interpreted_family_artifacts",
)


class Failure(Exception):
    pass


def require(condition: object, predicate: str) -> None:
    if not condition:
        raise Failure(predicate)


def sha256_of(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_identities(path: str) -> dict:
    rows = {}
    with open(path, encoding="ascii") as handle:
        header = handle.readline().rstrip("\n")
        require(header == "field\tvalue", "identities.tsv header is exact")
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            require(len(parts) == 2, f"identities.tsv row is a 2-field record: {line!r}")
            require(parts[0] not in rows, f"identities.tsv key is unique: {parts[0]}")
            rows[parts[0]] = parts[1]
    return rows


def verify(root: str) -> None:
    # --- presence: fail closed on any missing evidence file -----------------
    for relative in REQUIRED_FILES:
        target = os.path.join(root, relative)
        require(os.path.isfile(target), f"required evidence file exists: {relative}")
        require(
            not os.path.islink(target),
            f"required evidence file is not a symlink: {relative}",
        )

    result = json.load(open(os.path.join(root, "result.json"), encoding="ascii"))
    identities = load_identities(os.path.join(root, "identities.tsv"))

    # --- terminal-route predicate -------------------------------------------
    verdict = result["verdict"]
    require(verdict in TERMINAL_VERDICTS, f"verdict is a terminal route: {verdict!r}")
    require(
        identities["verdict"] == verdict,
        "identities.tsv verdict agrees with result.json",
    )
    require(
        result["route"] == identities["route"],
        "identities.tsv route agrees with result.json",
    )

    # --- no-selection predicate ---------------------------------------------
    require(
        result["selection"]["source_change_selected"] is False,
        "no source change is selected",
    )
    require(verdict.endswith("NO-SELECT"), "verdict carries NO-SELECT")

    # --- identity predicates -------------------------------------------------
    require(
        identities["instrument_main"] == INSTRUMENT_MAIN,
        "instrument main matches the reviewed resulting main",
    )
    require(
        result["instrument"]["resulting_main"] == INSTRUMENT_MAIN,
        "result.json instrument main matches the reviewed resulting main",
    )
    for key, blob in INSTRUMENT_BLOBS.items():
        require(identities[key] == blob, f"instrument blob is authentic: {key}")
    require(
        identities["frozen_source_commit"] == FROZEN_SOURCE_COMMIT,
        "frozen source commit is the preregistered one",
    )
    for side in ("src_a_head", "src_b_head"):
        require(
            identities[side] == FROZEN_SOURCE_COMMIT,
            f"{side} is detached at the frozen source commit",
        )
    require(
        identities["rustc_commit"] == "31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd",
        "rustc commit is the preregistered toolchain",
    )

    # --- failure-mechanism predicates ---------------------------------------
    failure = result["failure"]
    require(
        failure["expected_lock_sha256"] == EXPECTED_LOCK_SHA,
        "declared expected lock SHA is the preregistered frozen value",
    )
    require(
        identities["expected_lock_sha256"] == EXPECTED_LOCK_SHA,
        "identities.tsv expected lock SHA is the preregistered frozen value",
    )
    observed = failure["observed_lock_sha256"]
    require(
        identities["observed_lock_sha256"] == observed,
        "identities.tsv observed lock SHA agrees with result.json",
    )
    require(
        observed != EXPECTED_LOCK_SHA,
        "a NO-ATTEMPT lock-identity failure means observed != expected",
    )

    # The observed lock hash must be recomputable from the retained evidence,
    # and both independent clones must have produced the same bytes.
    lock_a = os.path.join(root, "remote-evidence", "Cargo.lock.src-a")
    lock_b = os.path.join(root, "remote-evidence", "Cargo.lock.src-b")
    digest_a, digest_b = sha256_of(lock_a), sha256_of(lock_b)
    require(digest_a == observed, "retained src-a lock reproduces the observed SHA")
    require(digest_b == observed, "retained src-b lock reproduces the observed SHA")
    require(
        failure["independent_clones_agree"] is True and digest_a == digest_b,
        "the two independent source clones produced byte-identical locks",
    )
    require(
        os.path.getsize(lock_a) == failure["observed_lock_bytes"],
        "retained lock byte count matches the declared value",
    )
    require(
        int(identities["observed_lock_bytes"]) == failure["observed_lock_bytes"],
        "identities.tsv lock byte count agrees with result.json",
    )

    # The drifted crates must actually appear, at the stated versions, in the
    # retained lock -- otherwise the stated mechanism is unsupported.
    lock_text = open(lock_a, encoding="ascii").read()
    require(failure["drifted_crates"], "at least one drifted crate is named")
    for entry in failure["drifted_crates"]:
        needle = 'name = "%s"\nversion = "%s"\n' % (entry["crate"], entry["version"])
        require(
            needle in lock_text,
            "drifted crate is present in the retained lock at the stated version: "
            f"{entry['crate']} {entry['version']}",
        )

    # The console log must corroborate the exit status and the failing stage.
    console = open(
        os.path.join(root, "remote-evidence", "prebuild-console.log"), encoding="ascii"
    ).read()
    require(
        "PREBUILD_EXIT=%s" % identities["prebuild_exit_status"] in console,
        "console log records the declared prebuild exit status",
    )
    require(
        int(identities["prebuild_exit_status"]) != 0,
        "a NO-ATTEMPT route has a non-zero prebuild exit status",
    )
    require(
        "G6 PREBUILD NO-ATTEMPT / NO-SELECT:" in console,
        "console log carries the helper's terminal NO-ATTEMPT marker",
    )
    require(observed in console, "console log records the observed lock SHA")
    require(
        EXPECTED_LOCK_SHA in console, "console log records the expected lock SHA"
    )

    # --- one-shot allowance conservation ------------------------------------
    allowances = result["one_shot_allowances"]
    require(
        allowances["prebuild"]["consumed"] is True,
        "the prebuild allowance is recorded as consumed",
    )
    require(
        allowances["prebuild"]["exit_status"]
        == int(identities["prebuild_exit_status"]),
        "allowance exit status agrees with identities.tsv",
    )
    for phase in ("validation", "admission", "campaign"):
        require(
            allowances[phase]["consumed"] is False,
            f"{phase} allowance is unspent on a prebuild-only route",
        )
        require(
            allowances[phase]["outcome"] == "NOT REACHED",
            f"{phase} outcome is explicitly NOT REACHED",
        )

    # --- terminal-state / zero-sample / zero-admission predicates ------------
    for key in ZERO_COUNT_KEYS:
        require(
            result["zero_counts"][key] == 0,
            f"zero-count predicate holds: {key}",
        )
    for key in (
        "targets_built",
        "receipt_published",
        "admission_submitted",
        "campaign_submitted",
        "campaign_cells",
        "perf_data_artifacts",
        "attribution_artifacts",
        "timing_artifacts",
    ):
        require(identities[key] == "0", f"identities.tsv zero predicate holds: {key}")

    require(
        identities["admission_unit_load_state"] == "not-found",
        "admission unit was never created",
    )
    require(
        identities["campaign_unit_load_state"] == "not-found",
        "campaign unit was never created",
    )

    # --- mapping / publication predicates -----------------------------------
    # No service was submitted, so both fixed service-evidence files must carry
    # an explicit NOT REACHED record rather than an absence or a PASS.
    unit_properties = open(
        os.path.join(root, "unit-properties.txt"), encoding="ascii"
    ).read()
    require(
        "[NOT REACHED:" in unit_properties,
        "unit-properties.txt carries an explicit NOT REACHED record",
    )
    require(
        "N/A" not in unit_properties and "PASS" not in unit_properties,
        "unit-properties.txt never converts absence into N/A or PASS",
    )

    journal_path = os.path.join(root, "systemd-journal.canonical.jsonl")
    journal_lines = [
        line for line in open(journal_path, encoding="ascii").read().splitlines() if line
    ]
    require(journal_lines, "canonical journal file is non-empty")
    marker_seen = False
    for line in journal_lines:
        event = json.loads(line)  # fail closed on malformed JSON
        if "[NOT REACHED:" in json.dumps(event):
            marker_seen = True
    require(
        marker_seen,
        "canonical journal carries an explicit NOT REACHED record",
    )

    # --- remote tree manifest predicates ------------------------------------
    manifest = {}
    with open(
        os.path.join(root, "remote-tree-manifest.tsv"), encoding="ascii"
    ) as handle:
        header = handle.readline().rstrip("\n")
        require(
            header == "path\ttype\tmode\towner\tbytes",
            "remote-tree-manifest.tsv header is exact",
        )
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            require(
                len(parts) == 5, f"manifest row is a 5-field record: {line!r}"
            )
            require(parts[0] not in manifest, f"manifest path is unique: {parts[0]}")
            manifest[parts[0]] = parts[1]
    for path in MUST_BE_ABSENT:
        require(path in manifest, f"manifest covers owned path: {path}")
        require(
            manifest[path] == "absent",
            f"owned path was never created on a prebuild-only route: {path}",
        )
    for path in (
        "cubr-new24-full-binary-g6-src-a",
        "cubr-new24-full-binary-g6-src-b",
    ):
        require(path in manifest, f"manifest covers created source tree: {path}")
        require(
            manifest[path] == "d",
            f"created source tree is a real directory, not a symlink: {path}",
        )

    # --- external-effect boundary -------------------------------------------
    for channel, count in result["external_effects"].items():
        require(count == 0, f"no external mutation on channel: {channel}")
    require(
        identities["database_mutations"] == "0",
        "identities.tsv records zero database mutations",
    )

    # --- statistical predicate ----------------------------------------------
    # G6 produced no sample, so a per-file P1-P5 evaluation must be empty
    # rather than fabricated.
    require(
        result["per_file_evaluation"]["files"] == {},
        "no per-file statistical claim is made without a sample",
    )

    # --- evidence hash conservation -----------------------------------------
    declared = result["evidence_sha256"]
    for relative, expected in declared.items():
        target = os.path.join(root, relative)
        require(os.path.isfile(target), f"declared evidence file exists: {relative}")
        require(
            sha256_of(target) == expected,
            f"declared evidence hash matches the file on disk: {relative}",
        )
    for relative in REQUIRED_FILES:
        if relative == "result.json":
            continue
        require(
            relative in declared,
            f"every retained evidence file is hash-declared: {relative}",
        )


def main(argv: list) -> int:
    root = argv[1] if len(argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    try:
        verify(root)
    except Failure as failure:
        print(f"G6 RESULT PACKAGE FAIL: {failure}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(
            f"G6 RESULT PACKAGE FAIL: unreadable package ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 1
    print("g6_result_package=PASS verdict=NO-ATTEMPT / NO-SELECT route=prebuild-only")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
