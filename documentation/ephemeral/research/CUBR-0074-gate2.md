# CUBR-0074 Gate 2: reference-channel gate

**Status:** MEASURED NEGATIVE / CORPUS-BLOCKED — the protocol void is retained for
numeric cells, diagnostics establish a deliberate `cube_size_limit` route switch
in the current archival configuration, and the current eight-sample manifest does
not satisfy the preregistered real-world-corpus share.

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

Use a separate `reference_phase_a` channel for `cubrim-lowmem-decode`. It leaves the
published five-codec `PHASE_A_CODECS` tuple, its bundle verifier, and its existing
120 validated rows byte-identical. The candidate is explicitly archival and
whole-buffer: it is not normalized to `cubrim-web`, has no real Web Profile, and
must not be presented as a shipping web codec.

The reference channel will reuse the existing sample manifest, trial order,
30-trial/3-warmup protocol, subprocess sandbox, provenance, five metrics, exact
round-trip checks, and summary machinery. It will add no format, WASM, proxy,
Chromium, or standards work.

## Verification and measurement result

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
- No candidate bundle, summary, evaluation, evidence, or derived row was written.
  The authoritative DB remains at one validated baseline run, with criterion 57
  set to `decode_throughput_vs_brotli5 >= 0.50` and dependency 5 still
  `pending_dependency`.
- Candidate build 7 remains immutable and still advertises
  `hostile_input_hardened=false`, `roundtrip_exact=false`, and no Web Profile;
  it was not mutated or used to manufacture a passing evaluation.

## Diagnostic conclusion: designed large-route switch, not a codec defect

The two competing explanations were stated before the diagnostic run:

1. A fixed per-invocation encode cost makes even small resources
   disproportionately slow.
2. The 300 KB JSON resource triggers a payload-class pathology.

The required no-timeout, one-file diagnostic used the same immutable candidate
binary and the same `compress INPUT OUTPUT --preset lowmem-decode -q` command as
the reference adapter. It ran outside the benchmark harness and therefore is
diagnostic only, not a web-schema benchmark result.

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

## Corpus provenance blocker

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

The route diagnostic is decision-relevant for attribution: the current archival
configuration chooses an inappropriate large-input mode for web resources above
64 KiB, while the supported small-route configuration handles the 300 KB response
within the budget. It is not a Gate2 continuation or WIN result. The true current
blocker is corpus provenance, not the codec, harness, or Web Profile: the manifest
has `real_world_sample_share=0.125`, so the `>=0.80` criterion is unsatisfied by
construction.

CUBR-0076 now has a concrete measured requirement: a Web Profile must select or
equivalently configure the small-input route by deployment context so a
300 KB web response does not pay the archival large-file competition. No 0076
implementation is authorized in this task.

The result also establishes the programme order: corpus acquisition/licensing is
the immediate prerequisite for a valid corpus-parity Gate2 evaluation. CUBR-0076
Web Profile work still has the concrete route requirement above, but it cannot
clear the current corpus blocker. CUBR-0076 through CUBR-0080 remain untouched in
this task.

## Stop conditions

- If any existing five-codec bundle or summary changes, stop and treat it as a
  published-result regression.
- If any candidate resource fails exact round-trip, do not write numeric evaluation
  rows; retain only a journaled void.
- Do not resolve the 0074 dependency or write evaluation/evidence/derived rows until
  every candidate cell is complete and validated.
