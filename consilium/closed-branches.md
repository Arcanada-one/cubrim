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

### external-address / global-snapshot lookup (16-byte universal reference)

**Status:** CLOSED — information-conservation proof (pigeonhole), same family as Gotcha #7.

**Evidence:** Operator dialogue 2026-06-22 (`_temp/addressator.txt`); refuted in-dialogue. Recorded as a steel-man so the loop does not re-propose it.

**Mechanism closed:** Replace a file with a short fixed-width reference (the
dialogue proposes 16 bytes = 8-byte server/disk id + 8-byte snapshot id) that
points at a cube bitmap "snapshot" stored in a global external library; the
decoder fetches the snapshot and unfolds it back to the file. A fixed-width
reference of B bits can address at most 2^B distinct inputs; the space of files
up to size S is 2^(8·S), astronomically larger (the dialogue's own figure: a
1 MB file space is 2^(8 000 000) ≫ 2^128). By pigeonhole, distinct files
collide on the same reference → lossless reconstruction is impossible for the
general case. The only inputs it can round-trip are those already registered in
the external library — i.e. a catalogue of known files, not a compressor. It
also violates the project's self-contained-archiver premise (no external server
dependency for decode). The "snapshot" itself (full cube bitmap) is, in the
general case, far larger than the source (2 MiB for 3D, 512 MiB for 4D), not
smaller.

**Kill condition:** None for the universal-archiver claim — the pigeonhole
argument is corpus-independent and cannot be overturned by measurement. (The
legitimate residue — corpus-local deduplication against a *charged* shared
dictionary — is tracked as a LIVE branch below; it is NOT this branch, because
it charges the dictionary in the size and makes no universal-address claim.)

**Auto-reject trigger:** Proposal relies on an external/global store, a
fixed-width universal reference/address, a content-address that is not charged
in the output size, or "look up a snapshot/seed on a server and unfold it".
Includes: global snapshot library, external address, universal reference,
content-addressed lookup whose store is not counted in the ratio.

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

### corpus-local deduplication against a charged shared dictionary

**Status:** CLOSED *on the frozen corpus* — cross-file dedup probe NO-GO
(2026-06-22). Corpus-bound, not algorithm-bound: re-open if the corpus gains
genuinely redundant multi-file structure. (The mechanism itself is sound; it
just has nothing to harvest here.)

**Probe evidence (do FIRST, no Rust):** `docs/ephemeral/research/probe_h18_crossfile_dedup.py`
— FastCDC content-defined chunking over all 10 files; cross-file redundant-byte
ratio = 0.0137% (avg-chunk 64 B) / 0.000% (avg ≥128 B), missing the 5% floor by
~3 orders of magnitude. The 10 corpus files come from 10 distinct generators
with no shared content by construction → nothing inter-file to deduplicate.
Intra-file run redundancy (18.9% dup_any) is already captured by BWT/Huffman.

**Provenance:** Operator dialogue 2026-06-22 (`_temp/addressator.txt`). The
naive "external snapshot library" form is CLOSED above; this is its legitimate
residue once the information-conservation objection is honoured — a
*self-contained* archive that ships one shared dictionary inside the artefact
and replaces repeated content (within and across the corpus files) with
references into it.

**Mechanism:** Content-defined chunking (CDC, e.g. a rolling-hash / Rabin
boundary) over the value-code stream of the whole corpus; identical chunks
across files are stored once in a shared dictionary; each file becomes a list
of chunk references plus its residual literals. Optionally combine with
delta-coding of near-duplicate chunks (zstd `--patch-from` style). This is the
inter-file lever the per-file BWT pipeline structurally cannot reach — BWT
exploits *intra-file* run locality only.

**Why it is NOT the CLOSED external-address branch:** the dictionary is
shipped inside the artefact and **charged in full, exactly once**, in the size
model. No external server, no universal fixed-width reference, no uncharged
content-address. It makes no claim to beat the entropy bound on a single random
file — it harvests *cross-file* redundancy the frozen corpus may or may not
contain.

**MANDATORY new metric (do not measure on the per-file rail):** the existing
gate computes a per-file ratio against a single `codec.rs`; that rail cannot
honestly score an inter-file scheme. A GO requires a **corpus-total** metric:
`(Σ file references + shared dictionary, counted once) / Σ original sizes`,
compared against the corpus-total of the BWT baseline (sum of per-file BWT
outputs). Charging the dictionary per-file (or not at all) is the exact
false-GO trap of Gotcha #7 (φ-map) and the CLOSED external-address branch —
the dictionary MUST be a single decoder branch charged once.

**Open questions before any Rust impl:**
- Does the frozen 10-file corpus even contain cross-file redundancy? A cheap
  probe (chunk the corpus, count duplicate chunk hashes across files) is the
  go/no-go gate — if cross-file duplicate ratio ≈ 0, this is NO-GO on this
  corpus regardless of implementation (analogue of the Gotcha #3 entropy probe).
- Chunk size vs reference overhead: small chunks find more duplicates but each
  reference costs more; the break-even is corpus-dependent and must be measured.

**Kill condition:** cross-file duplicate-chunk probe returns ≈0 on the frozen
corpus → NO-GO for this corpus (re-open only if the corpus gains genuinely
redundant multi-file structure). A corpus-total ratio that beats BWT
corpus-total AND round-trips AND charges the dictionary once → GO.

**Auto-reject trigger:** Proposal for inter-file / shared-dictionary
deduplication, content-defined chunking across the corpus, or chunk-reference
encoding — on the CURRENT frozen corpus (cross-file redundancy measured ≈0).
Re-runs of the probe are fine; a new Rust impl on this corpus is not.

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
