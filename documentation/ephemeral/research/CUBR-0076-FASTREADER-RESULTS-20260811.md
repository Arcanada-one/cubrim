# CUBR-0076 — refilled bit reader: ratio 0.7896, the product bar is CLEARED

**Executed:** 2026-08-11 UTC under the protocol frozen in
[`CUBR-0076-FASTREADER-PREREG-20260811.md`](CUBR-0076-FASTREADER-PREREG-20260811.md),
committed with the code and before any throughput number was taken.
**Evidence:** [`CUBR-0076-FASTREADER-20260811/raw/`](CUBR-0076-FASTREADER-20260811/raw/)
— both arms, with host, kernel, governor, binary sha256s, payload-set sha256,
pin, seed and admission load before and after.

## Verdict

**`decode_throughput_vs_brotli5 = 0.7896`. Bar `>= 0.50`. PASSED, with 58%
margin.** The 0.4007 miss recorded three hours earlier was an implementation
artefact, exactly as the preregistration claimed in advance it might be.

| metric | before | after | bar | |
|---|---|---|---|---|
| `decode_throughput_vs_brotli5` | 0.4007 | **0.7896** | >= 0.50 | **PASS** |
| cubrim decode (corpus aggregate) | 222.88 MB/s | **443.39 MB/s** | >= 50 (h12 GO) | **PASS, 8.9x** |
| | | | >= 200 (h12 WIN speed) | **PASS, 2.2x** |
| `ratio_vs_gzip9` | 0.9361 | **0.9361** | <= 1.00 | PASS |
| `ratio_vs_brotli11` | 1.1147 | **1.1147** | <= 1.00 | **FAIL** |

**Decode roughly doubled — 1.99x — and not one archive byte changed.** The
density columns are identical to the previous run on every sample, which is the
check that the optimisation was confined to the decoder.

So the registered scoreboard now reads: hypothesis 12 **GO passed on both
legs**, hypothesis 11's product-side decode ratio **passed**, and the only bar
still standing between this profile and an outright WIN is brotli-11 density
parity, missed by 11.5%.

## Both arms

Ratio arm — both decoders in one process, interleaved in one randomized seeded
schedule, byte-exact inside the timed region:

| sample | cubrim MB/s | brotli-5 MB/s | ratio | was |
|---|---|---|---|---|
| sourcemap-codec.umd.js.map | 243.47 | 211.24 | **1.1526** | 0.5903 |
| inter-latin.medium.woff2 | 158.88 | 150.63 | **1.0548** | 0.3702 |
| resolve-uri.umd.js | 202.92 | 204.35 | 0.9930 | 0.5551 |
| json-api-medium-web-benchmark-v2.json | 491.81 | 611.12 | 0.8048 | 0.4243 |
| magic-string.umd.js.map | 306.07 | 386.78 | 0.7913 | 0.4408 |
| tailwind.css | 297.95 | 379.84 | 0.7844 | 0.4562 |
| magic-string.umd.js | 238.08 | 311.92 | 0.7633 | 0.4385 |
| html-medium-home-v2.html | 215.49 | 283.02 | 0.7614 | 0.4678 |
| html-large-web-codec-v2.html | 746.77 | 981.76 | 0.7606 | 0.3590 |
| sourcemap-codec.umd.js | 191.04 | 252.82 | 0.7557 | 0.4704 |
| json-api-small-hypotheses-v2.json | 315.09 | 417.07 | 0.7555 | 0.4885 |
| json-api-large-world-benchmark-v2.json | 749.92 | 1055.31 | 0.7106 | 0.3146 |
| **aggregate** | **441.79** | **559.48** | **0.7896** | 0.4007 |

**Two samples now decode faster than brotli-5 outright** (the small source-map
at 1.15x, woff2 at 1.05x) and a third is level. The absolute arm, run
separately with the unchanged hypothesis-12 harness, gives **443.39 MB/s**
corpus aggregate — 0.4% from the ratio arm's figure for the same work, which is
the two harnesses agreeing.

## Predictions: direction right, magnitude wrong again — and one clean falsification

1. **Bar cleared, as predicted.** But the predicted **range was wrong**:
   0.55-0.75 predicted, 0.7896 measured. Likewise cubrim decode was predicted
   at 310-420 MB/s and came in at 443.39.
2. **HELD.** "The largest samples gain most": the two largest gained 2.27x and
   2.14x, against 1.79x for the smallest.
3. **WRONG, instructively.** woff2 was predicted to gain *least* in relative
   terms, on the reasoning that it is nearly all literals and so cannot use the
   copy fast path. It gained **most — 2.85x** (55.66 -> 158.88 MB/s). The
   reasoning had it backwards: being all literals means every output byte cost
   a full per-symbol bit assembly, which is precisely what the refilled reader
   removed. The copy fast path was never the main lever; the reader was.

That is the third preregistration in this lane where the direction held and the
magnitude did not. The pattern is now consistent enough to state plainly:
**this lane's mechanism reasoning has been reliable, its quantitative
estimates have not.**

## Measurement conditions

Host `arcana-kb` — AMD Ryzen 5 3600, kernel 6.8.0-134, governor `schedutil`,
pinned to core 11, admission loadavg **0.17 before / 0.23 after**, nothing on
the box above 1.9% CPU. 101 timed rounds, 5 warmups, randomized seeded
schedule, per-sample minimum, byte-exact verification inside the timed region.
Same host, pin, protocol and seed as the 0.4007 run it is compared against —
the only variable is the code.

## The change

Two decoder-side changes, described fully in the preregistration: a 64-bit
refilled bit accumulator peeling each codeword index with one shift and one
mask instead of a per-bit loop, and a block copy for non-overlapping match
runs while **overlapping runs stay byte-wise** (the run-length case, where a
block copy would silently produce different bytes).

**Mutation-verified rather than merely green:** removing the overlap guard
fails 9 of the 16 web unit tests, so the suite demonstrably covers the one case
where this optimisation could corrupt output silently. Gates: 338 lib tests,
`scheme_roundtrip` 7/7, `differential` 10/10, 16 web unit, 3 corpus (byte-exact
on all 12 census samples), clippy zero warnings, `cargo fmt --check` clean.

## What remains between this profile and a WIN

Exactly one thing: **brotli-11 density parity, missed at 1.1147.** Speed is no
longer the constraint anywhere in the registered family — the profile clears
the GO decode bar by 8.9x, the WIN decode bar by 2.2x, and the product ratio by
58%. Any further work on this profile is a **density** question, and the leads
are already measured and recorded: the distance streams are 37.2% of output
(the largest single term), and context modelling beyond the frozen 3-way split
plus a static dictionary are the two things brotli spends its remaining density
on.

## DB discipline

No DB write. `web_benchmark_hypothesis_evaluation` stays at 0 rows. Updated
proposal for the archival orchestrator, superseding the throughput figures in
the two earlier documents (density figures unchanged):

```
hypothesis 12 (web-profile-kill-gate)   verdict = GO
  ratio_vs_gzip9      = 0.9361     (bar <= 1.00)  PASS
  decode_throughput   = 443390000  (bar >= 5.0e7) PASS
  ratio_vs_brotli11   = 1.1147     (bar <= 1.00)  FAIL -> no WIN
hypothesis 11, criterion 57
  decode_throughput_vs_brotli5 = 0.7896  (bar >= 0.50)  PASS
roundtrip_exact_match_rate = 1   (12/12, checked inside the timed loop)
corpus = cubr0074-web-real-v2
host   = arcana-kb (Ryzen 5 3600), pinned core 11, loadavg 0.17/0.23
evidence = documentation/ephemeral/research/CUBR-0076-FASTREADER-20260811/raw/
```

---

## AMENDMENT 2026-08-12 — which decoder this 0.7896 is about

The verdict here is sound and is not withdrawn: interleaved, seeded, byte-exact
inside the timed region, preregistered before any number was taken. It measures
`cubrim::decode` in the main crate.

`CUBR-0074-DECODE-INPROC-20260812.md` measures the same criterion against the
*reference* decoder — `cubrim-web-decoder`, which the WASM module wraps and a
browser therefore executes — and gets 0.4102 at `opt-level=3` and 0.3603 in the
shipped `opt-level="z"` build. Against this document's own brotli-5 baseline of
559.48 MB/s rather than that run's, the shipped build still misses at 0.474.

So the sentence above — "the only bar still standing between this profile and
an outright WIN is brotli-11 density parity" — holds for the main crate and not
for the browser artefact. The two decoders are independent implementations
bound by a differential test, so no amount of care on one says anything about
the speed of the other, and the gate's own rationale ("decoding is on the
browser critical path") points at the one that was not measured here.
