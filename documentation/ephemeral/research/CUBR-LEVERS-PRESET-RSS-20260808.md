# Preregistration: packed-counter decode RSS by preset and file

**State:** PREREGISTERED — no measurement has run and this file contains no
results. The experiment answers the open NEW-30 consequence identified after
the stand run: whether the packed counter's file-dependent decode-RSS increase
persists under the `max`, `balanced`, and `web` presets.

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
- **Host:** quiet `dev-ai` / `162.55.81.5`, CPUs pinned to 0–15, with
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

The final report will state each observed delta as a fraction of the applicable
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
