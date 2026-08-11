# CUBR-BUILD-DETERMINISM-20260811 — committing the CLI lock, on supply-chain merits

**This is not a NEW-24 G6 fix, and it must not be read as one.** An earlier draft of this change was
framed that way; a consilium review and direct reading of G6 showed the framing was wrong on three
counts, all verified against `origin/main`:

1. **G6's protocol already built with `--locked`** (`datarim/plans/NEW-24-current-profile-g6-plan.md`
   lines 190, 231-232). Adding `--locked` to CI addresses nothing G6 did.
2. **G6 is terminal, not blocked.** Its own result states *"G6 cannot be retried. Its prebuild
   allowance is spent"* (results line 103), and that any future attempt is a new protocol with a new
   preregistration. There is nothing to unblock.
3. **G6 did not fail on the gitignored lock.** It failed comparing a freshly-resolved lock against a
   `LOCK_SHA` constant frozen at 2026-08-09T16:57:54Z, invalidated by crates published between the
   freeze and the run — *"the frozen lock identity was unreproducible by construction"* (results
   line 32). Its two independent clones produced **byte-identical** locks. The generalised lesson,
   already recorded in `CLAUDE.md` Lesson #12, is that a frozen identity must pin its **inputs**, not
   its **outputs**.

So this change is proposed and should be judged **only** on ordinary supply-chain hygiene for a
shipped CLI binary. The successor-protocol design (G7 — whether to commit the lock, vendor, or embed
the resolved lock in the receipt at capture time) is PROGRAM's call and is deliberately not
pre-empted here.

## The measured problem this does fix

### Resolution is stable within a moment, but drifts across time

Two fresh worktrees at commit `3a13f486`, one host, cargo 1.97.1:

| clone | binary sha256 | independently-resolved `Cargo.lock` sha256 |
|---|---|---|
| A | `8947ea9b155c10d3…` | `13e71e9bcdb2f043…` |
| B | `8947ea9b155c10d3…` | `13e71e9bcdb2f043…` |

Same-moment resolution is stable — G6 observed this too. But the lock resolved here differs from the
one G6 resolved hours earlier by exactly one transitive dependency:

```
962c962
< version = "0.103.13"        rustls-webpki
> version = "0.103.14"
964c964
< checksum = 61c429a8649f110dddef65e2a5ad240f747e85f7758a6bccc7e5777bd33f756e
> checksum = 0527518605e68109d875e248ea259b6758801cf165e4b2c2733ae3b51f12535a
```

Both locks are **41115 bytes** — the version strings are the same length, so a size or line-count
check sees nothing. This is the same class of event that invalidated G6's frozen constant
(`futures-core`/`-task`/`-util` 0.3.34 publishing ~1h before its run): with 17 semver-range direct
deps over 175 packages, the graph moves under the repo continuously.

### The release matrix can ship legs built from different dependency graphs

`release.yml`'s `build` job is a **three-target matrix, each from a fresh checkout**, and today each
leg re-resolves against live crates.io. A publish landing mid-run yields one release whose three
binaries were built from different graphs, with nothing in the record showing it. That is a
supply-chain defect independent of any research gate, and it is what `--locked` plus a committed lock
prevents.

## What this change does NOT deliver

**It does not deliver bit-identical binaries, and no one should read it as doing so.** Both CI and
release install the toolchain via `dtolnay/rust-toolchain@stable` — a floating channel — and there is
no `rust-toolchain.toml` in the tree. Ranked requirements for bit-identity, with current state:

| requirement | status | note |
|---|---|---|
| `Cargo.lock` committed + `--locked` | **this change** | pins the dependency graph across time and matrix legs |
| rustc/cargo version pinned | **NOT pinned** (`@stable`, no `rust-toolchain.toml`) | rustc changes codegen and embedded metadata between releases |
| build image / glibc / linker pinned | **NOT pinned** — the x86_64 leg builds natively on floating `ubuntu-latest` | only arm64/Windows go through `cross`'s pinned image |
| absolute path normalisation | **not handled** (no `.cargo/config.toml`, no `--remap-path-prefix`) | dependency `panic!`/`unwrap!` sites bake `$CARGO_HOME` paths in, so machines with different `$HOME` differ |

The last three are **deliberately not changed here** — pinning the repo's toolchain and build image
affects every lane and every release, and belongs to whoever owns that contract. The repo already has
a precedent for the stronger approach: `reproducibility/Dockerfile` pins exact apt package versions
for benchmark reproducibility. Extending that to the cubrim build is the real route to bit-identity.

`[profile.release]` sets only `opt-level = 3`; there is no `build.rs`, and nothing embeds build time,
git state or hostname — so those common sources are already clean.

## The change

1. `.gitignore` — keep the blanket `Cargo.lock` rule, add `!code/cubrim-rs/Cargo.lock`. The blanket
   rule is unanchored, so deleting it would also un-ignore `code/addressor/Cargo.lock` and
   `code/cubrim-rs/fuzz/Cargo.lock` (separate workspace roots, both `publish = false`). Verified after
   the edit: both remain ignored; only the CLI's lock is tracked. The repo already uses this negation
   idiom for `*.bin`.
2. Commit `code/cubrim-rs/Cargo.lock` — 175 packages, 41115 bytes, freshly generated and in sync
   (`cargo metadata --locked` succeeds).
3. `--locked` on exactly the four invocations that resolve dependencies: `ci.yml` clippy and
   `scheme_roundtrip`; `release.yml` `cargo build` and `cross build`. **Not** on `cargo fmt --check`
   (never resolves) or the `reproducibility` job (pure Python).
4. `.github/dependabot.yml` — add the `cargo` ecosystem for `/code/cubrim-rs`, grouped, matching the
   style introduced for github-actions in #105. This is a **required companion**: today the *absence*
   of a lock is the only thing keeping dependencies fresh, so committing one without an update path
   would freeze 175 packages with no automated security patching.

Untouched because they never read the lock: `release-lineage-guard.yml`,
`.github/scripts/check-release-lineage.sh` (reads only the `[package] version` string), and
`package-release.sh`.

## Costs, stated plainly

- **`Cargo.lock` is a conflict magnet** in a repo with many concurrent lanes. It diffs on any
  dependency-graph change, not just `Cargo.toml` edits.
- **`--locked` converts silent self-healing into hard CI failure** for anyone who bumps a dep and
  forgets to regenerate and commit the lock. That is the intended trade — visible failure over silent
  drift — but it is a real cost to contributors.
- `cross build --locked` on the arm64/Windows legs could not be exercised here; `cross` forwards
  cargo flags, but that is documentation, not a run. The first release build after this lands is the
  test.

## Voids

- Whether `cubrim` is published to crates.io could not be confirmed (registry egress blocked from
  this host). Every in-repo signal — no `cargo publish` step, binary-only release docs, PolyForm
  Noncommercial licensing — says it ships as an application, for which committing the lock is
  idiomatic. `addressor` and `fuzz` set `publish = false` and are untouched.
- This does not establish that pinning the toolchain *would* reconcile `8947ea9b…` with the G2
  attribution's `d4b9fc85…`. It establishes only that the lock is not the cause and that bit-identity
  holds when toolchain and environment are constant. The G2 build's toolchain version was never
  recorded, so that hypothesis is untested and stated as a void rather than assumed.

---

## Mutation verification of the `--locked` gate (2026-08-11, post-merge)

The PR that landed this change reported five green CI checks and called that "proof the committed
lock is in sync". **Green checks are not proof.** A gate that never fails proves nothing, so the gate
was tested by mutation: break the thing it is supposed to catch, and confirm it catches it.

Disposable worktree at `origin/main` `a742db7`, cargo 1.97.1. Each arm restored before the next.

| arm | mutation | `cargo metadata --locked` | without `--locked` |
|---|---|---|---|
| 1 control | none | **SUCCEEDS** | — |
| 2 | added `itoa = "1"` to `Cargo.toml`, lock untouched | **FAILS** | **SUCCEEDS** |
| 3 | edited `Cargo.lock`: `rustls-webpki` 0.103.14 → 0.103.13, checksum left stale | **FAILS** — `error: checksum for rustls-webpki v0.103.13 changed between lock files` | — |
| 1 again | restored | **SUCCEEDS** | — |

Arm 2 is the discriminating one. The same desynced tree that **fails** under `--locked` **succeeds**
without it, silently re-resolving — which is precisely what every CI job in this repo did before this
change. That is the behaviour difference the flag buys, demonstrated rather than asserted.

Arm 3 shows the lock is also integrity-checked, not merely present: a tampered pin is rejected on the
recorded checksum, so committing the lock gives a real supply-chain assertion and not just a file.

Two limits, stated rather than glossed:

- These arms exercise `cargo metadata --locked`, which performs the same resolution check as
  `cargo build/clippy/test --locked`. They do **not** exercise the `cross build --locked` legs
  (arm64, Windows), which remain untested here as noted above.
- This verifies the gate rejects a desynced or tampered lock. It says nothing about bit-identity of
  the resulting binary, which this change explicitly does not deliver.
