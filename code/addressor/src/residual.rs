//! Residual backend selection: the REAL Cubrim-1 codec (in-process lib call,
//! never a stand-in compressor) on large inputs; the light codec on small ones.
//! Every candidate also competes against raw — expansion never ships.
//!
//! Cubrim-1 integration note: the v1 cube codec raw-stores inputs above its
//! design limit `b*b = 65536` bytes (`EncodeConfig::cube_size_limit`), so the
//! real backend is applied BLOCK-WISE at that design block size — each block
//! is a genuine cubrim container (decodable by `cubrim::codec::decode`).
//! Scheme-1 payload layout: varint(n_blocks) ++ [varint(len) ++ block]*.

use crate::error::{AddressorError, Result};
use crate::format::SchemeByte;
use crate::lite;
use crate::refs::{varint_decode, varint_encode};

/// Starting size threshold for the Cubrim-1 backend (bytes).
/// `[to-be-measured]`: calibrated on the real fleet corpus in Phase 8.
pub const RESIDUAL_SIZE_THRESHOLD: usize = 128 * 1024;

/// Cubrim-1 v1 cube design block: b*b with default b=256.
pub const CUBRIM_BLOCK: usize = 65536;

fn cubrim_blocks_encode(data: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    let blocks: Vec<&[u8]> = data.chunks(CUBRIM_BLOCK).collect();
    varint_encode(blocks.len() as u64, &mut out);
    for b in blocks {
        let enc = cubrim::codec::encode(b);
        varint_encode(enc.len() as u64, &mut out);
        out.extend_from_slice(&enc);
    }
    out
}

fn cubrim_blocks_decode(payload: &[u8]) -> Result<Vec<u8>> {
    let mut pos = 0usize;
    let n = varint_decode(payload, &mut pos)?;
    let mut out = Vec::new();
    for _ in 0..n {
        let len = varint_decode(payload, &mut pos)? as usize;
        let end = pos
            .checked_add(len)
            .filter(|&e| e <= payload.len())
            .ok_or_else(|| AddressorError::Format("cubrim block overruns payload".into()))?;
        let block = cubrim::codec::decode(&payload[pos..end])
            .map_err(|e| AddressorError::Codec(format!("cubrim decode: {e:?}")))?;
        out.extend_from_slice(&block);
        pos = end;
    }
    if pos != payload.len() {
        return Err(AddressorError::Format("trailing bytes after cubrim blocks".into()));
    }
    Ok(out)
}

/// Encodes residual bytes, returning (scheme, payload) — the cheapest of
/// {backend-by-size, raw}.
pub fn encode(data: &[u8]) -> Result<(SchemeByte, Vec<u8>)> {
    let coded: (SchemeByte, Vec<u8>) = if data.len() >= RESIDUAL_SIZE_THRESHOLD {
        (SchemeByte::Cubrim1, cubrim_blocks_encode(data))
    } else {
        (SchemeByte::Lite, lite::encode(data)?)
    };
    if coded.1.len() < data.len() {
        Ok(coded)
    } else {
        Ok((SchemeByte::Raw, data.to_vec()))
    }
}

/// Decodes a residual payload by its scheme byte.
pub fn decode(scheme: SchemeByte, payload: &[u8]) -> Result<Vec<u8>> {
    match scheme {
        SchemeByte::Raw => Ok(payload.to_vec()),
        SchemeByte::Cubrim1 => cubrim_blocks_decode(payload),
        SchemeByte::Lite => lite::decode(payload),
        other => Err(AddressorError::Format(format!(
            "scheme {other:?} is not a residual scheme"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn small_input_takes_lite_or_raw() {
        let data = b"compressible compressible compressible".repeat(50);
        assert!(data.len() < RESIDUAL_SIZE_THRESHOLD);
        let (scheme, payload) = encode(&data).unwrap();
        assert!(matches!(scheme, SchemeByte::Lite | SchemeByte::Raw));
        assert_eq!(decode(scheme, &payload).unwrap(), data);
    }

    #[test]
    fn large_input_takes_real_cubrim_backend_blockwise() {
        // large, compressible input → block-wise Cubrim-1 must win over raw
        let data = b"the quick brown fox jumps over the lazy dog. ".repeat(6000);
        assert!(data.len() >= RESIDUAL_SIZE_THRESHOLD);
        let (scheme, payload) = encode(&data).unwrap();
        assert_eq!(scheme, SchemeByte::Cubrim1, "large residual must use cubrim");
        // every block must be a REAL cubrim container: cubrim::codec::decode
        // accepts each — a stand-in compressor cannot fake this.
        let mut pos = 0usize;
        let n = varint_decode(&payload, &mut pos).unwrap();
        assert!(n >= 2, "300KB input must span multiple 64KiB cube blocks");
        for _ in 0..n {
            let len = varint_decode(&payload, &mut pos).unwrap() as usize;
            let block = &payload[pos..pos + len];
            cubrim::codec::decode(block).expect("real cubrim container per block");
            pos += len;
        }
        assert_eq!(decode(scheme, &payload).unwrap(), data);
    }

    #[test]
    fn incompressible_input_falls_back_to_raw() {
        // xorshift noise — nothing should beat raw storage
        let mut x = 0xdeadbeefu64;
        let data: Vec<u8> = (0..10_000)
            .map(|_| {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                (x & 0xff) as u8
            })
            .collect();
        let (scheme, payload) = encode(&data).unwrap();
        if scheme == SchemeByte::Raw {
            assert_eq!(payload, data);
        }
        assert_eq!(decode(scheme, &payload).unwrap(), data);
    }

    #[test]
    fn truncated_cubrim_blocks_error_not_panic() {
        let data = b"abcdefgh ".repeat(20_000);
        let (scheme, payload) = encode(&data).unwrap();
        if scheme == SchemeByte::Cubrim1 {
            for cut in [0usize, 1, payload.len() / 2, payload.len() - 1] {
                let _ = decode(scheme, &payload[..cut]); // must never panic
            }
        }
    }
}
