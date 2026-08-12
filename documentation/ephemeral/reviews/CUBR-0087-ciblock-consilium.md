# CUBR-0087 CIBLOCK consilium

Date: 2026-08-01

## Outcome — IMPLEMENTED (verified 2026-08-12 against `cubrim-api` `origin/main` @ `c2b658d`)

`.github/workflows/ci.yml`, job `lint-and-test`, carries exactly the decided change:

```yaml
runs-on: [self-hosted, Linux, X64, ci-general]
timeout-minutes: 30
```

The stable `ci-general` label was used rather than a machine name, per the DevOps position.
The `infra-watchdog` run was left untouched, per the decision.

## Question

Should `cubrim-api` move its `lint-and-test` job off the single `arcana-devs`
runner and add a job timeout, and should the active `infra-watchdog` run be
interrupted?

## Context and blast radius

PR #26's security audit passed, while `lint-and-test` remained queued because
`arcana-devs` was busy with `infra-watchdog` run 30695073446. The API job only
checks out the repository, installs pnpm dependencies, runs typecheck/tests/
build, and creates a push-only release bundle. It has no dev-host mount,
service, credential, or deployment dependency. The organization has an idle
`ci-general` runner with the required Linux/X64 labels.

Blast radius: 2 (one repository workflow plus runner scheduling).

## Panel

- Architect: the workflow is portable; `ci-general` is the correct host.
- SRE: a bounded job is safer than holding a single-slot runner indefinitely.
- DevOps: use the stable `ci-general` label, not the runner's machine name.
- Security: the change does not widen permissions or move production secrets.
- Strategist: make the smallest reversible change and avoid another programme's
  active evidence run.

## Decision

Change `lint-and-test.runs-on` to `[self-hosted, Linux, X64, ci-general]` and
set `timeout-minutes: 30`. Thirty minutes is substantially above the observed
API CI duration (under six minutes) while converting a genuine hang into a
visible failure.

Do not cancel, rerun, signal, or modify `infra-watchdog` run 30695073446. Record
its anomalous duration and current scan position for that programme in a
visible issue; do not change its scan semantics.

The existing queued run is not manually rerun. A normal workflow-triggering
commit is sufficient for the durable fix to receive CI on the correct runner.

## Failure modes and gates

| Risk | Detection | Mitigation |
|---|---|---|
| `ci-general` lacks a required tool | CI setup/install step fails | Keep setup-node/pnpm provisioning; revert only with a specific dependency proof |
| CI hangs | 30-minute timeout | Failure becomes visible instead of blocking `arcana-devs` |
| old queued run consumes `arcana-devs` later | Runner queue remains observable | Do not cancel it; it is a separate historical run |
| watchdog slowdown is lost | Issue includes run, step, elapsed time, and nmap scope | Infra owner investigates without agent intervention |

## Conditions

This decision assumes the current workflow remains a build/test workflow and
does not acquire a dev-host-only dependency. Production deployment remains
separately gated by merge, deployment CI, and post-deploy readback.
