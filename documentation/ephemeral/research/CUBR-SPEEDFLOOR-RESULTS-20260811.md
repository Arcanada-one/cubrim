# CUBR-SPEEDFLOOR-20260811 — results: the CM2 decode path cannot reach the field

**Verdict on the CM2 rail: the field is unreachable by optimisation.** On `dickens/max`, driving
*every named CM2 component to zero cost* yields **0.53–0.63 MiB/s** — still **41–49× short of ninth
place**. Even matching bzip2, the slowest competitor measured, would need **~25× beyond** the
impossible whole-path bound.

Preregistration `CUBR-SPEEDFLOOR-20260811.md` merged to `main` as `da16b05` at **17:05:13Z**;
measurement began **17:05:27Z**. Prediction preceded measurement.

**One of three predictions is refuted, on the geocm cell.** Reported as stated, below.

## Predictions, scored

| | prediction | threshold | dickens (CM2) | x-ray (geocm) |
|---|---|---|---|---|
| **P1** | measured within 2× of the attribution-implied rate | — | 0.0454 in [0.0340, 0.1361] → **HOLDS** | 0.901× → **HOLDS** |
| **P2** | cubrim ≥100× slower than `xz -9`, same host/pin | ≥100× | 1261× → **HOLDS** | n/a |
| **P3** | perfect-CM2 best case < 25.69 MiB/s | ≥25.69 refutes | 0.634 → **HOLDS** | 65.259 → **REFUTED** |

### P3 refuted on x-ray — reported plainly, and it does not rescue the CM2 rail

x-ray's best case (1.1747 × 55.556 = 65.26 MiB/s) clears ninth place, so **P3 as literally stated
("every measured cell") is refuted.** Two things about that cell were preregistered and still hold:
its 55.556× bound comes from the G3 cell the attribution itself marked **instrument-perturbed**
(1.20161, cycle samples suppressed, "symbol shares only"), and the prereg carried it "only as an
upper marker, never as a decision number". More substantively, x-ray's 98.20% is the **`geocm`
replay path — not CM2 at all**. So the refutation says an image on the geocm rail has headroom; it
says nothing about the CM2 rail, which is what the lane was asking about. The prediction was written
too broadly, and that is a fault in the prediction, not a finding about CM2.

## Per-file measurement (same host, pin 0-15, median of 3, ratio beside speed)

Both sides of the trade are shown, per the mandate: cubrim is **densest on both files** and slowest
on both by orders of magnitude.

### dickens — 10,192,446 B

| tool | setting | ratio | decode s | MiB/s | RSS KiB | × faster than cubrim |
|---|---|---:|---:|---:|---:|---:|
| lz4 | -12 | 0.430208 | 0.020 | 486.01 | 7,424 | 10715× |
| zstd | -19 | 0.279646 | 0.030 | 324.01 | 11,776 | 7143× |
| brotli | -q11 | 0.277439 | 0.050 | 194.41 | 13,056 | 4286× |
| gzip | -9 | 0.377910 | 0.070 | 138.86 | 3,584 | 3061× |
| xz | -9 | 0.277716 | 0.170 | 57.18 | 12,288 | 1261× |
| bzip2 | -9 | 0.274666 | 0.740 | 13.14 | 4,864 | 290× |
| **cubrim** | **max** | **0.207263** | **214.300** | **0.045** | **11,056,640** | **1×** |

cubrim's ratio is **24.5% better than the best competitor** (0.2073 vs bzip2's 0.2747) and its decode
is **290–10,715× slower**. Its decode RSS is **10.5 GiB against 3.5–12.7 MiB** for every competitor —
three orders of magnitude, and a product property in its own right.

### x-ray — 8,474,240 B

| tool | setting | ratio | decode s | MiB/s | × faster than cubrim |
|---|---|---:|---:|---:|---:|
| zstd | -19 | 0.608403 | 0.040 | 202.04 | 172× |
| lz4 | -12 | 0.847311 | 0.040 | 202.04 | 172× |
| gzip | -9 | 0.712478 | 0.170 | 47.54 | 40× |
| brotli | -q11 | 0.552587 | 0.220 | 36.73 | 31× |
| xz | -9 | 0.529825 | 0.550 | 14.69 | 13× |
| bzip2 | -9 | 0.478050 | 1.430 | 5.65 | 5× |
| **cubrim** | **max** | **0.429187** | **6.880** | **1.175** | **1×** |

## The headline number is a maximum, not a typical value

The mandate quotes cubrim at **1.71 MiB/s** (`d_max`). Measured here: **1.1747 MiB/s on x-ray** and
**0.0454 MiB/s on dickens** — the text file is **26× slower than the headline**. `d_max` is a maximum
over files, and cubrim's maximum sits on the geocm/image rail. "Last by 15×" describes cubrim's best
case; on text the same-host gap to the *slowest* competitor measured is **290×**, and to lz4 **10,715×**.

## Timing honesty: the interleaved same-window pass

This box is shared with ~40 other agent sessions and load1 moved between **9.9 and 31.2** during the
run. Competitors were first measured near load 10–16 and cubrim near load 24, which makes a
cross-window ratio indefensible. The preregistration committed in advance to treating wall-clock as
contaminated under load and to reporting **tool-to-tool ratios measured in the same window**. So a
second pass decoded **all seven tools back-to-back inside each of 3 rounds**:

| tool | round 1 | round 2 | round 3 | median |
|---|---:|---:|---:|---:|
| lz4 | 3562× | 6560× | 9178× | **6560×** |
| zstd | 2003× | 3197× | 4064× | **3197×** |
| brotli | 1636× | 3187× | 3184× | **3184×** |
| gzip | 1307× | 2464× | 2281× | **2281×** |
| xz | 610× | 1256× | 1316× | **1256×** |
| bzip2 | 110× | 349× | 418× | **349×** |

cubrim's median across rounds is **257.7 s = 0.0377 MiB/s**. The per-round spread (110× to 418× for
bzip2) is itself the evidence that single-window numbers on this host must not be trusted; the
**median of same-round ratios** is the reportable quantity, and every conclusion below uses it.

## The ceiling, against measurement

| basis | cubrim MiB/s | × 13.986 bound | short of ppmd (25.69) |
|---|---:|---:|---:|
| main pass (median of 3) | 0.0454 | **0.634** | **40.5×** |
| interleaved (median of rounds) | 0.0377 | **0.528** | **48.7×** |

The 13.986× is the attribution's own "impossible whole-path bound, not a promised speedup" — it
assumes `predict_bit`, `Ctr::upd`, `update_bit`, `Match::end`, `start_byte`, `end_byte`, `Ctr::new`
and the `cm2_decode` shell **all cost nothing**. Under that impossible assumption cubrim still does
not reach ninth place, and **matching bzip2 alone would require ~25× beyond it**.

This is the answer the lane was opened for: **no optimisation of the CM2 decode path — however
complete — puts cubrim in the field on text.** Speed on that rail is not an engineering-effort
problem; it is a structural property of running an adaptive context-mixing model per bit. The only
live directions are not running CM2 at that operating point, or shipping a different rail — which is
what NEW-24 already targets. That lane's premise is now established rather than assumed.

## Binary equivalence check (and an independent reproduction of NEW-24 G6's blocker)

The binary built here from the attribution's frozen commit `3a13f486` has sha256 `8947ea9b…` against
the attribution's recorded `d4b9fc85…` — **same source, different bytes**. That independently
reproduces the failure that terminated **NEW-24 G6** in prebuild: `code/cubrim-rs/Cargo.lock` is
gitignored and dependencies are unpinned semver ranges, so two builds of one commit are not
bit-identical. It is a live blocker on that lane and, as of this writing, no branch or PR implements
the fix G6 itself prescribes (commit the lock and build `--locked`, or vendor).

**Behaviour, however, is identical**, so the ceilings legitimately apply to this binary:

| check | landed record | measured here |
|---|---|---|
| x-ray archive bytes | 3,637,036 | **3,637,036** |
| x-ray ratio | 0.4291873 | **0.429187** |
| x-ray decode RSS | 88 MiB | **88.4 MiB** |

Byte-exact archive output and matching residency from a differently-built binary: the sha difference
is a toolchain artefact, not a behavioural one.

## Scope and voids

Two cells, `dickens/max` and `x-ray/max`, per-file only — **no corpus aggregate is computed
anywhere**, by construction in `analyze.py`. No encoder, wire format, preset, counter or `decode()`
change; no candidate built, no lever selected (selection is NEW-24's). No database write, no
hypothesis row, no API, site or social action.

Stated as voids, not findings:
- **Absolute MiB/s here is contaminated** by a shared host at load 9.9–31.2. The measured/implied
  ratio was 0.667× on dickens and 0.901× on x-ray. Same-round tool ratios are the defensible
  quantity; a quiet pinned stand would be required for decision-grade absolute throughput.
- **Competitor `d_max` figures from `world_benchmark_timing_aggregate` were not used** for any
  comparison — everything above is same-host. The ppmd 25.69 MiB/s reference is carried only as the
  field's ninth-place marker, and it is a *cross-meta* number; the conclusion survives a wide margin
  of error in it (41–49× is not a rounding question).
- **`xml/max` and `dickens/web` were not measured**, though both have landed ceilings. Only `xml/max`
  has a stated combined bound (10.707×); `dickens/web`'s components sum to 99.22% with no combined
  row published, which would imply a very large bound — that is unverified and deliberately not used.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-SPEEDFLOOR-RESULTS-20260811
python3 analyze.py      # every table above, from results.tsv / interleaved.tsv / gates.tsv
```

`analyze.py` refuses to print any number if a gate is VOID or if a timing row lacks a passing gate.
63 gated decode observations, 0 VOID. Memory cap, pin, corpus hashes and toolchain in
`provenance.txt`.

---

## Correction — 2026-08-11: the lock is NOT why the binaries differed

The section above attributed the `8947ea9b…` vs `d4b9fc85…` difference to `Cargo.lock` being
gitignored with unpinned semver deps, "so two builds of one commit are not bit-identical". **A
direct experiment refutes that causal claim**, and it is corrected here rather than left standing.

Two independent worktrees were created at the same commit `3a13f486` on one host and built with one
toolchain (cargo 1.97.1):

| clone | binary sha256 | Cargo.lock sha256 |
|---|---|---|
| A | `8947ea9b155c10d3…` | `13e71e9bcdb2f043…` |
| B | `8947ea9b155c10d3…` | `13e71e9bcdb2f043…` |

**Bit-identical binaries, and byte-identical independently-resolved locks.** Two clones resolving
the same dependency graph at the same moment is exactly what NEW-24 G6 also observed — its own two
locks were byte-identical (`0d17c1fc…`, 41115 bytes). So same-moment resolution was never the
failing property, and committing the lock alone would not have made G6 pass.

What actually differs across the two recorded builds is the **toolchain and build environment**, not
the dependency graph. Bit-identity is achievable — it was just demonstrated — but it requires
holding rustc/cargo version, and the paths and system libraries the build sees, constant.

### The lock still matters, for a different reason — cross-time drift, now measured

Resolution is stable within a moment but **not across time**. G6's lock and the lock resolved here
hours later differ by exactly one transitive dependency:

```
962c962
< version = "0.103.13"        rustls-webpki
> version = "0.103.14"
964c964
< checksum = 61c429a8649f110dddef65e2a5ad240f747e85f7758a6bccc7e5777bd33f756e
> checksum = 0527518605e68109d875e248ea259b6758801cf165e4b2c2733ae3b51f12535a
```

Both files are 41115 bytes — the version strings are the same length, so a size check would have
missed it entirely. A patch release landed on crates.io between the two runs and every build after
it silently changed dependency graph. That is the real, measured hazard a committed lock removes,
and it also means the release matrix (three `cargo`/`cross` build jobs from fresh checkouts) can
diverge mid-run today.

So: commit the lock — the justification is cross-time and cross-job drift, demonstrated above, not
the same-moment binary difference this report originally blamed it for. And do not expect the lock
by itself to deliver bit-identity; see `CUBR-BUILD-DETERMINISM-20260811.md`.

### Second correction: G6 is terminal, not blocked, and already used `--locked`

This report called the lock issue "a live blocker on that lane" with "no branch or PR implementing
the fix G6 itself prescribes". That is wrong on three counts, each verified against `origin/main`:

- **G6's protocol already built with `--locked`** (`datarim/plans/NEW-24-current-profile-g6-plan.md`
  lines 190, 231-232), so it was never missing that.
- **G6 cannot be retried** — *"Its prebuild allowance is spent"* (G6 results line 103); any further
  attempt is a new protocol with a new preregistration. Nothing is waiting to be unblocked.
- **G6 did not fail on the gitignored lock.** It failed comparing a freshly-resolved lock against a
  `LOCK_SHA` frozen 2026-08-09T16:57:54Z and invalidated by crates published in between —
  *"unreproducible by construction"* (G6 results line 32). Its two clones' locks were byte-identical.
  The lesson, already in `CLAUDE.md` Lesson #12, is that a frozen identity must pin its **inputs**,
  not its **outputs**.

Committing the lock is therefore worth doing on supply-chain merits alone, and is **not** a NEW-24
fix. The successor-protocol design is PROGRAM's.

---

## Amendment 2026-08-11 — the rank language in this report is cross-meta, not same-host

Every "ninth place" / "eighth place" phrase above is measured against ppmd **25.69 MiB/s** and bzip2
**52.71**, taken from `world_benchmark_timing_aggregate`. Those markers were later measured on this
host and **they do not transfer** (`CUBR-SAMEHOST-FIELD-RESULTS-20260811.md`): same-host on x-ray,
interleaved and gated, ppmd decodes at **1.84 MiB/s** (14× lower) and bzip2 at **8.73** (6× lower).

Cause: `d_max` is a **maximum over files**, so 25.69 is ppmd's *best* file while x-ray is near its
worst; host load compounds it. cubrim's own discrepancy is only 2.0× precisely because its `d_max`
sits on x-ray — the same leaderboard column means "this file" for cubrim and "some other file" for
every competitor, which is what made the comparison feel valid while being invalid.

**No figure in this report changes, and its conclusions hold — conservatively.** The same-host margin
is *larger*, not smaller (the geocm floor clears same-host ppmd by 15.3× rather than 1.09×). But read
every rank phrase above as **"against the cross-meta leaderboard"**, never as a same-host claim.
Stated same-host, a perfected geocm rail at the 28.1 MiB/s floor ranks **5th of the 8 tools measured
on x-ray** — behind lz4/zstd/gzip/brotli, ahead of xz/bzip2/current cubrim.
