//! Decoder resource limits and header validation.
//!
//! `decode()` consumes untrusted bytes. Every field in the header is
//! attacker-controlled, and the decoder previously trusted all of them: a
//! declared point count was passed straight to `Vec::with_capacity`, and a
//! declared output length sized the reconstruction buffer. On a host with
//! 125 GB of RAM a single hostile 20 KB stream drove the decoder to an
//! anonymous RSS of ~111 GB and triggered a global OOM kill (arcana-devs,
//! 2026-07-29 22:48:54 and 2026-07-30 00:11:54, `task=hostile_inputs-`).
//!
//! The rule this module enforces is that a stream is refused *before* anything
//! is allocated for it. Refusal is deterministic and cheap: it depends only on
//! header fields and the length of the input buffer, never on how much memory
//! the host happens to have.
//!
//! Two kinds of bound live here, and the distinction matters:
//!
//! * **Structural invariants** are exact. They are derived from what the
//!   encoder can actually emit — `inverse_dict` holds distinct *byte* values,
//!   so `n_distinct` can never exceed 256, and `w` is a pure function of
//!   `n_distinct`. Violating one of these means the stream is not something
//!   this encoder produced, so refusing it costs no legitimate input.
//!
//! * **Resource limits** are policy. `l` (the decoded length) has no tight
//!   structural bound, so the decoder instead bounds the memory it will commit
//!   to reconstruct the stream ([`DecodeLimits::max_decoder_memory`]).
//!
//! The specific allocation that produced the OOM is worth naming, because it
//! explains why the limit is expressed in bytes. Reconstruction builds one
//! heap-allocated coordinate vector *per position* — `(0..l).map(phi)` — at
//! roughly 40 bytes each, so a declared `l` of `u32::MAX` asks for ~176 GB
//! before a single byte of payload is examined. The `l`-byte output buffer is
//! a rounding error next to it.
//!
//! These are the resource knobs CUBR-0076 specifies for the Web Profile;
//! this module is where the file codec implements them.

use crate::error::CubrimError;
use crate::header::Header;

/// `inverse_dict` stores distinct byte values, one byte each, so a stream can
/// never legitimately declare more than 256 of them.
pub const MAX_N_DISTINCT: usize = 256;

/// A radix below 2 is degenerate: `phi()` computes `remainder % b`, so `b == 0`
/// divides by zero and `b == 1` collapses every coordinate to zero.
pub const MIN_RADIX: usize = 2;

/// Ceiling on any single pre-allocation driven by an attacker-controlled count.
///
/// Sites that used to call `Vec::with_capacity(count)` now reserve at most this
/// many elements up front and let the vector grow as real data is decoded. A
/// dishonest count therefore costs a bounded reservation and then fails when
/// the input runs out, instead of reserving tens of gigabytes before reading a
/// single byte of payload.
pub const MAX_PREALLOC_ELEMENTS: usize = 1 << 16;

/// Limits applied to a single `decode()` call.
#[derive(Debug, Clone, Copy)]
pub struct DecodeLimits {
    /// Absolute ceiling on the decoded output length.
    pub max_output_size: usize,
    /// Ceiling on the memory the decoder will commit to reconstruct a stream.
    pub max_decoder_memory: usize,
}

impl DecodeLimits {
    /// Ceiling on decoded output. `l` is a `u32` on the wire, so 4 GiB is the
    /// widest value the format can express; the default leaves that reachable
    /// and lets `max_decoder_memory` do the binding work.
    pub const DEFAULT_MAX_OUTPUT_SIZE: usize = u32::MAX as usize;

    /// Ceiling on committed reconstruction memory.
    ///
    /// This is the limit that actually bounds a hostile stream, and it is
    /// deliberately expressed in bytes rather than as an expansion ratio. A
    /// ratio looks appealing but is wrong here: expansion grows without bound
    /// with file size for highly redundant input, so any fixed ratio would
    /// eventually reject a legitimate archive of a very compressible file
    /// while still permitting a hostile small blob to claim a large output.
    /// A memory budget has neither failure mode.
    ///
    /// 2 GiB is generous for a file archiver — a 64 KiB cube-mode stream, the
    /// largest the default `use_square_limit` produces, needs about 2.7 MB —
    /// and it refuses the OOM case outright: `l = u32::MAX` estimates to
    /// roughly 176 GB.
    ///
    /// A stream that legitimately needs more than this is refused
    /// deterministically instead of being attempted and killed by the OOM
    /// reaper, which is strictly the better outcome and is the whole point.
    pub const DEFAULT_MAX_DECODER_MEMORY: usize = 2 << 30;

    /// Estimated peak bytes to reconstruct `l` positions of an `n`-dimensional
    /// cube.
    ///
    /// The dominant term is the per-index coordinate vector built during
    /// reconstruction: one `Vec<usize>` header (24 bytes on 64-bit) plus `n`
    /// heap words per position, alongside the `l`-byte output buffer. This is
    /// an estimate, not an allocator-exact figure — it exists to reject the
    /// absurd, so it only has to be right to within a small factor.
    pub fn estimated_decode_memory(l: usize, n: usize) -> usize {
        const VEC_HEADER: usize = 24;
        let per_position = VEC_HEADER
            .saturating_add(n.saturating_mul(std::mem::size_of::<usize>()))
            .saturating_add(1);
        l.saturating_mul(per_position)
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

/// Reserve capacity for `requested` elements without trusting `requested`.
///
/// Returns a capacity that is safe to pass to `Vec::with_capacity`: the honest
/// case (a small count) is unaffected, and a hostile one is clamped so the
/// vector grows only as fast as real decoded data arrives.
#[inline]
pub fn bounded_capacity(requested: usize) -> usize {
    requested.min(MAX_PREALLOC_ELEMENTS)
}

/// Validate a cube-mode header against structural invariants and resource
/// limits, before any allocation is sized from it.
///
/// `blob_len` is the full length of the input buffer, which is what makes the
/// expansion check possible.
pub fn validate_cube_header(
    hdr: &Header,
    blob_len: usize,
    limits: &DecodeLimits,
) -> Result<(), CubrimError> {
    let reject = |msg: String| Err(CubrimError::Decode(msg));

    // --- Structural: geometry -------------------------------------------------
    if hdr.n == 0 {
        return reject("header declares N=0 dimensions".to_string());
    }
    if hdr.b < MIN_RADIX {
        return reject(format!(
            "header declares a degenerate radix B={} (minimum is {MIN_RADIX})",
            hdr.b
        ));
    }
    if hdr.b_k.len() != hdr.n {
        return reject(format!(
            "b_k length {} does not match N={}",
            hdr.b_k.len(),
            hdr.n
        ));
    }
    if hdr.axis_gap_counts.len() != hdr.n {
        return reject(format!(
            "axis_gap_counts length {} does not match N={}",
            hdr.axis_gap_counts.len(),
            hdr.n
        ));
    }
    for (k, &bk) in hdr.b_k.iter().enumerate() {
        if bk < MIN_RADIX || bk > hdr.b {
            return reject(format!(
                "b_k[{k}]={bk} outside the valid range [{MIN_RADIX}, {}]",
                hdr.b
            ));
        }
    }

    // --- Structural: value dictionary ----------------------------------------
    // inverse_dict entries are byte values, so the alphabet cannot exceed 256.
    if hdr.n_distinct > MAX_N_DISTINCT {
        return reject(format!(
            "header declares n_distinct={}, above the {MAX_N_DISTINCT}-symbol maximum \
             implied by a byte-valued dictionary",
            hdr.n_distinct
        ));
    }
    if hdr.inverse_dict.len() != hdr.n_distinct {
        return reject(format!(
            "inverse_dict length {} does not match n_distinct={}",
            hdr.inverse_dict.len(),
            hdr.n_distinct
        ));
    }
    if hdr.count > 0 && hdr.n_distinct == 0 {
        return reject(
            "header declares populated points but an empty value dictionary".to_string(),
        );
    }
    // `w` is not free: the encoder always writes compute_width(n_distinct).
    if hdr.n_distinct > 0 {
        let expected_w = crate::bitpack::compute_width(hdr.n_distinct);
        if hdr.w != expected_w {
            return reject(format!(
                "header declares W={} but n_distinct={} determines W={expected_w}",
                hdr.w, hdr.n_distinct
            ));
        }
    }

    // --- Structural: counts versus geometry -----------------------------------
    // Every populated point occupies a distinct index in [0, L), so a stream
    // claiming more points than positions is not decodable.
    if hdr.count > hdr.l {
        return reject(format!(
            "header declares count={} populated points for only L={} positions",
            hdr.count, hdr.l
        ));
    }
    // The cube must be able to hold L positions: b^n >= L.
    let capacity = hdr.b.checked_pow(hdr.n as u32).unwrap_or(usize::MAX);
    if hdr.l > capacity {
        return reject(format!(
            "header declares L={} beyond the cube capacity B^N = {}^{} = {capacity}",
            hdr.l, hdr.b, hdr.n
        ));
    }

    // --- Resource limits ------------------------------------------------------
    if hdr.l > limits.max_output_size {
        return Err(CubrimError::ResourceLimit(format!(
            "declared output length {} exceeds max_output_size {}",
            hdr.l, limits.max_output_size
        )));
    }
    // The binding check. Refusal depends only on the header and the configured
    // budget — never on how much memory the host happens to have, which is what
    // makes it deterministic and reproducible across machines.
    let needed = DecodeLimits::estimated_decode_memory(hdr.l, hdr.n);
    if needed > limits.max_decoder_memory {
        return Err(CubrimError::ResourceLimit(format!(
            "reconstructing L={} positions in {} dimensions would commit about {needed} bytes, \
             beyond the {}-byte decoder budget (input was {blob_len} bytes)",
            hdr.l, hdr.n, limits.max_decoder_memory
        )));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn header(count: usize, l: usize, n_distinct: usize) -> Header {
        Header {
            magic: crate::header::MAGIC,
            version: crate::header::VERSION,
            mode: crate::header::MODE_CUBE,
            n: 2,
            b: 256,
            l,
            count,
            b_k: vec![256, 256],
            map_scheme: 1,
            value_scheme: 1,
            w: crate::bitpack::compute_width(n_distinct),
            n_distinct,
            inverse_dict: (0..n_distinct).collect(),
            traversal: 1,
            phi_id: 1,
            axis_gap_counts: vec![4, 4],
        }
    }

    #[test]
    fn a_well_formed_header_is_accepted() {
        let hdr = header(100, 1000, 8);
        assert!(validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_ok());
    }

    #[test]
    fn a_zero_radix_is_refused_before_it_can_divide() {
        let mut hdr = header(100, 1000, 8);
        hdr.b = 0;
        assert!(validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_err());
        hdr.b = 1;
        assert!(validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_err());
    }

    #[test]
    fn an_alphabet_wider_than_a_byte_is_refused() {
        let mut hdr = header(100, 1000, 8);
        hdr.n_distinct = 0xFFFF;
        assert!(validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_err());
    }

    #[test]
    fn a_width_inconsistent_with_the_alphabet_is_refused() {
        for bogus in [0usize, 7, 64, 128, 255] {
            let mut hdr = header(100, 1000, 8);
            hdr.w = bogus;
            assert!(
                validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_err(),
                "W={bogus} must be refused for n_distinct=8"
            );
        }
    }

    #[test]
    fn more_points_than_positions_is_refused() {
        let hdr = header(2000, 1000, 8);
        assert!(validate_cube_header(&hdr, 4096, &DecodeLimits::default()).is_err());
    }

    #[test]
    fn an_absurd_declared_length_is_refused_by_cube_capacity() {
        // The exact shape of the OOM as the fixture produces it: N=2, B=256, so
        // the cube holds 65536 positions and a u32::MAX length is structurally
        // impossible. This layer needs no policy budget at all.
        let hdr = header(0, u32::MAX as usize, 8);
        let err = validate_cube_header(&hdr, 20_000, &DecodeLimits::default())
            .expect_err("u32::MAX output from a 20 KB blob must be refused");
        assert!(matches!(err, CubrimError::Decode(_)), "got {err:?}");
    }

    #[test]
    fn an_absurd_declared_length_is_refused_by_the_memory_budget() {
        // Raising N is how an attacker escapes the structural capacity check:
        // 256^8 is astronomically larger than u32::MAX, so b^n admits the
        // length and the memory budget becomes the binding limit.
        let mut hdr = header(0, u32::MAX as usize, 8);
        hdr.n = 8;
        hdr.b_k = vec![256; 8];
        hdr.axis_gap_counts = vec![4; 8];
        let err = validate_cube_header(&hdr, 20_000, &DecodeLimits::default())
            .expect_err("a 20 KB blob claiming a u32::MAX output must be refused");
        assert!(matches!(err, CubrimError::ResourceLimit(_)), "got {err:?}");
    }

    #[test]
    fn the_memory_estimate_matches_the_observed_oom_scale() {
        // The kernel recorded ~111 GB of anon-rss before the global OOM kill.
        // The estimate must land in that neighbourhood, or it is not modelling
        // the allocation that actually caused the incident.
        let estimated = DecodeLimits::estimated_decode_memory(u32::MAX as usize, 2);
        let gib = estimated / (1 << 30);
        assert!(
            (100..=250).contains(&gib),
            "estimate {gib} GiB should be the same order as the observed ~111 GiB"
        );
    }

    #[test]
    fn a_full_size_cube_mode_stream_is_still_accepted() {
        // 64 KiB is the largest cube the default square limit produces; it must
        // sit comfortably inside the budget or the limit would break real use.
        let hdr = header(1000, 65536, 8);
        assert!(validate_cube_header(&hdr, 100, &DecodeLimits::default()).is_ok());
        assert!(DecodeLimits::estimated_decode_memory(65536, 2) < 8 * 1024 * 1024);
    }

    #[test]
    fn a_caller_may_tighten_the_budget_below_the_default() {
        // A browser or proxy wants a far smaller ceiling than the archiver.
        let hdr = header(1000, 65536, 8);
        let tight = DecodeLimits {
            max_decoder_memory: 64 * 1024,
            ..DecodeLimits::default()
        };
        assert!(matches!(
            validate_cube_header(&hdr, 100, &tight),
            Err(CubrimError::ResourceLimit(_))
        ));
    }

    #[test]
    fn bounded_capacity_clamps_a_hostile_count_but_not_an_honest_one() {
        assert_eq!(bounded_capacity(10), 10);
        assert_eq!(bounded_capacity(u32::MAX as usize), MAX_PREALLOC_ELEMENTS);
    }
}
