// R5: Shift-to-corner dense re-indexing + explicit fixed-width bit-packing.
//
// 'Shift to corner' = map the populated values to a dense local code starting at 0.
// The mapping (inverse_dict) is stored in the header (R6) so the decoder can invert it.
//
// Explicit fixed width W = ceil(log2(n_distinct)) stored in header.
// Context-derived width is FORBIDDEN in v1 (R5 hard rule).
// No-delimiter: values are packed back-to-back at W bits each; width from header only.
// Encoding: MSB-first, big-endian, zero-padded final byte.
//
// Resolution criterion (OQ-4): a scheme minimising bits-per-value beats this baseline.

use crate::error::CubrimError;

/// R5: Build a dense mapping from distinct values to [0, n-1].
/// Returns (value_to_code, inverse_dict) where:
///   - value_to_code: maps original_value -> dense_code
///   - inverse_dict: list where inverse_dict[code] = original_value
pub fn build_value_dict(values: &[usize]) -> (Vec<(usize, usize)>, Vec<usize>) {
    let mut distinct: Vec<usize> = values.to_vec();
    distinct.sort_unstable();
    distinct.dedup();

    let inverse_dict = distinct.clone();
    let value_to_code: Vec<(usize, usize)> = distinct
        .iter()
        .enumerate()
        .map(|(code, &val)| (val, code))
        .collect();

    (value_to_code, inverse_dict)
}

/// R5: Fixed width W = ceil(log2(n_distinct)) bits. Minimum 1 bit.
pub fn compute_width(n_distinct: usize) -> usize {
    if n_distinct <= 1 {
        return 1;
    }
    // ceil(log2(n_distinct))
    let mut w = 0usize;
    let mut n = n_distinct - 1;
    while n > 0 {
        w += 1;
        n >>= 1;
    }
    w
}

/// R5: Encode list of values using shift-to-corner + fixed W-bit packing.
/// No delimiters — decoder uses W from header.
/// Returns packed bytes. Final byte is zero-padded if needed.
/// Encoding: MSB-first, big-endian.
pub fn bitpack_encode(values: &[usize], value_to_code: &[(usize, usize)], w: usize) -> Vec<u8> {
    if values.is_empty() {
        return vec![];
    }

    // Build lookup: value -> code (using the sorted pairs from build_value_dict)
    // value_to_code is sorted by value (original), code is index in that sorted order.
    // We need fast lookup: value -> code.
    // The caller provides this in sorted-by-value order: (value, code) pairs.
    // Use binary search on value.
    let lookup = |v: usize| -> usize {
        let pos = value_to_code.partition_point(|&(val, _)| val < v);
        value_to_code[pos].1
    };

    // Build as a big integer (bits), then convert to bytes
    // MSB-first: first value's bits are the most significant
    let bit_count = values.len() * w;
    let total_bytes = (bit_count + 7) / 8;
    let _padding = total_bytes * 8 - bit_count;

    // Accumulate bits as a big integer
    // Process as u128 chunks or use a byte-array approach for large inputs
    let mut bytes = vec![0u8; total_bytes];
    let mut bit_pos = 0usize; // current bit position from MSB of first byte

    for &v in values {
        let code = lookup(v);
        // Write W bits starting at bit_pos
        for b in (0..w).rev() {
            let bit = (code >> b) & 1;
            let byte_idx = bit_pos / 8;
            let bit_in_byte = 7 - (bit_pos % 8);
            if bit == 1 {
                bytes[byte_idx] |= 1 << bit_in_byte;
            }
            bit_pos += 1;
        }
    }
    // padding bits are already 0 from initialization

    bytes
}

/// R5 inverse: Decode W-bit packed values from bytes.
///
/// Args:
///   data: packed bytes from bitpack_encode
///   w: fixed bit width (from header — NEVER derived from context)
///   count: number of values to decode (from header)
///   inverse_dict: list where inverse_dict[code] = original_value
pub fn bitpack_decode(
    data: &[u8],
    w: usize,
    count: usize,
    inverse_dict: &[usize],
) -> Result<Vec<usize>, CubrimError> {
    if count == 0 {
        return Ok(vec![]);
    }
    if data.is_empty() {
        return Err(CubrimError::Decode(
            "Empty data but count > 0 in bitpack_decode".to_string(),
        ));
    }

    let total_bits = data.len() * 8;
    let needed_bits = count * w;
    if total_bits < needed_bits {
        return Err(CubrimError::Decode(format!(
            "Insufficient data: {} bytes = {} bits, need {} bits for {} values at W={}",
            data.len(),
            total_bits,
            needed_bits,
            count,
            w
        )));
    }

    let mut values = Vec::with_capacity(count);
    let mut bit_pos = 0usize; // current bit position from MSB of first byte

    for _ in 0..count {
        let mut code = 0usize;
        for _ in 0..w {
            let byte_idx = bit_pos / 8;
            let bit_in_byte = 7 - (bit_pos % 8);
            let bit = ((data[byte_idx] >> bit_in_byte) & 1) as usize;
            code = (code << 1) | bit;
            bit_pos += 1;
        }
        if code >= inverse_dict.len() {
            return Err(CubrimError::Decode(format!(
                "Decoded code {} exceeds inverse_dict size {}. Corrupt stream or wrong W.",
                code,
                inverse_dict.len()
            )));
        }
        values.push(inverse_dict[code]);
    }

    Ok(values)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_width_edge_cases() {
        assert_eq!(compute_width(0), 1); // degenerate
        assert_eq!(compute_width(1), 1); // single value -> 1 bit minimum
        assert_eq!(compute_width(2), 1); // 2 values -> 1 bit
        assert_eq!(compute_width(3), 2); // 3 values -> 2 bits
        assert_eq!(compute_width(4), 2); // 4 values -> 2 bits
        assert_eq!(compute_width(5), 3); // 5 values -> 3 bits
        assert_eq!(compute_width(256), 8); // 256 values -> 8 bits
        assert_eq!(compute_width(257), 9); // 257 values -> 9 bits
    }

    #[test]
    fn test_build_value_dict_basic() {
        let values = vec![10usize, 20, 10, 30, 20];
        let (v2c, inv) = build_value_dict(&values);
        // distinct sorted: [10, 20, 30] -> codes [0, 1, 2]
        assert_eq!(inv, vec![10, 20, 30]);
        // check lookup works: 10->0, 20->1, 30->2
        let lookup: std::collections::HashMap<usize, usize> = v2c.into_iter().collect();
        assert_eq!(lookup[&10], 0);
        assert_eq!(lookup[&20], 1);
        assert_eq!(lookup[&30], 2);
    }

    #[test]
    fn test_bitpack_round_trip_basic() {
        let values = vec![10usize, 20, 30, 10, 20];
        let (v2c, inv) = build_value_dict(&values);
        let w = compute_width(inv.len());
        let encoded = bitpack_encode(&values, &v2c, w);
        let decoded = bitpack_decode(&encoded, w, values.len(), &inv).unwrap();
        assert_eq!(decoded, values);
    }

    #[test]
    fn test_bitpack_all_256_bytes() {
        // All 256 distinct byte values -> W = 8 bits
        let values: Vec<usize> = (0..256).collect();
        let (v2c, inv) = build_value_dict(&values);
        let w = compute_width(inv.len());
        assert_eq!(w, 8);
        let encoded = bitpack_encode(&values, &v2c, w);
        let decoded = bitpack_decode(&encoded, w, values.len(), &inv).unwrap();
        assert_eq!(decoded, values);
    }

    #[test]
    fn test_bitpack_single_value() {
        // Single distinct value -> W=1, all codes=0
        let values = vec![42usize, 42, 42];
        let (v2c, inv) = build_value_dict(&values);
        let w = compute_width(inv.len());
        assert_eq!(w, 1);
        let encoded = bitpack_encode(&values, &v2c, w);
        let decoded = bitpack_decode(&encoded, w, values.len(), &inv).unwrap();
        assert_eq!(decoded, values);
    }

    #[test]
    fn test_bitpack_empty() {
        let (v2c, inv) = build_value_dict(&[]);
        assert!(bitpack_encode(&[], &v2c, 1).is_empty());
        assert_eq!(bitpack_decode(&[], 1, 0, &inv).unwrap(), Vec::<usize>::new());
    }

    #[test]
    fn test_bitpack_msb_first_layout() {
        // Verify MSB-first: two 4-bit values [0xA, 0x5] = 10101 0101
        // value_dict: 5->0 (code 0), 10->1 (code 1)
        // W=1 won't work for two distinct values, use W=1 for 2 values: 5->0, 10->1
        // bits for [10, 5] = [1, 0] -> packed into 1 byte: 1000_0000 (MSB-first, zero padded)
        let values = vec![10usize, 5];
        let (v2c, inv) = build_value_dict(&values);
        // distinct sorted: [5, 10] -> codes: 5->0, 10->1
        let w = compute_width(inv.len());
        assert_eq!(w, 1);
        let encoded = bitpack_encode(&values, &v2c, w);
        // 10 -> code 1 -> bit '1', 5 -> code 0 -> bit '0'
        // packed MSB-first: bits = 10, padded to byte: 1000_0000 = 0x80
        assert_eq!(encoded, vec![0x80], "MSB-first layout mismatch: {encoded:?}");
        let decoded = bitpack_decode(&encoded, w, values.len(), &inv).unwrap();
        assert_eq!(decoded, values);
    }

    #[test]
    fn test_bitpack_decode_rejects_empty_data_nonzero_count() {
        let result = bitpack_decode(&[], 8, 1, &[0usize]);
        assert!(result.is_err());
    }
}
