//! The streaming decoder must agree with the whole-buffer decoder, byte for
//! byte, no matter how the frame is chopped up — and must make progress before
//! the frame ends when the frame has more than one block.

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder::{decode, DecodeLimits, StreamDecoder};

fn web_config(block_size: Option<usize>) -> EncodeConfig {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = block_size;
    config
}

fn stream_in_chunks(frame: &[u8], chunk: usize) -> Result<Vec<u8>, String> {
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let mut collected = Vec::new();
    for piece in frame.chunks(chunk.max(1)) {
        let fresh = stream.push(piece).map_err(|e| e.0.clone())?;
        collected.extend_from_slice(fresh);
    }
    let whole = stream.finish().map_err(|e| e.0.clone())?;
    // The pieces handed out incrementally must reassemble into the same bytes.
    assert_eq!(collected, whole, "incremental pieces != final output");
    Ok(whole)
}

#[test]
fn streaming_matches_whole_buffer_at_every_chunk_size() {
    let payloads: Vec<Vec<u8>> = vec![
        b"the quick brown fox jumps over the lazy dog ".repeat(150),
        br#"{"k":"v","n":[1,2,3],"pad":"yyyyyyyyyyyyyyyy"}"#.repeat(200),
        vec![b'S'; 20_000],
    ];
    for data in &payloads {
        for block_size in [None, Some(512), Some(4096)] {
            let frame = encode_with_config(data, &web_config(block_size));
            let whole = decode(&frame).expect("whole-buffer decode");
            assert_eq!(&whole, data);
            for chunk in [1usize, 3, 17, 256, 4096, frame.len()] {
                let streamed = stream_in_chunks(&frame, chunk)
                    .unwrap_or_else(|e| panic!("chunk {chunk}, blocks {block_size:?}: {e}"));
                assert_eq!(streamed, whole, "chunk {chunk}, blocks {block_size:?}");
            }
        }
    }
}

#[test]
fn multi_block_frames_deliver_output_before_the_frame_ends() {
    let data = b"progressive rendering fixture ".repeat(400);
    let frame = encode_with_config(&data, &web_config(Some(256)));
    assert_eq!(frame[5], 18, "expected a web frame");

    let mut stream = StreamDecoder::new(DecodeLimits::default());
    // Feed everything except the last 40 bytes.
    let head = &frame[..frame.len() - 40];
    let fresh = stream.push(head).expect("partial push");
    assert!(
        !fresh.is_empty(),
        "a multi-block frame must yield bytes before its final chunk arrives"
    );
    assert!(
        stream.decoded_len() < data.len(),
        "should not be complete yet"
    );
    assert_eq!(stream.declared_len(), Some(data.len()));

    // Finishing early must fail, not hand back a partial buffer as if whole.
    let err = StreamDecoder::new(DecodeLimits::default())
        .finish()
        .expect_err("finish on an empty stream must fail");
    assert!(err.needs_more_input());

    stream.push(&frame[frame.len() - 40..]).expect("tail push");
    assert_eq!(stream.finish().expect("finish"), data);
}

#[test]
fn single_block_frames_yield_nothing_until_their_block_completes() {
    let data = b"single block progress fixture ".repeat(200);
    let frame = encode_with_config(&data, &web_config(None));
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let fresh = stream
        .push(&frame[..frame.len() / 2])
        .expect("half a frame is not an error");
    assert!(
        fresh.is_empty(),
        "half of a one-block frame cannot decode to anything"
    );
    stream.push(&frame[frame.len() / 2..]).expect("rest");
    assert_eq!(stream.finish().unwrap(), data);
}

#[test]
fn streaming_rejects_corruption_and_truncation_distinctly() {
    let data = b"integrity fixture ".repeat(300);
    let frame = encode_with_config(&data, &web_config(Some(512)));

    // Truncation: not an error while streaming, but finish() must refuse.
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    stream.push(&frame[..frame.len() / 3]).expect("partial");
    let err = stream
        .finish()
        .expect_err("truncated frame must not finish");
    assert!(
        err.needs_more_input(),
        "truncation is NeedMoreInput: {err:?}"
    );

    // A flipped checksum is corruption: it survives streaming and dies at finish.
    let mut corrupt = frame.clone();
    corrupt[13] ^= 0xFF;
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let _ = stream.push(&corrupt);
    let err = stream.finish().expect_err("checksum must be verified");
    assert!(!err.needs_more_input(), "checksum failure is Invalid");
    assert!(err.message().contains("checksum"));

    // A bad magic is rejected immediately, on the first push.
    let mut bad = frame.clone();
    bad[0] ^= 0xFF;
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let err = stream.push(&bad).expect_err("bad magic must fail fast");
    assert!(!err.needs_more_input());
}

#[test]
fn streaming_enforces_the_output_ceiling_before_decoding() {
    let data = b"ceiling fixture ".repeat(400);
    let frame = encode_with_config(&data, &web_config(Some(512)));
    let mut stream = StreamDecoder::new(DecodeLimits {
        max_output_size: data.len() - 1,
        ..DecodeLimits::default()
    });
    let err = stream.push(&frame).expect_err("ceiling must be enforced");
    assert!(err.message().contains("exceeds the limit"));
    assert!(!err.needs_more_input());
}

#[test]
fn streaming_handles_raw_store_frames() {
    let mut state = 0xBEEFu32;
    let data: Vec<u8> = (0..25_000)
        .map(|_| {
            state = state.wrapping_mul(1_103_515_245).wrapping_add(12345);
            (state >> 16) as u8
        })
        .collect();
    let frame = encode_with_config(&data, &web_config(None));
    assert_eq!(frame[5], 1, "expected the raw-store fallback");
    for chunk in [1usize, 97, 8192] {
        assert_eq!(
            stream_in_chunks(&frame, chunk).unwrap(),
            data,
            "chunk {chunk}"
        );
    }
}
