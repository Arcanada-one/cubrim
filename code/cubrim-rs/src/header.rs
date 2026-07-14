// R6: Self-describing header for deterministic decode without out-of-band state.
//
// Header layout (binary, big-endian) — byte-exact match with prototype header.py:
//   [magic 4B][version 1B][mode 1B][N 1B][B 2B][L 4B]            = 13 bytes fixed
//   [count 4B] (mode 0 only)
//   [b_k N*2B] (mode 0 only)
//   [map_scheme 1B][value_scheme 1B][W 1B] (mode 0 only)
//   [n_distinct 2B] (mode 0 only)
//   [inverse_dict n_distinct*1B] (mode 0 only)  -- u8: byte values 0..255
//   [traversal 1B][phi_id 1B] (mode 0 only)
//   [axis_gap_counts N*2B] (mode 0 only)  -- uint16 per axis
//
// Magic: 0xCB 'R' 'I' 'M'  (b"\xCBRIM" in Python = [0xCB, 0x52, 0x49, 0x4D])
// All fields big-endian.

use crate::error::CubrimError;

// Format identification — byte-exact match with prototype
// Python: MAGIC = b"\xCBRIM" = [0xCB, 0x52, 0x49, 0x4D]
pub const MAGIC: [u8; 4] = [0xCB, b'R', b'I', b'M'];

/// All fields needed to serialize the cube-mode portion of the header.
/// Passed to serialize_cube_header; `mode` is implied (always MODE_CUBE).
pub(crate) struct CubeHeaderState<'a> {
    pub n: usize,
    pub b: usize,
    pub l: usize,
    pub count: usize,
    pub b_k: &'a [usize],
    pub map_scheme: u8,
    pub value_scheme: u8,
    pub w: usize,
    pub inverse_dict: &'a [usize],
    pub axis_gap_counts: &'a [usize],
}
pub const VERSION: u8 = 1;

// Mode constants (R6/R7)
pub const MODE_CUBE: u8 = 0;
pub const MODE_RAW: u8 = 1;
/// Chunked container (CUBR big-file support). Wraps N independent sub-blobs, each
/// of which is itself a self-describing Cubrim blob (mode 0/1) for an input slice
/// of at most `cube_size_limit()` (≤65536) bytes. Used only when the whole input
/// exceeds the single-block cube ceiling; smaller inputs are byte-identical to v1.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_CHUNKED 1B][n_blocks 4B BE]
///       then n_blocks × ( [sub_len 4B BE][sub_blob sub_len bytes] ).
pub const MODE_CHUNKED: u8 = 2;
/// Whole-file LZ container (H-25d). The entire input is LZ77-tokenized over a
/// full-file window BEFORE chunking, so long-range repeats that cross the 64KB
/// block boundary become reachable. The literal residue is encoded through the
/// normal pipeline (a nested self-describing blob, itself possibly MODE_CHUNKED);
/// the match length/distance streams (with the repeat-offset cache) are coded at
/// file level. Emitted only when strictly smaller than the non-LZ encoding
/// (competitive size pick), so it is structurally regression-proof.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_LZ 1B][orig_len 4B][n_tokens 4B][n_matches 4B]
///       [lit_blob_len 4B][lit_blob …][token streams …].
pub const MODE_LZ: u8 = 3;
/// Columnar field-split container (H-29, class-C specialization). For record-structured
/// text (CSV / TSV / delimited telemetry), the input is split into rows (by '\n') and
/// fields (by a detected delimiter), then re-serialized column-major so each column's
/// values cluster — dramatically improving BWT-run quality and entropy coding on
/// telemetry/columnar data. Fully reversible (field boundaries kept as separators, a
/// per-row field-count side stream restores the row layout). Emitted only when strictly
/// smaller than every other candidate (competitive size pick) AND only attempted on
/// inputs larger than the single-block ceiling, so all ≤64KB inputs are byte-identical
/// to v1 (zero regression on the frozen leaderboard).
/// Wire: [MAGIC 4B][VERSION 1B][MODE_COLUMNAR 1B][orig_len 4B][delim 1B][n_rows 4B]
///       [n_cols 4B][kblob_len 4B][kblob …][colblob_len 4B][colblob …].
pub const MODE_COLUMNAR: u8 = 4;
/// VCF genotype-matrix container (H-52, genomic class). For a detected VCF (`##fileformat=VCF`
/// preamble + `#CHROM…` header + `GT`-only genotype rows), the genotype matrix is transformed
/// by PBWT (Positional BWT, Durbin 2014): haplotypes are reordered per variant by their
/// reversed-prefix match so linkage disequilibrium yields long allele-column runs (RLE'd).
/// The permutation is rebuilt incrementally by the decoder (like BWT's LF-mapping), so it is
/// NOT transmitted — a structural win unreachable by a per-byte backend. Multi-allelic /
/// unphased / missing cells are a charged exception list. Emitted only when strictly smaller
/// than the base encoding (competitive) AND only on detected VCF input, so every non-VCF
/// input (the whole tuned/holdout corpus) is byte-identical to v1.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_VCF 1B][orig_len 4B][ends_nl 1B][n_var 4B][n_samp 4B]
///       [n_exc 4B] then 4 length-prefixed sub-blobs: preamble, fixed-fields, PBWT-RLE, exceptions.
pub const MODE_VCF: u8 = 5;

/// Binary float-array container (H-54, point-cloud / binary-float class). For a detected
/// fixed-width little-endian float32 record stream (e.g. a raw LiDAR `.bin`: N points ×
/// {x,y,z,…} float32, array-of-structs), the records are split column-major (struct-of-
/// arrays) and each column is competitively coded raw or as a reversible wrapping-uint32
/// delta of the float bit pattern. Spatially-smooth row order (a raw spinning-LiDAR firing
/// sweep) makes consecutive coordinate bits nearly equal, so the delta column collapses;
/// attribute columns (reflectance) that do not benefit stay raw (per-column mode flag).
/// This is the telemetry-columnar lever (AoS→SoA + integer delta) transplanted to a binary
/// float input the cube/BWT/LZ path cannot reach. Emitted only when strictly smaller than
/// the base encoding (competitive min) AND only on detected plausible-float input gated
/// >cube_size_limit, so every non-matching input (the whole tuned/holdout corpus) is
/// byte-identical to v1.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_BINFLOAT 1B][orig_len 4B][rec_width 1B][n_cols 1B]
///       [col_modes n_cols B][tail_len 1B][tail bytes] then n_cols length-prefixed sub-blobs.
pub const MODE_BINFLOAT: u8 = 6;

/// 16-bit grayscale image MED predictor (H-60 x-ray / H-63 MR-DICOM). For a detected 16-bit
/// raster (little-endian u16 samples, row width auto-detected by min vertical-abs-diff), each
/// sample is replaced by its JPEG-LS/LOCO-I MED residual (median of left/up + gradient),
/// which the 1-D cube/BWT pipeline cannot reach. Emitted only when strictly smaller than base
/// (competitive min), gated >cube_size_limit — every non-image input stays byte-identical.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_MED16 1B][orig_len 4B][width_px 2B BE][tail_byte 1B]
///       then a length-implicit nested sub-blob (the MED residual, decodes to orig_len bytes).
pub const MODE_MED16: u8 = 7;

/// BCJ branch-conversion filter for executables (H-45 x86 / H-57 ARM64). A detected ELF/PE
/// binary has its arch-matched relative CALL/JMP operands (x86 E8/E9; ARM64 BL) rewritten to
/// absolute so repeated targets become byte-identical, then coded via the base pipeline.
/// Arch is matched to the ELF e_machine / PE machine field; mismatched filters are never
/// applied. Competitive min; small files participate only after strict ELF/PE architecture
/// detection, so non-executable inputs stay byte-identical.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_BCJ 1B][orig_len 4B][arch 1B] then nested sub-blob.
pub const MODE_BCJ: u8 = 8;

/// Byte-plane Structure-of-Arrays de-interleave for fixed-width binary records (H-40, sao
/// star catalog). A detected fixed record width W (min lag-W abs-diff) is transposed so every
/// record's byte-offset-p bytes are contiguous, grouping smoothly-varying columns into runs
/// the backend captures. Tail (< W) kept verbatim. Competitive min, gated >cube_size_limit.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_SOA 1B][orig_len 4B][width 2B BE] then nested sub-blob.
pub const MODE_SOA: u8 = 9;

/// Context-mixing backend (CUBR-0043, NEW-01). A lpaq-lite byte predictor with order-0..6,
/// word, and match contexts codes the raw byte stream directly via a range coder. It is a
/// top-level backend, not a cube value-scheme: the outer dispatcher keeps it only when it
/// strictly beats the current competitive minimum. Gated to large text-like inputs so binary
/// type-specializations do not pay the CM probe cost.
/// Wire: [MAGIC 4B][VERSION 1B][MODE_CM 1B][orig_len 8B BE][block_size 4B BE][n_blocks 4B BE]
///       then n_blocks x ([comp_len 4B BE][raw_hash 8B BE]) followed by concatenated CM blocks.
pub const MODE_CM: u8 = 10;

// Scheme identifiers (R4, R5)
pub const MAP_SCHEME_RLE: u8 = 1;
/// PackedNibble varint-per-gap scheme (GapScheme::PackedNibble).
pub const MAP_SCHEME_PACKED_NIBBLE: u8 = 2;
/// Bitpack-fixed value scheme: lex-order point values, W bits each (v1-default).
pub const VALUE_SCHEME_FIXED: u8 = 1;
/// RLE-codes value scheme: sequential-order codes, (code:u8, run:u16) triples.
pub const VALUE_SCHEME_RLE_CODES: u8 = 2;
/// Entropy value scheme: canonical Huffman on the value-code stream (order-0).
pub const VALUE_SCHEME_ENTROPY: u8 = 3;
/// EntropyContext value scheme: order-1 context-adaptive canonical Huffman (T4).
pub const VALUE_SCHEME_ENTROPY_CONTEXT: u8 = 4;

// Traversal and Phi identifiers (R1)
pub const TRAVERSAL_LEX: u8 = 1;
pub const PHI_MIXED_RADIX: u8 = 1;

// Fixed-size portion: 4+1+1+1+2+4 = 13 bytes
pub const FIXED_HEADER_SIZE: usize = 13;

/// Parsed header fields.
#[derive(Debug, Clone)]
pub struct Header {
    pub magic: [u8; 4],
    pub version: u8,
    pub mode: u8,
    pub n: usize,
    pub b: usize,
    pub l: usize,
    // Cube-mode only:
    pub count: usize,
    pub b_k: Vec<usize>,
    pub map_scheme: u8,
    pub value_scheme: u8,
    pub w: usize,
    pub n_distinct: usize,
    pub inverse_dict: Vec<usize>,
    pub traversal: u8,
    pub phi_id: u8,
    pub axis_gap_counts: Vec<usize>,
}

/// Serialize the fixed portion of the header for raw-store mode (MODE_RAW).
/// Only fixed fields are written; cube-specific fields are omitted.
pub(crate) fn serialize_raw_header(n: usize, b: usize, l: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(FIXED_HEADER_SIZE);
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(MODE_RAW);
    out.push(n as u8);
    out.extend_from_slice(&(b as u16).to_be_bytes());
    out.extend_from_slice(&(l as u32).to_be_bytes());
    out
}

/// Serialize the full cube-mode header from a CubeHeaderState.
/// `mode` is always MODE_CUBE; all cube-specific fields are written.
pub(crate) fn serialize_cube_header(s: &CubeHeaderState<'_>) -> Vec<u8> {
    let mut out = Vec::new();
    // Fixed portion: magic(4) + version(1) + mode(1) + N(1) + B(2) + L(4) = 13 bytes
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(MODE_CUBE);
    out.push(s.n as u8);
    out.extend_from_slice(&(s.b as u16).to_be_bytes());
    out.extend_from_slice(&(s.l as u32).to_be_bytes());
    // count (4B)
    out.extend_from_slice(&(s.count as u32).to_be_bytes());
    // b_k (N * 2B)
    for &bk in s.b_k {
        out.extend_from_slice(&(bk as u16).to_be_bytes());
    }
    // map_scheme(1) + value_scheme(1) + W(1)
    out.push(s.map_scheme);
    out.push(s.value_scheme);
    out.push(s.w as u8);
    // n_distinct (2B)
    let n_distinct = s.inverse_dict.len();
    out.extend_from_slice(&(n_distinct as u16).to_be_bytes());
    // inverse_dict (n_distinct * 1B)
    for &v in s.inverse_dict {
        out.push(v as u8);
    }
    // traversal(1) + phi_id(1)
    out.push(TRAVERSAL_LEX);
    out.push(PHI_MIXED_RADIX);
    // axis_gap_counts (N * 2B)
    for &gc in s.axis_gap_counts {
        out.extend_from_slice(&(gc as u16).to_be_bytes());
    }
    out
}

/// Parse header from bytes. Returns (Header, offset_after_header).
/// Raises CubrimError for invalid magic or unsupported version.
pub fn parse_header(data: &[u8]) -> Result<(Header, usize), CubrimError> {
    if data.len() < FIXED_HEADER_SIZE {
        return Err(CubrimError::Decode(format!(
            "Data too short to contain header: {} < {} bytes",
            data.len(),
            FIXED_HEADER_SIZE
        )));
    }

    let magic: [u8; 4] = data[0..4].try_into().unwrap();
    if magic != MAGIC {
        return Err(CubrimError::InvalidMagic(format!(
            "Invalid magic bytes: {:?}, expected {:?}. Not a Cubrim v1 file.",
            magic, MAGIC
        )));
    }

    let version = data[4];
    if version != VERSION {
        return Err(CubrimError::UnsupportedVersion(version));
    }

    let mode = data[5];
    let n = data[6] as usize;
    let b = u16::from_be_bytes([data[7], data[8]]) as usize;
    let l = u32::from_be_bytes([data[9], data[10], data[11], data[12]]) as usize;
    let mut offset = FIXED_HEADER_SIZE;

    let mut hdr = Header {
        magic,
        version,
        mode,
        n,
        b,
        l,
        count: 0,
        b_k: vec![],
        map_scheme: 0,
        value_scheme: 0,
        w: 0,
        n_distinct: 0,
        inverse_dict: vec![],
        traversal: 0,
        phi_id: 0,
        axis_gap_counts: vec![],
    };

    if mode == MODE_RAW {
        return Ok((hdr, offset));
    }

    if mode != MODE_CUBE {
        return Err(CubrimError::Decode(format!(
            "Unknown mode: {mode}. Expected {MODE_CUBE} or {MODE_RAW}."
        )));
    }

    // count (4B)
    if offset + 4 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at count field".to_string(),
        ));
    }
    hdr.count = u32::from_be_bytes([
        data[offset],
        data[offset + 1],
        data[offset + 2],
        data[offset + 3],
    ]) as usize;
    offset += 4;

    // b_k (N * 2B, uint16)
    if offset + n * 2 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at b_k field".to_string(),
        ));
    }
    for _ in 0..n {
        let bk = u16::from_be_bytes([data[offset], data[offset + 1]]) as usize;
        hdr.b_k.push(bk);
        offset += 2;
    }

    // map_scheme(1) + value_scheme(1) + W(1)
    if offset + 3 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at scheme fields".to_string(),
        ));
    }
    hdr.map_scheme = data[offset];
    hdr.value_scheme = data[offset + 1];
    hdr.w = data[offset + 2] as usize;
    offset += 3;

    // n_distinct (2B)
    if offset + 2 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at n_distinct".to_string(),
        ));
    }
    hdr.n_distinct = u16::from_be_bytes([data[offset], data[offset + 1]]) as usize;
    offset += 2;

    // inverse_dict (n_distinct * 1B)
    if offset + hdr.n_distinct > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at inverse_dict".to_string(),
        ));
    }
    for i in 0..hdr.n_distinct {
        hdr.inverse_dict.push(data[offset + i] as usize);
    }
    offset += hdr.n_distinct;

    // traversal(1) + phi_id(1)
    if offset + 2 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at traversal/phi fields".to_string(),
        ));
    }
    hdr.traversal = data[offset];
    hdr.phi_id = data[offset + 1];
    offset += 2;

    // axis_gap_counts (N * 2B, uint16)
    if offset + n * 2 > data.len() {
        return Err(CubrimError::Decode(
            "Header truncated at axis_gap_counts".to_string(),
        ));
    }
    for _ in 0..n {
        let gc = u16::from_be_bytes([data[offset], data[offset + 1]]) as usize;
        hdr.axis_gap_counts.push(gc);
        offset += 2;
    }

    Ok((hdr, offset))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_magic_bytes_exact() {
        // PRD §2.4 item 1: magic must be [0xCB, 0x52, 0x49, 0x4D]
        // Python: b"\xCBRIM" -> 0xCB 'R' 'I' 'M' = cb 52 49 4d
        assert_eq!(MAGIC, [0xCB, 0x52, 0x49, 0x4D]);
        assert_eq!(MAGIC[1], b'R');
        assert_eq!(MAGIC[2], b'I');
        assert_eq!(MAGIC[3], b'M');
    }

    #[test]
    fn test_fixed_header_size() {
        // 4+1+1+1+2+4 = 13 bytes
        assert_eq!(FIXED_HEADER_SIZE, 13);
    }

    #[test]
    fn test_serialize_parse_raw_mode() {
        let bytes = serialize_raw_header(2, 256, 1000);
        assert_eq!(&bytes[0..4], &MAGIC);
        assert_eq!(bytes[4], VERSION);
        assert_eq!(bytes[5], MODE_RAW);
        assert_eq!(bytes[6], 2); // N
        assert_eq!(u16::from_be_bytes([bytes[7], bytes[8]]), 256); // B
        assert_eq!(
            u32::from_be_bytes([bytes[9], bytes[10], bytes[11], bytes[12]]),
            1000
        ); // L

        let (hdr, offset) = parse_header(&bytes).unwrap();
        assert_eq!(offset, FIXED_HEADER_SIZE);
        assert_eq!(hdr.mode, MODE_RAW);
        assert_eq!(hdr.n, 2);
        assert_eq!(hdr.b, 256);
        assert_eq!(hdr.l, 1000);
    }

    #[test]
    fn test_serialize_parse_cube_mode() {
        let b_k = vec![256usize, 256];
        let inverse_dict = vec![65usize, 66, 67]; // 'A', 'B', 'C'
        let axis_gap_counts = vec![10usize, 8];

        let bytes = serialize_cube_header(&CubeHeaderState {
            n: 2,
            b: 256,
            l: 500,
            count: 42,
            b_k: &b_k,
            map_scheme: MAP_SCHEME_RLE,
            value_scheme: VALUE_SCHEME_FIXED,
            w: 2,
            inverse_dict: &inverse_dict,
            axis_gap_counts: &axis_gap_counts,
        });

        let (hdr, _offset) = parse_header(&bytes).unwrap();
        assert_eq!(hdr.mode, MODE_CUBE);
        assert_eq!(hdr.n, 2);
        assert_eq!(hdr.b, 256);
        assert_eq!(hdr.l, 500);
        assert_eq!(hdr.count, 42);
        assert_eq!(hdr.b_k, vec![256, 256]);
        assert_eq!(hdr.map_scheme, MAP_SCHEME_RLE);
        assert_eq!(hdr.value_scheme, VALUE_SCHEME_FIXED);
        assert_eq!(hdr.w, 2);
        assert_eq!(hdr.n_distinct, 3);
        assert_eq!(hdr.inverse_dict, vec![65, 66, 67]);
        assert_eq!(hdr.traversal, TRAVERSAL_LEX);
        assert_eq!(hdr.phi_id, PHI_MIXED_RADIX);
        assert_eq!(hdr.axis_gap_counts, vec![10, 8]);
    }

    #[test]
    fn test_b_k_is_u16_not_u8() {
        // PRD §2.4 item 3: b_k must be u16 (B=256 does not fit in u8)
        let b_k = vec![256usize, 256]; // B=256 exactly
        let full_dict: Vec<usize> = (0..256).collect();
        let bytes = serialize_cube_header(&CubeHeaderState {
            n: 2,
            b: 256,
            l: 100,
            count: 10,
            b_k: &b_k,
            map_scheme: MAP_SCHEME_RLE,
            value_scheme: VALUE_SCHEME_FIXED,
            w: 8,
            inverse_dict: &full_dict,
            axis_gap_counts: &[10, 8],
        });
        let (hdr, _) = parse_header(&bytes).unwrap();
        assert_eq!(
            hdr.b_k[0], 256,
            "b_k=256 must survive round-trip through u16"
        );
        assert_eq!(hdr.b_k[1], 256);
    }

    #[test]
    fn test_inverse_dict_is_u8() {
        // PRD §2.4 item 4: inverse_dict entries are u8 (0..255)
        let inverse_dict: Vec<usize> = (0..256).collect();
        let bytes = serialize_cube_header(&CubeHeaderState {
            n: 2,
            b: 256,
            l: 100,
            count: 10,
            b_k: &[256, 256],
            map_scheme: MAP_SCHEME_RLE,
            value_scheme: VALUE_SCHEME_FIXED,
            w: 8,
            inverse_dict: &inverse_dict,
            axis_gap_counts: &[10, 8],
        });
        let (hdr, _) = parse_header(&bytes).unwrap();
        assert_eq!(hdr.inverse_dict, inverse_dict);
        // n_distinct bytes for inverse_dict (not 2 bytes each)
        // So for 256 entries: 256 bytes, not 512
        // Verify the field offset implies u8 storage
        assert_eq!(hdr.n_distinct, 256);
    }

    #[test]
    fn test_parse_rejects_bad_magic() {
        let bad = b"XXXX rest of data padding here...";
        assert!(parse_header(bad).is_err());
    }

    #[test]
    fn test_parse_rejects_bad_version() {
        let mut bytes = serialize_raw_header(2, 256, 0);
        bytes[4] = 99; // bad version
        assert!(parse_header(&bytes).is_err());
    }

    #[test]
    fn test_map_scheme_packed_nibble_survives_header_round_trip() {
        let b_k = vec![256usize, 256];
        let inverse_dict = vec![1usize, 2];
        let axis_gap_counts = vec![5usize, 3];
        let bytes = serialize_cube_header(&CubeHeaderState {
            n: 2,
            b: 256,
            l: 400,
            count: 10,
            b_k: &b_k,
            map_scheme: MAP_SCHEME_PACKED_NIBBLE,
            value_scheme: VALUE_SCHEME_FIXED,
            w: 2,
            inverse_dict: &inverse_dict,
            axis_gap_counts: &axis_gap_counts,
        });
        let (hdr, _) = parse_header(&bytes).unwrap();
        assert_eq!(
            hdr.map_scheme, MAP_SCHEME_PACKED_NIBBLE,
            "PackedNibble scheme byte must survive header round-trip"
        );
    }

    #[test]
    fn test_value_scheme_rle_codes_survives_header_round_trip() {
        let b_k = vec![256usize, 256];
        let inverse_dict = vec![1usize, 2];
        let axis_gap_counts = vec![5usize, 3];
        let bytes = serialize_cube_header(&CubeHeaderState {
            n: 2,
            b: 256,
            l: 400,
            count: 10,
            b_k: &b_k,
            map_scheme: MAP_SCHEME_RLE,
            value_scheme: VALUE_SCHEME_RLE_CODES,
            w: 2,
            inverse_dict: &inverse_dict,
            axis_gap_counts: &axis_gap_counts,
        });
        let (hdr, _) = parse_header(&bytes).unwrap();
        assert_eq!(
            hdr.value_scheme, VALUE_SCHEME_RLE_CODES,
            "RleCodes value_scheme byte must survive header round-trip"
        );
    }

    #[test]
    fn test_serialize_round_trip_golden_vector() {
        // Golden vector: raw-mode, L=4, "ABCD"
        // Must produce: CB 52 49 4D 01 01 02 01 00 00 00 04
        //               magic(4) version(1) mode=1(1) N=2(1) B=256->0100(2) L=4->00000004(4)
        let bytes = serialize_raw_header(2, 256, 4);
        assert_eq!(&bytes[0..4], &[0xCB, 0x52, 0x49, 0x4D], "magic mismatch");
        assert_eq!(bytes[4], 1, "version");
        assert_eq!(bytes[5], MODE_RAW, "mode");
        assert_eq!(bytes[6], 2, "N");
        assert_eq!(&bytes[7..9], &[0x01, 0x00], "B=256 as u16 BE");
        assert_eq!(&bytes[9..13], &[0x00, 0x00, 0x00, 0x04], "L=4 as u32 BE");
        assert_eq!(bytes.len(), FIXED_HEADER_SIZE);
    }
}
