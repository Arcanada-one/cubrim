# Preregistration: NEW-24 current-main CM2 attribution G3

**State:** prospective; no performance sample has been collected under this
protocol. No Fast-CM candidate is selected or built.

## Why another baseline is required

The valid G2 campaign profiled exact source
`3a13f486aea51470e2079ba66abb94d99fd782d9` and landed its result in PR #66.
That result remains valid for that binary. It deliberately selected no lever.

Current `origin/main` is
`e0e8bdb2c2df924877d9dcf8a1897810683a147a`. The following later commits
changed the exact CM2 counter path that G2 attributed:

- `5cdb4d29f705ee73bc080d1f44f60745e9204f7f` packed the stationary `Ctr`
  arrays into one record;
- `67465fdd737fee43d1348d59127c92b4241e4d9d` replaced both counter-update
  divisions with exact reciprocal multiplication;
- `189a09308d38805f67c6263f5cc98793fb485e27` made the packed `Ctr` initial
  representation all-zero.
- `d1e6d1f` refactored CM2/Mixer iteration while clearing clippy warnings and
  shifted the exact source coordinates used by attribution. Even though the
  change was declared behavior-preserving, its source and binary identities
  must be measured rather than inherited.

Those changes alter both the historical `Ctr::upd` numerator and total decode
cycles. G2's 29–33% shares and Amdahl ceilings are historical context only;
they are not current ceilings and will not authorize a candidate. A fresh
current-main profile must land before any SM32 or other Fast-CM proposal.

PR #54 G0 and PR #58 are quarantined exploratory artifacts: their `16-19`
pin, measurements, tier ranking, verdicts, and lever choice are excluded.

## Frozen scope

The unmodified baseline source is the exact `e0e8bdb` commit above. The
profiling build uses Cargo release code generation plus line debug information
(`CARGO_PROFILE_RELEASE_DEBUG=1`); debug assertions remain disabled. The
binary SHA-256 and ELF build ID, generated lockfile SHA-256, compiler/Cargo
and resolver/perf tool versions, release flags, detached-clean source
identity, runner SHA-256, mapper SHA-256, and launch invocation ID are frozen
in the admission journal before the first encode or decode.

Only these CM2 cells run:

| cell | archive SHA-256 | original SHA-256 | bytes | encode timeout s | decode timeout s |
|---|---|---|---:|---:|---:|
| `dickens/max` | `b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 1340 | 435 |
| `xml/max` | `d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37` | `0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c` | 5345280 | 520 | 175 |
| `dickens/web` | `a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 380 | 320 |

`x-ray/max` is excluded because it routes through geocm and cannot decide a
CM2 StateMap ceiling. Cells are always reported separately. No corpus mean,
geometric mean, combined speedup, or profiling throughput is permitted.

## Admission and execution contract

The reviewed runner is launched exactly once on `dev-ai` in a transient
systemd service using `Type=exec`, `Restart=no`, and
`RuntimeMaxSec=4h5m`. The unit's live `InvocationID` must equal the process
environment and its `MainPID` must equal the runner process. Its separate
monotonic campaign budget is 14,400 seconds. The runner refuses pre-existing
final or `.partial` output paths;
there is no resume or restart mode. Failure leaves `.partial` and a terminal
journal record for review. It never substitutes or estimates a sample.

Before creating output, admission must prove:

- hostname `dev-ai`, model `AMD EPYC 7502P 32-Core Processor`, and the exact
  topology `0..31 -> cores 0..31`, `32..63 -> SMT siblings 0..31`;
- the only permitted affinity is `taskset -c 0-15`, with four thread-related
  environment variables pinned to 4;
- one-minute load below 8.0 and no competing Cubrim, perf, Cargo, Rust, or
  same-runner process;
- exact source commit, detached clean tracked tree, binary and runner hashes;
- `/root/phaseC/corpus_manifest.tsv` identity and the three exact `text`
  source rows above;
- successful `perf stat` and `perf record` smoke probes;
- exact debug-build codec identity on a fixed short fixture: generate 65,536
  zero bytes with `/usr/bin/dd`, require source SHA-256
  `de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31`,
  encode twice at preset `max`, and require both 50-byte archives plus their
  byte comparison to match SHA-256
  `352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3`;
  one decode must byte-match the fixture, and no timing value is read;
- full release suite and real scheme-roundtrip suite success, with generated
  build side effects captured and removed before a clean-status assertion.

## G1: archive and round-trip gates

For each cell the runner performs two independent encodes. Both archives must
have the registered SHA above and be identical by `cmp`. The second archive
is used for profiling. Each of the five independent decodes below must exit
zero and match the source by both `cmp` and the registered original SHA:

1. one plain pinned decode timed with `/usr/bin/time -v`;
2. two pinned `perf stat` decodes;
3. two pinned `perf record -F 997 -e cycles` decodes.

Every process has its cell-specific timeout and the remaining monotonic
campaign budget. Any archive, source, exit, timeout, or round-trip failure
voids the campaign before performance values are interpreted.

## G2: current-main counters and G3 perturbation

Each `perf stat` run requests explicit supported events from this set:
`task-clock`, `cycles`, `instructions`, `branches`, `branch-misses`,
`cache-references`, `cache-misses`, `dTLB-load-misses`, and `page-faults`.
Supported L1-dcache events may be preserved descriptively. Unsupported events
remain labelled unsupported; generic misses are never converted into a stall
percentage.

For each file, cycle disagreement is `abs(a-b)/max(a,b)`. Values at or below
0.10 are `cycle-agreement`; otherwise cycles/bit is suppressed. IPC and
misses/bit retain both independent samples and are never averaged across
files.

For each record sample, G3 is `record_wall/plain_wall`. A value at or below
1.10 is clean; a higher value is instrument-perturbed. Symbol/source-line
shares remain descriptive when perturbed, but a perturbed sample cannot
support cycles/bit.

## Frozen instruction attribution

The exact debug-line binary is disassembled before the first encode in both
raw-symbol form (`objdump --disassemble --line-numbers`) and human-readable
form (`objdump --disassemble --line-numbers --demangle`), with source/inline
frames resolved by `addr2line -a -f -C -i`. The raw-symbol stream is
authoritative for joining:
the host's `perf script` preserves Rust-v0 mangled symbols even when demangling
is requested, so a demangled objdump key would not match it. The runner writes
an immutable `instruction-map.tsv`. To keep evidence bounded, it correlates
raw and demangled headers by identical symbol start, retains every instruction
only from symbols whose demangled name belongs to `cubrim::cm2`, and resolves
only that compact address set. It records the full transient disassemblies'
hashes, byte counts, and line counts plus the compact raw, compact demangled,
compact addr2line, and map hashes. It rechecks the compact artifacts and map
before each `perf record` and at finalization. Each map row records the
object-relative instruction address, raw perf-compatible symbol plus offset,
resolved file/line, an independently derived `target_owner` boolean, and
exactly one bucket. `target_owner` is determined before bucket assignment
from an exact target source frame or direct target-function owner/symbol; an
inlined target frame remains an owner even when its outer frame is not a
target function. Runtime samples are normalized
through the exact recorded DSO/raw-symbol offset; a PIE/ASLR virtual address is
never joined directly to an object-file offset. An unknown offset within a
retained CM2 symbol fails closed; an exact-binary symbol outside that reviewed
CM2 set is `other_user`. The map uses these exact `e0e8bdb` `cm2.rs` source
buckets:

- `state_map_predict`: lines 235–238;
- `state_map_predict_call`: line 296, excluding instructions resolved to the
  inlined `state_map_predict` body;
- `state_map_update`: lines 240–248, except instructions resolved inside
  `sm_div`;
- `state_map_update_call`: line 314, excluding instructions resolved to the
  inlined `state_map_update` or `sm_div` body;
- `sm_div`: lines 97–104;
- `ctr_predict_stationary`: lines 291–299, excluding line 296 and inlined
  StateMap lines;
- `ctr_update_stationary`: lines 301–313;
- `ctr_next_state`: line 315;
- `ctr_record_store`: line 316;
- `target_unresolved`: an instruction whose demangled owner is one of the
  targeted functions but whose frozen inline/source frames do not assign it
  to a semantic bucket above; this bucket is never redistributed after
  sampling;
- every non-target sample remains visible without reinterpretation as its
  exact symbol plus offset under `other_user` for the exact Cubrim DSO,
  `kernel` for `[kernel.kallsyms]`, or `other_dso` otherwise.

Before sampling, every independently marked target-owner instruction address
must be assigned exactly once to a semantic bucket above or
`target_unresolved`; a non-owner may not enter a target bucket. Coverage must
be 100%, with no overlaps, drops, or duplicate DSO/symbol-offset keys. The
binary, build ID, symbol ranges, mapper,
resolver commands, tool versions, and complete map are hash-frozen before
`perf record`. If inlining produces an unresolved owner, it remains in
`target_unresolved`; no nearest-line inference or post-run redistribution is
allowed. A multiply mapped or dropped address, or failure of the debug-line
build to reproduce the registered archive bytes, is `VOID`.

Each record reduction retains sample count, period sum, and squared-period sum
for every bucket. For the union of the nine semantic target buckets and
`target_unresolved`, effective sample size is
`N_eff = (sum(period))^2 / sum(period^2)`. With six fixed records, the
simultaneous one-sided 95% zero-hit upper bound is
`U = 1 - (0.05/6)^(1/N_eff)`. Candidate eligibility requires, separately in
every record: zero `PERF_RECORD_LOST`/lost-sample records, both
`target_unresolved` sample count and period equal to zero, `N_eff >= 4787`, and
`U <= 0.001` (0.10 percentage points). Zero observed unresolved samples is
reported only as this bounded observation, never as proof that the
instructions did not execute.

The two record samples are reduced independently. Each targeted bucket's
absolute share difference must be at most 1.00 percentage point per file.
The report retains both shares and may use their within-file arithmetic mean
to compute that file's perfect-component Amdahl ceiling `1/(1-share)`.

## Prospective predictions

For these predictions, the per-file composite `state_map_total` is exactly
`state_map_predict + state_map_predict_call + state_map_update +
state_map_update_call + sm_div`. The per-file composite `whole_update` is
exactly `state_map_update + state_map_update_call + sm_div +
ctr_update_stationary + ctr_next_state + ctr_record_store`. Component shares
are summed within one record sample before the two-sample stability test; no
cross-file reduction is allowed.

- **P1 — current-path change:** the current whole `Ctr`/StateMap update share
  differs from historical G2 by at least 5 percentage points on each max cell.
  A failure is a result, not permission to reuse G2's ceiling.
- **P2 — sample-visible mapping coverage:** all six fixed records have zero
  lost samples, zero `target_unresolved` count and period, `N_eff >= 4787`, and
  simultaneous 95% upper bound `U <= 0.001`. Any nonzero unresolved count or
  period is `REFUTED`; zero unresolved with inadequate sample size/bound or
  lost samples is `INDETERMINATE`. Neither state implies the StateMap
  mechanism itself is cold.
- **P3 — StateMap materiality:** `state_map_total` is at least 5.00% on at
  least two cells. This is the minimum gate
  for considering an isolated StateMap lever later.
- **P4 — same-byte preset control:** the StateMap bucket difference between
  `dickens/max` and `dickens/web` is at most 10 percentage points. A larger
  change means selection must be preset-specific.
- **P5 — repeatability:** both record samples agree within 1.00 point for
  every targeted bucket, both stat samples agree within 10% cycles, and both
  record samples are G3-clean in every cell.

P1–P5 are evaluated exactly as written as `SUPPORTED`, `REFUTED`, or
`INDETERMINATE`. They do not constitute a candidate selection.

## Decision and void rules

The campaign is `VALID-CURRENT-PROFILE` only if every admission, suite,
archive, five-decode round-trip, cycle-agreement, instruction-map, targeted
share-stability, terminal exit, and evidence-manifest gate passes. A completed
correct run that fails any statistical selection gate—including cycle or
share stability, unresolved/lost/insufficient effective samples, or G3
perturbation—still finalizes as `VALID-DESCRIPTIVE-PROFILE` but is
`NO-SELECT`. Correctness, identity, tool execution/parsing, timeout, map
integrity/coverage, or evidence failure is `VOID`, with the exact reason
preserved in the journal.

SM32 is merely eligible for later independent selection if P2, P3, and P5
are supported. P3 failure makes SM32 `NO-SELECT`; an unmapped residual family
cannot be selected from this
campaign and requires its own prospective attribution protocol after this raw
evidence and report land. A later candidate requires its own prospective
ceiling, acceptance thresholds, and preregistration on `main` before its
source is built.

`state_map_total` is a conservative whole-target perfect-elimination ceiling,
not a pack-addressable share: it includes arithmetic such as `sm_div` and
other work that packing cannot remove. A later SM32 preregistration must not
translate that ceiling into an expected packing gain without a separately
frozen pack-relevant instruction analysis.

## Evidence and publication boundary

On success the runner writes `TIMING-DONE.STAMP` last, produces exhaustive
SHA-256 manifests, makes the raw tree read-only, and atomically renames
`.partial` to final. On failure `.partial` remains immutable evidence and no
final stamp exists. The unit must terminate once with exit 0, `NRestarts=0`,
and no surviving process before any value is read.

The raw tree, deterministic parser, per-file report, and independent spec and
quality reviews must land through a normal protected PR before any lever is
selected. This profile creates no measurement/evaluation row and writes no
database, API, site, social channel, or credentials. A later reviewed DB
transaction may append only a non-scoring pointer to the landed report while
NEW-24 stays `in_progress`, measurements stay empty, and evaluation stays
zero.
