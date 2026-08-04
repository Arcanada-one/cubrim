# CUBR-PROFFOUND — NEW-29 final-winner attribution

**Measured:** 2026-08-04 UTC
**Task:** CUBR-0087 / NEW-29 cause follow-up
**Status:** cause proven on two measured representative Silesia slices; full-corpus generalization not claimed

## Scope and identity

This run answers the narrow question left open by NEW-29: does one value scheme
win the block and keep winning across the measured file? It uses the Silesia
corpus that underlies the NEW-29/CUBR-0092 lane, not the web corpus.

- Full corpus manifest: `/home/dev/cubr-cubecore-research/corpus-silesia/SHA256SUMS.txt`
  SHA-256 `d9203058b86b39f94f20b29603a89af5229619b06c78741c64d7098730c39647`.
- Evidence commit: `6f281f360b9670f992976b1e248b41343a7c5bd3`.
- Measured source commit: `3a59903910aa526a5d8e1633465f784fbfb4fc65`.
- `src/prof.rs` blob SHA-256: `0e6c3eaf2a7b8102df3dcd1837216df4022d662c24e578acd2a4fb58fac727a7`.
- `src/codec.rs` blob SHA-256: `ff1c27faaae9739c29a40d13582edab43558774961d55e91f2e428edaaf3fa54`.
- Release binary: `code/cubrim-rs/target/release/cubrim` from the measured
  worktree; SHA-256 `0a327d55e6d549d4c742a4ca0e098bbc5e02946311893ccddaacc898fd3fd372`.
- Host resource check: `nproc` reported 16; every encode/decode process was
  pinned to CPUs `0-3` with `taskset`.
- The pinned campaign host `162.55.81.5` was not contacted.

## Method

The committed `CUBRIM_PROFILE=1` instrument was run through
`attribution-run.sh` on 2 MiB prefixes of two versioned Silesia files. Each
run wrote the compressed blob, decoded it, and used `cmp` for byte-exact
round-trip verification. The complete raw profiler and timing outputs are in
`raw/` beside this report.

The profiler header is binding methodology: nested candidates double-count,
so the table is attribution, not a partition. The ordinary `wins` column is a
running-minimum counter and can name several candidates for one block. Only
the special `FINAL:` row is used for the final-per-block winner.

## Results

| input | class | full-file SHA-256 | measured slice SHA-256 | compressed bytes | ratio | encode wall | decode wall | RT | final winner |
|---|---|---|---|---:|---:|---:|---:|---|---|
| `x-ray.2m` | image | `7de9fce1405dc44ae5e6813ed21cd5751e761bd4265655a005d39b9685d1c9ad` | `9bfd1c5321dbd4dcec1cfb037189ef78ceb7052ce8647086b70b0e1cb401aab3` | 878,363 | 0.418836 | 104.518 s | 1.661 s | PASS | `geomix`, 384/384 blocks |
| `ooffice.2m` | executable | `e7ee013880d34dd5208283d0d3d91b07f442e067454276095ded14f322a656eb` | `5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09` | 677,605 | 0.323107 | 142.805 s | 23.912 s | PASS | `geomix`, 384/384 blocks |

The raw tables contain the decisive rows:

```text
FINAL:geomix                       0        0.000     0.00       384              0
```

This row appears in both inputs. It is distinct from the ordinary candidate
`wins` counters and proves that the same final value scheme was selected for
every measured block in each representative file.

## Finding and limits

The cause is now proven for the measured representative image and executable
slices: the inner value-scheme rail recomputes a constant final answer,
`geomix`, across all 384 blocks in both files. That is the evidence needed to
explain the repeated candidate work behind the NEW-29 opportunity and to make a
sticky-selection lever a causally grounded hypothesis.

This does not claim that `geomix` wins every block in every Silesia file, does
not produce an N=12 or N=24 corpus aggregate, and does not measure the ratio
cost or speed benefit of a sticky lever. NEW-29 remains closed and killed by
the pre-registered CUBR-0092 gate; no verdict, status, or ship decision is
reopened.

## Harness correction

The first x-ray launch placed its output directory inside the corpus directory,
so the script emitted one invalid `out-xray` directory row. That row is
preserved in `raw/x-ray.SUMMARY.raw.tsv` for audit and excluded from the result
table. The valid `x-ray.2m` row has `rt=PASS`; the ooffice run used a separate
output directory outside its corpus and has no invalid row.

## Raw artefacts

| artefact | SHA-256 |
|---|---|
| `raw/x-ray.2m.prof.txt` | `b553e28e2c985f0c3109502b2ee34854bf0f034de19a32e0fc098869f1b9bd4b` |
| `raw/x-ray.2m.dec.txt` | `5071088ccc1e74922aa14fdcddc128d8d87290ee7ad4c9c9069c789798c8c455` |
| `raw/x-ray.SUMMARY.raw.tsv` | `c69792f985bd57a25d1538b6181751c8c3b5025fd6b0d835284ca89a9cde05dd` |
| `raw/ooffice.2m.prof.txt` | `3cdbe03322d0e865bd185be27b2da7df471b802cd53c0121cc835580bd5e784d` |
| `raw/ooffice.2m.dec.txt` | `e09714762d46dd22361b97150b5c6f343e70ff6fde84678f922521ddc7f2f99e` |
| `raw/ooffice.SUMMARY.tsv` | `72b93275b022e97a1333a50609ce7f8bee854a07e3c0df89bd900fbebdbcbddf` |

## Database boundary

The guarded append in `NEW29-PROFFOUND-EXTEND.sql` changes only
`public.hypotheses.measure_note` for `id='NEW-29'`, requires the current
read-back timestamp, and is idempotent on marker
`[PROF FOUND 2026-08-04]`. It does not insert a measurement row or change the
existing `status`, `verdict`, `measured`, `measure_date`, or `measure_task`.

Execution evidence: the pre-write `public.hypotheses` backup was
`/root/cubr-backups/CUBR-0087-NEW-29-before-PROFFOUND-20260804T133015Z.dump`,
mode `0600`, size 90,169 bytes, SHA-256
`298aeafd0019a0acaaa8d02f71d2e2c771d3946d0e32d6cf8c25de807abef70c`; its
restore catalog contained `TABLE DATA public hypotheses postgres`. The guarded
transaction committed at `2026-08-04 13:30:34.802214+00` and changed one row.
Fresh-session readback returned `new29_rows=1`, `n9_rows=1`, `n13_rows=1`,
`prof_rows=1`, `status=closed`, `measured=true`, `measure_date=2026-08-02`,
`measure_task=CUBR-0092`, unchanged KILLED verdict, note length `17274`, and
note MD5 `b2bc51d5164361503b0fa427bf961438`. A separate query confirmed
`public.measurements` has `0` rows for NEW-29.
