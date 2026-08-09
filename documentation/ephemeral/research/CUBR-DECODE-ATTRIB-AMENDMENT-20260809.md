# CUBR NEW-24 decode-attribution amendment

**Status:** Amendment to premeasurement protocol — no measurement result is claimed.
**Supersedes:** Only the invalid 16‑19 pin and the runner‑enforcement gaps described below. All cells, predictions (P1–P5), thresholds, instruments, and sample counts from the preregistered design (`documentation/ephemeral/research/CUBR-DECODE-ATTRIB-20260809.md`) remain unchanged.

## Authority and consilium decision

This amendment is issued under the operator’s hard constraint “Pin stays **0‑15**” (CUBR‑EPIC‑MANDATE.md) and the consilium convened on 2026‑08‑09 comprising Performance Developer, SRE, and Architect. The consilium decision was unanimous:

1. The only admissible pin for any measurement that may influence the DB or lever selection is `taskset -c 0‑15`.
2. The foreign Generation 0 run (pin 16‑19) is permanently excluded from validity and must not be promoted, restarted, or written to any database table. Only the bounded provenance fields already read to classify it are retained.
3. The corrected measurement (Generation G2) must run on pin 0‑15, enforce every gate required by the preregistration, and leave the database untouched.

## Invalid Generation 0 disposition

**Identifier:** `cubr-decode-attrib-20260809`
**Runner SHA256:** `3498a89aa7aec3bf2f54b752f4cea0e91b94e22f5aa75b7d9cba56541ffdcb28`
**Launch time:** 2026‑08‑09T12:33:06Z, host `dev-ai`, pin 16‑19

The Generation 0 run is invalid because it used the prohibited pin 16‑19. Additionally, its runner lacked multiple mandatory enforcement gates (see Corrected Generation G2 Contract below). Consequently:

- No observation from it may influence predictions, thresholds, lever selection, or database measurement rows.
- The artifact directory `/root/cubr-decode-attrib-20260809` is preserved as‑is; it must never be deleted, reused, restarted, or modified.
- The partial `dickens`/`max` observations and the `xml`/`max` source‑file‑missing void recorded in that session are not transferred to the corrected campaign.

**Bounded-read statement:** During provenance classification, the coordinator read the G0 journal through the `xml/max` void. That exposed timestamps, gate labels, the `dickens/max` wall times, the G3 ratio, and the source-missing void; no `perf stat` counters, `perf report`, symbol share, IPC, miss rate, or cycles/bit result was read. The pin correction was identified from the operator mandate before G0 was discovered. None of the bounded fields changed P1–P5, any threshold, the cell list, the instruments, the sample counts, or the lever ranking. The consilium did not read G0 observations and based its decision only on the preregistered design, the operator constraint, live topology/admission facts, and source-level runner gaps.

### Post-amendment reconciliation of invalid PR #54

After the G2 criteria above and the runner's RED contract had been frozen locally, current `origin/main` was fetched at `4b8a03bb62c7f8f45a8b8553ba205dc1693c12df`. That main includes PR #54 (`ad7f9fce7583413782c5c1ff3bf53ed22ce0f0af`), whose report publishes the completed G0 observations from pin 16‑19 and discloses that `xml/max` was re-run after the source-root failure. Both facts violate the operator's hard pin/no-restart constraints. Merge status therefore does not make PR #54 valid characterization evidence, does not close NEW-24, and does not license a database result pointer.

The coordinator read the complete 130-line landed PR #54 report only to reconcile current main after the prospective G2 criteria were fixed. That read exposed its counters, symbol shares, predictions, ceilings, and suggested direction. This broader exposure supersedes the earlier bounded-read statement for all work after the fetch; it does not retroactively change what the consilium or the prospective amendment used. No G2 cell, prediction, threshold, instrument, sample count, timeout, or gate was changed after the read. G2 is consequently a confirmatory replication of the already-preregistered P1–P5 contract, and its report must be reconciled mechanically from G2 raw evidence by independent reviewers. Any later lever-selection record must disclose the invalid PR #54 exposure rather than claim blind selection.

PR #54 and `/root/cubr-decode-attrib-20260809` are foreign landed outputs and remain preserved unchanged. They are classified as invalid evidence, not reverted or rewritten.

### Post-amendment reconciliation of PR #58

After the G2 contract and its test-repair gates were frozen locally, `origin/main` advanced to `8a4e062c19a4b0f4465258c0d8864702c520b2d8`, including PR #58 (head `28a9cc90f390f3e98f519d3d62df38ac8ddb51ab`, merge `423dcd87a137c51cb01e41c363b280a7c81510b4`). Its `CUBR-NEW24-TIERS-20260809.md` explicitly bases its speed model and tier selection on invalid PR #54, and preregisters the resulting real-codec measurements on pin 16–19. That conflicts with both the mandated sequence (valid decode characterisation before lever selection) and the hard 0–15 pin constraint. PR #58 therefore does not close NEW-24, authorise its F12/M8 implementation, or qualify as a valid post-G2 lever preregistration.

The landed PR #58 files are foreign outputs and remain preserved unchanged. Their analogue density probe may be treated only as disclosed exploratory material; its tier selection, speed predictions, and 16–19 measurement protocol cannot influence the valid G2 report or database. If a later lever resembles F12 or M8, its post-G2 selection record must derive independently from valid G2 evidence, disclose exposure to PR #58, and preregister fresh 0–15 measurements. No G2 cell, prediction, threshold, instrument, sample count, timeout, or gate changed during this reconciliation.

### Return to plan: exact-commit suite correction

An adversarial review performed before G2 was launched found that the originally specified focused command, `cargo test --release --test scheme_roundtrip -- --nocapture`, cannot run at the frozen source commit `3a13f486aea51470e2079ba66abb94d99fd782d9`: that tree has no `tests/scheme_roundtrip.rs` and no explicit `scheme_roundtrip` test target. The target exists only in later source and importing it would dirty the checkout and break the frozen source/binary provenance. Leaving the command unchanged would deterministically stop the campaign before any cell and would provide no safety evidence.

A subsequent exact-commit compile probe showed that merely naming the existing `differential` target was still insufficient: the frozen tree added the required `EncodeConfig.cm2_max_tbits` field without updating four test-only struct literals. `cargo test --release --test differential --no-run` failed with Rust error E0063 at its three affected literals; the full suite also reaches the fourth affected literal inside `src/config.rs`'s test module. Repository commit `3c06a213ce0c45ee16e1452fbe9ab2346ccb6a2a` later fixed exactly those four omissions. The G2 test overlay is the exact zero-context, two-file, four-line diff from frozen commit `3a13f486…` to that fix commit, stored as `decode-attrib-g2-test-overlay.patch` with SHA-256 `b0c09568746bf7ecce5466a98b5e62166b6fbd64d98726ffd2538214d486e7ec`.

The first overlay-enabled full-suite probe then exposed a second historical fresh-checkout defect: six strict corpus tests found 0/10 fixtures because the ten deterministic files were not tracked at `3a13f486…`. Repository commit `a3d399f57aa8ee5b7c172afd5322a7f7a1e14392` later committed those exact fixtures; their pinned Git tree is `8248283bcab58b4c4078b4a78425cd8717f165f7`. G2 may materialise only that authenticated tree for the suite, verify every file against its pinned Git blob, record their SHA-256 manifest, and remove the ignored fixture tree afterward. The frozen tree also intentionally omits and ignores `Cargo.lock`; Cargo's resolved lock is therefore copied into final evidence before cleanup so the suite dependency resolution is reproducible from the evidence even though it is not part of measured-binary provenance.

The prospective G6 contract is therefore corrected before measurement as follows. Admission first proves an exact detached, clean `3a13f486…` checkout and authenticates the overlay SHA plus fixture commit/tree. The main run copies the overlay into its evidence directory, makes that copy read-only, reauthenticates it immediately before apply and reverse, and never applies the mutable transfer source. The runner materialises exactly the authenticated ten-file fixture path set, applies the overlay with zero-context semantics only to the four test literals, verifies the exact two-path diff, runs the complete `cargo test --release` suite and its existing focused round-trip/back-compat target `cargo test --release --test differential -- --nocapture` with an isolated suite target directory, reverses the patch, captures the generated Cargo lock and fixture manifest, removes all suite-only inputs and build outputs, and proves the checkout exact-clean including ignored paths before any cell. The focused target exercises ordinary and configured value-scheme round trips, old-archive decoding, and entropy/context/RLE branches. Direct G2 execution independently performs byte comparison and original-SHA verification after every profiled decode. The production source, source commit identity, measured binary, cells, predictions, thresholds, instruments, sample counts, and all other gates remain unchanged. The operator mandate delegates ordinary implementation forks for autonomous resolution; these authenticated test-only repairs remove impossible fresh-checkout states without expanding scope or weakening the losslessness requirement.

## Corrected Generation G2 contract

A single systemd‑invoked, non‑restartable campaign is the only valid continuation of the decode‑attribution characterisation.

| Item | Value |
|------|-------|
| Immutable output path | `/root/cubr-decode-attrib-g2-20260809` |
| Pin | `taskset -c 0‑15` (cores 0‑15 only; no SMT siblings) |
| Worker threads | 4 (`CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4`) |
| Binary | `/root/phaseC/cubrim-3a13f48` (sha256 `d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb`) — exactly the campaign binary |
| Cells | `silesia/dickens` × `max`, `silesia/xml` × `max`, `silesia/x‑ray` × `max`, `silesia/dickens` × `web` (as preregistered) |
| Predictions | P1–P5 unchanged |
| Instruments | `perf record -F 997 -e cycles`, `perf stat -d` + explicit events, `/usr/bin/time -v` (as preregistered) |
| Validity gates | G1, G2, G3 of the preregistration, plus the additional fail‑closed gates listed below |
| Budget | ≤4 h stand wall‑clock; per‑step timeout 3× the DB‑derived expected duration |
| Stop rule | Any failed gate fails the cell; no substitution of files or presets |

## Fail‑closed gates (full set enforced in G2)

Every gate listed here must pass for a cell before any number from that cell is read. The first three are from the preregistration; the remainder correct the runner‑enforcement gaps discovered.

- **G1 — Canonical archive identity.** A freshly encoded archive at the cell’s preset must be byte‑identical (sha256) to the corresponding Phase C journal’s canonical `archive_sha256` (from `journal.max.jsonl` / `journal.web.jsonl`). In G2 the verification uses two independent fresh encodes, both of whose sha256 match the journal value, and those two archives must also be `cmp`‑identical to each other. A single‑encode check is not sufficient.
- **G2 — Round‑trip.** Every profiled decode’s output must pass `cmp` against the original corpus file, and its sha256 must equal the pinned `orig_sha256` value from `corpus_manifest.tsv` (which must be verified by the runner before any cell begins).
- **G3 — Instrument overhead sanity.** The `perf record` decode wall‑clock must be within 10 % of the plain decode wall‑clock taken in the same session on the same pin. If the ratio exceeds 1.10, the cell is flagged **instrument‑perturbed**, and no cycles/bit figure may be quoted from that run.
- **G4 — Admission gates (host and runner).** Before any cell is started:
  - The host must be `dev-ai`, confirmed by `hostname`.
  - No competing `cubrim` or `perf` process may be present (bounded process-table scan with the current runner and its parent excluded).
  - The 1‑minute load average must be < 8.0; if not, wait.
  - `perf` must be available and functional using bounded smoke commands for both `perf stat -e cycles` and `perf record -e cycles`; a broad `perf test` suite is not required.
  - CPU topology must match the observed EPYC 7502P layout: logical CPUs 0‑31 map one-to-one to physical core IDs 0‑31, and logical CPUs 32‑63 are their SMT siblings. The 0‑15 pin therefore contains 16 distinct physical cores and no SMT siblings.
  - The runner’s own provenance (SHA256 of the runner script/binary) must be logged and must match the exact landed version authorised for this campaign.
- **G5 — Historical archive absent; independent encode requirement.** The historical archive bytes are not present on the measurement host. G1’s correction (two independent fresh encodes) is the only permitted canonical‑identity gate.
- **G6 — Full release and focused differential suites with authenticated test-only repair.** Before profiling, an exact detached checkout of code commit `3a13f48` must authenticate and materialise the pinned ten-fixture tree, authenticate and apply the exact four-line test overlay described above, then pass `cargo test --release` and `cargo test --release --test differential -- --nocapture`. The explicit `--test` selector is mandatory so Cargo executes the frozen commit's real integration-test target rather than treating `differential` as a name filter. After both suites, the runner must reverse the overlay, capture the generated Cargo lock and fixture hashes, remove the suite-only inputs, and prove the checkout clean before the first cell. The measured binary remains the frozen Phase C binary above; a freshly built test binary is never substituted. Failure fails the entire campaign.
- **G7 — Per‑step 3× timeout.** Every per‑cell step (encode, plain decode, each perf‑stat decode, perf‑record decode) is subject to a wall‑clock limit of 3× the DB‑derived expected duration for that step. Any step exceeding its limit voids the cell to the journal.

  The frozen timeout constants below are the Phase C `world_benchmark_timing_file` encode/decode durations multiplied by three and rounded upward to the next five seconds. Both independent encodes use the encode timeout; every decode instrument uses the decode timeout.

  | Cell | DB encode ms | DB decode ms | Encode timeout s | Decode timeout s |
  |------|-------------:|-------------:|-----------------:|-----------------:|
  | `dickens/max` | 445727.761321 | 144014.354481 | 1340 | 435 |
  | `xml/max` | 172395.326257 | 57998.703865 | 520 | 175 |
  | `x-ray/max` | 312934.072179 | 6226.439667 | 940 | 20 |
  | `dickens/web` | 125565.677881 | 106035.455037 | 380 | 320 |
- **G8 — Four-hour total budget enforcement.** The runner records a monotonic deadline, refuses to begin any step after it, and caps each command at the lesser of its cell timeout and the remaining campaign budget. A budget expiry journals the active or unfinished cell as void and ends the campaign without substitution. The systemd runtime limit is a last-resort process cap, not the primary journaling mechanism.
- **G9 — `perf stat` cycle‑count agreement.** The total cycles reported by the two independent `perf stat` decodes must agree within ±10 %. If not, both are reported, neither is quoted as singular, and the cell is flagged cycle‑disagreement.
- **G10 — Existing output‑path refusal.** The runner must not overwrite any pre‑existing directory or file inside `/root/cubr-decode-attrib-g2-20260809`. If the path exists, the run must fail with a refusal note.
- **G11 — Process‑exit gate.** After every cell, the runner must confirm no orphaned `cubrim` or `perf` process remains before starting the next cell.

## Evidence and database semantics

- No throughput or attribution number from this characterisation (G2 or otherwise) is ever written to `world_benchmark_*` or `measurements` tables.
- The hypotheses row **NEW-24** remains **in_progress** throughout. Its `measure_note` will receive a one‑line pointer to the G2 results report only after a valid report lands. No evaluation row is created.
- All gate outcomes, void declarations, and raw instrumentation outputs are recorded under the unique G2 output directory. On completion, the runner writes sorted SHA-256 manifests and removes write permission from the evidence tree; those hashes and the systemd/journal provenance, rather than the path alone, establish integrity.

## Non‑influence declaration

The coordinator’s bounded provenance read is disclosed above. No G0 performance counter, symbol attribution, IPC, miss-rate, or cycles/bit observation informed this amendment. The original predictions, thresholds, cells, instruments, and sample counts remain byte-for-byte unchanged in the preregistration. The corrected gates and G2 contract derive from the operator’s hard constraints, live feasibility checks, and source-level enforcement analysis; they were not fitted to G0 results.
