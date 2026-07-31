//! Malformed-container fuzzing: decode paths must return Err, never panic.

use addressor::format::{decode_cdc_payload, Container};
use proptest::prelude::*;

proptest! {
    #![proptest_config(ProptestConfig { cases: 64, ..ProptestConfig::default() })]

    #[test]
    fn container_from_arbitrary_bytes_never_panics(bytes in proptest::collection::vec(any::<u8>(), 0..2048)) {
        let _ = Container::from_bytes(&bytes);
    }

    #[test]
    fn cdc_payload_from_arbitrary_bytes_never_panics(
        bytes in proptest::collection::vec(any::<u8>(), 0..2048),
        with_residual in any::<bool>(),
    ) {
        let _ = decode_cdc_payload(&bytes, with_residual);
    }
}
