// Canonical Huffman coding over the value-code stream.
//
// All functions are pub(crate) — this module is internal only.
// Codec wiring lands in P2; suppress dead-code lint until then.
// No task IDs in source; provenance lives in git log.
#![allow(dead_code)]
//
// Canonical assignment rule (identical in Rust and Python):
//   1. Count frequencies of symbol codes over seq_codes.
//   2. Build a Huffman tree using a min-heap over (freq, insertion_counter, symbol_value).
//      Tie-break: (frequency ASC, insertion_counter ASC, symbol_value ASC for leaves).
//      Internal nodes use their own insertion counter; symbol_value unused for internal.
//   3. Extract code lengths from tree.
//   4. Sort symbols by (length, symbol_value) ASC — classic DEFLATE canonical assignment.
//   5. Assign codewords: increment within a length, left-shift across length boundaries.
//
// Bitstream format: MSB-first, byte-aligned, zero-padded final byte.

use crate::error::CubrimError;
use std::collections::BinaryHeap;
use std::cmp::Reverse;

// ─── Internal tree node ────────────────────────────────────────────────────

#[derive(Debug, Eq, PartialEq)]
struct Node {
    freq: usize,
    insertion: usize,
    /// For leaves: the symbol code (0..n_distinct).
    /// For internal nodes: usize::MAX (sentinel — not a leaf).
    symbol: usize,
    left: Option<Box<Node>>,
    right: Option<Box<Node>>,
}

impl Ord for Node {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        // We wrap in Reverse for BinaryHeap, so this ordering makes a min-heap.
        // Primary: freq ASC, Secondary: insertion ASC, Tertiary: symbol ASC (leaves only).
        (self.freq, self.insertion, self.symbol)
            .cmp(&(other.freq, other.insertion, other.symbol))
    }
}

impl PartialOrd for Node {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

// ─── Public(crate) API ────────────────────────────────────────────────────

/// Compute canonical Huffman code lengths from a sequence of symbol codes.
///
/// `seq_codes`: slice of symbol codes in [0, n_distinct).
/// `n_distinct`: alphabet size. Returns a Vec of length n_distinct where
/// code_lengths[s] is the code length for symbol s (0 means symbol absent).
///
/// Tie-break during tree construction (pinned, identical to Python twin):
///   (frequency, monotonic insertion counter, symbol_value for leaves)
pub(crate) fn canonical_code_lengths(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    if n_distinct == 0 || seq_codes.is_empty() {
        return vec![0u8; n_distinct];
    }

    // Count frequencies
    let mut freq = vec![0usize; n_distinct];
    for &c in seq_codes {
        if c < n_distinct {
            freq[c] += 1;
        }
    }

    // Symbols that actually appear
    let present: Vec<usize> = (0..n_distinct).filter(|&s| freq[s] > 0).collect();

    if present.is_empty() {
        return vec![0u8; n_distinct];
    }

    // Single-symbol alphabet: every code gets length 1 (DEFLATE convention)
    if present.len() == 1 {
        let mut lengths = vec![0u8; n_distinct];
        lengths[present[0]] = 1;
        return lengths;
    }

    // Build min-heap of leaf nodes (Reverse for min-heap via BinaryHeap)
    let mut counter = 0usize;
    let mut heap: BinaryHeap<Reverse<Box<Node>>> = BinaryHeap::new();

    for &s in &present {
        heap.push(Reverse(Box::new(Node {
            freq: freq[s],
            insertion: counter,
            symbol: s,
            left: None,
            right: None,
        })));
        counter += 1;
    }

    // Huffman tree construction
    while heap.len() > 1 {
        let Reverse(left) = heap.pop().unwrap();
        let Reverse(right) = heap.pop().unwrap();
        let combined_freq = left.freq + right.freq;
        // Internal node: symbol = usize::MAX (not a leaf)
        let internal = Box::new(Node {
            freq: combined_freq,
            insertion: counter,
            symbol: usize::MAX,
            left: Some(left),
            right: Some(right),
        });
        counter += 1;
        heap.push(Reverse(internal));
    }

    let Reverse(root) = heap.pop().unwrap();

    // Extract code lengths via DFS
    let mut lengths = vec![0u8; n_distinct];
    assign_lengths(&root, 0, &mut lengths);

    lengths
}

fn assign_lengths(node: &Node, depth: u8, lengths: &mut Vec<u8>) {
    match (&node.left, &node.right) {
        (None, None) => {
            // Leaf node
            if node.symbol < lengths.len() {
                lengths[node.symbol] = depth;
            }
        }
        (Some(left), Some(right)) => {
            assign_lengths(left, depth + 1, lengths);
            assign_lengths(right, depth + 1, lengths);
        }
        _ => {
            // Malformed tree — should not happen in a well-built Huffman tree
        }
    }
}

/// DEFLATE-style canonical codeword assignment from code lengths.
///
/// `code_len`: Vec of length n_distinct. code_len[s]=0 means symbol s is absent.
/// Returns Vec of (codeword: u32, length: u8) indexed by symbol code.
/// For absent symbols (length=0), the returned pair is (0, 0) (unused sentinel).
///
/// Canonical assignment:
///   1. Sort symbols by (length, symbol_value) ASC (shortest first, ties by symbol).
///   2. Assign increasing numeric codeword values, left-shift on length increase.
pub(crate) fn assign_canonical_codes(code_len: &[u8]) -> Vec<(u32, u8)> {
    let n = code_len.len();
    let mut result = vec![(0u32, 0u8); n];

    if n == 0 {
        return result;
    }

    // Symbols sorted by (length, symbol_value) — absent symbols (len=0) excluded
    let mut symbols: Vec<usize> = (0..n).filter(|&s| code_len[s] > 0).collect();
    symbols.sort_by_key(|&s| (code_len[s], s));

    if symbols.is_empty() {
        return result;
    }

    let mut code: u32 = 0;
    let mut prev_len: u8 = 0;

    for &sym in &symbols {
        let len = code_len[sym];
        if prev_len > 0 {
            // Shift left by (len - prev_len) for length increase
            code <<= (len - prev_len) as u32;
        }
        result[sym] = (code, len);
        code += 1;
        prev_len = len;
    }

    result
}

/// Huffman-encode `seq_codes` using the given code lengths.
/// Returns MSB-first, byte-aligned, zero-padded bitstream.
pub(crate) fn huffman_encode(seq_codes: &[usize], code_len: &[u8]) -> Vec<u8> {
    if seq_codes.is_empty() {
        return vec![];
    }

    let codes = assign_canonical_codes(code_len);
    let mut out: Vec<u8> = Vec::new();
    let mut buf: u32 = 0;   // bit accumulator
    let mut bits: u32 = 0;  // bits in buf

    for &sym in seq_codes {
        let (cw, len) = codes[sym];
        let len = len as u32;
        // Pack codeword MSB-first into buf
        buf = (buf << len) | cw;
        bits += len;
        // Flush complete bytes
        while bits >= 8 {
            bits -= 8;
            out.push(((buf >> bits) & 0xFF) as u8);
        }
    }

    // Zero-pad final byte if any bits remain
    if bits > 0 {
        out.push(((buf << (8 - bits)) & 0xFF) as u8);
    }

    out
}

/// Huffman-decode `count` symbols from `blob[offset..]` using `code_len`.
///
/// Returns `(decoded_symbols, bits_consumed_rounded_up_to_byte)`.
/// Fail-closed: returns Err on Kraft violation, no-match pattern, truncation,
/// or count mismatch. Never panics.
pub(crate) fn huffman_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    code_len: &[u8],
) -> Result<(Vec<usize>, usize), CubrimError> {
    if count == 0 {
        return Ok((vec![], 0));
    }

    // Validate Kraft sum before attempting decode
    if !kraft_ok(code_len) {
        return Err(CubrimError::Decode(
            "Huffman decode: Kraft inequality violated (tree not valid)".to_string(),
        ));
    }

    let codes = assign_canonical_codes(code_len);

    // Build reverse lookup: (codeword, length) -> symbol
    // Index by length (max 32), then by codeword value
    let max_len = code_len.iter().copied().max().unwrap_or(0) as usize;

    // For small alphabets, linear scan per bit-position is fine;
    // use a flat (codeword << 5 | length) -> symbol map.
    // Since max length for <=256 symbols is practically <=20, this is bounded.
    let mut decode_table: std::collections::HashMap<(u32, u8), usize> =
        std::collections::HashMap::new();
    for (sym, &(cw, len)) in codes.iter().enumerate() {
        if len > 0 {
            decode_table.insert((cw, len), sym);
        }
    }

    let data = &blob[offset..];
    let mut result = Vec::with_capacity(count);
    let mut bit_pos = 0usize; // current bit position in the bitstream (MSB-first)

    while result.len() < count {
        // Try to match a codeword starting at bit_pos
        let mut matched = false;
        for len in 1..=(max_len as u8) {
            // Read `len` bits from bit_pos
            let end_bit = bit_pos + len as usize;
            let byte_end = end_bit.div_ceil(8);
            if byte_end > data.len() {
                return Err(CubrimError::Decode(format!(
                    "Huffman decode: bitstream truncated at bit {} (need {} bits of length {})",
                    bit_pos, len, len
                )));
            }
            // Extract `len` bits starting at bit_pos (MSB-first)
            let cw = read_bits(data, bit_pos, len as usize);
            if let Some(&sym) = decode_table.get(&(cw, len)) {
                result.push(sym);
                bit_pos += len as usize;
                matched = true;
                break;
            }
        }
        if !matched {
            return Err(CubrimError::Decode(format!(
                "Huffman decode: no matching codeword at bit position {} (corrupt stream)",
                bit_pos
            )));
        }
    }

    if result.len() != count {
        return Err(CubrimError::Decode(format!(
            "Huffman decode: decoded {} symbols, expected {}",
            result.len(),
            count
        )));
    }

    // Round up to the next byte boundary
    let bytes_consumed = bit_pos.div_ceil(8);
    Ok((result, bytes_consumed))
}

/// Compute bit-exact size (in bytes, rounded up) for Huffman encoding `seq_codes`.
pub(crate) fn huffman_bitstream_size(seq_codes: &[usize], code_len: &[u8]) -> usize {
    let total_bits: usize = seq_codes.iter().map(|&s| code_len[s] as usize).sum();
    total_bits.div_ceil(8)
}

/// Validate Kraft inequality: sum(2^(-length)) == 1 for used symbols.
///
/// Returns true iff the code lengths form a complete or single-symbol code.
///
/// Special case: a single present symbol with length=1 is valid (DEFLATE convention).
/// All other cases require the Kraft sum to equal exactly 1 (complete prefix-free code).
pub(crate) fn kraft_ok(code_len: &[u8]) -> bool {
    let present: Vec<u8> = code_len.iter().copied().filter(|&l| l > 0).collect();
    if present.is_empty() {
        return true; // empty alphabet is trivially ok (nothing to decode)
    }
    // Single-symbol exception (DEFLATE convention): one symbol assigned length 1
    // gives Kraft = 1/2, which is incomplete but unambiguous — always decodable.
    if present.len() == 1 {
        return present[0] == 1;
    }
    // Work in fixed-point: multiply by 2^max_len and check sum == 2^max_len
    let max_len = *present.iter().max().unwrap() as u32;
    if max_len > 30 {
        // Pathological depth — treat as invalid (can't represent 2^max_len in u64 safely)
        return false;
    }
    let total_capacity: u64 = 1u64 << max_len;
    let kraft_sum: u64 = present
        .iter()
        .map(|&l| 1u64 << (max_len - l as u32))
        .sum();
    kraft_sum == total_capacity
}

/// Read `len` bits from `data` starting at bit offset `start` (MSB-first).
fn read_bits(data: &[u8], start: usize, len: usize) -> u32 {
    let mut val: u32 = 0;
    for i in 0..len {
        let bit_idx = start + i;
        let byte_idx = bit_idx / 8;
        let bit_shift = 7 - (bit_idx % 8); // MSB-first
        let bit = (data[byte_idx] >> bit_shift) & 1;
        val = (val << 1) | bit as u32;
    }
    val
}

// ─── Unit Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Round-trip tests ────────────────────────────────────────────────

    #[test]
    fn huffman_round_trip_skewed_alphabet() {
        // 3 symbols: 0 appears 100x, 1 appears 10x, 2 appears 1x
        let seq_codes: Vec<usize> = {
            let mut v = vec![0usize; 100];
            v.extend(vec![1usize; 10]);
            v.extend(vec![2usize; 1]);
            v
        };
        let n_distinct = 3;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        let encoded = huffman_encode(&seq_codes, &lengths);
        let (decoded, _) = huffman_decode(&encoded, 0, seq_codes.len(), &lengths).unwrap();
        assert_eq!(decoded, seq_codes, "skewed alphabet round-trip failed");
    }

    #[test]
    fn huffman_round_trip_uniform_alphabet() {
        // All 8 symbols equally likely (32 occurrences each)
        let seq_codes: Vec<usize> = (0..8).flat_map(|s| std::iter::repeat(s).take(32)).collect();
        let n_distinct = 8;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        assert!(lengths.iter().all(|&l| l == 3), "uniform 8-symbol alphabet must have uniform lengths of 3");
        let encoded = huffman_encode(&seq_codes, &lengths);
        let (decoded, _) = huffman_decode(&encoded, 0, seq_codes.len(), &lengths).unwrap();
        assert_eq!(decoded, seq_codes, "uniform alphabet round-trip failed");
    }

    #[test]
    fn huffman_round_trip_long_run_single_value() {
        // A single repeated code — valid; length=1
        let seq_codes = vec![0usize; 256];
        let n_distinct = 1;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        assert_eq!(lengths[0], 1, "single-symbol must get length 1");
        let encoded = huffman_encode(&seq_codes, &lengths);
        let (decoded, _) = huffman_decode(&encoded, 0, seq_codes.len(), &lengths).unwrap();
        assert_eq!(decoded, seq_codes, "single-symbol round-trip failed");
    }

    #[test]
    fn huffman_round_trip_two_symbols() {
        let seq_codes: Vec<usize> = vec![0, 1, 0, 1, 1, 0, 0, 1];
        let n_distinct = 2;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        assert!(lengths.iter().all(|&l| l == 1), "two equal-freq symbols must have length 1 each");
        let encoded = huffman_encode(&seq_codes, &lengths);
        let (decoded, _) = huffman_decode(&encoded, 0, seq_codes.len(), &lengths).unwrap();
        assert_eq!(decoded, seq_codes, "two-symbol round-trip failed");
    }

    #[test]
    fn huffman_round_trip_full_256_alphabet() {
        // All 256 symbols, each appearing once
        let seq_codes: Vec<usize> = (0..256).collect();
        let n_distinct = 256;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        assert_eq!(lengths.len(), 256);
        let encoded = huffman_encode(&seq_codes, &lengths);
        let (decoded, _) = huffman_decode(&encoded, 0, seq_codes.len(), &lengths).unwrap();
        assert_eq!(decoded, seq_codes, "256-alphabet round-trip failed");
    }

    #[test]
    fn huffman_round_trip_empty_seq_codes() {
        let seq_codes: Vec<usize> = vec![];
        let n_distinct = 4;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        assert!(lengths.iter().all(|&l| l == 0), "empty seq_codes must produce all-zero lengths");
        let encoded = huffman_encode(&seq_codes, &lengths);
        assert!(encoded.is_empty(), "empty seq_codes must produce empty bitstream");
        let (decoded, _) = huffman_decode(&encoded, 0, 0, &lengths).unwrap();
        assert!(decoded.is_empty(), "empty decode must succeed with empty output");
    }

    // ── Length determinism under input permutation ─────────────────────

    #[test]
    fn huffman_length_determinism_under_permutation() {
        // Two symbols with the same frequency — lengths must be identical
        // regardless of which appears first in seq_codes.
        let n_distinct = 2;
        let seq_a: Vec<usize> = vec![0, 0, 0, 1, 1, 1]; // 0 first
        let seq_b: Vec<usize> = vec![1, 1, 1, 0, 0, 0]; // 1 first
        let lengths_a = canonical_code_lengths(&seq_a, n_distinct);
        let lengths_b = canonical_code_lengths(&seq_b, n_distinct);
        assert_eq!(lengths_a, lengths_b, "lengths must be identical under permutation of equal-freq input");
    }

    #[test]
    fn huffman_length_determinism_three_equal_freq() {
        // Three symbols each appearing 10 times
        let n_distinct = 3;
        let seq_a: Vec<usize> = (0..3).flat_map(|s| std::iter::repeat(s).take(10)).collect();
        let seq_b: Vec<usize> = vec![2usize, 1, 0].into_iter()
            .flat_map(|s| std::iter::repeat(s).take(10)).collect();
        let lengths_a = canonical_code_lengths(&seq_a, n_distinct);
        let lengths_b = canonical_code_lengths(&seq_b, n_distinct);
        assert_eq!(lengths_a, lengths_b, "three equal-freq symbols: lengths must be deterministic");
    }

    // ── Kraft validation ────────────────────────────────────────────────

    #[test]
    fn kraft_ok_valid_two_symbols() {
        // Lengths [1, 1] → Kraft = 1/2 + 1/2 = 1 ✓
        assert!(kraft_ok(&[1, 1]));
    }

    #[test]
    fn kraft_ok_valid_uniform_8() {
        // All length 3 for 8 symbols → Kraft = 8 × 1/8 = 1 ✓
        assert!(kraft_ok(&[3, 3, 3, 3, 3, 3, 3, 3]));
    }

    #[test]
    fn kraft_fail_over_full() {
        // Lengths [1, 1, 1] → Kraft = 3/2 > 1 ✗ (over-full)
        assert!(!kraft_ok(&[1, 1, 1]));
    }

    #[test]
    fn kraft_fail_incomplete() {
        // Lengths [2, 2] → Kraft = 1/4 + 1/4 = 1/2 < 1 ✗ (incomplete)
        assert!(!kraft_ok(&[2, 2]));
    }

    #[test]
    fn kraft_ok_all_zeros_empty_alphabet() {
        // All zeros = no symbols → trivially valid
        assert!(kraft_ok(&[0, 0, 0]));
    }

    #[test]
    fn kraft_ok_actual_huffman_output() {
        // Lengths produced by canonical_code_lengths must always satisfy Kraft
        let seq_codes: Vec<usize> = {
            let mut v = vec![0usize; 50];
            v.extend(vec![1usize; 30]);
            v.extend(vec![2usize; 15]);
            v.extend(vec![3usize; 5]);
            v
        };
        let lengths = canonical_code_lengths(&seq_codes, 4);
        assert!(kraft_ok(&lengths), "Huffman-generated lengths must satisfy Kraft");
    }

    // ── Bitstream size assertion ────────────────────────────────────────

    #[test]
    fn huffman_bitstream_size_matches_encode_len() {
        let seq_codes: Vec<usize> = {
            let mut v = vec![0usize; 100];
            v.extend(vec![1usize; 50]);
            v.extend(vec![2usize; 25]);
            v
        };
        let n_distinct = 3;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        let encoded = huffman_encode(&seq_codes, &lengths);
        assert_eq!(
            huffman_bitstream_size(&seq_codes, &lengths),
            encoded.len(),
            "huffman_bitstream_size must match actual encoded byte count"
        );
    }

    #[test]
    fn huffman_bitstream_size_single_symbol() {
        // Single-symbol alphabet: length=1, N codes → ceil(N/8) bytes
        let seq_codes = vec![0usize; 64];
        let lengths = canonical_code_lengths(&seq_codes, 1);
        let encoded = huffman_encode(&seq_codes, &lengths);
        assert_eq!(huffman_bitstream_size(&seq_codes, &lengths), encoded.len());
        assert_eq!(encoded.len(), 8, "64 bits / 8 = 8 bytes");
    }

    // ── MSB-first packing assertion ─────────────────────────────────────

    #[test]
    fn huffman_msb_first_two_symbols() {
        // Symbols 0→'0' and 1→'1' with codes [0:1bit=0, 1:1bit=1] respectively
        // Sequence [0,1,0,1,0,1,0,1] → bits 0,1,0,1,0,1,0,1 → byte 0x55
        let n_distinct = 2;
        let seq_codes = vec![0usize, 1, 0, 1, 0, 1, 0, 1];
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        // Both symbols appear 4 times → equal frequency → lengths both 1
        // canonical: sym 0 gets codeword 0, sym 1 gets codeword 1 (sorted by symbol value)
        assert_eq!(lengths[0], 1, "sym 0 must have length 1");
        assert_eq!(lengths[1], 1, "sym 1 must have length 1");
        let encoded = huffman_encode(&seq_codes, &lengths);
        assert_eq!(encoded.len(), 1, "8 bits = 1 byte");
        // [0,1,0,1,0,1,0,1] → 0b01010101 = 0x55
        assert_eq!(encoded[0], 0x55u8, "MSB-first: bits [0,1,0,1,0,1,0,1] = 0x55");
    }

    #[test]
    fn huffman_msb_first_zero_pad() {
        // 7 bits total → 1 byte with 1 zero-pad at LSB
        // 2 symbols: codes 0→0 (1 bit), 1→1 (1 bit)
        let seq_codes = vec![0usize, 1, 0, 1, 0, 1, 0]; // 7 symbols
        let n_distinct = 2;
        let lengths = canonical_code_lengths(&seq_codes, n_distinct);
        let encoded = huffman_encode(&seq_codes, &lengths);
        assert_eq!(encoded.len(), 1, "7 bits → 1 byte with zero-padding");
        // bits: 0,1,0,1,0,1,0 → 0b0101010_0 = 0x54
        assert_eq!(encoded[0], 0x54u8, "zero-padded: 7 bits 0,1,0,1,0,1,0 + pad 0 = 0x54");
    }

    // ── Negative / fail-closed decode tests ─────────────────────────────

    #[test]
    fn huffman_decode_kraft_violation_returns_error() {
        // Kraft-violating lengths: [1, 1, 1] — over-full, not valid
        let lengths = vec![1u8, 1, 1];
        let blob = vec![0xFFu8; 10];
        let result = huffman_decode(&blob, 0, 1, &lengths);
        assert!(result.is_err(), "Kraft-violating lengths must return Err");
    }

    #[test]
    fn huffman_decode_truncation_returns_error() {
        // Valid lengths but blob is too short to decode count symbols
        let seq_codes: Vec<usize> = (0..100).map(|i| i % 4).collect();
        let lengths = canonical_code_lengths(&seq_codes, 4);
        let encoded = huffman_encode(&seq_codes, &lengths);
        // Truncate the blob to 1 byte — cannot decode 100 symbols from it
        let truncated = &encoded[..1];
        let result = huffman_decode(truncated, 0, 100, &lengths);
        assert!(result.is_err(), "truncated bitstream must return Err");
    }

    #[test]
    fn huffman_decode_no_match_returns_error() {
        // Construct a blob with a bit pattern that has no codeword match.
        // Use a 2-symbol code: 0→0 (1 bit), 1→1 (1 bit); all codewords are
        // valid single bits, so we need a longer code to create a no-match.
        // Use a 4-symbol skewed alphabet: 0→0 (1 bit), 1→10 (2 bits), 2→110 (3 bits), 3→111 (3 bits)
        // Feed a blob with 0b11111111 (only 1+10+110+111 patterns exist; with 8 bits
        // we decode some patterns but if we demand 10 symbols from 1 byte that truncates).
        let seq_codes_for_lengths: Vec<usize> = {
            let mut v = vec![0usize; 8];
            v.extend(vec![1usize; 4]);
            v.extend(vec![2usize; 2]);
            v.push(3);
            v
        };
        let lengths = canonical_code_lengths(&seq_codes_for_lengths, 4);
        // Demand 20 symbols from a 1-byte blob — will truncate
        let blob = vec![0b11111111u8];
        let result = huffman_decode(&blob, 0, 20, &lengths);
        assert!(result.is_err(), "no-match/truncation must return Err, not panic");
    }

    #[test]
    fn huffman_decode_never_panics_on_empty_lengths() {
        // All-zero code_len with count=5 — Kraft says 0 symbols → valid empty alphabet
        // but count > 0 means we can't decode anything → should be err or panic-free
        let lengths = vec![0u8; 4];
        let blob = vec![0xFFu8; 4];
        // kraft_ok returns true for all-zeros (empty alphabet), but we can't decode
        // count=5 symbols from it — decode_table is empty → no-match immediately.
        let result = huffman_decode(&blob, 0, 5, &lengths);
        assert!(result.is_err(), "all-zero lengths with count>0 must return Err, not panic");
    }

    // ── assign_canonical_codes direct tests ─────────────────────────────

    #[test]
    fn canonical_codes_two_equal_length() {
        // lengths [1, 1]: sym 0 → codeword 0 (1 bit), sym 1 → codeword 1 (1 bit)
        let lengths = vec![1u8, 1];
        let codes = assign_canonical_codes(&lengths);
        assert_eq!(codes[0], (0u32, 1u8), "sym 0 must be codeword 0, length 1");
        assert_eq!(codes[1], (1u32, 1u8), "sym 1 must be codeword 1, length 1");
    }

    #[test]
    fn canonical_codes_mixed_lengths() {
        // lengths [1, 2, 3, 3]: classic DEFLATE example
        // sort by (length, sym): sym0(1), sym1(2), sym2(3), sym3(3)
        // code: sym0→0 (1b), sym1→10 (2b), sym2→110 (3b), sym3→111 (3b)
        let lengths = vec![1u8, 2, 3, 3];
        let codes = assign_canonical_codes(&lengths);
        assert_eq!(codes[0], (0b0, 1), "sym0 must be (0, 1)");
        assert_eq!(codes[1], (0b10, 2), "sym1 must be (2, 2) = 0b10");
        assert_eq!(codes[2], (0b110, 3), "sym2 must be (6, 3) = 0b110");
        assert_eq!(codes[3], (0b111, 3), "sym3 must be (7, 3) = 0b111");
    }

    #[test]
    fn canonical_codes_absent_symbol_is_zero() {
        // Symbol 2 absent (length=0) — must produce (0, 0) sentinel
        let lengths = vec![1u8, 1, 0, 2, 2];
        let codes = assign_canonical_codes(&lengths);
        assert_eq!(codes[2], (0, 0), "absent symbol must have sentinel (0, 0)");
    }
}
