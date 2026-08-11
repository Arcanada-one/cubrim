# CUBR-0076 — step 4, decode throughput: hypothesis 12 GO is PASSED

**Executed:** 2026-08-11 UTC on a quiet host, under the protocol frozen in
[`CUBR-0076-DECODE-PREREG-20260811.md`](CUBR-0076-DECODE-PREREG-20260811.md)
(commit `08e15ef`, pushed before the run).
**Subject:** the MODE_WEB prototype merged as PR #87 (`4ddc23b`), unchanged.
**Evidence:** [`CUBR-0076-DECODE-20260811/raw/`](CUBR-0076-DECODE-20260811/raw/)
— full harness output with host, kernel, governor, binary sha256, payload-set
sha256, pin, seed, and admission load before and after.

## Verdict

**Hypothesis 12 GO: PASSED on both legs. WIN: failed on density only.**

| verdict | criterion | bar | measured | |
|---|---|---|---|---|
| GO | `ratio_vs_gzip9` | ≤ 1.00 | **0.9361** | PASS |
| GO | `decode_throughput` | ≥ 50,000,000 B/s | **222,760,000 B/s** | **PASS, 4.46x the bar** |
| WIN | `decode_throughput` | ≥ 200,000,000 B/s | 222,760,000 B/s | PASS |
| WIN | `ratio_vs_brotli11` | ≤ 1.00 | 1.1147 | **FAIL** |

The kill gate that every existing decode path failed — CM2 by a wide margin,
GeoCM by ~30x on its own best case — is cleared by the table-driven
architecture. **The web track reopens on hypothesis 13.**

The decode number also clears the WIN speed bar. WIN is nonetheless not
awarded, and must not be reported as "nearly won": its density leg fails by
11.5%, and that leg was measured before this run and is not reopened by it.

## Measurement

Whole-buffer single-threaded decode of the web-profile archive of each census
sample; the metric is original bytes produced per second. Byte-exact
verification inside the timed loop on every decode.

Host `arcana-agents` — AMD Ryzen 5 3600, kernel 6.8.0-106, governor
`schedutil`, 12 cores, pinned to core 11. Admission loadavg **0.12 before,
0.19 after**; nothing on the box above 1.7% CPU (the Disk Arcana sync daemon,
tailscaled, sshd). 101 timed rounds, 5 warmups, randomized per-round schedule
from a recorded seed, per-sample minimum reported with the median beside it.

| sample | orig | archive | best MB/s | median MB/s |
|---|---|---|---|---|
| html-large-web-codec-v2.html | 227968 | 14428 | 348.66 | 346.35 |
| json-api-large-world-benchmark-v2.json | 320976 | 18590 | 329.62 | 327.73 |
| json-api-medium-web-benchmark-v2.json | 98948 | 9630 | 258.46 | 257.00 |
| json-api-small-hypotheses-v2.json | 13880 | 1558 | 215.74 | 200.12 |
| tailwind.css | 65257 | 10361 | 171.79 | 170.48 |
| magic-string.umd.js.map | 112594 | 19058 | 171.24 | 169.86 |
| magic-string.umd.js | 42936 | 9375 | 134.81 | 134.09 |
| html-medium-home-v2.html | 25031 | 5563 | 130.58 | 128.66 |
| sourcemap-codec.umd.js.map | 9700 | 2407 | 124.05 | 122.43 |
| sourcemap-codec.umd.js | 14590 | 3522 | 119.88 | 117.18 |
| resolve-uri.umd.js | 9866 | 2797 | 113.12 | 111.42 |
| inter-latin.medium.woff2 | 23664 | 23650 | **55.76** | 55.23 |
| **corpus aggregate** | **965410** | **120939** | **222.76** | |

**Every one of the 12 samples individually clears the 50 MB/s bar**, the
slowest by 1.12x. The aggregate is total original bytes over summed best-case
times across the same 12 fixed files — a ratio of two measured sums, not an
average speedup claim.

**Stability.** Three seeds at 101 rounds gave 223.36 / 223.60 / 223.19 MB/s,
and an earlier 9-round run gave 221.88 — a 0.8% spread across every run taken.
The archived evidence run reports 222.76.

## Predictions: the direction held, both numbers were wrong

1. **GO predicted, GO measured.** The verdict leg was called correctly.
2. **Range WRONG.** Predicted 100-200 MB/s; measured 222.76, above the
   predicted band. The prediction was made from a contended-host read (107.35
   MB/s at loadavg 11.90) and I under-corrected for how much of that read was
   contention: the quiet host is 2.1x the contended one.
3. **woff2 prediction WRONG.** Predicted below 50 MB/s; measured 55.76. The
   mechanism given (all-literal stream, no copy speedup) is right — it *is* the
   slowest sample by 2.1x — but the literal path is faster than the prediction
   assumed.

## What this number is not

- **It is a floor for the architecture, not its ceiling.** The prototype's bit
  reader assembles each code index one bit at a time; production table-driven
  decoders refill a 32/64-bit buffer and peel codes from a register. This was
  stated in the preregistration before the number existed, and it stands: 222.76
  MB/s is what an unoptimised implementation of this format does.
- **It is not a competitor comparison.** No same-host gzip/brotli decode number
  is reported, deliberately — see the refusal below.
- **It is not measured on the historical stand.** `dev-ai` is running Aether
  node workloads and remains off-limits for compute; `arcana-devs` carries CI
  runners and a soak. The gate's bars are absolute B/s, so a different quiet
  host is admissible for them, but this number must not be lined up against
  CUBR-0074's cross-host ratio.

## Recorded refusal: hypothesis 11's 0.50 ratio is NOT re-evaluated here

The gate document is explicit that passing hypothesis-12 GO does not clear the
product, and that viability additionally requires re-evaluating hypothesis 11's
`decode_throughput_vs_brotli5 >= 0.50` on the same corpus and protocol.

That re-evaluation needs an **in-process** brotli-5 decode baseline. The only
brotli available on the host is the CLI, and a CLI-to-CLI comparison is
**biased in our favour**: process startup and file I/O are a fixed cost that
drags the faster decoder down proportionally more, inflating the ratio toward
1. Producing a number that flatters the candidate on a bar it might otherwise
miss is exactly the error class the programme's protocol exists to prevent.

**So no ratio is produced here, and none is estimated.** The re-evaluation is
registered as the next action: it needs an in-process brotli baseline (a
dev-dependency and a harness), and it belongs in its own slice with its own
preregistration.

## Two named follow-ups, neither silently taken

1. **woff2 is selected on density and pays for it in decode.** The web scheme
   wins that sample by 27 bytes (23650 vs a 23677-byte raw-store) and decodes
   at 55.76 MB/s where raw-store decodes at copy speed. Inside the
   decode-eligible class the encoder still picks purely on size, so it takes a
   0.11% density gain for a large decode-cost increase. A decode-cost-aware
   tie-break is the obvious fix and it requires a **constant** — how much
   density is a decode-class change worth. That constant is a registered
   criterion, not something this lane invents mid-measurement. **Named, not
   taken.**
2. **The bit reader is the cheapest known speed lever** and is untouched. It
   cannot change any verdict here (GO is already passed; WIN is blocked by
   density), so optimising it now would only inflate a number that decides
   nothing.

## DB discipline

`web_benchmark_hypothesis_evaluation` is **still 0 rows**; this session wrote
nothing to the database. The pass licenses a row, but writing it from inside
the measuring session is the wrong hand on the pen. Proposed contents, for the
archival orchestrator to write or reject:

```
hypothesis_id = 12  (web-profile-kill-gate)
verdict       = GO
ratio_vs_gzip9        = 0.9361      (criterion 38, bar <= 1.00)   PASS
decode_throughput     = 222760000   (criterion 39, bar >= 5.0e7)  PASS
ratio_vs_brotli11     = 1.1147      (criterion 36, bar <= 1.00)   FAIL -> no WIN
roundtrip_exact_match_rate = 1      (12/12, checked in the timed loop)
corpus  = cubr0074-web-real-v2
host    = arcana-agents (Ryzen 5 3600), pinned core 11, loadavg 0.12/0.19
evidence= documentation/ephemeral/research/CUBR-0076-DECODE-20260811/raw/
```

## The standing dual verdict, updated for the first time

The old form quoted whole: *archival worth pursuing (best single split 2.09x,
whole model 22.52x); web unreachable on this algorithm — density WIN 0.877644
never without decode 0.004410 in the same sentence.*

**That sentence is still true and its scope is now visible: it was always a
verdict about the algorithm, not about the product.** On the same corpus, a
different value scheme — static tables on the wire, zero decode-time adaptation
— holds gzip-9 density at 0.9361 and decodes at 222.76 MB/s on a quiet host,
clearing the registered GO gate by 4.46x. The web profile is alive. What it has
not done is win: brotli-11 density parity is missed by 11.5%, and hypothesis
11's ratio bar is unevaluated by the refusal recorded above.

## Reproduction

```
cargo build --release --example web_decode_bench
taskset -c <core> ./target/release/examples/web_decode_bench <payloads-v2> 101 5 20260811
```

Deterministic schedule from the seed. The harness asserts byte-exactness inside
the timed loop, so a run that reports numbers is a run whose every decode was
verified.
