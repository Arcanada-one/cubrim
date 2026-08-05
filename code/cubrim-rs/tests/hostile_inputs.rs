//! Adversarial decoder coverage.
//!
//! These cases are deliberately separate from the ordinary round-trip suites:
//! they prove that malformed, resource-expensive wire data fails closed rather
//! than relying on a successful encode/decode pair to exercise the guard.

use cubrim::config::{EncodeConfig, ValueScheme};
use cubrim::header::{parse_header, Header, MODE_CUBE};
use cubrim::{decode, decode_with_limits, encode_with_config, CubrimError, DecodeLimits};
use std::panic::{catch_unwind, AssertUnwindSafe};

fn two_value_cube(scheme: ValueScheme) -> Vec<u8> {
    let data: Vec<u8> = (0..400)
        .map(|index| if index % 2 == 0 { 0xAB } else { 0xCD })
        .collect();
    let mut config = EncodeConfig::v1_default();
    config.value_scheme = scheme;
    let blob = encode_with_config(&data, &config);
    let (header, _) = parse_header(&blob).expect("encoder must emit a parseable header");
    assert_eq!(
        header.mode, MODE_CUBE,
        "fixture must exercise the cube decoder"
    );
    assert_eq!(header.value_scheme, scheme.scheme_byte());
    assert_eq!(decode(&blob).expect("valid fixture must decode"), data);
    blob
}

fn value_stream_offset(blob: &[u8], header: &Header, header_end: usize) -> usize {
    // The fixture uses the v1 RleU16 gap stream. Walk exactly the framed pairs
    // so the mutation below cannot accidentally target a gap byte.
    assert_eq!(header.map_scheme, 1, "fixture must use RleU16 gap streams");
    let mut offset = header_end;
    for &gap_count in &header.axis_gap_counts {
        let mut decoded_gaps = 0usize;
        while decoded_gaps < gap_count {
            assert!(offset + 4 <= blob.len(), "fixture gap stream is truncated");
            let run = u16::from_be_bytes([blob[offset + 2], blob[offset + 3]]) as usize;
            assert!(run > 0, "fixture gap stream must not contain a zero run");
            decoded_gaps += run;
            offset += 4;
        }
        assert_eq!(decoded_gaps, gap_count);
    }
    offset
}

fn mutate_t4_code_lengths(mut blob: Vec<u8>) -> Vec<u8> {
    let (header, header_end) = parse_header(&blob).unwrap();
    let value_offset = value_stream_offset(&blob, &header, header_end);
    let n_ctx = u16::from_be_bytes([blob[value_offset], blob[value_offset + 1]]) as usize;
    let mut pos = value_offset + 2;

    for _ in 0..n_ctx {
        let code_len_start = pos + 2; // ctx_id
        let code_lengths = &blob[code_len_start..code_len_start + header.n_distinct];
        let present: Vec<usize> = code_lengths
            .iter()
            .enumerate()
            .filter_map(|(index, &length)| (length > 0).then_some(index))
            .collect();
        if present.len() >= 2 {
            // 40 is beyond the decoder's representable Huffman depth and also
            // violates Kraft's equality with the remaining present symbol.
            blob[code_len_start + present[1]] = 40;
            return blob;
        }
        pos += 2 + header.n_distinct;
    }
    panic!("fixture did not contain a two-symbol T4 context table");
}

fn mutate_t5_code_lengths(mut blob: Vec<u8>) -> Vec<u8> {
    let (header, header_end) = parse_header(&blob).unwrap();
    let value_offset = value_stream_offset(&blob, &header, header_end);
    let n_ctx = u16::from_be_bytes([blob[value_offset + 2], blob[value_offset + 3]]) as usize;
    let mut pos = value_offset + 4; // min_ctx_count + n_contexts

    for _ in 0..n_ctx {
        let tag = blob[pos];
        let key_len = match tag {
            0 => 0,
            1 => 2,
            2 => 4,
            other => panic!("encoder emitted unknown T5 tag {other}"),
        };
        let code_len_start = pos + 1 + key_len;
        let code_lengths = &blob[code_len_start..code_len_start + header.n_distinct];
        let present: Vec<usize> = code_lengths
            .iter()
            .enumerate()
            .filter_map(|(index, &length)| (length > 0).then_some(index))
            .collect();
        if present.len() >= 2 {
            blob[code_len_start + present[1]] = 40;
            return blob;
        }
        pos = code_len_start + header.n_distinct;
    }
    panic!("fixture did not contain a two-symbol T5 context table");
}

fn assert_no_panic_and_error(blob: Vec<u8>, label: &str) {
    let result = catch_unwind(AssertUnwindSafe(|| {
        decode_with_limits(&blob, &DecodeLimits::default())
    }));
    assert!(result.is_ok(), "{label} input must not panic");
    match result.unwrap() {
        Err(CubrimError::Decode(message)) => assert!(
            message.contains("invalid Huffman code lengths"),
            "{label} input returned the wrong decode error: {message}"
        ),
        Ok(output) => panic!(
            "{label} input must fail with a typed decode error, got Ok({} bytes)",
            output.len()
        ),
        Err(other) => panic!("{label} input must fail with a typed decode error, got {other}"),
    }
}

fn assert_resource_limit(result: Result<Vec<u8>, CubrimError>, label: &str) {
    match result {
        Err(CubrimError::ResourceLimit(_)) => {}
        Ok(output) => panic!("{label} returned Ok({} bytes)", output.len()),
        Err(other) => panic!("{label} returned the wrong error: {other}"),
    }
}

#[test]
fn caller_output_budget_is_enforced_before_decode() {
    let blob = two_value_cube(ValueScheme::BitpackFixed);
    let (header, _) = parse_header(&blob).unwrap();
    let limits = DecodeLimits {
        max_output_size: header.l - 1,
        ..DecodeLimits::default()
    };

    assert_resource_limit(decode_with_limits(&blob, &limits), "caller output budget");
}

#[test]
fn caller_memory_budget_is_enforced_before_reconstruction() {
    let blob = two_value_cube(ValueScheme::BitpackFixed);
    let (header, _) = parse_header(&blob).unwrap();
    let estimate = DecodeLimits::estimated_decode_memory(header.l, header.n);
    let limits = DecodeLimits {
        max_decoder_memory: estimate - 1,
        ..DecodeLimits::default()
    };

    assert_resource_limit(decode_with_limits(&blob, &limits), "caller memory budget");
}

#[test]
fn degenerate_radix_is_rejected_by_header_preflight() {
    let mut blob = two_value_cube(ValueScheme::BitpackFixed);
    blob[7..9].copy_from_slice(&0u16.to_be_bytes());

    match decode_with_limits(&blob, &DecodeLimits::default()) {
        Err(CubrimError::Decode(message)) => assert!(message.contains("degenerate radix")),
        Ok(output) => panic!(
            "expected structural decode error, got Ok({} bytes)",
            output.len()
        ),
        Err(other) => panic!("expected structural decode error, got {other}"),
    }
}

#[test]
fn short_cube_count_is_rejected_before_reconstruction() {
    let mut blob = two_value_cube(ValueScheme::BitpackFixed);
    let (header, _) = parse_header(&blob).unwrap();
    assert!(header.l > 0);
    blob[13..17].copy_from_slice(&((header.l - 1) as u32).to_be_bytes());

    match decode_with_limits(&blob, &DecodeLimits::default()) {
        Err(CubrimError::Decode(message)) => {
            assert!(message.contains("must encode every position"))
        }
        Ok(output) => panic!(
            "expected short-count structural error, got Ok({} bytes)",
            output.len()
        ),
        Err(other) => panic!("expected short-count structural error, got {other}"),
    }
}

#[test]
fn malformed_t4_huffman_lengths_do_not_panic() {
    assert_no_panic_and_error(
        mutate_t4_code_lengths(two_value_cube(ValueScheme::EntropyContext)),
        "T4 malformed Huffman",
    );
}

#[test]
fn malformed_t5_huffman_lengths_do_not_panic() {
    assert_no_panic_and_error(
        mutate_t5_code_lengths(two_value_cube(ValueScheme::EntropyContext2)),
        "T5 malformed Huffman",
    );
}
