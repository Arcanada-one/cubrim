# CUBR-0017 verdict — DeepSeek (deepseek-chat) via coworker ask

Transport: `coworker ask --provider deepseek --profile datarim` (codex/gemini hook-blocked on Mac per reference_consilium_vendor_transport)

**1. Rank A/B/C/D (risk-adjusted path to >=15% improvement):** A > B > C >> D

- A (Order-1/context-adaptive) — directly attacks the order-1 substring gap (CUBR-0012), stays inside the canonical Huffman framework (determinism-preserving), n_distinct^2 overhead small for modest alphabets. The 10% order-0 left on text suggests context conditioning recovers most of it.
- B (Reordering) — does not create new information; reorganizes existing entropy; permutation overhead eats gains; sparse_clustered already 0.087 (no room); text runs are not spatial in cube space.
- C (LZ match pass) — large implementation surface; LZ on value-codes loses the byte-level repetition gzip exploits (abstraction mismatch); high risk, uncertain reward.
- D (ANS/rANS) — determinism hazard across Rust/Python oracle is existential; arithmetic finite-precision tie-breaks are a portability nightmare. Last resort only.

Threshold analysis: baseline 0.639416 -> target 0.543504 = 0.095912 absolute reduction. Order-0 gave ~0.061 on text alone; order-1 typically doubles context-model gains (text -> ~0.12-0.15 reduction). This single change likely clears the bar.

**2. Single recommended FIRST attempt: A — Order-1 context-adaptive canonical Huffman.**
Rationale: addresses the measured gap CUBR-0012 named and CUBR-0014 left; stays inside canonical Huffman (per-context code-length arrays, integer-only, byte-exact across Rust/Python); context-table overhead bounded (n_distinct x n_contexts x 1 byte); additive T4 ValueScheme, selector-gated, zero regression risk. Implementation sketch: context = prev_seq_code (0..n_distinct); context_tables: Vec<CanonicalHuffman>; header [n_contexts: u16] + per-context code-length arrays; fall back to order-0 when a context does not improve.

**3. Main risk: context dilution / model pollution.** If n_distinct large (binary_mixed), per-context tables fragment counts -> noisy code-length estimates -> regression vs order-0. Mitigation: selector-gated fallback to raw catches it automatically; min-count threshold (context used only if >=16 observations). Test binary_mixed specifically.

**4. Reject outright: D — ANS/rANS.** Determinism is non-negotiable; arithmetic/ANS require exact renormalization, finite-precision state tables, tie-breaks that differ between Rust i64 and Python arbitrary ints; would need per-implementation special-casing defeating the byte-exact twin. No ratio gain justifies breaking the single inviolable property.

Verdict: implement A (order-1 context-adaptive) as T4. Target text -> <=0.48, log_like -> <=0.55. Aggregate clears without touching geometry, without LZ complexity, without determinism risk. Measure binary_mixed separately for the dilution concern; selector covers regression.
