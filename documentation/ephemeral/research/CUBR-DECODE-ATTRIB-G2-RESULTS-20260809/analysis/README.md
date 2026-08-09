# NEW-24 G2 analysis reproduction

`../raw/` is the byte-exact, read-only evidence tree copied from
`dev-ai:/root/cubr-decode-attrib-g2-20260809/` after the one-shot service
terminated successfully. Its 95-entry `SHA256SUMS` excludes only itself and
`TIMING-DONE.STAMP`; the completion marker has SHA-256
`3ab438a6f25f6c9a829ffd750de321c6ed5a9931d73185290b3051a2c3e90d37`.

The committed runner's `perf report` used `--percent-limit 0.3`. The four
files in `full-symbols/` are derived views of those same immutable
`perf.data` files, generated after terminal validation with no new decode:

```text
/usr/bin/perf report -i /root/cubr-decode-attrib-g2-20260809/<cell>/perf.data --stdio --percent-limit 0 --no-children
```

They were generated on `dev-ai` with perf 6.8.12 while the exact recorded
binary remained at `/root/phaseC/cubrim-3a13f48`; its SHA-256 re-read was
`d4b9fc85a242f887fb1a49bd849c35779c48b8fda04480969309f2d0bb0211cb`.
The zero threshold leaves only two-decimal rounding residuals; it does not
create a new measurement.

Run the deterministic reduction and its checks from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python3 documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/test_parse_results.py
PYTHONDONTWRITEBYTECODE=1 python3 documentation/ephemeral/research/CUBR-DECODE-ATTRIB-G2-RESULTS-20260809/analysis/parse_results.py --check
```

`metrics.tsv` contains per-file counters only. `symbols.tsv` contains every
zero-threshold symbol row and its Amdahl ceiling. `predictions.tsv` applies
only preregistered predicates that the evidence can decide. P2, P3 and P5
remain `INDETERMINATE`: no post-run instruction-to-mixer map, miss-stall
formula, exhaustive bucket map, or tie rule was invented.

`systemd-journal.jsonl` is the exact seven-record `journalctl -o json` capture
for the unit. `systemd-terminal.txt` records the terminal service readback and
the systemd warning that `RuntimeMaxSec` is ineffective with `Type=oneshot`.
The runner's independent 14,400-second monotonic budget remained active; the
campaign completed normally in 3,533.695031 seconds and was never restarted.
