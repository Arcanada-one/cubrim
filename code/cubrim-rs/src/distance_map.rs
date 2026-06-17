// R3: Distance map (gap-to-next) encoding for populated point coordinates.
// R3.1: Sentinel -1 start; gap=1 means zero skipped slots.
//
// For each axis k, given the sorted coordinates of populated points along that axis,
// encode as gaps from sentinel x_k = -1:
//
//   gap_k^{(j)} = x_k^{(j)} - x_k^{(j-1)}    where x_k^{(-1)} = -1 (sentinel)
//
// Invariant (fail-closed):
//   1 <= gap_k <= b_k <= B
//   gap=0 is forbidden (two points cannot share the same slot in traversal order).
//   gap > b_k is forbidden (skip cannot exceed edge length).
//
// Decode: start at x_k = -1, then x_k += gap_k for each gap.
//
// Worked example (rulebook R3.1, 1D, b_k=8):
//   populated {0, 3, 7}
//   gaps: 0-(-1)=1, 3-0=3, 7-3=4  ->  D = (1, 3, 4)
//   decode: -1+1=0, 0+3=3, 3+4=7  ->  {0, 3, 7}  ✓

use crate::error::CubrimError;

/// R3/R3.1: Encode sorted coordinate list to gap sequence.
///
/// Sentinel x_k = -1 (virtual position before slot 0).
/// gap_k^{(j)} = coords[j] - coords[j-1]  (with coords[-1] = -1)
///
/// Invariant checks (fail-closed):
///   - coords must be strictly monotone (sorted ascending, no duplicates)
///   - all coords in [0, b_k-1]
///   - resulting gaps must satisfy 1 <= gap <= b_k
pub fn encode_axis_gaps(coords: &[usize], b_k: usize) -> Result<Vec<usize>, CubrimError> {
    if coords.is_empty() {
        return Ok(vec![]);
    }

    let mut gaps = Vec::with_capacity(coords.len());
    // sentinel is -1, represented as isize
    let mut prev: isize = -1;

    for &c in coords {
        if c >= b_k {
            return Err(CubrimError::GapInvariant(format!(
                "coordinate {c} out of range [0, {}] for b_k={b_k}",
                b_k - 1
            )));
        }
        let g = c as isize - prev;
        if g <= 0 {
            return Err(CubrimError::GapInvariant(format!(
                "gap invariant violated: gap={g} <= 0 at coord={c} (prev={prev}). \
                 Coordinates must be strictly increasing (no duplicates)."
            )));
        }
        if g as usize > b_k {
            return Err(CubrimError::GapInvariant(format!(
                "gap invariant violated: gap={g} > b_k={b_k} at coord={c}"
            )));
        }
        gaps.push(g as usize);
        prev = c as isize;
    }

    Ok(gaps)
}

/// R3.1 inverse: Decode gap sequence back to coordinate list.
///
/// Start: x_k = -1 (sentinel).
/// For each gap: x_k += gap_k.
pub fn decode_axis_gaps(gaps: &[usize]) -> Vec<usize> {
    let mut coords = Vec::with_capacity(gaps.len());
    let mut x: isize = -1; // sentinel start
    for &g in gaps {
        x += g as isize;
        coords.push(x as usize);
    }
    coords
}

/// R3.1: Validate gap sequence invariant: 1 <= gap <= b_k for all gaps.
pub fn validate_gaps(gaps: &[usize], b_k: usize) -> Result<(), CubrimError> {
    for (i, &g) in gaps.iter().enumerate() {
        if g < 1 {
            return Err(CubrimError::GapInvariant(format!(
                "gap[{i}]={g} < 1 (gap=0 forbidden; sentinel=-1 means gap=1 for slot 0)"
            )));
        }
        if g > b_k {
            return Err(CubrimError::GapInvariant(format!(
                "gap[{i}]={g} > b_k={b_k} (gap exceeds edge length)"
            )));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    // R3.1 WORKED EXAMPLE — must match rulebook §3.1 exactly
    #[test]
    fn test_r3_1_worked_example_encode() {
        // populated {0, 3, 7} with b_k=8 -> gaps (1, 3, 4)
        let gaps = encode_axis_gaps(&[0, 3, 7], 8).unwrap();
        assert_eq!(gaps, vec![1, 3, 4], "R3.1 worked example encode mismatch");
    }

    #[test]
    fn test_r3_1_worked_example_decode() {
        // D = (1, 3, 4) -> decode: -1+1=0, 0+3=3, 3+4=7 -> {0, 3, 7}
        let coords = decode_axis_gaps(&[1, 3, 4]);
        assert_eq!(coords, vec![0, 3, 7], "R3.1 worked example decode mismatch");
    }

    #[test]
    fn test_gap1_means_zero_skipped_slots() {
        // gap=1 means immediately adjacent — zero skipped slots
        let gaps = encode_axis_gaps(&[0, 1, 2], 4).unwrap();
        assert_eq!(gaps, vec![1, 1, 1], "gap=1 must mean no skip");
        assert_eq!(decode_axis_gaps(&gaps), vec![0, 1, 2]);
    }

    #[test]
    fn test_first_element_at_slot_0() {
        // First populated slot = 0 -> gap = 0 - (-1) = 1
        let gaps = encode_axis_gaps(&[0], 8).unwrap();
        assert_eq!(gaps, vec![1]);
        assert_eq!(decode_axis_gaps(&gaps), vec![0]);
    }

    #[test]
    fn test_first_element_at_slot_3() {
        // First populated slot = 3 -> gap = 3 - (-1) = 4, NOT 3
        let gaps = encode_axis_gaps(&[3], 8).unwrap();
        assert_eq!(gaps, vec![4], "Expected [4], got {gaps:?}");
        assert_eq!(decode_axis_gaps(&gaps), vec![3]);
    }

    #[test]
    fn test_round_trip_various_coords() {
        let test_cases = vec![
            (vec![0usize, 3, 7], 8usize),
            (vec![0, 1, 2, 3, 4, 5, 6, 7], 8),
            (vec![0, 255], 256),
            (vec![5], 256),
        ];
        for (coords, b_k) in test_cases {
            let gaps = encode_axis_gaps(&coords, b_k).unwrap();
            let recovered = decode_axis_gaps(&gaps);
            assert_eq!(recovered, coords, "round-trip failed for coords={coords:?}, b_k={b_k}");
        }
    }

    #[test]
    fn test_gap_invariant_rejects_zero_gap() {
        // gap=0 would mean duplicate coordinate — must fail
        // duplicate coords would produce gap=0
        let result = encode_axis_gaps(&[3, 3], 8);
        assert!(result.is_err(), "duplicate coords should produce error");
    }

    #[test]
    fn test_gap_invariant_rejects_out_of_range() {
        // coordinate >= b_k is out of range
        let result = encode_axis_gaps(&[8], 8);
        assert!(result.is_err(), "coord 8 with b_k=8 should fail");
    }

    #[test]
    fn test_validate_gaps_valid() {
        assert!(validate_gaps(&[1, 3, 4], 8).is_ok());
    }

    #[test]
    fn test_validate_gaps_rejects_zero() {
        assert!(validate_gaps(&[0, 3], 8).is_err());
    }

    #[test]
    fn test_validate_gaps_rejects_exceeds_bk() {
        assert!(validate_gaps(&[1, 9], 8).is_err());
    }

    #[test]
    fn test_empty_coords() {
        let gaps = encode_axis_gaps(&[], 8).unwrap();
        assert!(gaps.is_empty());
        assert!(decode_axis_gaps(&[]).is_empty());
    }
}
