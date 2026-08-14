# CUBR-0075 memory-rss result — 2026-08-14

Scope: the preregistered `memory-rss` axis only. This result does not evaluate
allocator telemetry (`bounded-state`), ARM-native execution, hostile streams,
streaming performance, profile trade-offs, density, or the parent CUBR-0072
decision.

## Frozen provenance

- Source commit: `1412a0d542baa1a550bbae210e4162ee2c567a7e`
- Probe: `memory_rss_probe`, SHA-256
  `dfad849711e08666c8e6d61653c56e6ef0680139a56b3fdf02c06286d925b4a2`
- Manifest SHA-256:
  `83ece3e3d5edad7bb74778d44de5cfa9a9b97d639b70d099edd0bd15059ffd30`
- Staged bundle SHA-256:
  `b7462192fb20251dba05f74945f48e5f5ab45f63fbd2ee4a71cba49cabc5778d`
- Local evidence directory:
  `/home/dev/evidence/CUBR-0075-MEMORY-RSS-20260814/`

The run used the deterministic CUBR-0075 cube ladder (4–64 KiB) and raw-store
ladder (1–128 MiB), seed `75075`, three warmups, and 30 measured trials per
cell: 13 cells and 390 measured trials total. Host admission pinned the
measurement processes to CPU 0 on `arcana-devs` (16 logical CPUs), with
load-per-CPU `0.398773193359375` and maximum sampled temperature `75°C`.

Each measured trial was a fresh process. GNU `/usr/bin/time -v` recorded that
process's maximum resident set size; the measured scope includes the input
payload, constructed frame, decoder state, and decoded output. The Rust probe
also recorded real encode/decode clocks and required SHA-256 plus byte equality
for every round trip. All 390 trials passed the exact round-trip gate.

## Result

The preregistered ordinary-least-squares fit over the 13 per-cell median RSS
values was:

```text
peak_rss_bytes = 2.986062002220198 * decoded_bytes + 4137055.9639226347
R² = 0.999778446544615
```

| Preregistered criterion | Observed | Satisfied |
|---|---:|---|
| GO `rss_slope <= 2.5` | `2.986062002220198` | no |
| GO `rss_intercept <= 16777216` | `4137055.9639226347 B` | yes |
| WIN `rss_slope <= 1.5` | `2.986062002220198` | no |

Verdict: **NO-GO** for `memory-rss`. The database publication is a separate
guarded API operation; this report does not imply that it has happened.

The result is evidence for the current whole-process protocol, not a claim
that the decoder's retained allocator state alone has this slope. The already
published allocator telemetry remains a separate bounded-state slice, and the
remaining CUBR-0075 dependencies stay explicitly open.
