# CUBR-0076 — charged size-model spike, preregistration

**Date:** 2026-08-11 UTC
**State:** prospective design only. No output of the model below has been
produced or inspected. This document commits the decision rule before the
candidate exists, per the standing protocol (ceiling before work, falsifiable
prediction before build, gates before measurement).
**Design-base commit:** `472be81dae400c29460d3f88092d9e19e5424a20` (freshly
fetched, exactly equal to `origin/main` when this was written; it cannot be the
execution revision because this uncommitted document is absent from it).
**Registry identity:** extends hypothesis **13** (`table-driven-entropy-stage`).
Never a duplicate row. No DB write is produced by this spike; `evaluation`
stays 0.

## What this executes

Step 1 of the implementation slice registered in
[`CUBR-0076-PROTOTYPE-SHAPE-20260806.md`](CUBR-0076-PROTOTYPE-SHAPE-20260806.md):

> a size-model of the web scheme on the 12 census samples that charges *every*
> decoder branch — static tables in the header included — with one cost term
> per decode branch, before any Rust. A GO from a model with fewer cost terms
> than decoder branches is unsound.

It is a **paper spike**. It ships no Rust, touches no `src/`, writes no DB row,
and makes **no timing claim** of any kind. Its single question is density:

> Can a value scheme whose decode is table-driven (static tables on the wire,
> zero decode-time adaptation) reach gzip-9 density parity (hypothesis 12 GO)
> or brotli-11 density parity (WIN) on the real web census, once every decoder
> branch is charged?

Throughput is out of scope by construction and stays a void until a quiet host
exists under the CUBR-0074 protocol.

## Why density is the only open question here

Decode-time architecture is already settled by measurement, all landed on main:
CM2 whole-model Amdahl ceiling 22.52x against a 113-227x need; GeoCM 0/12
routing on this corpus and >=8.9x short if it fired; the retrofit reading of
hypothesis 13 Amdahl-capped at 1.0206x (CUBR-0075 dependency-negative,
closed — not re-measured here). What was never measured is whether the
static-table architecture class can hold web density at all. That void is what
this spike fills, and it is fillable on any host because bytes are
load-insensitive.

## Frozen inputs

All already on `main` at the design-base commit; nothing is re-derived.

| Input | Path | Role |
|---|---|---|
| Payloads (12) | `bench/web-corpus/payloads-v2/`, sha256-pinned by `bench/web-corpus/manifest.v2.json` | model input bytes |
| Baselines | `documentation/ephemeral/research/CUBR-0076-DENSITY-20260806/baselines.tsv` | `gzip9`, `brotli11`, `zstd19`, `orig` |
| Today's static family | same dir, `static-detail.tsv` | per-slice best-static stream bytes |
| Today's champion | `.../CUBR-0076-WEBMODE-CENSUS-20260806/census.tsv` | CM2 `comp_bytes` |

**Column-provenance note.** `static-detail.tsv`'s header row is offset by one
against its data rows: the field labelled `static_min` carries the scheme
*name* (e.g. `vs_lz_rans`) and the field labelled `static_stream` carries that
scheme's *bytes*. This spike reads the bytes column and says so wherever the
number appears. Aggregates below are recomputed from the file, not copied from
prose.

## Aggregate reference points (recomputed from the frozen inputs)

Sum over the 12 census samples, bytes:

```
orig                          965410
CM2 (today's champion)         94385
brotli11  (WIN density bar)   108495
zstd19                        116662
gzip9     (GO density bar)    129193
best-static family today      158227
```

Distance today's static family must close, computed from those sums:

- to gzip-9 parity (GO): **-18.35%**
- to brotli-11 parity (WIN): **-31.43%**

(The state file quoted -19.2% / -32.1% from the `static_forced` column,
160626 B. Both columns are reported in the results; the tighter `-18.35%` /
`-31.43%` pair against the best-static column is the bar this spike is judged
against, because it is the harder-to-beat incumbent.)

## The charged decoder-branch inventory — one cost term each, no omissions

The model is unsound if any branch a decoder must execute is uncharged. Every
term below is charged in bits and reported as a separate line in the results,
and the itemised terms are asserted to sum exactly to the reported total (a
unit test, not a promise):

1. **Frame header** — magic, version, scheme byte, flags, original length
   (LEB128 varint), block count (varint).
2. **Per-block header** — final-block flag + block-type field.
3. **Table descriptors** — the code-length sequences for every alphabet in the
   block, RLE-coded (repeat-previous / repeat-zero-short / repeat-zero-long
   with their extra bits) and themselves Huffman-coded, plus the code-length
   alphabet's own lengths and the alphabet-size fields. **Static tables in the
   header are INCLUDED in the charge** (Gotcha #6). This is the term a model
   that "assumes entropy" silently drops.
4. **Literal symbols** — Huffman-coded from the real token histogram.
5. **Length symbols + extra bits** — code plus its extra-bit payload.
6. **Distance symbols + extra bits** — code plus its extra-bit payload.
7. **End-of-block / end-of-stream marker** — a real symbol in the alphabet,
   charged at its coded length, once per block.
8. **Checksum** — 4 bytes over the original bytes.

Entropy stage is **canonical Huffman with a 15-bit length limit** (package-merge
length-limited code construction), i.e. the class a table-driven decoder can
actually execute. No arithmetic/adaptive coder appears anywhere in the model.

## Soundness gates (all must pass before any number is reported)

- **Token-stream reconstruction.** Every parse must rebuild its input
  byte-exactly from the token stream alone. A parse that does not reconstruct
  is a void, not a result.
- **Kraft equality.** Every constructed code satisfies sum(2^-len) == 1 and
  max length <= its limit.
- **Accounting closure.** Itemised branch charges sum exactly to the reported
  compressed size.
- **Store floor.** Per file the scheme byte selects `min(modelled, store)`;
  store is charged header + checksum + original bytes. No file may be reported
  below its store cost through an accounting slip.

## Variants modelled (each a separately-charged, named delta)

- **V1 — whole-file window**, single block, one table set per file.
- **V2 — 64 KiB block window** (today's cube carrier), table set per block.
  Isolates the table-amortisation cost the carrier imposes.
- **V3 — V1 + context-split literal tables** (literals partitioned by a fixed
  function of the previous byte, tables frozen per block), charging the extra
  table descriptors and the context map.
- **Parse-quality axis** — hash-chain depth in {16, 128, 1024}, lazy matching.
  Reported for every variant; the parse quality used is stated as an explicit
  model term.

## The conservative-parse rule (binds the conclusion)

The model's parser is a hash-chain lazy parser, strictly weaker than
brotli-11's optimal parse. Therefore:

- A **GO** from this model is strong: a weaker parse already cleared the bar.
- A **NO-GO** is **not** a refutation of hypothesis 13 on its own. It must be
  reported as "NO-GO at parse quality Q", with the measured gap between parse
  qualities stated, and it may not be used to close the hypothesis unless the
  gap to the bar exceeds the demonstrated parse-quality span by a margin that
  the results doc names explicitly.

## Decision rule (committed before the candidate exists)

Judged on the aggregate over the 12 samples, best variant, best parse quality:

| Outcome | Condition |
|---|---|
| **WIN-density** | modelled total <= 108495 B (brotli-11 parity) |
| **GO-density** | modelled total <= 129193 B (gzip-9 parity) |
| **PARTIAL** | modelled total < 158227 B (beats today's static family) but > 129193 B |
| **NO-GO at parse quality Q** | modelled total >= 158227 B |

Per-media-family figures are reported per file. **No corpus-wide average
compression claim is made**; the aggregate above is a sum of the same 12 fixed
files, stated as such.

## Falsifiable prediction (committed before running)

**Predicted: GO-density met, WIN-density missed.** Predicted aggregate in the
range **112000-127000 B**, i.e. below gzip-9 (129193) and above brotli-11
(108495).

Mechanism behind the prediction, not curve-fitting: the modelled scheme is
deflate-class in its decode branches but has two advantages gzip-9 lacks — a
whole-file window (up to 320976 B here, against gzip's 32 KiB) and extended
distance codes — so it should clear gzip-9. It lacks the two things brotli-11
spends its density on: context modelling of literals beyond a single frozen
split, and the static dictionary. V3 is the term that could close part of that
gap; the prediction says it will not close all of it.

Secondary predictions:

- V2 (64 KiB blocks) costs measurably more than V1, because table descriptors
  are re-sent per block; predicted V2 - V1 > 0 on every multi-block sample.
- woff2 selects **store** in every variant.
- Parse depth 1024 beats depth 16 by less than 5% aggregate — i.e. the
  parse-quality term is small compared with the 18.35% GO gap, which is what
  licenses interpreting a near-miss.

Any of these being wrong is recorded as wrong in the results document.

## Disclosure classification (checked before publication)

The decoder-branch inventory, the wire-format shape, and the architecture-class
statement are **format/decoder-side → public**. The parser used here is a
textbook hash-chain lazy matcher and the context split is a fixed function of
the previous byte, both already-public technique — nothing new and
encoder-side is invented by this spike. If a later iteration's GO comes to
depend on a *new* encoder-side heuristic, that heuristic is NAMED and escalated
rather than published or silently crippled (standing rule, CUBR-0072/LEGAL-0062).

## Out of scope, explicitly

Timing, throughput, MiB/s, decode-cycle counts, any Rust, any `src/` change,
any DB write, any site or leaderboard change, and any statement about the
archival lane's hypotheses.
