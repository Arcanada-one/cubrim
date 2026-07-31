//! Light codec for small residual inputs (AH-18: per-file Cubrim-1 is
//! expensive on small files). The ONLY module besides delta.rs allowed to
//! touch the zstd dependency — enforced by the file-level V-AC-6 gate.

use crate::error::{AddressorError, Result};

const LEVEL: i32 = 3;

pub fn encode(data: &[u8]) -> Result<Vec<u8>> {
    zstd::stream::encode_all(data, LEVEL).map_err(|e| AddressorError::Codec(format!("lite enc: {e}")))
}

pub fn decode(blob: &[u8]) -> Result<Vec<u8>> {
    zstd::stream::decode_all(blob).map_err(|e| AddressorError::Codec(format!("lite dec: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip() {
        let data = b"small file contents, repetitive repetitive repetitive".repeat(20);
        let enc = encode(&data).unwrap();
        assert!(enc.len() < data.len());
        assert_eq!(decode(&enc).unwrap(), data);
    }

    #[test]
    fn garbage_decode_errors() {
        assert!(decode(b"\x00\x01\x02not-a-frame").is_err());
    }
}
