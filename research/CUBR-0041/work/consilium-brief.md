# Cubrim CUBR-0041 — findings brief for multivendor consilium

You are one of a multi-vendor panel (deepseek + moonshot) reviewing a compression-research
diagnostic. Give an INDEPENDENT interpretation. Be concrete, skeptical, and terse.

## Context
Cubrim is an experimental lossless compressor competing on a 24-file world benchmark
(canterbury+silesia+calgary). Overall metric = size-weighted ratio (lower=better).
Leaders: ppmd 0.2286, xz 0.2344, 7z 0.2355, brotli 0.2408, zstd 0.2490. Cubrim ≈ 0.249, rank 6/10.
enwik8 (100MB text) dominates the size-weighted overall (~41% of bytes).

## Architecture facts (measured, not prose)
1. Cubrim ALREADY dispatches per-file at the MODE level (LZ / CUBE / CHUNKED / MED16 / SOA)
   and runs a competitive-min rail that picks the smallest output per file.
2. Of 12 CLI `--value-scheme` options, 6 (the rANS family) collapse to ONE byte-identical
   min output. The benchmark's cubrim numbers are reproduced exactly by explicit `order2-rans`.
   The CLI default (bitpack/CUBE) is a broken default for tiny files, NOT what the benchmark uses.
3. MEASURED THIS TASK (world corpus, 12 files, RT-verified, byte-exact):
   - oracle-overall (ideal per-file pick among EXISTING 12 schemes) = 0.262140
   - current competitive-min overall (order2-rans) = 0.262140
   - specialization ceiling on existing schemes = 0.000000 (ZERO — no file is better served by any non-rANS scheme) (absolute) / 0.000% relative
   - leader ppmd on same corpus = 0.239264 (my ref-sweep, same 12-file corpus; operator quoted 0.228591 is the 24-file benchmark)
4. Prior measured evidence (byte-exact, on-stand): a context-mixing (CM) backend (zpaq-m5 proxy,
   and a hand-written NEW-01 CM probe) BEATS the world leaders on nearly every class:
   text dickens 0.2055 vs ppmd 0.2253 (−9%), large exe mozilla 0.2351 vs 7z 0.2605 (−10%),
   code≥10KB beats brotli, 16-bit image beats delta filters. Loses to LZMA only on tiny-SPARC
   `sum` (38KB). CM probe is RT-OK, fast, no 64KB block cliff, +13–21% vs current backend on all text.
5. Per-type "specialization" levers that FAILED when measured (mirages): tiny-file dispatcher
   (competitive-min already routes), SPARC-BCJ (+0.96%), x86-BCJ (≤0.2%). The gaps are a
   MODEL-CLASS gap (order-2 → order-3+/CM), not a routing gap.

## The operator's strategic fork
The operator suspected cubrim might be running everything through one algorithm and only
looking at overall-average, hiding per-type wins. Decision needed: RESET (rebuild toward a new
algorithm) vs RE-AUDIT (fix the dispatcher to capture hidden per-type wins). The number above
is meant to decide it.

## Questions for you (answer each briefly)
1. Given oracle≈current (ceiling 0.000000 (ZERO — no file is better served by any non-rANS scheme)), is the operator's "hidden per-type wins lost in
   averaging" hypothesis SUPPORTED or REFUTED for the existing scheme space? Why?
2. Does the evidence point to RESET-LITE (add a CM value-scheme behind the existing competitive-min
   rail) or to RE-AUDITING the dispatcher? Justify from the numbers.
3. Verify-first catch: this build ALREADY ships mr=0.2104 (beats ppmd 0.2326) and x-ray=0.4451
   (beats ppmd 0.4544) — cubrim is already #1 on both images (the roadmap table showing mr rank-3
   is stale prose). Does measured-beats-prose change how much per-type value is already captured?
4. Any risk/blind-spot in concluding "specialization on existing schemes is exhausted" from a
   value-scheme-only oracle (the MODE/width axis was not swept)?
5. Steelman the OPPOSITE conclusion in 2 sentences.
