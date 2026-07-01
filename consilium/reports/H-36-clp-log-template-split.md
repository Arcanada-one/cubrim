# H-36 — CLP-style log-template / variable split

**Status:** NO-GO (spike gate not met). No Rust parser written — the mandatory
Python-spike gate (≥1.5× over zstd-19 on real syslog BEFORE any Rust) was not cleared.

**Class targeted:** operational LOG files (syslog/journal, build, package) — the class-C
files Cubrim still loses to zstd-19 after H-30/H-31 (journal +5.8%, toolchain +9.4%,
dpkg +8.0%).

## Hypothesis

Parse each log line into (template, variables): a static skeleton (digit-bearing tokens
→ placeholder) with a template-id per line, and the variable values grouped **columnar**
by (template-id, variable-position); delta-code monotone numeric variable columns and
the leading timestamp. Compress each stream separately. CLP reports ~2.16× over zstd on
its corpus; this would flip the log losses to wins if it reaches the gate.

## Spike (faithful, fully charged — `probe_h36_log_template.py`)

Every decoder stream is a charged cost term (Gotcha #6): template dictionary,
template-id stream, columnar variable blob (with H-31 delta on monotone numeric
columns), and a timestamp-delta stream. Each stream is compressed by the **real cubrim
binary** (`--value-scheme bwt-rans`); total + a charged framing estimate is compared to
zstd-19 on the raw file. Corpus: the real H-29 class corpus (`gen_class_corpus.sh`).

| file (corpus) | raw | zstd-19 | CLP | CLP+ts-delta | best ×/zstd | gate ≥1.5× |
|---|---:|---:|---:|---:|---:|---|
| **journal.log (real syslog)** | 524288 | 18688 | 16089 | **14507** | **1.29×** | ❌ below |
| toolchain.log | 369191 | 27548 | 26274 | 26274 | 1.05× | ❌ below |
| dpkg.log | 109041 | 6764 | 7094 | 7094 | 0.95× (loses) | ❌ below |
| app_orchestrate.log | 524288 | 23218 | 15749 | 15749 | 1.47× | ❌ below |

(toolchain/dpkg/app timestamps are bracketed / space-separated / line-prefixed and were
not delta-extracted by the spike's leading-timestamp regex; even with perfect timestamp
delta, journal — the real syslog — caps at 1.29×: its residual is the template
dictionary 5367 B + high-entropy variables 7040 B (pids / hex addresses), neither of
which compresses into 1.5× territory.)

## Verdict

**NO-GO under the operator's gate.** The real syslog (`journal.log`) reaches **1.29×**
over zstd-19 with the full CLP lever set (template split + columnar variables + timestamp
delta) — short of the mandatory **1.5×** Rust-justification threshold. No log-parser
Rust was written, per the gate.

**Honest nuance / operator decision point:** the CLP transform *does* beat zstd-19 on
3/4 logs (journal 14507 < 18688 = 1.29×, app_orchestrate 15749 < 23218 = 1.47×,
toolchain 26274 < 27548 = 1.05×) — a MODE_LOG would *flip those class losses to wins* —
but only `dpkg.log` *loses* (0.95×) and none clear 1.5×. So there is a strategic choice:
- **Hold the 1.5× gate** → NO-GO stands; the log sub-class is at its practical ceiling for
  the template-split lever (the variable entropy floor — pids/addresses — is data-determined).
- **Relax the gate to "beat zstd-19"** → a MODE_LOG parser becomes justified (it would win
  journal/toolchain/app, ~1.05–1.47×), accepting the large parser cost for a 1.0–1.5×
  margin and a dpkg loss. This is the operator's call; the spike numbers above are the
  honest basis.

**Code SHA:** spike run on `6f76826` (feat/cubr-bigfiles). Leaderboard untouched, NOT pushed.
