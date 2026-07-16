//! Core B — version-chain delta via zstd patch-from (`CCtx::ref_prefix` +
//! long-distance matching), for the class where base identity is free:
//! versions, backups, deploy artifacts (AH-15).
//!
//! Wire format (scheme 5 payload): base_hash(32) ++ varint(window_log) ++
//! varint(orig_len) ++ zstd frame. The decoder needs the SAME window log
//! (`DCtx::set_parameter(WindowLogMax)`) — it is recorded in the header.
//!
//! Baseline discipline (D-REQ-08): comparisons run ONLY against the
//! strongest of {zstd --ultra -22, zstd --ultra -22 + trained dict,
//! Cubrim-1} — never zstd -19. That lives in the bench script; this module
//! is the mechanism.

use crate::cas::HASH_LEN;
use crate::error::{AddressorError, Result};
use crate::refs::{varint_decode, varint_encode};

/// Compression level for the delta frame (max, as measured in AH-15).
const DELTA_LEVEL: i32 = 22;
/// Hard cap on the window log — memory ≈ 2^window_log on BOTH ends
/// (multi-GB bases are a DoS surface; PRD Приложение A).
pub const WINDOW_LOG_MAX: u32 = 31;

fn window_log_for(base_len: usize, target_len: usize) -> u32 {
    let need = (base_len + target_len).max(1024);
    let mut log = 10u32;
    while (1usize << log) < need && log < WINDOW_LOG_MAX {
        log += 1;
    }
    log
}

/// Encodes `target` as a delta against `base`.
pub fn encode(base: &[u8], base_hash: &[u8; HASH_LEN], target: &[u8]) -> Result<Vec<u8>> {
    let window_log = window_log_for(base.len(), target.len());
    let mut cctx = zstd::zstd_safe::CCtx::create();
    cctx.set_parameter(zstd::zstd_safe::CParameter::CompressionLevel(DELTA_LEVEL))
        .map_err(|e| AddressorError::Codec(format!("delta level: {e:?}")))?;
    cctx.set_parameter(zstd::zstd_safe::CParameter::EnableLongDistanceMatching(true))
        .map_err(|e| AddressorError::Codec(format!("delta ldm: {e:?}")))?;
    cctx.set_parameter(zstd::zstd_safe::CParameter::WindowLog(window_log))
        .map_err(|e| AddressorError::Codec(format!("delta window: {e:?}")))?;
    cctx.ref_prefix(base)
        .map_err(|e| AddressorError::Codec(format!("delta ref_prefix: {e:?}")))?;
    let mut frame = Vec::with_capacity(zstd::zstd_safe::compress_bound(target.len()));
    cctx.compress2(&mut frame, target)
        .map_err(|e| AddressorError::Codec(format!("delta compress: {e:?}")))?;

    let mut out = Vec::with_capacity(frame.len() + HASH_LEN + 10);
    out.extend_from_slice(base_hash);
    varint_encode(window_log as u64, &mut out);
    varint_encode(target.len() as u64, &mut out);
    out.extend_from_slice(&frame);
    Ok(out)
}

/// Parses a delta payload header; returns (base_hash, window_log, orig_len, frame).
pub fn parse_header(payload: &[u8]) -> Result<([u8; HASH_LEN], u32, u64, &[u8])> {
    if payload.len() < HASH_LEN + 2 {
        return Err(AddressorError::Format("delta payload too short".into()));
    }
    let mut base_hash = [0u8; HASH_LEN];
    base_hash.copy_from_slice(&payload[..HASH_LEN]);
    let mut pos = HASH_LEN;
    let window_log = varint_decode(payload, &mut pos)? as u32;
    if window_log > WINDOW_LOG_MAX {
        return Err(AddressorError::Format(format!(
            "delta window_log {window_log} exceeds cap {WINDOW_LOG_MAX}"
        )));
    }
    let orig_len = varint_decode(payload, &mut pos)?;
    Ok((base_hash, window_log, orig_len, &payload[pos..]))
}

/// Decodes a delta payload against the provided `base` bytes.
pub fn decode(base: &[u8], payload: &[u8]) -> Result<Vec<u8>> {
    let (base_hash, window_log, orig_len, frame) = parse_header(payload)?;
    if blake3::hash(base).as_bytes() != &base_hash {
        return Err(AddressorError::Integrity(
            "delta base does not match recorded base hash".into(),
        ));
    }
    if orig_len > (1u64 << 40) {
        return Err(AddressorError::Format("delta declares absurd size".into()));
    }
    let mut dctx = zstd::zstd_safe::DCtx::create();
    dctx.set_parameter(zstd::zstd_safe::DParameter::WindowLogMax(window_log))
        .map_err(|e| AddressorError::Codec(format!("delta window max: {e:?}")))?;
    dctx.ref_prefix(base)
        .map_err(|e| AddressorError::Codec(format!("delta ref_prefix: {e:?}")))?;
    // STREAMING decompress: the output buffer grows only as bytes are actually
    // produced, so a tiny alloc-bomb frame (small frame, huge declared
    // orig_len) never forces a large up-front reservation, while a legit
    // high-ratio version delta (small frame → large real output) decodes
    // correctly. A frame that genuinely decompresses past the absolute cap is
    // rejected mid-stream.
    const CHUNK: usize = 128 * 1024;
    let mut out: Vec<u8> = Vec::new();
    let mut in_buf = zstd::zstd_safe::InBuffer::around(frame);
    loop {
        let old_len = out.len();
        out.resize(old_len + CHUNK, 0);
        let mut out_buf = zstd::zstd_safe::OutBuffer::around_pos(&mut out, old_len);
        let hint = dctx
            .decompress_stream(&mut out_buf, &mut in_buf)
            .map_err(|e| AddressorError::Codec(format!("delta decompress: {e:?}")))?;
        let produced = out_buf.pos();
        out.truncate(produced);
        if out.len() as u64 > (1u64 << 40) {
            return Err(AddressorError::Format("delta output exceeds cap".into()));
        }
        // hint == 0 ⇒ a frame boundary was reached (whole frame consumed)
        if hint == 0 && in_buf.pos() == frame.len() {
            break;
        }
        if produced == old_len && in_buf.pos() == frame.len() {
            break; // no progress and input exhausted
        }
    }
    if out.len() as u64 != orig_len {
        return Err(AddressorError::Integrity(
            "delta reconstructed length mismatch".into(),
        ));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_and_edit(n: usize) -> (Vec<u8>, Vec<u8>) {
        let words = ["config", "server", "value", "route", "block", "index"];
        let mut x = 0x2545F4914F6CDD1Du64;
        let mut base = Vec::new();
        while base.len() < n {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            base.extend_from_slice(words[(x % 6) as usize].as_bytes());
            base.push(b'\n');
        }
        base.truncate(n);
        // target: small edits — insert, replace, append (a realistic version)
        let mut target = base.clone();
        let insert: Vec<u8> = b"# inserted line\n".to_vec();
        target.splice(n / 3..n / 3, insert);
        let end = n / 2 + 20.min(n / 4);
        for b in &mut target[n / 2..end] {
            *b = b'X';
        }
        target.extend_from_slice(b"appended tail\n");
        (base, target)
    }

    #[test]
    fn patch_from_roundtrip() {
        let (base, target) = base_and_edit(200_000);
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        assert_eq!(decode(&base, &delta).unwrap(), target);
    }

    #[test]
    fn delta_is_far_smaller_than_plain_compression() {
        // mechanism check (the honest 4.2x baseline gate runs in the bench
        // script against the AH-15 pair corpus)
        let (base, target) = base_and_edit(300_000);
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        let plain = zstd::stream::encode_all(target.as_slice(), 19).unwrap();
        assert!(
            delta.len() * 2 < plain.len(),
            "delta {} not clearly smaller than plain {}",
            delta.len(),
            plain.len()
        );
    }

    #[test]
    fn wrong_base_is_integrity_error() {
        let (base, target) = base_and_edit(50_000);
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        let mut wrong = base.clone();
        wrong[0] ^= 1;
        match decode(&wrong, &delta) {
            Err(AddressorError::Integrity(_)) => {}
            other => panic!("expected Integrity, got {other:?}"),
        }
    }

    #[test]
    fn large_base_tiny_diff_roundtrips() {
        // the version-chain target class: a big file with a 1-line change →
        // a tiny delta frame, large output. (Regression: a frame-size-bounded
        // pre-reservation broke exactly this case.)
        let (base, _) = base_and_edit(500_000);
        let mut target = base.clone();
        target.splice(250_000..250_000, b"one changed line\n".iter().copied());
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        assert!(delta.len() < 2000, "tiny diff must produce a tiny delta, got {}", delta.len());
        assert_eq!(decode(&base, &delta).unwrap(), target);
    }

    #[test]
    fn absurd_orig_len_does_not_oom() {
        // a tiny frame declaring a huge orig_len must error/decompress-fail,
        // not pre-reserve terabytes (bounded by frame length)
        let (base, target) = base_and_edit(1000);
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        let (_, wl, _, frame) = parse_header(&delta).unwrap();
        let mut forged = Vec::new();
        forged.extend_from_slice(&bh);
        crate::refs::varint_encode(wl as u64, &mut forged);
        crate::refs::varint_encode(1u64 << 39, &mut forged); // 512 GiB declared
        forged.extend_from_slice(frame);
        // must not OOM; decompress will fail the length check
        assert!(decode(&base, &forged).is_err());
    }

    #[test]
    fn header_caps_window_log() {
        let mut payload = vec![0u8; 32];
        crate::refs::varint_encode(60, &mut payload); // absurd window log
        crate::refs::varint_encode(10, &mut payload);
        assert!(parse_header(&payload).is_err());
    }

    #[test]
    fn truncated_delta_errors_not_panics() {
        let (base, target) = base_and_edit(30_000);
        let bh = *blake3::hash(&base).as_bytes();
        let delta = encode(&base, &bh, &target).unwrap();
        for cut in [0usize, 10, 33, delta.len() / 2, delta.len() - 1] {
            let _ = decode(&base, &delta[..cut]);
        }
    }

    #[test]
    fn apply_property_random_pairs() {
        for seed in 1u64..5 {
            let mut x = seed.wrapping_mul(0x9E3779B97F4A7C15) | 1;
            let mut base = vec![0u8; 40_000];
            for b in &mut base {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                *b = (x & 0xff) as u8;
            }
            let mut target = base.clone();
            let rot = (seed as usize * 977) % target.len();
            target.rotate_left(rot);
            let bh = *blake3::hash(&base).as_bytes();
            let delta = encode(&base, &bh, &target).unwrap();
            assert_eq!(decode(&base, &delta).unwrap(), target);
        }
    }
}
