---
artifact: vendor-verdict
task: CUBR-0003
vendor: moonshot
model: kimi-k2.5 (Moonshot Kimi K2.5)
provenance: live CLI call via `coworker ask --provider moonshot --model kimi-k2.5` 2026-06-17
position: conditional-support
prd_ref: PRD-CUBR-0002
---

> 🔒 ВНУТРЕННИЙ / КОНФИДЕНЦИАЛЬНЫЙ — приватный репо `Arcanada-one/cubrim`. Механизм не публикуется.

**Vendor Reviewer:** Moonshot Kimi K2.5

## 1. Overall position
**Conditional support.** The codec is mechanically lossless but its efficiency claims rely on an unproven assumption—that N-dimensional gap-encoding captures locality better than modern adaptive entropy coders—while ignoring the context-fragmentation cost of splitting data into N independent streams.

## 2. Soundness of the core idea
The construction is coherent and *can* be lossless. The gap-to-next scheme with sentinel −1 (`gap_k^(0)=x_k^(0)+1`) and the invariant `1≤gap_k≤b_k≤B` (file:/tmp/cubr-brief.md:26) creates a prefix-free, decodable sequence because the sum of gaps along any axis reconstructs absolute coordinates modulo the edge bound. Shift-to-corner is a simple bijective reindexing to a dense prefix. Known-width packing works provided the width is explicitly stored in the header or derivable from a block-context without reading the bit-stream.

Round-trip silently breaks if:
*   **Gap overflow:** A populated cluster larger than edge bound `b_k` produces a gap `>B`, violating the invariant and causing coordinate desynchronization.
*   **Width underrun:** If the "pre-known" width (file:/tmp/cubr-brief.md:32) is derived from a local maximum that is later exceeded by a value in the packed stream, the decoder loses bit alignment.
*   **Bijection collision:** Mixed-radix Φ assumes the total cube size `∏b_k` equals the domain size; if `N` is variable per file (OQ-1) and the header omits explicit dimensionality, the decoder cannot reconstruct the hypercube geometry.

## 3. Per-OQ stance

**OQ-1 Dimensionality N**
*   **Recommendation:** Fixed `N=3` or `N=4` with per-axis `b_k` in the file header. Variable `N` adds branch-misprediction and indexing overhead for marginal density gains.
*   **Counter-argument:** For `N>4`, the product of edges explodes; the scheme collapses to a hash-table-like COO format because multi-dimensional locality becomes statistically irrelevant at high sparsity (ρ→0), and the overhead of N gap streams dominates.
*   **Reduces to:** Standard sparse tensor formats (CSR/CSC for 2-D, COO/DOK for N-D).

**OQ-2 Edge bound B + distance-map scheme**
*   **Recommendation:** `B=256` (byte-aligned) with Golomb-Rice (adaptive per-axis parameter) or tANS for the gap streams. Pure RLE fails on scattered gaps.
*   **Counter-argument:** `B=256` forces artificial fragmentation on data with natural periodicity >256 (e.g., 4KB page-aligned pointers), creating phantom "jumps" that inflate the distance-map size.
*   **Reduces to:** Golomb codes (1966), PforDelta (Zukowski et al.), and ANS (Duda).

**OQ-3 Mapping Φ (axes + traversal order)**
*   **Recommendation:** Z-order (Morton) as the default; Hilbert offers better locality but 2-3× CPU cost for typically <5% compression improvement.
*   **Counter-argument:** Domain-specific axes (e.g., separating timestamp from payload) can outperform space-filling curves, but this violates the PRD's implied generic byte-stream interface and requires schema awareness.
*   **Reduces to:** Space-filling curves (Morton 1896, Hilbert 1891) and locality-sensitive hashing.

**OQ-4 Value bit-packing scheme**
*   **Recommendation:** Block-fixed width (e.g., 1K values) with explicit width byte in block header. Context-dependent widths risk misprediction without beating simple FOR (Frame-of-Reference).
*   **Counter-argument:** Heavy-tailed distributions (e.g., document IDs) favor Elias γ/δ or Golomb-Rice, but these require delimiters or codebooks that violate the "no-delimiter" invariant (file:/tmp/cubr-brief.md:32).
*   **Reduces to:** FOR/PforDelta and Elias integer codes.

**OQ-5 Input domainization**
*   **Recommendation:** Treat input as raw byte stream (1-D cube). Pre-tokenization assumes compressibility patterns not present in binary executables or encrypted streams.
*   **Counter-argument:** Without semantic domainization (e.g., splitting pointers from offsets), sparsity ρ remains artificially high because "empty" slots often contain compressible structure (repeated zeros) that a transform like BWT would exploit, whereas CUBR treats them as voids.
*   **Reduces to:** Preprocessing stages in bzip2 (Burrows-Wheeler) or zstd (dictionary training).

## 4. The hardest risk (underrated by PRD)
**Entropy-coder context dilution.** By mandating "N streams (one per axis)" (file:/tmp/cubr-brief.md:27) plus a separate value stream, the design fragments the statistical context. Modern codecs (zstd, LZMA) capture cross-dimensional redundancy (e.g., correlations between X-gap and Y-gap in a 2-D image). CUBR isolates axes, preventing an adaptive entropy coder from exploiting these dependencies. Furthermore, the "known-width" constraint (file:/tmp/cubr-brief.md:32) forbids dynamic arithmetic coding of values, hard-capping efficiency at the Shannon limit of the quantized gaps—likely worse than a flat LZ77+ANS approach on non-clustered data.

## 5. What to measure first to fastest-falsify
Measure the **mean run-length of gap=1 events** (indicating dense clusters) on a representative corpus. If the average run length is <16–32, the distance-map overhead (N streams × ANS state + headers) will exceed the benefit, and CUBR will underperform against Brotli/zstd. This is a single-bit experiment: low locality falsifies the core hypothesis that gap-encoding exploits structure better than modern dictionary coders.

## 6. Novelty verdict
**No genuinely new algorithmic primitive is present.** This is a recombination of:
*   **CSR (Compressed Sparse Row)** delta encoding (gap-to-next is identical to CSR's compressed index deltas);
*   **FOR/PforDelta** bit-packing (shift-to-corner + known-width packing);
*   **Space-filling curves** (Morton/Hilbert) for Φ;
*   **Standard entropy coding** (Golomb/Rice/ANS).

The "N-dimensional" generalization of CSR is textbook sparse tensor storage (COO/DOK). The proposal is an architectural packaging of existing techniques, not a novel compression algorithm.
