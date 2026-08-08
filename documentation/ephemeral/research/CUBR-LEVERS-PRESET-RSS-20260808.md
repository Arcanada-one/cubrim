# Packed-counter decode RSS by preset and file

**State:** COMPLETE — preregistered protocol executed once on 2026-08-08. The
experiment answers the open NEW-30 consequence identified after the stand run:
whether the packed counter's file-dependent decode-RSS increase persists under
the `max`, `balanced`, and `web` presets.

## Result

All 54 measured decodes completed: 3 files × 3 presets × 2 builds × 3
interleaved samples. Every round trip passed, and the baseline/candidate
archives were byte-identical within all nine file/preset pairs. Values below
are medians of the three samples for that exact file, preset, and build; no
corpus aggregate is calculated.

| File | Preset | Baseline decode | Candidate decode | Baseline RSS | Candidate RSS | RSS delta | Mechanism ceiling | Delta / ceiling |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dickens | max | 27.03 s | 20.00 s | 1,543,680 KiB | 1,719,808 KiB | +172.0 MiB (+11.4%) | 768 MiB | 22.4% |
| dickens | balanced | 25.87 s | 19.24 s | 1,486,336 KiB | 1,654,784 KiB | +164.5 MiB (+11.3%) | 736 MiB | 22.4% |
| dickens | web | 22.55 s | 17.22 s | 110,080 KiB | 113,152 KiB | +3.0 MiB (+2.8%) | 46 MiB | 6.5% |
| nci | max | 18.76 s | 15.70 s | 1,430,016 KiB | 1,710,080 KiB | +273.5 MiB (+19.6%) | 768 MiB | 35.6% |
| nci | balanced | 18.07 s | 15.09 s | 1,385,984 KiB | 1,644,544 KiB | +252.5 MiB (+18.7%) | 736 MiB | 34.3% |
| nci | web | 15.75 s | 13.41 s | 107,520 KiB | 111,616 KiB | +4.0 MiB (+3.8%) | 46 MiB | 8.7% |
| ooffice | max | 25.58 s | 18.99 s | 1,635,328 KiB | 1,708,544 KiB | +71.5 MiB (+4.5%) | 736 MiB | 9.7% |
| ooffice | balanced | 25.40 s | 18.95 s | 1,635,840 KiB | 1,708,032 KiB | +70.5 MiB (+4.4%) | 736 MiB | 9.6% |
| ooffice | web | 22.24 s | 16.93 s | 112,640 KiB | 115,200 KiB | +2.5 MiB (+2.3%) | 46 MiB | 5.4% |

The preregistered prediction **passes on every file**. Each `web` delta is
below 64 MiB and smaller than the same file's delta under both uncapped
presets. This supports the packed-page explanation as sufficient for the
observed preset dependence: capping the table exponent at 20 sharply limits
the extra committed counter pages. It does not establish one general RSS
percentage across files. Encode RSS was not measured and remains
inconclusive.

The archived header inspection establishes the ceiling used in each row.
`dickens` and
`nci` selected the optional column model under `max` (24 tables, 768 MiB);
their `balanced` archives selected the 23-table base model. `ooffice` selected
BCJ-wrapped base CM2 under both uncapped presets (23 tables, 736 MiB). Every
`web` archive declares `tbits=20` and uses the 23-table base model (46 MiB).

## Execution and evidence

- Systemd unit: `cubr-preset-rss-20260808.service`; result `success`, exit 0.
- Admission/start-of-run log: `2026-08-08T08:26:48Z`; completion stamp:
  `2026-08-08T09:15:13Z`.
- Admission load average: 0.24; post-run load average: 1.37.
- Unit peak memory: 1.9 GiB; swap peak: 0 B.
- TSV: 55 lines including the header; SHA-256
  `8c58098bd669855f3d50ef2dc5c89d2b05d3e90cec0696db2a5eeadca805659a`.
- Public redacted log: 68 lines; SHA-256 recorded in `SHA256SUMS`. Broad
  process snapshots remain only in access-controlled stand evidence.
- Completion stamp SHA-256:
  `b5592083d48c125e2ea563340b0fc23b9591559607b1d188cf2e71c4d0d7ecc3`.

Public evidence: [`preset-rss.tsv`](CUBR-LEVERS-PRESET-RSS-20260808/preset-rss.tsv),
[`preset-rss.public.log`](CUBR-LEVERS-PRESET-RSS-20260808/preset-rss.public.log),
[`DONE.STAMP`](CUBR-LEVERS-PRESET-RSS-20260808/DONE.STAMP),
[`systemd-show.public.txt`](CUBR-LEVERS-PRESET-RSS-20260808/systemd-show.public.txt),
and [`archive-model-inspection.txt`](CUBR-LEVERS-PRESET-RSS-20260808/archive-model-inspection.txt).
Checksums are in
[`SHA256SUMS`](CUBR-LEVERS-PRESET-RSS-20260808/SHA256SUMS).

## Scope and comparison

- **Baseline:** `e70d1cdca6226e994c0393149e364f252f7c0a1f`, the `main`
  tree immediately before PR #41. It already contains all three presets.
  Stand-built binary SHA-256:
  `a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd`.
- **Candidate:** `49e429e58722f730c4f3cbb0a69731fec430bb56`, containing
  PR #41's packed counter and PR #42's exact reciprocal multiply. Stand-built
  binary SHA-256:
  `12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c`.
- **Files:** the existing SHA-verified 2 MiB Silesia slices `dickens`, `nci`,
  and `ooffice`. Every conclusion remains per-file; there is no corpus mean.
- **Presets:** `max`, `balanced`, and `web`. Both binaries expose all three
  with identical CLI meanings. `max` and `balanced` derive `tbits=24` on these
  slices; `web` caps the exponent at 20 and disables column variants.
- **Host:** quiet `dev-ai` stand, CPUs pinned to 0–15, with
  `CUBR_THREADS=RAYON_NUM_THREADS=OMP_NUM_THREADS=4`.

This is a focused decode-RSS experiment, not a restart of the completed pinned
campaign. It does not touch `decode()`, the wire format, encoder defaults,
`cube_size_limit`, `cm_should_try`, or the existing profiler counters.

## Ceiling before measurement

The old `Ctr` allocated a non-zero two-byte `t` slot plus zero-filled one-byte
`c` and `st` slots. The packed layout writes one non-zero four-byte value for
every slot. The maximum newly committed counter storage is therefore two bytes
per active counter slot. The default model has 23 counter tables:

- `tbits=24`: `2 * 23 * 2^24` = **736 MiB**.
- `tbits=20`: `2 * 23 * 2^20` = **46 MiB**.

If a `max` archive selects the optional column model, its 24-table ceiling is
768 MiB. These are allocation-mechanism ceilings, not predicted process RSS;
the measured process also contains unchanged maps, mixers, allocator metadata,
and fixed overhead.

## Falsifiable prediction

1. Baseline and candidate archives are byte-identical within every
   file/preset pair, and every decode round-trips byte-exactly.
2. For each file, the candidate-minus-baseline absolute decode-RSS increase
   under `web` is smaller than under both uncapped presets and does not exceed
   **64 MiB** (46 MiB mechanism ceiling plus an explicit 18 MiB process-noise
   allowance). A `web` delta above 64 MiB refutes the packed-page explanation
   as sufficient on that file.
3. No ordering is predicted between files and no encode-RSS trend is tested.

The result table states each observed delta as a fraction of the applicable
ceiling. A small fraction is a finding, not a failed experiment.

## Gates and protocol

Before measurement:

- Candidate release suite: 320 passed, 0 failed, 11 ignored; every integration
  suite passed on the exact code tree.
- Baseline release suite: 319 passed, 0 failed, 11 ignored; every integration
  suite passed. The one-test difference is PR #42's later reciprocal-domain
  test.
- Refuse admission at load average 1 minute >= 2.0 or when another Cubrim
  process exists.
- Verify both binary hashes and all three input hashes exactly.

For each file/preset pair, the tracked runner:

1. compresses once with each build;
2. performs one unmeasured decode warmup per build and checks `cmp`;
3. aborts before measurement unless the baseline/candidate archives are
   byte-identical;
4. runs three interleaved measured decodes per build under GNU `time -v`;
5. checks `cmp` after every observation and records wall time plus peak RSS.

Any failed hash, archive identity, process-admission, command, or round-trip
gate aborts the run. A partial or failed run stays in the stand journal and
does not enter the database. On a complete run, medians—not cherry-picked
rows—may extend existing hypothesis **NEW-30**. `evaluation` remains 0.

Exact runner:
[`CUBR-LEVERS-PRESET-RSS-20260808/preset-rss-run.sh`](CUBR-LEVERS-PRESET-RSS-20260808/preset-rss-run.sh).
