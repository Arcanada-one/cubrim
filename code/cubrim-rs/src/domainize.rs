// R8: bytes-as-is domainization (v1-default).
//
// v1-default: input V = raw bytes, no preprocessing, no domain assumptions.
// Round-trip is trivially guaranteed: domainize is identity, de_domainize is identity.
//
// Resolution criterion (OQ-5): a domainization giving lower density rho with higher
// locality on the corpus beats this baseline.

/// R8: Convert raw bytes to a list of integer values (0..255).
/// Identity function — no domain assumptions.
pub fn domainize(data: &[u8]) -> Vec<usize> {
    data.iter().map(|&b| b as usize).collect()
}

/// R8 inverse: Convert list of integers (0..255) back to bytes.
/// Identity function — trivially lossless.
pub fn de_domainize(values: &[usize]) -> Vec<u8> {
    values.iter().map(|&v| v as u8).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_domainize_round_trip() {
        // R8: bytes-as-is identity must be perfectly invertible
        let data: Vec<u8> = (0u8..=255).collect();
        let values = domainize(&data);
        let recovered = de_domainize(&values);
        assert_eq!(recovered, data);
    }

    #[test]
    fn test_domainize_empty() {
        assert_eq!(domainize(&[]), Vec::<usize>::new());
        assert_eq!(de_domainize(&[]), Vec::<u8>::new());
    }

    #[test]
    fn test_domainize_single_byte() {
        assert_eq!(domainize(&[0x42]), vec![0x42usize]);
        assert_eq!(de_domainize(&[0x42]), vec![0x42u8]);
    }

    #[test]
    fn test_domainize_preserves_byte_values() {
        // No mapping — each byte value survives as-is
        let data = vec![0u8, 127, 255, 128, 64, 1];
        let values = domainize(&data);
        assert_eq!(values, vec![0usize, 127, 255, 128, 64, 1]);
    }
}
