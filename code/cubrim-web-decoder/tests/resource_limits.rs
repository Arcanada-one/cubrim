//! Resource-policy regression tests for hostile Web Profile frames.
//!
//! These tests exercise the same reference decoder and stream state machine
//! used by the native FFI and WASM ABIs. A successful round trip alone cannot
//! prove that attacker-controlled declarations are bounded.

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder::{
    decode_with_limits, DecodeLimits, StreamDecoder, MAGIC, MODE_RAW, MODE_WEB, VERSION,
};

fn web_frame(len: usize, block_size: Option<usize>) -> (Vec<u8>, Vec<u8>) {
    let data = b"resource-limit fixture: repeated web text with a stable shape\n"
        .repeat((len / 64).max(1));
    let data = data[..len.min(data.len())].to_vec();
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = block_size;
    let frame = encode_with_config(&data, &config);
    assert_eq!(frame[5], 18, "fixture must exercise MODE_WEB");
    (frame, data)
}

#[test]
fn input_ceiling_is_checked_before_whole_buffer_decode() {
    let (frame, _) = web_frame(32_000, None);
    let limits = DecodeLimits {
        max_input_size: frame.len() - 1,
        ..DecodeLimits::default()
    };

    let err = decode_with_limits(&frame, &limits).expect_err("input ceiling must reject");
    assert!(err.message().contains("input"), "unexpected error: {err:?}");
}

#[test]
fn expansion_ratio_is_checked_before_whole_buffer_decode() {
    let (frame, data) = web_frame(64_000, None);
    assert!(frame.len() < data.len(), "fixture must actually compress");
    let limits = DecodeLimits {
        max_expansion_ratio: 1,
        ..DecodeLimits::default()
    };

    let err = decode_with_limits(&frame, &limits).expect_err("ratio ceiling must reject");
    assert!(
        err.message().contains("expansion ratio"),
        "unexpected error: {err:?}"
    );
}

#[test]
fn aggregate_memory_budget_is_checked_before_output_reservation() {
    let (frame, _) = web_frame(48_000, None);
    let limits = DecodeLimits {
        max_decoder_memory: 1024,
        ..DecodeLimits::default()
    };

    let err = decode_with_limits(&frame, &limits).expect_err("memory budget must reject");
    assert!(
        err.message().contains("decoder memory"),
        "unexpected error: {err:?}"
    );
}

#[test]
fn streaming_input_ceiling_is_checked_before_buffer_growth() {
    let (frame, _) = web_frame(24_000, Some(256));
    let mut stream = StreamDecoder::new(DecodeLimits {
        max_input_size: frame.len() - 1,
        ..DecodeLimits::default()
    });

    let err = stream
        .push(&frame)
        .expect_err("stream input ceiling must reject");
    assert!(err.message().contains("input"), "unexpected error: {err:?}");
}

#[test]
fn streaming_memory_budget_covers_retained_input_and_output() {
    let (frame, data) = web_frame(48_000, Some(256));
    let budget = data.len() + frame.len() + (1 << 20) + 64;
    let mut stream = StreamDecoder::new(DecodeLimits {
        max_decoder_memory: budget,
        ..DecodeLimits::default()
    });

    for chunk in frame.chunks(256) {
        stream.push(chunk).expect("one output allocation must fit");
    }
    assert_eq!(stream.finish().expect("stream finish"), data);
}

#[test]
fn streaming_expansion_ratio_is_checked_at_completion() {
    let (frame, data) = web_frame(32_000, Some(256));
    let mut stream = StreamDecoder::new(DecodeLimits {
        max_expansion_ratio: 1,
        ..DecodeLimits::default()
    });

    stream
        .push(&frame)
        .expect("ratio ceiling is checked only at completion");
    let err = stream
        .finish()
        .expect_err("ratio ceiling must reject at completion");
    assert!(
        err.message().contains("expansion ratio"),
        "unexpected error: {err:?}"
    );

    assert!(data.len() > frame.len(), "fixture must remain compressible");
}

#[test]
fn streaming_expansion_ratio_waits_for_the_complete_body() {
    let mut data = vec![b'a'; 4096];
    for i in 0..32_768u32 {
        let value = i.wrapping_mul(747_796_405).wrapping_add(2_891_336_453);
        data.extend_from_slice(&value.to_le_bytes());
        data.extend_from_slice(&value.to_le_bytes());
    }
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = Some(1024);
    let frame = encode_with_config(&data, &config);
    assert_eq!(frame[5], MODE_WEB, "fixture must exercise MODE_WEB");

    let limits = DecodeLimits {
        max_expansion_ratio: 2,
        ..DecodeLimits::default()
    };
    assert_eq!(
        decode_with_limits(&frame, &limits).expect("whole frame"),
        data
    );

    let mut stream = StreamDecoder::new(limits);
    let mut seen = 0usize;
    let mut max_prefix_ratio = 0usize;
    for chunk in frame.chunks(2048) {
        seen += chunk.len();
        stream
            .push(chunk)
            .expect("a valid final ratio must not fail on a prefix");
        if seen > 14 {
            let ratio = stream.decoded_len() / (seen - 14).max(1);
            max_prefix_ratio = max_prefix_ratio.max(ratio);
        }
    }
    assert!(
        max_prefix_ratio > 2,
        "fixture must have a high-compression prefix"
    );
    assert_eq!(stream.finish().expect("stream finish"), data);
}

#[test]
fn raw_store_stream_is_not_subject_to_compression_ratio() {
    let data: Vec<u8> = (0..50_000u32)
        .flat_map(|i| i.wrapping_mul(2_654_435_761).to_le_bytes())
        .collect();
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = Some(4096);
    let frame = encode_with_config(&data, &config);
    assert_eq!(frame[5], 1, "fixture must exercise MODE_RAW");

    let mut stream = StreamDecoder::new(DecodeLimits {
        max_expansion_ratio: 1,
        ..DecodeLimits::default()
    });
    for chunk in frame.chunks(3000) {
        stream.push(chunk).expect("raw frame must ignore ratio");
    }
    assert_eq!(stream.finish().expect("raw frame must finish"), data);
}

#[test]
fn empty_raw_store_is_consistent_between_whole_and_streaming_decode() {
    let frame = [
        MAGIC[0], MAGIC[1], MAGIC[2], MAGIC[3], VERSION, MODE_RAW, 0, 0, 0, 0, 0, 0, 0,
    ];
    assert_eq!(
        decode_with_limits(&frame, &DecodeLimits::default()).unwrap(),
        []
    );

    let mut stream = StreamDecoder::new(DecodeLimits::default());
    stream.push(&frame).expect("empty raw frame push");
    assert_eq!(stream.finish().expect("empty raw frame finish"), []);
}

#[test]
fn wasm_null_input_poison_clears_previous_fresh_output() {
    let (frame, _) = web_frame(20_000, Some(256));
    cubrim_web_decoder::wasm::cbr_stream_open(0);
    unsafe {
        assert_eq!(
            cubrim_web_decoder::wasm::cbr_stream_push(frame.as_ptr(), frame.len()),
            1
        );
        assert!(cubrim_web_decoder::wasm::cbr_stream_fresh_len() > 0);
        assert_eq!(
            cubrim_web_decoder::wasm::cbr_stream_push(core::ptr::null(), 1),
            0
        );
        assert_eq!(cubrim_web_decoder::wasm::cbr_stream_fresh_len(), 0);
        assert_eq!(
            cubrim_web_decoder::wasm::cbr_stream_push(frame.as_ptr(), frame.len()),
            0
        );
    }
    cubrim_web_decoder::wasm::cbr_stream_close();
}

#[test]
fn wasm_input_allocator_has_the_same_hard_input_ceiling() {
    let too_large = cubrim_web_decoder::wasm::cbr_alloc(DecodeLimits::DEFAULT_MAX_INPUT + 1);
    assert!(
        too_large.is_null(),
        "WASM input allocator must reject oversize buffers"
    );

    let small = cubrim_web_decoder::wasm::cbr_alloc(32);
    assert!(
        !small.is_null(),
        "small WASM input allocation should succeed"
    );
    unsafe { cubrim_web_decoder::wasm::cbr_free(small, 32) };
}
