//! Ordinal reference coding — adaptive, not bare varint.
//!
//! AH-08's ~2.15 B/ref was measured with adaptive codes over a skewed real
//! reference stream; a plain 7-bit varint over uniform ordinals ≥16384 costs
//! 3 B and fails the acceptance gate arithmetically. Mechanism here:
//! move-to-front recency ranking over the stream of ordinals, then varint of
//! the rank — hot ordinals get 1-byte codes regardless of their absolute
//! ordinal value. First occurrence of an ordinal is escaped with rank 0
//! followed by the varint of the ordinal itself.

use crate::catalog::Ordinal;
use crate::error::{AddressorError, Result};

pub fn varint_encode(mut v: u64, out: &mut Vec<u8>) {
    loop {
        let byte = (v & 0x7f) as u8;
        v >>= 7;
        if v == 0 {
            out.push(byte);
            return;
        }
        out.push(byte | 0x80);
    }
}

pub fn varint_decode(data: &[u8], pos: &mut usize) -> Result<u64> {
    let mut v = 0u64;
    let mut shift = 0u32;
    loop {
        let Some(&byte) = data.get(*pos) else {
            return Err(AddressorError::Format("truncated varint".into()));
        };
        *pos += 1;
        if shift >= 63 && (byte & 0x7f) > 1 {
            return Err(AddressorError::Format("varint overflow".into()));
        }
        v |= ((byte & 0x7f) as u64) << shift;
        if byte & 0x80 == 0 {
            return Ok(v);
        }
        shift += 7;
        if shift > 63 {
            return Err(AddressorError::Format("varint too long".into()));
        }
    }
}

/// Streaming adaptive coder for a sequence of ordinal references.
#[derive(Default)]
pub struct RefCoder {
    /// recency list: index = current rank (0 = most recent)
    mtf: Vec<Ordinal>,
}

impl RefCoder {
    pub fn new() -> Self {
        RefCoder { mtf: Vec::new() }
    }

    /// Encodes one ordinal into `out`.
    /// Known ordinal → varint(rank+1); new ordinal → 0x00 escape + varint(ordinal).
    pub fn encode(&mut self, ord: Ordinal, out: &mut Vec<u8>) {
        if let Some(rank) = self.mtf.iter().position(|&o| o == ord) {
            varint_encode((rank + 1) as u64, out);
            self.mtf.remove(rank);
            self.mtf.insert(0, ord);
        } else {
            out.push(0);
            varint_encode(ord, out);
            self.mtf.insert(0, ord);
        }
    }

    /// Decodes one ordinal from `data` at `pos` (symmetric to `encode`).
    pub fn decode(&mut self, data: &[u8], pos: &mut usize) -> Result<Ordinal> {
        let code = varint_decode(data, pos)?;
        if code == 0 {
            let ord = varint_decode(data, pos)?;
            self.mtf.insert(0, ord);
            Ok(ord)
        } else {
            let rank = (code - 1) as usize;
            if rank >= self.mtf.len() {
                return Err(AddressorError::Format(format!(
                    "ref rank {rank} out of range ({} known)",
                    self.mtf.len()
                )));
            }
            let ord = self.mtf.remove(rank);
            self.mtf.insert(0, ord);
            Ok(ord)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn varint_roundtrip_small_large() {
        for v in [0u64, 1, 127, 128, 16383, 16384, u32::MAX as u64, u64::MAX] {
            let mut buf = Vec::new();
            varint_encode(v, &mut buf);
            let mut pos = 0;
            assert_eq!(varint_decode(&buf, &mut pos).unwrap(), v);
            assert_eq!(pos, buf.len());
        }
    }

    #[test]
    fn varint_truncated_errors() {
        let mut buf = Vec::new();
        varint_encode(u64::MAX, &mut buf);
        buf.pop();
        let mut pos = 0;
        assert!(varint_decode(&buf, &mut pos).is_err());
    }

    #[test]
    fn refcoder_roundtrip() {
        let stream: Vec<Ordinal> = vec![5, 900_000, 5, 5, 900_000, 12, 5, 12, 12, 7_000_000];
        let mut enc = RefCoder::new();
        let mut buf = Vec::new();
        for &o in &stream {
            enc.encode(o, &mut buf);
        }
        let mut dec = RefCoder::new();
        let mut pos = 0;
        let decoded: Vec<Ordinal> = (0..stream.len())
            .map(|_| dec.decode(&buf, &mut pos).unwrap())
            .collect();
        assert_eq!(decoded, stream);
        assert_eq!(pos, buf.len());
    }

    #[test]
    fn hot_ordinals_cost_one_byte_regardless_of_magnitude() {
        // adaptivity property: a repeated large ordinal costs 1 byte after
        // its first occurrence — this is what bare varint cannot do.
        let mut enc = RefCoder::new();
        let mut buf = Vec::new();
        enc.encode(5_000_000, &mut buf); // escape + varint: several bytes
        let after_first = buf.len();
        for _ in 0..10 {
            enc.encode(5_000_000, &mut buf);
        }
        assert_eq!(buf.len() - after_first, 10, "hot ref must cost 1 B");
    }

    #[test]
    fn skewed_stream_mean_under_gate() {
        // Zipf-ish skewed stream over a large ordinal space: the acceptance
        // gate expects mean <= 2.3 B/ref on realistic skew (AH-08 profile).
        let mut enc = RefCoder::new();
        let mut buf = Vec::new();
        let mut n = 0usize;
        let mut x: u64 = 0x9e3779b97f4a7c15;
        for i in 0..50_000u64 {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            // 80% of refs hit a hot set of 64 ordinals, 20% cold long tail
            let ord = if x % 10 < 8 {
                1_000_000 + (x % 64)
            } else {
                (x % 5_000_000) + i
            };
            enc.encode(ord, &mut buf);
            n += 1;
        }
        let mean = buf.len() as f64 / n as f64;
        assert!(mean <= 2.3, "mean ref size {mean:.3} B > 2.3 B gate");
    }

    #[test]
    fn decode_bad_rank_errors() {
        let mut dec = RefCoder::new();
        let mut buf = Vec::new();
        varint_encode(5, &mut buf); // rank 4 with empty mtf
        let mut pos = 0;
        assert!(dec.decode(&buf, &mut pos).is_err());
    }
}
