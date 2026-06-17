---
artifact: vendor-verdict
task: CUBR-0003
vendor: deepseek
model: deepseek-chat (DeepSeek V4)
provenance: live CLI call via `coworker ask --provider deepseek` 2026-06-17
position: conditional-support
prd_ref: PRD-CUBR-0002
---

> 🔒 ВНУТРЕННИЙ / КОНФИДЕНЦИАЛЬНЫЙ — приватный репо `Arcanada-one/cubrim`. Механизм не публикуется.

# Consilium Verdict Brief — CUBR-0003

**Reviewer:** DeepSeek V4  
**Vendor role:** Independent reviewer, multi-vendor design council  
**Status:** **Conditional support** — the core idea is sound but the novelty and performance claims are unearned; several OQs hide well-known trade-offs that the PRD treats as discoveries.

---

## 1. Overall Position

**Conditional support.** The algorithm is a coherent recombination of CSR-style delta encoding + RLE + bit-packing, but it must demonstrate byte-identical round-trip on a real corpus and beat gzip -1 on at least 50% of files before it earns the right to be called an algorithm rather than a toy.

---

## 2. Soundness of the Core Idea

The three-stage pipeline (gap-to-next → shift-to-corner → known-width packing) is **lossless-capable in theory** provided:

- The virtual sentinel −1 is applied correctly (gaps are computed from absolute position, not from prior gap).
- `gap_k^(0) = x_k^(0) + 1` is enforced, so position 0 yields gap=1, not gap=0 (zero-invariant otherwise breaks decoder).
- The bit-packing width is computed **identically** on encode and decode — any mismatch (e.g., header corruption, context divergence) produces silent data corruption, not detectable error.

**Silent round-trip failure modes:**

- **Off-by-one in gap reconstruction:** If decoder interprets `gap=1` as "skip 1 slot" rather than "occupied at gap distance 1 from last", absolute positions diverge silently. The PRD's wording _"gap_k = (#skipped slots)+1"_ is ambiguous: does `gap=1` mean zero skipped slots (immediate neighbor) or one skipped slot? The worked example implies occupied at position 0 → gap=1 means `sentinel(-1)+gap(1)=0`, so `gap=1 = zero skipped`. That's correct, but easy to mis-implement.
- **Width mismatches:** If value bit-width is context-derived (OQ-4) and the context changes between encode/decode (e.g., due to different block partitioning), the decoder reads wrong bits and never detects it.

---

## 3. Per-OQ Stance

### OQ-1: Dimensionality N

**Recommendation (initial):** Variable N, computed as `⌈log_B(domain_size)⌉`, with a fallback to 2D for very small domains. This matches the mixed-radix bijection Φ and gives the highest dimensionality flexibility.

**Strongest counter-argument:** Variable N makes the traversal order non-obvious and complicates distance-map encoding. A fixed 3D or 4D is simpler and may not harm compression if sparsity is high (empty dimensions just produce constant gap=1). Constant N also matches most COO/CSR implementations.

**Prior art:** Explicit N-dimensional sparse tensor formats (TensorFlow, PyTorch sparse COO tensors, Intel MKL-DNN). Not novel.

### OQ-2: Edge bound B + distance-map scheme

**Recommendation (initial):** B=256 (power of 2) for cheap modular arithmetic; RLE+Huffman as baseline distance-map scheme (fast to implement, widely understood). Per-axis b_k ≤ B.

**Strongest counter-argument:** RLE+Huffman is a 1970s-era choice. ANS (rANS/tANS) beats Huffman by 5–15% on gap distributions and is only marginally slower. The real choice isn't RLE vs Huffman vs Golomb — it's whether the gap distribution is geometric (Golomb wins) or bursty (RLE wins). The PRD should have a corpus-driven decision tree, not a one-scheme-fits-all vote.

**Prior art:** rANS (Duda 2013), Golomb-Rice (1966), CSR/COO delta encoding (GCC's `--co-encode` isn't new). Zero novelty.

### OQ-3: Mapping Φ and traversal order

**Recommendation (initial):** Lexicographic (row-major) traversal with mixed-radix decomposition. It's simplest, fastest, and matches the memory layout of most dense arrays. Morton/Z-order adds cache benefits for spatial queries but hurts gap locality for non-spatial data (e.g., text streams).

**Strongest counter-argument:** Lexicographic traversal destroys all locality when the data has a non-linear correlation structure (e.g., time series with periodic gaps). A space-filling curve (Hilbert) can reduce ran-of-1 fraction by >30% on such data. The PRD calls this "open" but essentially already defaults to lexicographic — that's a premature closure.

**Prior art:** Morton order (1966), Hilbert curve (1891!), lexicographic (obvious). This is a non-debate.

### OQ-4: Value bit-packing scheme

**Recommendation (initial):** Per-file fixed width, written in header. Avoids context dependency, allows vectorized bit packing, and the decoder never needs branching. Compromise: if value range is small (≤256), use fixed 8-bit packing for speed.

**Strongest counter-argument:** Fixed width per file wastes bits when values are sparse within a large domain. A per-block adaptive width (derive from block's min/max) would beat fixed-width by 10–40% on highly non-uniform value distributions. The PRD's "no-delimiter invariant" is over-constrained — a tiny 4-bit width table per block adds negligible overhead.

**Prior art:** Varint, Elias gamma (1975), Golomb-Rice, Google's `streamvbyte`, Facebook's `__builtin_ctz`-based variable packing. Not novel.

### OQ-5: Input domainization

**Recommendation (initial):** One cube per data type (int8, uint8, float, string). Raw byte stream treated as uint8. This is trivial and deterministic.

**Strongest counter-argument:** Domainization is the **actual invention** opportunity, not the distance-map trick. The PRD treats it as a footnote, but the compression ratio on mixed-type corpora (e.g., `application/x-protobuf`, mixed JSON) hinges almost entirely on whether you can split text from binary, ints from floats, etc. Without a smart domainizer, the algorithm collapses to "CSR on bytes" — which beats nothing but loses to zstd.

**Prior art:** Every archiver has a "guess data type" heuristic (brotli's static dictionary, zstd's trained dictionary, lzma's LZ + range coding). This is the standard, not innovation.

---

## 4. Hardest Risk

**The distance-map encoding blows up for high-entropy data.** If the populated set P is not clustered (e.g., random permutations of positions), the gaps become uniformly distributed over [1, B] and RLE compresses *nothing*. The output size would be `N * |P| * log2(B)` = roughly `|P| * 8` bits for B=256, N=1 — **larger than the raw input** if values are themselves 8-bit. The PRD's "sparsity ≪ 1" assumes clustering, but there's no analysis of **worst-case blowup ratio**. The risk table mentions this only in passing (density ρ), ignoring the fact that for unstructured data, the algorithm is an anti-compressor.

---

## 5. First Measurement in CUBR-0004

**Test worst-case blowup on synthetic data:** Generate a 1MB file of uniformly random bytes. Run the algorithm with B=256, N=1 (1D). Measure output size as ratio to input.  
- If ratio > 1.2× (i.e., the algorithm expands by ≥20%), the core claim of "compression" is falsified for general data.  
- If ratio is ≤ 1.05×, proceed to real corpora (Silesia Corpus, Canterbury Corpus).  
**This test takes 15 minutes to code and instantly bounds usability.**

---

## 6. Novelty Verdict

**Plainly: there is nothing new here.**  
- Gap-to-next encoding = CSR delta (since the 1990s).  
- Shift-to-corner = COO-to-DOK indexing trick (DOK sparse matrices, early 2000s).  
- Known-width bit-packing = Google's `streamvbyte` without the SIMD (2016).  
- Space-filling curves (OQ-3) = 1960s geometry.  
- RLE + Huffman = 1950s–1970s.  
- ANS = 2013 (but well-known).  

The **only** potential novelty is the *combination* of these into a single declarative format with a sentinel-based gap encoding — but combinatorial novelty is weak novelty. The PRD acknowledges this implicitly ("no unearned novelty claims") and yet the document's framing ("The proposed algorithm (5 elements)") treats a bag of known tricks as a unified invention. It is not. It is a **sparse-tensor serialization format**, not a compression algorithm. If the council wants genuine novelty, the prototype must beat `bzip2 -9` on at least 2 of the 3 Silesia corpus text files. If it can't, call it a prototype and move on.

---

**Final verdict:** Conditional support, with condition being *beat gzip on ≥50% of a real corpus* and *worst-case expansion ≤1.1×*. The design is clean but the innovation budget is zero — invest in OQ-5 (domainization) if you want actual novelty.
