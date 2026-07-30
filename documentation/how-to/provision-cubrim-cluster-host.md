# How to Provision the Cubrim Research Cluster Host

This runbook is the single operator guide for bringing up the autonomous
compression-research cluster on a fresh AX41 dedicated host. Execute the
steps in order. Steps that require operator keyboard interaction are marked
**(interactive)**.

Related: `documentation/how-to/stop-the-cubrim-cluster.md` — the kill switch.

---

## Prerequisites

- A fresh Debian/Ubuntu 24.04 host (AX41 in HEL1 or equivalent).
- SSH root access to the host.
- The Cubrim repo checked out locally on your Mac.
- API keys for: OpenRouter, DeepSeek, Groq (free-tier keys).
- Your personal Claude Max subscription credentials (for `claude auth login`).

---

## Step 1 — Copy the repo to the host

On your Mac:

```bash
# Set the host IP or hostname
HOST=<ax41-ip>

# Copy the full repo
rsync -az --exclude 'target/' --exclude '.git/' \
    /Users/ug/arcanada/Projects/Cubrim/ \
    root@${HOST}:/opt/cubrim/repo/

# Or with scp (tarball method)
tar czf /tmp/cubrim-repo.tar.gz -C /Users/ug/arcanada/Projects/Cubrim .
scp /tmp/cubrim-repo.tar.gz root@${HOST}:/tmp/
ssh root@${HOST} "mkdir -p /opt/cubrim/repo && tar xzf /tmp/cubrim-repo.tar.gz -C /opt/cubrim/repo"
```

---

## Step 2 — Run the bootstrap script

On the host:

```bash
ssh root@${HOST}

# Verify the script is there
ls /opt/cubrim/repo/code/cluster/infra/bootstrap-host.sh

# Dry-run first to see the install plan
bash /opt/cubrim/repo/code/cluster/infra/bootstrap-host.sh --dry-run

# If the plan looks correct, run for real
bash /opt/cubrim/repo/code/cluster/infra/bootstrap-host.sh
```

The script is idempotent — safe to re-run. Each component prints `[skip]`
if already present.

---

## Step 3 — Interactive: authenticate Claude Code **(interactive)**

This step requires your personal subscription credentials. It cannot be
automated. Run it once on the host after the bootstrap:

```bash
ssh -t root@${HOST}
claude auth login
# Follow the browser OAuth flow (or device-code flow if headless)
# Use your personal Max subscription (NOT an API key)
```

Verify authentication:

```bash
claude --version
# Should print without errors
```

---

## Step 4 — Create the cluster environment file

On your Mac, fill in the real API keys:

```bash
# Copy the template
scp /Users/ug/arcanada/Projects/Cubrim/code/cluster/infra/.env.example \
    root@${HOST}:/opt/cubrim/repo/code/cluster/infra/.env

# Edit on the host to add real values
ssh root@${HOST} "nano /opt/cubrim/repo/code/cluster/infra/.env"
# Set: OPENROUTER_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY, CUBRIM_HOST_ID, CUBRIM_REPO_ROOT
```

Also create the per-worker env files (copy from examples and fill keys):

```bash
ssh root@${HOST} bash -c '
    cd /opt/cubrim/repo/code/cluster/infra/env
    for slot in worker-a worker-b worker-c; do
        cp ${slot}.env.example ${slot}.env
        echo "Edit ${slot}.env to fill in the real API key token"
    done
'
```

---

## Step 5 — Create the systemd environment file

```bash
ssh root@${HOST} bash -c '
    mkdir -p /etc/cubrim
    cat > /etc/cubrim/cluster.env <<EOF
CUBRIM_REPO_ROOT=/opt/cubrim/repo
CUBRIM_HOST_ID=ax41-hel1
EOF
    chmod 640 /etc/cubrim/cluster.env
'
```

---

## Step 6 — Install systemd units

```bash
ssh root@${HOST} bash -c '
    UNIT_DIR=/opt/cubrim/repo/code/cluster/infra/systemd
    cp "${UNIT_DIR}/cubrim-loop.service" /etc/systemd/system/
    cp "${UNIT_DIR}/cubrim-loop.timer" /etc/systemd/system/
    cp "${UNIT_DIR}/cubrim-watchdog.service" /etc/systemd/system/
    cp "${UNIT_DIR}/cubrim-watchdog.timer" /etc/systemd/system/
    systemctl daemon-reload
'
```

---

## Step 7 — Build the Docker image and start containers

```bash
ssh root@${HOST} bash -c '
    cd /opt/cubrim/repo
    docker compose -f code/cluster/infra/docker-compose.yml build
    CUBRIM_REPO_ROOT=/opt/cubrim/repo CUBRIM_HOST_ID=ax41-hel1 \
        docker compose -f code/cluster/infra/docker-compose.yml up -d
'
```

Verify all four containers are running:

```bash
ssh root@${HOST} "docker ps --filter label=cubrim-role --format 'table {{.Names}}\t{{.Status}}'"
```

Expected output:

```
NAMES                   STATUS
cubrim-orchestrator     Up ...
cubrim-worker-a         Up ...
cubrim-worker-b         Up ...
cubrim-worker-c         Up ...
```

---

## Step 8 — Initialise the STATE doc

Set the initial baseline SHA:

```bash
ssh root@${HOST} bash -c '
    cd /opt/cubrim/repo
    SHA=$(git rev-parse HEAD)
    sed -i "s/main_baseline: \"unknown\"/main_baseline: \"${SHA}\"/" CUBR-AUTONOMOUS-STATE.md
    echo "STATE doc initialised with baseline $SHA"
'
```

---

## Step 9 — Enable and start the cluster

```bash
ssh root@${HOST} bash -c '
    systemctl enable --now cubrim-loop.timer
    systemctl enable --now cubrim-watchdog.timer
    systemctl status cubrim-loop.timer
'
```

The loop will fire its first iteration within 5 minutes of boot (per
`OnBootSec=5min` in the timer). Subsequent iterations run every 60 minutes.

---

## Verify the cluster is running

```bash
# Check timer status
ssh root@${HOST} "systemctl status cubrim-loop.timer"

# Check last iteration log
ssh root@${HOST} "journalctl -u cubrim-loop --no-pager -n 50"

# Check run log
ssh root@${HOST} "tail -5 /opt/cubrim/repo/datarim/cubrim-run-log.jsonl | jq ."

# Check leaderboard
ssh root@${HOST} "python3 -c \"
import json
lb = json.load(open('/opt/cubrim/repo/documentation/leaderboard/cubrim-leaderboard.json'))
print('Current best:', lb['current_best']['aggregate'])
print('Win target:  ', lb['win_target']['gzip_aggregate'])
\""
```

---

## Kill switch

**Stop the cluster (two commands):**

```bash
ssh root@${HOST} bash -c '
    sudo systemctl stop cubrim-loop.timer cubrim-loop.service
    docker stop cubrim-orchestrator cubrim-worker-a cubrim-worker-b cubrim-worker-c 2>/dev/null || true
'
```

Full kill-switch procedure including emergency options:
`documentation/how-to/stop-the-cubrim-cluster.md`
