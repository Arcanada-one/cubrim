# CUBR-0076 — hypothesis 11 ratio re-evaluation: preregistration

**Date:** 2026-08-11 UTC
**Registry identity:** hypothesis **11**, criterion **57**
(`decode_throughput_vs_brotli5 >= 0.50`). Extends the existing row; no
duplicate, no new bar, nothing renegotiated.
**Subject:** the MODE_WEB prototype on `origin/main` at `3ce877a`, unchanged.
**State when written:** the harness compiles; **no ratio has been produced or
inspected**.

## Why this exists

[`CUBR-0076-DECODE-RESULTS-20260811.md`](CUBR-0076-DECODE-RESULTS-20260811.md)
passed hypothesis 12's GO gate (0.9361 gzip-9 density, 222.76 MB/s decode) and
**refused** to evaluate this criterion, because the only brotli on the host was
a CLI and a CLI-to-CLI comparison is biased toward 1.0 — fixed process-startup
cost penalises the faster decoder proportionally more, which would flatter the
candidate on a bar it might otherwise miss. That refusal is now resolved by
design rather than by waiting: an **in-process** brotli-5 baseline.

The gate document is explicit that this is the bar standing between "the
prototype direction is alive" and product viability:

> Passing hypothesis-12 GO does not clear the product. Product viability still
> requires re-evaluating hypothesis 11's `>= 0.50` on the same corpus and
> protocol.

## Harness and fairness rules

`documentation/ephemeral/research/CUBR-0076-BROTLI5-20260811/harness` — a
standalone crate, deliberately **not** part of `code/cubrim-rs`: the shipped
crate must not gain a dependency for a measurement.

- Both decoders run **in the same process**, whole-buffer, single-threaded,
  each from its own archive of the same payload.
- The two arms are **interleaved inside one randomized schedule** (seeded,
  recorded), so drift in machine state cannot land on one arm only.
- **Byte-exact verification inside the timed region** for both arms.
- Per (sample, arm) the **minimum** time is the observation.
- brotli compresses at **quality 5, lgwin 22** (the dynamic-response baseline
  the criterion names, at the CLI's default window) and decodes through its own
  reader API with a 64 KiB internal buffer — its fastest ordinary usage, chosen
  so the baseline is **not handicapped**.
- Same quiet host and pin as the decode gate: `arcana-agents`, `taskset -c 11`,
  loadavg recorded before and after.

## Verdict rule

`decode_throughput_vs_brotli5` = (corpus aggregate cubrim MB/s) / (corpus
aggregate brotli-5 MB/s), both from summed best-case times over the same 12
fixed samples.

- **PASS** iff ratio >= 0.50.
- A pass means the web profile clears the product-side decode bar as well as
  hypothesis 12's GO gate.
- A miss means hypothesis 12 GO still stands (it is a separate, absolute bar
  and is already measured) while the product bar is not met by **this
  implementation**. That distinction must be stated wherever the number
  appears, because the next lever is implementation, not architecture — see
  below.

## Prediction

**I do not know which side of 0.50 this lands, and I am recording that.**
Predicted ratio **0.35 to 0.75**, centred near 0.5. Mechanism: in-process
brotli-5 decode on small web payloads on this class of core typically runs in
the 300-600 MB/s band; cubrim measured 222.76 MB/s, which straddles the bar
across that band.

Two sub-predictions that are falsifiable regardless of where the ratio lands:

1. **brotli-5 wins on every sample.** No sample where cubrim decodes faster.
2. **woff2 is cubrim's worst arm relative to brotli** (already-compressed
   payload: brotli passes it through cheaply, cubrim pays literal-symbol cost).

## The named lever, fixed in advance so a miss cannot be spun

If the ratio misses, the responsible next step is **not** to renegotiate the
bar and **not** to change the format. It is the already-named implementation
lever: the prototype's bit reader assembles each code index **one bit at a
time**, where production table-driven decoders refill a 32/64-bit buffer and
peel codes from a register. That was recorded as a known limitation in the
decode preregistration *before* any throughput number existed. Optimising it
changes no wire bytes, so the density verdicts stand untouched, and it would be
re-measured under this same protocol with its own preregistration.

## Out of scope

No DB write. No change to the wire format or to any density number. No claim
about the archival lane. No product statement beyond this criterion.
