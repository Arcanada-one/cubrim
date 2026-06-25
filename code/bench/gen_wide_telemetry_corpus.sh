#!/usr/bin/env bash
# Wide real-world telemetry corpus (class-wide victory confirmation, H-40 consolidation).
# Real forex tick OHLCV (10 currency pairs) + paxbt trading telemetry + sar system metrics
# + representative generated fixed-interval (prometheus/sensor) + enum events.
# Host-dependent (like holdout/class corpora); relative standing is the stable finding.
# Output dir = $1 (default ./wide_telemetry). Big forex years are sliced to ~512KB.
set -u; OUT="${1:-wide_telemetry}"; mkdir -p "$OUT"
for sym in EURUSD GBPJPY AUDCAD CHFJPY EURGBP NZDUSD USDCAD GBPCHF EURJPY AUDNZD; do
  src="/opt/paxbt-stand/data/$sym/2013.csv"
  [ -f "$src" ] && { head -c 524288 "$src" | head -n -1 > "$OUT/forex_${sym}.csv"; }
done
head -c 524288 /home/dev/paxbt-monitor/pull/status.csv > "$OUT/paxbt_status.csv" 2>/dev/null
cp /home/dev/paxbt-monitor/pull-alfa/status.csv "$OUT/paxbt_alfa_status.csv" 2>/dev/null
sadf -d -- -u -r 2>/dev/null | head -c 300000 > "$OUT/sar_metrics.csv" 2>/dev/null
# generated representatives (see gen_fixedinterval_corpus.py / events.csv recipe)
for f in "$OUT"/*; do [ -s "$f" ] || rm -f "$f"; done
echo "wide telemetry corpus -> $OUT ($(ls "$OUT"|wc -l) files)"
