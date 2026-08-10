# H-33 charged digit/non-digit split oracle preregistration

Date: 2026-08-10
State: prospective design/preregistration only; no H-33 outcome has been accessed
Registry identity: extend existing row `H-33`; never create a duplicate row
Design-base commit: `c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4`

## Authority and prior-evidence boundary

This document defines one characterization oracle for the existing H-33
digit-context-decomposition mechanism. It contains no H-33 result, archive,
digit-share observation, winning branch, candidate implementation, product
selection, GO/NO-GO disposition, or authorization to launch.

No output from an H-33 split oracle, implementation, candidate, benchmark, or
pilot was inspected while selecting or writing this protocol. The only prior
inputs were the already-published H-33 registry/source rationale and the
current public world-benchmark baseline used to state the prospective gates.
Those inputs are not H-33 outcome data. In particular, no archive size produced
by the transform below is known.

The design base above was freshly fetched and exactly equalled `origin/main`
before this preregistration was drafted. It cannot be the execution revision,
because this uncommitted document is absent from it. Before outcome access,
this document, the reviewed oracle harness, its tests, and all frozen constants
MUST land through the normal protected-main path. A fresh fetch must then prove
that clean detached `HEAD`, `origin/main`, the committed preregistration blob,
the harness blob, and the test blob all equal the reviewed resulting-main
identities. A PR head, local branch, synthetic remote ref, uncommitted file, or
ancestor-only check is insufficient for launch.

This experiment never writes the H-33 row. A result package may later report a
prospective gate outcome, but this protocol itself authorizes no database, API,
site, social, credential, or backlog mutation.

## Frozen existing-registry identity

H-33 is an existing registry row, not an ID allocated by this experiment. A
fresh read-only transaction on the authoritative registry established this
exact prospective identity before drafting:

- cardinality for `id = 'H-33'`: exactly `1`;
- `id`: `H-33`;
- `title`: `H-30..H-36 — external-research candidate ladder, round 1 (SOTA log/columnar) [H-33]`;
- `status`: `go`;
- `runnable`: `false`;
- `md_path`: `datarim/cubrim-hypotheses/H-30..H-36.md`;
- database column `src` (source): `cubrim-hypotheses-canon`.

The future execution harness MUST repeat one
`SERIALIZABLE READ ONLY DEFERRABLE` transaction immediately before input
authentication and require exact equality of the cardinality and all six row
fields above. It must take no row lock and issue no insert, update, delete,
upsert, DDL, advisory lock, notification, or stored procedure. Registry
unavailability, a second row, a missing row, or any field drift is a prelaunch
`VOID`; no outcome command may start.

The historical registry word `go` is prior research-triage state only. It is
not an H-33 oracle result, a density or performance pass, a runnable flag, a
candidate selection, a deployment authorization, or permission to change the
row. This preregistration does not change it.

## Frozen question

H-33 asks whether losslessly separating maximal ASCII digit runs from all
other bytes exposes enough sub-byte structure to reduce charged archive bytes
on numeric-dense files before the existing strongest eligible Cubrim rail,
without hiding framing, fallback, speed, or memory costs.

The oracle is a mechanism ceiling, not production code. It answers only:

1. how many charged bytes the exact split can recover per file;
2. whether that ceiling clears the preregistered per-file density gates; and
3. what encode/decode throughput and peak-RSS tradeoff the exact oracle incurs.

It does not select a wire format or candidate. A future candidate would require
a new prospective registration committed before candidate construction or
measurement.

## Frozen 24-file inventory

The canonical inventory is the current 24-file world-benchmark inventory in
the exact order below: 11 Canterbury files, `enwik8`, then 12 Silesia files.
The source is the authoritative current `world_benchmark_file` identity set.
For every row, the input must be a regular, nonsymlink file with the exact byte
count and SHA-256 before any digit count, encode, archive-size read, or outcome
access.

Canonical tuple serialization is one UTF-8 line per row, with no header, six
TAB-separated fields
`ordinal, corpus, file, type, bytes, input_sha256`, and exactly one LF after
every line including the last. Its SHA-256 is
`33dda3acf23f1a7dff903114481fa9ecd0da60270c25df2976568c8622224695`.

| # | corpus | file | type | bytes | input SHA-256 |
|---:|---|---|---|---:|---|
| 1 | canterbury | `alice29.txt` | text | 152089 | `7467306ee0feed4971260f3c87421154a05be571d944e9cb021a5713700c38f0` |
| 2 | canterbury | `asyoulik.txt` | text | 125179 | `eaa3526fe53859f34ecdf255712f9ecf0b2c903451d4755b2edaa2e2599cb0fc` |
| 3 | canterbury | `cp.html` | text | 24603 | `e0cd21cef5b6c4069461e949be100080c3ce887de6f1dd8626c480528efaaf61` |
| 4 | canterbury | `fields.c` | code | 11150 | `85d73e354cc50cec76cb5a50537cf8dc035f8cbb8480f9e1cbe2f7d6c23393c7` |
| 5 | canterbury | `grammar.lsp` | code | 3721 | `1b0805dfc0ae706b35aac2bb4e15f02485efd24dda5dbd29de7b2f84d1a88c15` |
| 6 | canterbury | `kennedy.xls` | binary | 1029744 | `9af47239ca29dfe20e633f80bbbb9a4cc9783d0803d7b2b5626f42e4c3790420` |
| 7 | canterbury | `lcet10.txt` | text | 426754 | `5314ba1dbb03f471df88bec6cd120a938ef60d0fd3511c5c1dce61bf7463245f` |
| 8 | canterbury | `plrabn12.txt` | text | 481861 | `07e2e0b461af78c7c647cb53dab39de560198e16f799b4516eccf0fbd69f764c` |
| 9 | canterbury | `ptt5` | image | 513216 | `0ec3a75089bb52342813496b17e51377bc9eba3cb519a444d67025354841d650` |
| 10 | canterbury | `sum` | binary | 38240 | `ee5733cd76ecc2f9d8ff156adc3c02a7a851051dcf43a2d56ff4ee4ff606bdb3` |
| 11 | canterbury | `xargs.1` | text | 4227 | `c58aeb5d2d1e12751d47e7412b45784405fc30a5671b03d480fa05776e183619` |
| 12 | enwik8 | `enwik8` | text | 100000000 | `2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8` |
| 13 | silesia | `dickens` | text | 10192446 | `b24c37886142e11d0ee687db6ab06f936207aa7f2ea1fd1d9a36763c7a507e6a` |
| 14 | silesia | `mozilla` | exe | 51220480 | `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b` |
| 15 | silesia | `mr` | image | 9970564 | `68637ed52e3e4860174ed2dc0840ac77d5f1a60abbcb13770d5754e3774d53e6` |
| 16 | silesia | `nci` | database | 33553445 | `fc63a31770947b8c2062d3b19ca94c00485a232bb91b502021948fee983e1635` |
| 17 | silesia | `ooffice` | exe | 6152192 | `e7ee013880d34dd5208283d0d3d91b07f442e067454276095ded14f322a656eb` |
| 18 | silesia | `osdb` | database | 10085684 | `60f027179302ca3ad87c58ac90b6be72ec23588aaa7a3b7fe8ecc0f11def3fa3` |
| 19 | silesia | `reymont` | text | 6627202 | `0eac0114a3dfe6e2ee1f345a0f79d653cb26c3bc9f0ed79238af4933422b7578` |
| 20 | silesia | `samba` | code | 21606400 | `93ba07bc44d8267789c1d911992f40b089ffa2140b4a160fac11ccae9a40e7b2` |
| 21 | silesia | `sao` | binary | 7251944 | `c2d0ea2cc59d4c21b7fe43a71499342a00cbe530a1d5548770e91ecd6214adcc` |
| 22 | silesia | `webster` | text | 41458703 | `6a68f69b26daf09f9dd84f7470368553194a0b294fcfa80f1604efb11143a383` |
| 23 | silesia | `x-ray` | image | 8474240 | `7de9fce1405dc44ae5e6813ed21cd5751e761bd4265655a005d39b9685d1c9ad` |
| 24 | silesia | `xml` | text | 5345280 | `0e82e54e695c1938e4193448022543845b33020c8be6bf3bf3ead2224903e08c` |

No file may be added, removed, substituted, shortened, sampled, or renamed.
Canterbury files remain mandatory observations even though their fixed
overhead dominates some ratios.

## Input-only digit-share classification

Classification is deterministic and precedes all compression:

- A digit byte is exactly an ASCII byte in inclusive range `0x30..0x39`.
- `digit_bytes` is the exact count of those bytes in the authenticated input.
- `digit_share` is reported as the exact rational
  `digit_bytes / input_bytes`; decimal rendering is descriptive only.
- A file is `HIGH_DIGIT` exactly when
  `digit_bytes * 100 >= input_bytes * 30`, evaluated with checked integers.
- Every other file is `LOW_DIGIT`.

The harness must write all 24 classifications, counts, exact rationals, input
identities, and ordered-classification SHA-256 to a sealed pre-outcome record
before the first baseline or split encode. Classification never permits a file
to be skipped. If the record changes after any outcome access, the whole run is
`VOID`; it cannot be recomputed to rescue a gate.

## Fully charged reversible split oracle

For each input, the transform partitions the byte sequence into maximal,
strictly alternating digit and non-digit runs. It emits three logical streams:

1. `run_map_plain`: one byte for the first run kind (`0` non-digit, `1`
   digit), then canonical minimal unsigned LEB128 for the run count, followed
   by one canonical minimal unsigned LEB128 length for every run;
2. `digit_plain`: all original ASCII digit bytes in original order, unchanged;
3. `nondigit_plain`: all other original bytes in original order, unchanged.

There are no zero-length runs, adjacent runs of the same kind, nonminimal
LEB128 values, ignored trailing bytes, or implicit lengths. The run lengths
must sum exactly to the frozen input byte count. Reconstruction must consume
all three streams exactly and reproduce the input by both `cmp` and SHA-256.

Each logical stream is compressed independently by the same exact
provenance-authenticated Cubrim `max` baseline command used for the whole-file
baseline. Component archives are complete charged Cubrim archives, not raw
backend payloads. This conservatively charges their individual containers and
backend selection.

The outer oracle has exactly two branches:

- baseline branch: one selector byte `0x00`, then the complete baseline
  archive;
- split branch: one selector byte `0x01`, one schema-version byte `0x01`,
  canonical minimal unsigned LEB128 values for original byte count,
  `run_map` archive length, digit archive length, and non-digit archive length,
  followed in that exact order by the three complete component archives.

The fully charged oracle is the byte-shorter branch. A tie selects the baseline
branch. No byte is free: the branch selector, schema marker, every run marker,
run length, stream length, archive boundary, component container, checksum,
backend selector, padding byte, and fallback byte is included in the stored
archive size and hash. There is no estimated framing, amortized dictionary,
shared table, uncharged side channel, or out-of-band decoder state.

The oracle decoder must parse the selected branch from its bytes alone. It
must reject an unknown selector/version, nonminimal or overflowing LEB128,
length mismatch, missing or extra component, invalid component archive,
unconsumed byte, run-map inconsistency, or reconstructed-size mismatch before
acceptance.

## Frozen execution environment and namespaces

The future harness and its tests do not exist in this design-only change. They
MUST land with this preregistration before outcome access at these exact paths
inside a clean detached execution worktree:

- `REPO=/home/dev/.worktrees/cubrim/CUBR-H33-EXEC`;
- `HARNESS=$REPO/documentation/ephemeral/research/h33_digit_split_oracle.py`;
- `HARNESS_TEST=$REPO/documentation/ephemeral/research/test_h33_digit_split_oracle.py`;
- `CGROUP_LAUNCHER=$REPO/documentation/ephemeral/research/h33_cgroup_launcher.py`;
- `CGROUP_LAUNCHER_TEST=$REPO/documentation/ephemeral/research/test_h33_cgroup_launcher.py`;
- `LICENSE_FIXTURE=$REPO/documentation/ephemeral/research/h33-license-state.json`;
- `CUBRIM=$REPO/code/cubrim-rs/target/release/cubrim`;
- `INPUT_ROOT=/home/dev/cubrim-corpora/world-v1`;
- `RESULT_ROOT=/home/dev/cubrim-results/H-33-v1`;
- `LICENSE_STATE_DIR=/home/dev/.local/share/cubrim-h33-license-v1`;
- `LICENSE_STATE=$LICENSE_STATE_DIR/state.json`.

The execution commit, preregistration blob, harness blob, test blob, cgroup
launcher blob and SHA-256, cgroup-launcher test blob, license-fixture blob,
release binary, Cargo inputs,
compiler, and release flags are future identities, but
there is no choice among them: each is the single reviewed blob from the clean
execution revision, and `HEAD` must exactly equal freshly fetched
`origin/main`. `EXECUTION_SHA256` is the SHA-256 of the exact raw bytes emitted
by `/usr/bin/git cat-file commit HEAD`; `INVENTORY_SHA256` is the canonical
tuple hash frozen above; and `HARNESS_SHA256` is the SHA-256 of the committed
harness file. The run ID is exactly
`h33-v1-${EXECUTION_SHA256}-${INVENTORY_SHA256}-${HARNESS_SHA256}`, using all
64 lowercase hex characters of each SHA-256 and no timestamp or random suffix.
The only namespaces are:

- `STAGE=$RESULT_ROOT/.${RUN_ID}.stage`;
- `PUBLISHING=$RESULT_ROOT/.${RUN_ID}.publishing`;
- `FINAL=$RESULT_ROOT/${RUN_ID}`;
- `QUARANTINE=$RESULT_ROOT/.${RUN_ID}.quarantine`;
- `VOID_JOURNAL=$RESULT_ROOT/H-33-v1-VOID.jsonl`.

`STAGE`, `PUBLISHING`, `FINAL`, and `QUARANTINE` must all be absent at
prelaunch. Their presence is `VOID`; the harness never deletes, adopts,
renames, resumes, or overwrites them.

Execution is admitted only on this exact host profile: hostname
`arcana-devs`; SHA-256 of `/etc/machine-id`
`8c29c8ac11d4e1f91eec0c73abb364c90c0837afc79ff80fb457b527667809be`;
Linux `6.8.0-124-generic` on `x86_64`; one socket, eight cores, two threads per
core, 16 online CPUs exactly `0-15`, one NUMA node containing exactly CPUs
`0-15`; CPU model `Intel(R) Core(TM) i9-9900K CPU @ 3.60GHz`; `MemTotal`
exactly `131811180 KiB`; every scaling governor `powersave`; Intel
`no_turbo=0`; cgroup v2 with the `cpu`, `cpuset`, `memory`, and `pids`
controllers. Any mismatch is prelaunch `VOID`. Immediately before every timed
command the harness reads `/proc/loadavg` once and requires each of its 1-, 5-,
and 15-minute values to be at most `0.50`. It does not wait, sleep, retest, or
choose a different host if admission fails.

The fixed host-tool profile is also part of admission. Each command path and
resolved target must be a regular executable with exactly this SHA-256 and
first version line; `/usr/bin/python3` must resolve to `/usr/bin/python3.12`.
The future Cubrim binary and harness hashes are not known in this design-only
revision, but each must equal its single reviewed execution-main artifact.

| command path | resolved SHA-256 | exact version line |
|---|---|---|
| `/usr/bin/env` | `0aefff8f912fb75716c5d4de3b6acde93edbe8fa280fc8ee895c1226d3e373ef` | `env (GNU coreutils) 9.4` |
| `/usr/bin/timeout` | `4fccd5b0192653a2446b745d5385ea547b78e466150e07ade9e2caff2b7f4e08` | `timeout (GNU coreutils) 9.4` |
| `/usr/bin/time` | `3b11dec50514a8473e9f6efa7a34d584d0657538c09988f61b72d38ad4991a10` | `time (GNU Time) UNKNOWN` |
| `/usr/bin/taskset` | `a9c851792e54e91fba7b827019380abee54e715b6817899c835e4f221354b260` | `taskset from util-linux 2.39.3` |
| `/usr/bin/python3` -> `/usr/bin/python3.12` | `1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118` | `Python 3.12.3` |
| `/usr/bin/cmp` | `e10750ef3db9bd3595d3cbb1e25bcfd6a964dc6aa0ba9561034067913ee1cc04` | `cmp (GNU diffutils) 3.10` |
| `/usr/bin/sha256sum` | `9992e1f1feb6f0f396bc8d6691ebc1adbfc269fd628bce84eda1d4ba5c3995c7` | `sha256sum (GNU coreutils) 9.4` |
| `/usr/bin/git` | `2a8c18fbf43da9f692d75474c72bea9dfd796c260b0f3dfe456376abc3bbd668` | `git version 2.43.0` |
| `/usr/bin/systemd-run` | `49f0bf95eb8a781b93853bf9fc981b4929dd0009f55a3e6db95534c0a2d11716` | `systemd 255 (255.4-1ubuntu8.16)` |
| `/usr/bin/systemctl` | `7ba82b5ba146759c710e1b80fadaa3fdbc0f9b85c8fb2c8c3196b7b1a0037ef8` | `systemd 255 (255.4-1ubuntu8.16)` |
| `/usr/bin/true` | `4b5a5694e3c0e8b1d58fc52ac6ef076e55e72c2f53195243ac86d5ff517cc2f6` | `true (GNU coreutils) 9.4` |

Every child starts through `/usr/bin/env -i`; therefore unlisted variables are
absent. The exact environment is `HOME=/nonexistent`,
`PATH=/usr/bin:/bin`, `LANG=C`, `LC_ALL=C`, `TZ=UTC`,
`RUST_BACKTRACE=0`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`,
`RAYON_NUM_THREADS=16`, `CUBRIM_THREADS=16`, `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`,
`VECLIB_MAXIMUM_THREADS=1`, `BLIS_NUM_THREADS=1`, and
`MALLOC_ARENA_MAX=16`, `CUBRIM_ACCEPT_LICENSE=1`, and
`CUBRIM_STATE_DIR=/home/dev/.local/share/cubrim-h33-license-v1`. `TMPDIR` is the current cell's empty
`CELL_ROOT/tmp`; this is the only per-cell value.

The license state is not generated during a measurement. Before any input or
outcome access, a reviewed provisioning step copies one committed fixture to
`LICENSE_STATE`. Its raw bytes are exactly the following UTF-8 object, including
the final LF and no other whitespace:

```json
{
  "install_id": "00000000-0000-4000-8000-000000000033",
  "accepted": true,
  "license_version": "1.0.0",
  "accepted_at": "2026-08-10T00:00:00Z"
}
```

Its SHA-256 is
`b728c6903a00faa4e9d69eaf8aa2f743b8dd3363da1776998bce75948e5ac060`.
The directory is owned by numeric UID/GID `1002:1002` at mode `0555`; the file
is owned by `1002:1002`, is a regular nonsymlink file at mode `0444`, and has
link count one. Provisioning fails rather than replacing an existing
nonidentical path. Prelaunch records its inode, device, mode, ownership, size,
mtime-ns, and SHA-256, opens it with `O_RDONLY|O_NOFOLLOW`, and retains that
descriptor. Immediately before and after every stock or oracle child, the same
facts and hash must match. Because `accepted=true`, both
`ensure_license_accepted` and the `CUBRIM_ACCEPT_LICENSE=1` automation path
return before license fetch; outbound network is forbidden for the unit. A
pre-outcome feasibility probe invokes the exact stock-child and oracle-child
Cubrim arrays against a fixed deliberately nonexistent operand and requires
the post-license input-open error, unchanged state identity/hash, and no other
filesystem write. A prompt, state write, network attempt, or different error is
prelaunch `VOID`.

No direct write beneath root-owned `/sys/fs/cgroup` is assumed. Each timed
command is launched by the committed `CGROUP_LAUNCHER`, as UID/GID `1002:1002`
with no ambient, inheritable, permitted, or effective Linux capabilities,
through the UID 1002 user-systemd manager. The exact outer array is:

```text
/usr/bin/env -i HOME=/home/dev PATH=/usr/bin:/bin LANG=C LC_ALL=C TZ=UTC \
  XDG_RUNTIME_DIR=/run/user/1002 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1002/bus \
  /usr/bin/systemd-run --user --remain-after-exit --service-type=exec \
  --unit=cubr-h33-RUN_KEY-MEASURED_STEP.service \
  --property=Slice=app.slice --property=Restart=no \
  --property=KillMode=control-group --property=TimeoutStopSec=60s \
  --property=MemoryMax=infinity --property=MemorySwapMax=infinity \
  --property=TasksMax=4096 --property=RestrictAddressFamilies=AF_UNIX \
  --property=StandardOutput=null --property=StandardError=null -- \
  /usr/bin/python3 -I -B CGROUP_LAUNCHER run \
  --unit cubr-h33-RUN_KEY-MEASURED_STEP.service \
  --stdout CELL_ROOT/OP-unit.stdout --stderr CELL_ROOT/OP-unit.stderr \
  --evidence CELL_ROOT/OP-cgroup.json -- COMMAND_ARRAY...
```

`RUN_KEY` is the first 16 lowercase hex characters of SHA-256 over the exact
UTF-8 `RUN_ID`; `MEASURED_STEP` is the manifest step ID and contains only
uppercase ASCII letters and digits. `OP` is exactly `encode` for an encode
step, `decode` for a decode step, and `preflight` only for `P04`; no other value
is valid. Before launch the three exact `OP` destinations must all be absent.
Systemd receives no file path and connects the launcher's inherited stdout and
stderr to `null`; the authenticated launcher itself opens its `--stdout`,
`--stderr`, and `--evidence` operands with
`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, then `dup2`s the first two before any
child creation. Overwrite, truncate, append, symlink, hard-link, or reuse is
`VOID`. `/run/user/1002` and
its `bus` must be
owned by UID 1002, nonsymlink, and usable by the authenticated user manager;
all other control-process variables are absent. Admission requires the exact
current user-manager and `app.slice` controller set `cpu memory pids`; `cpuset`
and BPF-firewall delegation are deliberately not claimed. CPU affinity remains
the frozen `/usr/bin/taskset -c 0-15` command inside every measured array, and
the authenticated host has a single NUMA node containing exactly CPUs `0-15`.
User systemd creates the service leaf under the authenticated UID-1002
`app.slice` and applies the supported `memory` and `pids` limits before it
executes the launcher. `RestrictAddressFamilies=AF_UNIX` is admitted only if the
disposable probe below proves an AF_INET socket creation is denied while an
AF_UNIX socket succeeds; no unsupported `IPAddressDeny` evidence is claimed.
The launcher forks the
command child stopped before `exec`, proves the child's `/proc/PID/cgroup`
equals its own service leaf and its numeric UID/GID/capability sets are exact,
then sends `SIGCONT`. It records every descendant identity until the child is
reaped. While the launcher remains the sole process, it records `memory.peak`,
`memory.events`, `pids.current`, `/proc/self/status` affinity, and
`cgroup.procs`; any process other than the launcher at that point is `VOID`.

The outer call intentionally has neither `--wait` nor `--pipe`. With
`--remain-after-exit`, it returns after the start job while the unit remains
loaded. The external harness polls the exact unit via `/usr/bin/systemctl
--user show` every 250 monotonic milliseconds, without relaunching it, until
either `(ActiveState=active, SubState=exited)` or a terminal failed state. The
hard controller deadline is the inner command deadline plus 120 seconds (120
seconds total for the disposable preflight); expiry first stops the unit and is
`VOID`. While the successful unit is still loaded, the harness requires and
hashes `Type=exec`, `RemainAfterExit=yes`, `Restart=no`, `NRestarts=0`,
`Result=success`, `ExecMainStatus=0`, one nonempty `InvocationID`, the exact
`ControlGroup`, `MemoryMax=infinity`, `MemorySwapMax=infinity`, `TasksMax=4096`,
`StandardOutput=null`, `StandardError=null`, the exact launcher arguments and
the launcher's sealed evidence. It then runs
`systemctl --user stop UNIT` and waits at most 60 seconds for both
`systemctl --user show UNIT` and the recorded cgroup path to become absent. A
failed unit is first fully captured, then cleaned with `systemctl --user
reset-failed UNIT` and the same absence proof; it cannot enter the success
route. Not-found before evidence capture is never success. Failure at any
creation, move-before-exec, containment, reap, evidence, or teardown step is
`VOID`.

At `P04`, before input authentication, the same outer array and properties are
executed once with a disposable `cubr-h33-RUN_KEY-PREFLIGHT.service` leaf and
the launcher's fixed `preflight` mode. That mode proves AF_INET socket creation
is denied, AF_UNIX socket creation succeeds, and then runs
`COMMAND_ARRAY=[/usr/bin/true]`. It must prove the stopped-child handshake,
supported effective properties, `/proc` affinity `0-15`, descendant
containment, zero event counters, successful reap, retained-unit evidence, and
complete unit/leaf removal. Its exact output namespace is the newly created
`STAGE/preflight` directory and contains exactly `preflight-unit.stdout`,
`preflight-unit.stderr`, `preflight-cgroup.json`, `systemd-show.env`, and
`probe.json`; every file is retained, hashed, and included in the final payload
manifest. This reversible preflight is forbidden from opening `INPUT_ROOT`, any
cell path, or any H-33 outcome. Failure is a
prelaunch `VOID`; there is no retry or alternate privileged mechanism.

The step supervisor uses `CLOCK_MONOTONIC` hard deadlines with no extension:
the registry transaction is `60s`; each other `P` step is `3600s`; every
untimed `VERIFY`, pair-check, row/gate, and per-file cleanup step is `1800s`;
each of `S01` through `S06` and `S14` is `3600s`; and each of `S07` through
`S13` is `1800s`. The four encode/decode deadlines are the command-wrapper
values below. Deadline expiry is `VOID`; it is never a reason to retry, resume,
skip, or raise a limit.

## Exact command arrays and timing parser

For each fixed replicate, `CELL_ROOT` and every operand below are derived
mechanically from the manifest in the next section. `B1` and `B2` use these
exact arrays with encode timeout `86400s` and decode timeout `21600s`:

```text
/usr/bin/env -i ENV... TMPDIR=CELL_ROOT/tmp \
  /usr/bin/timeout --signal=TERM --kill-after=60s 86400s \
  /usr/bin/time -v -o CELL_ROOT/encode.time -- \
  /usr/bin/taskset -c 0-15 CUBRIM compress --preset max --quiet \
  INPUT CELL_ROOT/archive.cub

/usr/bin/env -i ENV... TMPDIR=CELL_ROOT/tmp \
  /usr/bin/timeout --signal=TERM --kill-after=60s 21600s \
  /usr/bin/time -v -o CELL_ROOT/decode.time -- \
  /usr/bin/taskset -c 0-15 CUBRIM decompress --quiet \
  CELL_ROOT/archive.cub CELL_ROOT/decoded.bin
```

`O1` and `O2` use these exact oracle-parent arrays with encode timeout
`172800s` and decode timeout `21600s`:

```text
/usr/bin/env -i ENV... TMPDIR=CELL_ROOT/tmp \
  /usr/bin/timeout --signal=TERM --kill-after=60s 172800s \
  /usr/bin/time -v -o CELL_ROOT/encode.time -- \
  /usr/bin/taskset -c 0-15 /usr/bin/python3 -I -B HARNESS encode-oracle \
  --cubrim CUBRIM --preset max --input INPUT \
  --output CELL_ROOT/archive.cub --work-dir CELL_ROOT/tmp

/usr/bin/env -i ENV... TMPDIR=CELL_ROOT/tmp \
  /usr/bin/timeout --signal=TERM --kill-after=60s 21600s \
  /usr/bin/time -v -o CELL_ROOT/decode.time -- \
  /usr/bin/taskset -c 0-15 /usr/bin/python3 -I -B HARNESS decode-oracle \
  --cubrim CUBRIM --input CELL_ROOT/archive.cub \
  --output CELL_ROOT/decoded.bin --work-dir CELL_ROOT/tmp
```

`ENV...`, `CUBRIM`, `HARNESS`, `INPUT`, and `CELL_ROOT` are notation for the
single exact values specified here and in the manifest; they are not shell
lookups or operator choices. `INPUT` is exactly
`$INPUT_ROOT/$corpus/$file` from the frozen inventory row. The harness persists
the fully expanded NUL-safe
argument array and environment before launch and the validator reconstructs
and byte-compares them. Shell evaluation, globbing, aliases, PATH resolution,
optional flags, and extra variables are forbidden.

The oracle-encode envelope begins before either candidate exists and ends only
after the parent independently creates the whole-file fallback, transforms the
input, creates all three component archives by the exact Cubrim child array,
serializes and validates the outer frame, selects the shorter branch, `fsync`s
the archive, and closes it. Losing candidates and all children remain charged.
No standalone baseline, component, classification buffer, or earlier replicate
may be reused. Oracle decode begins before selector parsing and ends after the
full decoded output is `fsync`ed and closed.

Inside `encode-oracle`, the exact order is: create
`tmp/fallback.cub` from the whole input; create the three plain transform files
`tmp/run-map.plain`, `tmp/digit.plain`, and `tmp/nondigit.plain`; then create
`tmp/run-map.cub`, `tmp/digit.cub`, and `tmp/nondigit.cub` in that order; then
frame, validate, compare charged byte counts, select, `fsync`, and close. Each
archive creation child array is exactly
`[CUBRIM, compress, --preset, max, --quiet, PLAIN, COMPONENT_ARCHIVE]` and
inherits the parent's frozen environment, affinity, and cgroup. Inside
`decode-oracle`, selector `0x00` invokes exactly one Cubrim decompress child;
selector `0x01` invokes exactly three in frame order `run-map`, `digit`, then
`nondigit`, followed by reconstruction. Each child array is exactly
`[CUBRIM, decompress, --quiet, COMPONENT_ARCHIVE, COMPONENT_PLAIN]`.

All correctness commands are also fixed arrays: decoded/source comparison is
`[/usr/bin/cmp, -s, --, DECODED, INPUT]`; each file hash is
`[/usr/bin/sha256sum, --, FILE]`; baseline-pair comparison is
`[/usr/bin/cmp, -s, --, B1/archive.cub, B2/archive.cub]`; and oracle-pair
comparison is `[/usr/bin/cmp, -s, --, O1/archive.cub, O2/archive.cub]`.
Operands are the exact absolute manifest-derived paths and the recorded hashes
must equal freshly parsed `sha256sum` stdout.

GNU `time` must be GNU time and locale `C`. Its file must contain exactly one
line beginning with one ASCII TAB and otherwise matching
`^Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (([0-9]+):)?([0-9]+):([0-9]{2})(\.[0-9]+)?$`,
and exactly one line beginning with one ASCII TAB and otherwise matching
`^Maximum resident set size \(kbytes\): ([0-9]+)$`. Duplicate, missing,
negative, overflowed, or differently formatted values are `VOID`. Elapsed time
is converted without floating point to integer nanoseconds from the captured
hours, minutes, seconds, and decimal fraction, right-padding that fraction to
nine digits and rejecting more than nine. The stored timing file is hashed and
reparsed by the final validator. The charged peak-memory value is the larger
of GNU-time maximum RSS and `ceil(cgroup memory.peak / 1024)` KiB, preventing a
short-lived child or simultaneous descendants from escaping the gate.

## Complete ordered 24-file campaign manifest

Pre-outcome steps are exactly: `P01` fresh fetch, exact-main/blob checks, and
expected-cells hash/entry checks;
`P02` registry read-only equality; `P03` namespace nonexistence and stage plus
empty `STAGE/preflight` creation; `P04` host/tool/license-state/cgroup checks
and the harmless disposable-leaf feasibility probe; `P05` authenticate all 24 inputs in
inventory order; `P06` compute all 24 input-only classifications in inventory
order; `P07` write, hash, `fsync`, and seal the classification record; `P08`
perform the load-admission check immediately preceding `M001`. No compression
size or archive is read before `P08` passes. Later timed commands perform their
single load check inside their immediately preceding numbered step boundary;
`M001` does not repeat `P08`.

Each file then owns 16 consecutive measured steps, expanded with no branch in
this exact order: `+01 B1_ENCODE`, `+02 B1_DECODE`, `+03 B1_VERIFY`,
`+04 B2_ENCODE`, `+05 B2_DECODE`, `+06 B2_VERIFY`,
`+07 BASELINE_PAIR_CMP_SHA`, `+08 O1_ENCODE`, `+09 O1_DECODE`,
`+10 O1_VERIFY`, `+11 O2_ENCODE`, `+12 O2_DECODE`, `+13 O2_VERIFY`,
`+14 ORACLE_PAIR_CMP_SHA`, `+15 FILE_ROW_AND_GATES`, `+16 FILE_CLEANUP`.
The load check occurs once immediately before each of the eight timed commands
in that block. `VERIFY` includes decoded/source `cmp` and SHA-256. Cleanup
removes exactly `CELL_ROOT/tmp` and `CELL_ROOT/decoded.bin` after their evidence
is durably recorded; archives, time files, cgroup records, expanded commands,
hashes, and verification rows remain.

| file ordinal | measured steps | exact cell namespace |
|---:|---:|---|
| 1 | M001-M016 | `cells/01-canterbury-alice29.txt` |
| 2 | M017-M032 | `cells/02-canterbury-asyoulik.txt` |
| 3 | M033-M048 | `cells/03-canterbury-cp.html` |
| 4 | M049-M064 | `cells/04-canterbury-fields.c` |
| 5 | M065-M080 | `cells/05-canterbury-grammar.lsp` |
| 6 | M081-M096 | `cells/06-canterbury-kennedy.xls` |
| 7 | M097-M112 | `cells/07-canterbury-lcet10.txt` |
| 8 | M113-M128 | `cells/08-canterbury-plrabn12.txt` |
| 9 | M129-M144 | `cells/09-canterbury-ptt5` |
| 10 | M145-M160 | `cells/10-canterbury-sum` |
| 11 | M161-M176 | `cells/11-canterbury-xargs.1` |
| 12 | M177-M192 | `cells/12-enwik8-enwik8` |
| 13 | M193-M208 | `cells/13-silesia-dickens` |
| 14 | M209-M224 | `cells/14-silesia-mozilla` |
| 15 | M225-M240 | `cells/15-silesia-mr` |
| 16 | M241-M256 | `cells/16-silesia-nci` |
| 17 | M257-M272 | `cells/17-silesia-ooffice` |
| 18 | M273-M288 | `cells/18-silesia-osdb` |
| 19 | M289-M304 | `cells/19-silesia-reymont` |
| 20 | M305-M320 | `cells/20-silesia-samba` |
| 21 | M321-M336 | `cells/21-silesia-sao` |
| 22 | M337-M352 | `cells/22-silesia-webster` |
| 23 | M353-M368 | `cells/23-silesia-x-ray` |
| 24 | M369-M384 | `cells/24-silesia-xml` |

Within each cell namespace the replicate roots are exactly `B1`, `B2`, `O1`,
and `O2`, and `CELL_ROOT` is exactly that replicate root. Each replicate root
contains exactly `archive.cub`, `encode.time`, `decode.time`,
`encode-command.json`, `decode-command.json`, `encode-cgroup.json`,
`decode-cgroup.json`, `encode-unit.stdout`, `encode-unit.stderr`,
`decode-unit.stdout`, `decode-unit.stderr`, `verify.json`, `decoded.bin` until
cleanup, and `tmp` until cleanup. Every one of those fixed destinations is
absent before its producing step and is created once; no later step may write
it. `FILE_CLEANUP` removes the four `decoded.bin` paths and four
`tmp` trees for that file, and no other path. No file or replicate may run
concurrently. The next numbered step cannot begin until the preceding step and
its journal append are durable.

After `M384`, success processing is exactly: `S01` validate all 384 step rows
and four archives per file; `S02` compute independent booleans and a provisional
non-VOID label; `S03` write canonical result JSONL and summary; `S04` prove
every exact scratch/decoded cleanup completed and no other deletion occurred;
`S05` write `payload-manifest.tsv`, exhaustive over every payload path except,
by frozen definition, itself and the two status-marker names; `S06` revalidate
every manifested artifact and prove the only excluded existing path is the
manifest itself; `S07` `fsync` every regular file and directory bottom-up;
`S08` create and `fsync` `STATUS.pending`; `S09` atomically rename `STAGE` to
`PUBLISHING` and `fsync` `RESULT_ROOT`; `S10` atomically rename
`STATUS.pending` to `STATUS.COMPLETE` and `fsync` `PUBLISHING`; `S11` make the
tree read-only and revalidate modes; `S12` atomically no-replace rename
`PUBLISHING` to `FINAL`; `S13` `fsync` `RESULT_ROOT`; `S14` read back and
revalidate `FINAL` from a fresh process. Only an `S14` success is authoritative.

If any failure occurs after `S12` and before `S14` succeeds, the visible `FINAL` is
atomically no-replace renamed to `QUARANTINE`, `RESULT_ROOT` is `fsync`ed, and
the attempt remains `VOID`. Any other failure journals the primary error before
the exact cleanup attempted for that step; cleanup errors append separately and
never erase the primary record.

For every file, both baseline archives must be byte-identical by `cmp`, size,
and SHA-256; both oracle archives must likewise be identical. Every one of the
four archives decodes exactly once and each decoded output must match the
frozen source by `cmp` and SHA-256. A split branch also authenticates and
decodes each manifested component and proves exact stream consumption. The
first baseline becomes canonical only after the baseline-pair check. No
pre-existing archive substitutes for any replicate.

## Ceiling and gate formulas

For file `f`, let:

- `I_f` be the authenticated original input bytes;
- `B_f` be the canonical bare baseline archive bytes;
- `O_f` be the fully charged selected oracle archive bytes, including its
  selector and all split/fallback charges;
- `C_f = max(0, B_f - O_f)` be
  `digit_separation_ceiling_bytes(f)`;
- `P_f = C_f / B_f` be the per-file ceiling fraction;
- `R_f = max(0, O_f - B_f) / B_f` be the charged oracle-regression fraction;
- `Tenc_f = I_f / encode_elapsed_seconds` and
  `Tdec_f = I_f / decode_elapsed_seconds`, each reported for the corresponding
  replicate rather than averaged.

The oracle may select the charged baseline fallback, so a negative raw delta
is recorded but the named ceiling remains zero. Every raw and clamped value is
retained; clamping cannot hide the selector/framing cost.

### Frozen density predictions

- `nci`: `P_nci < 0.015` kills H-33's mechanism gate; `P_nci >= 0.015`
  passes the H-33 density GO gate.
- `nci`: rank relevance is the exact integer condition
  `O_nci <= 1449272`, equivalently `C_nci >= 105421` after the required
  baseline identity below. It is separately labelled `RANK_RELEVANT`.
  Passing 1.5% does not imply rank relevance.
- `osdb`: predicted `P_osdb >= 0.005` (at least 0.5%).
- Every input-only `HIGH_DIGIT` file: predicted `P_f >= 0.015`.
- Named controls `xargs.1`, `dickens`, `webster`, `enwik8`, `ptt5`, `mr`,
  and `x-ray`: charged oracle regression `R_f` must be strictly below `0.003`
  (below 0.3%). Each control is reported independently even if its digit-share
  class is unexpected.

The `nci` relevance threshold is frozen context, not an H-33 result. Current
`reproducibility/expected_cells.json`, SHA-256
`4895770cf703dc61d741975021a9b05cc5d81cd025ce4c7b2b5f9ac1f7dc007c`,
contains exact `nci` archive bytes `1554693` for Cubrim and `1449272` for xz.
The exact difference is `105421` bytes and its exact Cubrim-baseline fraction
is `105421 / 1554693`, approximately
`0.06780824252762442488645668308791510606917`, or
`6.780824252762442488645668308791510606917%`.

The execution must reauthenticate that expected-cells file and both entries
before outcomes, and the two baseline replicates must establish
`B_nci = 1554693`; any mismatch makes the campaign `VOID` rather than moving
the threshold. With that baseline, `O_nci <= 1449272` and
`B_nci - O_nci >= 105421` are identical integer tests. Neither is retuned after
an oracle archive is seen.

### Frozen speed and RSS gates

For both fixed replicates of every file:

- oracle encode throughput must be at least `0.90x` the corresponding
  baseline encode throughput;
- oracle decode throughput must be at least `0.90x` the corresponding
  baseline decode throughput;
- oracle encode and decode peak RSS must each be at most
  `1.10x` the corresponding baseline peak RSS plus `8 MiB` (`8192 KiB`).

Replicates pair only as `B1` with `O1` and `B2` with `O2`. With elapsed integer
nanoseconds `t` and charged peak-memory KiB `M`, the exact encode/decode speed
test is `10 * t_baseline >= 9 * t_oracle`; the exact memory test is
`10 * M_oracle <= 11 * M_baseline + 81920`. These integer comparisons, not
rounded throughput or displayed decimals, decide the booleans.

Any future candidate must be separately preregistered and must recover at
least 50% of the measured per-file ceiling on every file for which it claims
the mechanism, while independently satisfying the same density, speed, RSS,
and correctness gates. Its exact recovery test is
`2 * max(0, B_f - candidate_bytes_f) >= C_f`; rounded percentages cannot pass
it. This 50% rule does not authorize that candidate.

### Frozen independent booleans and terminal precedence

The successful result derives and publishes these independent booleans before
choosing a label. No label suppresses or rewrites a boolean:

- `CAMPAIGN_VALID`: every preflight, identity, containment, ordered step,
  archive-pair, decode, `cmp`, SHA-256, timing parse, cleanup, and publication
  precondition passed. Any failure sets it false.
- `NCI_DENSITY_PASS`: `C_nci * 1000 >= B_nci * 15` (at least 1.5%).
- `NCI_RANK_RELEVANT`: `O_nci <= 1449272`, equivalently
  `C_nci >= 105421` because `B_nci` must equal `1554693`.
- `OSDB_DENSITY_PASS`: `C_osdb * 1000 >= B_osdb * 5` (at least 0.5%).
- `HIGH_DIGIT_APPLICABLE_f`: true exactly for input-only `HIGH_DIGIT` files.
- `HIGH_DIGIT_DENSITY_PASS_f`: true exactly when the file is `LOW_DIGIT` or
  `C_f * 1000 >= B_f * 15`; the separate applicability boolean prevents a
  `LOW_DIGIT` value from being presented as measured support.
- `ALL_HIGH_DIGIT_DENSITY_PASS`: true exactly when every applicable
  `HIGH_DIGIT_DENSITY_PASS_f` is true; the empty applicable set is true.
- `CONTROL_APPLICABLE_f`: true exactly for a named control.
- `CONTROL_REGRESSION_f`: true exactly when the file is a named control and
  `max(0, O_f - B_f) * 1000 >= B_f * 3`; equality is regression because the
  required bound is strictly below 0.3%. It is false for non-controls.
- `ANY_CONTROL_REGRESSION`: true exactly when any applicable control boolean
  is true.
- `ENCODE_SPEED_PASS_f_r` and `DECODE_SPEED_PASS_f_r`: the exact integer speed
  comparison above, independently for `r in {1,2}`.
- `ENCODE_MEMORY_PASS_f_r` and `DECODE_MEMORY_PASS_f_r`: the exact integer
  memory comparison above, independently for `r in {1,2}`.
- `ALL_PERFORMANCE_PASS`: true exactly when every encode/decode speed and
  memory boolean for all 24 files and both pairs is true.
- `ALL_DENSITY_PREDICTIONS_PASS`: exactly
  `NCI_DENSITY_PASS AND OSDB_DENSITY_PASS AND
  ALL_HIGH_DIGIT_DENSITY_PASS`.

There is exactly one campaign terminal label, selected by the first matching
row in this fixed precedence table:

| precedence | exact condition | terminal label |
|---:|---|---|
| 1 | `NOT CAMPAIGN_VALID` | `VOID` |
| 2 | `ANY_CONTROL_REGRESSION` | `CONTROL_REGRESSION` |
| 3 | `NOT ALL_DENSITY_PREDICTIONS_PASS` | `BELOW_H33_GATE` |
| 4 | `NOT ALL_PERFORMANCE_PASS` | `DENSITY_ONLY_TRADEOFF` |
| 5 | `NCI_RANK_RELEVANT` | `H33_RANK_RELEVANT` |
| 6 | otherwise | `H33_DENSITY_GO_NOT_RANK_RELEVANT` |

Thus `VOID` dominates everything. A control regression dominates apparent
density, rank, speed, or RSS success. Density failure remains
`BELOW_H33_GATE` even if performance also fails, while all performance
booleans remain visible. Density success with any speed/RSS failure routes to
`DENSITY_ONLY_TRADEOFF`; it is never a product GO. Rank relevance is considered
only after all density, control, speed, and memory gates pass. The S02 label is
provisional: only S14 can make a non-VOID label authoritative. Failure in any
later success-publication step changes `CAMPAIGN_VALID` to false and leaves
only the journaled `VOID`, regardless of the provisional row.

## Per-file reporting boundary

The result schema must contain one record per file and replicate with at least:

- exact run, code, binary, tool, input, classification, branch, component,
  archive, and decoded-output identities;
- bare baseline bytes, fully charged oracle bytes, raw byte delta, ceiling
  bytes, and ceiling fraction;
- digit bytes, input bytes, exact digit-share rational, and frozen class;
- encode/decode elapsed seconds, throughput, and peak RSS for baseline and
  oracle;
- archive-pair `cmp` result and SHA-256 equality;
- decoded/source `cmp` result and SHA-256 equality;
- every applicable independent boolean above and the single campaign terminal
  label selected by the frozen precedence table.

No arithmetic, geometric, weighted, or unweighted corpus average is allowed.
No cross-file speedup, density improvement, RSS mean, combined ceiling, or
overall rank projection is allowed. Canterbury files are measured and listed
exactly like every other file, but are fixed-overhead-dominated and MUST be
excluded from any broad family or product statement. A claim may name only the
individual files whose exact gates support it.

## One-shot execution and VOID authority

The only CPU affinity is exactly `0-15`. It must not widen. All thread-count
environment variables, timeouts, host identity, topology, load admission,
binary identity, and output namespaces must be frozen by the future reviewed
harness before the first encode.

The canonical campaign launches exactly once. There is no retry, restart,
resume, checkpoint continuation, failed-cell replay, shortened rerun, sample
substitution, or promotion of a preflight/pilot. The two fixed replicates are
part of the original grid and do not create retry authority.

Any setup, identity, classification, input, encode, component, framing,
decode, `cmp`, SHA-256, timing, RSS, publication, or cleanup failure makes the
entire attempted run `VOID`. A durable append-only journal is the sole failure
authority. A VOID produces no usable measurement, gate result, DB disposition,
candidate choice, or partial publication.

Successful publication must be all-or-nothing under a preregistered final
namespace: same-filesystem staging, exhaustive file/directory manifest,
file/directory `fsync`, hidden publishing rename, durable completion marker,
read-only tree, no-replace final rename, and parent-directory `fsync`. Staged,
partial, publishing, quarantined, or late paths are never authoritative.

## Interpretation and mutation boundary

The only allowed campaign terminal labels are:

- `BELOW_H33_GATE`;
- `H33_DENSITY_GO_NOT_RANK_RELEVANT`;
- `H33_RANK_RELEVANT`;
- `DENSITY_ONLY_TRADEOFF`;
- `CONTROL_REGRESSION`;
- `VOID`.

None changes H-33's registry status. No result from this oracle is a shipped
codec, deployable candidate, product GO, leaderboard update, API/site claim,
or database write. A separately reviewed result package and a separately
authorized disposition would be required after the immutable raw publication
exists.

## Freeze rule

This preregistration, registry tuple, expected-cells identities, exact
inventory, tuple hash, digit definition, classification predicate, transform
serialization, component coding, outer-frame charging, fallback rule, host and
tool profile, environment, cgroup containment, timeouts, command arrays,
timing parser, ordered campaign manifest, namespaces, replicate count, pin,
ceiling formula, predictions, independent booleans, terminal precedence,
correctness checks, publication rules, and mutation boundary must land before
any H-33 outcome access.

Changing any of them after outcome access cannot repair this experiment. It
requires a new, separately named prospective registration and never grants a
retry of the run defined here.
