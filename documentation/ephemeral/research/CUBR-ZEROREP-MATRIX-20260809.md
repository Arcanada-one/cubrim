# Preregistration: zero-representation eight‑cell matrix

**State:** PREREGISTERED DESIGN — no implementation change, measurement, or result
is recorded in this document. The prediction is committed before the candidate is
built (fresh build from the zero‑representation patch) and before any cell is
measured.

---

## 1. Purpose and scope

This experiment extends the **NEW-30** zero-representation packed-Ctr lever from
the previously measured `nci` / `max` cell to the remaining eight cells in the
Silesia-2M slice matrix. The separately landed `nci` / `max` result at
`documentation/ephemeral/research/CUBR-ZEROREP-RESULTS-20260808/result.md`
reported a compound product PASS, but one cell neither closes the full lever nor
fully explains the observed RSS reclaim. The goal here is to answer whether the
XOR-bias mechanism reclaims the packed de-commit RSS penalty on every remaining
file/preset cell while preserving its measured speed behavior.

- **Excluded:** `nci` / `max` (already measured, **NEW‑30** run‑mode
  `zerorep-nci-max-pin0-15-t4`). No observation for that cell is repeated here.
- **Included (eight cells):**
  `nci` / `balanced`,
  `nci` / `web`,
  `dickens` / `max`,
  `dickens` / `balanced`,
  `dickens` / `web`,
  `ooffice` / `max`,
  `ooffice` / `balanced`,
  `ooffice` / `web`.

Each cell receives its own per‑file, per‑preset prediction. There is no
corpus‑wide aggregate, no averaging, and no estimated value. The campaign is one
immutable systemd invocation covering all eight cells in a fixed order; it is
never restarted or widened.

---

## 2. Input files

All three slices are the existing SHA‑verified 2‑MiB Silesia fragments used
throughout the pinned campaign. Their SHA‑256 values, recorded before admission,
are:

| File | Size | SHA‑256 |
| --- | ---: | --- |
| `nci` | 2,097,152 | `6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e` |
| `dickens` | 2,097,152 | `df925056e0779c51cb2a27c014e8fc6d25d28ef2fac5b8ce4632d93b86860603` |
| `ooffice` | 2,097,152 | `5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09` |

The canonical archive identities come from the completed pre-PR41/current preset
run and are pinned before this campaign:

| Cell | Bytes | Canonical SHA-256 |
| --- | ---: | --- |
| `nci` / `balanced` | 108,014 | `c812943fd63414bf4ec185ee048b6550cc6b1a0a523dd3a63afe242bdf133066` |
| `nci` / `web` | 108,624 | `2caaa78101082ccfb753909440a60e7381f94210fd8817ac89ccc02d7b6d6848` |
| `dickens` / `max` | 461,437 | `c8aed8ae4c39d8a463e3d2bcb3fd082ec955d60fd320bbeec41af7a65922285e` |
| `dickens` / `balanced` | 472,253 | `25378abf1cbe18e016143c0f0401aac055db8fb1c2964e5a4525371ba400a5ad` |
| `dickens` / `web` | 487,506 | `0f3677eeadf937facb8c3b3fd79d6fc04677f19e0b648b983dd732db8a92ba0f` |
| `ooffice` / `max` | 677,605 | `4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be` |
| `ooffice` / `balanced` | 677,605 | `4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be` |
| `ooffice` / `web` | 704,087 | `a8e04efd9c890c8f72a645571ebfd230774e638e9bef7c3118d22a5fffeb0be4` |

Before timing, each newly generated base/current/zero archive must match its
pinned size and SHA-256, must compare byte-for-byte with the retained canonical
archive, and must compare byte-for-byte with the other two fresh archives. A
mismatch aborts the entire campaign.

---

## 3. Models, table counts, and ceilings

The optional‑column model selects 24 tables when `max` is combined with a field
that benefits from the extra bit history; otherwise the 23‑table base CM‑2 model
is used. `web` uses the base 23‑table model with `tbits=20`. The exact model
per cell was determined from the earlier preset‑run archive‑model inspection and
is reproduced here.

| Cell | Preset | Tables | tbits | E (2·tables·2^tbits) | T (4·tables·2^tbits) |
| --- | --- | ---: | ---: | ---: | ---: |
| `nci` / `balanced` | balanced | 23 | 24 | 736 MiB | 1 472 MiB |
| `nci` / `web` | web | 23 | 20 | 46 MiB | 92 MiB |
| `dickens` / `max` | max | 24 | 24 | 768 MiB | 1 536 MiB |
| `dickens` / `balanced` | balanced | 23 | 24 | 736 MiB | 1 472 MiB |
| `dickens` / `web` | web | 23 | 20 | 46 MiB | 92 MiB |
| `ooffice` / `max` | max | 23 | 24 | 736 MiB | 1 472 MiB |
| `ooffice` / `balanced` | balanced | 23 | 24 | 736 MiB | 1 472 MiB |
| `ooffice` / `web` | web | 23 | 20 | 46 MiB | 92 MiB |

- **E** = extra‑two‑byte ceiling: 2 bytes per slot, all tables.
- **T** = total zero‑word deferrable storage: 4 bytes per slot (the full packed `u32`).
  Both ceilings are theoretical maxima; the measured reclaim can be larger than E
  if the zero word also defers the two original bytes.

The tables state E and T in MiB. Runner comparisons convert them to KiB
(`E_KiB = E_MiB × 1024`, `T_KiB = T_MiB × 1024`) before comparing them with
`time -v` RSS values.

The **accounting consistency** check is defined per cell and *does not affect the
compound product prediction*. It is a separate forensic label.

---

## 4. Per‑cell compound product prediction

For each cell, let:

- `base`   = pre‑PR41 build median decode RSS and time
- `current` = current packed build (PR #41 + PR #42) median decode RSS and time
- `zero`   = zero‑representation build (same source as current plus XOR‑bias patch) median
- `P = current_rss − base_rss` (must be positive; if non-positive the product
  prediction is refuted for that cell)
- `R = current_rss − zero_rss`
- `B = base_rss − zero_rss` (the total decrease from pre‑PR41 to zero‑rep)

**RSS prediction (both conditions must pass, per cell):**

1. **Reclaim fraction:** `R / P ≥ 0.75`
2. **Residual bound:** `zero_rss − base_rss ≤ 65,536 KiB` (64 MiB)

If either condition fails, the cell’s compound prediction is refuted.

**Speed prediction (both conditions must pass, per cell):**

3. **No slowdown vs. current:** `zero_time / current_time ≤ 1.05`
4. **Speedup vs. baseline:** `base_time / zero_time ≥ 1.10`

The reasoning is identical to the original nci/max lever: the XOR‑bias adds a
single XOR instruction and should not regress performance, while retaining the
cache‑line efficiency that gave the speedup in the first place.

If any of the four product conditions fail, the lever is refuted **on that cell**.
The cell is marked `REFUTED` and receives no further tuning. All other cells
continue independently.

---

## 5. Accounting‑consistency label (separate, per cell)

After measurement, compute:

- If `R ≤ T` and (if `B > 0` then `B ≤ E`), label **`ACCOUNTING_CONSISTENT`**.
- If `R > T` or `B > E`, label **`EXPLANATION_INCOMPLETE`**.

This is a forensic label indicating whether the observed reclaim falls within the
static hardware‑independent ceilings. It has no effect on the product PASS/REFUTED
criterion. The label is recorded alongside the cell’s medians; it is not a
refutation.

---

## 6. Predicted cells summary (pre‑measurement)

No measurement has been performed. The table below restates the prediction per
cell in qualitative terms.

| Cell | P positive | R/P ≥ 0.75 | zero‑base ≤ 64 MiB | time ratio ≤ 1.05 | speedup ≥ 1.10 |
| --- | :---: | :---: | :---: | :---: | :---: |
| `nci` / `balanced` | ✓ (historical: +252.5 MiB) | ✓ | ✓ | ✓ | ✓ |
| `nci` / `web` | ✓ (historical: +4.0 MiB) | ✓ | ✓ | ✓ | ✓ |
| `dickens` / `max` | ✓ (historical: +172.0 MiB) | ✓ | ✓ | ✓ | ✓ |
| `dickens` / `balanced` | ✓ (historical: +164.5 MiB) | ✓ | ✓ | ✓ | ✓ |
| `dickens` / `web` | ✓ (historical: +3.0 MiB) | ✓ | ✓ | ✓ | ✓ |
| `ooffice` / `max` | ✓ (historical: +71.5 MiB) | ✓ | ✓ | ✓ | ✓ |
| `ooffice` / `balanced` | ✓ (historical: +70.5 MiB) | ✓ | ✓ | ✓ | ✓ |
| `ooffice` / `web` | ✓ (historical: +2.5 MiB) | ✓ | ✓ | ✓ | ✓ |

Historical penalty values come from the preset run and are *calibration only*.
All decisions are made from the new interleaved same‑run medians. No cell’s
prediction is considered “trivial” because of a small historical penalty: the
same‑run measurement is mandatory and the product gates must be met exactly.

---

## 7. Global validity gates (campaign admission)

Before any cell is measured, the runner asserts:

1. **Host:** `dev-ai` stand with CPUs pinned to 0–15.
2. **Thread variables:** `CUBR_THREADS=RAYON_NUM_THREADS=OMP_NUM_THREADS=4`.
3. **Admission:** 1‑minute load average < 2.0; no other `cubrim` process exists.
4. **Binary provenance (three separate builds):**
   - **pre‑PR41 baseline** commit
     `e70d1cdca6226e994c0393149e364f252f7c0a1f` → binary SHA‑256
     `a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd`.
   - **current packed** commit
     `49e429e58722f730c4f3cbb0a69731fec430bb56` → binary SHA‑256
     `12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c`.
   - **zero‑representation candidate** built only after this preregistration and
     its runner land, from that exact resulting `main`. Its `cm2.rs` blob must
     equal the reviewed zero-representation product blob SHA-256
     `1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf`
     (original product commit `f047523fcdc15561baa05fee597819fd6bdb53d3`).
     A prior clean binary from that product source had SHA-256
     `771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20`,
     and reproducibility requires the fresh resulting-main binary to equal that
     hash; otherwise the campaign stops before measurement.
   All binaries compiled with the same `--release` flags and toolchain as the
   pinned campaign. Baselines must match the preregistered hashes exactly.
5. **Slice hashes:** the three input slices must match the SHA‑256 values in §2.
6. **Canonical archive check:** for every cell, the pre‑PR41 encoder produces an
   archive whose SHA‑256 matches the stand catalog. Every current‑packed and
   zero‑rep archive for that cell must be byte‑identical to that canonical file.
   Any mismatch aborts the campaign before timing starts.
7. **Suite pass:** The zero‑rep candidate tree passes the full release test suite
   (exact counts recorded), including the XOR‑bias‑specific mutation‑tested
   unit tests and the scheme round‑trip suite. The suite must pass on the exact
   source tree used for the stand build.

If any admission gate fails, the whole campaign is void and no DB rows are added.

---

## 8. Measurement protocol

### 8.1 Campaign orchestration

One immutable systemd unit: `cubr-zerorep-matrix-20260809.service`. The output
root is `/root/cubr-levers/zerorep-matrix-20260809` and must not exist at
admission. Fixed cell order (as listed in §3), executed sequentially. The campaign is launched exactly
once as:

```
timeout 14400 systemd-run --wait --collect \
  --unit=cubr-zerorep-matrix-20260809.service \
  --property=RuntimeMaxSec=7200 \
  /root/cubr-levers/zerorep-matrix-code/documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-20260809/zerorep-matrix-run.sh
```

- `RuntimeMaxSec=7200` (two-hour unit cap) is the primary envelope.
- The four-hour `timeout` is the hard outer watchdog. Neither is widened.

No restart, no partial rerun, no cherry‑picking of cells.

### 8.2 Per‑cell warm‑up and Latin‑square timed interleaving

For each cell (fixed order):

1. **Compress** with each of the three builds. Archive identity (byte‑equal to
   canonical, same SHA‑256) is verified for all three outputs.
2. **One unmeasured warm‑up decode per build**, `cmp` checked after each.
3. **Three interleaved measured decodes per build** — Latin square of order 3:
   sample 1: `base`, `current`, `zero`; sample 2: `current`, `zero`, `base`;
   sample 3: `zero`, `base`, `current`. Within every cell, each build occupies
   the first, middle, and last timed position exactly once.
   Wall time and peak RSS are captured from `time -v`.
4. After **every** decode (warm‑up and measured), `cmp` is checked; any failure
   immediately aborts the campaign.

**Totals:** 8 cells × (3 warm‑ups + 9 measured) = 96 decode operations.
72 timed observations, 24 warm‑ups.

### 8.3 Timeout caps

- Compress: 1,800 s per command.
- Every decode (warm‑up or measured): 300 s.

### 8.4 Data recording

After every timed decode the raw `time -v` output is logged. At campaign
completion, per‑build‑per‑cell medians are computed from the three samples.
No cherry‑picking, no removal of outliers.

A separate `roundtrips.tsv` records one row only after each successful `cmp`,
including cell, phase (`warmup` or `timed`), sample, build, and `cmp=PASS`.
Campaign completion requires exactly 96 unique rows: 24 warm-up and 72 timed,
all PASS. `results.tsv` contains exactly the 72 timed observations. Either count
or any non-PASS value voids the whole campaign.

---

## 9. Stop and void semantics

- **Void (no DB entry):** The campaign is void if any admission gate fails, any
  compress‑timeout expires, any round‑trip `cmp` fails, any binary hash mismatches,
  or the build/test‑suite check fails. A void run is not a refutation; it is
  a broken instrument. The journal alone records the reason.
- **Valid observation but refuted prediction:** If all gates pass and 72 valid
  decode observations exist, but on a given cell the compound product prediction
  fails, that cell is marked REFUTED. Its medians are inserted into NEW‑30 with a
  REFUTED note. The lever is stopped for that cell; no second attempt is made.
- **No widening:** No compressor or decode parameter is changed during the
  campaign. If a cell times out, the entire campaign is void; all partial values
  stay in the journal and no matrix DB row is written.

---

## 10. Database protocol

After a complete, valid campaign:

- **Insert exactly 24 measurement rows** under existing hypothesis **NEW‑30**,
  three per cell (base, current, zero). Each cell receives a unique run‑mode
  identifier: `zerorep-<file>-<preset>-pin0-15-t4`.
- Resolve each `measurements.codec_rev` integer foreign key through the existing
  `codec_revisions.sha` identity before mutation: base ID 9 maps to
  `cli-sha256:a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd`,
  current ID 8 maps to
  `cli-sha256:12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c`,
  and zero ID 10 maps to
  `cli-sha256:771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20`.
  Any live mapping drift aborts the transaction.
- Each row records the exact `corpus_file`, `orig_bytes=2097152`, pinned
  `comp_bytes`, exact `ratio`, `rt_ok=true`, `host=dev-ai`, and `cpu_pin=0-15`;
  stores the cell medians in `decode_ms` and `decode_peak_rss_kib`; and leaves
  `duration_ms` and `peak_rss_kib` NULL. The transaction does not write
  `web_benchmark_hypothesis_evaluation`.
- Insert in a single transaction:
  - Before mutation, backup/readback NEW‑30 and assert zero existing rows for any
    of the eight new run‑mode IDs.
  - After insert, assert exactly 24 rows, eight distinct run‑mode IDs, required
    identity/round-trip/decode values present, encode fields NULL, and exactly
    zero `web_benchmark_hypothesis_evaluation` rows joined through
    `web_benchmark_hypothesis.task_id='NEW-30'`.
  - Roll back on any assertion failure.
- The transaction is idempotent: an exact rerun with identical medians and
  run‑mode IDs inserts zero new rows. Any partial pre‑existing state aborts.
- One exact `hypotheses.measure_note` extension on NEW-30 records all eight
  product and accounting labels; labels are not measurement columns.

---

## 11. Constraints

- `decode()`, the wire format, encoder defaults, `cube_size_limit`,
  `cm_should_try`, and `prof.rs` counters remain untouched.
- Archival byte‑identical property enforced before every timed decode.
- Pin 0–15, threads 4.
- Per‑file only; no corpus aggregate.
- No site deployment, no blog update, no social publishing.
- `evaluation` stays 0.
- If the zero‑rep build exceeds any of the product speed bounds on a cell, the
  lever is refuted on that cell; no tuning loop begins.

---

## 12. Recommended approach (unchanged from nci/max)

The XOR-bias mechanism is unchanged. No additional design modification is needed.
The campaign candidate is the exact resulting `main` after this preregistration
and runner land. Its reviewed product blob is identical to the product originally
built from `f047523fcdc15561baa05fee597819fd6bdb53d3`; that original commit is
provenance, not the campaign checkout revision. A fresh resulting-main build is
required to prove binary reproducibility; this matrix introduces no product-code
change.

---

**No measurement result exists yet. The exact input and canonical archive
identities above are premeasurement gates, not observations from this campaign.**
