# Preregistration: NEW-24 full-binary residual attribution G5

**State:** prospective design/preregistration only. G5 has not launched, and
no G5 performance sample exists. This document does not authorize launch.

## G4 — immutable VOID / NO-SELECT

The exact G4 one-shot ended `VOID / NO-SELECT` during admission because a
mock cgroup self-test subprocess inherited the live campaign's
`CUBR_SYSTEMD_UNIT`. The inherited authority changed the mock sentinel's
expected stop target and caused the reviewed admission contract to reject the
run. The failure occurred after nine admission-only `perf stat` capability
probes but before any campaign cell, `perf record`, `perf.data`, product
performance record, or campaign sample row. Those retained capability probes
are non-performance failure evidence: they were not interpreted, and no
performance outcome informed this G5 design.

G4's campaign-output tree and terminal journal are immutable,
nonauthoritative failure evidence. Its campaign-output namespace consists only
of
`/root/cubr-new24-full-binary-g4-20260809` and that exact path with
`.partial`, `.publishing`, or `.late` appended. Those paths MUST remain under
their G4 names and MUST NOT be edited, renamed into a G5 namespace, appended
to, reinterpreted, ingested, or used as sample substitution. The G4
designation and its exactly-once allowance are consumed. An environment
reload, parameter change, surrogate admission, partial checkpoint, or
relabelled launch cannot make another G4 run valid. G4 is never retried,
restarted, resumed, or repaired in place.

## G5 — fresh, separately named experiment

G5 is a new characterization experiment with a new designation, unit,
`InvocationID`, PID baseline, output namespace, `CLOCK_MONOTONIC` start, and
campaign budget. It does not inherit G4 process state, campaign time, partial
output, or performance evidence. A G4 non-performance artifact may be reused
only when this protocol permits the artifact class and the pre-launch seal
re-authenticates its exact content hash and provenance; reuse never transfers
G4 campaign identity or authority.

G5 is governed exclusively by this protocol. It MUST NOT launch until every
pre-launch predicate below is satisfied by concrete reviewed identities on
`origin/main`. Renaming the G4 runner or output without satisfying those
predicates is an impermissible G4 retry, not G5.

## Code-under-test baseline

The immutable code-under-test baseline retained from G4 is commit
`830a9a31deb00926a97f3fa5bd74f58003573fc0`. G5 builds only from a detached,
clean checkout of that exact baseline and records its full tree plus the
explicit `code/cubrim-rs` and Cargo-input subtree identities. No source
candidate is built or selected by this characterization protocol.

The G5 runner and its tests are outside this design-only slice. Before launch,
they and this preregistration MUST land through normal protected PRs. The
resulting-main instrument commit and exact mapper, runner, and test blobs are
frozen separately from the code-under-test baseline. A PR-head commit, local
branch, or uncommitted worktree is insufficient. The campaign may start only
after a fresh fetch proves `origin/main` contains every reviewed instrument
blob and the detached code-under-test tree still equals
`830a9a31deb00926a97f3fa5bd74f58003573fc0`. Any mismatch is `VOID` before
sampling.

## Frozen scope

The code-under-test build uses Cargo release code generation with line debug
information (`CARGO_PROFILE_RELEASE_DEBUG=1`); debug assertions remain
disabled. Before any campaign encode or decode, the journal freezes the exact
source baseline commit/tree/subtrees, clean detached-tree proof, generated
`Cargo.lock`, compiler/Cargo versions, release flags, binary SHA-256, ELF
build ID, separate instrument resulting-main commit, runner SHA-256, mapper
SHA-256, test hashes, and every mapping artifact hash.

Only these cells run, always reported separately:

| cell | archive SHA-256 | original SHA-256 | bytes | encode timeout s | decode timeout s |
|---|---|---|---:|---:|---:|
| `dickens/max` | `b39d5043a6b615a261c8904d104f01f3d5fe948b0ef46e001acd2d869b7ddc82` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 1340 | 435 |
| `xml/max` | `d64f83f33552922d41e1c32f22f14b283844079b1509d43109140e26a1425a37` | `0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c` | 5345280 | 520 | 175 |
| `dickens/web` | `a77d540decf56c5db98278d18799a8095d9d87adc037cb40639bb2e3577bc341` | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` | 10192446 | 380 | 320 |

`x-ray/max` remains excluded because it routes through geocm and cannot
characterize the CM decode path. No corpus mean, geometric mean, combined
speedup, profiling throughput, or cross-file family share is permitted.

## One-shot admission and execution

The reviewed runner is launched exactly once on `dev-ai` in a transient
systemd service with `Type=exec`, `Restart=no`, and
`RuntimeMaxSec=4h`, `KillMode=control-group`, `KillSignal=SIGTERM`, and
`FinalKillSignal=SIGKILL`. The live unit `InvocationID` must equal the runner
environment and its `MainPID` must equal the runner process. Its exact
`ControlGroup` property must resolve without traversal or symlinks to one
`/sys/fs/cgroup/.../cgroup.procs` file. Admission freezes the numeric PID set
from that file, including the runner. After every bounded call and immediately
before the final acceptance rename, any PID outside that frozen set (apart
from the authenticated publisher ancestry at the precommit check) voids the
campaign and requests a stop of that exact unit. The runner never discovers or
kills a survivor by scanning an SID or unrelated process. A separate
monotonic campaign budget is 14,400 seconds. There is no retry, restart,
resume, or sample substitution.

The precommit publisher exception is not membership-by-assertion: its `/proc`
parent walk must keep every visited PID in the exact bound `cgroup.procs` set
and terminate at exactly one frozen baseline PID. Reaching PID 1, leaving the
bound cgroup, losing or malforming a parent record, or encountering a cycle
before that baseline is a hard void and requests the exact-unit stop. A
disconnected fixture containing only a baseline PID, worker PID, and publisher
PID must therefore leave no final tree even though every fixture PID appears in
`cgroup.procs`.

## Cgroup self-test with sanitized allowlisted environment

Admission MUST retain the production cgroup guard and its bounded
double-fork/TERM-ignoring descendant test. The repair is an authority-boundary
change at mock subprocess creation, not weaker acceptance.

The runner-test harness MUST have one reviewed helper for mock-only cgroup
subprocesses. That helper MUST start with an empty environment and populate a
closed allowlist. For the pure sentinel fixture the complete allowlist is
`LC_ALL=C`, `PATH=/usr/bin:/bin`, and
`CUBR_SYSTEMD_UNIT=mock.unit`. For the disconnected-precommit fixture the
complete allowlist is `LC_ALL=C`, `PATH=/usr/bin:/bin`, and
`CUBR_SYSTEMD_UNIT=precommit-disconnected.service`. Fixture paths and the stop
sentinel are created inside the fixture root by the invoked self-test; they are
not inherited authority.

The user-systemd live fixture is distinct from those pure mocks. Its outer
launcher MUST additionally pass exactly `HOME`, `XDG_RUNTIME_DIR`, and
`DBUS_SESSION_BUS_ADDRESS` from the admitted host, plus the pure-mock
`LC_ALL` and `PATH` values. Each copied value MUST be nonempty; otherwise the
live fixture is unsupported and launch is blocked. It MUST strip the
campaign's `CUBR_SYSTEMD_UNIT`,
`INVOCATION_ID`, `CUBR_CGROUP_SYSTEMCTL_USER`, and
`CUBR_CGROUP_LIVE_RESULT`. The fixture creates a fresh G5-prefixed transient
unit, and `systemd-run --setenv` assigns that fixture unit and fixture-local
result path to the worker. Neither the outer mock launcher nor its worker may
derive a unit from the campaign environment.

The contract tests MUST poison their own parent environment with
`CUBR_SYSTEMD_UNIT=g4-live-authority-must-not-be-used.service` and prove that
the sentinel contains only the applicable fixture unit. They MUST also prove
that the live G5 campaign unit name never appears in mock output, a sentinel,
or a systemctl argument. The live fixture still MUST prove that
`KillMode=control-group` removes its setsid double-fork descendant that ignores
TERM. A mutation that removes the empty-environment boundary, admits the
poisoned variable, substitutes the campaign unit, or skips the descendant
check MUST fail at the intended assertion.

After every self-test, admission MUST re-read the G5 campaign unit and verify
its original `InvocationID`, `MainPID`, `NRestarts=0`, and exact
`ControlGroup`. A mismatch is a hard pre-sample void and requests a stop of
that exact G5 unit.

Two alternatives are forbidden:

1. Tolerating an inherited live unit because the mock still returns an
   expected exit code. This preserves ambient authority and cannot distinguish
   the fixture from the campaign.
2. Removing, skipping, or weakening the cgroup self-test. This discards the
   proof that `KillMode=control-group` contains a descendant that escapes a
   process group and ignores TERM.

## Admission prerequisites

Admission must establish:

- hostname `dev-ai`, CPU model `AMD EPYC 7502P 32-Core Processor`, and
  topology `0..31 -> cores 0..31`, `32..63 -> SMT siblings 0..31`;
- the only permitted affinity is `taskset -c 0-15`; the pin MUST NOT widen
  and samples MUST NOT be shortened;
- `CUBR_THREADS=4`, `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=4`, and
  `MKL_NUM_THREADS=4` for every build, encode, decode, and perf subprocess;
- one-minute load below 8.0 and no competing Cubrim, perf, Cargo, Rust, or
  same-runner process, using a stable process snapshot that excludes only the
  runner and its known parent;
- exact source, binary, build-ID, runner, mapper, toolchain, corpus-manifest,
  and three registered corpus-row identities;
- supported `perf stat` events and successful `perf record` operation;
- fixed-fixture codec identity: 65,536 zero bytes with SHA-256
  `de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31`,
  two `max` encodes that are both 50 bytes and match SHA-256
  `352840f3350619078b42ff316ade28a2b4a9e2ce5dd9385c439ed2a27bb0cae3`,
  plus one byte-exact decode;
- the full release suite and real scheme-roundtrip suite, followed by removal
  of captured build side effects and a clean tracked-source assertion;
- the sanitized cgroup self-test exiting zero, with its captured contract-test
  output and SHA-256 bound into the pre-launch seal;
- a complete frozen full-binary instruction map, constructed before the
  address-join smoke described below.

The runner refuses a pre-existing final, `.partial`, `.publishing`, or `.late`
output path. A failure leaves immutable, nonauthoritative `.partial` or
`.publishing` evidence plus an exact terminal journal reason; any final path
observed after rejection is atomically quarantined as `.late`.

## G1: archive and round-trip correctness

For each cell the runner performs two independent encodes. Both archives must
match the registered SHA-256 and each other by `cmp`; the second is used for
profiling. Each of these five independent decodes must exit zero and match the
registered original by both `cmp` and SHA-256:

1. one pinned plain decode timed by `/usr/bin/time -v`;
2. two pinned `perf stat` decodes;
3. two pinned `perf record -F 997 -e cycles` decodes.

Every process uses the cell timeout and remaining monotonic campaign budget.
Any archive, source, exit, timeout, or round-trip failure is `VOID` before
performance data is interpreted.

## G2: per-file counter and perturbation gates

Each stat run requests explicit supported events from `task-clock`, `cycles`,
`instructions`, `branches`, `branch-misses`, `cache-references`,
`cache-misses`, `dTLB-load-misses`, and `page-faults`. Supported L1-dcache
events may remain descriptive. Unsupported events stay labelled unsupported;
generic misses are never converted into stall time.

For each file, cycle disagreement is `abs(a-b)/max(a,b)`. At or below 0.10
is `cycle-agreement`; otherwise cycles/bit is suppressed. IPC and misses/bit
retain both samples and are not combined across files.

For each record, perturbation is `record_wall/plain_wall`. At or below 1.10
is `instrument-clean`. A higher value is descriptive only and cannot support
an attribution-grade result.

## G3: frozen full-binary instruction map

### Executable address universe

The mapper reads ELF program headers, section headers, symbols, build ID, and
the complete disassembly of every executable section from the exact binary.
It records every executable `PT_LOAD` segment and section with virtual-address
range, file-offset range, alignment, flags, and hashes. Every decoded
instruction start retains its ELF virtual address, but the sole runtime join
coordinate is its canonical DSO file offset:

```text
dso_file_offset = p_offset + (instruction_vaddr - p_vaddr)
```

Exactly one executable `PT_LOAD` segment must contain the instruction VMA and
its file-backed byte. The forward conversion and reverse conversion
`instruction_vaddr = p_vaddr + (dso_file_offset - p_offset)` must be unique and
exact, including nonzero and unequal `p_vaddr`/`p_offset` cases. Duplicate
VMAs, duplicate canonical offsets, incompatible segment overlap, a decoded
address outside an executable segment/section, or an empty executable
universe is `VOID`. A synthetic mutation fixture with unequal VMA and file
offset must fail if either coordinate is compared directly to the other.

The exhaustive disassembly, resolver stream, and rendered map may be large.
Their canonical evidence form is deterministic `gzip -n -9` output. The
journal records both the uncompressed byte count/SHA-256 and compressed
byte count/SHA-256; the uncompressed transient is removed only after a
decompression hash check. No committed evidence object may exceed the hosting
limit. The hard per-object protocol maximum is 90,000,000 bytes, below the
100 MiB host rejection threshold. If splitting is required, an ordered part
manifest freezes for every part its index, first/last canonical DSO offset,
row count, uncompressed byte count/SHA-256, and compressed byte count/SHA-256.
Part ranges must be strictly increasing, disjoint, and contiguous in the
independently enumerated ordered instruction-row sequence. Ordered
decompression and concatenation must exactly reproduce the pre-split canonical
stream byte count, row count, and SHA-256. Extra parts, missing/duplicate rows,
extra gzip members, or trailing bytes are rejected. Completeness is rechecked
against the executable universe rather than inferred from the part manifest
itself.

Full map construction has an independent 1,200-second admission timeout and
remains inside the 14,400-second campaign budget. Before G5 may launch, the
exact mapper MUST either complete a no-performance dry run on the exact G5
binary or re-authenticate the permitted byte-identical static artifacts under
the reuse rule below. The resulting fresh G5 seal freezes the complete
instruction universe, all split/reassembly checks, every part below
90,000,000 bytes, elapsed tool time, peak RSS, row count, and output sizes.
This timing characterizes the instrument only, takes no product-performance
sample, and does not resolve P1–P5. Mapping identity derives only from the
frozen binary, mapper, mapper-test, schema, toolchain, and map artifacts;
runner and runner-test provenance remains independently frozen.

Padding or undecoded bytes remain explicit executable-range gaps. A runtime
sample at a gap is never rounded to the nearest instruction; it is
`binary_unresolved` and voids the campaign.

### Mechanical three-level ownership

For every instruction address, the map records exactly one row with:

- instruction VMA, canonical DSO file offset, executable segment, and section;
- exact raw outer emitted symbol plus offset, or `raw_symbol_unresolved`;
- the complete ordered `addr2line -a -f -C -i` inline-frame stack;
- a mechanically derived innermost source-family key;
- a resolution status.

Two family levels are generated mechanically. `emitted_family` is the exact
raw outer symbol identity. `source_family` is a collision-closed tuple of
source domain, package identity, normalized path, innermost item, exact
innermost source location, raw outer symbol, and the SHA-256 of the complete
ordered inline-frame stack. Source domain distinguishes workspace code, Rust
standard library with rustc commit, exact Rust-distribution dependency roots
with rustc commit and crate version, Cargo crates with
name/version/checksum, and the one observed system header with exact
package/version/content identity. A path is normalized through the frozen
prefix table; every absolute resolver location must match exactly one
namespace-distinct rule, and an unknown, ambiguous, or lexically escaping
root is `VOID` before sampling. Raw symbol identity remains separate;
demangled spelling is informational and is never a sample join key. Standard
library, dependency, runtime, and Cubrim code all follow the same rule. There
is no hand-selected family table, no outcome-driven top-N list, and no manual
merging, pruning, or relabelling after outcome access.

Every rendered family key is reverse-indexed to its full canonical provenance
tuple. A key collision between distinct tuples, including closures with the
same displayed name, is `ambiguous_inline_owner`; it is never silently merged.
If no source frame exists, the row is `binary_unresolved`. If repeated
resolution of the same address returns conflicting ordered frame stacks, the
row is also `ambiguous_inline_owner`. Both states remain visible and are never
redistributed. Map construction is admissible only with 100% one-row-per-
instruction coverage, no duplicate VMA or DSO offset, stable repeated
resolution, collision-free reverse indexes, and hash-stable rendered output.

### Symbol-independent runtime join

`perf record` uses `--buildid-all --buildid-mmap`; device/inode MMAP2 union
records are not accepted by this protocol. Before reduction of each
`perf.data`, `perf buildid-list -i` must contain exactly one entry binding the
expected Cubrim filename to the registered ELF build ID. `perf script` is
invoked with fields `period,ip,dso,dsoff` and `--show-mmap-events`. Its Cubrim
MMAP2 record must be the build-ID union form and carry that same exact build
ID, filename, executable protection, file-offset range, and one unambiguous
runtime mapping. The binary path is independently opened without following
symlinks; its build ID, SHA-256, size, device, inode, and executable-segment
metadata must equal the admission snapshot before and after every record.
Missing, mixed, or ambiguous MMAP2 union modes are `VOID`.
The frozen page size is 4,096. The executable PT_LOAD must satisfy ELF page
congruence (`p_offset % page_size == p_vaddr % page_size`); the accepted MMAP2
has `pgoff = align_down(p_offset,page_size)` and
`length = align_up((p_vaddr-align_down(p_vaddr,page_size))+p_filesz,page_size)`.
It must use exact `r-xp` protection and a page-congruent load bias. `p_memsz`
never silently widens this file-backed range.
For every exact-binary sample, the mapper independently computes:

```text
object_offset = runtime_ip - mmap_start + mmap_pgoff
```

The computed value must equal perf's parsed `dsoff`, and it must match exactly
one frozen instruction address. Symbols are neither requested nor consulted.
Samples outside the exact binary are accepted only as the frozen kernel
spellings (`[kernel.kallsyms]`, `[kallsyms]`), preregistered pseudo-DSOs
(`[vdso]`, `[vsyscall]`), or authenticated DSO snapshots with exact sampled-
path cardinality. Each such DSO path must be canonical and absolute, every
component must exist without symlinks, and the final node must be regular.
The mapper opens the node with `O_NOFOLLOW`, then uses that same descriptor to
compute SHA-256 and independently read the GNU build ID plus executable
PT_LOAD identities. Pre/post `fstat` device, inode, size, mtime, and ctime must
remain stable. The authenticated build ID must equal both `perf buildid-list`
and the applicable executable build-ID MMAP2 identity; that MMAP2 must match
exactly one snapshotted executable PT_LOAD, use `r-xp`, and satisfy the frozen
page-offset, length, and load-bias rules. The entire snapshot is reauthenticated
after reduction and must compare exactly. Missing, extra, mutated, symlinked,
nonregular, or identity-mismatched DSO snapshots are `VOID`.
`unknown`, `(unknown)`, `[unknown]`, arbitrary bracket tokens, relative paths,
controls, traversal, and unauthenticated absolute paths are `VOID` rather than
`other_dso`.

Before the first campaign encode, a non-timed fixed-fixture `perf record`
smoke must contain at least one exact-binary sample, and every exact-binary
smoke sample must satisfy the MMAP2 formula, `dsoff` equality, build-ID match,
and exact instruction join. This smoke is a tool/identity feasibility gate;
none of its timing or family shares is read or retained as a performance
result.

For each campaign record, every observed period is assigned exactly once.
The sum of all bucket periods and sample counts must equal the raw perf-script
totals, and squared-period sums are retained. Any lost record, unknown DSO
identity, multiple applicable mapping, MMAP2/dsoff disagreement, exact-binary
non-instruction offset, or period-conservation failure is `VOID`.
Any exact-binary sample joining a row whose resolution status is not exactly
`resolved`, including `binary_unresolved` or `ambiguous_inline_owner`, is also
immediately `VOID`; it cannot be downgraded to `VALID-DESCRIPTIVE`.

## Statistical and repeatability gates

The uncertainty trial is one retained exact-binary `PERF_RECORD_SAMPLE`, not
its period weight. Conditional on zero loss and exact address conservation,
the frozen sampling model treats those sample rows as exchangeable draws from
the cycle-weighted exact-binary execution distribution produced by perf
frequency mode at `-F 997`. Periods still determine shares, but they are not
substituted for a Bernoulli trial count.

For each fixed record with `n_binary` exact-binary sample rows and zero
unresolved rows, the exact one-sided Clopper-Pearson zero-hit bound with a
Bonferroni family-wise allocation across six records is:

```text
U_binary = 1 - (0.05/6)^(1/n_binary)
```

This is the exact zero-success binomial inversion under the stated sampling
model (Clopper and Pearson, *Biometrika* 26(4), 1934,
doi:10.1093/biomet/26.4.404); the six-way alpha allocation makes the joint
one-sided coverage at least 95% by Bonferroni. The model and its limitation are
reported with every result; the bound is not a claim about unexecuted code.

Attribution-grade evidence requires, separately in every record,
`n_binary >= 4787`, `U_binary <= 0.001`, zero lost records, and zero
`binary_unresolved` or `ambiguous_inline_owner` runtime samples and period.
Zero observed unresolved samples are reported only with this bound and never
as proof that unobserved code did not execute.

Emitted-family and source-family shares use total observed period in that
record, including kernel and other-DSO period in the denominator. A family
enters the repeatability set for a file when its share is at least 5.00% in
either record. Its explicit shares from both records, including a zero, must
differ by at most 1.00 percentage point. Thus a 9%/4% or 12%/0% family cannot
escape P5. Non-material families remain in the exhaustive output but do not
enter the repeatability predicate. No family shares are combined across
files.

A per-file perfect-family Amdahl ceiling may be computed only for a material,
repeatable family from its two-record arithmetic mean share. It is a
characterization ceiling, not a candidate expectation or selection.

## Filesystem and parser safety

Every binary, source, map, perf, gzip, manifest, raw, and analysis path MUST be
contained beneath its declared root after component-wise validation. Roots and
every descendant are enumerated with `lstat`; symlinks, FIFOs, sockets,
devices, unexpected directories, and other non-regular nodes are rejected.
Regular inputs are opened with no-follow semantics and rechecked by `fstat`.
Manifest paths are canonical relative paths with no absolute path, `..`,
duplicate, alternate spelling, or unlisted node.

Writes use randomized exclusive temporary files inside the validated output
root, flush and `fsync`, then atomically replace their destinations. Negative
tests MUST cover directory and broken symlinks, FIFOs, path escape,
predictable-temporary attacks, replacement failure, malformed or oversized
rows, duplicate keys, and decompression bombs before launch.

## Frozen predictions

These predictions characterize the exact baseline. They do not name a winning
family or authorize a source candidate:

- **P1 — static map integrity:** the full executable universe has 100%
  unique instruction-row coverage, stable resolver output, no incompatible
  range overlap, and no post-freeze hash drift.
- **P2 — address normalization:** the pre-cell smoke has at least one
  exact-binary sample; every exact-binary smoke sample matches the registered
  build ID, one MMAP2 mapping, the independent offset formula, perf `dsoff`,
  and exactly one map row.
- **P3 — record integrity:** all six records have zero loss, exact sample and
  period conservation, and every exact-binary sample joins exactly once by
  address without consulting a symbol string.
- **P4 — attribution power:** separately in all six records,
  `n_binary >= 4787`, `U_binary <= 0.001`, and there are zero runtime samples
  or period in `binary_unresolved` and `ambiguous_inline_owner`.
- **P5 — repeatability:** both stat samples are within 10% cycles, both
  record samples have `record_wall/plain_wall <= 1.10`, and every mechanically
  generated family reaching at least 5.00% share in either record differs by
  at most 1.00 percentage point between that file's two records.

P1–P5 are evaluated exactly as `SUPPORTED`, `REFUTED`, or `INDETERMINATE`.
They are per-file characterization results only. Their definitions,
thresholds, and routes MUST NOT change after any G5 performance sample exists.

## Decision routes

The campaign is `VALID-ATTRIBUTION / NO-SELECT` only when every admission,
suite, archive, round-trip, terminal, static-map, smoke, record-integrity,
attribution-power, cycle, perturbation, and repeatability gate passes.

It is `VALID-DESCRIPTIVE / NO-SELECT` only when correctness, identity,
mapping, conservation, and terminal gates pass but sample size, perturbation,
cycle agreement, or family repeatability is insufficient. Affected ceilings
are suppressed.

It is `VOID / NO-SELECT` for any identity mismatch, correctness failure,
timeout, lost record, static-map failure, MMAP2 or `dsoff` mismatch, unknown
exact-binary instruction offset, ambiguous ownership, period-conservation
failure, environment-isolation failure, evidence failure, or nonterminal
execution. A void is preserved and never retried. No route selects a source
change.

## Fresh G5 identities and namespaces

The following names are exclusive to G5:

- source checkout: `/root/cubr-new24-full-binary-g5-src`;
- build target: `/root/cubr-new24-full-binary-g5-target`;
- instrument checkout: `/root/cubr-new24-full-binary-g5-instrument`;
- accepted output: `/root/cubr-new24-full-binary-g5-20260810`;
- nonauthoritative work paths: that output plus `.partial`, `.publishing`,
  and `.late`;
- transient unit: `cubr-new24-full-binary-g5-20260810.service`.

Before launch, none of the four accepted-output variants --
`/root/cubr-new24-full-binary-g5-20260810`, that path plus `.partial`, that path
plus `.publishing`, and that path plus `.late` -- or the G5 unit may exist. The
runner MUST refuse a collision; it MUST NOT delete, reuse, rename, or repair a
colliding path or unit. No G4 path, unit, PID baseline, `InvocationID`, clock,
or journal may satisfy a G5 predicate. The live G5 unit's `InvocationID` and
`MainPID` MUST equal the runner environment and PID, and its exact
`ControlGroup` MUST bind one traversal-free, nonsymlinked
`/sys/fs/cgroup/.../cgroup.procs` file.

The G5 runner is launched exactly once on `dev-ai` with `Type=exec`,
`Restart=no`, `RuntimeMaxSec=4h`, `KillMode=control-group`,
`KillSignal=SIGTERM`, and `FinalKillSignal=SIGKILL`. Its independent monotonic
budget is 14,400 seconds. There is no retry, restart, resume, continuation,
sample substitution, shortened sample, widened CPU pin, or second launch. If
G5 voids before sampling, the correct route is an immutable G5 void and a new
prospective protocol—not another G5 attempt.

## Mandatory hash and provenance seal

This design intentionally contains no invented future hash. Before launch, a
protected resulting-main amendment MUST record concrete lowercase SHA-256 or
Git object identities for every item below. Absence, non-hex text, a mutable
reference, or a mismatch blocks launch:

1. the G4 terminal journal and immutable failure-evidence manifest, together
   with their byte counts, the terminal admission-step identity, all nine
   admission-only `preflight/perf-*.csv` capability probes plus
   `preflight/perf-events.tsv` as uninterpreted non-performance evidence, zero
   `perf.data` files, zero campaign-cell directories, and zero campaign sample
   rows;
2. the G5 preregistration blob and resulting-main instrument commit;
3. source commit, full source tree, `code/cubrim-rs` subtree, Cargo input
   blobs, generated `Cargo.lock`, compiler/Cargo versions, release flags,
   binary SHA-256, ELF build ID, size, device, and inode;
4. runner, runner-test, mapper, mapper-test, mapping-schema, corpus manifest,
   and each of the three exact corpus-row identities;
5. the complete instruction-map stream, reverse index, deterministic gzip
   members, part manifest, row and byte counts, and fresh reviewed G5 compact
   map-admission seal; and
6. the sanitized-environment allowlist contract, its positive tests, poison
   test, live-unit noninterference test, and each required mutation test.

G4 static-map artifacts are non-performance evidence. They may avoid redundant
generation only if the pre-launch amendment proves byte-for-byte that the
source tree, binary, build ID, mapper, mapper test, mapping schema, toolchain,
page size, and every map artifact equal the reviewed identities, then creates
a fresh G5 seal binding those identities. Otherwise G5 MUST construct a fresh
map before sampling. No G4 `perf.data`, timing, family share, campaign verdict,
or capability-probe result may satisfy a G5 gate or be interpreted as a G5
performance outcome.

## Evidence and publication boundary

One immutable `CLOCK_MONOTONIC` start establishes a deadline exactly 14,400
seconds later and a work deadline 120 seconds before that. Every blocking
precommit command is capped at the smaller of its own limit and the remaining
work budget. The exact cgroup is checked after every bounded call and
immediately before acceptance. Publication uses the same no-replace,
manifest-authenticated, read-only `.partial` to `.publishing` to final
transition as G4. The final rename is the sole acceptance point.

On any failure, only immutable nonauthoritative `.partial`, `.publishing`, or
`.late` evidence plus the exact terminal reason may remain. The transient unit
MUST terminate once with `NRestarts=0`, no surviving process, and a terminal
status before any performance value is read. A nonterminal tree, late final,
manifest mismatch, or surviving process is `VOID / NO-SELECT`.

## Database and external-effect boundary

G4 `VOID / NO-SELECT` produces no database write. G5 writes no database, API,
site, social channel, or credential path while running. It MUST NOT touch
`config/credentials/`. No G5 decision route, result bundle, or evidence PR
writes the database. NEW-24 remains `in_progress`; measurement fields remain
empty, `evaluation` remains zero, and no duplicate hypothesis row is created.
Any later evidence-pointer transaction is outside this protocol, requires its
own prospective review and authority, and cannot alter those measurement or
evaluation fields.

## Pre-launch hard gate

G5 remains `NO-LAUNCH` until all of the following are true on one fresh
`origin/main` read:

1. this preregistration and the immutable G4 void binding are on main;
2. the sanitized-environment runner correction and its exact tests are on
   main through a normal protected PR;
3. the complete hash/provenance seal above is on main;
4. the full release suite, real scheme-roundtrip suite, runner tests, mapper
   tests, poison test, live-unit noninterference test, and mutation tests pass
   for those exact blobs;
5. independent specification and quality reviews approve those exact blobs;
6. the detached code-under-test and every registered corpus identity still
   match this protocol; and
7. no G5 output path or unit exists and no competing process violates
   admission.

This design commit alone satisfies none of those launch predicates. No local
commit, PR head, earlier CI run, dry-run result, or consilium decision grants
launch authority.
