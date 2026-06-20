# CUBR-0029 Probe Verdicts

**Task:** CUBR-0029 — Next-axis value-stream follow-ups after BWT GO
**Code SHA modelled against:** ebf485c (main HEAD before CUBR-0029 chore)
**Probes run:** 2026-06-20
**GO threshold:** aggregate ≤ 0.575495 (−2% vs T4 0.587240, CORPUS_TOTAL = 51456)

---

## P1 — Cargo-fmt chore

**Status: DONE**

- Branch: `chore/cubr-0029-cargo-fmt` (from main ebf485c)
- Commit: **4425d4e** (`chore(CUBR-0029): cargo fmt across src/ + tests/`)
- Files formatted: 12 src/*.rs + 3 tests/*.rs = 15 files
- `cargo test`: **172/172 green** (no semantic change)
- `cargo fmt --check`: **exits 0** (clean)
- Push/merge to main: **operator-gated** (CUBR convention)

---

## P2 — Distance-map revisit probe

**Verdict: NO-GO**

**Probe:** `cubr0029_distmap_probe.py`
**Gotcha #6 compliance:** 4 decoder branches, 4 cost terms — PASS

### Per-file ρ (populated-density) table

N=2, B=256, cube_volume=65536. Since each file has L ≤ 65536 and all
byte positions map to distinct phi-coordinates, ρ = L / 65536.

| File             | L      | ρ      | axis-0 distinct | axis-1 distinct | T4 mode |
|------------------|--------|--------|-----------------|-----------------|---------|
| sparse_clustered | 2048   | 0.0312 | 256             | 8               | cube    |
| dense            | 4096   | 0.0625 | 256             | 16              | raw     |
| text             | 16384  | 0.2500 | 256             | 64              | cube    |
| log_like         | 16384  | 0.2500 | 256             | 64              | cube    |
| binary_mixed     | 8192   | 0.1250 | 256             | 32              | raw     |
| random_high      | 4096   | 0.0625 | 256             | 16              | raw     |
| sparse_small     | 256    | 0.0039 | 256             | 1               | raw     |
| **Aggregate**    |        | 0.1903 |                 |                 |         |

**Note:** The spec's ρ ≥ 0.3 immediate-NO-GO condition is not triggered
(weighted ρ = 0.19 < 0.3). However the contribution-size check gives
a definitive NO-GO regardless.

### Contribution analysis

- Prior distance-map contribution (CUBR-0028 axis-1 probe): **26 bytes**
  (0.05% of CORPUS_TOTAL 51456 bytes; 0.09% of T4 wire bytes 30217 bytes — two different denominators)
- Best-case model (zero distance-map cost): T4_total − 26 = 30191 bytes
- Hypothetical aggregate = 30191 / 51456 = **0.586734**
- GO threshold = **0.575495**
- Gap to GO: **+0.011239** (nearly 2× the gate gap needed)

**NO-GO: Even eliminating the entire distance-map cost cannot clear the −2% GO gate.
The lever contributes 26 bytes (0.09% of T4 wire bytes; 0.05% of CORPUS_TOTAL) — 10× smaller
than what is needed to move the aggregate by −2%. No sparse corpus added. Honest NO-GO per spec.**

---

## P3 — Suffix-array O(n) BWT + larger-blocks probe

**Verdict: NO-GO**

**Probe:** `cubr0029_bigblock_probe.py`
**Gotcha #6 compliance:** 4 decoder branches, 4 cost terms — PASS

### Block-bound analysis

| File             | L      | L/limit | Block-bound? |
|------------------|--------|---------|--------------|
| sparse_clustered | 2048   | 3.1%    | NO           |
| dense            | 4096   | 6.3%    | NO           |
| text             | 16384  | 25.0%   | NO           |
| log_like         | 16384  | 25.0%   | NO           |
| binary_mixed     | 8192   | 12.5%   | NO           |
| random_high      | 4096   | 6.3%    | NO           |
| sparse_small     | 256    | 0.4%    | NO           |

**No corpus file reaches cube_size_limit = 65536.** Largest is 16384 bytes (25% of limit).

### Widening overhead (Gotcha #6)

- Current: u16 primary_index = 2 bytes/block
- Proposed: u32 primary_index = 4 bytes/block → **+2 bytes/block**
- 7 corpus blocks × +2 bytes = **+14 bytes total overhead**
- BWT after widening: (25955 + 14) / 51456 = **0.504684** (vs 0.504412 baseline)

The widening overhead is negligible, but there is ZERO ratio gain because no file
spans more than 25% of the current block limit.

### O(n) suffix-array analysis

The current `bwt_encode_codes` (codec.rs:1595) is **O(n·log n × k)** via Rust's
stable sort on index slices (comparator loops up to n on symbol ties). This is NOT
the worst-case O(n²·log n) framing — typical inputs with limited alphabet early-exit.

SA-IS / divsufsort would make it O(n), which is a **throughput improvement only**:
- Does not change BWT output or compression ratio
- Becomes relevant only if cube_size_limit is raised above 65536 (which Step 1
  shows has no present justification on this corpus)

### primary_index u16 width — explicit resolution

- **Current:** u16 (2 bytes), guarded by `debug_assert!(primary <= u16::MAX)` at codec.rs:1620
- **Why u16 is correct:** cube_size_limit() = b² = 65536 = u16::MAX + 1, so primary ∈ [0, 65535] ⊆ u16
- **What widening requires:** cube_size_limit > 65536 → primary can exceed u16::MAX → must widen to u32
  + update wire header, bwt_encode_codes return type, bwt_decode_codes parameter, all callers
  + remove/update debug_assert at codec.rs:1620
- **Decision:** deferred — no corpus justification for raising cube_size_limit today

**NO-GO: No corpus file is block-bound at the current limit. Larger blocks add zero
ratio benefit with +14 bytes wire overhead. O(n) SA-IS is a future throughput
prerequisite, not a present ratio lever. u16 primary_index is correct for L ≤ 65536.**

---

## Summary

| Phase | Direction              | wish_id                             | Verdict |
|-------|------------------------|-------------------------------------|---------|
| P1    | Cargo-fmt chore        | spike-gate-and-cargo-fmt-chore      | DONE    |
| P2    | Distance-map revisit   | distance-map-sparse-corpus-gated    | NO-GO   |
| P3    | SA O(n) BWT/big-blocks | suffix-array-bwt-larger-blocks      | NO-GO   |

Both P2 and P3 probes are honest NO-GO on the current corpus. No Rust codec
branches created. Verdicts persist in `docs/ephemeral/research/` per the
"hypotheses are logged, not lost" convention.

**Next actions (operator-gated):**
1. Push/FF `chore/cubr-0029-cargo-fmt` to `main` when ready.
2. To revisit distance-map: add a synthetic sparse corpus with ρ < 0.1 across
   all axes (not just L/65536 density) and re-run P2.
3. To revisit larger blocks: add corpus files with L ≥ 65536, re-run P3, then
   implement u32 widening + O(n) SA only on GO.
