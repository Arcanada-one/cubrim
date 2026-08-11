# PROBE NEW-14 (nci residual lane) — notes. CEILING SECTION WAS WRITTEN BEFORE ANY RUN.

Date: 2026-08-11. Original location: /home/dev/.worktrees/cubrim/PROBE-NEW14/
documentation/ephemeral/research/probes-20260809/ — that worktree was REMOVED
by another session mid-probe (after the ceiling + xz-ladder + mechanism
sections were written there, before the cubrim prefix runs finished). This
file is the faithful reconstruction in the probe scratchpad; sections 1-4
are byte-content-identical to what was committed to the worktree file before
deletion (all content was authored in-session and re-emitted verbatim).
Lane: locate + mechanism-attribute the cubrim-vs-xz crossover on nci (the
only remaining LZ-class density deficit, +7.3% rel, ~105 KB whole-file).
Extends row NEW-14, no new row.

## 1. Routing / source check (BEFORE probe)

Verified in `code/cubrim-rs/src/cm2.rs` (worktree @ current main, before deletion):

- Match models m1/m2/m3: M1_MIN=6, M2_MIN=3, M3_MIN=12 (consts at ~line 500).
- Each is a direct-mapped table `vec![0u32; 1<<tbits]` storing the ABSOLUTE u32
  position of the last write of that slot. `Match::end` inserts at EVERY
  position (`buf.len() >= minlen`); lookup happens only when `len == 0` and
  does NOT verify the gram at the candidate — `ptr = cand+1; len = 1`
  immediately. A slot collision therefore injects a live false predictor
  (soft cost via mixer, not a correctness bug).
- Hash: `h = 0xABCDEF01 ^ minlen; for j in 0..minlen { h = h*0x85EBCA77 +
  buf[t-j]; h ^= h>>13 }; slot = h & mask` — replicated exactly in the probe.
- `tbits_for(len) = clamp(ceil_log2(len)+3, 18, 27)`, TBITS_MAX=27. Per nci
  prefix: 4 MB -> 25, 8 MB -> 26, 16 MB -> 27, 33.5 MB -> 27 (capped;
  uncapped would be 28). Positions/slots load: 0.125 / 0.125 / 0.125 / 0.25 —
  the table STOPS growing between 16 MB and whole-file while the data doubles.
- CM2 codes the whole file (no 64 KB ceiling) — consistent with prior records.
- MODE_LZ whole-file rail (`encode_lz_prepass`, codec.rs) exists as a
  competitive-min candidate (H-25i/j/k/l all on main per probe-h25i notes).

## 2. CEILING (stated BEFORE probe, per prefix; basis = xz "preset max" on the exact prefix)

Reference definition: for each nci prefix P in {4, 8, 16, 33.5 MB}, the
ceiling for cubrim on P is xz's ratio on that exact prefix (xz parity = the
demonstrated LZ-class reference; whole-file xz 0.0431929 from meta-36).
Residual(P) = cubrim_ratio(P) − xz_ratio(P).

Anchors already measured (NOT re-run):
- 4 MB prefix (probe-h25i, slice): cubrim 201,576 B = 0.048059; "xz -9"
  255,932 B = 0.061022. Residual vs that = −0.012963 (cubrim AHEAD).
- Whole file 33,553,445 B (meta-36 anchor): cubrim 0.0463348; xz 0.0431929.
  Residual = +0.0031419 (cubrim BEHIND 7.27% rel, ≈ 105.4 KB).

Mechanism predictions committed BEFORE runs (falsifiable by the runs):
- If the deficit is CM2 match-table eviction/collision at scale, cubrim's
  ratio should hold near xz-or-better through 16 MB (load still 0.125,
  tbits grew with the input) and the crossover should fall between 16 and
  33.5 MB, where load doubles to 0.25 with no table growth; the Python table
  simulation should show the m3 true-retrieval rate dropping / false-candidate
  rate rising markedly in the same interval.
- If instead xz's ratio simply improves with window size faster than cubrim
  degrades (nci ultra-repetitive; xz -9 dict = 64 MB covers the whole file),
  the per-prefix xz curve will fall steeply while cubrim's stays ~flat, and
  the crossover will not coincide with any simulated table-stress inflection
  -> hypothesis refuted as an eviction story.

## 3. Reference ladder runs (measured 2026-08-11, xz 5.4.5, round-trip cmp OK on every row)

Discrepancy found and resolved: plain `xz -9` on the whole file gives
1,738,884 B = 0.051824, NOT the meta-36 anchor. `xz -9e` gives 1,449,272 B =
0.043193 — matches the meta-36 anchor to 6 decimals. Meta-36 "preset max"
xz is therefore `-9e`; the ceiling reference uses **xz -9e** (the anchor
wins per brief). probe-h25i's 4 MB "xz -9" 255,932 B is reproduced exactly
by plain -9 (its slice ladder was plain -9; cubrim still beats the -9e
number at 4 MB, so no prior conclusion flips).

| prefix | bytes | xz -9 | ratio | xz -9e | ratio (CEILING ref) |
|---|---|---|---|---|---|
| 4 MB | 4,194,304 | 255,932 | 0.061019 | 227,504 | 0.054241 |
| 8 MB | 8,388,608 | 490,312 | 0.058450 | 424,176 | 0.050566 |
| 16 MB | 16,777,216 | 899,664 | 0.053624 | 760,672 | 0.045340 |
| full | 33,553,445 | 1,738,884 | 0.051824 | 1,449,272 | 0.043193 |

xz -9e improves monotonically with prefix size (0.0542 -> 0.0432, −20.4% rel
from 4 MB to full): nci's repeats keep paying off across the whole 33.5 MB
(xz -9/-9e dict = 64 MB, whole file in window).

## 4. Mechanism probe — m1/m2/m3 table simulation (PROBE, probe_new14_nci.py)

Exact replica of cm2.rs hashing/insert/lookup semantics (hash constants,
slot = h & mask, insert at every position, lookup = previous same-slot write,
NO gram verification), vectorized in numpy; gram identity via 64-bit poly
fingerprint (collision odds ~6e-5 over 33.5 M positions — negligible).
Per-POSITION stats (encoder looks up only when len==0, so per-lookup rates
are biased toward match starts; stated honestly — the sign of the finding is
insensitive to this: to explain the 105 KB residual the match models would
have to lose ~0.025 b/B, and the measured wrong-candidate rate bounds the
damage near ~0.002 b/B even at a few bits per event, 10x too small).

Key rows (full table in probe-new14-tables.txt, same directory):

| prefix | tbits | model | distinct grams | gram/slot load | lost-repeat rate | false-cand (novel) | survival >16M |
|---|---|---|---|---|---|---|---|
| 4 MB | 25 | m3(12) | 384,544 | 0.0115 | 0.0136% | 0.57% | n/a |
| 8 MB | 26 | m3(12) | 641,512 | 0.0096 | 0.0122% | 0.47% | n/a |
| 16 MB | 27 | m3(12) | 1,027,556 | 0.0077 | 0.0077% | 0.38% | n/a |
| full | 27 | m3(12) | 1,812,382 | 0.0135 | 0.0132% | 0.68% | 99.005% |
| full | 28 (counterfactual) | m3(12) | 1,812,382 | 0.0068 | 0.0067% | 0.34% | 99.513% |

m1(6) and m2(3) are even less stressed (m2: 7,994 distinct 3-grams in the
whole file, retrieval 100.0000%; m1 full-file lost-repeat 0.0015%, survival
>16M = 99.775%).

**The tables are unstressed at every scale.** nci is SO repetitive that the
whole 33.5 MB contains only 1.81 M distinct 12-grams — gram/slot pressure at
tbits=27 is 0.0135, two orders of magnitude below any regime where
direct-mapped eviction could matter. NEW-06's exp(−d/2^tbits) survival model
assumed one DISTINCT random slot write per position; on nci the distinct-write
rate is ~5% of positions, so effective eviction pressure is ~20x lower than
that model — measured survival at >16 M distance is 99.0%, not the modeled
78%. The tbits=28 counterfactual (what TBITS_MAX=27 blocks) merely halves
already-negligible rates: no meaningful bytes are recoverable from table
sizing on nci.

Repeat structure (FULL file, exact nearest-prev): 12-gram repeats cover
94.60% of positions; nearest-prev beyond 8 MB only 0.80%, beyond 16 MB
0.26%. 16-gram: repeats 92.12%, beyond 8 MB 0.98%, beyond 16 MB 0.32%.
nci's repeats are overwhelmingly LOCAL — long-range reach is not where its
redundancy lives.

## 5. cubrim prefix runs (measured 2026-08-11; binary cubrim-new24-fba3f88 =
cubrim 0.3.2, byte-identical to main per lane brief; CUBR_THREADS=4, nice 10,
MemoryMax=14G systemd scope; both new archives round-tripped decompress+cmp OK)

| prefix | cubrim bytes | cubrim ratio | xz -9e ratio | residual | rel | source |
|---|---|---|---|---|---|---|
| 4 MB | 201,576 | 0.048059 | 0.054241 | −0.006182 | cubrim −11.4% | probe-h25i (slice) |
| 8 MB | 397,464 | 0.047381 | 0.050566 | −0.003185 | cubrim −6.3% | this probe, rt OK, 769 s |
| 16 MB | 764,716 | 0.045581 | 0.045340 | +0.000241 | cubrim +0.53% | this probe, rt OK, 1299 s |
| full | 1,554,682 | 0.046335 | 0.043193 | +0.003142 | cubrim +7.27% | meta-36 anchor |

**Crossover located: between 8 and 16 MB, ≈15 MB by linear interpolation of
the residual.** It does NOT coincide with any table-stress inflection: at
16 MB the tables had just GROWN to tbits=27 (load 0.125, m3 lost-repeat rate
at its series minimum 0.0077%), and the load doubling to 0.25 happens only
after 16 MB — by which point cubrim was already behind.

Marginal (second-half) cost, derived from the prefix pairs:
- xz -9e, bytes 16.8->33.5 MB: (1,449,272−760,672)/16,776,229 = 0.041046
  (vs 0.045340 first-half average — xz gets CHEAPER deeper into the file).
- cubrim, same span: (1,554,682−764,716)/16,776,229 = 0.047088
  (vs 0.045581 first-half average — cubrim gets slightly MORE expensive,
  while its match retrieval stays 99.99% — the worsening is not table loss).

Attribution consistent with all measurements: deep into nci the input is
almost pure repeats (12-gram coverage 94.6%, overwhelmingly local). LZMA -9e
codes a long repeat as one token — marginal cost per repeated byte amortizes
toward ~0 — and its -e optimal-parse depth exploits this fully (plain -9,
same 64 MB window, is 17% worse than -9e on nci and LOSES to cubrim
whole-file, 0.051824 vs 0.046335 — so the xz edge is parse quality, not
window). CM2's LZP match models predict the repeat bytes correctly (tables
unstressed) but the coder pays a per-byte mixer/coder floor for every
predicted byte; integrated over 33.5 MB of near-pure repetition that floor
accumulates faster than xz's token amortization. The residual is a
coding-architecture floor (per-byte CM vs tokenized LZ + extreme parse on
ultra-repetitive input), NOT a capacity/eviction defect.

Lever check (for completeness): cubrim's MODE_LZ rail is already
full-file-window (codec.rs:2298 comment, LZ_MAX_MATCH=65535, LZ_BT_DEPTH=128)
with the H-25i/j/k/l optimal parse, and its 4 MB nci slice size (257,788 B)
tracks plain xz -9 (255,932 B), 13% behind xz -9e — and plain xz -9
whole-file loses to cubrim. Routing nci to MODE_LZ therefore cannot reach
the −9e anchor; H-25l already attributed the remaining MODE_LZ gap to an
offset-entropy format floor. No small lever consistent with the measured
mechanism reaches xz -9e parity — closing the last +7.3% would need an
LZMA-class tokenized backend with -9e-depth parse (a NEW-04-class effort
that lane already NO-GO'd) or a CM-side long-match bypass (SSE/deterministic
run coding), which is a new hypothesis, not this row.

## Incident note

The probe worktree /home/dev/.worktrees/cubrim/PROBE-NEW14 was deleted from
the shared repo's worktree registry by another session while the cubrim
16 MB encode was running. Notes and the probe script were reconstructed
verbatim into this scratchpad directory; all measurement outputs
(probe-new14-tables.txt, cubrim-runs.log, rt-*.log, archives) were already
in the scratchpad and were unaffected. No git worktree was recreated (shared
repo registry — not this lane's to mutate).
