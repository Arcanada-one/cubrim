#!/usr/bin/env bash
# bootstrap-host.sh — Idempotent toolchain installer for the Cubrim research cluster host.
#
# Installs: Docker engine + compose plugin, rustup + cargo, python3 + numpy,
#           jq, git, claude (Claude Code CLI), claude-code-router.
#
# Usage:
#   ./bootstrap-host.sh              # full install
#   ./bootstrap-host.sh --dry-run   # print the plan, install nothing
#
# Environment overrides (testing):
#   CUBRIM_BOOTSTRAP_DRYRUN=1       # equivalent to --dry-run
#
# Idempotent: each component is skipped if already present.
# Must be run as root (or with sudo) on a Debian/Ubuntu host.
#
# Kill switch: after provisioning, use systemctl stop cubrim-loop.timer
# and the runbook at docs/how-to/stop-the-cubrim-cluster.md.

set -euo pipefail

# ── constants ────────────────────────────────────────────────────────────────
CLAUDE_CODE_ROUTER_VERSION="1.7.4"
CLAUDE_CODE_ROUTER_URL="https://github.com/musistudio/claude-code-router/releases/download/v${CLAUDE_CODE_ROUTER_VERSION}/claude-code-router-linux-amd64"
CLAUDE_CODE_ROUTER_SHA256="PLACEHOLDER_SHA256_OPERATOR_MUST_VERIFY"

REQUIRED_CORES=4  # reserve this many cores free (ecosystem convention)

# ── argument parsing ─────────────────────────────────────────────────────────
DRY_RUN="${CUBRIM_BOOTSTRAP_DRYRUN:-0}"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) echo "bootstrap-host: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[bootstrap] $*"; }
plan() { echo "[plan]      $*"; }
skip() { echo "[skip]      $* — already present"; }

run_or_plan() {
    # $1 = description; remaining = command
    local desc="$1"; shift
    if [ "$DRY_RUN" -eq 1 ]; then
        plan "$desc"
    else
        log "$desc"
        "$@"
    fi
}

# ── dry-run guard — do NOT execute installs when sourced or in dry-run ───────
main() {
    if [ "$DRY_RUN" -eq 1 ]; then
        log "DRY-RUN mode — printing install plan, executing nothing"
        echo ""
    fi

    # ── host resource check ──────────────────────────────────────────────────
    NPROC=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 0)
    if [ "$NPROC" -gt 0 ] && [ "$NPROC" -le "$REQUIRED_CORES" ]; then
        log "WARNING: host has $NPROC cores; cluster reserves $REQUIRED_CORES — very tight margin."
    fi

    # ── 1. Docker engine + compose plugin ────────────────────────────────────
    if command -v docker >/dev/null 2>&1; then
        skip "docker"
    else
        run_or_plan "install Docker engine + compose plugin" \
            bash -c '
                apt-get update -qq
                apt-get install -y ca-certificates curl gnupg lsb-release
                install -m 0755 -d /etc/apt/keyrings
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
                    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
                echo "deb [arch=$(dpkg --print-architecture) \
                    signed-by=/etc/apt/keyrings/docker.gpg] \
                    https://download.docker.com/linux/ubuntu \
                    $(lsb_release -cs) stable" \
                    > /etc/apt/sources.list.d/docker.list
                apt-get update -qq
                apt-get install -y docker-ce docker-ce-cli containerd.io \
                    docker-buildx-plugin docker-compose-plugin
            '
    fi

    if docker compose version >/dev/null 2>&1; then
        skip "docker compose plugin"
    else
        run_or_plan "enable docker compose plugin" \
            apt-get install -y docker-compose-plugin
    fi

    # ── 2. git ───────────────────────────────────────────────────────────────
    if command -v git >/dev/null 2>&1; then
        skip "git"
    else
        run_or_plan "install git" \
            apt-get install -y git
    fi

    # ── 3. jq ────────────────────────────────────────────────────────────────
    if command -v jq >/dev/null 2>&1; then
        skip "jq"
    else
        run_or_plan "install jq" \
            apt-get install -y jq
    fi

    # ── 4. python3 + numpy ───────────────────────────────────────────────────
    if command -v python3 >/dev/null 2>&1; then
        skip "python3"
    else
        run_or_plan "install python3 + pip" \
            apt-get install -y python3 python3-pip python3-venv
    fi

    if python3 -c "import numpy" 2>/dev/null; then
        skip "numpy"
    else
        run_or_plan "install numpy via pip" \
            pip3 install --quiet numpy
    fi

    # ── 5. rustup + cargo ────────────────────────────────────────────────────
    if command -v cargo >/dev/null 2>&1; then
        skip "cargo/rustup"
    else
        run_or_plan "install rustup (stable toolchain)" \
            bash -c '
                export RUSTUP_HOME=/usr/local/rustup
                export CARGO_HOME=/usr/local/cargo
                curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs \
                    | sh -s -- -y --no-modify-path --default-toolchain stable
                echo "export PATH=/usr/local/cargo/bin:\$PATH" \
                    >> /etc/profile.d/cargo.sh
            '
    fi

    # ── 6. Claude Code CLI ───────────────────────────────────────────────────
    # Installs via npm (the official distribution channel).
    if command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ]; then
        skip "claude CLI"
    else
        if command -v node >/dev/null 2>&1; then
            run_or_plan "install Claude Code CLI via npm" \
                npm install -g @anthropic-ai/claude-code
        else
            run_or_plan "install Node.js LTS then Claude Code CLI" \
                bash -c '
                    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
                    apt-get install -y nodejs
                    npm install -g @anthropic-ai/claude-code
                '
        fi
    fi

    # ── 7. claude-code-router ────────────────────────────────────────────────
    if command -v claude-code-router >/dev/null 2>&1 \
       || [ -x /usr/local/bin/claude-code-router ]; then
        skip "claude-code-router"
    else
        run_or_plan "install claude-code-router v${CLAUDE_CODE_ROUTER_VERSION}" \
            bash -c "
                curl -fsSL -o /tmp/claude-code-router '${CLAUDE_CODE_ROUTER_URL}'
                # OPERATOR: verify SHA-256 before enabling in production:
                # echo '${CLAUDE_CODE_ROUTER_SHA256}  /tmp/claude-code-router' | sha256sum -c
                chmod +x /tmp/claude-code-router
                mv /tmp/claude-code-router /usr/local/bin/claude-code-router
            "
    fi

    # ── 8. systemd environment file for PATH ─────────────────────────────────
    # Ensures /root/.local/bin is in the system PATH so systemd units
    # resolve 'claude' and 'cargo' without a full login shell (PAX lesson).
    run_or_plan "ensure /etc/environment includes /root/.local/bin in PATH" \
        bash -c '
            if ! grep -q "\.local/bin" /etc/environment 2>/dev/null; then
                echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin:/usr/local/cargo/bin" >> /etc/environment
            fi
        '

    # ── 9. create cluster work directory ────────────────────────────────────
    run_or_plan "create /opt/cubrim with correct permissions" \
        bash -c '
            mkdir -p /opt/cubrim
            chmod 750 /opt/cubrim
        '

    # ── summary ──────────────────────────────────────────────────────────────
    echo ""
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Dry-run complete. Components printed above would be installed."
        log "Run without --dry-run (as root) to execute."
        log ""
        log "After install, complete provisioning:"
        log "  1. claude auth login          (interactive — personal subscription)"
        log "  2. Drop real keys into code/cluster/infra/.env"
        log "  3. docker compose -f code/cluster/infra/docker-compose.yml up -d"
        log "  4. sudo systemctl enable --now cubrim-loop.timer"
    else
        log "Bootstrap complete."
        log ""
        log "Next steps:"
        log "  1. claude auth login           (interactive — run once, personal subscription)"
        log "  2. cp code/cluster/infra/.env.example code/cluster/infra/.env"
        log "     # then fill in real API keys"
        log "  3. docker compose -f code/cluster/infra/docker-compose.yml up -d"
        log "  See: docs/how-to/provision-cubrim-cluster-host.md for the full runbook."
    fi
}

# ── entrypoint guard — only execute when run directly, not when sourced ──────
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
