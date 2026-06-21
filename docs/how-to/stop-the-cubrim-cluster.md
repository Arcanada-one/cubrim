# How to Stop the Cubrim Research Cluster (Kill Switch)

**Law 4 — Control and Termination.** The cluster MUST be detectable,
isolatable, and terminable. This document is the single documented control.

## Quick Stop (Two Commands)

```bash
# 1. Stop the systemd timer and service (prevents new iterations)
sudo systemctl stop cubrim-loop.timer cubrim-loop.service

# 2. Stop all worker containers (terminates in-progress work)
docker stop cubrim-orchestrator cubrim-worker-a cubrim-worker-b cubrim-worker-c 2>/dev/null || true
```

After these two commands: the loop is halted. No new iterations will start.
Any iteration in progress is cleanly stopped. The `main` branch is left at
the last successful merge. The STATE doc (`CUBR-AUTONOMOUS-STATE.md` at repo
root) preserves the resume point.

## Verify Stopped

```bash
# Confirm no running containers
docker ps --filter "name=cubrim" --format "table {{.Names}}\t{{.Status}}"

# Confirm systemd units inactive
systemctl is-active cubrim-loop.timer  # should print "inactive"
systemctl is-active cubrim-loop.service  # should print "inactive"
```

## Restart (Resume Loop)

```bash
# Resume from the last STATE doc checkpoint
sudo systemctl start cubrim-loop.timer

# Or force-start an iteration immediately (bypasses timer schedule)
sudo systemctl start cubrim-loop.service
```

The orchestrator reads `CUBR-AUTONOMOUS-STATE.md` on start to resume from
the last known-good checkpoint (last merged SHA + last iteration ID).

## Emergency: Kill All Cubrim Processes

If the systemd approach does not work (broken service, stuck process):

```bash
# Kill all cubrim Docker containers forcibly
docker kill $(docker ps -q --filter "name=cubrim") 2>/dev/null || true

# Find and kill any orphan cubrim-loop processes
pkill -f "cubrim-loop" || true
```

## Container Identity (Law 5 — Traceability)

Every cluster container is labelled and identifiable:

| Container | Role | Label |
|-----------|------|-------|
| `cubrim-orchestrator` | Orchestrator (loop control, gate runner, leaderboard writer) | `cubrim-role=orchestrator` |
| `cubrim-worker-a` | Vendor A free-model agent | `cubrim-role=worker-a` |
| `cubrim-worker-b` | Vendor B free-model agent | `cubrim-role=worker-b` |
| `cubrim-worker-c` | Vendor C free-model agent (optional) | `cubrim-role=worker-c` |

```bash
# List all cubrim containers (running or stopped)
docker ps -a --filter "label=cubrim-role" --format "table {{.Names}}\t{{.Status}}\t{{.Labels}}"
```

## Audit Log

Every gate result, merge, and leaderboard write is recorded in:
`datarim/cubrim-run-log.jsonl` (append-only, git-tracked after each iteration).

```bash
# View last 10 run-log entries
tail -10 datarim/cubrim-run-log.jsonl | jq .

# Find all merges
grep '"event":"merge_rail_pass"' datarim/cubrim-run-log.jsonl | jq '{run_id,merged_sha,ts}'
```

## Win Condition

The loop runs until `current_best.aggregate` in `docs/leaderboard/cubrim-leaderboard.json`
falls below `win_target.gzip_aggregate` (currently 0.159674). After that, the
orchestrator shifts to defend-mode (lower iteration cadence, strict no-regression
validation). The win condition is tracked in the leaderboard — check it with:

```bash
python3 -c "
import json
lb = json.load(open('docs/leaderboard/cubrim-leaderboard.json'))
best = lb['current_best']['aggregate']
target = lb['win_target']['gzip_aggregate']
gap = best - target
print(f'Current best: {best:.6f}')
print(f'Win target:   {target:.6f}')
print(f'Gap:          {gap:+.6f}')
print('STATUS:', 'WIN' if best <= target else 'BEHIND')
"
```

## Systemd Service Reference (for P7 — install on host)

The actual service files are created during P7 (operator-gated host provisioning).
This section describes the expected unit file structure for reference.

```
# /etc/systemd/system/cubrim-loop.service
[Unit]
Description=Cubrim Autonomous Research Loop
After=docker.service network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/cubrim/cluster.env
# PAX watchdog lesson: systemd MUST set PATH to include ~/.local/bin
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin
ExecStart=/opt/cubrim/cluster/orchestrator-run.sh
User=root
RemainAfterExit=no
TimeoutStartSec=3600

[Install]
WantedBy=multi-user.target
```

```
# /etc/systemd/system/cubrim-loop.timer
[Unit]
Description=Cubrim Autonomous Research Loop Timer

[Timer]
OnCalendar=*:0/60  # every 60 minutes
RandomizedDelaySec=120
Persistent=true

[Install]
WantedBy=timers.target
```

**IMPORTANT (PAX lesson):** `Environment=PATH=...` in the service unit is mandatory.
The default systemd PATH does not include `~/.local/bin` where `claude` is installed.
Without it, `command -v claude` fails silently and the watchdog cannot respawn
the brain. See `documentation/mandates/autonomous-agents.md` § systemd PATH.

## Related Files

- `CUBR-AUTONOMOUS-STATE.md` (repo root) — resume checkpoint STATE doc
- `datarim/cubrim-run-log.jsonl` — append-only audit trail
- `docs/leaderboard/cubrim-leaderboard.json` — machine-readable results
- `code/cluster/gate/run-merge-rail.sh` — the AC-5 merge rail (Law 5 traceability)
