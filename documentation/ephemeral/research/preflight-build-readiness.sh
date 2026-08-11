#!/usr/bin/env bash
# Build-readiness probe for one-shot experiment plans.
#
# Why this exists
# ---------------
# Two experiments died on environment defects unrelated to their hypotheses:
#
#   NEW-24 G6  froze a SHA-256 of a Cargo.lock it regenerated against the live
#              crates.io index; three crates published mid-flight and moved the
#              hash. Prebuild allowance consumed, non-retryable.
#   H-33       froze `cargo build --offline --locked` as its only permitted
#              build, on a tree where Cargo.lock was gitignored. Measured
#              exit 101 before a single crate compiled.
#
# Both share one cause: a one-shot plan asserted an unverified precondition
# about state the repository does not fix. The durable separation is
#
#     the one-shot property belongs to the MEASUREMENT, never to the
#     ENVIRONMENT CHECK
#
# This probe carries no scientific allowance. Run it a hundred times. An
# experiment plan should cite it as a precondition and spend its allowance only
# on the measurement it was designed for.
#
# It is read-only with respect to the repository: it builds into a caller-chosen
# scratch target directory and never writes to a tracked path.
#
# Usage:
#   preflight-build-readiness.sh [--repo DIR] [--target DIR] [--no-build]
# Exit: 0 = GO, 1 = NO-GO (reason printed), 2 = usage error.

set -uo pipefail
export LC_ALL=C

REPO=""
TARGET=""
RUN_BUILD=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo) REPO=${2:-}; shift 2 ;;
        --target) TARGET=${2:-}; shift 2 ;;
        --no-build) RUN_BUILD=0; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) printf 'usage error: unknown argument %s\n' "$1" >&2; exit 2 ;;
    esac
done

FAILURES=0

no_go() {
    printf 'NO-GO: %s\n' "$*"
    FAILURES=$((FAILURES + 1))
}

ok() {
    printf 'ok: %s\n' "$*"
}

if [[ -z $REPO ]]; then
    REPO=$(git rev-parse --show-toplevel 2>/dev/null) || {
        printf 'NO-GO: not inside a Git repository and --repo was not given\n'
        exit 1
    }
fi
if [[ ! -d $REPO || -L $REPO ]]; then
    printf 'NO-GO: repository root is not a real directory: %s\n' "$REPO"
    exit 1
fi

MANIFEST="$REPO/code/cubrim-rs/Cargo.toml"
LOCK="$REPO/code/cubrim-rs/Cargo.lock"

printf '== build readiness probe ==\n'
printf 'repo: %s\n' "$REPO"
printf 'head: %s\n' "$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"

# 1. The lock must be TRACKED, not merely present. A present-but-untracked lock
#    is exactly the state that let H-33's plan look feasible in a working tree
#    while failing in the fresh checkout the experiment actually uses.
if [[ ! -f $MANIFEST ]]; then
    no_go "manifest is missing: $MANIFEST"
elif [[ ! -f $LOCK ]]; then
    no_go "Cargo.lock is absent; --locked cannot create one"
elif ! git -C "$REPO" ls-files --error-unmatch -- code/cubrim-rs/Cargo.lock >/dev/null 2>&1; then
    no_go "Cargo.lock exists but is UNTRACKED; a fresh checkout will not have it"
else
    ok "Cargo.lock is tracked"
fi

# 2. Toolchain must resolve and be reported, so a plan can pin against fact.
# Resolve cargo without assuming an interactive PATH: a probe that reports
# "cargo missing" on a host that has cargo is a probe nobody will trust.
if [[ -n ${CARGO_BIN:-} ]]; then
    :
elif command -v cargo >/dev/null 2>&1; then
    CARGO_BIN=cargo
elif [[ -x ${CARGO_HOME:-$HOME/.cargo}/bin/cargo ]]; then
    CARGO_BIN=${CARGO_HOME:-$HOME/.cargo}/bin/cargo
else
    CARGO_BIN=cargo
fi
if ! command -v "$CARGO_BIN" >/dev/null 2>&1 && [[ ! -x $CARGO_BIN ]]; then
    no_go "cargo not found (looked on PATH and in \${CARGO_HOME:-\$HOME/.cargo}/bin)"
else
    ok "cargo: $("$CARGO_BIN" --version 2>&1)"
    RUSTC_BIN=${RUSTC_BIN:-}
    if [[ -z $RUSTC_BIN ]]; then
        if command -v rustc >/dev/null 2>&1; then
            RUSTC_BIN=rustc
        elif [[ -x ${CARGO_HOME:-$HOME/.cargo}/bin/rustc ]]; then
            RUSTC_BIN=${CARGO_HOME:-$HOME/.cargo}/bin/rustc
        fi
    fi
    if [[ -n $RUSTC_BIN ]]; then
        ok "rustc: $("$RUSTC_BIN" --version 2>/dev/null)"
    else
        no_go "rustc not found (looked on PATH and in \${CARGO_HOME:-\$HOME/.cargo}/bin)"
    fi
fi

# 3. Lock/manifest agreement, without touching the network or the tree.
#    `--locked --offline` on a metadata query fails loudly when the lock is
#    stale relative to the manifest -- the drift that silently breaks a frozen
#    build array long after review.
if [[ -f $LOCK && -f $MANIFEST ]] && { command -v "$CARGO_BIN" >/dev/null 2>&1 || [[ -x $CARGO_BIN ]]; }; then
    if "$CARGO_BIN" metadata --locked --offline --format-version 1 \
        --manifest-path "$MANIFEST" >/dev/null 2>/tmp/preflight-meta.$$; then
        ok "lock is in sync with the manifest"
    else
        no_go "lock/manifest disagree or crates are missing from the cargo cache: $(tail -1 /tmp/preflight-meta.$$ 2>/dev/null)"
    fi
    rm -f /tmp/preflight-meta.$$
fi

# 4. The real thing. `--offline` needs the BYTES of every locked crate in
#    $CARGO_HOME; that is a property of the machine, not of the commit, so no
#    merge can carry it. This is the check that cannot be replaced by reasoning.
if [[ $RUN_BUILD -eq 1 ]]; then
    if [[ -z $TARGET ]]; then
        TARGET=$(mktemp -d "${TMPDIR:-/tmp}/preflight-target.XXXXXX")
        CLEAN_TARGET=1
    else
        CLEAN_TARGET=0
    fi
    printf 'building (offline, locked) into %s ...\n' "$TARGET"
    if CARGO_TARGET_DIR="$TARGET" "$CARGO_BIN" build --offline --locked --release \
        --manifest-path "$MANIFEST" >/tmp/preflight-build.$$ 2>&1; then
        ok "offline --locked release build succeeded"
    else
        no_go "offline --locked release build FAILED: $(tail -3 /tmp/preflight-build.$$ | tr '\n' ' ')"
        printf 'hint: if this reports a download in offline mode, run\n'
        printf '      cargo fetch --locked --manifest-path %s\n' "$MANIFEST"
        printf '      out of band, online, BEFORE spending any one-shot allowance.\n'
    fi
    rm -f /tmp/preflight-build.$$
    [[ ${CLEAN_TARGET:-0} -eq 1 ]] && rm -rf "$TARGET"
else
    printf 'skip: build not run (--no-build)\n'
fi

printf '== result ==\n'
if [[ $FAILURES -eq 0 ]]; then
    printf 'BUILD_READINESS=GO\n'
    exit 0
fi
printf 'BUILD_READINESS=NO-GO failures=%d\n' "$FAILURES"
exit 1
