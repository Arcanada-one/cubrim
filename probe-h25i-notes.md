# PROBE H-25i — integration-status lane notes (written BEFORE probe runs)

Worktree: /home/dev/.worktrees/cubrim/PROBE-H25I @ d212c1c (current main).

## 1. Integration status (from source + git history, verified before ceiling)

All H-25 parser-line commits are ancestors of d212c1c (checked with
`git merge-base --is-ancestor`):

- 0077d2b H-25i optimal DP parser
- 8881245 H-25j-lite rep-offset-aware DP cost
- 01617c8 H-25j-full binary-tree match finder (union with hash chain)
- edabfe0 H-25k FSE/rANS offset model (seq_format 2)
- 705b29f H-25l DP offset-cost recalibration (LZ_OFF_COST_SCALE=0.70)
- eb883f2 status: H-25l STOP-clean line

Source: `code/cubrim-rs/src/codec.rs` — `lz77_parse_optimal` (line 9908) carries
the H-25i DP, H-25j-lite rep-aware `match_cost` with rep cache on the incumbent
path, H-25j-full BT finder (`son`/`bt_head`, line ~9979), H-25l
LZ_OFF_COST_SCALE=0.70. It is called from `encode_lz_prepass` (line 2276),
which is the MODE_LZ whole-file container, gated on input > cube_size_limit
(64 KB) and offered as a competitive-min candidate against base/CM2/columnar/
etc. — active on every multi-block encode at every preset, wins only when
strictly smaller.

Verdict on status: **integrated-and-active** (competitive candidate on the
>64 KB whole-file rail), NOT "интеграция не завершена". Both consilium-named
next steps (BT finder = H-25j-full, rep-aware price = H-25j-lite) landed, plus
two steps beyond (H-25k, H-25l), and the line was closed with a STOP-clean
status commit. The only fragment of the hypothesis text NOT on main is the
full "state-aware цена под LZMA-слой" (LZMA-style state-machine price); the
DP price is rep-aware + coder-efficiency-calibrated but not state-machine-aware.
H-25l's own commit message records the residual to zstd as an offset-entropy
floor ("~64K distinct cross-file offsets, data-determined"), not parse
optimality.

## 2. Meta-36 LZ-class standings refresh (measured, quotable)

Hypothesis-text numbers (srctree +5.1% / multiversion +6.4% to zstd) are
internal mixed-tarball bench figures and are STALE for corpus claims; meta-36
wins:

| file | cubrim | xz | 7z | brotli | zstd | best-ref | cubrim vs best-ref |
|---|---|---|---|---|---|---|---|
| samba | 0.145278 | 0.173075 | 0.174012 | 0.174316 | 0.179454 | xz | cubrim AHEAD 16.1% rel |
| mozilla | 0.239116 | 0.261150 | 0.260534 | 0.270834 | 0.292224 | 7z | cubrim AHEAD 8.2% rel |
| xml | 0.063279 | 0.081360 | 0.085122 | 0.080551 | 0.084788 | brotli | cubrim AHEAD 21.4% rel |
| nci | 0.046335 | 0.043193 | 0.051900 | 0.045294 | 0.048145 | xz | cubrim BEHIND 7.3% rel |

Only **nci** still shows an LZ-class deficit (vs xz, and marginally vs brotli
0.045294, −2.2% rel). samba/mozilla/xml premises of the hypothesis are
satisfied/overtaken on current main.

## 3. Ceiling (stated BEFORE probe, per file, reference-derived)

Basis: the best measured optimal-parse reference (meta-36) bounds what a
btultra/LZMA-class parser upgrade can be worth on cubrim's winning rail.

- samba: 0.145278 -> ceiling ≤ 0.145278 (xz 0.173075 already beaten; reference
  ladder shows NO measurable parser headroom on the shipped number).
- mozilla: 0.239116 -> ceiling ≤ 0.239116 (7z 0.260534 beaten; none).
- xml: 0.063279 -> ceiling ≤ 0.063279 (brotli 0.080551 beaten; none).
- nci: 0.046335 -> 0.043193 (xz -9 basis; −6.8% rel is the entire
  demonstrated parser+format headroom on LZ-class files).

Slice-probe expectation (samba 4 MB head): ladder should order
gzip-9 > zstd-19 > zstd-22 ≥ xz-9, and cubrim (competitive rail, likely CM2
winning the pick) at or below xz-9. Any cubrim>xz gap on the slice is
slice-local and must not be projected to the whole file without the whole-file
meta-36 number in hand (it is: cubrim wins whole-file samba).

## 4. PROBE results (run AFTER the ceiling above; all figures measured)

Binary: `/home/dev/.worktrees/cubrim/PROBE-H25I/target-c/release/cubrim`
(cubrim 0.3.2; built 2026-08-09 12:39:48 UTC in this worktree, 7 min after the
d212c1c commit timestamp — taken as built-from-HEAD). Slices: 4,194,304-byte
heads of silesia samba and nci (SLICES, not whole files).

samba 4 MB head (PROBE, slice):
- gzip -9:         1,069,416 B (0.25497)
- zstd -19:          672,666 B (0.16038)
- zstd --ultra -22:  671,873 B (0.16019)
- xz -9:             659,084 B (0.15715)
- cubrim compress (preset max default): 516,577 B (0.123162), round-trip OK,
  rerun byte-identical.
- CUBRIM_PROFILE=1 attribution: winner = cm2 (516,577). lz_prepass candidate
  (the rail carrying ALL of H-25i/j/k/l) produced 719,585 B and LOST the pick
  — it is larger than xz -9 by +9.2% and larger than the CM2 winner by +39.3%.

nci 4 MB head (PROBE, slice):
- gzip -9:           390,594 B (0.09313)
- zstd -19:          252,833 B (0.06028)
- zstd --ultra -22:  252,276 B (0.06015)
- xz -9:             255,932 B (0.06102)
- cubrim: 201,576 B (0.048059), rerun byte-identical.
- Attribution: winner = cm2 (201,576); lz_prepass = 257,788 B, LOST
  (larger than zstd-22 and xz on the slice).

Whole-file nci context (meta-36, measured): cubrim 0.046335 vs xz 0.043193.
The slice shows cubrim AHEAD of xz at 4 MB scale (0.0481 vs 0.0610); xz's
whole-file lead materialises only with the full 33.5 MB in view — the nci
deficit is a whole-file long-range/scale effect on the CM2 rail, not a
4 MB-scale parse-optimality effect.

## 5. Parser-headroom conversion (honest, per Gotcha #6)

The ladder spread gzip-9→xz-9 (samba slice: 1,069,416→659,084, −38.4%) bounds
parser+format value jointly, not parser alone. Within cubrim, the only surface
a btultra-class parser touches is lz_prepass — and on both probed gap-class
files that candidate loses the competitive pick to CM2 by 21.6% (samba slice:
659,084 xz vs 516,577 cm2) / 28% (nci slice). Even a PERFECT parser closing
lz_prepass's entire remaining gap to xz (719,585→659,084) leaves it 27.6%
above the CM2 winner: leaderboard effect = 0 bytes. Product-level parser
headroom on the meta-36 gap files is therefore 0; the one real deficit (nci
whole-file, −6.8% rel vs xz) is mechanistically out of the parser's reach.

## Gotcha #6 honesty note (decoder branches)

The reference ladder rungs change BOTH the parser and the entropy/format
branches (gzip: Huffman lit/len/dist; zstd: FSE LL/ML/OF + literal Huffman;
xz/LZMA: state machine + rep0..3 + context-coded literals). So
(gzip-9 − xz-9) is an upper bound on "parser" value that silently includes
format-branch value; a parser-only claim inside cubrim's MODE_LZ wire format
may not take credit for it. Within MODE_LZ's actual decoder branches
(token kind, rep-mode index, offset, length, literal residue — all already
priced in the DP), H-25l measured the remaining gap as offset-entropy floor,
i.e. parser-side headroom within the current format ≈ exhausted.
