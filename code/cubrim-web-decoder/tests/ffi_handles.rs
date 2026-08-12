//! The handle-based native FFI (CUBR-0079), exercised through the extern "C"
//! surface itself — including the exact failure the wasm ABI would have:
//! two streams interleaved on one thread.

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder::ffi::*;

fn frame(data: &[u8], block_size: Option<usize>) -> Vec<u8> {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = block_size;
    encode_with_config(data, &config)
}

fn sample(seed: u8, len: usize) -> Vec<u8> {
    // Compressible, distinct per seed so cross-contamination cannot pass.
    let mut out = Vec::with_capacity(len);
    while out.len() < len {
        out.extend_from_slice(format!("<row seed=\"{seed}\" n=\"{}\"/>\n", out.len()).as_bytes());
    }
    out.truncate(len);
    out
}

struct Stream(*mut CbmStream);
impl Stream {
    fn new(max: usize) -> Self {
        let h = cbm_stream_new(max);
        assert!(!h.is_null());
        Stream(h)
    }
    fn push(&self, chunk: &[u8]) -> Result<Vec<u8>, String> {
        unsafe {
            if cbm_stream_push(self.0, chunk.as_ptr(), chunk.len()) == 1 {
                let fresh = core::slice::from_raw_parts(
                    cbm_stream_fresh_ptr(self.0),
                    cbm_stream_fresh_len(self.0),
                );
                Ok(fresh.to_vec())
            } else {
                Err(self.error())
            }
        }
    }
    fn finish(&self) -> Result<(), String> {
        unsafe {
            if cbm_stream_finish(self.0) == 1 {
                Ok(())
            } else {
                Err(self.error())
            }
        }
    }
    fn error(&self) -> String {
        unsafe {
            let bytes = core::slice::from_raw_parts(
                cbm_stream_error_ptr(self.0),
                cbm_stream_error_len(self.0),
            );
            String::from_utf8_lossy(bytes).into_owned()
        }
    }
}
impl Drop for Stream {
    fn drop(&mut self) {
        unsafe { cbm_stream_free(self.0) }
    }
}

#[test]
fn abi_version_is_1() {
    assert_eq!(cbm_ffi_abi_version(), 1);
}

#[test]
fn single_stream_byte_exact_across_chunk_sizes() {
    let original = sample(1, 200_000);
    let frame = frame(&original, Some(4096));
    for chunk_size in [1usize, 7, 1024, frame.len()] {
        let s = Stream::new(0);
        let mut decoded = Vec::new();
        for chunk in frame.chunks(chunk_size) {
            decoded.extend_from_slice(&s.push(chunk).expect("push"));
        }
        s.finish().expect("finish");
        assert_eq!(decoded, original, "chunk_size {chunk_size}");
    }
}

#[test]
fn interleaved_streams_do_not_clobber_each_other() {
    // The wasm ABI's thread_local single slot fails exactly this shape; the
    // handle API must not. Three streams, pushes strictly interleaved.
    let originals: Vec<Vec<u8>> = (0..3)
        .map(|i| sample(i as u8, 60_000 + 10_000 * i))
        .collect();
    let frames: Vec<Vec<u8>> = originals.iter().map(|o| frame(o, Some(4096))).collect();
    let streams: Vec<Stream> = (0..3).map(|_| Stream::new(0)).collect();
    let mut outputs: Vec<Vec<u8>> = vec![Vec::new(); 3];

    let mut offsets = [0usize; 3];
    let step = 1500;
    loop {
        let mut progressed = false;
        for i in 0..3 {
            if offsets[i] < frames[i].len() {
                let end = (offsets[i] + step).min(frames[i].len());
                let fresh = streams[i].push(&frames[i][offsets[i]..end]).expect("push");
                outputs[i].extend_from_slice(&fresh);
                offsets[i] = end;
                progressed = true;
            }
        }
        if !progressed {
            break;
        }
    }
    for i in 0..3 {
        streams[i].finish().expect("finish");
        assert_eq!(
            outputs[i], originals[i],
            "stream {i} corrupted by interleaving"
        );
    }
}

#[test]
fn declared_len_appears_after_header() {
    let original = sample(9, 50_000);
    let f = frame(&original, None);
    let s = Stream::new(0);
    unsafe {
        assert_eq!(cbm_stream_declared_len(s.0), u64::MAX, "before any bytes");
    }
    s.push(&f[..3]).expect("push");
    unsafe {
        assert_eq!(cbm_stream_declared_len(s.0), u64::MAX, "header incomplete");
    }
    s.push(&f[3..]).expect("push");
    unsafe {
        assert_eq!(cbm_stream_declared_len(s.0), original.len() as u64);
    }
    s.finish().expect("finish");
}

#[test]
fn corrupt_frame_poisons_the_stream() {
    let original = sample(3, 80_000);
    let mut f = frame(&original, Some(4096));
    let mid = f.len() / 2;
    f[mid] ^= 0xFF;
    let s = Stream::new(0);
    let mut failed = false;
    for chunk in f.chunks(2048) {
        if s.push(chunk).is_err() {
            failed = true;
            break;
        }
    }
    // Structural corruption fails at push; a lucky flip that survives
    // structure must die at the checksum.
    if !failed {
        assert!(s.finish().is_err(), "corrupt frame verified clean");
        return;
    }
    assert!(!s.error().is_empty(), "failure must carry a message");
    // Poisoned: further pushes keep failing rather than resuming.
    assert!(s.push(b"more").is_err());
    assert_eq!(s.error(), s.error(), "message stable");
}

#[test]
fn truncated_frame_fails_at_finish_not_push() {
    let original = sample(4, 40_000);
    let f = frame(&original, None);
    let s = Stream::new(0);
    s.push(&f[..f.len() - 5])
        .expect("truncation is normal between chunks");
    let err = s.finish().expect_err("incomplete frame must not verify");
    assert!(!err.is_empty());
}

#[test]
fn output_cap_is_enforced() {
    let original = sample(5, 120_000);
    let f = frame(&original, None);
    let s = Stream::new(10_000); // cap far below the declared 120000
    let mut result = Ok(Vec::new());
    for chunk in f.chunks(1024) {
        result = s.push(chunk);
        if result.is_err() {
            break;
        }
    }
    assert!(result.is_err(), "a frame above the cap must be refused");
}

#[test]
fn finish_twice_and_push_after_finish_fail_cleanly() {
    let original = sample(6, 30_000);
    let f = frame(&original, None);
    let s = Stream::new(0);
    s.push(&f).expect("push");
    s.finish().expect("finish");
    assert!(s.finish().is_err(), "second finish must fail, not crash");
    assert!(
        s.push(b"x").is_err(),
        "push after finish must fail, not crash"
    );
}

#[test]
fn null_handles_are_inert() {
    unsafe {
        assert_eq!(
            cbm_stream_push(core::ptr::null_mut(), core::ptr::null(), 0),
            0
        );
        assert_eq!(cbm_stream_fresh_len(core::ptr::null()), 0);
        assert!(cbm_stream_fresh_ptr(core::ptr::null()).is_null());
        assert_eq!(cbm_stream_declared_len(core::ptr::null()), u64::MAX);
        assert_eq!(cbm_stream_finish(core::ptr::null_mut()), 0);
        assert_eq!(cbm_stream_error_len(core::ptr::null()), 0);
        cbm_stream_free(core::ptr::null_mut()); // must be a no-op
    }
}

#[test]
fn raw_store_frames_stream_through_the_same_surface() {
    // Already-compressed payloads fall back to MODE_RAW; the embedder decodes
    // both containers through one API (spec §10a).
    let original: Vec<u8> = (0..50_000u32)
        .flat_map(|i| (i * 2654435761).to_le_bytes())
        .collect();
    let f = frame(&original, Some(4096));
    let s = Stream::new(0);
    let mut decoded = Vec::new();
    for chunk in f.chunks(3000) {
        decoded.extend_from_slice(&s.push(chunk).expect("push"));
    }
    s.finish().expect("finish");
    assert_eq!(decoded, original);
}
