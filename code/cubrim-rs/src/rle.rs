// R4: Compact run-encoding of the distance map (v1-default: pure RLE).
//
// Each gap stream is encoded as a sequence of (value, run_length) pairs.
// Trivially reversible, zero decode ambiguity.
//
// v1-default: simple RLE with (value: uint16, run_length: uint16) pairs.
// Run-length capped at 65535 to fit uint16.
// Encoding: big-endian (matches prototype struct.Struct(">HH")).
//
// PackedNibble scheme: each gap encoded as a LEB128-style unsigned varint.
//   - g in [1, 127]:    1 byte  0b0ggggggg
//   - g in [128, 16383]: 2 bytes 0b1ggggggg 0b0ggggggg (little-endian 7-bit groups)
//   - larger: 3+ bytes (same pattern)
// Gaps are always >= 1 (distance-map invariant R3.1). B <= 256 so all gaps fit in 1 byte.
// Decode reads exactly axis_gap_counts[k] varints.
//
// Resolution criterion (OQ-2): a scheme minimising bits-per-populated-point
// on the corpus beats this baseline.

use crate::error::CubrimError;

/// Size of one RLE pair in bytes: (u16 value + u16 run_length) = 4 bytes
pub const PAIR_SIZE: usize = 4;
/// Maximum run length for uint16 storage
pub const MAX_RUN: usize = 65535;

/// R4: Encode a list of gap values as pure RLE.
/// Returns bytes: sequence of (value: u16, run_length: u16) pairs, big-endian.
pub fn rle_encode(gaps: &[usize]) -> Vec<u8> {
    if gaps.is_empty() {
        return vec![];
    }

    let mut result = Vec::new();
    let mut current = gaps[0];
    let mut run = 1usize;

    for &g in &gaps[1..] {
        if g == current && run < MAX_RUN {
            run += 1;
        } else {
            // emit pair
            result.extend_from_slice(&(current as u16).to_be_bytes());
            result.extend_from_slice(&(run as u16).to_be_bytes());
            current = g;
            run = 1;
        }
    }
    // emit final pair
    result.extend_from_slice(&(current as u16).to_be_bytes());
    result.extend_from_slice(&(run as u16).to_be_bytes());

    result
}

/// R4 inverse: Decode RLE-encoded bytes back to gap list.
/// Raises error if data length is not a multiple of PAIR_SIZE.
pub fn rle_decode(data: &[u8]) -> Result<Vec<usize>, CubrimError> {
    if data.is_empty() {
        return Ok(vec![]);
    }

    if !data.len().is_multiple_of(PAIR_SIZE) {
        return Err(CubrimError::Decode(format!(
            "RLE data length {} is not a multiple of PAIR_SIZE={}. \
             Corrupt or truncated stream.",
            data.len(),
            PAIR_SIZE
        )));
    }

    let mut gaps = Vec::new();
    let mut offset = 0;
    while offset < data.len() {
        let value = u16::from_be_bytes([data[offset], data[offset + 1]]) as usize;
        let run = u16::from_be_bytes([data[offset + 2], data[offset + 3]]) as usize;
        offset += PAIR_SIZE;
        for _ in 0..run {
            gaps.push(value);
        }
    }
    Ok(gaps)
}

/// Compute the encoded byte size without allocating the full output.
pub fn rle_size(gaps: &[usize]) -> usize {
    if gaps.is_empty() {
        return 0;
    }
    let mut pairs = 1usize;
    let mut current = gaps[0];
    let mut run = 1usize;
    for &g in &gaps[1..] {
        if g == current && run < MAX_RUN {
            run += 1;
        } else {
            pairs += 1;
            current = g;
            run = 1;
        }
    }
    pairs * PAIR_SIZE
}

// ----- PackedNibble (varint-per-gap) encoding -----

/// Encode a single gap value as a LEB128-style unsigned varint.
/// Each 7-bit group is emitted LSB-first; the high bit of each byte is 1 if more
/// bytes follow, 0 on the last byte.
fn encode_varint(mut v: usize, out: &mut Vec<u8>) {
    loop {
        let byte = (v & 0x7F) as u8;
        v >>= 7;
        if v == 0 {
            out.push(byte); // high bit = 0: last byte
            break;
        } else {
            out.push(byte | 0x80); // high bit = 1: more bytes follow
        }
    }
}

/// Decode one LEB128 varint from `data` starting at `pos`.
/// Returns (value, bytes_consumed) or an error on truncation.
fn decode_varint(data: &[u8], pos: usize) -> Result<(usize, usize), CubrimError> {
    let mut value = 0usize;
    let mut shift = 0usize;
    let mut i = pos;
    loop {
        if i >= data.len() {
            return Err(CubrimError::Decode(format!(
                "PackedNibble varint truncated at offset {i}"
            )));
        }
        let byte = data[i] as usize;
        i += 1;
        value |= (byte & 0x7F) << shift;
        shift += 7;
        if byte & 0x80 == 0 {
            break;
        }
        if shift >= 64 {
            return Err(CubrimError::Decode("PackedNibble varint overflow".to_string()));
        }
    }
    Ok((value, i - pos))
}

/// Encode a list of gap values using the PackedNibble (varint-per-gap) scheme.
/// Produces typically 1 byte per gap when B <= 256 (all gaps fit in [1, 256]).
pub fn packed_nibble_encode(gaps: &[usize]) -> Vec<u8> {
    let mut out = Vec::with_capacity(gaps.len());
    for &g in gaps {
        encode_varint(g, &mut out);
    }
    out
}

/// Decode exactly `n_gaps` varints from `data` starting at `offset`.
/// Returns (decoded_gaps, bytes_consumed).
pub fn packed_nibble_decode(data: &[u8], offset: usize, n_gaps: usize) -> Result<(Vec<usize>, usize), CubrimError> {
    let mut gaps = Vec::with_capacity(n_gaps);
    let mut pos = offset;
    for _ in 0..n_gaps {
        let (val, consumed) = decode_varint(data, pos)?;
        pos += consumed;
        gaps.push(val);
    }
    Ok((gaps, pos - offset))
}

/// Compute encoded byte size for PackedNibble without allocating.
pub fn packed_nibble_size(gaps: &[usize]) -> usize {
    gaps.iter().map(|&g| {
        if g < 0x80 { 1 }
        else if g < 0x4000 { 2 }
        else if g < 0x200000 { 3 }
        else { 4 }
    }).sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rle_encode_decode_round_trip() {
        let gaps = vec![1usize, 1, 1, 3, 4, 1, 1];
        let encoded = rle_encode(&gaps);
        let decoded = rle_decode(&encoded).unwrap();
        assert_eq!(decoded, gaps);
    }

    #[test]
    fn test_rle_encode_empty() {
        assert!(rle_encode(&[]).is_empty());
        assert_eq!(rle_decode(&[]).unwrap(), Vec::<usize>::new());
    }

    #[test]
    fn test_rle_single_value() {
        let gaps = vec![5usize];
        let encoded = rle_encode(&gaps);
        assert_eq!(encoded.len(), PAIR_SIZE);
        // big-endian: value=5 (0x0005), run=1 (0x0001)
        assert_eq!(encoded, vec![0, 5, 0, 1]);
        assert_eq!(rle_decode(&encoded).unwrap(), gaps);
    }

    #[test]
    fn test_rle_big_endian_pairs() {
        // Verify exact byte layout matches prototype's struct.Struct(">HH")
        let gaps = vec![1usize; 3]; // three 1s -> (value=1, run=3) = [0x0001, 0x0003]
        let encoded = rle_encode(&gaps);
        assert_eq!(encoded, vec![0, 1, 0, 3], "big-endian encoding mismatch");
    }

    #[test]
    fn test_rle_decode_rejects_odd_length() {
        // length not multiple of 4
        let result = rle_decode(&[0, 1, 0]);
        assert!(result.is_err());
    }

    #[test]
    fn test_rle_size_matches_encode_len() {
        let test_cases = vec![
            vec![1usize, 1, 1, 2, 3],
            vec![5usize],
            vec![],
            vec![1usize, 2, 3, 4, 5],
        ];
        for gaps in test_cases {
            assert_eq!(rle_size(&gaps), rle_encode(&gaps).len());
        }
    }

    #[test]
    fn test_rle_max_run_splits() {
        // run of MAX_RUN+1 identical values should produce 2 pairs
        let gaps: Vec<usize> = vec![1; MAX_RUN + 1];
        let encoded = rle_encode(&gaps);
        // 2 pairs = 8 bytes
        assert_eq!(encoded.len(), 2 * PAIR_SIZE);
        let decoded = rle_decode(&encoded).unwrap();
        assert_eq!(decoded, gaps);
    }

    #[test]
    fn test_rle_all_distinct() {
        // No runs — each value is its own pair
        let gaps = vec![1usize, 2, 3, 4, 5];
        let encoded = rle_encode(&gaps);
        assert_eq!(encoded.len(), 5 * PAIR_SIZE);
        assert_eq!(rle_decode(&encoded).unwrap(), gaps);
    }

    // ----- PackedNibble tests -----

    #[test]
    fn test_packed_nibble_small_gaps_one_byte_each() {
        // All gaps in [1,127] -> 1 byte each
        let gaps = vec![1usize, 2, 3, 127];
        let enc = packed_nibble_encode(&gaps);
        assert_eq!(enc.len(), 4, "each gap < 128 should be 1 byte");
        assert_eq!(enc[0], 1);
        assert_eq!(enc[1], 2);
        assert_eq!(enc[2], 3);
        assert_eq!(enc[3], 127);
        let (dec, consumed) = packed_nibble_decode(&enc, 0, 4).unwrap();
        assert_eq!(dec, gaps);
        assert_eq!(consumed, 4);
    }

    #[test]
    fn test_packed_nibble_gap_128_is_two_bytes() {
        // 128 = 0b10000000 -> varint: 0x80 0x01
        let gaps = vec![128usize];
        let enc = packed_nibble_encode(&gaps);
        assert_eq!(enc.len(), 2, "gap=128 must encode to 2 bytes");
        assert_eq!(enc[0], 0x80); // low 7 bits of 128 = 0, high bit set (more follows)
        assert_eq!(enc[1], 0x01); // next group = 1
        let (dec, _) = packed_nibble_decode(&enc, 0, 1).unwrap();
        assert_eq!(dec[0], 128);
    }

    #[test]
    fn test_packed_nibble_roundtrip_various() {
        let gaps = vec![1usize, 64, 127, 128, 200, 255, 256];
        let enc = packed_nibble_encode(&gaps);
        let (dec, consumed) = packed_nibble_decode(&enc, 0, gaps.len()).unwrap();
        assert_eq!(dec, gaps);
        assert_eq!(consumed, enc.len());
    }

    #[test]
    fn test_packed_nibble_empty() {
        let enc = packed_nibble_encode(&[]);
        assert!(enc.is_empty());
        let (dec, consumed) = packed_nibble_decode(&enc, 0, 0).unwrap();
        assert!(dec.is_empty());
        assert_eq!(consumed, 0);
    }

    #[test]
    fn test_packed_nibble_size_matches_encode_len() {
        let cases = vec![
            vec![1usize, 2, 3],
            vec![127usize],
            vec![128usize],
            vec![255usize, 256],
            vec![1usize; 50],
        ];
        for gaps in cases {
            assert_eq!(
                packed_nibble_size(&gaps),
                packed_nibble_encode(&gaps).len(),
                "size mismatch for {:?}", gaps
            );
        }
    }

    #[test]
    fn test_packed_nibble_decode_partial_offset() {
        // Decode from a non-zero offset in a larger buffer
        let prefix = vec![0xFFu8; 3];
        let gaps = vec![5usize, 10, 20];
        let enc = packed_nibble_encode(&gaps);
        let mut buf = prefix.clone();
        buf.extend_from_slice(&enc);
        let (dec, consumed) = packed_nibble_decode(&buf, 3, 3).unwrap();
        assert_eq!(dec, gaps);
        assert_eq!(consumed, enc.len());
    }

    #[test]
    fn test_packed_nibble_vs_rle_all_distinct_gaps() {
        // When every gap is a distinct small value (no RLE compressibility),
        // PackedNibble (1 byte per gap < 128) wins over RleU16 (4 bytes per gap).
        // This models an axis where coordinates are all distinct — no runs.
        let gaps: Vec<usize> = (1..=20).collect(); // 20 distinct gaps in [1,20]
        let rle_bytes = rle_encode(&gaps).len();    // 20 * 4 = 80 bytes
        let pn_bytes = packed_nibble_encode(&gaps).len(); // 20 * 1 = 20 bytes
        assert!(
            pn_bytes < rle_bytes,
            "PackedNibble ({pn_bytes}B) must be < RleU16 ({rle_bytes}B) for all-distinct small gaps"
        );
    }
}
