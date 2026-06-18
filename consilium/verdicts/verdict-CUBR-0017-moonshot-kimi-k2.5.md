# CUBR-0017 verdict — Moonshot (kimi-k2.5) via coworker ask

Transport: `coworker ask --provider moonshot --model kimi-k2.5 --profile datarim` (default k2.6 returns empty; codex/gemini hook-blocked on Mac per reference_consilium_vendor_transport)

**1. Ranking (determinism-risk-adjusted): A > B > C > D.**
A extends the existing canonical-Huffman machinery (proven byte-exact in CUBR-0014) with static per-context code tables; integer-only, preserves the oracle. B is deterministically doable but speculative — entropy may simply migrate to the permutation table. C introduces a massive new determinism surface (match-finding hash chains, window offsets) clashing with the byte-exact gate. D is explicitly a determinism hazard (renormalization thresholds, division semantics drift) — unsuitable as first-line.

**2. Single recommended FIRST attempt: A — Order-1 context-adaptive entropy coding (static canonical).**
Rationale: baseline 0.639416 must drop to <=0.543504 (-15%). Slack is concentrated in text (0.568) and log_like (0.621), where CUBR-0012 identified order-1 substring dependencies that order-0 cannot capture. A static order-1 scheme (previous-symbol context -> distinct canonical length array) attacks that slack without altering cube/distance-map. Reuses the proven T3 entropy backend, multiplexing by n_distinct contexts, so the oracle stays valid (integer-only, deterministic tie-break (freq ASC, insertion_counter ASC, symbol_value ASC) per context). Selector falls back to raw/T3 when header overhead hurts -> non-regression automatic.

**3. Main risk of A: context-table header overhead (~n_distinct^2 bytes) may erase gains on high-alphabet files.** On binary_mixed (0.958, near-incompressible) or large distinct-count inputs, the cost of transmitting n_distinct separate Huffman tables can exceed benefit, pushing aggregate above target. Must cap contexts or fall back to T3 when n_distinct exceeds a file-size-derived threshold.

**4. Outright rejection: D — ANS/rANS or arithmetic backend.** Marked a determinism HAZARD and LAST RESORT. Renormalization loops, integer-division rounding, state-table tie-breaks diverge between Rust and Python, breaking the byte-exact oracle that guards the single inviolable property. Until cross-language determinism constraints are relaxed, D is incompatible with the hard gates.
