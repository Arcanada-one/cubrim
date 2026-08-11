# CUBR-0087 Phase C — operating points

Cubrim is first on ratio (0.1890 against ppmd 0.2286 on the 24-file world corpus,
`meta_id=35`) and about 410× slower than ppmd to encode. Publishing only the
maximum-ratio point forces every user to pay 3 h 41 m for 300 MB. Publishing only
a fast point would give away the one thing Cubrim is best at. Both are true, both
are products, so the operating point is explicit and both are published.

## Rule this document is written under

**A preset that has not been measured on the real corpus does not exist.** No
preset is added here on the strength of an argument about what it should cost.
That is why this file defines `max`, `balanced` and `web` but **not** `--fast`,
which the mandate sketched: `--fast` requires a measurement that has not been
taken, and inventing its numbers would be exactly the fabrication the programme
forbids. `web` is here instead, and was not in the original sketch, because the
measurement produced a need the sketch did not anticipate — a decoder memory
ceiling that blocks another epic.

## Presets that exist

### `--preset max` (default)

Every competitive candidate runs, including the CM2 column-position variants.
**Byte-identical to the shipped v0.3.2 encoder** — this is not a new operating
point, it is the existing one, named.

Reachable from both `cubrim compress` (the benchmark path) and `cubrim a` (the
product path). Before this task the archive path had no configuration at all:
`archive.rs` called `encode(&data)`, so the operating point was selectable only
from the hidden internal subcommand the benchmark uses. A preset the benchmark can
select and the product cannot is not a product feature.

### `--preset balanced`

Drops the FH4-03 CM2 column-variant passes. `cm2_encode` otherwise encodes the
input once for the base model **and once more per candidate column delimiter** (up
to two extra full passes) while the decoder replays exactly one — the measured
origin of the corpus-level 4.11× encode/decode asymmetry.

Measured end to end on **dev-ai (aether), 64 cores, load 0.36**, fixed 8-core pin,
byte-exact round-trip on every row:

| file | class | native | `balanced` | output cost | **encode speedup** |
|---|---|---|---|---|---|
| dickens | text | 461,437 B in 80.8 s | 472,253 B in **26.9 s** | +2.35% | **3.00×** |
| ooffice | exe | 677,605 B in 93.9 s | **677,605 B** in 94.0 s | **0** | **1.00× — no-op** |

**The `ooffice` row is not a disappointment, it is the honest shape of the
lever.** On a class where a type transform wins, CM2 is not the winner and the
column sweep never fires, so `balanced` emits the *byte-identical* blob and saves
nothing. This was predicted before the run and confirmed by it.

**Therefore: `3.00×` is a text/xml/database figure, not a corpus figure.** Any
public claim must name the classes it applies to. Saying "3× faster" unqualified
would be misleading on exactly the half of the corpus where the competitors are
strongest.

**Wire-compatible in both directions.** The column model and its delimiter are
recorded in the blob's length header, so a `balanced` archive opens under `max`
and a `max` archive opens under `balanced`. Choosing a preset never strands data.

### `--preset web` — bounded decoder memory

Caps the CM2 table exponent at 20 and drops the column variants.

This one exists because of a finding that outranks presets. The **decoder**
rebuilds the same model tables the encoder used, sized from `orig_len`, so
decoding a file of ≥ 16 MB needs **~12.3 GiB** — measured across scopes in the DB,
not estimated. `wasm32` has a **4 GiB** address space. The web-codec decoder
(`CUBR-0077`) could therefore not exist at any size that matters, and
`CUBR-0075`'s "bounded decoder memory" acceptance criterion could not be met at
any setting.

Measured, `dickens` 2 MB slice, byte-exact round-trip:

| cap | output | vs native | **decode peak RSS** |
|---|---|---|---|
| none (=24 here) | 461,437 B | — | 1.47 GiB |
| 22 | 466,176 B | +1.03% | 0.40 GiB |
| **20 (`web`)** | 476,746 B | **+3.32%** | **0.109 GiB** |
| 18 | 499,852 B | +8.32% | 0.033 GiB |

**The memory figure is class-independent** — decode peak lands at 0.107–0.109 GiB
at `tbits = 20` on both `dickens` and `ooffice`, because decode is CM2 alone
whatever won at encode time. That is the number the web-codec epic needs and it
does not vary by input type.

**Compatibility, stated precisely because I got it wrong first.** The exponent
travels in the CM2 length header (bits 56..60, `0` = derive as before), so:

- `max` and `balanced` archives leave the field zero, are **byte-identical** to
  what earlier builds produced, and decode **everywhere including older
  decoders** (verified: sha `2840d51a…` on both builds, and the pre-change binary
  reads new uncapped output).
- A `web` archive **needs a decoder that reads the field**. An older decoder does
  not silently produce wrong bytes — verified, it fails closed with
  `DecodeError: MODE_CM2: coded stream exhausted before orig_len bytes decoded`,
  exit 2, no output file — but it cannot open the archive.

So choosing `web` is a decision about who can read the result. It is the right
default for a browser and the wrong one for an archive you hand to someone with an
older binary.

An explicit exponent can only ever **shrink** the derived one (`effective_tbits`
clamps to `min(declared, derived)`). Without that clamp a 214-byte crafted blob
could request 2^27 tables and regain the QA-F-007 model-amplification vector that
bound was added to close.

## Presets that do NOT exist yet

### `--fast`

Still does not exist. The intent is an operating point that trades real ratio for
order-of-magnitude speed — plausibly by not running the CM2 backend at all. The
measurement that would define it has **not** been taken, so it is not defined
here, and its numbers are not guessed.

## Hard refusal, inherited from the consilium

**`--max` ratio above ~0.21 is refused outright.** At that point Cubrim is an
expensive ppmd (0.2286) and the product claim dies. No preset may be added, and no
lever accepted into `max`, that crosses it.

Every preset states its trade in measured numbers or it does not ship.

## ⚠ Compatibility warning — read before choosing `web`

**A decoder that predates the table-exponent field CANNOT read a `--preset web`
archive.** It does not misread it and it does not return wrong bytes; it stops:

<!-- gate:literal -->
```
Error: DecodeError: MODE_CM2: coded stream exhausted before orig_len bytes decoded
exit status 2, no output file written
```
<!-- /gate:literal -->

Verified by running an older binary against a capped archive, not inferred.

`max` and `balanced` archives are unaffected — they leave the field zero, are
**byte-identical** to what pre-field builds produced, and open on any decoder old
or new. Only `web` narrows the audience, and it narrows it to builds carrying the
field. Choosing `web` is a decision about **who can open the result**, and it
should be made once per distribution channel rather than per file.

## Status — and what "status" means here

The word *shipped* was used in an earlier revision of this file and was wrong in
two independent ways, so the ladder is now explicit:

| stage | `max` | `balanced` | `web` | `fast` |
|---|---|---|---|---|
| implemented | ✅ | ✅ | ✅ | ❌ |
| measured | it *is* the current benchmark row | ✅ 2 MB slices, 2 classes | ✅ 2 MB slices, 2 classes | ❌ |
| **reachable from the CLI** (`compress` **and** `a`) | ✅ | ✅ | ✅ | — |
| merged to `main` | ❌ | ❌ | ❌ | — |
| in a released binary | ❌ | ❌ | ❌ | — |

**Why the two corrections matter:**

1. The compiled artefact under the default `target/` lagged the source by an hour,
   so for a while the flag existed in `cli.rs` and *not* in the binary a user
   would run. The measurements were legitimate — they went through the library
   API — but a library-reachable option is not a user-reachable one. The CLI row
   above exists because that distinction is exactly what got blurred.
2. Even with the flag in the binary, all of this lives on branch
   `CUBR-0087-speed-memory`. It is **not on `main` and not in any release**; the
   latest release is `v0.3.2` (2026-07-25), which predates every preset.

So: implemented, measured, and CLI-verified — **not** available to users.

## Corpus numbers (2026-07-31) — these supersede every slice figure above

Full 24-file world corpus, 314,749,364 bytes, **round-trip OK on all 24 files in
every run**:

| preset | archive bytes | corpus ratio | vs `max` | rank vs field |
|---|---|---|---|---|
| `max` | 59,489,703 | **0.189007** | — | **#1**, 17.3% clear of ppmd |
| `balanced` | 59,768,178 | **0.189891** | **+0.47%** | **#1**, 16.9% clear |
| `web` | 65,035,750 | **0.206627** | **+9.32%** | **#1**, 9.6% clear |

(ppmd 0.228592, xz 0.234411 on the same corpus.)

`max` reproduces `meta_id=35`'s `0.18900658684095069371` to six decimals on a
different host — the strongest available evidence the harness is sound.

**Both slice estimates above were wrong, in opposite directions.** `balanced` was
overstated ~5× (+2.35% slice vs **+0.47%** corpus) because the column sweep is a
no-op wherever CM2 does not win, and most of the corpus is in that position.
`web` was understated ~3× (+3.32% vs **+9.32%**) because a 2 MB slice derives
`tbits = 24` — capping to 20 costs four steps — while a real corpus file ≥ 16 MB
derives 27 and the same cap costs **seven**. The slice structurally could not show
the real price.

**The headline this licenses:** the 13.5× decoder-memory cut does not cost the
ratio lead, it narrows it from 17.3% to 9.6%. Publish it that way — as a corpus
number, per operating point, never as a single "Cubrim is X" figure.

**One caution:** `web` at 0.206627 sits close to the consilium's ~0.21 refusal
threshold. That threshold was set for `--max` and `web` is a different operating
point, so it is not breached — but the margin is thin enough that any further
ratio-costing lever stacked onto `web` must be re-checked against it rather than
assumed to have headroom.
