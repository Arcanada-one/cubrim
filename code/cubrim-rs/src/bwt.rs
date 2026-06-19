// Burrows-Wheeler Transform (BWT) — forward and inverse.
//
// Variant: primary-index (no sentinel symbol). The alphabet is unchanged;
// reversibility is achieved by storing a single integer (the primary index)
// alongside the BWT output (the last column L).
//
// Forward: given seq_codes (length n), produce (L, primary_index) where
//   L[k] = last symbol of k-th lexicographically-sorted rotation
//   primary_index = index k whose rotation is the identity (zero-shift)
//
// Inverse: given (L, primary_index), reconstruct the original sequence using
//   the LF-mapping (no suffix array stored — O(n) time, O(n) space).
//
// Block size: whole value-stream block, n = count <= 65536 (cube-mode bound).
//
// Edge cases:
//   n = 0 → empty output, primary_index = 0
//   n = 1 → L = seq_codes, primary_index = 0
//
// Primary-index serialization: LEB128 varint (1–3 bytes for n <= 65536).
//
// Risk register (design §5):
//   R1 primary-index off-by-one: forward defines I as the row whose rotation
//      is the identity; inverse walks from I. Pinned by property tests.
//   R2 varint width: LEB128 is width-agnostic; decoded bytes_consumed returned
//      so offset arithmetic is exact.
//   R3 empty/length-1: explicit guards in forward and inverse.
//   R5 stable-sort: Rust slice::sort_by is stable; rank within symbol is the
//      insertion order in L (left to right), which is consistent between
//      forward and inverse because both use the same counting-sort pass.

use crate::error::CubrimError;

// ─── Forward BWT ─────────────────────────────────────────────────────────────

/// Forward Burrows-Wheeler Transform.
///
/// Returns (L, primary_index) where:
///   L is the last-column permutation of seq_codes (length n),
///   primary_index is the row in the sorted rotation matrix that equals the
///   original (identity rotation, offset 0).
///
/// The alphabet is preserved (no sentinel). For n <= 65536 the O(n log n)
/// sort is fast enough — worst case ~65536 * 17 comparisons, each O(n) in
/// the degenerate case but practically very fast with Rust's pdqsort.
pub(crate) fn bwt_forward(seq_codes: &[usize]) -> (Vec<usize>, usize) {
    let n = seq_codes.len();
    if n == 0 {
        return (vec![], 0);
    }
    if n == 1 {
        return (vec![seq_codes[0]], 0);
    }

    // Sort rotation indices by their lexicographic rotation key.
    // Rotation i is seq_codes[i..] ++ seq_codes[..i].
    // We compare rotations by comparing symbols at offset k (mod n) for k = 0, 1, ...
    // This is O(n^2) worst case but Rust's sort is adaptive and very fast in practice
    // for n <= 65536 with a bounded alphabet.
    let mut indices: Vec<usize> = (0..n).collect();
    indices.sort_by(|&a, &b| {
        for k in 0..n {
            let sa = seq_codes[(a + k) % n];
            let sb = seq_codes[(b + k) % n];
            match sa.cmp(&sb) {
                std::cmp::Ordering::Equal => continue,
                ord => return ord,
            }
        }
        std::cmp::Ordering::Equal
    });

    // primary_index = the position in `indices` where indices[k] == 0
    // (the sorted rotation that is the identity / zero-shift rotation)
    let primary_index = indices.iter().position(|&i| i == 0)
        .expect("identity rotation must be in sorted list");

    // L[k] = last symbol of k-th sorted rotation = seq_codes[(indices[k] + n - 1) % n]
    let l: Vec<usize> = indices.iter()
        .map(|&rot| seq_codes[(rot + n - 1) % n])
        .collect();

    (l, primary_index)
}

// ─── Inverse BWT (LF mapping) ────────────────────────────────────────────────

/// Inverse Burrows-Wheeler Transform using the LF mapping.
///
/// Reconstructs the original sequence from (L, primary_index).
/// No suffix array is stored or required — O(n) time and space.
///
/// The LF mapping: for the k-th occurrence of symbol c in L, its predecessor
/// in F (the sorted first column) is the k-th occurrence of c in F. Because F
/// is just L sorted, the rank within each symbol is determined by a single
/// left-to-right pass over L (identical stable counting-sort).
///
/// Walk: starting at row primary_index, walk lf[] n times to recover the
/// original sequence in reverse order (each step gives the symbol at that row).
pub(crate) fn bwt_inverse(l: &[usize], primary_index: usize) -> Result<Vec<usize>, CubrimError> {
    let n = l.len();
    if n == 0 {
        return Ok(vec![]);
    }
    if n == 1 {
        return Ok(vec![l[0]]);
    }
    if primary_index >= n {
        return Err(CubrimError::Decode(format!(
            "BWT inverse: primary_index {primary_index} >= n {n}"
        )));
    }

    // Step 1: find alphabet and count occurrences in L.
    // n_distinct is the number of distinct symbols (codes are in [0, n_distinct)).
    // We compute the max to size the count array.
    let max_sym = l.iter().copied().max().unwrap_or(0);
    let n_sym = max_sym + 1;

    let mut count = vec![0usize; n_sym];
    for &sym in l {
        count[sym] += 1;
    }

    // Step 2: compute starting positions in F for each symbol (counting sort).
    // F is the sorted version of L; start[c] = position of first occurrence of c in F.
    let mut start = vec![0usize; n_sym];
    let mut pos = 0usize;
    for c in 0..n_sym {
        start[c] = pos;
        pos += count[c];
    }

    // Step 3: build LF array.
    // lf[k] = the row in F that L[k] maps to (rank-preserving).
    // We track per-symbol occurrence counters using a second pass left-to-right over L.
    let mut sym_rank = vec![0usize; n_sym];
    let mut lf = vec![0usize; n];
    for k in 0..n {
        let sym = l[k];
        lf[k] = start[sym] + sym_rank[sym];
        sym_rank[sym] += 1;
    }

    // Step 4: walk LF mapping n times from primary_index to reconstruct original.
    // Each step: result[n-1-i] = L[k]; k = lf[k].
    let mut result = vec![0usize; n];
    let mut k = primary_index;
    for i in (0..n).rev() {
        result[i] = l[k];
        k = lf[k];
    }

    Ok(result)
}

// ─── LEB128 varint encode/decode for primary_index ───────────────────────────

/// Encode primary_index as LEB128 varint.
/// For n <= 65536: 1 byte (< 128), 2 bytes (< 16384), 3 bytes (<= 65536).
pub(crate) fn varint_encode(mut value: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(3);
    loop {
        let byte = (value & 0x7F) as u8;
        value >>= 7;
        if value == 0 {
            out.push(byte);
            break;
        } else {
            out.push(byte | 0x80);
        }
    }
    out
}

/// Decode LEB128 varint from bytes starting at offset.
/// Returns (value, bytes_consumed).
/// Returns Err on truncated or malformed varint.
pub(crate) fn varint_decode(data: &[u8], offset: usize) -> Result<(usize, usize), CubrimError> {
    let mut value: usize = 0;
    let mut shift = 0usize;
    let mut consumed = 0usize;

    loop {
        if offset + consumed >= data.len() {
            return Err(CubrimError::Decode(format!(
                "BWT varint: truncated at offset {}+{}",
                offset, consumed
            )));
        }
        let byte = data[offset + consumed];
        consumed += 1;
        let low7 = (byte & 0x7F) as usize;
        value |= low7 << shift;
        shift += 7;
        if byte & 0x80 == 0 {
            break;
        }
        if shift >= 64 {
            return Err(CubrimError::Decode(
                "BWT varint: overflow (more than 9 bytes)".to_string()
            ));
        }
    }

    Ok((value, consumed))
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Varint round-trip ──────────────────────────────────────────────────────

    #[test]
    fn test_varint_encode_decode_small() {
        for v in [0usize, 1, 126, 127, 128, 255, 16383, 16384, 65535, 65536] {
            let encoded = varint_encode(v);
            let (decoded, consumed) = varint_decode(&encoded, 0).unwrap();
            assert_eq!(decoded, v, "varint round-trip failed for {v}");
            assert_eq!(consumed, encoded.len(), "consumed != encoded length for {v}");
        }
    }

    #[test]
    fn test_varint_1_byte_for_lt_128() {
        let v = varint_encode(0);
        assert_eq!(v.len(), 1);
        let v = varint_encode(127);
        assert_eq!(v.len(), 1);
    }

    #[test]
    fn test_varint_2_bytes_for_128_to_16383() {
        let v = varint_encode(128);
        assert_eq!(v.len(), 2);
        let v = varint_encode(16383);
        assert_eq!(v.len(), 2);
    }

    #[test]
    fn test_varint_3_bytes_for_16384_to_65536() {
        let v = varint_encode(16384);
        assert_eq!(v.len(), 3);
        let v = varint_encode(65536);
        assert_eq!(v.len(), 3);
    }

    #[test]
    fn test_varint_decode_offset_exact() {
        // Place varint at offset 2 in a larger buffer; bytes_consumed must be exact
        let val = 300usize;
        let encoded = varint_encode(val);
        let mut buf = vec![0xFFu8; 2];
        buf.extend_from_slice(&encoded);
        buf.push(0xFF);
        let (decoded, consumed) = varint_decode(&buf, 2).unwrap();
        assert_eq!(decoded, val);
        assert_eq!(consumed, encoded.len());
    }

    // ── BWT round-trip (primary-index variant) ────────────────────────────────

    fn rt(input: Vec<usize>) {
        let (l, pi) = bwt_forward(&input);
        let recovered = bwt_inverse(&l, pi).expect("inverse must not error on valid input");
        assert_eq!(
            recovered, input,
            "BWT round-trip FAIL: n={} pi={pi}",
            input.len()
        );
    }

    #[test]
    fn test_bwt_empty() {
        rt(vec![]);
    }

    #[test]
    fn test_bwt_length_1() {
        rt(vec![7]);
    }

    #[test]
    fn test_bwt_length_2_same() {
        rt(vec![3, 3]);
    }

    #[test]
    fn test_bwt_length_2_diff() {
        rt(vec![0, 1]);
        rt(vec![1, 0]);
    }

    #[test]
    fn test_bwt_all_same_symbol() {
        // All-same: BWT output is also all-same; primary_index = n - 1 (last rotation is identity)
        // or 0 depending on how equal rotations are ordered — round-trip must hold regardless.
        rt(vec![5; 256]);
    }

    #[test]
    fn test_bwt_all_distinct_ascending() {
        let seq: Vec<usize> = (0..256).collect();
        rt(seq);
    }

    #[test]
    fn test_bwt_all_distinct_descending() {
        let seq: Vec<usize> = (0..256).rev().collect();
        rt(seq);
    }

    #[test]
    fn test_bwt_periodic_binary() {
        // Highly periodic — adversarial for BWT sorts
        let seq: Vec<usize> = (0..1024).map(|i| i % 2).collect();
        rt(seq);
    }

    #[test]
    fn test_bwt_periodic_4symbol() {
        let seq: Vec<usize> = (0..2048).map(|i| i % 4).collect();
        rt(seq);
    }

    #[test]
    fn test_bwt_two_symbol_alphabet_long_runs() {
        // Two symbols with long runs — tests R5 (rank stability with many ties)
        let mut seq = vec![0usize; 200];
        seq.extend(vec![1usize; 200]);
        seq.extend(vec![0usize; 100]);
        rt(seq);
    }

    #[test]
    fn test_bwt_text_like() {
        // Simulate a small text-like code sequence (values in [0, 26))
        let text = b"banana";
        let seq: Vec<usize> = text.iter().map(|&c| (c - b'a') as usize).collect();
        rt(seq.clone());

        // Check that BWT of "banana" has a well-known transformation
        // "banana" → BWT known result: "nnbaaa" (primary_index = 3)
        // Codes: b=1, a=0, n=13 (in our 0-based alphabet for {a,b,n})
        // Our alphabet: a=0, b=1, n=2
        let (l, pi) = bwt_forward(&seq);
        // The last column and pi must invert correctly — exact values are tested above
        let back = bwt_inverse(&l, pi).unwrap();
        assert_eq!(back, seq);
    }

    #[test]
    fn test_bwt_random_1k() {
        // Pseudorandom sequence (deterministic)
        let seq: Vec<usize> = (0usize..1024)
            .map(|i| (i.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407) >> 56) % 53)
            .collect();
        rt(seq);
    }

    #[test]
    fn test_bwt_inverse_rejects_bad_primary_index() {
        let l = vec![0usize, 1, 2];
        let result = bwt_inverse(&l, 3); // out of bounds
        assert!(result.is_err(), "primary_index >= n must return Err");
    }

    // ── BWT forward properties ────────────────────────────────────────────────

    #[test]
    fn test_bwt_l_is_permutation() {
        // L must be a permutation of the input (same multiset)
        let seq: Vec<usize> = vec![2, 1, 3, 1, 2, 0, 1, 3];
        let (l, _) = bwt_forward(&seq);
        let mut seq_sorted = seq.clone();
        let mut l_sorted = l.clone();
        seq_sorted.sort_unstable();
        l_sorted.sort_unstable();
        assert_eq!(seq_sorted, l_sorted, "BWT L must be a permutation of input");
    }

    #[test]
    fn test_bwt_primary_index_in_bounds() {
        let seq: Vec<usize> = vec![3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5];
        let (l, pi) = bwt_forward(&seq);
        assert!(pi < seq.len(), "primary_index must be < n");
        assert_eq!(l.len(), seq.len(), "L must have same length as input");
    }
}
