# CUBR-0076 — proposed shape of the web-profile prototype

**Written:** 2026-08-06 UTC, after the gate statement and the ceiling
measurement, per the brief's ordering. This document proposes; it ships
nothing. `decode()`, the wire format, encoder defaults, `cube_size_limit`,
`cm_should_try`, and `prof.rs` are untouched.

## What the measurements force

1. **Routing is dead.** GeoCM never fires on web content (0/12 census,
   2026-08-06) and would be ≥ 8.9× short of the laxest bar if it did
   (ceiling doc, anchors B–D).
2. **Optimising CM2 decode is dead.** The Amdahl limit of deleting the entire
   CM2 model is 22.52×; the gate needs 113× (vs 0.50 × brotli-5). A 5×
   shortfall survives even the unreachable limit.
3. **Therefore the profile is a different decode-time architecture.** The
   gate's GO bar implies a decode budget of ~72 cycles per output byte on
   3.6 GHz-class hardware (WIN: ~18). Adaptive per-bit modelling costs
   thousands-to-tens-of-thousands of cycles per byte in every measured Cubrim
   mode. The only architecture class in that budget is **table-driven /
   static-table entropy decode** — brotli, zstd, and every ≥ 100 MB/s decoder
   live there. This is precisely pre-registered hypothesis **13**
   (`table-driven-entropy-stage`, GO: `scheme_flag_effective`,
   `ratio_vs_brotli11 ≤ 1`, decode ≥ 100 MB/s; WIN: ≥ 250 MB/s).

### Relation to CUBR-0075's measured negatives (added 2026-08-06)

CUBR-0075's `dependency-negatives` artefact records a measured negative
labelled "Dependency 13": the range-coder primitive calls inside CM2 decode
are 2.0185% of substage cycles, so **retrofitting** a table-driven coder into
the existing path is Amdahl-capped at 1.0206×. That negative is about the
retrofit, and it is closed — do not re-measure it. The lever proposed here is
the *other* reading of hypothesis 13, the one its ≥ 100 MB/s GO bar has always
implied: a new value scheme whose decode has **no adaptive model at all**. The
0075 measurement supports rather than contradicts this route — it proves the
decode cost is the model (95.55% of cycles), not the coder. Full scope
analysis: [`CUBR-0076-DEPSTATE-RECONCILIATION-20260806.md`](CUBR-0076-DEPSTATE-RECONCILIATION-20260806.md).

## Proposed shape (specification for the prototype slice)

- **An encoder-side profile, not a decoder patch.** `--profile web` (final
  flag name owned by the implementation slice) selects a value-scheme whose
  decode is table-driven: static entropy tables (canonical Huffman or
  FSE/static-rANS) transmitted in the blob header, no per-symbol model
  adaptation at decode time. The existing strong encode-side machinery
  (BWT, columnar, LZ pre-passes) may still shape the stream — what changes is
  that the decoder consumes *frozen* tables.
- **Competitive per-file selection with a scheme byte**, the architecture
  Gotcha #4 already proved regression-proof: the encoder writes
  min(web-scheme, existing) only when the web profile is requested, and the
  scheme byte makes decode unambiguous. Store/RAW passthrough is retained
  as-is — the census shows it is already the correct behaviour for
  pre-compressed families (woff2, ratio 1.0005, copy-speed decode).
- **Block-parallel (hyp 14) and SIMD (hyp 15) are follow-on multipliers**,
  not part of the first prototype: the first prototype must prove the
  single-core table-driven budget, because parallelism cannot rescue a
  per-byte cost that is orders of magnitude over budget (hyp 14's own GO
  requires ≥ 50 MB/s single-core first). Dictionary (hyp 16) and reduced
  window (hyp 17) are density/memory levers on top, each with registered
  criteria.
- **Kill gate:** hypothesis 12, exactly as registered — GO at gzip-9 parity +
  50 MB/s, WIN at brotli-11 parity + 200 MB/s, byte-exact round-trip on every
  observation, evaluated only on a quiet host under the CUBR-0074 protocol.

## The density cost, stated from measured numbers only

Density is the win this project has: **0.877644 vs brotli-11 on the real web
corpus** (never quoted without decode `0.004410` in the same sentence). The
profile spends density to buy decode speed, and the spend must stay visible:

- **Measured headroom to the WIN criterion:** `ratio_vs_brotli11 ≤ 1` allows
  the aggregate output to grow at most **+13.9%** over today's measured
  0.877644 (1 / 0.877644 = 1.1394) before density parity with brotli-11 is
  forfeited. That headroom is derived from a measured number, not assumed.
- **The only measured price of a decode-friendly reconfiguration so far:**
  the `lowmem-decode` preset costs **+3.32% output** for its memory bound —
  measured on 2 MB slices of two files (dickens, ooffice) and scope-limited
  exactly as recorded; it is a *precedent magnitude*, not a prediction for a
  static-entropy stage.
- **The static-entropy density cost on the web corpus is a void.** It is the
  first number the prototype phase must produce, and it goes in as a measured
  range per media family, not an assumption. Until then the honest statement
  is: measured precedent +3.32% (different lever, slice scope), registered
  ceiling +13.9% (WIN) / gzip-9 parity (GO), actual cost **unmeasured**.

## Ordered next actions for the implementation slice

1. **Cheap charged spike first** (Gotcha #3/#6/#7 discipline): a size-model
   of the web scheme on the 12 census samples that charges *every* decoder
   branch — static tables in the header included — with one cost term per
   decode branch, before any Rust. A GO from a model with fewer cost terms
   than decoder branches is unsound.
2. **Prototype behind a scheme flag** in an isolated branch; encoder-side
   only; byte-exact round-trip on all 12 samples as the first gate.
3. **Density range measured per media family** on the census corpus
   (load-insensitive, can run on this host), published next to the existing
   ratios in this directory.
4. **Throughput evaluation deferred to a quiet host** under the CUBR-0074
   protocol; the refusal stands until stand time exists. No number is
   estimated in the meantime, and `evaluation` stays 0.

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — best single split 2.09×, whole model 22.52×.
**Web: unreachable on this algorithm** — density WIN `0.877644` never ships
without decode `0.004410` in the same sentence; the gate needs 0.50 and the
measured miss is 113×.
