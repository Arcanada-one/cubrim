# Closed-Branch Ledger

Git-tracked record of compression directions that are provably exhausted.
The autonomous research loop checks each new proposal against this ledger
before spending implementation effort — a CLOSED-branch match triggers
auto-rejection at the consilium judge step.

## Schema

Each entry: branch name, status (CLOSED / LIVE), evidence (task IDs / Gotchas),
kill condition (what would reopen it — usually "none" for proven-closed branches).

---

## CLOSED Branches

### distance-map / content-derived φ (coordinate-storing permutations)

**Status:** CLOSED — information-conservation proof, Gotcha #7.

**Evidence:** CUBR-0028, CUBR-0029, CUBR-0030, CUBR-0031, CUBR-0032.

**Mechanism closed:** Any φ that transmits a coordinate permutation must pay
for the permutation in a decoder branch (Gotcha #6 full-branch size model).
For a content-derived φ that sorts/places by value: the φ-map transmission
cost ≥ the disorder it removes from the value stream — information conservation
prevents a net win. Measured on CUBR-0032 steel-man (OIVR): aggregate 1.981771
(≈2× worse than T4 0.587240); on structured files the φ-map alone costs
+37888 B (text), +31252 B (log_like).

**Kill condition:** None. The information-conservation argument is
corpus-independent; no empirical measurement can overturn it. Any proposal
in this category is rejected before arbiter probes.

**Auto-reject trigger:** Proposal uses a coordinate-storing φ (permutation
transmitted in the bitstream) as a compression lever. Includes: distance-map
revisit, sorted-value placement, content-derived addressing, any scheme where
the decoder needs a stored mapping from positions to cube coordinates.

---

### N-sweep on the T4 i-order value stream (Gotcha #5)

**Status:** CLOSED — structural proof (phi_inv identity) + measurement.

**Evidence:** CUBR-0025 (grouped-context), Gotcha #5.

**Mechanism closed:** The T4 value-stream coding produces seq_codes in i-order
regardless of N (phi_inv(phi(i, b, N), b) == i for any valid N). H(X_t|X_{t-1})
is byte-exact across N=2..6 on all 7 corpus files (max variation 0.0000%). No
N-value can improve T4 performance — the lever does not lie in N.

**Kill condition:** A non-i-order value-stream serialization that exploits
N-dependent axis structure. Currently no such scheme is in the LIVE set. If
proposed, it must pass the Gotcha #3 entropy probe first.

**Auto-reject trigger:** Proposal to sweep N values targeting T4-scheme
compression improvement, without introducing a non-i-order serialization.

---

### order-2 (and higher) context-only fallback chains

**Status:** CLOSED — Gotcha #6 full-branch size model failure.

**Evidence:** CUBR-0026 (spike GO at 0.547730), CUBR-0027 (real codec
0.592215 — WORSE than T4). Root cause: order-2 fallback chain has 3 decoder
branches (order-2, order-1, order-0) but the spike only charged 2 cost terms
(omitted order-1 fallback table bytes). Real codec with all 3 terms: worse
than T4.

**Kill condition:** A fallback-chain scheme that charges ALL fallback level
cost terms in the size model AND shows positive delta. Currently no such
variant is in the LIVE set.

**Auto-reject trigger:** Proposal for multi-level context fallback (order-k
for k≥2) where the size model has fewer cost terms than decoder branches.

---

### RLE pre-pass on value stream (Gotcha #2 corollary)

**Status:** CLOSED — order-1 Huffman already absorbs run redundancy.

**Evidence:** CUBR-0023 (RLE pre-pass NO-GO). Order-1 entropy coder already
captures the per-code context optimally; a separate RLE pass adds overhead
without reducing conditional entropy.

**Kill condition:** A corpus with entropy-dominated (non-run) structure
where pre-transform reduces H(X) significantly before entropy coding. Not
seen on the current frozen corpus.

**Auto-reject trigger:** Proposal for a dedicated RLE pass BEFORE entropy
coding on the i-order value stream without evidence of H(X) reduction on
the frozen corpus (entropy probe required).

---

## LIVE Branches (active research targets)

### BWT-class reorders (implicit permutation via LF-mapping)

**Status:** LIVE — current best lever. Confirmed GO in CUBR-0028.

**Mechanism:** BWT sorts the value-code sequence by context (producing
runs), but encodes the permutation implicitly via LF-mapping + one
primary_index integer. No transmitted coordinate map — escapes the
Gotcha #7 information-conservation trap.

**Current best:** aggregate 0.504412 (BwtEntropy scheme, 7-file corpus
subset, code_sha e476294879f8bfc97b6e03958508c2649cff69e3).

**Open sub-directions:**
- Larger BWT blocks (pending: widening primary_index u16→u32 costs +14 B,
  current corpus max file = 16384 bytes = 25% of L=65536 threshold;
  measure only if corpus grows to L≥65536 files).
- Suffix-array O(n) construction (throughput, not ratio; backburner until
  ratio is competitive).
- Combined BWT + additional value-stream transform (open hypothesis for
  consilium to explore).

**Kill condition:** A new hypothesis that beats BWT aggregate AND passes
the full gate rail (AC-5 merge rail) replaces BWT as the LIVE leader.
BWT itself is not closed — it is the baseline all candidates must beat.

---

### New value-stream entropy-coding improvements

**Status:** LIVE — open hypothesis space.

**Candidates in scope:**
- Context mixing (combining order-1 and order-0 predictions with learned
  weights).
- Block BWT with separate sub-block Huffman tables.
- Arithmetic coding replacing Huffman (fractional-bit savings).
- PPM (Prediction by Partial Matching) on the value-code stream.

**Constraint:** Any new scheme must pass both arbiter probes (entropy probe
+ full-branch size model) BEFORE Rust implementation.

---

## Using This Ledger

1. **Consilium brief** — the iteration brief template embeds the CLOSED
   section verbatim so free-model proposers know what is exhausted.
2. **Auto-reject** — the arbiter checks each proposal's name and mechanism
   against this ledger before running entropy/size-model probes. A proposal
   matching a CLOSED entry is rejected with a reference to the evidence.
3. **Updates** — when a new branch is exhausted (GO fails the rail) or a
   new LIVE direction opens, the orchestrator appends to this file and
   commits it to main as part of the iteration record.
