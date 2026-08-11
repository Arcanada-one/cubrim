# Preregistration: NEW-24 full-binary residual attribution G6

**State:** prospective design/preregistration only. G6 has not launched, and no G6 performance sample exists. This document does not authorize launch.

## G5 — immutable terminal VOID before sampling

The G5 experiment ended `VOID` before any performance sample was taken, during
the admission phase, because the prebuilt release binary was missing or unsafe.
The exact terminal unit is `cubr-new24-full-binary-g5-admission-20260810.service`,
`InvocationID=9bb2c1d32c714cf28575e61fcbb601bc`, `NRestarts=0`,
`Result=exit-code`, and `ExecMainStatus=1`. No `perf.data`, address-smoke artifact, campaign cell
directory, attribution summary, `pstat`/`prec` file, or cell journal row was
produced. The incident manifest has SHA-256
`2d8cbdf7876644a69e176e9578c2b663a12ebe1872ecb1a1048b72c77eb99b15` (261 bytes);
the exact manifest stream is retained at
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv`,
Git blob `49fb705f5230a35e43726d4f6a333e47c5cb1b29`;
the raw unit-journal rendering captured at the incident has SHA-256
`b11d33ecde790f61e679494d9e48419688a1aef0e3a979de2eb5b65556597c25`
(6428 bytes). Because later `journalctl --output=json` renders vary JSON key
order, live reauthentication sorts events by `__CURSOR` and uses the compact
sorted-key canonical stream:
SHA-256 `926fdebe5690ce450ce6970c3260c54ce37bd095241f760d2acd9931b0586e4c`
(6428 bytes). The retained canonical stream is
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl`,
Git blob `5ea61262dacd442fdf1676a7a7613c8e5534b6a3`.

The controlling G5 clause is
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md`
lines 507–513, blob `5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f`,
reviewed head `e4f7efe84d6478d5f0c7286873910972f87b4d68`, and
resulting main `c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4`. It requires
a new protocol — not a retry, restart, resume, or parameter adjustment of G5.
The G5 output namespace is immutable,
nonauthoritative failure evidence. No G5 path, unit, PID baseline,
`InvocationID`, or journal may satisfy a G6 runtime, admission, campaign, or
performance predicate. The three incident identities may satisfy only explicit
provenance predicates.

## G6 — fresh, separately named experiment

G6 is a new characterization experiment with a new designation, units,
`InvocationID`, PID baseline, output namespace, `CLOCK_MONOTONIC` start, and
campaign budget. It does not inherit G5 process state, campaign time, partial
output, or performance evidence. No G5 runtime artifact is reused. G6 may cite
only the immutable G5 incident-record blob, retained manifest blob/hash/bytes,
raw-capture journal hash/bytes, retained canonical journal blob/hash/bytes, and
the controlling G5 preregistration path/blob/reviewed-head/resulting-main
identities. Those citations convey incident or authority provenance, never G5
runtime, process, admission, campaign, or performance identity.

G6 is governed exclusively by this protocol. It MUST NOT launch until every
pre-launch predicate below is satisfied by concrete reviewed identities on
`origin/main`.

## Code-under-test baseline

The immutable code-under-test baseline is commit
`830a9a31deb00926a97f3fa5bd74f58003573fc0`. The toolchain is pinned to
Rust 1.96.1 and Cargo 1.96.1, with rustc commit
`31fca3adb283cc9dfd56b49cdee9a96eb9c96ffd`. The independently generated
`Cargo.lock` MUST have SHA-256
`0080335ef71fa475f167338b96f1c6dfb5cd6bf3e188dfa0a86aeed68caa35b9`.
Each release binary MUST have SHA-256
`2afa71bca90c9c26a2bb048523d1c3e3ea83bd6851949f184e64be2f18186b78`
and ELF build ID `789119db24ae1a28a24bcc0ecbec136c7e937d9a`.
These values were frozen before G5 admission and MUST NOT be changed to match a
future build.

## Prebuild from two independent source trees

Before any admission or campaign service exists, a stand-alone prebuild phase
must prove repeatability across two distinct checkouts and targets on this host
under the frozen toolchain, and equality to the already frozen binary. It does
not claim independence from the shared host, Cargo home, or toolchain. The
prebuild is invoked once. A mismatch, ambiguous
result, interruption, or partially sealed receipt is terminal G6
`NO-ATTEMPT`: no service may be created, the expected values are not adjusted,
and the prebuild is not repeated under the G6 designation.

1. **Independent checkouts.** Create two distinct, clean detached checkouts
   of the source commit:
   * `/root/cubr-new24-full-binary-g6-src-a`
   * `/root/cubr-new24-full-binary-g6-src-b`
   Both trees are verified clean (`git status --porcelain` empty) and refer to
   the same commit.

2. **Lockfile generation.** In each checkout, run:
   ```bash
   /root/.cargo/bin/cargo generate-lockfile \
     --manifest-path code/cubrim-rs/Cargo.toml
   ```
   The two resulting `Cargo.lock` files are compared with `cmp`. If they are
   not byte-identical, the build is **NO-ATTEMPT**; hashes are never adjusted,
   the incident is recorded, and no machine state is altered further.

3. **Release build.** In each checkout, with `CARGO_PROFILE_RELEASE_DEBUG=1`,
   `CUBR_THREADS=4`, `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=4`, and
   `MKL_NUM_THREADS=4`, run the pinned Cargo under `taskset -c 0-15`:
   ```bash
   /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo build \
     --release --locked \
     --manifest-path /root/cubr-new24-full-binary-g6-src-a/code/cubrim-rs/Cargo.toml \
     --target-dir /root/cubr-new24-full-binary-g6-target-a
   /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo build \
     --release --locked \
     --manifest-path /root/cubr-new24-full-binary-g6-src-b/code/cubrim-rs/Cargo.toml \
     --target-dir /root/cubr-new24-full-binary-g6-target-b
   ```
   The resulting binaries under each literal target's `release/cubrim` path are
   compared with `cmp`, SHA-256, size, and ELF build ID. Each lock and binary
   must also equal the frozen identities above. Any mismatch is
   **NO-ATTEMPT**.

4. **Sealing.** Once the two binaries match, remove every write bit from both
   source and target trees before computing their final identities. A canonical
   tree-manifest stream first rejects every nested entry that is not a regular
   file or directory. It requires exactly one root-directory row whose relative
   path is the empty string; every non-root relative path must match the ASCII
   allowlist `^[A-Za-z0-9._/@+=,-]+$`. It then consists of a `LC_ALL=C`
   path-sorted, tab-separated row
   containing relative path, type, mode, uid, gid, and size for every entry,
   followed by a path-sorted, tab-separated SHA-256, byte-count, and relative
   path row for every regular file. The receipt is
   staged privately below
   `/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811.partial` and
   published no-clobber as mode `0444` at
   `/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811/receipt.env` only
   after every sealed-tree identity is known.

   `g6-prebuild-receipt-v1` is a closed, lowercase, lexicographically sorted
   key set. It contains exactly:

   ```text
   binary_a_build_id binary_a_bytes binary_a_device binary_a_inode binary_a_sha256
   binary_b_build_id binary_b_bytes binary_b_device binary_b_inode binary_b_sha256
   build_cpuset campaign_artifact_count cargo_build_args_sha256 cargo_inputs_manifest_bytes
   cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes
   cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256
   cargo_profile_release_debug cargo_version
   cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob
   g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob
   g5_journal_canonical_blob g5_journal_canonical_bytes
   g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256
   g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head
   map_artifact_count
   mkl_num_threads omp_num_threads perf_data_count prebuild_helper_blob
   prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob
   prebuild_test_sha256
   rayon_num_threads rustc_commit rustc_version schema service_count
   source_commit source_tree_a_git_tree source_tree_a_manifest_bytes
   source_tree_a_manifest_sha256 source_tree_b_git_tree
   source_tree_b_manifest_bytes source_tree_b_manifest_sha256
   target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes
   target_b_manifest_sha256
   ```

   The Cargo-input manifest covers every tracked `Cargo.toml`, `build.rs`,
   `.cargo/config*`, and `rust-toolchain*` path plus the generated lock. Unknown,
   duplicate, missing, unsorted, or malformed keys void the receipt. Its
   concrete SHA-256 and byte count are unknown prospectively and MUST be
   recorded later by a standalone protected launch-identity file; this
   preregistration remains byte-identical and does not invent them.

5. **No performance.** This phase produces no `perf.data`, no timing, no
   map, and no campaign artifacts. It is a build‑reproducibility gate only.

After sealing, both source trees and target directories remain read-only and
are preserved as immutable inputs; none may be used as a scratch space later.

## Admission prerequisites

Admission must establish:

* hostname `dev-ai`, CPU model `AMD EPYC 7502P 32-Core Processor`, topology
  `0..31` cores and `32..63` SMT siblings;
* the only permitted affinity is `taskset -c 0-15`;
* `CUBR_THREADS=4`, `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=4`,
  `MKL_NUM_THREADS=4` for every subprocess;
* one-minute load below 8.0 and no competing Cubrim, perf, Cargo, Rust, or
  same-runner process;
* exact binary from the prebuild receipt (SHA‑256, build ID, ELF metadata)
  present and immutable;
* exact source tree identity, instrument repo state, and all frozen
  identities from the prebuild receipt;
* `cargo test --release --locked` and
  `cargo test --release --locked --test scheme_roundtrip -- --nocapture` pass
  in the separate validation checkout/target under the same pin and
  environment;
* cgroup self-test with sanitized allowlist (see below) exits zero;
* a complete frozen full-binary instruction map is constructed from the
  prebuild binary (G3);
* admission is **no-performance-only** — no campaign cell is decoded and no
  performance counter, timing result, or family share is interpreted. The
  only permitted perf activity is capability probing against literal
  `/usr/bin/true` and the fixed address-join smoke whose timing and shares are
  neither retained nor interpreted.

The separate one-shot validation helper seals the validation source, target,
and output trees first, then applies the same nested-entry/path rejection and
canonical tree-manifest algorithm defined for prebuild. Its manifest is outside
all three covered roots, so it is not self-referential. It is staged below
`/root/cubr-new24-full-binary-g6-validation-manifest-20260811.partial` and
published no-clobber as mode `0444` at
`/root/cubr-new24-full-binary-g6-validation-manifest-20260811/manifest.env`.
The manifest root is mode `0500` after publication.

The manifest schema is `g6-validation-manifest-v1` with exactly these
lowercase, lexicographically sorted keys:

```text
binary_build_id binary_sha256 build_cpuset campaign_artifact_count
cargo_lock_bytes cargo_lock_sha256 cargo_test_release_log_bytes
cargo_test_release_log_sha256 cargo_version cubr_threads instrument_main
map_artifact_count mkl_num_threads omp_num_threads output_tree_manifest_bytes
output_tree_manifest_sha256 perf_data_count rayon_num_threads rustc_commit
rustc_version schema scheme_roundtrip_log_bytes scheme_roundtrip_log_sha256
service_count source_commit source_tree_manifest_bytes
source_tree_manifest_sha256 suite_commands_sha256 target_tree_manifest_bytes
target_tree_manifest_sha256 validation_helper_blob validation_helper_sha256
validation_test_blob validation_test_sha256
```

Before the admission submission, a mode-`0444` canonical
`/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env` is published
no-clobber. Its closed schema contains the admission unit/output literals,
instrument main, all eight instrument blobs and SHA-256 values, receipt
SHA-256/bytes/schema, source commit, both sealed binary identities, the full G5
incident/authority provenance set, plus the exact validation
manifest SHA-256/bytes. The runner independently
rederives every value from the exact local instrument checkout, sealed receipt,
and read-only build trees; the file is an authenticated input record, not
protected launch authority. The successful admission seals its exact hash and
byte count. Campaign mode additionally requires the later protected launch
identity set from resulting main.

The admission-input schema is `g6-admission-inputs-v1` with exactly these
lowercase, lexicographically sorted keys:

```text
admission_output_root admission_unit binary_a_build_id binary_a_sha256
binary_b_build_id binary_b_sha256 g5_incident_manifest_blob
g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob
g5_journal_canonical_blob g5_journal_canonical_bytes
g5_journal_canonical_sha256 g5_journal_raw_bytes g5_journal_raw_sha256
g5_prereg_blob g5_prereg_resulting_main g5_prereg_reviewed_head
g6_prereg_blob instrument_main mapper_blob mapper_sha256 mapper_test_blob
mapper_test_sha256 prebuild_helper_blob prebuild_helper_sha256
prebuild_test_blob prebuild_test_sha256 receipt_bytes receipt_schema
receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256
schema source_commit validation_helper_blob validation_helper_sha256
validation_manifest_bytes validation_manifest_sha256 validation_test_blob
validation_test_sha256
```

## Frozen scope

Only these three cells run, and every result is reported separately:

| cell           | archive SHA‑256                                                     | original SHA‑256                                                    | bytes    | encode timeout s | decode timeout s |
|----------------|---------------------------------------------------------------------|---------------------------------------------------------------------|----------|-----------------:|-----------------:|
| `dickens/max`  | `b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 1340             | 435              |
| `xml/max`      | `d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37` | `0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c` | 5345280  | 520              | 175              |
| `dickens/web`  | `a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 380              | 320              |

`x-ray/max` remains excluded.

## One-shot admission and execution

After the two-build preflight succeeds, the reviewed runner enters admission
exactly once as
`cubr-new24-full-binary-g6-admission-20260811.service`, writing only beneath
`/root/cubr-new24-full-binary-g6-map-dryrun-20260811`. Admission uses
`Type=exec`, `Restart=no`, `RuntimeMaxSec=4h`, `KillMode=control-group`,
`KillSignal=SIGTERM`, and `FinalKillSignal=SIGKILL`; its `InvocationID`,
`MainPID`, and exact cgroup are verified. A failed, ambiguous, or nonterminal
admission is immutable G6 `VOID / NO-SELECT`; there is no second G6 admission.
The first `systemd-run` submission consumes the G6 admission allowance even if
the client returns nonzero, disconnects, or cannot recover a unit identity.

Only after a successful sealed admission and a protected concrete launch
identity file may the campaign runner launch exactly once as
`cubr-new24-full-binary-g6-20260811.service`, writing only beneath
`/root/cubr-new24-full-binary-g6-20260811`. It uses the same systemd contract
and an independent monotonic budget of 14,400 seconds. There is no retry,
restart, resume, continuation, shortened sample, widened pin, or sample
substitution in either phase.
The first campaign `systemd-run` submission likewise consumes the G6 campaign
allowance even if submission is nonzero or ambiguous.

## Cgroup self-test with sanitized allowlisted environment

The pure-mock fixture uses `g6-mock-fix.unit` and
`g6-precommit-disconnected.service`; the live fixture uses one unique
`current-profile-g6-cgroup-selftest-$$.service`. Both start from a poisoned
parent environment and prove that only `HOME=/root`,
`XDG_RUNTIME_DIR=/run/user/0`,
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus`, `LC_ALL=C`,
`PATH=/usr/bin:/bin`, and the four thread limits reach the child.

The fixture authenticates the transient unit's InvocationID, MainPID, and exact
cgroup before opening one traversal-free, nonsymlinked `cgroup.procs` file. The
export remains bound to that file descriptor while a disconnected precommit
state is injected. It rejects an empty, recycled, mismatched, or out-of-cgroup
PID and never signals a PID from the pre-fixture baseline. Exact cleanup removes
only the fixture unit/processes and proves no descendant survives. After every
self-test, the exact currently admitted production unit identity is reread and
compared; during admission this is the admission unit, and during campaign
execution this is the campaign unit.

## G1: archive and round-trip correctness

For each cell, two independent encodes produce identical archives matching the
registered SHA‑256. Five decodes (one timed, two `perf stat`, two `perf record`)
exit zero and match the registered original by `cmp` and SHA‑256. Any failure
is `VOID` before performance data is interpreted.

## G2: per-file counter and perturbation gates

Every requested counter must be supported and retained without multiplexing or
loss. The two cycle counts for a cell must agree within 10%, and each record
run's wall-time perturbation relative to its paired non-recorded reference must
be at most 1.10. A gate miss suppresses inferential attribution and routes an
otherwise correct cell to descriptive-only treatment; it never changes the
sample or threshold.

## G3: frozen full-binary instruction map

The mapper reads the exact binary from the prebuild receipt. Schema labels use
`cubr-new24-g6-*` prefixes (e.g., `cubr-new24-g6-normalized-elf-v1`,
`cubr-new24-g6-static-map-summary-v3`, etc.). The map is constructed during the
no-performance admission and sealed in the admission identity set. The campaign
**MUST** reuse the admission map unchanged; no new map is generated during the
campaign.

Runtime addresses are normalized by the matching MMAP2 mapping and DSO offset,
the observed `dsoff` must equal the normalized file offset, and the join must be
independent of symbol names. Every sample and period is conserved across the
join. Any exact-binary `binary_unresolved` row or
`ambiguous_inline_owner` row is a void; it may not be discarded, reassigned, or
absorbed into another family.

## Statistical and repeatability gates

Unchanged from G5: one-sided Clopper‑Pearson zero-hit bound with Bonferroni
correction, minimum `n_binary ≥ 4787`, `U_binary ≤ 0.001`, per-file family
share repeatability (≥ 5.00% in either record, difference ≤ 1.00 pp), and
perfect-family Amdahl ceilings computed from the two‑record mean share where
eligible.

## Frozen predictions

The predictions and thresholds are unchanged:

* **P1 — static map integrity:** 100% unique instruction-row coverage, stable
  resolver output, no incompatible overlap, no hash drift.
* **P2 — address normalization:** pre-cell smoke joins every exact-binary
  sample to exactly one map row via MMAP2/dsoff.
* **P3 — record integrity:** zero loss, sample and period conservation.
* **P4 — attribution power:** separately in all six records, `n_binary ≥ 4787`,
  `U_binary ≤ 0.001`, zero unresolved samples.
* **P5 — repeatability:** both stat cycles within 10%, both record perturbations
  ≤ 1.10, every material family’s share stable within 1.00 pp.

P1–P5 are evaluated as `SUPPORTED`, `REFUTED`, or `INDETERMINATE`. They are
per‑file characterization results only.

## Decision routes

* `NO-ATTEMPT / NO-SELECT` — prebuild, pre-service validation, collision, or
  submission prerequisites fail before an admission unit is submitted. Owned
  evidence is preserved read-only; the G6 prebuild is never invoked again and
  no admission is submitted.
* `VALID-ATTRIBUTION / NO-SELECT` — every admission, suite, archive,
  round‑trip, terminal, static‑map, smoke, record‑integrity, attribution‑power,
  cycle, perturbation, and repeatability gate passes.
* `VALID-DESCRIPTIVE / NO-SELECT` — correctness, identity, mapping,
  conservation, and terminal gates pass but sample size, perturbation, cycle
  agreement, or family repeatability is insufficient. Affected ceilings are
  suppressed.
* `VOID / NO-SELECT` — any identity mismatch, correctness failure, timeout,
  lost record, static‑map failure, MMAP2 or `dsoff` mismatch, unknown
  exact‑binary instruction offset, ambiguous ownership, period‑conservation
  failure, environment‑isolation failure, or nonterminal execution. A void is
  preserved and never retried. No route selects a source change.

## Fresh G6 identities and namespaces

All paths, units, and identity prefixes are exclusive to G6:

* source checkouts: `/root/cubr-new24-full-binary-g6-src-a`,
  `/root/cubr-new24-full-binary-g6-src-b`
* build targets: `/root/cubr-new24-full-binary-g6-target-a`,
  `/root/cubr-new24-full-binary-g6-target-b`
* prebuild receipt root: `/root/cubr-new24-full-binary-g6-prebuild-receipt-20260811`
* validation source: `/root/cubr-new24-full-binary-g6-validation-src`
* validation target: `/root/cubr-new24-full-binary-g6-validation-target`
* validation output: `/root/cubr-new24-full-binary-g6-validation-20260811`
* validation manifest root:
  `/root/cubr-new24-full-binary-g6-validation-manifest-20260811`
* admission input: `/root/cubr-new24-full-binary-g6-admission-inputs-20260811.env`
* instrument checkout: `/root/cubr-new24-full-binary-g6-instrument`
* admission output: `/root/cubr-new24-full-binary-g6-map-dryrun-20260811`
* campaign output: `/root/cubr-new24-full-binary-g6-20260811`
* nonauthoritative work variants: same plus `.partial`, `.publishing`, `.late`
* transient units: `cubr-new24-full-binary-g6-admission-20260811.service`,
  `cubr-new24-full-binary-g6-20260811.service`
* mapper schemas: `cubr-new24-g6-*`

No G5 runtime path, unit, `InvocationID`, PID baseline, or artifact content may
appear or be reused. Only the incident and controlling-preregistration
identities explicitly enumerated above are provenance inputs to the G6
receipt.

## Mandatory hash and provenance seal

This design intentionally contains no invented future hash. Before campaign
launch, a standalone protected resulting-main launch-identity file MUST record
concrete lowercase SHA‑256 or Git object identities for the following eight
categories. Absence, non‑hex text, a mutable reference, or a mismatch blocks
campaign launch:

1. the G5 terminal incident-record blob; incident-manifest blob, SHA-256, and
   bytes; historical raw-journal SHA-256 and bytes; retained canonical-journal
   blob, SHA-256, and bytes; and controlling-preregistration blob, reviewed
   head, and resulting-main commit (the exact 12-field set listed in the G5
   section);
2. the G6 preregistration blob and resulting-main instrument commit;
3. source commit, full source tree, `code/cubrim-rs` subtree, Cargo input
   blobs, the deterministic `Cargo.lock` (sha256 and blob), compiler/Cargo
   versions, release flags, binary SHA‑256, ELF build ID, size, device, inode;
4. the prebuild receipt SHA-256 and byte count, both binary identities, and
   both source/target identities;
5. prebuild helper/test, validation helper/test, runner/test, mapper/test,
   their exact instrument blobs and SHA-256 values, mapping schema, corpus
   manifest, and each exact corpus row identity;
6. the complete instruction‑map stream, reverse index, deterministic gzip
   members, part manifest, row/byte counts, and fresh G6 map‑admission seal;
7. the sanitized‑environment allowlist contract and all accompanying tests;
8. the admission-input and admission-identity-set SHA‑256 values and byte
   counts (including the map seal, prebuild receipt hash, and all other
   admission-frozen identities);

The prelaunch gate additionally binds three live external provenance values:
the reviewed launch-file PR head, the launch-file blob computed from fresh
resulting main, and that resulting-main commit. None is a field in the launch
file. All three are independently recorded and rechecked immediately before
launch, keeping the protected file intentionally self-reference-free.

The protected launch file uses schema `g6-protected-launch-identities-v1` and
contains exactly this lowercase, lexicographically sorted key set:

```text
admission_control_group admission_identity_set_bytes
admission_identity_set_sha256 admission_input_bytes admission_input_sha256
admission_instrument_main admission_invocation_id admission_journal_bytes
admission_journal_sha256 admission_main_pid admission_output_manifest_bytes
admission_output_manifest_sha256 admission_unit admission_unit_properties_bytes
admission_unit_properties_sha256 binary_a_build_id binary_a_bytes
binary_a_device binary_a_inode binary_a_sha256 binary_b_build_id binary_b_bytes
binary_b_device binary_b_inode binary_b_sha256 build_cpuset campaign_output_root
campaign_unit cargo_build_args_sha256 cargo_inputs_manifest_bytes
cargo_inputs_manifest_sha256 cargo_lock_a_blob cargo_lock_a_bytes
cargo_lock_a_sha256 cargo_lock_b_blob cargo_lock_b_bytes cargo_lock_b_sha256
cargo_profile_release_debug cargo_version corpus_dickens_max_archive_sha256
corpus_dickens_max_bytes corpus_dickens_max_decode_timeout_seconds
corpus_dickens_max_encode_timeout_seconds corpus_dickens_max_original_sha256
corpus_dickens_web_archive_sha256 corpus_dickens_web_bytes
corpus_dickens_web_decode_timeout_seconds
corpus_dickens_web_encode_timeout_seconds corpus_dickens_web_original_sha256
corpus_manifest_bytes corpus_manifest_sha256 corpus_xml_max_archive_sha256
corpus_xml_max_bytes corpus_xml_max_decode_timeout_seconds
corpus_xml_max_encode_timeout_seconds corpus_xml_max_original_sha256
cubr_threads cubrim_subtree_git_tree g5_incident_manifest_blob
g5_incident_manifest_bytes g5_incident_manifest_sha256 g5_incident_record_blob g5_journal_canonical_blob
g5_journal_canonical_bytes g5_journal_canonical_sha256 g5_journal_raw_bytes
g5_journal_raw_sha256 g5_prereg_blob g5_prereg_resulting_main
g5_prereg_reviewed_head g6_prereg_blob map_admission_seal_bytes
map_admission_seal_sha256 map_gzip_manifest_bytes map_gzip_manifest_sha256
map_gzip_member_count map_instruction_row_count map_reverse_index_bytes
map_reverse_index_sha256 map_reverse_row_count map_stream_bytes
map_stream_sha256 mapper_blob mapper_sha256 mapper_test_blob mapper_test_sha256
mapping_schema_sha256 mkl_num_threads omp_num_threads prebuild_helper_blob
prebuild_helper_sha256 prebuild_instrument_main prebuild_test_blob
prebuild_test_sha256 rayon_num_threads receipt_bytes receipt_schema
receipt_sha256 runner_blob runner_sha256 runner_test_blob runner_test_sha256
rustc_commit rustc_version sanitized_env_contract_sha256 schema source_commit
source_tree_a_git_tree source_tree_a_manifest_bytes
source_tree_a_manifest_sha256 source_tree_b_git_tree
source_tree_b_manifest_bytes source_tree_b_manifest_sha256
target_a_manifest_bytes target_a_manifest_sha256 target_b_manifest_bytes
target_b_manifest_sha256 validation_helper_blob validation_helper_sha256
validation_manifest_bytes validation_manifest_sha256 validation_test_blob
validation_test_sha256
```

Unknown future values must remain explicitly absent until the corresponding
artifact exists. They are recorded only in the standalone launch-identity file
through a normal protected PR; this preregistration is not amended, and no
placeholder text is accepted by the launch parser.

## Pre‑launch hard gate

G6 remains `NO-LAUNCH` until all of the following are true on one fresh
`origin/main` read:

1. this preregistration is on main with the G5 incident binding intact;
2. the prebuild helper, validation helper, admission mapper/runner, and all
   exact tests land through protected PRs and pass;
3. two independent builds and the no-performance admission finish
   successfully, without changing a scientific variable;
4. the concrete standalone campaign-launch identity file is on main with real,
   exact values and no placeholder or mutable reference;
5. the full release suite, real scheme-roundtrip suite, prebuild tests, runner tests, mapper
   tests, poison test, live‑unit noninterference test, and mutation tests pass
   for those exact blobs;
6. independent specification and quality reviews approve those exact blobs;
7. the detached code-under-test and every registered corpus identity still
   match this protocol;
8. no G6 campaign output path or campaign unit exists and no competing process violates
   admission;
9. the prebuild receipt binary is present and identical to the sealed
   identities.

## Database and external-effect boundary

G6 writes no database, API, site, social channel, or credential path while
running. It MUST NOT touch `config/credentials/`. No G6 decision route, result
bundle, or evidence PR writes the database. NEW‑24 remains `in_progress`;
measurement fields remain empty, `evaluation` remains zero, and no duplicate
hypothesis row is created. Any later evidence‑pointer transaction is outside
this protocol, requires its own prospective review and authority, and cannot
alter those measurement or evaluation fields.

## Evidence and publication boundary

Publication follows the same no‑replace, manifest‑authenticated, read‑only
`.partial` → `.publishing` → final transition. The final rename is the sole
acceptance point. On failure, only nonauthoritative `.partial`, `.publishing`,
or `.late` evidence plus the exact terminal reason may remain. A nonterminal
tree, late final, manifest mismatch, or surviving process is `VOID / NO-SELECT`.

---

*Prospective protocol only. G6 has not been launched.*
