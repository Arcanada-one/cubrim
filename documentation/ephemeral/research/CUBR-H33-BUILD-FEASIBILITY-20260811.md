# H-33 admission-build feasibility, measured both sides of the lock commit

H-33's plan freezes exactly one permitted build (`datarim/plans/H-33-digit-split-oracle-implementation-plan.md`,
Task 9), states that any tool or cache miss is `NO-LAUNCH`, and forbids adding a
flag or fetching a dependency after review. That makes the build a **one-shot
gate**: the first failure is terminal.

Until PR #106 that gate could not pass. This note records the measurement on
both sides of it, so the next session to execute H-33 has evidence rather than
an assumption, and knows the one precondition that is still not carried by the
repository.

## The frozen build array

```text
/usr/bin/env -i HOME=/home/dev PATH=/home/dev/.cargo/bin:/usr/bin:/bin \
  LANG=C LC_ALL=C TZ=UTC CARGO_HOME=/home/dev/.cargo \
  RUSTUP_HOME=/home/dev/.rustup CARGO_NET_OFFLINE=true \
  CARGO_TARGET_DIR=REPO/code/cubrim-rs/target-h33 \
  /home/dev/.cargo/bin/cargo build --offline --locked --release \
  --manifest-path REPO/code/cubrim-rs/Cargo.toml
```

Both runs below used that array verbatim on `arcana-devs` — the plan's own
execution host — against a fresh detached worktree, with scratch paths
substituted for `REPO` and the target directory. No H-33 owned path was
created and no H-33 allowance was touched.

## Before the lock was committed: NO-LAUNCH

Fresh detached worktree at main `a905fb3`:

```text
error: cannot create the lock file .../code/cubrim-rs/Cargo.lock
       because --locked was passed to prevent this
exit 101
```

`code/cubrim-rs/Cargo.lock` was gitignored, so a fresh checkout had none, and
`--locked` refuses to create one. The failure is immediate and total: it
happens before a single crate is compiled, and the plan's own rules forbid the
recovery (adding a flag). H-33 would have reached admission, failed, and
consumed its allowance on an environment defect unrelated to its hypothesis.

## After the lock was committed: GO

Fresh detached worktree at main `53c15ff`:

```text
Finished `release` profile [optimized] target(s) in 39.31s
exit 0
```

PR #106 committed `code/cubrim-rs/Cargo.lock` and un-ignored it via a negation.
That change was made on supply-chain merits and its record
(`CUBR-BUILD-DETERMINISM-20260811.md`) correctly disclaims being a NEW-24 G6
fix. It does not mention H-33 at all — so the fact that it also removes H-33's
admission blocker is unrecorded elsewhere, which is why this note exists.

## Cross-version check: the lock is not host-specific

The lock is `version = 4`, generated under `cargo 1.97.1` on `arcana-devs`. The
benchmark stand `dev-ai` runs the older `cargo 1.96.1`, so format skew was a
live risk. Measured directly, with the same lock placed in a clean clone on
`dev-ai`:

```text
Finished `release` profile [optimized] target(s) in 21.44s
exit 0
```

Both hosts build the committed lock. Format skew is closed by measurement, not
argument.

## The precondition the repository still does not carry

`--locked` is now satisfied by the repo. **`--offline` is not, and cannot be.**
With a complete lock there is nothing left to resolve, so no index access is
needed — but cargo still needs the *bytes* of all 175 locked packages present
in `$CARGO_HOME`. A miss produces a different and equally terminal error:

```text
failed to download ... attempted to download in offline mode
```

`CARGO_NET_OFFLINE=true` does not soften this; it is the same switch as
`--offline`. Crate availability is a property of a machine's cargo home, not of
the commit, so it is not carried by any merge.

Both runs above passed because both hosts' caches happened to be warm today.
That is a fact about today, not a guarantee.

**Before H-33 spends its admission allowance, run `cargo fetch --locked` on the
execution host, out of band and online.** It is idempotent, retryable, carries
no scientific allowance, and populates the cache for exactly the locked graph.
After it, the frozen array is deterministic.

## The structural lesson

G6 and H-33 failed for opposite-looking reasons with one shared cause: **a
one-shot plan asserted an unverified precondition about state the repository
does not fix.** G6 pinned an output derived from an unpinned input; H-33
demanded a pinned input that was never committed.

The durable fix is not another constant. It is separation: *the one-shot
property belongs to the measurement, never to the environment check.* An
experiment plan should cite a freely rerunnable build-readiness probe as a
precondition — assert the lock is tracked and in sync, assert the toolchain,
then run the exact frozen array and print GO/NO-GO — and spend its allowance
only on the measurement it was designed for. A probe may run a hundred times;
an admission may run once.

This note is that probe's result for H-33 as of main `53c15ff`. It authorizes
no launch, issues no H-33 outcome, and reads no H-33 result. It records a
build gate, nothing more.
