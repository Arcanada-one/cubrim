# Preregistration: decode-time attribution at the world-benchmark operating point

**State:** PREREGISTERED DESIGN — no measurement result is recorded here. This
document commits the cells, instruments, validity gates, and falsifiable
predictions before any profiling run. It proposes **no lever**. Its product is a
map of where decode time goes, with an honest Amdahl ceiling per component, so
that every subsequent speed lever (NEW-24 Fast-CM included) is priced against a
measured budget instead of an assumed one.

## Why this run exists

At the Phase C operating point (metas 36/37/38, code `3a13f48`, cli sha256
`d4b9fc85…0211cb`), Cubrim decode is last of ten archivers. Overall decode
throughput: 0.0866 MiB/s (`max`), 0.0876 (`balanced`), 0.1179 (`web`). The
best cubrim row anywhere in `world_benchmark_timing_aggregate` is 1.71 MiB/s;
the slowest competitor (ppmd) decodes at 25.7 MiB/s. The per-file split at
`max` shows two regimes:

- CM2-decoded files (text/code/database/exe): 0.068–0.11 MiB/s, decode peak RSS
  5.7–12.6 GiB;
- non-CM2 files (image/binary: `mr`, `x-ray`, `sao`): 0.30–1.46 MiB/s, RSS
  ≈90 MiB — the decoder replays one recorded scheme per block.

The speed branch has had two levers total (packed Ctr PR #41, reciprocal
multiply PR #42, jointly 1.16–1.33× decode on the stand record, PR #43).
Before any further lever is proposed, this run characterises where the
remaining cycles go — the same discipline that previously found the
encode-side cost was algorithmic (variant sweeps, candidate races) rather than
where source-reading placed it.

## Mechanism inventory (source-derived, `main` @ 368bc17; decode loop unchanged since 3a13f48 except PR #41/#42/#47 Ctr internals)

Per decoded bit, `cm2_decode` executes serially:

1. **Model probes** (`CmModel::predict_bit`): 12 order + 6 sparse + 1 indirect
   + 4 word = **23 hashed `Ctr` probes**, each a data-dependent random load
   from a `2^tbits`-slot packed `u32` table (512 MiB per table at `tbits=27`)
   plus a `StateMap` load, feeding **2 `stretch` table lookups each** (~46);
   plus 3 match-model inputs.
2. **Mixer**: 5 layer-1 mixers × 51 inputs (dot product) + layer-2 (7-wide):
   ~262 multiply-accumulates in `mix`; the same width again in `update` →
   **~520 MACs/bit**, plus 46 reciprocal-multiply divisions inside `Ctr`/`StateMap`
   updates (PR #42).
3. **APM/SSE**: 2 refines + 2 updates (interpolated table lookups).
4. **Range decoder**: `get_freq` + `decode` + renormalisation (measured 2.0–2.08%
   of the per-bit budget at encode, F12 — the decode analogue is expected similar
   and is measured here, not assumed).
5. **Serial dependency**: bit *t+1*'s partial-byte context `c0` includes bit
   *t*'s decoded value, so consecutive bits cannot overlap; bytes are chained
   through `start_byte`/`end_byte` re-hashing (23 hash computations per byte).

**Derived cycle budget** (arithmetic on DB numbers, not a measurement):
`dickens`/`max` decodes 10,192,446 B in 144.01 s ⇒ ≈1.766 µs/bit ≈ **4,400
cycles/bit at the 2.5 GHz nominal clock** (more at boost). The source
enumerates ≈600–700 arithmetic ops and ≈26 data-dependent random loads per
bit. The gap between ~700 ops and ~4,400+ cycles is the question this run
answers: miss stalls, dependency-chain latency, or cycles outside the loop.

## Cells (per-file figures only — no corpus aggregate will be computed or quoted)

| # | cell | why |
|---|------|-----|
| 1 | `silesia/dickens` × `max` | text, CM2, `tbits=27`, the slow regime's representative |
| 2 | `silesia/xml` × `max` | CM2 at `tbits=26` — same loop, half the table footprint |
| 3 | `silesia/x-ray` × `max` | non-CM2 replay path — the fast-regime contrast cell |
| 4 | `silesia/dickens` × `web` | `tbits=20` (0.1 GiB tables) — table-budget contrast on the same bytes |

Canterbury files are excluded by design (3–4 KB, fixed-overhead-dominated).
`enwik8` is excluded for run-length (>20 min per decode observation) — a void
worth noting, not estimating; its loop is the same CM2 loop as cells 1–2.

## Instruments

- `perf record -F 997 -e cycles` on the decode invocation → per-symbol cycle
  shares (the campaign binary carries 9,629 symbols including the hot types;
  if inlining blurs attribution, `perf annotate` of the containing symbol is
  the fallback and is reported as such).
- `perf stat -d` plus explicit events (cycles, instructions, branches,
  branch-misses, cache-references, cache-misses, dTLB-load-misses,
  page-faults, task-clock) on a separate, unprofiled-instrumentation decode
  of the same archive → IPC, misses/bit, cycles/bit.
- `/usr/bin/time -v` peak RSS per decode (provenance only).

**Environment:** stand `dev-ai` (AMD EPYC 7502P, 64 HW threads), binary
`/root/phaseC/cubrim-3a13f48` (sha256 `d4b9fc85a242f887fb1a49bd849c35779c48…0211cb`
— the exact campaign binary), `CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4
RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4` matching campaign thread semantics.
All runs `taskset -c 16-19` — physical cores 16–19. The measurement
convention pin 0–15 and its SMT siblings 32–47 are untouched: this
characterisation must not perturb the pinned campaign lanes, and shares (not
absolute throughput) are its product. Quiet gate: 1-minute load average < 8.0
immediately before each run, else wait; a cell that cannot run quietly within
the envelope is recorded as a **void in the run journal — never in the DB**.

## Validity gates (per cell; every gate must pass before any number from that cell is read)

- **G1 — canonical archive identity.** The archive freshly produced by the
  campaign binary at the cell's preset is byte-identical (sha256) to the Phase
  C journal's canonical `archive_sha256` for that cell (`journal.max.jsonl` /
  `journal.web.jsonl`). A mismatch fails the cell; nothing is profiled on a
  non-canonical archive.
- **G2 — round-trip.** Every profiled decode's output passes `cmp` against the
  original corpus file AND its sha256 equals `corpus_manifest.tsv`'s
  `orig_sha256`.
- **G3 — instrument overhead sanity.** The perf-record decode wall-clock must
  be within 10% of the plain decode wall-clock taken in the same session on
  the same pin. If it is not, symbol shares are still reported but flagged
  instrument-perturbed, and no cycles/bit figure is quoted from that run.

## Falsifiable predictions (committed before the run)

- **P1 — loop dominance.** On cells 1 and 2, ≥85% of decode cycles attribute
  to the CM2 per-bit machinery (`predict_bit`/`update_bit` and everything they
  call: `Ctr`, `StateMap`, `Mixer`, `Apm`, `Match`, `Logistic`
  stretch/squash), and the range decoder ≤5%.
- **P2 — largest bucket.** `Mixer::mix` + `Mixer::update` together form the
  largest single bucket on cells 1 and 2, predicted 30–50% of decode cycles
  (op-count argument: ~520 of ~700 arithmetic ops per bit).
- **P3 — boundedness fork** (the decision this run exists to make). Predicted,
  extrapolating F10/F14 (which measured only ≤2 MB slices, `tbits≤24`): the
  loop is **not** memory-latency-dominated even at `tbits=27` — IPC ≥ 1.0 and
  the implied miss-stall share < 50% of cycles. Refuted if IPC < 1.0 with
  LLC+dTLB misses per bit high enough to account for ≥50% of the cycle
  budget. The refutation direction flips the lever ranking from
  compute-shaped (SIMD/pruned mixer, fewer models — NEW-24 territory) to
  layout/prefetch-shaped; either outcome is a finding.
- **P4 — contrast cell.** On `x-ray`/`max`, CM2 symbols take ≤10% of decode
  cycles; the recorded-scheme replay path dominates.
- **P5 — preset invariance of shape.** `dickens`/`web` shows the same bucket
  ordering as `dickens`/`max` with every bucket share within ±10 points: the
  preset moves table size, not loop structure. (If P3 is refuted this is
  expected to fail too — the shares would shift toward the model probes at
  `max`.)

## Honest-ceiling clause

Whatever the shares turn out to be, the report states each component's Amdahl
ceiling (`1/(1-share)`) explicitly, including the unflattering ones. A small
fraction is a finding. If a share implies a ceiling below 2× for the flagship
lever direction, that is stated in the summary sentence, not buried.

## Execution envelope

- Per cell: 1 encode (canonical-identity gate), 1 plain decode (baseline wall
  + `time -v`), 2 `perf stat` decodes (agreement check: total cycles within
  ±10% of each other; disagreement → report both, quote neither as singular),
  1 `perf record` decode. Encodes are gates, not measurements — their wall
  time is not reported.
- Budget: ≤4 h stand wall-clock total. Per-step timeout: 3× the DB-derived
  expected duration; a timeout voids the cell to the journal.
- Stop rule: a failed gate fails the cell; no substitution of files or
  presets. Voids and failures are reported as such.

## DB semantics

This characterisation writes **no** DB rows. `hypotheses` row NEW-24 is set to
`in_progress` when the run starts (it is the open speed-branch hypothesis this
groundwork serves), and its `measure_note` gains a one-line pointer to the
results report when it lands. `evaluation` tables are untouched. No throughput
number from a pinned-to-4-cores profiling run is ever written to
`world_benchmark_*`.
