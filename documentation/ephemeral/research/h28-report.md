# H-28 — Literal-stream context/PPM modelling is NO-GO (charged); literal floor is data-determined

**Class change:** out of the LZ/offset micro-efficiency domain (H-25l parse, H-26
offset-transform, H-27 context-offset — all closed). H-28 attacks the **LITERALS**.

**Question (brief):** on the mixed/near-duplicate tarball, how many residual bytes
sit in the literal block vs the match/token block, and does a context-mixing / PPM
order-2+ literal model (online learning, charged) recover the residual zstd gap?
If the literal floor is also data-determined, say so plainly.

**Codec:** committed H-27 head (1bca7c9). No code shipped — diagnostic only; codec.rs
byte-identical, so tuned 0.158273 + holdout 0.2390 stay byte-identical by construction.

## 1. Charged literal-vs-match breakdown (winning optimal-parse MODE_LZ container)

Fixtures regenerated reproducibly (same recipe as H-25l):
`srctree.tar` = `tar` of 120 × `/usr/include/*.h` (1310720 B); `multiversion.bin` =
last 3 git revisions of `codec.rs` concatenated (1021595 B). Env-gated dump in
`build_lz_container` (added then fully reverted).

| | srctree.tar | multiversion.bin |
|---|---|---|
| cubrim total | 231433 | 65277 |
| zstd-19 | 221518 (**+4.48 %**) | 61406 (**+6.30 %**) |
| gzip-9 | 274924 (cubrim −15.8 %) | 204141 (cubrim −68.0 %) |
| **literal blob** | **32382 B (14.0 %)** | **11982 B (18.4 %)** |
| **match/token block** | **199027 B (86.0 %)** | **53271 B (81.6 %)** |
| n_lits / n_matches | 42000 / 76187 | 15604 / 19462 |
| current lit coder | **lit_kind=1 (order-0 rANS)** | **lit_kind=1 (order-0 rANS)** |

Two structural facts up front:

1. **Literals are a minority of the output (14–18 %).** The match/token block
   (82–86 %) dominates, and that block is already at the offset-entropy floor
   (data-determined, information-conserved — H-25k/l, H-26 Gotcha #8, H-27 Gotcha #9).
2. **The literal residue is already coded by order-0 rANS.** The competitive
   `lit_kind` rail picks order-0 over both order-1 rANS *and* the nested
   BWT+geomix (context-mixing) pipeline. **Context-mixing on these literals was
   already tried by the existing pipeline and lost** — a measured fact, not a guess.

## 2. Charged literal-model probe (`probe_h28_literal_model.py`)

Run on the ACTUAL serialised literal residue (the winning optimal-parse stream).
Ideal H_k = knowledge-of-distribution lower bound. Real adaptive = a KT online
predictor (no transmitted table) — the bits a real range coder pays *while learning*
(Gotcha #9). Cell sanity = distinct contexts × 256 vs stream length.

**srctree.tar** literal stream n=42000, current order-0 rANS = 32382 B:

| model | bytes | obs/cell |
|---|---|---|
| ideal H0 / H1 / H2 / H3 | 32061 / 27855 / 16694 / **3356** | — |
| real adaptive o0 | 32211 | 164 |
| real adaptive o1 | **32069** | 1.59 |
| real adaptive o2 | 39328 (worse) | **0.029** |
| real adaptive o3 | 41490 (worse) | 0.005 |
| real PPM-C (o3 escape) | 34362 | — |

**multiversion.bin** literal stream n=15604, current order-0 rANS = 11982 B:

| model | bytes | obs/cell |
|---|---|---|
| ideal H0 / H1 / H2 / H3 | 11623 / 9672 / 4886 / **899** | — |
| real adaptive o0 | **11750** | 61 |
| real adaptive o1 | 12381 (worse) | 0.53 |
| real adaptive o2 | 14932 (worse) | 0.016 |
| real adaptive o3 | 15543 (worse) | 0.005 |
| real PPM-C (o3 escape) | 12615 | — |

**Best charged real model:** srctree 32069 B (save 313 B, 1.0 %, closes 3.2 % of the
9915 B zstd gap); multiversion 11750 B (save 232 B, 1.9 %, closes 6.0 % of the 3871 B
gap). And nearly all of that "saving" is just avoiding the order-0 rANS **table**
(~256–320 B) — an adaptive table-free o0, NOT a higher-order modelling win.

## 3. Why the ideal entropy is a mirage (Gotcha #9, now on literals)

The ideal H2/H3 collapse (srctree H3 = 3356 B, −90 % vs H0) is the classic
sparse-context overfit: at order-3 almost every context appears ~once, so it
"predicts" its single occurrence perfectly. A real online coder cannot realise this —
**0.005–0.029 obs/cell** means each high-order context is seen ~once, so learning
cost ≈ the symbol itself. Measured: adaptive o2/o3 are *15–28 % WORSE* than o0.

Root cause specific to LZ literals: the **optimal parse already ate the structured /
repetitive bytes as matches**. What remains as literals is the high-entropy residue —
precisely the bytes LZ could not match. It has no learnable high-order structure left
to model; its real floor is its order-0 entropy, and the current coder is within ~1 %
of it (32382 ≈ H0 32061 + table).

## 4. zstd cross-check

zstd-19 codes literals with an **order-0** entropy stage (Huffman literals section;
FSE is used only for the sequence symbols — literal-length / match-length / offset-code).
zstd does **not** PPM/context-model its literals either. Its edge on these fixtures is
therefore **not** a better literal model — it is sequence/parse micro-efficiency on the
82–86 % match block, exactly the data-determined floor H-26/H-27 closed.

## Verdict

**NO-GO. The literal floor is data-determined (order-0), same conclusion class as the
offset floor.** The literal residue is (a) only 14–18 % of output, (b) already coded
within ~1 % of its order-0 entropy, (c) un-improvable by higher order because the
post-optimal-parse residue is high-entropy and the streams are 100–1000× too short to
learn order-2+ contexts (0.005–0.03 obs/cell), and (d) coded the same way (order-0) by
zstd. Context-mixing was already tried (nested BWT+geomix lost to order-0 in the live
rail). The residual zstd gap (+4.5 % / +6.3 %) is **not** recoverable through the
literal coder; it is the match/token block's offset-entropy floor + zstd's FSE/parse
micro-efficiency — honest ceiling, not a missing model.

A table-free adaptive order-0 literal coder could bank ~230–310 B (the order-0 table)
as a regression-proof `lit_kind` candidate, but that is a <0.4 %-of-file micro-opt of
exactly the FSE/micro-efficiency class already ruled "not a structural win" — not the
literal-class win H-28 sought. No code shipped; codec stays byte-identical.

Added **Gotcha #10** (LZ literal residue is the high-entropy leftover after optimal
parse; its order-2+ ideal entropy is an overfit mirage; real adaptive loses at order≥2;
already at order-0 floor = zstd's own literal model).

Artefacts: `probe_h28_literal_model.py`, `h28-report.md`.
