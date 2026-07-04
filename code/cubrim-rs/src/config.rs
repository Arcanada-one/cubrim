// Configuration for the encode path.
//
// v1_default() returns the configuration that matches the frozen default byte
// stream (values match the hardcoded constants used before config plumbing).
// encode(data) == encode_with_config(data, &EncodeConfig::v1_default()) byte-for-byte.
//
// The header is self-describing; decode is deterministic from header fields alone
// and does not read this struct (R6). Non-default configs only affect encode
// decisions and are compatible with decode as long as the header is written
// correctly (which encode_with_config guarantees).

use crate::codec::HEADER_OVERHEAD_BOUND;
use crate::phi::B_DEFAULT;

/// Gap encoding scheme for the per-axis distance map streams.
///
/// Default (RleU16) reproduces the v1 byte stream exactly.
/// PackedNibble uses a LEB128-style varint per gap: 1 byte for gaps < 128,
/// 2 bytes for gaps in [128, 16383], etc. Reduces gap-stream size on inputs
/// where most gaps are small (e.g. sparse_clustered).
#[derive(Debug, Clone, PartialEq, Copy)]
pub enum GapScheme {
    /// v1-default: (value: u16, run_length: u16) pairs, 4 bytes per unique gap value.
    RleU16,
    /// Varint-per-gap: each gap g encoded as LEB128 (1 byte if g < 128, 2 if < 16384).
    PackedNibble,
}

/// Value encoding scheme for the bitpacked value stream.
///
/// Default (BitpackFixed) reproduces the v1 byte stream exactly — lex-order
/// point values packed W bits each.
/// RleCodes gathers value codes in SEQUENTIAL INPUT (i-order), not lex order,
/// then run-length encodes them as (code: u8, run_length: u16) triplets.
/// Codes are in [0, n_distinct) so they fit u8.  Run-length capped at 65535
/// (same MAX_RUN cap as rle.rs).
/// Entropy applies static canonical Huffman coding (order-0) to the value-code
/// stream: n_distinct code-length bytes followed by the MSB-first bitstream.
/// Header byte = 3.
#[derive(Debug, Clone, PartialEq, Copy)]
pub enum ValueScheme {
    /// v1-default: bitpack values in lex-sorted point order, W bits each.
    /// Byte-identical to all previous output. Header byte = 1.
    BitpackFixed,
    /// RLE on the value CODE sequence in sequential (i-order) input order.
    /// Collapses clustered runs into compact (code: u8, run: u16) triples.
    /// Header byte = 2.
    RleCodes,
    /// Static canonical Huffman on the value-code stream (order-0).
    /// Wire: [code_len[0..n_distinct]: u8 × n_distinct] + [MSB-first bitstream].
    /// Header byte = 3.
    Entropy,
    /// Order-1 context-adaptive canonical Huffman on the value-code stream (T4).
    /// Context = previous value-code (sentinel 0 for position 0).
    /// Contexts with fewer than MIN_CTX_COUNT=16 observations fall back to the
    /// shared order-0 table (ctx=FALLBACK_CTX sentinel, stored at index 0 in header).
    ///
    /// Wire (after header + gap streams):
    ///   [n_contexts : u16 BE]                              — number of context entries
    ///   for each context entry (ascending ctx_id order):
    ///     [ctx_id : u16 BE]                                — context code (0=fallback/order-0)
    ///     [code_len[0..n_distinct] : u8 × n_distinct]      — code-length table for this ctx
    ///   [coded bitstream : MSB-first, byte-aligned, zero-padded tail]
    ///
    /// Header byte = 4.
    EntropyContext,
    /// Order-2 context-adaptive canonical Huffman on the value-code stream (T5).
    /// Context key = (prev2_code, prev_code) — a pair of the two most recently
    /// decoded codes (sentinels: pos 0 → (0,0), pos 1 → (0, first_code)).
    ///
    /// Fallback chain (3 levels on the wire):
    ///   1. (prev2, prev) has ≥ MIN_CTX_COUNT observations → own order-2 table
    ///   2. else (prev) has ≥ MIN_CTX_COUNT observations   → order-1 fallback table
    ///   3. else → shared order-0 global table (sentinel key (0,0))
    ///
    /// Wire (after header + gap streams):
    ///   [min_ctx_count : u16 BE]                           — 2 bytes (sweepable threshold)
    ///   [n_contexts    : u16 BE]                           — total context entries in header
    ///   for each context entry (ascending key order):
    ///     [tag : u8]                                       — 2 = order-2, 1 = order-1, 0 = order-0 fallback
    ///     [prev2_code : u16 BE]  (tag=2 only)              — 2 bytes (order-2 entries only)
    ///     [prev_code  : u16 BE]  (tag=2 or tag=1)          — 2 bytes
    ///     [code_len[0..n_distinct] : u8 × n_distinct]
    ///   [coded bitstream : MSB-first, byte-aligned, zero-padded tail]
    ///
    /// Header byte = 5.
    EntropyContext2,
    /// BWT reorder + order-1 context-adaptive Huffman on the transformed code stream.
    ///
    /// The value-code sequence (i-order) is reordered using the Burrows-Wheeler
    /// Transform (BWT), which groups runs of identical codes by sorting cyclic
    /// rotations. The primary index (position of the original first element in the
    /// sorted rotation list) is stored for exact inverse.  The BWT output is then
    /// coded with T4 (EntropyContext) — the same order-1 context Huffman as scheme 4.
    ///
    /// The BWT preserves n_distinct → the cube header and gap map are unchanged.
    /// Only the value bitstream changes.  The encoder selects this scheme only when
    /// the BWT branch produces a smaller blob than EntropyContext (scheme 4).
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [n_contexts    : u16 BE]     — T4 context-table header (same as EntropyContext)
    ///   for each context entry:
    ///     [ctx_id : u16 BE]
    ///     [code_len[0..n_distinct] : u8 × n_distinct]
    ///   [coded bitstream : MSB-first, byte-aligned, zero-padded tail]
    ///
    /// Header byte = 6.
    BwtEntropy,
    /// BWT reorder + order-1 context-adaptive rANS on the transformed code stream.
    ///
    /// Identical front-end to BwtEntropy (scheme 6): the value-code sequence is
    /// Burrows-Wheeler-transformed, the primary index is stored, and the same
    /// order-1 context model (context = previous code, fallback to the global
    /// order-0 table for contexts below MIN_CTX_COUNT) is used.  The only change
    /// is the entropy back-end: rANS replaces canonical Huffman, removing the
    /// per-symbol integer-bit rounding penalty.  On structured streams where BWT
    /// makes contexts near-deterministic, Huffman pays its 1-bit floor while rANS
    /// reaches the entropy bound to a fraction of a bit (H-19).
    ///
    /// The encoder is competitive (Gotcha #4): it emits min(BwtRans, BwtEntropy,
    /// EntropyContext) per file with the winner's scheme byte, so the scheme can
    /// never regress a file relative to the existing leader.
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [scale_bits    : u8]         — rANS total M = 1 << scale_bits
    ///   [n_contexts    : u16 BE]     — number of context freq tables (incl. fallback)
    ///   for each context entry (wire order = encoder emit order):
    ///     [ctx_id : u16 BE]          — 0 = fallback/order-0
    ///     [n_syms : u16 BE]          — number of nonzero-freq symbols in this ctx
    ///     for each symbol (ascending symbol index):
    ///       [symbol : u8]            — value code in [0, n_distinct)
    ///       [freq   : u16 BE]        — normalized freq; sum over ctx = M
    ///   [rans_len : u32 BE]          — byte length of the rANS payload
    ///   [rans payload : rANS bytes]  — byte-wise rANS, LE state prefix
    ///
    /// Header byte = 7.
    BwtRans,
    /// BWT reorder + order-2 context-adaptive rANS on the transformed code stream (H-20).
    ///
    /// Same BWT front-end as BwtRans (scheme 7); the entropy back-end uses an
    /// order-2 context model (key = (prev2_code, prev_code)) instead of order-1.
    /// Every fallback level the decoder needs is serialized and charged (Gotcha #6):
    /// the encoder emits the smaller of two wire layouts —
    ///   submode A (3-level): fallback order-0 table + order-1 tables + order-2 tables,
    ///   submode B (2-level): fallback order-0 table + order-2 tables (no order-1),
    /// distinguished on the wire by n_ctx1 (0 ⇒ submode B). The fallback chain at
    /// decode is order-2 → order-1 (if present) → order-0.
    ///
    /// Competitive (Gotcha #4): produced only as a winner of the scheme-7 selection
    /// when it is strictly smaller than BwtRans / BwtEntropy / EntropyContext, so it
    /// can never regress a file.
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [scale_bits    : u8]         — rANS total M = 1 << scale_bits
    ///   [fallback(order-0) table]    — [n_syms u16 BE] then (sym u8, freq u16 BE)*
    ///   [n_ctx1 : u16 BE]            — number of order-1 tables (0 ⇒ submode B)
    ///   for each order-1 table: [ctx_id u16 BE] [table]
    ///   [n_ctx2 : u16 BE]            — number of order-2 tables
    ///   for each order-2 table: [prev2 u16 BE] [prev1 u16 BE] [table]
    ///   [rans_len : u32 BE] [rans payload : bytes]
    ///
    /// Header byte = 8.
    Order2Rans,
    /// BWT reorder + ADAPTIVE order-1 range coding on the transformed code stream (H-21).
    ///
    /// Same BWT front-end as BwtRans (scheme 7), but the entropy back-end transmits
    /// NO frequency tables: the decoder rebuilds the exact order-1 model symbol-by-
    /// symbol from the codes it has already decoded. On short, structured BWT'd streams
    /// the champion's per-context tables dominate the value-stream cost; removing them
    /// is the win. A range coder (not rANS) is used because adaptive modelling needs
    /// forward coding + symmetric count rescaling, which rANS's reverse-encode cannot
    /// provide; range coding is informationally equivalent.
    ///
    /// Model: per-context (context = previous code) integer freqs, init 1 each,
    /// increment `inc` per observation (effective Laplace alpha = 1/inc), halved when a
    /// context total exceeds 2^15. The encoder tries a small set of `inc` values and
    /// keeps the smallest payload. Competitive (Gotcha #4): produced only as a winner
    /// of the scheme-7 selection, so it can never regress a file.
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [inc           : u8]         — model increment (effective alpha = 1/inc)
    ///   [rc_len        : u32 BE]     — range-coded payload length
    ///   [rc payload    : bytes]      — carryless (Subbotin) range-coder bytes
    ///
    /// Header byte = 9.
    BwtAdaptive,
    /// BWT reorder + CONTEXT-MIXING of order-1 and order-0 predictions (H-22).
    ///
    /// Same BWT front-end as BwtRans (scheme 7). The entropy back-end transmits NO
    /// frequency tables; the decoder rebuilds the model symbol-by-symbol (like the
    /// adaptive order-1 scheme) but blends two predictions per symbol via a LEARNED
    /// scalar weight that adapts toward whichever model has been predicting better.
    /// Mixing the stabler order-0 estimate into the order-1 estimate reduces the
    /// variance of low-count contexts. A range coder is used (adaptive forward coding,
    /// like H-21). The encoder picks per file, via a one-byte mode, between:
    ///   mode 0 — pure adaptive order-1 (never worse than the adaptive baseline),
    ///   mode 1 — learned-weight linear mix of order-1 and order-0.
    /// Competitive (Gotcha #4): produced only as a winner of the scheme-7 selection.
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [mode          : u8]         — 0 = pure order-1, 1 = learned mix
    ///   [inc           : u8]         — model increment (effective alpha = 1/inc)
    ///   [lr_idx        : u8]         — learning-rate index (mode 1 only)
    ///   [rc_len        : u32 BE]     — range-coded payload length
    ///   [rc payload    : bytes]      — carryless (Subbotin) range-coder bytes
    ///
    /// Header byte = 10.
    BwtContextMix,
    /// BWT reorder + GEOMETRIC (logistic) context-mixing of order-2/1/0 (H-24).
    ///
    /// Same BWT front-end as BwtRans (scheme 7). The entropy back-end transmits NO
    /// frequency tables; the decoder rebuilds three adaptive models (order-2 key
    /// (prev2,prev1), order-1 key prev1, order-0) symbol-by-symbol and blends their
    /// predictions in the LOG domain — p(s) ∝ ∏_k p_k(s)^{w_k}, renormalized over the
    /// alphabet — with three weights learned online by gradient on the per-symbol
    /// log-loss. Geometric mixing sharpens high-confidence predictions (multiply, not
    /// average), beating the scheme-10 linear o1+o0 mix on every structured cube file.
    /// A range coder is used (adaptive forward coding, like H-21/H-22). The encoder
    /// sweeps a small (inc, lr) grid and keeps the smallest payload. Competitive
    /// (Gotcha #4): produced only as a winner of the scheme-7 selection.
    ///
    /// Wire (after header + gap streams):
    ///   [primary_index : u16 BE]     — 2 bytes; BWT primary index (≤ L ≤ 65536)
    ///   [inc           : u8]         — model increment (effective alpha = 1/inc)
    ///   [lr_idx        : u8]         — learning-rate index into GM_LRS
    ///   [rc_len        : u32 BE]     — range-coded payload length
    ///   [rc payload    : bytes]      — carryless range-coder bytes
    ///
    /// Header byte = 11.
    BwtGeoMix,
    /// LZ77 match modeling + rANS — a NON-BWT value-stream class (H-25).
    ///
    /// The value-code stream is tokenized into (literal, match) tokens by greedy
    /// LZ77 (3-code hash chains, full prior window). Every sub-stream is then
    /// entropy-coded: literals through the BWT + order-1 rANS backend (scheme 7),
    /// the token flags through order-1 rANS over {0,1}, and the match length and
    /// distance values through a bit-length BUCKET (order-1 rANS) + raw extra bits.
    /// The distance stream is the dominant cost; bucket+extra reaches ~log2(d)
    /// (the information floor) while rANS models the bucket distribution.
    ///
    /// Captures long-range repeats that the BWT-family schemes leave on the table
    /// (the holdout gap to gzip/zstd). Competitive (Gotcha #4): produced only as a
    /// winner of the scheme-7 selection rail, so it can never regress a file.
    ///
    /// Wire (after header + gap streams):
    ///   [n_tokens u32][n_lits u32][n_matches u32]
    ///   [flags  : order-1 rANS over {0,1}]
    ///   [lits   : BWT + order-1 rANS (scheme-7 body), count = n_lits]
    ///   [lenbkt : order-1 rANS over bit-length buckets, count = n_matches]
    ///   [distbkt: order-1 rANS over bit-length buckets, count = n_matches]
    ///   [extra_len u32][extra bits: per match (token order), len-extra then dist-extra]
    ///
    /// Header byte = 12.
    LzRans,
}

impl GapScheme {
    /// Returns the map_scheme byte written to / read from the header.
    pub fn scheme_byte(&self) -> u8 {
        match self {
            GapScheme::RleU16 => 1,
            GapScheme::PackedNibble => 2,
        }
    }

    /// Construct from header byte. Returns None for unknown values.
    pub fn from_byte(b: u8) -> Option<Self> {
        match b {
            1 => Some(GapScheme::RleU16),
            2 => Some(GapScheme::PackedNibble),
            _ => None,
        }
    }
}

impl ValueScheme {
    /// Returns the value_scheme byte written to / read from the header.
    pub fn scheme_byte(&self) -> u8 {
        match self {
            ValueScheme::BitpackFixed => 1,
            ValueScheme::RleCodes => 2,
            ValueScheme::Entropy => 3,
            ValueScheme::EntropyContext => 4,
            ValueScheme::EntropyContext2 => 5,
            ValueScheme::BwtEntropy => 6,
            ValueScheme::BwtRans => 7,
            ValueScheme::Order2Rans => 8,
            ValueScheme::BwtAdaptive => 9,
            ValueScheme::BwtContextMix => 10,
            ValueScheme::BwtGeoMix => 11,
            ValueScheme::LzRans => 12,
        }
    }

    /// Construct from header byte. Returns None for unknown values.
    pub fn from_byte(b: u8) -> Option<Self> {
        match b {
            1 => Some(ValueScheme::BitpackFixed),
            2 => Some(ValueScheme::RleCodes),
            3 => Some(ValueScheme::Entropy),
            4 => Some(ValueScheme::EntropyContext),
            5 => Some(ValueScheme::EntropyContext2),
            6 => Some(ValueScheme::BwtEntropy),
            7 => Some(ValueScheme::BwtRans),
            8 => Some(ValueScheme::Order2Rans),
            9 => Some(ValueScheme::BwtAdaptive),
            10 => Some(ValueScheme::BwtContextMix),
            11 => Some(ValueScheme::BwtGeoMix),
            12 => Some(ValueScheme::LzRans),
            _ => None,
        }
    }
}

/// Encode configuration for the cube algorithm.
///
/// All fields are Approach-A tunable: they change which path is taken in
/// encode_with_config, but the default values reproduce the v1 byte stream
/// exactly. Decode does not use this struct — it reads header fields.
#[derive(Debug, Clone, PartialEq)]
pub struct EncodeConfig {
    /// Edge bound B (number of distinct values per axis slot).
    /// v1-default: 256 (one byte per coordinate slot).
    pub b: usize,

    /// Raw-store threshold: inputs <= this byte count always use raw-store.
    /// v1-default: HEADER_OVERHEAD_BOUND (320).
    pub raw_store_bound: usize,

    /// Upper limit for cube eligibility: inputs > b*b always raw-store.
    /// v1-default: true (use b*b = 65536 as the limit).
    pub use_square_limit: bool,

    /// Optional N override. When Some(n), the cube is built with exactly n
    /// dimensions. Must satisfy B^n >= L; if not, encode falls back to
    /// raw-store (injectivity guard). When None, N = compute_min_n(L, B).
    /// v1-default: None (minimal N).
    pub n_override: Option<usize>,

    /// Gap encoding scheme for the per-axis distance map streams.
    /// v1-default: GapScheme::RleU16 (byte-identical to v1 output).
    pub gap_scheme: GapScheme,

    /// Value encoding scheme for the value stream.
    /// v1-default: ValueScheme::BitpackFixed (byte-identical to v1 output).
    pub value_scheme: ValueScheme,

    /// Minimum observation count for an order-2 context to get its own Huffman table.
    /// Only used when value_scheme = EntropyContext2. Serialized as u16 BE in the
    /// order-2 value stream header (self-describing — decoder reads this from the blob,
    /// never from EncodeConfig).
    /// None → use the scheme default (128). Range: 1..=65535.
    pub min_ctx_count: Option<u16>,
}

impl EncodeConfig {
    /// Returns the v1-default configuration.
    /// Every field exactly matches the hardcoded constants in the original encode().
    pub fn v1_default() -> Self {
        Self {
            b: B_DEFAULT,
            raw_store_bound: HEADER_OVERHEAD_BOUND,
            use_square_limit: true,
            n_override: None,
            gap_scheme: GapScheme::RleU16,
            value_scheme: ValueScheme::BitpackFixed,
            min_ctx_count: None,
        }
    }

    /// Returns the upper size limit for cube eligibility.
    /// Inputs strictly larger than this always use raw-store.
    pub fn cube_size_limit(&self) -> usize {
        if self.use_square_limit {
            self.b * self.b
        } else {
            usize::MAX
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_v1_default_values() {
        let cfg = EncodeConfig::v1_default();
        assert_eq!(cfg.b, 256);
        assert_eq!(cfg.raw_store_bound, 320);
        assert!(cfg.use_square_limit);
        assert_eq!(cfg.cube_size_limit(), 65536);
        assert_eq!(cfg.n_override, None, "v1-default: n_override must be None");
        assert_eq!(
            cfg.gap_scheme,
            GapScheme::RleU16,
            "v1-default: gap_scheme must be RleU16"
        );
        assert_eq!(
            cfg.value_scheme,
            ValueScheme::BitpackFixed,
            "v1-default: value_scheme must be BitpackFixed"
        );
    }

    #[test]
    fn test_value_scheme_byte_roundtrip() {
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BitpackFixed.scheme_byte()),
            Some(ValueScheme::BitpackFixed)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::RleCodes.scheme_byte()),
            Some(ValueScheme::RleCodes)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::Entropy.scheme_byte()),
            Some(ValueScheme::Entropy)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::EntropyContext.scheme_byte()),
            Some(ValueScheme::EntropyContext)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::EntropyContext2.scheme_byte()),
            Some(ValueScheme::EntropyContext2)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BwtEntropy.scheme_byte()),
            Some(ValueScheme::BwtEntropy)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BwtRans.scheme_byte()),
            Some(ValueScheme::BwtRans)
        );
        assert_eq!(
            ValueScheme::from_byte(0),
            None,
            "0 is not a valid value_scheme byte"
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::Order2Rans.scheme_byte()),
            Some(ValueScheme::Order2Rans)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BwtAdaptive.scheme_byte()),
            Some(ValueScheme::BwtAdaptive)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BwtContextMix.scheme_byte()),
            Some(ValueScheme::BwtContextMix)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::BwtGeoMix.scheme_byte()),
            Some(ValueScheme::BwtGeoMix)
        );
        assert_eq!(
            ValueScheme::from_byte(ValueScheme::LzRans.scheme_byte()),
            Some(ValueScheme::LzRans)
        );
        assert_eq!(
            ValueScheme::from_byte(13),
            None,
            "13 is not a valid value_scheme byte"
        );
        assert_eq!(
            ValueScheme::from_byte(99),
            None,
            "unknown byte returns None"
        );
    }

    #[test]
    fn test_value_scheme_default_is_1() {
        // BitpackFixed = 1 is the v1 byte on the wire; must not change (V-AC-8)
        assert_eq!(ValueScheme::BitpackFixed.scheme_byte(), 1u8);
        assert_eq!(ValueScheme::RleCodes.scheme_byte(), 2u8);
        assert_eq!(ValueScheme::Entropy.scheme_byte(), 3u8);
        assert_eq!(ValueScheme::EntropyContext.scheme_byte(), 4u8);
        assert_eq!(ValueScheme::EntropyContext2.scheme_byte(), 5u8);
        assert_eq!(ValueScheme::BwtEntropy.scheme_byte(), 6u8);
        assert_eq!(ValueScheme::BwtRans.scheme_byte(), 7u8);
    }

    #[test]
    fn test_gap_scheme_byte_roundtrip() {
        assert_eq!(
            GapScheme::from_byte(GapScheme::RleU16.scheme_byte()),
            Some(GapScheme::RleU16)
        );
        assert_eq!(
            GapScheme::from_byte(GapScheme::PackedNibble.scheme_byte()),
            Some(GapScheme::PackedNibble)
        );
        assert_eq!(
            GapScheme::from_byte(0),
            None,
            "0 is not a valid scheme byte"
        );
        assert_eq!(GapScheme::from_byte(99), None, "unknown byte returns None");
    }

    #[test]
    fn test_gap_scheme_default_is_1() {
        // RleU16 = 1 is the v1 byte on the wire; must not change
        assert_eq!(GapScheme::RleU16.scheme_byte(), 1u8);
        assert_eq!(GapScheme::PackedNibble.scheme_byte(), 2u8);
    }

    #[test]
    fn test_encode_equals_encode_with_config_on_fixtures() {
        use crate::codec::{encode, encode_with_config};

        let fixture_inputs: Vec<Vec<u8>> = vec![
            vec![],                        // empty
            vec![0x42],                    // single_byte
            vec![0x58u8; 100],             // all_same_100
            (0u8..=255).collect(),         // all_distinct_256
            b"hello, world!\n\n".to_vec(), // hello_world_test (16 bytes)
            b"the quick brown fox jumps over the lazy dog "
                .iter()
                .copied()
                .cycle()
                .take(1024)
                .collect(), // text_1kb
            (0usize..1024)
                .map(|i| (i as u8).wrapping_mul(71).wrapping_add(13))
                .collect(), // random_1kb
        ];

        for input in &fixture_inputs {
            let default_blob = encode(input);
            let config_blob = encode_with_config(input, &EncodeConfig::v1_default());
            assert_eq!(
                default_blob,
                config_blob,
                "encode(x) != encode_with_config(x, v1_default()) for {} bytes",
                input.len()
            );
        }
    }

    #[test]
    fn test_non_default_config_round_trips() {
        use crate::codec::{decode, encode_with_config};
        // A tuned config (lower raw_store_bound) — byte stream differs from v1 default,
        // but must still round-trip byte-exact.
        let tuned = EncodeConfig {
            b: 256,
            raw_store_bound: 200, // smaller threshold: let more inputs try cube mode
            use_square_limit: true,
            n_override: None,
            gap_scheme: GapScheme::RleU16,
            value_scheme: ValueScheme::BitpackFixed,
            min_ctx_count: None,
        };

        let inputs: Vec<Vec<u8>> = vec![
            vec![0xAAu8; 250], // would be raw at default (250 <= 320), cube-eligible at tuned
            b"the quick brown fox "
                .iter()
                .copied()
                .cycle()
                .take(800)
                .collect(),
        ];
        for input in &inputs {
            let blob = encode_with_config(input, &tuned);
            let recovered = decode(&blob).expect("decode must succeed");
            assert_eq!(
                &recovered,
                input,
                "non-default config round-trip failed for {} bytes",
                input.len()
            );
        }
    }
}
