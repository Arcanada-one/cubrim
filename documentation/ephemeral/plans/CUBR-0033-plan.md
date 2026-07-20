---
task_id: CUBR-0033
artifact: plan
schema_version: 1
captured_at: 2026-06-21
captured_by: /dr-plan
agent: planner
complexity: L4
type: infra
prd_status: waived
parent_init_task: ../../../../datarim/tasks/CUBR-0033-init-task.md
task_description: ../../../../datarim/tasks/CUBR-0033-task-description.md
design: ../research/CUBR-0033-design.md
baseline_scheme: BwtEntropy
baseline_aggregate: 0.504412
corpus_total_bytes: 51456
code_sha_at_plan: e476294
win_target_aggregate: 0.30
host: AX41-HEL1
orchestrator_brain: personal-claude-sub
workers: free-tier
---

# CUBR-0033 — Autonomous Multi-Vendor Compression-Research Cluster — Implementation Plan

> **L4 infra. PRD waived** (the founding-brief + init-task + the consilium-gated
> design `CUBR-0033-design.md` carry the requirements; this is a cluster/loop build,
> not a product needing a separate PRD). **This plan operationalises design §§A–H.**
> It does **not** provision the host, build images, push, deploy, or publish — that is
> `/dr-do` (and the host-provisioning + public-promotion sub-steps are operator-gated).
>
> **Scope reminder (init-task Boundary note):** the deliverable is the **cluster +
> loop + streaming**. The winning algorithm is the loop's *emergent output over time*,
> NOT a deliverable of this task.
>
> **Binding decisions already made — do NOT re-litigate** (init-task append-log,
> design-round-1 + plan-round-1, decided-by operator):
> - HOST = an underloaded **AX41 in HEL1** (bare relative to arcana-dev → full
>   toolchain bootstrap phase required). Host provisioning is operator-gated do-stage.
> - ORCHESTRATOR BRAIN = operator's **personal Claude subscription (Max)**; workers
>   stay free-tier. Safety lives in the **mechanical rail + deterministic arbiter**
>   (local shell), never in the orchestrator's brain.
> - WORKER A = `qwen/qwen3-coder:free` (1M ctx). WORKER B = do-stage tool-calling
>   bake-off across distinct-weight free OpenRouter code models; **DeepSeek-free** is
>   the named fallback pin. WORKER C / background = Groq llama.
> - AUTONOMY = auto-merge to `main` behind the AC-5 mechanical rail ONLY; public
>   cubrim.com promotion is an **operator-gated batch**; the git-tracked leaderboard
>   write is autonomous. These floor constraints are non-negotiable.

---

## Overview

### Problem
Cubrim's compression research has been a sequence of hand-driven CUBR cycles
(0023→0032). The current `main` best is **BWT aggregate 0.504412** (CUBR-0028) on the
frozen 7-file corpus (`corpus_total = 51456 B`), ~1.7× *worse* than gzip/xz (~0.30).
Each manual cycle costs operator attention. The goal of CUBR-0033 is to **industrialise
the cycle**: a self-running cluster that runs the same consilium → arbiter → implement
→ gate → merge discipline perpetually on free-tier brains, until the aggregate beats
the standard archivers, then defends.

### Goal
Stand up **1 orchestrator + ≥2 free-model workers** (AC-1/AC-3) in Docker on a clean
dedicated AX41 (AC-2), driving an infinite loop (AC-7) whose only path to `main` is the
**deterministic AC-5 merge rail** (AC-5), whose results stream to a git-tracked
leaderboard (AC-6), with a kill switch + audit trail (AC-8) and a measured win
condition (AC-9). Every iteration is a self-contained CUBR research cycle gated by the
existing **Gotcha #1–#7** discipline.

### Non-goals
- The winning algorithm itself (loop output over time — out of scope).
- Migrating the AngryRobot trader (it stays on Трейдер, untouched — the dedicated AX41
  removes the cross-space risk structurally).
- Paid model tiers for the workers (free-tier only; the orchestrator runs on the
  operator's personal subscription auth, NOT pay-per-token billing).

### Headline reuse posture (do NOT reinvent)
The design's inventory section is the starting contract. Canonical sources:
- `Projects/Datarim/code/datarim/plugins/dr-fleet-evolution/{evolution-loop.sh,gates/run-all-gates.sh,lib/jsonl.sh}` — the generate→gate→select→branch loop skeleton + the **fail-closed ordered gate runner** + the JSONL run-log helpers. **Key divergence:** fleet-evolution *never auto-merges* (stops at PR); CUBR-0033 adds the conservative AC-5 merge step on top — everything upstream of merge is reused.
- `Projects/Datarim/code/datarim/plugins/dr-orchestrate/scripts/{content_consilium_fanout.sh,content_consilium_judge.sh}` + the `consilium` skill degradation rules (3-of-3 / 2-of-3 / abort) — the runtime consilium.
- `Projects/Cubrim/code/bench/run_bench.py` + the `CUBR-0028-bench.json` shape (`code_sha`, `*_aggregate`, `per_file[]` deltas, `verdict`) — feeds the leaderboard directly.
- PAX autonomous-loop STATE-doc-at-repo-root + watchdog + the **systemd `Environment=PATH` respawn lesson** (ecosystem memory).
- `documentation/runbooks/multi-vendor-agent-cluster.md` — headless multi-vendor cluster host conventions.

---

## Phasing & ordering (the binding sequence)

```
P1 bootstrap → P2 images/compose → P3 tool-calling verify (+ Worker-B bake-off)
   → P4 AC-5 rail (TESTED IN ISOLATION FIRST) → P5 consilium + deterministic arbiter
   → P6 leaderboard (+ operator-gated batch promotion) → P7 loop control
   → P8 kill switch + audit trail
```

Rationale for the order: nothing can run before the host has a toolchain (P1); no agent
exists before its image/compose (P2); **an unverified tool-calling model makes its
worker inert (AC-1 blocker)** so P3 must clear before any loop trusts a worker; the rail
is the single safety guarantee for full autonomy, so it is **built and proven against a
known-good and a known-bad candidate before any live loop can reach it** (P4); the
consilium+arbiter only feed candidates into a rail that already works (P5); the
leaderboard records what the rail decides (P6); the loop wraps it all (P7); kill/audit
close Law 4 / Law 5 (P8).

---

## Phase 1 — Toolchain bootstrap on the AX41 host (OPERATOR-GATED)

**AC mapping:** prerequisite for AC-1/AC-2. **Gating:** **OPERATOR-GATED** — host
provisioning is do-stage work the operator triggers; the agent does not SSH-provision a
bare host autonomously (it is a new dedicated machine, not an Arcanada-owned resource
the autonomy carve-out already covers).

### Deliverables
1. `infra/bootstrap-host.sh` (idempotent, re-runnable) installing on the AX41:
   - Docker engine + compose plugin (rootless or daemon per host policy).
   - The Cubrim Rust toolchain (`rustup` + `cargo`) — needed inside the image build,
     but also a host smoke-build to confirm the AX41 compiles `code/cubrim-rs`.
   - Python 3 + NumPy (entropy/size-model probes — the deterministic arbiter).
   - `jq`, `git`, `claude` (Claude Code CLI), `claude-code-router` (the per-agent model
     router). The orchestrator's Claude CLI authenticates to the **operator's personal
     subscription** (subscription auth via `claude auth login`, NOT an API key — mirrors
     the headless-VM login pattern from the cluster runbook; operator runs the
     interactive auth once over SSH).
2. `infra/.env.example` — the template enumerating every required key name
   (`OPENROUTER_API_KEY`, `GROQ_API_KEY`, …) with **no values**. The real
   `infra/.env` is **gitignored** (Security S1; Appendix A).
3. Secrets placement: a gitignored host env-file under the cluster work dir (or Vault if
   the host gets a Vault agent — fallback is the env-file). Never in compose, never
   committed.
4. A `documentation/how-to/provision-cubrim-cluster-host.md` runbook section: the exact operator
   steps (SSH target, `bootstrap-host.sh` invocation, the one interactive
   `claude auth login`, where to drop `infra/.env`).

### Reuse vs new
- **Reuse:** the cluster runbook's headless-login + vendor-CLI conventions.
- **New:** `bootstrap-host.sh`, `.env.example`, the provision how-to.

### Test strategy
- `bats` for `bootstrap-host.sh` argument/idempotency handling against a mock `apt`/`docker`/`rustup` (no real install in test).
- Do-stage live check: after provisioning, `cargo test` green on a host smoke-build of `code/cubrim-rs` (proves the AX41 can run the gate's CPU spike).

### Operator-gated steps
- The actual provisioning run on the AX41 (irreversible host mutation on a new machine).
- The interactive `claude auth login` to the personal subscription.

---

## Phase 2 — Worker images + docker-compose with cgroup limits

**AC mapping:** AC-1 (containers each a Claude Code CLI → free model), AC-2
(self-contained cgroup CPU/RAM resource limit).

### Deliverables
1. `infra/Dockerfile.cubrim-worker` — one image bundling Claude Code CLI,
   claude-code-router, the Rust toolchain (`cargo`), Python3+NumPy, `jq`, `git`. Per
   design §A.3 a single image serves all roles; containers differ only by `--env-file`.
2. `infra/docker-compose.yml`:
   - services `cubrim-orchestrator`, `cubrim-worker-a`, `cubrim-worker-b`,
     `cubrim-worker-c` — each with a **unique container label** (Law 5 identity).
   - `deploy.resources.limits` per container — workers ≤ 1.5 CPU / ≤ 4 GB,
     orchestrator ≤ 1 CPU / ≤ 2 GB (tune to the AX41 headroom; **reserve ≥ 4 cores
     free** per the ecosystem standing convention for shared dev iron).
   - per-worker `--env-file` (`infra/env/worker-a.env`, …) selecting model + key — the
     **only** difference between containers (design §A.3).
   - orchestrator mounts the git working tree **and** the read-only pinned gate copy
     (§P4 / design §D.4); workers do **not** mount the gate copy.
3. `infra/claude-code-router/config.<slot>.json` (or one config + per-slot env) — routes
   `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL` per worker:
   Worker A → OpenRouter `qwen/qwen3-coder:free`; Worker B → the bake-off winner (P3),
   DeepSeek-free fallback; Worker C → Groq `llama-*`.

### Reuse vs new
- **Reuse:** the cluster runbook's `ANTHROPIC_BASE_URL` + claude-code-router routing
  recipe (already documented; init-task append-log records the research result).
- **New:** the Dockerfile, compose, the per-slot router configs.

### Test strategy
- `docker compose config` lint (schema valid, limits present) in CI/bats.
- `bats` assertion that compose declares `deploy.resources.limits` on every service and
  that no `*.env` is referenced by a committed value (grep gate — Appendix A).
- Do-stage: `docker compose up` smoke — every container reaches healthy, `claude --version` resolves inside each.

### Operator-gated steps
- None beyond P1 (image build + `compose up` on the provisioned host is ordinary
  Arcanada-owned-resource infra ops once the host exists — but in practice it runs on
  the operator-provisioned host, so it follows P1's gate).

---

## Phase 3 — Free-model tool-calling verification + Worker-B bake-off (AC-1 BLOCKER)

**AC mapping:** AC-1 ("verified tool-calling on the chosen models"). **This is the
named blocker:** an unverified tool-calling model makes its worker inert.

### Deliverables
1. `infra/verify-tool-calling.sh <slot>` — a deterministic recipe that points a Claude
   Code CLI at the slot's free model and demands a **real end-to-end tool call**:
   - a Read of a fixture file, an Edit that changes a sentinel line, and a Bash call
     whose stdout the agent must echo back. The script asserts the fixture was actually
     mutated + the Bash sentinel returned — proving the model can call tools, not just
     describe them. Exit 0 = verified, non-zero = inert (Appendix A: never logs keys).
2. `infra/bakeoff-worker-b.sh` — runs `verify-tool-calling.sh` across the candidate
   distinct-weight free OpenRouter code models, scores each on (a) tool-call success,
   (b) a small fixed code-edit task completion, (c) latency; emits a ranked
   `infra/bakeoff-worker-b.result.json`. **Distinct weights from Worker A
   (qwen3-coder:free) is a hard requirement** (consilium voice independence).
   **DeepSeek-free is the pinned fallback** if the bake-off is inconclusive.
3. A short `documentation/how-to/verify-free-model-tool-calling.md`.

### Reuse vs new
- **Reuse:** none directly (tool-calling verification is new); the fixture/sentinel
  pattern mirrors the bats fixture conventions in the framework's gate tests.
- **New:** `verify-tool-calling.sh`, `bakeoff-worker-b.sh`, the how-to.

### Test strategy
- `bats` for `verify-tool-calling.sh` against a **mock** Claude CLI shim that simulates
  (a) a model that calls tools → exit 0, (b) a model that only narrates → non-zero.
  This proves the script's pass/fail logic without burning free-tier quota.
- Do-stage live: run the real recipe against qwen3-coder:free, the Worker-B candidates,
  and Groq llama; record results to `bakeoff-worker-b.result.json`.

### Operator-gated steps
- None — running verification probes against free models is ordinary autonomous I/O.

---

## Phase 4 — The AC-5 deterministic merge rail (TESTED IN ISOLATION FIRST)

**AC mapping:** AC-5 (absolute merge gate), AC-4 (implement+measure feeds it),
**partial AC-6** (the rail gates the leaderboard write on the round-trip proof).
**Verifies: V-AC-5, V-AC-4.**

### Deliverables (the rail = pinned out-of-tree shell, run by the orchestrator)
1. The five gate scripts, executed **fail-closed, ordered** (design §D.1). Mirror the
   `run-all-gates.sh` fail-closed pattern (unknown exit ≥2 = failure) but **ordered**
   (each gate is a prerequisite for the next), per `gates/run-all-gates.sh`:
   ```
   gate-corpus-hash.sh    # corpus manifest sha256 == frozen baseline (anti-tamper)
     └─ gate-cargo-test.sh   # `cargo test` green (round-trip + property tests)
        └─ gate-roundtrip.sh   # byte-exact decode(encode(f)) == f for EVERY corpus file
           └─ gate-ratio.sh   # aggregate strictly improves vs current main baseline
              └─ gate-competitive.sh   # min(new,T4)+scheme byte; NO per-file regression
                 └─ all green → MERGE (signed FF to main) + record GO to leaderboard
   any failure at any step → git branch -D the feature branch + record NO-GO + continue
   ```
2. `gate/run-merge-rail.sh` — the ordered driver that runs the five gates in sequence,
   short-circuits on first failure, and on all-green performs the **signed
   fast-forward merge to `main`** (`merge_main` under the autonomy resolver — NOT
   history deletion). On any failure: `git branch -D feat/cubr-0033-iter-<RUN-ID>`,
   write NO-GO to the leaderboard, return non-zero. Emits a run-log line for every gate
   result (Law 5).
3. **Corpus manifest freeze + hash anchor.** `gate-corpus-hash.sh` reads
   `documentation/ephemeral/research/corpus/manifest.json` (already present; lists each file's
   `sha256`, `size_bytes`), recomputes each corpus file's sha256, and asserts both the
   per-file hashes **and** a frozen manifest-level sha256 anchor match a committed
   baseline (`gate/corpus-baseline.sha256`). Any drift → fail (Gotcha #1 anti-tamper).
4. **Baseline-from-main property.** `gate-ratio.sh` reads the current-best aggregate
   from `main`/the leaderboard's `current_best`, **never from the candidate branch** —
   a branch cannot lower its own bar (design §D.4).
5. **Tamper-resistance.** Gate scripts live in a pinned out-of-tree copy
   (`gate/` checked out at the orchestrator's pinned ref, mounted **read-only** into the
   orchestrator container). The **worker never runs its own gate**; a worker editing
   `gate-*.sh` inside its branch has no effect (Appendix A: worker-cannot-edit-its-own-gate).

### Reuse vs new
- **Reuse:** `dr-fleet-evolution/gates/run-all-gates.sh` fail-closed pattern (extended
  to ordered short-circuit); `code/bench/run_bench.py` for the ratio/per-file numbers
  consumed by `gate-ratio.sh`/`gate-competitive.sh`; `lib/jsonl.sh` for run-log lines.
- **New:** the five `gate-*.sh`, `run-merge-rail.sh`, `corpus-baseline.sha256`.

### Test strategy — **rail proven in isolation before any live loop (binding order)**
- `bats` for each gate + the driver: assert fail-closed ordering (a failed gate
  short-circuits and the next never runs), and unknown-exit-treated-as-failure.
- **Dry-run of the full rail against a known-good and a known-bad candidate:**
  - *known-good fixture branch:* a real improvement (or a synthetic branch whose bench
    output strictly beats baseline + passes round-trip) → rail reaches MERGE step
    (in dry-run mode, stops before the actual FF push; assert it *would* merge).
  - *known-bad fixtures:* (a) tampered corpus → `gate-corpus-hash` fails;
    (b) round-trip-breaking codec change → `gate-roundtrip` fails; (c) a candidate that
    regresses one file while improving the aggregate → `gate-competitive` fails; (d) a
    no-improvement candidate → `gate-ratio` fails. Each asserts branch-discard + NO-GO
    record + non-zero exit, and that `main` is untouched.

### Operator-gated steps
- The actual signed FF to `main` in **live** mode is autonomous **by design** (it is
  `merge_main` behind the conservative machine-checked rail — operator-accepted). The
  rail is built/tested with the FF push disabled (`--dry-run`); flipping to live is part
  of the loop bring-up (P7), still autonomous per the operator decision.

---

## Phase 5 — Runtime consilium + deterministic arbiter + closed-branch ledger

**AC mapping:** AC-3 (consilium step), pre-AC-4 (arbiter decides what gets implemented).
**Verifies: V-AC-3.**

### Deliverables
1. **Runtime consilium per iteration** (design §C), reusing `dr-orchestrate`
   `content_consilium_fanout.sh` / `content_consilium_judge.sh` + the `consilium` skill
   degradation rules:
   - `consilium/iteration-brief.template.md` — the self-contained structured-output
     brief, modelled on `CUBR-0032-consilium-brief.md`, carrying: codec-in-one-paragraph
     + live baseline numbers (pulled from the leaderboard), the live Gotcha #1–#7 set,
     the closed-branch ledger, and the required structured output (candidate name,
     wire-cost, sparsity mechanism, Gotcha #3 self-check, Gotcha #6/#7 branch count,
     predicted verdict, kill condition).
   - **Fan-out** identical brief + role label (Vendor A/B/C), no cross-worker leakage;
     drafts land in `datarim/pub-consilium/{RUN-ID}/draft-*.md` (gitignored) + one
     run-log line per worker (`{slot,status,elapsed_s}`).
   - **Score + select** via the judge. **Proposals are voice-bearing — generated by the
     free models themselves, NEVER re-routed through coworker** (coworker may still do
     bulk *reading*). Degradation: 3-of-3 full / 2-of-3 proceeds with a
     `degradation_note` / <2 aborts the iteration (no crash).
2. **The deterministic arbiter** (design §C.1 — the real go/no-go, local + deterministic,
   **before any Rust is written**):
   - `arbiter/probe-entropy.sh` (wraps a ~50-LoC Python over real corpus bytes) — the
     **order-1 conditional-entropy probe** `H(X_t | X_{t-1})` on the candidate's value
     stream (Gotcha #3). Raises conditional entropy on clustered files → **auto NO-GO**.
   - `arbiter/size-model.sh` (wraps Python) — the **full-branch size model** charging
     **one cost term per decoder branch including any φ-map / permutation transmission**
     (Gotcha #6 **and** #7). Asserts `len(cost_terms) ≥ len(decode_branches)`; fewer
     terms than branches = unsound → reject before it can produce a false GO.
   - Only a candidate passing **both** probes proceeds to implementation (P4 rail input).
3. **Git-tracked closed-branch ledger** `consilium/closed-branches.md` (design §C.3):
   - CLOSED — distance-map / content-derived φ (CUBR-0028/29/30/31/32, Gotcha #7).
   - CLOSED — N-sweep on the T4 value stream (Gotcha #5).
   - LIVE — BWT-class reorders (implicit permutation) + any new value-stream coder that
     beats T4 under competitive per-file selection (where the loop spends budget).
   - A proposal matching a CLOSED entry is **auto-rejected at the judge step** before
     arbiter cost is spent.

### Reuse vs new
- **Reuse:** `content_consilium_fanout.sh` / `content_consilium_judge.sh`; the
  `consilium` skill degradation; `code/bench/entropy_*_probe.py` as the entropy-probe
  starting point; `cubr0028_*_probe.py` size-model patterns as the size-model starting
  point; `CUBR-0032-consilium-brief.md` as the brief template.
- **New:** `iteration-brief.template.md`, `arbiter/probe-entropy.sh`,
  `arbiter/size-model.sh`, `consilium/closed-branches.md`.

### Test strategy
- `bats` for the arbiter wrappers: a fixture candidate that raises clustered-file
  entropy → NO-GO; a fixture with fewer cost terms than decode branches → reject; a
  fixture φ-map candidate (Gotcha #7) → the size model charges the φ-map branch and
  rejects (regression-guard against the CUBR-0032 false-GO class).
- `bats` for ledger-match auto-reject at the judge step (a CLOSED-matching proposal
  never reaches the arbiter).
- Consilium degradation: simulate 2 live workers → proceeds with `degradation_note`;
  1 live → aborts iteration cleanly.

### Operator-gated steps
- None — consilium + arbiter are autonomous; they only *select*, the rail decides merge.

---

## Phase 6 — Leaderboard (autonomous write) + operator-gated batch promotion

**AC mapping:** AC-6 (autonomous git-tracked leaderboard; public promotion
operator-gated), AC-9 (win condition is an explicit measured metric).
**Verifies: V-AC-6, V-AC-9.**

### Deliverables
1. `documentation/leaderboard/cubrim-leaderboard.json` (git-tracked, orchestrator-committed) —
   reuses the `CUBR-0028-bench.json` shape (`code_sha`, `aggregate`, per-file deltas,
   `verdict`) extended per design §E.1: `schema_version`, `win_target`
   (`gzip_aggregate: 0.30`, `xz_aggregate: 0.30`), `current_best`
   (live `main` baseline — seeded `{scheme: BwtEntropy, aggregate: 0.504412,
   code_sha: 60ae94c…}`), and a `runs[]` append-list. **Each record is appended ONLY
   after the round-trip proof** (never record an unverified result) and carries
   `corpus_manifest_sha256` (anti-tamper provenance), `vs_gzip`/`vs_xz` (gap to win
   target — AC-9), `merged`, and `run_log_ref` (Law 5).
2. `documentation/leaderboard/gen-leaderboard-md.sh` → `documentation/leaderboard/LEADERBOARD.md` — a
   Markdown table regenerated from the JSON each iteration (autonomous, reversible).
3. `infra/promote-to-cubrim-com.sh` — the **operator-gated batch** promotion command
   (do-stage deliverable): renders the leaderboard to the cubrim.com site surface and
   **stops for review before deploy** (a `/dr-publish`-style batch; never per-iteration).
   The script itself **must not** auto-deploy — it stages + prints the diff for the
   operator.

### Reuse vs new
- **Reuse:** `code/bench/run_bench.py` (feeds the JSON directly); the
  `CUBR-0028-bench.json` shape; the ecosystem `deploy.sh <domain>` for the eventual
  cubrim.com deploy (invoked by the operator, not the loop).
- **New:** `cubrim-leaderboard.json` (seeded), `gen-leaderboard-md.sh`,
  `promote-to-cubrim-com.sh`.

### Test strategy
- `bats` for `gen-leaderboard-md.sh` (JSON → stable Markdown table; deterministic).
- `bats` asserting a leaderboard append is **rejected** when `roundtrip_ok != true`
  (the "never record garbage" invariant) and that `run_log_ref` is mandatory.
- `bats` asserting `promote-to-cubrim-com.sh` **never deploys** without an explicit
  operator confirm flag (it stages + diffs only).

### Operator-gated steps
- **Promotion to public cubrim.com** — HARD-GATED (always-gated floor; Law 1
  reputational/informational harm; Law 4 control). The autonomy resolver classifies
  site-publish as hard-gated; "всё разрешаю" cannot waive it. The leaderboard JSON +
  `LEADERBOARD.md` writes are autonomous (git-tracked, reversible).

---

## Phase 7 — Infinite-loop control (reuse, do not reinvent)

**AC mapping:** AC-7 (continuous run, restart-survival, self-heal, rate-limit
discipline). **Verifies: V-AC-7.**

### Deliverables
1. `cubrim-loop` driver — reuses the `dr-fleet-evolution/evolution-loop.sh`
   collect→generate→gate→select skeleton (and its `--dry-run`, jsonl run-log
   conventions), **extended** with the new conservative merge step (P4 rail). The loop
   phase machine: `consilium → arbiter → impl → gate → merged|discarded → sleeping`.
2. `CUBR-AUTONOMOUS-STATE.md` at the **Cubrim repo root** (git-tracked — NOT under
   gitignored `datarim/`, mirroring the PAX lesson). Holds: current iteration id, loop
   phase, current `main` baseline, closed-branch-ledger pointer, last run-log id. The
   orchestrator reads it **first** on (re)start and resumes from the recorded phase.
3. `infra/systemd/cubrim-loop.service` + `infra/systemd/cubrim-watchdog.timer`:
   - **PAX PATH lesson is binding:** the unit MUST set `Environment=PATH=...` covering
     `~/.local/bin` so `command -v claude` / `cargo` resolve under systemd's non-login
     PATH (the exact gap that left a PAX watchdog unable to respawn its brain).
   - Watchdog respawns dead workers / the orchestrator; a worker that dies or hangs
     (`HANG_IDLE_SECS`, default 120 s) is closed + respawned; if it stays down the
     consilium degrades (2-of-3) rather than crashing.
4. **Rate-limit discipline** (design §F.4): claude-code-router handles per-provider
   backoff + key rotation. Free-tier caps documented (OpenRouter 20 RPM / 50→1000 RPD;
   Groq ~6000 TPM). A hit limit **pauses + backs off** the affected worker — never
   crashes the loop. Rotation **never logs a key** (Appendix A). The resource ceiling is
   rate-limit (free-tier), not money; cadence respects provider RPD.
5. **Defend-mode (AC-9 tie-in):** when `current_best.aggregate ≤ win_target` the loop
   drops cadence to validation-only (the metric that flips the mode is the leaderboard's
   measured aggregate vs target — not a vendor opinion).

### Reuse vs new
- **Reuse:** `evolution-loop.sh` (skeleton + `--dry-run` + jsonl run-log); PAX
  STATE-doc-at-repo-root + watchdog + the `Environment=PATH` systemd lesson;
  claude-code-router backoff/rotation.
- **New:** the `cubrim-loop` driver wrapper, `CUBR-AUTONOMOUS-STATE.md`, the two
  systemd units.

### Test strategy
- `bats` for the loop phase machine: resume-from-STATE re-enters the recorded phase;
  a hung-worker fixture is respawned; <2 live workers → iteration aborts (not crash).
- `bats` asserting the systemd unit declares `Environment=PATH` covering `~/.local/bin`
  (the PAX-respawn regression guard).
- Do-stage: live restart drill (kill orchestrator mid-iteration → watchdog respawns →
  resumes from STATE).

### Operator-gated steps
- Enabling the systemd timer on the host (host-side, follows P1's operator gate);
  the loop running thereafter is autonomous.

---

## Phase 8 — Kill switch (Law 4) + audit trail (Law 5)

**AC mapping:** AC-8 (single documented stop control; unique identity + audit; every
merge/leaderboard write traces to a run-log entry). **Verifies: V-AC-8.**

### Deliverables
1. **Kill switch (single documented control):** `systemctl stop cubrim-loop.timer
   cubrim-loop.service` + a `cubrim-loop stop` wrapper that also stops worker
   containers — halts the loop cleanly mid-phase; the STATE doc preserves the resume
   point. Documented in the kill-switch runbook (`documentation/how-to/stop-the-cubrim-cluster.md`).
   Termination affects **only** the cluster (the trader is on a different host; `main`
   is left at its last green state) — Law 4 terminability.
2. **Audit trail (Law 5):** every container uniquely labelled (`cubrim-orchestrator`,
   `cubrim-worker-{a,b,c}`); an **append-only run log** (`datarim/cubrim-run-log.jsonl`
   via `lib/jsonl.sh`) recording per iteration: iteration id, consilium drafts ref,
   arbiter verdict, gate results, merge sha (or discard), leaderboard write.
   **Every merge and every leaderboard write carries `run_log_ref`** — nothing reaches
   `main` or the leaderboard without a traceable run-log line.

### Reuse vs new
- **Reuse:** `lib/jsonl.sh`; systemd stop semantics.
- **New:** `cubrim-loop stop` wrapper, the kill-switch runbook, the run-log wiring.

### Test strategy
- `bats` asserting `cubrim-loop stop` stops both the service and the worker containers
  (mock `systemctl`/`docker`).
- `bats` asserting a merge or leaderboard write **without** a `run_log_ref` is rejected
  (the Law-5 traceability invariant).

### Operator-gated steps
- None — the kill switch is an operator control by definition; the audit trail is
  autonomous.

---

## AC → Phase coverage matrix

| AC | Phase(s) | Verifier |
|----|----------|----------|
| AC-1 orchestrator + ≥2 workers, verified tool-calling | P1, P2, P3 | V-AC-1 (P3 verify recipe + bake-off result) |
| AC-2 clean dedicated host, cgroup limits | P1, P2 | V-AC-2 (compose limits + dedicated-host bootstrap) |
| AC-3 consilium ≥2 proposals, scored, selected | P5 | V-AC-3 |
| AC-4 implement + measure (cargo test, round-trip, ratio vs T4/BWT + gzip/xz) | P4 (rail), P5 (arbiter feeds it), P6 (records) | V-AC-4 |
| AC-5 absolute mechanical merge gate | P4 | V-AC-5 |
| AC-6 autonomous leaderboard write; public promotion operator-gated | P6 (+ P4 round-trip gate) | V-AC-6 |
| AC-7 infinite loop control (systemd/watchdog, STATE, self-heal, rate-limit) | P7 | V-AC-7 |
| AC-8 kill switch + audit trail | P8 | V-AC-8 |
| AC-9 win condition tracked, measured | P6 (leaderboard field), P7 (defend-mode) | V-AC-9 |

---

## Rollback Strategy

The cluster is built almost entirely as **new, additive artefacts** (infra scripts,
gate scripts, systemd units, leaderboard files) — there is no risky edit to the existing
Cubrim codec in this task (codec changes are the *loop's* output, each individually
behind the AC-5 rail). Rollback is therefore mostly "stop + remove additive files".

- **Stop the loop (immediate):** `systemctl stop cubrim-loop.timer cubrim-loop.service`
  + `cubrim-loop stop` (also stops worker containers). STATE doc preserves resume point.
- **Tear down the cluster:** `docker compose -f infra/docker-compose.yml down` on the
  host; `systemctl disable cubrim-loop.timer cubrim-watchdog.timer`.
- **Revert plan artefacts (git):** all new files land on a task branch
  `feat/cubr-0033-cluster`; `git revert` the merge or `git branch -D` the unmerged
  branch. No migrations, no schema changes.
- **A bad loop-produced merge** is caught by the rail *before* it reaches `main`; if a
  defect slips through (rail bug), `git revert <merge-sha>` restores `main` and the
  leaderboard `current_best` is reset to the prior record (the leaderboard is an
  append-only JSON — revert the offending append commit).
- **Corpus tamper suspicion:** `gate-corpus-hash.sh` is the detector; restore the corpus
  from `git checkout documentation/ephemeral/research/corpus/` (the files are git-tracked) and
  re-anchor `gate/corpus-baseline.sha256`.

---

## Validation Checklist (for /dr-qa)

- [ ] **Order honoured:** bootstrap (P1) → images (P2) → tool-calling verify (P3) →
      rail tested in isolation (P4) → consilium+arbiter (P5) → leaderboard (P6) →
      loop control (P7) → kill/audit (P8).
- [ ] **AC-1:** orchestrator + ≥2 worker containers defined; `verify-tool-calling.sh`
      passes for every chosen model; Worker-B bake-off result recorded (distinct weights
      from qwen3-coder:free; DeepSeek-free fallback honoured if inconclusive).
- [ ] **AC-2:** compose declares `deploy.resources.limits` on every service; host is the
      dedicated AX41 (not Трейдер); ≥4 cores reserved.
- [ ] **AC-3:** consilium fan-out reuses dr-orchestrate; degradation 3/2/abort works;
      proposals voice-bearing (not coworker-routed); closed-branch ledger injected.
- [ ] **AC-4/AC-5:** rail runs the five gates fail-closed ordered; round-trip byte-exact
      on the full corpus; ratio strictly improves vs main baseline; no per-file
      regression; signed FF merge only on all-green; branch discarded on any failure.
      Dry-run proves known-good → would-merge and each known-bad → discard.
- [ ] **AC-5 anti-tamper:** `gate-corpus-hash.sh` rejects a mutated manifest; gate runs
      from the pinned out-of-tree read-only copy; worker cannot edit its own gate.
- [ ] **AC-6:** leaderboard write is autonomous + gated on `roundtrip_ok`; `run_log_ref`
      present; `LEADERBOARD.md` regenerated; promotion-to-cubrim.com never auto-deploys.
- [ ] **AC-7:** STATE doc at repo root (git-tracked); systemd unit sets
      `Environment=PATH` covering `~/.local/bin`; watchdog respawns; rate-limit
      pause+backoff never crashes the loop.
- [ ] **AC-8:** single documented kill switch stops loop + containers; every merge +
      leaderboard write traces to a run-log line.
- [ ] **AC-9:** `win_target` + `vs_gzip`/`vs_xz` are explicit leaderboard fields;
      defend-mode flips on measured `aggregate ≤ win_target`.
- [ ] **bats green** for every shell gate; **dry-run rail** passes both fixtures.
- [ ] **Security (Appendix A):** no key committed; rotation never logs keys; corpus
      anti-tamper anchored; personal-sub auth not stored as a committed key.

---

## Appendix A — Security Design

### Attack surface
1. **Free-model API keys** — the highest-value secret in the cluster. Mitigation:
   keys live ONLY in **gitignored** host env-files (`infra/.env`, `infra/env/*.env`) or
   Vault (Security S1); injected via `--env-file`/Docker secret; **never** in
   `docker-compose.yml`, **never** committed. `infra/.env.example` carries key *names*
   only. A grep gate (`gate-no-secrets`-style, reused pattern) blocks any committed
   value. **Key rotation never logs a key** (the rotation path redacts).
2. **Corpus tampering (the sharpest finding — design §0).** A worker could "win" the
   aggregate by mutating the frozen 7-file corpus (Gotcha #1). Mitigation:
   `gate-corpus-hash.sh` recomputes per-file sha256 + a manifest-level anchor against a
   committed baseline before any ratio is trusted; the corpus files are git-tracked
   (restorable). The ratio gate reads the baseline from `main`, not the branch.
3. **Worker editing its own gate.** Mitigation (design §D.4): gates run from a **pinned
   out-of-tree copy** mounted **read-only** into the orchestrator; the **worker never
   runs its own gate**; a `gate-*.sh` edit inside a worker's branch is inert.
4. **Orchestrator personal-subscription auth.** The orchestrator authenticates to the
   operator's personal Claude subscription via interactive `claude auth login`
   (subscription auth, **not** an API key) — the credential is the CLI's own session
   store, never committed, never placed in an env-file or compose. Workers use free-model
   API keys only; the personal-sub credential is never shared into a worker container.
5. **Autonomous merge to `main`.** Mitigation: the conservative AC-5 rail (machine-
   checked, reversible, signed FF = `merge_main` not history deletion). Public-site
   promotion stays hard-gated (Law 1 / Law 4) — autonomy cannot waive the floor.
6. **Coworker context leak (Ladder L4).** Bulk reads exclude
   `~/arcanada/config/credentials/`; coworker is given explicit path lists, never
   wildcards (autonomous-mode skill mitigation).

### Risks
- **R1 (med):** a rail bug lets a bad merge through. *Mitigation:* the rail is proven in
  isolation against known-good + known-bad fixtures (P4) before any live loop reaches
  it; `git revert <merge-sha>` is the recovery; the leaderboard append is revertable.
- **R2 (low):** free-tier rate-limit storm stalls the loop. *Mitigation:* pause+backoff
  + key rotation; the loop degrades, never crashes; ceiling is RPD, not money.
- **R3 (low):** systemd non-login PATH leaves the watchdog unable to respawn the brain
  (the PAX gap). *Mitigation:* `Environment=PATH` in the unit is a binding deliverable +
  a bats regression guard.
- **R4 (low):** a worker fabricates a passing bench result. *Mitigation:* the gate runs
  the bench itself from the pinned copy on the corpus it hashes — it never trusts the
  worker's reported numbers.

### Supreme Directive mapping
- **Law 1 (Non-Harm):** dedicated host removes the cross-space trader risk; public
  promotion gated so no garbage ratio is ever published (reputational/informational
  harm).
- **Law 4 (Control/Termination):** single documented kill switch; termination affects
  only the cluster.
- **Law 5 (Transparency):** unique container labels + `run_log_ref` on every merge and
  leaderboard write.

---

## Phase 6 (docs) — Documentation to update (dr-plan Phase 6)

- `documentation/how-to/provision-cubrim-cluster-host.md` (P1) — operator provisioning steps.
- `documentation/how-to/verify-free-model-tool-calling.md` (P3).
- `documentation/how-to/stop-the-cubrim-cluster.md` (P8) — kill-switch runbook.
- `documentation/reference/cubrim-leaderboard-schema.md` (P6) — the leaderboard JSON schema.
- `documentation/runbooks/multi-vendor-agent-cluster.md` (ecosystem) — cross-link the
  Cubrim cluster as a consumer of the runbook's conventions.
- `CUBR-AUTONOMOUS-STATE.md` (repo root, P7) — created + documented in CLAUDE.md Key Files.
