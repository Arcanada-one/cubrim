# H-39 — Small-file class (<64KB structured): micro-efficiency ceiling (NO-GO)

**Status:** NO-GO (multiply-confirmed micro-efficiency ceiling). No Rust written — every
candidate lever was spiked/charged and none beats zstd-19/brotli-11 structurally.

**Class targeted:** small (<64KB) structured text losers where Cubrim trails zstd:
`alternatives.log` (18708 B, +27.8% vs zstd), `deals_record.csv` (17796 B, +7.0%).

## Diagnosis

The competitive rail already picks Cubrim's best scheme (BwtGeoMix, scheme 11, mode 0).
Cubrim beats gzip-9 but loses to zstd-19 / xz-9 / brotli-11 (brotli leads).

| file | cubrim | zstd-19 | brotli-11 | xz-9 | gzip-9 | H2 (ideal) | LZ-match |
|---|---:|---:|---:|---:|---:|---:|---:|
| alternatives.log | 1238 | 969 | **921** | 1076 | 1166 | 1364 | 98% |
| deals_record.csv | 3799 | 3549 | **3289** | 3452 | 4290 | 3404 | 90% |

`alternatives` is 98% LZ-matchable — an LZ-ideal file; Cubrim's BWT+geomix already codes
*below* order-2 entropy (1238 < H2 1364), but zstd/brotli win via superior LZ. `deals`
sits *above* its order-2 floor (3799 > 3404) but the floor is unreachable (see below).

## Levers spiked (faithful) — all NO-GO

1. **Optimal-parse LZ + repcode for small blocks (research Lever 1, HIGH a priori).**
   Temporarily lowered the >64KB gate so small files get the MODE_LZ optimal-parse +
   repeat-offset path. Result: both files **still chose mode 0 (geomix)** — MODE_LZ
   produced ≥1238 on alternatives, i.e. Cubrim's optimal+repcode LZ does **not** beat
   zstd-19 (969). The LZ gap is parse/FSE micro-efficiency, not a missing mode. (gate reverted, codec byte-identical.)
2. **Columnar field-split on small CSV (H-30).** `deals` columnar probe = 3702 single-blob,
   but the real `MODE_COLUMNAR` (kblob + colmodes + headers) lands ≥3799 — small-file
   **framing overhead** eats the win, and even the 3702 floor > zstd 3549.
3. **Shipped static dictionary (research Lever 4, brotli's mechanism).** `zstd --train`
   on other logs (cross-file, realistic) → alternatives **970 vs no-dict 969 (ZERO gain)**;
   even an overfit dict trained *including* alternatives → 966 (−0.3%). A dictionary helps
   `<1KB` cold-start files (zstd docs: 500% under 1KB, ~10% at 64KB); at 18KB the file's
   own LZ history dominates and the dictionary is **dead**.
4. **Reaching the order-2 floor on `deals` (3404 < zstd 3549).** Static order-2 rANS pays
   prohibitive table cost at 18KB; adaptive order-2 is unlearnable (256×256 cells, ~0.27
   obs/cell — Gotcha #9, confirmed H-27/H-28). The H2 floor is an overfit mirage, not reachable.

## Verdict

**NO-GO — micro-efficiency ceiling.** The small-file gap to zstd-19/brotli-11 is composed
of zstd's repcode-efficient LZ parse, brotli's order-2 literal context model, and brotli's
static-dictionary cold-start — all **micro-efficiency / format-level**, none a structural
transform Cubrim's BWT+rANS+LZ can close (external research Lever 5: "DEAD as a structural
path"). The one structural candidate (shipped dictionary) gives **zero** benefit at 18KB.

This mirrors the logs (H-36, 1.29× ceiling) and the general-purpose gap (H-25l/26/27/28):
the residual is data-determined micro-efficiency. **Class-final picture:** Cubrim WINS the
columnar/telemetry sub-class decisively (H-30/H-31: forex −40/−44%, status −4.6%, class
aggregate −22.1% vs zstd, −44.5% vs gzip) and beats gzip everywhere; the logs and small
structured files are micro-efficiency ceilings with no remaining structural lever.

**Operator decision point** (no autonomous lever remains for the ceilings): (a) accept the
ceiling — ship Cubrim as a telemetry/columnar specialist that crushes gzip universally and
beats zstd on its sub-class; (b) a brotli-class rewrite (static dictionary + order-2 literal
context for <1KB cold-start) — a different architecture, large, and overfit-prone; (c) a
domain-specific `--csv`/`--log` mode that relaxes gates (modest, sub-zstd on most logs).

**Code SHA:** spikes run on `a4ba861` (codec byte-identical after revert). Leaderboard untouched, NOT pushed.
