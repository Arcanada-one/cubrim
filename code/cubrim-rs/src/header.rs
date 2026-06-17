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
pub const VERSION: u8 = 1;

// Mode constants (R6/R7)
pub const MODE_CUBE: u8 = 0;
pub const MODE_RAW: u8 = 1;

// Scheme identifiers (R4, R5)
pub const MAP_SCHEME_RLE: u8 = 1;
pub const VALUE_SCHEME_FIXED: u8 = 1;

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

/// Serialize header to bytes.
/// For mode=1 (raw-store): only fixed fields + L are meaningful.
/// For mode=0 (cube): all fields required.
pub fn serialize_header(
    mode: u8,
    n: usize,
    b: usize,
    l: usize,
    // cube-mode only:
    count: usize,
    b_k: &[usize],
    w: usize,
    inverse_dict: &[usize],
    axis_gap_counts: &[usize],
) -> Vec<u8> {
    let mut out = Vec::new();

    // Fixed portion: magic(4) + version(1) + mode(1) + N(1) + B(2) + L(4) = 13 bytes
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(mode);
    out.push(n as u8);
    out.extend_from_slice(&(b as u16).to_be_bytes());
    out.extend_from_slice(&(l as u32).to_be_bytes());

    if mode == MODE_RAW {
        return out;
    }

    // mode == MODE_CUBE: append cube-specific fields
    // count (4B, uint32)
    out.extend_from_slice(&(count as u32).to_be_bytes());

    // b_k (N * 2B, uint16) — b_k can be 256 which doesn't fit in u8 (PRD §2.4 item 3)
    for &bk in b_k {
        out.extend_from_slice(&(bk as u16).to_be_bytes());
    }

    // map_scheme(1) + value_scheme(1) + W(1)
    out.push(MAP_SCHEME_RLE);
    out.push(VALUE_SCHEME_FIXED);
    out.push(w as u8);

    // n_distinct (2B, uint16)
    let n_distinct = inverse_dict.len();
    out.extend_from_slice(&(n_distinct as u16).to_be_bytes());

    // inverse_dict (n_distinct * 1B, uint8) — values are bytes 0..255
    for &v in inverse_dict {
        out.push(v as u8);
    }

    // traversal(1) + phi_id(1)
    out.push(TRAVERSAL_LEX);
    out.push(PHI_MIXED_RADIX);

    // axis_gap_counts (N * 2B, uint16)
    for &gc in axis_gap_counts {
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
        return Err(CubrimError::Decode("Header truncated at count field".to_string()));
    }
    hdr.count = u32::from_be_bytes([data[offset], data[offset+1], data[offset+2], data[offset+3]]) as usize;
    offset += 4;

    // b_k (N * 2B, uint16)
    if offset + n * 2 > data.len() {
        return Err(CubrimError::Decode("Header truncated at b_k field".to_string()));
    }
    for _ in 0..n {
        let bk = u16::from_be_bytes([data[offset], data[offset+1]]) as usize;
        hdr.b_k.push(bk);
        offset += 2;
    }

    // map_scheme(1) + value_scheme(1) + W(1)
    if offset + 3 > data.len() {
        return Err(CubrimError::Decode("Header truncated at scheme fields".to_string()));
    }
    hdr.map_scheme = data[offset];
    hdr.value_scheme = data[offset + 1];
    hdr.w = data[offset + 2] as usize;
    offset += 3;

    // n_distinct (2B)
    if offset + 2 > data.len() {
        return Err(CubrimError::Decode("Header truncated at n_distinct".to_string()));
    }
    hdr.n_distinct = u16::from_be_bytes([data[offset], data[offset+1]]) as usize;
    offset += 2;

    // inverse_dict (n_distinct * 1B)
    if offset + hdr.n_distinct > data.len() {
        return Err(CubrimError::Decode("Header truncated at inverse_dict".to_string()));
    }
    for i in 0..hdr.n_distinct {
        hdr.inverse_dict.push(data[offset + i] as usize);
    }
    offset += hdr.n_distinct;

    // traversal(1) + phi_id(1)
    if offset + 2 > data.len() {
        return Err(CubrimError::Decode("Header truncated at traversal/phi fields".to_string()));
    }
    hdr.traversal = data[offset];
    hdr.phi_id = data[offset + 1];
    offset += 2;

    // axis_gap_counts (N * 2B, uint16)
    if offset + n * 2 > data.len() {
        return Err(CubrimError::Decode("Header truncated at axis_gap_counts".to_string()));
    }
    for _ in 0..n {
        let gc = u16::from_be_bytes([data[offset], data[offset+1]]) as usize;
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
        let bytes = serialize_header(MODE_RAW, 2, 256, 1000, 0, &[], 0, &[], &[]);
        assert_eq!(&bytes[0..4], &MAGIC);
        assert_eq!(bytes[4], VERSION);
        assert_eq!(bytes[5], MODE_RAW);
        assert_eq!(bytes[6], 2); // N
        assert_eq!(u16::from_be_bytes([bytes[7], bytes[8]]), 256); // B
        assert_eq!(u32::from_be_bytes([bytes[9], bytes[10], bytes[11], bytes[12]]), 1000); // L

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

        let bytes = serialize_header(
            MODE_CUBE, 2, 256, 500, 42,
            &b_k, 2, &inverse_dict, &axis_gap_counts,
        );

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
        let bytes = serialize_header(MODE_CUBE, 2, 256, 100, 10, &b_k, 8, &(0..256).collect::<Vec<_>>(), &[10, 8]);
        let (hdr, _) = parse_header(&bytes).unwrap();
        assert_eq!(hdr.b_k[0], 256, "b_k=256 must survive round-trip through u16");
        assert_eq!(hdr.b_k[1], 256);
    }

    #[test]
    fn test_inverse_dict_is_u8() {
        // PRD §2.4 item 4: inverse_dict entries are u8 (0..255)
        let inverse_dict: Vec<usize> = (0..256).collect();
        let bytes = serialize_header(MODE_CUBE, 2, 256, 100, 10, &[256usize, 256], 8, &inverse_dict, &[10, 8]);
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
        let mut bytes = serialize_header(MODE_RAW, 2, 256, 0, 0, &[], 0, &[], &[]);
        bytes[4] = 99; // bad version
        assert!(parse_header(&bytes).is_err());
    }

    #[test]
    fn test_serialize_round_trip_golden_vector() {
        // Golden vector: raw-mode, L=4, "ABCD"
        // Must produce: CB 52 49 4D 01 01 02 01 00 00 00 04
        //               magic(4) version(1) mode=1(1) N=2(1) B=256->0100(2) L=4->00000004(4)
        let bytes = serialize_header(MODE_RAW, 2, 256, 4, 0, &[], 0, &[], &[]);
        assert_eq!(&bytes[0..4], &[0xCB, 0x52, 0x49, 0x4D], "magic mismatch");
        assert_eq!(bytes[4], 1, "version");
        assert_eq!(bytes[5], MODE_RAW, "mode");
        assert_eq!(bytes[6], 2, "N");
        assert_eq!(&bytes[7..9], &[0x01, 0x00], "B=256 as u16 BE");
        assert_eq!(&bytes[9..13], &[0x00, 0x00, 0x00, 0x04], "L=4 as u32 BE");
        assert_eq!(bytes.len(), FIXED_HEADER_SIZE);
    }
}
