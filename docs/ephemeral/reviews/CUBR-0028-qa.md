# CUBR-0028 — QA Verdict (Adversarial)

**Reviewer:** QA & Security Lead (Datarim `/dr-qa`, autonomous mode)
**Date:** 2026-06-20
**Branch:** `feat/cubr-0028-bwt-valuescheme` @ `774fa4a`
**Reproduced code_sha:** `774fa4a8a06b1b06c6fea54e9aa792761427567b` (my own `cargo test` run regenerated the bench JSON)

## Verdict: **PASS_WITH_FINDINGS**

The −8.28%-aggregate (0.504412 vs T4 0.587240) GO is **real and lossless**. It is **not** a
Gotcha-#6-class measurement artefact. Unlike CUBR-0026 — where the GO came from a Python
*model* that omitted a fallback level's wire cost — this GO is measured from the **actual
serialized `encode()` output byte length** of a round-tripping Rust codec, and the size
model and the real encoder share the same `context_huffman_*` functions, so they cannot
diverge. Findings below are minor (labeling + one latent-edge doc gap); none undermine the GO.

---

## Checklist

### 1. Re-ran the tests — PASS
- `cargo test --release` → **172 passed, 0 failed** (6 suites). Reproduced independently.
- The bench (`tests/cubr0028_bench.rs`) genuinely round-trips, it does not re-read a cached
  size. Step 1 (lines 63-81) loops all 7 files: `encode_bwt(&data)` → `decode(&blob)` →
  `assert_eq!(recovered, data, ...)` (byte-exact), then `assert_eq!(round_trip_ok, 7)`.
- The measured `bwt_bytes` come from the **actual encoder output length**, not a model:
  per-file JSON row is built from `encode_bwt(&data).len()` (`cubr0028_bench.rs:159-162`),
  and `bwt_total` sums `bwt_blob.len()` (`:106-111`). T4 sizes are likewise asserted against
  the known baseline via real `encode_t4` (`:96-104`).
- The bench writes the JSON *after* the round-trip assertions pass; a green test therefore
  guarantees 7/7 byte-exact round-trips. My run regenerated `CUBR-0028-bench.json` with the
  current HEAD sha and `bwt_total_bytes: 25955`, `bwt_aggregate: 0.504412`, `verdict: GO`.

### 2. Gotcha #6 audit (the critical one) — PASS
Decoder branches the wire format needs (`codec.rs` decode path + `config.rs:88-109`):
1. per-file `value_scheme` header byte (selector among schemes) — `header.rs`, parsed in
   `decode()` at `codec.rs:481`.
2. `primary_index : u16 BE` — `codec.rs:1708`.
3. T4 context-table header: `n_contexts : u16 BE` — `context_huffman_decode :893`.
4. per-context entries: `ctx_id : u16 BE` + `code_len[0..n_distinct]` — `:911-927`.
5. coded bitstream — `:937-976`.

`bwt_entropy_size` (`codec.rs:1727-1730`) charges `2 + context_huffman_size(bwt_out)`. This is
**term-for-term identical** to what the real encoder emits: `bwt_entropy_encode`
(`:1686-1693`) writes `primary(2) + context_huffman_encode(bwt_out)`. The selector byte (#1)
is the existing cube-header `value_scheme` field (`pre-existing`) charged once via `serialize_cube_header`
in both `estimate_cube_size` and the real emit — not an added branch. **Every decode branch
has a matching cost term.** The decisive fact: the measured 25955 is the real `encode()` output
length, so even if the model were wrong, the GO stands on the measured number. (CUBR-0026's
failure was that it never built a real codec; here the real codec exists and is the metric.)

### 3. Competitive-selection soundness — PASS
`encode_with_config` `ValueScheme::BwtEntropy` arm (`codec.rs:335-374`) builds **both**
`bwt_entropy_encode` and `context_huffman_encode` (T4) value streams, picks
`if bwt_bytes.len() <= t4_bytes_val.len()` else T4, and writes the **winner's scheme byte**
into a re-serialized header. So a BWT-worse file emits the T4 stream + scheme byte 4 — BWT can
**never regress** the aggregate.

I verified this empirically with a throwaway integration test (since removed): on
`sparse_clustered` (BWT loses) the BwtEntropy-config encode is **byte-exact identical** to a
plain `EntropyContext` encode (`assert_eq!(bwt_blob, t4_blob)` passed); on `text`/`log_like`
the BWT blob is strictly smaller. Sum check: `502+4109+3583+5178+8205+4109+269 = 25955` =
the reported `bwt_total`, and each file's `bwt_bytes ≤ t4_bytes`. The 25955 is exactly the
sum of per-file `min(T4, BWT)` winners.

### 4. Round-trip on the winning files — PASS
`text.bin` and `log_like.bin` (the only two files with a gain, −2122 / −2140) both decode
byte-exact under BwtEntropy — confirmed in the bench Step-1 loop and re-confirmed in my
throwaway test. The gain is from a lossless reorder + entropy code, not a lossy encode (a
lossy encode would have failed the `assert_eq!(recovered, data)`).

### 5. Lossless invariant / u16 primary-index — PASS (with finding F-2)
- Forward BWT (`bwt_encode_codes :1595-1618`) is textbook cyclic-rotation sort; inverse
  (`bwt_decode_codes :1627-1682`) is standard LF-mapping. Primary index stored as `u16 BE`.
- Truncation analysis: cube mode runs only for `l ∈ (320, cube_size_limit()]` where
  `cube_size_limit() = b*b = 65536` (`config.rs:216-222`, `codec.rs:217,224`). Populated
  `count ≤ l ≤ 65536`, and `primary ∈ [0, count)`, so `primary ≤ 65535` — fits u16 with no
  truncation even at the boundary. Inputs `l > 65536` fall to raw-store (`codec.rs:217-221`)
  and never reach BWT. **No silent-truncation risk** on any cube-eligible input; corpus max
  is 16384. See F-2 for the latent-edge documentation gap.

### 6. Expectations — all 4 wish_ids assessed below.

### 7. hypothesis-log — PASS
`consilium/hypothesis-log.md` H-13 (Python GO), H-14 (preproc NO-GO), H-15 (distmap NO-GO,
Gotcha #1 confirmed), H-16 (Rust GO). H-16 records the measured result **honestly**: real
aggregate 0.504412, threshold beaten by 7.1 pp, 172 tests, and it **discloses the model↔real
gap** (0.464088 predicted vs 0.504412 measured) with the correct root cause (real Huffman
code lengths exceed the H1 entropy lower bound). No overclaiming.

---

## Wish-ID statuses

| wish_id | status | evidence |
|---|---|---|
| **orthogonal-axis-not-context-depth** | **met** | `CUBR-0028-axis2-probe-report.md:3,9,13` — "BWT builds its own locality… NOT phi-sort (Gotcha #3)"; verdict + probe-results enumerate all 3 orthogonal axes (BWT / preproc-n_distinct / distance-map), none an order-N context-key variant. |
| **python-spike-full-wire-cost-first** | **met** | `code/bench/cubr0028_axis2_bwt_reorder_probe.py:13-15,134-160` — Python probe runs before Rust, declares `branches` + `extra_terms`, asserts `len(cost_terms) == len(branches)+len(extra_terms)` (=5), and charges `primary_index` (the term CUBR-0026 dropped). Three probes (axis1/2/3) all Python; Rust touched only after the axis-2 GO. |
| **go-nogo-threshold-vs-t4** | **met** | `CUBR-0028-bench.json` (regenerated by my run): `t4_aggregate 0.587240`, `bwt_aggregate 0.504412`, `go_threshold 0.575495`, `delta_vs_t4 -0.082828`, `verdict GO`. Probe-results + verdict state baseline, candidate, % delta, explicit GO/NO-GO per axis (axis1/3 honest NO-GO). |
| **rust-only-on-go** | **met** | Rust changes confined to `code/cubrim-rs/` (4 files: config/codec/main + bench test, `git diff --stat main…` = 469 insertions), all on feature branch, gated behind the existing per-file mode selection and the GO. No production deploy, no cross-project write. |

---

## Findings (non-blocking)

> **RESOLVED in compliance (commit 3516cc2)** — both findings below were fixed inline in the
> same /dr-auto cycle (L1 Class A), not deferred. Quoted here for the audit trail; the
> labels («`cosmetic`», «doc gap») describe the original QA observation, now closed.
>
> - **F-1 (labeling):** the verdict + H-16 originally called the result "−8.28%". That is the
>   delta in **aggregate-ratio points** (0.587240−0.504412). The **relative** improvement is
>   −14.1% (4262/30217). Both clear the GO gate (on the *absolute* aggregate ≤ 0.575495).
>   Fixed: verdict.md now reads "−0.0828 aggregate-ratio points (−4262 bytes; −14.1% relative)".
> - **F-2 (latent edge):** `bwt_encode_codes` cast `primary as u16` (`codec.rs:1617`) with no
>   explicit guard. It was *currently* safe via the `cube_size_limit() = 65536` invariant
>   (`count ≤ 65536` ⇒ `primary ≤ 65535`); a future raise of `cube_size_limit` could silently
>   truncate. Fixed: a `debug_assert!(primary <= u16::MAX as usize)` + tying comment landed in
>   `bwt_encode_codes` (commit 3516cc2), elided in release builds, wire format unchanged.

## Independent judgment

**The −8.28%-aggregate GO is real and lossless.** The headline number is the actual encoded
byte length of a codec that round-trips all 7 corpus files byte-exact (172 tests, reproduced),
the size model charges every decoder branch (Gotcha #6 satisfied at both the Python-probe and
Rust levels), and the competitive `min(T4, BWT)` selection makes regression structurally
impossible. This is the opposite of the CUBR-0026 false-GO: there the GO was a model with a
missing cost term and no real codec; here the GO is a measured result from a complete,
lossless implementation whose model and encoder share code. Recommend proceeding to
`/dr-compliance`.

## Files created
- `docs/ephemeral/reviews/CUBR-0028-qa.md` (this report)

(Throwaway `tests/qa_cubr0028_fallback.rs` was created to verify competitive fallback, then removed; `CUBR-0028-bench.json` was regenerated in place by the bench test run — same content, current code_sha.)
