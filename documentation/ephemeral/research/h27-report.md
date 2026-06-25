# H-27 — context-modelled offset coding (NO-GO, charged)

Target: the residual mixed/near-duplicate gap to zstd-19 that H-26 isolated as
parse/FSE micro-efficiency. Lever: context the offset code on recent state (prev
offset-byte / prev bucket / match-length class) instead of the current context-free
order-0 byte-split. Charged-diagnose first (Gotcha #6); code SHA `705b29f` (H-25l),
no code shipped by H-27.

Measured on the dumped winning MODE_LZ parse (new-distance stream, rep-cache applied
— exactly what `lz_encode_token_streams` serialises). The current coder byte-splits
each new distance into b0..b3 and codes each **order-0** rANS.

## The conditional-entropy mirage and how it dies

| stream | order-0 (current) | order-1 IDEAL (H1\|prev) | static-rANS o1 | adaptive o1 (real) |
|---|---|---|---|---|
| srctree.tar    | 131346 B | 119535 B (−9.0 %) | 131346 B (+0.0 %, tables eat it) | **137204 B (−4.5 % WORSE)** |
| multiversion   |  33588 B |  26483 B (−21.2 %) |  33588 B (+0.0 %) | **35710 B (−6.3 % WORSE)** |

Three independent charges, each killing the lever harder:

1. **Static order-1 rANS** (the codebase's `rans_order1_encode`): serialises a full
   freq table per prev-byte context (≥16 obs). For near-uniform offset low-bytes
   that is ~256 contexts × ~256 nonzero syms = **+126 KB (srctree b0) / +50 KB
   (multiversion b0)** of tables — 10–20× the ideal saving. The competitive min
   picks order-0 everywhere → +0.0 %.

2. **Adaptive order-1 range coder** (no tables, like scheme-9/10/11): the honest GO
   bar. A real online KT-smoothed order-1 predictor over the 256-symbol byte
   alphabet has 256×256 cells but only 18 K–70 K symbols to learn from (~1 obs/cell).
   The learning cost — coding early symbols near-uniform before the model adapts —
   **exceeds** the conditional-entropy saving: adaptive o1 lands **−4.5 % / −6.3 %
   WORSE** than the current order-0. The ideal H1 assumed perfect knowledge of the
   distribution; the stream is far too short to acquire it.

3. **Low-cardinality contexts that WOULD be learnable** (offset-code bucket | prev
   bucket, or | match-length class) carry negligible signal even ideally: bucket
   H0 35626 → H1|prevbucket 35180 (−1.3 %), H1|lenclass 34451 (−3.3 %). Nothing to
   realise once learning is charged.

The whole-byte offcode+raw-bits alternative stays worse than the byte-split
(srctree offcode 127641 vs byte-split 131346 — but the byte-split *real* coder beats
both; H-25k already established this). delta-coding the bytes gives +0.0 % (offsets
are not globally monotonic — they jump between the inter-version distance clusters).

## Verdict

NO-GO, no Rust. The only context with a meaningful conditional-entropy gain
(prev-byte, ideal −9 %/−21 %) is **unlearnable** at these stream sizes — a real
adaptive order-1 byte coder LOSES to order-0 (−4.5 %/−6.3 %), and the static-table
variant loses far worse (+50–126 KB). The learnable low-cardinality contexts
(bucket / len-class) carry ≤3 % even before learning is charged. zstd does not beat
us here with order-1-on-offsets either — it uses repcodes (Cubrim has the rep cache)
plus a single adaptive FSE offset-code table (Cubrim's byte-split is already
competitive, H-25k). The residual gap is not recoverable by offset-code context
modelling.

Picture unchanged (no code shipped; codec = committed H-25l):
- srctree.tar    1310720 -> 228989 vs zstd 221518 = +3.4 % (gzip 274924, beats −17 %)
- multiversion.bin 999210 -> 64175 vs zstd 60978 = +5.2 % (gzip 198710, beats −68 %)

Leaderboard frozen (tuned 0.158273, holdout 0.2390 — byte-identical). Added Gotcha
#9 (the conditional-entropy probe is an asymptotic floor; charge a real online
predictor and beware high-cardinality contexts on short streams).

Artefact: `probe_h27_ctx_offset.py`.
