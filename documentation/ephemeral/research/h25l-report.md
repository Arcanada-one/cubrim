# H-25l — DP offset-cost recalibration (MODE_LZ optimal parser)

Parent code_sha: `edabfe0` (H-25k). Measured on the working tree (`edabfe0`-dirty),
release build. Round-trip byte-exact on every file below.

## Charged diagnosis (Gotcha #6 — where the bytes are)

`build_lz_container` / `lz_encode_token_streams` instrumented (env `CUBR_LZ_DEBUG`,
since reverted). Winning containers (optimal parse selected):

- **srctree.tar** 1310720 → 229164 (zstd-19 221518, +3.46%): token_block = 186041
  (**81% of output**); within it the new-distance byte-split streams
  b0+b1+b2 = 64657+43732+10759 = **119162 B = 52% of the whole file** for 64203
  distinct new offsets ≈ **14.85 bits/offset**; lengths 45639; flags 16237;
  lit_blob 43099 (19%). n_matches 71225, of which 64203 are NEW offsets (rep-cache
  hits only ~10%).
- **multiversion.bin** 999210 → 64575 (zstd 60978, +5.90%): same shape, offset
  byte-split dominates the token block.

The residual gap is the **offset entropy floor**, driven by match count. Offset
*coding format* was already ruled out (H-25k: offcode seq_format lost to the
separate byte-split + order-1 rANS on these diverse-offset files).

## Lever: cost-model calibration (zero-risk)

The H-25i/j optimal-parse DP charged a new offset the full raw `2 + bit_length(dist)`
(~22 bits for a 1 MB file). The real byte-split + order-1 rANS coder achieves
**14.85 bits/offset** (measured above) — the model **over-prices new offsets by
~0.7×**, so the DP under-takes profitable short new-offset matches and leaves them
as literals. Fix: `off = 2.0 + LZ_OFF_COST_SCALE · bit_length(dist)`,
`LZ_OFF_COST_SCALE = 0.70` (coder efficiency 14.85 / ~20 raw ≈ 0.74, **not** a
corpus knob). The parse only affects MODE_LZ (>64 KB); the exact encoder guarantees
round-trip regardless, and ≤64 KB inputs run no prepass so tuned/holdout are
byte-identical.

### Sweep (confirms the minimum, guards against over-fit)

| scale | srctree (zstd 221518) | multiversion (zstd 60978) | multicopy120k | repeated.log |
|------:|----------------------:|--------------------------:|--------------:|-------------:|
| 1.00  | 229164                | 64575                     | 10056         | 56921        |
| 0.70  | **228989** (−175)     | **64195** (−380)          | 10056         | 56921        |
| 0.65  | 229207 (**+43**)      | 64153 (−422)              | 10056         | 56921        |

0.65 over-fits multiversion at srctree's expense (regresses srctree above baseline);
**0.70 improves both mixed files, regresses neither**, and matches the measured
coder efficiency. Selected 0.70.

## Result — marginal long-range win, regression-proof

- srctree.tar: 229164 → **228989** (−175 B, −0.08%); vs zstd +3.46% → **+3.37%**
- multiversion.bin: 64575 → **64195** (−380 B, −0.59%); vs zstd +5.90% → **+5.27%**
- multicopy120k.bin: 10056 (unchanged — rep-offset dominated, no new offsets to reprice)
- repeated.log: 56921 (unchanged)

## Zero regression (verified)

- `cargo test --release`: 215 lib + 14 integration GREEN, 0 failed; clippy 0 new warnings.
- Tuned 10-file corpus (`run_bench --value-scheme bwt-rans`): aggregate **0.158273**,
  per-file byte-identical to the H-24/k champion, RT 10/10 PASS.
- Holdout 6-file (`run_holdout_bench`): aggregate **0.2390** (48255 B), byte-identical
  to H-25k, RT 6/6 PASS (MODE_LZ selected 0/6 — no cross-block structure).

## Verdict

Marginal win. The offset cost-model was mis-calibrated (charged raw bit-length;
real coder ≈ 0.7×); recalibrating to 0.70 shaves −0.08% (srctree) / −0.59%
(multiversion) on genuine mixed/near-duplicate long-range data and is structurally
regression-proof (competitive parse + exact encoder + ≤64 KB byte-identical). It does
**not** close the gap to zstd-19 (still +3.4% / +5.3%): the residual is the offset
entropy floor from ~64 K distinct cross-file offsets, which is data-determined, not a
coding inefficiency. Deep diminishing-returns territory, as the brief anticipated.

### Fixture regeneration (ad-hoc, not committed)

- srctree.tar: `tar cf srctree.tar -C /usr/include $(ls /usr/include/*.h | head -120)`
- multiversion.bin: first 3 git revisions of `code/cubrim-rs/src/codec.rs` concatenated
- repeated.log: 8000 synthetic syslog lines (seed 42), multicopy120k.bin: 10 KB random unit ×12 (seed 7)

Absolute bytes differ run-to-run (host `/usr/include`, git history depth); the
relative gap to zstd and the zero-regression guarantee are the stable findings.
