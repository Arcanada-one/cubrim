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

use crate::phi::B_DEFAULT;
use crate::codec::HEADER_OVERHEAD_BOUND;

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
        }
    }

    /// Construct from header byte. Returns None for unknown values.
    pub fn from_byte(b: u8) -> Option<Self> {
        match b {
            1 => Some(ValueScheme::BitpackFixed),
            2 => Some(ValueScheme::RleCodes),
            3 => Some(ValueScheme::Entropy),
            4 => Some(ValueScheme::EntropyContext),
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
        assert_eq!(cfg.gap_scheme, GapScheme::RleU16, "v1-default: gap_scheme must be RleU16");
        assert_eq!(cfg.value_scheme, ValueScheme::BitpackFixed, "v1-default: value_scheme must be BitpackFixed");
    }

    #[test]
    fn test_value_scheme_byte_roundtrip() {
        assert_eq!(ValueScheme::from_byte(ValueScheme::BitpackFixed.scheme_byte()), Some(ValueScheme::BitpackFixed));
        assert_eq!(ValueScheme::from_byte(ValueScheme::RleCodes.scheme_byte()), Some(ValueScheme::RleCodes));
        assert_eq!(ValueScheme::from_byte(ValueScheme::Entropy.scheme_byte()), Some(ValueScheme::Entropy));
        assert_eq!(ValueScheme::from_byte(ValueScheme::EntropyContext.scheme_byte()), Some(ValueScheme::EntropyContext));
        assert_eq!(ValueScheme::from_byte(0), None, "0 is not a valid value_scheme byte");
        assert_eq!(ValueScheme::from_byte(99), None, "unknown byte returns None");
    }

    #[test]
    fn test_value_scheme_default_is_1() {
        // BitpackFixed = 1 is the v1 byte on the wire; must not change (V-AC-8)
        assert_eq!(ValueScheme::BitpackFixed.scheme_byte(), 1u8);
        assert_eq!(ValueScheme::RleCodes.scheme_byte(), 2u8);
        assert_eq!(ValueScheme::Entropy.scheme_byte(), 3u8);
        assert_eq!(ValueScheme::EntropyContext.scheme_byte(), 4u8);
    }

    #[test]
    fn test_gap_scheme_byte_roundtrip() {
        assert_eq!(GapScheme::from_byte(GapScheme::RleU16.scheme_byte()), Some(GapScheme::RleU16));
        assert_eq!(GapScheme::from_byte(GapScheme::PackedNibble.scheme_byte()), Some(GapScheme::PackedNibble));
        assert_eq!(GapScheme::from_byte(0), None, "0 is not a valid scheme byte");
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
            vec![],                                       // empty
            vec![0x42],                                   // single_byte
            vec![0x58u8; 100],                            // all_same_100
            (0u8..=255).collect(),                        // all_distinct_256
            b"hello, world!\n\n".to_vec(),                // hello_world_test (16 bytes)
            b"the quick brown fox jumps over the lazy dog "
                .iter().copied().cycle().take(1024).collect(),  // text_1kb
            (0usize..1024).map(|i| (i as u8).wrapping_mul(71).wrapping_add(13)).collect(), // random_1kb
        ];

        for input in &fixture_inputs {
            let default_blob = encode(input);
            let config_blob = encode_with_config(input, &EncodeConfig::v1_default());
            assert_eq!(
                default_blob, config_blob,
                "encode(x) != encode_with_config(x, v1_default()) for {} bytes",
                input.len()
            );
        }
    }

    #[test]
    fn test_non_default_config_round_trips() {
        use crate::codec::{encode_with_config, decode};
        // A tuned config (lower raw_store_bound) — byte stream differs from v1 default,
        // but must still round-trip byte-exact.
        let tuned = EncodeConfig {
            b: 256,
            raw_store_bound: 200,  // smaller threshold: let more inputs try cube mode
            use_square_limit: true,
            n_override: None,
            gap_scheme: GapScheme::RleU16,
            value_scheme: ValueScheme::BitpackFixed,
        };

        let inputs: Vec<Vec<u8>> = vec![
            vec![0xAAu8; 250],     // would be raw at default (250 <= 320), cube-eligible at tuned
            b"the quick brown fox ".iter().copied().cycle().take(800).collect(),
        ];
        for input in &inputs {
            let blob = encode_with_config(input, &tuned);
            let recovered = decode(&blob).expect("decode must succeed");
            assert_eq!(&recovered, input, "non-default config round-trip failed for {} bytes", input.len());
        }
    }
}
