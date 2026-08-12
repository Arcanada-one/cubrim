# CUBR-0087 programme execution plan

Date: 2026-08-01
Source contract: `/home/dev/LUNA-HANDOVER.md` and its required handover chain.

## Outcome — EXECUTED (verified 2026-08-12)

Retained as the record of how the CUBR-0087 pass was scoped and bounded. Disposition of the
work sequence:

- Steps 1-3 (API verdict classification and source-row reconciliation) landed on
  `cubrim-api` `origin/main`; see `../reviews/CUBR-0087-api-gap-consilium.md` § Outcome.
- The CI runner blocker raised during step 3 landed as decided; see
  `../reviews/CUBR-0087-ciblock-consilium.md` § Outcome.
- Steps 6-7 (PR salvage, campaign polling) closed: the handover's open PRs `#10`
  (CUBR-0075 hostile-input hardening) and `#12` (CUBR-0074 rar thread determinism) are both
  merged, and CUBR-0075 has since grown a streaming decode API (PR `#145`).
- The CLI-facing half of this lane — replacing 2 MB slice figures in `--preset` help with
  full-corpus measurements — merged as PR `#35`, and remains current on `origin/main`
  (`code/cubrim-rs/src/cli.rs`: balanced `+0.47%` output with the per-class speedup bands,
  `lowmem-decode` peak decode RSS 12,561 MiB -> 221 MiB, 56.8x).

The boundaries and non-go criteria below were honoured; they are recorded because they are
reusable, not because anything remains open in them.

## Boundaries

- DB source: `arcanada_cubrim`; no measurement or hypothesis prose writes in this pass.
- API implementation: isolated worktree from `cubrim-api` `origin/main`.
- Site implementation: isolated worktree from `cubrim-site` `origin/main`; never edit the dirty shared site checkout.
- Timing campaign: read-only polling of `dev-ai:/root/phaseC/timing`; no restart, pin change, or sample change.
- Workspace safeguards: verify current `origin/main` before changing anything; preserve dirty shared worktrees and existing untracked files.

## Work sequence

1. Reconcile current DB, API, site origin, production routes, PRs, and campaign state. Record exact evidence and distinguish cards from source rows.
2. Implement API verdict classification and source-row reconciliation in `src/build.ts`/`src/types.ts`, with TDD fixtures in `test/build.test.ts` and validation coverage in `test/validate.ts`.
3. Run API typecheck, unit/integration tests, and the deployment test suite. Review the diff for raw-verdict preservation, override precedence, deterministic ordering, and no secrets.
4. Verify the fresh site `origin/main` hardening tests and trace `/build-info.php` to the CI-controlled generation/deployment source. Fix only a source-controlled defect, with a regression test, and use push -> main -> CI for any release.
5. Verify the tracked session-start secret-scan hook and backlog/allocator checks against their authoritative `origin/main`/Datarim sources. Do not modify already-landed safeguards without a fresh failing proof.
6. Re-prove PR #10 and #12 state, run only scoped read-only or local tests on the decoder salvage, and do not merge unrelated codec work from a dirty/shared worktree.
7. Poll the timing campaign again, then perform production route/API readback. Report separately what is merged/deployed/proven, what is prepared only, and which hard gates remain.

## Verification commands

- API: `pnpm test`, `pnpm typecheck`, `pnpm build` in the isolated API worktree.
- Site: fresh-origin tests, PHP lint/static raw-path tests, and Playwright/sitemap sweep where the local environment supports them.
- Production: `curl` every changed Cubrim route and API endpoint; confirm `/benchmark` remains a legitimate 404 and `/en/evolution/benchmark` is the canonical route. Use the handover’s full-route requirement before claiming deployment.
- Campaign: inspect process, journal counts, and balanced completion markers only; never mutate the remote run.

## Non-go criteria

- Any unrepresented source row or unknown verdict token without an explicit classification.
- Any site release without merged SHA, CI success, and route/browser proof.
- Any production claim based only on a local branch or a successful dispatch.
- Any timing conclusion before the balanced journal exists and grows through its terminal marker.
