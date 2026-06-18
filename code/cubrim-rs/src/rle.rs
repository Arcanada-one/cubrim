// R4: Compact run-encoding of the distance map (v1-default: pure RLE).
//
// Each gap stream is encoded as a sequence of (value, run_length) pairs.
// Trivially reversible, zero decode ambiguity.
//
// v1-default: simple RLE with (value: uint16, run_length: uint16) pairs.
// Run-length capped at 65535 to fit uint16.
// Encoding: big-endian (matches prototype struct.Struct(">HH")).
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
}
