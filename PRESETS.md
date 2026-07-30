# CUBR-0087 Phase C — operating points

Cubrim is first on ratio (0.1890 against ppmd 0.2286 on the 24-file world corpus,
`meta_id=35`) and about 410× slower than ppmd to encode. Publishing only the
maximum-ratio point forces every user to pay 3 h 41 m for 300 MB. Publishing only
a fast point would give away the one thing Cubrim is best at. Both are true, both
are products, so the operating point is explicit and both are published.

## Rule this document is written under

**A preset that has not been measured on the real corpus does not exist.** No
preset is added here on the strength of an argument about what it should cost.
That is why this file currently defines **two** presets and not the three the
mandate sketched (`--fast` / `--balanced` / `--max`): `--fast` requires a
measurement that has not been taken, and inventing its numbers would be exactly
the fabrication the programme forbids.

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

Measured on 2 MB Silesia slices, byte-exact round-trip on every row:

| file | class | base variant | with column sweep | ratio cost | CM2 encode cost |
|---|---|---|---|---|---|
| xml | xml | 160,517 B in 53.2 s | 159,384 B in 173.9 s | **+0.71%** | **2.27×** |
| osdb | database | 496,824 B in 57.2 s | 472,809 B in 188.7 s | **+4.83%** | **3.30×** |

No effect on classes where a type transform wins (`ooffice` exe → `bcj_cm2`,
`x-ray` image → `med16`), because CM2 is not the winner there and the sweep never
runs.

**Wire-compatible in both directions.** The column model and its delimiter are
recorded in the blob's length header, so a `balanced` archive opens under `max`
and a `max` archive opens under `balanced`. Choosing a preset never strands data.

## Presets that do NOT exist yet, and what each is waiting for

### `--fast`

The intent is an operating point that trades real ratio for order-of-magnitude
speed — plausibly by not running the CM2 backend at all and falling back to the
LZ/rANS rail. The measurement that would define it has **not** been taken, so it
is not defined here. Two things must be measured first:

1. the ratio at each candidate configuration, on the world corpus, not a slice;
2. whether the resulting ratio stays under the refusal threshold below.

### A memory-budget preset

The single largest memory lever is CM2's table sizing:
`tbits_for(len) = clamp(ceil_log2(len) + 3, 18, 27)`, so any input ≥ 16 MB gets
`tbits = 27` and a **13.50 GiB** model — 75% of the measured 18,439 MiB peak.

**This cannot be a preset in its current form, and the reason is a wire-format
constraint, not a measurement gap.** The decoder re-derives `tbits` from
`orig_len` using the same function, so the table size is *not in the blob*. An
archive written under a smaller cap is only decodable under the same cap. The
development override (`CUBRIM_CM2_TBITS`) is documented at its call site as
sweep-only for exactly this reason.

A shipping memory knob therefore needs the exponent recorded in the wire format —
a header field or a preset byte — before any preset may select it. That is a
format change and is out of scope for a task that has not measured what the
smaller tables cost in ratio.

## Hard refusal, inherited from the consilium

**`--max` ratio above ~0.21 is refused outright.** At that point Cubrim is an
expensive ppmd (0.2286) and the product claim dies. No preset may be added, and no
lever accepted into `max`, that crosses it.

Every preset states its trade in measured numbers or it does not ship.

## Status

| preset | defined | measured | shipped |
|---|---|---|---|
| `max` | yes | it *is* the current benchmark row | flag implemented, reachable from `compress` and `a` |
| `balanced` | yes | 2 MB slices only — **not the world corpus** | flag implemented; not yet benchmarked end to end |
| `fast` | no | no | no |
| memory budget | blocked on wire format | no | no |

`balanced`'s numbers come from 2 MB slices. Before it appears on a public
benchmark it needs a full-corpus run on a quiet host, because a ratio measured on
a slice is not a ratio on the corpus — the project's own rule is that a ratio is
only valid against the corpus it was measured on.
