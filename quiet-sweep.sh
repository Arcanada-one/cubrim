#!/usr/bin/env bash
# Run the CUBR-0087 memory/throughput sweep, but only on a quiet host.
#
# The sweep's whole purpose is a timing comparison across CM2 table sizes. On a
# contended host the rows differ by scheduling noise rather than by the variable
# under test — and because the full-footprint row runs first, falling background
# load would make every small-table row look faster for a reason that has nothing
# to do with the tables. That would manufacture support for the hypothesis, which
# is the same class of error as widening a CPU pin to pass a quiet-host gate.
# So it waits instead of racing.
#
# Usage: quiet-sweep.sh <scratchpad-dir> [load-threshold]
set -uo pipefail
SP="${1:?scratchpad dir}"
THRESHOLD="${2:-6.0}"

quiet() {
    local l
    l=$(awk '{print $1}' /proc/loadavg)
    awk -v l="$l" -v t="$THRESHOLD" 'BEGIN{exit !(l < t)}'
}

# Any cubrim encode/decode anywhere on the box — including a sibling session's —
# disqualifies the host. Matching on the binary name rather than on a script name
# also avoids the pkill/pgrep self-match trap that killed the first attempt at
# this script: a pattern that appears in this script's own command line matches
# this script.
busy() {
    pgrep -x cubrim >/dev/null && return 0
    pgrep -f "cargo build" >/dev/null && return 0
    return 1
}

waited=0
while busy || ! quiet; do
    sleep 30
    waited=$((waited + 30))
    if [ $((waited % 600)) -eq 0 ]; then
        echo "still waiting: load=$(awk '{print $1}' /proc/loadavg) busy=$(pgrep -x cubrim >/dev/null && echo yes || echo no) after ${waited}s"
    fi
    if [ "$waited" -ge 14400 ]; then
        echo "GAVE UP after ${waited}s: host never went quiet. Sweep NOT run — no timing numbers rather than bad ones."
        exit 2
    fi
done
sleep 60
echo "host quiet (load=$(awk '{print $1}' /proc/loadavg)) after ${waited}s wait; starting sweep"

export BIN="$SP/cubrim-sweep" OUT="$SP/sweep" CPUSET=0-7
for f in dickens.2m ooffice.2m; do
    FILE="$SP/corpus/$f" /home/dev/.worktrees/cubrim/CUBR-0087/sweep.sh
done
echo CHAIN-SWEEP-COMPLETE
