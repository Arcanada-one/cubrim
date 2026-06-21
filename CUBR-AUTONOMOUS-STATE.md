---
# CUBR-AUTONOMOUS-STATE.md — Cubrim Autonomous Research Loop STATE Document
#
# This file is git-tracked at the repo root (NOT under datarim/ which is gitignored).
# The orchestrator reads it first on (re)start to resume from the last known-good point.
# Update via state_set() in cubrim-loop.sh — do NOT edit while the loop is running.
#
# PAX lesson: this file mirrors the PAX-AUTONOMOUS-STATE.md pattern:
# git-tracked at repo root so it survives container restarts + watchdog respawns.

# ── Current iteration ─────────────────────────────────────────────────────────
iteration: "0"

# ── Current loop phase ────────────────────────────────────────────────────────
# Allowed values: idle | consilium | arbiter | impl | gate | merged | discarded | sleeping
loop_phase: "sleeping"

# ── Current main baseline ─────────────────────────────────────────────────────
# Git SHA of the HEAD of main at the time of the last successful merge.
# Set to the repo's initial commit SHA after first bootstrap.
main_baseline: "unknown"

# ── Closed-branch ledger pointer ──────────────────────────────────────────────
# Pointer to the ledger file that lists all discarded iteration branches.
closed_branch_ledger: "consilium/closed-branches.md"

# ── Last run-log entry ID ─────────────────────────────────────────────────────
# The run_id of the most recent iteration (success or failure).
last_run_id: "none"

# ── Win condition ─────────────────────────────────────────────────────────────
# Once current_best.aggregate in cubrim-leaderboard.json falls below
# win_target.gzip_aggregate, the loop shifts to defend-mode.
# See docs/how-to/stop-the-cubrim-cluster.md § Win Condition for details.
win_condition_met: "false"
---

# Cubrim Autonomous Research Loop — STATE

This document is the restart-survival checkpoint for the autonomous compression
research loop. If the orchestrator or host restarts, it reads this file first
and resumes from the recorded `loop_phase`.

## How to read this file

| Field | Meaning |
|-------|---------|
| `iteration` | Monotonically increasing iteration counter |
| `loop_phase` | Last completed phase (the loop resumes from the NEXT phase) |
| `main_baseline` | Git SHA of main at last successful merge |
| `closed_branch_ledger` | Path to the file listing discarded branches |
| `last_run_id` | The `run_id` of the most recent iteration |
| `win_condition_met` | Set to `"true"` when the leaderboard target is reached |

## How the loop transitions

```
idle → consilium → arbiter → impl → gate → merged (GO) → sleeping → consilium ...
                                          ↘ discarded (NO-GO) → sleeping → consilium ...
```

Defend-mode (when `win_condition_met = true`): consilium and impl are skipped;
the loop only validates main on the gate chain.

## Resume command

```bash
sudo systemctl start cubrim-loop.service
# or wait for the next timer tick (every 60 min)
```

## Kill switch

See `docs/how-to/stop-the-cubrim-cluster.md` — two commands stop the loop safely.
