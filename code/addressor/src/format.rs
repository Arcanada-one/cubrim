//! Container format.
//!
//! Layout: magic "CBA1" ++ scheme_byte ++ scheme-specific payload.
//!
//! Scheme bytes (PRD scheme table):
//!   0 = Raw            payload = original bytes as-is
//!   1 = Cubrim1        payload = real cubrim container
//!   2 = WholeFile      OUTCOME TAG ONLY (whole-file dedup hit) — never
//!                       serialized to a container; not a wire scheme
//!   3 = CdcDedup       payload = entry stream, refs only (no residual)
//!   4 = CdcResidual    payload = entry stream + residual sub-blob
//!   5 = Delta          payload = version-chain delta (Core B)
//!   6 = Lite           payload = light-codec frame (lite.rs)
//!
//! Scheme 3/4 entry stream: varint(chunk_count), then per chunk either
//!   0x01 ++ refcoded(ordinal)          — matched chunk (catalog ref)
//!   0x00 ++ varint(len)                — unmatched chunk of `len` bytes,
//! unmatched chunk bytes are concatenated into the residual stream, which is
//! stored after the entries as: sub_scheme_byte ++ varint(payload_len) ++ payload.

use crate::error::{AddressorError, Result};
use crate::refs::{varint_decode, varint_encode, RefCoder};

pub const MAGIC: &[u8; 4] = b"CBA1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum SchemeByte {
    Raw = 0,
    Cubrim1 = 1,
    WholeFile = 2,
    CdcDedup = 3,
    CdcResidual = 4,
    Delta = 5,
    Lite = 6,
}

impl SchemeByte {
    pub fn from_u8(b: u8) -> Result<Self> {
        Ok(match b {
            0 => SchemeByte::Raw,
            1 => SchemeByte::Cubrim1,
            2 => SchemeByte::WholeFile,
            3 => SchemeByte::CdcDedup,
            4 => SchemeByte::CdcResidual,
            5 => SchemeByte::Delta,
            6 => SchemeByte::Lite,
            other => {
                return Err(AddressorError::Format(format!(
                    "unknown scheme byte {other}"
                )))
            }
        })
    }
}

/// A residual sub-blob: its own scheme byte + payload bytes.
pub type ResidualBlob = (SchemeByte, Vec<u8>);

/// One CDC entry of a scheme-3/4 container.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CdcEntry {
    Matched { ordinal: u64 },
    Unmatched { len: u64 },
}

pub struct Container {
    pub scheme: SchemeByte,
    pub payload: Vec<u8>,
}

impl Container {
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(5 + self.payload.len());
        out.extend_from_slice(MAGIC);
        out.push(self.scheme as u8);
        out.extend_from_slice(&self.payload);
        out
    }

    pub fn from_bytes(data: &[u8]) -> Result<Self> {
        if data.len() < 5 || &data[0..4] != MAGIC {
            return Err(AddressorError::Format("bad container magic".into()));
        }
        Ok(Container {
            scheme: SchemeByte::from_u8(data[4])?,
            payload: data[5..].to_vec(),
        })
    }
}

/// Encodes a scheme-3/4 entry stream (+ optional residual sub-blob).
pub fn encode_cdc_payload(
    entries: &[CdcEntry],
    residual: Option<(SchemeByte, &[u8])>,
) -> Vec<u8> {
    let mut out = Vec::new();
    varint_encode(entries.len() as u64, &mut out);
    let mut coder = RefCoder::new();
    for e in entries {
        match e {
            CdcEntry::Matched { ordinal } => {
                out.push(1);
                coder.encode(*ordinal, &mut out);
            }
            CdcEntry::Unmatched { len } => {
                out.push(0);
                varint_encode(*len, &mut out);
            }
        }
    }
    if let Some((scheme, payload)) = residual {
        out.push(scheme as u8);
        varint_encode(payload.len() as u64, &mut out);
        out.extend_from_slice(payload);
    }
    out
}

/// Decodes a scheme-3/4 payload back into entries + optional residual sub-blob.
pub fn decode_cdc_payload(
    data: &[u8],
    with_residual: bool,
) -> Result<(Vec<CdcEntry>, Option<ResidualBlob>)> {
    let mut pos = 0usize;
    let count = varint_decode(data, &mut pos)?;
    // each entry costs >= 2 payload bytes (flag + >=1 varint byte); a tight
    // bound stops an allocation-amplification claim in the declared count
    if count > (data.len() as u64) / 2 + 1 {
        return Err(AddressorError::Format("entry count exceeds payload".into()));
    }
    let mut entries = Vec::with_capacity(count as usize);
    let mut coder = RefCoder::new();
    for _ in 0..count {
        let Some(&flag) = data.get(pos) else {
            return Err(AddressorError::Format("truncated entry flag".into()));
        };
        pos += 1;
        match flag {
            1 => {
                let ordinal = coder.decode(data, &mut pos)?;
                entries.push(CdcEntry::Matched { ordinal });
            }
            0 => {
                let len = varint_decode(data, &mut pos)?;
                entries.push(CdcEntry::Unmatched { len });
            }
            other => {
                return Err(AddressorError::Format(format!("bad entry flag {other}")));
            }
        }
    }
    let residual = if with_residual {
        let Some(&sb) = data.get(pos) else {
            return Err(AddressorError::Format("missing residual sub-scheme".into()));
        };
        pos += 1;
        let scheme = SchemeByte::from_u8(sb)?;
        let len = varint_decode(data, &mut pos)? as usize;
        let end = pos
            .checked_add(len)
            .ok_or_else(|| AddressorError::Format("residual length overflow".into()))?;
        if end > data.len() {
            return Err(AddressorError::Format("residual length exceeds payload".into()));
        }
        let payload = data[pos..end].to_vec();
        pos = end;
        Some((scheme, payload))
    } else {
        None
    };
    if pos != data.len() {
        return Err(AddressorError::Format("trailing bytes in container".into()));
    }
    Ok((entries, residual))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn container_roundtrip() {
        let c = Container {
            scheme: SchemeByte::Lite,
            payload: vec![1, 2, 3],
        };
        let bytes = c.to_bytes();
        let c2 = Container::from_bytes(&bytes).unwrap();
        assert_eq!(c2.scheme, SchemeByte::Lite);
        assert_eq!(c2.payload, vec![1, 2, 3]);
    }

    #[test]
    fn bad_magic_and_scheme_rejected() {
        assert!(Container::from_bytes(b"XXXX\x00rest").is_err());
        assert!(Container::from_bytes(b"CBA1\x63rest").is_err());
        assert!(Container::from_bytes(b"CB").is_err());
    }

    #[test]
    fn cdc_payload_roundtrip() {
        let entries = vec![
            CdcEntry::Matched { ordinal: 42 },
            CdcEntry::Unmatched { len: 100 },
            CdcEntry::Matched { ordinal: 42 },
            CdcEntry::Matched { ordinal: 7_000_000 },
            CdcEntry::Unmatched { len: 3 },
        ];
        let residual = b"residual-bytes".to_vec();
        let payload = encode_cdc_payload(&entries, Some((SchemeByte::Raw, &residual)));
        let (e2, r2) = decode_cdc_payload(&payload, true).unwrap();
        assert_eq!(e2, entries);
        assert_eq!(r2, Some((SchemeByte::Raw, residual)));
    }

    #[test]
    fn cdc_payload_no_residual() {
        let entries = vec![CdcEntry::Matched { ordinal: 1 }];
        let payload = encode_cdc_payload(&entries, None);
        let (e2, r2) = decode_cdc_payload(&payload, false).unwrap();
        assert_eq!(e2, entries);
        assert!(r2.is_none());
    }

    #[test]
    fn truncated_payload_errors_not_panics() {
        let entries = vec![
            CdcEntry::Matched { ordinal: 500_000 },
            CdcEntry::Unmatched { len: 9 },
        ];
        let full = encode_cdc_payload(&entries, Some((SchemeByte::Lite, b"x")));
        for cut in 0..full.len() {
            let _ = decode_cdc_payload(&full[..cut], true); // must never panic
        }
    }

    #[test]
    fn oversized_declared_residual_rejected() {
        let entries = vec![CdcEntry::Unmatched { len: 1 }];
        let mut payload = encode_cdc_payload(&entries, None);
        payload.push(SchemeByte::Raw as u8);
        varint_encode(1_000_000, &mut payload); // declares 1 MB, provides none
        assert!(decode_cdc_payload(&payload, true).is_err());
    }
}
