# Preregistration: NEW-24 full-binary residual attribution G4

**State:** prospective; no G4 performance sample has been collected. This is
a characterization-only protocol and cannot select a source candidate.

## Why G4 is required

The G3 campaign is preserved in PR #71 as `VOID / NO-SELECT`. Its frozen
instruction map used raw Rust-v0 mangled `symbol+offset` keys, but the host's
`perf script` emitted demangled labels. Across six records, 414,343
exact-binary sample rows produced zero exact key intersections with the 9,412
map keys. The producer silently labelled those samples `other_user`; the
independent reducer correctly rejected that as
`PERF_MAP_SYMBOL_NAMESPACE_MISMATCH`.

All G3 shares, ceilings, and P1–P5 outcomes are quarantined as
`NOT-EVALUATED`. G3 is not repaired, retried, or reinterpreted. G4 collects a
fresh sample only after a symbol-spelling-independent instrument lands on
`main`.

G4 separates the code-under-test identity from the measurement-instrument
identity. The immutable code-under-test baseline is commit
`830a9a31deb00926a97f3fa5bd74f58003573fc0`, which is current `origin/main`
before this preregistration/instrument PR. Its Cubrim code and Cargo input
blobs are unchanged from the G3 build commit. G4 builds only from a detached,
clean checkout of that exact baseline and records its full tree plus the
explicit `code/cubrim-rs` and Cargo-input subtree identities.

The preregistration, mapper, runner, and tests necessarily land later. Their
normal protected-PR resulting-main commit is frozen separately as the
instrument commit, along with exact mapper/runner/test blobs and hashes. The
campaign may start only after `origin/main` contains those reviewed instrument
blobs and the detached code-under-test tree still equals `830a9a31...`.
Subsequent unrelated main movement cannot alter either frozen identity; any
instrument-blob or source-tree mismatch is `VOID` before sampling.

## Frozen scope

The code-under-test build uses Cargo release code generation with line debug information
(`CARGO_PROFILE_RELEASE_DEBUG=1`); debug assertions remain disabled. Before
any campaign encode or decode, the journal freezes the exact source baseline
commit/tree/subtrees, clean detached-tree proof, generated `Cargo.lock`,
compiler/Cargo versions, release flags, binary SHA-256, ELF build ID, separate
instrument resulting-main commit, runner SHA-256, mapper SHA-256, test hashes,
and every mapping artifact hash.

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

Admission must establish:

- hostname `dev-ai`, CPU model `AMD EPYC 7502P 32-Core Processor`, and
  topology `0..31 -> cores 0..31`, `32..63 -> SMT siblings 0..31`;
- the only permitted affinity is `taskset -c 0-15`, with four
  thread-related environment variables pinned to 4;
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
100 MiB host rejection threshold. If splitting is required, an ordered part manifest freezes for every
part its index, first/last canonical DSO offset, row count, uncompressed byte
count/SHA-256, and compressed byte count/SHA-256. Part ranges must be strictly
increasing, disjoint, and contiguous in the independently enumerated ordered
instruction-row sequence. Ordered decompression and concatenation must exactly
reproduce the pre-split canonical stream byte count, row count, and SHA-256.
Extra parts, missing/duplicate rows, extra gzip members, or trailing bytes are
rejected. Completeness is rechecked against the executable universe rather
than inferred from the part manifest itself.

Full map construction has an independent 1,200-second admission timeout and
remains inside the 14,400-second campaign budget. Before this instrument may
land, the exact mapper must complete a no-performance dry run on the exact G4
binary, freeze and cover the exact observed instruction universe, pass all
split/reassembly checks, keep every part below 90,000,000 bytes, and record
elapsed time, peak RSS, row count, and output sizes as instrument-feasibility
evidence. This timing characterizes the tool only and is never a product
performance result.

Attempts 7 and 8 are retained as historical feasibility evidence only.
Subsequent mapper and mapper-test hardening changed the exact mapping-schema
identity, so neither attempt can admit the campaign even though neither took a
performance sample.

The replacement prospective dry run is sealed read-only at
`/root/cubr-new24-full-binary-g4-map-dryrun-attempt9-pass-20260810` on
`dev-ai`. Its mapping identity is derived only from the frozen mapper and
mapper-test blobs: mapper SHA-256
`36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1`,
mapper-test SHA-256
`97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314`,
and derived mapping-schema SHA-256
`1c8f5be539eaaa94f3a64d071e859ee5eccf8f4314908e143246f47bd8760e12`;
resulting-main, runner, and runner-test provenance remains independently
frozen in the outer campaign evidence and cannot perturb canonical map bytes.
Attempt 9 froze 739,548 instruction rows and 2,815,329 classified absolute
resolver-location rows at page size 4,096. The canonical instruction map is
1,111,781,924 bytes, SHA-256
`8bd7b254793cb5a3bf84b7e7c995f8f65d55e04e2e69d86340b876cb2a9d03b7`,
and reconstructs exactly from one 40,287,882-byte deterministic gzip part
(SHA-256 `cb8674ded7be56a114873ad86ea75771955107a8013adcf9ead48c9a136dc668`).
The 121,941,235-byte reverse-index summary (SHA-256
`bfcd4c3d3dc3fcb652c5e49cdb8fb60b4bb082cb4de0264456ccfb303948c961`)
is independently verified and stored as a 27,591,662-byte deterministic
single-member gzip object (SHA-256
`5811308b6c98bbd730c61aa98a08619a1ab99346cf5aa9f32d79eeb88ac495fe`).
All evidence objects are below 90,000,000 bytes. The dry run completed in
342.90 seconds with peak RSS 12,494,684 KiB. It took no performance sample and
does not resolve P1-P5. The reviewed compact admission seal is SHA-256
`565cce3c44c9fb8a228184e0af37270e0caeb2160f15c36b4690bc81aa139a6f`.

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

The address-normalization V-AC is feasible on the pinned host. After PR #71
landed, a read-only probe of the six quarantined G3 `perf.data` files used
`perf 6.8.12` fields `period,ip,dso,dsoff` plus `--show-mmap-events`. Each
record exposed exactly one executable Cubrim MMAP2 mapping and the registered
build ID `649a0cd9dab6d31cf3bbf45aab1f4aa3b890fadf`. The independent formula
matched perf `dsoff` for all exact-binary rows: 91,035 and 91,206 on
`dickens/max`, 37,912 and 37,923 on `xml/max`, and 78,052 and 78,215 on
`dickens/web`, with zero formula mismatch and zero ambiguous mapping in every
record. This probe read no timing or family-share outcome and does not make an
old sample admissible; it establishes only that the prospective runtime fields
and normalization equation are available.

A separate non-Cubrim tool smoke verified the frozen build-ID union mode on
the same host and perf version. `perf record --buildid-all --buildid-mmap`
recorded `/usr/bin/python3.12` with build ID
`04657a7aa3577f9234b186f9a5918f06030389b6` in both `buildid-list` and the
MMAP2 union. Its executable mapping began at VMA `0x420000` with file offset
`0x20000`; a sample IP `0x57324b` produced perf `dsoff 0x17324b`, exactly the
independent formula despite unequal VMA and file offset. This proves the
required union format and coordinate conversion are available without
collecting or interpreting a Cubrim performance outcome.

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

Every binary, source, map, perf, gzip, manifest, raw, and analysis path must be
contained beneath its declared root after component-wise validation. Roots and
every descendant are enumerated with `lstat`; symlinks (including directory
and broken links), FIFOs, sockets, devices, unexpected directories, and other
non-regular nodes are rejected. Regular inputs are opened with no-follow
semantics and rechecked by `fstat`. Manifest paths are canonical relative paths
with no absolute path, `..`, duplicate, alternate spelling, or unlisted node.

Output roots must themselves be real directories. Expected and foreign
symlinks/non-regular nodes are rejected in both write and check modes. Writes
use randomized exclusive temporary files inside the validated output root,
flush and `fsync`, then atomically replace the destination; failure removes
only the exact temporary inode. Negative tests cover directory/broken
symlinks, FIFOs, path escape, predictable-temp attacks, replacement failure,
malformed/oversized rows, duplicate keys, and decompression bombs before the
instrument may land.

## Frozen predictions

These predictions do not name a winning family or authorize a lever:

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
- **P4 — attribution power:** all six records have
  `n_binary >= 4787`, `U_binary <= 0.001`, and zero runtime samples or
  period in `binary_unresolved` and `ambiguous_inline_owner`.
- **P5 — repeatability:** both stat samples are within 10% cycles, both
  record samples are instrument-clean, and every material mechanically
  generated source family is within 1.00 point for its file.

P1–P5 are evaluated exactly as `SUPPORTED`, `REFUTED`, or `INDETERMINATE`.
They are characterization results only.

## Decision routes

The campaign is `VALID-ATTRIBUTION / NO-SELECT` only when every admission,
suite, archive, round-trip, terminal, static-map, smoke, record-integrity,
attribution-power, cycle, perturbation, and repeatability gate passes.

It is `VALID-DESCRIPTIVE / NO-SELECT` when correctness, identity, mapping,
conservation, and terminal gates pass but sample size, perturbation, cycle
agreement, or family repeatability is insufficient. In that route, affected
ceilings are suppressed.

It is `VOID / NO-SELECT` for any source/binary/tool identity mismatch,
correctness failure, timeout, lost record, static-map failure, MMAP2 or
`dsoff` mismatch, unknown exact-binary instruction offset, ambiguous runtime
ownership, period-conservation failure, evidence failure, or nonterminal
execution. A void is preserved and never retried from the same sample.

Even `VALID-ATTRIBUTION` cannot select a source change. A later candidate
requires its own prospective mechanism, instruction-addressable ceiling,
density boundary, predictions, and acceptance thresholds committed to `main`
before that candidate is built.

## Evidence and publication boundary

One immutable `CLOCK_MONOTONIC` start establishes a hard deadline exactly
14,400 seconds later and a work deadline 120 seconds before that. Every
possibly blocking precommit command is capped at the smaller of its own limit
and the remaining work budget. A process-group wrapper sends TERM then KILL;
the exact `cgroup.procs` guard then rejects any new systemd-unit PID. A bounded
transient-systemd test creates a setsid double-fork descendant that ignores
TERM, proves the guard requests only the exact unit stop, and proves
`KillMode=control-group` removes the unit. Manifest generation and publication
run in one final bounded process group against the same hard deadline. A
five-second commit margin prohibits beginning the final acceptance rename too
close to the deadline.

On terminal success, the worker produces an exhaustive SHA-256 manifest and a
non-authoritative pending marker in `.partial`. The marker is written with a
checked `write_all` loop that retries `EINTR`, completes short writes, rejects
zero progress, fsyncs the file, and requires exact-byte readback. Its payload
binds the schema, campaign status, `NO-SELECT`, source commit, instrument
commit, reviewed map-admission seal SHA-256, final absolute path, and completion
time. The worker removes all write bits and then fsyncs every evidence file and
directory, atomically renames `.partial` to `.publishing` without replacement,
renames the pending marker without replacement, and authenticates both marker
and manifest before acceptance. It repeats marker and manifest authentication,
plus the exact cgroup check, immediately before atomically renaming
`.publishing` to the final path. That final rename is the sole acceptance point
and is followed by parent and final-directory fsync and exact readback.
`.partial`, `.publishing`, and `.late` are always non-authoritative regardless
of marker spelling. Timeout/crash tests cover every publication transition,
one-byte marker tamper, one-byte manifested-content tamper, `EINTR`, short and
zero writes, stalls before acceptance, and a forced post-rename deadline
crossing. A late final is moved to `.late` without replacement, parent-fsynced,
its authenticated marker is moved without replacement to
`REJECTED-TIMING-DONE.STAMP`, every post-chmod file/directory is fsynced, and
the parent is fsynced again. A final tree is accepted only before the hard
deadline when marker, manifest, read-only, bounded-process, and exact-cgroup
predicates all pass. On failure, no authoritative completion stamp exists. The
unit must terminate once with exit zero,
`NRestarts=0`, and no surviving process before any performance value is read.

The raw tree, deterministic reducer, per-file report, and independent spec
and quality reviews must land through a normal protected PR before a later
candidate preregistration. G4 writes no database, API, site, social channel,
or credentials. Only a later reviewed transaction for a landed
`VALID-ATTRIBUTION` result may append a non-scoring evidence pointer while
NEW-24 remains `in_progress`, measurements remain empty, evaluation remains
zero, and no web-benchmark hypothesis row is created. `VALID-DESCRIPTIVE` and
`VOID` produce no database write.
