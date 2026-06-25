---
task_id: CUBR-0028
artifact: plan
schema_version: 1
captured_at: 2026-06-20
captured_by: /dr-plan
agent: planner
complexity: L2
prd_status: waived
parent_init_task: ../../../../datarim/tasks/CUBR-0028-init-task.md
expectations: ../../../../datarim/tasks/CUBR-0028-expectations.md
baseline_t4_aggregate: 0.587240
go_threshold_aggregate: 0.575495
code_sha_at_plan: 15b0ba6
---

# CUBR-0028 — Next-axis value-stream research — Implementation Plan

> **L2 spike-research, PRD waived.** Spike-gated by the CUBR-0023/0025/0026 template:
> Python probe first with the FULL wire-cost model (Gotcha #6), explicit GO/NO-GO
> against a −2% aggregate threshold, Rust touched ONLY on a GO. This plan produces
> probes and a verdict — it does **not** write Rust or run any probe (that is `/dr-do`).

## Overview

### Problem
The value-stream optimum for the 7-file corpus is **T4 (order-1 per-code Huffman,
i-order)** at **aggregate ratio 0.587240** (verified: `sum(actual_t4_bytes)=30217 /
sum(size_bytes)=51456` from `docs/ephemeral/research/corpus/manifest.json`). Three
prior axes that stayed within the order-1-key context-depth dimension all returned
NO-GO at implementation:

| Axis | Task | Verdict |
|------|------|---------|
| R4 RLE-prepass | CUBR-0023 | NO-GO |
| R5 grouped-context | CUBR-0025 | NO-GO |
| R6 order-2 context-key | CUBR-0027 | NO-GO (false-GO 0.547730 → real 0.592215, Gotcha #6) |

Hypothesis-log H-12 concludes: **order-1 key context-depth is exhausted.** This task
switches to an axis **orthogonal** to context-depth.

### Goal
For each of the three orthogonal axes named in the operator brief, run a Python-first
probe with a full wire-cost model and a hard GO/NO-GO gate. **GO only if the modelled
aggregate ratio is ≤ 0.575495** (= 0.587240 × 0.98, i.e. ≥2% better than T4). In byte
terms over this corpus that is an absolute budget of **≤ 29612 compressed bytes** (vs
the current 30217 — a candidate must net-save ≥ 605 bytes after charging every
decoder branch).

### The three orthogonal axes (verbatim from the brief)
1. **distance-map** — currently ~0% contribution; lever ONLY if the corpus gains
   sparse inputs ρ<0.3 (Gotcha #1).
2. **BWT-style reordering of the value stream** — builds its own locality, separate
   from phi-coordinates; explicitly NOT phi-sort (Gotcha #3).
3. **corpus-specific pre-processing** — byte-level transforms reducing `n_distinct`
   before Huffman.

### Non-goals
- No fourth order-N context-key variant (that dimension is closed — H-12).
- No phi-coordinate reordering / axis-sort (Gotcha #3 already disproved it: CUBR-0018).
- No Rust on a NO-GO. No production deploy. No corpus mutation that silently shifts
  the T4 baseline (Gotcha #1).

## Architecture Impact

- **Scope:** research artefacts only, all under
  `/Users/ug/arcanada/Projects/Cubrim/docs/ephemeral/`. No change to
  `code/cubrim-rs/` unless a probe returns GO.
- **Reused infrastructure (do NOT rebuild):**
  - `code/bench/entropy_traversal_probe.py` — canonical order-1 conditional-entropy
    probe. Reuse `build_value_codes(data)->np.ndarray`,
    `cond_entropy_h1(seq, n_distinct)->float`, `verdict(rows, threshold)->(go_str, rationale)`.
  - `code/bench/run_bench.py` — full round-trip + per-file `cubrim_ratio = cubrim_size/size`
    harness (cubrim-rs encode/decode, sha256 round-trip, zstd/brotli). Note: it stores
    **per-file** ratios; the **aggregate** is `sum(cubrim_bytes)/sum(size)` and must be
    computed in the spike (the value 0.587240 is reproduced this way).
  - `code/bench/entropy_ndim_probe.py` — precedent for a per-axis probe
    (`run_length_stats`, `process_file(entry, n_list, b)`, `verdict_check`).
- **Two probe families:**
  - *Entropy probe* (axes 2, 3) — reuses `cond_entropy_h1`; the entropy result is the
    cheap pre-gate (Gotcha #3). An entropy drop is necessary but **not sufficient** —
    the modelled aggregate-bytes gate is the binding GO/NO-GO.
  - *Size-model probe* (all axes) — the new code: a `size_model_*()` function per axis
    that returns one cost term per decoder branch and produces a modelled aggregate
    ratio comparable to 0.587240. This is where Gotcha #6 lives.

### Wire-cost contract (Gotcha #6 — baked into every axis)
T4's `actual_t4_mode` is already per-file `min(raw, cube)` — the live decoder ALREADY
has a 2-branch fallback (raw | cube). Any new scheme **adds** branches and every added
branch MUST carry a cost term. The contract for each axis's `size_model_*()`:

1. Write the wire-format spec as an explicit list of `decode` branches
   (`branches = [...]`) in the probe's docstring.
2. Assert `len(cost_terms) == len(branches)` at runtime (probe aborts with a loud
   error otherwise — this is the literal CUBR-0026 root-cause guard: 3 branches, 2
   terms → false GO).
3. Charge the per-file **mode/header selector byte(s)** for choosing among branches.
4. The modelled aggregate = `sum_over_files( min(charged_branch_bytes) ) / sum(size_bytes)`.

## Implementation Steps

> All steps are `/dr-do` work. This plan only specifies them. Each probe ≤ ~100 LoC,
> reuses the bench template, writes its report to
> `docs/ephemeral/research/CUBR-0028-<axis>-probe-report.md` and a machine row to
> `docs/ephemeral/research/CUBR-0028-<axis>-probe.json` carrying `code_sha`
> (`git rev-parse HEAD`) per the Cubrim "bench results carry their code SHA" rule.

### Sequencing rationale (probe-first ordering)
Order chosen by **cheapest signal × highest expected lever**, and to avoid wasted
effort on a likely NO-GO:

1. **Axis 3 — corpus pre-processing (byte-level transforms)** — FIRST.
   *Why first:* highest expected lever and cheapest signal. The aggregate is dominated
   by the four `raw`-mode files (`dense`, `random_high`, `binary_mixed`, `sparse_small`
   = 16692 of 30217 T4 bytes, ratio ≈ 1.0) where the cube/Huffman path loses to raw
   storage. A pre-transform that reduces `n_distinct` before Huffman is the only axis
   with a plausible path to move those files below ratio 1.0. The probe is a pure
   entropy + size-model computation, no corpus change.

2. **Axis 2 — BWT-style value-stream reordering** — SECOND.
   *Why second:* medium lever, medium cost. BWT builds its own locality (NOT phi-sort,
   Gotcha #3), so it could lower order-1 conditional entropy on the `cube`-mode files
   (`text`, `log_like`, `sparse_clustered`). But it adds an inverse-BWT primary-index
   per file to the wire format (a branch + cost term, Gotcha #6), which eats into any
   entropy gain on small files.

3. **Axis 1 — distance-map** — LAST, expected NO-GO, called out so `/dr-do` does not
   waste effort.
   *Why last / why likely NO-GO:* per Gotcha #2 the distance-map carries ~0% because
   coordinates are positional (i-order), so gaps collapse to a handful of bytes while
   the value stream is 99%+ of output. Gotcha #1's lever (sparse inputs ρ<0.3) is only
   reachable by **adding** sparse inputs to the corpus — which **changes the baseline**
   and breaks the 0.587240 comparison. The plan does NOT silently mutate the corpus.
   If `/dr-do` wants to exercise this axis it MUST use a **separate, clearly-labelled
   corpus** (`docs/ephemeral/research/corpus-sparse/`) and report per-file deltas only,
   never fold the result into the 7-file aggregate. Most likely outcome: documented
   NO-GO on the canonical corpus (consistent with Gotcha #1), with the sparse-corpus
   experiment as an optional Class-B follow-up rather than a GO.

### Step 1 — Axis-3 probe: `code/bench/preproc_n_distinct_probe.py`
- Reuse `build_value_codes`, `cond_entropy_h1`, `verdict` from `entropy_traversal_probe.py`.
- Candidate transforms (each invertible — round-trip is the gate): delta/XOR-prev
  byte coding, MTF (move-to-front), and a stride-2 split — chosen because they target
  `n_distinct` reduction without context-depth.
- For each file: compute pre/post `n_distinct`, pre/post `cond_entropy_h1`, and the
  size-model bytes.
- **Wire-format branches** (declare + assert one cost term each): `[raw, cube_huffman,
  preproc_huffman]` + a per-file 1-byte mode selector. → 3 branches + selector ⇒ 4
  cost terms. Assert `len(cost_terms) == 4`.
- Modelled aggregate = `sum_over_files(min(raw_bytes, cube_bytes, preproc_bytes) +
  selector) / 51456`. GO iff ≤ 0.575495.

### Step 2 — Axis-2 probe: `code/bench/bwt_reorder_probe.py`
- Apply a bounded-block BWT to the i-order value stream (NOT phi-sort). For each file:
  `cond_entropy_h1` of the BWT-transformed stream vs i-order baseline.
- Entropy pre-gate: if BWT does not reduce `cond_entropy_h1` on any file, NO-GO
  immediately (skip the size model — Gotcha #3 gate).
- **Wire-format branches:** `[raw, cube_huffman, bwt_huffman]` + per-file BWT
  primary-index (`ceil(log2(L))` bits) + 1-byte mode selector ⇒ 3 branches + index +
  selector = 5 cost terms. Assert `len(cost_terms) == 5`. The primary-index cost is the
  branch CUBR-0026-style omissions would drop — charge it explicitly.
- Modelled aggregate = `sum_over_files(min(raw, cube, bwt_huffman+index+selector)) /
  51456`. GO iff ≤ 0.575495.

### Step 3 — Axis-1 probe: `code/bench/distance_map_sparse_probe.py` (expected NO-GO)
- On the **canonical** corpus: confirm (do not re-derive) that the distance-map term
  is byte-trivial → contributes ~0% → NO-GO on the aggregate. Report the actual
  distance-map byte count per file as evidence.
- Optional sparse experiment: ONLY if `/dr-do` builds
  `docs/ephemeral/research/corpus-sparse/` with ≥1 ρ<0.3 input and a `manifest.json`
  of its own. Report **per-file** ratio deltas on that separate corpus; do NOT compute
  a cross-corpus aggregate against 0.587240 (Gotcha #1 — the comparison would be
  invalid). This branch produces a labelled side-finding, not a GO against T4.
- **Wire-format branches** (if a sparse scheme is modelled): `[raw, cube_huffman,
  cube_huffman_with_distmap]` + distance-map RLE bytes + selector ⇒ assert one term per
  branch.

### Step 4 — Aggregate verdict + reflection
- Combine the three probe verdicts. If **any** probe returns GO (aggregate ≤ 0.575495
  with a fully-charged size model) → proceed to a Rust implementation step under
  `code/cubrim-rs/` with a lossless round-trip test (Step 5).
- If **all three** are NO-GO → the deliverable is a documented NO-GO at
  `docs/ephemeral/research/CUBR-0028-verdict.md` + follow-up proposals filed as Class B
  in the CUBR-0028 reflection. **No Rust is written, no dangling code** (wish 4).

### Step 5 — Rust implementation (ONLY on a GO; otherwise skipped entirely)
- Implement the winning transform in `code/cubrim-rs/src/` behind the existing
  per-file mode-selection, add a decode branch for the new mode, add the cost term to
  the real size accounting.
- Mandatory: `cargo test` lossless round-trip (sha256 in == out) on all 7 files, then
  `run_bench.py` to confirm the **real** aggregate ≤ 0.575495 (guards against a
  CUBR-0026-style model↔real divergence — the real codec must reproduce the modelled
  number within rounding).

## Test Plan (mapped to expectation wish_ids)

| wish_id | Verification step | Where |
|---------|-------------------|-------|
| **orthogonal-axis-not-context-depth** | Each probe report states which orthogonal axis it exercises and why it is not an order-N context-key variant (BWT builds its own locality, not phi-sort; pre-proc reduces `n_distinct`; distance-map is sparse-gap, not context). Verdict doc lists ≥1 of the 3 axes with that rationale. | `CUBR-0028-<axis>-probe-report.md`, `CUBR-0028-verdict.md` |
| **python-spike-full-wire-cost-first** | Each probe is Python, runs before any Rust; each `size_model_*()` asserts `len(cost_terms) == len(branches)` (the Gotcha #6 guard) and the assertion appears in the probe output. No Rust file is added before a Python GO. | probe sources `code/bench/*_probe.py`; `git status` shows no `code/cubrim-rs/` change pre-GO |
| **go-nogo-threshold-vs-t4** | Each report prints the baseline aggregate (0.587240), the candidate modelled aggregate, the absolute delta in % vs 0.587240, and an explicit GO/NO-GO line; GO requires ≤ 0.575495. | `CUBR-0028-<axis>-probe.json` (numbers), `CUBR-0028-verdict.md` (verdict + deltas) |
| **rust-only-on-go** | If all probes NO-GO: `git -C Projects/Cubrim status` shows zero new `code/cubrim-rs/` branches for this task, and the verdict doc records the NO-GO + Class-B follow-ups. If GO: a Rust impl with passing `cargo test` lossless round-trip exists and `run_bench.py` confirms the real aggregate ≤ 0.575495. | `git status`; `cargo test`; `run_bench.py` output |

Evidence types per the expectations file: wish 1 `static`, wish 2 `empirical`,
wish 3 `measurement`, wish 4 `static`.

## Rollback Strategy

Trivial — all artefacts are transient research files under `docs/ephemeral/`, no
production surface, no migration.

- **Probes / reports only (NO-GO path):** `git -C /Users/ug/arcanada/Projects/Cubrim
  checkout -- docs/ephemeral/research/ code/bench/` or simply delete the new
  `code/bench/*_probe.py` and `docs/ephemeral/research/CUBR-0028-*` files. Nothing is
  shipped, nothing deployed.
- **Rust step (GO path only):** all work on a feature branch
  `feat/cubr-0028-<axis>`; rollback = `git checkout main` (branch never merged until
  round-trip + real-aggregate gate pass). No DB, no schema, no deploy to revert.
- **Sparse-corpus experiment (axis 1):** lives in its own
  `docs/ephemeral/research/corpus-sparse/` dir; delete the dir to roll back — the
  canonical 7-file corpus and the 0.587240 baseline are never touched.

## Validation Checklist

- [ ] Aggregate baseline reproduced: `sum(actual_t4_bytes)/sum(size_bytes) = 30217/51456 = 0.587240` (sanity-check before any candidate claim).
- [ ] GO threshold computed and stated: ≤ 0.575495 (≤ 29612 bytes; net-save ≥ 605 bytes).
- [ ] Each probe ≤ ~100 LoC and reuses `build_value_codes` / `cond_entropy_h1` / `verdict` — no rebuild of bench infra.
- [ ] Gotcha #6 guard present in EVERY size model: `branches` list declared + `assert len(cost_terms) == len(branches)` + per-file mode-selector byte charged.
- [ ] Gotcha #3 entropy pre-gate applied to the BWT axis before its size model.
- [ ] Gotcha #1 honoured: distance-map axis does NOT mutate the canonical corpus; any sparse experiment uses a separate labelled corpus and reports per-file deltas only.
- [ ] Probe order is Axis 3 → Axis 2 → Axis 1, with the Axis-1 likely-NO-GO called out so `/dr-do` does not over-invest.
- [ ] Each probe JSON carries `code_sha` (`git rev-parse HEAD`).
- [ ] No Rust touched unless a probe returns GO; on all-NO-GO the deliverable is `CUBR-0028-verdict.md` + Class-B follow-ups, no dangling code.
- [ ] (GO path only) Rust round-trip `cargo test` passes on all 7 files AND `run_bench.py` real aggregate ≤ 0.575495 (model↔real parity guard).
- [ ] All four expectation wish_ids map to a concrete verification artefact (Test Plan table).
