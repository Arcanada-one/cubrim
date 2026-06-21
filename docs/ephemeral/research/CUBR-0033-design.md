# CUBR-0033 — L4 Design: Autonomous Multi-Vendor Compression-Research Cluster

> **Stage:** `/dr-design` (consilium-gated, L4). **Mode:** autonomous (`/dr-auto`).
> **Author:** architect agent. **Provenance:** Cubrim @ `e476294`.
> **Scope reminder:** this task delivers the **cluster + loop + streaming**. The
> winning algorithm is the loop's *emergent output*, NOT a deliverable here.
> **Binding operator decisions (init-task design-round-1):** host = clean dedicated
> (off Трейдер); merge = autonomous behind the mechanical AC-5 gate; publish to
> cubrim.com = operator-gated batch.

---

## 0. Consilium verdict (design-time panel)

Panel: architect, security, sre, strategist, reviewer (blast-radius 3). Verdict:
**architecture APPROVED with five binding conditions** (folded into the sections
below). The single sharpest finding — from the reviewer — is that the most likely
silent-cheat vector is **corpus tampering**: a worker could "win" the aggregate by
mutating the frozen 7-file corpus (Gotcha #1). The AC-5 rail therefore hashes the
corpus manifest and rejects any ratio that was measured against a changed corpus.
Security's finding: a worker must not be able to edit the gate script inside the
branch it is trying to merge — gates run from a **pinned out-of-tree copy**, executed
by the orchestrator, never by the worker. Full panel record is inline in the
`/dr-design` turn that produced this file.

This is the *design-time* consilium. It is distinct from the **runtime consilium**
(§C) the cluster executes once per iteration.

---

## A. Cluster topology

### A.1 Roles

```
                ┌──────────────────────────────────────────────┐
                │  ORCHESTRATOR  (1)                            │
                │  Claude Code CLI — paid/personal sub OR a     │
                │  capable free model; runs the loop driver,    │
                │  the runtime consilium, the deterministic     │
                │  arbiter (probe + size model), and the AC-5   │
                │  merge rail. Owns the git tree + gate copy.   │
                └───────────────┬──────────────────────────────┘
                                │ briefs (identical, role-labelled)
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
          ┌──────────┐   ┌──────────┐   ┌──────────┐
          │ WORKER A │   │ WORKER B │   │ WORKER C │   (≥2 required; 3 = full panel)
          │ Claude   │   │ Claude   │   │ Claude   │
          │ Code CLI │   │ Code CLI │   │ Code CLI │
          │ → free   │   │ → free   │   │ → free   │
          │  model 1 │   │  model 2 │   │  model 3 │
          └──────────┘   └──────────┘   └──────────┘
```

- **1 orchestrator + ≥2 workers** (AC-1, AC-3). Three workers gives the consilium
  the same 3-of-N graceful-degradation the multi-vendor mode already defines (run
  proceeds at 2-of-3; below 2 the consilium step aborts that iteration, no crash).
- Each agent is the **Claude Code CLI** pointed at a **free model** via
  `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_MODEL` through
  **claude-code-router** (per-agent model routing). One Docker container = one
  top-level Claude Code agent with its own env.

### A.2 Model routing (claude-code-router)

| Slot | Provider/model | Role | Why |
|------|----------------|------|-----|
| Worker A (primary code-gen) | OpenRouter `qwen/qwen3-coder:free` (1M ctx) | proposes + implements codec changes | strong code-gen, huge context for the codec (`codec.rs` alone is 130 KB) |
| Worker B | a second free OpenRouter code model (distinct weights) | independent proposal | voice independence — must NOT be the same weights as A |
| Worker C / background | Groq `llama-*` (free) | background tasks, probe-script drafting, summaries | fast, high TPM for cheap I/O |

- **Tool-calling verification is a hard do-stage checkpoint (AC-1).** Before the
  loop is trusted, each chosen free model must demonstrate a real tool call
  (Read/Edit/Bash) end-to-end. A free model that cannot reliably call tools makes
  its worker inert — the design treats unverified tool-calling as a blocker, not an
  assumption. Verification recipe lives in the do-stage plan.
- **Secrets:** free-model API keys live in a **gitignored env file** on the host
  (or Vault if the host has an agent), injected into containers via
  `--env-file`/Docker secret — never in `docker-compose.yml`, never committed
  (Security S1). Key rotation (§F) never logs a key.

### A.3 Containerisation

- Docker on the dedicated host. One image (`cubrim-worker`) bundling: Claude Code
  CLI, claude-code-router, the Cubrim Rust toolchain (`cargo`), Python3+NumPy (for
  the entropy/size-model probes), `jq`, `git`. Per-agent container differs only by
  its `--env-file` (which model/key).
- The orchestrator container additionally mounts the git working tree and holds the
  **pinned out-of-tree gate copy** (§D.4).

---

## B. Resource discipline on the dedicated host (AC-2 reframed)

The operator moved the cluster **off Трейдер entirely** onto a clean dedicated host
(an underloaded AX41 @ 1-3 % CPU in HEL1, or `arcana-dev`). This structurally
removes the Law-1 cross-space risk to AngryRobot production trading — **the trader
is not touched, not shared, not migrated**. AC-2 is therefore an *ordinary
self-contained resource limit on a dedicated host*, not a trader-fence.

- **cgroup CPU/RAM caps per container** via compose `deploy.resources.limits`
  (`cpus`, `memory`) — e.g. each worker ≤ 1.5 CPU / ≤ 4 GB, orchestrator ≤ 1 CPU /
  ≤ 2 GB; tune to the chosen host's headroom. Reserve ≥ 4 cores free as the standing
  ecosystem convention for shared dev iron.
- The Rust `cargo test` + bench runs are the CPU spike; they run **serialised** in
  the orchestrator (one gate at a time), never N-parallel, to bound peak load.
- **Host provisioning is operator-gated and is do-stage work** — this design does
  NOT provision the host or start containers.

---

## C. Runtime consilium step (per iteration) — AC-3

Once per iteration the orchestrator runs a real multi-vendor consilium, reusing the
`dr-orchestrate` plugin's fan-out/judge protocol (`content_consilium_fanout.sh` /
`content_consilium_judge.sh`) and the `consilium` skill's degradation rules.

1. **Brief assembly.** The orchestrator builds an iteration brief modelled on the
   `CUBR-0032-consilium-brief.md` template (self-contained, structured-output
   contract). The brief **MUST** carry:
   - the codec-in-one-paragraph + current baseline numbers (T4 / BWT aggregate,
     gzip/xz targets) pulled live from the leaderboard;
   - the **live Gotcha #1–#7 set** and the **closed-branch ledger** (§ C.3) so a
     worker cannot re-propose a dead branch;
   - the required structured output (candidate name, wire-cost, sparsity mechanism,
     Gotcha #3 self-check, Gotcha #6/#7 branch count, predicted verdict, kill
     condition).
2. **Fan-out.** Identical brief + a role label ("Vendor A/B/C") to each worker; no
   cross-worker leakage. Drafts land in `datarim/pub-consilium/{RUN-ID}/draft-*.md`
   (gitignored), one run-log line per worker (`{slot,status,elapsed_s}`).
3. **Score + select.** The orchestrator's judge scores each proposal against the
   structured criteria and selects candidate(s) to implement. **Proposals are
   voice-bearing — generated by the free models themselves, NEVER re-routed through
   coworker** (coworker may still do bulk *reading* of source files). Degradation:
   3-of-3 full; 2-of-3 proceeds with a `degradation_note`; <2 aborts the iteration.

### C.1 The deterministic arbiter (the real go/no-go — NOT a vendor opinion)

After selection, the orchestrator runs — **locally, deterministically, before any
Rust is written** — the two cheap probes that are the structural embodiment of the
Gotchas:

1. **Order-1 conditional-entropy probe** (Gotcha #3): ~50-LoC Python over the actual
   corpus bytes, computing `H(X_t | X_{t-1})` on the candidate's resulting value
   stream. If the candidate raises conditional entropy on clustered files → **auto
   NO-GO, no implementation**.
2. **Full-branch size model** (Gotcha #6 **and** #7): a size model that charges
   **one cost term per decoder branch, including any φ-map / permutation
   transmission**. The arbiter asserts `len(cost_terms) ≥ len(decode_branches)`;
   a model with fewer terms than branches is unsound and is rejected before it can
   produce a false GO.

Only a candidate that **passes both probes** proceeds to implementation (§D). This
is what stops the cluster wasting free-tier budget re-discovering closed branches.

### C.2 Each iteration = a self-contained CUBR research cycle

Every iteration honours the full Gotcha discipline as *gates*, not advice:

| Gotcha | Structural enforcement in the iteration |
|--------|-----------------------------------------|
| #1 ρ=1 / corpus trap | corpus is **frozen**; manifest hash checked (§D); sparse files already present in the canonical 7-file set |
| #2 positional-φ inertness | arbiter measures whether the map carries weight before tuning cube geometry |
| #3 φ-not-locality | order-1 entropy probe is a **mandatory pre-impl gate** |
| #4 BWT lever | flagged in the ledger as the **live lever** (the one open hypothesis class) |
| #5 N-invariance | N-sweep on the value stream is pre-marked NO-GO in the ledger |
| #6 full-branch size model | arbiter asserts one cost term per decoder branch |
| #7 φ-map-as-branch | size model charges the φ-map permutation as its own branch — **distance-map branch is CLOSED** |

### C.3 Closed-branch ledger (anti-rediscovery)

A git-tracked `consilium/closed-branches.md` (new) records every dead branch with
its kill-evidence so the brief can inject it:

- **CLOSED — distance-map / content-derived φ** (CUBR-0028/29/30/31/32, Gotcha #7,
  information-conservation proof). Workers MUST NOT re-propose.
- **CLOSED — N-sweep on the T4 value stream** (Gotcha #5, N-invariant, measured).
- **LIVE — BWT-class reorders** that encode their permutation implicitly (LF-mapping
  + one index), and any *new* value-stream coder that beats T4 under competitive
  per-file selection. This is where the loop spends its budget.

A proposal that matches a CLOSED entry is auto-rejected at the judge step before
arbiter cost is spent.

---

## D. The mechanical merge rail (AC-5) — the safety rail for full autonomy

A candidate is merged to `main` **only** when ALL of the following hold. The rail is
**deterministic shell**, run by the **orchestrator** from a **pinned out-of-tree gate
copy** (§D.4). No human in the loop; the gate is mechanical and conservative. **Any
failure → the branch is discarded** (deleted), the NO-GO is recorded to the
leaderboard, and the loop continues.

### D.1 Gate sequence (fail-closed, ordered)

```
gate-corpus-hash.sh     # manifest sha256 == frozen baseline   (anti-tamper, reviewer finding)
  └─ pass → gate-cargo-test.sh   # `cargo test` green (round-trip + property tests)
       └─ pass → gate-roundtrip.sh   # byte-exact decode(encode(f)) == f for EVERY corpus file
            └─ pass → gate-ratio.sh   # aggregate strictly improves vs current main baseline
                 └─ pass → gate-competitive.sh   # new scheme wired as min(new,T4)+scheme byte;
                 │                                 per-file delta recorded; NO file regresses
                 └─ pass → MERGE (signed FF to main) + record GO to leaderboard
  any failure at any step → discard branch + record NO-GO + continue
```

### D.2 Why each term exists

- **corpus-hash** — the single most likely silent cheat is mutating the frozen
  corpus to inflate the aggregate (Gotcha #1). Reject any ratio measured against a
  changed manifest. Anchor: `docs/ephemeral/research/corpus/manifest.json`.
- **cargo-test + round-trip** — round-trip byte-exact on the **full** corpus is the
  absolute invariant (Constraint). A lossy compressor is a bug, never a trade-off.
- **ratio strictly improves** — measured **only** on the frozen corpus, vs the
  current `main` baseline (read from the leaderboard's `current_best`).
- **competitive per-file selection** — CUBR-0028 proved `min(new, T4)` + scheme byte
  in the header is *structurally* regression-proof. The gate asserts the new
  ValueScheme is wired competitively and that **no individual file regresses**, so a
  per-file regression cannot hide behind an aggregate win.

### D.3 Branch discard semantics

- Each candidate is implemented on `feat/cubr-0033-iter-<RUN-ID>`.
- Gate failure → `git branch -D` the feature branch (it never touched `main`).
- The merge is a **signed fast-forward to `main`** (which is `merge_main` under the
  autonomy resolver, NOT history deletion) — only after every gate is green.
  *Cubrim `main` does not require signed commits the way the Datarim repo does;*
  if branch protection is added later, the orchestrator signs locally before FF.

### D.4 Tamper-resistance (security finding)

- The gate scripts live in a **pinned copy outside the candidate's mutable tree**
  (e.g. `code/cubrim-rs/../gate/` checked out at the orchestrator's pinned ref, or a
  read-only mount). The orchestrator runs the gate; the **worker never runs its own
  gate**. A worker editing `gate-*.sh` inside its branch has no effect — the pinned
  copy is authoritative.
- The gate reads the **baseline from `main`/leaderboard**, not from the branch, so a
  branch cannot lower its own bar.

---

## E. Leaderboard + operator-gated batch publish (AC-6 reframed) — AC-9

### E.1 Machine-readable leaderboard (git-tracked, autonomous write)

`docs/leaderboard/cubrim-leaderboard.json` (git-tracked, committed by the
orchestrator). Each iteration appends one record — **only after the round-trip
proof** (never record an unverified result):

```jsonc
{
  "schema_version": 1,
  "win_target": { "gzip_aggregate": 0.30, "xz_aggregate": 0.30 },   // AC-9 explicit
  "current_best": {                                                  // the live main baseline
    "scheme": "BwtEntropy", "aggregate": 0.504412, "code_sha": "60ae94c…"
  },
  "runs": [
    {
      "run_id": "2026-06-21T18:00:00Z-abc123",
      "date": "2026-06-21",
      "candidate": "<scheme name>",
      "code_sha": "<git sha the bench ran on>",          // Cubrim rule: bench carries code_sha
      "corpus_manifest_sha256": "<frozen hash>",         // anti-tamper provenance
      "aggregate": 0.49xxxx,
      "vs_t4": -0.0xx, "vs_bwt": -0.0xx,
      "vs_gzip": +0.19, "vs_xz": +0.19,                  // gap to the win target
      "roundtrip_ok": true,
      "verdict": "GO|NO-GO",
      "merged": true,
      "run_log_ref": "<audit-log entry id>"              // Law 5 traceability
    }
  ]
}
```

The record schema reuses the existing `CUBR-0028-bench.json` shape (`code_sha`,
`aggregate`, per-file deltas, `verdict`) so the bench harness (`code/bench/run_bench.py`)
feeds it directly.

### E.2 Human-readable view

A generated `docs/leaderboard/LEADERBOARD.md` (Markdown table, regenerated from the
JSON each iteration). This is the autonomous, git-tracked, **reversible** surface.

### E.3 Operator-gated batch promotion to cubrim.com (NON-NEGOTIABLE)

- Per-iteration autonomous publish to the live public site is **OUT** (superseded).
- The loop writes results autonomously **only** to the git-tracked leaderboard.
- Promoting the leaderboard to the **public cubrim.com** site is a **human-triggered
  batch step**: the operator runs a documented promotion command (do-stage
  deliverable; e.g. a `/dr-publish`-style batch that renders the leaderboard to the
  site and is reviewed before deploy).
- **Why this floor cannot be waived by "всё разрешаю":** public-surface / irreversible
  public messages are the framework always-gated floor; Supreme Directive Law 1
  (no reputational/informational harm — never publish a garbage ratio) and Law 4
  (control) outrank the operator's blanket-autonomy instruction. The autonomy
  resolver classifies site-publish as hard-gated; merge stays autonomous because it
  is conservative + machine-checked + reversible (a bad merge is caught by the gate,
  never reaches it).

---

## F. Infinite-loop control (AC-7) — reuse, do not reinvent

### F.1 Reuse map

| Need | Reused pattern | Source |
|------|----------------|--------|
| generate→gate→select→integrate loop with **fail-closed Bash gates** | `evolution-loop.sh` + `gates/run-all-gates.sh` (fail-closed orchestrator) | `plugins/dr-fleet-evolution/` |
| multi-vendor fan-out / judge / degradation | `content_consilium_fanout.sh` / `content_consilium_judge.sh` | `plugins/dr-orchestrate/` + `consilium` skill |
| restart-survival STATE doc + watchdog respawn | git-tracked STATE doc at **repo root**; systemd timer watchdog | PAX autonomous-loop + watchdog (ecosystem memory) |
| headless multi-vendor cluster host conventions | the canonical cluster runbook | `documentation/runbooks/multi-vendor-agent-cluster.md` |

> **Key divergence from fleet-evolution:** that loop **never auto-merges** (stops at
> PR). CUBR-0033 **does** auto-merge — but only behind the AC-5 mechanical rail (§D).
> Everything *upstream* of merge (collect→generate→gate-pattern) is reused; the merge
> step is the new, conservative addition.

### F.2 STATE doc (restart survival)

`CUBR-AUTONOMOUS-STATE.md` at the **Cubrim repo root** (git-tracked — NOT under
gitignored `datarim/`, mirroring the PAX lesson). Holds: current iteration id, loop
phase (consilium|arbiter|impl|gate|merged|sleeping), current `main` baseline, the
closed-branch ledger pointer, last run-log id. The orchestrator reads it **first** on
(re)start and resumes from the recorded phase.

### F.3 systemd + watchdog

- `cubrim-loop.service` (the orchestrator driver) + `cubrim-watchdog.timer`
  (respawns dead workers / the orchestrator).
- **PAX PATH lesson is binding:** the unit MUST set `Environment=PATH=...` covering
  `~/.local/bin` so `command -v claude` / `cargo` resolve under systemd's non-login
  PATH (the exact gap that left a PAX watchdog unable to respawn its brain).
- Self-heal: a worker container that dies or hangs (`HANG_IDLE_SECS`, default 120 s)
  is closed and respawned; if it stays down the consilium degrades (2-of-3) rather
  than crashing.

### F.4 Rate-limit discipline

- Free-tier caps: OpenRouter **20 RPM / 50→1000 RPD**, Groq **~6000 TPM**.
- claude-code-router handles per-provider backoff + **key rotation**. A hit limit
  **pauses + backs off** the affected worker — it **never crashes the loop**.
  Rotation never logs a key (Security).
- Because brains are free-tier, the resource ceiling is **rate-limit**, not money;
  "infinite" is bounded by provider RPD, which the cadence respects.

---

## G. Stop/kill switch (Law 4) + audit trail (Law 5) — AC-8

- **Kill switch (single documented control):** `systemctl stop cubrim-loop.timer
  cubrim-loop.service` (+ a `cubrim-loop stop` wrapper that also stops worker
  containers) halts the loop cleanly mid-phase; the STATE doc preserves resume point.
  Documented in the do-stage runbook. This satisfies Law 4 terminability — and the
  termination affects only the cluster, not any external system (the trader is on a
  different host; `main` is left at its last green state).
- **Unique identity + audit (Law 5):** every container is uniquely labelled
  (`cubrim-orchestrator`, `cubrim-worker-{a,b,c}`); **every merge and every
  leaderboard write traces to a run-log entry** (`run_log_ref` in the leaderboard
  record). The append-only run log records: iteration id, consilium drafts ref,
  arbiter verdict, gate results, merge sha (or discard), leaderboard write. Nothing
  reaches `main` or the leaderboard without a traceable run-log line.

---

## H. Win-condition tracking (AC-9)

- **Target:** beat gzip/xz aggregate **~0.30** on the canonical frozen corpus.
  Current Cubrim best = **BWT aggregate 0.504** (CUBR-0028) — ~1.7× *worse* than
  gzip today. The gap (`vs_gzip` / `vs_xz`) is an explicit field in every leaderboard
  record.
- **"Infinite" = "until win, then defend", not unbounded burn.** When `current_best.aggregate
  ≤ win_target` the loop shifts to **defend-mode**: lower cadence, only runs to
  validate that no regression creeps in and to chase further marginal gains. The
  metric that flips the mode is the leaderboard's measured aggregate vs the target —
  not a vendor opinion.

---

## Open questions for the operator (genuine ambiguity / hard-gated)

1. **Which dedicated host** — an underloaded AX41 in HEL1 vs `arcana-dev`? Both
   satisfy AC-2. Recommendation: **`arcana-dev`** — the multi-vendor cluster runbook
   already documents it (vendor CLIs installed + authenticated, headless SSH via
   `dev@65.109.56.79`), which removes most do-stage provisioning. An AX41 is cleaner
   isolation but needs full toolchain bootstrap. *Host provisioning is operator-gated
   do-stage work — escalating now so the plan targets the right host.*
2. **Orchestrator brain** — free model (pure free-tier, but the orchestrator runs the
   judge + arbiter, which benefit from a stronger model) vs the operator's personal
   Claude sub for the orchestrator only (workers stay free). The init-task says
   *workers* are free; it does not pin the orchestrator. Recommendation: orchestrator
   on a capable model (personal sub or a stronger free model), workers free.
3. **Second free code-gen model (Worker B)** — `qwen3-coder:free` is pinned for A;
   B needs *distinct weights* for true voice independence. Operator preference on the
   specific second OpenRouter free model? (Resolvable at do-stage via a tool-calling
   bake-off; flagging in case the operator has a preference.)

These are flagged, not blocking: the design is complete and internally consistent
for all three under the recommended defaults.

---

## Reuse / new-artefact inventory (for the plan)

**Reuse (do not reinvent):** `plugins/dr-fleet-evolution/{evolution-loop.sh,gates/run-all-gates.sh,lib/jsonl.sh}`;
`plugins/dr-orchestrate/{content_consilium_fanout.sh,content_consilium_judge.sh}`;
`consilium` skill degradation rules; `code/bench/run_bench.py`; PAX STATE-doc +
watchdog pattern; multi-vendor cluster runbook.

**New artefacts (do-stage):** Docker image `cubrim-worker` + `docker-compose.yml`
(cgroup limits, `--env-file` secrets); claude-code-router config per worker;
`gate-{corpus-hash,cargo-test,roundtrip,ratio,competitive}.sh` (the AC-5 rail);
`cubrim-loop` driver + `cubrim-loop.service`/`cubrim-watchdog.timer`;
`consilium/closed-branches.md` (the ledger); `docs/leaderboard/{cubrim-leaderboard.json,LEADERBOARD.md}`
+ generator; iteration consilium brief template (from `CUBR-0032-consilium-brief.md`);
the operator batch-publish-to-cubrim.com command; the do-stage tool-calling
verification recipe; the kill-switch runbook.
