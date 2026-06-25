# H-26 — pre-LZ transform to reduce distinct cross-file offsets (NO-GO)

Change of lever CLASS (H-25 exhausted the LZ-internal levers: parse/offset/literal).
Hypothesis: a transform applied BEFORE the matcher — cross-file dedup / long-range
reorder / dictionary-index — could lower the *data-determined* offset-entropy floor
itself by shrinking the number of distinct cross-file offsets. Charged-diagnose
first (Gotcha #6), permutation/dictionary transmission charged as a mandatory decoder
branch (Gotcha #7). Code SHA `705b29f` (H-25l); no code shipped by H-26.

Measured on regenerated long-range fixtures (srctree.tar = tar of /usr/include/*.h;
multiversion.bin = 3 git revisions of codec.rs). Current cubrim is the H-25l codec.

## Probe 1 — generic reorder / grid dictionary (charged, Gotcha #7)

A match coded as a source-bucket index of width W. The v1 model showed a phantom
win — until the **within-bucket precision** `log2(W)` per match is charged (the
decoder still needs the EXACT source byte). With it charged:

| file | W=64 | W=256 | W=1024 | W=4096 | bar (order-1 byte-split) |
|---|---|---|---|---|---|
| srctree.tar | x1.83 | x1.60 | x1.53 | x1.52 | 126716 B |
| multiversion.bin | x1.99 | x1.71 | x1.63 | x1.61 | 27368 B |

LOSES at every granularity. The bucket-index stream gets cheaper exactly as the
within-bucket stream gets more expensive — disorder relocates, it does not vanish.
Pure Gotcha #7. **NO-GO.**

## Probe 2 — CDC exact-dedup (the valid Gotcha-#7 escape)

Content-defined chunking + dedup of EXACT-equal chunks references each duplicate by a
**position-invariant chunk-id** (no within-offset — exact chunks are copied whole,
boundaries re-derivable from the residual). The charged-model (offset-only) suggested
a large win, because near-duplicate data with alignment drift makes LZ offsets
position-relative (expensive, ~15 bits) while chunk-ids are position-invariant
(cheap). multiversion shows 64–73 % exact-dup chunk mass — genuinely near-duplicate.

### End-to-end validation (Gotcha #6 — charge the FULL serialization)

Reversible dedup, residual compressed by the REAL cubrim codec, ref/flag streams
charged at order-1/order-0 entropy:

```
multiversion.bin  L=999210  current cubrim=64175  zstd=60978
  sanity cubrim(full) = 64175
  S=256 : residual 327699 (33%) -> cubrim(res)=63974 + flags=728 + refs=139 = 64841  LOSE (+1.0%)
  S=1024: residual 360211 (36%) -> cubrim(res)=64169 + flags=153 + refs=  3 = 64325  LOSE
srctree.tar  L=1310720  current cubrim=228989  zstd=221518
  S=256 : residual 1162895 (89%) -> cubrim(res)=228403 + 700 + 192 = 229295  LOSE
  S=1024: residual 1236745 (94%) -> cubrim(res)=228785 + 114 +  48 = 228947  ~tie (+42/-42, noise)
```

**Decisive measurement:** removing **67 % of multiversion's bytes** (the exact-dup
chunk mass) changed the cubrim output by only **201 B** (64175 → 63974). Those
duplicate bytes were ALREADY coded near-free by the LZ pipeline (cheap matches +
repeat-offset cache). The charged-model's "LZ pays 21566 B for that mass" was a
phantom: it priced the dup mass at the *average* 13 bits/match when the real cost
was ≈0.6 bits/match. Dedup then re-spends that information as residual + flags +
refs and lands WORSE. **NO-GO.**

## Verdict

NO-GO for the entire pre-LZ offset-reducing transform class. The offset-entropy
floor is genuinely data-determined and information-conserved: any transform that
reduces the *count* of distinct cross-file offsets must transmit the removed
information elsewhere (within-bucket stream, or residual + chunk-ref stream), and the
LZ pipeline was already coding that information at its floor. This is Gotcha #7
generalised from the distance-map/φ domain to the cross-file-offset domain, now
confirmed end-to-end: the duplicate structure LZ exploits is already near its
information content, so factoring it out pre-matcher conserves (slightly worsens) the
total.

The residual gap to zstd-19 on mixed/near-duplicate (srctree +3.4 %, multiversion
+5.5 %) is **not** a missing structural transform — it is zstd's mature FSE-offset +
btultra2 parse micro-efficiency. Cubrim's net picture stands: BEATS gzip on all
long-range shapes, matches/approaches zstd on pure-duplicate, +3–6 % on mixed/near-
duplicate, BEATS zstd on repetitive logs. Leaderboard frozen (tuned 0.158273,
holdout 0.2390 — byte-identical, no code shipped).

Artefacts: `probe_h26_offset_floor.py`, `probe_h26_dedup_e2e.py`.
