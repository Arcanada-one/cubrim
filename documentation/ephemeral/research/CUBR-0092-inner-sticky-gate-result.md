# CUBR-0092 inner sticky value-stream gate result

**Date:** 2026-08-02  
**Verdict:** KILLED by the pre-registered gate — implemented and measured, not shipped

## Gate

The pre-registered ship gate required all of the following:

- at least 1.50x end-to-end encode speedup on one representative image and one independent executable;
- byte-exact round-trip on every measured configuration;
- no target-file output growth above 1%; and
- at most +0.50% relative ratio cost on the 24-file corpus.

The measurement used the same host and harness for baseline and candidate: `dev-ai`, CPUs `0-15`, and `CUBR_THREADS=16`. These timings were measured on dev-ai (64 cores, pinned 0-15), not on the campaign stand `162.55.81.5` (16 cores). They are internally comparable baseline-versus-candidate timings on dev-ai and must not be compared with any N=24 campaign figure. The baseline binary SHA256 is `d2ee91bf8b2eec3c144183ebde06fb4e72bae5c89a96d23be8bd1e08fd60dd19`; the candidate binary SHA256 is `a9fec5a2a1c74d2337581afc28eae52a0225ee5d590033bdf8100a9191e27374`.

| Representative | Baseline encode | Candidate encode | Speedup | Compressed bytes | Round-trip |
|---|---:|---:|---:|---:|---|
| x-ray | 131.10 s | 98.67 s | 1.33x | 3,637,036 / 3,637,036 | PASS |
| ooffice | 222.34 s | 211.61 s | 1.05x | 1,763,460 / 1,763,460 | PASS |

## Evidence correction

The original `representative.tsv` had a corrupted `enc_rss_kib` column and has been renamed to `representative.raw.tsv`; the canonical TSV was regenerated from the `.time` files. The `217.44` candidate-ooffice value came from an earlier encode: its artifacts were born at 18:07:10 +0200, while a later encode overwrote the `.time` and output files at 18:12:11 +0200 with the authoritative `211.61` seconds. The candidate-ooffice encode cell is therefore n=2, with `211.61` selected for the gate and `217.44` retained as prior-run evidence. The final `211.61` blob was decoded in 78.21 seconds and compared byte-for-byte successfully. The corrected table also uses the authoritative baseline-ooffice decode time of 84.66 seconds rather than the stale 79.07-second value.

The two candidate runs have a 5.83-second spread (`217.44 - 211.61`), while the baseline-to-selected difference is 10.73 seconds (`222.34 - 211.61`), so the 1.05x executable result is not distinguishable from noise at n=2 versus n=1. The x-ray comparison is n=1 on each side; its 1.33x result is a single-run comparison, not a repeatability estimate.

Both speed cells miss 1.50x. Output growth is zero on both measured representatives, and both round trips pass, but those passing cells cannot clear the failed speed gate. The 24-file corpus sweep was stopped by the newer gate after 12 baseline rows and before any candidate corpus row. It is preserved as partial evidence; no corpus verdict is claimed, and no statement is made about the remaining corpus files.

## RSS observation

Encode peak RSS was 1,746,428 KiB baseline versus 1,542,056 KiB candidate for x-ray (-11.70%), and 6,662,864 KiB baseline versus 7,340,856 KiB candidate for ooffice (+10.18%). The selected RSS comparison is still one pinned run per representative; the extra candidate-ooffice run does not establish a distribution. These observations cannot distinguish measurement noise from retained candidate state. The cause remains unresolved; no memory benefit is claimed.

## Shipping boundary

The candidate source remains uncommitted and unmerged. No PR, deploy, production claim, or corpus-wide performance claim follows from this run. The corrected and raw evidence files are preserved on `dev-ai` at `/root/cubr0092-inner-sticky-20260802T155722Z`. The three campaign journals remain untouched.

The canonical `arcanada_cubrim.hypotheses` row `NEW-29` was extended rather than duplicated and records this result as `CUBR-0092`, `measured=true`, `status=closed`, with verdict `KILLED by pre-registered gate`.
