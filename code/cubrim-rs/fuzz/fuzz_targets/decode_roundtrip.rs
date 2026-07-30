//! Fuzz the encode/decode round trip, and the decoder against *mutated* valid
//! streams.
//!
//! `decode_hostile` explores the space of arbitrary bytes, most of which are
//! rejected at the magic check and never reach the entropy stages. This target
//! reaches deeper: it encodes the fuzzer's input, checks the round trip is
//! exact, and then corrupts the resulting stream so the hostile bytes land
//! inside structures the decoder has already committed to parsing.
//!
//! ```text
//! cargo +nightly fuzz run decode_roundtrip -- -rss_limit_mb=2048 -max_total_time=300
//! ```

#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Keep inputs small: the encoder is slow (~0.023 MiB/s), so large bodies
    // would starve the fuzzer of iterations without exploring new structure.
    if data.len() > 4096 {
        return;
    }

    let blob = cubrim::encode(data);

    // Lossless is the whole product claim; a violation here is a correctness
    // bug, not a hardening one.
    match cubrim::decode(&blob) {
        Ok(decoded) => assert_eq!(
            decoded.as_slice(),
            data,
            "round trip must reproduce the input exactly"
        ),
        Err(e) => panic!("a stream produced by encode() must decode: {e}"),
    }

    // Now corrupt the valid stream. Every single-byte substitution keeps the
    // prefix parseable, so the mutated bytes are reached by the deeper decode
    // paths rather than refused at the header.
    if blob.is_empty() {
        return;
    }
    for (offset, byte) in [(3usize, 0xFFu8), (7, 0x00), (11, 0xFF), (17, 0x80)] {
        if offset < blob.len() {
            let mut mutated = blob.clone();
            mutated[offset] ^= byte;
            let _ = cubrim::decode(&mutated);
        }
    }

    // Truncation at a few structural points, which is the class the preregistered
    // hostile ladder calls out.
    for divisor in [2usize, 4, 8] {
        let cut = blob.len() / divisor;
        let _ = cubrim::decode(&blob[..cut]);
    }
});
