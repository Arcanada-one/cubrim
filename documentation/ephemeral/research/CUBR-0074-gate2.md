# CUBR-0074 Gate 2: reference-channel gate

**Status:** MEASURED NEGATIVE / DECODE-GATE-FAILED — the v2 corpus is 100% real and
the aggregate density ratio is a WIN, but the candidate misses the fixed
decode-throughput gate by a wide margin. Exact round-trips are proven for every
candidate and Brotli-5 cell; dependency 5 was resolved only after the v2 harness
completed. No evaluation, evidence, or derived rows were written.

## Gate

The existing 0074 corpus-parity criteria remain the ratio gate:

- `ratio_vs_brotli11 <= 1.00` is the continuation gate.
- `ratio_vs_brotli11 <= 0.92` is the stronger WIN gate.
- `real_world_sample_share >= 0.80` remains required.
- `decode_throughput_vs_brotli5 >= 0.50` is the fixed decode gate.
- Exact byte-for-byte round-trip is required for every resource in all measured cells.

The throughput factor is 0.50 because decoding is on the browser critical path. A
candidate must deliver at least half of Brotli-5's decode throughput, allowing at
most twice the decode latency of the dynamic-response baseline. This permits one
equal-sized decode-latency budget for a new codec while rejecting a four-times-slower
decoder that would not be a credible browser delivery path. Brotli-11 remains the
density baseline; Brotli-5 is the speed baseline actually used for dynamic web
responses.

## Reference-channel choice

Use a separate `reference_phase_a` channel for `cubrim-lowmem-decode` against
`bench/web-corpus/manifest.v2.json`. It leaves the published five-codec
`PHASE_A_CODECS` tuple, its bundle verifier, and its existing 120 validated rows
byte-identical. The reference invocation uses the supported `--b 1024` route
override in addition to `--preset lowmem-decode`; this is benchmark-channel
configuration and does not change codec defaults. The candidate is explicitly
archival and whole-buffer: it is not normalized to `cubrim-web`, has no real Web
Profile, and must not be presented as a shipping web codec.

The reference channel uses the v2 sample manifest, the existing trial order,
30-trial/3-warmup protocol, subprocess sandbox, provenance, five metrics, exact
round-trip checks, and summary machinery. It will add no format, WASM, proxy,
Chromium, or standards work.

## V1 history: protocol void and route diagnostic

- Gate2 implementation commit: `f9176dcfc6ae7ee003486ae3ed4c67280fe55639`.
- Candidate binary: `cubrim 0.3.2`, SHA-256
  `b14aa4009d5bd3c277c9f7da792dbadec256c2c801da64c6b2064643fcedd1c1`.
- The required eight-sample `manifest.v1.json` was used; its manifest SHA-256 is
  `9a0fcb56b9af5c98cd987d1ad289f5adde4b073480646fb472d784b0bbf58599`.
- Manifest provenance was rechecked for all eight samples: seven samples
  (`html-small-v1`, `css-medium-v1`, `javascript-small-v1`, `source-map-small-v1`,
  `json-api-large-v1`, `svg-medium-v1`, and `wasm-small-v1`) use
  `project-authored:` source references from `generate_project_fixtures.py`; only
  `woff2-medium-inter-latin-v20` uses a genuinely fetched source reference. The
  current `real_world_sample_share` is therefore `1/8 = 0.125`, below the
  required `0.80`.
- Focused attribution tests and the full Python harness passed: `51/51`.
- Full release Rust tests passed in a clean detached worktree: 311 library tests,
  7 CLI tests, 5 archive integration tests, 2/1/1 benchmark tests, and 10
  differential tests, with no failures.
- The deterministic canonical five-codec fixture bundle is byte-identical before
  and after the reference-channel change: SHA-256
  `5dcdd335d53c63a3be6a493cd07b4baebb7e963d83dbf96bbc091317a47a615f`.
- The reference run was launched with 3 warmups and 30 trials per cell under the
  unchanged 60-second subprocess timeout. Both attempts journaled the same first
  failure: `json-api-large-v1/cubrim-lowmem-decode`, warmup `-1`, reason
  `timeout`. The quiet-host recovery attempt was admitted at load-per-CPU `0.390`,
  so the repeat is an intrinsic protocol timeout, not an admission rejection.
- No candidate bundle, summary, evaluation, evidence, or derived row was written
  at that time. The authoritative DB then remained at one validated baseline
  run, with criterion 57 set to `decode_throughput_vs_brotli5 >= 0.50` and
  dependency 5 still `pending_dependency`.
- Candidate build 7 remains immutable and still advertises
  `hostile_input_hardened=false`, `roundtrip_exact=false`, and no Web Profile;
  it was not mutated or used to manufacture a passing evaluation.

## V2 reconciliation and measurement result

The v2 manifest is the measured Gate2 corpus. Its SHA-256 is
`fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf`;
`schema_version=2`, `sample_count=12`, and `real_world_sample_share=12/12=1.000`.
All twelve samples are non-project-authored and redistributable. The manifest
records the canon gaps rather than fabricating coverage: WASM is blocked on
CUBR-0077 and SVG is blocked on an operator sourcing decision.

The benchmark reference-channel change is runner commit
`03d7f1c71f0f76652f7db655db6c5e2fe1e4dc15`. Preflight was admitted with the
same 16-CPU host and recorded the v2 manifest, the candidate binary SHA-256
`b14aa4009d5bd3c277c9f7da792dbadec256c2c801da64c6b2064643fcedd1c1`, and the
flags `compress --preset lowmem-decode --b 1024 -q`. The preflight JSON SHA-256
is `066e23fb2edb082f75f8554ee2a0c257ccf433adc7cf7b0399ecc639590ba565`.
The separate forced-route diagnostic covered all twelve samples before the full
run; every external `cmp` check passed. Its TSV result SHA-256 is
`81562f14654a2d67afc68c6d27e69564ffabb5b3b86cfd27fc1c0cea4d763806`.

The candidate reference bundle completed the fixed 3-warmup/30-trial protocol:
12 cells, 360 resource results, and 60 metric summaries. Every candidate record
has an exact decoded/original byte and SHA-256 match (`360/360`); every sample
has trial numbers 1 through 30. The bundle SHA-256 is
`c6dc46df1618eeb0da9d30b62c8b53adef6f1ab88dc2b4075b297839b0d3ea89`.

The same v2 harness then measured the registered Brotli-5 adapter as the speed
baseline: 12 cells, 360 results, and `360/360` exact round-trips. Its bundle
SHA-256 is `7e03436074021b27c7447412a0c76cb1a34b334c39e8f3e16c4cc9608e0ede67`.
The candidate and comparator both used runner SHA
`03d7f1c71f0f76652f7db655db6c5e2fe1e4dc15` and the same v2 manifest hash.

| Sample | Input B | Candidate B | Brotli-11 B | Ratio | Candidate decode ms | Brotli-5 decode ms | Throughput ratio | Exact |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `css-medium-tailwind-v2` | 65,257 | 6,916 | 9,161 | 0.754939 | 634.458 | 3.348 | 0.005276 | yes |
| `html-large-web-codec-v2` | 227,968 | 10,936 | 11,746 | 0.931040 | 2,158.383 | 3.915 | 0.001814 | yes |
| `html-medium-home-v2` | 25,031 | 4,730 | 4,763 | 0.993072 | 244.464 | 3.405 | 0.013930 | yes |
| `javascript-medium-magic-string-v2` | 42,936 | 7,246 | 8,672 | 0.835563 | 493.459 | 3.246 | 0.006579 | yes |
| `javascript-medium-sourcemap-codec-v2` | 14,590 | 2,910 | 3,280 | 0.887195 | 160.431 | 3.193 | 0.019905 | yes |
| `javascript-small-resolve-uri-v2` | 9,866 | 2,451 | 2,467 | 0.993514 | 111.215 | 3.296 | 0.029632 | yes |
| `json-api-large-world-benchmark-v2` | 320,976 | 13,638 | 14,910 | 0.914688 | 3,134.593 | 3.683 | 0.001175 | yes |
| `json-api-medium-web-benchmark-v2` | 98,948 | 5,754 | 8,344 | 0.689597 | 951.339 | 3.488 | 0.003666 | yes |
| `json-api-small-hypotheses-v2` | 13,880 | 1,444 | 1,383 | 1.044107 | 144.521 | 3.264 | 0.022582 | yes |
| `source-map-large-magic-string-v2` | 112,594 | 13,675 | 17,827 | 0.767095 | 1,184.003 | 3.731 | 0.003151 | yes |
| `source-map-small-sourcemap-codec-v2` | 9,700 | 1,843 | 2,319 | 0.794739 | 110.087 | 3.257 | 0.029586 | yes |
| `woff2-medium-inter-latin-v20` | 23,664 | 23,677 | 23,623 | 1.002286 | 4.045 | 3.325 | 0.821968 | yes |

The density aggregate is `95,220 / 108,495 = 0.877644`, so the corpus-level
ratio clears both GO (`<=1.00`) and WIN (`<=0.92`). The table remains the
authoritative per-sample view: `json-api-small-hypotheses-v2` and WOFF2 are above
1.00, while four samples are above the stronger 0.92 line. The source-map
samples are reported explicitly and both are below 0.92; none is hidden by the
aggregate.

The throughput factor is median Brotli-5 decode duration divided by median
candidate decode duration for each equal-sized sample. The aggregate, computed
from the sum of sample bytes divided by the sum of those per-sample median
durations, is candidate `0.098670 MiB/s` versus Brotli-5 `22.373188 MiB/s`, a
factor of `0.004410`. Only WOFF2 reaches the per-sample `0.50` threshold
(`0.821968`); the overall decode gate therefore fails decisively despite the
density WIN. This is the Gate2 verdict: **NEGATIVE — decode throughput gate
failed**.

After the candidate v2 run completed and the exact checks passed, dependency 5
(`instrumentation / real-world-web-corpus`) was updated in one guarded
transaction from `pending_dependency` to `resolved`, with `resolved_by_build_id=7`.
The pre-write database dump was gzip-verified; its SHA-256 is
`3e74d4b3cd1e242cccb09e014677e9fae308c81b42dbbc8a622235464b223dd0`. Readback
confirmed one validated run, 120 existing summaries, zero hypothesis
evaluations, zero evidence rows, and zero new candidate result rows. The
immutable build-7 row was not changed; the `--b 1024` value remains a measured
reference-channel invocation flag.

## Diagnostic conclusion: designed large-route switch, not a codec defect

The two competing explanations were stated before the diagnostic run:

1. A fixed per-invocation encode cost makes even small resources
   disproportionately slow.
2. The 300 KB JSON resource triggers a payload-class pathology.

The required no-timeout, one-file v1 diagnostic used the same immutable candidate
binary and the same v1 reference-adapter command,
`compress INPUT OUTPUT --preset lowmem-decode -q`. It ran outside the benchmark
harness and therefore is diagnostic only, not a web-schema benchmark result.

| Resource | Input | Archive | Encode wall | Peak RSS | Exact round-trip |
|---|---:|---:|---:|---:|---|
| `json-api-large-v1` | 300,000 B | 1,149 B | 70.49 s | 651,908 kB | yes |
| `wasm-small-v1` | 2,048 B | 57 B | 0.02 s | 22,272 kB | yes |
| `html-small-v1` | 4,096 B | 226 B | 0.04 s | 29,184 kB | yes |
| `source-map-small-v1` | 6,144 B | 250 B | 0.06 s | 29,776 kB | yes |

The small-resource discriminator rejected both fixed invocation overhead and a
JSON-only explanation. A size-only ladder was therefore run on prefixes of the
JSON payload and on a second media type made by repeating/truncating the
source-map seed. Every row was a single no-timeout encode followed by exact
`cmp` verification:

| Size | JSON wall | JSON s/MiB | JSON peak RSS | Source-map wall | Source-map s/MiB | Source-map peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 12,288 B | 0.13 s | 11.1 | 31,016 kB | 0.11 s | 9.4 | 30,248 kB |
| 25,600 B | 0.27 s | 11.1 | 31,000 kB | 0.26 s | 10.6 | 30,104 kB |
| 51,200 B | 0.58 s | 11.9 | 55,484 kB | 0.47 s | 9.6 | 51,644 kB |
| 102,400 B | 14.61 s | 149.6 | 622,728 kB | 9.44 s | 96.7 | 602,104 kB |
| 204,800 B | 42.98 s | 220.1 | 638,288 kB | 15.74 s | 80.6 | 619,616 kB |
| 300,000 B | 77.52 s | 271.0 | 654,568 kB | 30.65 s | 107.1 | 625,508 kB |

The transition is a designed route switch. `code/cubrim-rs/src/config.rs:520-524`
defines `cube_size_limit()` as `b*b`; the default `b=256` is 65,536 B, and
`code/cubrim-rs/src/codec.rs:288-334` selects the large-input competition only
when the input exceeds that limit. The ladder's 51,200 → 102,400 B step is the
first rung crossing this gate, so the 25x jump is the cost of entering the
large-file strategy, not an unlocalized superlinear core-codec defect.

### Forced-small-route diagnostic

The supported CLI override `--b 1024` raises the route ceiling to 1,048,576 B,
keeping the 300,000-byte JSON resource on the small route without changing
source. With the same `--preset lowmem-decode` and exact round-trip check:

| Route | Encode wall | Peak RSS | Archive | Candidate ratio | Ratio vs Brotli-11 | Exact round-trip |
|---|---:|---:|---:|---:|---:|---|
| Default `b=256` ladder point | 77.52 s | 654,568 kB | 1,149 B | 0.003830 | 0.552138 | yes |
| Forced small `--b 1024` | 2.15 s | 106,008 kB | 1,149 B | 0.003830 | 0.552138 | yes |

The Brotli-11 comparison uses the validated run-2 summary for this sample:
2,081 compressed bytes over 30 trials. The forced-small diagnostic is about
36x faster than the default route, uses roughly 84% less RSS, and emits the
same archive bytes, so it demonstrates the route timing/RSS effect and preserves
exact round-trip behavior. It is diagnostic only and creates no web-schema
benchmark result.

## Corpus reconciliation

The forced-small `ratio_vs_brotli11=0.552138` is mechanically reproducible but
must not be treated as evidence toward the ratio gate. The large JSON fixture is
one of the seven deterministic project-authored fixtures generated by
`bench/web-corpus/generate_project_fixtures.py`: `json_api_payload()` creates 512
near-identical records and pads the document to exactly 300,000 bytes. This
synthetic repetition is a fixture artifact. Brotli-11 reaches 2,081 bytes
(`0.0069367` of input), while the candidate archive is 1,149 bytes (`0.003830`);
the relative `0.552138` is valid arithmetic for this fixture, not a web-corpus
generalization.

The timing/RSS route-switch finding remains useful: the forced small route is
about 36x faster, uses roughly 84% less RSS, emits identical archive bytes, and
passes the exact round-trip check. The ratio result stays in this research
record only; it does not authorize a numeric, evaluation, evidence, or derived
row in the database.

The epic already owns the corpus question. The CUBR-0072 canon defines the
CUBR-0074 corpus as HTML, CSS, JavaScript, source maps, JSON API, SVG, WASM, and
fonts across small/medium/large size classes, with canonical sources and
checksums. The backlog has one CUBR-0074 world-web-benchmark row and no separate
corpus-acquisition task; CUBR-0075 owns decode-side hypotheses, and CUBR-0076
through CUBR-0080 are downstream tasks.

The repository also contains the already-designed real corpus candidate
`bench/web-corpus/manifest.v2.json` (`cubr0074-web-real-v2`). It has 12 samples,
all with non-`project-authored:` provenance and `redistributable=true`:
HTML x2, CSS x1, JavaScript x3, JSON API x3, source maps x2, and WOFF2 x1;
the size split is small x2, medium x7, and large x3. Its
`real_world_sample_share` is `12/12 = 1.000`. The manifest records, rather than
fakes, two canon gaps: WASM is blocked on CUBR-0077, and SVG is blocked on an
operator sourcing decision because available third-party assets carry trademark
concerns. This v2 manifest is now the measured Gate2 corpus. Only dependency 5
was updated in the database after measurement; no candidate result or evaluation
rows were inserted.

The route diagnostic is decision-relevant for attribution: the current archival
configuration chooses an inappropriate large-input mode for web resources above
64 KiB, while the supported small-route configuration handles the 300 KB response
within the budget. The v1 route result remains history only. The v2
reconciliation removes the provenance blocker (`real_world_sample_share=1.000`),
but the measured candidate is still negative because its decode-throughput factor
is `0.004410` in aggregate. The missing WASM/SVG canon classes remain explicitly
owned gaps, not hidden samples.

CUBR-0076 now has a concrete measured requirement: a Web Profile must select or
equivalently configure the small-input route by deployment context so a
300 KB web response does not pay the archival large-file competition. No 0076
implementation is authorized in this task.

The result also establishes the programme order: reconcile the existing v2 corpus
record before proposing any acquisition work. CUBR-0076 Web Profile work still
has the concrete route requirement above, but it cannot clear the measured
decode-throughput failure. CUBR-0076 through CUBR-0080 remain untouched in this
task.

## Stop conditions

- If any existing five-codec bundle or summary changes, stop and treat it as a
  published-result regression.
- If any candidate resource fails exact round-trip, do not write numeric evaluation
  rows; retain only a journaled void.
- Dependency 5 may be resolved only after the v2 candidate cells are complete and
  validated; that guarded update is now complete. Do not write evaluation,
  evidence, or derived rows from the negative result without a separately
  authorized ingestion step.

## State handoff for the next session

- **Cliff:** approximately 10 s/MiB is linear below 64 KiB; the first rung above
  the threshold has a 25x step. `cube_size_limit` is defined at
  `code/cubrim-rs/src/config.rs:520` and gates `cm_should_try` (the symbol is at
  `code/cubrim-rs/src/codec.rs:3317` in this checkout); the cliff reproduced on
  JSON and source-map inputs, with 12/12 exact round-trips.
- **Route override:** the 300 KB JSON moved from 77.52 s / 654 MB to 2.15 s /
  106 MB with `--b 1024 --preset lowmem-decode`, exact round-trip preserved.
  `ratio_vs_brotli11=0.552138` is fixture-only; Brotli-11 reaches roughly 144x
  compression on that same synthetic file, so the ratio is not web-representative.
- **Binding blocker:** corpus provenance is cleared for the measured v2 set at
  `real_world_sample_share=1.000`, and dependency 5,
  `instrumentation: real-world-web-corpus`, is `resolved` by build 7. The Gate2
  result is negative on `decode_throughput_vs_brotli5` (`0.004410` aggregate
  versus `0.50` required). WASM and SVG remain explicit canon gaps.
- **Ownership:** CUBR-0074 already owns the world-web benchmark and corpus
  decision. No duplicate corpus task exists in the backlog. The canonical
  backlog pointer to `tasks/CUBR-0074-task-description.md` is dangling in the
  inspected checkout; that record-location gap is not authorization to create a
  competing corpus task. CUBR-0075 owns the decode-side hypothesis work; 0076
  owns the Web Profile route/format requirement and gates 0077/0078/0079; 0080
  is last and operator-gated for public standardisation.
- **0076 requirement:** select the small-input route by deployment context, not
  input size; the route requirement is measured, not assumed.
- **Untouched:** codec defaults, harness timeout, `PHASE_A_CODECS`, the database's
  120 summaries / 0 evaluations / 0 evidence rows, the shared backlog (` M`,
  unstaged), and CUBR-0076 through CUBR-0080. Dependency 5 is the sole database
  mutation from this v2 reconciliation.
- **Next session:** carry the negative decode-speed result to CUBR-0075's
  decode-side hypothesis work and retain the measured route requirement for
  CUBR-0076. Do not fetch third-party resources, add manifest entries, create a
  duplicate task, or treat the v1 fixture ratio as evidence. Any evaluation or
  evidence ingestion needs its own guarded authorization.
- **Boundary:** stop at the instructed quota boundary with this handoff committed;
  no outward-facing publication was made. The dependency transition was the one
  authorized irreversible database action and has backup/readback evidence.
