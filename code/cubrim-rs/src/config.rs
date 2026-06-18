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
}

impl EncodeConfig {
    /// Returns the v1-default configuration.
    /// Every field exactly matches the hardcoded constants in the original encode().
    pub fn v1_default() -> Self {
        Self {
            b: B_DEFAULT,
            raw_store_bound: HEADER_OVERHEAD_BOUND,
            use_square_limit: true,
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
