# A Phase A run that passes every check and must not be published

2026-08-12, arcana-devs, corpus v3, runner
`evidence/CUBR-0074-phase-a-v3-runner-20260812` (`10d9964`).

`phase-a.json` here is a complete, valid Phase A bundle: 1950 trials, zero
voids, 1950/1950 round trips byte-exact, thirteen real-world samples, the five
Phase A presets. It passes `summarize.verify_bundle` and it is accepted by
`parseWebBenchmarkBundle` on the fixed `cubrim-api` contract.

**It is kept as a counter-example, not as a result. Do not publish it.**

The host was admitted at **0.667** load per CPU and then ran for 468 s while CI
work pushed arcana-devs to **2.13** against a 1.0 ceiling. Admission was
evaluated once, before the first trial, so the bundle records `accepted: true`
beside the pre-ramp figure and nothing downstream disagrees.
`host-load-samples.txt` is an independent record of the ramp, sampled from
`/proc/loadavg` from outside the run.

`load-drift.json` is `bench/web-benchmark/load_drift.py` over this bundle:

| | median last/first | p90 | cells past +25% |
|---|---|---|---|
| compression duration | 1.2048 | 1.480 | 24 / 65 |
| decompression duration | 1.2304 | 1.590 | 29 / 65 |

and `cells_with_varying_compressed_bytes: 0` — across all 1950 trials the
compressed size is identical within every one of the 65 sample/codec cells.

That contrast is the whole point. **Density is a property of the codec and the
bytes; a timing is a statement about the host.** The same run is simultaneously
publishable on one axis and worthless on the other, which is why the two cannot
share one gate — and why "re-run on a quiet host" is not a scheduling
preference but a correctness condition for half the table.

The runner now re-reads load every 25 trials and aborts when it passes the
ceiling it was admitted under (Arcanada-one/cubrim#194), so a later run cannot
produce this artefact silently again.
