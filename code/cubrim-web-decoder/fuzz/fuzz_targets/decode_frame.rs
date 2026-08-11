//! Fuzz the Web Profile decoder against arbitrary `application/cubrim` bytes.
//!
//! The property under test is the one a browser depends on: for ANY input, the
//! decoder returns a value or an error — it never panics, never reads out of
//! bounds, and never allocates past the caller's limit.
#![no_main]

use cubrim_web_decoder::{decode_with_limits, DecodeLimits, MAGIC, MODE_WEB, VERSION};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // A modest ceiling, so an allocation bug shows up as a failure rather than
    // as the fuzzer being OOM-killed.
    let limits = DecodeLimits {
        max_output_size: 4 << 20,
    };
    let _ = decode_with_limits(data, &limits);

    // Most random inputs die at the magic check, which would leave the actual
    // bitstream logic unexercised. Re-run with a valid-looking header so the
    // fuzzer spends its budget inside the decoder.
    if data.len() > 14 {
        let mut framed = data.to_vec();
        framed[0..4].copy_from_slice(&MAGIC);
        framed[4] = VERSION;
        framed[5] = MODE_WEB;
        let _ = decode_with_limits(&framed, &limits);
    }
});
