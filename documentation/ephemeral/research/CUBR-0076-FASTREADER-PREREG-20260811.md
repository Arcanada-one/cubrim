# CUBR-0076 — refilled bit reader: preregistration of the re-measurement

**Date:** 2026-08-11 UTC
**Registry identity:** hypothesis **11**, criterion **57**
(`decode_throughput_vs_brotli5 >= 0.50`), and hypothesis **12**'s decode
criterion. Existing rows; no new bar, nothing renegotiated.
**Trigger:** the miss recorded in
[`CUBR-0076-BROTLI5-RESULTS-20260811.md`](CUBR-0076-BROTLI5-RESULTS-20260811.md)
— ratio **0.4007** against a 0.50 bar.
**State when written:** the change is implemented and the correctness gates
pass; **no throughput number has been produced or inspected for it.**

## The change, and why it is the licensed one

This executes the lever that the ratio preregistration named **before** the
miss existed, so it cannot be a post-hoc rescue:

> If the ratio misses, the responsible next step is not to renegotiate the bar
> and not to change the format. It is the already-named implementation lever:
> the prototype's bit reader assembles each code index one bit at a time.

Two implementation changes in `code/cubrim-rs/src/web.rs`, both decoder-side:

1. **Refilled bit reader.** The reader keeps a 64-bit accumulator topped up to
   at least 57 live bits and peels a codeword index with one shift and one
   mask, replacing a per-bit loop. Wire order is unchanged: the same MSB-first
   stream, read a register at a time.
2. **Non-overlapping match runs are copied at once** (`extend_from_within`).
   Overlapping runs — where later bytes read what earlier iterations just
   wrote, i.e. the run-length case — **stay byte-wise**, because a block copy
   there would silently produce different output.

**No wire byte changes. No encoder change. No density change.** Archives
produced before this change decode identically after it; every density number
already measured stands as measured.

## Correctness gates (already green, stated before the timing run)

- `web.rs` unit tests 16/16, including round trips over text, JSON, single-byte
  runs, all byte values, incompressible bytes and every length 1..64, plus
  fail-closed truncation, corruption, declared-length and checksum tests.
- **Mutation-verified, not merely passing:** removing the overlap guard (making
  every run a block copy) fails **9 of the 16** tests. The suite demonstrably
  covers the one case where this optimisation could silently corrupt output —
  checked by mutation before the change was trusted, per the standing rule that
  a test which passes when its subject is deleted proves nothing.
- The census corpus gate and the full existing suite are re-run before any
  throughput number is taken.

## Protocol for the re-measurement

Identical to the runs it is compared against, so the comparison is honest:
quiet host, admission loadavg recorded before and after, `taskset` pin, 101
timed rounds, 5 warmups, randomized seeded schedule, per-sample minimum,
byte-exact verification inside the timed region, both decoders in one process
and interleaved for the ratio arm.

## Verdict rule

- `decode_throughput_vs_brotli5 >= 0.50` → hypothesis 11's product-side decode
  bar is met, and the web profile clears both it and hypothesis 12's GO gate.
- `< 0.50` → the bar is missed by the optimised implementation too. **That is
  a real finding and it gets reported as one**, with no further lever invented
  in the same breath: the next candidate would be a format-level change
  (larger literal alphabets, fewer per-symbol decisions), which is a different
  hypothesis and needs its own registration.

## Prediction

**Ratio 0.55 to 0.75, i.e. the bar is cleared**, from cubrim decode of
**310-420 MB/s** (up from 222.88) against the same 556.25 MB/s brotli-5
baseline.

Mechanism: the previous reader executed roughly one loop iteration, one byte
load, one shift and one mask **per bit** of every codeword; the census stream
averages a little over 8 bits per symbol, so per-symbol bit assembly dominated
the decode. Replacing it with a single shift-and-mask per symbol removes most
of that work, and the remaining per-symbol cost is the table lookup, the extra
bits and the copy. A 1.4-1.9x whole-decode speedup is what that mechanism
supports.

Falsifiable sub-predictions:

1. **The largest samples gain most** — they are the ones where the ratio was
   worst (0.3146 on the largest JSON), because per-symbol overhead scales with
   symbol count.
2. **woff2 gains least in relative terms.** It is nearly all literals with few
   long matches, so it benefits from the reader but not from the copy fast
   path.
3. **The absolute hypothesis-12 decode number stays above 50 MB/s on every
   sample** — it cannot regress, since no work is added anywhere.

## Out of scope

No wire-format change, no encoder change, no DB write, no claim about the
archival lane, and no re-opening of any density verdict.
