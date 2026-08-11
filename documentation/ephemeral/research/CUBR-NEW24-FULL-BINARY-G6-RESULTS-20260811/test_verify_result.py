#!/usr/bin/env python3
"""Mutation suite for the G6 terminal result-package verifier.

Contract proven here:

1. The unmodified package verifies GREEN in a fresh process.
2. Every mutation below actually changes the package bytes (no no-op mutants).
3. Every mutation drives the verifier RED in a fresh process.
4. After restoring the mutated input, the package verifies GREEN again in a
   fresh process.

A verifier that stayed GREEN under any of these mutations would not be proving
the corresponding predicate, so a surviving mutant fails this suite.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFIER = os.path.join(HERE, "verify_result.py")
EVIDENCE = "remote-evidence"
LOCK_A = os.path.join(EVIDENCE, "Cargo.lock.src-a")
LOCK_B = os.path.join(EVIDENCE, "Cargo.lock.src-b")
CONSOLE = os.path.join(EVIDENCE, "prebuild-console.log")


def run_verifier(root: str) -> subprocess.CompletedProcess:
    """Run the verifier in a FRESH process against `root`."""
    return subprocess.run(
        [sys.executable, VERIFIER, root],
        capture_output=True,
        text=True,
        check=False,
    )


def snapshot(root: str) -> dict:
    state = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            with open(path, "rb") as handle:
                state[os.path.relpath(path, root)] = handle.read()
    return state


# --- mutation primitives ---------------------------------------------------


def drop_file(relative: str):
    def apply(root: str) -> None:
        os.remove(os.path.join(root, relative))

    return apply


def edit_json(relative: str, path: tuple, value: object):
    def apply(root: str) -> None:
        target = os.path.join(root, relative)
        with open(target, encoding="ascii") as handle:
            document = json.load(handle)
        cursor = document
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with open(target, "w", encoding="ascii") as handle:
            handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")

    return apply


def replace_text(relative: str, old: str, new: str):
    def apply(root: str) -> None:
        target = os.path.join(root, relative)
        with open(target, encoding="ascii") as handle:
            body = handle.read()
        if old not in body:
            raise AssertionError(f"mutation precondition absent in {relative}: {old!r}")
        with open(target, "w", encoding="ascii") as handle:
            handle.write(body.replace(old, new, 1))

    return apply


def append_text(relative: str, suffix: str):
    def apply(root: str) -> None:
        with open(os.path.join(root, relative), "a", encoding="ascii") as handle:
            handle.write(suffix)

    return apply


def symlink_file(relative: str):
    def apply(root: str) -> None:
        target = os.path.join(root, relative)
        stashed = target + ".stash"
        os.rename(target, stashed)
        os.symlink(stashed, target)

    return apply


OTHER_SHA = "1" * 64

# (name, mutation) -- each must drive the verifier RED.
MUTATIONS = [
    # presence / publication
    ("drop-result-json", drop_file("result.json")),
    ("drop-identities", drop_file("identities.tsv")),
    ("drop-manifest", drop_file("remote-tree-manifest.tsv")),
    ("drop-unit-properties", drop_file("unit-properties.txt")),
    ("drop-journal", drop_file("systemd-journal.canonical.jsonl")),
    ("drop-console", drop_file(CONSOLE)),
    ("drop-lock-a", drop_file(LOCK_A)),
    ("drop-lock-b", drop_file(LOCK_B)),
    ("symlinked-console", symlink_file(CONSOLE)),
    # terminal-route / no-selection
    ("nonterminal-verdict", edit_json("result.json", ("verdict",), "IN-PROGRESS")),
    (
        "selection-claimed",
        edit_json("result.json", ("selection", "source_change_selected"), True),
    ),
    (
        "verdict-disagreement",
        replace_text("identities.tsv", "verdict\tNO-ATTEMPT / NO-SELECT", "verdict\tVOID / NO-SELECT"),
    ),
    ("route-disagreement", edit_json("result.json", ("route",), "campaign")),
    # identity
    (
        "instrument-main-drift",
        replace_text("identities.tsv", "instrument_main\t756ff160", "instrument_main\t0000000"),
    ),
    (
        "instrument-main-drift-json",
        edit_json("result.json", ("instrument", "resulting_main"), "deadbeef"),
    ),
    (
        "instrument-blob-drift",
        replace_text("identities.tsv", "instrument_blob_run_sh\t8c5ed11b", "instrument_blob_run_sh\t0000000f"),
    ),
    (
        "map-blob-drift",
        replace_text("identities.tsv", "instrument_blob_map_py\t310240da", "instrument_blob_map_py\t0000000d"),
    ),
    (
        "frozen-source-drift",
        replace_text("identities.tsv", "frozen_source_commit\t830a9a31", "frozen_source_commit\t0000000a"),
    ),
    (
        "src-a-head-drift",
        replace_text("identities.tsv", "src_a_head\t830a9a31", "src_a_head\t0000000a"),
    ),
    (
        "rustc-commit-drift",
        replace_text("identities.tsv", "rustc_commit\t31fca3adb", "rustc_commit\t00000000b"),
    ),
    # failure-mechanism / conservation
    (
        "expected-lock-rewritten",
        edit_json("result.json", ("failure", "expected_lock_sha256"), OTHER_SHA),
    ),
    (
        "failure-erased",
        edit_json(
            "result.json",
            ("failure", "observed_lock_sha256"),
            "0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9",
        ),
    ),
    (
        "observed-lock-unbacked",
        edit_json("result.json", ("failure", "observed_lock_sha256"), OTHER_SHA),
    ),
    ("lock-a-tampered", append_text(LOCK_A, "\n# tampered\n")),
    ("lock-b-tampered", append_text(LOCK_B, "\n# tampered\n")),
    (
        "lock-bytes-drift",
        edit_json("result.json", ("failure", "observed_lock_bytes"), 12345),
    ),
    (
        "independence-claim-false",
        edit_json("result.json", ("failure", "independent_clones_agree"), False),
    ),
    (
        "drift-crate-unsupported",
        edit_json(
            "result.json",
            ("failure", "drifted_crates"),
            [{"crate": "not-a-real-crate", "version": "9.9.9", "published_utc": "2026-01-01T00:00:00Z"}],
        ),
    ),
    (
        "console-marker-removed",
        replace_text(CONSOLE, "G6 PREBUILD NO-ATTEMPT / NO-SELECT:", "G6 PREBUILD OK:"),
    ),
    ("console-exit-removed", replace_text(CONSOLE, "PREBUILD_EXIT=1", "PREBUILD_EXIT=")),
    (
        "exit-status-zeroed",
        replace_text("identities.tsv", "prebuild_exit_status\t1", "prebuild_exit_status\t0"),
    ),
    # one-shot allowance conservation
    (
        "validation-allowance-spent",
        edit_json("result.json", ("one_shot_allowances", "validation", "consumed"), True),
    ),
    (
        "admission-allowance-spent",
        edit_json("result.json", ("one_shot_allowances", "admission", "consumed"), True),
    ),
    (
        "campaign-allowance-spent",
        edit_json("result.json", ("one_shot_allowances", "campaign", "consumed"), True),
    ),
    (
        "campaign-outcome-laundered",
        edit_json("result.json", ("one_shot_allowances", "campaign", "outcome"), "PASS"),
    ),
    (
        "prebuild-allowance-disclaimed",
        edit_json("result.json", ("one_shot_allowances", "prebuild", "consumed"), False),
    ),
    # zero-sample / zero-admission
    ("campaign-cells-nonzero", edit_json("result.json", ("zero_counts", "campaign_cells"), 1)),
    ("perf-data-nonzero", edit_json("result.json", ("zero_counts", "perf_data"), 1)),
    ("targets-built-nonzero", edit_json("result.json", ("zero_counts", "targets_built"), 2)),
    (
        "attribution-nonzero",
        edit_json("result.json", ("zero_counts", "attribution_artifacts"), 1),
    ),
    (
        "identities-campaign-cells-nonzero",
        replace_text("identities.tsv", "campaign_cells\t0", "campaign_cells\t9"),
    ),
    (
        "admission-unit-materialized",
        replace_text(
            "identities.tsv",
            "admission_unit_load_state\tnot-found",
            "admission_unit_load_state\tloaded",
        ),
    ),
    (
        "campaign-unit-materialized",
        replace_text(
            "identities.tsv",
            "campaign_unit_load_state\tnot-found",
            "campaign_unit_load_state\tloaded",
        ),
    ),
    # mapping / NOT REACHED discipline
    (
        "unit-properties-not-reached-removed",
        replace_text("unit-properties.txt", "[NOT REACHED:", "[reached:"),
    ),
    (
        "unit-properties-laundered-to-pass",
        append_text("unit-properties.txt", "\nPASS\n"),
    ),
    (
        "unit-properties-laundered-to-na",
        append_text("unit-properties.txt", "\nN/A\n"),
    ),
    (
        "journal-not-reached-removed",
        replace_text("systemd-journal.canonical.jsonl", "[NOT REACHED:", "[reached:"),
    ),
    (
        "journal-malformed",
        append_text("systemd-journal.canonical.jsonl", "{not json}\n"),
    ),
    # remote tree manifest
    (
        "receipt-materialized",
        replace_text(
            "remote-tree-manifest.tsv",
            "cubr-new24-full-binary-g6-prebuild-receipt-20260811\tabsent",
            "cubr-new24-full-binary-g6-prebuild-receipt-20260811\td",
        ),
    ),
    (
        "campaign-tree-materialized",
        replace_text(
            "remote-tree-manifest.tsv",
            "cubr-new24-full-binary-g6-20260811\tabsent",
            "cubr-new24-full-binary-g6-20260811\td",
        ),
    ),
    (
        "target-materialized",
        replace_text(
            "remote-tree-manifest.tsv",
            "cubr-new24-full-binary-g6-target-a\tabsent",
            "cubr-new24-full-binary-g6-target-a\td",
        ),
    ),
    (
        "src-a-symlinked",
        replace_text(
            "remote-tree-manifest.tsv",
            "cubr-new24-full-binary-g6-src-a\td",
            "cubr-new24-full-binary-g6-src-a\tsymlink",
        ),
    ),
    (
        "manifest-row-dropped",
        replace_text(
            "remote-tree-manifest.tsv",
            "cubr-new24-full-binary-g6-map-dryrun-20260811\tabsent\t-\t-\t-\n",
            "",
        ),
    ),
    # external effects / statistics
    ("database-mutation", edit_json("result.json", ("external_effects", "database"), 1)),
    ("site-mutation", edit_json("result.json", ("external_effects", "site"), 1)),
    (
        "identities-database-mutation",
        replace_text("identities.tsv", "database_mutations\t0", "database_mutations\t1"),
    ),
    (
        "fabricated-per-file-claim",
        edit_json(
            "result.json",
            ("per_file_evaluation", "files"),
            {"dickens": {"P1": "PASS"}},
        ),
    ),
    # evidence hash conservation
    (
        "declared-hash-drift",
        edit_json("result.json", ("evidence_sha256", "identities.tsv"), OTHER_SHA),
    ),
    (
        "manifest-hash-drift",
        edit_json("result.json", ("evidence_sha256", "remote-tree-manifest.tsv"), OTHER_SHA),
    ),
    (
        "identities-silently-edited",
        replace_text("identities.tsv", "host\tdev-ai", "host\tsomewhere-else"),
    ),
]


def main() -> int:
    failures = []
    noop_mutants = []

    # 1. baseline GREEN in a fresh process
    baseline = run_verifier(HERE)
    if baseline.returncode != 0:
        print("FAIL baseline: unmodified package did not verify GREEN")
        print(baseline.stdout, baseline.stderr)
        return 1
    print("ok baseline - unmodified package verifies GREEN in a fresh process")

    original = snapshot(HERE)

    # 2/3. every mutation must change bytes and drive the verifier RED
    for name, mutate in MUTATIONS:
        with tempfile.TemporaryDirectory() as work:
            root = os.path.join(work, "pkg")
            shutil.copytree(HERE, root, symlinks=True)
            try:
                mutate(root)
            except AssertionError as error:
                failures.append(f"{name}: mutation could not be applied ({error})")
                continue

            if snapshot(root) == original:
                noop_mutants.append(name)
                failures.append(f"{name}: NO-OP MUTANT - package bytes unchanged")
                continue

            outcome = run_verifier(root)
            if outcome.returncode == 0:
                failures.append(
                    f"{name}: MUTANT SURVIVED - verifier stayed GREEN under mutation"
                )
            else:
                print(f"ok mutant killed: {name}")

    # 4. restoration proves the RED was caused by the mutation, not by the run
    with tempfile.TemporaryDirectory() as work:
        root = os.path.join(work, "pkg")
        shutil.copytree(HERE, root, symlinks=True)
        target = os.path.join(root, CONSOLE)
        with open(target, "rb") as handle:
            saved = handle.read()
        os.remove(target)
        if run_verifier(root).returncode == 0:
            failures.append("restore-cycle: verifier stayed GREEN with evidence deleted")
        else:
            print("ok restore-cycle - deleting a result-bearing input proves RED")
        with open(target, "wb") as handle:
            handle.write(saved)
        if run_verifier(root).returncode != 0:
            failures.append("restore-cycle: verifier did not return GREEN after restore")
        else:
            print("ok restore-cycle - restoring it returns fresh-process GREEN")

    print()
    if noop_mutants:
        print(f"NO-OP MUTANTS: {len(noop_mutants)} -> {', '.join(noop_mutants)}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"g6_result_verifier_contract=FAIL failures={len(failures)}")
        return 1
    print(
        "g6_result_verifier_contract=PASS "
        f"mutants={len(MUTATIONS)} noop_mutants=0 surviving_mutants=0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
