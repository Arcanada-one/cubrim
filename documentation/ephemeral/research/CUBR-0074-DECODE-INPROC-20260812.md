# CUBR-0074 — the decode gate does not have one answer: it depends which decoder

**Status:** the gate Phase B recorded as UNMEASURABLE is measurable. The result
is that `decode_throughput_vs_brotli5` **has no single value**, because Cubrim
has two decoders and the criterion never said which one it is about.

| decoder measured | throughput | ratio vs brotli-5 | verdict |
|---|---|---|---|
| `cubrim::decode`, main crate (CUBR-0076, 2026-08-11) | 441.79 MB/s | **0.7896** | PASS |
| reference decoder, `opt-level=3` | 321.4 MB/s | **0.4102** | FAIL |
| reference decoder, `opt-level="z"` (the shipped build) | 265.0 MB/s | **0.3603** | FAIL |

Evidence: `CUBR-0074-DECODE-INPROC-20260812/decode-throughput.json` and
`…-opt3.json`.

## What was actually wrong, and what was not

**The Phase B subprocess figure was worthless and that part stands.** It
reported 0.9764 against a 0.50 bar while every codec sat on a 3.5–4.1 ms floor
of process spawn, with decode a sliver inside it. Every ratio was dragged toward
1.0 and a decoder ten times slower would also have "passed".

**The CUBR-0076 figure of 0.7896 was not wrong.** That arm timed both decoders
in one process, interleaved, in a seeded randomized schedule, byte-exact inside
the timed region, against a preregistration committed before any number was
taken. It is a sound measurement of `cubrim::decode`. An earlier draft of this
document claimed the gate "was never passing" and that calling density the only
remaining bar was "false when it was written". **That was an overstatement and
is withdrawn** — for the decoder that arm measured, the gate passes.

What is new is narrower and sharper: the browser does not run that decoder.

## Two decoders, one wire format, and only one of them ships to browsers

`cubrim-web-decoder` is a deliberately independent implementation — no
`unsafe`, enforced limits, dependency-light so it builds for wasm32. It is what
the WASM module wraps and therefore what a browser executes. `cubrim::decode`
in the main crate is the other implementation, and the two are bound together
by a differential test, not by shared code.

Measured through `cbr_decode` — the same C ABI the browser calls — the
reference decoder reaches 265.0 MB/s in its shipped `opt-level="z"` build and
321.4 MB/s rebuilt at `opt-level=3`. So roughly a seventh of the gap to the main
crate is the size-optimised build profile (chosen because the artefact ships to
browsers, where bytes matter), and the rest is that these are two different
implementations, the reference one being about 27% slower at equal optimisation.

**Both reference-decoder builds fail the gate**, at 0.41 and 0.36 against a 0.50
bar. Cross-checking against the CUBR-0076 arm's own brotli-5 figure of 559.48
MB/s rather than this run's changes nothing: 321.4/559.48 = 0.574 at
`opt-level=3`, 265.0/559.48 = 0.474 as shipped — the shipped build still misses.

## The finding

`decode_throughput_vs_brotli5 >= 0.50` was preregistered with the rationale
that *"decoding is on the browser critical path"*. That rationale points
unambiguously at the reference decoder, and the criterion was then measured
against the main crate. Nobody substituted anything — the gate simply never
named an artefact, and at the time it was written there was only one decoder to
mean.

So the honest scoreboard is:

| criterion | bar | main crate | shipped browser decoder |
|---|---|---|---|
| `ratio_vs_brotli11` | ≤ 1.00 | 1.1163 FAIL | 1.1163 FAIL (same bytes) |
| `decode_throughput_vs_brotli5` | ≥ 0.50 | 0.7896 PASS | 0.3603 FAIL |

Density is identical for both — the bytes do not care which decoder reads them.
Speed is not, and the profile is short on the browser side of a gate whose
whole justification was the browser.

**This also resolves a number that never fit.** CUBR-0077 measured 99.1 MB/s in
Chromium against 443 MB/s "native" — a 22% ratio, worse than WASM usually costs,
recorded and left unexplained. Against the reference decoder's native 265 MB/s
it is 37%, an ordinary WASM penalty. The gap was never the browser; it was
comparing the browser's decoder against the other implementation's speed.

## Method notes worth carrying

1. **Time the decoder, not the binding.** The first version of this module
   timed `decode()` together with marshalling output into Python bytes.
   `bytes(ctypes_array[:n])` converts element by element while `string_at` is a
   memcpy, so it reported Cubrim-Web at **10.4× brotli-5**. The implausible
   direction is what exposed it; a subtler error in the same place would have
   been believed.
2. **Name the artefact in the criterion, not just the metric.** A gate that
   says "decode throughput" without saying *whose* decode is not one criterion,
   it is one per implementation, and it will be read against whichever exists
   when someone measures it.
3. **A release profile is part of the measurement.** `opt-level="z"` is correct
   for a module shipped over the wire and costs 18% of decode throughput here.
   Quoting a speed number without the profile that produced it is quoting half
   a fact.
4. **Randomize the cell schedule even in-process**, or a load change lands
   entirely on whichever codec is in flight; and **record admission alongside
   the number** rather than only gating on it, because a ratio can be sound on a
   host where an absolute throughput is not. Across four runs at loads from 0.75
   to 2.3 per CPU the ratio moved between 0.338 and 0.381 while absolute
   throughput moved far more.
