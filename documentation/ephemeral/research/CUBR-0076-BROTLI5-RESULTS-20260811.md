# CUBR-0076 — hypothesis 11 ratio: 0.4007, the product bar is MISSED

**Executed:** 2026-08-11 UTC under the protocol frozen in
[`CUBR-0076-BROTLI5-PREREG-20260811.md`](CUBR-0076-BROTLI5-PREREG-20260811.md),
committed before the harness produced a number.
**Evidence:** [`CUBR-0076-BROTLI5-20260811/raw/`](CUBR-0076-BROTLI5-20260811/raw/)
— full output with host, kernel, governor, binary sha256, payload-set sha256,
pin, seed, and admission load before and after.

## Verdict

**`decode_throughput_vs_brotli5 = 0.4007`. Bar is `>= 0.50`. MISSED, by 20%.**

```
cubrim web profile   222.88 MB/s   (corpus aggregate, best-case)
brotli -q5           556.25 MB/s   (same process, same schedule)
ratio                 0.4007       bar >= 0.50   FAIL
```

To clear the bar this implementation needs **278.1 MB/s**, i.e. **+24.8%**.

## What this does and does not change

- **Hypothesis 12's GO verdict stands, untouched.** Its bars are absolute
  (gzip-9 density parity, 50 MB/s decode) and were measured under their own
  preregistration: 0.9361 and 222.76 MB/s. Nothing here reopens them.
- **Hypothesis 11's product bar is missed by THIS IMPLEMENTATION**, not
  necessarily by the architecture. The distinction is not a hedge invented
  after the fact — the preregistration fixed it in advance, together with the
  lever, precisely so a miss could not be spun:

  > If the ratio misses, the responsible next step is not to renegotiate the
  > bar and not to change the format. It is the already-named implementation
  > lever: the prototype's bit reader assembles each code index one bit at a
  > time.

  That lever is now the registered next action. It changes no wire bytes, so
  every density number stands as measured.

## Per sample

| sample | orig | cubrim B | brotli-5 B | cubrim MB/s | brotli-5 MB/s | ratio |
|---|---|---|---|---|---|---|
| sourcemap-codec.umd.js.map | 9700 | 2407 | 2510 | 124.04 | 210.13 | 0.5903 |
| resolve-uri.umd.js | 9866 | 2797 | 2737 | 113.43 | 204.35 | 0.5551 |
| json-api-small-hypotheses-v2.json | 13880 | 1558 | 1522 | 202.92 | 415.44 | 0.4885 |
| sourcemap-codec.umd.js | 14590 | 3522 | 3564 | 118.94 | 252.86 | 0.4704 |
| html-medium-home-v2.html | 25031 | 5563 | 5377 | 132.61 | 283.47 | 0.4678 |
| tailwind.css | 65257 | 10361 | 10238 | 172.83 | 378.82 | 0.4562 |
| magic-string.umd.js.map | 112594 | 19058 | 21142 | 170.31 | 386.32 | 0.4408 |
| magic-string.umd.js | 42936 | 9375 | 9769 | 136.65 | 311.65 | 0.4385 |
| json-api-medium-web-benchmark-v2.json | 98948 | 9630 | 9980 | 258.14 | 608.42 | 0.4243 |
| inter-latin.medium.woff2 | 23664 | 23650 | 23649 | 55.66 | 150.36 | 0.3702 |
| html-large-web-codec-v2.html | 227968 | 14428 | 13863 | 349.53 | 973.63 | 0.3590 |
| json-api-large-world-benchmark-v2.json | 320976 | 18590 | 18820 | 329.92 | 1048.69 | 0.3146 |
| **aggregate** | **965410** | **120939** | **123171** | **222.88** | **556.25** | **0.4007** |

**Two samples clear 0.50 on their own** (the two smallest source-map/JS files);
the ratio degrades as payloads grow, because brotli's decode scales better with
size than this implementation's per-symbol bit assembly does. That is the
signature of exactly the limitation the preregistration named.

Density footnote, not a claim: cubrim's archives total 120939 B against
brotli-5's 123171 B — **1.8% smaller than the speed baseline it is being timed
against**. brotli-5 is not the density bar (brotli-11 is, and that leg failed
at 1.1147); it is stated only because both numbers came out of this run.

## An unplanned cross-host confirmation

The measurement moved hosts mid-lane, and that turned into a check worth more
than the inconvenience cost.

`arcana-agents` — the box that produced the 222.76 MB/s gate number — picked up
a self-hosted CI job (a Runner.Worker plus two `rustc` at 100%) and stopped
being admissible. Rather than measure on a contended host, the run moved to
`arcana-kb`: **the same CPU model** (AMD Ryzen 5 3600), loadavg 0.11 before and
after, nothing above 1.8% CPU.

Running the *unchanged* absolute harness there gave **222.35 MB/s**, against
222.76 MB/s on `arcana-agents` — a **0.18% cross-host difference on an
independent box**. The gate number reproduces.

## Predictions: range held, one sub-prediction wrong

1. **Held.** Predicted 0.35-0.75 with the side of the bar explicitly unknown;
   measured 0.4007. Recording the uncertainty rather than a confident guess was
   the honest call and it was the right one.
2. **Held.** brotli-5 is faster on every one of the 12 samples.
3. **WRONG.** woff2 was predicted to be cubrim's worst arm relative to brotli.
   It is second-worst (0.3702); `json-api-large-world-benchmark-v2.json` is
   worse at 0.3146. The mechanism given for woff2 (all-literal stream) is real
   but was outweighed by the size-scaling effect above.

## Method note worth keeping

The bias this harness was built to avoid was real and large. A CLI-to-CLI
comparison would have measured process startup on both arms, and since brotli
is the faster decoder, the fixed cost would have penalised it proportionally
more — pushing the ratio toward 1.0 and quite plausibly over the 0.50 bar. The
honest in-process number is **0.4007**: a fail. Refusing the convenient
measurement in the decode-gate document and building the fair one instead is
the only reason this is a fail rather than a fake pass.

## Registered next action

Optimise the decoder's bit reader — refill a 32/64-bit register and peel
codewords from it, instead of assembling each index one bit at a time. It is
pure implementation: no wire-format change, no encoder change, no density
change. Target is a ratio `>= 0.50`, needing `>= 278.1 MB/s`, i.e. `+24.8%`.
It gets its own preregistration and is re-measured under this same protocol,
on a quiet host, with byte-exactness inside the timed loop.

## DB discipline

No DB write. `web_benchmark_hypothesis_evaluation` stays at 0 rows. This result
does not change the hypothesis-12 row proposed in
[`CUBR-0076-DECODE-RESULTS-20260811.md`](CUBR-0076-DECODE-RESULTS-20260811.md);
it adds the hypothesis-11 criterion-57 observation `0.4007` (FAIL) alongside
it, for the archival orchestrator to write or reject.
