// R1: N-dimensional cube with bounded edge.
// R2: Sparsity — only populated points stored.
//
// The cube C has dimensions b_0 x b_1 x ... x b_{N-1} where each b_k <= B.
// Input S (bytes) is mapped to cube coordinates via Phi (R1).
// Only populated points P (positions where values exist) are stored.
//
// v1-default:
//   - N=2, B=256 (mixed-radix Phi)
//   - Traversal: lexicographic order of coordinates (x_0, x_1, ...)
//   - b_k = B (all edges at maximum)

use crate::phi::{phi, phi_inv, compute_n_and_b, B_DEFAULT};

/// Sparse cube data produced by build_cube.
pub struct CubeData {
    pub n: usize,
    pub b: usize,
    pub b_k: Vec<usize>,
    pub l: usize,
    /// Populated points in lexicographic coordinate order: (coords, value)
    pub populated: Vec<(Vec<usize>, usize)>,
    pub count: usize,
    pub density: f64,
}

/// R1/R2: Build sparse cube from input bytes with explicit B and N.
///
/// `n` MUST satisfy `b^n >= l` (caller responsibility; use compute_n_and_b or clamp).
/// v1-default wrapper: `build_cube(data)` uses `B_DEFAULT` and `compute_n_and_b`.
pub fn build_cube_with_params(data: &[u8], b: usize, n: usize) -> CubeData {
    let l = data.len();

    debug_assert!(b > 0, "b must be > 0");
    debug_assert!(
        b.checked_pow(n as u32).unwrap_or(usize::MAX) >= l.max(1),
        "B^N={} < L={l}: phi non-injective — caller must clamp n",
        b.checked_pow(n as u32).unwrap_or(usize::MAX)
    );

    if l == 0 {
        return CubeData {
            n,
            b,
            b_k: vec![b; n],
            l: 0,
            populated: vec![],
            count: 0,
            density: 0.0,
        };
    }

    let b_k = vec![b; n];

    let mut points: Vec<(Vec<usize>, usize)> = data
        .iter()
        .enumerate()
        .map(|(i, &val)| (phi(i, n, b), val as usize))
        .collect();
    points.sort_by(|a, bv| a.0.cmp(&bv.0));

    let cube_volume = b.checked_pow(n as u32).unwrap_or(usize::MAX);
    let density = if cube_volume > 0 { l as f64 / cube_volume as f64 } else { 0.0 };

    CubeData { n, b, b_k, l, populated: points, count: l, density }
}

/// R1/R2: Build sparse cube from input bytes.
pub fn build_cube(data: &[u8]) -> CubeData {
    let l = data.len();
    let b = B_DEFAULT;

    if l == 0 {
        return CubeData {
            n: 2,
            b,
            b_k: vec![b; 2],
            l: 0,
            populated: vec![],
            count: 0,
            density: 0.0,
        };
    }

    let (n, b) = compute_n_and_b(l, b);
    let b_k = vec![b; n]; // v1: all edges at max B

    // Build (phi(i), data[i]) for each i, then sort by coords lex order
    let mut points: Vec<(Vec<usize>, usize)> = data
        .iter()
        .enumerate()
        .map(|(i, &val)| (phi(i, n, b), val as usize))
        .collect();

    // Sort by lexicographic order of coordinates
    points.sort_by(|a, b_| a.0.cmp(&b_.0));

    let cube_volume = b.pow(n as u32);
    let density = if cube_volume > 0 {
        l as f64 / cube_volume as f64
    } else {
        0.0
    };

    CubeData {
        n,
        b,
        b_k,
        l,
        populated: points,
        count: l,
        density,
    }
}

/// R1/R2 inverse: Reconstruct original byte sequence from sparse cube.
/// Uses Phi^{-1} to map coordinates back to original positions.
pub fn rebuild_from_cube(populated: &[(Vec<usize>, usize)], l: usize, b: usize) -> Vec<u8> {
    if l == 0 {
        return vec![];
    }

    let mut result = vec![0u8; l];
    for (coords, val) in populated {
        let i = phi_inv(coords, b);
        if i < l {
            result[i] = *val as u8;
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_cube_empty() {
        let cube = build_cube(&[]);
        assert_eq!(cube.l, 0);
        assert!(cube.populated.is_empty());
        assert_eq!(cube.count, 0);
    }

    #[test]
    fn test_build_cube_single_byte() {
        let cube = build_cube(&[0x42]);
        assert_eq!(cube.l, 1);
        assert_eq!(cube.count, 1);
        assert_eq!(cube.n, 2); // N_DEFAULT
        assert_eq!(cube.b, 256); // B_DEFAULT
        // phi(0, 2, 256) = (0, 0)
        assert_eq!(cube.populated[0].0, vec![0, 0]);
        assert_eq!(cube.populated[0].1, 0x42);
    }

    #[test]
    fn test_build_cube_lex_order() {
        // Verify that points are in lexicographic coordinate order
        // phi(0) = (0, 0), phi(1) = (1, 0), phi(256) = (0, 1)
        // Lex order: (0,0) < (0,1) < (1,0) -- so phi(0) < phi(256) < phi(1)
        let _data: Vec<u8> = vec![10, 20, 30]; // indices 0, 1, 2 with N=2, B=256
        // Add enough data to have interesting ordering: use index 256 which maps to (0,1)
        let mut big_data = vec![0u8; 257];
        big_data[0] = 0xAA;    // phi(0) = (0, 0)
        big_data[1] = 0xBB;    // phi(1) = (1, 0)
        big_data[256] = 0xCC;  // phi(256) = (0, 1) -- should sort BEFORE phi(1) in lex

        let cube = build_cube(&big_data);
        // Find entries for indices 0, 1, 256
        let entry_0 = cube.populated.iter().find(|(c, _)| c == &vec![0, 0]).unwrap();
        let entry_256 = cube.populated.iter().find(|(c, _)| c == &vec![0, 1]).unwrap();
        let entry_1 = cube.populated.iter().find(|(c, _)| c == &vec![1, 0]).unwrap();

        // Lex order: (0,0) < (0,1) < (1,0)
        let pos_0 = cube.populated.iter().position(|(c, _)| c == &entry_0.0).unwrap();
        let pos_256 = cube.populated.iter().position(|(c, _)| c == &entry_256.0).unwrap();
        let pos_1 = cube.populated.iter().position(|(c, _)| c == &entry_1.0).unwrap();
        assert!(pos_0 < pos_256, "phi(0)=(0,0) must precede phi(256)=(0,1) in lex order");
        assert!(pos_256 < pos_1, "phi(256)=(0,1) must precede phi(1)=(1,0) in lex order");
    }

    #[test]
    fn test_rebuild_from_cube_round_trip() {
        let original = b"hello world test data";
        let cube = build_cube(original);
        let recovered = rebuild_from_cube(&cube.populated, cube.l, cube.b);
        assert_eq!(recovered, original.as_ref());
    }

    #[test]
    fn test_cube_b_k_is_all_b() {
        // v1: all edges at max B=256
        let cube = build_cube(&[1u8, 2, 3, 4, 5]);
        for &bk in &cube.b_k {
            assert_eq!(bk, B_DEFAULT, "all b_k must equal B_DEFAULT in v1");
        }
    }

    #[test]
    fn test_cube_all_256_values_round_trip() {
        // All 256 distinct bytes -- V-AC-4 edge case
        let data: Vec<u8> = (0u8..=255).collect();
        let cube = build_cube(&data);
        let recovered = rebuild_from_cube(&cube.populated, cube.l, cube.b);
        assert_eq!(recovered, data);
    }

    #[test]
    fn test_build_cube_with_params_non_minimal_n() {
        // N=3 for a 100-byte input (minimal N=2 for B=256 since 256^2=65536 >= 100)
        let data: Vec<u8> = (0u8..100).collect();
        let cube = build_cube_with_params(&data, 256, 3);
        assert_eq!(cube.n, 3);
        assert_eq!(cube.b_k.len(), 3);
        // All populated points must have 3-component coords
        for (coords, _) in &cube.populated {
            assert_eq!(coords.len(), 3, "each point must have N=3 coords");
        }
        // Round-trip via rebuild_from_cube
        let recovered = rebuild_from_cube(&cube.populated, cube.l, cube.b);
        assert_eq!(recovered, data.to_vec(), "non-minimal N=3 round-trip failed");
    }

    #[test]
    fn test_build_cube_with_params_default_n_matches_build_cube() {
        // build_cube_with_params(data, B_DEFAULT, minimal_n) must equal build_cube(data)
        use crate::phi::compute_n_and_b;
        let data: Vec<u8> = (0u8..100).collect();
        let (n_min, _) = compute_n_and_b(data.len(), B_DEFAULT);
        let cube_param = build_cube_with_params(&data, B_DEFAULT, n_min);
        let cube_default = build_cube(&data);
        assert_eq!(cube_param.n, cube_default.n);
        assert_eq!(cube_param.populated, cube_default.populated,
            "build_cube_with_params with min N must produce same result as build_cube");
    }
}
