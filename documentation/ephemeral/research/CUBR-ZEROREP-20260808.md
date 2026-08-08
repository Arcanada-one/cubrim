# Preregistration: zero-representation counter storage for packed Ctr

**State:** PREREGISTERED DESIGN — no implementation or measurement result is
recorded here. The prediction must be committed before the candidate is built
or measured.

## Design

PR #41’s packed Ctr stores each table entry as a single `u32`:
```
| t (16 bits) | count (8 bits) | state (8 bits) |
```
The model initialises every slot with `t = 32768` (0x8000), `count = 0`, `state = 0`.
That non-zero `t` field forces every 4 KiB page that contains a slot to be physically
committed immediately, producing the file-dependent decode-RSS increase observed in
NEW-30. The preset run confirmed that a per-file ceiling (768 MiB for the 24‑table
model under `max`) bounds the extra storage, and that `web`’s 20‑bit table exponent
shrinks the delta to single‑digit MiB. The mechanism note in NEW-30 correctly identifies
the initial non‑zero `t` as a candidate explanation; this experiment tests whether
that explanation is sufficient.

### Zero representation via stationary‑probability XOR

Instead of a separate sparse layout, we keep the packed `u32` and make the initial
(stationary) entry all‑zero by XOR‑ing the stored `t` with `0x8000` on every read and
write:

- **Encode / update path**
  When storing the stationary probability `t` (the encoder’s initial value 32768), we
  store `t ^ 0x8000`. Thus the initial entry becomes `0x00000000` – a full zero `u32`.

- **Predict / read path**
  The stored value is recovered by the same XOR: `t_stored ^ 0x8000`.

- **Packed integer semantics are preserved** because XOR is a bijection and is
  undone before probability arithmetic, then reapplied before storage. No extra
  branch is required in the hot loop; the representation adds one integer XOR at
  each unpack/pack site.

- **Count and state** are already zero at initialisation and do not require
  transformation.

The zero word permits the allocator and kernel to retain shared zero-page backing
for slots that have never been updated, matching the opportunity the original
`c`/`st` arrays had before PR #41. Whether the actual allocation path realizes
that opportunity is the measurement question, not a design assumption.

### What does *not* change

- The packed `u32` layout and all its bit widths.
- `decode()`, the wire format, encoder defaults, `cube_size_limit`, `cm_should_try`,
  or any existing prof.rs counter.
- Output archives are required to remain byte-identical to those produced by
  the current packed Ctr. Reversibility makes this plausible; archive comparison
  and round-trip gates establish it rather than the design asserting it.

The only behavioural change is a lower resident set during decode (and,
incidentally, lower encode RSS, which we explicitly *do not claim* unless measured).

### Ceiling derivation for nci / max

The largest model selected by the `max` preset on the Silesia slice `nci` has 24 counter
tables, each with `2^24` slots.

- **Packed-induced extra-two-byte ceiling** (the extra physical commitment versus
  the old layout, whose two-byte `t` array was non-zero while its one-byte `c` and
  one-byte `st` arrays could remain lazy):
  2 bytes × 24 tables × 2^24 slots = 805 306 368 bytes = **768 MiB**.

- **Total zero‑word deferrable table storage** (the full 4‑byte packed entry that becomes
  zero in the stationary state):
  4 bytes × 24 tables × 2^24 slots = 1 610 612 736 bytes = **1536 MiB**.

The observed decode‑RSS penalty for nci / max under the packed Ctr is **+273.5 MiB**,
or 35.6 % of the 768 MiB extra‑two‑byte ceiling. Because the zero representation can
defer *all* stationary slots, the maximum reclaimable RSS is the fraction of those
768 MiB that was actually committed due to the non‑zero `t`. A full reclaim would
bring the decode RSS back to the pre‑PR41 baseline of 1 430 016 KiB (1 396.5 MiB),
but memory‑allocator metadata and kernel overhead will consume some of the freed
pages. We therefore set a conservative target: no more than 64 MiB above the
same-run pre‑PR41 baseline while reclaiming at least 75% of the same-run packed
penalty. On the historical +273.5 MiB observation, those thresholds correspond
to at least 205.1 MiB reclaimed and at most 68.4 MiB residual. The nearby
209.5 MiB / 76.6% figures obtained by subtracting 64 MiB from the historical
observation are context, not a separate same-run threshold. The 64 MiB allowance
is explicit acceptance headroom, not an estimate of known fixed overhead.

---

## Falsifiable prediction (preregistered)

The archive and round-trip checks below are validity preconditions on the `nci`
file under the `max` preset, measured on the quiet `dev-ai` stand with CPUs
pinned to 0–15 and `CUBR_THREADS=4`:

1. **Archive identity and round‑trip**
   The pre-PR41, current-packed, and zero-rep encoders produce archives that are
   mutually byte-identical and equal the canonical `nci/max` SHA-256. Every
   measured decode round-trips byte-exactly with `cmp` returning 0.

If and only if those validity gates pass, both performance conditions below must
hold for the compound prediction to pass:

2. **RSS reduction**
   The same-run median decode RSS of the zero-rep binary is **at most 64 MiB
   (65,536 KiB)** above the same-run pre-PR41 baseline. The previous baseline
   median was 1,430,016 KiB, but the decision uses the new interleaved run rather
   than freezing a host-noise-sensitive absolute number. In addition, the
   same-run packed penalty must be positive and the zero-rep build must reclaim
   at least **75%** of it, calculated as
   `(current_rss - zero_rss) / (current_rss - baseline_rss)`. The historical
   209.5 MiB / 76.6% calculation is reported for context only.

3. **Speed preservation**
   The same-run median decode time of the zero-rep binary is **no more than 5%
   slower** than the interleaved current-packed binary and is **at least 1.10×
   faster** than the interleaved pre-PR41 baseline. Previous medians were 15.70 s
   and 18.76 s respectively, but both ratios are recomputed from this run.

**Refutation**
On a complete, identity-valid run, either of the following refutes the prediction
for this lever:

- The zero-rep median RSS exceeds the same-run baseline by 65,536 KiB, the
  same-run packed penalty is non-positive, or the reclaim fraction is below 75%.
- The zero-rep/current-packed median-time ratio exceeds 1.05, or the
  pre-PR41/zero-rep speedup is below 1.10×.

An archive mismatch or failed `cmp` is not a refutation result: it violates a
hard validity gate, voids the run, and makes the implementation ineligible.

A refutation does not mean the zero‑representation idea is wrong, only that the
XOR‑bias mechanism as described does not achieve the stated threshold on `nci` / `max`.
In that case we record the actual medians and the fraction of ceiling reclaimed, then
**stop**. The result is a finding, not a failed experiment.

---

## Stop conditions

The measurement run halts before any timed decode if:

- Any admission gate fails (load average ≥ 2.0, existing cubrim process, binary hash
  mismatch, input file hash mismatch).
- The full release suite, including the new XOR-bias tests, does not pass on the
  exact source tree used for the stand build. Exact test counts are recorded,
  not predicted here.
- The archives from any of the three builds for `nci` / `max` are not byte-identical
  (verified by `cmp` and SHA‑256 before measurement).
- Any warm‑up round‑trip fails.

After measurement, the lever is stopped without further tuning if:

- The compound falsifiable prediction is refuted on either performance axis.
- The zero‑rep binary violates the hard constraints (e.g., it touches `decode`, the
  wire format, or any excluded file).

Any pre-measurement or partial-run stop is written to the void journal only: no
DB row is added and NEW‑30 is not extended. A complete run whose round-trip and
identity gates pass is valid evidence even when it refutes the compound
prediction. In that case, record its three medians in the DB, extend NEW‑30 with
the negative result, leave `evaluation` at 0, and do not ship the code change.

---

## Protocol

1. **Implementation & TDD**
   - Add the XOR-bias directly to the packed `Ctr` internal representation. The
     current-packed comparison remains a separate, hash-pinned binary; a feature
     flag would add an unnecessary second shipped behavior.
   - Write a dedicated test suite covering:
     - The initial stationary word is all‑zero in memory.
     - After one update, the stored `t` is `updated_t ^ 0x8000`.
     - The predict path recovers the original `t`.
     - Byte-by-byte comparison of encoded archives from the current and zero-rep
       builds (must be identical).
   - Run mutation testing on the new XOR operations to confirm the tests catch inverted or
     omitted XORs.
   - The full release suite (`cargo test --release`) must pass on the exact
     candidate tree; record the actual test counts.

2. **Build and hash verification** (stand‑only)
   - **Pre-PR41 baseline**: commit
     `e70d1cdca6226e994c0393149e364f252f7c0a1f` (same binary as the NEW-30
     preset run), SHA-256
     `a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd`.
   - **Current packed**: commit
     `49e429e58722f730c4f3cbb0a69731fec430bb56` (same binary as the NEW-30
     candidate), SHA-256
     `12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c`.
   - **Zero-rep candidate**: the implementation commit on top of canonical main
     (whose codec source still contains PR #41 and PR #42). Binary and source
     SHA-256 values are recorded before measurement.
   - All three binaries compiled with the same compiler, flags, and `--release` profile
     used for the existing pinned campaign.

3. **Input data**
   - The same 2 MiB `nci` slice as in the preset run, SHA-256
     `6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e`.
   - The expected `nci/max` archive is 104,139 bytes with SHA-256
     `1dcc11fa179e3aa0a0b745fba85b5c2187aa382b4b3022ec8ecd8839962b925b`.
   - Both values are verified against the stand's canonical copies before work.

4. **Measurement host and admission**
   - Host: `dev-ai` (quiet stand, CPUs pinned 0–15), `CUBR_THREADS=4`.
   - Admission gate: 1‑min load average < 2.0, no other `cubrim` process.
   - Per-command caps are fixed before measurement: 1,800 seconds for each
     compression and 300 seconds for every warm-up or measured decode.
   - The runner is launched exactly once as
     `timeout 14400 systemd-run --wait --collect --unit=cubr-zerorep-20260808.service --property=RuntimeMaxSec=7200 /root/cubr-levers/zerorep-20260808/zerorep-run.sh`.
     The systemd unit's two-hour runtime cap is the primary envelope; the
     four-hour caller timeout is a hard outer watchdog. Neither may be widened.
   - Record the unit result, main exit status, peak memory, and swap peak.

5. **Runner script** (per‑build, interleaved)
   For each of the three binaries (pre‑PR41, current packed, zero‑rep):
   - Compress the input once; require all three outputs to match each other and
     the existing canonical `nci/max` SHA-256. The candidate never defines its
     own expected hash.
   - Perform one unmeasured decode warm‑up, verify `cmp`.
   - Run three measured decodes under `time -v`, interleaved across builds:
     (pre‑PR41 sample 1, current sample 1, zero‑rep sample 1, … , sample 3).
   - After every decode, check `cmp`; any failure aborts the whole run.

6. **Data recording**
   - Wall clock time ([s]) and peak RSS ([KiB]) from `time -v`.
   - Medians computed over the three samples per build; no cherry‑picking.
   - Report the zero-rep RSS reduction from current-packed as a fraction of the
     768 MiB regression ceiling, the same-run reclaim fraction, and the residual
     versus pre-PR41. Do not average this file with any other file.
   - If the run completes with valid observations, insert exactly three median
     measurement rows under existing **NEW-30**, whether the compound prediction
     is confirmed or refuted: one per codec revision with one new run-mode
     identifier. Encode duration/RSS remain NULL; no duplicate hypothesis is
     created and `evaluation` remains 0. The implementation is eligible to ship
     only when the compound prediction passes.
   - Before mutation, capture a scoped backup/readback of NEW-30 and prove the
     new run-mode identifier has zero rows. Write the hypothesis note extension
     and all three measurements in one transaction; inside that transaction,
     assert exactly three rows, three distinct pinned revisions, required
     decode values present, encode values NULL, and `evaluation = 0` before
     commit. Roll back on any failed assertion.
   - An exact rerun is idempotent: three already-identical rows plus the identical
     note are a no-op; any partial or conflicting pre-existing state aborts.
   - Any partial or failed measurement run goes to the stand journal only; no DB
     entry.

7. **Constraints checklist**
   - `decode()` untouched.
   - Output bytes unchanged (enforced by archive identity gate).
   - Encode default, `cube_size_limit`, `cm_should_try`, prof.rs counters unchanged.
   - Pin 0–15, threads 4, no corpus aggregate, per‑file `nci` only.
   - `evaluation` stays 0.

---

## Why XOR‑bias is the recommended approach

Three alternative zero‑representation strategies were considered:

1. **Restore the three parallel arrays**
   The pre-PR41 layout already keeps `c` and `st` zero pages lazy. It is the lowest
   implementation risk, but deliberately returns predict/update to two or three
   cache-line streams and gives back the measured locality win.
   *Rejected* because the mandate requires the memory result to preserve speed.

2. **Sparse page map or non-zero bitmap**
   Allocate backing pages only when a slot changes from its initial value. This can
   preserve arithmetic but adds a lookup/branch to every hot access plus allocation
   and synchronization machinery.
   *Rejected* because its runtime overhead and complexity attack the exact speed
   property being preserved.

3. **OS-specific lazy backing with `mmap`**
   Use `MAP_NORESERVE` or `fallocate` tricks to defer page allocation without
   touching the data. The kernel commits pages on first write regardless of the
   stored value; a non‑zero `t` still triggers the write. The only way to avoid
   the commit is to write a zero word, exactly what the XOR‑bias achieves.
   *Insufficient on its own* – it would need to be combined with the XOR‑bias,
   adding OS‑specific complexity for no additional benefit.

The XOR‑bias approach is recommended because:

- It changes only the *encoding* of the stationary probability, leaving every
  public interface intact.
- It adds a single XOR instruction in the already‑hot probability path; the
  performance impact is expected to be within measurement noise on modern OoO
  pipelines (the preset run’s speed gains come from the packed layout’s
  cache‑line efficiency, which is preserved).
- It is fully deterministic and directly testable without maintaining a second
  feature-flagged implementation.
- It does not intentionally alter the archive or any on-disk representation;
  cross-build archive identity verifies that requirement.

---

*PRD/design only – no measurement results are recorded in this document.*
*Evidence will be added after the protocol is executed.*
