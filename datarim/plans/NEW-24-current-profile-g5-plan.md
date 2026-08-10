# NEW-24 Current-Profile G5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended, when your runtime supports spawning isolated agents) or `executing-plans` (single-session execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, review, seal, and execute one separately named G5 full-binary residual-attribution experiment whose admission subprocesses cannot inherit campaign authority, then publish a deterministic terminal result without selecting a source change or writing external state.

**Architecture:** Fork the reviewed G4 instrument into four new G5-owned assets while preserving every fail-closed mapping, correctness, cgroup, deadline, and publication guard. The only behavioral repair is an explicit empty-environment boundary around mock cgroup subprocesses plus a separate allowlisted user-systemd launcher; a no-performance admission run generates a fresh G5 map seal, and a protected preregistration amendment freezes all concrete resulting-main identities before the one allowed campaign launch. G4 code and evidence remain immutable inputs, never edited, renamed, resumed, or interpreted as G5 performance evidence.

**Tech Stack:** Bash 5, Python 3 standard library and `unittest`, GNU binutils, `perf`, GNU `time`, Cargo/Rust, systemd transient services, Git/GitHub protected pull requests, SHA-256 and Git object identities.

---

## Frozen starting point and file map

`367b6c74143ce9d6d987d9e75f47cd8f70813ce7` is the minimum reviewed
ancestry anchor, not a forever-current execution SHA. The implementation starts
only after a fresh fetch proves `HEAD == origin/main == ls-remote main`, proves
that anchor is an ancestor, and reauthenticates every frozen G5/G4 blob below.
This prevents the plan's own protected merge, or later unrelated documentation
merges, from making Step 1 impossible while still failing closed on content
drift:

- the G5 preregistration is Git blob `5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f`, SHA-256 `ceed266d524721fa0bef6b496566f36a9ed04bd4ca9838b92e4250d5e65843e4`;
- the G4 terminal report is Git blob `8536837a103f7f8bd9b07955aeb85e53228e7dd7`, SHA-256 `e1fdbbed99279add28880875f5f8c37ffb061f6e7afd1564d8d15294a92900e1`;
- the G4 terminal journal is Git blob `4b1fabfef622c2652d0e33360a860238321fbb77`, 1,071 bytes, SHA-256 `8d57ceb1a2e53c8c715dd4bdcc17c05383494c83fbdbdfae4d16f91778acea74`;
- the G4 remote-tree manifest is Git blob `9d6f51f3f2f1480b047c94b5ea74196aba706012`, 2,035 bytes, SHA-256 `6ab89a7d8c83e8341a71a43c4379dc66c103898c13d012365cce277e93a15958`.

Existing immutable references:

- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md` — prospective G5 protocol; modify only in the later identity-amendment pull request.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-20260809.md` — immutable G4 protocol and static-map identities; read only.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-RESULTS-20260810.md` — immutable G4 terminal verdict; read only.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/` — immutable G4 failure package; read only.
- `documentation/ephemeral/research/current-profile-g4-run.sh` — immutable source for the new runner.
- `documentation/ephemeral/research/current-profile-g4-run-test.sh` — immutable source for the new runner contract.
- `documentation/ephemeral/research/current_profile_g4_map.py` — immutable source for the new mapper.
- `documentation/ephemeral/research/test_current_profile_g4_map.py` — immutable source for the new mapper tests.

New instrument files:

- `documentation/ephemeral/research/current-profile-g5-run.sh` — G5-only campaign runner, admission runner, cgroup checks, and durable publication.
- `documentation/ephemeral/research/current-profile-g5-run-test.sh` — G5 namespace, admission-environment, cgroup, publication, and mutation contract.
- `documentation/ephemeral/research/current_profile_g5_map.py` — G5-labelled deterministic full-binary mapper and reducer.
- `documentation/ephemeral/research/test_current_profile_g5_map.py` — G5 mapper unit, filesystem, runtime-join, and mutation tests.

Protected launch-amendment file:

- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env` — canonical ordered `g5-protected-launch-identities-v1` key/value set copied byte-for-byte into the marked preregistration amendment and authenticated separately by Git blob.

Terminal-result files created only after the one G5 service is terminal:

- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md` — terminal per-file verdict and `NO-SELECT` boundary.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/identities.tsv` — exact Git, instrument, binary, unit, source, and seal identities.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/unit-properties.txt` — terminal systemd properties.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/systemd-journal.jsonl` — invocation-bound journal export.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/remote-tree-manifest.tsv` — exact remote evidence-tree path/type/mode/owner/size/hash manifest.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/remote-evidence/` — byte-exact terminal G5 tree under its original relative paths.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/result.json` — deterministic route and P1-P5 result.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/verify_result.py` — fail-closed whole-package verifier.
- `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/test_verify_result.py` — mutation tests for the terminal package.

## Task 1: Create a G5-only instrument skeleton under RED namespace tests

**Files:**

- Create: `documentation/ephemeral/research/current-profile-g5-run.sh`
- Create: `documentation/ephemeral/research/current-profile-g5-run-test.sh`
- Create: `documentation/ephemeral/research/current_profile_g5_map.py`
- Create: `documentation/ephemeral/research/test_current_profile_g5_map.py`
- Read only: the four corresponding G4 assets listed above

- [ ] **Step 1: Re-fetch and refuse a stale or dirty implementation base**

Run:

```bash
git fetch origin main
remote_main=$(git ls-remote origin refs/heads/main | awk '{print $1}')
test -n "$remote_main"
test "$(git rev-parse origin/main)" = "$remote_main"
test "$(git rev-parse HEAD)" = "$remote_main"
git merge-base --is-ancestor 367b6c74143ce9d6d987d9e75f47cd8f70813ce7 "$remote_main"
test "$(git rev-parse origin/main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md)" = \
  5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f
while IFS=' ' read -r expected path; do
  test "$(git rev-parse "origin/main:$path")" = "$expected"
done <<'EOF'
f3164d39d10febc8d8fc14c217232e6a083ffc5f documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-20260809.md
8536837a103f7f8bd9b07955aeb85e53228e7dd7 documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-RESULTS-20260810.md
4b1fabfef622c2652d0e33360a860238321fbb77 documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/systemd-journal.jsonl
9d6f51f3f2f1480b047c94b5ea74196aba706012 documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/remote-tree-manifest.tsv
63fcf9b26d4ff54e6857e66a3b4b87cd425503ab documentation/ephemeral/research/current-profile-g4-run.sh
0e057269d64fe4ecca8099928c44d7fe9905c480 documentation/ephemeral/research/current-profile-g4-run-test.sh
b0ee509b1909c4f77dcd11490626f9d1d06773b6 documentation/ephemeral/research/current_profile_g4_map.py
b6e546413ebd56d423abd6b24744476c0f6e2f6f documentation/ephemeral/research/test_current_profile_g4_map.py
EOF
test -n "$(git rev-parse origin/main:datarim/plans/NEW-24-current-profile-g5-plan.md)"
test "$(git branch --show-current)" = codex/cubr-new24-g5-instrument
test -z "$(git status --porcelain)"
```

Expected: all assertions exit 0, including remote equality, reviewed ancestry,
the unchanged G5 preregistration blob, the landed plan, and a clean instrument
branch that the controller already created directly from that exact remote
main.

- [ ] **Step 2: Create only the G5 test assets from reviewed G4 bytes**

Run:

```bash
cp -- documentation/ephemeral/research/current-profile-g4-run-test.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
cp -- documentation/ephemeral/research/test_current_profile_g4_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py
perl -0pi -e 's/current-profile-g4/current-profile-g5/g; s/current_profile_g4/current_profile_g5/g; s/NEW-24 G4/NEW-24 G5/g; s/cubr-new24-full-binary-g4/cubr-new24-full-binary-g5/g; s/cubr-new24-g4/cubr-new24-g5/g; s/cubr-new24-g4-/cubr-new24-g5-/g; s/g4-map/g5-map/g; s/20260809/20260810/g' \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  documentation/ephemeral/research/test_current_profile_g5_map.py
```

Expected: only the two G5 test paths appear in `git status --short`; all four G4 assets remain byte-identical to `HEAD`.

- [ ] **Step 3: Run the runner contract and observe the missing implementation RED state**

Run:

```bash
set +e
runner_output=$(bash documentation/ephemeral/research/current-profile-g5-run-test.sh 2>&1)
runner_rc=$?
set -e
printf 'rc=%s\n%s\n' "$runner_rc" "$runner_output"
test "$runner_rc" -eq 2
grep -qF 'current_profile_g5_contract=HARNESS_INVALID reason=runner not found or unsafe:' <<<"$runner_output"
```

Expected: exit 0 from the final assertion sequence, with captured `runner_rc=2` and no PASS token.

- [ ] **Step 4: Run the mapper tests and observe the missing module RED state**

Run:

```bash
set +e
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py \
  > /tmp/current-profile-g5-map-red.txt 2>&1
mapper_rc=$?
set -e
test "$mapper_rc" -ne 0
grep -Eq 'No such file|ModuleNotFoundError' /tmp/current-profile-g5-map-red.txt
```

Expected: the test module fails before any test can pass because `current_profile_g5_map.py` does not exist.

- [ ] **Step 5: Copy the implementation assets and perform only mechanical G5 namespace changes**

Run:

```bash
cp -- documentation/ephemeral/research/current-profile-g4-run.sh \
  documentation/ephemeral/research/current-profile-g5-run.sh
cp -- documentation/ephemeral/research/current_profile_g4_map.py \
  documentation/ephemeral/research/current_profile_g5_map.py
perl -0pi -e 's/current-profile-g4/current-profile-g5/g; s/current_profile_g4/current_profile_g5/g; s/NEW-24 G4/NEW-24 G5/g; s/cubr-new24-full-binary-g4/cubr-new24-full-binary-g5/g; s/cubr-new24-g4/cubr-new24-g5/g; s/cubr-new24-g4-/cubr-new24-g5-/g; s/g4-map/g5-map/g; s/20260809/20260810/g' \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current_profile_g5_map.py
chmod 0755 documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: four new G5 paths exist; `git diff --exit-code --` over the four G4 paths exits 0.

- [ ] **Step 6: Add RED namespace checks before changing behavior**

Insert these exact contract assertions into `current-profile-g5-run-test.sh` after the existing forbidden-literal checks:

```bash
require_runner_fixed '/root/cubr-new24-full-binary-g5-src'
require_runner_fixed '/root/cubr-new24-full-binary-g5-target'
require_runner_fixed '/root/cubr-new24-full-binary-g5-instrument'
require_runner_fixed '/root/cubr-new24-full-binary-g5-20260810'
reject_runner_fixed '/root/cubr-new24-full-binary-g4-20260809'
reject_runner_fixed 'cubr-new24-full-binary-g4.service'
reject_runner_fixed 'current_profile_g4_'
reject_runner_fixed 'config/credentials/'
```

Also add a mapper test that asserts every emitted schema begins with `cubr-new24-g5-` and that `cubr-new24-g4-` never appears in a fresh G5 output.

Expected: the new assertions are RED against any G4 namespace residue or
credential-path literal; after the mechanical fork they pass without editing
any G4 asset.

- [ ] **Step 7: Run the G5 suites and confirm remaining behavior is RED only at the admission isolation contract**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: mapper tests pass and the mechanically forked runner contract prints
exactly `current_profile_g5_contract=PASS`. This is the inherited control
baseline; it does not yet claim the poisoned-parent requirement passes.

- [ ] **Step 8: Commit the namespace-only instrument fork**

Run:

```bash
git add -- documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  documentation/ephemeral/research/current_profile_g5_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py
git commit -m "test: establish NEW-24 G5 instrument namespace"
```

Expected: one commit containing only the four new G5 paths.

## Task 2: Add the empty-environment pure-mock boundary with poisoned-parent TDD

**Files:**

- Modify: `documentation/ephemeral/research/current-profile-g5-run-test.sh`
- Modify: `documentation/ephemeral/research/current-profile-g5-run.sh`

- [ ] **Step 1: Write the poisoned-parent RED contract**

Add these constants and helper assertions to the runner test:

```bash
readonly POISONED_PARENT_UNIT=g4-live-authority-must-not-be-used.service
readonly LIVE_G5_CAMPAIGN_UNIT=cubr-new24-full-binary-g5-20260810.service
readonly PURE_MOCK_PATH=/usr/bin:/bin

assert_mock_output_isolated() {
    local output=$1 expected_unit=$2
    [[ $output == *"unit=$expected_unit"* ]] ||
        fail "pure mock did not report expected fixture unit: $expected_unit"
    [[ $output != *"$POISONED_PARENT_UNIT"* ]] ||
        fail 'poisoned parent unit reached pure mock output'
    [[ $output != *"$LIVE_G5_CAMPAIGN_UNIT"* ]] ||
        fail 'live G5 campaign unit reached pure mock output'
}
```

Run the existing cgroup and disconnected-precommit controls in a subshell that exports `CUBR_SYSTEMD_UNIT=$POISONED_PARENT_UNIT`, `INVOCATION_ID=poisoned-invocation`, `CUBR_CGROUP_SYSTEMCTL_USER=poisoned-user-scope`, and `CUBR_CGROUP_LIVE_RESULT=/poisoned/result`. Assert the sentinel reports only `mock.unit` or `precommit-disconnected.service`.

Expected: the added assertions fail against the inherited launcher because at
least one poisoned parent value reaches the pure-mock boundary.

- [ ] **Step 2: Run the poisoned-parent test and verify RED**

Run:

```bash
set +e
CUBR_SYSTEMD_UNIT=g4-live-authority-must-not-be-used.service \
INVOCATION_ID=poisoned-invocation \
CUBR_CGROUP_SYSTEMCTL_USER=poisoned-user-scope \
CUBR_CGROUP_LIVE_RESULT=/poisoned/result \
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  > /tmp/current-profile-g5-poison-red.txt 2>&1
poison_rc=$?
set -e
test "$poison_rc" -ne 0
grep -Eq 'cgroup containment control failed|poisoned parent unit reached' \
  /tmp/current-profile-g5-poison-red.txt
```

Expected: nonzero exit at the poison/isolation assertion and no `current_profile_g5_contract=PASS`.

- [ ] **Step 3: Implement the one pure-mock launcher**

Add this exact helper to `current-profile-g5-run-test.sh` and route both `--self-test-cgroup` and `--self-test-cgroup-precommit` through it:

```bash
run_pure_mock_cgroup() {
    local fixture_unit=$1 mode=$2
    /usr/bin/env -i \
        LC_ALL=C \
        PATH="$PURE_MOCK_PATH" \
        CUBR_SYSTEMD_UNIT="$fixture_unit" \
        /usr/bin/bash "$RUNNER" "$mode"
}
```

Do not pass `HOME`, `INVOCATION_ID`, any `CUBR_CGROUP_*` variable, the campaign unit, fixture paths, or a stop-sentinel path. The invoked runner self-test creates fixture paths and its stop sentinel inside its own randomized fixture root.

Expected: inspection of the helper shows one `/usr/bin/env -i` invocation and
only the four literal assignments shown above before the runner path and mode.

- [ ] **Step 4: Make each pure runner self-test report the unit it actually stopped**

Change only the G5 runner's success lines to:

```bash
printf 'current_profile_g5_cgroup_test=PASS unit=mock.unit\n'
printf 'current_profile_g5_cgroup_precommit_test=PASS unit=precommit-disconnected.service\n'
```

The existing sentinel equality checks remain authoritative and execute before either line.

Expected: each mode emits exactly its fixture unit after its sentinel equality
check; neither success line can be reached on a stop-target mismatch.

- [ ] **Step 5: Run the poisoned-parent regression and verify GREEN**

Run:

```bash
CUBR_SYSTEMD_UNIT=g4-live-authority-must-not-be-used.service \
INVOCATION_ID=poisoned-invocation \
CUBR_CGROUP_SYSTEMCTL_USER=poisoned-user-scope \
CUBR_CGROUP_LIVE_RESULT=/poisoned/result \
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: exactly `current_profile_g5_contract=PASS`; no poison value and no G5 campaign unit occur in captured mock output.

- [ ] **Step 6: Add the ambient-inheritance mutation and prove it fails at the intended assertion**

Add this exact helper beside the existing runner-mutant helpers:

```bash
expect_contract_source_mutant_red() {
    local label=$1 expression=$2 expected_fragment=$3 mutant
    mutant=$mutation_root/$label-test.sh
    /usr/bin/cp -- "$SELF" "$mutant"
    /usr/bin/sed -i "$expression" "$mutant"
    ! /usr/bin/cmp -s -- "$SELF" "$mutant" ||
        fail "contract mutation did not change test: $label"
    capture_child /usr/bin/env \
        SELF_MUTATION_TESTS=0 RUNNER="$RUNNER" MAPPER="$MAPPER" \
        CUBR_SYSTEMD_UNIT="$POISONED_PARENT_UNIT" \
        INVOCATION_ID=poisoned-invocation \
        CUBR_CGROUP_SYSTEMCTL_USER=poisoned-user-scope \
        CUBR_CGROUP_LIVE_RESULT=/poisoned/result \
        /usr/bin/bash "$mutant"
    (( CHILD_RC != 0 )) || fail "contract mutation survived: $label"
    /usr/bin/grep -qF "$expected_fragment" <<<"$CHILD_OUTPUT" ||
        invalid "contract mutation failed at unrelated assertion: $label rc=$CHILD_RC output=$CHILD_OUTPUT"
}
```

Extend the mutation harness with these two exact calls:

```bash
expect_contract_source_mutant_red empty_environment_removed \
    's#/usr/bin/env -i#/usr/bin/env#' \
    'pure mock helper must start from an empty environment'
expect_contract_source_mutant_red fixture_unit_replaced_by_parent \
    's/CUBR_SYSTEMD_UNIT="\$fixture_unit"/CUBR_SYSTEMD_UNIT="\${CUBR_SYSTEMD_UNIT}"/' \
    'poisoned parent unit reached pure mock output'
```

The contract must check the exact `/usr/bin/env -i` launcher before executing mutants, so removing the boundary cannot fail later at an unrelated cgroup assertion.

Expected: both mutants exit nonzero and the harness matches the named failure
fragment for each mutation.

- [ ] **Step 7: Run the complete runner contract including mutations**

Run:

```bash
bash -n documentation/ephemeral/research/current-profile-g5-run.sh
bash -n documentation/ephemeral/research/current-profile-g5-run-test.sh
shellcheck documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: both parsers and ShellCheck exit 0; the only runner-contract output is `current_profile_g5_contract=PASS`; both new mutants are observed RED internally.

- [ ] **Step 8: Commit the pure-mock authority-boundary repair**

Run:

```bash
git add -- documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git commit -m "fix: isolate NEW-24 G5 mock cgroup authority"
```

Expected: the commit changes only the two G5 Bash assets.

## Task 3: Add the separate allowlisted user-systemd fixture and live-unit noninterference

**Files:**

- Modify: `documentation/ephemeral/research/current-profile-g5-run-test.sh`
- Modify: `documentation/ephemeral/research/current-profile-g5-run.sh`

- [ ] **Step 1: Write RED tests for the live-fixture allowlist**

Add assertions that the outer launcher rejects an empty `HOME`, `XDG_RUNTIME_DIR`, or `DBUS_SESSION_BUS_ADDRESS`; starts with `/usr/bin/env -i`; passes exactly those three copied values plus `LC_ALL=C` and `PATH=/usr/bin:/bin`; and does not pass `CUBR_SYSTEMD_UNIT`, `INVOCATION_ID`, `CUBR_CGROUP_SYSTEMCTL_USER`, or `CUBR_CGROUP_LIVE_RESULT` from its parent.

Run:

```bash
set +e
capture_dir=$(/usr/bin/mktemp -d)
CUBR_REMOTE_LIVE_FIXTURE=1 \
HOME= XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh "$capture_dir" \
  > /tmp/current-profile-g5-live-allowlist-red.txt 2>&1
allowlist_rc=$?
set -e
test "$allowlist_rc" -ne 0
grep -qF 'live fixture host variable is empty: HOME' \
  /tmp/current-profile-g5-live-allowlist-red.txt
/usr/bin/rm -rf -- "$capture_dir"
```

Expected: nonzero exit at the exact missing-variable assertion.

- [ ] **Step 2: Implement the distinct outer user-systemd launcher**

Add this helper to the runner test:

```bash
run_user_systemd_fixture() {
    local host_home=$1 host_xdg=$2 host_dbus=$3 capture_dir=$4
    [[ -n $host_home ]] || fail 'live fixture host variable is empty: HOME'
    [[ -n $host_xdg ]] || fail 'live fixture host variable is empty: XDG_RUNTIME_DIR'
    [[ -n $host_dbus ]] || fail 'live fixture host variable is empty: DBUS_SESSION_BUS_ADDRESS'
    [[ -d $capture_dir && ! -L $capture_dir ]] || fail 'live fixture capture directory is unsafe'
    /usr/bin/env -i \
        LC_ALL=C \
        PATH=/usr/bin:/bin \
        HOME="$host_home" \
        XDG_RUNTIME_DIR="$host_xdg" \
        DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
        /usr/bin/bash "$RUNNER" --self-test-cgroup-live "$capture_dir"
}
```

Replace the inherited direct `--self-test-cgroup-live` block with this exact
gate and call. Gate `0` takes no capture argument; gate `1` requires exactly
one capture directory and must return PASS, never SKIP:

```bash
case ${CUBR_REMOTE_LIVE_FIXTURE:-0} in
    0)
        (( $# == 0 )) || invalid 'unexpected live fixture capture argument'
        ;;
    1)
        (( $# == 1 )) || invalid 'live fixture capture argument missing'
        live_output=$(run_user_systemd_fixture \
            "${HOME:-}" "${XDG_RUNTIME_DIR:-}" "${DBUS_SESSION_BUS_ADDRESS:-}" "$1") ||
            invalid "runner live cgroup containment control failed: $live_output"
        [[ $live_output =~ ^current_profile_g5_cgroup_live_test=PASS\ result_sha256=([0-9a-f]{64})\ test_output_sha256=([0-9a-f]{64})$ ]] ||
            invalid "runner live cgroup containment output mismatch: $live_output"
        [[ $(sha256sum "$1/cgroup-live.tsv" | awk '{print $1}') == "${BASH_REMATCH[1]}" ]] ||
            invalid 'live fixture result hash mismatch'
        [[ $(sha256sum "$1/systemd-run.output.txt" | awk '{print $1}') == "${BASH_REMATCH[2]}" ]] ||
            invalid 'live fixture test-output hash mismatch'
        ;;
    *) invalid 'CUBR_REMOTE_LIVE_FIXTURE must be 0 or 1' ;;
esac
```

Inside the G5 runner, retain the fresh fixture unit
`current-profile-g5-cgroup-selftest-$$.service`. Only `systemd-run --setenv`
may assign that fixture's `CUBR_SYSTEMD_UNIT`, `CUBR_CGROUP_SYSTEMCTL_USER=1`,
and fixture-local `CUBR_CGROUP_LIVE_RESULT` to the live worker.

Expected: the outer child contains exactly five environment assignments copied
from the three explicit parent arguments; gate `1` actually invokes it and
authenticates both exported files, while fixture authority appears only in the
inner `systemd-run` argument vector.

- [ ] **Step 3: Capture and assert the user-systemd argument vector**

Change `self_test_cgroup_live` to require its export directory as `$1`. Build
one array, persist it, execute that same array, and export the two exact
fixture files before deleting the randomized root:

```bash
local export_dir=$1 root fixture_result fixture_unit runner_path systemd_output rc result_sha output_sha
local -a systemd_args
[[ -d $export_dir && ! -L $export_dir ]] || die 'live fixture export directory is unsafe'
root=$(/usr/bin/mktemp -d)
fixture_result=$root/cgroup-live.tsv
fixture_unit=current-profile-g5-cgroup-selftest-$$.service
runner_path=$(/usr/bin/readlink -f -- "${BASH_SOURCE[0]}")
systemd_output=$root/systemd-run.output.txt
systemd_args=(
  /usr/bin/systemd-run --user --wait --collect
  --unit="$fixture_unit" --service-type=exec
  --property=Restart=no --property=KillMode=control-group
  --setenv=CUBR_SYSTEMD_UNIT="$fixture_unit"
  --setenv=CUBR_CGROUP_SYSTEMCTL_USER=1
  --setenv=CUBR_CGROUP_LIVE_RESULT="$fixture_result"
  /usr/bin/bash "$runner_path" --self-test-cgroup-live-worker
)
printf '%q ' "${systemd_args[@]}" >"$root/systemd-run.argv"
printf '\n' >>"$root/systemd-run.argv"
set +e
"${systemd_args[@]}" >"$systemd_output" 2>&1
rc=$?
set -e
(( rc != 0 )) || die 'live fixture unexpectedly returned success'
grep -qF -- "--unit=$fixture_unit" "$root/systemd-run.argv"
grep -qF -- "--setenv=CUBR_CGROUP_LIVE_RESULT=$fixture_result" "$root/systemd-run.argv"
! grep -qF 'g4-live-authority-must-not-be-used.service' "$root/systemd-run.argv"
! grep -qF 'cubr-new24-full-binary-g5-20260810.service' "$root/systemd-run.argv"
/usr/bin/grep -qF 'cgroup_new_pid=' "$fixture_result"
/usr/bin/grep -qF "unit_stop_request=$fixture_unit scope=user" "$fixture_result"
! /usr/bin/grep -qF 'live_cgroup_guard_unexpected_return=' "$fixture_result"
/usr/bin/install -m 0444 -- "$fixture_result" "$export_dir/cgroup-live.tsv"
/usr/bin/install -m 0444 -- "$systemd_output" "$export_dir/systemd-run.output.txt"
result_sha=$(sha "$export_dir/cgroup-live.tsv")
output_sha=$(sha "$export_dir/systemd-run.output.txt")
/usr/bin/rm -rf -- "$root"
printf 'current_profile_g5_cgroup_live_test=PASS result_sha256=%s test_output_sha256=%s\n' \
  "$result_sha" "$output_sha"
```

Retain the existing assertion that `KillMode=control-group` removes the setsid
double-fork descendant which ignores TERM.

Expected: the captured and executed vectors are identical, contain only the
fresh fixture authority, the descendant PID no longer exists at return, and
the two read-only exported files hash to the values in the PASS line.

- [ ] **Step 4: Add campaign-identity reread after every self-test**

Add this outer-harness function:

```bash
verify_admitted_campaign_identity() {
    [[ ${CUBR_ENFORCE_CAMPAIGN_REREAD:-0} == 1 ]] || return 0
    local props
    props=$(/usr/bin/systemctl show "$CUBR_ADMITTED_SYSTEMD_UNIT" \
        -p InvocationID -p MainPID -p NRestarts -p ControlGroup)
    /usr/bin/grep -qx "InvocationID=$CUBR_ADMITTED_INVOCATION_ID" <<<"$props" ||
        fail 'admitted campaign InvocationID changed after self-test'
    /usr/bin/grep -qx "MainPID=$CUBR_ADMITTED_MAIN_PID" <<<"$props" ||
        fail 'admitted campaign MainPID changed after self-test'
    /usr/bin/grep -qx 'NRestarts=0' <<<"$props" ||
        fail 'admitted campaign restart count changed after self-test'
    /usr/bin/grep -qx "ControlGroup=$CUBR_ADMITTED_CONTROL_GROUP" <<<"$props" ||
        fail 'admitted campaign ControlGroup changed after self-test'
}
```

Wrap every runner self-test call as `run self-test -> assert exact output -> verify_admitted_campaign_identity`. The G5 campaign runner invokes the contract with `CUBR_ENFORCE_CAMPAIGN_REREAD=1` and passes its already authenticated unit, invocation, main PID, and control group. Those outer values never enter a pure-mock or live-fixture child.

In `admission()`, create the collision-free capture directory and replace the
inherited G4 runner-test invocation with exactly:

```bash
/usr/bin/mkdir -m 0700 -- "$PREFLIGHT_DIR/live-fixture"
run_bounded 900 /usr/bin/env \
    RUNNER="${BASH_SOURCE[0]}" MAPPER="$MAPPER_SOURCE" SELF_MUTATION_TESTS=1 \
    CUBR_REMOTE_LIVE_FIXTURE=1 CUBR_ENFORCE_CAMPAIGN_REREAD=1 \
    CUBR_ADMITTED_SYSTEMD_UNIT="$SYSTEMD_UNIT" \
    CUBR_ADMITTED_INVOCATION_ID="$INVOCATION_ID" \
    CUBR_ADMITTED_MAIN_PID="$$" \
    CUBR_ADMITTED_CONTROL_GROUP="$CONTROL_GROUP" \
    /usr/bin/bash "$RUNNER_TEST_SOURCE" "$PREFLIGHT_DIR/live-fixture" \
    >"$PREFLIGHT_DIR/runner-contract-test.txt"
/usr/bin/chmod 0444 -- "$PREFLIGHT_DIR/runner-contract-test.txt"
```

Expected: every successful self-test is immediately followed by all four exact
service property checks; the gated helper actually runs, and deleting any
reread makes the contract RED.

- [ ] **Step 5: Write and run reread/noninterference mutations**

Add these exact source mutations. The contract first requires the literal
reread call after every self-test, the double-fork payload, and the exact outer
allowlist, so every mutant fails at its named assertion:

```bash
expect_contract_source_mutant_red post_self_test_reread_removed \
  's/    verify_admitted_campaign_identity/    : # mutation removed campaign identity reread/' \
  'campaign identity reread missing after self-test'
expect_runner_mutant_red fixture_uses_campaign_unit \
  's/--unit="\$fixture_unit"/--unit=cubr-new24-full-binary-g5-20260810.service/' \
  'live fixture argument vector contains campaign unit'
expect_runner_mutant_red double_fork_removed \
  's/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=os.fork()/p=os.fork(); os._exit(0) if p else None; os.setsid(); p=0/' \
  'live fixture double-fork payload missing'
expect_contract_source_mutant_red inherited_invocation_passed \
  's#DBUS_SESSION_BUS_ADDRESS="\$host_dbus"#DBUS_SESSION_BUS_ADDRESS="$host_dbus" INVOCATION_ID="${INVOCATION_ID:-}"#' \
  'outer live-fixture allowlist admitted INVOCATION_ID'
```

Each must fail at its named contract assertion and must not stop or alter the
admitted campaign unit.

Run:

```bash
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: `current_profile_g5_contract=PASS`; all four live-fixture mutants are internally RED.

- [ ] **Step 6: Prove the contract calls the live fixture only at the explicit remote gate**

Run locally:

```bash
runner=documentation/ephemeral/research/current-profile-g5-run.sh
contract=documentation/ephemeral/research/current-profile-g5-run-test.sh
test "$(rg -n --fixed-strings 'current-profile-g5-cgroup-selftest-' "$runner" | wc -l)" -eq 1
test "$(rg -n --fixed-strings 'run_user_systemd_fixture' "$contract" | wc -l)" -ge 2
test "$(rg -n --fixed-strings '/usr/bin/env -i' "$contract" | wc -l)" -ge 2
test "$(rg -n --fixed-strings 'case ${CUBR_REMOTE_LIVE_FIXTURE:-0} in' "$contract" | wc -l)" -eq 1
test "$(rg -n --fixed-strings 'live_output=$(run_user_systemd_fixture' "$contract" | wc -l)" -eq 1
```

Expected: all assertions exit 0. Gate `0` never invokes user systemd; gate `1`
contains one real helper call and is first executed only after Task 7 has
materialized and hash-authenticated the landed files on `dev-ai`.

- [ ] **Step 7: Commit the live-fixture and identity-reread contract**

Run:

```bash
git add -- documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git commit -m "test: prove NEW-24 G5 live-unit noninterference"
```

Expected: one commit limited to the two G5 Bash assets.

## Task 4: Re-label the mapper, preserve exhaustive mapping gates, and force a fresh G5 seal

**Files:**

- Modify: `documentation/ephemeral/research/current_profile_g5_map.py`
- Modify: `documentation/ephemeral/research/test_current_profile_g5_map.py`
- Modify: `documentation/ephemeral/research/current-profile-g5-run.sh`
- Modify: `documentation/ephemeral/research/current-profile-g5-run-test.sh`

- [ ] **Step 1: Write RED schema and reuse-decision tests**

Require these exact G5 schemas:

```text
cubr-new24-g5-normalized-elf-v1
cubr-new24-g5-static-map-summary-v3
cubr-new24-g5-map-parts-v1
cubr-new24-g5-map-admission-seal-v1
```

Add a test proving that a byte-identical G4 static map is not reusable when
either the G5 mapper SHA, G5 mapper-test SHA, schema SHA, source tree, binary
SHA/build ID, toolchain, page size, or any map artifact differs. The result
must be `reuse_decision=REJECTED_IDENTITY_MISMATCH` followed by fresh
no-performance map construction, never a silent fallback to G4 evidence.

Expected: the new tests name all eight identity axes and fail until the G5 seal
and exact-equality reuse predicate exist.

- [ ] **Step 2: Run the new mapper tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py
```

Expected: failures name G4 schema remnants and the missing G5 reuse-decision seal.

- [ ] **Step 3: Implement G5 schemas without changing mapping mathematics**

Change only schema labels and add this concrete seal constructor; callers pass
already authenticated scalar identities and map artifact rows:

```python
def build_g5_admission_seal(*, binary_build_id, binary_sha256,
                            instrument_resulting_main, map_artifacts,
                            mapper_sha256, mapper_test_sha256,
                            mapping_schema_sha256, reuse_decision,
                            source_tree, toolchain):
    return {
        "binary_build_id": binary_build_id,
        "binary_sha256": binary_sha256,
        "instrument_resulting_main": instrument_resulting_main,
        "map_artifacts": sorted(map_artifacts, key=lambda row: row["path"]),
        "mapper_sha256": mapper_sha256,
        "mapper_test_sha256": mapper_test_sha256,
        "mapping_schema_sha256": mapping_schema_sha256,
        "page_size": 4096,
        "performance_sample": "NO",
        "reuse_decision": reuse_decision,
        "schema": "cubr-new24-g5-map-admission-seal-v1",
        "source_tree": source_tree,
        "toolchain": dict(sorted(toolchain.items())),
    }
```

Add a `seal-admission` mapper subcommand which reads the authenticated relative
manifest, compressed summary, raw-stream evidence, and toolchain JSON under
`--input-root`, calls `build_g5_admission_seal` exactly once, and exclusively
writes compact sorted JSON plus newline through
`_output(args.output_root, args.seal_out)`. The output root is the already
created absolute `$PARTIAL/map`, so `--seal-out` is the single relative
basename `map-admission-seal.json`; a nested `map/map-admission-seal.json`
argument is forbidden. Its required arguments
are `--binary-build-id`, `--binary-sha256`, `--instrument-resulting-main`,
`--mapper-sha256`, `--mapper-test-sha256`, `--mapping-schema-sha256`,
`--reuse-decision`, `--source-tree`, `--toolchain-json`, `--map-manifest`,
`--map-summary`, `--raw-stream-evidence`, and `--seal-out`.

Add `test_seal_admission_uses_single_output_join`: create absolute
`output_root / "map"`, invoke the command with
`seal_out=Path("map-admission-seal.json")`, and assert the only created seal is
`output_root/map/map-admission-seal.json`; assert
`output_root/map/map/map-admission-seal.json` is absent. The runner contract
also requires exactly one literal `--seal-out map-admission-seal.json` and
rejects `--seal-out map/map-admission-seal.json`.

The `run_command` branch performs its only seal write with the existing mapper
primitive—never by manually joining `input_root` or adding another `map`:

```python
seal = build_g5_admission_seal(
    binary_build_id=args.binary_build_id,
    binary_sha256=args.binary_sha256,
    instrument_resulting_main=args.instrument_resulting_main,
    map_artifacts=map_artifacts,
    mapper_sha256=args.mapper_sha256,
    mapper_test_sha256=args.mapper_test_sha256,
    mapping_schema_sha256=args.mapping_schema_sha256,
    reuse_decision=args.reuse_decision,
    source_tree=args.source_tree,
    toolchain=toolchain,
)
write_new_bytes(_output(args.output_root, args.seal_out), json_bytes(seal))
```

Keep the unique VMA/DSO-offset transforms, one-row-per-instruction coverage,
deterministic `gzip -n -9`, 90,000,000-byte object limit, same-FD DSO
authentication, MMAP2 build-ID join, `dsoff` equality, no-rounding rule,
period conservation, and filesystem no-follow checks unchanged.

Expected: JSON serialization with `sort_keys=True`, compact separators, and a
terminal newline is byte-deterministic; existing mapping math tests remain
unchanged and GREEN.

- [ ] **Step 4: Replace the G4 inline seal path with the G5 mapper constructor**

The reauthentication input is the read-only directory
`/root/cubr-new24-full-binary-g4-map-dryrun-attempt9-pass-20260810` with G4
mapper SHA `36226ff6caf35983a97fa472b1433e37f18a6ac4b565d1ae016e27cd957ae5e1`,
mapper-test SHA `97af2daacca00b20d9eb56dee34d56f9a3a9c22ffcdba820bfce171e7a371314`,
schema SHA `1c8f5be539eaaa94f3a64d071e859ee5eccf8f4314908e143246f47bd8760e12`,
and compact seal SHA `565cce3c44c9fb8a228184e0af37270e0caeb2160f15c36b4690bc81aa139a6f`.
Because the mapper-test and schema identities differ, remove the G4 inline
seal Python block and every G5 copy of `EXPECTED_MAP_SEAL_SHA`,
`EXPECTED_MAP_*`, `EXPECTED_SUMMARY_*`, `EXPECTED_PREFIX_LOCATION_ROWS`, and
the hard-coded `attempt: 9`. After fresh map construction, call only:

```bash
/usr/bin/python3 "$MAPPER" seal-admission \
  --input-root "$PARTIAL" --output-root "$PARTIAL/map" \
  --binary-build-id "$BINARY_BUILD_ID" --binary-sha256 "$EXPECTED_BINARY_SHA" \
  --instrument-resulting-main "$INSTRUMENT_COMMIT" \
  --mapper-sha256 "$EXPECTED_MAPPER_SHA" --mapper-test-sha256 "$EXPECTED_MAPPER_TEST_SHA" \
  --mapping-schema-sha256 "$MAPPING_SCHEMA_SHA256" \
  --reuse-decision REJECTED_IDENTITY_MISMATCH \
  --source-tree "$(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD^{tree})" \
  --toolchain-json preflight/map-toolchain.json \
  --map-manifest map/map-parts-manifest.json \
  --map-summary map/map-summary.json.gz \
  --raw-stream-evidence map/raw-stream-evidence.tsv \
  --seal-out map-admission-seal.json
test -f "$PARTIAL/map/map-admission-seal.json"
test ! -e "$PARTIAL/map/map/map-admission-seal.json"
test "$(json_value "$PARTIAL/map/map-admission-seal.json" schema)" = \
  cubr-new24-g5-map-admission-seal-v1
test "$(json_value "$PARTIAL/map/map-admission-seal.json" reuse_decision)" = \
  REJECTED_IDENTITY_MISMATCH
```

`MAPPING_SCHEMA_SHA256` is the SHA-256 of the two authenticated landed mapper
hash lines; it is not compared with the G4 schema constant. No G4 performance,
timing, family-share, probe interpretation, or campaign verdict is opened.

Run the targeted identity mismatch test:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py \
  -k test_g4_identity_reuse_is_rejected
```

Expected: the test passes with one `_output()` destination at
`$PARTIAL/map/map-admission-seal.json`, no nested `map/map-*` output, and
`reuse_decision=REJECTED_IDENTITY_MISMATCH`, a newly constructed G5 map seal,
zero opened G4 performance paths, and no G4 seal constant in the G5 runner.

- [ ] **Step 5: Run all mapper and runner integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: all mapper tests pass and the runner prints exactly `current_profile_g5_contract=PASS`.

- [ ] **Step 6: Commit the mapper schema and seal contract**

Run:

```bash
git add -- documentation/ephemeral/research/current_profile_g5_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git commit -m "feat: seal NEW-24 G5 full-binary map identity"
```

Expected: one commit limited to the four G5 instrument assets.

## Task 5: Select the output namespace before readonly initialization and add no-performance admission

**Files:**

- Modify: `documentation/ephemeral/research/current-profile-g5-run.sh`
- Modify: `documentation/ephemeral/research/current-profile-g5-run-test.sh`

- [ ] **Step 1: Inventory all 88 transitive campaign-root references and write the filesystem RED test**

Add this exact test before the positive runner controls:

```bash
pre_self_test_root_refs=$(
    /usr/bin/awk '/^self_test_fail\(\)/ { exit } { print }' "$RUNNER" |
        /usr/bin/grep -Eo '\$(OUT|PARTIAL|PUBLISHING|MEASURED_BINARY)\b' |
        /usr/bin/wc -l
)
[[ $pre_self_test_root_refs == 88 ]] ||
    fail "transitive campaign-root inventory changed: $pre_self_test_root_refs"

mode_root=$(/usr/bin/mktemp -d)
set +e
CUBR_G5_TEST_ROOT_PREFIX="$mode_root" \
    /usr/bin/bash "$RUNNER" --self-test-mode-roots \
    >"$mode_root/output.txt" 2>&1
mode_rc=$?
set -e
[[ $mode_rc == 0 ]] || fail "mode-root self-test failed rc=$mode_rc"
campaign_base=$mode_root/cubr-new24-full-binary-g5-20260810
admission_base=$mode_root/cubr-new24-full-binary-g5-map-dryrun-20260810
[[ -f $admission_base/MODE-ROOT.PASS ]] || fail 'admission test root was not created'
for path in "$campaign_base" "$campaign_base.partial" \
    "$campaign_base.publishing" "$campaign_base.late"; do
    [[ ! -e $path && ! -L $path ]] ||
        fail "admission created campaign path: $path"
done
/usr/bin/rm -rf -- "$mode_root"
```

Run:

```bash
set +e
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  > /tmp/current-profile-g5-mode-root-red.txt 2>&1
mode_red_rc=$?
set -e
test "$mode_red_rc" -ne 0
grep -qF 'mode-root self-test failed' /tmp/current-profile-g5-mode-root-red.txt
```

Expected: nonzero because `--self-test-mode-roots` does not exist; none of the
absolute G5 campaign paths is created.

- [ ] **Step 2: Select campaign or admission roots before any readonly path is initialized**

Replace the five G4-derived readonly output declarations with this exact
top-of-file block, before any function or readonly path derived from `OUT`:

```bash
case ${1:-} in
    --admission-feasibility|--self-test-mode-roots) RUN_MODE=admission ;;
    *) RUN_MODE=campaign ;;
esac
readonly RUN_MODE

ROOT_PREFIX=${CUBR_G5_TEST_ROOT_PREFIX:-}
if [[ -n $ROOT_PREFIX && ${1:-} != --self-test-mode-roots ]]; then
    printf 'current_profile_g5_contract=HARNESS_INVALID reason=test root outside root self-test\n' >&2
    exit 2
fi
if [[ -n $ROOT_PREFIX ]]; then
    CAMPAIGN_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g5-20260810
    ADMISSION_OUT=$ROOT_PREFIX/cubr-new24-full-binary-g5-map-dryrun-20260810
else
    CAMPAIGN_OUT=/root/cubr-new24-full-binary-g5-20260810
    ADMISSION_OUT=/root/cubr-new24-full-binary-g5-map-dryrun-20260810
fi
readonly ROOT_PREFIX CAMPAIGN_OUT ADMISSION_OUT
if [[ $RUN_MODE == admission ]]; then
    OUT=$ADMISSION_OUT
else
    OUT=$CAMPAIGN_OUT
fi
readonly OUT
readonly PARTIAL=$OUT.partial
readonly PUBLISHING=$OUT.publishing
readonly LATE=$OUT.late
readonly MEASURED_BINARY=$PARTIAL/binary/cubrim
```

The 88 inventoried references remain unchanged and therefore inherit the
selected root. `$LATE` also derives from the selected `OUT`. Do not maintain a
second set of call-site paths and do not assign any root after a readonly
derived path exists.

Expected: `awk` reports 88 before and after the refactor; the first assignment
of `OUT`, `PARTIAL`, `PUBLISHING`, `LATE`, or `MEASURED_BINARY` occurs only
after `RUN_MODE` is readonly.

- [ ] **Step 3: Implement the filesystem-only root self-test and prove GREEN**

Add this runner function and dispatch case:

```bash
self_test_mode_roots() {
    [[ $RUN_MODE == admission && -n $ROOT_PREFIX ]] || {
        printf 'current_profile_g5_mode_root_test=FAIL unsafe-mode\n'
        exit 1
    }
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    /usr/bin/printf 'mode=admission\nperformance_sample=NO\n' >"$PARTIAL/MODE-ROOT.PASS"
    /usr/bin/chmod 0444 -- "$PARTIAL/MODE-ROOT.PASS"
    /usr/bin/chmod 0555 -- "$PARTIAL"
    /usr/bin/mv -T --no-clobber -- "$PARTIAL" "$OUT"
    printf 'current_profile_g5_mode_root_test=PASS\n'
}
```

Add `--self-test-mode-roots) self_test_mode_roots ;;` to the bottom dispatch.
Then run:

```bash
SELF_MUTATION_TESTS=0 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
```

Expected: exactly `current_profile_g5_contract=PASS`; the contract creates only
its randomized admission base and confirms all four randomized campaign
variants remain absent.

- [ ] **Step 4: Add root-selection and campaign-creation mutations**

Add these exact source mutations to `expect_runner_mutant_red`:

```bash
expect_runner_mutant_red admission_selects_campaign \
    's/OUT=\$ADMISSION_OUT/OUT=\$CAMPAIGN_OUT/' \
    'admission root selection must use ADMISSION_OUT'
expect_runner_mutant_red admission_creates_campaign_final \
    's#/usr/bin/mkdir -m 0700 -- "\$PARTIAL"#/usr/bin/mkdir -m 0700 -- "$CAMPAIGN_OUT"#' \
    'root self-test must create selected PARTIAL only'
expect_runner_mutant_red mode_selected_after_readonly \
    's/readonly RUN_MODE/readonly OUT=\$CAMPAIGN_OUT\nreadonly RUN_MODE/' \
    'RUN_MODE must precede every readonly output path'
```

Expected: each mutant exits nonzero at the named static or filesystem
assertion; no mutant is allowed to touch an absolute `/root` path.

- [ ] **Step 5: Implement admission-only sequencing under the selected root**

Add this exact function:

```bash
admission_feasibility_run() {
    trap on_exit EXIT
    trap on_error ERR
    [[ $RUN_MODE == admission && $OUT == "$ADMISSION_OUT" ]] ||
        die 'admission root selection mismatch'
    refuse_existing_output
    /usr/bin/mkdir -m 0700 -- "$PARTIAL"
    PREFLIGHT_DIR=$PARTIAL/preflight
    /usr/bin/mkdir -m 0700 -- "$PREFLIGHT_DIR"
    JOURNAL=$PREFLIGHT_DIR/journal.tsv
    local campaign_start_monotonic_ns
    campaign_start_monotonic_ns=$(monotonic_ns)
    readonly HARD_DEADLINE_MONOTONIC_NS=$((campaign_start_monotonic_ns + CAMPAIGN_BUDGET_SECONDS * 1000000000))
    readonly WORK_DEADLINE_MONOTONIC_NS=$((HARD_DEADLINE_MONOTONIC_NS - FINALIZATION_RESERVE_SECONDS * 1000000000))
    admission "$PREFLIGHT_DIR" 1
    run_suites
    capture_g5_identity_inputs
    build_full_instruction_map
    verify_feasibility_fixture "$PARTIAL"
    verify_address_join_smoke "$PARTIAL"
    for artifact in address-smoke.data address-smoke.perf-script.txt \
        address-smoke.buildid-list.txt; do
        [[ -f $PARTIAL/$artifact && ! -L $PARTIAL/$artifact ]] ||
            die "address-smoke artifact missing or unsafe: $artifact"
        /usr/bin/rm -- "$PARTIAL/$artifact"
    done
    assert_admission_has_no_performance "$PARTIAL"
    write_g5_admission_identity_set "$PARTIAL"
    /usr/bin/grep -qx 'performance_sample=NO' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity performance_sample mismatch'
    /usr/bin/grep -qx 'campaign_cells=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity campaign_cells mismatch'
    /usr/bin/grep -qx 'retained_perf_data=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity retained_perf_data mismatch'
    /usr/bin/grep -qx 'campaign_sample_rows=0' "$PARTIAL/sealed-identity-set.env" ||
        die 'admission identity campaign_sample_rows mismatch'
    CAMPAIGN_STATUS=NO-PERFORMANCE-ADMISSION
    FINALIZING=1
    run_terminal_finalization
}
```

Define `write_g5_admission_identity_set` exactly as follows; every referenced
file is created earlier in admission, and `write_new_checked` is the existing
exclusive-write/fsync/readback helper:

```bash
write_g5_admission_identity_set() {
    local root=$1 target=$root/sealed-identity-set.env tmp
    local instrument_tree source_tree cubrim_rs_tree runner_blob runner_test_blob
    local mapper_blob mapper_test_blob rustc_version cargo_version release_flags
    local binary_size binary_device binary_inode map_stream_sha map_manifest_sha
    local map_summary_sha map_row_count map_part_count map_seal_sha
    instrument_tree=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse HEAD^{tree})
    source_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD^{tree})
    cubrim_rs_tree=$(/usr/bin/git -C "$CODE_DIR" rev-parse HEAD:code/cubrim-rs)
    runner_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g5-run.sh")
    runner_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current-profile-g5-run-test.sh")
    mapper_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/current_profile_g5_map.py")
    mapper_test_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$INSTRUMENT_COMMIT:documentation/ephemeral/research/test_current_profile_g5_map.py")
    rustc_version=$(/usr/bin/tr '\n' ';' <"$PREFLIGHT_DIR/rustc-version.txt")
    cargo_version=$(/usr/bin/tr '\n' ';' <"$PREFLIGHT_DIR/cargo-version.txt")
    release_flags='CARGO_PROFILE_RELEASE_DEBUG=1;debug_assertions=false;CUBR_THREADS=4;RAYON_NUM_THREADS=4;OMP_NUM_THREADS=4;MKL_NUM_THREADS=4;taskset=0-15'
    binary_size=$(/usr/bin/stat -c %s -- "$MEASURED_BINARY")
    binary_device=$(/usr/bin/stat -c %d -- "$MEASURED_BINARY")
    binary_inode=$(/usr/bin/stat -c %i -- "$MEASURED_BINARY")
    map_stream_sha=$(json_value "$root/map/map-parts-manifest.json" full_uncompressed_sha256)
    map_manifest_sha=$(sha "$root/map/map-parts-manifest.json")
    map_summary_sha=$(sha "$root/map/map-summary.json.gz")
    map_row_count=$(json_value "$root/map/map-parts-manifest.json" row_count)
    map_part_count=$(json_value "$root/map/map-parts-manifest.json" part_count)
    map_seal_sha=$(sha "$root/map/map-admission-seal.json")
    tmp=$target.tmp
    {
        printf 'schema=g5-admission-identity-set-v1\n'
        printf 'instrument_resulting_main=%s\n' "$INSTRUMENT_COMMIT"
        printf 'instrument_tree=%s\n' "$instrument_tree"
        printf 'runner_blob=%s\nrunner_sha256=%s\n' "$runner_blob" "$EXPECTED_RUNNER_SHA"
        printf 'runner_test_blob=%s\nrunner_test_sha256=%s\n' "$runner_test_blob" "$EXPECTED_TEST_SHA"
        printf 'mapper_blob=%s\nmapper_sha256=%s\n' "$mapper_blob" "$EXPECTED_MAPPER_SHA"
        printf 'mapper_test_blob=%s\nmapper_test_sha256=%s\n' "$mapper_test_blob" "$EXPECTED_MAPPER_TEST_SHA"
        printf 'source_commit=%s\nsource_tree=%s\ncubrim_rs_tree=%s\n' "$CODE_COMMIT" "$source_tree" "$cubrim_rs_tree"
        printf 'cargo_inputs_manifest_sha256=%s\n' "$(sha "$PREFLIGHT_DIR/cargo-inputs-manifest.tsv")"
        printf 'generated_cargo_lock_sha256=%s\n' "$(sha "$root/suites/generated-Cargo.lock")"
        printf 'rustc_commit=%s\nrustc_version=%s\ncargo_version=%s\nrelease_flags=%s\n' \
            "$EXPECTED_RUSTC_COMMIT" "$rustc_version" "$cargo_version" "$release_flags"
        printf 'binary_sha256=%s\nbinary_build_id=%s\nbinary_size=%s\nbinary_device=%s\nbinary_inode=%s\n' \
            "$(sha "$MEASURED_BINARY")" "$BINARY_BUILD_ID" "$binary_size" "$binary_device" "$binary_inode"
        printf 'mapping_schema_sha256=%s\n' "$MAPPING_SCHEMA_SHA256"
        printf 'corpus_manifest_sha256=%s\ncorpus_rows_sha256=%s\n' \
            "$(sha "$CORPUS_MANIFEST")" "$(sha "$PREFLIGHT_DIR/cell-inputs.tsv")"
        printf 'map_stream_sha256=%s\nmap_manifest_sha256=%s\nmap_summary_sha256=%s\n' \
            "$map_stream_sha" "$map_manifest_sha" "$map_summary_sha"
        printf 'map_row_count=%s\nmap_part_count=%s\nmap_seal_sha256=%s\n' \
            "$map_row_count" "$map_part_count" "$map_seal_sha"
        printf 'sanitized_allowlist_contract_sha256=%s\n' \
            "$(sha "$PREFLIGHT_DIR/sanitized-environment-contract.txt")"
        printf 'runner_contract_test_sha256=%s\nrunner_contract_test_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/runner-contract-test.txt")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/runner-contract-test.txt")"
        printf 'live_fixture_result_sha256=%s\nlive_fixture_result_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/live-fixture/cgroup-live.tsv")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/live-fixture/cgroup-live.tsv")"
        printf 'live_fixture_test_output_sha256=%s\nlive_fixture_test_output_bytes=%s\n' \
            "$(sha "$PREFLIGHT_DIR/live-fixture/systemd-run.output.txt")" \
            "$(/usr/bin/stat -c %s -- "$PREFLIGHT_DIR/live-fixture/systemd-run.output.txt")"
        printf 'performance_sample=NO\ncampaign_cells=0\nretained_perf_data=0\ncampaign_sample_rows=0\nselection=NO-SELECT\n'
    } >"$tmp"
    [[ $(/usr/bin/wc -l <"$tmp") == 46 ]] || die 'admission identity key count mismatch'
    write_new_checked "$target" "$tmp"
    /usr/bin/rm -- "$tmp"
}
```

Add these exact helpers before `write_g5_admission_identity_set`:

```bash
json_value() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import json, os, stat, sys
path, key = sys.argv[1:]
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise SystemExit("JSON input is not regular")
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        value = json.load(handle).get(key)
    fd = -1
finally:
    if fd >= 0:
        os.close(fd)
if isinstance(value, (dict, list)) or value is None:
    raise SystemExit(f"missing or nonscalar JSON key: {key}")
print(str(value).lower() if isinstance(value, bool) else value)
PY
}

write_new_checked() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import hashlib, os, secrets, sys
from pathlib import Path
target, source = map(Path, sys.argv[1:])
payload = source.read_bytes()
parent = target.parent
tmp = parent / ("." + target.name + "." + secrets.token_hex(16) + ".tmp")
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("zero-progress identity write")
        view = view[written:]
    os.fsync(fd)
finally:
    os.close(fd)
try:
    os.link(tmp, target, follow_symlinks=False)
finally:
    os.unlink(tmp)
dirfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    os.fsync(dirfd)
finally:
    os.close(dirfd)
if target.read_bytes() != payload:
    raise SystemExit("identity readback mismatch")
os.chmod(target, 0o444, follow_symlinks=False)
PY
}
```

Add the campaign-only launch authenticator in this instrument PR. `main_run`
calls it immediately after initializing both deadlines and before `admission`,
`run_suites`, or any performance action; insert
`require_deadline before-launch-authentication` followed by the exact line
`    authenticate_campaign_launch_inputs`. `admission_feasibility_run` does
not call it:

```bash
persist_authenticated_admission_identity() {
    local source=${CUBR_ADMISSION_IDENTITY_SET:?missing admission identity path}
    local expected_sha=${CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256:?missing admission identity SHA}
    local expected_bytes=${CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES:?missing admission identity bytes}
    local target=$PREFLIGHT_DIR/admission-sealed-identity-set.env
    [[ $expected_sha =~ ^[0-9a-f]{64}$ && $expected_bytes =~ ^(0|[1-9][0-9]*)$ ]] ||
        die 'invalid sealed admission identity expectation'
    [[ -f $source && ! -L $source ]] || die 'unsafe sealed admission identity source'
    [[ $(sha "$source") == "$expected_sha" ]] || die 'sealed admission identity SHA mismatch'
    [[ $(/usr/bin/stat -c %s -- "$source") == "$expected_bytes" ]] ||
        die 'sealed admission identity byte mismatch'
    /usr/bin/install -m 0444 -- "$source" "$target"
    [[ $(sha "$target") == "$expected_sha" ]] || die 'persisted admission identity SHA mismatch'
    [[ $(/usr/bin/stat -c %s -- "$target") == "$expected_bytes" ]] ||
        die 'persisted admission identity byte mismatch'
}

launch_identity_value() {
    /usr/bin/awk -F= -v wanted="$1" '$1 == wanted { print substr($0, index($0, "=") + 1) }' \
        "$CUBR_LAUNCH_IDENTITIES"
}

authenticate_campaign_launch_inputs() {
    local parser_output actual_prereg_blob actual_identities_blob
    [[ $CUBR_LAUNCH_MAIN =~ ^[0-9a-f]{40}$ && $CUBR_EXPECTED_PREREG_BLOB =~ ^[0-9a-f]{40}$ &&
       $CUBR_EXPECTED_IDENTITIES_BLOB =~ ^[0-9a-f]{40}$ ]] || die 'invalid launch Git identity'
    /usr/bin/git -C "$INSTRUMENT_REPO" merge-base --is-ancestor \
        "$INSTRUMENT_COMMIT" "$CUBR_LAUNCH_MAIN" || die 'instrument is not ancestor of launch main'
    actual_prereg_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$CUBR_LAUNCH_MAIN:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md")
    actual_identities_blob=$(/usr/bin/git -C "$INSTRUMENT_REPO" rev-parse \
        "$CUBR_LAUNCH_MAIN:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env")
    [[ $actual_prereg_blob == "$CUBR_EXPECTED_PREREG_BLOB" ]] ||
        die 'launch-main preregistration blob mismatch'
    [[ $actual_identities_blob == "$CUBR_EXPECTED_IDENTITIES_BLOB" ]] ||
        die 'launch-main identity blob mismatch'
    parser_output=$(verify_launch_identity_files "$CUBR_LAUNCH_PREREG" "$CUBR_LAUNCH_IDENTITIES")
    [[ $parser_output == 'current_profile_g5_launch_identity_parser=PASS schema=g5-protected-launch-identities-v1 keys=59' ]] ||
        die 'protected launch identity parser output mismatch'
    [[ $(/usr/bin/git hash-object --no-filters "$CUBR_LAUNCH_PREREG") == "$CUBR_EXPECTED_PREREG_BLOB" ]] ||
        die 'launch preregistration blob mismatch'
    [[ $(/usr/bin/git hash-object --no-filters "$CUBR_LAUNCH_IDENTITIES") == "$CUBR_EXPECTED_IDENTITIES_BLOB" ]] ||
        die 'launch identity blob mismatch'
    [[ $(launch_identity_value instrument_resulting_main) == "$INSTRUMENT_COMMIT" ]] ||
        die 'launch instrument commit mismatch'
    [[ $(launch_identity_value runner_sha256) == "$EXPECTED_RUNNER_SHA" &&
       $(launch_identity_value runner_test_sha256) == "$EXPECTED_TEST_SHA" &&
       $(launch_identity_value mapper_sha256) == "$EXPECTED_MAPPER_SHA" &&
       $(launch_identity_value mapper_test_sha256) == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'launch runtime asset identity mismatch'
    [[ $(sha "${BASH_SOURCE[0]}") == "$EXPECTED_RUNNER_SHA" &&
       $(sha "$RUNNER_TEST_SOURCE") == "$EXPECTED_TEST_SHA" &&
       $(sha "$MAPPER_SOURCE") == "$EXPECTED_MAPPER_SHA" &&
       $(sha "$MAPPER_TEST_SOURCE") == "$EXPECTED_MAPPER_TEST_SHA" ]] ||
        die 'installed runtime asset identity mismatch'
    [[ $(launch_identity_value admission_identity_set_sha256) == "$CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256" &&
       $(launch_identity_value admission_identity_set_bytes) == "$CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES" ]] ||
        die 'launch admission identity expectation mismatch'
    printf '%s\n' "$parser_output" >"$PREFLIGHT_DIR/launch-identity-parser.txt"
    /usr/bin/chmod 0444 -- "$PREFLIGHT_DIR/launch-identity-parser.txt"
    persist_authenticated_admission_identity
}
```

The runner contract mutates each of the four runtime SHA fields, the two
admission identity fields, each expected Git blob, and the persisted copy; each
mutation must fail at its named comparison before a suite or performance
subprocess is invoked.

Define `capture_g5_identity_inputs` with the exact body below. Call it once
after `run_suites` and before `build_full_instruction_map` in both
`admission_feasibility_run` and `main_run`; the mapper seal and the admission
identity writer therefore consume the same already-frozen input format, and
the campaign map never lacks its toolchain input:

```bash
capture_g5_identity_inputs() {
/root/.cargo/bin/rustc -vV >"$PREFLIGHT_DIR/rustc-version.txt"
/root/.cargo/bin/cargo -V >"$PREFLIGHT_DIR/cargo-version.txt"
/usr/bin/find "$CODE_DIR/code/cubrim-rs" -xdev -type f \
  \( -name Cargo.toml -o -name Cargo.lock -o -name build.rs -o -name '*.rs' \) \
  -print0 | LC_ALL=C /usr/bin/sort -z | /usr/bin/xargs -0 /usr/bin/sha256sum \
  >"$PREFLIGHT_DIR/cargo-inputs-manifest.tsv"
/usr/bin/chmod 0444 "$PREFLIGHT_DIR/rustc-version.txt" \
  "$PREFLIGHT_DIR/cargo-version.txt" "$PREFLIGHT_DIR/cargo-inputs-manifest.tsv"
/usr/bin/python3 - "$PREFLIGHT_DIR/rustc-version.txt" \
  "$PREFLIGHT_DIR/cargo-version.txt" "$PREFLIGHT_DIR/map-toolchain.json" <<'PY'
import json, pathlib, sys
rustc, cargo, target = map(pathlib.Path, sys.argv[1:])
value = {"cargo": cargo.read_text().strip(), "release_debug": "1",
         "rustc": rustc.read_text().strip(), "taskset": "0-15", "threads": 4}
target.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
PY
/usr/bin/chmod 0444 "$PREFLIGHT_DIR/map-toolchain.json"
contract_tmp=$PREFLIGHT_DIR/sanitized-environment-contract.txt.source
{
  printf 'schema=g5-sanitized-environment-contract-v1\n'
  printf 'pure_mock=LC_ALL,PATH,CUBR_SYSTEMD_UNIT\n'
  printf 'outer_user_systemd=LC_ALL,PATH,HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS\n'
  printf 'service_outer=HOME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS,CUBR_THREADS,RAYON_NUM_THREADS,OMP_NUM_THREADS,MKL_NUM_THREADS\n'
  printf 'child_boundary=env-i\n'
} >"$contract_tmp"
write_new_checked "$PREFLIGHT_DIR/sanitized-environment-contract.txt" "$contract_tmp"
/usr/bin/rm -- "$contract_tmp"
}
```

Expected: all five files are regular, nonempty, and read-only before their
hashes enter the sealed identity set; no ambient environment value is copied
into the sanitized contract.

Add `verify_launch_identity_files` as one embedded-Python structured parser;
it replaces every broad hex scan:

```bash
verify_launch_identity_files() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
from pathlib import Path
import re, sys
prereg, identity = map(Path, sys.argv[1:])
begin = "<!-- g5-protected-launch-identities-v1-begin -->\n"
end = "<!-- g5-protected-launch-identities-v1-end -->"
text = prereg.read_text(encoding="utf-8")
if text.count(begin) != 1 or text.count(end) != 1:
    raise SystemExit("launch identity markers must occur exactly once")
block = text.split(begin, 1)[1].split(end, 1)[0]
canonical = identity.read_text(encoding="utf-8")
if block != canonical:
    raise SystemExit("preregistration block and identity file differ")
keys = (
    "schema original_prereg_blob g4_terminal_journal_sha256 g4_terminal_journal_bytes "
    "g4_failure_manifest_sha256 g4_failure_manifest_bytes g4_capability_probe_count "
    "g4_perf_data_count g4_campaign_cell_count g4_campaign_sample_row_count g4_terminal_gate "
    "g4_verdict instrument_resulting_main instrument_tree runner_blob runner_sha256 "
    "runner_test_blob runner_test_sha256 mapper_blob mapper_sha256 mapper_test_blob "
    "mapper_test_sha256 source_commit source_tree cubrim_rs_tree cargo_inputs_manifest_sha256 "
    "generated_cargo_lock_sha256 rustc_commit rustc_version cargo_version release_flags "
    "binary_sha256 binary_build_id binary_size binary_device binary_inode mapping_schema_sha256 "
    "corpus_manifest_sha256 corpus_rows_sha256 map_stream_sha256 map_manifest_sha256 "
    "map_summary_sha256 map_row_count map_part_count map_seal_sha256 "
    "sanitized_allowlist_contract_sha256 runner_contract_test_sha256 runner_contract_test_bytes "
    "live_fixture_result_sha256 live_fixture_result_bytes live_fixture_test_output_sha256 "
    "live_fixture_test_output_bytes performance_sample campaign_cells retained_perf_data "
    "campaign_sample_rows selection admission_identity_set_sha256 admission_identity_set_bytes"
).split()
lines = canonical.splitlines()
if len(lines) != len(keys):
    raise SystemExit(f"launch identity key count mismatch: {len(lines)}")
parsed = {}
for expected, line in zip(keys, lines):
    key, sep, value = line.partition("=")
    if not sep or key != expected or key in parsed or not value:
        raise SystemExit(f"invalid or reordered launch identity: {line!r}")
    if any(ord(ch) < 0x20 or ord(ch) > 0x7e for ch in value):
        raise SystemExit(f"control or non-ASCII value: {key}")
    parsed[key] = value
hex40 = {k for k in keys if k.endswith(("_blob", "_tree", "_commit", "_main"))}
hex64 = {k for k in keys if k.endswith("_sha256")}
integers = {k for k in keys if k.endswith(("_bytes", "_count", "_size", "_device", "_inode"))}
hex40.add("binary_build_id")
for key in hex40:
    if not re.fullmatch(r"[0-9a-f]{40}", parsed[key]):
        raise SystemExit(f"invalid Git identity: {key}")
for key in hex64:
    if not re.fullmatch(r"[0-9a-f]{64}", parsed[key]):
        raise SystemExit(f"invalid SHA-256 identity: {key}")
for key in integers:
    if not re.fullmatch(r"0|[1-9][0-9]*", parsed[key]):
        raise SystemExit(f"invalid integer identity: {key}")
required_literals = {
    "schema": "g5-protected-launch-identities-v1",
    "original_prereg_blob": "5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f",
    "g4_capability_probe_count": "9", "g4_perf_data_count": "0",
    "g4_campaign_cell_count": "0", "g4_campaign_sample_row_count": "0",
    "g4_terminal_gate": "admission-runner-contract", "g4_verdict": "VOID-NO-SELECT",
    "source_commit": "830a9a31deb00926a97f3fa5bd74f58003573fc0",
    "performance_sample": "NO", "campaign_cells": "0", "retained_perf_data": "0",
    "campaign_sample_rows": "0", "selection": "NO-SELECT",
}
for key, expected in required_literals.items():
    if parsed[key] != expected:
        raise SystemExit(f"fixed launch identity mismatch: {key}")
print(f"current_profile_g5_launch_identity_parser=PASS schema={parsed['schema']} keys={len(keys)}")
PY
}
```

Add dispatch
`--verify-launch-identity-files) verify_launch_identity_files "$2" "$3" ;;`.
Runner tests use this exact mutation matrix against a valid temporary pair:

```python
cases = {
    "missing_marker": (
        prereg_text.replace("<!-- g5-protected-launch-identities-v1-begin -->\n", "", 1),
        identity_text, "launch identity markers must occur exactly once"),
    "renamed_key": (prereg_text, identity_text.replace("runner_blob=", "runner_object=", 1),
                    "invalid or reordered launch identity"),
    "reordered_keys": (prereg_text,
        identity_text.replace("runner_blob=" + rows["runner_blob"] + "\nrunner_sha256=" + rows["runner_sha256"],
                              "runner_sha256=" + rows["runner_sha256"] + "\nrunner_blob=" + rows["runner_blob"], 1),
        "invalid or reordered launch identity"),
    "duplicate_key": (prereg_text, identity_text + "selection=NO-SELECT\n",
                      "launch identity key count mismatch"),
    "unknown_key": (prereg_text, identity_text + "unknown_key=value\n",
                    "launch identity key count mismatch"),
    "duplicate_marker": (prereg_text.replace(
        "<!-- g5-protected-launch-identities-v1-end -->",
        "<!-- g5-protected-launch-identities-v1-end -->\n"
        "<!-- g5-protected-launch-identities-v1-end -->", 1),
        identity_text, "launch identity markers must occur exactly once"),
    "wrong_width": (prereg_text,
        identity_text.replace(rows["runner_sha256"], rows["runner_sha256"][:-1], 1),
        "invalid SHA-256 identity: runner_sha256"),
    "fixed_literal": (prereg_text, identity_text.replace("performance_sample=NO", "performance_sample=YES", 1),
                      "fixed launch identity mismatch: performance_sample"),
    "block_file_drift": (prereg_text.replace("selection=NO-SELECT", "selection=NO-SELECX", 1),
                         identity_text, "preregistration block and identity file differ"),
}
```

For identity-file mutations, rebuild the marked prereg block from the mutated
identity before invoking the parser, except `block_file_drift`, which changes
only the preregistration byte. Each mutation must fail at its named parser
assertion.

Implement the exhaustive no-performance predicate exactly:

```bash
assert_admission_has_no_performance() {
    local root=$1 perf_count address_raw_count cell_dir_count max_min_summary_count
    local attribution_count pstat_count prec_count cell_journal_count
    perf_count=$(/usr/bin/find "$root" -type f -name perf.data -printf '.\n' | /usr/bin/wc -l)
    address_raw_count=$(/usr/bin/find "$root" -type f \
        \( -name address-smoke.data -o -name address-smoke.perf-script.txt \
        -o -name address-smoke.buildid-list.txt \) -printf '.\n' | /usr/bin/wc -l)
    cell_dir_count=$(/usr/bin/find "$root" -type d \
        -path "$root/cells/silesia-*" -printf '.\n' | /usr/bin/wc -l)
    max_min_summary_count=$(/usr/bin/find "$root" -type f \
        \( -path '*/silesia-*-max/attribution-summary.json' -o \
        -path '*/silesia-*-min/attribution-summary.json' \) -printf '.\n' | /usr/bin/wc -l)
    attribution_count=$(/usr/bin/find "$root" -type f -name attribution-summary.json \
        -printf '.\n' | /usr/bin/wc -l)
    pstat_count=$(/usr/bin/find "$root" -type f -name 'pstat*.perf-stat.csv' \
        -printf '.\n' | /usr/bin/wc -l)
    prec_count=$(/usr/bin/find "$root" -type f \
        \( -name 'prec*.data' -o -name 'prec*.perf-script.txt' \
        -o -name 'prec*.buildid-list.txt' -o -name 'prec*.record.json' \
        -o -name 'prec*.time.txt' \) -printf '.\n' | /usr/bin/wc -l)
    cell_journal_count=$(/usr/bin/awk -F '\t' \
        '{ for (i=1; i<=NF; i++) if ($i ~ /^cell=/) count++ } END { print count+0 }' \
        "$JOURNAL")
    [[ $perf_count == 0 ]] || die 'admission retained perf.data'
    [[ $address_raw_count == 0 ]] || die 'admission retained address-smoke raw artifact'
    [[ $max_min_summary_count == 0 ]] || die 'admission contains max/min attribution summary'
    [[ $attribution_count == 0 ]] || die 'admission contains attribution summary'
    [[ $pstat_count == 0 ]] || die 'admission contains pstat artifact'
    [[ $prec_count == 0 ]] || die 'admission contains prec artifact'
    [[ $cell_dir_count == 0 ]] || die 'admission contains campaign cell directory'
    [[ $cell_journal_count == 0 ]] || die 'admission journal contains cell row'
}
```

Each count must equal zero; the identity set must contain
`performance_sample=NO`, `campaign_cells=0`, `retained_perf_data=0`, and
`campaign_sample_rows=0`.

Expected: `--admission-feasibility` reaches map, fixture, and address-smoke
gates, never calls `run_cell`, and publishes only the selected admission root.

- [ ] **Step 6: Add no-performance mutations and run the full local checks**

Add a filesystem-only runner dispatch which creates no campaign path:

```bash
self_test_admission_no_performance() {
    local fixture_root=$1
    [[ $fixture_root == /tmp/* && -d $fixture_root && ! -L $fixture_root ]] ||
        die 'unsafe admission no-performance fixture root'
    PREFLIGHT_DIR=$fixture_root/preflight
    JOURNAL=$PREFLIGHT_DIR/journal.tsv
    [[ -f $JOURNAL && ! -L $JOURNAL ]] || die 'unsafe admission fixture journal'
    assert_admission_has_no_performance "$fixture_root"
    printf 'current_profile_g5_admission_no_performance_test=PASS\n'
}
```

Add dispatch
`--self-test-admission-no-performance) self_test_admission_no_performance "$2" ;;`.
The contract first proves an empty fixture passes, then uses this exact helper
for valid non-profiling artifact injections:

```bash
expect_admission_artifact_red() {
    local label=$1 relative=$2 expected=$3 root
    root=$mutation_root/admission-$label
    /usr/bin/mkdir -p -- "$root/preflight" "$(/usr/bin/dirname -- "$root/$relative")"
    : >"$root/preflight/journal.tsv"
    printf 'mutation\n' >"$root/$relative"
    capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance "$root"
    (( CHILD_RC != 0 )) || fail "admission artifact mutation survived: $label"
    /usr/bin/grep -qF "current_profile_g5=VOID reason=$expected" <<<"$CHILD_OUTPUT" ||
        invalid "admission artifact mutation failed elsewhere: $label output=$CHILD_OUTPUT"
}

positive_root=$mutation_root/admission-positive
/usr/bin/mkdir -p -- "$positive_root/preflight"
: >"$positive_root/preflight/journal.tsv"
capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance "$positive_root"
(( CHILD_RC == 0 )) && [[ $CHILD_OUTPUT == current_profile_g5_admission_no_performance_test=PASS ]] ||
  invalid "admission no-performance positive control failed: rc=$CHILD_RC output=$CHILD_OUTPUT"
expect_admission_artifact_red retained_perf perf.data 'admission retained perf.data'
for artifact in address-smoke.data address-smoke.perf-script.txt \
  address-smoke.buildid-list.txt; do
  expect_admission_artifact_red "address-${artifact//./-}" "$artifact" \
    'admission retained address-smoke raw artifact'
done
for cell in silesia-dickens-max silesia-xml-min; do
  expect_admission_artifact_red "summary-$cell" \
    "cells/$cell/attribution-summary.json" \
    'admission contains max/min attribution summary'
done
for sample in pstat1.perf-stat.csv pstat2.perf-stat.csv; do
  expect_admission_artifact_red "pstat-${sample//./-}" \
    "cells/silesia-xml-max/$sample" 'admission contains pstat artifact'
done
for repeat in prec1 prec2; do
  for suffix in data perf-script.txt buildid-list.txt record.json time.txt; do
    expect_admission_artifact_red "prec-$repeat-${suffix//./-}" \
      "cells/silesia-dickens-web/$repeat.$suffix" 'admission contains prec artifact'
  done
done
/usr/bin/mkdir -p -- "$mutation_root/admission-empty-cell/preflight" \
  "$mutation_root/admission-empty-cell/cells/silesia-dickens-max"
: >"$mutation_root/admission-empty-cell/preflight/journal.tsv"
capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance \
  "$mutation_root/admission-empty-cell"
(( CHILD_RC != 0 )) && /usr/bin/grep -qF \
  'current_profile_g5=VOID reason=admission contains campaign cell directory' <<<"$CHILD_OUTPUT"
/usr/bin/mkdir -p -- "$mutation_root/admission-journal/preflight"
printf 'cell=mutation\n' >"$mutation_root/admission-journal/preflight/journal.tsv"
capture_child /usr/bin/bash "$RUNNER" --self-test-admission-no-performance \
  "$mutation_root/admission-journal"
(( CHILD_RC != 0 )) && /usr/bin/grep -qF \
  'current_profile_g5=VOID reason=admission journal contains cell row' <<<"$CHILD_OUTPUT"
```

Then run:

```bash
bash -n documentation/ephemeral/research/current-profile-g5-run.sh
bash -n documentation/ephemeral/research/current-profile-g5-run-test.sh
shellcheck documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git diff --check
git diff --exit-code -- \
  documentation/ephemeral/research/current-profile-g4-run.sh \
  documentation/ephemeral/research/current-profile-g4-run-test.sh \
  documentation/ephemeral/research/current_profile_g4_map.py \
  documentation/ephemeral/research/test_current_profile_g4_map.py
```

Expected: Bash, ShellCheck, 51-or-more mapper tests, the runner contract, diff
check, and G4 immutability all pass; every no-performance mutation is RED.

- [ ] **Step 7: Commit the selected-root admission implementation**

Run:

```bash
git add -- documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git commit -m "feat: add isolated NEW-24 G5 admission root"
```

Expected: one commit limited to the two G5 Bash assets; `git status --short`
is empty after the commit.

## Task 6: Independently review and land the instrument through a protected PR

**Files:**

- Review: the four new G5 instrument files
- Read only: G5 preregistration, G4 preregistration, G4 terminal report, and G4 void package

- [ ] **Step 1: Run the full release and real round-trip suites from the exact source baseline**

In a clean detached checkout of
`830a9a31deb00926a97f3fa5bd74f58003573fc0`, run:

```bash
cd code/cubrim-rs
env CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  CARGO_PROFILE_RELEASE_DEBUG=1 \
  /usr/bin/taskset -c 0-15 cargo test --release
env CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  CARGO_PROFILE_RELEASE_DEBUG=1 \
  /usr/bin/taskset -c 0-15 cargo test --release \
  --test scheme_roundtrip -- --nocapture
cd ../..
git clean -fX -- code/cubrim-rs/Cargo.lock code/cubrim-rs/target
test -z "$(git status --porcelain)"
```

Expected: both suites pass under CPUs 0-15 and four-thread environment; cleanup
removes generated lock/target side effects; the final source status is empty.

- [ ] **Step 2: Run an owned-path secret and forbidden-effect scan**

Run:

```bash
set +e
rg -n '/usr/bin/(psql|curl)|world_benchmark_|config/credentials/|--retry|--resume|taskset -c (16-19|0-31)|corpus average|geometric mean' \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current_profile_g5_map.py \
  > /tmp/current-profile-g5-forbidden-implementation.txt
implementation_rg_rc=$?
set -e
test "$implementation_rg_rc" -eq 1
implementation_hits=$(wc -l < /tmp/current-profile-g5-forbidden-implementation.txt)
test "$implementation_hits" -eq 0
rg -n "^reject_runner_fixed '/usr/bin/psql'$|^reject_runner_fixed '/usr/bin/curl'$|^reject_runner_fixed 'config/credentials/'$" \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  > /tmp/current-profile-g5-forbidden-contract.txt
contract_hits=$(wc -l < /tmp/current-profile-g5-forbidden-contract.txt)
test "$contract_hits" -eq 3
rg -n --fixed-strings 'readonly -a PIN=(/usr/bin/taskset -c 0-15)' \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  > /tmp/current-profile-g5-pin-contract.txt
pin_hits=$(wc -l < /tmp/current-profile-g5-pin-contract.txt)
test "$pin_hits" -eq 1
```

Expected: `implementation_hits=0`, `contract_hits=3`, and `pin_hits=1`. The
three contract literals explicitly forbid PostgreSQL, curl, and
`config/credentials/`. Separate count assertions require three cells, five
verified decodes per cell, two records per cell, one 14,400-second budget, and
one `NO-SELECT` terminal contract.

- [ ] **Step 3: Obtain independent specification review of exact blobs**

Run:

```bash
review_head=$(git rev-parse HEAD)
git diff --binary origin/main..."$review_head" -- \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  documentation/ephemeral/research/current_profile_g5_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py \
  > /tmp/current-profile-g5-instrument-spec-review.diff
sha256sum /tmp/current-profile-g5-instrument-spec-review.diff
```

Dispatch a read-only specification reviewer with the exact preregistration,
G4 terminal report, `review_head`, and this diff. Require one terminal line
`READY: YES` or findings classified Critical/Important/Minor. Resolve every
Critical/Important finding, regenerate the diff, and rerun Tasks 2-5.

Expected: the reviewed diff SHA and `review_head` equal the bytes later pushed;
the terminal specification verdict is `READY: YES`.

- [ ] **Step 4: Obtain independent code/quality review of exact blobs**

Run:

```bash
test "$(git rev-parse HEAD)" = "$review_head"
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  > /tmp/current-profile-g5-runner-review-tests.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/test_current_profile_g5_map.py \
  > /tmp/current-profile-g5-mapper-review-tests.txt 2>&1
sha256sum /tmp/current-profile-g5-runner-review-tests.txt \
  /tmp/current-profile-g5-mapper-review-tests.txt
```

Dispatch a different read-only code/quality reviewer with the same diff and
the two exact test-output hashes. Require `READY: YES`; resolve every
Critical/Important finding and rerun the complete Task 5 check block.

Expected: the quality reviewer approves the same `review_head`, diff hash, and
test-output hashes as the specification reviewer.

- [ ] **Step 5: Push one normal branch and open the instrument PR**

Run:

```bash
git status --short
git push -u origin codex/cubr-new24-g5-instrument
gh pr create --base main --head codex/cubr-new24-g5-instrument \
  --title "feat: add NEW-24 G5 isolated attribution instrument" \
  --body "Prospective G5 instrument only. No campaign launch, performance result, selection, or external write."
```

Expected: clean status before push; a normal protected PR whose diff contains
only the four G5 instrument paths.

- [ ] **Step 6: Wait for exact-head CI and merge without bypass**

Run:

```bash
pr_number=$(gh pr view --json number --jq .number)
pr_head=$(gh pr view "$pr_number" --json headRefOid --jq .headRefOid)
test "$pr_head" = "$review_head"
gh pr checks "$pr_number" --watch
test "$(gh pr view "$pr_number" --json headRefOid --jq .headRefOid)" = "$pr_head"
gh pr merge "$pr_number" --merge --delete-branch
```

Expected: every required check is terminal-success for `pr_head`; merge is
performed normally with no self-approval, admin bypass, or stale check reuse.

- [ ] **Step 7: Verify resulting-main equality and landed blob parity**

Run:

```bash
git fetch origin main
instrument_main=$(git rev-parse origin/main)
git merge-base --is-ancestor "$pr_head" origin/main
for path in \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  documentation/ephemeral/research/current_profile_g5_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py; do
  test "$(git rev-parse "$pr_head:$path")" = "$(git rev-parse "origin/main:$path")"
done
printf 'instrument_resulting_main=%s\n' "$instrument_main"
printf '%s\n' "$instrument_main" > /tmp/current-profile-g5-instrument-resulting-main.txt
```

Expected: all assertions exit 0; one concrete `instrument_resulting_main` is
printed and persisted for Task 7. It is the instrument merge result and must
not later be replaced by the preregistration-amendment `launch_main`.

## Task 7: Run and seal the no-performance G5 admission feasibility

**Files:**

- Remote source checkout: `/root/cubr-new24-full-binary-g5-src`
- Remote build target: `/root/cubr-new24-full-binary-g5-target`
- Remote instrument checkout: `/root/cubr-new24-full-binary-g5-instrument`
- Remote dry-run output: `/root/cubr-new24-full-binary-g5-map-dryrun-20260810`
- Remote admission unit: `cubr-new24-full-binary-g5-admission-20260810.service`

- [ ] **Step 1: Derive and persist expected instrument identities from the landed Git objects**

Run locally from a fresh main read:

```bash
git fetch origin main
instrument_resulting_main=$(cat /tmp/current-profile-g5-instrument-resulting-main.txt)
test "$instrument_resulting_main" = "$(git rev-parse origin/main)"
identity_file=/tmp/current-profile-g5-landed-instrument-identities.env
runner_path=documentation/ephemeral/research/current-profile-g5-run.sh
runner_test_path=documentation/ephemeral/research/current-profile-g5-run-test.sh
mapper_path=documentation/ephemeral/research/current_profile_g5_map.py
mapper_test_path=documentation/ephemeral/research/test_current_profile_g5_map.py
{
  printf 'schema=g5-landed-instrument-identities-v1\n'
  printf 'instrument_resulting_main=%s\n' "$instrument_resulting_main"
  for pair in runner:"$runner_path" runner_test:"$runner_test_path" \
      mapper:"$mapper_path" mapper_test:"$mapper_test_path"; do
    key=${pair%%:*}
    path=${pair#*:}
    printf '%s_blob=%s\n' "$key" "$(git rev-parse "$instrument_resulting_main:$path")"
    printf '%s_sha256=%s\n' "$key" \
      "$(git cat-file blob "$instrument_resulting_main:$path" | sha256sum | awk '{print $1}')"
  done
} > "$identity_file"
chmod 0444 "$identity_file"
test "$(wc -l < "$identity_file")" -eq 10
```

Expected: ten canonical lines are persisted from authenticated Git objects;
no value is derived from a future runtime copy.

- [ ] **Step 2: Materialize exact clean source and instrument checkouts on `dev-ai`**

Run this exact bounded materialization from the local repository:

```bash
source /tmp/current-profile-g5-landed-instrument-identities.env
ssh root@100.118.134.82 /usr/bin/bash -s -- \
  "$instrument_resulting_main" "$runner_sha256" "$runner_test_sha256" \
  "$mapper_sha256" "$mapper_test_sha256" <<'REMOTE'
set -euo pipefail
instrument_resulting_main=$1
expected_runner_sha=$2
expected_runner_test_sha=$3
expected_mapper_sha=$4
expected_mapper_test_sha=$5
for path in \
  /root/cubr-new24-full-binary-g5-src \
  /root/cubr-new24-full-binary-g5-target \
  /root/cubr-new24-full-binary-g5-instrument \
  /root/cubr-new24-full-binary-g5-map-dryrun-20260810 \
  /root/cubr-new24-full-binary-g5-map-dryrun-20260810.partial \
  /root/cubr-new24-full-binary-g5-map-dryrun-20260810.publishing \
  /root/cubr-new24-full-binary-g5-map-dryrun-20260810.late; do
  [[ ! -e $path && ! -L $path ]] || { printf 'collision=%s\n' "$path" >&2; exit 2; }
done
/usr/bin/git clone --no-checkout https://github.com/Arcanada-one/cubrim.git \
  /root/cubr-new24-full-binary-g5-src
/usr/bin/git -C /root/cubr-new24-full-binary-g5-src checkout --detach \
  830a9a31deb00926a97f3fa5bd74f58003573fc0
/usr/bin/git clone --no-checkout https://github.com/Arcanada-one/cubrim.git \
  /root/cubr-new24-full-binary-g5-instrument
/usr/bin/git -C /root/cubr-new24-full-binary-g5-instrument checkout --detach \
  "$instrument_resulting_main"
repo=/root/cubr-new24-full-binary-g5-instrument/documentation/ephemeral/research
/usr/bin/install -m 0555 "$repo/current-profile-g5-run.sh" \
  /root/cubr-new24-full-binary-g5-run.sh
/usr/bin/install -m 0555 "$repo/current-profile-g5-run-test.sh" \
  /root/cubr-new24-full-binary-g5-run-test.sh
/usr/bin/install -m 0444 "$repo/current_profile_g5_map.py" \
  /root/cubr-new24-full-binary-g5-map.py
/usr/bin/install -m 0444 "$repo/test_current_profile_g5_map.py" \
  /root/cubr-new24-full-binary-g5-map-test.py
[[ $(sha256sum /root/cubr-new24-full-binary-g5-run.sh | awk '{print $1}') == "$expected_runner_sha" ]]
[[ $(sha256sum /root/cubr-new24-full-binary-g5-run-test.sh | awk '{print $1}') == "$expected_runner_test_sha" ]]
[[ $(sha256sum /root/cubr-new24-full-binary-g5-map.py | awk '{print $1}') == "$expected_mapper_sha" ]]
[[ $(sha256sum /root/cubr-new24-full-binary-g5-map-test.py | awk '{print $1}') == "$expected_mapper_test_sha" ]]
[[ -z $(git -C /root/cubr-new24-full-binary-g5-src status --porcelain) ]]
[[ -z $(git -C /root/cubr-new24-full-binary-g5-instrument status --porcelain) ]]
REMOTE
```

Expected: both checkouts are detached and clean at their distinct fixed
commits; all four runtime files match the landed SHA values before any remote
runner test executes.

- [ ] **Step 3: Validate the outer host allowlist and run the real dev-ai runner contract**

Run only after Step 2 succeeds:

```bash
ssh root@100.118.134.82 /usr/bin/bash -s <<'REMOTE'
set -euo pipefail
host_home=${HOME:-}
host_xdg=${XDG_RUNTIME_DIR:-}
host_dbus=${DBUS_SESSION_BUS_ADDRESS:-}
[[ -n $host_home ]] || { printf 'missing=HOME\n' >&2; exit 2; }
[[ -n $host_xdg ]] || { printf 'missing=XDG_RUNTIME_DIR\n' >&2; exit 2; }
[[ -n $host_dbus ]] || { printf 'missing=DBUS_SESSION_BUS_ADDRESS\n' >&2; exit 2; }
[[ -d $host_home && -d $host_xdg ]] || { printf 'invalid=host-directory\n' >&2; exit 2; }
capture_dir=/tmp/current-profile-g5-live-fixture
[[ ! -e $capture_dir && ! -L $capture_dir ]]
/usr/bin/mkdir -m 0700 -- "$capture_dir"
/usr/bin/env -i LC_ALL=C PATH=/usr/bin:/bin \
  HOME="$host_home" XDG_RUNTIME_DIR="$host_xdg" \
  DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
  CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  CUBR_REMOTE_LIVE_FIXTURE=1 \
  RUNNER=/root/cubr-new24-full-binary-g5-run.sh \
  MAPPER=/root/cubr-new24-full-binary-g5-map.py \
  /usr/bin/taskset -c 0-15 /usr/bin/bash \
  /root/cubr-new24-full-binary-g5-run-test.sh "$capture_dir"
test -s "$capture_dir/cgroup-live.tsv"
test -s "$capture_dir/systemd-run.output.txt"
/usr/bin/rm -r -- "$capture_dir"
REMOTE
```

Expected: exactly `current_profile_g5_contract=PASS`; the user-systemd fixture
passes, its descendant is contained, and no campaign or admission output path
is created. This is the first real dev-ai runner-test execution.

- [ ] **Step 4: Prove unit/output absence and launch the distinct admission service once**

First copy and authenticate the ten-line file from the local host:

```bash
local_identity=/tmp/current-profile-g5-landed-instrument-identities.env
remote_identity=/root/cubr-new24-full-binary-g5-landed-instrument-identities.env
local_identity_sha=$(sha256sum "$local_identity" | awk '{print $1}')
scp "$local_identity" root@100.118.134.82:"$remote_identity"
ssh root@100.118.134.82 chmod 0444 "$remote_identity"
remote_identity_sha=$(ssh root@100.118.134.82 sha256sum "$remote_identity" | awk '{print $1}')
test "$remote_identity_sha" = "$local_identity_sha"
remote_identity_lines=$(ssh root@100.118.134.82 wc -l "$remote_identity" | awk '{print $1}')
test "$remote_identity_lines" -eq 10
```

Then run inside the same validated dev-ai login environment:

```bash
set -euo pipefail
host_home=${HOME:-}
host_xdg=${XDG_RUNTIME_DIR:-}
host_dbus=${DBUS_SESSION_BUS_ADDRESS:-}
[[ -n $host_home && -n $host_xdg && -n $host_dbus ]]
unit=cubr-new24-full-binary-g5-admission-20260810.service
set +e
unit_load=$(/usr/bin/systemctl show "$unit" -p LoadState --value 2>/dev/null)
unit_rc=$?
set -e
[[ $unit_rc -ne 0 || $unit_load == not-found ]]
for suffix in '' .partial .publishing .late; do
  path=/root/cubr-new24-full-binary-g5-map-dryrun-20260810$suffix
  [[ ! -e $path && ! -L $path ]]
done
source /root/cubr-new24-full-binary-g5-landed-instrument-identities.env
/usr/bin/systemd-run \
  --unit="$unit" --service-type=exec \
  --property=Restart=no --property=RuntimeMaxSec=4h \
  --property=KillMode=control-group --property=KillSignal=SIGTERM \
  --property=FinalKillSignal=SIGKILL \
  --setenv=CUBR_SYSTEMD_UNIT="$unit" \
  --setenv=HOME="$host_home" \
  --setenv=XDG_RUNTIME_DIR="$host_xdg" \
  --setenv=DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
  --setenv=CUBR_THREADS=4 --setenv=RAYON_NUM_THREADS=4 \
  --setenv=OMP_NUM_THREADS=4 --setenv=MKL_NUM_THREADS=4 \
  --setenv=CUBR_INSTRUMENT_COMMIT="$instrument_resulting_main" \
  --setenv=CUBR_EXPECTED_RUNNER_SHA256="$runner_sha256" \
  --setenv=CUBR_EXPECTED_MAPPER_SHA256="$mapper_sha256" \
  --setenv=CUBR_EXPECTED_TEST_SHA256="$runner_test_sha256" \
  --setenv=CUBR_EXPECTED_MAPPER_TEST_SHA256="$mapper_test_sha256" \
  /usr/bin/taskset -c 0-15 /usr/bin/bash \
  /root/cubr-new24-full-binary-g5-run.sh --admission-feasibility
```

Expected: the local and remote identity bytes match before service creation;
the admission service starts once with all three validated outer host variables
and all four thread limits; pure-mock children still start from `env -i`.

- [ ] **Step 5: Verify terminal admission, exhaustive zero-sample predicates, cleanup, and clean trees**

After read-only monitoring reaches terminal, run:

```bash
unit=cubr-new24-full-binary-g5-admission-20260810.service
props=$(/usr/bin/systemctl show "$unit" -p Type -p Result -p ExecMainStatus \
  -p NRestarts -p InvocationID -p MainPID -p ControlGroup -p ActiveState -p SubState)
grep -qx 'Type=exec' <<<"$props"
grep -qx 'Result=success' <<<"$props"
grep -qx 'ExecMainStatus=0' <<<"$props"
grep -qx 'NRestarts=0' <<<"$props"
grep -qx 'ActiveState=inactive' <<<"$props"
root=/root/cubr-new24-full-binary-g5-map-dryrun-20260810
perf_count=$(/usr/bin/find "$root" -type f -name perf.data -printf '.\n' | /usr/bin/wc -l)
address_raw_count=$(/usr/bin/find "$root" -type f \( -name address-smoke.data \
  -o -name address-smoke.perf-script.txt -o -name address-smoke.buildid-list.txt \) \
  -printf '.\n' | /usr/bin/wc -l)
cell_dir_count=$(/usr/bin/find "$root" -type d \
  -path "$root/cells/silesia-*" -printf '.\n' | /usr/bin/wc -l)
attribution_count=$(/usr/bin/find "$root" -type f -name attribution-summary.json \
  -printf '.\n' | /usr/bin/wc -l)
pstat_count=$(/usr/bin/find "$root" -type f -name 'pstat*.perf-stat.csv' \
  -printf '.\n' | /usr/bin/wc -l)
prec_count=$(/usr/bin/find "$root" -type f \( -name 'prec*.data' \
  -o -name 'prec*.perf-script.txt' -o -name 'prec*.buildid-list.txt' \
  -o -name 'prec*.record.json' -o -name 'prec*.time.txt' \) \
  -printf '.\n' | /usr/bin/wc -l)
cell_journal_count=$(/usr/bin/awk -F '\t' \
  '{ for (i=1; i<=NF; i++) if ($i ~ /^cell=/) count++ } END { print count+0 }' \
  "$root/preflight/journal.tsv")
[[ $perf_count == 0 && $address_raw_count == 0 && $cell_dir_count == 0 ]]
[[ $attribution_count == 0 && $pstat_count == 0 && $prec_count == 0 && $cell_journal_count == 0 ]]
grep -qx 'performance_sample=NO' "$root/sealed-identity-set.env"
grep -qx 'campaign_cells=0' "$root/sealed-identity-set.env"
grep -qx 'retained_perf_data=0' "$root/sealed-identity-set.env"
grep -qx 'campaign_sample_rows=0' "$root/sealed-identity-set.env"
/usr/bin/git -C /root/cubr-new24-full-binary-g5-src clean -fX -- \
  code/cubrim-rs/Cargo.lock code/cubrim-rs/target
[[ -z $(git -C /root/cubr-new24-full-binary-g5-src status --porcelain) ]]
[[ -z $(git -C /root/cubr-new24-full-binary-g5-instrument status --porcelain) ]]
```

Expected: every terminal property passes, all seven exhaustive counts are zero,
the sealed identity set reports no performance, and both Git trees are clean.

- [ ] **Step 6: Persist and independently verify the sealed admission identity set**

Run:

```bash
remote=root@100.118.134.82
root=/root/cubr-new24-full-binary-g5-map-dryrun-20260810
remote_sha=$(ssh "$remote" sha256sum "$root/sealed-identity-set.env" | awk '{print $1}')
remote_bytes=$(ssh "$remote" /usr/bin/stat -c %s -- "$root/sealed-identity-set.env")
scp "$remote:$root/sealed-identity-set.env" /tmp/current-profile-g5-sealed-identity-set.env
test "$(sha256sum /tmp/current-profile-g5-sealed-identity-set.env | awk '{print $1}')" = "$remote_sha"
test "$(wc -c < /tmp/current-profile-g5-sealed-identity-set.env)" = "$remote_bytes"
test "$(stat -c %a /tmp/current-profile-g5-sealed-identity-set.env)" = 444
test "$(grep -c '^schema=g5-admission-identity-set-v1$' /tmp/current-profile-g5-sealed-identity-set.env)" -eq 1
test "$(cut -d= -f1 /tmp/current-profile-g5-sealed-identity-set.env | sort | uniq -d | wc -l)" -eq 0
```

Expected: local and remote bytes/hashes match, the file is read-only, the
schema occurs exactly once, and there are no duplicate keys. Preserve
`remote_sha` and `remote_bytes` for the protected amendment; do not read or
interpret any admission perf capability values.

## Task 8: Land the concrete preregistration identity amendment

**Files:**

- Modify: `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md`
- Create: `documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env`
- Read only: all G4 evidence and the sealed G5 admission output

- [ ] **Step 1: Create the amendment worktree and prove instrument blob parity**

Run:

```bash
git fetch origin main
test ! -e /tmp/cubr-g5-amendment-main
git worktree add -b codex/cubr-new24-g5-launch-seal \
  /tmp/cubr-g5-amendment-main origin/main
cd /tmp/cubr-g5-amendment-main
instrument_resulting_main=$(cat /tmp/current-profile-g5-instrument-resulting-main.txt)
git merge-base --is-ancestor "$instrument_resulting_main" HEAD
for path in \
  documentation/ephemeral/research/current-profile-g5-run.sh \
  documentation/ephemeral/research/current-profile-g5-run-test.sh \
  documentation/ephemeral/research/current_profile_g5_map.py \
  documentation/ephemeral/research/test_current_profile_g5_map.py; do
  test "$(git rev-parse "$instrument_resulting_main:$path")" = \
       "$(git rev-parse "HEAD:$path")"
done
```

Expected: fresh main contains the exact four reviewed instrument blobs while
`instrument_resulting_main` remains a separately recorded earlier commit.

- [ ] **Step 2: Verify the exhaustive G4 terminal boundary without interpreting probes**

Run:

```bash
g4=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810
expected_probes='perf-branch-misses.csv
perf-branches.csv
perf-cache-misses.csv
perf-cache-references.csv
perf-cycles.csv
perf-dTLB-load-misses.csv
perf-instructions.csv
perf-page-faults.csv
perf-task-clock.csv'
actual_probes=$(find "$g4/remote-evidence/preflight" -maxdepth 1 -type f \
  -name 'perf-*.csv' -printf '%f\n' | sort)
test "$actual_probes" = "$expected_probes"
test "$(find "$g4" -type f -name perf.data -printf '.\n' | wc -l)" -eq 0
test "$(find "$g4/remote-evidence" -type d \( -name 'dickens.*' -o -name 'xml.*' \) -printf '.\n' | wc -l)" -eq 0
test "$(find "$g4/remote-evidence" -type f -name cell-summary.json -printf '.\n' | wc -l)" -eq 0
test "$(grep -c $'admission-runner-contract' "$g4/remote-evidence/preflight/journal.tsv")" -eq 1
test "$(sha256sum "$g4/systemd-journal.jsonl" | awk '{print $1}')" = \
  8d57ceb1a2e53c8c715dd4bdcc17c05383494c83fbdbdfae4d16f91778acea74
test "$(wc -c < "$g4/systemd-journal.jsonl")" -eq 1071
test "$(sha256sum "$g4/remote-tree-manifest.tsv" | awk '{print $1}')" = \
  6ab89a7d8c83e8341a71a43c4379dc66c103898c13d012365cce277e93a15958
test "$(wc -c < "$g4/remote-tree-manifest.tsv")" -eq 2035
```

Expected: the nine probe filenames match exactly; all three sample/cell counts
are zero; the terminal gate and immutable G4 hashes/byte counts match. No probe
CSV value is parsed.

- [ ] **Step 3: Generate the canonical protected identity file from the sealed admission set**

Copy `/tmp/current-profile-g5-sealed-identity-set.env` to the new repository
path, then run this exact structured generator:

```bash
identity=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env
cp -- /tmp/current-profile-g5-sealed-identity-set.env /tmp/g5-admission-input.env
python3 - "$identity" /tmp/g5-admission-input.env <<'PY'
from pathlib import Path
import hashlib
import sys

target, source = map(Path, sys.argv[1:])
rows = {}
for line in source.read_text(encoding="utf-8").splitlines():
    key, sep, value = line.partition("=")
    if not sep or key in rows or not value:
        raise SystemExit(f"invalid admission identity line: {line!r}")
    rows[key] = value

ordered = [
    ("schema", "g5-protected-launch-identities-v1"),
    ("original_prereg_blob", "5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f"),
    ("g4_terminal_journal_sha256", "8d57ceb1a2e53c8c715dd4bdcc17c05383494c83fbdbdfae4d16f91778acea74"),
    ("g4_terminal_journal_bytes", "1071"),
    ("g4_failure_manifest_sha256", "6ab89a7d8c83e8341a71a43c4379dc66c103898c13d012365cce277e93a15958"),
    ("g4_failure_manifest_bytes", "2035"),
    ("g4_capability_probe_count", "9"),
    ("g4_perf_data_count", "0"),
    ("g4_campaign_cell_count", "0"),
    ("g4_campaign_sample_row_count", "0"),
    ("g4_terminal_gate", "admission-runner-contract"),
    ("g4_verdict", "VOID-NO-SELECT"),
]
copy_keys = [
    "instrument_resulting_main", "instrument_tree", "runner_blob", "runner_sha256",
    "runner_test_blob", "runner_test_sha256", "mapper_blob", "mapper_sha256",
    "mapper_test_blob", "mapper_test_sha256", "source_commit", "source_tree",
    "cubrim_rs_tree", "cargo_inputs_manifest_sha256", "generated_cargo_lock_sha256",
    "rustc_commit", "rustc_version", "cargo_version", "release_flags",
    "binary_sha256", "binary_build_id", "binary_size", "binary_device", "binary_inode",
    "mapping_schema_sha256", "corpus_manifest_sha256", "corpus_rows_sha256",
    "map_stream_sha256", "map_manifest_sha256", "map_summary_sha256", "map_row_count",
    "map_part_count", "map_seal_sha256", "sanitized_allowlist_contract_sha256",
    "runner_contract_test_sha256", "runner_contract_test_bytes",
    "live_fixture_result_sha256", "live_fixture_result_bytes",
    "live_fixture_test_output_sha256", "live_fixture_test_output_bytes",
    "performance_sample", "campaign_cells", "retained_perf_data",
    "campaign_sample_rows", "selection",
]
for key in copy_keys:
    if key not in rows:
        raise SystemExit(f"missing admission identity key: {key}")
    ordered.append((key, rows[key]))
source_bytes = source.read_bytes()
ordered.extend([
    ("admission_identity_set_sha256", hashlib.sha256(source_bytes).hexdigest()),
    ("admission_identity_set_bytes", str(len(source_bytes))),
])
target.write_text("".join(f"{key}={value}\n" for key, value in ordered), encoding="utf-8")
PY
chmod 0444 "$identity"
```

Expected: the file has exactly 59 ordered, nonempty key/value lines, starts
`schema=g5-protected-launch-identities-v1`, and ends with the sealed admission
identity-set byte count. No future `launch_main` or amended-prereg blob is
embedded, avoiding self-reference.

- [ ] **Step 4: Append the exact marked amendment block and validate it structurally**

Run this deterministic append only once:

```bash
prereg=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md
identity=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env
python3 - "$prereg" "$identity" <<'PY'
from pathlib import Path
import sys

prereg, identity = map(Path, sys.argv[1:])
begin = "<!-- g5-protected-launch-identities-v1-begin -->"
end = "<!-- g5-protected-launch-identities-v1-end -->"
text = prereg.read_text(encoding="utf-8")
if begin in text or end in text:
    raise SystemExit("protected launch amendment already exists")
block = identity.read_text(encoding="utf-8")
addition = (
    "\n## G5 protected launch identity amendment — 2026-08-10\n\n"
    + begin + "\n" + block + end + "\n"
)
prereg.write_text(text + addition, encoding="utf-8")
PY
/usr/bin/bash documentation/ephemeral/research/current-profile-g5-run.sh \
  --verify-launch-identity-files "$prereg" "$identity"
```

Expected: the parser prints
`current_profile_g5_launch_identity_parser=PASS schema=g5-protected-launch-identities-v1 keys=59`;
the marked block bytes equal the standalone identity file exactly.

- [ ] **Step 5: Run mutation, blob, and zero-performance amendment checks**

Run:

```bash
SELF_MUTATION_TESTS=1 bash \
  documentation/ephemeral/research/current-profile-g5-run-test.sh
git diff --check
test "$(grep -c '^performance_sample=NO$' \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env)" -eq 1
test "$(grep -c '^campaign_cells=0$' \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env)" -eq 1
test "$(grep -c '^selection=NO-SELECT$' \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env)" -eq 1
```

Expected: parser mutations for missing/duplicate/unknown/reordered keys,
malformed per-key values, duplicate markers, and block/file drift are RED;
the canonical identity file retains all three no-performance boundaries.

- [ ] **Step 6: Obtain exact-byte specification and evidence reviews**

Run:

```bash
amendment_base=$(git rev-parse HEAD)
git add -N -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env
git diff --binary -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env \
  > /tmp/current-profile-g5-amendment-review.diff
amendment_review_sha=$(sha256sum /tmp/current-profile-g5-amendment-review.diff | awk '{print $1}')
printf 'amendment_base=%s\namendment_review_sha256=%s\n' \
  "$amendment_base" "$amendment_review_sha" \
  > /tmp/current-profile-g5-amendment-review.env
```

Give one read-only reviewer the protocol and exact diff; give a different
reviewer the G4 package, admission seal, canonical identity file, and their
hashes. Each must return `READY: YES` for the same diff SHA. Resolve every
Critical/Important finding and rerun Steps 4-5.

Expected: both reviewers approve identical amendment bytes and the structured
parser, with no claim that G5 has launched.

- [ ] **Step 7: Commit, open, and merge the protected amendment PR at exact-head green**

Run:

```bash
git add -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env
git commit -m "docs: seal NEW-24 G5 launch identities"
source /tmp/current-profile-g5-amendment-review.env
test "$(git rev-parse HEAD^)" = "$amendment_base"
git diff --binary HEAD^..HEAD -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env \
  > /tmp/current-profile-g5-amendment-committed.diff
test "$(sha256sum /tmp/current-profile-g5-amendment-committed.diff | awk '{print $1}')" = \
  "$amendment_review_sha256"
git push -u origin codex/cubr-new24-g5-launch-seal
gh pr create --base main --head codex/cubr-new24-g5-launch-seal \
  --title "docs: seal NEW-24 G5 launch identities" \
  --body "Concrete prospective launch seal only. No G5 campaign or performance sample exists."
amendment_pr=$(gh pr view --json number --jq .number)
amendment_head=$(gh pr view "$amendment_pr" --json headRefOid --jq .headRefOid)
test "$amendment_head" = "$(git rev-parse HEAD)"
gh pr checks "$amendment_pr" --watch
test "$(gh pr view "$amendment_pr" --json headRefOid --jq .headRefOid)" = "$amendment_head"
reviewed_prereg_blob=$(git rev-parse "$amendment_head:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md")
reviewed_identities_blob=$(git rev-parse "$amendment_head:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env")
gh pr merge "$amendment_pr" --merge --delete-branch
git fetch origin main
launch_main=$(git rev-parse origin/main)
git merge-base --is-ancestor "$amendment_head" "$launch_main"
test "$(git rev-parse "$launch_main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md")" = "$reviewed_prereg_blob"
test "$(git rev-parse "$launch_main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env")" = "$reviewed_identities_blob"
printf 'launch_main=%s\nreviewed_prereg_blob=%s\nreviewed_identities_blob=%s\n' \
  "$launch_main" "$reviewed_prereg_blob" "$reviewed_identities_blob" \
  > /tmp/current-profile-g5-launch-git-identities.env
```

Expected: exact-head CI is green, normal merge succeeds, current main contains
the exact reviewed preregistration and identity-file blobs, and the three Git
launch identities are persisted separately from `instrument_resulting_main`.

## Task 9: Revalidate every hard gate and launch G5 exactly once

**Files and remote identities:**

- Campaign unit: `cubr-new24-full-binary-g5-20260810.service`
- Source: `/root/cubr-new24-full-binary-g5-src`
- Target: `/root/cubr-new24-full-binary-g5-target`
- Instrument: `/root/cubr-new24-full-binary-g5-instrument`
- Accepted output: `/root/cubr-new24-full-binary-g5-20260810`
- Failure paths: accepted output plus `.partial`, `.publishing`, and `.late`

- [ ] **Step 1: Fresh-fetch and authenticate the exact preregistration amendment blobs and schema**

Run locally immediately before remote prelaunch:

```bash
source /tmp/current-profile-g5-launch-git-identities.env
git fetch origin main
launch_main=$(git rev-parse origin/main)
prereg=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md
identity=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env
test "$(git rev-parse "$launch_main:$prereg")" = "$reviewed_prereg_blob"
test "$(git rev-parse "$launch_main:$identity")" = "$reviewed_identities_blob"
git cat-file blob "$launch_main:$prereg" > /tmp/current-profile-g5-launch-prereg.md
git cat-file blob "$launch_main:$identity" > /tmp/current-profile-g5-launch-identities.env
/usr/bin/bash documentation/ephemeral/research/current-profile-g5-run.sh \
  --verify-launch-identity-files \
  /tmp/current-profile-g5-launch-prereg.md \
  /tmp/current-profile-g5-launch-identities.env
instrument_resulting_main=$(awk -F= '$1=="instrument_resulting_main" {print $2}' \
  /tmp/current-profile-g5-launch-identities.env)
test "$instrument_resulting_main" != "$launch_main"
git merge-base --is-ancestor "$instrument_resulting_main" "$launch_main"
```

Expected: both exact reviewed blobs are still the blobs on fresh main; the
parser prints schema `g5-protected-launch-identities-v1` with 59 keys; the
instrument resulting-main remains distinct from and ancestral to launch main.

- [ ] **Step 2: Materialize the authenticated launch files without moving the instrument checkout**

Run:

```bash
scp /tmp/current-profile-g5-launch-prereg.md \
  root@100.118.134.82:/root/cubr-new24-full-binary-g5-launch-prereg.md
scp /tmp/current-profile-g5-launch-identities.env \
  root@100.118.134.82:/root/cubr-new24-full-binary-g5-launch-identities.env
scp /tmp/current-profile-g5-launch-git-identities.env \
  root@100.118.134.82:/root/cubr-new24-full-binary-g5-launch-git-identities.env
ssh root@100.118.134.82 /usr/bin/bash -s -- \
  "$launch_main" "$reviewed_prereg_blob" "$reviewed_identities_blob" \
  "$(sha256sum /tmp/current-profile-g5-launch-git-identities.env | awk '{print $1}')" <<'REMOTE'
set -euo pipefail
launch_main=$1
expected_prereg_blob=$2
expected_identities_blob=$3
expected_git_identities_sha=$4
instrument=/root/cubr-new24-full-binary-g5-instrument
/usr/bin/git -C "$instrument" fetch origin "$launch_main"
[[ $(git -C "$instrument" rev-parse HEAD) == \
   $(awk -F= '$1=="instrument_resulting_main" {print $2}' \
     /root/cubr-new24-full-binary-g5-launch-identities.env) ]]
[[ -z $(git -C "$instrument" status --porcelain) ]]
[[ $(git -C "$instrument" hash-object /root/cubr-new24-full-binary-g5-launch-prereg.md) == "$expected_prereg_blob" ]]
[[ $(git -C "$instrument" hash-object /root/cubr-new24-full-binary-g5-launch-identities.env) == "$expected_identities_blob" ]]
[[ $(git -C "$instrument" rev-parse "$launch_main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md") == "$expected_prereg_blob" ]]
[[ $(git -C "$instrument" rev-parse "$launch_main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-LAUNCH-IDENTITIES-20260810.env") == "$expected_identities_blob" ]]
/usr/bin/chmod 0444 /root/cubr-new24-full-binary-g5-launch-prereg.md \
  /root/cubr-new24-full-binary-g5-launch-identities.env \
  /root/cubr-new24-full-binary-g5-launch-git-identities.env
[[ $(sha256sum /root/cubr-new24-full-binary-g5-launch-git-identities.env | awk '{print $1}') == "$expected_git_identities_sha" ]]
REMOTE
```

Expected: the instrument worktree stays detached at
`instrument_resulting_main`; only Git objects are fetched; the two runtime
launch files equal their reviewed Git blobs and are read-only.

- [ ] **Step 3: Refuse collisions, wrong host/topology/load, competitors, or missing outer environment**

Run on `dev-ai`:

```bash
set -euo pipefail
[[ $(hostname) == dev-ai ]]
grep -qF 'AMD EPYC 7502P 32-Core Processor' /proc/cpuinfo
topology_rows=$(lscpu -p=CPU,CORE | awk -F, '!/^#/ {count++; if ($1<32 && $2!=$1) bad=1; if ($1>=32 && $2!=$1-32) bad=1} END {print count ":" bad+0}')
[[ $topology_rows == 64:0 ]]
awk '{exit !($1 < 8.0)}' /proc/loadavg
host_home=${HOME:-}; host_xdg=${XDG_RUNTIME_DIR:-}; host_dbus=${DBUS_SESSION_BUS_ADDRESS:-}
[[ -n $host_home && -n $host_xdg && -n $host_dbus ]]
unit=cubr-new24-full-binary-g5-20260810.service
set +e
unit_load=$(/usr/bin/systemctl show "$unit" -p LoadState --value 2>/dev/null)
unit_rc=$?
set -e
[[ $unit_rc -ne 0 || $unit_load == not-found ]]
for suffix in '' .partial .publishing .late; do
  path=/root/cubr-new24-full-binary-g5-20260810$suffix
  [[ ! -e $path && ! -L $path ]]
done
/usr/bin/ps -eo pid=,ppid=,comm=,args= > /tmp/current-profile-g5-prelaunch-processes.txt
competitor_count=$(awk '$3 ~ /^(cubrim|perf|cargo|rustc)$/ || $0 ~ /current-profile-g5-run/ {count++} END {print count+0}' \
  /tmp/current-profile-g5-prelaunch-processes.txt)
[[ $competitor_count == 0 ]]
```

Expected: exact host/topology/load and all three outer variables pass; unit and
four output variants are absent; competitor count is zero. Any failure is
`NO-LAUNCH` and no path or unit is removed or repaired.

- [ ] **Step 4: Re-run every no-performance hard gate with pin, thread limits, cleanup, and identity parsing**

Run on `dev-ai`:

```bash
set -euo pipefail
host_home=${HOME:-}
host_xdg=${XDG_RUNTIME_DIR:-}
host_dbus=${DBUS_SESSION_BUS_ADDRESS:-}
[[ -n $host_home && -n $host_xdg && -n $host_dbus ]]
common_env=(CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4)
source_dir=/root/cubr-new24-full-binary-g5-src
env "${common_env[@]}" CARGO_PROFILE_RELEASE_DEBUG=1 \
  /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo test --release \
  --manifest-path "$source_dir/code/cubrim-rs/Cargo.toml"
env "${common_env[@]}" CARGO_PROFILE_RELEASE_DEBUG=1 \
  /usr/bin/taskset -c 0-15 /root/.cargo/bin/cargo test --release \
  --manifest-path "$source_dir/code/cubrim-rs/Cargo.toml" \
  --test scheme_roundtrip -- --nocapture
capture_dir=/tmp/current-profile-g5-prelaunch-live-fixture
[[ ! -e $capture_dir && ! -L $capture_dir ]]
/usr/bin/mkdir -m 0700 -- "$capture_dir"
env -i LC_ALL=C PATH=/usr/bin:/bin \
  HOME="$host_home" XDG_RUNTIME_DIR="$host_xdg" DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
  "${common_env[@]}" CUBR_REMOTE_LIVE_FIXTURE=1 \
  RUNNER=/root/cubr-new24-full-binary-g5-run.sh \
  MAPPER=/root/cubr-new24-full-binary-g5-map.py \
  /usr/bin/taskset -c 0-15 /usr/bin/bash \
  /root/cubr-new24-full-binary-g5-run-test.sh "$capture_dir"
test -s "$capture_dir/cgroup-live.tsv"
test -s "$capture_dir/systemd-run.output.txt"
/usr/bin/rm -r -- "$capture_dir"
env "${common_env[@]}" PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/taskset -c 0-15 /usr/bin/python3 -m unittest -v \
  /root/cubr-new24-full-binary-g5-map-test.py
/usr/bin/bash /root/cubr-new24-full-binary-g5-run.sh \
  --verify-launch-identity-files \
  /root/cubr-new24-full-binary-g5-launch-prereg.md \
  /root/cubr-new24-full-binary-g5-launch-identities.env
/usr/bin/git -C "$source_dir" clean -fX -- code/cubrim-rs/Cargo.lock code/cubrim-rs/target
[[ -z $(git -C "$source_dir" status --porcelain) ]]
[[ -z $(git -C /root/cubr-new24-full-binary-g5-instrument status --porcelain) ]]
```

Expected: release, round-trip, runner/mutation, mapper, poisoned-parent,
live-unit noninterference, and structured identity gates all pass; cleanup
leaves both Git trees clean and no campaign path exists.

- [ ] **Step 5: Launch exactly once using literal authenticated amendment fields**

Load the already validated identity file without `eval`; only the exact keys
needed by the launcher are accepted. First prove the Task 5 authenticator and
its pre-performance `main_run` call are already present in the authenticated
landed runner; no code is edited after the instrument PR:

```bash
/usr/bin/grep -En '^authenticate_campaign_launch_inputs\(\)|^persist_authenticated_admission_identity\(\)' \
  /root/cubr-new24-full-binary-g5-run.sh
test "$(/usr/bin/grep -Ec '^    authenticate_campaign_launch_inputs$' \
  /root/cubr-new24-full-binary-g5-run.sh)" -eq 1
```

The already-landed runner re-runs `--verify-launch-identity-files`, hashes the
four installed runtime assets, compares the authenticated literals, and then
persists the admission identity bytes into the campaign tree.

```bash
source /root/cubr-new24-full-binary-g5-launch-git-identities.env
host_home=${HOME:-}
host_xdg=${XDG_RUNTIME_DIR:-}
host_dbus=${DBUS_SESSION_BUS_ADDRESS:-}
[[ -n $launch_main && -n $reviewed_prereg_blob && -n $reviewed_identities_blob ]]
[[ -n $host_home && -n $host_xdg && -n $host_dbus ]]
declare -A launch_identity=()
while IFS='=' read -r key value; do
  case $key in
    schema|instrument_resulting_main|runner_sha256|runner_test_sha256|mapper_sha256|mapper_test_sha256|admission_identity_set_sha256|admission_identity_set_bytes)
      [[ -z ${launch_identity[$key]+x} && -n $value ]] || exit 2
      launch_identity[$key]=$value
      ;;
  esac
done < /root/cubr-new24-full-binary-g5-launch-identities.env
test "${#launch_identity[@]}" -eq 8
[[ ${launch_identity[schema]} == g5-protected-launch-identities-v1 ]]
[[ ${launch_identity[instrument_resulting_main]} != "$launch_main" ]]
for key in runner_sha256 runner_test_sha256 mapper_sha256 mapper_test_sha256 \
  admission_identity_set_sha256; do
  [[ ${launch_identity[$key]} =~ ^[0-9a-f]{64}$ ]]
done
[[ ${launch_identity[admission_identity_set_bytes]} =~ ^(0|[1-9][0-9]*)$ ]]
/usr/bin/systemd-run \
  --unit=cubr-new24-full-binary-g5-20260810.service \
  --service-type=exec --property=Restart=no --property=RuntimeMaxSec=4h \
  --property=KillMode=control-group --property=KillSignal=SIGTERM \
  --property=FinalKillSignal=SIGKILL \
  --setenv=CUBR_SYSTEMD_UNIT=cubr-new24-full-binary-g5-20260810.service \
  --setenv=HOME="$host_home" \
  --setenv=XDG_RUNTIME_DIR="$host_xdg" \
  --setenv=DBUS_SESSION_BUS_ADDRESS="$host_dbus" \
  --setenv=CUBR_THREADS=4 --setenv=RAYON_NUM_THREADS=4 \
  --setenv=OMP_NUM_THREADS=4 --setenv=MKL_NUM_THREADS=4 \
  --setenv=CUBR_INSTRUMENT_COMMIT="${launch_identity[instrument_resulting_main]}" \
  --setenv=CUBR_EXPECTED_RUNNER_SHA256="${launch_identity[runner_sha256]}" \
  --setenv=CUBR_EXPECTED_TEST_SHA256="${launch_identity[runner_test_sha256]}" \
  --setenv=CUBR_EXPECTED_MAPPER_SHA256="${launch_identity[mapper_sha256]}" \
  --setenv=CUBR_EXPECTED_MAPPER_TEST_SHA256="${launch_identity[mapper_test_sha256]}" \
  --setenv=CUBR_EXPECTED_ADMISSION_IDENTITY_SHA256="${launch_identity[admission_identity_set_sha256]}" \
  --setenv=CUBR_EXPECTED_ADMISSION_IDENTITY_BYTES="${launch_identity[admission_identity_set_bytes]}" \
  --setenv=CUBR_ADMISSION_IDENTITY_SET=/root/cubr-new24-full-binary-g5-map-dryrun-20260810/sealed-identity-set.env \
  --setenv=CUBR_LAUNCH_MAIN="$launch_main" \
  --setenv=CUBR_EXPECTED_PREREG_BLOB="$reviewed_prereg_blob" \
  --setenv=CUBR_EXPECTED_IDENTITIES_BLOB="$reviewed_identities_blob" \
  --setenv=CUBR_LAUNCH_PREREG=/root/cubr-new24-full-binary-g5-launch-prereg.md \
  --setenv=CUBR_LAUNCH_IDENTITIES=/root/cubr-new24-full-binary-g5-launch-identities.env \
  /usr/bin/taskset -c 0-15 /usr/bin/bash \
  /root/cubr-new24-full-binary-g5-run.sh
```

Expected: the command contains no runtime `sha256sum` substitution. The runner
parses literal expected hashes from the authenticated amendment, hashes actual
runtime files only for comparison, asserts exact preregistration/identity Git
blobs and schema, and starts one new invocation. Never execute this command a
second time, including after an ambiguous client return.

- [ ] **Step 6: Monitor only terminal identity and filesystem state**

Run read-only checks:

```bash
unit=cubr-new24-full-binary-g5-20260810.service
/usr/bin/systemctl show "$unit" -p ActiveState -p SubState -p NRestarts \
  -p InvocationID -p MainPID -p ControlGroup
/usr/bin/journalctl -u "$unit" --output=json --no-pager \
  > /tmp/current-profile-g5-live-journal.jsonl
```

Expected: while active, one unchanged invocation, `NRestarts=0`, and no read of
timing counters, perf records, family shares, or campaign summaries. An
interruption, surviving process, or nonterminal tree routes to immutable
`VOID / NO-SELECT`; it never authorizes another launch.

## Task 10: Package and verify the terminal result for every route

**Files:** the result package and report paths in the file map

- [ ] **Step 1: Freeze systemd and remote-tree evidence before reading performance**

After the service is terminal, create the isolated result worktree and package
root, then capture the exact unit and invocation before copying bytes:

```bash
git fetch origin main
test ! -e /tmp/cubr-new24-g5-results
git worktree add -b codex/cubr-new24-g5-results \
  /tmp/cubr-new24-g5-results origin/main
cd /tmp/cubr-new24-g5-results
package=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810
mkdir -p "$package/remote-evidence"
unit=cubr-new24-full-binary-g5-20260810.service
remote=root@100.118.134.82
ssh "$remote" /usr/bin/systemctl show "$unit" \
  -p Type -p Restart -p RuntimeMaxUSec -p Result -p ExecMainStatus \
  -p NRestarts -p InvocationID -p MainPID -p ControlGroup \
  -p ActiveState -p SubState -p ExecMainStartTimestampMonotonic \
  -p ExecMainExitTimestampMonotonic >"$package/unit-properties.txt"
invocation=$(awk -F= '$1=="InvocationID" {print $2}' "$package/unit-properties.txt")
test "$(grep -c '^InvocationID=' "$package/unit-properties.txt")" -eq 1
test "$(grep -c '^Result=' "$package/unit-properties.txt")" -eq 1
test "$(grep -c '^ExecMainStatus=' "$package/unit-properties.txt")" -eq 1
[[ $invocation =~ ^[0-9a-f]{32}$ ]]
grep -qx 'NRestarts=0' "$package/unit-properties.txt"
ssh "$remote" /usr/bin/journalctl _SYSTEMD_INVOCATION_ID="$invocation" \
  --output=json --no-pager >"$package/systemd-journal.jsonl"
test -s "$package/systemd-journal.jsonl"
```

Resolve exactly one immutable terminal variant and prove the recorded cgroup
has no survivors. The remote script emits only the selected root path:

```bash
remote_tree=$(ssh "$remote" /usr/bin/bash -s <<'REMOTE'
set -euo pipefail
unit=cubr-new24-full-binary-g5-20260810.service
base=/root/cubr-new24-full-binary-g5-20260810
matches=()
for suffix in '' .partial .publishing .late; do
  path=$base$suffix
  if [[ -e $path || -L $path ]]; then matches+=("$path"); fi
done
[[ ${#matches[@]} == 1 ]]
cg=$(/usr/bin/systemctl show "$unit" -p ControlGroup --value)
if [[ -n $cg && -e /sys/fs/cgroup$cg/cgroup.procs ]]; then
  [[ ! -s /sys/fs/cgroup$cg/cgroup.procs ]]
fi
printf '%s\n' "${matches[0]}"
REMOTE
)
python3 - "$package/identities.tsv" "$remote_tree" "$invocation" \
  /tmp/current-profile-g5-launch-git-identities.env \
  /tmp/current-profile-g5-launch-identities.env <<'PY'
from pathlib import Path
import sys
target, remote_root, invocation, git_file, launch_file = sys.argv[1:]
def read_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if not sep or not key or key in values or "\t" in value or "\n" in value:
            raise SystemExit(f"invalid identity row: {line!r}")
        values[key] = value
    return values
rows = {"host":"dev-ai", "remote_evidence_root":remote_root,
        "unit":"cubr-new24-full-binary-g5-20260810.service",
        "invocation_id":invocation}
for key, value in read_env(git_file).items(): rows[f"git_{key}"] = value
for key, value in read_env(launch_file).items(): rows[f"launch_{key}"] = value
Path(target).write_text("field\tvalue\n" + "".join(
    f"{key}\t{rows[key]}\n" for key in sorted(rows)), encoding="utf-8")
PY
```

Generate the exact path/type/mode/owner/size/hash manifest on `dev-ai`, copy
the tree without dereferencing links, then independently compare every copied
node. This is byte transport only; no performance record is parsed:

```bash
ssh "$remote" /usr/bin/python3 - "$remote_tree" <<'PY' \
  >"$package/remote-tree-manifest.tsv"
import hashlib, os, stat, sys
from pathlib import Path
root = Path(sys.argv[1])
print("type\tmode\tuid\tgid\tsize_bytes\tsha256\tpath")
for path in [root, *sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())]:
    st = path.lstat()
    kind = "f" if stat.S_ISREG(st.st_mode) else "d" if stat.S_ISDIR(st.st_mode) else "l" if stat.S_ISLNK(st.st_mode) else "o"
    digest = "-"
    if kind == "f":
        h = hashlib.sha256()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with os.fdopen(fd, "rb", closefd=False) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
        finally:
            os.close(fd)
        digest = h.hexdigest()
    rel = "." if path == root else path.relative_to(root).as_posix()
    print(f"{kind}\t{stat.S_IMODE(st.st_mode):04o}\t{st.st_uid}\t{st.st_gid}\t{st.st_size}\t{digest}\t{rel}")
PY
rsync -a --numeric-ids -- "$remote:$remote_tree/" "$package/remote-evidence/"
PYTHONDONTWRITEBYTECODE=1 python3 - "$package" <<'PY'
import csv, hashlib, os, stat, sys
from pathlib import Path
package = Path(sys.argv[1]); root = package / "remote-evidence"
with (package / "remote-tree-manifest.tsv").open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream, delimiter="\t"))
assert rows and rows[0]["path"] == "."
seen = set()
for row in rows:
    rel = row["path"]
    assert rel not in seen and not rel.startswith("/") and ".." not in Path(rel).parts
    seen.add(rel); path = root if rel == "." else root / rel; st = path.lstat()
    kind = "f" if stat.S_ISREG(st.st_mode) else "d" if stat.S_ISDIR(st.st_mode) else "l" if stat.S_ISLNK(st.st_mode) else "o"
    assert kind == row["type"] and f"{stat.S_IMODE(st.st_mode):04o}" == row["mode"]
    assert str(st.st_size) == row["size_bytes"]
    if kind == "f": assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
actual = {"."} | {p.relative_to(root).as_posix() for p in root.rglob("*")}
assert actual == seen
PY
```

Expected: one 32-hex invocation, single captured `Result` and `ExecMainStatus`
fields, `NRestarts=0`, no cgroup survivor, exactly one
unaltered terminal variant, and exact local/remote node and byte parity. No
path is renamed, repaired, or semantically interpreted.

- [ ] **Step 2: Classify VOID without opening performance artifacts**

Classify the hard boundary from unit properties, node metadata, stamps, and
sealed identity only. The classifier must not open `perf.data`, timing files,
stat CSV files, record JSON, cell summaries, or attribution outputs:

```bash
boundary_file=/tmp/current-profile-g5-boundary.json
PYTHONDONTWRITEBYTECODE=1 python3 - "$package" "$boundary_file" <<'PY'
import hashlib, json, os, re, stat, sys
from pathlib import Path
p = Path(sys.argv[1]); boundary_file = Path(sys.argv[2]); root = p / "remote-evidence"
props = dict(line.split("=", 1) for line in (p / "unit-properties.txt").read_text().splitlines())
reasons = []
for key, value in {"Type":"exec", "Restart":"no", "Result":"success",
                   "ExecMainStatus":"0", "NRestarts":"0", "MainPID":"0"}.items():
    if props.get(key) != value: reasons.append(f"systemd:{key}")
if props.get("ActiveState") not in {"inactive", "failed"}: reasons.append("systemd:nonterminal")
unsafe = [x for x in root.rglob("*") if not (stat.S_ISREG(x.lstat().st_mode) or stat.S_ISDIR(x.lstat().st_mode))]
if unsafe: reasons.append("filesystem:unsafe-node")
final = root / "COMPLETE.STAMP"; failed = root / "FAILED.STAMP"
if final.exists() == failed.exists(): reasons.append("marker:missing-or-duplicate")
identity = root / "preflight" / "admission-sealed-identity-set.env"
identity_rows = dict(line.split("\t", 1) for line in (p / "identities.tsv").read_text().splitlines()[1:])
try:
    identity_stat = identity.lstat()
except FileNotFoundError:
    identity_stat = None
if identity_stat is None or not stat.S_ISREG(identity_stat.st_mode):
    reasons.append("identity:missing-or-unsafe")
else:
    allowed = {"schema", "performance_sample", "campaign_cells", "retained_perf_data", "campaign_sample_rows", "selection"}
    values = {}
    fd = os.open(identity, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        identity_bytes = stream.read()
    identity_lines = identity_bytes.decode("ascii").splitlines()
    for line in identity_lines:
        key, sep, value = line.partition("=")
        if sep and key in allowed:
            if key in values: reasons.append(f"identity:duplicate:{key}")
            values[key] = value
    if values.get("schema") != "g5-admission-identity-set-v1": reasons.append("identity:schema")
    expected_sha = identity_rows.get("launch_admission_identity_set_sha256", "")
    expected_bytes = identity_rows.get("launch_admission_identity_set_bytes", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha): reasons.append("identity:expected-sha")
    elif hashlib.sha256(identity_bytes).hexdigest() != expected_sha: reasons.append("identity:sha")
    if not re.fullmatch(r"0|[1-9][0-9]*", expected_bytes): reasons.append("identity:expected-bytes")
    elif len(identity_bytes) != int(expected_bytes): reasons.append("identity:bytes")
    fixed = {"performance_sample":"NO", "campaign_cells":"0",
             "retained_perf_data":"0", "campaign_sample_rows":"0"}
    for key, expected in fixed.items():
        if values.get(key) != expected: reasons.append(f"identity:{key}")
    if values.get("selection") != "NO-SELECT": reasons.append("identity:selection")
source_root = identity_rows["remote_evidence_root"]
if source_root.endswith((".partial", ".publishing", ".late")) or failed.exists():
    reasons.append("tree:not-authoritative-final")
boundary = {"schema":"cubr-new24-g5-boundary-v1", "performance_read":False,
            "selection":"NO-SELECT", "terminal_reasons":sorted(set(reasons))}
boundary_file.write_text(json.dumps(boundary, sort_keys=True, indent=2) + "\n")
print("VOID" if reasons else "VALID-CANDIDATE")
PY
boundary_route=$(PYTHONDONTWRITEBYTECODE=1 python3 -c \
  'import json,sys; d=json.load(open(sys.argv[1])); print("VOID" if d["terminal_reasons"] else "VALID-CANDIDATE")' \
  "$boundary_file")
```

If `boundary_route=VOID`, write final `result.json` with schema
`cubr-new24-full-binary-g5-result-v1`, route `VOID`, selection `NO-SELECT`,
`performance_read=false`, the exact sorted terminal reasons, empty `files` and
`p1_p5` objects, and all publication mutation flags false. If it is
`VALID-CANDIDATE`, defer `result.json` creation to Step 5.

```bash
if [[ $boundary_route == VOID ]]; then
  PYTHONDONTWRITEBYTECODE=1 python3 - "$package" "$boundary_file" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); boundary = json.loads(Path(sys.argv[2]).read_text())
result = {
    "files": {}, "p1_p5": {}, "performance_read": False,
    "publication_limits": {
        "api_mutation_performed": False, "backlog_mutation_performed": False,
        "credential_mutation_performed": False, "database_mutation_performed": False,
        "site_mutation_performed": False, "social_mutation_performed": False,
    },
    "route": "VOID", "schema": "cubr-new24-full-binary-g5-result-v1",
    "selection": "NO-SELECT", "terminal_reasons": boundary["terminal_reasons"],
}
(p / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
PY
fi
```

Expected: only exact `Result=success`, `ExecMainStatus=0`, admission-seal
SHA/byte parity with the authenticated launch identity, and all four fixed
no-performance values can produce `VALID-CANDIDATE`. Every mismatch produces
`VOID` without opening a performance-bearing file or emitting an interpreted
value; either route remains `NO-SELECT` and performs no DB/API/site/social/
backlog/credential mutation.

- [ ] **Step 3: Write RED package-verifier tests**

Create the test from the audited G4 mutation harness, mechanically rename its
module/class/package identifiers, and replace its case table with the exact G5
matrix below:

```bash
cp -- documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/test_verify_void_result.py \
  "$package/test_verify_result.py"
perl -0pi -e 's/verify_void_result/verify_result/g; s/VerifyVoidResult/VerifyResult/g; s/FULL-BINARY-G4-VOID/FULL-BINARY-G5-RESULTS/g; s/current_profile_g4/current_profile_g5/g' \
  "$package/test_verify_result.py"
```

The rewritten test defines these one-mutation fixtures and asserts
`returncode != 0` plus the exact error fragment:

```python
MUTATIONS = {
    "injected_file": "package path set mismatch",
    "symlink": "unsafe evidence node",
    "fifo": "unsafe evidence node",
    "path_traversal": "unsafe manifest path",
    "mode_drift": "remote mode mismatch",
    "owner_drift": "remote owner mismatch",
    "size_drift": "remote size mismatch",
    "hash_drift": "remote hash mismatch",
    "changed_invocation": "invocation identity mismatch",
    "restart": "NRestarts mismatch",
    "systemd_result": "systemd Result mismatch",
    "exec_main_status": "systemd ExecMainStatus mismatch",
    "surviving_pid": "terminal MainPID mismatch",
    "missing_tree": "remote evidence tree missing",
    "duplicate_marker": "terminal marker cardinality mismatch",
    "marker_drift": "terminal marker mismatch",
    "late_final": "late tree cannot be valid",
    "sealed_identity_sha": "sealed identity SHA mismatch",
    "sealed_identity_bytes": "sealed identity byte mismatch",
    "sealed_performance_sample": "sealed identity fixed value mismatch: performance_sample",
    "sealed_campaign_cells": "sealed identity fixed value mismatch: campaign_cells",
    "sealed_retained_perf_data": "sealed identity fixed value mismatch: retained_perf_data",
    "sealed_campaign_sample_rows": "sealed identity fixed value mismatch: campaign_sample_rows",
    "unknown_route": "unsupported route",
    "void_performance_read": "VOID performance_read must be false",
    "forbidden_effect_artifact": "forbidden effect path",
    "aggregate_speed": "aggregate result is forbidden",
    "cross_file_share": "cross-file family share is forbidden",
    "selection": "selection must be NO-SELECT",
}
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/test_verify_result.py
```

Expected: all 29 mutation subtests are RED because `verify_result.py` does not yet
exist; after implementation, those cases plus the three classifier cases run,
and the test fails if a mutation is rejected only for an unrelated reason.

- [ ] **Step 4: Implement the deterministic whole-package verifier**

Fork the audited safe-read/manifest helpers from the G4 verifier, then replace
all G4 constants and route-specific checks. The G5 verifier accepts exactly:

```python
ALLOWED_ROUTES = {
    ("VALID-ATTRIBUTION", "NO-SELECT"),
    ("VALID-DESCRIPTIVE", "NO-SELECT"),
    ("VOID", "NO-SELECT"),
}
EXPECTED_SELECTION = "NO-SELECT"
EXPECTED_RESULT_SCHEMA = "cubr-new24-full-binary-g5-result-v1"
EXPECTED_UNIT = "cubr-new24-full-binary-g5-20260810.service"
REQUIRED_CELLS = ("dickens/max", "xml/max", "dickens/web")
CELL_PATHS = {
    "dickens/max": "cells/silesia-dickens-max",
    "xml/max": "cells/silesia-xml-max",
    "dickens/web": "cells/silesia-dickens-web",
}
FORBIDDEN_RESULT_KEYS = {
    "corpus_mean", "geometric_mean", "aggregate_speed", "cross_file_share",
    "profiling_throughput", "candidate_expectation",
}
FORBIDDEN_PATH_PARTS = {
    "database", "api", "site", "social", "backlog", "credentials",
}
```

Add an explicit G5 classifier used by `--build-result`, rather than retaining
the copied G4 VOID-only classifier. It reads `campaign-verdict.tsv` first,
requires exactly the three `CELL_PATHS`, and classifies only these states:

```python
def classify_g5_route(campaign_rows, cells):
    status = campaign_rows.get("status")
    selection = campaign_rows.get("selection")
    if selection != EXPECTED_SELECTION:
        raise ValueError("selection must be NO-SELECT")
    if set(cells) != set(REQUIRED_CELLS):
        raise ValueError("required cell set mismatch")
    cell_statuses = {cell: cells[cell]["status"] for cell in REQUIRED_CELLS}
    if status == "VALID-ATTRIBUTION" and set(cell_statuses.values()) == {"VALID-ATTRIBUTION"}:
        return "VALID-ATTRIBUTION"
    if status == "VALID-DESCRIPTIVE" and set(cell_statuses.values()) <= {
            "VALID-ATTRIBUTION", "VALID-DESCRIPTIVE"}:
        return "VALID-DESCRIPTIVE"
    raise ValueError("unsupported G5 campaign/cell classification")
```

The parser obtains each `status` field from the cell's `verdict.txt`, the campaign
fields from `campaign-verdict.tsv`, and the attribution data only from that
cell's `attribution-summary.json`, `measurement-stability.tsv`, and two
`prec*.record.json` files. Add unit tests for all-attribution,
mixed-descriptive, and unsupported combinations; the boundary classifier
remains the only route able to emit `VOID` without reading performance files.

Implement these checks in this exact order, stopping at the first failure:

```text
1 package top-level allowlist and regular-file/no-follow reads
2 manifest header, safe unique relative paths, exact node set/type/mode/uid/gid/size/hash
3 exact unit, one 32-hex InvocationID, Type=exec, Restart=no, Result=success, ExecMainStatus=0, NRestarts=0, MainPID=0, terminal state
4 invocation-bound journal identity and zero second invocation
5 launch-main/prereg/identity, source, instrument, binary, corpus, map, and persisted `preflight/admission-sealed-identity-set.env` exact SHA/byte equality to `launch_admission_identity_set_{sha256,bytes}` plus its four fixed no-performance values
6 exactly one COMPLETE.STAMP xor FAILED.STAMP and root suffix compatible with route
7 schema, one allowed route, selection=NO-SELECT, boolean performance_read
8 VOID implies performance_read=false, files={}, p1_p5={}, no interpreted rows
9 valid implies exactly REQUIRED_CELLS, pstat1/pstat2 CSV and prec1/prec2 record samples per cell
10 valid implies correctness, mapping, period conservation, cycle agreement, perturbation, sample bound, repeatability gates true
11 VALID-DESCRIPTIVE implies every affected Amdahl ceiling is null with a reason
12 recursively reject FORBIDDEN_RESULT_KEYS and aggregate/cross-file objects
13 reject any package path whose case-folded component is in FORBIDDEN_PATH_PARTS
14 require all publication mutation flags false
```

The only successful stdout is `VALID-ATTRIBUTION / NO-SELECT`,
`VALID-DESCRIPTIVE / NO-SELECT`, or `VOID / NO-SELECT`.

```bash
cp -- documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G4-VOID-20260810/verify_void_result.py \
  "$package/verify_result.py"
chmod 0755 "$package/verify_result.py"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile "$package/verify_result.py"
```

Expected: the implementation contains all fourteen ordered gates, imports no
network/database client, and passes Python compilation before mutation tests.

- [ ] **Step 5: Verify a valid route per file without selection**

For `boundary_route=VALID-CANDIDATE`, verify the three explicit per-file
summaries already frozen by the runner and construct `result.json` without an
aggregate reduction. For `VOID`, retain the Step 2 result. Then render and
verify the complete package for either route:

```bash
if [[ $boundary_route == VALID-CANDIDATE ]]; then
  for cell in silesia-dickens-max silesia-xml-max silesia-dickens-web; do
    dir=$package/remote-evidence/cells/$cell
    test -f "$dir/pstat1.perf-stat.csv"
    test -f "$dir/pstat2.perf-stat.csv"
    test -f "$dir/prec1.data"
    test -f "$dir/prec2.data"
    test -f "$dir/prec1.record.json"
    test -f "$dir/prec2.record.json"
    test -f "$dir/attribution-summary.json"
    test -f "$dir/measurement-stability.tsv"
    test -f "$dir/verdict.txt"
  done
  PYTHONDONTWRITEBYTECODE=1 python3 "$package/verify_result.py" \
    --build-result --package "$package" \
    --cell dickens/max="$package/remote-evidence/cells/silesia-dickens-max/attribution-summary.json" \
    --cell xml/max="$package/remote-evidence/cells/silesia-xml-max/attribution-summary.json" \
    --cell dickens/web="$package/remote-evidence/cells/silesia-dickens-web/attribution-summary.json"
else
  test "$boundary_route" = VOID
  test -s "$package/result.json"
fi
```

`--build-result` copies each cell's two raw `pstat*.perf-stat.csv` identities,
two `prec*.record.json`
identities, P1-P5, cycle agreement, perturbation, sample bound, repeatability,
and eligible perfect-family Amdahl ceiling into its own key. It emits
`VALID-ATTRIBUTION` only when every attribution gate is true; otherwise it
emits `VALID-DESCRIPTIVE` and nulls each affected ceiling with its exact gate
reason. It never sums or averages across keys.

Generate the Markdown report deterministically from `result.json`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 "$package/verify_result.py" \
  --render-report "$package/result.json" \
  --output documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md
test -s documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md
for required in result.json identities.tsv unit-properties.txt systemd-journal.jsonl \
  remote-tree-manifest.tsv verify_result.py test_verify_result.py; do
  test -s "$package/$required"
done
test -d "$package/remote-evidence"
```

Expected: exactly three separate cells, two stat and two record identities per
cell, one P1-P5 object per cell, no aggregate key, and `NO-SELECT` for either
valid route.

- [ ] **Step 6: Run verifier tests and self-mutation checks**

Run:

```bash
PACKAGE=documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810
PYTHONDONTWRITEBYTECODE=1 python3 "$PACKAGE/verify_result.py" --package "$PACKAGE"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v "$PACKAGE/test_verify_result.py"
git diff --check
```

Expected: verifier prints exactly the terminal verdict plus `/ NO-SELECT`;
all mutations pass by being rejected.

- [ ] **Step 7: Obtain independent result specification and evidence reviews**

Freeze one exact review bundle and hash it:

```bash
result_base=$(git rev-parse HEAD)
git add -N -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  "$package"
git diff --binary -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  "$package" > /tmp/current-profile-g5-result-review.diff
result_review_sha=$(sha256sum /tmp/current-profile-g5-result-review.diff | awk '{print $1}')
printf 'result_base=%s\nresult_review_sha256=%s\n' \
  "$result_base" "$result_review_sha" > /tmp/current-profile-g5-result-review.env
```

One read-only reviewer checks every G5 gate and route in that exact diff. A
different reviewer recomputes the manifest, identities, unit/journal boundary,
P1-P5 reduction, and no-performance-on-VOID rule. Both return `READY: YES`
against the same `result_review_sha`; otherwise resolve every Critical or
Important finding, regenerate the bundle, and rerun Steps 5-6.

Expected: two independent `READY: YES` verdicts cite the identical review SHA
and candidate head; neither review authorizes a second campaign invocation.

- [ ] **Step 8: Land the terminal package through a normal exact-head PR**

Stage only the result report and package in the isolated result worktree:

```bash
git -C /tmp/cubr-new24-g5-results add -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810
git -C /tmp/cubr-new24-g5-results commit \
  -m "docs: record terminal NEW-24 G5 attribution result"
source /tmp/current-profile-g5-result-review.env
test "$(git -C /tmp/cubr-new24-g5-results rev-parse HEAD^)" = "$result_base"
git -C /tmp/cubr-new24-g5-results diff --binary HEAD^..HEAD -- \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810 \
  > /tmp/current-profile-g5-result-committed.diff
test "$(sha256sum /tmp/current-profile-g5-result-committed.diff | awk '{print $1}')" = "$result_review_sha256"
git -C /tmp/cubr-new24-g5-results push -u origin codex/cubr-new24-g5-results
gh pr create --repo Arcanada-one/cubrim --base main \
  --head codex/cubr-new24-g5-results \
  --title "docs: record terminal NEW-24 G5 attribution result" \
  --body "Terminal G5 evidence and deterministic NO-SELECT verdict; no database or external mutation."
```

Run secret/forbidden-effect scans, object-size checks below 90,000,000 bytes,
then exact-head CI and a normal protected merge:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - "$package" <<'PY'
import csv, json, os, re, stat, sys
from pathlib import Path, PurePosixPath

package = Path(sys.argv[1])
secret = re.compile(rb"postgres(?:ql)?://|https?://[^ ]+:[^ ]+@|AKIA[0-9A-Z]{16}")
for path in [package / "result.json", *(package / "remote-evidence").rglob("*")]:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise SystemExit(f"unsafe evidence symlink: {path}")
    if stat.S_ISREG(mode):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            if secret.search(stream.read()):
                raise SystemExit(f"secret-like payload: {path}")

def forbidden_path(value):
    if not isinstance(value, str):
        return False
    parts = tuple(part.casefold() for part in PurePosixPath(value).parts)
    return any(parts[i:i + 2] == ("config", "credentials")
               for i in range(len(parts) - 1))

with (package / "remote-tree-manifest.tsv").open(newline="", encoding="utf-8") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        if forbidden_path(row["path"]):
            raise SystemExit("semantic forbidden manifest path")

def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if forbidden_path(key):
                raise SystemExit("semantic forbidden result key")
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)
    elif forbidden_path(value):
        raise SystemExit("semantic forbidden result value")

walk(json.loads((package / "result.json").read_text(encoding="utf-8")))
print("current_profile_g5_semantic_forbidden_scan=PASS")
PY
git -C /tmp/cubr-new24-g5-results ls-tree -r --long HEAD \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  "$package" | awk '$4 >= 90000000 {print; bad=1} END {exit bad}'
result_pr=$(gh pr view --json number --jq .number)
result_pr_head=$(gh pr view "$result_pr" --json headRefOid --jq .headRefOid)
test "$result_pr_head" = "$(git -C /tmp/cubr-new24-g5-results rev-parse HEAD)"
gh pr checks "$result_pr" --watch
test "$(gh pr view "$result_pr" --json headRefOid --jq .headRefOid)" = "$result_pr_head"
gh pr merge "$result_pr" --merge --delete-branch
git fetch origin main
result_main=$(git rev-parse origin/main)
git merge-base --is-ancestor "$result_pr_head" "$result_main"
for path in \
  documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810.md \
  "$package/result.json" "$package/verify_result.py" "$package/remote-tree-manifest.tsv"; do
  test "$(git rev-parse "$result_pr_head:$path")" = "$(git rev-parse "$result_main:$path")"
done
```

Expected: the semantic forbidden scan passes without self-matching verifier
contract literals, every landed blob is below
90,000,000 bytes, CI is green for the exact merged head, and fresh resulting
main contains the exact reviewed report, result, verifier, and manifest blobs.
No result route writes the database, API, site, social channel,
`config/credentials/`, or backlog.

- [ ] **Step 9: Preserve the decision boundary after merge**

Read the landed JSON from fresh main and assert the decision boundary:

```bash
git fetch origin main
git show origin/main:documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-RESULTS-20260810/result.json \
  > /tmp/current-profile-g5-landed-result.json
python3 - /tmp/current-profile-g5-landed-result.json <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["schema"] == "cubr-new24-full-binary-g5-result-v1"
assert (d["route"], d["selection"]) in {
    ("VALID-ATTRIBUTION", "NO-SELECT"),
    ("VALID-DESCRIPTIVE", "NO-SELECT"),
    ("VOID", "NO-SELECT"),
}
assert d["publication_limits"] == {
    "api_mutation_performed": False,
    "backlog_mutation_performed": False,
    "credential_mutation_performed": False,
    "database_mutation_performed": False,
    "site_mutation_performed": False,
    "social_mutation_performed": False,
}
print(f'{d["route"]} / {d["selection"]}')
PY
git diff --quiet "$result_pr_head^" "$result_main" -- datarim/backlog.md datarim/tasks.md
```

Expected: the exact landed route prints with `NO-SELECT`, and the delivery
contains no backlog/task mutation. NEW-24 therefore stays `in_progress`, its
measurement fields remain empty, `evaluation` remains `0`, and no duplicate
hypothesis row is created. Any candidate requires a separately reviewed
prospective mechanism, ceiling, density boundary, predictions, and acceptance
gates on main before candidate construction.

## Validation checklist

- [ ] Fresh `origin/main` equals the expected base before implementation and contains exact reviewed blobs before each protected transition.
- [ ] The four G4 instrument files and every G4 result/evidence file remain byte-identical and unmodified.
- [ ] All 88 transitive campaign-root references inherit the mode-selected root, and admission filesystem tests prove zero final/partial/publishing/late campaign-path creation.
- [ ] Pure mock subprocesses start from an empty environment and receive only `LC_ALL=C`, `PATH=/usr/bin:/bin`, and their exact fixture unit.
- [ ] The user-systemd outer launcher receives only nonempty `HOME`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `LC_ALL`, and `PATH`; fixture authority is assigned only by `systemd-run --setenv`.
- [ ] Both admission and campaign services receive validated `HOME`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS` and the four thread-limit variables; pure-mock children retain `env -i`.
- [ ] Poisoned parent authority cannot reach mock output, sentinel, systemctl argument, or live fixture.
- [ ] Removing the empty-environment boundary, admitting poison, substituting the campaign unit, skipping post-self-test identity rereads, or skipping descendant containment makes the exact intended test RED.
- [ ] Every self-test is followed by a live G5 campaign `InvocationID`, `MainPID`, `NRestarts=0`, and `ControlGroup` reread when admission enforcement is enabled.
- [ ] New G5 paths, schemas, unit, invocation, PID baseline, monotonic clock, map seal, and output tree are distinct from G4.
- [ ] `seal-admission` performs exactly one output join: absolute `$PARTIAL/map` plus relative `map-admission-seal.json`; no nested `map/map-*` seal exists.
- [ ] The no-performance admission result has zero campaign cells, zero retained `perf.data`, zero interpreted counters, and `performance_sample=NO`.
- [ ] The sealed admission identity set is persisted and independently byte/hash verified before amendment generation.
- [ ] The protected preregistration amendment and standalone file contain exactly the ordered 59-key `g5-protected-launch-identities-v1` schema, match byte-for-byte, and land as the exact reviewed Git blobs before launch.
- [ ] `instrument_resulting_main` stays separately recorded, differs from `launch_main`, and is its ancestor; runtime expected hashes come only from literal authenticated amendment fields.
- [ ] The campaign uses CPUs `0-15`, four threads, `Type=exec`, `Restart=no`, four-hour unit cap, 14,400-second monotonic budget, control-group kill, and exactly one launch.
- [ ] Release, round-trip, runner, and mapper checks run under the `0-15` pin and four-thread environment, then remove generated lock/target artifacts and leave both trees clean.
- [ ] Owned-path scan counts are exactly implementation `0`, contract forbiddens `3` including `config/credentials/`, and pin declaration `1`.
- [ ] Terminal packaging handles valid and void routes; VOID reads no performance and writes no database; every route is `NO-SELECT` and per-file only.
- [ ] Before any valid-route performance read, captured systemd state is exactly `Result=success` and `ExecMainStatus=0`, the persisted admission identity matches authenticated launch SHA/bytes, and its four no-performance literals are exact.
- [ ] Independent specification and quality/evidence reviews approve the same exact blobs that CI and resulting main contain.

## Path and symbol validation

`PATH VALIDATION` at plan authoring checked 9 tracked repository references:
the G5 preregistration, G4 preregistration, G4 terminal report, G4 void package,
four G4 instrument assets, and the existing Datarim plan directory are present
at the reviewed ancestry anchor
`367b6c74143ce9d6d987d9e75f47cd8f70813ce7` and are reauthenticated on fresh
main before edits. The four G5 instrument files,
the protected launch-identity file, and nine terminal-result surfaces are
explicitly created by this plan. Runtime
paths under `/root/cubr-new24-full-binary-g5-*`, `/root/phaseC`,
`/root/corpus-full/silesia`, and `/sys/fs/cgroup` are external `dev-ai`
admission prerequisites and are not asserted present by this repository plan.
`/usr/bin/bash`, `/usr/bin/env`, `/usr/bin/systemd-run`, `/usr/bin/systemctl`,
`/usr/bin/taskset`, `/usr/bin/perf`, `/usr/bin/time`, `/usr/bin/sha256sum`,
`/usr/bin/readelf`, `/usr/bin/objdump`, and `/usr/bin/addr2line` are required
host tools and are re-probed before feasibility and launch. No referenced
present repository path carries a deprecation marker.

`SYMBOL VALIDATION` before implementation must re-run:

```bash
rg -n '^(verify_systemd_contract|self_test_cgroup|self_test_cgroup_live|self_test_cgroup_precommit|build_full_instruction_map|verify_address_join_smoke|publish_campaign|main_run)\(\)' \
  documentation/ephemeral/research/current-profile-g4-run.sh
rg -n '^(def (build_instruction_rows|split_instruction_map|verify_map_parts|reduce_record|summarize_file|make_parser|main)|class MappingError)' \
  documentation/ephemeral/research/current_profile_g4_map.py
```

Expected: every source symbol used by the copy-and-adapt steps exists on the
fresh implementation base; any missing symbol requires stopping before edits
and re-planning from current main.
