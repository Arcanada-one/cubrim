// R1: N-dimensional cube with bounded edge, mixed-radix Phi (v1-default).
//
// Phi: index i in [0, L-1] -> coordinates (x_0, x_1, ..., x_{N-1})
//   where x_k = (i / B^k) mod B  (mixed-radix base-B decomposition)
// Phi^{-1}: (x_0, ..., x_{N-1}) -> i = sum(x_k * B^k)
//
// v1-default: N=2, B=256.
// Resolution criterion (OQ-1/OQ-3): a Phi giving higher locality beats this.

/// v1-default: base B = 256 (one byte per coordinate)
pub const B_DEFAULT: usize = 256;
/// v1-default: two dimensions
pub const N_DEFAULT: usize = 2;

/// R1: Mixed-radix decomposition of index into N coordinates, base B.
///
/// phi(i) = (i mod B, (i / B) mod B, ..., (i / B^{N-1}) mod B)
///
/// Bijective on [0, B^N - 1].
pub fn phi(index: usize, n: usize, b: usize) -> Vec<usize> {
    let mut coords = Vec::with_capacity(n);
    let mut remainder = index;
    for _ in 0..n {
        coords.push(remainder % b);
        remainder /= b;
    }
    coords
}

/// R1: Inverse mixed-radix: coordinates back to index.
///
/// phi_inv((x_0, x_1, ..., x_{N-1})) = sum(x_k * B^k)
pub fn phi_inv(coords: &[usize], b: usize) -> usize {
    let mut index = 0usize;
    let mut base = 1usize;
    for &x in coords {
        index += x * base;
        base *= b;
    }
    index
}

/// Compute minimum N such that B^N >= length.
/// v1-default is N=2; if length > B^2, N grows.
pub fn compute_n_and_b(length: usize, b: usize) -> (usize, usize) {
    if length == 0 {
        return (N_DEFAULT, b);
    }
    // Start at N_DEFAULT, grow until b^N >= length
    let mut n = N_DEFAULT;
    loop {
        let capacity = b.checked_pow(n as u32).unwrap_or(usize::MAX);
        if capacity >= length {
            break;
        }
        n += 1;
    }
    (n, b)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_phi_basic_n2_b256() {
        // phi(0) = (0, 0)
        assert_eq!(phi(0, 2, 256), vec![0, 0]);
        // phi(1) = (1, 0)
        assert_eq!(phi(1, 2, 256), vec![1, 0]);
        // phi(256) = (0, 1)  — first index that changes second coordinate
        assert_eq!(phi(256, 2, 256), vec![0, 1]);
        // phi(257) = (1, 1)
        assert_eq!(phi(257, 2, 256), vec![1, 1]);
    }

    #[test]
    fn test_phi_inv_basic() {
        assert_eq!(phi_inv(&[0, 0], 256), 0);
        assert_eq!(phi_inv(&[1, 0], 256), 1);
        assert_eq!(phi_inv(&[0, 1], 256), 256);
        assert_eq!(phi_inv(&[1, 1], 256), 257);
    }

    #[test]
    fn test_phi_round_trip_n2_b256() {
        // phi_inv(phi(i)) == i for all i in [0, B^2 - 1]
        let b = 256;
        let n = 2;
        for i in [0, 1, 127, 255, 256, 512, 65535] {
            let coords = phi(i, n, b);
            let recovered = phi_inv(&coords, b);
            assert_eq!(recovered, i, "phi_inv(phi({i})) failed");
        }
    }

    #[test]
    fn test_phi_lex_order() {
        // Key insight from PRD §2.4 item 8: phi(256) = (0,1) sorts BEFORE phi(1) = (1,0) in lex order
        let p256 = phi(256, 2, 256); // (0, 1)
        let p1 = phi(1, 2, 256); // (1, 0)
        assert!(
            p256 < p1,
            "phi(256)={p256:?} must be lex-before phi(1)={p1:?}"
        );
    }

    #[test]
    fn test_compute_n_and_b_empty() {
        let (n, b) = compute_n_and_b(0, 256);
        assert_eq!(n, N_DEFAULT);
        assert_eq!(b, 256);
    }

    #[test]
    fn test_compute_n_and_b_small() {
        // length <= 256^2 = 65536 -> N=2
        let (n, _) = compute_n_and_b(1, 256);
        assert_eq!(n, 2);
        let (n, _) = compute_n_and_b(65536, 256);
        assert_eq!(n, 2);
    }

    #[test]
    fn test_compute_n_and_b_large() {
        // length > 65536 -> N >= 3
        let (n, _) = compute_n_and_b(65537, 256);
        assert!(n >= 3, "n={n} should be >=3 for length>65536");
    }
}
