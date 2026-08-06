# CUBR-0076 — reconciling the dependency rows with CUBR-0075's measured negatives

**Written:** 2026-08-06 UTC.
**Question (operator's fork):** the DB shows dependencies for hypotheses 12–15
at `pending_dependency` while the programme's briefs say dependencies 13 and 14
are "measured negatives with cycle counts". Is that (1) a persistence gap, or
(2) an overstated claim?
**Answer: neither.** The DB is correct as it stands, the CUBR-0075 negatives
are real and committed — and the two record *different statements*. The
mismatch is a scope conflation, and the part of the briefs' phrasing that needs
retracting is retracted below, precisely.

## 1. What `resolution_state = resolved` means — from the schema, not from habit

`web_benchmark_hypothesis_dependency` is a **build-prerequisite tracker**, and
the schema makes any other use impossible:

- `resolution_state` admits exactly two values:
  `CHECK (resolution_state IN ('pending_dependency','resolved'))`.
- `CHECK ((resolution_state = 'pending_dependency') = (resolved_at IS NULL AND
  resolved_by_build_id IS NULL))` — a row can only be `resolved` by naming a
  **registered codec build** (`resolved_by_build_id` FK →
  `web_benchmark_codec_build`).
- `dependency_type` admits only
  `{hardware, instrumentation, api_capability, profile_pair}` — kinds of
  *prerequisite artefact*, not kinds of verdict.

**The worked example (row 5):** `real-world-web-corpus` for hypothesis 11 became
`resolved` at 2026-08-03 03:38 by `resolved_by_build_id = 7` — the registered
`cubrim-lowmem-decode` candidate build. Resolution recorded that *the artefact
the evaluation needs now exists*, nothing more. Hypothesis 11's actual verdict
(density WIN 0.877644 / decode 0.004410) lives in the CUBR-0074 record, not in
that flag.

Applied to rows 6–9: `web-profile-prototype`, `table-driven-entropy-build`,
`independent-block-container`, `simd-decode-build` are all `api_capability`
dependencies — each waits for **a codec build having that capability**. No such
build exists: `web_benchmark_codec_build` holds three baselines and one
archival candidate whose capabilities read `"web_profile": false`. So
`pending_dependency` on all four rows is **the true state of the world**, not a
gap. Writing `resolved` there would require inventing a build id and would be
exactly the false-green this programme reversed on NEW-28.

## 2. What CUBR-0075 actually measured — from the committed artefact

`documentation/ephemeral/research/CUBR-0075-profile/dependency-negatives.{md,json}`
on `origin/codex/cubr-0075-profile` (tip `cbdae7d`), committed with
binary/manifest/source SHAs, 792/792 exact round-trips. The JSON's own status
string is the key: **`measured-negative-throughput`** — every negative is
scoped to *throughput leverage on the existing CM2 decode path*:

| negatives-doc heading | measured claim | number | what it kills | what it does NOT touch (its own words) |
|---|---|---|---|---|
| "Dependency 14" | framing/container work in the current decoder | 196,008 of 2,259,933,725,206 stage cycles (0.00%) | independent blocks as a *single-thread throughput* lever — there is no framing overhead to remove | "streaming or first-output latency… separate pending goals… not cleared by this negative"; parallel scaling unmeasured |
| "Dependency 8" | allocation cost + retained state | 8,942,160,152 cycles / 90,480 calls (0.40%); retained-state delta 0 B ×792 | allocator work as a throughput lever | "not a bounded-memory proof" — hypothesis 8's actual subject stays open |
| "Dependency 13" | the range-coder *primitive calls* inside CM2 decode | `range_get_freq` + `range_decode` = 49,592,573,186 cycles = 2.0185% of substage cycles → Amdahl ≤ **1.0206×** | **retrofitting** a table-driven coder into the CM2 path — swapping the coder while the adaptive model stays | "does not rule out a coder improvement for a different non-CM path"; the new-scheme architecture is unbuilt and unmeasured |

## 3. The id conflation, mapped once so it stops recurring

The negatives doc numbers its sections by **hypothesis id**. The DB dependency
**row ids** are different numbers, and the dependency **key** is not the
hypothesis **label**:

| negatives-doc "Dependency" | = hypothesis id | hypothesis label | DB dependency row id | dependency key |
|---:|---:|---|---:|---|
| 8 | 8 | `bounded-state` (CUBR-0075) | 2 | `allocator-telemetry` |
| 13 | 13 | `table-driven-entropy-stage` | 7 | `table-driven-entropy-build` |
| 14 | 14 | `block-parallel-decode` | 8 | `independent-block-container` |

The operator's note is confirmed: "dependency 8" the briefs mentioned is DB
**row** 2 (`allocator-telemetry`) hanging off **hypothesis** 8
(`bounded-state`, CUBR-0075). DB dependency *row* 8 is a different thing
entirely (hypothesis 14's container build).

## 4. Verdict on the fork, and the retraction

**Reading 1 (persistence gap): no.** Nothing measured is missing from the DB,
because the DB has no legal cell for a pre-evaluation measured negative:
`web_benchmark_hypothesis_evidence` requires a NOT-NULL `evaluation_id` (and
`evaluation` stays 0 until the reopen gates — standing constraint);
`lifecycle` admits only `{preregistered, frozen, evaluated, archived}` — there
is no "killed"; `resolution_state` is the binary build tracker above. The
designed home for these negatives is the journal, and they are already there,
committed with SHAs and pushed. **No DB write is made by this reconciliation,
and none would be legitimate.**

**Reading 2 ("killed by measurement" too strong): yes, for the hypotheses; no,
for what 0075 actually claimed.** The precise statements:

- KILLED by measurement: coder-swap retrofit inside CM2 decode (≤1.0206×);
  container-overhead removal as a throughput lever (0.00%); allocator work as
  a throughput lever (0.40%). These are closed. **Do not re-measure them.**
- NOT killed: **hypothesis 13 as registered** — a new value scheme whose
  decode has no adaptive model, GO bar ≥ 100 MB/s. Its registered bar is two
  orders of magnitude above anything the current path can reach, so it was
  never a claim about the current path. The 2.0185% coder-share measurement is
  in fact *supporting evidence for* this route: it proves the decode cost is
  the model (95.55% of cycles), which is precisely what the new scheme
  removes. Also not killed: **hypothesis 14 as registered** (parallel scaling
  from independent blocks — unmeasured) and **hypothesis 8's bounded-state
  subject** (explicitly not proven by the telemetry negative).
- Correct as stated: dependency 15 — "SIMD insufficient alone" is arithmetic
  against the 227× gate, and stands.

So a brief sentence of the form "dependencies 13 and 14 are measured negatives"
is accurate about the *dependency-key readings* (retrofit coder swap; container
overhead) and **overstates** if read as "hypotheses 13 and 14 are killed". The
prototype-shape document's choice of hypothesis 13 as the first lever is
consistent with — indeed, motivated by — the 0075 measurement.

## 5. Consequences for the lever-13 build

1. Build against the **new-scheme** reading only; the retrofit question is
   closed and must not be re-measured.
2. Dependency row 7 resolves **when and only when** a codec build with the
   table-driven capability registers in `web_benchmark_codec_build` — that is
   the row's job, and it will happen as a side effect of doing the work, never
   by hand-editing state.
3. `evaluation` stays 0 throughout the build; the first legal evidence rows
   arrive only with an authorized evaluation under the reopen gates.
4. One custody note: the 0075 negatives live on the unmerged
   `codex/cubr-0075-profile` branch. They are pushed (remote-preserved, tip
   `cbdae7d`), so this is not a one-disk incident, but a docs-only merge of the
   evidence directory would put them on `main` where the other verdicts live.
   That is an operator decision — the branch also carries feature-gated
   instrumentation on a hot decode path, which was deliberately left unmerged.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — best single split 2.09×, whole model 22.52×.
**Web: unreachable on this algorithm** — density WIN `0.877644` never ships
without decode `0.004410` in the same sentence; the gate needs 0.50 and the
measured miss is 113×.
