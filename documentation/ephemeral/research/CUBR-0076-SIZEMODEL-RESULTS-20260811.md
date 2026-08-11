# CUBR-0076 — charged size-model spike, results

**Executed:** 2026-08-11 UTC
**Preregistration:** [`CUBR-0076-SIZEMODEL-PREREG-20260811.md`](CUBR-0076-SIZEMODEL-PREREG-20260811.md),
commit `c39f957`, pushed to `origin/cubr-0076-size-model-spike` **before**
`size_model.py` existed. The decision rule and the prediction below were fixed
in that commit and are not restated here in any softened form.
**Artefacts:** [`CUBR-0076-SIZEMODEL-20260811/`](CUBR-0076-SIZEMODEL-20260811/)
— `size_model.py`, `driver.py`, `test_size_model.py`, `results.tsv`,
`summary.tsv`, `provenance.txt`.
**Scope:** density only. No timing claim, no Rust, no `src/` change, no DB
write; `evaluation` stays 0.

## Verdict

**GO-density. WIN-density missed.**

Aggregate over the 12 census samples, best per-file configuration (what the
scheme byte would actually select):

```
modelled web scheme      121608 B
gzip-9   (GO bar)        129193 B     ratio 0.9413   PASS
brotli-11 (WIN bar)      108495 B     ratio 1.1209   FAIL
best-static family today 158227 B     ratio 0.7686   -23.14%
CM2 champion (adaptive)   94385 B     ratio 1.2884
original                 965410 B
```

Every one of the 12 samples individually beats its own gzip-9 baseline; none
reaches its brotli-11 baseline. The closest to WIN is
`source-map-small-sourcemap-codec-v2` at 1.038x brotli-11, the furthest
`json-api-large-world-benchmark-v2` at 1.252x.

This is the first measured answer to the density void that
[`CUBR-0076-PROTOTYPE-SHAPE-20260806.md`](CUBR-0076-PROTOTYPE-SHAPE-20260806.md)
named: the static-table architecture class does hold gzip-9 density on the
real web corpus, at a modelled cost of **+28.8% output over today's CM2
champion** — which is the density being spent to leave the adaptive decode
path. The registered WIN headroom was +13.9%; this spends more than double
that, so brotli-11 parity is not reachable by this shape as modelled.

## What was predicted, and what was wrong

The preregistration predicted **GO met, WIN missed, aggregate 112000-127000 B**.
Measured 121608 B — inside the range, both bars called correctly. The
mechanism given for the prediction (whole-file window + extended distance
codes clear gzip-9; absence of brotli's context modelling and static
dictionary keeps WIN out of reach) survives.

Two of the three secondary predictions held; one was **wrong**, and one was
right for the wrong reason:

- **Held.** V2 (64 KiB blocks) costs more than V1 on every multi-block sample
  and never less on a single-block one: +2255 B on `html-large-web-codec-v2`
  (4 blocks), +2451 B on `json-api-large-world-benchmark-v2` (5 blocks),
  +124 B and +105 B on the two 2-block samples, 0 B on the eight single-block
  samples. Re-sending table descriptors per 64 KiB block is a real, measured
  tax on the current cube carrier.
- **WRONG.** woff2 was predicted to select **store**. It does not: modelled
  23651 B against a store cost of 23680 B, so the scheme byte selects the web
  scheme by 29 bytes. Entropy-coding an already-compressed payload as literals
  buys back marginally more than the frame costs. The prediction was wrong;
  the store floor still guards the case (the test suite proves a random
  payload does select store) and the difference is immaterial to the verdict.
- **Right, but it did not mean what it implied.** "Chain depth 1024 beats
  depth 16 by less than 5% aggregate" held: 136415 -> 131829 B, 3.36%. The
  implication drawn from it — that the parse-quality term is small — was
  false. Adding the shortest-path parse tier moved V1 from 131829 to 123192 B,
  taking the full parse-quality span to **9.69%**. Parse quality, not the
  scheme, was the binding constraint at the first pass.

## The parse-quality escalation, and why the conservative-parse rule mattered

The first complete run, with the hash-chain lazy parser only (depths 16 / 128 /
1024), reported **130621 B — a PARTIAL**: it beat today's static family by
17.4% but missed the gzip-9 bar by 1.11%.

The frozen conservative-parse rule forbids calling that a NO-GO: the measured
gap (1.11%) was smaller than the demonstrated parse-quality span (3.36%),
so the shortfall could not be attributed to the scheme rather than the parser.
Resolving it required a stronger parser, so one was added: a shortest-path
(zopfli-class) parse that prices every candidate against the real Huffman bit
costs and re-derives those costs over three iterations. It is long-standing
public encoder technique, invented nowhere in this spike.

That tier settled the question in the opposite direction from the first pass:
**123192 B for V1 alone, 121608 B best-per-file — GO, with 7585 B (7.4 KiB) of
margin below the gzip-9 bar.** Had the rule not been written down in advance, the
honest-looking report would have been "NO-GO, misses gzip-9 by 1.1%", and it
would have been wrong.

Full parse-quality ladder, V1 (whole-file window, single literal table):

| parse tier | aggregate B | vs gzip-9 | vs brotli-11 |
|---|---|---|---|
| chain 16 | 136415 | 1.0559 | 1.2573 |
| chain 128 | 132766 | 1.0277 | 1.2237 |
| chain 1024 | 131829 | 1.0204 | 1.2151 |
| shortest-path (chain 256, 3 iterations) | 123192 | **0.9536** | 1.1355 |

## Where the bytes go — the charged decoder-branch inventory

Aggregate over the 12 samples for the strongest single configuration
(V3, whole-file window, 3 literal contexts, shortest-path parse; 974230 bits
= 121779 B before the per-file store comparison):

| decoder branch | bits | bytes | share |
|---|---|---|---|
| literal symbols | 416943 | 52118 | 42.80% |
| distance extra bits | 232285 | 29036 | 23.84% |
| length symbols | 147453 | 18432 | 15.14% |
| distance symbols | 129724 | 16216 | 13.32% |
| length extra bits | 29458 | 3682 | 3.02% |
| table descriptors | 15097 | 1887 | 1.55% |
| context map | 1704 | 213 | 0.17% |
| frame header | 1024 | 128 | 0.11% |
| checksum | 384 | 48 | 0.04% |
| end-of-block markers | 122 | 15 | 0.01% |
| block headers | 36 | 4 | 0.00% |

All eleven terms are charged; the itemised bits are asserted to sum exactly to
the reported size, as a test rather than a claim.

**The static tables cost 2100 B — 1.72% of the stream.** That is the term an
uncharged model drops. Dropping it would have reported 119679 B (0.9264x
gzip-9, 1.1031x brotli-11): the GO verdict survives the charge, and the WIN
verdict is not rescued by removing it. Stating it plainly: on this corpus the
table-descriptor charge is real but small, and the honest model and the
unsound one happen to agree on both bars. That is an outcome, not a licence —
the charge stays in, and on a corpus of many small blocks (V2 shows the
mechanism) it would not have been small.

**The distance streams cost 45252 B — 37.2% of the output, more than the
literals-minus-nothing intuition suggests.** That is where the whole-file
window is paid for, and it is the largest single lead for a next iteration.

## Per-sample results (best configuration per file)

| sample | orig | modelled | config | gzip-9 | brotli-11 | static today | CM2 | vs gz | vs br |
|---|---|---|---|---|---|---|---|---|---|
| css-medium-tailwind-v2 | 65257 | 10478 | V3-ctx3/opt | 11278 | 9161 | 12447 | 6847 | 0.929 | 1.144 |
| html-large-web-codec-v2 | 227968 | 14610 | V3-ctx3/opt | 15804 | 11746 | 22960 | 10629 | 0.924 | 1.244 |
| html-medium-home-v2 | 25031 | 5615 | V3-ctx3/opt | 5801 | 4763 | 7295 | 4700 | 0.968 | 1.179 |
| javascript-medium-magic-string-v2 | 42936 | 9449 | V3-ctx3/opt | 9896 | 8672 | 11701 | 7242 | 0.955 | 1.090 |
| javascript-medium-sourcemap-codec-v2 | 14590 | 3559 | V3-ctx3/opt | 3705 | 3280 | 5045 | 2893 | 0.961 | 1.085 |
| javascript-small-resolve-uri-v2 | 9866 | 2797 | V1/opt | 2895 | 2467 | 4154 | 2420 | 0.966 | 1.134 |
| json-api-large-world-benchmark-v2 | 320976 | 18674 | V3-ctx3/opt | 21196 | 14910 | 26451 | 13323 | 0.881 | 1.252 |
| json-api-medium-web-benchmark-v2 | 98948 | 9688 | V3-ctx3/opt | 10516 | 8344 | 13356 | 5719 | 0.921 | 1.161 |
| json-api-small-hypotheses-v2 | 13880 | 1583 | V3-ctx3/opt | 1674 | 1383 | 2642 | 1442 | 0.946 | 1.145 |
| source-map-large-magic-string-v2 | 112594 | 19097 | V3-ctx3/opt | 20194 | 17827 | 23906 | 13664 | 0.946 | 1.071 |
| source-map-small-sourcemap-codec-v2 | 9700 | 2407 | V1/opt | 2546 | 2319 | 3849 | 1829 | 0.945 | 1.038 |
| woff2-medium-inter-latin-v20 | 23664 | 23651 | V1/opt | 23688 | 23623 | 24421 | 23677 | 0.998 | 1.001 |
| **total** | **965410** | **121608** | | **129193** | **108495** | **158227** | **94385** | **0.941** | **1.121** |

These are twelve fixed files reported per file. No corpus-wide average
compression claim is made or implied by the total row; it is a sum of the same
twelve files under every column.

Context splitting (V3) is worth having but is not the lever: 3 literal
contexts buy 1501 B over V1 at the shortest-path tier (123192 -> 121691),
about 1.2%, for 213 B of context map. It wins on nine of the twelve samples
and loses on three, so it is a per-file choice the scheme byte already makes,
not a global default.

## What this does and does not license

**Licensed by this result:**

- Hypothesis 13's density leg clears the GO bar in model. Step 2 of the
  prototype slice — an encoder-side prototype behind a scheme flag, byte-exact
  round trip on all 12 samples as the first gate — is now justified by a
  charged model rather than by an architecture argument.
- The 64 KiB cube carrier is the wrong block geometry for this scheme on this
  corpus: it costs 2.3-2.5 KB per large sample against a whole-file window.
  A prototype should carry the whole-file window (or a much larger block) from
  the start, and the carrier question should be settled before, not after, the
  Rust exists.

**Not licensed, and explicitly still void:**

- **Any throughput statement whatsoever.** This spike measured bytes. The
  decode budget the GO bar implies (~72 cycles/output byte) is untested here
  and stays untested until a quiet host exists under the CUBR-0074 protocol.
  A table-driven decoder is in the right architecture class; that is an
  argument, not a measurement, and it is not upgraded by this document.
- **Brotli-11 density parity.** Missed by 12.1% aggregate, on every sample.
  Nothing here suggests a route to it within this shape; the two ingredients
  brotli spends its density on (deeper context modelling, static dictionary)
  are both absent by design, and the second is a corpus-coupled asset with its
  own disclosure question.
- **Any claim about the archival lane.** Untouched.

Standing dual verdict, quoted whole and unchanged by this spike: **archival —
worth pursuing** (best single split 2.09x, whole model 22.52x); **web —
unreachable on this algorithm**, density WIN `0.877644` never without decode
`0.004410` in the same sentence, the gate needs 0.50 and the measured miss is
113x. What this spike adds is that a *different* value scheme, not this
algorithm, holds gzip-9 density in model — which is exactly the reading of
hypothesis 13 the prototype-shape document registered.

## Disclosure classification

Checked against the standing split (CUBR-0072 / LEGAL-0062). The wire-format
shape, the decoder-branch inventory, the extended distance-code construction,
and every number above are format/decoder-side or benchmark results —
**public**. The parser is a textbook hash-chain lazy matcher plus a
shortest-path parse against a real price table, both long-standing public
technique; the context function is a fixed, published function of the previous
byte. **No new encoder-side technique was invented by this spike**, so nothing
here triggers the name-and-escalate rule. If a later iteration's GO comes to
depend on a new encoder-side heuristic, that heuristic is named and escalated
rather than published or silently crippled.

## Reproduction

```
cd documentation/ephemeral/research/CUBR-0076-SIZEMODEL-20260811
python3 test_size_model.py    # 24 gates, must be 0 failure(s)
python3 driver.py             # writes results.tsv + summary.tsv, prints the verdict
```

Standard library only, deterministic, load-insensitive. `provenance.txt`
carries host, interpreter, artefact sha256s, and the input list.
