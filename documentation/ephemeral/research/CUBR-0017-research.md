# CUBR-0017 Research Report: Compression Algorithms, State-of-the-Art, and Novelties

> PRIVATE — internal research artefact. Ephemeral research directory.
> This report covers V-AC-1 through V-AC-4 for the order-1 context-adaptive Huffman prototype.

---

## Section 1 — Algorithm Family Survey (V-AC-1)

Analysis of six open compression algorithm families relevant to Cubrim's cube model pipeline.

### 1.1 LZ77 / LZ78 (Lempel-Ziv sliding-window and dictionary)

**Principle.** LZ77 encodes each input position as a back-reference (distance, length) to a matching string in a sliding window of recent output. LZ78 builds an explicit phrase dictionary instead. Both replace repeated substrings with shorter tokens. Modern derivatives: Deflate (gzip, PNG), LZX (CAB), LZMA (7-Zip, xz), LZ4, Snappy, Zstd's LZ stage.

**Strengths.** Exploits long-range repetition without requiring a probability model. Works extremely well on text (repeated words, phrases) and log data (repeated timestamps, log prefixes). Decompression is fast (sequential dictionary lookup). LZ4 and Snappy are near-memory-bandwidth speed.

**Weaknesses.** Does not exploit conditional probabilities — it cannot assign shorter codes to characters based on context. Blind to byte-level correlation not expressed as literal substrings. Poor on already-random or encrypted data. Overhead from back-reference encoding grows with small inputs.

**Applicability to Cubrim.** Cubrim's value stream after cube encoding is a sequence of value-codes (integers in [0, n_distinct)) that may share long runs but not repeated substring patterns — the structure is arithmetic, not textual. LZ back-referencing would add framing overhead without benefiting from the cube's spatial clustering. The gap-distance stream might benefit from LZ if repeating gap patterns exist, but RLE already dominates there. LZ is likely sub-optimal vs. the cube pipeline's native structure but could be useful as a post-processing layer if future work produces longer blocks.

---

### 1.2 Huffman Coding (static and adaptive)

**Principle.** Build an optimal prefix-free binary code from symbol frequency counts: assign shorter codewords to more frequent symbols. Static Huffman requires a single frequency scan. Canonical Huffman normalizes code assignment to code-length sequences, enabling compact header representation (one byte per symbol length) and fast decode. Adaptive Huffman (Vitter FGK) updates the tree on each symbol without a pre-scan, at the cost of constant tree-maintenance overhead.

**Strengths.** Asymptotically optimal for integer code-lengths (wastes at most 1 bit/symbol vs. entropy). Extremely fast encode/decode (table lookup). Canonical form enables compact headers and simple decoder without explicit tree storage. Deterministic: same frequencies yield identical codes — byte-exact compatibility with a Python oracle is straightforward.

**Weaknesses.** Order-0 Huffman ignores context. Each symbol is coded with its marginal frequency, missing conditional structure. Requires a full frequency pass before encoding (two-pass). Inefficient for low-entropy symbols whose true probability exceeds 0.5 (arithmetic/ANS can exploit these without wasting the forced-one-bit floor).

**Applicability to Cubrim.** The core of CUBR-0014's T3 Entropy and T4's order-1 extension. Canonical integer Huffman (already implemented in `huffman.rs`) is the byte-exact foundation. Order-1 extension (T4) maintains one table per previous symbol context — direct application to Cubrim's value-code stream where conditional distributions may differ markedly between contexts (e.g., after a high-value code the next is more likely high-value too, in text-like inputs).

---

### 1.3 Arithmetic Coding (AC) and Range Coding (RC)

**Principle.** Encode a sequence of symbols as a single fractional number in [0, 1). Each symbol's interval is subdivided proportional to its cumulative probability. Range coding is an integer implementation of AC that avoids floating-point. Both achieve expected code-length approaching entropy within ε per symbol (where ε → 0 for long sequences). Entropy for each symbol can be a non-integer number of bits.

**Strengths.** No 1-bit floor per symbol: can use fractional bits. Approaches Shannon entropy tightly. Context conditioning is natural — just supply a different probability table for each context without structural changes to the coder. Widely used in video standards (HEVC CABAC) and learned compression.

**Weaknesses.** More complex to implement correctly and byte-exactly than Huffman — the interval arithmetic requires careful integer overflow handling. Decode requires sequential state; no random access. Parallel decode is non-trivial. Slower than Huffman or ANS on modern CPUs without SIMD.

**Applicability to Cubrim.** AC is strictly better than Huffman at approaching entropy. For Cubrim's value-code stream (small n_distinct, e.g., 2–50 symbols), the per-symbol loss of Huffman over AC is at most 1 bit/symbol. For a 16 KB text file with ~256 distinct codes, that is ≤ 16 KB / 8 = ≤ 2 KB potential gain. If T4 order-1 Huffman still falls short of the target, a future direction could swap the per-context coder to AC/RC. Complexity cost: byte-exact Python-Rust parity becomes harder to maintain.

---

### 1.4 Asymmetric Numeral Systems (ANS / tANS / rANS / FSE)

**Principle.** ANS (Duda, arXiv:1311.2540) encodes a stream by mapping each symbol to a new state in a finite automaton whose transitions are derived from symbol probabilities. tANS uses a lookup table; rANS uses a multiply-and-shift recurrence. Both combine the speed of Huffman with the compression rate of arithmetic coding. Finite State Entropy (FSE), used in Zstandard, is a production tANS implementation.

**Strengths.** Near-arithmetic-coding compression rates. Encode and decode in a single register-width integer state — extremely CPU-cache-friendly. rANS decode is embarrassingly parallel (reversed order of operations). Used in Zstd, Apple LZFSE, Google Draco — industry-proven.

**Weaknesses.** More complex than Huffman to implement and to verify byte-exactly across two languages (Rust + Python). rANS decode requires knowing the sequence length and encoding in reverse. Adapting to per-context tables (order-1 ANS) requires table switching at each step — workable but adds complexity. Integer table construction (spreading symbols to state slots) is non-trivial.

**Applicability to Cubrim.** tANS or rANS would replace per-context Huffman in a T4 successor (T5 direction). The expected gain over order-1 Huffman is small for Cubrim's n_distinct ≤ 256 (Huffman wastes ≤ 1 bit/symbol vs. true entropy; for 30% entropy symbols that is ≤ 0.3 bits additional waste). ANS is the right long-term direction if T4 order-1 Huffman does not close the remaining gap to the 15% target — implement ANS as a potential CUBR-0018/T5 direction.

---

### 1.5 PPM — Prediction by Partial Matching (with order-k context models)

**Principle.** PPM builds a set of context models at orders 0, 1, 2, …, k. To encode a symbol it tries the longest context first; if the symbol has been seen in that context, it codes it with the conditional probability; if not, it escapes to the next shorter context. Final fallback is a uniform distribution. The arithmetic coder then encodes based on the predicted probability. PPM achieves near-optimal compression on natural language text.

**Strengths.** Captures deep conditional dependencies (order-4 PPM approaches theoretical entropy on English text). Adaptive — no pre-scan needed. Widely studied; many well-analyzed variants (PPM-A, PPM-C, PPM-D, PPM-*).

**Weaknesses.** Memory usage grows with context history (unbounded context trees for high orders). Slow — each symbol requires context-tree traversal and arithmetic-coder update. Context trees require careful implementation to avoid blowup on large alphabets. Escape probability estimation is non-trivial.

**Applicability to Cubrim.** Cubrim's value-code stream has a small, bounded alphabet (n_distinct ≤ 256 codes) and relatively short blocks (≤ 65536 bytes per cube). Order-1 context (prev symbol → current symbol distribution) is the minimum useful PPM-like approach and is what T4 implements. Higher-order contexts (order-2, order-3) could be explored in a T5 direction but face context-tree overhead on short blocks — most order-2 contexts would have only 1–2 training samples per context. T4 already captures the dominant first-order conditional structure.

---

### 1.6 Context Mixing (CM) — PAQ family, CMIX, Brotli's context model

**Principle.** Context mixing blends predictions from multiple specialized models. PAQ-family compressors (Matt Mahoney) combine hundreds to thousands of binary context models (each predicting P(next_bit = 0 | context)) using logistic-domain averaging, then feed the mixture to an arithmetic coder. Brotli uses static context models with Huffman coding and IETF-standardized literal context modes (LSB-6 and MSB-6 of the previous byte) for literal coding.

**Strengths.** Achieves state-of-the-art lossless ratios on heterogeneous data by blending structural, positional, and statistical models. Brotli's context mixing is practical (standardized, fast) — LSB-6 mode is a 2-bit context that divides literals into 64 context classes, roughly approximating an order-1 byte-level context model.

**Weaknesses.** PAQ-style CM is extremely slow (seconds per megabyte, gigabytes of RAM). Not suitable for Cubrim's performance goals. Brotli-style static context mixing is faster but requires pre-tuned context maps derived from training data. Harder to maintain byte-exact cross-language parity than simple Huffman.

**Applicability to Cubrim.** Brotli's LSB-6 context mode (context = low 6 bits of previous byte) is directly analogous to Cubrim's T4 order-1 approach (context = previous value-code). For Cubrim's value-code stream where codes are in [0, n_distinct) with n_distinct ≤ 256, using the full previous code as context (order-1) subsumes the coarser LSB-6 approach. If n_distinct is large (say, 200+), context counts per slot may be too sparse — the MIN_CTX_COUNT=16 threshold in T4 handles this by falling back to the order-0 table for sparse contexts.

---

## Section 2 — State of the Art: Recent arXiv Works (V-AC-2)

Five recent papers with direct relevance to Cubrim's compression pipeline, verified via arXiv.

### 2.1 Duda, J. (2014, updated). *Asymmetric numeral systems: entropy coding combining speed of Huffman coding with compression rate of arithmetic coding.*
**arXiv:1311.2540** — https://arxiv.org/abs/1311.2540

**Authors/year:** Jarosław Duda, 2013/2014 (widely cited foundational work; FSE/Zstd deploy it in production).

**Takeaway for Cubrim.** rANS / tANS can replace per-context Huffman in T4's coder — same output to within ~0.01 bits/symbol (the 1-bit Huffman floor is the dominant gap, and ANS largely closes it). If the T4 order-1 Huffman does not reach the 15% target, an ANS-based T5 is the natural successor. The Python parity oracle would need an ANS twin, but the Rust side has proven implementations (the `rans` and `constriction` crates) to draw from.

---

### 2.2 Premkumar, A. (2024). *Neural Entropy.*
**arXiv:2409.03817** — https://arxiv.org/abs/2409.03817

**Authors/year:** Akhil Premkumar, September 2024 (NeurIPS 2025 camera-ready).

**Abstract summary.** Introduces "neural entropy" — an information-theoretic measure of how much information a neural network's weights store during diffusion training. The paper shows diffusion models achieve extremely efficient compression of structured data ensembles as a consequence of their entropy structure.

**Takeaway for Cubrim.** Not directly implementable in Cubrim's current pipeline (no neural component). However, the paper's framing — that a model which captures conditional structure can approach theoretical entropy — reinforces the motivation for T4: adding the prev-symbol context is a minimal Markov model that approximates the first-order conditional distribution without neural overhead. If further gains are needed in CUBR-0018+, lightweight neural predictors (e.g., a small lookup table trained per-block) could replace the count-based context tables.

---

### 2.3 Lu, J. et al. (2025). *Learned Image Compression with Dictionary-based Entropy Model.*
**arXiv:2504.00496** — https://arxiv.org/abs/2504.00496 (CVPR 2025)

**Authors/year:** Jingbo Lu, Leheng Zhang, Xingyu Zhou, Mu Li, Wen Li, Shuhang Gu, 2025.

**Abstract summary.** Proposes a dictionary-based cross-attention entropy model for learned image compression — a learnable dictionary captures typical feature patterns from training data, enabling more accurate probability estimates. Achieves state-of-the-art rate-distortion performance with manageable compute cost.

**Takeaway for Cubrim.** The dictionary concept maps to Cubrim's existing value-dictionary (`inverse_dict`), which maps codes to original byte values. The CVPR-2025 contribution of learning which "typical patterns" dominate is analogous to Cubrim choosing which context slots to materialize (the MIN_CTX_COUNT threshold). For lossless compression on a fixed corpus, the analogue of the dictionary is the per-context frequency table trained on the block being encoded — identical in spirit to T4's adaptive per-context Huffman.

---

### 2.4 Wan, M. et al. (2025). *Lossless Compression: A New Benchmark for Time Series Model Evaluation.*
**arXiv:2509.21002** — https://arxiv.org/abs/2509.21002

**Authors/year:** Meng Wan, Benxi Tian, Jue Wang, et al., 2025.

**Abstract summary.** Proposes lossless compression as a unified information-theoretic evaluation criterion for time series models, releasing TSCom-Bench — a framework that adapts time series models as compression backends and reveals distributional blind spots that standard forecasting benchmarks miss.

**Takeaway for Cubrim.** Cubrim's corpus includes `log_like` and `text` files — both share characteristics with time series (repeated patterns, bounded value distributions). The paper's finding that models which compress well generalise well supports Cubrim's approach of fitting a statistical model (order-1 Huffman) to each block: a block-local context table is a block-specific compressor that captures exactly the conditional structure present in that block. The benchmarking methodology (per-file ratio + aggregate) directly mirrors Cubrim's PRD measurement contract.

---

### 2.5 Matt, J.G. et al. (2025). *Lossless Compression of Time Series Data: A Comparative Study.*
**arXiv:2510.07015** — https://arxiv.org/abs/2510.07015

**Authors/year:** Jonas G. Matt et al., October 2025.

**Abstract summary.** Comparative study of lossless compression algorithms (Zstd, bzip2, Blosc, and others) on time series data; Zstd consistently leads in speed, while bzip2's BWT+MTF+RLE+Huffman pipeline achieves the best ratio on structured numeric data.

**Takeaway for Cubrim.** bzip2's pipeline is instructive: BWT permutes the data so that similar bytes cluster (analogous to Cubrim's cube axis sorting), MTF then makes frequent neighbours adjacent in the code sequence (analogous to Cubrim's code assignment), and the final Huffman stage compresses the resulting low-entropy sequence. T4's order-1 Huffman is a lighter analogue of this pipeline applied to Cubrim's value-code stream rather than raw bytes. The comparison also confirms that Zstd's FSE (tANS) achieves better ratio than Huffman alone on structured data — supporting a potential T5 ANS direction.

---

## Section 3 — Recommendations (V-AC-3)

Concrete recommendations tied to mechanisms and expected effects, ranked by implementation cost / expected gain ratio.

### R1 — Order-1 context-adaptive Huffman on the value-code stream (T4, primary target)

**Mechanism.** Maintain one canonical Huffman table per distinct previous value-code. For each position in the i-order value sequence, look up the table keyed by the preceding code (sentinel 0 for position 0), then encode the current code with that table's codeword. On decode, mirror the same context-switch logic. Fall back to the order-0 table (T3 Entropy) for contexts with fewer than MIN_CTX_COUNT=16 training samples.

**Expected effect.** For text-like inputs where adjacent value-codes are correlated (e.g., ASCII letter followed by ASCII letter, whitespace followed by whitespace), the conditional distribution H(X_t | X_{t-1}) is substantially below the marginal H(X_t). CUBR-0014 T3 Entropy achieved 0.567871 ratio on `text` — if first-order conditional entropy is ~15% lower than marginal entropy on this corpus, T4 should achieve ~0.483 on `text` (below the ≤0.4827 per-file target). Real measured numbers required; this is the primary hypothesis.

**Applies to Cubrim.** Yes — implemented as T4/ValueScheme::EntropyContext. The MIN_CTX_COUNT and n_contexts cap bound overhead on binary_mixed inputs where high-entropy distributions make context tables wasteful.

---

### R2 — Selector fallback: always pick the best scheme at encoding time (current T4 design)

**Mechanism.** In `estimate_cube_size`, compute T4's predicted output size and only select T4 if it beats T3 (Entropy) and T2 (RleCodes). The selector already does this implicitly by being called at encode time. Explicit per-file selection makes T4 a strict non-regression over T3: if T4 is larger, the encoder falls back to T3.

**Expected effect.** Non-regression on all 7 corpus files is guaranteed automatically. No manual selection of scheme per file type.

**Applies to Cubrim.** Yes — built into the existing architecture; T4 must plug into `estimate_cube_size` correctly.

---

### R3 — Bounded context count: cap n_contexts to bound header overhead

**Mechanism.** Before materialising context tables, compute the projected header size: `2 + n_present_contexts * (2 + n_distinct)` bytes. Cap n_present_contexts so that the header does not exceed 5% of the input size. This handles `binary_mixed` inputs where n_distinct is large and many contexts are sparsely populated — in the extreme case, uncapped T4 would emit n_distinct^2 / 8 bytes of header, reversing gains.

**Expected effect.** Prevents T4 from expanding binary_mixed above T3. The selector fallback (R2) handles the case where even the capped version is worse than T3.

**Applies to Cubrim.** Yes — n_contexts cap is part of the design (Moonshot proposal in consilium verdict). Implementation: sort contexts by frequency and materialise only the top-K most frequent, where K is chosen so the header stays below the cap.

---

### R4 — Run-length hybrid: RLE pre-pass before entropy coding (future, T5 direction)

**Mechanism.** Apply a short run-length pass over the value-code sequence to collapse uniform runs (already handled by T2 RleCodes), then apply order-1 Huffman to the post-RLE symbol sequence. Combines the 6× run gain of T2 on `sparse_clustered` with the conditional entropy gain of T4 on `text`. For inputs with mixed statistics (some runs, some correlated non-run patterns), a two-pass encoder could outperform either T2 or T4 alone.

**Expected effect.** On `sparse_clustered`, T2 already achieves 0.086914 (near-optimal given cube overhead) — little additional gain from T4. On `log_like`, patterns include both repeated tokens and conditional structure — a hybrid could improve from T4's estimated ~0.52–0.55 down toward 0.45. Cheap test: apply RLE first, then measure entropy of the post-RLE residual vs. direct order-1 entropy.

**Applies to Cubrim.** Future direction — CUBR-0018 candidate if T4 alone does not reach the 15% target.

---

### R5 — Context definition: use value (not code) as context key

**Mechanism.** Instead of conditioning on the previous value-code (integer in [0, n_distinct)), condition on the previous raw byte value (in [0, 255]). This exposes richer context at the cost of up to 256 context tables instead of n_distinct tables. For inputs where n_distinct < 64, both are equivalent. For text with n_distinct ≈ 50-70 printable ASCII codes, conditioning on the raw byte value (which = inverse_dict[code]) would have the same number of contexts but carry natural byte-level semantics (e.g., after ASCII 0x20 space, the next byte is likely a capital letter).

**Expected effect.** Slightly richer context at the cost of 256/n_distinct more context tables. For typical Cubrim inputs with n_distinct ≤ 60, this is minimal overhead and may reduce context-sparsity issues when n_distinct is low.

**Applies to Cubrim.** Minor variant — implement as a T4b alternative if T4a (code-keyed) misses the target. Cheap test: measure H(X_t | prev_byte) vs. H(X_t | prev_code) on the corpus.

---

## Section 4 — Novel Unimplemented Ideas (V-AC-4)

Three ideas not currently in Cubrim's implementation, beyond the T4 direction, with honest novelty and risk assessment.

### Idea 1 — Axis-sorted value stream re-ordering before entropy coding

**Essence.** Currently the value stream is encoded in i-order (sequential input position). The cube's axis structure provides a different traversal: for each axis dimension k, sort occupied positions by coordinate k before coding the value sequence. Different sort orders expose different statistical patterns — axis-k traversal groups values that share coordinate k (analogous to "scanline order" in image compression), potentially making adjacent values in the traversal more correlated than in i-order.

**Difference from known work.** Standard order-1 Huffman conditions on the immediate predecessor in a fixed traversal order. This idea changes the traversal order itself — the encoder could try multiple traversals (i-order, axis-0 sort, axis-1 sort) and pick the one with lowest order-1 conditional entropy. It is not a known published technique for the specific cube-model value stream; it exploits the cube's multi-dimensional structure, which is unique to Cubrim.

**Win hypothesis.** For sparse inputs where populated points cluster along axis dimensions (e.g., the `sparse_clustered` corpus), axis-sorted traversal would expose long runs of the same value-code, making both RLE and order-1 entropy more effective. Expected gain: 5–15% ratio improvement on sparse inputs over T4 i-order; neutral or slight regression on dense text where axis sorting gives random order.

**Cheap test.** Compute H(X_t | X_{t-1}) for i-order vs. axis-0-sorted traversal on all 7 corpus files using Python's scipy.stats.entropy on empirical bigram tables. No code change to Rust required — just a 50-line Python analysis script.

---

### Idea 2 — Block-adaptive context order selection (per-cube order-0 vs order-1 gate)

**Essence.** For each cube block at encode time, measure the empirical mutual information MI(X_t; X_{t-1}) on the value-code sequence. If MI exceeds a threshold θ (e.g., 0.1 bits), use T4 order-1; otherwise fall back to T3 order-0. The threshold θ is set by the encoder (not stored in the header — the selector already picks the scheme that compresses better; MI is just a faster heuristic than encoding both and comparing sizes).

**Difference from known work.** Context-adaptive arithmetic coders (CABAC) adapt order on-the-fly per position. This idea makes a single per-block decision at encode time based on the block's measured MI — a batch-mode offline oracle. Not published as a discrete technique for short-block cube-model coding; standard PPM always tries all orders.

**Win hypothesis.** For `binary_mixed` and `random_high` inputs where MI ≈ 0, the heuristic gate avoids the T4 overhead entirely, resulting in T3-class output with zero T4 context-table bytes. For text where MI ≈ 0.3 bits, T4 is selected and gains ~15% vs. T3. Net effect: robust non-regression across all inputs, faster encode time (no dual-encode for most inputs).

**Cheap test.** Measure MI(X_t; X_{t-1}) for each corpus file using a Python bigram table (entropy of marginal minus conditional entropy). Compare MI values to the selector's binary decision. If MI thresholding perfectly predicts the selector's choice, the heuristic is valid and eliminates the need to encode both T3 and T4 for comparison.

---

### Idea 3 — Value-stream BWT (Burrows-Wheeler Transform) as a pre-pass

**Essence.** Apply the Burrows-Wheeler Transform to the value-code sequence before entropy coding. BWT is a reversible permutation that groups identical symbols and their successors together, substantially lowering conditional entropy of the resulting sequence. After BWT, a simple order-0 Huffman or even RLE achieves near-PPM-level compression without the order-k model overhead. The BWT suffix-array construction for short sequences (≤ 65536 symbols) is O(n log n) and cheap.

**Difference from known work.** bzip2 applies BWT to raw byte sequences. Applying BWT to Cubrim's value-code sequence (instead of raw bytes) is novel because: (a) the alphabet is small (n_distinct ≤ 256, often ≤ 60), making BWT suffix array construction faster and the resulting symbol grouping more effective; (b) the BWT permutation is applied after the cube's coordinate transform and value-code assignment, not to the original bytes — the composed transform (cube-coord → code → BWT) is a genuinely different entropy structure.

**Win hypothesis.** BWT on text-type value-code sequences should cluster identical consecutive codes, enabling an order-0 Huffman on the post-BWT stream to match or exceed order-1 Huffman on the pre-BWT stream. Effective BWT compression on enwik8 achieves ~2.2 bpb with Huffman follow-up — well below order-0 entropy. If the value-code alphabet has entropy ≈ 3 bits (n_distinct ≈ 60, roughly uniform), order-0 Huffman on post-BWT should approach ~2.5 bits, comparable to order-1 Huffman at ~2.0 bits directly. The BWT adds about n·log(n) / 8 bytes of suffix-array overhead for the inverse permutation — viable only for blocks where n·log(n)/8 < savings.

**Cheap test.** Implement a Python-only BWT + order-0 Huffman on the value-code sequence for each corpus file. Measure ratio vs. T3 and T4. No Rust change needed until the Python prototype validates the hypothesis. Suffix array construction for n ≤ 16384 takes < 1 ms in Python with SA-IS.

---

*End of research report. V-AC-1 through V-AC-4 complete: 6 algorithm families, 5 arXiv papers with verified links, 5 recommendations (R1–R5), 3 novel ideas.*
