# CUBR-0076 — step 4, decode-throughput measurement: preregistration

**Date:** 2026-08-11 UTC
**Registry identity:** hypothesis **12** (`web-profile-kill-gate`), criteria
36–39. No duplicate row. This document fixes the protocol, the host, the
verdict rule and the prediction **before** the quiet-host run.
**Subject:** the MODE_WEB prototype merged in PR #87 (`4ddc23b`), unchanged.

## The registered gate, verbatim (CUBR-0076-GATE-20260806.md)

| verdict | criterion | bar |
|---|---|---|
| WIN | `ratio_vs_brotli11` | ≤ 1.00 |
| WIN | `decode_throughput` | ≥ 200,000,000 B/s |
| GO | `ratio_vs_gzip9` | ≤ 1.00 |
| GO | `decode_throughput` | ≥ 50,000,000 B/s |

**The density legs are already measured and are not reopened here:**
`ratio_vs_gzip9 = 0.9361` (GO leg **passed**), `ratio_vs_brotli11 = 1.1147`
(WIN leg **failed**). WIN is therefore unreachable for this prototype whatever
the clock says, and the only open question is the GO decode leg:

> Does whole-buffer decode of the web-profile archives reach 50 MB/s on a
> genuinely quiet host?

## Disclosure: a contended-host read already exists

Honesty about ordering, because it changes how much this preregistration is
worth. A rough read was taken first on `arcana-devs` at loadavg 11.90 —
explicitly not a verdict, taken to decide whether the decoder needed
optimisation before a quiet-host slot was spent. It reported a corpus
aggregate of 107.35 MB/s, with a per-sample range of 22.38 MB/s (woff2) to
176.31 MB/s.

So the prediction below is **informed, not blind**. What this document still
fixes in advance, and what it is for: the host and its admission rule, the
protocol, which number the verdict reads, and what each outcome licenses.

## Host, and why it is not the historical stand

The programme's recorded refusal names `dev-ai` / `162.55.81.5` as the pinned
campaign stand — "files may be read, compute may not run" — and `arcana-devs`
as unfit (CI runners plus a steady soak). Both were re-probed today:

- `dev-ai` (64 cores): loadavg 4.91, and the load is **Aether node workloads**
  (many processes above 100% CPU), not a cubrim campaign. Unfit for timing and
  still off-limits for compute.
- `arcana-devs` (16 cores): loadavg 11.90. Unfit, exactly as recorded.
- **`arcana-agents` (12 cores): loadavg 0.40**, with nothing above 1.7% CPU
  (a python helper, the Disk Arcana sync daemon, tailscaled). Genuinely quiet.

The measurement therefore runs on `arcana-agents`, pinned to one core. This is
a **different host from the one CUBR-0074 used**, which is stated wherever the
number appears: the gate's bars are absolute (B/s), not relative to a stand, so
a different quiet host is admissible — but a cross-host comparison of *this*
number against CUBR-0074's `0.004410` ratio is not, and none is made.

## Protocol

- Single-threaded whole-buffer decode of the web-profile archive of each of the
  12 census samples; the metric is **original bytes produced per second**.
- Pinned to one core (`taskset -c 11`), normal priority.
- 3 untimed warmups over the full corpus, then **9 timed rounds**.
- **Randomized schedule** per round from a seeded PRNG (seed recorded), so a
  drift in background load cannot be absorbed by a fixed ordering.
- Per sample the **minimum** time is the reported observation (the least
  contaminated one), with the median reported beside it.
- **Byte-exact check inside the timed loop** on every single decode. An
  observation without a passing check is not an observation.
- Loadavg recorded **before and after** the run; if the after-reading shows the
  host stopped being quiet, the run is void and repeated, not adjusted.
- Harness: `code/cubrim-rs/examples/web_decode_bench.rs`, committed with this
  document before the run.

## Verdict rule (fixed here)

- The gate's `decode_throughput` is read as the **corpus aggregate**: total
  original bytes across the 12 samples divided by the summed best-case decode
  time. This matches how the programme's existing corpus-level decode number
  was produced.
- **Per-sample figures are reported too, and a sample below the bar is named
  rather than averaged away.** No corpus-wide average *speedup* claim is made;
  the aggregate is a ratio of two measured sums over the same fixed 12 files.
- GO decode leg passes iff the corpus aggregate ≥ 50,000,000 B/s.
- Combined with the already-measured density legs, the outcomes are:
  **GO** (aggregate ≥ 50 MB/s) — hypothesis 12's GO verdict is met and the web
  track reopens on hypothesis 13; **KILL** (< 50 MB/s) — the profile is killed
  by its own pre-registered gate and the web verdict stands unchanged.
  **WIN is not available either way**, because the brotli-11 density leg is
  already failed.

## Prediction

**GO. Corpus aggregate between 100 and 200 MB/s**, i.e. clearing the 50 MB/s
bar by more than 2x, and **not** reaching the 200 MB/s WIN bar (which is moot,
the density leg having failed).

**Per-sample, woff2 is predicted to fall below 50 MB/s** — it is an
already-compressed payload whose stream is almost pure literals, so it decodes
at literal-symbol cost with none of the copy speedup matches give.

Mechanism, not curve-fitting: the decoder does one flat table lookup per
symbol with no adaptation, and a match emits many bytes per symbol decoded.
The measured 42.8% literal share of the stream is what sets the pace.

## Known limitation, stated before the number exists

The prototype's bit reader assembles each code index **one bit at a time**;
production table-driven decoders refill a 32/64-bit buffer and peel codes from
a register. Whatever this measures is therefore a **floor for the
architecture**, not its ceiling, and the results document must say so rather
than presenting the number as what a table-driven decoder can do.

## Out of scope

No DB write is performed by this run. `web_benchmark_hypothesis_evaluation`
stays at 0 rows; if the gate passes, the row and its provenance are proposed as
the next action rather than written from inside the measuring session. No site,
no leaderboard, no claim about the archival lane.
