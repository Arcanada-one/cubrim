# PROBE NEW-04 — LZMA-class backend (LZ77 + range coder, pos/state/rep contexts)

Date: 2026-08-09. Worktree main = d212c1c. Probe stage only — no Rust, no prereg, no push.

## 0. Routing check against current main (BEFORE ceiling)

Hypothesis DB numbers are STALE. Meta-36 (current, preset max) says:

| file    | cubrim (now) | hypothesis claimed | leader xz/7z/brotli/rar (now) | gap now |
|---------|--------------|--------------------|-------------------------------|---------|
| samba   | 0.14528      | "0.1934"           | xz 0.17307                    | cubrim AHEAD by 16.1% |
| nci     | 0.04633      | "0.0478"           | xz 0.04319                    | cubrim BEHIND by 7.3% |
| xml     | 0.06328      | "0.0907"           | brotli 0.08055                | cubrim AHEAD by 21.4% |
| mozilla | 0.23912      | "0.3066"           | 7z 0.26053                    | cubrim AHEAD by 8.2%  |
| ooffice | 0.28664      | "0.4357"           | rar 0.37425                   | cubrim AHEAD by 23.4% |

4 of 5 target files no longer have a gap — the CM2 whole-file flagship overtook the
LZ77-mechanic leaders since the hypothesis was filed. The hypothesis's target group
has collapsed to ONE file: nci (xz leads by 0.00314 ratio = 105,421 bytes on
33,553,445 input).

Source verification (code/cubrim-rs/src/codec.rs @ d212c1c):
- LZ rail EXISTS and already has most "LZMA-class ingredients" the consilium routing
  assumed missing:
  - rep-distance codes: YES — 3-slot MTF cache, modes 0/1/2/3 (LZ_REP_INIT,
    lz_repcode_classify, codec.rs ~9600-9640). LZMA has 4 slots + rep0-long.
  - optimal parse: YES — DP cost minimisation with binary-tree match finder
    (lz77_parse_optimal, H-25i/H-25j, codec.rs 9893+), competitively picked vs
    greedy+lazy at file level (encode_lz_prepass, codec.rs 2268).
  - literal coder: static rANS, min(order-0, order-1 fallback-table)
    (lz_rans_encode, codec.rs 10730+). NOT pos/prev-byte-contexted, NOT adaptive,
    no match-byte prediction.
  - flags: order-1 rANS over {0,1}; dist modes: order-1 rANS over {0..3};
    lengths/new distances: order-0 byte-split rANS; H-25k zstd-style offset codes
    + H-25g combined varint sequence coder exist as competitive alternatives.
- Genuinely MISSING vs LZMA:
  1. (state, posState) conditioning of the match/literal decision — LZMA's 12-state
     machine × pb position bits; cubrim codes flags order-1 on previous flag only.
  2. Literal coder contexts lc/lp (prev-byte high bits × position low bits) and
     match-byte prediction (post-match literal XOR-exclusion).
  3. Adaptive bit-probability coding — LZ rail is static-table rANS (two-pass);
     LZMA updates probabilities per symbol. (Adaptive coding exists elsewhere:
     BwtAdaptive scheme 9, cm2.rs, geocm.rs — but not in the LZ rail.)
  4. Length coder conditioned on rep-vs-new and posState; distance-slot conditioned
     on length; aligned low-bits context.
  5. rep0-long (1-byte matches at rep0); LZ_MIN_MATCH=3.
- Consilium routing said "solve in LZ+literal-coder, NOT CM". Against current main
  this routing is MOOT for 4/5 files (CM2 already won them) and only arguable for
  nci.
- Brief's 64KB-ceiling caveat: confirmed CM2 codes whole file; MODE_LZ container is
  also whole-file (full prior window, distances up to u32). The 64KB chunking
  applies only to the cube/value-stream rail (codec.rs). No 64KB gate on this
  hypothesis.

## 1. CEILING (stated before probe, per file, reference-derived)

Basis: meta-36 measured competitor ratios (quotable reference). Hypothesis target =
"xz −1..−3% on the group". An LZMA-class backend's mechanism ceiling is xz -9e
itself, minus a small margin for a better parse/newer literal coder; I take
ceiling = xz × 0.97 (the hypothesis's own most optimistic figure).

| file    | cubrim now | xz/7z/brotli-leader | LZMA-class ceiling (leader×0.97) | headroom vs cubrim |
|---------|-----------|---------------------|----------------------------------|--------------------|
| samba   | 0.14528   | 0.17307 (xz)        | 0.16788                          | NONE (ceiling 15.6% WORSE than current cubrim) |
| nci     | 0.04633   | 0.04319 (xz)        | 0.04190                          | −9.6% (~148 KB) — only live target |
| xml     | 0.06328   | 0.08055 (brotli)    | 0.07813                          | NONE (23% worse than cubrim) |
| mozilla | 0.23912   | 0.26053 (7z)        | 0.25271                          | NONE (5.7% worse than cubrim) |
| ooffice | 0.28664   | 0.37425 (rar)       | 0.36302                          | NONE (26.6% worse than cubrim) |
| SUM (5 files, bytes) | 19,042,975 B (computed from ratios×orig) | leaders sum 21,266,517 B | — | cubrim already 10.5% below the leader-sum |

So the mechanism ceiling of "an LZMA-class backend that lands at xz−3%" is ABOVE
(worse than) current cubrim on samba/xml/mozilla/ooffice. The entire remaining
opportunity is nci: 0.04633 → best case 0.04190.

## 2. PROBE PLAN (before running)

Per brief Gotcha #6 cheap probe: on 2–4 MB slices of samba and xml (and nci, the
only live target), decompose xz's edge into (a) raw match-finding/window,
(b) rep-codes + entropy backend, (c) pos/state/literal contexts, (d) parse quality:
- gzip -9      : greedy-lazy, 32 KB window, no rep-codes, static Huffman.
- zstd -19 --long=27 : big window + 3 rep codes + FSE, near-optimal parse, NO
                 pos/state literal contexts, no adaptive bit coder.
- xz -9e (lc=3,lp=0,pb=2 default) : full LZMA2 = contexts + adaptive coder + parse.
- xz --lzma2=preset=9e,lc=0,lp=0,pb=0 : same parse/window, contexts stripped →
                 (xz_default − this) isolates the pos/prev-byte context ingredient.
- xz --lzma2=preset=9e,mode=fast,nice=16,depth=4 : same contexts, crippled
                 match-finder/parse → isolates parse-quality ingredient.
All slices labelled SLICE-4M (first 4 MiB). Ratios are slice-local (size/4194304),
NOT comparable to full-file meta-36 ratios; used only for ingredient attribution.

Decoder-branch cost audit (Gotcha #6) for the proposed backend is in §4 of the
final verdict: every LZMA branch (is_match, is_rep, is_rep_g0/g1/g2, is_rep0_long,
literal w/ match-byte, len choice/choice2/low/mid/high, dist slot, align bits,
direct bits) must carry a cost term; the probe's xz arms price them empirically as
a bundle.

## 3. PROBE RESULTS (SLICE-4M = first 4 MiB of each file; sizes in bytes; PROBE)

Commands: gzip -9 | zstd -19 --long=27 -T1 | xz -9e -T1 |
xz -T1 --lzma2=preset=9e,lc=0,lp=0,pb=0 |
xz -T1 --lzma2=preset=9e,mode=fast,nice=16,depth=4 | both ablations combined.

samba SLICE-4M: gzip 1,069,416 (+63.41% vs xz9e) | zstd 672,502 (+2.76%) |
  xz9e 654,424 | xz lc0lp0pb0 655,588 (+0.18%) | xz fast-mf 803,140 (+22.72%) |
  noctx+fastmf 804,348 (+22.91%)
xml SLICE-4M: gzip 400,209 (+44.18%) | zstd 290,192 (+4.55%) | xz9e 277,572 |
  xz lc0lp0pb0 278,324 (+0.27%) | xz fast-mf 407,020 (+46.64%) |
  noctx+fastmf 407,424 (+46.78%)
nci SLICE-4M: gzip 390,594 (+71.69%) | zstd 251,952 (+10.75%) | xz9e 227,504 |
  xz lc0lp0pb0 227,232 (−0.12%: contexts slightly HURT) | xz fast-mf 358,312
  (+57.50%) | noctx+fastmf 358,412 (+57.54%)

Ingredient attribution (bundle bounds, PROBE):
- pos/state/prev-byte literal contexts (lc/lp/pb — the headline NEW-04 ingredient):
  +0.18% / +0.27% / −0.12%. NEGLIGIBLE on all three files.
- match-finder + optimal-parse quality (9e BT4-optimal vs fast/nice16/depth4):
  22.7% / 46.6% / 57.5% of the coded size. DOMINANT ingredient.
- everything-beyond-zstd bundle (adaptive bit coder + BT4 optimal parse margin +
  4th rep + rep0-long + len/dist conditioning): zstd→xz = 2.76% / 4.55% / 10.75%.
  Upper bound on what a full LZMA-class coder adds over a zstd-class engine.

## 4. Decoder-branch cost audit (Gotcha #6/#7) for the proposed backend

An LZMA-class wire format implies ~12 decoder branch families, each needing a cost
term: is_match[state×posState], is_rep[state], is_rep_g0/g1/g2[state],
is_rep0_long[state×posState], literal tree[2^lc×2^lp ctx + match-byte mode],
len choice/choice2, len low/mid[posState]/high, dist slot[len ctx], dist direct
bits, dist align bits. The probe empirically prices the context-conditioned subset
(everything that distinguishes LZMA contexts from a flat zstd-style coder that
cubrim already has): ≤0.3% on samba/xml, negative on nci. Most of the proposed
branches do not pay for their decoder complexity; the paying ingredient
(match-finder/parse strength) requires NO new decoder branch at all — cubrim's
existing MODE_LZ wire already decodes any better parse the encoder finds.

## 5. VERDICT: NO-GO (hypothesis as framed). nci residual → re-route, different mechanism.
