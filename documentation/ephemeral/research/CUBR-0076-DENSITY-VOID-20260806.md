# CUBR-0076 — the density void, filled: a static-decode scheme costs +69.4% today

**Measured:** 2026-08-06 UTC. Ratio-only, load-insensitive, byte-exact round
trip on every observation. Full provenance and raw profiler tables:
[`CUBR-0076-DENSITY-20260806/`](CUBR-0076-DENSITY-20260806/provenance.txt).
**Verdict:** the option "ship Cubrim's *existing* static scheme family as the
web profile" is **dead on the density leg alone** — it fails hypothesis 12's
GO floor (gzip-9 parity) by **23.7%** before any decode code exists. That is
the cheapest possible kill, in exactly the order the programme demands.
Hypothesis 13 (a *new* static scheme) stays alive, and now carries a measured
floor instead of a void.

## 1. The analytic bound first — and why it was not decisive

From held measurements only: the registered headroom to brotli-11 parity is
+13.9% on the CUBR-0074 aggregate (0.877644). The only held static-vs-adaptive
figure was old-corpus: T4 static-context Huffman 0.587240 vs the adaptive
champion 0.504412 — static **+16.4% relative**, already above the headroom *if
it transferred*. But corpus transfer is precisely what this programme's
gotchas forbid assuming, and the prediction indeed under-shot: the measured
web-corpus cost is **+69.4%**, four times the analytic figure, because the
relevant adaptive champion on web text is whole-file CM2, not the cube-family
mix — a gap the old-corpus numbers never saw. The experiment was therefore
necessary, and it was run.

## 2. What was measured

The stock binary's own committed 8-way value-scheme competition
(`--value-scheme bwt-rans` + `CUBRIM_PROFILE=1` — an existing measurement
knob; encoder defaults untouched; the emitted archive stays the stock CM2
winner). Every sample cut at the chunked path's own 64 KiB block boundary so
each unit is a single cube and every candidate's full wire stream (tables
included, by wire layout) is exact. Static-forced blob per slice =
`base − winner_stream + min(static streams)`, clamped at raw-store.

| sample | current (CM2) | static-forced | Δ | brotli-11 | gzip-9 | zstd-19 |
|---|---:|---:|---:|---:|---:|---:|
| css-medium-tailwind | 6,847 | 12,563 | +83.5% | 9,161 | 11,278 | 10,131 |
| html-large-web-codec | 10,629 | 23,452 | +120.6% | 11,746 | 15,804 | 13,543 |
| html-medium-home | 4,700 | 7,444 | +58.4% | 4,763 | 5,801 | 5,573 |
| js-medium-magic-string | 7,242 | 11,846 | +63.6% | 8,672 | 9,896 | 9,293 |
| js-medium-sourcemap-codec | 2,893 | 5,175 | +78.9% | 3,280 | 3,705 | 3,525 |
| js-small-resolve-uri | 2,420 | 4,274 | +76.6% | 2,467 | 2,895 | 2,802 |
| json-large-world-benchmark | 13,323 | 26,996 | +102.6% | 14,910 | 21,196 | 16,664 |
| json-medium-web-benchmark | 5,719 | 13,567 | +137.2% | 8,344 | 10,516 | 8,980 |
| json-small-hypotheses | 1,442 | 2,745 | +90.4% | 1,383 | 1,674 | 1,599 |
| source-map-large | 13,664 | 24,159 | +76.8% | 17,827 | 20,194 | 18,484 |
| source-map-small | 1,829 | 3,965 | +116.8% | 2,319 | 2,546 | 2,390 |
| woff2 (RAW passthrough) | 23,677 | 23,677 | 0.0% | 23,623 | 23,688 | 23,678 |
| **aggregate (Σ/Σ)** | **94,385** | **159,863** | **+69.4%** | **108,495** | **129,193** | **116,662** |

Baselines were produced with the exact binaries the web benchmark registered
(sha-verified against codec_build rows 4/5/6) and round-tripped 36/36. The
aggregate here is Σcompressed/Σcompressed; on that basis current-vs-brotli-11
is 0.869948 — close to, but not the same aggregate as, CUBR-0074's recorded
0.877644, and both sit inside the WIN criterion. Both figures are labeled so
neither is quoted as the other.

## 3. Against the two bars, as pre-registered

| | measured | bar | verdict |
|---|---:|---|---|
| static ÷ gzip-9 | **1.237** | ≤ 1.00 (hyp 12 **GO** floor) | **FAIL by 23.7%** |
| static ÷ brotli-11 | **1.473** | ≤ 1.00 (hyp 12 **WIN**) | **FAIL by 47.3%** |
| static vs current | +69.4% | +14.95% headroom (Σ/Σ basis) | overshoots ~4.6× |

The gap decomposes into two measured layers, and both matter for the lever:

1. **The cube carrier itself trails CM2 by +36.0%** on these samples
   (Σ base-with-family-min 128,373 vs Σ CM2 94,385) — even *with* the
   adaptive geomix streams, which won **every one of the 21 slices**.
2. **Going static inside the carrier adds +24.5%** on top (159,863 vs
   128,373); the best static stream was `lz_rans` on 19 of 21 slices.

The whole-file `MODE_LZ` candidate — the codec's zstd-shaped LZ+entropy
architecture, unavailable below 64 KiB — is better than the per-block static
family (e.g. html-large 16,122 vs 23,452) yet **still loses to gzip-9 on 3 of
the 4 multi-block samples** and loses to brotli-11 on all 4, even though its
sub-streams may adaptively help it (caveat in provenance).

## 4. What this kills, and what it leaves alive

**Dead, by measurement:** the zero-build option — routing the web profile to
the static schemes Cubrim already has. It fails the pre-registered GO floor
on density alone, before a line of decode code. Combined with the ceiling
document (GeoCM 0/12 and ≥8.9× short on speed), *every* existing-path route
to hypothesis 12 is now closed by measurement: adaptive paths fail the speed
leg, static paths fail the density leg.

**Alive, with a measured floor:** hypothesis 13's new scheme. To clear the GO
floor it must beat today's static family by **≥19.2%**; to reach WIN parity,
by **≥32.1%**. Brotli-11 itself is a static-table decoder, so the WIN target
is architecturally reachable *in general* — the open question is whether it
is reachable *from Cubrim's machinery*, and the measured two-layer
decomposition says the new scheme must first not lose the +36.0% the 64 KiB
cube carrier gives up, before it addresses the static-coding gap itself.
That is a large-window LZ/BWT + static-entropy design question — precisely
hypothesis 13 as registered, now with a quantified bar.

**Voids that remain voids:** decode throughput of any of this is unmeasured —
the quiet-host refusal stands (arcana-devs soak + CI, dev-ai forbidden), same
as the ceiling document recorded. Nothing from this experiment enters the DB:
`evaluation` stays 0, and the designed home for a pre-evaluation measurement
is this journal (per the DEPSTATE reconciliation — the schema itself refuses
evidence without an evaluation row).

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — best single split 2.09×, whole model 22.52×.
**Web: unreachable on this algorithm** — density WIN `0.877644` never ships
without decode `0.004410` in the same sentence; the gate needs 0.50 and the
measured miss is 113×. Today's result sharpens the web half: the density WIN
is a property of the adaptive model the web gate cannot afford, and removing
that model costs +69.4% of the density that made the WIN.
