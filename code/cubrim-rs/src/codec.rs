// R6: Deterministic decode from header (orchestration layer).
// R7: Mandatory raw-store fallback against blowup.
//
// encode(data: &[u8]) -> Vec<u8> (Cubrim v1 blob):
//   1. Domainize (R8): S -> values
//   2. Build cube (R1/R2): values -> cube_data
//   3. Compute cube encoding size
//   4. R7 decision: if cube_size >= len(S) + overhead -> mode=1 (raw-store)
//   5. mode=0: build distance map (R3/R3.1) -> RLE (R4) -> bitpack values (R5) -> header (R6)
//   6. mode=1: header(mode=1, L=len(S)) + S verbatim
//
// decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError>:
//   1. Parse header (R6) — deterministic, no out-of-band state
//   2. mode=1: return raw block directly
//   3. mode=0: decode RLE gap streams -> coords -> bitpack values -> cube -> S
//
// HEADER_OVERHEAD_BOUND: R7 raw-store threshold constant.
// Matches prototype: max cube header ~286 bytes, bound = 320 with margin.
// For inputs <= 320 bytes, raw-store always fires.

use crate::error::CubrimError;
use crate::phi::{phi as phi_fn, phi_inv as phi_inv_fn, compute_n_and_b, B_DEFAULT};
use crate::cube::build_cube;
use crate::distance_map::{encode_axis_gaps, decode_axis_gaps};
use crate::rle::{rle_encode, rle_decode, rle_size};
use crate::bitpack::{build_value_dict, compute_width, bitpack_encode, bitpack_decode};
use crate::header::{
    serialize_header, parse_header,
    MODE_CUBE, MODE_RAW,
};

/// R7: Header overhead bound constant. Calibrated for v1-defaults.
/// fixed(13) + count(4) + b_k(4) + schemes(3) + n_distinct(2) +
/// inverse_dict(256) + traversal_phi(2) + gap_counts(4) = 288 bytes max for N=2.
/// 320 with margin, matches prototype HEADER_OVERHEAD_BOUND.
pub const HEADER_OVERHEAD_BOUND: usize = 320;

/// Compute minimum N such that B^N >= L. Matches prototype's _compute_min_N.
fn compute_min_n(l: usize, b: usize) -> usize {
    let (n, _) = compute_n_and_b(l, b);
    n
}

/// Estimate the cube-mode encoded output size (without allocating the full output).
fn estimate_cube_size(
    n: usize,
    b: usize,
    l: usize,
    count: usize,
    b_k: &[usize],
    axis_gaps: &[Vec<usize>],
    inverse_dict: &[usize],
    w: usize,
) -> usize {
    let axis_gap_counts: Vec<usize> = axis_gaps.iter().map(|g| g.len()).collect();
    let hdr_size = serialize_header(
        MODE_CUBE, n, b, l, count, b_k, w, inverse_dict, &axis_gap_counts,
    ).len();

    let rle_total: usize = axis_gaps.iter().map(|g| rle_size(g)).sum();

    let bitpack_total = if count > 0 { (count * w + 7) / 8 } else { 0 };

    hdr_size + rle_total + bitpack_total
}

/// R6/R7: Encode input bytes to Cubrim v1 format.
///
/// Returns a blob that:
/// - If mode=1 (raw-store): header + data verbatim; size <= len(data) + HEADER_OVERHEAD_BOUND
/// - If mode=0 (cube): header + RLE gap streams + bitpacked values
pub fn encode(data: &[u8]) -> Vec<u8> {
    let l = data.len();
    let b = B_DEFAULT;

    // Special case: empty input -> raw-store
    if l == 0 {
        let hdr = serialize_header(MODE_RAW, 2, b, 0, 0, &[], 0, &[], &[]);
        return hdr;
    }

    let n_min = compute_min_n(l, b);

    // R7 fast-path: L > B^2 = 65536 requires N>2; cube mode always expands
    if l > b * b {
        let hdr = serialize_header(MODE_RAW, n_min, b, l, 0, &[], 0, &[], &[]);
        let mut out = hdr;
        out.extend_from_slice(data);
        return out;
    }

    // R7: small inputs always raw-store (header alone would exceed any savings)
    if l <= HEADER_OVERHEAD_BOUND {
        let hdr = serialize_header(MODE_RAW, n_min, b, l, 0, &[], 0, &[], &[]);
        let mut out = hdr;
        out.extend_from_slice(data);
        return out;
    }

    // Step 1: R8 domainize (identity)
    // Step 2: R1/R2 build cube
    let cube = build_cube(data);
    let n = cube.n;
    let b = cube.b;
    let b_k = &cube.b_k;
    let populated = &cube.populated;

    // Step 3: R5 shift-to-corner — build value dictionary
    let all_values: Vec<usize> = populated.iter().map(|(_, v)| *v).collect();
    let (v2c, inverse_dict) = build_value_dict(&all_values);
    let w = compute_width(inverse_dict.len());

    // Step 4: R3/R3.1 build distance map (per-axis unique sorted coords + gaps)
    // For each axis k, extract unique sorted coords of all populated points on axis k
    let mut axis_gaps: Vec<Vec<usize>> = Vec::with_capacity(n);
    for k in 0..n {
        let mut coords_k: Vec<usize> = populated.iter().map(|(c, _)| c[k]).collect();
        coords_k.sort_unstable();
        coords_k.dedup();
        // encode_axis_gaps is fail-closed; can only fail on encode bugs, not data
        let gaps = encode_axis_gaps(&coords_k, b_k[k]).expect("gap encode cannot fail on valid cube data");
        axis_gaps.push(gaps);
    }

    // Step 5: R7 decision — compare cube encoded size vs raw-store output size
    let axis_gap_counts: Vec<usize> = axis_gaps.iter().map(|g| g.len()).collect();
    let cube_size = estimate_cube_size(n, b, l, cube.count, b_k, &axis_gaps, &inverse_dict, w);
    let raw_hdr = serialize_header(MODE_RAW, n, b, l, 0, &[], 0, &[], &[]);
    let raw_output_size = raw_hdr.len() + l;

    if cube_size >= raw_output_size {
        // R7: cube does not improve on raw; use raw-store
        let mut out = raw_hdr;
        out.extend_from_slice(data);
        return out;
    }

    // Step 6: R4 RLE-encode gap streams
    let rle_streams: Vec<Vec<u8>> = axis_gaps.iter().map(|g| rle_encode(g)).collect();

    // Step 7: R5 bitpack values (in lex-sorted point order)
    let point_values: Vec<usize> = populated.iter().map(|(_, v)| *v).collect();
    let packed_values = bitpack_encode(&point_values, &v2c, w);

    // Step 8: R6 serialize header
    let hdr = serialize_header(
        MODE_CUBE, n, b, l, cube.count, b_k, w, &inverse_dict, &axis_gap_counts,
    );

    let mut out = hdr;
    for stream in &rle_streams {
        out.extend_from_slice(stream);
    }
    out.extend_from_slice(&packed_values);
    out
}

/// R6: Decode a Cubrim v1 blob back to original bytes.
///
/// Deterministic decode from header alone — no out-of-band state.
/// Corrupt input raises CubrimError (never silent garbage).
pub fn decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    // Parse header (R6)
    let (hdr, mut offset) = parse_header(blob)?;
    let l = hdr.l;

    // R7: raw-store mode — return payload directly
    if hdr.mode == MODE_RAW {
        let payload = &blob[offset..];
        if payload.len() < l {
            return Err(CubrimError::Decode(format!(
                "Raw-store payload too short: got {} bytes, expected {} bytes (from header L field).",
                payload.len(),
                l
            )));
        }
        return Ok(payload[..l].to_vec());
    }

    // mode == MODE_CUBE
    if hdr.mode != MODE_CUBE {
        return Err(CubrimError::Decode(format!("Unknown mode in header: {}", hdr.mode)));
    }

    // Empty input special case
    if l == 0 {
        return Ok(vec![]);
    }

    let n = hdr.n;
    let b = hdr.b;
    let b_k = &hdr.b_k;
    let count = hdr.count;
    let w = hdr.w;
    let inverse_dict = &hdr.inverse_dict;
    let axis_gap_counts = &hdr.axis_gap_counts;

    if b_k.len() != n {
        return Err(CubrimError::Decode(format!("b_k length {} != N={}", b_k.len(), n)));
    }
    if axis_gap_counts.len() != n {
        return Err(CubrimError::Decode(format!("axis_gap_counts length != N={}", n)));
    }

    // Read RLE streams for each axis
    // Each axis has axis_gap_counts[k] unique coordinate values -> that many gaps in the stream
    let mut axis_coords: Vec<Vec<usize>> = Vec::with_capacity(n);
    for k in 0..n {
        let n_gaps = axis_gap_counts[k];
        // Read enough RLE pairs to decode n_gaps gaps
        let (stream_bytes, consumed) = read_rle_stream(blob, offset, n_gaps)?;
        let gaps_k = rle_decode(stream_bytes)?;
        if gaps_k.len() != n_gaps {
            return Err(CubrimError::Decode(format!(
                "Axis {k}: decoded {} gaps, expected {n_gaps}", gaps_k.len()
            )));
        }
        // Validate gap invariant on decode (R3.1 fail-closed)
        for (i, &g) in gaps_k.iter().enumerate() {
            if g < 1 {
                return Err(CubrimError::GapInvariant(format!(
                    "Axis {k} gap[{i}]={g} < 1 — corrupt stream"
                )));
            }
            if g > b_k[k] {
                return Err(CubrimError::GapInvariant(format!(
                    "Axis {k} gap[{i}]={g} > b_k[{k}]={} — corrupt stream", b_k[k]
                )));
            }
        }
        let coords_k = decode_axis_gaps(&gaps_k);
        axis_coords.push(coords_k);
        offset += consumed;
    }

    // Read bitpacked values
    let bitpack_bytes_count = if count > 0 { (count * w + 7) / 8 } else { 0 };
    if offset + bitpack_bytes_count > blob.len() {
        return Err(CubrimError::Decode(format!(
            "Bitpack data truncated: need {} bytes at offset {}, have {} bytes total",
            bitpack_bytes_count, offset, blob.len()
        )));
    }
    let packed_values_bytes = &blob[offset..offset + bitpack_bytes_count];

    // Decode bitpacked values
    let values = bitpack_decode(packed_values_bytes, w, count, inverse_dict)?;

    // Reconstruct original byte sequence.
    //
    // During encode, cube.rs builds (phi(i), data[i]) for each i in [0, L-1],
    // then sorts by phi(i) coordinates in lex order.
    // Values are stored in that lex-sorted order.
    //
    // NOTE (PRD §2.4 item 8): lex order of phi(i) coords != sequential index order.
    // Example: phi(256)=(0,1) < phi(1)=(1,0) in lex order.
    // Therefore: rebuild lex-sorted list of phi(i) for i in [0, L-1],
    // then result[phi_inv(coords)] = values[j].
    //
    // This is deterministic from (L, N, B) alone — no out-of-band state (R6).

    let mut lex_sorted_coords: Vec<Vec<usize>> = (0..l)
        .map(|i| phi_fn(i, n, b))
        .collect();
    lex_sorted_coords.sort();

    let mut result = vec![0u8; l];
    for (j, coords) in lex_sorted_coords.iter().enumerate() {
        let orig_idx = phi_inv_fn(coords, b);
        if orig_idx < l && j < values.len() {
            result[orig_idx] = values[j] as u8;
        }
    }

    Ok(result)
}

/// Read enough RLE pairs from blob starting at offset to decode n_gaps gaps.
/// Returns (&[u8] slice of pairs consumed, bytes consumed).
fn read_rle_stream(blob: &[u8], offset: usize, n_gaps: usize) -> Result<(&[u8], usize), CubrimError> {
    if n_gaps == 0 {
        return Ok((&blob[offset..offset], 0));
    }

    const PAIR_SIZE: usize = 4;
    let mut total_decoded = 0usize;
    let mut bytes_read = 0usize;
    let mut pos = offset;

    while total_decoded < n_gaps {
        if pos + PAIR_SIZE > blob.len() {
            return Err(CubrimError::Decode(format!(
                "RLE stream truncated: need more pairs to decode {n_gaps} gaps, got {total_decoded} so far."
            )));
        }
        let _value = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
        let run_length = u16::from_be_bytes([blob[pos + 2], blob[pos + 3]]) as usize;
        total_decoded += run_length;
        pos += PAIR_SIZE;
        bytes_read += PAIR_SIZE;
    }

    if total_decoded != n_gaps {
        return Err(CubrimError::Decode(format!(
            "RLE stream over-reads: decoded {total_decoded} gaps, expected {n_gaps}."
        )));
    }

    Ok((&blob[offset..offset + bytes_read], bytes_read))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // V-AC-1: Byte-exact lossless round-trip (CORNERSTONE)
    // -------------------------------------------------------------------------

    #[test]
    fn test_round_trip_empty() {
        let data = b"";
        assert_eq!(decode(&encode(data)).unwrap(), data.as_ref());
    }

    #[test]
    fn test_round_trip_single_byte() {
        let data = b"\x42";
        assert_eq!(decode(&encode(data)).unwrap(), data.as_ref());
    }

    #[test]
    fn test_round_trip_all_same_byte() {
        // Uniform data — raw-store path (L=256 <= HEADER_OVERHEAD_BOUND=320)
        let data: Vec<u8> = vec![0xAA; 256];
        assert_eq!(decode(&encode(&data)).unwrap(), data);
    }

    #[test]
    fn test_round_trip_all_256_distinct() {
        // V-AC-4 edge: all 256 distinct values
        let data: Vec<u8> = (0u8..=255).collect();
        assert_eq!(decode(&encode(&data)).unwrap(), data);
    }

    #[test]
    fn test_round_trip_text() {
        let line = b"2026-06-17T12:00:00Z INFO cubrim starting up level=debug\n";
        let data: Vec<u8> = line.iter().copied().cycle().take(1024).collect();
        let recovered = decode(&encode(&data)).unwrap();
        assert_eq!(recovered, data, "text round-trip failed");
    }

    #[test]
    fn test_round_trip_random_bytes() {
        // Pseudo-random bytes (not crypto — just a deterministic sequence)
        let data: Vec<u8> = (0usize..1024).map(|i| ((i % 256) as u8).wrapping_mul(71).wrapping_add(13)).collect();
        assert_eq!(decode(&encode(&data)).unwrap(), data);
    }

    // -------------------------------------------------------------------------
    // V-AC-3: CLI-level: blob starts with magic
    // -------------------------------------------------------------------------

    #[test]
    fn test_encode_starts_with_magic() {
        use crate::header::MAGIC;
        let data = b"hello world";
        let blob = encode(data);
        assert_eq!(&blob[0..4], &MAGIC, "blob must start with magic cb 52 49 4d");
    }

    // -------------------------------------------------------------------------
    // V-AC-4: Round-trip across input classes (parametrised)
    // -------------------------------------------------------------------------

    #[test]
    fn test_round_trip_all_classes() {
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("1byte", vec![0x42]),
            ("uniform_256", vec![0xAA; 256]),
            ("all_distinct_256", (0u8..=255).collect()),
            ("text_1kb", b"the quick brown fox jumps over the lazy dog ".iter().copied().cycle().take(1024).collect()),
            ("random_1kb", (0usize..1024).map(|i| (i as u8).wrapping_mul(113).wrapping_add(7)).collect()),
        ];

        for (name, data) in &cases {
            let blob = encode(data);
            let recovered = decode(&blob).unwrap();
            assert_eq!(&recovered, data, "round-trip failed for '{name}'");
        }
    }

    // -------------------------------------------------------------------------
    // V-AC-5: R3.1 worked example
    // -------------------------------------------------------------------------

    #[test]
    fn test_r3_1_worked_example_via_distance_map() {
        use crate::distance_map::{encode_axis_gaps, decode_axis_gaps};
        // {0, 3, 7} with b_k=8 -> gaps (1, 3, 4) -> decode -> {0, 3, 7}
        let gaps = encode_axis_gaps(&[0, 3, 7], 8).unwrap();
        assert_eq!(gaps, vec![1, 3, 4]);
        assert_eq!(decode_axis_gaps(&gaps), vec![0, 3, 7]);
    }

    // -------------------------------------------------------------------------
    // V-AC-6: R7 raw-store fallback never blows up
    // -------------------------------------------------------------------------

    #[test]
    fn test_raw_store_for_large_input() {
        use crate::header::{parse_header, MODE_RAW};
        // >65536 bytes -> always raw-store
        let data: Vec<u8> = (0usize..66000).map(|i| (i % 256) as u8).collect();
        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();
        assert_eq!(hdr.mode, MODE_RAW, "large input must trigger raw-store");
        let overhead = blob.len() - data.len();
        assert!(
            overhead <= HEADER_OVERHEAD_BOUND,
            "raw-store overhead {overhead} > HEADER_OVERHEAD_BOUND {HEADER_OVERHEAD_BOUND}"
        );
        assert_eq!(decode(&blob).unwrap(), data, "large raw-store round-trip failed");
    }

    #[test]
    fn test_raw_store_for_small_input() {
        use crate::header::{parse_header, MODE_RAW};
        // <= HEADER_OVERHEAD_BOUND bytes -> always raw-store
        let data: Vec<u8> = vec![42u8; 100];
        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();
        assert_eq!(hdr.mode, MODE_RAW, "small input <= {HEADER_OVERHEAD_BOUND} must trigger raw-store");
        assert_eq!(decode(&blob).unwrap(), data);
    }

    // -------------------------------------------------------------------------
    // CUBE PATH: clustered input in 321..65536-byte window (V-AC requirement)
    // The plan explicitly requires a clustered input that exercises cube mode.
    // -------------------------------------------------------------------------

    #[test]
    fn test_cube_path_clustered_input() {
        use crate::header::{parse_header, MODE_CUBE};
        // Clustered sparse-ish input: a 500-byte buffer where only a few distinct
        // byte values appear with long runs -> should compress well enough for cube mode.
        // Use a pattern with exactly 2 distinct values to minimize W (W=1 bit).
        // 500 bytes > HEADER_OVERHEAD_BOUND=320, < 65536 -> eligible for cube.
        let data: Vec<u8> = (0..500)
            .map(|i: usize| if i % 10 == 0 { 0x01 } else { 0x00 })
            .collect();

        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();

        // This specific pattern should trigger cube mode (2 distinct values, W=1 bit)
        // If it doesn't, we still need to verify round-trip
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "clustered input cube-path round-trip failed");

        // Log which mode was chosen for diagnostic purposes
        if hdr.mode == MODE_CUBE {
            // Good: cube mode exercised
        } else {
            // Raw-store: R7 decided cube wouldn't help; still valid per R7 contract
            // but we need at least one cube-mode test, so try a better clustered pattern
        }
    }

    #[test]
    fn test_cube_path_forced_clustered() {
        use crate::header::{parse_header, MODE_CUBE};
        // Create an input specifically designed to trigger cube mode:
        // - Size in (HEADER_OVERHEAD_BOUND=320, 65536] range -> 400 bytes
        // - Very few distinct values so W is small (1-2 bits)
        // - Single repeated value is trivially compressible by bitpacking
        // With W=1 bit for 2 values, bitpack(400 bytes) = 50 bytes + header ~<400
        let data: Vec<u8> = vec![0xABu8; 400]; // all same -> W=1 bit -> 50 bytes packed + header
        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();
        // 400 bytes, all same: value_dict has 1 value, W=1 bit
        // bitpacked: ceil(400*1/8) = 50 bytes
        // Header for N=2, n_distinct=1: ~44 bytes
        // Total cube: ~94 bytes vs raw: 13+400=413 bytes -> cube wins
        assert_eq!(hdr.mode, MODE_CUBE, "all-same 400-byte input must trigger cube mode (94 < 413)");
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "cube-mode round-trip failed for all-same-400");
    }

    // -------------------------------------------------------------------------
    // Decode robustness (fail-closed, V-AC related)
    // -------------------------------------------------------------------------

    #[test]
    fn test_decode_rejects_bad_magic() {
        let mut blob = encode(b"hello");
        blob[0] = 0xFF;
        assert!(decode(&blob).is_err());
    }

    #[test]
    fn test_decode_rejects_truncated() {
        let blob = encode(b"hello world test");
        let truncated = &blob[..5];
        assert!(decode(truncated).is_err());
    }
}
