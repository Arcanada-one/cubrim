//! Deterministic resource policy for the classic cube/raw decoder path.
//!
//! Header fields are untrusted. Structural checks reject streams the encoder
//! cannot produce; policy checks let a caller choose a smaller output or
//! reconstruction-memory budget without relying on host RAM or allocator
//! behavior. Newer container modes retain their mode-specific fail-closed
//! guards in `codec`; this module covers the self-describing cube/raw header
//! exposed by `decode_with_limits`.

use crate::error::CubrimError;
use crate::header::{Header, MODE_CUBE, MODE_RAW};

/// The inverse dictionary stores byte values, so the alphabet cannot exceed
/// the 256 values representable by the wire format.
pub const MAX_N_DISTINCT: usize = 256;

/// A mixed-radix coordinate system with a radix below two is degenerate.
pub const MIN_RADIX: usize = 2;

/// Bound the total number of per-symbol context-map entries built from one
/// hostile T4/T5 header. This is independent of the cube reconstruction
/// budget because those maps are allocated before value decoding begins.
pub(crate) const MAX_CONTEXT_TABLE_ENTRIES: usize = 1 << 20;

/// Caller-selected limits for one classic cube/raw decode.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DecodeLimits {
    /// Maximum decoded output length.
    pub max_output_size: usize,
    /// Maximum estimated memory committed while reconstructing cube positions.
    pub max_decoder_memory: usize,
}

impl DecodeLimits {
    /// The wire length field is four bytes.
    pub const DEFAULT_MAX_OUTPUT_SIZE: usize = u32::MAX as usize;
    /// Two GiB is comfortably above ordinary single-cube archives and far below
    /// the multi-gigabyte hostile reconstruction that motivated this policy.
    pub const DEFAULT_MAX_DECODER_MEMORY: usize = 2 << 30;

    /// Conservative peak-memory estimate for the current cube reconstruction.
    ///
    /// The decoder's largest normal path holds a ranked `(u64, u32)` pair per
    /// position, one decoded value code, and one output byte. The estimate is
    /// intentionally conservative across value schemes and platforms; it is a
    /// policy floor, not an allocator-exact measurement.
    pub fn estimated_decode_memory(length: usize, dimensions: usize) -> usize {
        let per_position = std::mem::size_of::<(u64, u32)>()
            .saturating_add(std::mem::size_of::<usize>())
            .saturating_add(1)
            // Keep a dimension-dependent margin for coordinate/key work in
            // alternate decoder paths without resurrecting the old Vec<Vec>
            // allocation model.
            .saturating_add(dimensions.saturating_mul(std::mem::size_of::<usize>()));
        length.saturating_mul(per_position)
    }
}

impl Default for DecodeLimits {
    fn default() -> Self {
        Self {
            max_output_size: Self::DEFAULT_MAX_OUTPUT_SIZE,
            max_decoder_memory: Self::DEFAULT_MAX_DECODER_MEMORY,
        }
    }
}

/// Compute the order-1 context header span without allowing arithmetic wrap.
pub(crate) fn checked_context_header_span(
    context_count: usize,
    distinct_count: usize,
) -> Result<usize, CubrimError> {
    let entry_size = 2usize
        .checked_add(distinct_count)
        .ok_or_else(|| CubrimError::Decode("context table entry size overflow".into()))?;
    context_count
        .checked_mul(entry_size)
        .and_then(|span| span.checked_add(2))
        .ok_or_else(|| CubrimError::Decode("context table header span overflow".into()))
}

/// Reject context tables whose per-symbol maps would exceed the fixed decoder
/// safety budget before allocating one map per context.
pub(crate) fn validate_context_table_entries(
    context_count: usize,
    distinct_count: usize,
) -> Result<(), CubrimError> {
    let entries = context_count
        .checked_mul(distinct_count)
        .ok_or_else(|| CubrimError::ResourceLimit("context table entry count overflow".into()))?;
    if entries > MAX_CONTEXT_TABLE_ENTRIES {
        return Err(CubrimError::ResourceLimit(format!(
            "context tables request {entries} per-symbol entries, above the {MAX_CONTEXT_TABLE_ENTRIES}-entry decoder budget"
        )));
    }
    Ok(())
}

/// Validate the parsed classic cube/raw header before decoder allocations.
pub fn validate_header(hdr: &Header, limits: &DecodeLimits) -> Result<(), CubrimError> {
    if hdr.mode == MODE_RAW {
        return validate_output_limit(hdr.l, limits);
    }
    if hdr.mode != MODE_CUBE {
        return Ok(());
    }

    if hdr.n == 0 {
        return Err(CubrimError::Decode("header declares N=0 dimensions".into()));
    }
    if hdr.b < MIN_RADIX {
        return Err(CubrimError::Decode(format!(
            "header declares degenerate radix B={} (minimum is {MIN_RADIX})",
            hdr.b
        )));
    }
    if hdr.b_k.len() != hdr.n {
        return Err(CubrimError::Decode(format!(
            "b_k length {} does not match N={}",
            hdr.b_k.len(),
            hdr.n
        )));
    }
    if hdr.axis_gap_counts.len() != hdr.n {
        return Err(CubrimError::Decode(format!(
            "axis_gap_counts length {} does not match N={}",
            hdr.axis_gap_counts.len(),
            hdr.n
        )));
    }
    for (index, &radix) in hdr.b_k.iter().enumerate() {
        if !(MIN_RADIX..=hdr.b).contains(&radix) {
            return Err(CubrimError::Decode(format!(
                "b_k[{index}]={radix} outside [{MIN_RADIX}, {}]",
                hdr.b
            )));
        }
    }

    if hdr.n_distinct > MAX_N_DISTINCT {
        return Err(CubrimError::Decode(format!(
            "header declares n_distinct={} above {MAX_N_DISTINCT}",
            hdr.n_distinct
        )));
    }
    if hdr.inverse_dict.len() != hdr.n_distinct {
        return Err(CubrimError::Decode(format!(
            "inverse_dict length {} does not match n_distinct={}",
            hdr.inverse_dict.len(),
            hdr.n_distinct
        )));
    }
    if hdr.count > 0 && hdr.n_distinct == 0 {
        return Err(CubrimError::Decode(
            "header declares populated points with an empty value dictionary".into(),
        ));
    }
    if hdr.n_distinct > 0 {
        let expected_width = crate::bitpack::compute_width(hdr.n_distinct);
        if hdr.w != expected_width {
            return Err(CubrimError::Decode(format!(
                "header declares W={} but n_distinct={} determines W={expected_width}",
                hdr.w, hdr.n_distinct
            )));
        }
    }
    if hdr.count > hdr.l {
        return Err(CubrimError::Decode(format!(
            "header declares count={} for only L={} positions",
            hdr.count, hdr.l
        )));
    }
    if hdr.count != hdr.l {
        return Err(CubrimError::Decode(format!(
            "header declares count={} for L={} positions; cube streams must encode every position",
            hdr.count, hdr.l
        )));
    }

    let capacity = hdr.b.checked_pow(hdr.n as u32).unwrap_or(usize::MAX);
    if hdr.l > capacity {
        return Err(CubrimError::Decode(format!(
            "header declares L={} beyond cube capacity B^N={capacity}",
            hdr.l
        )));
    }

    validate_output_limit(hdr.l, limits)?;
    let estimated = DecodeLimits::estimated_decode_memory(hdr.l, hdr.n);
    if estimated > limits.max_decoder_memory {
        return Err(CubrimError::ResourceLimit(format!(
            "reconstructing L={} positions in {} dimensions needs about {} bytes, above the {}-byte decoder budget",
            hdr.l, hdr.n, estimated, limits.max_decoder_memory
        )));
    }
    Ok(())
}

fn validate_output_limit(length: usize, limits: &DecodeLimits) -> Result<(), CubrimError> {
    if length > limits.max_output_size {
        return Err(CubrimError::ResourceLimit(format!(
            "declared output length {} exceeds max_output_size {}",
            length, limits.max_output_size
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn context_header_span_is_checked() {
        assert_eq!(checked_context_header_span(3, 5).unwrap(), 23);
        assert!(checked_context_header_span(usize::MAX, usize::MAX).is_err());
    }

    #[test]
    fn context_table_entry_budget_is_checked() {
        let error = validate_context_table_entries(u16::MAX as usize, MAX_N_DISTINCT)
            .expect_err("hostile context maps must exceed the fixed entry budget");
        assert!(matches!(error, CubrimError::ResourceLimit(_)));
    }

    #[test]
    fn memory_estimate_is_monotonic() {
        assert!(
            DecodeLimits::estimated_decode_memory(100, 2)
                < DecodeLimits::estimated_decode_memory(101, 2)
        );
        assert!(
            DecodeLimits::estimated_decode_memory(100, 2)
                < DecodeLimits::estimated_decode_memory(100, 3)
        );
    }
}
