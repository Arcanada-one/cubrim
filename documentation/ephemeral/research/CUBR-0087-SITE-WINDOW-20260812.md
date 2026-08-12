# The site window was frozen shut, and its CI gate cannot run at all

Date: 2026-08-12. Task: CUBR-0087 (Phase C). Repo touched: `Arcanada-one/cubrim-site`.

Third and last stage of the same content gap. The measurement existed
(`world_benchmark_timing_file`, imported 2026-08-04); the API was made to serve it
(`CUBR-0087-SPEED-CONTRACT-APPLIED-20260812.md`); this is the window.

## The site had been serving a frozen cache for two days

`cubrim.com/en/evolution/benchmark` printed **"Speed not measured on this
corpus"** on all three preset cards, hours after `/api/operating-points` began
returning measured throughput.

Cause: `cubrim-api` #29 bumped that endpoint to `schema_version: 2` on
**2026-08-10**. The site's validator pinned `!== 1` and rejected every response
from that moment. The rejection is **silent by design** — `cubrim_api_fetch`
falls back to the last-good cache rather than erroring, which is the right
behaviour for a transient API fault and the wrong one for a permanent schema
change. Nothing logged, nothing alerted, and the page kept rendering pre-v2 data.

Diagnosis was mechanical rather than by inspection: the validator was ported to
Python and run against the live payload. Of every condition it checks, exactly
one failed.

```
VALIDATOR FAILURES: 1
  - schema_version != 1 (is 2)
```

v2 is a superset — every field the page reads is present and unchanged — so the
pin was widened to `[1, 2]`, and **only for this endpoint**: `/api/web-benchmark`
and its hypotheses sibling still return v1 (verified live) and their pins are
correct as they stand.

## The copy was premised on the missing measurement

Two strings had been written when the speed did not exist:

- `op_preset_balanced` — *"measured, not recommended"*
- `op_summary_balanced` — *"…it costs ratio and saves almost no memory, and the
  speed it is named for has never been measured on this corpus."*

The verdict's own stated grounds were that the measurements did not support a
trade. The measurements now exist, and they do not support that verdict either
(FINDINGS **F22**): on 10 of 24 files `balanced` writes byte-identical output to
`max`, and on the largest of them — `enwik8` — it is still **2.48× faster**, so
there it is strictly the better setting. The whole +0.47% comes from the other
14 files, which pay +0.06%…+3.9% for 1.2–3.1×. Both locales now carry that, and
the verdict reads **"depends on the input"**.

## A negative control caught a test of mine that proved nothing

The first regression test asserted "no unmeasured marker present" and **passed
against the deliberately reverted validator**. A rejected payload drops the whole
operating-points section, so `toHaveCount(0)` held on zero cards. The test would
have shipped green and guarded nothing.

It now pins card count *and* the rendered numbers (`0.023` / `0.038` / `0.040
MiB/s`). Both tests fail without the fix and pass with it — checked in both
directions rather than assumed.

## The gate that should have caught this cannot run

`.github/workflows/test.yml` is red on `main` since **2026-08-09**, and not for
any reason in the code. The job never starts:

> The job was not started because recent account payments have failed or your
> spending limit needs to be increased.

It is the only workflow in the repo on a **GitHub-hosted** runner — a choice its
own header documents and defends, on the reasoning that a self-hosted label which
later disappears would queue forever and leave "a dead gate that still shows a
green tick". The gate died anyway, by a route that reasoning did not cover.
`deploy.yml` is unaffected: it runs through the shared workflow on the
self-hosted `arcana-www` runner and has succeeded on every push throughout,
including the two `main` commits whose `test` runs failed.

Consequences worth stating plainly:

- Locally the suite is green — `main` **119/119**, this branch **120/121** with
  the single failure an `ERR_NETWORK_CHANGED` blip that passes 8/8 in isolation.
  So there is no code defect hiding behind the red gate.
- But **no PR in this repository has been mechanically tested since 2026-08-09**,
  and a red tick that is red for billing trains readers to ignore it — the exact
  habit the workflow was created to break.
- Fixing it is an account action (billing / spending limit), not a code change.

### The self-hosted alternative, now measured rather than assumed

An earlier revision of this note left the runner question open ("was not verified
here"). It is cheap to answer, so it is answered:

| runner (label) | host | PHP | notes |
|---|---|---|---|
| `arcana-www-arcanada` (`arcana-www`, `sites`) | arcana-www | **8.4.19** | the only runner carrying `sites` |
| `arcana-kb-general` (`ci-general`) | arcana-kb | **none** | passwordless sudo available |
| — | dev-ai | n/a | **hosts no Actions runner at all** |

Three conclusions follow, and they argue *against* a runner move rather than for
one:

1. **dev-ai is not in the runner fleet.** The `arcana-ai` label on
   `arcana-ci-general` had raised the worry that CI work could land on the
   measurement stand and break quiet-host discipline. It cannot: dev-ai carries
   no runner installation. That concern is closed.
2. **`arcana-www` satisfies the PHP assertion but is the wrong slot.** It is the
   only runner labelled `sites`, and it is what `deploy.yml` waits on — this
   lane's own deploy queued roughly fifteen minutes behind it. Adding a
   four-minute browser suite to that single slot serialises testing against
   deployment, which is exactly the failure the `cubrim-api` CIBLOCK decision
   moved a job *away* from.
3. **`ci-general` is the right slot but lacks PHP.** It could be installed —
   passwordless sudo is available — but that mutates a shared CI host used by
   other repositories, and it cuts against this workflow's own supply-chain
   reasoning for taking PHP from the runner image rather than a setup action.

So the runner move is *feasible* and *not obviously desirable*. Restoring billing
restores the design the workflow's author chose and documented. That remains a
fleet/account decision; what has changed is that it can now be taken on evidence
instead of on an open question.

## Verification

`php -l` clean on all four PHP files. Both new tests checked fail-without /
pass-with. Merged as `4053bba`; the deploy runs through `push → main → CI` on the
self-hosted runner, never manual rsync.
