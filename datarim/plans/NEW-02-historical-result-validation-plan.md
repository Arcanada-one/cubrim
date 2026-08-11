# NEW-02 Historical Result Validation Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended, when your runtime supports spawning isolated agents) or `executing-plans` (single-session execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone, version-frozen validator that can authenticate the immutable NEW-02 raw publication after `origin/main` has advanced, rebuild and verify the derived result package deterministically, and add strictly supplemental systemd correlation evidence without rewriting canonical capture identity.

**Architecture:** A single stdlib Python validator owns a frozen NEW-02 contract and has three explicit boundaries: current-repository authentication, offline/read-only raw-publication validation, and supplemental systemd-evidence validation. The existing derived-package builder calls that validator instead of importing the execution harness; the capture harness and its test remain byte-identical to their execution-commit blobs. A narrow shell collector captures exact `systemctl --user show` and unit-filtered `journalctl --user` JSON bytes from `arcana-devs`, rejects unsafe fields or secret-like material, and records the result as correlated rather than canonical.

**Tech Stack:** Python 3.12 standard library (`argparse`, `dataclasses`, `decimal`, `hashlib`, `json`, `pathlib`, `stat`, `subprocess`, `unittest`), Bash strict mode, Git plumbing, systemd user-manager read APIs, repository CI and protected pull requests.

---

## Decision and non-negotiable truth boundaries

This plan implements consilium Option B. The historical validator is a new post-capture verifier; it is not the capture harness and cannot retroactively make supplemental evidence canonical.

| Layer | Exact successful value | Authority |
|---|---|---|
| `CAPTURE_STATUS` | `COMPLETE` | Frozen raw `COMPLETE`, raw manifest, provenance, and all 243 rows |
| `HISTORICAL_VALIDATION_STATUS` | `PASS` | This version-frozen validator over current Git provenance and immutable raw bytes |
| `SCIENTIFIC_CHARACTERIZATION` | `CHARACTERIZED_NO_SELECT` | Preregistered result-package interpretation |
| `PRODUCT_SELECTION_STATUS` | `NOT_ISSUED` | No winner, GO, ceiling, aggregate, or product candidate was preregistered |
| `SYSTEMD_CORRELATION_STATUS` | `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF` when the exact snapshot validates; otherwise `SYSTEMD_EVIDENCE_UNAVAILABLE` | Read-only post-capture start correlation only; never exit/restart/capture authority |

The validator may authenticate stored capture claims, but it must not claim that it freshly ran 7-Zip, decoded an archive, compared source bytes, or reproduced GNU time. It verifies exact archive/decoded/timing bytes, command arrays, captured listing semantics, return codes, and source identities already sealed by the raw manifest. Fresh tool execution remains a property of the original canonical harness only.

The following canonical sentinels remain unchanged in the derived package:

```text
execution_identity.systemd_unit=NOT_RECORDED_BY_CANONICAL_HARNESS
execution_identity.systemd_invocation_id=NOT_RECORDED_BY_CANONICAL_HARNESS
```

The original capture sources are immutable and must have no diff throughout implementation:

```text
documentation/ephemeral/research/new02_oracle_grid.py
documentation/ephemeral/research/test_new02_oracle_grid.py
documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md
```

## Frozen identities

### Git and source-object pins

| Identity | Exact value |
|---|---|
| Execution commit | `708cda945a285526610371d812e4f54725eb6baf` |
| Execution tree | `9cdad69314f94e0cc0323b1dd6fb64d34c0f677b` |
| Preregistration blob / size / SHA-256 | `d96df7e3478a6ba52b737ef30dea63d68b0e01ac` / `7651` / `fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093` |
| Harness blob / size / SHA-256 | `3acaa4a5fc2b5622404f041a28575cbf9ad10bd5` / `84669` / `35c2f7eb7dc7f3ef5008136b7658607342273df36c8c9b13d3fdeda80f3143c5` |
| Harness-test blob / size / SHA-256 | `ccf6613b13aa178eb1bb6a0896e5ea8b0276e10b` / `58121` / `35be4a2cdcf5f09487eddd542966c3435bedf40874e6b081fe282b6edb8eb005` |

### Raw-publication pins

| Identity | Exact value |
|---|---|
| Raw basename | `new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z` |
| Final namespace | `/home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z` |
| Harness run ID | `4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba` |
| Inventory SHA-256 | `77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda` |
| Grid SHA-256 | `8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4` |
| `COMPLETE` SHA-256 | `9db58ad5bfa01bfeaff2f46807d0645baa2e002cd1ed930585fcefb2ce177d06` |
| `MANIFEST.json` SHA-256 | `4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c` |
| `observations.jsonl` SHA-256 | `7622bb1eed1199f98c599cdad588340fcffc3df74b03eef32f37b16c4eabe75c` |
| `provenance.json` SHA-256 | `42caafdbcf13c37e3f7b6f57f62a1923c35c470bf2c22bda04d645b3f1b6fc6b` |
| 7-Zip binary SHA-256 | `60fc00b4e1ed37668972c51f03426973d8006db3c7224075878f6d66196d7c27` |
| `cmp` binary SHA-256 | `e10750ef3db9bd3595d3cbb1e25bcfd6a964dc6aa0ba9561034067913ee1cc04` |
| `taskset` binary SHA-256 | `a9c851792e54e91fba7b827019380abee54e715b6817899c835e4f221354b260` |
| GNU time binary SHA-256 | `3b11dec50514a8473e9f6efa7a34d584d0657538c09988f61b72d38ad4991a10` |

The frozen axes are inventory order, then order `(4, 6, 8)`, then requested memory `(16, 64, 256)` MiB, with CPU set `0-15`, producing exactly 243 cells. The 27-entry inventory tuple, including every path, byte count, and source SHA-256, is copied literally into the new validator from the execution blob at lines 104-132; it is encoded with `json.dumps(tuple, separators=(",", ":"), ensure_ascii=True).encode()` and must recompute to the inventory pin above. The grid appends order, memory, and CPU set to each tuple entry using the same encoding and must recompute to the grid pin above.

### Supplemental systemd correlation pins

```text
CAPTURE_HOST=arcana-devs
USER_UNIT=cubr-new02-oracle-20260810t020926z.service
USER_INVOCATION_ID=f648d8b61de34ae0900291a06371a3dc
```

`USER_UNIT` and `USER_INVOCATION_ID` in the three user-journal records are the correlation keys. `_SYSTEMD_UNIT` identifies the user manager (`user@1002.service`) and must not be compared to `USER_UNIT`. The transient unit is unloaded: current show fields such as blank `InvocationID`, `Result=success`, `NRestarts=0`, `ExecMainCode=0`, and `ExecMainStatus=0` are unloaded defaults and are explicitly non-probative. The journal proves only that systemd recorded start/started/resource messages for the exact command namespace; it contains no authoritative process-exit or restart-history proof.

## File map

| Operation | Exact path | Responsibility |
|---|---|---|
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py` `[to-be-created on origin/main]` | Standalone frozen Git/raw/systemd validator; no import of the capture harness |
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py` `[to-be-created on origin/main]` | Synthetic fixtures, real-publication acceptance, exhaustive mutation contracts |
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh` `[to-be-created on origin/main]` | Read-only, atomic, narrow systemd evidence capture |
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/systemctl-show.txt` `[to-be-created on origin/main]` | Exact show-command bytes |
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/journalctl-user-unit.jsonl` `[to-be-created on origin/main]` | Exact user-unit journal JSON bytes |
| Create | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/capture.json` `[to-be-created on origin/main]` | Byte hashes, counts, exact correlation assertions, classification |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py` `[to-be-created on origin/main; present in result worktree]` | Use historical validator for raw authentication and deterministic rebuild |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py` `[to-be-created on origin/main; present in result worktree]` | Regression coverage for advanced-main rebuild and separated statuses |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md` `[to-be-created on origin/main; present in result worktree]` | Explain historical validation versus canonical capture and systemd correlation |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json` `[to-be-created on origin/main; present in result worktree]` | Add historical-validation and supplemental-evidence sections without changing sentinels |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv` `[to-be-created on origin/main; present in result worktree]` | Deterministic 243-row projection of authenticated stored observations |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv` `[to-be-created on origin/main; present in result worktree]` | Deterministic 27-row per-file effect projection from `results.tsv` |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json` `[to-be-created on origin/main; present in result worktree]` | Carry the five independent status values |
| Modify | `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS` `[to-be-created on origin/main; present in result worktree]` | Re-pin deterministic derived files after their intentional changes |

The implementation must not edit either capture-harness file, the preregistration, the raw publication, or its parent directory.

### Task 1: Freeze repository and execution-object authentication

**Files:**
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py`
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`

- [ ] **Step 1: Write failing repository-authentication tests**

Add tests named exactly:

```python
REPO_ROOT = Path(__file__).resolve().parents[4]

class RepositoryTests(unittest.TestCase):
    def test_advanced_current_main_with_execution_ancestor_passes(self) -> None:
        probe = FakeGitProbe(local_main="b" * 40, remote_main="b" * 40, ancestor=True)
        self.assertEqual(verify_repository(REPO_ROOT, probe).current_main, "b" * 40)

    def test_stale_tracking_ref_fails(self) -> None:
        probe = FakeGitProbe(local_main="b" * 40, remote_main="c" * 40, ancestor=True)
        with self.assertRaises(HistoricalValidationError) as raised:
            verify_repository(REPO_ROOT, probe)
        self.assertEqual(raised.exception.code, "REPOSITORY_REMOTE_TRACKING_MISMATCH")

    def test_execution_object_mutations_fail(self) -> None:
        evidence = verify_repository(REPO_ROOT, FakeGitProbe.valid())
        self.assertEqual(evidence.execution_commit, EXECUTION_COMMIT)
        self.assertEqual(evidence.execution_tree, EXECUTION_TREE)
        self.assertEqual(set(evidence.source_blobs), set(SOURCE_BLOBS))
```

The fake probe returns exact output per argument vector and records all calls. Add separate mutations for missing execution object, `tree` returned where `commit` is required, tree-SHA drift, missing blob, wrong blob type, blob object-ID drift, size drift, and SHA-256 drift. Each mutation must assert its stable code: `EXECUTION_COMMIT_MISSING`, `EXECUTION_OBJECT_TYPE_MISMATCH`, `EXECUTION_TREE_MISMATCH`, `SOURCE_BLOB_MISSING`, `SOURCE_BLOB_TYPE_MISMATCH`, `SOURCE_BLOB_ID_MISMATCH`, `SOURCE_BLOB_SIZE_MISMATCH`, or `SOURCE_BLOB_SHA256_MISMATCH`.

- [ ] **Step 2: Run the focused tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: exit `1`; import fails because `verify_new02_historical.py` does not yet expose `verify_repository`, `EXECUTION_COMMIT`, `EXECUTION_TREE`, and `SOURCE_BLOBS`.

- [ ] **Step 3: Implement the minimal repository boundary**

Use the exact constants below:

```python
EXECUTION_COMMIT = "708cda945a285526610371d812e4f54725eb6baf"
EXECUTION_TREE = "9cdad69314f94e0cc0323b1dd6fb64d34c0f677b"
SOURCE_BLOBS = {
    "documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md": (
        "d96df7e3478a6ba52b737ef30dea63d68b0e01ac", 7651,
        "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093",
    ),
    "documentation/ephemeral/research/new02_oracle_grid.py": (
        "3acaa4a5fc2b5622404f041a28575cbf9ad10bd5", 84669,
        "35c2f7eb7dc7f3ef5008136b7658607342273df36c8c9b13d3fdeda80f3143c5",
    ),
    "documentation/ephemeral/research/test_new02_oracle_grid.py": (
        "ccf6613b13aa178eb1bb6a0896e5ea8b0276e10b", 58121,
        "35be4a2cdcf5f09487eddd542966c3435bedf40874e6b081fe282b6edb8eb005",
    ),
}
```

`GitProbe.run()` must call `subprocess.run(("git", *args), cwd=repo, check=False, stdout=PIPE, stderr=PIPE)` without a shell. `verify_repository()` must perform, in order:

```text
rev-parse --verify refs/remotes/origin/main
ls-remote origin refs/heads/main
merge-base --is-ancestor 708cda945a285526610371d812e4f54725eb6baf VERIFIED_CURRENT_MAIN
cat-file -e 708cda945a285526610371d812e4f54725eb6baf^{commit}
cat-file -t 708cda945a285526610371d812e4f54725eb6baf
rev-parse 708cda945a285526610371d812e4f54725eb6baf^{tree}
for source_path in \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md \
  documentation/ephemeral/research/new02_oracle_grid.py \
  documentation/ephemeral/research/test_new02_oracle_grid.py
do
  cat-file -e "708cda945a285526610371d812e4f54725eb6baf:$source_path"
  cat-file -t "708cda945a285526610371d812e4f54725eb6baf:$source_path"
  rev-parse "708cda945a285526610371d812e4f54725eb6baf:$source_path"
  cat-file -s "708cda945a285526610371d812e4f54725eb6baf:$source_path"
  cat-file blob "708cda945a285526610371d812e4f54725eb6baf:$source_path"
done
```

Reject multiple or malformed `ls-remote` rows. Hash the returned blob bytes in Python. Do not compare current `origin/main` for equality with the historical execution commit; only require fresh local/remote equality plus the ancestor gate.

- [ ] **Step 4: Run focused tests and record GREEN**

Run the Step 2 command. Expected: all repository-authentication tests `ok`, exit `0`.

- [ ] **Step 5: Commit this isolated slice**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv
git commit -m "test: freeze NEW-02 execution provenance"
```

### Task 2: Validate raw topology, immutability, manifest, and publication envelope offline

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`

- [ ] **Step 1: Add a valid 243-cell synthetic fixture and topology mutations**

Implement `build_valid_raw_fixture(root: Path, policy: FrozenPolicy) -> Path` in the test file. It must write `cells/{cell.slug}/{payload.7z,decoded.bin,encode.time,decode.time}` for every policy cell, one closed-schema JSONL row per cell, frozen provenance, exhaustive manifest, then `COMPLETE`; finally chmod all files `0444` and all directories including the root `0555`. The production CLI always uses `FROZEN_POLICY`; test injection is an in-process API only.

Add these direct mutations and exact expected error codes:

```python
TOPOLOGY_MUTATIONS = {
    "wrong root basename": "RAW_NAMESPACE_MISMATCH",
    "root symlink": "RAW_SPECIAL_FILE",
    "exact raw sibling .VOID.jsonl": "RAW_VOID_SIBLING_PRESENT",
    "missing cell file": "RAW_PATH_SET_MISMATCH",
    "extra cell file": "RAW_PATH_SET_MISMATCH",
    "file symlink": "RAW_SPECIAL_FILE",
    "file hard link": "RAW_LINK_COUNT_MISMATCH",
    "writable file": "RAW_MODE_MISMATCH",
    "writable directory": "RAW_MODE_MISMATCH",
    "manifest entry removed": "MANIFEST_ENTRY_SET_MISMATCH",
    "manifest entry duplicated": "MANIFEST_DUPLICATE_PATH",
    "manifest size changed": "MANIFEST_SIZE_MISMATCH",
    "manifest hash changed": "MANIFEST_HASH_MISMATCH",
    "manifest status changed from STAGED": "MANIFEST_STATUS_MISMATCH",
    "complete status changed from COMPLETE": "COMPLETE_STATUS_MISMATCH",
    "complete count changed": "COMPLETE_ENVELOPE_MISMATCH",
    "complete namespace changed": "COMPLETE_ENVELOPE_MISMATCH",
    "complete manifest hash changed": "COMPLETE_MANIFEST_MISMATCH",
}
```

Each mutation test restores parent-directory write permission only in its temporary copy, applies one mutation, re-seals unrelated bytes when the defect being tested is semantic, invokes `verify_raw_publication()`, and asserts the stable code.

- [ ] **Step 2: Run topology tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: exit `1`; `verify_raw_publication` and `FrozenPolicy` are missing.

- [ ] **Step 3: Implement the fail-closed raw envelope**

The production policy must require:

```python
RAW_BASENAME = "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
RAW_FINAL_NAMESPACE = "/home/dev/cubr-new02-canonical-runs/" + RAW_BASENAME
RAW_TOP_HASHES = {
    "COMPLETE": "9db58ad5bfa01bfeaff2f46807d0645baa2e002cd1ed930585fcefb2ce177d06",
    "MANIFEST.json": "4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c",
    "observations.jsonl": "7622bb1eed1199f98c599cdad588340fcffc3df74b03eef32f37b16c4eabe75c",
    "provenance.json": "42caafdbcf13c37e3f7b6f57f62a1923c35c470bf2c22bda04d645b3f1b6fc6b",
}
EXPECTED_COUNTS = {"observations": 243, "manifest_entries": 974, "files": 976, "directories": 245}
```

Walk with `os.scandir`/`lstat`; never follow links. Require ordinary files with `st_nlink == 1` and mode `0444`, directories with mode `0555`, no device/socket/FIFO/symlink entries, exactly the root plus `cells` plus 243 cell directories, and exactly 976 files. Normalize manifest paths with `PurePosixPath`, rejecting absolute paths, `..`, `.`, backslashes, duplicate paths, or a path outside the exact set. Stream-hash every file named by the 974-entry manifest and require its exact declared size. Hash the four top-level files against `RAW_TOP_HASHES` only when using `FROZEN_POLICY`; synthetic tests use their internally sealed policy hashes.

Before reading the tree, use `os.path.lexists(raw_root.parent / f"{raw_root.name}.VOID.jsonl")`; any file, link, directory, or special object at that exact sibling name fails `RAW_VOID_SIBLING_PRESENT`. The real-tree positive test must prove the sibling is absent; the mutation creates the exact sibling and expects that code.

The 974 manifest entries are exactly 972 cell artifacts plus `observations.jsonl` and `provenance.json`. They do not include the 27 external source inputs. Historical validation must not claim to re-read those vanished inputs: it authenticates their frozen tuple through the pinned inventory digest, requires every row’s input identity to equal that tuple, and requires each manifested decoded artifact’s size/SHA-256 to equal the corresponding frozen input identity.

`MANIFEST.json` must have exact keys `directories`, `entries`, `observation_count`, `schema`, `status` and exact status `STAGED`. `COMPLETE` must have exact keys `final_namespace`, `manifest_sha256`, `observation_count`, `schema`, `status` and exact status `COMPLETE`. Both require schema `new02-ppmd-oracle-v1` and count 243; only `COMPLETE` carries the exact final namespace and binds the manifest SHA-256. Raw validation opens files read-only and makes no subprocess or network call.

- [ ] **Step 4: Run topology tests and record GREEN**

Run the Step 2 command. Expected: all selected tests `ok`, exit `0`.

- [ ] **Step 5: Commit this isolated slice**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv
git commit -m "feat: authenticate immutable NEW-02 raw topology"
```

### Task 3: Validate every provenance and cell claim without old tools or paths

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`

- [ ] **Step 1: Add semantic mutation tests**

Build table-driven tests covering every row and provenance axis. Each mutation must first rewrite the enclosing manifest and top hashes in the temporary test policy so hash checks pass and the intended semantic gate is what turns RED.

```python
SEMANTIC_MUTATIONS = {
    "provenance run id": "PROVENANCE_RUN_ID_MISMATCH",
    "provenance execution commit": "PROVENANCE_CODE_SHA_MISMATCH",
    "inventory tuple or digest": "INVENTORY_IDENTITY_MISMATCH",
    "grid tuple or digest": "GRID_IDENTITY_MISMATCH",
    "provenance preregistration missing key": "PREREGISTRATION_IDENTITY_MISMATCH",
    "provenance preregistration extra key": "PREREGISTRATION_IDENTITY_MISMATCH",
    "provenance preregistration path drift": "PREREGISTRATION_IDENTITY_MISMATCH",
    "provenance preregistration repo_path drift": "PREREGISTRATION_IDENTITY_MISMATCH",
    "provenance preregistration git_blob_sha drift": "PREREGISTRATION_IDENTITY_MISMATCH",
    "provenance preregistration sha256 drift": "PREREGISTRATION_IDENTITY_MISMATCH",
    "row preregistration missing key": "PREREGISTRATION_IDENTITY_MISMATCH",
    "row preregistration extra key": "PREREGISTRATION_IDENTITY_MISMATCH",
    "row preregistration value drift": "PREREGISTRATION_IDENTITY_MISMATCH",
    "harness identity": "HARNESS_IDENTITY_MISMATCH",
    "harness-test identity": "HARNESS_TEST_IDENTITY_MISMATCH",
    "tool path, version, or hash": "TOOL_IDENTITY_MISMATCH",
    "observation missing, extra, duplicate, or reordered": "OBSERVATION_GRID_MISMATCH",
    "observation closed-schema drift": "OBSERVATION_SCHEMA_MISMATCH",
    "command tool, switch, operand, order, memory, or artifact path": "COMMAND_ARRAY_MISMATCH",
    "archive zero bytes": "ARCHIVE_SIZE_INVALID",
    "artifact path, size, or hash": "ARTIFACT_IDENTITY_MISMATCH",
    "decoded bytes versus frozen input": "DECODED_IDENTITY_MISMATCH",
    "cmp return code or equality flag": "ROUND_TRIP_CLAIM_MISMATCH",
    "sha equality or round-trip flag": "ROUND_TRIP_CLAIM_MISMATCH",
    "listing member count, name, size, method, order, exponent, or error marker": "LISTING_SEMANTICS_MISMATCH",
    "timing missing, duplicate, reordered, malformed, NaN, Inf, or value drift": "TIMING_GRAMMAR_MISMATCH",
    "encode, inspect, or decode return code": "CELL_RETURN_CODE_MISMATCH",
    "captured error marker in stdout": "CELL_ERROR_MARKER",
    "captured error marker in stderr": "CELL_ERROR_MARKER",
}
```

Every preregistration mutation starts from a deep copy of the exact four-key `PREREG` object and changes only the named axis. Both the provenance object and each repeated observation object require dictionary equality (`candidate == PREREG`), so a missing or extra key is as invalid as a changed value. Every child phase is scanned across both `stdout` and `stderr`; the listing parser receives their concatenation after the error-marker gate.

Add a spy test that patches `subprocess.run`, `os.system`, and `shutil.which` to raise during `verify_raw_publication()`. The valid fixture must still pass, proving raw validation neither runs `/usr/bin/7z`, `/usr/bin/cmp`, `/usr/bin/taskset`, `/usr/bin/time`, nor accesses a network.

- [ ] **Step 2: Run semantic tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: exit `1`; at least one mutation is accepted or reports an undefined code.

- [ ] **Step 3: Implement exact provenance and observation validation**

Copy the exact 27-entry `_FROZEN_INVENTORY` tuple from the execution blob into the new file, including cohort, logical name, relative path, byte count, and SHA-256. Do not import `new02_oracle_grid.py` and do not dereference its historical `repo_root`. Recompute the inventory and 243-grid pins using the exact serialization described above.

Require raw provenance’s exact closed schema, axes, CPU set, observation count, publication mode, execution commit, run ID, preregistration blob/SHA/path, harness/test hashes, and all four tool path/version/hash triples. Accept the recorded historical absolute `repo_root` only as sealed data; never open or execute anything through it.

For each canonical cell, derive the slug and exact command arrays:

```python
encode = ["/usr/bin/time", "-v", "-o", f"cells/{slug}/encode.time",
          "/usr/bin/taskset", "-c", "0-15", "/usr/bin/7z", "a", "-t7z",
          "-m0=PPMd", f"-mo={order}", f"-mmem={memory}m", "-bd", "-y",
          f"cells/{slug}/payload.7z", source_operand]
inspect = ["/usr/bin/7z", "l", "-slt", f"cells/{slug}/payload.7z"]
decode = ["/usr/bin/time", "-v", "-o", f"cells/{slug}/decode.time",
          "/usr/bin/taskset", "-c", "0-15", "/usr/bin/7z", "x", "-so", "-y",
          f"cells/{slug}/payload.7z"]
compare = ["/usr/bin/cmp", "-s", source_operand, f"cells/{slug}/decoded.bin"]
```

Derive `source_operand` from cohort plus registered relative path exactly as the raw row does. Require all four artifact objects and the input object to bind path, size, and SHA-256; require manifest agreement; require archive bytes positive; require decoded hash and size equal the frozen input identity; require zero return codes and true equality flags.

Parse stored `archive_inspection.stdout` as evidence: exactly one separator and member; exact member name and size; exact method regex `PPMD:o(4|6|8):mem([0-9]+)` with row order and stored effective exponent; no method chain, LZMA2, extra member, warning, or error marker. This is explicitly stored-output validation, not fresh archive inspection.

Parse each manifested GNU-time artifact with a fixed ordered field-name tuple copied from the execution harness’s `parse_gnu_time` contract. Require every field exactly once and in order, finite nonnegative elapsed `Decimal`, integral nonnegative peak RSS, and exact equality with the row. Do not use float parsing.

- [ ] **Step 4: Run semantic tests and record GREEN**

Run the Step 2 command. Expected: all selected tests `ok`, exit `0`.

- [ ] **Step 5: Commit this isolated slice**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv
git commit -m "feat: validate all NEW-02 historical cell evidence"
```

### Task 4: Add standalone CLI and five-layer output contract

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`

- [ ] **Step 1: Add CLI tests**

Test these exact behaviors:

```python
class CliTests(unittest.TestCase):
    def test_cli_reports_separate_success_layers(self) -> None:
        completed = run_cli("validate", "--repository", self.repository, "--raw-run", self.valid_raw)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines(), [
            "CAPTURE_STATUS=COMPLETE",
            "HISTORICAL_VALIDATION_STATUS=PASS",
            "SCIENTIFIC_CHARACTERIZATION=CHARACTERIZED_NO_SELECT",
            "PRODUCT_SELECTION_STATUS=NOT_ISSUED",
            "SYSTEMD_CORRELATION_STATUS=SYSTEMD_EVIDENCE_UNAVAILABLE",
            "NEW02_HISTORICAL_VALIDATION=PASS cells=243 run_id=" + RAW_RUN_ID,
        ])

    def test_cli_failure_is_stable_and_fail_closed(self) -> None:
        completed = run_cli("validate", "--repository", self.repository, "--raw-run", self.mutated_raw)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("NEW02_HISTORICAL_VALIDATION=FAIL code=", completed.stderr)
        self.assertNotIn("HISTORICAL_VALIDATION_STATUS=PASS", completed.stdout)
```

Also assert `--raw-only` makes zero Git/subprocess calls and that the normal command requires both current-repository and raw validation. `--raw-only` is a diagnostic/offline mode and must print `HISTORICAL_VALIDATION_STATUS=PASS_RAW_ONLY`; it cannot be used as release or merge evidence.

- [ ] **Step 2: Run CLI tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: exit `1`; CLI output is missing.

- [ ] **Step 3: Implement parser and deterministic output**

The parser must expose two subcommands. `validate` exposes:

```python
validate.add_argument("--repository", type=Path)
validate.add_argument("--raw-run", type=Path, required=True)
validate.add_argument("--systemd-evidence", type=Path)
validate.add_argument("--raw-only", action="store_true")
capture = subparsers.add_parser("capture-systemd")
capture.add_argument("--output", type=Path, required=True)
```

`capture-systemd` requires `--output` equal to `Path(__file__).resolve().parent / "systemd-correlated"`; any other path is an argparse error. It always constructs `production_tools(run_capture_command)` and has no command-path, hash, runner, host, unit, invocation, or policy override.

Default `--repository` to `git rev-parse --show-toplevel` only in normal mode. Catch only expected validation, I/O, JSON, Unicode, decimal, and subprocess errors; convert them to stable code/detail output on stderr and exit `2`. Do not print a traceback, environment, journal contents, or repository remote URL. Successful normal mode prints the exact lines in Step 1. If systemd evidence is supplied and passes Task 6, replace `SYSTEMD_EVIDENCE_UNAVAILABLE` with `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF`.

- [ ] **Step 4: Run CLI tests and record GREEN**

Run the Step 2 command. Expected: all CLI tests `ok`, exit `0`.

- [ ] **Step 5: Commit this isolated slice**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv
git commit -m "feat: expose NEW-02 historical validation statuses"
```

### Task 5: Replace the derived builder’s mutable-harness dependency

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS`

- [ ] **Step 1: Add advanced-main and deterministic-rebuild tests**

Replace the old test assumption that the raw verifier imports the landed capture harness. Load `verify_new02_historical.py` by exact sibling path, call its `verify_raw_publication`, and inject the returned immutable rows into the result builder. Add a fake repository where current main differs from `708cda945a285526610371d812e4f54725eb6baf` but ancestry is true; rebuild must pass.

Add `test_result_build_uses_no_landed_oracle_or_fresh_tools`: patch `HISTORICAL.verify_repository` to return fixed repository evidence, install selective result-module `subprocess.run` and `shutil.which` guards that permit only the separately tested authenticated Git-object path, build from a valid raw fixture, and assert success with zero fresh-tool executions or lookups. Also parse the result module AST and assert there is no string/import reference to `new02_oracle_grid`, `_load_landed_oracle`, `/usr/bin/7z`, `/usr/bin/cmp`, `/usr/bin/taskset`, or `/usr/bin/time`; reject unqualified `Name` loads of `verify_repository`, `verify_raw_publication`, `FROZEN_POLICY`, or `expected_memory_exponent`; and require explicit `Import` nodes for `os`, `stat`, and `subprocess`. The corresponding allowed references are only `HISTORICAL.verify_repository`, `HISTORICAL.verify_raw_publication`, `HISTORICAL.FROZEN_POLICY`, and `HISTORICAL.expected_memory_exponent`.

Build twice into separate empty temporary directories and assert byte equality for exactly:

```python
GENERATED_FILES = (
    "README.md", "provenance.json", "results.tsv",
    "effects.tsv", "summary.json", "SHA256SUMS",
)
```

Snapshot `git status --porcelain=v1` and all capture-source hashes before and after both builds; assert both are unchanged. Add package mutations for canonical systemd sentinels, `CHARACTERIZED_NO_SELECT`, `NOT_ISSUED`, `NOT_DEFINED_IN_PREREGISTRATION`, `NOT_COMPUTED`, `per_file_only`, and Canterbury exclusions.

- [ ] **Step 2: Run package tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py
```

Expected: exit `1`; current builder still imports `new02_oracle_grid.py` and rejects advanced current main.

- [ ] **Step 3: Integrate the historical validator and regenerate derived files**

Remove `_landed_oracle_path`, `_load_landed_oracle`, `_inspect_live_publication_archive`, every runtime import of `new02_oracle_grid.py`, and every result-verifier subprocess call to 7-Zip/cmp/taskset/time. Add explicit top-level imports for `importlib.util`, `os`, `stat`, and `subprocess`; do not rely on names leaking from the dynamically loaded historical module. Replace the old helpers and `_verify_result_semantics` with the complete definitions below. Every historical symbol is qualified through `HISTORICAL`; the result module must not import historical helpers into its own global namespace:

```python
import importlib.util
import os
import stat
from typing import Any

def load_historical_validator() -> Any:
    path = Path(__file__).resolve().with_name("verify_new02_historical.py")
    spec = importlib.util.spec_from_file_location("new02_frozen_historical_validator", path)
    if spec is None or spec.loader is None:
        raise VerificationError("historical validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

HISTORICAL = load_historical_validator()

def authenticated_source(raw_root: Path, repository: Path) -> Any:
    HISTORICAL.verify_repository(repository)
    return HISTORICAL.verify_raw_publication(raw_root, HISTORICAL.FROZEN_POLICY)

def expected_result_cells() -> tuple[tuple[Any, str], ...]:
    return tuple(
        (cell, f"PPMD:o{cell.order}:mem"
               f"{HISTORICAL.expected_memory_exponent(cell.entry.size_bytes, cell.memory_mib)}")
        for cell in HISTORICAL.FROZEN_POLICY.cells
    )

def _verify_result_semantics(rows: Sequence[Mapping[str, str]]) -> None:
    expected = expected_result_cells()
    expected_ids = [cell.identifier for cell, _method in expected]
    if len(rows) != len(expected) or [row["cell"] for row in rows] != expected_ids:
        raise VerificationError("results.tsv is not the exact ordered 243-cell grid")
    sha_pattern = re.compile(r"[0-9a-f]{64}")
    for index, (row, (cell, method)) in enumerate(zip(rows, expected, strict=True)):
        excluded = cell.entry.relative_path.startswith("canterbury/")
        fixed = {
            "schema": PACKAGE_SCHEMA, "status": "PASS",
            "run_id": HISTORICAL.RAW_RUN_ID,
            "code_sha": HISTORICAL.EXECUTION_COMMIT,
            "grid_index": str(index), "cell": cell.identifier,
            "cohort": cell.entry.cohort, "file": cell.entry.name,
            "relative_path": cell.entry.relative_path,
            "excluded_from_broad_claims": str(excluded).lower(),
            "input_bytes": str(cell.entry.size_bytes),
            "input_sha256": cell.entry.sha256,
            "order": str(cell.order), "memory_mib": str(cell.memory_mib),
            "cpu_set": "0-15", "member_method": method,
            "member_paths": json.dumps([cell.entry.name], separators=(",", ":")),
            "inspection_returncode": "0", "encode_returncode": "0",
            "decode_returncode": "0", "cmp_returncode": "0",
            "cmp_equal": "true", "sha256_equal": "true", "round_trip": "true",
            "decoded_bytes": str(cell.entry.size_bytes),
            "decoded_sha256": cell.entry.sha256,
        }
        if any(row.get(key) != value for key, value in fixed.items()):
            raise VerificationError(f"source row semantics mismatch at grid index {index}")
        if _exact_integer(row["archive_bytes"], "archive_bytes") <= 0:
            raise VerificationError(f"archive bytes are not positive at grid index {index}")
        for key in ("archive_sha256", "encode_time_sha256", "decode_time_sha256"):
            if sha_pattern.fullmatch(row[key]) is None:
                raise VerificationError(f"source row {key} is invalid at grid index {index}")
        _exact_decimal(row["encode_elapsed_seconds"], "encode_elapsed_seconds")
        _exact_decimal(row["decode_elapsed_seconds"], "decode_elapsed_seconds")
        _exact_integer(row["encode_peak_rss_kib"], "encode_peak_rss_kib")
        _exact_integer(row["decode_peak_rss_kib"], "decode_peak_rss_kib")
```

The result builder consumes only `RawEvidence.provenance` and `RawEvidence.observations` returned by `authenticated_source`. The result verifier derives all 243 expected rows from `expected_result_cells`; it never opens the historical `repo_root`, dereferences any historical inventory/preregistration/tool path, or freshly inspects an archive.

Replace the stale validation prose value exactly:

```python
ARCHIVE_AUTHENTICATION_TEXT = (
    "exact per-cell stored archive SHA-256 and authenticated stored archive-inspection transcript"
)
```

The regenerated README must say `authenticated stored archive-inspection transcript`; it must not say `fresh landed 7z inspection`, `fresh 7z inspection`, or claim that any old capture tool was rerun. `test_result_build_uses_no_landed_oracle_or_fresh_tools` scans the result-module AST for runtime tool execution/import references and scans all generated UTF-8 text (`README.md`, `provenance.json`, `summary.json`, `results.tsv`, and `effects.tsv`) for the two forbidden fresh-inspection phrases. Historical executable paths remain permitted only as sealed provenance identities. The authenticated-stored wording must be present in README and summary.

Replace `_summary_document` and `_readme` in full with the exact binding definitions below; do not surgically retain any sentence from their old bodies. The generated-document regression executes both replacement functions, serializes their returned text/JSON, then scans the complete regenerated document set. Historical executable paths may remain as provenance identities, but no generated sentence may claim a fresh 7-Zip inspection.

Use the binding `build`/`verify` subcommands. `build` requires `--systemd-mode unavailable|correlated`; `--systemd-evidence` is forbidden in unavailable mode and required in correlated mode. `verify` requires the post-commit exact `--trusted-revision`. Normal builds require repository authentication as well as raw authentication. Correlated mode generates these exact status fields:

```json
{
  "capture_status": "COMPLETE",
  "historical_validation_status": "PASS",
  "scientific_characterization": "CHARACTERIZED_NO_SELECT",
  "product_selection_status": "NOT_ISSUED",
  "systemd_correlation_status": "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF"
}
```

In `--systemd-mode unavailable`, `--systemd-evidence` is forbidden, the first four values remain exact, and only `systemd_correlation_status` is `SYSTEMD_EVIDENCE_UNAVAILABLE`. In correlated mode the evidence argument is required and Task 6 performs the final deterministic regeneration with `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF`; neither mode changes canonical sentinels or the historical-validation verdict.

Keep both canonical systemd fields equal to `NOT_RECORDED_BY_CANONICAL_HARNESS`. In README, state that archive/listing/round-trip facts are authenticated historical capture claims and that the new validator does not freshly execute the old tools. Recompute root `SHA256SUMS` from deterministic generated bytes in sorted filename order; never hand-edit digest values.

- [ ] **Step 4: Run package tests and record GREEN**

Run the Step 2 command. Expected: all package tests `ok`, exit `0`; two builds are byte-identical.

- [ ] **Step 5: Commit this isolated slice**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py
git commit -m "fix: rebuild NEW-02 results from frozen history"
```

### Task 6: Capture and validate supplemental systemd evidence

**Files:**
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh`
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/systemctl-show.txt`
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/journalctl-user-unit.jsonl`
- Create: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/capture.json`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS`

- [ ] **Step 1: Add collector and evidence mutation tests**

Test collection through Python DI only: inject `CaptureTools.runner` and a `RuntimeIdentity` whose temporary mode-`0700` directory owns a real AF_UNIX mode-`0666` `bus` socket. Require the two exact argument vectors, the invocation-ID journal match, and the three exact frozen records. Add production-runtime mutations for absent `XDG_RUNTIME_DIR`, noncanonical path, symlink, wrong owner/mode, missing bus, and non-socket bus; each must fail `SYSTEMD_RUNTIME_DIR_INVALID`. Execute the shell wrapper itself with one argument and by a relative path and require exit `64`; execute its absolute path with a fake Python verifier only by replacing the test copy's fixed verifier file, never by PATH substitution. Assert the wrapper contains no unqualified executable and that production CLI exposes no DI option.

Add exact validator mutations:

```python
SYSTEMD_MUTATIONS = {
    "show byte hash": "SYSTEMD_SHOW_HASH_MISMATCH",
    "journal byte hash": "SYSTEMD_JOURNAL_HASH_MISMATCH",
    "wrong USER_UNIT": "SYSTEMD_USER_UNIT_MISMATCH",
    "wrong or mixed USER_INVOCATION_ID": "SYSTEMD_INVOCATION_MISMATCH",
    "command drift": "SYSTEMD_COMMAND_MISMATCH",
    "output namespace or run-prefix drift": "SYSTEMD_NAMESPACE_MISMATCH",
    "show key/type/value drift": "SYSTEMD_SHOW_SCHEMA_MISMATCH",
    "journal key/type/order drift": "SYSTEMD_JOURNAL_SCHEMA_MISMATCH",
    "invalid user bus runtime": "SYSTEMD_RUNTIME_DIR_INVALID",
    "show defaults asserted as exit proof": "SYSTEMD_OVERCLAIM_REJECTED",
    "Environment field present": "SYSTEMD_UNSAFE_FIELD",
    "secret-like key or value present": "SYSTEMD_SECRET_SCAN_FAILED",
    "canonical sentinel changed": "CANONICAL_SYSTEMD_SENTINEL_MISMATCH",
}
```

- [ ] **Step 2: Run systemd tests and record RED**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: exit `1`; collector and evidence validator do not exist.

- [ ] **Step 3: Implement the narrow atomic collector**

The complete shell wrapper is:

```bash
#!/usr/bin/bash
set -euo pipefail
IFS=$'\n\t'
if (( $# != 0 )); then
  /usr/bin/printf '%s\n' 'capture_new02_systemd_evidence.sh accepts no arguments' >&2
  exit 64
fi
if [[ "${BASH_SOURCE[0]}" != /* ]]; then
  /usr/bin/printf '%s\n' 'invoke this wrapper by absolute path' >&2
  exit 64
fi
readonly SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
readonly VERIFIER="$SCRIPT_DIR/verify_new02_historical.py"
readonly EVIDENCE_DIR="$SCRIPT_DIR/systemd-correlated"
readonly RUNTIME_DIR="${XDG_RUNTIME_DIR:-}"
exec /usr/bin/env -i LC_ALL=C LANG=C XDG_RUNTIME_DIR="$RUNTIME_DIR" \
  /usr/bin/python3 "$VERIFIER" capture-systemd --output "$EVIDENCE_DIR"
```

Production execution has no PATH lookup. It accepts only the inherited `XDG_RUNTIME_DIR`, requires it equal `Path(f"/run/user/{os.getuid()}")`, validates a real owner-matching mode-`0700` directory and owner-matching AF_UNIX mode-`0666` `bus` socket, then passes only `LC_ALL=C`, `LANG=C`, and that validated path to child commands. Before capture, resolve and hash these four executables exactly:

| Command path | `realpath` | SHA-256 |
|---|---|---|
| `/usr/bin/systemctl` | `/usr/bin/systemctl` | `7ba82b5ba146759c710e1b80fadaa3fdbc0f9b85c8fb2c8c3196b7b1a0037ef8` |
| `/usr/bin/journalctl` | `/usr/bin/journalctl` | `c49bd25d7e7655b9a44ff867923952ed5a5e0a65e9df7a0510e239bf0558e3fa` |
| `/usr/bin/hostname` | `/usr/bin/hostname` | `071fec20458397874e6121589d5210e7eed22a1b1afe16c2b9970b8a8233cc5b` |
| `/usr/bin/python3` | `/usr/bin/python3.12` | `1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118` |

Tests inject `CaptureTools` and `RuntimeIdentity` directly into `capture_systemd_evidence`; the production CLI constructs both from fixed executable constants, `os.getuid()`, and the validated inherited `XDG_RUNTIME_DIR`, and exposes no DI flag.

The wrapper accepts no arguments. Test-only destination and tool injection occur by importing `capture_systemd_evidence` directly; they are not CLI flags. The production `capture-systemd` subcommand accepts only the exact canonical `--output` inserted by this wrapper and rejects any other destination. The binding `capture_systemd_evidence` callable executes the exact argument tuples in its body for `systemctl --user show` with the frozen property list and `journalctl --user -u` with JSON output and no pager.

Never invoke `sudo`; never request `Environment` or `show-environment`. Before publication, the exact parser in the binding code appendix must parse both files, require exactly three journal records, exact `USER_UNIT` and `USER_INVOCATION_ID` on every record, and start/started messages that bind the exact Python harness command, raw output namespace, and 16-character run prefix `4352d71ee8f4479c`. The show snapshot is retained and hashed but its unloaded `Result`, `NRestarts`, `ExecMainCode`, `ExecMainStatus`, and blank `InvocationID` values must never be promoted into exit or restart proof.

Write sorted, indented `capture.json` plus newline with exact schema `new02-systemd-correlation-v1`, classification `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF`, host, unit, invocation, run ID, raw namespace, executable path/realpath/hash map, journal record count, show/journal SHA-256, `start_correlated=true`, `exit_proven=false`, and `restart_history_proven=false`. Hash the exact unfiltered bytes produced by the two commands, not a parsed/re-serialized substitute.

Atomic evidence publication is owned entirely by Python: record the destination parent’s original mode; temporarily add owner-write permission; create a same-parent temporary directory; create each file mode `0444`; flush and `fsync` every file; `fsync` and chmod the directory `0555`; rename it to the absent destination; `fsync` the parent; and restore the exact parent mode in `finally`. A post-rename durability failure removes the complete new directory and fsyncs the parent. The wrapper performs no chmod or cleanup.

- [ ] **Step 4: Implement systemd evidence validation**

`verify_systemd_evidence(path)` must require exactly the three files, modes `0444`/`0555`, their capture.json hashes, exact identifiers, exact three-record start correlation, safe-field/secret scan, and explicit false exit/restart proof booleans. A blank show `InvocationID` is retained only as a non-probative unloaded-unit fact; the three journal `USER_INVOCATION_ID` values provide start correlation. `_SYSTEMD_UNIT` must not be used as the user-unit key.

- [ ] **Step 5: Run tests and capture on `arcana-devs`**

```bash
shellcheck -S warning \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh
/usr/bin/bash "$PWD/documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh"
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
```

Expected: shellcheck exit `0`; capture exit `0` and creates three read-only files; all systemd tests `ok`, exit `0`. If the exact journal records are no longer readable, stop with `SYSTEMD_EVIDENCE_UNAVAILABLE`; do not fabricate or relax the evidence.

Regenerate the final bytes to be committed. The build verdict is explicitly untrusted until `SHA256SUMS` exists as a reviewed Git blob:

```bash
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  build \
  --repository "$(git rev-parse --show-toplevel)" \
  --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z \
  --systemd-mode correlated \
  --systemd-evidence documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated \
  --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 \
  --replace
```

Expected: exit `0` with `NEW02_RESULT_BUILD=PASS_UNTRUSTED`; canonical sentinels are unchanged and only the supplemental layer reports `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF`. Trusted verification occurs only after Step 6 commits the ledger.

- [ ] **Step 6: Review the generated ledger, commit it, then verify the committed blob**

Before `git add`, a distinct findings-only reviewer compares the generated path set and bytes against this plan and records `APPROVE` or findings. Resolve findings and rebuild before continuing. Then run:

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py
git commit -m "docs: bind correlated NEW-02 systemd evidence"
trusted_revision="$(git rev-parse HEAD)"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  verify --repository "$(git rev-parse --show-toplevel)" \
  --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 \
  --trusted-revision "$trusted_revision"
```

Expected: the commit succeeds, then trusted verification reads `SHA256SUMS` from that exact commit and exits `0`. Any amendment requires recomputing `trusted_revision` and rerunning verification.

### Task 7: Run real-publication RED/GREEN mutations and deterministic review gates

**Files:**
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py`
- Modify: `documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py`

- [ ] **Step 1: Add bounded real-publication acceptance and mutation helpers**

Use the immutable raw path exactly:

```python
REAL_RAW = Path(
    "/home/dev/cubr-new02-canonical-runs/"
    "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
)
```

The positive test skips only when that external publication is absent; it may not convert absence into PASS. Real mutations operate in a temporary copy or on one bounded copied cell plus a synthesized sealed envelope; they never chmod or write the canonical raw root. Cover every mutation code listed in Tasks 1-3 and 6, including post-hoc `selection`, `GO`, aggregate, ceiling, or fraction changes in the derived package.

Fixed-production-policy coverage is mandatory and may not substitute a synthetic policy. `test_real_tree_fixed_policy_passes` calls the full `verify_raw_publication(REAL_RAW, FROZEN_POLICY)`, asserts all 243 returned observations are bound in frozen order, and checks every row's `relative_path == cell.entry.relative_path` while its external input artifact remains `cell.entry.source_operand`. It also asserts manifest status `STAGED`, marker status `COMPLETE`, all four top hashes, 974 manifest entries, and absent exact `.VOID.jsonl` sibling. The exact body is:

```python
def test_real_tree_fixed_policy_passes(self) -> None:
    if not REAL_RAW.is_dir():
        self.skipTest("NO-TEST-ENV: external immutable NEW-02 publication absent")
    evidence = verify_raw_publication(REAL_RAW, FROZEN_POLICY)
    self.assertEqual(len(evidence.observations), 243)
    self.assertEqual(
        [row["cell"] for row in evidence.observations],
        [cell.identifier for cell in FROZEN_POLICY.cells],
    )
    for row, cell in zip(evidence.observations, FROZEN_POLICY.cells, strict=True):
        self.assertEqual(row["relative_path"], cell.entry.relative_path)
        self.assertEqual(row["artifacts"]["input"]["relative_path"], cell.entry.source_operand)
    self.assertEqual(evidence.manifest["status"], "STAGED")
    self.assertEqual(load_json(REAL_RAW / "COMPLETE", COMPLETE_KEYS,
                               "COMPLETE_SCHEMA_MISMATCH")["status"], "COMPLETE")
    self.assertEqual(len(evidence.manifest["entries"]), 974)
    self.assertFalse(os.path.lexists(REAL_RAW.parent / f"{REAL_RAW.name}.VOID.jsonl"))
    for name, digest in FROZEN_POLICY.top_hashes.items():
        self.assertEqual(sha256_file(REAL_RAW / name), digest)
```

Four separate tests copy only one real top-level file into a temporary path, mutate one byte, and call `verify_fixed_top_file(name, path)` with `FROZEN_POLICY`; expected codes are `TOP_COMPLETE_HASH_MISMATCH`, `TOP_MANIFEST_HASH_MISMATCH`, `TOP_OBSERVATIONS_HASH_MISMATCH`, and `TOP_PROVENANCE_HASH_MISMATCH`.

Package mutations must include: change a derived file without changing `SHA256SUMS` -> `PACKAGE_HASH_MISMATCH`; change a derived file and rehash `SHA256SUMS` -> `TRUSTED_LEDGER_MISMATCH`; change a supplemental file and rehash `SHA256SUMS` -> `TRUSTED_LEDGER_MISMATCH`; correlated status with missing supplemental file -> `SUPPLEMENTAL_EVIDENCE_REQUIRED`; supplemental hash mutation -> `SUPPLEMENTAL_EVIDENCE_HASH_MISMATCH`; canonical systemd sentinel mutation -> `CANONICAL_SYSTEMD_SENTINEL_MISMATCH`.

- [ ] **Step 2: Run the complete suite**

```bash
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py
```

Expected: exit `0`; positive real-publication test reports `ok` on `arcana-devs`; every mutation is a passing test because the validator returns the exact expected RED code.

- [ ] **Step 3: Run the exact full historical command**

```bash
git fetch origin main --prune
local_main="$(git rev-parse --verify refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
test -n "$remote_main"
test "$local_main" = "$remote_main"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  validate \
  --repository "$(git rev-parse --show-toplevel)" \
  --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z \
  --systemd-evidence documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated
```

Expected final output:

```text
CAPTURE_STATUS=COMPLETE
HISTORICAL_VALIDATION_STATUS=PASS
SCIENTIFIC_CHARACTERIZATION=CHARACTERIZED_NO_SELECT
PRODUCT_SELECTION_STATUS=NOT_ISSUED
SYSTEMD_CORRELATION_STATUS=CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF
NEW02_HISTORICAL_VALIDATION=PASS cells=243 run_id=4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba
```

- [ ] **Step 4: Rebuild twice and prove no source mutation**

```bash
before="$(git status --porcelain=v1)"
tmp_one="$(mktemp -d)"
tmp_two="$(mktemp -d)"
tmp_unavailable="$(mktemp -d)"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  build \
  --repository "$(git rev-parse --show-toplevel)" \
  --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z \
  --systemd-evidence documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated \
  --systemd-mode correlated --package "$tmp_one/package"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  build \
  --repository "$(git rev-parse --show-toplevel)" \
  --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z \
  --systemd-evidence documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated \
  --systemd-mode correlated --package "$tmp_two/package"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  build --repository "$(git rev-parse --show-toplevel)" \
  --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z \
  --systemd-mode unavailable --package "$tmp_unavailable/package"
diff -ruN "$tmp_one/package" "$tmp_two/package"
test ! -e "$tmp_unavailable/package/systemd-correlated"
test "$(wc -l < "$tmp_unavailable/package/SHA256SUMS")" -eq 5
test "$before" = "$(git status --porcelain=v1)"
git diff --exit-code 708cda945a285526610371d812e4f54725eb6baf -- \
  documentation/ephemeral/research/new02_oracle_grid.py \
  documentation/ephemeral/research/test_new02_oracle_grid.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md
```

Expected: all three build commands exit `0` with `PASS_UNTRUSTED`; correlated outputs are byte-identical, unavailable output has no supplemental directory and exactly five ledger rows, status snapshot is unchanged, and immutable-source diff exits `0`. None of these pre-commit builds is release verification.

- [ ] **Step 5: Run security and syntax gates**

```bash
python3 -m py_compile \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py
python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py
shellcheck -S warning \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh
gitleaks detect --no-git --source \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810
rg -n -i '(authorization:|bearer[[:space:]]+[a-z0-9._-]+|api[_-]?key|password=|BEGIN (RSA |OPENSSH )?PRIVATE KEY)' \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated
```

Expected: compile, stdlib AST security test, shellcheck, and gitleaks exit `0`; evidence-only regex scan exit `1` with no matches.

- [ ] **Step 6: Commit test hardening if Step 1 changed tests**

```bash
git add documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv
git commit -m "test: exhaust NEW-02 historical mutation gates"
```

### Task 8: Independent review, protected PR, and exact resulting-main proof

**Files:**
- Review all owned paths listed in the File map.
- Do not modify the three immutable capture-source paths.

- [ ] **Step 1: Obtain a distinct findings-only review**

Give an independent reviewer the mandate, this plan, the branch diff, and exact commands. Require explicit findings on: no current-main equality-to-execution bug; no old `repo_root` dereference; no capture-tool execution; exhaustive raw path/mode/hash validation; stored-output claim wording; Git object pins; systemd safe-field/secret scan; canonical sentinel preservation; five status layers; mutation completeness; deterministic rebuild.

Expected: a recorded `APPROVE` or concrete findings. Fix every finding and rerun Tasks 7.2-7.5 before PR creation.

- [ ] **Step 2: Re-fetch and confirm exact pre-push provenance**

```bash
git fetch origin main --prune
local_main="$(git rev-parse --verify refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
test -n "$remote_main"
test "$local_main" = "$remote_main"
git merge-base --is-ancestor 708cda945a285526610371d812e4f54725eb6baf "$local_main"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
```

Expected: all checks exit `0`; only owned changes are present and committed.

- [ ] **Step 3: Push a feature branch and open a protected pull request**

```bash
branch="$(git branch --show-current)"
test -n "$branch"
test "$branch" != main
git push -u origin "$branch"
pr_body="$(mktemp)"
head_sha="$(git rev-parse HEAD)"
printf '%s\n' \
  '## Provenance' \
  '- Execution commit: `708cda945a285526610371d812e4f54725eb6baf`' \
  "- Proposed branch head: \`$head_sha\`" \
  '- The current main may be newer; the execution commit is authenticated as its ancestor.' \
  '' \
  '## Separated outcomes' \
  '- Canonical capture: `COMPLETE`.' \
  '- Historical validation: `PASS` over immutable stored bytes.' \
  '- Scientific characterization: `CHARACTERIZED_NO_SELECT`.' \
  '- Product selection: `NOT_ISSUED`.' \
  '- Supplemental systemd: `CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF`.' \
  '- Canonical systemd sentinels remain `NOT_RECORDED_BY_CANONICAL_HARNESS`.' \
  '' \
  '## Tests run on this exact head' \
  '- `python3 -m unittest -v documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py`' \
  '- `shellcheck -S warning documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh`' \
  '- `python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py validate --repository "$PWD" --raw-run /home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z --systemd-evidence documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated`' \
  "- \`python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py verify --repository \"$PWD\" --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 --trusted-revision $head_sha\`" \
  '' \
  '## Raw-proof boundary' \
  '- The external 1.7 GiB immutable raw publication passed locally on `arcana-devs`.' \
  '- CI covers the complete synthetic fixture, mutation contracts, and package verification; it does not contain or independently validate that external raw publication.' \
  > "$pr_body"
for required in \
  '708cda945a285526610371d812e4f54725eb6baf' \
  "$head_sha" \
  'CHARACTERIZED_NO_SELECT' \
  'NOT_ISSUED' \
  'CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF' \
  'python3 -m unittest -v' \
  'verify_new02_historical.py validate' \
  'verify_new02_results.py verify' \
  'external 1.7 GiB immutable raw publication'; do
  rg -F -- "$required" "$pr_body" >/dev/null
done
gh pr create --base main --head "$branch" \
  --title "fix: authenticate NEW-02 historical results" \
  --body-file "$pr_body"
pr_number="$(gh pr view --json number --jq .number)"
remote_body="$(mktemp)"
gh pr view "$pr_number" --json body --jq -r '.body' > "$remote_body"
cmp "$pr_body" "$remote_body"
```

The PR body must separate code, raw local proof, correlated systemd proof, and no-selection scientific status. It must list exact execution SHA, branch-head SHA, test commands, and the fact that the 1.7 GiB raw publication is external to CI. Do not self-approve, bypass protection, or claim external raw validation from synthetic CI tests.

- [ ] **Step 4: Require exact-head CI and independent approval before merge**

```bash
git fetch origin main --prune
head_sha="$(git rev-parse HEAD)"
pr_number="$(gh pr view --json number --jq .number)"
base_sha="$(git rev-parse refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
repo_nwo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
viewer="$(gh api user --jq .login)"
test -n "$pr_number" && test "$base_sha" = "$remote_main"
test "$(git merge-base "$head_sha" "$base_sha")" = "$base_sha"
test "$head_sha" = "$(gh pr view "$pr_number" --json headRefOid --jq .headRefOid)"
gh pr checks --watch --fail-fast "$pr_number"
test "$(gh pr view "$pr_number" --json reviewDecision --jq .reviewDecision)" = APPROVED
test "$(gh pr view "$pr_number" --json state --jq .state)" = OPEN
independent_reviewers="$(gh api --paginate "repos/$repo_nwo/pulls/$pr_number/reviews" \
  --jq ".[] | select(.state == \"APPROVED\" and .commit_id == \"$head_sha\") | .user.login" \
  | awk -v viewer="$viewer" '$0 != viewer' | sort -u)"
test -n "$independent_reviewers"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  verify --repository "$(git rev-parse --show-toplevel)" \
  --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 \
  --trusted-revision "$head_sha"
reviewed_paths="$(mktemp)"
git diff --name-only "$base_sha" "$head_sha" | LC_ALL=C sort -u > "$reviewed_paths"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
```

Expected: every required check terminal-success for the exact `head_sha`; independent approval present. If the branch is rebased or amended, discard old check evidence and repeat this step.

- [ ] **Step 5: Merge through the protected PR path and verify resulting main**

After the exact-head checks and approval above, execute the protected merge and verify its terminal result:

```bash
git fetch origin main --prune
head_sha="$(git rev-parse HEAD)"
pr_number="$(gh pr view --json number --jq .number)"
base_sha="$(git rev-parse refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
repo_nwo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
viewer="$(gh api user --jq .login)"
test -n "$head_sha" && test -n "$pr_number" && test -n "$base_sha" && test -n "$remote_main"
test "$base_sha" = "$remote_main"
test "$(git merge-base "$head_sha" "$base_sha")" = "$base_sha"
test "$head_sha" = "$(gh pr view "$pr_number" --json headRefOid --jq .headRefOid)"
test "$(gh pr view "$pr_number" --json state --jq .state)" = OPEN
gh pr checks --watch --fail-fast "$pr_number"
test -z "$(gh pr checks "$pr_number" --json state --jq \
  '.[] | select(.state != "SUCCESS" and .state != "SKIPPED" and .state != "NEUTRAL") | .state')"
test "$(gh pr view "$pr_number" --json reviewDecision --jq .reviewDecision)" = APPROVED
independent_reviewers="$(gh api --paginate "repos/$repo_nwo/pulls/$pr_number/reviews" \
  --jq ".[] | select(.state == \"APPROVED\" and .commit_id == \"$head_sha\") | .user.login" \
  | awk -v viewer="$viewer" '$0 != viewer' | sort -u)"
test -n "$independent_reviewers"
remote_body="$(mktemp)"
gh pr view "$pr_number" --json body --jq -r '.body' > "$remote_body"
for required in \
  '708cda945a285526610371d812e4f54725eb6baf' \
  "$head_sha" \
  'CHARACTERIZED_NO_SELECT' \
  'NOT_ISSUED' \
  'CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF' \
  'python3 -m unittest -v' \
  'shellcheck -S warning' \
  'verify_new02_historical.py validate' \
  'verify_new02_results.py verify' \
  'external 1.7 GiB immutable raw publication' \
  'CI covers the complete synthetic fixture'; do
  rg -F -- "$required" "$remote_body" >/dev/null
done
reviewed_paths="$(mktemp)"
git diff --name-only "$base_sha" "$head_sha" | LC_ALL=C sort -u > "$reviewed_paths"
expected_paths="$(mktemp)"
printf '%s\n' \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/README.md \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/SHA256SUMS \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/capture_new02_systemd_evidence.sh \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/effects.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/provenance.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/results.tsv \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/summary.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/capture.json \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/journalctl-user-unit.jsonl \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/systemd-correlated/systemctl-show.txt \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  | LC_ALL=C sort -u > "$expected_paths"
cmp "$expected_paths" "$reviewed_paths"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  verify --repository "$(git rev-parse --show-toplevel)" \
  --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 \
  --trusted-revision "$head_sha"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git rev-parse refs/remotes/origin/main)" = "$base_sha"
git fetch origin main --prune
head_sha="$(git rev-parse HEAD)"
pr_number="$(gh pr view --json number --jq .number)"
base_sha="$(git rev-parse refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
repo_nwo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
viewer="$(gh api user --jq .login)"
test -n "$head_sha" && test -n "$pr_number" && test "$base_sha" = "$remote_main"
test "$(git merge-base "$head_sha" "$base_sha")" = "$base_sha"
test "$head_sha" = "$(gh pr view "$pr_number" --json headRefOid --jq .headRefOid)"
test "$(gh pr view "$pr_number" --json reviewDecision --jq .reviewDecision)" = APPROVED
test "$(gh pr view "$pr_number" --json state --jq .state)" = OPEN
test -z "$(gh pr checks "$pr_number" --json state --jq \
  '.[] | select(.state != "SUCCESS" and .state != "SKIPPED" and .state != "NEUTRAL") | .state')"
independent_reviewers="$(gh api --paginate "repos/$repo_nwo/pulls/$pr_number/reviews" \
  --jq ".[] | select(.state == \"APPROVED\" and .commit_id == \"$head_sha\") | .user.login" \
  | awk -v viewer="$viewer" '$0 != viewer' | sort -u)"
test -n "$independent_reviewers"
reviewed_paths="$(mktemp)"
git diff --name-only "$base_sha" "$head_sha" | LC_ALL=C sort -u > "$reviewed_paths"
cmp "$expected_paths" "$reviewed_paths"
python3 documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py \
  verify --repository "$(git rev-parse --show-toplevel)" \
  --package documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810 \
  --trusted-revision "$head_sha"
remote_body="$(mktemp)"
gh pr view "$pr_number" --json body --jq -r '.body' > "$remote_body"
for required in "$head_sha" 'python3 -m unittest -v' 'shellcheck -S warning' \
  'verify_new02_historical.py validate' 'verify_new02_results.py verify' \
  'CHARACTERIZED_NO_SELECT' 'NOT_ISSUED' \
  'CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF' \
  'external 1.7 GiB immutable raw publication'; do
  rg -F -- "$required" "$remote_body" >/dev/null
done
test -z "$(git status --porcelain=v1 --untracked-files=all)"
gh pr merge "$pr_number" --squash --delete-branch=false
test "$(gh pr view "$pr_number" --json state --jq .state)" = MERGED
merge_sha="$(gh pr view "$pr_number" --json mergeCommit --jq .mergeCommit.oid)"
test -n "$merge_sha"
git fetch origin main --prune
result_main="$(git rev-parse refs/remotes/origin/main)"
remote_main="$(git ls-remote origin refs/heads/main | awk 'NR == 1 { print $1 }')"
test "$result_main" = "$remote_main"
test "$result_main" = "$merge_sha"
git merge-base --is-ancestor 708cda945a285526610371d812e4f54725eb6baf "$result_main"
result_paths="$(mktemp)"
git diff --name-only "${result_main}^" "$result_main" | LC_ALL=C sort -u > "$result_paths"
cmp "$reviewed_paths" "$result_paths"
while IFS= read -r path; do
  test "$(git rev-parse "$head_sha:$path")" = "$(git rev-parse "$result_main:$path")"
done < "$reviewed_paths"
for path in \
  documentation/ephemeral/research/new02_oracle_grid.py \
  documentation/ephemeral/research/test_new02_oracle_grid.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md; do
  test "$(git rev-parse "708cda945a285526610371d812e4f54725eb6baf:$path")" = \
       "$(git rev-parse "$result_main:$path")"
done
verify_worktree="$(mktemp -d)"
rmdir "$verify_worktree"
git worktree add --detach "$verify_worktree" "$result_main"
test -z "$(git -C "$verify_worktree" status --porcelain=v1 --untracked-files=all)"
/usr/bin/python3 "$verify_worktree/documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/verify_new02_results.py" \
  verify --repository "$verify_worktree" \
  --package "$verify_worktree/documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810" \
  --trusted-revision "$result_main"
(cd "$verify_worktree" && /usr/bin/python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_historical.py \
  documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-RESULTS-20260810/test_verify_new02_results.py)
git worktree remove "$verify_worktree"
```

The path-set comparisons and per-path blob loop are mandatory squash-merge proof; ancestry of PR head is not expected. Expected: exact local/remote/merge-SHA equality, exact reviewed/result path-set and blob equality, execution ancestor gate `0`, immutable capture sources unchanged, committed-ledger verification PASS at resulting main, and both suites green in a clean detached worktree.

No tag, deployment, archive closure, product-selection claim, or scientific GO is part of this repair.

---

## Binding implementation contracts

The following callables, types, regular expressions, error codes, and test-discovery contract are normative. Implementation tasks may split them across the exact files in the File map, but may not replace them with prose, dynamic policy loaded from evidence, a capture-harness import, or a weaker interface.

### Historical validator: types, policy, and errors

```python
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence

ERROR_CODES = frozenset({
    "REPOSITORY_REMOTE_TRACKING_MISMATCH", "REPOSITORY_REMOTE_RESPONSE_INVALID",
    "EXECUTION_NOT_ANCESTOR", "EXECUTION_COMMIT_MISSING",
    "EXECUTION_OBJECT_TYPE_MISMATCH", "EXECUTION_TREE_MISMATCH",
    "SOURCE_BLOB_MISSING", "SOURCE_BLOB_TYPE_MISMATCH", "SOURCE_BLOB_ID_MISMATCH",
    "SOURCE_BLOB_SIZE_MISMATCH", "SOURCE_BLOB_SHA256_MISMATCH",
    "RAW_NAMESPACE_MISMATCH", "RAW_VOID_SIBLING_PRESENT", "RAW_SPECIAL_FILE",
    "RAW_LINK_COUNT_MISMATCH", "RAW_MODE_MISMATCH", "RAW_PATH_SET_MISMATCH",
    "MANIFEST_SCHEMA_MISMATCH", "MANIFEST_STATUS_MISMATCH",
    "MANIFEST_DUPLICATE_PATH", "MANIFEST_ENTRY_SET_MISMATCH", "MANIFEST_ENTRY_ORDER_MISMATCH",
    "MANIFEST_SIZE_MISMATCH", "MANIFEST_HASH_MISMATCH",
    "COMPLETE_SCHEMA_MISMATCH", "COMPLETE_STATUS_MISMATCH",
    "COMPLETE_ENVELOPE_MISMATCH", "COMPLETE_MANIFEST_MISMATCH",
    "TOP_COMPLETE_HASH_MISMATCH", "TOP_MANIFEST_HASH_MISMATCH",
    "TOP_OBSERVATIONS_HASH_MISMATCH", "TOP_PROVENANCE_HASH_MISMATCH",
    "PROVENANCE_SCHEMA_MISMATCH", "PROVENANCE_RUN_ID_MISMATCH",
    "PROVENANCE_CODE_SHA_MISMATCH", "PROVENANCE_REPOSITORY_MISMATCH",
    "PROVENANCE_ENVIRONMENT_MISMATCH", "INVENTORY_IDENTITY_MISMATCH",
    "GRID_IDENTITY_MISMATCH", "PREREGISTRATION_IDENTITY_MISMATCH",
    "HARNESS_IDENTITY_MISMATCH", "HARNESS_TEST_IDENTITY_MISMATCH",
    "TOOL_IDENTITY_MISMATCH", "OBSERVATION_GRID_MISMATCH",
    "OBSERVATION_SCHEMA_MISMATCH", "COMMAND_ARRAY_MISMATCH",
    "ARCHIVE_SIZE_INVALID", "ARTIFACT_IDENTITY_MISMATCH",
    "DECODED_IDENTITY_MISMATCH", "ROUND_TRIP_CLAIM_MISMATCH",
    "LISTING_SEMANTICS_MISMATCH", "TIMING_GRAMMAR_MISMATCH",
    "CELL_RETURN_CODE_MISMATCH", "CELL_ERROR_MARKER",
    "SYSTEMD_TOOL_IDENTITY_MISMATCH", "SYSTEMD_SHOW_HASH_MISMATCH",
    "SYSTEMD_JOURNAL_HASH_MISMATCH", "SYSTEMD_USER_UNIT_MISMATCH",
    "SYSTEMD_INVOCATION_MISMATCH", "SYSTEMD_COMMAND_MISMATCH",
    "SYSTEMD_NAMESPACE_MISMATCH", "SYSTEMD_RUNTIME_DIR_INVALID",
    "SYSTEMD_SHOW_SCHEMA_MISMATCH", "SYSTEMD_JOURNAL_SCHEMA_MISMATCH", "SYSTEMD_UNSAFE_FIELD",
    "SYSTEMD_SECRET_SCAN_FAILED", "SYSTEMD_OVERCLAIM_REJECTED",
    "SYSTEMD_EVIDENCE_UNAVAILABLE", "SYSTEMD_EVIDENCE_PATH_SET_MISMATCH",
    "SUPPLEMENTAL_EVIDENCE_REQUIRED", "SUPPLEMENTAL_EVIDENCE_HASH_MISMATCH",
    "CANONICAL_SYSTEMD_SENTINEL_MISMATCH", "PACKAGE_HASH_MISMATCH",
    "PACKAGE_LEDGER_INVALID", "TRUSTED_LEDGER_MISMATCH",
    "ATOMIC_DESTINATION_EXISTS", "ATOMIC_PUBLICATION_FAILED",
    "VALIDATION_DATA_ERROR", "VALIDATION_SUBPROCESS_ERROR",
    "RESULT_PACKAGE_INVALID",
})

class HistoricalValidationError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unregistered validation code: {code}")
        super().__init__(detail)
        self.code = code
        self.detail = detail

def fail(code: str, detail: str) -> None:
    raise HistoricalValidationError(code, detail)

@dataclass(frozen=True)
class InventoryEntry:
    cohort: str
    name: str
    relative_path: str
    size_bytes: int
    sha256: str

    @property
    def source_operand(self) -> str:
        return f"{self.cohort}/{self.relative_path}"

@dataclass(frozen=True)
class Cell:
    entry: InventoryEntry
    order: int
    memory_mib: int

    @property
    def identifier(self) -> str:
        return (f"{self.entry.cohort}/{self.entry.name}/"
                f"order={self.order}/mem={self.memory_mib}MiB")

    @property
    def slug(self) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.entry.name)
        return f"{self.entry.cohort}-{safe}-o{self.order}-m{self.memory_mib}"

@dataclass(frozen=True)
class FrozenPolicy:
    inventory: tuple[InventoryEntry, ...]
    orders: tuple[int, ...]
    memory_mib: tuple[int, ...]
    cpu_set: str
    top_hashes: Mapping[str, str]

    @property
    def cells(self) -> tuple[Cell, ...]:
        return tuple(Cell(e, o, m) for e in self.inventory
                     for o in self.orders for m in self.memory_mib)

@dataclass(frozen=True)
class RawEvidence:
    root: Path
    provenance: Mapping[str, Any]
    observations: tuple[Mapping[str, Any], ...]
    manifest: Mapping[str, Any]

@dataclass(frozen=True)
class RepositoryEvidence:
    current_main: str
    execution_commit: str
    execution_tree: str
    source_blobs: Mapping[str, str]

FROZEN_INVENTORY = tuple(InventoryEntry(*row) for row in (
    ("world", "dickens", "silesia/dickens", 10192446, "b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a"),
    ("world", "reymont", "silesia/reymont", 6627202, "0eac0114a3dfe6e2ee1f345a0f79d653cb26c3bc9f0ed79238af4933422b7578"),
    ("world", "webster", "silesia/webster", 41458703, "6a68f69b26daf09f9dd84f7470368553194a0b294fcfa80f1604efb11143a383"),
    ("world", "xml", "silesia/xml", 5345280, "0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c"),
    ("world", "enwik8", "enwik8/enwik8", 100000000, "2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8"),
    ("world", "alice29.txt", "canterbury/alice29.txt", 152089, "7467306ee0feed4971260f3c87421154a05be571d944e9cb021a5713700c38f0"),
    ("world", "asyoulik.txt", "canterbury/asyoulik.txt", 125179, "eaa3526fe53859f34ecdf255712f9ecf0b2c903451d4755b2edaa2e2599cb0fc"),
    ("world", "cp.html", "canterbury/cp.html", 24603, "e0cd21cef5b6c4069461e949be100080c3ce887de6f1dd8626c480528efaaf61"),
    ("world", "lcet10.txt", "canterbury/lcet10.txt", 426754, "5314ba1dbb03f471df88bec6cd120a938ef60d0fd3511c5c1dce61bf7463245f"),
    ("world", "plrabn12.txt", "canterbury/plrabn12.txt", 481861, "07e2e0b461af78c7c647cb53dab39de560198e16f799b4516eccf0fbd69f764c"),
    ("world", "xargs.1", "canterbury/xargs.1", 4227, "c58aeb5d2d1e12751d47e7412b45784405fc30a5671b03d480fa05776e183619"),
    ("tuned", "binary_mixed.bin", "binary_mixed.bin", 8192, "669a93863d0fab21a599f70df7d8bc9ec98c9c933f60be5112612157622672d6"),
    ("tuned", "block_bound_runs.bin", "block_bound_runs.bin", 65536, "abcb2d5a7ea6c1e74f753c2a775998379568e79a13358cb52dfb48a956c040d5"),
    ("tuned", "both_sparse_16.bin", "both_sparse_16.bin", 16, "84c92eca52cc2721fbd3a0e285ecf16596756e1e7513bf4f4e314c0b7b9259e3"),
    ("tuned", "both_sparse_24.bin", "both_sparse_24.bin", 24, "ba3a1f0d984b45025c9a8ade0740d33355f430e48864bc7d83f26af579a2e510"),
    ("tuned", "dense.bin", "dense.bin", 4096, "a4ecb8ba6554b63d398076f1f00545c935d7b73b4e21988666185d6371c65c27"),
    ("tuned", "log_like.bin", "log_like.bin", 16384, "ac4ef4845750390362797bc33af63b3a3d480f827a8b7ff54090ce1c89a9543d"),
    ("tuned", "random_high.bin", "random_high.bin", 4096, "0e232e8ae9db07cc67194aa713d7a287876fec886ded19cffddb732a1094b415"),
    ("tuned", "sparse_clustered.bin", "sparse_clustered.bin", 2048, "d11533a77218a34e56285bf0df004ac06e845319e1ca07cb8d65f0911d75f7ce"),
    ("tuned", "sparse_small.bin", "sparse_small.bin", 256, "8c23d37b2230be9754c446b6cdef385fb4eb7dcac874905fcbb2e25b6f05672c"),
    ("tuned", "text.bin", "text.bin", 16384, "0160b7a1b4311fa6b273b63125f8cff4603205d8dc7fcc7cf9186691570c5415"),
    ("holdout", "rust_src.rs", "rust_src.rs", 26805, "27230e0c7ad1eb2b163b320debffbc4f5660d45ec931cdd3ffbe5cf3d7b13eb0"),
    ("holdout", "c_header.h", "c_header.h", 34649, "b4f6709d12c8493e2a42f740845abe2994deb27fc78fb85fcaa6e27228a87d62"),
    ("holdout", "config.json", "config.json", 66294, "259f831b18f3d1aecc130839ca075541b199f855570fb27a2f044309d2b7dc94"),
    ("holdout", "prose.txt", "prose.txt", 17774, "9026c001530a657fb8910a1d990325d07e19443ee898a65ae1b3ea3d2d9c9bf8"),
    ("holdout", "data.csv", "data.csv", 17029, "c9b1e70e718f33f7cd6433b98f123fcc2914a24d1974e1bcf53d73a2806b2860"),
    ("holdout", "exe.bin", "exe.bin", 39384, "a63158e6e5bce20616425f5d61e5bd7374bb5bccf15bbb93ae2e40238248f179"),
))

FROZEN_POLICY = FrozenPolicy(
    inventory=FROZEN_INVENTORY,
    orders=(4, 6, 8), memory_mib=(16, 64, 256), cpu_set="0-15",
    top_hashes={
        "COMPLETE": "9db58ad5bfa01bfeaff2f46807d0645baa2e002cd1ed930585fcefb2ce177d06",
        "MANIFEST.json": "4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c",
        "observations.jsonl": "7622bb1eed1199f98c599cdad588340fcffc3df74b03eef32f37b16c4eabe75c",
        "provenance.json": "42caafdbcf13c37e3f7b6f57f62a1923c35c470bf2c22bda04d645b3f1b6fc6b",
    },
)

EXECUTION_COMMIT = "708cda945a285526610371d812e4f54725eb6baf"
EXECUTION_TREE = "9cdad69314f94e0cc0323b1dd6fb64d34c0f677b"
SOURCE_BLOBS = {
    "documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md":
        ("d96df7e3478a6ba52b737ef30dea63d68b0e01ac", 7651, "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093"),
    "documentation/ephemeral/research/new02_oracle_grid.py":
        ("3acaa4a5fc2b5622404f041a28575cbf9ad10bd5", 84669, "35c2f7eb7dc7f3ef5008136b7658607342273df36c8c9b13d3fdeda80f3143c5"),
    "documentation/ephemeral/research/test_new02_oracle_grid.py":
        ("ccf6613b13aa178eb1bb6a0896e5ea8b0276e10b", 58121, "35be4a2cdcf5f09487eddd542966c3435bedf40874e6b081fe282b6edb8eb005"),
}

class GitProbe:
    def run(self, repository: Path, arguments: Sequence[str], binary: bool = False) -> bytes | str:
        result = subprocess.run(("git", *arguments), cwd=repository, check=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            fail("EXECUTION_COMMIT_MISSING", f"git command failed: {' '.join(arguments)}")
        return result.stdout if binary else result.stdout.decode("utf-8").strip()

    def status(self, repository: Path, arguments: Sequence[str]) -> int:
        return subprocess.run(("git", *arguments), cwd=repository, check=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode

class FakeGitProbe(GitProbe):
    def __init__(self, local_main: str, remote_main: str, ancestor: bool,
                 overrides: Mapping[tuple[str, ...], bytes | str | int] | None = None) -> None:
        self.local_main = local_main
        self.remote_main = remote_main
        self.ancestor = ancestor
        self.overrides = dict(overrides or {})

    @classmethod
    def valid(cls) -> "FakeGitProbe":
        current = "b" * 40
        return cls(current, current, True)

    def run(self, repository: Path, arguments: Sequence[str], binary: bool = False) -> bytes | str:
        key = tuple(arguments)
        if key in self.overrides:
            value = self.overrides[key]
            if isinstance(value, int):
                fail("EXECUTION_COMMIT_MISSING", f"fake command failed: {key}")
            return value
        if key == ("rev-parse", "--verify", "refs/remotes/origin/main"):
            return self.local_main
        if key == ("ls-remote", "origin", "refs/heads/main"):
            return f"{self.remote_main}\trefs/heads/main"
        return super().run(repository, arguments, binary)

    def status(self, repository: Path, arguments: Sequence[str]) -> int:
        key = tuple(arguments)
        if key in self.overrides and isinstance(self.overrides[key], int):
            return int(self.overrides[key])
        if key[:2] == ("merge-base", "--is-ancestor"):
            return 0 if self.ancestor else 1
        return super().status(repository, arguments)

def verify_repository(repository: Path, probe: GitProbe | None = None) -> RepositoryEvidence:
    probe = probe or GitProbe()
    local_main = str(probe.run(repository, ("rev-parse", "--verify", "refs/remotes/origin/main")))
    remote_text = str(probe.run(repository, ("ls-remote", "origin", "refs/heads/main")))
    remote_rows = [line.split() for line in remote_text.splitlines() if line.strip()]
    if len(remote_rows) != 1 or len(remote_rows[0]) != 2 or remote_rows[0][1] != "refs/heads/main" \
            or re.fullmatch(r"[0-9a-f]{40}", remote_rows[0][0]) is None:
        fail("REPOSITORY_REMOTE_RESPONSE_INVALID", "ls-remote main response is not exact")
    if local_main != remote_rows[0][0]:
        fail("REPOSITORY_REMOTE_TRACKING_MISMATCH", "local origin/main differs from remote main")
    if probe.status(repository, ("merge-base", "--is-ancestor", EXECUTION_COMMIT, local_main)) != 0:
        fail("EXECUTION_NOT_ANCESTOR", "execution commit is not an ancestor of current main")
    if probe.status(repository, ("cat-file", "-e", f"{EXECUTION_COMMIT}^{{commit}}")) != 0:
        fail("EXECUTION_COMMIT_MISSING", "execution commit is unavailable")
    object_type = str(probe.run(repository, ("cat-file", "-t", EXECUTION_COMMIT)))
    if object_type != "commit":
        fail("EXECUTION_OBJECT_TYPE_MISMATCH", "execution object is not a commit")
    tree = str(probe.run(repository, ("rev-parse", f"{EXECUTION_COMMIT}^{{tree}}")))
    if tree != EXECUTION_TREE:
        fail("EXECUTION_TREE_MISMATCH", "execution tree mismatch")
    verified: dict[str, str] = {}
    for path, (blob_id, size, digest) in SOURCE_BLOBS.items():
        spec = f"{EXECUTION_COMMIT}:{path}"
        if probe.status(repository, ("cat-file", "-e", spec)) != 0:
            fail("SOURCE_BLOB_MISSING", f"source blob missing: {path}")
        if str(probe.run(repository, ("cat-file", "-t", spec))) != "blob":
            fail("SOURCE_BLOB_TYPE_MISMATCH", f"source object is not blob: {path}")
        if str(probe.run(repository, ("rev-parse", spec))) != blob_id:
            fail("SOURCE_BLOB_ID_MISMATCH", f"source blob ID mismatch: {path}")
        if int(str(probe.run(repository, ("cat-file", "-s", spec)))) != size:
            fail("SOURCE_BLOB_SIZE_MISMATCH", f"source blob size mismatch: {path}")
        payload = probe.run(repository, ("cat-file", "blob", spec), binary=True)
        if not isinstance(payload, bytes) or hashlib.sha256(payload).hexdigest() != digest:
            fail("SOURCE_BLOB_SHA256_MISMATCH", f"source blob SHA-256 mismatch: {path}")
        verified[path] = blob_id
    return RepositoryEvidence(local_main, EXECUTION_COMMIT, tree, verified)
```

### Historical validator: traversal and envelope callables

```python
RAW_BASENAME = "new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z"
RAW_NAMESPACE = f"/home/dev/cubr-new02-canonical-runs/{RAW_BASENAME}"
TOP_CODE = {
    "COMPLETE": "TOP_COMPLETE_HASH_MISMATCH",
    "MANIFEST.json": "TOP_MANIFEST_HASH_MISMATCH",
    "observations.jsonl": "TOP_OBSERVATIONS_HASH_MISMATCH",
    "provenance.json": "TOP_PROVENANCE_HASH_MISMATCH",
}
MANIFEST_KEYS = frozenset({"directories", "entries", "observation_count", "schema", "status"})
COMPLETE_KEYS = frozenset({"final_namespace", "manifest_sha256", "observation_count", "schema", "status"})

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify_fixed_top_file(name: str, path: Path,
                          policy: FrozenPolicy = FROZEN_POLICY) -> None:
    expected = policy.top_hashes.get(name)
    if expected is None or name not in TOP_CODE:
        raise ValueError(f"unknown top-level pin: {name}")
    if sha256_file(path) != expected:
        fail(TOP_CODE[name], f"fixed top-level hash mismatch: {name}")

def require_keys(value: Any, keys: frozenset[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        fail(code, "object has an inexact closed schema")
    return value

def load_json(path: Path, keys: frozenset[str], code: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"invalid JSON: {path.name}: {exc}")
    return require_keys(value, keys, code)

def checked_relative(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    pure = PurePosixPath(relative)
    if (pure.is_absolute() or not pure.parts or any(p in {"", ".", ".."} for p in pure.parts)
            or "\\" in relative):
        fail("RAW_PATH_SET_MISMATCH", f"unsafe relative path: {relative}")
    return relative

def walk_raw_tree(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        root_info = os.lstat(root)
    except OSError as exc:
        fail("RAW_SPECIAL_FILE", f"raw root unavailable: {exc}")
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        fail("RAW_SPECIAL_FILE", "raw root is not a real directory")
    if stat.S_IMODE(root_info.st_mode) != 0o555:
        fail("RAW_MODE_MISMATCH", "raw root mode is not 0555")
    directories: list[str] = [""]
    files: list[str] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError as exc:
            fail("RAW_SPECIAL_FILE", f"cannot scan raw tree: {exc}")
        for entry in entries:
            path = Path(entry.path)
            info = entry.stat(follow_symlinks=False)
            relative = checked_relative(root, path)
            if stat.S_ISDIR(info.st_mode):
                if stat.S_IMODE(info.st_mode) != 0o555:
                    fail("RAW_MODE_MISMATCH", f"directory not 0555: {relative}")
                directories.append(relative)
                stack.append(path)
            elif stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    fail("RAW_LINK_COUNT_MISMATCH", f"file link count is not one: {relative}")
                if stat.S_IMODE(info.st_mode) != 0o444:
                    fail("RAW_MODE_MISMATCH", f"file not 0444: {relative}")
                files.append(relative)
            else:
                fail("RAW_SPECIAL_FILE", f"special entry in raw tree: {relative}")
    return tuple(sorted(directories)), tuple(sorted(files))

def expected_raw_paths(policy: FrozenPolicy) -> tuple[set[str], set[str], set[str]]:
    cell_dirs = {f"cells/{cell.slug}" for cell in policy.cells}
    artifacts = {
        f"cells/{cell.slug}/{name}"
        for cell in policy.cells
        for name in ("payload.7z", "decoded.bin", "encode.time", "decode.time")
    }
    files = artifacts | {"COMPLETE", "MANIFEST.json", "observations.jsonl", "provenance.json"}
    manifest_entries = artifacts | {"observations.jsonl", "provenance.json"}
    return {"", "cells"} | cell_dirs, files, manifest_entries

def verify_raw_envelope(root: Path, policy: FrozenPolicy = FROZEN_POLICY) -> Mapping[str, Any]:
    if root.name != RAW_BASENAME:
        fail("RAW_NAMESPACE_MISMATCH", f"unexpected raw basename: {root.name}")
    void_sibling = root.parent / f"{root.name}.VOID.jsonl"
    if os.path.lexists(void_sibling):
        fail("RAW_VOID_SIBLING_PRESENT", f"VOID sibling exists: {void_sibling.name}")
    if policy is FROZEN_POLICY:
        for name in policy.top_hashes:
            verify_fixed_top_file(name, root / name, policy)
    actual_dirs, actual_files = walk_raw_tree(root)
    expected_dirs, expected_files, expected_entries = expected_raw_paths(policy)
    if set(actual_dirs) != expected_dirs or set(actual_files) != expected_files:
        fail("RAW_PATH_SET_MISMATCH", "raw path set is not exact 245-directory/976-file tree")
    manifest = load_json(root / "MANIFEST.json", MANIFEST_KEYS, "MANIFEST_SCHEMA_MISMATCH")
    if manifest["schema"] != "new02-ppmd-oracle-v1":
        fail("MANIFEST_SCHEMA_MISMATCH", "manifest schema mismatch")
    if manifest["status"] != "STAGED":
        fail("MANIFEST_STATUS_MISMATCH", "manifest status must be STAGED")
    if manifest["observation_count"] != len(policy.cells):
        fail("MANIFEST_SCHEMA_MISMATCH", "manifest observation count mismatch")
    if manifest["directories"] != sorted(expected_dirs - {""}):
        fail("MANIFEST_ENTRY_SET_MISMATCH", "manifest directory list mismatch")
    entries = manifest["entries"]
    if not isinstance(entries, list) or len(entries) != len(expected_entries):
        fail("MANIFEST_ENTRY_SET_MISMATCH", "manifest entry count mismatch")
    indexed: dict[str, Mapping[str, Any]] = {}
    for raw_entry in entries:
        entry = require_keys(raw_entry, frozenset({"path", "sha256", "size_bytes"}),
                             "MANIFEST_SCHEMA_MISMATCH")
        path_text = entry["path"]
        if not isinstance(path_text, str):
            fail("MANIFEST_SCHEMA_MISMATCH", "manifest path is not text")
        pure = PurePosixPath(path_text)
        if (pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts)
                or "\\" in path_text):
            fail("MANIFEST_SCHEMA_MISMATCH", f"unsafe manifest path: {path_text}")
        if path_text in indexed:
            fail("MANIFEST_DUPLICATE_PATH", f"duplicate manifest path: {path_text}")
        indexed[path_text] = entry
    if [entry["path"] for entry in entries] != sorted(entry["path"] for entry in entries):
        fail("MANIFEST_ENTRY_ORDER_MISMATCH", "manifest entries are not sorted by path")
    if set(indexed) != expected_entries:
        fail("MANIFEST_ENTRY_SET_MISMATCH", "manifest entry set mismatch")
    for relative, entry in indexed.items():
        path = root / relative
        if path.stat().st_size != entry["size_bytes"]:
            fail("MANIFEST_SIZE_MISMATCH", f"manifest size mismatch: {relative}")
        if sha256_file(path) != entry["sha256"]:
            fail("MANIFEST_HASH_MISMATCH", f"manifest hash mismatch: {relative}")
    complete = load_json(root / "COMPLETE", COMPLETE_KEYS, "COMPLETE_SCHEMA_MISMATCH")
    if complete["schema"] != "new02-ppmd-oracle-v1":
        fail("COMPLETE_SCHEMA_MISMATCH", "complete schema mismatch")
    if complete["status"] != "COMPLETE":
        fail("COMPLETE_STATUS_MISMATCH", "marker status must be COMPLETE")
    if (complete["final_namespace"] != RAW_NAMESPACE
            or complete["observation_count"] != len(policy.cells)):
        fail("COMPLETE_ENVELOPE_MISMATCH", "complete namespace/count mismatch")
    if complete["manifest_sha256"] != sha256_file(root / "MANIFEST.json"):
        fail("COMPLETE_MANIFEST_MISMATCH", "complete does not bind manifest bytes")
    return manifest
```

### Historical validator: timing, listing, commands, and observation semantics

```python
TIME_FIELD_PATTERNS = (
    ("Command being timed", re.compile(r'"[^\r\n]*"')),
    ("User time (seconds)", re.compile(r"[0-9]+(?:\.[0-9]+)?")),
    ("System time (seconds)", re.compile(r"[0-9]+(?:\.[0-9]+)?")),
    ("Percent of CPU this job got", re.compile(r"[0-9]+%")),
    ("Elapsed (wall clock) time (h:mm:ss or m:ss)",
     re.compile(r"(?:[0-9]+:[0-5]?[0-9]|[0-9]+:[0-5]?[0-9]:[0-5]?[0-9])(?:\.[0-9]+)?")),
    ("Average shared text size (kbytes)", re.compile(r"[0-9]+")),
    ("Average unshared data size (kbytes)", re.compile(r"[0-9]+")),
    ("Average stack size (kbytes)", re.compile(r"[0-9]+")),
    ("Average total size (kbytes)", re.compile(r"[0-9]+")),
    ("Maximum resident set size (kbytes)", re.compile(r"[0-9]+")),
    ("Average resident set size (kbytes)", re.compile(r"[0-9]+")),
    ("Major (requiring I/O) page faults", re.compile(r"[0-9]+")),
    ("Minor (reclaiming a frame) page faults", re.compile(r"[0-9]+")),
    ("Voluntary context switches", re.compile(r"[0-9]+")),
    ("Involuntary context switches", re.compile(r"[0-9]+")),
    ("Swaps", re.compile(r"[0-9]+")),
    ("File system inputs", re.compile(r"[0-9]+")),
    ("File system outputs", re.compile(r"[0-9]+")),
    ("Socket messages sent", re.compile(r"[0-9]+")),
    ("Socket messages received", re.compile(r"[0-9]+")),
    ("Signals delivered", re.compile(r"[0-9]+")),
    ("Page size (bytes)", re.compile(r"[0-9]+")),
    ("Exit status", re.compile(r"[0-9]+")),
)
ERROR_MARKER_RE = re.compile(r"(?:^|\b)(?:error|warning|failed|cannot)(?:\b|$)", re.I)

def parse_duration(value: str) -> Decimal:
    if re.fullmatch(r"[0-9]+:[0-5]?[0-9](?:\.[0-9]+)?", value):
        minutes, seconds = value.split(":")
        return Decimal(minutes) * 60 + Decimal(seconds)
    if re.fullmatch(r"[0-9]+:[0-5]?[0-9]:[0-5]?[0-9](?:\.[0-9]+)?", value):
        hours, minutes, seconds = value.split(":")
        return Decimal(hours) * 3600 + Decimal(minutes) * 60 + Decimal(seconds)
    fail("TIMING_GRAMMAR_MISMATCH", f"invalid duration: {value}")

def parse_gnu_time(text: str) -> tuple[Decimal, int]:
    if not text or "\r" in text or not text.endswith("\n"):
        fail("TIMING_GRAMMAR_MISMATCH", "time report framing mismatch")
    lines = text.splitlines()
    if len(lines) != len(TIME_FIELD_PATTERNS):
        fail("TIMING_GRAMMAR_MISMATCH", "time field count mismatch")
    values: dict[str, str] = {}
    for line, (field, pattern) in zip(lines, TIME_FIELD_PATTERNS, strict=True):
        prefix = f"\t{field}: "
        if not line.startswith(prefix):
            fail("TIMING_GRAMMAR_MISMATCH", f"time field order mismatch: {field}")
        value = line[len(prefix):]
        if field in values or pattern.fullmatch(value) is None:
            fail("TIMING_GRAMMAR_MISMATCH", f"time field grammar mismatch: {field}")
        values[field] = value
    if len(values) != len(TIME_FIELD_PATTERNS):
        fail("TIMING_GRAMMAR_MISMATCH", "time field count mismatch")
    elapsed = parse_duration(values["Elapsed (wall clock) time (h:mm:ss or m:ss)"])
    rss = int(values["Maximum resident set size (kbytes)"])
    if not elapsed.is_finite() or elapsed < 0 or rss < 0:
        fail("TIMING_GRAMMAR_MISMATCH", "time values are not finite/nonnegative")
    return elapsed, rss

def expected_memory_exponent(input_bytes: int, memory_mib: int) -> int:
    if input_bytes <= 0 or memory_mib <= 0 or memory_mib & (memory_mib - 1):
        fail("LISTING_SEMANTICS_MISMATCH", "invalid PPMd size/memory")
    requested = 20 + memory_mib.bit_length() - 1
    capped = max(16, (input_bytes * 16 - 1).bit_length())
    return min(requested, capped)

def parse_listing(text: str, cell: Cell) -> tuple[str, tuple[str, ...]]:
    if ERROR_MARKER_RE.search(text):
        fail("CELL_ERROR_MARKER", f"listing error marker: {cell.identifier}")
    lines = text.splitlines()
    if len([line for line in lines if re.fullmatch(r"\s*Method\s*=\s*PPMD\s*", line)]) != 1:
        fail("LISTING_SEMANTICS_MISMATCH", "archive-level method is not exactly PPMD")
    separators = [i for i, line in enumerate(lines) if line.strip() == "----------"]
    if len(separators) != 1:
        fail("LISTING_SEMANTICS_MISMATCH", "member boundary count mismatch")
    member = lines[separators[0] + 1:]
    def one(key: str) -> str:
        expression = re.compile(rf"\s*{re.escape(key)}\s*=\s*(.*?)\s*")
        values = [match.group(1) for line in member if (match := expression.fullmatch(line))]
        if len(values) != 1:
            fail("LISTING_SEMANTICS_MISMATCH", f"member {key} count mismatch")
        return values[0]
    path, size, method = one("Path"), one("Size"), one("Method")
    expected_method = (f"PPMD:o{cell.order}:mem"
                       f"{expected_memory_exponent(cell.entry.size_bytes, cell.memory_mib)}")
    if path != cell.entry.name or size != str(cell.entry.size_bytes) or method != expected_method:
        fail("LISTING_SEMANTICS_MISMATCH", f"member identity mismatch: {cell.identifier}")
    return method, (path,)

def expected_commands(cell: Cell) -> Mapping[str, list[str]]:
    base = f"cells/{cell.slug}"
    source = cell.entry.source_operand
    return {
        "encode": ["/usr/bin/time", "-v", "-o", f"{base}/encode.time",
                   "/usr/bin/taskset", "-c", "0-15", "/usr/bin/7z", "a", "-t7z",
                   "-m0=PPMd", f"-mo={cell.order}", f"-mmem={cell.memory_mib}m",
                   "-bd", "-y", f"{base}/payload.7z", source],
        "inspect": ["/usr/bin/7z", "l", "-slt", f"{base}/payload.7z"],
        "decode": ["/usr/bin/time", "-v", "-o", f"{base}/decode.time",
                   "/usr/bin/taskset", "-c", "0-15", "/usr/bin/7z", "x", "-so",
                   "-y", f"{base}/payload.7z"],
        "compare": ["/usr/bin/cmp", "-s", source, f"{base}/decoded.bin"],
    }

OBSERVATION_KEYS = frozenset({
    "archive_bytes", "archive_inspection", "archive_sha256", "artifacts", "cell",
    "cmp_command", "cmp_equal", "cmp_returncode", "code_sha", "cohort", "cpu_set",
    "decode", "decoded_bytes", "decoded_sha256", "encode", "file", "grid_sha256",
    "input_bytes", "input_sha256", "inventory_sha256", "memory_mib", "order",
    "preregistration", "relative_path", "round_trip", "run_id", "schema",
    "sha256_equal", "tools",
})
PHASE_KEYS = frozenset({"command", "returncode", "elapsed_seconds", "peak_rss_kib", "stdout", "stderr"})
INSPECTION_KEYS = frozenset({"command", "returncode", "stdout", "stderr", "method", "member_paths"})
ARTIFACT_KEYS = frozenset({"relative_path", "sha256", "size_bytes"})

def exact_nonnegative_integer(value: Any, *, positive: bool = False) -> bool:
    return type(value) is int and value >= (1 if positive else 0)

def exact_zero_returncode(value: Any) -> bool:
    return type(value) is int and value == 0

def validate_observation(root: Path, row: Mapping[str, Any], cell: Cell,
                         manifest: Mapping[str, Mapping[str, Any]]) -> None:
    require_keys(row, OBSERVATION_KEYS, "OBSERVATION_SCHEMA_MISMATCH")
    commands = expected_commands(cell)
    encode = require_keys(row["encode"], PHASE_KEYS, "OBSERVATION_SCHEMA_MISMATCH")
    inspection = require_keys(row["archive_inspection"], INSPECTION_KEYS,
                              "OBSERVATION_SCHEMA_MISMATCH")
    decode = require_keys(row["decode"], PHASE_KEYS, "OBSERVATION_SCHEMA_MISMATCH")
    if (row["cell"] != cell.identifier or row["cohort"] != cell.entry.cohort
            or row["file"] != cell.entry.name or row["relative_path"] != cell.entry.relative_path
            or row["order"] != cell.order or row["memory_mib"] != cell.memory_mib
            or row["cpu_set"] != "0-15"):
        fail("OBSERVATION_GRID_MISMATCH", f"cell identity mismatch: {cell.identifier}")
    if (encode["command"] != commands["encode"]
            or inspection["command"] != commands["inspect"]
            or decode["command"] != commands["decode"]
            or row["cmp_command"] != commands["compare"]):
        fail("COMMAND_ARRAY_MISMATCH", f"command mismatch: {cell.identifier}")
    if not all(exact_zero_returncode(phase["returncode"])
               for phase in (encode, inspection, decode)):
        fail("CELL_RETURN_CODE_MISMATCH", f"nonzero child status: {cell.identifier}")
    if not exact_zero_returncode(row["cmp_returncode"]) or row["cmp_equal"] is not True:
        fail("ROUND_TRIP_CLAIM_MISMATCH", f"cmp claim mismatch: {cell.identifier}")
    if row["sha256_equal"] is not True or row["round_trip"] is not True:
        fail("ROUND_TRIP_CLAIM_MISMATCH", f"round-trip claim mismatch: {cell.identifier}")
    for name, phase in (("encode", encode), ("archive_inspection", inspection), ("decode", decode)):
        if not isinstance(phase["stdout"], str) or not isinstance(phase["stderr"], str):
            fail("OBSERVATION_SCHEMA_MISMATCH", f"child text type mismatch: {name}")
        if ERROR_MARKER_RE.search(phase["stdout"]) or ERROR_MARKER_RE.search(phase["stderr"]):
            fail("CELL_ERROR_MARKER", f"error marker in {name}: {cell.identifier}")
    artifacts = require_keys(row["artifacts"],
        frozenset({"archive", "decode_time", "decoded", "encode_time", "input"}),
        "ARTIFACT_IDENTITY_MISMATCH")
    base = f"cells/{cell.slug}"
    expected_paths = {
        "archive": f"{base}/payload.7z", "decoded": f"{base}/decoded.bin",
        "encode_time": f"{base}/encode.time", "decode_time": f"{base}/decode.time",
    }
    for label, relative in expected_paths.items():
        artifact = require_keys(artifacts[label], ARTIFACT_KEYS,
                                "ARTIFACT_IDENTITY_MISMATCH")
        if (not isinstance(artifact["relative_path"], str)
                or not exact_nonnegative_integer(artifact["size_bytes"], positive=True)
                or not isinstance(artifact["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) is None):
            fail("ARTIFACT_IDENTITY_MISMATCH", f"artifact type mismatch: {relative}")
        manifest_entry = manifest.get(relative)
        if (artifact["relative_path"] != relative or not isinstance(manifest_entry, dict)
                or manifest_entry.get("sha256") != artifact["sha256"]
                or manifest_entry.get("size_bytes") != artifact["size_bytes"]):
            fail("ARTIFACT_IDENTITY_MISMATCH", f"artifact/manifest mismatch: {relative}")
        if sha256_file(root / relative) != artifact["sha256"] or (root / relative).stat().st_size != artifact["size_bytes"]:
            fail("ARTIFACT_IDENTITY_MISMATCH", f"artifact bytes mismatch: {relative}")
    source = artifacts["input"]
    if source != {"relative_path": cell.entry.source_operand,
                  "size_bytes": cell.entry.size_bytes, "sha256": cell.entry.sha256}:
        fail("INVENTORY_IDENTITY_MISMATCH", f"external input identity mismatch: {cell.identifier}")
    archive = artifacts["archive"]
    if (not exact_nonnegative_integer(row["archive_bytes"], positive=True)
            or row["archive_bytes"] != archive["size_bytes"]
            or row["archive_sha256"] != archive["sha256"]):
        fail("ARCHIVE_SIZE_INVALID", f"archive identity mismatch: {cell.identifier}")
    decoded = artifacts["decoded"]
    if (decoded["size_bytes"] != cell.entry.size_bytes or decoded["sha256"] != cell.entry.sha256
            or row["decoded_bytes"] != cell.entry.size_bytes or row["decoded_sha256"] != cell.entry.sha256
            or row["input_bytes"] != cell.entry.size_bytes or row["input_sha256"] != cell.entry.sha256):
        fail("DECODED_IDENTITY_MISMATCH", f"decoded/source identity mismatch: {cell.identifier}")
    method, paths = parse_listing(
        inspection["stdout"] + "\n" + inspection["stderr"], cell
    )
    if inspection["method"] != method or inspection["member_paths"] != list(paths):
        fail("LISTING_SEMANTICS_MISMATCH", f"stored listing projection mismatch: {cell.identifier}")
    for phase in ("encode", "decode"):
        elapsed, rss = parse_gnu_time((root / artifacts[f"{phase}_time"]["relative_path"]).read_text(encoding="utf-8"))
        try:
            recorded = Decimal(str((encode if phase == "encode" else decode)["elapsed_seconds"]))
        except InvalidOperation as exc:
            fail("TIMING_GRAMMAR_MISMATCH", f"invalid row duration: {exc}")
        phase_record = encode if phase == "encode" else decode
        if (not recorded.is_finite() or recorded < 0
                or not exact_nonnegative_integer(phase_record["peak_rss_kib"])
                or recorded != elapsed or phase_record["peak_rss_kib"] != rss):
            fail("TIMING_GRAMMAR_MISMATCH", f"timing projection mismatch: {cell.identifier}")
```

```python
RAW_RUN_ID = "4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba"
HISTORICAL_REPO_ROOT = "/home/dev/.worktrees/cubrim/CUBR-NEW02-CAMPAIGN"
HISTORICAL_PREREG_PATH = (
    HISTORICAL_REPO_ROOT
    + "/documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md"
)
HISTORICAL_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "python": "3.12.3"}
INVENTORY_SHA256 = "77b355f6b109acb26eb5606cf1538e2e6628fac3f6ed88b76f99f70a9716ceda"
GRID_SHA256 = "8c5f8d8ba6016f03eded06842d444a6ac06f417e6ae8fd01db9d0e0abef206f4"
PREREG = {
    "path": HISTORICAL_PREREG_PATH,
    "repo_path": "documentation/ephemeral/research/CUBR-NEW02-PPMD-ORACLE-PREREG-20260810.md",
    "git_blob_sha": "d96df7e3478a6ba52b737ef30dea63d68b0e01ac",
    "sha256": "fd712e0f0936b2fcce94ff49e1d559852d8e7db7b89ec8affa83263c6e6dd093",
}
PROVENANCE_KEYS = frozenset({
    "code_sha", "environment", "grid_sha256", "harness_sha256",
    "inventory_sha256", "preregistration", "repo_root", "run_id",
    "test_sha256", "tools",
})
INVENTORY_ROW_KEYS = frozenset({
    "cohort", "name", "path", "relative_path", "sha256", "size_bytes",
})
HARNESS_SHA256 = "35c2f7eb7dc7f3ef5008136b7658607342273df36c8c9b13d3fdeda80f3143c5"
HARNESS_TEST_SHA256 = "35be4a2cdcf5f09487eddd542966c3435bedf40874e6b081fe282b6edb8eb005"
TOOLS = {
    "7z": {"path": "/usr/bin/7z", "version": "7-Zip 23.01 (x64) : Copyright (c) 1999-2023 Igor Pavlov : 2023-06-20",
           "binary_sha256": "60fc00b4e1ed37668972c51f03426973d8006db3c7224075878f6d66196d7c27"},
    "cmp": {"path": "/usr/bin/cmp", "version": "cmp (GNU diffutils) 3.10",
            "binary_sha256": "e10750ef3db9bd3595d3cbb1e25bcfd6a964dc6aa0ba9561034067913ee1cc04"},
    "taskset": {"path": "/usr/bin/taskset", "version": "taskset from util-linux 2.39.3",
                "binary_sha256": "a9c851792e54e91fba7b827019380abee54e715b6817899c835e4f221354b260"},
    "time": {"path": "/usr/bin/time", "version": "time (GNU Time) UNKNOWN",
             "binary_sha256": "3b11dec50514a8473e9f6efa7a34d584d0657538c09988f61b72d38ad4991a10"},
}

def inventory_rows(policy: FrozenPolicy) -> tuple[tuple[object, ...], ...]:
    return tuple((e.cohort, e.name, e.relative_path, e.size_bytes, e.sha256)
                 for e in policy.inventory)

def historical_input_path(entry: InventoryEntry) -> str:
    roots = {
        "world": "/home/dev/cubr-new02-campaign-assets/corpus",
        "tuned": HISTORICAL_REPO_ROOT + "/documentation/ephemeral/research/corpus",
        "holdout": HISTORICAL_REPO_ROOT + "/documentation/ephemeral/research/holdout",
    }
    if entry.cohort not in roots:
        fail("INVENTORY_IDENTITY_MISMATCH", f"unknown inventory cohort: {entry.cohort}")
    return f"{roots[entry.cohort]}/{entry.relative_path}"

def expected_inventory_document(policy: FrozenPolicy) -> list[Mapping[str, Any]]:
    return [{
        "cohort": entry.cohort,
        "name": entry.name,
        "path": historical_input_path(entry),
        "relative_path": entry.relative_path,
        "sha256": entry.sha256,
        "size_bytes": entry.size_bytes,
    } for entry in policy.inventory]

def recompute_run_id(provenance: Mapping[str, Any]) -> str:
    material_keys = (
        "code_sha", "repo_root", "harness_sha256", "test_sha256",
        "inventory_sha256", "grid_sha256", "preregistration", "tools", "environment",
    )
    if frozenset(provenance) != PROVENANCE_KEYS:
        fail("PROVENANCE_SCHEMA_MISMATCH", "inner provenance schema mismatch")
    payload = json.dumps(
        {"schema": "new02-ppmd-oracle-v1", **{key: provenance[key] for key in material_keys}},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def inventory_digest(policy: FrozenPolicy) -> str:
    payload = json.dumps(inventory_rows(policy), separators=(",", ":"),
                         ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()

def grid_digest(policy: FrozenPolicy) -> str:
    rows = tuple((*entry, order, memory, policy.cpu_set)
                 for entry in inventory_rows(policy)
                 for order in policy.orders for memory in policy.memory_mib)
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()

def verify_provenance(document: Mapping[str, Any], policy: FrozenPolicy) -> None:
    require_keys(document, frozenset({"cpu_set", "inventory", "memory_mib",
        "observation_count", "orders", "provenance", "publication", "schema"}),
        "PROVENANCE_SCHEMA_MISMATCH")
    if (document["schema"] != "new02-ppmd-oracle-v1"
            or document["cpu_set"] != policy.cpu_set
            or document["orders"] != list(policy.orders)
            or document["memory_mib"] != list(policy.memory_mib)
            or document["observation_count"] != len(policy.cells)
            or document["publication"] != "all-or-nothing"):
        fail("PROVENANCE_SCHEMA_MISMATCH", "raw provenance envelope mismatch")
    inventory = document["inventory"]
    if (not isinstance(inventory, list)
            or any(not isinstance(row, dict) or frozenset(row) != INVENTORY_ROW_KEYS
                   for row in inventory)
            or inventory != expected_inventory_document(policy)
            or inventory_digest(policy) != INVENTORY_SHA256):
        fail("INVENTORY_IDENTITY_MISMATCH", "frozen inventory mismatch")
    if grid_digest(policy) != GRID_SHA256:
        fail("GRID_IDENTITY_MISMATCH", "frozen grid mismatch")
    provenance = document["provenance"]
    if not isinstance(provenance, dict) or frozenset(provenance) != PROVENANCE_KEYS:
        fail("PROVENANCE_SCHEMA_MISMATCH", "provenance material is not an object")
    if provenance.get("code_sha") != EXECUTION_COMMIT:
        fail("PROVENANCE_CODE_SHA_MISMATCH", "execution SHA mismatch")
    if provenance.get("run_id") != RAW_RUN_ID:
        fail("PROVENANCE_RUN_ID_MISMATCH", "run ID mismatch")
    if provenance.get("repo_root") != HISTORICAL_REPO_ROOT:
        fail("PROVENANCE_REPOSITORY_MISMATCH", "historical repository path string mismatch")
    if (provenance.get("inventory_sha256") != INVENTORY_SHA256
            or provenance.get("grid_sha256") != GRID_SHA256):
        fail("GRID_IDENTITY_MISMATCH", "provenance inventory/grid digest mismatch")
    if provenance.get("harness_sha256") != HARNESS_SHA256:
        fail("HARNESS_IDENTITY_MISMATCH", "harness SHA mismatch")
    if provenance.get("test_sha256") != HARNESS_TEST_SHA256:
        fail("HARNESS_TEST_IDENTITY_MISMATCH", "harness-test SHA mismatch")
    prereg = provenance.get("preregistration")
    if not isinstance(prereg, dict) or prereg != PREREG:
        fail("PREREGISTRATION_IDENTITY_MISMATCH", "preregistration identity mismatch")
    if provenance.get("tools") != TOOLS:
        fail("TOOL_IDENTITY_MISMATCH", "capture tool provenance mismatch")
    if provenance.get("environment") != HISTORICAL_ENVIRONMENT:
        fail("PROVENANCE_ENVIRONMENT_MISMATCH", "historical environment mismatch")
    if recompute_run_id(provenance) != RAW_RUN_ID:
        fail("PROVENANCE_RUN_ID_MISMATCH", "run ID does not bind exact provenance material")

def observation_rows(path: Path, expected_count: int) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line in handle:
                if not line.endswith("\n"):
                    fail("OBSERVATION_SCHEMA_MISMATCH", "unterminated JSONL row")
                value = json.loads(line, parse_float=Decimal)
                if not isinstance(value, dict):
                    fail("OBSERVATION_SCHEMA_MISMATCH", "JSONL row is not an object")
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("OBSERVATION_SCHEMA_MISMATCH", f"invalid observations JSONL: {exc}")
    if len(rows) != expected_count:
        fail("OBSERVATION_GRID_MISMATCH", "observation row count mismatch")
    return tuple(rows)

def verify_repeated_row_identity(row: Mapping[str, Any]) -> None:
    if row.get("schema") != "new02-ppmd-oracle-v1":
        fail("OBSERVATION_SCHEMA_MISMATCH", "row schema mismatch")
    if row.get("run_id") != RAW_RUN_ID or row.get("code_sha") != EXECUTION_COMMIT:
        fail("PROVENANCE_RUN_ID_MISMATCH", "row run/code mismatch")
    if row.get("inventory_sha256") != INVENTORY_SHA256 or row.get("grid_sha256") != GRID_SHA256:
        fail("GRID_IDENTITY_MISMATCH", "row inventory/grid mismatch")
    if row.get("tools") != TOOLS:
        fail("TOOL_IDENTITY_MISMATCH", "row tool identity mismatch")
    prereg = row.get("preregistration")
    if not isinstance(prereg, dict) or prereg != PREREG:
        fail("PREREGISTRATION_IDENTITY_MISMATCH", "row preregistration mismatch")

def verify_raw_publication(root: Path,
                           policy: FrozenPolicy = FROZEN_POLICY) -> RawEvidence:
    manifest_document = verify_raw_envelope(root, policy)
    provenance = load_json(root / "provenance.json",
        frozenset({"cpu_set", "inventory", "memory_mib", "observation_count",
                   "orders", "provenance", "publication", "schema"}),
        "PROVENANCE_SCHEMA_MISMATCH")
    verify_provenance(provenance, policy)
    rows = observation_rows(root / "observations.jsonl", len(policy.cells))
    manifest_index = {entry["path"]: entry for entry in manifest_document["entries"]}
    identifiers: list[str] = []
    for row, cell in zip(rows, policy.cells, strict=True):
        verify_repeated_row_identity(row)
        validate_observation(root, row, cell, manifest_index)
        identifiers.append(str(row["cell"]))
    if (identifiers != [cell.identifier for cell in policy.cells]
            or len(set(identifiers)) != len(policy.cells)):
        fail("OBSERVATION_GRID_MISMATCH", "ordered unique cell grid mismatch")
    return RawEvidence(root=root, provenance=provenance, observations=rows,
                       manifest=manifest_document)
```

### Supplemental systemd: exact parser, safe fields, tools, and atomic publisher

```python
JOURNAL_ALLOWED_KEYS = frozenset({
    "CODE_FILE", "CODE_FUNC", "CODE_LINE", "CPU_USAGE_NSEC", "JOB_ID", "JOB_RESULT",
    "JOB_TYPE", "MEMORY_PEAK", "MEMORY_SWAP_PEAK", "MESSAGE", "MESSAGE_ID", "PRIORITY",
    "SYSLOG_FACILITY", "SYSLOG_IDENTIFIER", "TID", "USER_INVOCATION_ID", "USER_UNIT",
    "_AUDIT_LOGINUID", "_AUDIT_SESSION", "_BOOT_ID", "_CAP_EFFECTIVE", "_CMDLINE", "_COMM",
    "_EXE", "_GID", "_HOSTNAME", "_MACHINE_ID", "_PID", "_RUNTIME_SCOPE",
    "_SELINUX_CONTEXT", "_SOURCE_REALTIME_TIMESTAMP", "_SYSTEMD_CGROUP",
    "_SYSTEMD_OWNER_UID", "_SYSTEMD_SLICE", "_SYSTEMD_UNIT", "_SYSTEMD_USER_SLICE",
    "_SYSTEMD_USER_UNIT", "_TRANSPORT", "_UID", "__CURSOR", "__MONOTONIC_TIMESTAMP",
    "__REALTIME_TIMESTAMP", "__SEQNUM", "__SEQNUM_ID",
})
JOURNAL_REQUIRED_KEYS = frozenset({"MESSAGE", "USER_UNIT", "USER_INVOCATION_ID"})
UNSAFE_KEY_RE = re.compile(r"(?:^|_)(?:ENVIRONMENT|CREDENTIAL|SECRET|TOKEN|PASSWORD|AUTHORIZATION|COOKIE|PRIVATE_KEY)(?:$|_)", re.I)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:authorization|proxy-authorization)\s*[:=]\s*(?:bearer|basic)\s+\S+", re.I),
    re.compile(r"\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
USER_UNIT = "cubr-new02-oracle-20260810t020926z.service"
USER_INVOCATION_ID = "f648d8b61de34ae0900291a06371a3dc"
RUN_PREFIX = "4352d71ee8f4479c"
SHOW_KEYS = frozenset({
    "Result", "NRestarts", "ExecMainStartTimestamp", "ExecMainExitTimestamp",
    "ExecMainCode", "ExecMainStatus", "Id", "Names", "Description", "LoadState",
    "ActiveState", "SubState", "InvocationID",
})
SHOW_PROPERTIES = (
    "Id,Names,Description,LoadState,ActiveState,SubState,Result,NRestarts,"
    "ExecMainStartTimestamp,ExecMainExitTimestamp,ExecMainCode,ExecMainStatus,InvocationID"
)
JOURNAL_COMMON_KEYS = frozenset({
    "CODE_FILE", "CODE_FUNC", "CODE_LINE", "MESSAGE", "MESSAGE_ID", "PRIORITY",
    "SYSLOG_FACILITY", "SYSLOG_IDENTIFIER", "TID", "USER_INVOCATION_ID", "USER_UNIT",
    "_AUDIT_LOGINUID", "_AUDIT_SESSION", "_BOOT_ID", "_CAP_EFFECTIVE", "_CMDLINE",
    "_COMM", "_EXE", "_GID", "_HOSTNAME", "_MACHINE_ID", "_PID", "_RUNTIME_SCOPE",
    "_SELINUX_CONTEXT", "_SOURCE_REALTIME_TIMESTAMP", "_SYSTEMD_CGROUP",
    "_SYSTEMD_OWNER_UID", "_SYSTEMD_SLICE", "_SYSTEMD_UNIT", "_SYSTEMD_USER_SLICE",
    "_SYSTEMD_USER_UNIT", "_TRANSPORT", "_UID", "__CURSOR", "__MONOTONIC_TIMESTAMP",
    "__REALTIME_TIMESTAMP", "__SEQNUM", "__SEQNUM_ID",
})
JOURNAL_KEY_SETS = (
    JOURNAL_COMMON_KEYS | {"JOB_ID", "JOB_TYPE"},
    JOURNAL_COMMON_KEYS | {"JOB_ID", "JOB_RESULT", "JOB_TYPE"},
    JOURNAL_COMMON_KEYS | {"CPU_USAGE_NSEC", "MEMORY_PEAK", "MEMORY_SWAP_PEAK"},
)
HARNESS_COMMAND = (
    f"/usr/bin/python3 {HISTORICAL_REPO_ROOT}/documentation/ephemeral/research/new02_oracle_grid.py "
    "--execute --world-root /home/dev/cubr-new02-campaign-assets/corpus "
    f"--tuned-root {HISTORICAL_REPO_ROOT}/documentation/ephemeral/research/corpus "
    f"--holdout-root {HISTORICAL_REPO_ROOT}/documentation/ephemeral/research/holdout "
    f"--repo-root {HISTORICAL_REPO_ROOT} --output-dir {RAW_NAMESPACE} "
    f"--void-journal {RAW_NAMESPACE}.VOID.jsonl"
)
JOURNAL_MESSAGES = (
    f"Starting {USER_UNIT} - {HARNESS_COMMAND}" + "." * 3,
    f"Started {USER_UNIT} - {HARNESS_COMMAND}.",
    f"{USER_UNIT}: Consumed 5min 54.303s CPU time, 1.9G memory peak, 0B memory swap peak.",
)

@dataclass(frozen=True)
class RuntimeIdentity:
    path: Path
    expected_path: Path
    uid: int

@dataclass(frozen=True)
class ToolIdentity:
    path: Path
    realpath: Path
    sha256: str

@dataclass(frozen=True)
class CaptureTools:
    systemctl: ToolIdentity
    journalctl: ToolIdentity
    hostname: ToolIdentity
    python: ToolIdentity
    runner: Callable[[Sequence[str]], bytes]

def production_tools(runner: Callable[[Sequence[str]], bytes]) -> CaptureTools:
    return CaptureTools(
        ToolIdentity(Path("/usr/bin/systemctl"), Path("/usr/bin/systemctl"), "7ba82b5ba146759c710e1b80fadaa3fdbc0f9b85c8fb2c8c3196b7b1a0037ef8"),
        ToolIdentity(Path("/usr/bin/journalctl"), Path("/usr/bin/journalctl"), "c49bd25d7e7655b9a44ff867923952ed5a5e0a65e9df7a0510e239bf0558e3fa"),
        ToolIdentity(Path("/usr/bin/hostname"), Path("/usr/bin/hostname"), "071fec20458397874e6121589d5210e7eed22a1b1afe16c2b9970b8a8233cc5b"),
        ToolIdentity(Path("/usr/bin/python3"), Path("/usr/bin/python3.12"), "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118"),
        runner,
    )

def validate_user_bus(runtime: RuntimeIdentity) -> None:
    try:
        directory = os.lstat(runtime.path)
        bus = os.lstat(runtime.path / "bus")
    except OSError as exc:
        fail("SYSTEMD_RUNTIME_DIR_INVALID", f"user bus unavailable: {type(exc).__name__}")
    if (runtime.path != runtime.expected_path or not runtime.path.is_absolute()
            or not stat.S_ISDIR(directory.st_mode) or stat.S_ISLNK(directory.st_mode)
            or directory.st_uid != runtime.uid or stat.S_IMODE(directory.st_mode) != 0o700
            or not stat.S_ISSOCK(bus.st_mode) or bus.st_uid != runtime.uid
            or stat.S_IMODE(bus.st_mode) != 0o666):
        fail("SYSTEMD_RUNTIME_DIR_INVALID", "user runtime directory/socket identity mismatch")

def run_capture_command(argv: Sequence[str], runtime: RuntimeIdentity) -> bytes:
    validate_user_bus(runtime)
    result = subprocess.run(tuple(argv), check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env={
                                "LC_ALL": "C", "LANG": "C",
                                "XDG_RUNTIME_DIR": str(runtime.path),
                            })
    if result.returncode != 0:
        fail("SYSTEMD_EVIDENCE_UNAVAILABLE",
             f"capture command failed: {Path(argv[0]).name}: exit {result.returncode}")
    return result.stdout

def validate_tool(tool: ToolIdentity) -> None:
    if tool.path.resolve(strict=True) != tool.realpath or sha256_file(tool.path) != tool.sha256:
        fail("SYSTEMD_TOOL_IDENTITY_MISMATCH", f"capture tool mismatch: {tool.path}")

def secret_scan(record: Mapping[str, Any]) -> None:
    for key, value in record.items():
        if key not in JOURNAL_ALLOWED_KEYS or UNSAFE_KEY_RE.search(key):
            fail("SYSTEMD_UNSAFE_FIELD", f"unsafe journal key: {key}")
        rendered = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        if any(pattern.search(rendered) for pattern in SECRET_VALUE_PATTERNS):
            fail("SYSTEMD_SECRET_SCAN_FAILED", f"secret-like journal value in key: {key}")

def secret_scan_text(payload: bytes, label: str) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("SYSTEMD_SECRET_SCAN_FAILED", f"{label} is not UTF-8: {exc}")
    if any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS):
        fail("SYSTEMD_SECRET_SCAN_FAILED", f"secret-like content in {label}")
    return text

def parse_systemctl_show(payload: bytes) -> Mapping[str, str]:
    text = secret_scan_text(payload, "systemctl show")
    if not text.endswith("\n") or "\r" in text or "\x00" in text:
        fail("SYSTEMD_SHOW_SCHEMA_MISMATCH", "show framing mismatch")
    values: dict[str, str] = {}
    for line in text.splitlines():
        if line.count("=") < 1:
            fail("SYSTEMD_SHOW_SCHEMA_MISMATCH", "show line lacks separator")
        key, value = line.split("=", 1)
        if UNSAFE_KEY_RE.search(key):
            fail("SYSTEMD_UNSAFE_FIELD", f"unsafe show key: {key}")
        if key in values:
            fail("SYSTEMD_SHOW_SCHEMA_MISMATCH", f"duplicate show key: {key}")
        values[key] = value
    if frozenset(values) != SHOW_KEYS:
        fail("SYSTEMD_SHOW_SCHEMA_MISMATCH", "show key set mismatch")
    expected = {
        "Result": "success", "NRestarts": "0", "ExecMainStartTimestamp": "",
        "ExecMainExitTimestamp": "", "ExecMainCode": "0", "ExecMainStatus": "0",
        "Id": USER_UNIT, "Names": USER_UNIT, "Description": USER_UNIT,
        "LoadState": "not-found", "ActiveState": "inactive", "SubState": "dead",
        "InvocationID": "",
    }
    if values != expected:
        fail("SYSTEMD_SHOW_SCHEMA_MISMATCH", "unloaded show snapshot mismatch")
    return values

def parse_journal_bytes(payload: bytes) -> tuple[Mapping[str, Any], ...]:
    try:
        rows = tuple(json.loads(line) for line in payload.decode("utf-8").splitlines() if line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("SYSTEMD_JOURNAL_HASH_MISMATCH", f"journal JSON invalid: {exc}")
    if len(rows) != 3:
        fail("SYSTEMD_JOURNAL_SCHEMA_MISMATCH", "journal record count is not three")
    messages: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail("SYSTEMD_JOURNAL_SCHEMA_MISMATCH", "journal record is not an object")
        secret_scan(row)
        if (frozenset(row) != JOURNAL_KEY_SETS[index]
                or any(not isinstance(value, str) for value in row.values())):
            fail("SYSTEMD_JOURNAL_SCHEMA_MISMATCH", "journal record schema/type mismatch")
        if row["USER_UNIT"] != USER_UNIT:
            fail("SYSTEMD_USER_UNIT_MISMATCH", "journal USER_UNIT mismatch")
        if row["USER_INVOCATION_ID"] != USER_INVOCATION_ID:
            fail("SYSTEMD_INVOCATION_MISMATCH", "journal USER_INVOCATION_ID mismatch")
        messages.append(row["MESSAGE"])
    if not all(RAW_NAMESPACE in message and RUN_PREFIX in message for message in messages[:2]):
        fail("SYSTEMD_NAMESPACE_MISMATCH", "journal namespace/run-prefix mismatch")
    if tuple(messages) != JOURNAL_MESSAGES:
        fail("SYSTEMD_COMMAND_MISMATCH", "start command correlation mismatch")
    return rows

def atomic_publish(directory: Path, files: Mapping[str, bytes]) -> None:
    import shutil
    import tempfile
    parent = directory.parent
    original_mode = stat.S_IMODE(os.lstat(parent).st_mode)
    temporary: Path | None = None
    renamed = False
    published = False
    try:
        if os.path.lexists(directory):
            fail("ATOMIC_DESTINATION_EXISTS", f"destination exists: {directory}")
        os.chmod(parent, original_mode | stat.S_IWUSR)
        temporary = Path(tempfile.mkdtemp(prefix=f".{directory.name}.tmp-", dir=parent))
        for name, payload in files.items():
            target = temporary / name
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            try:
                os.fchmod(fd, 0o444)
                with os.fdopen(fd, "wb", closefd=False) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(fd)
        dir_fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        os.chmod(temporary, 0o555)
        os.rename(temporary, directory)
        renamed = True
        temporary = None
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        published = True
    except HistoricalValidationError:
        raise
    except OSError as exc:
        fail("ATOMIC_PUBLICATION_FAILED", f"atomic evidence publication failed: {exc}")
    finally:
        if temporary is not None and os.path.lexists(temporary):
            os.chmod(temporary, 0o755)
            shutil.rmtree(temporary)
        if renamed and not published and os.path.lexists(directory):
            os.chmod(directory, 0o755)
            shutil.rmtree(directory)
            rollback_parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(rollback_parent_fd)
            finally:
                os.close(rollback_parent_fd)
        os.chmod(parent, original_mode)

def capture_systemd_evidence(destination: Path, tools: CaptureTools,
                             runtime: RuntimeIdentity) -> Mapping[str, Any]:
    validate_user_bus(runtime)
    for tool in (tools.systemctl, tools.journalctl, tools.hostname, tools.python):
        validate_tool(tool)
    if tools.runner((str(tools.hostname.path),)).decode().strip() != "arcana-devs":
        fail("SYSTEMD_EVIDENCE_UNAVAILABLE", "capture host is not arcana-devs")
    show = tools.runner((str(tools.systemctl.path), "--user", "show", USER_UNIT, "--no-pager",
        f"--property={SHOW_PROPERTIES}"))
    journal = tools.runner((str(tools.journalctl.path), "--user", "-u", USER_UNIT,
                            f"USER_INVOCATION_ID={USER_INVOCATION_ID}", "-o", "json", "--no-pager"))
    parse_systemctl_show(show)
    rows = parse_journal_bytes(journal)
    capture = {
        "schema": "new02-systemd-correlation-v1",
        "classification": "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF",
        "host": "arcana-devs", "user_unit": USER_UNIT,
        "user_invocation_id": USER_INVOCATION_ID, "run_id": RAW_RUN_ID,
        "raw_namespace": RAW_NAMESPACE, "journal_record_count": len(rows),
        "systemctl_show_sha256": hashlib.sha256(show).hexdigest(),
        "journalctl_user_unit_sha256": hashlib.sha256(journal).hexdigest(),
        "start_correlated": True, "exit_proven": False, "restart_history_proven": False,
        "tools": {name: {"path": str(tool.path), "realpath": str(tool.realpath), "sha256": tool.sha256}
                  for name, tool in (("systemctl", tools.systemctl), ("journalctl", tools.journalctl),
                                     ("hostname", tools.hostname), ("python", tools.python))},
    }
    capture_bytes = (json.dumps(capture, indent=2, sort_keys=True) + "\n").encode()
    atomic_publish(destination, {
        "systemctl-show.txt": show,
        "journalctl-user-unit.jsonl": journal,
        "capture.json": capture_bytes,
    })
    return capture

def verify_systemd_evidence(directory: Path) -> Mapping[str, Any]:
    if not directory.exists():
        fail("SYSTEMD_EVIDENCE_UNAVAILABLE", "supplemental systemd directory is absent")
    info = os.lstat(directory)
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o555:
        fail("SYSTEMD_EVIDENCE_PATH_SET_MISMATCH", "systemd directory must be real mode 0555")
    expected = {"systemctl-show.txt", "journalctl-user-unit.jsonl", "capture.json"}
    if {entry.name for entry in os.scandir(directory)} != expected:
        fail("SYSTEMD_EVIDENCE_PATH_SET_MISMATCH", "systemd evidence path set mismatch")
    for name in expected:
        child = os.lstat(directory / name)
        if not stat.S_ISREG(child.st_mode) or child.st_nlink != 1 or stat.S_IMODE(child.st_mode) != 0o444:
            fail("SYSTEMD_EVIDENCE_PATH_SET_MISMATCH", f"invalid evidence file: {name}")
    capture = load_json(directory / "capture.json", frozenset({
        "schema", "classification", "host", "user_unit", "user_invocation_id", "run_id",
        "raw_namespace", "journal_record_count", "systemctl_show_sha256",
        "journalctl_user_unit_sha256", "start_correlated", "exit_proven",
        "restart_history_proven", "tools",
    }), "SYSTEMD_EVIDENCE_PATH_SET_MISMATCH")
    if (capture["schema"] != "new02-systemd-correlation-v1"
            or capture["classification"] != "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF"
            or capture["host"] != "arcana-devs" or capture["user_unit"] != USER_UNIT
            or capture["user_invocation_id"] != USER_INVOCATION_ID
            or capture["run_id"] != RAW_RUN_ID or capture["raw_namespace"] != RAW_NAMESPACE
            or capture["journal_record_count"] != 3 or capture["start_correlated"] is not True):
        fail("SYSTEMD_INVOCATION_MISMATCH", "capture correlation envelope mismatch")
    if capture["exit_proven"] is not False or capture["restart_history_proven"] is not False:
        fail("SYSTEMD_OVERCLAIM_REJECTED", "unloaded show defaults promoted to proof")
    show = (directory / "systemctl-show.txt").read_bytes()
    journal = (directory / "journalctl-user-unit.jsonl").read_bytes()
    if hashlib.sha256(show).hexdigest() != capture["systemctl_show_sha256"]:
        fail("SYSTEMD_SHOW_HASH_MISMATCH", "show byte hash mismatch")
    if hashlib.sha256(journal).hexdigest() != capture["journalctl_user_unit_sha256"]:
        fail("SYSTEMD_JOURNAL_HASH_MISMATCH", "journal byte hash mismatch")
    parse_systemctl_show(show)
    parse_journal_bytes(journal)
    expected_tools = production_tools(lambda argv: b"")
    expected_map = {name: {"path": str(tool.path), "realpath": str(tool.realpath), "sha256": tool.sha256}
                    for name, tool in (("systemctl", expected_tools.systemctl),
                                       ("journalctl", expected_tools.journalctl),
                                       ("hostname", expected_tools.hostname),
                                       ("python", expected_tools.python))}
    if capture["tools"] != expected_map:
        fail("SYSTEMD_TOOL_IDENTITY_MISMATCH", "captured executable identity map mismatch")
    return capture

def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_new02_historical.py")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--repository", type=Path)
    validate.add_argument("--raw-run", type=Path, required=True)
    validate.add_argument("--systemd-evidence", type=Path)
    validate.add_argument("--raw-only", action="store_true")
    capture = commands.add_parser("capture-systemd")
    capture.add_argument("--output", type=Path, required=True)
    return parser

def discover_repository() -> Path:
    result = subprocess.run(("git", "rev-parse", "--show-toplevel"), check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        fail("VALIDATION_SUBPROCESS_ERROR", "unable to discover repository root")
    try:
        return Path(result.stdout.decode("utf-8").strip())
    except UnicodeDecodeError as exc:
        fail("VALIDATION_DATA_ERROR", f"repository root is not UTF-8: {exc}")

def validation_lines(historical_status: str, systemd_status: str) -> tuple[str, ...]:
    return (
        "CAPTURE_STATUS=COMPLETE",
        f"HISTORICAL_VALIDATION_STATUS={historical_status}",
        "SCIENTIFIC_CHARACTERIZATION=CHARACTERIZED_NO_SELECT",
        "PRODUCT_SELECTION_STATUS=NOT_ISSUED",
        f"SYSTEMD_CORRELATION_STATUS={systemd_status}",
        f"NEW02_HISTORICAL_VALIDATION=PASS cells=243 run_id={RAW_RUN_ID}",
    )

def main(argv: Sequence[str] | None = None) -> int:
    arguments = argument_parser().parse_args(argv)
    try:
        if arguments.command == "capture-systemd":
            canonical = Path(__file__).resolve().parent / "systemd-correlated"
            if arguments.output.resolve(strict=False) != canonical:
                argument_parser().error("--output must be the canonical systemd-correlated path")
            uid = os.getuid()
            runtime = RuntimeIdentity(
                Path(os.environ.get("XDG_RUNTIME_DIR", "")), Path(f"/run/user/{uid}"), uid,
            )
            tools = production_tools(lambda command: run_capture_command(command, runtime))
            capture_systemd_evidence(canonical, tools, runtime)
            return 0
        verify_raw_publication(arguments.raw_run)
        if arguments.raw_only:
            lines = validation_lines("PASS_RAW_ONLY", "SYSTEMD_EVIDENCE_UNAVAILABLE")
        else:
            repository = arguments.repository or discover_repository()
            verify_repository(repository)
            systemd_status = "SYSTEMD_EVIDENCE_UNAVAILABLE"
            if arguments.systemd_evidence is not None:
                verify_systemd_evidence(arguments.systemd_evidence)
                systemd_status = "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF"
            lines = validation_lines("PASS", systemd_status)
        sys.stdout.write("\n".join(lines) + "\n")
        return 0
    except HistoricalValidationError as exc:
        sys.stderr.write(f"NEW02_HISTORICAL_VALIDATION=FAIL code={exc.code} detail={exc.detail}\n")
        return 2
    except (OSError, json.JSONDecodeError, UnicodeError, InvalidOperation) as exc:
        sys.stderr.write(f"NEW02_HISTORICAL_VALIDATION=FAIL code=VALIDATION_DATA_ERROR detail={type(exc).__name__}\n")
        return 2
    except subprocess.SubprocessError as exc:
        sys.stderr.write(f"NEW02_HISTORICAL_VALIDATION=FAIL code=VALIDATION_SUBPROCESS_ERROR detail={type(exc).__name__}\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
```

`RAW_RUN_ID` in the module is the full frozen run ID already listed under Raw-publication pins. The production systemd subprocess runner uses `subprocess.run(tuple(argv), check=False, stdout=PIPE, stderr=PIPE, env={"LC_ALL":"C","LANG":"C","XDG_RUNTIME_DIR":str(runtime.path)})`, where `runtime.path` is the already validated canonical user runtime directory. It requires exit zero and never uses a shell. The frozen `HISTORICAL_ENVIRONMENT` above describes the old raw capture and intentionally remains separate. Tests inject a callable runner through `CaptureTools`; the CLI has no injection surface.

### Derived package: trusted ledger and automatic supplemental verification

```python
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from typing import Callable

GENERATED_FILES = ("README.md", "provenance.json", "results.tsv", "effects.tsv", "summary.json")
SUPPLEMENTAL_FILES = (
    "systemd-correlated/capture.json",
    "systemd-correlated/journalctl-user-unit.jsonl",
    "systemd-correlated/systemctl-show.txt",
)
UNAVAILABLE_STATUS = "SYSTEMD_EVIDENCE_UNAVAILABLE"
CORRELATED_STATUS = "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF"
BASE_LEDGER_FILES = tuple(sorted(GENERATED_FILES))
CORRELATED_LEDGER_FILES = tuple(sorted((*GENERATED_FILES, *SUPPLEMENTAL_FILES)))

def _summary_document() -> dict[str, object]:
    return {
        "schema": PACKAGE_SCHEMA,
        "verdict": {
            "outcome": "CHARACTERIZED_NO_SELECT", "source_status": "COMPLETE",
            "evidence_validation": "PASS", "selection": "NO-SELECT",
            "go_no_go": "NOT_ISSUED", "candidate": "NONE",
            "ceiling": "NOT_DEFINED_IN_PREREGISTRATION",
            "fraction_of_ceiling": "NOT_COMPUTED",
            "reason": (
                "The prospective preregistration froze measurement mechanics but no "
                "ceiling, aggregate, ranking, winner rule, or implementation-selection rule."
            ),
        },
        "scope": {
            "inventory_entries": 27, "observation_cells": 243, "per_file_only": True,
            "corpus_wide_average": "NOT_COMPUTED",
            "canterbury_policy": (
                "All six registered Canterbury files remain measured in results.tsv and "
                "effects.tsv but are excluded from broader claims."
            ),
        },
        "parameter_axes": {
            "var_h": {
                "parameter": "PPMd order", "levels": [4, 6, 8],
                "reported_effect": "adjacent charged-archive byte deltas per file at fixed memory",
            },
            "var_i": {
                "parameter": "requested PPMd memory MiB", "levels": [16, 64, 256],
                "reported_effect": "adjacent charged-archive byte deltas per file at fixed order",
            },
        },
        "validation": {
            "cell_status": "243/243 PASS", "encode_returncode": "243/243 zero",
            "inspection_returncode": "243/243 zero", "decode_returncode": "243/243 zero",
            "cmp_returncode": "243/243 zero", "cmp_equal": "243/243 true",
            "sha256_equal": "243/243 true", "round_trip": "243/243 true",
            "archive_authentication": (
                "exact per-cell stored archive SHA-256 and authenticated stored archive-inspection transcript"
            ),
        },
    }

def _signed(value: str) -> str:
    return f"{int(value):+d}"

def _readme(effects: Sequence[Mapping[str, str]]) -> str:
    lines = [
        "# NEW-02 canonical PPMd oracle-grid results", "", "Date: 2026-08-10",
        "Status: `COMPLETE` source publication; `CHARACTERIZED_NO_SELECT` scientific outcome",
        "", "## Authority and boundary", "",
        f"The historical validator authenticated the immutable `{SOURCE_BASENAME}` publication:",
        f"execution commit `{SOURCE_CODE_SHA}`, harness run ID `{SOURCE_RUN_ID}`, manifest",
        f"SHA-256 `{SOURCE_TOP_HASHES['MANIFEST.json']}`, and all 243 declared cells. Every",
        "archive/listing/round-trip statement below is an authenticated stored-capture claim:",
        "the validator checks sealed bytes and the authenticated stored archive-inspection transcript;",
        "it does not freshly execute 7-Zip, cmp, taskset, time, or the old harness.",
        "`results.tsv` states all 243 outcomes and measured timing/RSS values without any",
        "corpus-wide average.", "",
        "The preregistration contains no ceiling, aggregate, ranking, winner rule, or",
        "implementation-selection rule. Therefore this package does not select a parameter",
        "cell, issue GO/NO-GO, build a candidate, or compute a fraction of ceiling. The",
        "scientific result is characterization only: `NO-SELECT`.", "",
        "No systemd unit or systemd invocation ID is recorded by the canonical harness. The",
        "authenticated invocation identity is the harness run ID above; supplemental systemd",
        "evidence is correlation-only and cannot establish exit or restart history.", "",
        "## Var.H and Var.I per-file effects", "",
        "Var.H is the PPMd order axis (`4`, `6`, `8`). Var.I is requested PPMd memory",
        "(`16`, `64`, `256` MiB). Each archive triple is `16/64/256 MiB`. Order deltas are",
        "`4->6,6->8` at each fixed memory; memory deltas are `16->64,64->256` at each fixed",
        "order. A negative delta means the later level charged fewer archive bytes. These are",
        "exhaustive adjacent contrasts, not a ranking or selection rule.", "",
        "| cohort/file | order 4 archives | order 6 archives | order 8 archives | Var.H deltas at m16; m64; m256 | Var.I deltas at o4; o6; o8 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in effects:
        marker = " †" if row["excluded_from_broad_claims"] == "true" else ""
        archive = {order: "/".join(row[f"o{order}_m{memory}_archive_bytes"]
                                   for memory in (16, 64, 256)) for order in (4, 6, 8)}
        order_deltas = "; ".join(
            f"{_signed(row[f'o4_to_o6_at_m{memory}_delta_bytes'])},"
            f"{_signed(row[f'o6_to_o8_at_m{memory}_delta_bytes'])}"
            for memory in (16, 64, 256)
        )
        memory_deltas = "; ".join(
            f"{_signed(row[f'm16_to_m64_at_o{order}_delta_bytes'])},"
            f"{_signed(row[f'm64_to_m256_at_o{order}_delta_bytes'])}"
            for order in (4, 6, 8)
        )
        lines.append(f"| `{row['cohort']}/{row['file']}`{marker} | {archive[4]} | "
                     f"{archive[6]} | {archive[8]} | {order_deltas} | {memory_deltas} |")
    lines.extend([
        "", "† Registered Canterbury file: measured in all nine cells and retained in both TSV",
        "files, but excluded from broader claims because fixed archive overhead dominates",
        "these small inputs. This package makes no broader aggregate claim in any case.", "",
        "## Files", "", "- `results.tsv`: all 243 authenticated stored cell outcomes.",
        "- `effects.tsv`: 27 per-file matrices and adjacent Var.H/Var.I byte deltas.",
        "- `provenance.json`: frozen source identities and separated systemd evidence.",
        "- `summary.json`: structured `CHARACTERIZED_NO_SELECT` reporting boundary.",
        "- `SHA256SUMS`: deterministic package-data hashes.", "",
        "No database, API, site, backlog, candidate, or campaign state is changed by this package.", "",
    ])
    return "\n".join(lines)

def expected_ledger_files(systemd_status: str) -> tuple[str, ...]:
    if systemd_status == UNAVAILABLE_STATUS:
        return BASE_LEDGER_FILES
    if systemd_status == CORRELATED_STATUS:
        return CORRELATED_LEDGER_FILES
    HISTORICAL.fail("PACKAGE_LEDGER_INVALID", f"unknown systemd status: {systemd_status}")

def ledger_bytes(root: Path, names: Sequence[str]) -> bytes:
    return "".join(f"{sha256_file(root / name)}  {name}\n" for name in names).encode("ascii")

def parse_ledger(payload: bytes) -> Mapping[str, str]:
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        HISTORICAL.fail("PACKAGE_LEDGER_INVALID", f"ledger is not ASCII: {exc}")
    parsed: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)", line)
        if match is None or match.group(2) in parsed:
            HISTORICAL.fail("PACKAGE_LEDGER_INVALID", "ledger line/duplicate mismatch")
        parsed[match.group(2)] = match.group(1)
    return parsed

def verify_trusted_ledger(package: Path, repository: Path, trusted_revision: str,
                          git_blob: Callable[[Path, str, str], bytes]) -> Mapping[str, str]:
    if re.fullmatch(r"[0-9a-f]{40}", trusted_revision) is None:
        HISTORICAL.fail("TRUSTED_LEDGER_MISMATCH", "trusted revision must be an exact commit SHA")
    repo_relative = package.resolve().relative_to(repository.resolve()).as_posix()
    ledger_path = package / "SHA256SUMS"
    working = ledger_path.read_bytes()
    committed = git_blob(repository, trusted_revision, f"{repo_relative}/SHA256SUMS")
    if working != committed:
        HISTORICAL.fail("TRUSTED_LEDGER_MISMATCH", "working ledger differs from reviewed Git blob")
    ledger = parse_ledger(working)
    if tuple(ledger) not in {BASE_LEDGER_FILES, CORRELATED_LEDGER_FILES}:
        HISTORICAL.fail("PACKAGE_LEDGER_INVALID", "final ledger path set mismatch")
    for name in sorted(ledger):
        if not (package / name).is_file():
            HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_REQUIRED" if name in SUPPLEMENTAL_FILES else "PACKAGE_HASH_MISMATCH",
                 f"ledger file missing: {name}")
        if sha256_file(package / name) != ledger[name]:
            HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_HASH_MISMATCH" if name in SUPPLEMENTAL_FILES else "PACKAGE_HASH_MISMATCH",
                 f"ledger hash mismatch: {name}")
    return ledger

PRESERVED_FILES = (
    "verify_new02_historical.py", "test_verify_new02_historical.py",
    "verify_new02_results.py", "test_verify_new02_results.py",
    "capture_new02_systemd_evidence.sh",
)

def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

def make_tree_removable(path: Path) -> None:
    for directory in sorted((p for p in path.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        os.chmod(directory, 0o755)
    os.chmod(path, 0o755)

@dataclass(frozen=True)
class PublicationResult:
    committed: bool
    backup_retained: bool
    backup_path: Path | None

def cleanup_backup_tree(path: Path) -> None:
    make_tree_removable(path)
    shutil.rmtree(path)

def seal_surviving_backup(path: Path) -> None:
    for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
            fsync_directory(item)
    os.chmod(path, 0o555)
    fsync_directory(path)

def atomic_replace_generated(
    output_dir: Path,
    documents: Mapping[str, bytes],
    replace: bool,
    *,
    cleanup_backup: Callable[[Path], None] = cleanup_backup_tree,
) -> PublicationResult:
    import tempfile
    source_dir = Path(__file__).resolve().parent
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=parent))
    backup = parent / f".{output_dir.name}.rollback"
    old_moved = False
    committed = False
    try:
        if os.path.lexists(backup):
            HISTORICAL.fail("ATOMIC_PUBLICATION_FAILED", "stale rollback directory exists")
        if os.path.lexists(output_dir) and not replace:
            HISTORICAL.fail("ATOMIC_DESTINATION_EXISTS", "package destination exists")
        for name in PRESERVED_FILES:
            payload = (source_dir / name).read_bytes()
            target = stage / name
            target.write_bytes(payload)
            os.chmod(target, 0o555 if name.endswith(".sh") else 0o444)
            with target.open("rb") as handle:
                os.fsync(handle.fileno())
        for name, payload in documents.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            os.chmod(target, 0o444)
            with target.open("rb") as handle:
                os.fsync(handle.fileno())
        for directory in sorted((p for p in stage.rglob("*") if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            os.chmod(directory, 0o555)
            fsync_directory(directory)
        os.chmod(stage, 0o555)
        fsync_directory(stage)
        if os.path.lexists(output_dir):
            os.rename(output_dir, backup)
            old_moved = True
        os.rename(stage, output_dir)
        fsync_directory(parent)
        committed = True  # commit point: durable new generation owns output_dir
    except Exception as exc:
        if os.path.lexists(output_dir) and not os.path.lexists(stage):
            os.rename(output_dir, stage)
        if old_moved and os.path.lexists(backup):
            os.rename(backup, output_dir)
            old_moved = False
        fsync_directory(parent)
        if isinstance(exc, HISTORICAL.HistoricalValidationError):
            raise
        HISTORICAL.fail("ATOMIC_PUBLICATION_FAILED", f"generation swap failed: {type(exc).__name__}")
    finally:
        if not committed and os.path.lexists(stage):
            make_tree_removable(stage)
            shutil.rmtree(stage)
    if not old_moved:
        return PublicationResult(committed=True, backup_retained=False, backup_path=None)
    try:
        cleanup_backup(backup)
        fsync_directory(parent)
        return PublicationResult(committed=True, backup_retained=False, backup_path=None)
    except Exception:
        # Cleanup is strictly post-commit. Never remove or roll back the durable new output.
        if os.path.lexists(backup):
            seal_surviving_backup(backup)
        fsync_directory(parent)
        return PublicationResult(
            committed=True,
            backup_retained=os.path.lexists(backup),
            backup_path=backup if os.path.lexists(backup) else None,
        )

def build_package(raw_root: Path, output_dir: Path, repository: Path,
                  systemd_mode: str, systemd_evidence: Path | None,
                  replace: bool = False) -> PublicationResult:
    raw = authenticated_source(raw_root, repository)
    if systemd_mode not in {"unavailable", "correlated"}:
        HISTORICAL.fail("PACKAGE_LEDGER_INVALID", "systemd mode must be unavailable or correlated")
    if (systemd_mode == "correlated") != (systemd_evidence is not None):
        HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_REQUIRED", "systemd mode/evidence mismatch")
    systemd = (HISTORICAL.verify_systemd_evidence(systemd_evidence)
               if systemd_evidence is not None else None)
    systemd_status = CORRELATED_STATUS if systemd is not None else UNAVAILABLE_STATUS
    result_rows = _source_to_result_rows(raw.observations)
    effects = _effect_rows(result_rows)
    if len(result_rows) != 243 or len(effects) != 27:
        raise VerificationError("source result cardinality is not exact 27/243")
    provenance = _provenance_document(raw.provenance)
    provenance["execution_identity"]["systemd_unit"] = "NOT_RECORDED_BY_CANONICAL_HARNESS"
    provenance["execution_identity"]["systemd_invocation_id"] = "NOT_RECORDED_BY_CANONICAL_HARNESS"
    provenance["supplemental_systemd"] = (
        systemd if systemd is not None else {"classification": UNAVAILABLE_STATUS}
    )
    summary = _summary_document()
    summary["statuses"] = {
        "capture_status": "COMPLETE",
        "historical_validation_status": "PASS",
        "scientific_characterization": "CHARACTERIZED_NO_SELECT",
        "product_selection_status": "NOT_ISSUED",
        "systemd_correlation_status": systemd_status,
    }
    documents = {
        "README.md": _readme(effects).encode("utf-8"),
        "provenance.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode(),
        "results.tsv": _tsv_bytes(RESULT_COLUMNS, result_rows),
        "effects.tsv": _tsv_bytes(EFFECT_COLUMNS, effects),
        "summary.json": (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
    }
    if systemd_evidence is not None:
        for name in SUPPLEMENTAL_FILES:
            documents[name] = (systemd_evidence / Path(name).name).read_bytes()
    ledger_lines: list[str] = []
    for name in expected_ledger_files(systemd_status):
        digest = hashlib.sha256(documents[name]).hexdigest()
        ledger_lines.append(f"{digest}  {name}\n")
    documents["SHA256SUMS"] = "".join(ledger_lines).encode("ascii")
    return atomic_replace_generated(output_dir, documents, replace=replace)

def verify_package(root: Path, repository: Path, trusted_revision: str,
                   git_blob: Callable[[Path, str, str], bytes]) -> Mapping[str, Any]:
    ledger = verify_trusted_ledger(root, repository, trusted_revision, git_blob)
    results = _read_tsv(root / "results.tsv", RESULT_COLUMNS)
    effects = _read_tsv(root / "effects.tsv", EFFECT_COLUMNS)
    _verify_result_semantics(results)
    _verify_effect_semantics(results, effects)
    provenance, summary = _verify_documents(root)
    execution = provenance.get("execution_identity")
    if (not isinstance(execution, dict)
            or execution.get("systemd_unit") != "NOT_RECORDED_BY_CANONICAL_HARNESS"
            or execution.get("systemd_invocation_id") != "NOT_RECORDED_BY_CANONICAL_HARNESS"):
        HISTORICAL.fail("CANONICAL_SYSTEMD_SENTINEL_MISMATCH", "canonical systemd sentinel drift")
    statuses = summary.get("statuses")
    base_statuses = {
        "capture_status": "COMPLETE",
        "historical_validation_status": "PASS",
        "scientific_characterization": "CHARACTERIZED_NO_SELECT",
        "product_selection_status": "NOT_ISSUED",
    }
    if (not isinstance(statuses, dict)
            or {key: statuses.get(key) for key in base_statuses} != base_statuses
            or frozenset(statuses) != frozenset((*base_statuses, "systemd_correlation_status"))):
        raise VerificationError("separated status contract mismatch")
    systemd_status = statuses["systemd_correlation_status"]
    if tuple(ledger) != expected_ledger_files(systemd_status):
        HISTORICAL.fail("PACKAGE_LEDGER_INVALID", "ledger path set disagrees with systemd mode")
    if systemd_status == CORRELATED_STATUS:
        supplemental = HISTORICAL.verify_systemd_evidence(root / "systemd-correlated")
        if provenance.get("supplemental_systemd") != supplemental:
            HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_HASH_MISMATCH", "provenance supplemental projection mismatch")
    elif (os.path.lexists(root / "systemd-correlated")
          or provenance.get("supplemental_systemd") != {"classification": UNAVAILABLE_STATUS}):
        HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_REQUIRED", "unavailable mode contains supplemental evidence")
    return {"status": "PASS", "cells": len(results), "files": len(effects),
            "run_id": SOURCE_RUN_ID, "statuses": statuses}

def git_blob(repository: Path, revision: str, repo_path: str) -> bytes:
    result = subprocess.run(("git", "cat-file", "blob", f"{revision}:{repo_path}"),
                            cwd=repository, check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        HISTORICAL.fail("TRUSTED_LEDGER_MISMATCH", "trusted Git blob is unavailable")
    return result.stdout

def result_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_new02_results.py")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repository", type=Path, required=True)
    build.add_argument("--raw-run", type=Path, required=True)
    build.add_argument("--package", type=Path, required=True)
    build.add_argument("--systemd-mode", choices=("unavailable", "correlated"), required=True)
    build.add_argument("--systemd-evidence", type=Path)
    build.add_argument("--replace", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--repository", type=Path, required=True)
    verify.add_argument("--package", type=Path, required=True)
    verify.add_argument("--trusted-revision", required=True)
    return parser

def result_main(argv: Sequence[str] | None = None) -> int:
    arguments = result_parser().parse_args(argv)
    try:
        if arguments.command == "build":
            if ((arguments.systemd_mode == "correlated")
                    != (arguments.systemd_evidence is not None)):
                HISTORICAL.fail("SUPPLEMENTAL_EVIDENCE_REQUIRED", "mode/evidence arguments disagree")
            publication = build_package(
                arguments.raw_run, arguments.package, arguments.repository,
                arguments.systemd_mode, arguments.systemd_evidence,
                replace=arguments.replace,
            )
            print("NEW02_RESULT_BUILD=PASS_UNTRUSTED "
                  "commit_ledger_before_release_verification=true "
                  f"backup_retained={str(publication.backup_retained).lower()}")
            return 0
        result = verify_package(arguments.package, arguments.repository,
                                arguments.trusted_revision, git_blob)
        print("NEW02_RESULT_VERIFICATION=PASS "
              f"cells={result['cells']} files={result['files']} run_id={result['run_id']} "
              f"systemd={result['statuses']['systemd_correlation_status']}")
        return 0
    except HISTORICAL.HistoricalValidationError as exc:
        print(f"NEW02_RESULT_VERIFICATION=FAIL code={exc.code}", file=sys.stderr)
        return 2
    except (VerificationError, OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"NEW02_RESULT_VERIFICATION=FAIL code=RESULT_PACKAGE_INVALID detail={type(exc).__name__}",
              file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(result_main())
```

`atomic_replace_generated` stages the entire package directory beside the destination, including the fixed source/test/wrapper files plus exactly the mode-appropriate supplemental directory, and fsyncs it recursively. Its commit point is the successful stage-to-destination rename followed by parent-directory fsync. Only failures before that point roll back. Backup cleanup is post-commit best effort: a cleanup error must leave the complete new output in place, seal any surviving (possibly partially deleted) rollback directory read-only, and report `backup_retained=true`; it must never replace the new output with a damaged backup. `test_generation_directory_swap_rolls_back` injects a pre-commit rename/fsync failure and requires exact old-output restoration. `test_partial_backup_cleanup_retains_committed_generation` injects a cleanup callable that deletes one backup leaf and then raises; it asserts the newly committed package still verifies, the surviving backup is present, the deleted backup leaf stays deleted, and `PublicationResult(committed=True, backup_retained=True, ...)` is returned. `verify_package` trusts only a committed `SHA256SUMS` blob at an exact 40-character `--trusted-revision`. Correlated mode requires and validates the three ledger-bound supplemental files; unavailable mode requires their absence and records only `SYSTEMD_EVIDENCE_UNAVAILABLE`.

### Complete executable test support

The test module loads the historical validator once as `HISTORICAL`, then aliases only its public types for annotations. The following support bodies are exact; no `pass`, `...`, `NotImplementedError`, dynamically injected tests, or fixture that copies the 1.7 GiB publication is permitted.

```python
import ast
import contextlib
import copy
import csv
import hashlib
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from unittest import mock

def load_sibling(module_name: str, filename: str) -> Any:
    path = Path(__file__).resolve().with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load sibling module: {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

if "HISTORICAL" not in globals():
    HISTORICAL = load_sibling("new02_test_historical", "verify_new02_historical.py")
if "RESULTS" not in globals():
    RESULTS = load_sibling("new02_test_results", "verify_new02_results.py")

def run_cli(script: Path, *arguments: str, cwd: Path | None = None,
            env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    clean_env = {"LC_ALL": "C", "LANG": "C"}
    if env is not None:
        clean_env.update(env)
    return subprocess.run(
        (sys.executable, str(script), *arguments), cwd=cwd, env=clean_env,
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="strict",
    )

def synthetic_policy() -> Any:
    entries = []
    for index in range(27):
        payload = bytes((index + 1,))
        entries.append(HISTORICAL.InventoryEntry(
            "tuned", f"fixture-{index:02d}.bin", f"fixture-{index:02d}.bin",
            len(payload), hashlib.sha256(payload).hexdigest(),
        ))
    return HISTORICAL.FrozenPolicy(
        inventory=tuple(entries), orders=(4, 6, 8), memory_mib=(16, 64, 256),
        cpu_set="0-15", top_hashes={},
    )

def fixture_time_report() -> bytes:
    values = {
        "Command being timed": '"fixture"',
        "User time (seconds)": "0.00",
        "System time (seconds)": "0.00",
        "Percent of CPU this job got": "100%",
        "Elapsed (wall clock) time (h:mm:ss or m:ss)": "0:00.01",
        "Maximum resident set size (kbytes)": "1",
        "Exit status": "0",
    }
    lines = [f"\t{field}: {values.get(field, '0')}\n"
             for field, _pattern in HISTORICAL.TIME_FIELD_PATTERNS]
    payload = "".join(lines).encode("utf-8")
    HISTORICAL.parse_gnu_time(payload.decode("utf-8"))
    return payload

def _write_fixture_file(path: Path, payload: bytes) -> Mapping[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }

def build_valid_raw_fixture(parent: Path, policy: Any) -> Path:
    if len(policy.cells) != 243:
        raise AssertionError("synthetic fixture policy must contain exactly 243 cells")
    raw = parent / HISTORICAL.RAW_BASENAME
    raw.mkdir()
    (raw / "cells").mkdir()
    inventory_sha = HISTORICAL.inventory_digest(policy)
    grid_sha = HISTORICAL.grid_digest(policy)
    provenance_material = {
        "code_sha": HISTORICAL.EXECUTION_COMMIT,
        "repo_root": HISTORICAL.HISTORICAL_REPO_ROOT,
        "harness_sha256": HISTORICAL.HARNESS_SHA256,
        "test_sha256": HISTORICAL.HARNESS_TEST_SHA256,
        "inventory_sha256": inventory_sha,
        "grid_sha256": grid_sha,
        "preregistration": copy.deepcopy(HISTORICAL.PREREG),
        "tools": copy.deepcopy(HISTORICAL.TOOLS),
        "environment": copy.deepcopy(HISTORICAL.HISTORICAL_ENVIRONMENT),
    }
    run_payload = json.dumps(
        {"schema": "new02-ppmd-oracle-v1", **provenance_material},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    run_id = hashlib.sha256(run_payload).hexdigest()
    provenance_material["run_id"] = run_id
    manifest_rows: list[Mapping[str, object]] = []
    observations: list[Mapping[str, object]] = []
    report = fixture_time_report()
    source_bytes = {
        entry.name: bytes((index + 1,))
        for index, entry in enumerate(policy.inventory)
    }
    for cell in policy.cells:
        cell_dir = raw / "cells" / cell.slug
        cell_dir.mkdir()
        decoded = source_bytes[cell.entry.name]
        archive = b"fixture-archive:" + cell.identifier.encode("utf-8")
        payloads = {
            "payload.7z": archive,
            "decoded.bin": decoded,
            "encode.time": report,
            "decode.time": report,
        }
        artifacts: dict[str, Mapping[str, object]] = {}
        artifact_labels = {
            "payload.7z": "archive", "decoded.bin": "decoded",
            "encode.time": "encode_time", "decode.time": "decode_time",
        }
        for name, payload in payloads.items():
            path = cell_dir / name
            path.write_bytes(payload)
            relative = path.relative_to(raw).as_posix()
            record = {"relative_path": relative,
                      "sha256": hashlib.sha256(payload).hexdigest(),
                      "size_bytes": len(payload)}
            artifacts[artifact_labels[name]] = record
            manifest_rows.append({"path": relative, "sha256": record["sha256"],
                                  "size_bytes": record["size_bytes"]})
        artifacts["input"] = {
            "relative_path": cell.entry.source_operand,
            "sha256": cell.entry.sha256,
            "size_bytes": cell.entry.size_bytes,
        }
        commands = HISTORICAL.expected_commands(cell)
        method = (f"PPMD:o{cell.order}:mem"
                  f"{HISTORICAL.expected_memory_exponent(cell.entry.size_bytes, cell.memory_mib)}")
        listing = ("Method = PPMD\n----------\n"
                   f"Path = {cell.entry.name}\nSize = {cell.entry.size_bytes}\n"
                   f"Method = {method}\n")
        phase = lambda command: {
            "command": command, "returncode": 0, "elapsed_seconds": 0.01,
            "peak_rss_kib": 1, "stdout": "", "stderr": "",
        }
        observations.append({
            "schema": "new02-ppmd-oracle-v1", "run_id": run_id,
            "code_sha": HISTORICAL.EXECUTION_COMMIT,
            "inventory_sha256": inventory_sha, "grid_sha256": grid_sha,
            "preregistration": copy.deepcopy(HISTORICAL.PREREG),
            "tools": copy.deepcopy(HISTORICAL.TOOLS),
            "cell": cell.identifier, "cohort": cell.entry.cohort,
            "file": cell.entry.name, "relative_path": cell.entry.relative_path,
            "order": cell.order, "memory_mib": cell.memory_mib, "cpu_set": "0-15",
            "input_bytes": cell.entry.size_bytes, "input_sha256": cell.entry.sha256,
            "archive_bytes": len(archive),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "decoded_bytes": len(decoded),
            "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
            "encode": phase(commands["encode"]),
            "archive_inspection": {
                "command": commands["inspect"], "returncode": 0,
                "stdout": listing, "stderr": "", "method": method,
                "member_paths": [cell.entry.name],
            },
            "decode": phase(commands["decode"]),
            "cmp_command": commands["compare"], "cmp_returncode": 0,
            "cmp_equal": True, "sha256_equal": True, "round_trip": True,
            "artifacts": artifacts,
        })
    observations_bytes = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in observations
    )
    provenance = {
        "schema": "new02-ppmd-oracle-v1", "cpu_set": policy.cpu_set,
        "orders": list(policy.orders), "memory_mib": list(policy.memory_mib),
        "observation_count": len(policy.cells), "publication": "all-or-nothing",
        "inventory": HISTORICAL.expected_inventory_document(policy),
        "provenance": provenance_material,
    }
    top_payloads = {
        "observations.jsonl": observations_bytes,
        "provenance.json": (json.dumps(provenance, sort_keys=True, indent=2) + "\n").encode(),
    }
    for name, payload in top_payloads.items():
        (raw / name).write_bytes(payload)
        manifest_rows.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest(),
                              "size_bytes": len(payload)})
    directories = sorted(["cells", *(f"cells/{cell.slug}" for cell in policy.cells)])
    manifest = {
        "schema": "new02-ppmd-oracle-v1", "status": "STAGED",
        "observation_count": len(policy.cells), "directories": directories,
        "entries": sorted(manifest_rows, key=lambda row: str(row["path"])),
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    (raw / "MANIFEST.json").write_bytes(manifest_bytes)
    complete = {
        "schema": "new02-ppmd-oracle-v1", "status": "COMPLETE",
        "final_namespace": HISTORICAL.RAW_NAMESPACE,
        "observation_count": len(policy.cells),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    (raw / "COMPLETE").write_text(
        json.dumps(complete, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    for path in raw.rglob("*"):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(raw, 0o555)
    return raw

@contextlib.contextmanager
def fixture_identity(raw: Path, policy: Any) -> Iterator[None]:
    provenance = json.loads((raw / "provenance.json").read_text(encoding="utf-8"))["provenance"]
    with mock.patch.multiple(
        HISTORICAL,
        INVENTORY_SHA256=provenance["inventory_sha256"],
        GRID_SHA256=provenance["grid_sha256"],
        RAW_RUN_ID=provenance["run_id"],
    ):
        yield

def mutable_fixture_copy(source: Path, parent: Path) -> Path:
    target = parent / source.name
    shutil.copytree(source, target)
    for path in target.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(target, 0o755)
    return target

def seal_fixture(raw: Path) -> None:
    for path in sorted(raw.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(raw, 0o555)

def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def read_rows(raw: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (raw / "observations.jsonl").read_text().splitlines()]

def refresh_envelope(raw: Path, *, artifact_paths: Sequence[str] = ()) -> None:
    manifest_path = raw / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    touched = {"observations.jsonl", "provenance.json", *artifact_paths}
    indexed = {entry["path"]: entry for entry in manifest["entries"]}
    for relative in touched:
        payload = raw / relative
        indexed[relative]["sha256"] = hashlib.sha256(payload.read_bytes()).hexdigest()
        indexed[relative]["size_bytes"] = payload.stat().st_size
    manifest["entries"] = [indexed[name] for name in sorted(indexed)]
    write_json(manifest_path, manifest)
    complete = json.loads((raw / "COMPLETE").read_text(encoding="utf-8"))
    complete["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    write_json(raw / "COMPLETE", complete)

def apply_raw_envelope_mutation(raw: Path, policy: Any, name: str) -> Path:
    del policy
    artifact = next((raw / "cells").glob("*/payload.7z"))
    if name == "basename":
        moved = raw.with_name("wrong-raw-basename")
        raw.rename(moved)
        return moved
    if name == "void-sibling":
        (raw.parent / f"{raw.name}.VOID.jsonl").write_text("{}\n")
    elif name == "root-symlink":
        backing = raw.with_name(raw.name + ".backing")
        raw.rename(backing)
        raw.symlink_to(backing, target_is_directory=True)
    elif name == "missing-file":
        artifact.unlink()
    elif name == "extra-file":
        (raw / "extra").write_bytes(b"x")
    elif name == "file-symlink":
        target = artifact.with_name("decoded.bin")
        artifact.unlink()
        artifact.symlink_to(target.name)
    elif name == "hardlink":
        target = artifact.with_name("decoded.bin")
        target.unlink()
        os.link(artifact, target)
    elif name == "writable-file": pass
    elif name == "writable-directory": pass
    else:
        manifest_path = raw / "MANIFEST.json"
        complete_path = raw / "COMPLETE"
        manifest = json.loads(manifest_path.read_text())
        complete = json.loads(complete_path.read_text())
        if name == "manifest-remove": manifest["entries"].pop()
        elif name == "manifest-duplicate": manifest["entries"][-1] = copy.deepcopy(manifest["entries"][0])
        elif name == "manifest-order": manifest["entries"][0], manifest["entries"][1] = manifest["entries"][1], manifest["entries"][0]
        elif name == "manifest-size": manifest["entries"][0]["size_bytes"] += 1
        elif name == "manifest-hash":
            payload = artifact.read_bytes()
            artifact.write_bytes(bytes((payload[0] ^ 1,)) + payload[1:])
        elif name == "manifest-status": manifest["status"] = "COMPLETE"
        elif name == "complete-status": complete["status"] = "STAGED"
        elif name == "complete-count": complete["observation_count"] -= 1
        elif name == "complete-namespace": complete["final_namespace"] += "-wrong"
        elif name == "complete-manifest": complete["manifest_sha256"] = "0" * 64
        elif name == "manifest-schema": manifest["extra"] = True
        elif name == "complete-schema": complete["extra"] = True
        else: raise AssertionError(f"unknown raw-envelope mutation: {name}")
        if name != "manifest-hash":
            write_json(manifest_path, manifest)
            if name not in {"complete-status", "complete-count", "complete-namespace",
                            "complete-manifest", "complete-schema"}:
                complete["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        write_json(complete_path, complete)
    seal_fixture(raw if raw.is_dir() and not raw.is_symlink() else raw.parent)
    if name == "writable-file": os.chmod(artifact, 0o644)
    if name == "writable-directory": os.chmod(artifact.parent, 0o755)
    return raw

def apply_semantic_mutation(raw: Path, policy: Any, name: str) -> None:
    provenance = json.loads((raw / "provenance.json").read_text())
    material = provenance["provenance"]
    rows = read_rows(raw)
    row = rows[0]
    touched: list[str] = []
    if name == "provenance-schema": provenance["extra"] = True
    elif name == "provenance-repository": material["repo_root"] += "-wrong"
    elif name == "provenance-environment": material["environment"]["LANG"] = "wrong"
    elif name == "provenance-run": material["run_id"] = "0" * 64
    elif name == "provenance-code": material["code_sha"] = "0" * 40
    elif name == "inventory": provenance["inventory"][0]["size_bytes"] += 1
    elif name == "grid": material["grid_sha256"] = "0" * 64
    elif name.startswith("prereg-provenance-"):
        prereg = material["preregistration"]
        suffix = name.removeprefix("prereg-provenance-")
        if suffix == "missing": prereg.pop("path")
        elif suffix == "extra": prereg["extra"] = True
        elif suffix == "path": prereg["path"] += "-wrong"
        elif suffix == "repo-path": prereg["repo_path"] += "-wrong"
        elif suffix == "blob": prereg["git_blob_sha"] = "0" * 40
        elif suffix == "sha256": prereg["sha256"] = "0" * 64
    elif name.startswith("prereg-row-"):
        prereg = row["preregistration"]
        suffix = name.removeprefix("prereg-row-")
        if suffix == "missing": prereg.pop("path")
        elif suffix == "extra": prereg["extra"] = True
        else: prereg["sha256"] = "0" * 64
    elif name == "harness": material["harness_sha256"] = "0" * 64
    elif name == "harness-test": material["test_sha256"] = "0" * 64
    elif name == "tool": material["tools"]["7z"]["path"] = "/tmp/7z"
    elif name == "row-order": rows[0], rows[1] = rows[1], rows[0]
    elif name == "row-schema": row["extra"] = True
    elif name in {"encode-command", "inspect-command", "decode-command", "cmp-command"}:
        key = {"encode-command": "encode", "inspect-command": "archive_inspection",
               "decode-command": "decode"}.get(name)
        command = row["cmp_command"] if key is None else row[key]["command"]
        command[0] = "/tmp/wrong"
    elif name == "archive-size": row["archive_bytes"] = 0
    elif name == "artifact": row["artifacts"]["archive"]["relative_path"] += "-wrong"
    elif name == "decoded": row["decoded_bytes"] += 1
    elif name == "cmp-claim": row["cmp_equal"] = False
    elif name == "sha-claim": row["sha256_equal"] = False
    elif name == "listing": row["archive_inspection"]["stdout"] = "Method = LZMA2\n"
    elif name == "timing":
        relative = row["artifacts"]["encode_time"]["relative_path"]
        report = (raw / relative).read_text().replace("0:00.01", "0:00.02")
        (raw / relative).write_text(report)
        row["artifacts"]["encode_time"]["sha256"] = hashlib.sha256(report.encode()).hexdigest()
        row["artifacts"]["encode_time"]["size_bytes"] = len(report.encode())
        touched.append(relative)
    elif name == "return-code": row["encode"]["returncode"] = 1
    elif name == "bool-return-code": row["encode"]["returncode"] = True
    elif name == "error-marker-stdout": row["encode"]["stdout"] = "warning"
    elif name == "error-marker-stderr": row["encode"]["stderr"] = "error"
    else: raise AssertionError(f"unknown semantic mutation: {name}")
    write_json(raw / "provenance.json", provenance)
    (raw / "observations.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in rows)
    )
    refresh_envelope(raw, artifact_paths=touched)
    seal_fixture(raw)

def systemd_payloads() -> tuple[bytes, bytes]:
    show_values = {
        "Result": "success", "NRestarts": "0", "ExecMainStartTimestamp": "",
        "ExecMainExitTimestamp": "", "ExecMainCode": "0", "ExecMainStatus": "0",
        "Id": HISTORICAL.USER_UNIT, "Names": HISTORICAL.USER_UNIT,
        "Description": HISTORICAL.USER_UNIT, "LoadState": "not-found",
        "ActiveState": "inactive", "SubState": "dead", "InvocationID": "",
    }
    show = "".join(f"{key}={show_values[key]}\n" for key in sorted(show_values)).encode()
    rows = []
    for keys, message in zip(HISTORICAL.JOURNAL_KEY_SETS,
                             HISTORICAL.JOURNAL_MESSAGES, strict=True):
        row = {key: "fixture" for key in keys}
        row.update({"USER_UNIT": HISTORICAL.USER_UNIT,
                    "USER_INVOCATION_ID": HISTORICAL.USER_INVOCATION_ID,
                    "MESSAGE": message})
        rows.append(row)
    journal = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows)
    HISTORICAL.parse_systemctl_show(show)
    HISTORICAL.parse_journal_bytes(journal)
    return show, journal

def build_systemd_fixture(parent: Path) -> Path:
    directory = parent / "systemd-correlated"
    directory.mkdir()
    show, journal = systemd_payloads()
    tools = HISTORICAL.production_tools(lambda argv: b"")
    capture = {
        "schema": "new02-systemd-correlation-v1",
        "classification": "CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF",
        "host": "arcana-devs", "user_unit": HISTORICAL.USER_UNIT,
        "user_invocation_id": HISTORICAL.USER_INVOCATION_ID,
        "run_id": HISTORICAL.RAW_RUN_ID, "raw_namespace": HISTORICAL.RAW_NAMESPACE,
        "journal_record_count": 3,
        "systemctl_show_sha256": hashlib.sha256(show).hexdigest(),
        "journalctl_user_unit_sha256": hashlib.sha256(journal).hexdigest(),
        "start_correlated": True, "exit_proven": False, "restart_history_proven": False,
        "tools": {name: {"path": str(tool.path), "realpath": str(tool.realpath),
                         "sha256": tool.sha256}
                  for name, tool in (("systemctl", tools.systemctl),
                                     ("journalctl", tools.journalctl),
                                     ("hostname", tools.hostname), ("python", tools.python))},
    }
    (directory / "systemctl-show.txt").write_bytes(show)
    (directory / "journalctl-user-unit.jsonl").write_bytes(journal)
    write_json(directory / "capture.json", capture)
    seal_fixture(directory)
    return directory

def apply_systemd_mutation(directory: Path, name: str) -> Callable[[], object]:
    if name == "missing":
        return lambda: HISTORICAL.verify_systemd_evidence(directory / "absent")
    if name == "runtime":
        runtime = HISTORICAL.RuntimeIdentity(directory, Path("/run/user/1"), 1)
        return lambda: HISTORICAL.validate_user_bus(runtime)
    for path in directory.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(directory, 0o755)
    capture_path = directory / "capture.json"
    show_path = directory / "systemctl-show.txt"
    journal_path = directory / "journalctl-user-unit.jsonl"
    capture = json.loads(capture_path.read_text())
    if name == "tool": capture["tools"]["python"]["sha256"] = "0" * 64
    elif name == "show-hash": show_path.write_bytes(show_path.read_bytes() + b"x")
    elif name == "journal-hash": journal_path.write_bytes(journal_path.read_bytes() + b"x")
    elif name == "overclaim": capture["exit_proven"] = True
    elif name == "show-schema":
        show_path.write_text(show_path.read_text().replace("Result=success", "Result=failed"))
        capture["systemctl_show_sha256"] = hashlib.sha256(show_path.read_bytes()).hexdigest()
    elif name == "path-set": (directory / "extra").write_bytes(b"x")
    else:
        rows = [json.loads(line) for line in journal_path.read_text().splitlines()]
        if name == "unit": rows[0]["USER_UNIT"] = "wrong.service"
        elif name == "invocation": rows[0]["USER_INVOCATION_ID"] = "0" * 32
        elif name == "command": rows[0]["MESSAGE"] = rows[0]["MESSAGE"].replace(
            "/usr/bin/python3", "/tmp/python3")
        elif name == "namespace": rows[0]["MESSAGE"] = rows[0]["MESSAGE"].replace(
            HISTORICAL.RAW_NAMESPACE, "/tmp/wrong")
        elif name == "unsafe-field": rows[0]["Environment"] = "x"
        elif name == "secret": rows[0]["MESSAGE"] += " token=secret"
        elif name == "journal-schema": rows[0].pop("MESSAGE")
        else: raise AssertionError(f"unknown systemd mutation: {name}")
        journal_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        capture["journalctl_user_unit_sha256"] = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    write_json(capture_path, capture)
    seal_fixture(directory)
    return lambda: HISTORICAL.verify_systemd_evidence(directory)

def copy_package_fixture(source: Path, parent: Path) -> Path:
    destination = parent / "package"
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
    for path in destination.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else (0o555 if path.suffix == ".sh" else 0o444))
    os.chmod(destination, 0o555)
    return destination

def reseal_package(package: Path) -> None:
    for path in sorted(package.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() or path.suffix in {".py", ".sh"} else 0o444)
    os.chmod(package, 0o555)

def apply_package_mutation(package: Path, name: str, results: Any) -> Callable[[], object]:
    for path in package.rglob("*"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(package, 0o755)
    ledger_path = package / "SHA256SUMS"
    committed = ledger_path.read_bytes()
    def rewrite_ledger() -> None:
        status = json.loads((package / "summary.json").read_text())["statuses"]["systemd_correlation_status"]
        ledger_path.write_bytes(results.ledger_bytes(package, results.expected_ledger_files(status)))
    if name == "derived-tamper": (package / "README.md").write_text("tampered\n")
    elif name == "derived-rehash":
        (package / "README.md").write_text("tampered\n"); rewrite_ledger()
    elif name == "supplemental-rehash":
        target = package / "systemd-correlated" / "systemctl-show.txt"
        target.write_bytes(target.read_bytes() + b"x"); rewrite_ledger()
    elif name == "supplemental-missing":
        target = package / "systemd-correlated" / "capture.json"; target.unlink()
    elif name == "supplemental-hash":
        target = package / "systemd-correlated" / "capture.json"
        target.write_bytes(target.read_bytes() + b"x")
    elif name == "canonical-sentinel":
        value = json.loads((package / "provenance.json").read_text())
        value["execution_identity"]["systemd_unit"] = "fabricated.service"
        write_json(package / "provenance.json", value); rewrite_ledger(); committed = ledger_path.read_bytes()
    elif name == "uncommitted-ledger": committed = b"0" * len(committed)
    elif name == "mode-evidence":
        value = json.loads((package / "summary.json").read_text())
        value["statuses"]["systemd_correlation_status"] = results.UNAVAILABLE_STATUS
        write_json(package / "summary.json", value); rewrite_ledger(); committed = ledger_path.read_bytes()
    elif name == "ledger-schema":
        ledger_path.write_text("not-a-ledger\n"); committed = ledger_path.read_bytes()
    elif name in {"swap-failure", "destination-exists"}:
        reseal_package(package)
        if name == "destination-exists":
            return lambda: results.atomic_replace_generated(package, {}, replace=False)
        def injected_swap_failure() -> object:
            with mock.patch.object(results.os, "rename", side_effect=OSError("injected")):
                return results.atomic_replace_generated(package, {}, replace=True)
        return injected_swap_failure
    else: raise AssertionError(f"unknown package mutation: {name}")
    reseal_package(package)
    return lambda: results.verify_package(
        package, package.parent, "a" * 40,
        lambda repository, revision, repo_path: committed,
    )

def generated_text_has_no_fresh_claim(package: Path) -> None:
    forbidden = ("fresh landed 7z inspection", "fresh 7z inspection")
    documents = [package / name for name in
                 ("README.md", "provenance.json", "summary.json", "results.tsv", "effects.tsv")]
    text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
    if any(value in text for value in forbidden):
        raise AssertionError("generated document retained a fresh-tool claim")
    if "authenticated stored archive-inspection transcript" not in text:
        raise AssertionError("generated document lacks authenticated-stored wording")

def apply_cli_mutation(name: str) -> tuple[int, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        if name == "invalid-data":
            status = HISTORICAL.main(("validate", "--raw-run", "/definitely/absent", "--raw-only"))
        elif name == "git-subprocess":
            with mock.patch.object(HISTORICAL, "verify_raw_publication", return_value=None), \
                 mock.patch.object(HISTORICAL.subprocess, "run",
                                   side_effect=subprocess.SubprocessError("injected")):
                status = HISTORICAL.main(("validate", "--repository", str(REPO_ROOT),
                                          "--raw-run", str(REAL_RAW)))
        elif name == "result-package":
            status = RESULTS.result_main(("verify", "--repository", str(REPO_ROOT),
                                          "--package", "/definitely/absent",
                                          "--trusted-revision", "0" * 40))
        else:
            raise AssertionError(f"unknown CLI mutation: {name}")
    return status, stdout.getvalue() + stderr.getvalue()
```

`build_valid_raw_fixture` is fully synthetic: it writes 27 one-byte registered inputs projected through all 243 cells, generates four stored artifacts per cell, constructs every observation/provenance/manifest/COMPLETE byte, and seals the tree. `fixture_identity` changes only in-process validation pins around a call using a non-production `FrozenPolicy`; the CLI always supplies `FROZEN_POLICY` and has no fixture/pin argument.

### Complete unittest discovery contract

Every test is a method on `unittest.TestCase`. No module-level pytest-style test functions, fixtures, dynamic method injection, or substring filters are permitted.

```python
import unittest
from dataclasses import dataclass

EXPECTED_TESTS = {
    "RepositoryTests": (
        "test_advanced_current_main_with_execution_ancestor_passes",
        "test_stale_tracking_ref_fails",
        "test_execution_object_mutations_fail",
        "test_source_blob_mutations_fail",
    ),
    "RawEnvelopeTests": (
        "test_real_tree_fixed_policy_passes",
        "test_real_manifest_staged_and_marker_complete",
        "test_real_top_hash_mutations_fail_fixed_policy",
        "test_void_sibling_fails",
        "test_topology_mutations_fail",
        "test_manifest_mutations_fail",
        "test_external_inputs_are_identity_checked_not_manifested",
    ),
    "SemanticTests": (
        "test_all_243_cells_pass",
        "test_provenance_mutations_fail",
        "test_command_and_artifact_mutations_fail",
        "test_listing_and_timing_mutations_fail",
        "test_raw_validation_executes_no_capture_tools",
    ),
    "SystemdTests": (
        "test_exact_start_correlation_has_no_exit_or_restart_proof",
        "test_missing_systemd_evidence_is_unavailable",
        "test_journal_identity_mutations_fail",
        "test_show_defaults_cannot_be_promoted_to_proof",
        "test_safe_field_and_secret_mutations_fail",
        "test_production_tool_paths_realpaths_and_hashes_are_fixed",
        "test_runtime_dir_and_user_bus_validation",
        "test_show_and_journal_closed_grammars",
        "test_absolute_no_argument_wrapper",
        "test_atomic_capture_restores_permissions_and_fsyncs",
    ),
    "PackageTests": (
        "test_deterministic_rebuild_is_byte_identical",
        "test_unavailable_and_correlated_modes_are_consistent",
        "test_trusted_revision_requires_committed_ledger_blob",
        "test_generation_directory_swap_rolls_back",
        "test_partial_backup_cleanup_retains_committed_generation",
        "test_result_build_uses_no_landed_oracle_or_fresh_tools",
        "test_package_file_tamper_fails",
        "test_package_rehash_tamper_fails_trusted_ledger",
        "test_supplemental_rehash_tamper_fails_trusted_ledger",
        "test_correlated_status_requires_supplemental_files",
        "test_canonical_sentinels_and_no_select_boundary_are_immutable",
    ),
    "SecurityTests": (
        "test_python_ast_security_floor",
        "test_registered_emitted_and_mutated_error_codes_match",
        "test_cli_output_redacts_evidence_and_remote_urls",
    ),
    "CliTests": (
        "test_cli_failure_is_stable_and_fail_closed",
        "test_cli_reports_separate_success_layers",
    ),
}
EXPECTED_DISCOVERED_COUNT = 42
@dataclass(frozen=True)
class MutationCase:
    name: str
    code: str

def cases(*rows: tuple[str, str]) -> tuple[MutationCase, ...]:
    return tuple(MutationCase(*row) for row in rows)

MUTATION_CASES = {
    "repository": cases(
        ("remote-response", "REPOSITORY_REMOTE_RESPONSE_INVALID"),
        ("stale-tracking", "REPOSITORY_REMOTE_TRACKING_MISMATCH"),
        ("not-ancestor", "EXECUTION_NOT_ANCESTOR"),
        ("missing-execution", "EXECUTION_COMMIT_MISSING"),
        ("execution-type", "EXECUTION_OBJECT_TYPE_MISMATCH"),
        ("execution-tree", "EXECUTION_TREE_MISMATCH"),
        ("missing-blob", "SOURCE_BLOB_MISSING"),
        ("blob-type", "SOURCE_BLOB_TYPE_MISMATCH"),
        ("blob-id", "SOURCE_BLOB_ID_MISMATCH"),
        ("blob-size", "SOURCE_BLOB_SIZE_MISMATCH"),
        ("blob-sha256", "SOURCE_BLOB_SHA256_MISMATCH"),
    ),
    "raw_envelope": cases(
        ("basename", "RAW_NAMESPACE_MISMATCH"), ("void-sibling", "RAW_VOID_SIBLING_PRESENT"),
        ("root-symlink", "RAW_SPECIAL_FILE"), ("missing-file", "RAW_PATH_SET_MISMATCH"),
        ("extra-file", "RAW_PATH_SET_MISMATCH"), ("file-symlink", "RAW_SPECIAL_FILE"),
        ("hardlink", "RAW_LINK_COUNT_MISMATCH"), ("writable-file", "RAW_MODE_MISMATCH"),
        ("writable-directory", "RAW_MODE_MISMATCH"),
        ("manifest-remove", "MANIFEST_ENTRY_SET_MISMATCH"),
        ("manifest-duplicate", "MANIFEST_DUPLICATE_PATH"),
        ("manifest-order", "MANIFEST_ENTRY_ORDER_MISMATCH"),
        ("manifest-size", "MANIFEST_SIZE_MISMATCH"), ("manifest-hash", "MANIFEST_HASH_MISMATCH"),
        ("manifest-status", "MANIFEST_STATUS_MISMATCH"),
        ("complete-status", "COMPLETE_STATUS_MISMATCH"),
        ("complete-count", "COMPLETE_ENVELOPE_MISMATCH"),
        ("complete-namespace", "COMPLETE_ENVELOPE_MISMATCH"),
        ("complete-manifest", "COMPLETE_MANIFEST_MISMATCH"),
        ("manifest-schema", "MANIFEST_SCHEMA_MISMATCH"),
        ("complete-schema", "COMPLETE_SCHEMA_MISMATCH"),
    ),
    "top_hash": cases(
        ("complete", "TOP_COMPLETE_HASH_MISMATCH"),
        ("manifest", "TOP_MANIFEST_HASH_MISMATCH"),
        ("observations", "TOP_OBSERVATIONS_HASH_MISMATCH"),
        ("provenance", "TOP_PROVENANCE_HASH_MISMATCH"),
    ),
    "semantic": cases(
        ("provenance-schema", "PROVENANCE_SCHEMA_MISMATCH"),
        ("provenance-repository", "PROVENANCE_REPOSITORY_MISMATCH"),
        ("provenance-environment", "PROVENANCE_ENVIRONMENT_MISMATCH"),
        ("provenance-run", "PROVENANCE_RUN_ID_MISMATCH"),
        ("provenance-code", "PROVENANCE_CODE_SHA_MISMATCH"),
        ("inventory", "INVENTORY_IDENTITY_MISMATCH"), ("grid", "GRID_IDENTITY_MISMATCH"),
        ("prereg-provenance-missing", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-provenance-extra", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-provenance-path", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-provenance-repo-path", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-provenance-blob", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-provenance-sha256", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-row-missing", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-row-extra", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("prereg-row-value", "PREREGISTRATION_IDENTITY_MISMATCH"),
        ("harness", "HARNESS_IDENTITY_MISMATCH"),
        ("harness-test", "HARNESS_TEST_IDENTITY_MISMATCH"),
        ("tool", "TOOL_IDENTITY_MISMATCH"), ("row-order", "OBSERVATION_GRID_MISMATCH"),
        ("row-schema", "OBSERVATION_SCHEMA_MISMATCH"),
        ("encode-command", "COMMAND_ARRAY_MISMATCH"),
        ("inspect-command", "COMMAND_ARRAY_MISMATCH"),
        ("decode-command", "COMMAND_ARRAY_MISMATCH"),
        ("cmp-command", "COMMAND_ARRAY_MISMATCH"),
        ("archive-size", "ARCHIVE_SIZE_INVALID"),
        ("artifact", "ARTIFACT_IDENTITY_MISMATCH"),
        ("decoded", "DECODED_IDENTITY_MISMATCH"),
        ("cmp-claim", "ROUND_TRIP_CLAIM_MISMATCH"),
        ("sha-claim", "ROUND_TRIP_CLAIM_MISMATCH"),
        ("listing", "LISTING_SEMANTICS_MISMATCH"),
        ("timing", "TIMING_GRAMMAR_MISMATCH"),
        ("return-code", "CELL_RETURN_CODE_MISMATCH"),
        ("bool-return-code", "CELL_RETURN_CODE_MISMATCH"),
        ("error-marker-stdout", "CELL_ERROR_MARKER"),
        ("error-marker-stderr", "CELL_ERROR_MARKER"),
    ),
    "systemd": cases(
        ("tool", "SYSTEMD_TOOL_IDENTITY_MISMATCH"), ("show-hash", "SYSTEMD_SHOW_HASH_MISMATCH"),
        ("journal-hash", "SYSTEMD_JOURNAL_HASH_MISMATCH"),
        ("unit", "SYSTEMD_USER_UNIT_MISMATCH"), ("invocation", "SYSTEMD_INVOCATION_MISMATCH"),
        ("command", "SYSTEMD_COMMAND_MISMATCH"), ("namespace", "SYSTEMD_NAMESPACE_MISMATCH"),
        ("unsafe-field", "SYSTEMD_UNSAFE_FIELD"), ("secret", "SYSTEMD_SECRET_SCAN_FAILED"),
        ("overclaim", "SYSTEMD_OVERCLAIM_REJECTED"),
        ("runtime", "SYSTEMD_RUNTIME_DIR_INVALID"),
        ("show-schema", "SYSTEMD_SHOW_SCHEMA_MISMATCH"),
        ("journal-schema", "SYSTEMD_JOURNAL_SCHEMA_MISMATCH"),
        ("missing", "SYSTEMD_EVIDENCE_UNAVAILABLE"),
        ("path-set", "SYSTEMD_EVIDENCE_PATH_SET_MISMATCH"),
    ),
    "package": cases(
        ("derived-tamper", "PACKAGE_HASH_MISMATCH"),
        ("derived-rehash", "TRUSTED_LEDGER_MISMATCH"),
        ("supplemental-rehash", "TRUSTED_LEDGER_MISMATCH"),
        ("supplemental-missing", "SUPPLEMENTAL_EVIDENCE_REQUIRED"),
        ("supplemental-hash", "SUPPLEMENTAL_EVIDENCE_HASH_MISMATCH"),
        ("canonical-sentinel", "CANONICAL_SYSTEMD_SENTINEL_MISMATCH"),
        ("uncommitted-ledger", "TRUSTED_LEDGER_MISMATCH"),
        ("mode-evidence", "SUPPLEMENTAL_EVIDENCE_REQUIRED"),
        ("swap-failure", "ATOMIC_PUBLICATION_FAILED"),
        ("destination-exists", "ATOMIC_DESTINATION_EXISTS"),
        ("ledger-schema", "PACKAGE_LEDGER_INVALID"),
    ),
    "cli": cases(
        ("invalid-data", "VALIDATION_DATA_ERROR"),
        ("git-subprocess", "VALIDATION_SUBPROCESS_ERROR"),
        ("result-package", "RESULT_PACKAGE_INVALID"),
    ),
}
EXPECTED_MUTATION_COUNTS = {
    "repository": 11, "raw_envelope": 21, "top_hash": 4,
    "semantic": 36, "systemd": 15, "package": 11, "cli": 3,
}

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_ROOT = Path(__file__).resolve().parent
REAL_RAW = Path("/home/dev/cubr-new02-canonical-runs/new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z")

class ContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name)
        self.policy = synthetic_policy()

    def raw(self) -> Path:
        return build_valid_raw_fixture(self.temp, self.policy)

    def assert_raw_mutations(self, category: str, names: set[str]) -> None:
        selected = tuple(case for case in MUTATION_CASES[category] if case.name in names)
        self.assertEqual({case.name for case in selected}, names)
        for index, case in enumerate(selected):
            with self.subTest(name=case.name):
                parent = self.temp / f"mutation-{category}-{index}"
                parent.mkdir()
                source = build_valid_raw_fixture(parent, self.policy)
                for path in source.rglob("*"):
                    os.chmod(path, 0o755 if path.is_dir() else 0o644)
                os.chmod(source, 0o755)
                target = (apply_raw_envelope_mutation(source, self.policy, case.name)
                          if category == "raw_envelope" else source)
                if category == "semantic":
                    apply_semantic_mutation(target, self.policy, case.name)
                with fixture_identity(target.resolve() if target.is_symlink() else target,
                                      self.policy):
                    with self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                        HISTORICAL.verify_raw_publication(target, self.policy)
                self.assertEqual(raised.exception.code, case.code)

    def assert_systemd_mutations(self, names: set[str]) -> None:
        selected = tuple(case for case in MUTATION_CASES["systemd"] if case.name in names)
        self.assertEqual({case.name for case in selected}, names)
        for index, case in enumerate(selected):
            with self.subTest(name=case.name):
                parent = self.temp / f"systemd-{index}"
                parent.mkdir()
                evidence = build_systemd_fixture(parent)
                invocation = apply_systemd_mutation(evidence, case.name)
                with self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                    invocation()
                self.assertEqual(raised.exception.code, case.code)

    def assert_package_mutation(self, name: str) -> None:
        case = next(item for item in MUTATION_CASES["package"] if item.name == name)
        parent = self.temp / f"package-{name}"; parent.mkdir()
        package = copy_package_fixture(PACKAGE_ROOT, parent)
        invocation = apply_package_mutation(package, name, RESULTS)
        with self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
            invocation()
        self.assertEqual(raised.exception.code, case.code)

class RepositoryTests(ContractTestCase):
    def test_advanced_current_main_with_execution_ancestor_passes(self) -> None:
        probe = HISTORICAL.FakeGitProbe.valid()
        evidence = HISTORICAL.verify_repository(REPO_ROOT, probe)
        self.assertEqual(evidence.execution_commit, HISTORICAL.EXECUTION_COMMIT)

    def test_stale_tracking_ref_fails(self) -> None:
        probe = HISTORICAL.FakeGitProbe("b" * 40, "c" * 40, True)
        with self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
            HISTORICAL.verify_repository(REPO_ROOT, probe)
        self.assertEqual(raised.exception.code, "REPOSITORY_REMOTE_TRACKING_MISMATCH")

    def test_execution_object_mutations_fail(self) -> None:
        path = next(iter(HISTORICAL.SOURCE_BLOBS))
        cases = {
            "missing-execution": ({("cat-file", "-e", f"{HISTORICAL.EXECUTION_COMMIT}^{{commit}}"): 1}, "EXECUTION_COMMIT_MISSING"),
            "execution-type": ({("cat-file", "-t", HISTORICAL.EXECUTION_COMMIT): "tree"}, "EXECUTION_OBJECT_TYPE_MISMATCH"),
            "execution-tree": ({("rev-parse", f"{HISTORICAL.EXECUTION_COMMIT}^{{tree}}"): "0" * 40}, "EXECUTION_TREE_MISMATCH"),
        }
        for name, (overrides, code) in cases.items():
            with self.subTest(name=name), self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                HISTORICAL.verify_repository(REPO_ROOT, HISTORICAL.FakeGitProbe(
                    "b" * 40, "b" * 40, True, overrides))
            self.assertEqual(raised.exception.code, code)

    def test_source_blob_mutations_fail(self) -> None:
        path, expected = next(iter(HISTORICAL.SOURCE_BLOBS.items()))
        spec = f"{HISTORICAL.EXECUTION_COMMIT}:{path}"
        mutations = (
            ({("cat-file", "-e", spec): 1}, "SOURCE_BLOB_MISSING"),
            ({("cat-file", "-t", spec): "tree"}, "SOURCE_BLOB_TYPE_MISMATCH"),
            ({("rev-parse", spec): "0" * 40}, "SOURCE_BLOB_ID_MISMATCH"),
            ({("cat-file", "-s", spec): str(expected[1] + 1)}, "SOURCE_BLOB_SIZE_MISMATCH"),
            ({("cat-file", "blob", spec): b"wrong"}, "SOURCE_BLOB_SHA256_MISMATCH"),
        )
        for overrides, code in mutations:
            with self.subTest(code=code), self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                HISTORICAL.verify_repository(REPO_ROOT, HISTORICAL.FakeGitProbe(
                    "b" * 40, "b" * 40, True, overrides))
            self.assertEqual(raised.exception.code, code)

class RawEnvelopeTests(ContractTestCase):
    def test_real_tree_fixed_policy_passes(self) -> None:
        if not REAL_RAW.is_dir(): self.skipTest("NO-TEST-ENV: external immutable publication absent")
        evidence = HISTORICAL.verify_raw_publication(REAL_RAW, HISTORICAL.FROZEN_POLICY)
        self.assertEqual(len(evidence.observations), 243)

    def test_real_manifest_staged_and_marker_complete(self) -> None:
        if not REAL_RAW.is_dir(): self.skipTest("NO-TEST-ENV: external immutable publication absent")
        evidence = HISTORICAL.verify_raw_publication(REAL_RAW, HISTORICAL.FROZEN_POLICY)
        self.assertEqual((evidence.manifest["status"], len(evidence.manifest["entries"])), ("STAGED", 974))
        self.assertEqual(json.loads((REAL_RAW / "COMPLETE").read_text())["status"], "COMPLETE")

    def test_real_top_hash_mutations_fail_fixed_policy(self) -> None:
        if not REAL_RAW.is_dir(): self.skipTest("NO-TEST-ENV: external immutable publication absent")
        for case in MUTATION_CASES["top_hash"]:
            name = {"complete": "COMPLETE", "manifest": "MANIFEST.json",
                    "observations": "observations.jsonl", "provenance": "provenance.json"}[case.name]
            target = self.temp / name.replace("/", "-")
            target.write_bytes((REAL_RAW / name).read_bytes() + b"x")
            with self.subTest(name=case.name), self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                HISTORICAL.verify_fixed_top_file(name, target, HISTORICAL.FROZEN_POLICY)
            self.assertEqual(raised.exception.code, case.code)

    def test_void_sibling_fails(self) -> None:
        self.assert_raw_mutations("raw_envelope", {"void-sibling"})

    def test_topology_mutations_fail(self) -> None:
        self.assert_raw_mutations("raw_envelope", {"basename", "root-symlink", "missing-file",
            "extra-file", "file-symlink", "hardlink", "writable-file", "writable-directory"})

    def test_manifest_mutations_fail(self) -> None:
        self.assert_raw_mutations("raw_envelope", {case.name for case in MUTATION_CASES["raw_envelope"]}
                                  - {"basename", "void-sibling", "root-symlink", "missing-file",
                                     "extra-file", "file-symlink", "hardlink", "writable-file",
                                     "writable-directory"})

    def test_external_inputs_are_identity_checked_not_manifested(self) -> None:
        raw = self.raw()
        with fixture_identity(raw, self.policy):
            evidence = HISTORICAL.verify_raw_publication(raw, self.policy)
        manifested = {entry["path"] for entry in evidence.manifest["entries"]}
        self.assertTrue(all(cell.entry.source_operand not in manifested for cell in self.policy.cells))

class SemanticTests(ContractTestCase):
    def test_all_243_cells_pass(self) -> None:
        raw = self.raw()
        with fixture_identity(raw, self.policy): evidence = HISTORICAL.verify_raw_publication(raw, self.policy)
        self.assertEqual([row["cell"] for row in evidence.observations],
                         [cell.identifier for cell in self.policy.cells])

    def test_provenance_mutations_fail(self) -> None:
        self.assert_raw_mutations("semantic", {case.name for case in MUTATION_CASES["semantic"]
            if case.name.startswith(("provenance", "prereg", "harness", "tool"))
            or case.name in {"inventory", "grid"}})

    def test_command_and_artifact_mutations_fail(self) -> None:
        self.assert_raw_mutations("semantic", {"row-order", "row-schema", "encode-command",
            "inspect-command", "decode-command", "cmp-command", "archive-size", "artifact",
            "decoded", "cmp-claim", "sha-claim", "return-code", "bool-return-code"})

    def test_listing_and_timing_mutations_fail(self) -> None:
        self.assert_raw_mutations("semantic", {"listing", "timing", "error-marker-stdout",
                                                "error-marker-stderr"})

    def test_raw_validation_executes_no_capture_tools(self) -> None:
        raw = self.raw()
        with fixture_identity(raw, self.policy), \
             mock.patch.object(HISTORICAL.subprocess, "run", side_effect=AssertionError), \
             mock.patch.object(HISTORICAL.os, "system", side_effect=AssertionError), \
             mock.patch.object(shutil, "which", side_effect=AssertionError):
            self.assertEqual(len(HISTORICAL.verify_raw_publication(raw, self.policy).observations), 243)

class SystemdTests(ContractTestCase):
    def test_exact_start_correlation_has_no_exit_or_restart_proof(self) -> None:
        value = HISTORICAL.verify_systemd_evidence(build_systemd_fixture(self.temp))
        self.assertEqual((value["classification"], value["exit_proven"], value["restart_history_proven"]),
                         ("CORRELATED_START_ONLY_NO_EXIT_OR_RESTART_PROOF", False, False))

    def test_missing_systemd_evidence_is_unavailable(self) -> None:
        self.assert_systemd_mutations({"missing"})

    def test_journal_identity_mutations_fail(self) -> None:
        self.assert_systemd_mutations({"unit", "invocation", "command", "namespace"})

    def test_show_defaults_cannot_be_promoted_to_proof(self) -> None:
        self.assert_systemd_mutations({"overclaim"})

    def test_safe_field_and_secret_mutations_fail(self) -> None:
        self.assert_systemd_mutations({"unsafe-field", "secret"})

    def test_production_tool_paths_realpaths_and_hashes_are_fixed(self) -> None:
        self.assert_systemd_mutations({"tool"})

    def test_runtime_dir_and_user_bus_validation(self) -> None:
        self.assert_systemd_mutations({"runtime"})

    def test_show_and_journal_closed_grammars(self) -> None:
        show, journal = systemd_payloads()
        self.assertEqual(len(HISTORICAL.parse_systemctl_show(show)), 13)
        self.assertEqual(len(HISTORICAL.parse_journal_bytes(journal)), 3)
        self.assert_systemd_mutations({"show-schema", "journal-schema", "show-hash",
                                       "journal-hash", "path-set"})

    def test_absolute_no_argument_wrapper(self) -> None:
        wrapper = PACKAGE_ROOT / "capture_new02_systemd_evidence.sh"
        if not wrapper.is_file(): self.skipTest("RED fixture: wrapper not implemented yet")
        one_arg = subprocess.run((str(wrapper.resolve()), "x"), check=False,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        relative = subprocess.run(("/usr/bin/bash", wrapper.name), cwd=PACKAGE_ROOT, check=False,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((one_arg.returncode, relative.returncode), (64, 64))

    def test_atomic_capture_restores_permissions_and_fsyncs(self) -> None:
        parent = self.temp / "parent"; parent.mkdir(); os.chmod(parent, 0o555)
        target = parent / "evidence"
        HISTORICAL.atomic_publish(target, {"a": b"a", "b": b"b"})
        self.assertEqual((stat.S_IMODE(parent.stat().st_mode), stat.S_IMODE(target.stat().st_mode)),
                         (0o555, 0o555))

class PackageTests(ContractTestCase):
    def test_deterministic_rebuild_is_byte_identical(self) -> None:
        if not REAL_RAW.is_dir(): self.skipTest("NO-TEST-ENV: external immutable publication absent")
        first, second = self.temp / "first", self.temp / "second"
        with mock.patch.object(RESULTS.HISTORICAL, "verify_repository", return_value=None):
            RESULTS.build_package(REAL_RAW, first, REPO_ROOT, "unavailable", None)
            RESULTS.build_package(REAL_RAW, second, REPO_ROOT, "unavailable", None)
        self.assertEqual({p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()},
                         {p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()})

    def test_unavailable_and_correlated_modes_are_consistent(self) -> None:
        summary = RESULTS._summary_document()
        self.assertEqual((summary["verdict"]["outcome"], summary["verdict"]["go_no_go"]),
                         ("CHARACTERIZED_NO_SELECT", "NOT_ISSUED"))

    def test_trusted_revision_requires_committed_ledger_blob(self) -> None:
        calls: list[tuple[str, ...]] = []
        def git_success(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            command = tuple(argv); calls.append(command)
            self.assertEqual(command, ("git", "cat-file", "blob",
                "a" * 40 + ":documentation/evidence/SHA256SUMS"))
            self.assertEqual(kwargs.get("cwd"), REPO_ROOT)
            return subprocess.CompletedProcess(command, 0, b"trusted-ledger\n", b"")
        with mock.patch.object(RESULTS.subprocess, "run", side_effect=git_success):
            self.assertEqual(RESULTS.git_blob(
                REPO_ROOT, "a" * 40, "documentation/evidence/SHA256SUMS"),
                b"trusted-ledger\n")
        self.assertEqual(len(calls), 1)
        def git_failure(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            del kwargs
            command = tuple(argv)
            if command[:3] != ("git", "cat-file", "blob"):
                raise AssertionError(f"unexpected subprocess: {command}")
            return subprocess.CompletedProcess(command, 1, b"", b"missing")
        with mock.patch.object(RESULTS.subprocess, "run", side_effect=git_failure):
            with self.assertRaises(HISTORICAL.HistoricalValidationError) as raised:
                RESULTS.git_blob(REPO_ROOT, "a" * 40, "documentation/evidence/SHA256SUMS")
        self.assertEqual(raised.exception.code, "TRUSTED_LEDGER_MISMATCH")
        self.assert_package_mutation("uncommitted-ledger")
        self.assert_package_mutation("ledger-schema")

    def test_generation_directory_swap_rolls_back(self) -> None:
        self.assert_package_mutation("swap-failure")
        self.assert_package_mutation("destination-exists")

    def test_partial_backup_cleanup_retains_committed_generation(self) -> None:
        package = copy_package_fixture(PACKAGE_ROOT, self.temp)
        def partial(path: Path) -> None:
            next(item for item in path.rglob("*") if item.is_file()).unlink()
            raise OSError("partial cleanup")
        result = RESULTS.atomic_replace_generated(package, {}, replace=True, cleanup_backup=partial)
        self.assertTrue(result.committed and result.backup_retained and package.is_dir())

    def test_result_build_uses_no_landed_oracle_or_fresh_tools(self) -> None:
        raw = self.raw()
        source_dir = self.temp / "result-source"; source_dir.mkdir()
        for name in RESULTS.PRESERVED_FILES:
            original = PACKAGE_ROOT / name
            target = source_dir / name
            target.write_bytes(original.read_bytes() if original.is_file() else b"test fixture\n")
        output = self.temp / "built-package"
        subprocess_calls: list[tuple[str, ...]] = []
        which_calls: list[str] = []
        def guarded_run(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            command = tuple(argv); subprocess_calls.append(command)
            if command[:3] == ("git", "cat-file", "blob"):
                return subprocess.CompletedProcess(command, 0, b"authenticated-git-object", b"")
            raise AssertionError(f"fresh subprocess execution forbidden: {command}")
        def guarded_which(name: str) -> str | None:
            which_calls.append(name)
            if name == "git":
                return "/usr/bin/git"
            raise AssertionError(f"fresh tool lookup forbidden: {name}")
        repository_evidence = HISTORICAL.RepositoryEvidence(
            current_main="b" * 40, execution_commit=HISTORICAL.EXECUTION_COMMIT,
            execution_tree=HISTORICAL.EXECUTION_TREE,
            source_blobs={path: value[0] for path, value in HISTORICAL.SOURCE_BLOBS.items()},
        )
        with fixture_identity(raw, self.policy), \
             mock.patch.object(RESULTS.HISTORICAL, "FROZEN_POLICY", self.policy), \
             mock.patch.object(RESULTS.HISTORICAL, "verify_repository",
                               return_value=repository_evidence), \
             mock.patch.object(RESULTS, "__file__", str(source_dir / "verify_new02_results.py")), \
             mock.patch.object(RESULTS.subprocess, "run", side_effect=guarded_run), \
             mock.patch.object(RESULTS.shutil, "which", side_effect=guarded_which):
            publication = RESULTS.build_package(
                raw, output, REPO_ROOT, "unavailable", None, replace=False
            )
        self.assertTrue(publication.committed)
        self.assertEqual(subprocess_calls, [])
        self.assertEqual(which_calls, [])
        generated_text_has_no_fresh_claim(output)
        source = Path(RESULTS.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = ("new02_oracle_grid", "_load_landed_oracle", "/usr/bin/7z",
                     "/usr/bin/cmp", "/usr/bin/taskset", "/usr/bin/time")
        string_references = [node.value for node in ast.walk(tree)
                             if isinstance(node, ast.Constant) and isinstance(node.value, str)
                             and any(value in node.value for value in forbidden)]
        import_references = [ast.unparse(node) for node in ast.walk(tree)
                             if isinstance(node, (ast.Import, ast.ImportFrom))
                             and any(value in ast.unparse(node) for value in forbidden)]
        self.assertEqual(string_references, [])
        self.assertEqual(import_references, [])

    def test_package_file_tamper_fails(self) -> None:
        self.assert_package_mutation("derived-tamper")

    def test_package_rehash_tamper_fails_trusted_ledger(self) -> None:
        self.assert_package_mutation("derived-rehash")

    def test_supplemental_rehash_tamper_fails_trusted_ledger(self) -> None:
        self.assert_package_mutation("supplemental-rehash")
        self.assert_package_mutation("supplemental-hash")

    def test_correlated_status_requires_supplemental_files(self) -> None:
        self.assert_package_mutation("supplemental-missing")
        self.assert_package_mutation("mode-evidence")

    def test_canonical_sentinels_and_no_select_boundary_are_immutable(self) -> None:
        self.assert_package_mutation("canonical-sentinel")

class SecurityTests(ContractTestCase):
    def test_python_ast_security_floor(self) -> None:
        for path in (PACKAGE_ROOT / "verify_new02_historical.py", PACKAGE_ROOT / "verify_new02_results.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = ast.unparse(node.func)
                    self.assertNotIn(name, {"eval", "exec", "pickle.loads", "yaml.load"})
                    self.assertFalse(name.startswith("subprocess.") and any(
                        keyword.arg == "shell" and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True for keyword in node.keywords))

    def test_registered_emitted_and_mutated_error_codes_match(self) -> None:
        mutated = {case.code for values in MUTATION_CASES.values() for case in values}
        self.assertEqual(mutated, set(HISTORICAL.ERROR_CODES))

    def test_cli_output_redacts_evidence_and_remote_urls(self) -> None:
        for case in MUTATION_CASES["cli"]:
            with self.subTest(name=case.name):
                status, output = apply_cli_mutation(case.name)
                self.assertEqual(status, 2)
                self.assertIn(f"code={case.code}", output)
                self.assertNotIn("https://", output)
                self.assertNotIn("observations.jsonl", output)

class CliTests(ContractTestCase):
    def test_cli_failure_is_stable_and_fail_closed(self) -> None:
        completed = run_cli(PACKAGE_ROOT / "verify_new02_historical.py", "validate",
                            "--raw-run", "/definitely/absent", "--raw-only")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("NEW02_HISTORICAL_VALIDATION=FAIL code=", completed.stderr)

    def test_cli_reports_separate_success_layers(self) -> None:
        if not REAL_RAW.is_dir(): self.skipTest("NO-TEST-ENV: external immutable publication absent")
        completed = run_cli(PACKAGE_ROOT / "verify_new02_historical.py", "validate",
                            "--raw-run", str(REAL_RAW), "--raw-only")
        self.assertEqual(completed.returncode, 0)
        for value in ("CAPTURE_STATUS=COMPLETE", "HISTORICAL_VALIDATION_STATUS=PASS_RAW_ONLY",
                      "SCIENTIFIC_CHARACTERIZATION=CHARACTERIZED_NO_SELECT",
                      "PRODUCT_SELECTION_STATUS=NOT_ISSUED"):
            self.assertIn(value, completed.stdout)

def load_tests(loader: unittest.TestLoader, standard_tests: unittest.TestSuite,
               pattern: str | None) -> unittest.TestSuite:
    del standard_tests, pattern
    suite = unittest.TestSuite()
    classes = (RepositoryTests, RawEnvelopeTests, SemanticTests,
               SystemdTests, PackageTests, SecurityTests, CliTests)
    discovered: set[str] = set()
    for case_class in classes:
        names = tuple(loader.getTestCaseNames(case_class))
        expected = tuple(sorted(EXPECTED_TESTS[case_class.__name__]))
        if names != expected:
            raise AssertionError(f"discovery names drifted for {case_class.__name__}: {names}")
        discovered.update(f"{case_class.__name__}.{name}" for name in names)
        suite.addTests(loader.loadTestsFromTestCase(case_class))
    expected_names = {f"{class_name}.{name}" for class_name, names in EXPECTED_TESTS.items()
                      for name in names}
    if discovered != expected_names or suite.countTestCases() != EXPECTED_DISCOVERED_COUNT:
        raise AssertionError("unittest discovery name/count mismatch")
    for label, expected_count in EXPECTED_MUTATION_COUNTS.items():
        actual_count = len(MUTATION_CASES[label])
        if actual_count != expected_count:
            raise AssertionError(f"mutation count drifted for {label}: {actual_count}")
    return suite

if __name__ == "__main__":
    unittest.main()
```

Each listed method must have an explicit body that constructs its fixture/copy, invokes one public callable, and asserts exact return value or `HistoricalValidationError.code`; mutation methods iterate only the fixed `MUTATION_CASES` tuple named by `EXPECTED_MUTATION_COUNTS` and wrap each case with `self.subTest(name=case.name)`. `test_python_ast_security_floor` parses the two shipped Python files with stdlib `ast` and fails on calls to `eval`, `exec`, `pickle.loads`, `yaml.load`, any `subprocess` call with `shell=True`, and any `requests` call with `verify=False`. This is the exact available substitute for unavailable `bandit`; do not list or invoke `bandit` in validation commands.
