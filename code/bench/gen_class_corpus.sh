#!/usr/bin/env bash
# H-29 class corpus generator (logs / telemetry / columnar) — REAL host data.
# Reproducibility note (like the holdout corpus): absolute bytes are host-dependent
# (/var/log contents, /opt data, journald history). The RELATIVE standing vs
# gzip-9 / zstd-19 and the columnar-transform win are the stable findings.
# Output dir: $1 (default ./classcorpus). DISJOINT from the tuned 10-file leaderboard.
set -u
OUT="${1:-classcorpus}"
mkdir -p "$OUT"

# --- logs (syslog / app / package / build) ---
journalctl --no-pager 2>/dev/null | head -c 524288       > "$OUT/journal.log"
tail -c 524288 /var/log/dr-orchestrate-prod.log 2>/dev/null > "$OUT/app_orchestrate.log"
cat /var/log/dpkg.log 2>/dev/null                        > "$OUT/dpkg.log"
cp /var/log/alternatives.log "$OUT/alternatives.log" 2>/dev/null
head -c 400000 /var/log/toolchain-freshness.log 2>/dev/null > "$OUT/toolchain.log"

# --- columnar / telemetry / record CSV ---
head -c 524288 /opt/paxbt-stand/data/EURCAD/2013.csv 2>/dev/null > "$OUT/forex_tick.csv"
head -c 400000 /opt/paxbt-stand/data/USDCHF/2013.csv 2>/dev/null > "$OUT/forex_usdchf.csv"
head -c 200000 /home/dev/paxbt-monitor/pull/status.csv 2>/dev/null > "$OUT/status_timeseries.csv"
head -c 524288 /home/dev/paxbt-monitor/pull/deals.csv 2>/dev/null > "$OUT/deals_record.csv"

# drop any empty (permission-denied / missing source) files
for f in "$OUT"/*; do [ -s "$f" ] || rm -f "$f"; done
echo "class corpus in $OUT:"; ls -la "$OUT" | awk 'NR>3{print $5"\t"$9}'
