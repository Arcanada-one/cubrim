//! Ordinal reference coding — adaptive, not bare varint.
//!
//! AH-08's ~2.15 B/ref exploits ORDINAL LOCALITY: a file re-using a donor
//! references a RUN of the donor's chunk ordinals, which were promoted in
//! order and are therefore consecutive integers. So the coder delta-codes
//! each ref against the previous one (zigzag varint of the difference): a
//! consecutive run costs ~1 B/ref regardless of the absolute magnitude,
//! where a bare varint of a large ordinal would cost 3 B. The stream is
//! self-synchronizing; the decoder mirrors it.

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

fn zigzag(d: i64) -> u64 {
    ((d << 1) ^ (d >> 63)) as u64
}
fn unzigzag(z: u64) -> i64 {
    ((z >> 1) as i64) ^ -((z & 1) as i64)
}

/// Streaming delta coder for a sequence of ordinal references.
#[derive(Default)]
pub struct RefCoder {
    prev: Ordinal,
    started: bool,
}

impl RefCoder {
    pub fn new() -> Self {
        RefCoder { prev: 0, started: false }
    }

    /// Encodes one ordinal as a zigzag varint of its delta from the previous.
    pub fn encode(&mut self, ord: Ordinal, out: &mut Vec<u8>) {
        if !self.started {
            varint_encode(ord, out); // first ref: absolute
            self.started = true;
        } else {
            let delta = ord as i64 - self.prev as i64;
            varint_encode(zigzag(delta), out);
        }
        self.prev = ord;
    }

    /// Decodes one ordinal (symmetric to `encode`).
    pub fn decode(&mut self, data: &[u8], pos: &mut usize) -> Result<Ordinal> {
        let ord = if !self.started {
            self.started = true;
            varint_decode(data, pos)?
        } else {
            let z = varint_decode(data, pos)?;
            let d = unzigzag(z);
            let v = self.prev as i64 + d;
            if v < 0 {
                return Err(AddressorError::Format("ref delta underflow".into()));
            }
            v as Ordinal
        };
        self.prev = ord;
        Ok(ord)
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
    fn consecutive_run_costs_one_byte_regardless_of_magnitude() {
        // the AH-08 locality property: a run of consecutive large ordinals
        // (a donor's chunks referenced in order) costs 1 B/ref after the
        // first — bare varint of each would cost 3 B.
        let mut enc = RefCoder::new();
        let mut buf = Vec::new();
        enc.encode(5_000_000, &mut buf); // first: absolute varint
        let after_first = buf.len();
        for k in 1..=10u64 {
            enc.encode(5_000_000 + k, &mut buf); // +1 deltas
        }
        assert_eq!(buf.len() - after_first, 10, "consecutive run must cost 1 B/ref");
    }

    #[test]
    fn run_structured_stream_mean_under_gate() {
        // realistic store ref stream: runs of consecutive donor ordinals
        // interspersed with jumps to new runs. Mean must clear the 2.3 B gate
        // via delta coding of the runs (the AH-08 mechanism).
        let mut enc = RefCoder::new();
        let mut buf = Vec::new();
        let mut n = 0usize;
        let mut x: u64 = 0x9e3779b97f4a7c15;
        let mut cur: u64 = 500_000;
        for _ in 0..50_000u64 {
            x ^= x << 13; x ^= x >> 7; x ^= x << 17;
            if x.is_multiple_of(8) {
                cur = x % 5_000_000; // jump to a new run start
            } else {
                cur += 1; // continue the consecutive run
            }
            enc.encode(cur, &mut buf);
            n += 1;
        }
        let mean = buf.len() as f64 / n as f64;
        assert!(mean <= 2.3, "mean ref size {mean:.3} B > 2.3 B gate");
    }

    #[test]
    fn decode_underflow_errors() {
        // first ref absolute = 10, then a delta that would take it below 0
        let mut buf = Vec::new();
        varint_encode(10, &mut buf);
        varint_encode(zigzag(-20), &mut buf); // 10 + (-20) < 0
        let mut dec = RefCoder::new();
        let mut pos = 0;
        assert_eq!(dec.decode(&buf, &mut pos).unwrap(), 10);
        assert!(dec.decode(&buf, &mut pos).is_err());
    }

    #[test]
    fn zigzag_roundtrip() {
        for d in [-1_000_000i64, -1, 0, 1, 1_000_000] {
            assert_eq!(unzigzag(zigzag(d)), d);
        }
    }
}
