# PROBE NEW-13 — typed-column codec bank, competitive-min per column → common rANS

Worktree: /home/dev/.worktrees/cubrim/PROBE-NEW13 @ d212c1c

## Routing check (source, before probe)

Verified in `code/cubrim-rs/src/codec.rs` @ d212c1c:

- MODE_COLUMNAR (line ~1267): TEXT-delimited tables only (`,\t;|`), per-column modes
  raw / ASCII-numeric delta / decimal-scale delta. No binary typed columns.
- MODE_BINFLOAT (`encode_binfloat`, line 2081): f32-only, record widths {12,16,20,24,28,32},
  per-column bank of exactly TWO codecs: raw vs arithmetic wrapping u32-delta, competitive
  min per column over the FULL column (not a prefix). No XOR-delta, no f64, no zigzag+FOR,
  no dict, no RLE, no u8/u16/u64 widths, no BE variants.
- MODE_SOA (line 3342): byte transpose at `soa_detect_width` stride (4..=64, lag-W L1 dip),
  nested re-encode. No per-column codec choice at all.
- MODE_RECORDCM (line 4425, CUBR-0061/FH-10): record-aware CM, contexts = base CM 9 inputs
  + record-offset + previous-same-field, optional per-offset SSE. This is the CURRENT sao
  champion (FH-10: width=28, beat 7z by ~13% rel).
- MODE_VCF: PBWT genotype matrix (specialized).
- MODE_CM2: whole-file CM flagship — current osdb champion (FINDINGS osdb.2m attribution:
  cm2 472,809 B beats record_cm 563,034 B on the 2 MB slice).
- "64KB ceiling": only the cube/value-stream rail is 64 KB-chunked; CM/CM2/RECORDCM code in
  8 MB blocks (CM_BLOCK_SIZE), CM2 whole-file. The routing's "расширяет
  MODE_COLUMNAR/VCF/BINFLOAT" is accurate but INCOMPLETE: it omits that record-shaped
  binaries are already served by MODE_RECORDCM/MODE_SOA, which are stronger model classes
  (context mixing) than bank→order-0 rANS.

Bank codecs already existing vs missing:
- EXIST: raw (everywhere), arithmetic u32-delta LE (binfloat), text-numeric delta/decimal
  (columnar), byte transpose (soa), RLE as a generic stream stage (`rle.rs`, value-stream
  rail) but NOT as a per-column candidate.
- MISSING: delta-u8/u16/u64, BE variants, zigzag+FOR, XOR-delta f32/f64, per-column dict,
  per-column RLE, prefix-based (4 KB) O(1) auto-selection, typed schema search.

## Targets and current cubrim bytes (meta-36, preset max — CURRENT numbers)

| file | orig | cubrim ratio | cubrim bytes | best competitor |
|---|---|---|---|---|
| sao | 7,251,944 | 0.5253835 | 3,810,124 | 7z 0.608654 |
| osdb | 10,085,684 | 0.2169406 | 2,187,996 | ppmd 0.236641 |
| kennedy.xls | 1,029,744 | 0.0233922 | 24,088 | rar 0.034538 (cubrim leads — verified) |
| x-ray | 8,474,240 | 0.4291873 | 3,637,076 | ppmd 0.454471 |
| mr | 9,970,564 | 0.2077646 | 2,076,532 | ppmd 0.230793 |

## CEILING (stated BEFORE probe)

Mechanism: the hypothesis class is per-column reversible transform → order-0 entropy
coding ("выход — в общий rANS"). Its information-theoretic ceiling per file is
  Σ_columns min_codec [ adaptive-order-0 cost of codec output ]  (oracle codec choice,
  zero header) — computable cheaply; it CANNOT exploit cross-record sequential
  correlation beyond what the chosen transform linearizes, whereas the current champions
  (RECORDCM on sao, CM2 on osdb) are mixed high-order models. A-priori mechanism
  expectation: oracle-bank ≥ current cubrim bytes on sao/osdb (bank does not beat the
  rail); the bank's value would be infrastructure (NEW-11/12) and/or files where typed
  transforms (XOR-delta floats) expose structure CM byte-contexts miss.

Numeric ceilings (oracle pass, run FIRST, before the 4KB-prefix probe pass — see
ceiling-pass output below; reference ceilings from meta-36 = best competitor, quotable):

- sao: cubrim 0.52538 -> reference floor: no competitor below cubrim (7z 0.60865);
  class ceiling = oracle-bank number measured in ceiling pass.
- osdb: cubrim 0.21694 -> same structure; class ceiling = oracle-bank number.
- kennedy.xls: cubrim 0.02339 (already #1 by 32% rel over rar) -> class ceiling =
  oracle-bank number; expectation: far above 0.0234 (kennedy needs BIFF/row-sharing
  modelling, not order-0 columns).
- x-ray / mr: only if record stride is detected (stride pass); else VOID for this
  hypothesis (not record-structured at ≤512-byte lag).

## Ceiling-pass output (oracle bank, run before prefix probe)

4 MB head slices (kennedy whole file). ceiling = greedy typed partition + oracle
full-column codec choice, zero header, per-column adaptive-H0(+MDL) model (optimistic:
per-column stats + planar split; a truly shared rANS would be worse).

| file | slice | stride | oracle-bank bytes | oracle ratio | prorated cubrim (meta36) | xz -9 same slice |
|---|---|---|---|---|---|---|
| sao | 4,194,304 | 28 | 2,580,770 | 0.6153 | 2,203,616 (0.5254, prorated) | 2,562,596 (0.6110) |
| osdb | 4,194,304 | 4 (weak, forced=source gate) | 3,400,443 | 0.8107 | 909,916 (0.2169, prorated) | 1,204,420 (0.2872) |
| kennedy.xls | 1,029,744 (full) | 13 | 120,074 | 0.1166 | 24,088 (0.0234, measured full) | 49,116 (0.0477) |
| x-ray | 4,194,304 | 4 | 1,983,894 | 0.4730 | 1,800,157 (0.4292, prorated) | 2,223,788 (0.5302) |
| mr | 4,194,304 | 4 | 1,341,367* | 0.3198* | 871,486 (0.2078, prorated) | 1,092,272 (0.2604) |

*mr: the 4KB-prefix pass found a better partition (per-byte RLE, 1,320,485) than the
greedy oracle — greedy schema is not a true partition oracle; class ceiling for mr is
min(1,320,485, greedy) = 1,320,485 (0.3148).

Prorating caveat (cross-check): FINDINGS osdb.2m measured cm2 = 472,809 B on the 2 MB
head (0.2364 on-slice) vs prorated 0.2169 — prorating flatters cubrim by ~9% rel on osdb;
does not change any conclusion (bank oracle is 2.8-3.7x worse either way).

## Probe pass (4 KB-prefix competitive-min, full Gotcha-#6 header charged)

| file | probe bytes | probe ratio | vs oracle |
|---|---|---|---|
| sao | 2,619,332 | 0.6245 | 98.5% of oracle (prefix loss 1.5%) |
| osdb | 3,400,465 | 0.8107 | ~100% |
| kennedy.xls | 133,658 | 0.1298 | 89.8% |
| x-ray | 1,983,916 | 0.4730 | ~100% |
| mr | 1,320,485 | 0.3148 | better than greedy oracle (see *) |

## Routing criteria (real extracted columns, sao stride 28)

- float XOR-delta >= +5% vs plain delta: **FAIL** on all four sao float columns:
  f64@0 -3.75%, f64@8 +1.20%, f32@20 -1.00%, f32@24 -6.02%. XOR-delta never reaches
  +5%; on 3/4 columns arithmetic delta is strictly better.
- int8 RLE >= +10% vs raw: **PASS** (sao 1-byte col @offset 6: RLE 30,118 bits vs raw
  884,057 bits, +96.6%; kennedy prefix pass also selects RLE on 6/13 byte-columns).

## Conclusion

Class ceiling (oracle bank -> order-0) is ABOVE current cubrim bytes on every target:
sao +17.1%, osdb +274%, kennedy +398%, x-ray +10.2%, mr +51.5% worse. The prefix
auto-selection mechanism itself works (<=1.5% loss vs oracle on record files, 10% on
kennedy), but the model class it selects within cannot reach the rail's CM-family
champions. NO-GO as a ratio lever; resurrect only if NEW-11/12 independently advance
and need the bank as plumbing.
