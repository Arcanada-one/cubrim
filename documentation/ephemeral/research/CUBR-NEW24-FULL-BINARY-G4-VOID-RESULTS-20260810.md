# NEW-24 full-binary residual attribution G4 result

**Verdict:** `VOID / NO-SELECT`

The one-shot G4 invocation failed during the
`admission-runner-contract` gate, before any campaign cell or performance
sample started. The immutable failure tree contains no campaign performance
sample artifact and has no authoritative completion marker. No performance
value, prediction, attribution share, ceiling, or source candidate is
admissible.

The failure was a runner-test isolation defect. The mock cgroup self-test
inherited the live `CUBR_SYSTEMD_UNIT=cubr-new24-full-binary-g4.service`
environment value, requested a stop for that live unit name in its mock
sentinel, and then asserted that the sentinel named `mock.unit`. The service
exited once with status 2 and `NRestarts=0`. This result records the failure;
it does not fix the defect or rerun the campaign.

This report applies the decision boundary in
[`CUBR-NEW24-FULL-BINARY-G4-20260809.md`](CUBR-NEW24-FULL-BINARY-G4-20260809.md).
The byte-exact failure package and its fail-closed verifier are in
[`CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/`](CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/).

## Frozen identities

| identity | value |
|---|---|
| current `origin/main` commit | `708cda945a285526610371d812e4f54725eb6baf` |
| current `origin/main` tree | `9cdad69314f94e0cc0323b1dd6fb64d34c0f677b` |
| measurement instrument commit | `ced543590f7529721f894011829a9d0e8f91385d` |
| measurement instrument tree | `bb07cbb1fd40bc61e1ab4001c17a2d52870b8239` |
| code-under-test source commit | `830a9a31deb00926a97f3fa5bd74f58003573fc0` |
| code-under-test source tree | `a2638f1a20c7654e0efde9d09f9a8807ef7523b2` |
| runner SHA-256 | `9db371bfab3376785744d0a1399ab79e8f033cb8f29eb920315556a23e821f32` |
| runner-test SHA-256 | `1da8ac44536547d70ab769907954d6e4088618865584db0ed53b057fefb7c1b3` |
| mapper SHA-256 | `36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1` |
| mapper-test SHA-256 | `97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314` |

The instrument commit exists on the remote and is an ancestor of the recorded
current-main commit. The package records both commit/tree pairs and the exact
reviewed instrument blob identities; none is inferred from the failure tree.

## Terminal proof and campaign boundary

The transient systemd unit was
`cubr-new24-full-binary-g4.service`, invocation
`27cba50809fb4066b8915510b33a2b30`. Its terminal properties were
`Type=exec`, `Restart=no`, `RuntimeMaxUSec=4h`, `Result=exit-code`,
`ExecMainStatus=2`, and `NRestarts=0`. The invocation-bound journal contains
exactly the terminal runner message:

```text
current_profile_g4_contract=HARNESS_INVALID reason=runner cgroup containment control failed: current_profile_g4_cgroup_test=FAIL
```

The failure stamp records `status=VOID`, `cell=none`, and
`failed_at=2026-08-10T02:01:38Z`. The preflight journal ends at the
`admission-runner-contract` deadline gate followed by `error_rc=2`. Therefore:

- campaign cells: 0;
- campaign performance samples: 0;
- campaign performance sample artifacts: 0;
- authoritative completion markers: 0;
- selection: `NO-SELECT`.

The retained `preflight/perf-*.csv` files are preflight event-support probes,
not campaign samples. They are preserved as raw evidence and are deliberately
not interpreted.

## Immutable failure evidence

The source tree on `dev-ai` is
`/root/cubr-new24-full-binary-g4-20260809.partial`. Its recorded state has 18
regular files, two directories, no symlinks, 72,861 total file bytes, directory
mode `0500`, file mode `0444`, and root ownership for every node. The package's
[`remote-tree-manifest.tsv`](CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/remote-tree-manifest.tsv)
seals every relative path, type, remote mode, owner, byte size, and file
SHA-256.

The two source files that were empty remain independently present and exactly
zero bytes:

- `preflight/process-conflicts.txt`;
- `preflight/runner-contract-test.txt`.

Arbitrary read-only mode bits are terminal-host evidence rather than a
portable Git checkout property. The verifier therefore enforces the recorded
remote modes in the manifest while enforcing the checkout's path set,
symlink safety, byte sizes, hashes, and per-file emptiness directly.

## Exact-main isolation reproduction

The current-main runner was exercised locally without changing it:

| environment | command result | output |
|---|---:|---|
| `CUBR_SYSTEMD_UNIT` absent | 0 | `current_profile_g4_cgroup_test=PASS` |
| `CUBR_SYSTEMD_UNIT=cubr-new24-full-binary-g4.service` | 1 | `current_profile_g4_cgroup_test=FAIL` |

The runner reads `CUBR_SYSTEMD_UNIT` into readonly `SYSTEMD_UNIT`. Its mock
`self_test_cgroup` installs a fake cgroup and stop sentinel but does not clear
the inherited unit. The stop helper consequently records
`${SYSTEMD_UNIT:-mock.unit}`, while the self-test assertion requires the
literal `systemctl --no-block stop mock.unit`. The runner contract test invokes
this self-test without removing an inherited unit value. That is the complete
cause of the observed admission failure.

## Deterministic verification

From the repository root:

```text
PACKAGE=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810
PYTHONDONTWRITEBYTECODE=1 python3 "$PACKAGE/verify_void_result.py" --package "$PACKAGE"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v "$PACKAGE/test_verify_void_result.py"
```

The verifier enforces an exact whole-package path/node allowlist and fails
closed on path, node-type, recorded mode/owner, byte-size, hash, empty-file,
terminal stamp, journal, invocation, restart count, commit/tree/blob identity,
reproduction, result-schema, or sample-boundary drift. Its only success output
is `VOID / NO-SELECT`. Mutation tests cover raw content, empty-file filling,
remote-mode drift, injected remote or top-level sample artifacts, top-level
cell trees, authoritative completion markers, database artifacts, unit
invocation/restart drift, journal drift, identity drift, and reproduction
drift.

## Publication limits

This slice performed no campaign rerun and made no change to the runner,
database, API, site, social channel, backlog, or remote host. It publishes only
failure identity, immutable evidence, and the reproduced harness root cause.
This G4 invocation is terminal and cannot be rerun, restarted, resumed,
repaired, or reinterpreted. Any future characterization experiment must be a
separately named, prospectively preregistered successor and independently
authorized before launch.
