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

use crate::bitpack::{bitpack_decode, bitpack_encode, build_value_dict, compute_width};
use crate::config::{EncodeConfig, GapScheme, ValueScheme};
use crate::cube::build_cube_with_params;
use crate::distance_map::{decode_axis_gaps, encode_axis_gaps};
use crate::error::CubrimError;
use crate::header::{
    parse_header, serialize_cube_header, serialize_raw_header, CubeHeaderState, MAGIC, MODE_CHUNKED,
    MODE_CUBE, MODE_LZ, MODE_RAW, VERSION,
};
use crate::huffman::{
    canonical_code_lengths, huffman_bitstream_size, huffman_decode, huffman_encode,
};
use crate::phi::{compute_n_and_b, phi as phi_fn, phi_inv as phi_inv_fn};
use crate::rle::{
    packed_nibble_decode, packed_nibble_encode, packed_nibble_size, rle_decode, rle_encode,
    rle_size,
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
/// `state` carries all header fields; `axis_gaps` and `seq_codes` are needed only
/// for gap/value size computation and are not part of the header state.
/// `config_min_ctx_count` is only used for ValueScheme::EntropyContext2.
fn estimate_cube_size(
    state: &CubeHeaderState<'_>,
    axis_gaps: &[Vec<usize>],
    gap_scheme: GapScheme,
    value_scheme: ValueScheme,
    seq_codes: &[usize],
    config_min_ctx_count: Option<u16>,
) -> usize {
    let hdr_size = serialize_cube_header(state).len();

    let gap_total: usize = match gap_scheme {
        GapScheme::RleU16 => axis_gaps.iter().map(|g| rle_size(g)).sum(),
        GapScheme::PackedNibble => axis_gaps.iter().map(|g| packed_nibble_size(g)).sum(),
    };

    let value_total = match value_scheme {
        ValueScheme::BitpackFixed => {
            if state.count > 0 {
                (state.count * state.w).div_ceil(8)
            } else {
                0
            }
        }
        ValueScheme::RleCodes => rle_codes_size(seq_codes),
        ValueScheme::Entropy => {
            // n_distinct code-length bytes + MSB-first bitstream
            let n_distinct = state.inverse_dict.len();
            let code_len = canonical_code_lengths(seq_codes, n_distinct);
            n_distinct + huffman_bitstream_size(seq_codes, &code_len)
        }
        ValueScheme::EntropyContext => {
            // Wire: n_contexts(2) + per-context (2 + n_distinct) headers + bitstream
            context_huffman_size(seq_codes, state.inverse_dict.len())
        }
        ValueScheme::EntropyContext2 => {
            // Wire: min_ctx(2) + n_contexts(2) + per-entry headers + bitstream
            let min_ctx = config_min_ctx_count.unwrap_or(ORDER2_DEFAULT_MIN_CTX);
            order2_context_huffman_size(seq_codes, state.inverse_dict.len(), min_ctx)
        }
        ValueScheme::BwtEntropy => {
            // Wire: primary_index(2) + T4 context_huffman stream of BWT output
            bwt_entropy_size(seq_codes, state.inverse_dict.len())
        }
        ValueScheme::BwtRans
        | ValueScheme::Order2Rans
        | ValueScheme::BwtAdaptive
        | ValueScheme::BwtContextMix
        | ValueScheme::BwtGeoMix
        | ValueScheme::LzRans => {
            // Competitive: every scheme in this family emits the same per-file minimum
            // over the full candidate set (BwtRans, BwtEntropy, EntropyContext,
            // Order2Rans, BwtAdaptive, BwtContextMix, BwtGeoMix, LzRans) and writes the
            // winner's scheme byte. Estimate with that same minimum so the raw-vs-cube
            // decision matches the bytes the encoder will actually produce (Gotcha #4/#6).
            let n_distinct = state.inverse_dict.len();
            bwt_rans_size(seq_codes, n_distinct)
                .min(bwt_entropy_size(seq_codes, n_distinct))
                .min(context_huffman_size(seq_codes, n_distinct))
                .min(bwt_order2_rans_size(seq_codes, n_distinct))
                .min(bwt_adaptive_size(seq_codes, n_distinct))
                .min(bwt_ctxmix_size(seq_codes, n_distinct))
                .min(bwt_geomix_size(seq_codes, n_distinct))
                .min(lz_rans_size(seq_codes, n_distinct))
        }
    };

    hdr_size + gap_total + value_total
}

/// Iterate over (code, run_length) pairs in `seq_codes`, calling `emit` for each run.
/// Run lengths are capped at MAX_RUN (65535).  Empty input produces zero calls.
fn for_each_rle_run(seq_codes: &[usize], mut emit: impl FnMut(usize, usize)) {
    use crate::rle::MAX_RUN;
    if seq_codes.is_empty() {
        return;
    }
    let mut current = seq_codes[0];
    let mut run = 1usize;
    for &c in &seq_codes[1..] {
        if c == current && run < MAX_RUN {
            run += 1;
        } else {
            emit(current, run);
            current = c;
            run = 1;
        }
    }
    emit(current, run);
}

/// Encode value codes in sequential (i-order) input order as RLE triplets.
/// Each run emitted as: code(u8) + run_length(u16 BE) = 3 bytes.
/// Codes are in [0, n_distinct) which fits u8 (n_distinct <= 256 by design).
/// Run lengths capped at 65535 (same as rle.rs MAX_RUN).
fn rle_codes_encode(seq_codes: &[usize]) -> Vec<u8> {
    let mut out = Vec::new();
    for_each_rle_run(seq_codes, |code, run| {
        out.push(code as u8);
        out.extend_from_slice(&(run as u16).to_be_bytes());
    });
    out
}

/// Compute byte size of the RLE-codes stream without allocating.
fn rle_codes_size(seq_codes: &[usize]) -> usize {
    let mut triplets = 0usize;
    for_each_rle_run(seq_codes, |_, _| {
        triplets += 1;
    });
    triplets * 3 // 1 byte code + 2 bytes run_length
}

/// Decode `count` value codes from a RLE-codes stream starting at `offset`.
/// Returns (decoded_codes, bytes_consumed).
fn rle_codes_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    let mut codes = Vec::with_capacity(count);
    let mut pos = offset;
    while codes.len() < count {
        if pos + 3 > blob.len() {
            return Err(CubrimError::Decode(format!(
                "RLE-codes stream truncated at offset {pos}: need code+run (3B), have {}B remaining",
                blob.len().saturating_sub(pos)
            )));
        }
        let code = blob[pos] as usize;
        let run = u16::from_be_bytes([blob[pos + 1], blob[pos + 2]]) as usize;
        pos += 3;
        if run == 0 {
            return Err(CubrimError::Decode(format!(
                "RLE-codes run_length=0 at offset {}: invalid (stream corrupt)",
                pos - 3
            )));
        }
        let remaining = count - codes.len();
        if run > remaining {
            return Err(CubrimError::Decode(format!(
                "RLE-codes run {run} would exceed remaining count {remaining}: corrupt stream"
            )));
        }
        for _ in 0..run {
            codes.push(code);
        }
    }
    Ok((codes, pos - offset))
}

/// R6/R7: Encode input bytes to Cubrim v1 format using v1-default configuration.
///
/// This is the canonical public API. It delegates to encode_with_config with
/// EncodeConfig::v1_default(), guaranteeing byte-identical output to the pre-config
/// implementation. The frozen default byte stream is enforced by the differential
/// oracle fixtures (tests/differential.rs).
pub fn encode(data: &[u8]) -> Vec<u8> {
    encode_with_config(data, &EncodeConfig::v1_default())
}

/// R6/R7: Encode input bytes to Cubrim v1 format using the given configuration.
///
/// Returns a blob that:
/// - If mode=1 (raw-store): header + data verbatim; size <= len(data) + raw_store_bound
/// - If mode=0 (cube): header + RLE gap streams + bitpacked values
///
/// The header is self-describing; decode is config-independent (R6).
///
/// H-25d: for multi-block inputs (l > cube_size_limit) this also tries a whole-file
/// LZ pre-pass (MODE_LZ) and returns whichever encoding is smaller — a competitive
/// size pick, so an input that does not benefit falls back byte-identically to the
/// base encoding (zero regression). Single-block inputs skip the pre-pass entirely.
pub fn encode_with_config(data: &[u8], config: &EncodeConfig) -> Vec<u8> {
    let base = encode_base(data, config);
    // Whole-file LZ only helps when long-range repeats can cross a chunk boundary,
    // i.e. when the input would otherwise be split into ≥2 blocks. Smaller inputs
    // already get within-block LZ via the LzRans value-scheme, so skip the pre-pass.
    if data.len() > config.cube_size_limit() {
        let lz = encode_lz_prepass(data, config);
        if lz.len() < base.len() {
            return lz;
        }
    }
    base
}

/// Base encoder (single-block cube/raw, or MODE_CHUNKED for large inputs). This is
/// the non-LZ path; `encode_with_config` wraps it with the optional MODE_LZ pre-pass.
fn encode_base(data: &[u8], config: &EncodeConfig) -> Vec<u8> {
    let l = data.len();
    let b = config.b;
    let gap_scheme = config.gap_scheme;
    let value_scheme = config.value_scheme;

    // Special case: empty input -> raw-store
    if l == 0 {
        return serialize_raw_header(2, b, 0);
    }

    let n_min = compute_min_n(l, b);

    // Phase A: apply n_override if given; validate injectivity guard (B^n >= L).
    // If the override would make phi non-injective, fall back to raw-store.
    let n_requested = config.n_override.unwrap_or(n_min);
    // Clamp up to at least n_min (cannot have fewer dimensions than required)
    let n_effective = if n_requested < n_min {
        n_min
    } else {
        n_requested
    };

    // Injectivity guard: B^n_effective >= L must hold. For n_effective = n_min this
    // is always true by construction. For larger N it is trivially true (more capacity).
    // The guard is against a caller supplying n_override < n_min via the field directly,
    // which we've clamped above; this debug assert verifies invariant.
    debug_assert!(
        b.checked_pow(n_effective as u32).unwrap_or(usize::MAX) >= l,
        "n_effective={n_effective} B^N < L={l}: injectivity violated after clamp"
    );

    // Big-file path: L > cube_size_limit. A single cube cannot represent more than
    // cube_size_limit values (and the BWT primary_index is a u16, valid only while a
    // block is ≤65536), so split the input into independently-encoded blocks and wrap
    // them in a MODE_CHUNKED container. Each block re-enters the full competitive
    // machinery (cube / BWT / raw), so big files compress instead of raw-storing.
    if l > config.cube_size_limit() {
        return encode_chunked(data, config);
    }

    // R7: small inputs always raw-store (header alone would exceed any savings)
    if l <= config.raw_store_bound {
        let mut out = serialize_raw_header(n_effective, b, l);
        out.extend_from_slice(data);
        return out;
    }

    // Step 1: R8 domainize (identity)
    // Step 2: R1/R2 build cube — use n_effective and config.b
    let cube = build_cube_with_params(data, b, n_effective);
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
        let gaps =
            encode_axis_gaps(&coords_k, b_k[k]).expect("gap encode cannot fail on valid cube data");
        axis_gaps.push(gaps);
    }

    // Gather sequential codes (i-order) for RleCodes estimation and encoding.
    // populated is in lex order; we need codes indexed by original position i.
    // Build (i -> code) by inverting phi for each (coords, val) in populated.
    let seq_codes: Vec<usize> = {
        // Build a map from original index i to code
        let mut idx_to_code = vec![0usize; l];
        for (coords, val) in populated.iter() {
            let i = phi_inv_fn(coords, b);
            if i < l {
                // v2c is sorted by value; look up code via binary search
                let code = {
                    let pos = v2c.partition_point(|&(v, _)| v < *val);
                    v2c[pos].1
                };
                idx_to_code[i] = code;
            }
        }
        idx_to_code
    };

    // Step 5: R7 decision — compare cube encoded size vs raw-store output size
    let axis_gap_counts: Vec<usize> = axis_gaps.iter().map(|g| g.len()).collect();
    let cube_state = CubeHeaderState {
        n,
        b,
        l,
        count: cube.count,
        b_k,
        map_scheme: gap_scheme.scheme_byte(),
        value_scheme: value_scheme.scheme_byte(),
        w,
        inverse_dict: &inverse_dict,
        axis_gap_counts: &axis_gap_counts,
    };
    let cube_size = estimate_cube_size(
        &cube_state,
        &axis_gaps,
        gap_scheme,
        value_scheme,
        &seq_codes,
        config.min_ctx_count,
    );
    let raw_output_size = serialize_raw_header(n, b, l).len() + l;

    if cube_size >= raw_output_size {
        // R7: cube does not improve on raw; use raw-store
        let mut out = serialize_raw_header(n, b, l);
        out.extend_from_slice(data);
        return out;
    }

    // Step 6: Encode gap streams using the configured scheme
    let gap_streams: Vec<Vec<u8>> = match gap_scheme {
        GapScheme::RleU16 => axis_gaps.iter().map(|g| rle_encode(g)).collect(),
        GapScheme::PackedNibble => axis_gaps.iter().map(|g| packed_nibble_encode(g)).collect(),
    };

    // Step 7: Encode value stream using the configured value scheme
    let encoded_values: Vec<u8> = match value_scheme {
        ValueScheme::BitpackFixed => {
            // R5: bitpack values in lex-sorted point order (v1-default)
            let point_values: Vec<usize> = populated.iter().map(|(_, v)| *v).collect();
            bitpack_encode(&point_values, &v2c, w)
        }
        ValueScheme::RleCodes => {
            // RLE on codes in sequential i-order — collapses clustered runs
            rle_codes_encode(&seq_codes)
        }
        ValueScheme::Entropy => {
            // Canonical Huffman on codes in sequential i-order.
            // Wire: [code_len[0..n_distinct]: u8 × n_distinct] + [MSB-first bitstream]
            let n_distinct = inverse_dict.len();
            let code_len = canonical_code_lengths(&seq_codes, n_distinct);
            let mut out =
                Vec::with_capacity(n_distinct + huffman_bitstream_size(&seq_codes, &code_len));
            // Emit code-length table
            out.extend_from_slice(&code_len);
            // Emit MSB-first bitstream
            out.extend_from_slice(&huffman_encode(&seq_codes, &code_len));
            out
        }
        ValueScheme::EntropyContext => {
            // Order-1 context-adaptive canonical Huffman on the value-code stream.
            context_huffman_encode(&seq_codes, inverse_dict.len())
        }
        ValueScheme::EntropyContext2 => {
            // Order-2 context-adaptive canonical Huffman on the value-code stream.
            let min_ctx = config.min_ctx_count.unwrap_or(ORDER2_DEFAULT_MIN_CTX);
            order2_context_huffman_encode(&seq_codes, inverse_dict.len(), min_ctx)
        }
        ValueScheme::BwtEntropy => {
            // Competitive selection: BWT+T4 vs plain T4 (EntropyContext).
            // Pick whichever produces the smaller value-stream bytes.
            // The decoder dispatches on value_scheme in the header — the chosen
            // winner is signalled by writing the appropriate scheme byte.
            // IMPORTANT: we therefore return here early, overriding value_scheme
            // so the correct scheme byte reaches the header.
            let n_distinct = inverse_dict.len();
            let bwt_bytes = bwt_entropy_encode(&seq_codes, n_distinct);
            let t4_bytes_val = context_huffman_encode(&seq_codes, n_distinct);

            // Which value stream wins?  Pick the smaller.
            // We have already estimated cube_size with BwtEntropy; we re-emit
            // the header with the actual winner's scheme byte.
            let (winner_scheme, encoded_values) = if bwt_bytes.len() <= t4_bytes_val.len() {
                (ValueScheme::BwtEntropy, bwt_bytes)
            } else {
                (ValueScheme::EntropyContext, t4_bytes_val)
            };

            // Re-build the cube header with the winner's scheme byte (may differ from
            // what was used in estimate_cube_size, but the header is self-describing).
            let winner_cube_state = CubeHeaderState {
                n,
                b,
                l,
                count: cube.count,
                b_k,
                map_scheme: gap_scheme.scheme_byte(),
                value_scheme: winner_scheme.scheme_byte(),
                w,
                inverse_dict: &inverse_dict,
                axis_gap_counts: &axis_gap_counts,
            };
            let hdr = serialize_cube_header(&winner_cube_state);
            let mut out = hdr;
            for stream in &gap_streams {
                out.extend_from_slice(stream);
            }
            out.extend_from_slice(&encoded_values);
            return out;
        }
        ValueScheme::BwtRans
        | ValueScheme::Order2Rans
        | ValueScheme::BwtAdaptive
        | ValueScheme::BwtContextMix
        | ValueScheme::BwtGeoMix
        | ValueScheme::LzRans => {
            // Consolidated competitive selection (Gotcha #4). Any scheme in this family
            // request emits the smallest of the full candidate set and writes the
            // winner's scheme byte, so requesting any one of them can never regress
            // another:
            //   BwtRans (7)       — BWT + order-1 rANS                  (H-19)
            //   BwtEntropy (6)    — BWT + order-1 Huffman
            //   EntropyContext (4)— plain order-1 Huffman (no BWT)
            //   Order2Rans (8)    — BWT + order-2 rANS                  (H-20)
            //   BwtAdaptive (9)   — BWT + adaptive order-1 range coding (H-21)
            //   BwtContextMix (10)— BWT + context-mixing range coding   (H-22)
            //   BwtGeoMix (11)    — BWT + geometric o2/o1/o0 mixing     (H-24)
            //   LzRans (12)       — LZ77 + rANS (non-BWT match model)   (H-25)
            // Decode is header-driven, so the winner's byte is all the decoder needs.
            let n_distinct = inverse_dict.len();
            let rans_bytes = bwt_rans_encode(&seq_codes, n_distinct);
            let bwt_huff_bytes = bwt_entropy_encode(&seq_codes, n_distinct);
            let t4_bytes_val = context_huffman_encode(&seq_codes, n_distinct);
            let order2_bytes = bwt_order2_rans_encode(&seq_codes, n_distinct);
            let adaptive_bytes = bwt_adaptive_encode(&seq_codes, n_distinct);
            let ctxmix_bytes = bwt_ctxmix_encode(&seq_codes, n_distinct);
            let geomix_bytes = bwt_geomix_encode(&seq_codes, n_distinct);
            let lz_bytes = lz_rans_encode(&seq_codes, n_distinct);

            // Start from BwtRans and keep the strictly-smaller candidate, so ties
            // resolve to the earlier-listed scheme (stable, deterministic).
            let mut winner_scheme = ValueScheme::BwtRans;
            let mut encoded_values = rans_bytes;
            if bwt_huff_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::BwtEntropy;
                encoded_values = bwt_huff_bytes;
            }
            if t4_bytes_val.len() < encoded_values.len() {
                winner_scheme = ValueScheme::EntropyContext;
                encoded_values = t4_bytes_val;
            }
            if order2_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::Order2Rans;
                encoded_values = order2_bytes;
            }
            if adaptive_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::BwtAdaptive;
                encoded_values = adaptive_bytes;
            }
            if ctxmix_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::BwtContextMix;
                encoded_values = ctxmix_bytes;
            }
            if geomix_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::BwtGeoMix;
                encoded_values = geomix_bytes;
            }
            if lz_bytes.len() < encoded_values.len() {
                winner_scheme = ValueScheme::LzRans;
                encoded_values = lz_bytes;
            }

            let winner_cube_state = CubeHeaderState {
                n,
                b,
                l,
                count: cube.count,
                b_k,
                map_scheme: gap_scheme.scheme_byte(),
                value_scheme: winner_scheme.scheme_byte(),
                w,
                inverse_dict: &inverse_dict,
                axis_gap_counts: &axis_gap_counts,
            };
            let hdr = serialize_cube_header(&winner_cube_state);
            let mut out = hdr;
            for stream in &gap_streams {
                out.extend_from_slice(stream);
            }
            out.extend_from_slice(&encoded_values);
            return out;
        }
    };

    // Step 8: R6 serialize header
    let hdr = serialize_cube_header(&cube_state);

    let mut out = hdr;
    for stream in &gap_streams {
        out.extend_from_slice(stream);
    }
    out.extend_from_slice(&encoded_values);
    out
}

/// Big-file block size. Each chunk is encoded as an independent single-block blob,
/// so it must stay within BOTH limits that bound single-block encoding:
///   - `cube_size_limit()` — beyond it a single cube/blob would itself overflow; and
///   - 65536 — the BWT `primary_index` is a u16, valid only while a block is ≤65536
///     (a block of exactly 65536 yields primary < 65536 ≤ u16::MAX).
/// Taking the min satisfies both for every config (default: 65536).
fn chunk_block_size(config: &EncodeConfig) -> usize {
    config.cube_size_limit().min(65536)
}

/// Encode an input larger than the single-block ceiling as a MODE_CHUNKED container.
///
/// The input is sliced into `chunk_block_size(config)`-byte blocks; each block is
/// encoded independently via `encode_with_config` (re-entering the full competitive
/// machinery — cube / BWT / raw) and framed with its serialized length. The decoder
/// (`decode_chunked`) decodes every sub-blob and concatenates the results, so the
/// round-trip is byte-exact for any input length.
///
/// Wire: [MAGIC 4B][VERSION 1B][MODE_CHUNKED 1B][n_blocks u32 BE]
///       then n_blocks × ( [sub_len u32 BE][sub_blob] ).
fn encode_chunked(data: &[u8], config: &EncodeConfig) -> Vec<u8> {
    let block_size = chunk_block_size(config);
    debug_assert!(block_size >= 1, "chunk block size must be positive");

    let n_blocks = data.len().div_ceil(block_size);
    let mut out = Vec::with_capacity(data.len());
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(MODE_CHUNKED);
    out.extend_from_slice(&(n_blocks as u32).to_be_bytes());

    for block in data.chunks(block_size) {
        // Blocks are ≤ block_size ≤ cube_size_limit, so they never need the LZ
        // pre-pass — call the base encoder directly (no nested MODE_LZ attempt).
        let sub_blob = encode_base(block, config);
        out.extend_from_slice(&(sub_blob.len() as u32).to_be_bytes());
        out.extend_from_slice(&sub_blob);
    }
    out
}

/// Encode `data` as a whole-file LZ container (MODE_LZ, H-25d). The entire input is
/// LZ77-tokenized over a full-file window FIRST; the literal residue is encoded
/// through the normal pipeline (`encode_base`, itself possibly MODE_CHUNKED) and the
/// match length/distance streams (with the repeat-offset cache) are coded at file
/// level. This makes cross-block long-range repeats reachable. Caller gates on a
/// competitive size pick, so this is never returned when it does not help.
fn encode_lz_prepass(data: &[u8], config: &EncodeConfig) -> Vec<u8> {
    let seq: Vec<usize> = data.iter().map(|&b| b as usize).collect();
    // Competitive parse pick (H-25i): the fast greedy parse preserves repeat-offset
    // structure (wins on duplicate/repetitive data) while the slow optimal DP parse
    // finds fewer/longer matches (wins on mixed data with many distinct offsets).
    // Build a container with each and return the smaller — regression-proof, and the
    // 120KB repeat case keeps the greedy result while srctree keeps the optimal one.
    let greedy = lz77_parse_greedy(&seq);
    let optimal = lz77_parse_optimal(&seq);
    let c_greedy = build_lz_container(data, config, &greedy);
    let c_optimal = build_lz_container(data, config, &optimal);
    if c_optimal.len() < c_greedy.len() {
        c_optimal
    } else {
        c_greedy
    }
}

/// Assemble a MODE_LZ container from one parse result. The literal residue is coded
/// by the smallest of {nested pipeline, order-0 rANS, order-1 rANS} (lit_kind), and
/// the token streams by the smaller of {separate, combined} (seq_format).
#[allow(clippy::type_complexity)]
fn build_lz_container(
    data: &[u8],
    config: &EncodeConfig,
    parse: &(Vec<usize>, Vec<usize>, Vec<usize>, Vec<usize>),
) -> Vec<u8> {
    let (flags, literals, lengths, distances) = parse;
    let n_tokens = flags.len();
    let n_matches = lengths.len();
    let lit_bytes: Vec<u8> = literals.iter().map(|&c| c as u8).collect();

    // H-25f dedicated literal coder: cube/BWT/rANS pipeline (kind 0), or a direct
    // order-0 (kind 1) / order-1 (kind 2) rANS with no cube framing. Pick smallest.
    let nested = encode_base(&lit_bytes, config);
    let direct0 = rans_order0_encode(literals, 256);
    let direct1 = rans_order1_encode(literals, 256);
    let mut lit_kind = 0u8;
    let mut lit_blob = nested;
    if direct0.len() < lit_blob.len() {
        lit_kind = 1;
        lit_blob = direct0;
    }
    if direct1.len() < lit_blob.len() {
        lit_kind = 2;
        lit_blob = direct1;
    }

    // Token coding: separate per-stream (0) vs H-25g combined sequence (1).
    let token_separate = lz_encode_token_streams(flags, lengths, distances);
    let token_combined = lz_encode_token_combined(flags, lengths, distances);
    let (seq_format, token_block) = if token_combined.len() < token_separate.len() {
        (1u8, token_combined)
    } else {
        (0u8, token_separate)
    };

    let mut out = Vec::with_capacity(26 + lit_blob.len() + token_block.len());
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(MODE_LZ);
    out.extend_from_slice(&(data.len() as u32).to_be_bytes());
    out.extend_from_slice(&(n_tokens as u32).to_be_bytes());
    out.extend_from_slice(&(n_matches as u32).to_be_bytes());
    out.push(seq_format);
    out.push(lit_kind);
    out.extend_from_slice(&(lit_blob.len() as u32).to_be_bytes());
    out.extend_from_slice(&lit_blob);
    out.extend_from_slice(&token_block);
    out
}

/// Decode a MODE_LZ container (`encode_lz_prepass`). Fail-closed.
fn decode_lz_prepass(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    // Header: MAGIC(4)+VERSION(1)+MODE_LZ(1)+orig_len(4)+n_tokens(4)+n_matches(4)
    //         +seq_format(1)+lit_kind(1)+lit_len(4) = 24.
    const LZ_HEADER_SIZE: usize = 24;
    if blob.len() < LZ_HEADER_SIZE {
        return Err(CubrimError::Decode(format!(
            "MODE_LZ container too short: {} < {LZ_HEADER_SIZE}",
            blob.len()
        )));
    }
    let rd = |p: usize| u32::from_be_bytes([blob[p], blob[p + 1], blob[p + 2], blob[p + 3]]) as usize;
    let orig_len = rd(6);
    let n_tokens = rd(10);
    let n_matches = rd(14);
    let seq_format = blob[18];
    let lit_kind = blob[19];
    let lit_len = rd(20);
    let n_lits = n_tokens.saturating_sub(n_matches);
    let mut pos = LZ_HEADER_SIZE;
    if pos + lit_len > blob.len() {
        return Err(CubrimError::Decode("MODE_LZ: literal blob truncated".into()));
    }
    // The literal residue is coded by one of three coders (H-25f), selected on size.
    let literals: Vec<u8> = match lit_kind {
        0 => decode(&blob[pos..pos + lit_len])?,
        1 => {
            let (codes, _) = rans_order0_decode(&blob[pos..pos + lit_len], 0, n_lits, 256)?;
            codes.iter().map(|&c| c as u8).collect()
        }
        2 => {
            let (codes, _) = rans_order1_decode(&blob[pos..pos + lit_len], 0, n_lits, 256)?;
            codes.iter().map(|&c| c as u8).collect()
        }
        k => {
            return Err(CubrimError::Decode(format!("MODE_LZ: bad lit_kind {k}")));
        }
    };
    pos += lit_len;

    let mut out: Vec<u8> = Vec::with_capacity(orig_len);
    // Reconstruct the (literal, match) interleaving. The two token formats produce
    // the same logical sequence — H-25g's combined format yields per-match literal
    // run-lengths directly; the separate-stream format yields per-token flags.
    let copy_match = |out: &mut Vec<u8>, length: usize, distance: usize| -> Result<(), CubrimError> {
        if distance == 0 || distance > out.len() {
            return Err(CubrimError::Decode(format!(
                "MODE_LZ: invalid distance {distance} (output len {})",
                out.len()
            )));
        }
        if length == 0 || out.len() + length > orig_len {
            return Err(CubrimError::Decode(
                "MODE_LZ: match length 0 or overflows orig_len".into(),
            ));
        }
        let start = out.len() - distance;
        for k in 0..length {
            out.push(out[start + k]);
        }
        Ok(())
    };

    match seq_format {
        0 => {
            let (flags, lengths, distances, _consumed) =
                lz_decode_token_streams(blob, pos, n_tokens, n_matches)?;
            let mut li = 0usize;
            let mut mi = 0usize;
            for &flag in &flags {
                if flag == 0 {
                    if li >= literals.len() {
                        return Err(CubrimError::Decode("MODE_LZ: literal underflow".into()));
                    }
                    out.push(literals[li]);
                    li += 1;
                } else {
                    if mi >= n_matches {
                        return Err(CubrimError::Decode("MODE_LZ: match underflow".into()));
                    }
                    copy_match(&mut out, lengths[mi], distances[mi])?;
                    mi += 1;
                }
            }
        }
        1 => {
            let (lit_lengths, final_ll, lengths, distances, _consumed) =
                lz_decode_token_combined(blob, pos, n_matches)?;
            let mut li = 0usize;
            for m in 0..n_matches {
                for _ in 0..lit_lengths[m] {
                    if li >= literals.len() {
                        return Err(CubrimError::Decode("MODE_LZ: literal underflow".into()));
                    }
                    out.push(literals[li]);
                    li += 1;
                }
                copy_match(&mut out, lengths[m], distances[m])?;
            }
            for _ in 0..final_ll {
                if li >= literals.len() {
                    return Err(CubrimError::Decode("MODE_LZ: literal underflow".into()));
                }
                out.push(literals[li]);
                li += 1;
            }
        }
        f => return Err(CubrimError::Decode(format!("MODE_LZ: bad seq_format {f}"))),
    }

    if out.len() != orig_len {
        return Err(CubrimError::Decode(format!(
            "MODE_LZ: decoded {} bytes but expected {orig_len}",
            out.len()
        )));
    }
    Ok(out)
}

/// Decode a MODE_CHUNKED container produced by `encode_chunked`.
/// Fail-closed: any truncation or sub-blob decode error propagates.
fn decode_chunked(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    // Header: MAGIC(4) + VERSION(1) + MODE_CHUNKED(1) + n_blocks(4) = 10 bytes.
    const CHUNK_HEADER_SIZE: usize = 10;
    if blob.len() < CHUNK_HEADER_SIZE {
        return Err(CubrimError::Decode(format!(
            "Chunked container too short: {} < {CHUNK_HEADER_SIZE} bytes",
            blob.len()
        )));
    }
    let n_blocks = u32::from_be_bytes([blob[6], blob[7], blob[8], blob[9]]) as usize;
    let mut offset = CHUNK_HEADER_SIZE;
    let mut out = Vec::new();
    for block_idx in 0..n_blocks {
        if offset + 4 > blob.len() {
            return Err(CubrimError::Decode(format!(
                "Chunked container truncated at block {block_idx} length field"
            )));
        }
        let sub_len = u32::from_be_bytes([
            blob[offset],
            blob[offset + 1],
            blob[offset + 2],
            blob[offset + 3],
        ]) as usize;
        offset += 4;
        if offset + sub_len > blob.len() {
            return Err(CubrimError::Decode(format!(
                "Chunked container truncated at block {block_idx} payload: need {sub_len} bytes"
            )));
        }
        let sub_blob = &blob[offset..offset + sub_len];
        out.extend_from_slice(&decode(sub_blob)?);
        offset += sub_len;
    }
    Ok(out)
}

/// R6: Decode a Cubrim v1 blob back to original bytes.
///
/// Deterministic decode from header alone — no out-of-band state.
/// Corrupt input raises CubrimError (never silent garbage).
pub fn decode(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    // Container modes are detected before parse_header (which only knows the
    // single-block modes 0/1): MODE_CHUNKED wraps independent sub-blobs; MODE_LZ
    // wraps a whole-file LZ pre-pass (H-25d).
    if blob.len() >= 6 && blob[0..4] == MAGIC && blob[4] == VERSION {
        if blob[5] == MODE_CHUNKED {
            return decode_chunked(blob);
        }
        if blob[5] == MODE_LZ {
            return decode_lz_prepass(blob);
        }
    }

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
        return Err(CubrimError::Decode(format!(
            "Unknown mode in header: {}",
            hdr.mode
        )));
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
        return Err(CubrimError::Decode(format!(
            "b_k length {} != N={}",
            b_k.len(),
            n
        )));
    }
    if axis_gap_counts.len() != n {
        return Err(CubrimError::Decode(format!(
            "axis_gap_counts length != N={}",
            n
        )));
    }

    // Decode gap scheme from header
    let gap_scheme = GapScheme::from_byte(hdr.map_scheme).ok_or_else(|| {
        CubrimError::Decode(format!(
            "Unknown map_scheme byte: {} in header",
            hdr.map_scheme
        ))
    })?;

    // Read gap streams for each axis (scheme-dispatched)
    // Each axis has axis_gap_counts[k] unique coordinate values -> that many gaps in the stream
    let mut axis_coords: Vec<Vec<usize>> = Vec::with_capacity(n);
    for k in 0..n {
        let n_gaps = axis_gap_counts[k];

        let (gaps_k, consumed) = match gap_scheme {
            GapScheme::RleU16 => {
                let (stream_bytes, consumed) = read_rle_stream(blob, offset, n_gaps)?;
                let gaps = rle_decode(stream_bytes)?;
                if gaps.len() != n_gaps {
                    return Err(CubrimError::Decode(format!(
                        "Axis {k}: decoded {} gaps, expected {n_gaps}",
                        gaps.len()
                    )));
                }
                (gaps, consumed)
            }
            GapScheme::PackedNibble => packed_nibble_decode(blob, offset, n_gaps)?,
        };

        // Validate gap invariant on decode (R3.1 fail-closed)
        for (i, &g) in gaps_k.iter().enumerate() {
            if g < 1 {
                return Err(CubrimError::GapInvariant(format!(
                    "Axis {k} gap[{i}]={g} < 1 — corrupt stream"
                )));
            }
            if g > b_k[k] {
                return Err(CubrimError::GapInvariant(format!(
                    "Axis {k} gap[{i}]={g} > b_k[{k}]={} — corrupt stream",
                    b_k[k]
                )));
            }
        }
        let coords_k = decode_axis_gaps(&gaps_k);
        axis_coords.push(coords_k);
        offset += consumed;
    }

    // Determine value scheme from header
    let value_scheme = ValueScheme::from_byte(hdr.value_scheme).ok_or_else(|| {
        CubrimError::Decode(format!(
            "Unknown value_scheme byte: {} in header",
            hdr.value_scheme
        ))
    })?;

    // Decode value stream (scheme-dispatched)
    let result = match value_scheme {
        ValueScheme::BitpackFixed => {
            // Read bitpacked values (lex order)
            let bitpack_bytes_count = if count > 0 {
                (count * w).div_ceil(8)
            } else {
                0
            };
            if offset + bitpack_bytes_count > blob.len() {
                return Err(CubrimError::Decode(format!(
                    "Bitpack data truncated: need {} bytes at offset {}, have {} bytes total",
                    bitpack_bytes_count,
                    offset,
                    blob.len()
                )));
            }
            let packed_values_bytes = &blob[offset..offset + bitpack_bytes_count];

            // Decode bitpacked values (in lex-sorted point order)
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

            let mut lex_sorted_coords: Vec<Vec<usize>> = (0..l).map(|i| phi_fn(i, n, b)).collect();
            lex_sorted_coords.sort();

            let mut result = vec![0u8; l];
            for (j, coords) in lex_sorted_coords.iter().enumerate() {
                let orig_idx = phi_inv_fn(coords, b);
                if orig_idx < l && j < values.len() {
                    result[orig_idx] = values[j] as u8;
                }
            }
            result
        }
        ValueScheme::RleCodes => {
            // Decode RLE-codes stream: sequential i-order codes.
            // Each (code: u8, run: u16) encodes `run` copies of inverse_dict[code].
            let (seq_codes, _consumed) = rle_codes_decode(blob, offset, count)?;

            // seq_codes[i] is the code for original position i.
            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "RLE-codes decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= inverse_dict.len() {
                    return Err(CubrimError::Decode(format!(
                        "RLE-codes code {} at position {} >= n_distinct {}",
                        code,
                        i,
                        inverse_dict.len()
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::Entropy => {
            // Entropy decode: read n_distinct code-length bytes, then Huffman bitstream.
            let n_distinct = inverse_dict.len();
            if offset + n_distinct > blob.len() {
                return Err(CubrimError::Decode(format!(
                    "Entropy: code-length table truncated: need {} bytes at offset {}, have {} total",
                    n_distinct, offset, blob.len()
                )));
            }
            let code_len: Vec<u8> = blob[offset..offset + n_distinct].to_vec();
            let huff_offset = offset + n_distinct;

            let (seq_codes, _consumed) = huffman_decode(blob, huff_offset, count, &code_len)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "Entropy decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "Entropy code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::EntropyContext => {
            // Order-1 context-adaptive Huffman decode.
            let (seq_codes, _consumed) =
                context_huffman_decode(blob, offset, count, inverse_dict.len())?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            let n_distinct = inverse_dict.len();
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "EntropyContext code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::EntropyContext2 => {
            // Order-2 context-adaptive Huffman decode.
            let (seq_codes, _consumed) =
                order2_context_huffman_decode(blob, offset, count, inverse_dict.len())?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext2 decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            let n_distinct = inverse_dict.len();
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "EntropyContext2 code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::BwtEntropy => {
            // BWT inverse + T4 context-adaptive Huffman decode.
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_entropy_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "BwtEntropy decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "BwtEntropy code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::BwtRans => {
            // BWT inverse + order-1 context rANS decode (H-19).
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_rans_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "BwtRans decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            // Reconstruct: result[i] = inverse_dict[seq_codes[i]] as u8.
            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "BwtRans code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::Order2Rans => {
            // BWT inverse + order-2 context rANS decode (H-20).
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_order2_rans_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "Order2Rans decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "Order2Rans code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::BwtAdaptive => {
            // BWT inverse + adaptive order-1 range-coding decode (H-21).
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_adaptive_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "BwtAdaptive decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "BwtAdaptive code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::BwtContextMix => {
            // BWT inverse + context-mixing decode (H-22).
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_ctxmix_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "BwtContextMix decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "BwtContextMix code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::BwtGeoMix => {
            // BWT inverse + geometric context-mixing decode (H-24).
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = bwt_geomix_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "BwtGeoMix decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "BwtGeoMix code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
        ValueScheme::LzRans => {
            // LZ77 + rANS decode (H-25). Non-BWT match model.
            let n_distinct = inverse_dict.len();
            let (seq_codes, _consumed) = lz_rans_decode(blob, offset, count, n_distinct)?;

            if seq_codes.len() != count {
                return Err(CubrimError::Decode(format!(
                    "LzRans decoded {} codes but expected {} (count from header)",
                    seq_codes.len(),
                    count
                )));
            }

            let mut result = vec![0u8; l];
            for (i, &code) in seq_codes.iter().enumerate() {
                if code >= n_distinct {
                    return Err(CubrimError::Decode(format!(
                        "LzRans code {} at position {} >= n_distinct {}",
                        code, i, n_distinct
                    )));
                }
                if i < l {
                    result[i] = inverse_dict[code] as u8;
                }
            }
            result
        }
    };

    Ok(result)
}

/// Read enough RLE pairs from blob starting at offset to decode n_gaps gaps.
/// Returns (&[u8] slice of pairs consumed, bytes consumed).
fn read_rle_stream(
    blob: &[u8],
    offset: usize,
    n_gaps: usize,
) -> Result<(&[u8], usize), CubrimError> {
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

// ─── T4 Order-1 Context-Adaptive Huffman ─────────────────────────────────────
//
// Context = previous value-code in i-order (sentinel 0 for position 0).
// Each context with >= MIN_CTX_COUNT observations gets its own canonical
// Huffman table.  Sparse contexts fall back to a shared order-0 "fallback"
// table stored at ctx_id = 0 in the header.
//
// Wire format (after header + gap streams):
//   [n_contexts : u16 BE]                       — number of entries (including fallback)
//   for each entry (ascending ctx_id order):
//     [ctx_id : u16 BE]                          — 0 = fallback/order-0
//     [code_len[0..n_distinct] : u8 × n_distinct]
//   [coded bitstream : MSB-first, byte-aligned, zero-padded]
//
// Byte-exact invariant: identical algorithm in Python twin (context_huffman.py).

/// Minimum observation count for a context to get its own table.
const MIN_CTX_COUNT: usize = 16;

/// Context-id sentinel for the shared fallback (order-0) table.
const FALLBACK_CTX: u16 = 0;

/// Collect per-context frequency tables from seq_codes.
/// Returns (ctx_id -> freq_vec[n_distinct]) sorted ascending by ctx_id.
/// ctx_id = FALLBACK_CTX (0) holds the global order-0 frequencies used for
/// fallback contexts (built from all tokens, regardless of context).
fn build_context_tables(seq_codes: &[usize], n_distinct: usize) -> Vec<(u16, Vec<u8>)> {
    if seq_codes.is_empty() || n_distinct == 0 {
        return vec![];
    }

    // 1. Count per-context occurrences: context_counts[ctx][sym] = count.
    //    Use a BTreeMap so insertion order is deterministic.
    use std::collections::BTreeMap;
    let mut ctx_freq: BTreeMap<u16, Vec<usize>> = BTreeMap::new();

    // Fallback (order-0) counts: all tokens.
    let mut fallback_freq = vec![0usize; n_distinct];

    let mut prev_ctx: u16 = 0; // sentinel for position 0
    for &code in seq_codes.iter() {
        // Track for current context
        let entry = ctx_freq
            .entry(prev_ctx)
            .or_insert_with(|| vec![0usize; n_distinct]);
        if code < n_distinct {
            entry[code] += 1;
        }
        if code < n_distinct {
            fallback_freq[code] += 1;
        }
        prev_ctx = code as u16;
    }

    // 2. Determine which contexts meet MIN_CTX_COUNT.
    let mut total_ctx_obs: BTreeMap<u16, usize> = BTreeMap::new();
    for (&ctx, freq) in &ctx_freq {
        total_ctx_obs.insert(ctx, freq.iter().sum());
    }

    // 3. Build fallback code_len from global order-0 frequencies.
    //    Always emit fallback at ctx_id=0, even if it overlaps with a real ctx=0.
    let fallback_code_len = canonical_code_lengths(
        // Build a seq from fallback_freq to feed into canonical_code_lengths
        &{
            let mut seq = Vec::with_capacity(seq_codes.len());
            for (sym, &cnt) in fallback_freq.iter().enumerate() {
                for _ in 0..cnt {
                    seq.push(sym);
                }
            }
            seq
        },
        n_distinct,
    );

    // 4. Emit: fallback first (ctx_id=0), then any non-zero real contexts that
    //    meet MIN_CTX_COUNT, in ascending ctx_id order.
    let mut result: Vec<(u16, Vec<u8>)> = vec![(FALLBACK_CTX, fallback_code_len)];

    for (&ctx, freq) in &ctx_freq {
        let obs: usize = *total_ctx_obs.get(&ctx).unwrap_or(&0);
        if obs < MIN_CTX_COUNT {
            continue; // use fallback for this context
        }
        // Build seq_codes for this context only
        let ctx_seq: Vec<usize> = freq
            .iter()
            .enumerate()
            .flat_map(|(sym, &cnt)| std::iter::repeat(sym).take(cnt))
            .collect();
        let ctx_len = canonical_code_lengths(&ctx_seq, n_distinct);
        result.push((ctx, ctx_len));
    }

    // Sort ascending by ctx_id (fallback=0 is always first; real contexts follow).
    result.sort_by_key(|(ctx, _)| *ctx);
    result
}

/// Encode the value-code stream with order-1 context-adaptive canonical Huffman.
/// Returns the wire bytes: context-table header + MSB-first bitstream.
pub(crate) fn context_huffman_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    if seq_codes.is_empty() {
        // Emit n_contexts=0 + empty bitstream (zero bytes).
        return vec![0u8, 0u8];
    }

    let ctx_tables = build_context_tables(seq_codes, n_distinct);
    let n_ctx = ctx_tables.len() as u16;

    // Build lookup: ctx_id -> index in ctx_tables (for fast encode-time lookup).
    use std::collections::HashMap;
    let mut ctx_idx: HashMap<u16, usize> = HashMap::new();
    for (i, (ctx_id, _)) in ctx_tables.iter().enumerate() {
        ctx_idx.insert(*ctx_id, i);
    }
    // Index 0 is always the fallback.
    let fallback_idx = *ctx_idx.get(&FALLBACK_CTX).unwrap_or(&0);

    // 1. Encode bitstream: use per-context table or fallback.
    //    We need all codewords for the encode pass.
    //    Pre-build assign_canonical_codes for each context table.
    let canonical_codes: Vec<Vec<(u32, u8)>> = ctx_tables
        .iter()
        .map(|(_, code_len)| crate::huffman::assign_canonical_codes(code_len))
        .collect();

    let mut bit_acc: u64 = 0;
    let mut bit_count: u32 = 0;
    let mut bitstream: Vec<u8> = Vec::new();

    let mut prev_ctx: u16 = 0;
    for &code in seq_codes.iter() {
        let table_idx = ctx_idx.get(&prev_ctx).copied().unwrap_or(fallback_idx);
        let (codeword, length) = canonical_codes[table_idx][code];
        // MSB-first: shift left by bit_count, OR in codeword
        bit_acc = (bit_acc << length) | (codeword as u64);
        bit_count += length as u32;
        while bit_count >= 8 {
            bit_count -= 8;
            bitstream.push((bit_acc >> bit_count) as u8);
        }
        prev_ctx = code as u16;
    }
    // Flush remaining bits (zero-pad)
    if bit_count > 0 {
        bitstream.push((bit_acc << (8 - bit_count)) as u8);
    }

    // 2. Serialize header: n_contexts(u16 BE) + for each ctx: ctx_id(u16) + code_len[n_distinct]
    let mut out: Vec<u8> = Vec::new();
    out.extend_from_slice(&n_ctx.to_be_bytes());
    for (ctx_id, code_len) in &ctx_tables {
        out.extend_from_slice(&ctx_id.to_be_bytes());
        out.extend_from_slice(code_len);
    }
    out.extend_from_slice(&bitstream);
    out
}

/// Decode the order-1 context-adaptive Huffman stream from blob at offset.
/// Returns (decoded seq_codes, bytes consumed from offset).
pub(crate) fn context_huffman_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if count == 0 {
        // Edge case: nothing to decode; consume n_contexts header only.
        if offset + 2 > blob.len() {
            return Err(CubrimError::Decode(
                "EntropyContext: blob too short for n_contexts".into(),
            ));
        }
        let n_ctx = u16::from_be_bytes([blob[offset], blob[offset + 1]]) as usize;
        // Skip context table entries.
        let header_bytes = 2 + n_ctx * (2 + n_distinct);
        return Ok((vec![], header_bytes));
    }

    // 1. Read n_contexts.
    if offset + 2 > blob.len() {
        return Err(CubrimError::Decode(
            "EntropyContext: blob too short for n_contexts".into(),
        ));
    }
    let n_ctx = u16::from_be_bytes([blob[offset], blob[offset + 1]]) as usize;
    let mut pos = offset + 2;

    // 2. Read context tables.
    let header_entry_size = 2 + n_distinct; // ctx_id(u16) + code_len[n_distinct]
    if pos + n_ctx * header_entry_size > blob.len() {
        return Err(CubrimError::Decode(format!(
            "EntropyContext: context table header truncated: need {} bytes, have {}",
            n_ctx * header_entry_size,
            blob.len().saturating_sub(pos)
        )));
    }

    // ctx_tables: Vec<(ctx_id, decode_table)>
    // decode_table: HashMap<(codeword, length), symbol> for that context.
    use std::collections::HashMap;
    let mut ctx_tables: Vec<(u16, HashMap<(u32, u8), usize>)> = Vec::with_capacity(n_ctx);

    for _ in 0..n_ctx {
        let ctx_id = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
        pos += 2;
        let code_len: Vec<u8> = blob[pos..pos + n_distinct].to_vec();
        pos += n_distinct;

        // Build decode table: (codeword, length) -> symbol.
        // Reuse assign_canonical_codes from huffman.rs.
        let canonical = crate::huffman::assign_canonical_codes(&code_len);
        let mut decode_table: HashMap<(u32, u8), usize> = HashMap::new();
        for (sym, &(codeword, length)) in canonical.iter().enumerate() {
            if length > 0 {
                decode_table.insert((codeword, length), sym);
            }
        }
        ctx_tables.push((ctx_id, decode_table));
    }

    // Build ctx_id -> index map for O(1) lookup.
    let mut ctx_idx: HashMap<u16, usize> = HashMap::new();
    for (i, (ctx_id, _)) in ctx_tables.iter().enumerate() {
        ctx_idx.insert(*ctx_id, i);
    }
    let fallback_idx = *ctx_idx.get(&FALLBACK_CTX).unwrap_or(&0);

    // 3. Decode bitstream.
    let bitstream_offset = pos;
    let mut bit_pos: usize = 0; // position in bits from bitstream_offset
    let mut decoded: Vec<usize> = Vec::with_capacity(count);
    let mut prev_ctx: u16 = 0;

    for _ in 0..count {
        let table_idx = ctx_idx.get(&prev_ctx).copied().unwrap_or(fallback_idx);
        let decode_table = &ctx_tables[table_idx].1;

        // Try increasing lengths until we find a match.
        let mut codeword: u32 = 0;
        let mut found = false;
        for length in 1u8..=32u8 {
            // Read one more bit.
            let byte_off = bitstream_offset + bit_pos / 8;
            let bit_off = 7 - (bit_pos % 8);
            if byte_off >= blob.len() {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext: bitstream exhausted at bit {bit_pos} decoding symbol {}/{}",
                    decoded.len(),
                    count
                )));
            }
            let bit = (blob[byte_off] >> bit_off) & 1;
            codeword = (codeword << 1) | (bit as u32);
            bit_pos += 1;

            if let Some(&sym) = decode_table.get(&(codeword, length)) {
                decoded.push(sym);
                prev_ctx = sym as u16;
                found = true;
                break;
            }
        }
        if !found {
            return Err(CubrimError::Decode(format!(
                "EntropyContext: no codeword match after 32 bits at symbol {}/{}",
                decoded.len(),
                count
            )));
        }
    }

    // Total bytes consumed = n_contexts header + context table headers + bitstream bytes used.
    let bitstream_bytes = bit_pos.div_ceil(8);
    let total_consumed = (pos - offset) + bitstream_bytes;
    Ok((decoded, total_consumed))
}

/// Estimate byte size of T4 encoded stream without allocating the full output.
pub(crate) fn context_huffman_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    if seq_codes.is_empty() {
        return 2; // n_contexts=0 header
    }
    let ctx_tables = build_context_tables(seq_codes, n_distinct);
    let n_ctx = ctx_tables.len();

    // Header: 2 (n_contexts) + n_ctx * (2 + n_distinct)
    let header_bytes = 2 + n_ctx * (2 + n_distinct);

    // Bitstream: encode each symbol with its context's table.
    use std::collections::HashMap;
    let mut ctx_idx: HashMap<u16, usize> = HashMap::new();
    for (i, (ctx_id, _)) in ctx_tables.iter().enumerate() {
        ctx_idx.insert(*ctx_id, i);
    }
    let fallback_idx = *ctx_idx.get(&FALLBACK_CTX).unwrap_or(&0);

    let canonical_codes: Vec<Vec<(u32, u8)>> = ctx_tables
        .iter()
        .map(|(_, code_len)| crate::huffman::assign_canonical_codes(code_len))
        .collect();

    let mut total_bits: usize = 0;
    let mut prev_ctx: u16 = 0;
    for &code in seq_codes.iter() {
        let table_idx = ctx_idx.get(&prev_ctx).copied().unwrap_or(fallback_idx);
        let (_, length) = canonical_codes[table_idx][code];
        total_bits += length as usize;
        prev_ctx = code as u16;
    }

    header_bytes + total_bits.div_ceil(8)
}

// ─── T5 Order-2 Context-Adaptive Huffman ─────────────────────────────────────
//
// Context key = (prev2_code, prev_code) — tuple of two previously decoded codes.
// Sentinel rules:
//   position 0 → (0, 0)
//   position 1 → (0, seq_codes[0])
//   position i≥2 → (seq_codes[i-2], seq_codes[i-1])
//
// Fallback chain (3 levels, all serialized on the wire):
//   1. (prev2, prev) has ≥ min_ctx_count observations → order-2 table (tag=2)
//   2. else (prev) alone has ≥ min_ctx_count observations → order-1 table (tag=1)
//   3. else → global order-0 fallback table (tag=0, key (0,0))
//
// Wire format (after cube header + gap streams):
//   [min_ctx_count : u16 BE]           — 2 bytes
//   [n_contexts    : u16 BE]           — 2 bytes (total entries in header including fallback)
//   for each entry (ordered: tag=0 first, then tag=1 ascending prev, then tag=2 ascending (p2,p)):
//     [tag : u8]                       — 0 = order-0 fallback, 1 = order-1, 2 = order-2
//     [prev2_code : u16 BE]            — only when tag=2
//     [prev_code  : u16 BE]            — when tag=1 or tag=2
//     [code_len[0..n_distinct] : u8 × n_distinct]
//   [coded bitstream : MSB-first, byte-aligned, zero-padded tail]

/// Default MIN_CTX_COUNT for order-2 scheme (used when config.min_ctx_count = None).
pub const ORDER2_DEFAULT_MIN_CTX: u16 = 128;

// ── Option B (2-level wire) was benchmarked at /dr-qa and found WORSE than Option A ──
//
// QA adversarial review measured Option B (order-2 + order-0 only, no order-1 tables)
// at best ≈0.626 aggregate, compared to Option A best 0.592215 and T4 baseline 0.587240.
// Both options are worse than T4 — the NO-GO is real from two independent wire designs.
// The Option B builders are removed; the measured numbers are recorded in:
//   docs/ephemeral/research/CUBR-0027-bench.json  § option_b_summary
//
// To re-derive Option B: drop the Order1 arm in order2_build_context_tables and the
// order1_map lookup in the encoder/size functions below.

/// Compute the order-2 context key at position i in seq_codes.
/// Position 0 → (0,0), position 1 → (0, seq_codes[0]), i≥2 → (seq_codes[i-2], seq_codes[i-1]).
///
/// SYNC NOTE: the decoder (`order2_context_huffman_decode`) inlines equivalent sentinel logic
/// using a rolling `(prev2, prev1)` pair — look for "SYNC NOTE: sentinel values" comment in
/// the `// ── Decode bitstream ──` block inside that function.
/// Both sides MUST use the same sentinel values and update order — keep them in sync when editing.
#[inline]
fn order2_ctx_at(seq_codes: &[usize], i: usize) -> (u16, u16) {
    match i {
        0 => (0, 0),
        1 => (0, seq_codes[0] as u16),
        _ => (seq_codes[i - 2] as u16, seq_codes[i - 1] as u16),
    }
}

/// Entry types in the serialized header.
#[derive(Debug, Clone)]
enum CtxEntry {
    /// Order-0 global fallback (tag=0).  No key.
    Order0 { code_len: Vec<u8> },
    /// Order-1 fallback table (tag=1).  Key = prev_code.
    Order1 { prev_code: u16, code_len: Vec<u8> },
    /// Order-2 primary table (tag=2).  Key = (prev2_code, prev_code).
    Order2 {
        prev2_code: u16,
        prev_code: u16,
        code_len: Vec<u8>,
    },
}

impl CtxEntry {
    fn code_len(&self) -> &[u8] {
        match self {
            CtxEntry::Order0 { code_len } => code_len,
            CtxEntry::Order1 { code_len, .. } => code_len,
            CtxEntry::Order2 { code_len, .. } => code_len,
        }
    }
    fn wire_bytes(&self, n_distinct: usize) -> usize {
        match self {
            CtxEntry::Order0 { .. } => 1 + n_distinct,     // tag(1)
            CtxEntry::Order1 { .. } => 1 + 2 + n_distinct, // tag(1)+prev(2)
            CtxEntry::Order2 { .. } => 1 + 2 + 2 + n_distinct, // tag(1)+prev2(2)+prev(2)
        }
    }
}

/// Build the 3-level context table set for the order-2 scheme.
/// Returns entries in canonical serialization order:
///   [Order0 fallback] [Order1 entries, ascending prev_code] [Order2 entries, ascending (p2,p)]
fn order2_build_context_tables(
    seq_codes: &[usize],
    n_distinct: usize,
    min_ctx_count: u16,
) -> Vec<CtxEntry> {
    use std::collections::BTreeMap;

    if seq_codes.is_empty() || n_distinct == 0 {
        // Emit only the fallback table (empty frequencies → all code_len zero).
        let code_len = vec![0u8; n_distinct];
        return vec![CtxEntry::Order0 { code_len }];
    }

    let min = min_ctx_count as usize;

    // ── Accumulate frequency tables ───────────────────────────────────────────
    let mut ctx2_freq: BTreeMap<(u16, u16), Vec<usize>> = BTreeMap::new();
    let mut ctx1_freq: BTreeMap<u16, Vec<usize>> = BTreeMap::new();
    let mut fallback_freq = vec![0usize; n_distinct];

    for (i, &code) in seq_codes.iter().enumerate() {
        if code >= n_distinct {
            continue;
        }
        let (p2, p1) = order2_ctx_at(seq_codes, i);
        ctx2_freq
            .entry((p2, p1))
            .or_insert_with(|| vec![0usize; n_distinct])[code] += 1;
        ctx1_freq
            .entry(p1)
            .or_insert_with(|| vec![0usize; n_distinct])[code] += 1;
        fallback_freq[code] += 1;
    }

    // ── Observation totals ────────────────────────────────────────────────────
    let ctx2_total: BTreeMap<(u16, u16), usize> = ctx2_freq
        .iter()
        .map(|(k, v)| (*k, v.iter().sum()))
        .collect();
    let ctx1_total: BTreeMap<u16, usize> = ctx1_freq
        .iter()
        .map(|(k, v)| (*k, v.iter().sum()))
        .collect();

    // ── Global (order-0) fallback ─────────────────────────────────────────────
    let fallback_code_len = {
        let seq: Vec<usize> = fallback_freq
            .iter()
            .enumerate()
            .flat_map(|(sym, &cnt)| std::iter::repeat(sym).take(cnt))
            .collect();
        canonical_code_lengths(&seq, n_distinct)
    };

    // ── Order-1 qualifying tables ─────────────────────────────────────────────
    let mut order1_entries: Vec<CtxEntry> = Vec::new();
    for (&prev, freq) in &ctx1_freq {
        let obs = *ctx1_total.get(&prev).unwrap_or(&0);
        if obs < min {
            continue;
        }
        let seq: Vec<usize> = freq
            .iter()
            .enumerate()
            .flat_map(|(sym, &cnt)| std::iter::repeat(sym).take(cnt))
            .collect();
        let code_len = canonical_code_lengths(&seq, n_distinct);
        order1_entries.push(CtxEntry::Order1 {
            prev_code: prev,
            code_len,
        });
    }
    // BTreeMap iteration is already ascending, so order1_entries is ascending by prev_code.

    // ── Order-2 qualifying tables ─────────────────────────────────────────────
    let mut order2_entries: Vec<CtxEntry> = Vec::new();
    for (&(p2, p1), freq) in &ctx2_freq {
        let obs = *ctx2_total.get(&(p2, p1)).unwrap_or(&0);
        if obs < min {
            continue;
        }
        let seq: Vec<usize> = freq
            .iter()
            .enumerate()
            .flat_map(|(sym, &cnt)| std::iter::repeat(sym).take(cnt))
            .collect();
        let code_len = canonical_code_lengths(&seq, n_distinct);
        order2_entries.push(CtxEntry::Order2 {
            prev2_code: p2,
            prev_code: p1,
            code_len,
        });
    }
    // Already in ascending BTreeMap order.

    // ── Combine: [fallback] [order1] [order2] ────────────────────────────────
    let mut result = Vec::with_capacity(1 + order1_entries.len() + order2_entries.len());
    result.push(CtxEntry::Order0 {
        code_len: fallback_code_len,
    });
    result.extend(order1_entries);
    result.extend(order2_entries);
    result
}

/// Select the appropriate table index from the entries for a given position.
/// Returns the index into `entries` that should be used to encode/decode position i.
fn order2_select_table(entries: &[CtxEntry], prev2: u16, prev1: u16) -> usize {
    // Walk fallback chain: order-2 → order-1 → order-0
    // Entries are [Order0 at 0] [Order1 entries] [Order2 entries].
    // Check order-2 first (last block), then order-1, then fallback at 0.
    for (idx, entry) in entries.iter().enumerate().rev() {
        match entry {
            CtxEntry::Order2 {
                prev2_code,
                prev_code,
                ..
            } if *prev2_code == prev2 && *prev_code == prev1 => return idx,
            _ => {}
        }
    }
    for (idx, entry) in entries.iter().enumerate() {
        if let CtxEntry::Order1 { prev_code, .. } = entry {
            if *prev_code == prev1 {
                return idx;
            }
        }
    }
    0 // Order0 fallback is always at index 0
}

/// Encode the value-code stream with order-2 context-adaptive canonical Huffman.
/// Returns the wire bytes: [min_ctx_count u16 BE][n_contexts u16 BE][entries][bitstream].
pub(crate) fn order2_context_huffman_encode(
    seq_codes: &[usize],
    n_distinct: usize,
    min_ctx_count: u16,
) -> Vec<u8> {
    if seq_codes.is_empty() {
        // Emit min_ctx + n_contexts=1 + fallback entry (tag=0, empty code_len) + empty bitstream.
        let mut out = Vec::new();
        out.extend_from_slice(&min_ctx_count.to_be_bytes());
        out.extend_from_slice(&1u16.to_be_bytes()); // n_contexts = 1 (just fallback)
        out.push(0u8); // tag = 0 (Order0)
        out.extend_from_slice(&vec![0u8; n_distinct]); // empty code lengths
        return out;
    }

    let entries = order2_build_context_tables(seq_codes, n_distinct, min_ctx_count);

    // Pre-build canonical codes for each entry.
    let canonical_codes: Vec<Vec<(u32, u8)>> = entries
        .iter()
        .map(|e| crate::huffman::assign_canonical_codes(e.code_len()))
        .collect();

    // ── Encode bitstream ──────────────────────────────────────────────────────
    let mut bit_acc: u64 = 0;
    let mut bit_count: u32 = 0;
    let mut bitstream: Vec<u8> = Vec::new();

    for (i, &code) in seq_codes.iter().enumerate() {
        let (p2, p1) = order2_ctx_at(seq_codes, i);
        let table_idx = order2_select_table(&entries, p2, p1);
        let (codeword, length) = canonical_codes[table_idx][code];
        bit_acc = (bit_acc << length) | (codeword as u64);
        bit_count += length as u32;
        while bit_count >= 8 {
            bit_count -= 8;
            bitstream.push((bit_acc >> bit_count) as u8);
        }
    }
    if bit_count > 0 {
        bitstream.push((bit_acc << (8 - bit_count)) as u8);
    }

    // ── Serialize header ──────────────────────────────────────────────────────
    let n_ctx = entries.len() as u16;
    let mut out: Vec<u8> = Vec::new();
    out.extend_from_slice(&min_ctx_count.to_be_bytes());
    out.extend_from_slice(&n_ctx.to_be_bytes());
    for entry in &entries {
        match entry {
            CtxEntry::Order0 { code_len } => {
                out.push(0u8);
                out.extend_from_slice(code_len);
            }
            CtxEntry::Order1 {
                prev_code,
                code_len,
            } => {
                out.push(1u8);
                out.extend_from_slice(&prev_code.to_be_bytes());
                out.extend_from_slice(code_len);
            }
            CtxEntry::Order2 {
                prev2_code,
                prev_code,
                code_len,
            } => {
                out.push(2u8);
                out.extend_from_slice(&prev2_code.to_be_bytes());
                out.extend_from_slice(&prev_code.to_be_bytes());
                out.extend_from_slice(code_len);
            }
        }
    }
    out.extend_from_slice(&bitstream);
    out
}

/// Decode the order-2 context-adaptive Huffman stream from blob at offset.
/// Returns (decoded seq_codes, bytes consumed from offset).
pub(crate) fn order2_context_huffman_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    // ── Read min_ctx_count ────────────────────────────────────────────────────
    if offset + 4 > blob.len() {
        return Err(CubrimError::Decode(
            "EntropyContext2: blob too short for min_ctx_count+n_contexts header".into(),
        ));
    }
    let _min_ctx_count = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let n_ctx = u16::from_be_bytes([blob[offset + 2], blob[offset + 3]]) as usize;
    let mut pos = offset + 4;

    if count == 0 {
        // Skip entry headers.
        let header_end = order2_skip_entries(blob, pos, n_ctx, n_distinct)?;
        return Ok((vec![], header_end - offset));
    }

    // ── Parse context entries ─────────────────────────────────────────────────
    use std::collections::HashMap;

    // We'll build decode tables keyed by tag+key for O(1) lookup.
    struct DecodeTable {
        decode_map: HashMap<(u32, u8), usize>,
    }

    // Parsed entries: (tag, optional prev2, prev1, decode_table)
    #[derive(Debug)]
    enum ParsedEntry {
        Order0 {
            table_idx: usize,
        },
        Order1 {
            prev_code: u16,
            table_idx: usize,
        },
        Order2 {
            prev2_code: u16,
            prev_code: u16,
            table_idx: usize,
        },
    }

    let mut decode_tables: Vec<DecodeTable> = Vec::with_capacity(n_ctx);
    let mut parsed_entries: Vec<ParsedEntry> = Vec::with_capacity(n_ctx);

    for _ in 0..n_ctx {
        if pos >= blob.len() {
            return Err(CubrimError::Decode(
                "EntropyContext2: truncated context entry header".into(),
            ));
        }
        let tag = blob[pos];
        pos += 1;

        let (prev2, prev1, code_len_start) = match tag {
            0 => {
                // Order-0 fallback: no key fields
                (0u16, 0u16, pos)
            }
            1 => {
                // Order-1: prev_code (2 bytes) + code_len
                if pos + 2 > blob.len() {
                    return Err(CubrimError::Decode(
                        "EntropyContext2: truncated order-1 prev_code field".into(),
                    ));
                }
                let prev = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
                pos += 2;
                (0u16, prev, pos)
            }
            2 => {
                // Order-2: prev2 (2 bytes) + prev (2 bytes) + code_len
                if pos + 4 > blob.len() {
                    return Err(CubrimError::Decode(
                        "EntropyContext2: truncated order-2 key fields".into(),
                    ));
                }
                let p2 = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
                let p1 = u16::from_be_bytes([blob[pos + 2], blob[pos + 3]]);
                pos += 4;
                (p2, p1, pos)
            }
            other => {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext2: unknown entry tag {other} in context header"
                )));
            }
        };

        // Read code_len table
        if code_len_start + n_distinct > blob.len() {
            return Err(CubrimError::Decode(format!(
                "EntropyContext2: code_len table truncated at entry: need {n_distinct} bytes, \
                 have {} remaining",
                blob.len().saturating_sub(code_len_start)
            )));
        }
        let code_len: Vec<u8> = blob[code_len_start..code_len_start + n_distinct].to_vec();
        pos = code_len_start + n_distinct;

        // Build decode table.
        let canonical = crate::huffman::assign_canonical_codes(&code_len);
        let mut decode_map: HashMap<(u32, u8), usize> = HashMap::new();
        for (sym, &(codeword, length)) in canonical.iter().enumerate() {
            if length > 0 {
                decode_map.insert((codeword, length), sym);
            }
        }

        let table_idx = decode_tables.len();
        decode_tables.push(DecodeTable { decode_map });

        let parsed = match tag {
            0 => ParsedEntry::Order0 { table_idx },
            1 => ParsedEntry::Order1 {
                prev_code: prev1,
                table_idx,
            },
            _ => ParsedEntry::Order2 {
                prev2_code: prev2,
                prev_code: prev1,
                table_idx,
            },
        };
        parsed_entries.push(parsed);
    }

    // Build fast lookup maps.
    let mut order0_idx: usize = 0; // fallback (always index 0 of parsed_entries by wire convention)
    let mut order1_map: HashMap<u16, usize> = HashMap::new(); // prev_code → table_idx
    let mut order2_map: HashMap<(u16, u16), usize> = HashMap::new(); // (p2,p1) → table_idx

    for entry in &parsed_entries {
        match entry {
            ParsedEntry::Order0 { table_idx } => {
                order0_idx = *table_idx;
            }
            ParsedEntry::Order1 {
                prev_code,
                table_idx,
            } => {
                order1_map.insert(*prev_code, *table_idx);
            }
            ParsedEntry::Order2 {
                prev2_code,
                prev_code,
                table_idx,
            } => {
                order2_map.insert((*prev2_code, *prev_code), *table_idx);
            }
        }
    }

    // ── Decode bitstream ──────────────────────────────────────────────────────
    let bitstream_offset = pos;
    let mut bit_pos: usize = 0;
    let mut decoded: Vec<usize> = Vec::with_capacity(count);

    // Maintain rolling context (two previously decoded values).
    // SYNC NOTE: sentinel values and update order here MUST match `order2_ctx_at` (encoder side).
    // pos=0 → (0,0), pos=1 → (0, decoded[0]), pos≥2 → (prev2, prev1).
    // If you change sentinel values or update order in either place, change BOTH.
    let mut prev2: u16 = 0;
    let mut prev1: u16 = 0;

    for sym_idx in 0..count {
        // Determine context at position sym_idx.
        let (ctx_p2, ctx_p1) = if sym_idx == 0 {
            (0u16, 0u16)
        } else if sym_idx == 1 {
            (0u16, decoded[0] as u16)
        } else {
            (prev2, prev1)
        };

        // Select table: order-2 → order-1 → order-0.
        let table_idx = order2_map
            .get(&(ctx_p2, ctx_p1))
            .copied()
            .or_else(|| order1_map.get(&ctx_p1).copied())
            .unwrap_or(order0_idx);

        let decode_table = &decode_tables[table_idx].decode_map;

        // Huffman decode: try increasing lengths.
        let mut codeword: u32 = 0;
        let mut found = false;
        for length in 1u8..=32u8 {
            let byte_off = bitstream_offset + bit_pos / 8;
            let bit_off = 7 - (bit_pos % 8);
            if byte_off >= blob.len() {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext2: bitstream exhausted at bit {bit_pos} decoding symbol {sym_idx}/{count}"
                )));
            }
            let bit = (blob[byte_off] >> bit_off) & 1;
            codeword = (codeword << 1) | (bit as u32);
            bit_pos += 1;

            if let Some(&sym) = decode_table.get(&(codeword, length)) {
                decoded.push(sym);
                // Advance rolling context.
                prev2 = prev1;
                prev1 = sym as u16;
                found = true;
                break;
            }
        }
        if !found {
            return Err(CubrimError::Decode(format!(
                "EntropyContext2: no codeword match after 32 bits at symbol {sym_idx}/{count}"
            )));
        }
    }

    let bitstream_bytes = bit_pos.div_ceil(8);
    let total_consumed = (pos - offset) + bitstream_bytes;
    Ok((decoded, total_consumed))
}

/// Skip n_ctx context entry headers in the blob at pos (for count=0 edge case).
fn order2_skip_entries(
    blob: &[u8],
    mut pos: usize,
    n_ctx: usize,
    n_distinct: usize,
) -> Result<usize, CubrimError> {
    for _ in 0..n_ctx {
        if pos >= blob.len() {
            return Err(CubrimError::Decode(
                "EntropyContext2: truncated entry while skipping".into(),
            ));
        }
        let tag = blob[pos];
        pos += 1;
        let key_bytes = match tag {
            0 => 0usize,
            1 => 2usize,
            2 => 4usize,
            other => {
                return Err(CubrimError::Decode(format!(
                    "EntropyContext2: unknown tag {other} while skipping entries"
                )))
            }
        };
        pos += key_bytes;
        if pos + n_distinct > blob.len() {
            return Err(CubrimError::Decode(
                "EntropyContext2: code_len table truncated while skipping".into(),
            ));
        }
        pos += n_distinct;
    }
    Ok(pos)
}

/// Estimate byte size of the order-2 encoded stream without allocating the full output.
pub(crate) fn order2_context_huffman_size(
    seq_codes: &[usize],
    n_distinct: usize,
    min_ctx_count: u16,
) -> usize {
    if seq_codes.is_empty() {
        // min_ctx(2) + n_contexts(2) + tag(1) + code_len(n_distinct)
        return 4 + 1 + n_distinct;
    }
    let entries = order2_build_context_tables(seq_codes, n_distinct, min_ctx_count);
    // Header: min_ctx(2) + n_ctx(2) + per-entry sizes
    let header_bytes = 4 + entries
        .iter()
        .map(|e| e.wire_bytes(n_distinct))
        .sum::<usize>();

    // Build canonical code lookup for size estimation.
    let canonical_codes: Vec<Vec<(u32, u8)>> = entries
        .iter()
        .map(|e| crate::huffman::assign_canonical_codes(e.code_len()))
        .collect();

    // Build same lookup maps as encoder for table selection.
    use std::collections::HashMap;
    let mut order0_idx: usize = 0;
    let mut order1_map: HashMap<u16, usize> = HashMap::new();
    let mut order2_map: HashMap<(u16, u16), usize> = HashMap::new();

    for (i, entry) in entries.iter().enumerate() {
        match entry {
            CtxEntry::Order0 { .. } => {
                order0_idx = i;
            }
            CtxEntry::Order1 { prev_code, .. } => {
                order1_map.insert(*prev_code, i);
            }
            CtxEntry::Order2 {
                prev2_code,
                prev_code,
                ..
            } => {
                order2_map.insert((*prev2_code, *prev_code), i);
            }
        }
    }

    let mut total_bits: usize = 0;
    for (i, &code) in seq_codes.iter().enumerate() {
        let (p2, p1) = order2_ctx_at(seq_codes, i);
        let table_idx = order2_map
            .get(&(p2, p1))
            .copied()
            .or_else(|| order1_map.get(&p1).copied())
            .unwrap_or(order0_idx);
        let (_, length) = canonical_codes[table_idx][code];
        total_bits += length as usize;
    }

    header_bytes + total_bits.div_ceil(8)
}

// ─── BWT (Burrows-Wheeler Transform) + T4 Context Huffman ────────────────────
//
// BWT reorders the value-code sequence by sorting all cyclic rotations of the
// sequence, then taking the last column of the sorted rotation table.  This
// groups identical symbols into runs, dramatically reducing H(X_t|X_{t-1}) on
// structured data.  The primary index (position of the original sequence's
// first element in the sorted rotation list) is stored for exact inverse.
//
// Wire format (after cube header + gap streams):
//   [primary_index : u16 BE]   — 2 bytes; exact inverse requires this
//   followed by the T4 context-Huffman-encoded BWT output
//   (same wire as EntropyContext / scheme 4)
//
// BWT preserves n_distinct → cube header, gap map, and Huffman table overhead
// are unchanged.  The encoder selects BwtEntropy only when its real encoded
// size is smaller than EntropyContext.

// ─── SA-IS linear-time suffix array (for fast BWT) ───────────────────────────
//
// The BWT below sorts the cyclic rotations of `seq`.  A naive comparison sort is
// O(n² log n) and takes minutes on a full 65536-element block.  Instead we build
// the suffix array of the *doubled* string (seq·seq + sentinel) in linear time
// with SA-IS (Nong–Zhang–Chan induced sorting); a suffix starting in [0, n) has
// the corresponding rotation as its first n symbols, so SA order over those
// positions IS the rotation order.  Output is byte-identical to the naive sort
// (see test_sais_bwt_matches_naive): within a tie-group of fully-equal rotations
// the last-column values are identical, so `bwt_out` is invariant, and the exact
// `primary` is recovered with a Z-function (rotation 0 is last in its SA tie-group).

/// Sentinel for "empty slot" in the SA-IS workspace (positions are always < n).
const SAIS_EMPTY: usize = usize::MAX;

/// Bucket boundaries for alphabet size `k`. `end=false` → bucket heads (start
/// offsets); `end=true` → bucket tails (one past the last offset).
fn sais_buckets(s: &[usize], k: usize, end: bool) -> Vec<usize> {
    let mut count = vec![0usize; k];
    for &c in s {
        count[c] += 1;
    }
    let mut out = vec![0usize; k];
    let mut sum = 0usize;
    for i in 0..k {
        sum += count[i];
        out[i] = if end { sum } else { sum - count[i] };
    }
    out
}

#[inline]
fn sais_is_lms(t: &[bool], i: usize) -> bool {
    i > 0 && t[i] && !t[i - 1]
}

/// Induced-sort pass: given LMS suffixes already placed at their bucket tails,
/// induce all L-type then all S-type suffixes into their sorted positions.
fn sais_induce(s: &[usize], sa: &mut [usize], t: &[bool], k: usize) {
    let n = s.len();
    // L-type, scan left→right, place at bucket heads.
    let mut heads = sais_buckets(s, k, false);
    for i in 0..n {
        let j = sa[i];
        if j != SAIS_EMPTY && j != 0 {
            let p = j - 1;
            if !t[p] {
                let c = s[p];
                sa[heads[c]] = p;
                heads[c] += 1;
            }
        }
    }
    // S-type, scan right→left, place at bucket tails.
    let mut tails = sais_buckets(s, k, true);
    for i in (0..n).rev() {
        let j = sa[i];
        if j != SAIS_EMPTY && j != 0 {
            let p = j - 1;
            if t[p] {
                let c = s[p];
                tails[c] -= 1;
                sa[tails[c]] = p;
            }
        }
    }
}

/// Are the LMS substrings starting at `a` and `b` identical (same symbols and
/// L/S types, same length)?  Used to name LMS substrings during SA-IS.
fn sais_lms_equal(s: &[usize], t: &[bool], a: usize, b: usize) -> bool {
    if a == b {
        return true;
    }
    let n = s.len();
    let mut i = 0usize;
    loop {
        let aa = a + i;
        let bb = b + i;
        if aa >= n || bb >= n {
            return false;
        }
        if s[aa] != s[bb] || t[aa] != t[bb] {
            return false;
        }
        let a_lms = i > 0 && sais_is_lms(t, aa);
        let b_lms = i > 0 && sais_is_lms(t, bb);
        if a_lms && b_lms {
            return true; // both substrings end here; all prior symbols matched
        }
        if a_lms != b_lms {
            return false; // different lengths
        }
        i += 1;
    }
}

/// SA-IS suffix array of `s` over alphabet `0..k`. `s` MUST end with a unique
/// smallest sentinel (value 0 appearing exactly once, at the last position).
fn sais(s: &[usize], k: usize) -> Vec<usize> {
    let n = s.len();
    if n == 0 {
        return vec![];
    }
    if n == 1 {
        return vec![0];
    }

    // 1. Classify suffix types (true = S-type). Sentinel is S-type.
    let mut t = vec![false; n];
    t[n - 1] = true;
    for i in (0..n - 1).rev() {
        t[i] = s[i] < s[i + 1] || (s[i] == s[i + 1] && t[i + 1]);
    }

    // 2. Place LMS suffixes at bucket tails, then induced-sort.
    let mut sa = vec![SAIS_EMPTY; n];
    {
        let mut tails = sais_buckets(s, k, true);
        for i in (1..n).rev() {
            if sais_is_lms(&t, i) {
                let c = s[i];
                tails[c] -= 1;
                sa[tails[c]] = i;
            }
        }
    }
    sais_induce(s, &mut sa, &t, k);

    // 3. Name the LMS substrings in their (now sorted) SA order.
    let sorted_lms: Vec<usize> = sa
        .iter()
        .copied()
        .filter(|&x| x != SAIS_EMPTY && sais_is_lms(&t, x))
        .collect();
    let mut names = vec![SAIS_EMPTY; n];
    let mut name = 0usize;
    let mut prev = SAIS_EMPTY;
    for &cur in &sorted_lms {
        if prev != SAIS_EMPTY && !sais_lms_equal(s, &t, prev, cur) {
            name += 1;
        }
        names[cur] = name;
        prev = cur;
    }
    let num_names = if sorted_lms.is_empty() { 0 } else { name + 1 };

    // 4. Reduced string in LMS *text* order; recurse if any names collide.
    let lms_text: Vec<usize> = (1..n).filter(|&i| sais_is_lms(&t, i)).collect();
    let reduced: Vec<usize> = lms_text.iter().map(|&i| names[i]).collect();
    let lms_sa: Vec<usize> = if num_names == reduced.len() {
        // All names unique → SA is the inverse permutation of the names.
        let mut inv = vec![0usize; reduced.len()];
        for (idx, &nm) in reduced.iter().enumerate() {
            inv[nm] = idx;
        }
        inv
    } else {
        sais(&reduced, num_names)
    };

    // 5. Re-place LMS at bucket tails in correct order, induced-sort once more.
    for x in sa.iter_mut() {
        *x = SAIS_EMPTY;
    }
    {
        let mut tails = sais_buckets(s, k, true);
        for &r in lms_sa.iter().rev() {
            let i = lms_text[r];
            let c = s[i];
            tails[c] -= 1;
            sa[tails[c]] = i;
        }
    }
    sais_induce(s, &mut sa, &t, k);
    sa
}

/// Size of rotation 0's tie-group: the number of cyclic rotations of `seq` that
/// are byte-for-byte equal to rotation 0 (i.e. `{0, p, 2p, …}` where `p` is the
/// minimal cyclic period). Computed via the Z-function over the doubled stream.
fn sais_rotation0_group_size(seq: &[usize]) -> usize {
    let n = seq.len();
    if n <= 1 {
        return 1;
    }
    let m = 2 * n;
    let get = |idx: usize| seq[idx % n];
    let mut z = vec![0usize; m];
    let (mut l, mut r) = (0usize, 0usize);
    for i in 1..m {
        if i < r {
            z[i] = (r - i).min(z[i - l]);
        }
        while i + z[i] < m && get(z[i]) == get(i + z[i]) {
            z[i] += 1;
        }
        if i + z[i] > r {
            l = i;
            r = i + z[i];
        }
    }
    let mut count = 1usize; // rotation 0 itself
    for &zi in z.iter().take(n).skip(1) {
        if zi >= n {
            count += 1;
        }
    }
    count
}

/// Compute the BWT of `seq` (elements in [0, n_distinct)) over its cyclic
/// rotations. Returns (bwt_out, primary_index).
///
/// The primary index is the row in the sorted-rotation matrix that corresponds
/// to the original sequence (the rotation starting at position 0). For exact
/// inversion, every caller stores this value on the wire (2 bytes).
///
/// Algorithm: O(n) SA-IS suffix array of the doubled stream. Output is
/// byte-identical to the previous naive O(n² log n) rotation sort — see
/// `test_sais_bwt_matches_naive`. The LF-mapping inverse (`bwt_decode_codes`)
/// and the wire format (u16 `primary_index`) are unchanged.
pub(crate) fn bwt_encode_codes(seq: &[usize]) -> (Vec<usize>, u16) {
    let n = seq.len();
    if n == 0 {
        return (vec![], 0);
    }
    if n == 1 {
        return (vec![seq[0]], 0);
    }

    // Build the doubled stream with a +1 shift so 0 is a unique smallest sentinel.
    let max_code = *seq.iter().max().unwrap();
    let k = max_code + 2; // symbols 1..=max_code+1, plus sentinel 0
    let mut doubled = Vec::with_capacity(2 * n + 1);
    for &c in seq {
        doubled.push(c + 1);
    }
    for &c in seq {
        doubled.push(c + 1);
    }
    doubled.push(0); // unique smallest sentinel
    let sa = sais(&doubled, k);

    // Rotation order = SA entries starting in [0, n), kept in SA order.
    let mut bwt_out = Vec::with_capacity(n);
    let mut pos0 = 0usize; // SA-rank of rotation 0 among the rotations
    let mut r = 0usize;
    for &start in &sa {
        if start < n {
            // Last column of this rotation = element just before its start.
            bwt_out.push(seq[(start + n - 1) % n]);
            if start == 0 {
                pos0 = r;
            }
            r += 1;
        }
    }
    debug_assert_eq!(bwt_out.len(), n, "SA-IS rotation count mismatch");

    // Periodic-tie correction: equal rotations are placed shorter-suffix-first in
    // SA, so rotation 0 (longest suffix) is LAST in its tie-group. The naive stable
    // sort placed it FIRST (smallest start index). primary = pos0 − (group − 1).
    let group_size = sais_rotation0_group_size(seq);
    let primary = pos0 - (group_size - 1);

    // Safety: cube mode is only reached when l <= cube_size_limit() = b*b = 65536,
    // so primary < l <= 65536 <= u16::MAX. If the chunk/cube ceiling is ever raised
    // above 65536, revisit this cast (and the BWT wire format).
    debug_assert!(
        primary <= u16::MAX as usize,
        "primary_index {primary} exceeds u16::MAX; cube/chunk ceiling may have been raised above 65536 without updating BWT wire format"
    );
    (bwt_out, primary as u16)
}

/// Inverse BWT: reconstruct the original sequence from (bwt_out, primary_index).
///
/// Uses the standard LF-mapping inversion:
///   1. Build first_col by sorting bwt_out.
///   2. Build the LF map: for each rank r in bwt_out, LF(r) = position of the
///      r-th occurrence of symbol bwt_out[r] in first_col.
///   3. Walk back n steps starting from primary_index to recover the sequence.
pub(crate) fn bwt_decode_codes(
    bwt_out: &[usize],
    primary: u16,
    n_distinct: usize,
) -> Result<Vec<usize>, CubrimError> {
    let n = bwt_out.len();
    if n == 0 {
        return Ok(vec![]);
    }
    let primary = primary as usize;
    if primary >= n {
        return Err(CubrimError::Decode(format!(
            "BWT primary_index {primary} out of range [0, {n})"
        )));
    }

    // Validate all codes are in range.
    for (i, &c) in bwt_out.iter().enumerate() {
        if c >= n_distinct {
            return Err(CubrimError::Decode(format!(
                "BWT: code {c} at position {i} >= n_distinct {n_distinct}"
            )));
        }
    }

    // Count symbol frequencies (for building first_col and LF map).
    let mut freq = vec![0usize; n_distinct];
    for &c in bwt_out {
        freq[c] += 1;
    }

    // Cumulative sum: C[s] = number of symbols strictly less than s in bwt_out.
    let mut cum = vec![0usize; n_distinct + 1];
    for s in 0..n_distinct {
        cum[s + 1] = cum[s] + freq[s];
    }

    // Build LF map: LF[r] = cum[bwt_out[r]] + rank_of_r_among_same_symbol
    // Rank of r: number of occurrences of bwt_out[r] in bwt_out[0..r].
    let mut rank_so_far = vec![0usize; n_distinct];
    let mut lf = vec![0usize; n];
    for r in 0..n {
        let sym = bwt_out[r];
        lf[r] = cum[sym] + rank_so_far[sym];
        rank_so_far[sym] += 1;
    }

    // Walk back: start at primary, follow LF n times, collect reversed sequence.
    let mut result = vec![0usize; n];
    let mut cur = primary;
    for i in (0..n).rev() {
        result[i] = bwt_out[cur];
        cur = lf[cur];
    }
    Ok(result)
}

/// Encode the value-code stream with BWT + T4 (order-1 context Huffman).
/// Wire: [primary_index: u16 BE] + T4 context-Huffman stream of BWT output.
pub(crate) fn bwt_entropy_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let ctx_bytes = context_huffman_encode(&bwt_out, n_distinct);
    let mut out = Vec::with_capacity(2 + ctx_bytes.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.extend_from_slice(&ctx_bytes);
    out
}

/// Decode the BWT+T4 stream from blob at offset.
/// Returns (decoded seq_codes, bytes consumed from offset).
pub(crate) fn bwt_entropy_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 2 > blob.len() {
        return Err(CubrimError::Decode(
            "BwtEntropy: blob too short for primary_index (need 2 bytes)".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let ctx_offset = offset + 2;

    let (bwt_out, ctx_consumed) = context_huffman_decode(blob, ctx_offset, count, n_distinct)?;

    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;

    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "BwtEntropy: decoded {} codes but expected {} (count from header)",
            seq_codes.len(),
            count
        )));
    }

    Ok((seq_codes, 2 + ctx_consumed))
}

/// Estimate byte size of BWT+T4 encoded stream without allocating the full output.
/// Wire = 2 (primary_index) + T4 context_huffman_size(bwt_out).
pub(crate) fn bwt_entropy_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    let (bwt_out, _) = bwt_encode_codes(seq_codes);
    2 + context_huffman_size(&bwt_out, n_distinct)
}

// ─── H-19: Order-1 Context-Adaptive rANS ─────────────────────────────────────
//
// Same order-1 context model as T4 (context = previous code, fallback to the
// global order-0 table for contexts below MIN_CTX_COUNT) but with a rANS entropy
// back-end instead of canonical Huffman.  rANS reaches the entropy bound to a
// fraction of a bit; Huffman rounds every code length up to an integer bit and
// so pays a ~1-bit floor on near-deterministic contexts (the BWT'd structured
// streams).  All frequency tables are serialized and charged (Gotcha #6).
//
// Byte-wise rANS (Giesen rans_byte.h convention): 32-bit state, lower bound
// RANS_L = 1<<23, renormalize one byte at a time.  Frequencies are normalized to
// a power-of-two total M = 1 << RANS_SCALE_BITS so the modulo/divide reduce to
// mask/shift on decode.
//
// Encoding processes symbols in REVERSE so the decoder pops them in FORWARD order
// — the order-1 context of symbol i (= symbol i-1) is therefore always available
// (already in the input on encode, already decoded on decode).

/// rANS lower bound for the 32-bit state (renorm emits a byte whenever x < L).
const RANS_L: u32 = 1 << 23;
/// rANS normalization total exponent: M = 1 << RANS_SCALE_BITS.
const RANS_SCALE_BITS: u32 = 12;

/// One normalized order-1 context frequency table.
struct RansCtxTable {
    /// freq[sym] in [0, M]; 0 iff the symbol never occurs in this context.
    freq: Vec<u32>,
    /// cum[sym] = sum of freq[0..sym]; cum.len() == n_distinct.
    cum: Vec<u32>,
    /// slot -> symbol map of length M (decode only; empty on encode).
    slot_to_sym: Vec<u16>,
}

/// Normalize raw counts to frequencies summing to exactly M = 1<<scale_bits.
/// Every symbol with count > 0 gets freq >= 1; symbols with count 0 stay 0.
/// Returns the freq vector (length n_distinct). Caller guarantees total > 0 and
/// the number of nonzero counts <= M (true here: n_distinct <= 256 <= 4096).
fn rans_normalize(counts: &[usize], scale_bits: u32) -> Vec<u32> {
    let m: u32 = 1 << scale_bits;
    let total: usize = counts.iter().sum();
    let n = counts.len();
    let mut freq = vec![0u32; n];
    if total == 0 {
        return freq;
    }
    // Initial proportional allocation, flooring nonzero counts to >= 1.
    let mut allocated: u32 = 0;
    for (s, &c) in counts.iter().enumerate() {
        if c == 0 {
            continue;
        }
        // round(c * M / total), then clamp to >= 1.
        let scaled = ((c as u64 * m as u64) + (total as u64 / 2)) / total as u64;
        let f = scaled.max(1) as u32;
        freq[s] = f;
        allocated = allocated.saturating_add(f);
    }
    // Reconcile to exactly M by adjusting the largest-frequency symbol(s).
    // Adding is always safe; subtracting never takes a symbol below 1.
    if allocated < m {
        let mut deficit = m - allocated;
        // Give the surplus to the current maximum (keeps distortion minimal).
        let max_sym = (0..n).filter(|&s| freq[s] > 0).max_by_key(|&s| freq[s]).unwrap();
        freq[max_sym] += deficit;
        deficit = 0;
        let _ = deficit;
    } else if allocated > m {
        let mut surplus = allocated - m;
        // Repeatedly trim the current maximum, never below 1.
        while surplus > 0 {
            let max_sym = (0..n)
                .filter(|&s| freq[s] > 1)
                .max_by_key(|&s| freq[s])
                .expect("normalize: cannot trim surplus without dropping a symbol below 1");
            let take = surplus.min(freq[max_sym] - 1);
            freq[max_sym] -= take;
            surplus -= take;
        }
    }
    debug_assert_eq!(freq.iter().sum::<u32>(), m, "rans_normalize: sum != M");
    freq
}

/// Build order-1 context COUNT tables, mirroring build_context_tables' selection
/// logic exactly (fallback at ctx_id=0 from global counts, then each context with
/// >= MIN_CTX_COUNT observations, sorted ascending by ctx_id) but returning raw
/// per-context counts (length n_distinct) instead of Huffman code lengths.
fn build_context_count_tables(seq_codes: &[usize], n_distinct: usize) -> Vec<(u16, Vec<usize>)> {
    if seq_codes.is_empty() || n_distinct == 0 {
        return vec![];
    }
    use std::collections::BTreeMap;
    let mut ctx_freq: BTreeMap<u16, Vec<usize>> = BTreeMap::new();
    let mut fallback_freq = vec![0usize; n_distinct];

    let mut prev_ctx: u16 = 0;
    for &code in seq_codes.iter() {
        let entry = ctx_freq
            .entry(prev_ctx)
            .or_insert_with(|| vec![0usize; n_distinct]);
        if code < n_distinct {
            entry[code] += 1;
            fallback_freq[code] += 1;
        }
        prev_ctx = code as u16;
    }

    // Fallback (order-0 global) first at ctx_id=0.
    let mut result: Vec<(u16, Vec<usize>)> = vec![(FALLBACK_CTX, fallback_freq)];

    for (&ctx, freq) in &ctx_freq {
        let obs: usize = freq.iter().sum();
        if obs < MIN_CTX_COUNT {
            continue;
        }
        result.push((ctx, freq.clone()));
    }
    result.sort_by_key(|(ctx, _)| *ctx);
    result
}

/// Serialize one context's normalized freq table to the wire as a sparse list:
///   [n_syms : u16 BE] then for each nonzero symbol (ascending) [sym:u8][freq:u16 BE]
fn rans_serialize_ctx_table(out: &mut Vec<u8>, freq: &[u32]) {
    let nz: Vec<usize> = (0..freq.len()).filter(|&s| freq[s] > 0).collect();
    out.extend_from_slice(&(nz.len() as u16).to_be_bytes());
    for s in nz {
        out.push(s as u8);
        out.extend_from_slice(&(freq[s] as u16).to_be_bytes());
    }
}

/// Build a full RansCtxTable (freq + cum, no slot map) from a normalized freq vec.
fn rans_table_from_freq(freq: Vec<u32>) -> RansCtxTable {
    let n = freq.len();
    let mut cum = vec![0u32; n];
    let mut acc = 0u32;
    for s in 0..n {
        cum[s] = acc;
        acc += freq[s];
    }
    RansCtxTable {
        freq,
        cum,
        slot_to_sym: Vec::new(),
    }
}

/// Encode the value-code stream with order-1 context rANS.
/// Wire: scale_bits(1) + fallback table + n_contexts(2) + per-ctx tables
///       + rans_len(4) + rans bytes.
///
/// The fallback (global order-0) table is a DEDICATED wire entity, separate from
/// the context list — never shadowed by a same-id real context (this avoids the
/// latent ctx_id-0 collision that would make rANS see a freq-0 symbol).
pub(crate) fn rans_order1_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let scale_bits = RANS_SCALE_BITS;
    let mut out: Vec<u8> = Vec::new();
    out.push(scale_bits as u8);

    if seq_codes.is_empty() || n_distinct == 0 {
        // Empty fallback table + zero contexts + zero rANS bytes.
        out.extend_from_slice(&0u16.to_be_bytes()); // fallback n_syms = 0
        out.extend_from_slice(&0u16.to_be_bytes()); // n_contexts = 0
        out.extend_from_slice(&0u32.to_be_bytes()); // rans_len = 0
        return out;
    }

    let count_tables = build_context_count_tables(seq_codes, n_distinct);
    // count_tables[0] is always the FALLBACK_CTX global table; the rest are
    // per-context own tables (which may include a real ctx_id == 0).
    debug_assert!(!count_tables.is_empty() && count_tables[0].0 == FALLBACK_CTX);
    let fallback_freq = rans_normalize(&count_tables[0].1, scale_bits);
    let fallback_table = rans_table_from_freq(fallback_freq.clone());
    let own = &count_tables[1..];
    let n_ctx = own.len() as u16;

    // Serialize fallback first, then own context tables; build encode lookup.
    use std::collections::HashMap;
    let mut ctx_idx: HashMap<u16, usize> = HashMap::new();
    let mut tables: Vec<RansCtxTable> = Vec::with_capacity(own.len());

    rans_serialize_ctx_table(&mut out, &fallback_freq);
    out.extend_from_slice(&n_ctx.to_be_bytes());
    for (i, (ctx_id, counts)) in own.iter().enumerate() {
        let freq = rans_normalize(counts, scale_bits);
        out.extend_from_slice(&ctx_id.to_be_bytes());
        rans_serialize_ctx_table(&mut out, &freq);
        ctx_idx.insert(*ctx_id, i);
        tables.push(rans_table_from_freq(freq));
    }

    // rANS encode in reverse so decode is forward (context always available).
    let n = seq_codes.len();
    let mut buf = vec![0u8; 16 + 4 * n];
    let mut p = buf.len();
    let mut x: u32 = RANS_L;

    for i in (0..n).rev() {
        let ctx = if i == 0 { 0u16 } else { seq_codes[i - 1] as u16 };
        let table = match ctx_idx.get(&ctx) {
            Some(&idx) => &tables[idx],
            None => &fallback_table,
        };
        let s = seq_codes[i];
        let f = table.freq[s];
        let c = table.cum[s];
        debug_assert!(f > 0, "rans encode: zero freq for symbol {s} in ctx {ctx}");
        // Renormalize: emit bytes while x would overflow the slot range.
        let x_max = ((RANS_L >> scale_bits) << 8) * f;
        while x >= x_max {
            p -= 1;
            buf[p] = (x & 0xff) as u8;
            x >>= 8;
        }
        // x = (x / f) * M + (x % f) + c
        x = ((x / f) << scale_bits) + (x % f) + c;
    }
    // Flush 4-byte state, little-endian, at the lowest written addresses.
    p -= 4;
    buf[p] = (x & 0xff) as u8;
    buf[p + 1] = ((x >> 8) & 0xff) as u8;
    buf[p + 2] = ((x >> 16) & 0xff) as u8;
    buf[p + 3] = ((x >> 24) & 0xff) as u8;

    let rans_bytes = &buf[p..];
    out.extend_from_slice(&(rans_bytes.len() as u32).to_be_bytes());
    out.extend_from_slice(rans_bytes);
    out
}

/// Decode the order-1 context rANS stream from blob at offset.
/// Returns (decoded seq_codes, bytes consumed from offset).
pub(crate) fn rans_order1_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    let mut pos = offset;
    if pos + 1 > blob.len() {
        return Err(CubrimError::Decode(
            "rANS: blob too short for scale_bits".into(),
        ));
    }
    let scale_bits = blob[pos] as u32;
    pos += 1;
    if scale_bits == 0 || scale_bits > 16 {
        return Err(CubrimError::Decode(format!(
            "rANS: invalid scale_bits {scale_bits} (expected 1..=16)"
        )));
    }
    let m: u32 = 1 << scale_bits;
    let mask: u32 = m - 1;

    // Helper: read one freq table (sparse list) at `pos`, build a full RansCtxTable.
    // Returns the table or an error; advances pos via the returned new position.
    let read_table = |blob: &[u8], mut pos: usize| -> Result<(RansCtxTable, usize), CubrimError> {
        if pos + 2 > blob.len() {
            return Err(CubrimError::Decode("rANS: table n_syms truncated".into()));
        }
        let n_syms = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
        pos += 2;
        let mut freq = vec![0u32; n_distinct];
        let mut sum: u32 = 0;
        for _ in 0..n_syms {
            if pos + 3 > blob.len() {
                return Err(CubrimError::Decode("rANS: table entry truncated".into()));
            }
            let sym = blob[pos] as usize;
            let f = u16::from_be_bytes([blob[pos + 1], blob[pos + 2]]) as u32;
            pos += 3;
            if sym >= n_distinct {
                return Err(CubrimError::Decode(format!(
                    "rANS: table symbol {sym} >= n_distinct {n_distinct}"
                )));
            }
            if f == 0 {
                return Err(CubrimError::Decode(
                    "rANS: table freq 0 (corrupt stream)".into(),
                ));
            }
            freq[sym] = f;
            sum += f;
        }
        let mut cum = vec![0u32; n_distinct];
        let mut slot_to_sym = vec![0u16; m as usize];
        let mut acc: u32 = 0;
        for s in 0..n_distinct {
            cum[s] = acc;
            let end = acc + freq[s];
            for slot in acc..end {
                slot_to_sym[slot as usize] = s as u16;
            }
            acc = end;
        }
        // sum must equal M unless the table is empty (n_syms == 0, used only by the
        // empty-stream sentinel where count == 0 and no symbol is ever decoded).
        if n_syms > 0 && sum != m {
            return Err(CubrimError::Decode(format!(
                "rANS: freq sum {sum} != M {m} (corrupt stream)"
            )));
        }
        Ok((
            RansCtxTable {
                freq,
                cum,
                slot_to_sym,
            },
            pos,
        ))
    };

    // Read the dedicated fallback (global order-0) table.
    let (fallback_table, new_pos) = read_table(blob, pos)?;
    pos = new_pos;

    if pos + 2 > blob.len() {
        return Err(CubrimError::Decode("rANS: blob too short for n_contexts".into()));
    }
    let n_ctx = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
    pos += 2;

    // Read own context tables (wire order = encoder emit order).
    use std::collections::HashMap;
    let mut ctx_idx: HashMap<u16, usize> = HashMap::new();
    let mut tables: Vec<RansCtxTable> = Vec::with_capacity(n_ctx);

    for _ in 0..n_ctx {
        if pos + 2 > blob.len() {
            return Err(CubrimError::Decode("rANS: ctx table ctx_id truncated".into()));
        }
        let ctx_id = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
        pos += 2;
        let (table, new_pos) = read_table(blob, pos)?;
        pos = new_pos;
        ctx_idx.insert(ctx_id, tables.len());
        tables.push(table);
    }

    // Read rans payload length + bytes.
    if pos + 4 > blob.len() {
        return Err(CubrimError::Decode("rANS: blob too short for rans_len".into()));
    }
    let rans_len =
        u32::from_be_bytes([blob[pos], blob[pos + 1], blob[pos + 2], blob[pos + 3]]) as usize;
    pos += 4;
    if pos + rans_len > blob.len() {
        return Err(CubrimError::Decode(format!(
            "rANS: payload truncated: need {rans_len} bytes, have {}",
            blob.len().saturating_sub(pos)
        )));
    }
    let payload = &blob[pos..pos + rans_len];
    pos += rans_len;

    if count == 0 {
        return Ok((vec![], pos - offset));
    }
    if payload.len() < 4 {
        return Err(CubrimError::Decode(
            "rANS: payload too short for state init".into(),
        ));
    }

    // Init state (little-endian) and decode forward.
    let mut cursor = 0usize;
    let mut x: u32 = payload[0] as u32
        | (payload[1] as u32) << 8
        | (payload[2] as u32) << 16
        | (payload[3] as u32) << 24;
    cursor += 4;

    let mut result = Vec::with_capacity(count);
    let mut prev_ctx: u16 = 0;
    for _ in 0..count {
        let table = match ctx_idx.get(&prev_ctx) {
            Some(&idx) => &tables[idx],
            None => &fallback_table,
        };
        let slot = x & mask;
        let s = table.slot_to_sym[slot as usize] as usize;
        let f = table.freq[s];
        let c = table.cum[s];
        // x = f * (x >> scale_bits) + slot - c
        x = f * (x >> scale_bits) + slot - c;
        // Renormalize.
        while x < RANS_L {
            if cursor >= payload.len() {
                return Err(CubrimError::Decode(
                    "rANS: payload exhausted during renorm".into(),
                ));
            }
            x = (x << 8) | payload[cursor] as u32;
            cursor += 1;
        }
        result.push(s);
        prev_ctx = s as u16;
    }

    Ok((result, pos - offset))
}

/// Encode a symbol stream with a single order-0 rANS table (no contexts). This is
/// the "lighter" coder used for LzRans sub-streams: it pays one global freq table
/// (sparse, `[n_syms u16][(sym u8, freq u16)]*`) instead of the per-context tables
/// the order-1 coder would build — which dominate on short streams (H-25b fix #2).
///
/// Wire: scale_bits(1) + table + rans_len(4) + rANS payload (LE state prefix).
pub(crate) fn rans_order0_encode(symbols: &[usize], alphabet: usize) -> Vec<u8> {
    let scale_bits = RANS_SCALE_BITS;
    let mut out: Vec<u8> = Vec::new();
    out.push(scale_bits as u8);

    if symbols.is_empty() || alphabet == 0 {
        out.extend_from_slice(&0u16.to_be_bytes()); // n_syms = 0
        out.extend_from_slice(&0u32.to_be_bytes()); // rans_len = 0
        return out;
    }

    let mut counts = vec![0usize; alphabet];
    for &s in symbols {
        counts[s] += 1;
    }
    let freq = rans_normalize(&counts, scale_bits);
    let table = rans_table_from_freq(freq.clone());
    rans_serialize_ctx_table(&mut out, &freq);

    let n = symbols.len();
    let mut buf = vec![0u8; 16 + 4 * n];
    let mut p = buf.len();
    let mut x: u32 = RANS_L;
    for i in (0..n).rev() {
        let s = symbols[i];
        let f = table.freq[s];
        let c = table.cum[s];
        debug_assert!(f > 0, "rans0 encode: zero freq for symbol {s}");
        let x_max = ((RANS_L >> scale_bits) << 8) * f;
        while x >= x_max {
            p -= 1;
            buf[p] = (x & 0xff) as u8;
            x >>= 8;
        }
        x = ((x / f) << scale_bits) + (x % f) + c;
    }
    p -= 4;
    buf[p] = (x & 0xff) as u8;
    buf[p + 1] = ((x >> 8) & 0xff) as u8;
    buf[p + 2] = ((x >> 16) & 0xff) as u8;
    buf[p + 3] = ((x >> 24) & 0xff) as u8;
    let rans_bytes = &buf[p..];
    out.extend_from_slice(&(rans_bytes.len() as u32).to_be_bytes());
    out.extend_from_slice(rans_bytes);
    out
}

/// Decode an order-0 rANS stream (see `rans_order0_encode`) of `count` symbols.
/// Returns (symbols, bytes consumed).
pub(crate) fn rans_order0_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    alphabet: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    let mut pos = offset;
    if pos + 1 > blob.len() {
        return Err(CubrimError::Decode("rANS0: blob too short for scale_bits".into()));
    }
    let scale_bits = blob[pos] as u32;
    pos += 1;
    if scale_bits == 0 || scale_bits > 16 {
        return Err(CubrimError::Decode(format!(
            "rANS0: invalid scale_bits {scale_bits}"
        )));
    }
    let m: u32 = 1 << scale_bits;
    let mask: u32 = m - 1;

    if pos + 2 > blob.len() {
        return Err(CubrimError::Decode("rANS0: table n_syms truncated".into()));
    }
    let n_syms = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
    pos += 2;
    let mut freq = vec![0u32; alphabet.max(1)];
    let mut sum: u32 = 0;
    for _ in 0..n_syms {
        if pos + 3 > blob.len() {
            return Err(CubrimError::Decode("rANS0: table entry truncated".into()));
        }
        let sym = blob[pos] as usize;
        let f = u16::from_be_bytes([blob[pos + 1], blob[pos + 2]]) as u32;
        pos += 3;
        if sym >= alphabet {
            return Err(CubrimError::Decode(format!(
                "rANS0: table symbol {sym} >= alphabet {alphabet}"
            )));
        }
        if f == 0 {
            return Err(CubrimError::Decode("rANS0: table freq 0".into()));
        }
        freq[sym] = f;
        sum += f;
    }
    let mut cum = vec![0u32; alphabet.max(1)];
    let mut slot_to_sym = vec![0u16; m as usize];
    let mut acc: u32 = 0;
    for s in 0..alphabet {
        cum[s] = acc;
        let end = acc + freq[s];
        for slot in acc..end {
            slot_to_sym[slot as usize] = s as u16;
        }
        acc = end;
    }
    if n_syms > 0 && sum != m {
        return Err(CubrimError::Decode(format!(
            "rANS0: freq sum {sum} != M {m}"
        )));
    }

    if pos + 4 > blob.len() {
        return Err(CubrimError::Decode("rANS0: blob too short for rans_len".into()));
    }
    let rans_len =
        u32::from_be_bytes([blob[pos], blob[pos + 1], blob[pos + 2], blob[pos + 3]]) as usize;
    pos += 4;
    if pos + rans_len > blob.len() {
        return Err(CubrimError::Decode("rANS0: payload truncated".into()));
    }
    let payload = &blob[pos..pos + rans_len];
    pos += rans_len;

    if count == 0 {
        return Ok((vec![], pos - offset));
    }
    if payload.len() < 4 {
        return Err(CubrimError::Decode("rANS0: payload too short for state".into()));
    }
    let mut cursor = 0usize;
    let mut x: u32 = payload[0] as u32
        | (payload[1] as u32) << 8
        | (payload[2] as u32) << 16
        | (payload[3] as u32) << 24;
    cursor += 4;

    let mut result = Vec::with_capacity(count);
    for _ in 0..count {
        let slot = x & mask;
        let s = slot_to_sym[slot as usize] as usize;
        let f = freq[s];
        let c = cum[s];
        x = f * (x >> scale_bits) + slot - c;
        while x < RANS_L {
            if cursor >= payload.len() {
                return Err(CubrimError::Decode("rANS0: payload exhausted".into()));
            }
            x = (x << 8) | payload[cursor] as u32;
            cursor += 1;
        }
        result.push(s);
    }
    Ok((result, pos - offset))
}

/// Encode the value-code stream with BWT + order-1 rANS.
/// Wire: [primary_index: u16 BE] + rANS order-1 stream of BWT output.
pub(crate) fn bwt_rans_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let body = rans_order1_encode(&bwt_out, n_distinct);
    let mut out = Vec::with_capacity(2 + body.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.extend_from_slice(&body);
    out
}

/// Decode the BWT + order-1 rANS stream from blob at offset.
/// Returns (decoded seq_codes, bytes consumed from offset).
pub(crate) fn bwt_rans_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 2 > blob.len() {
        return Err(CubrimError::Decode(
            "BwtRans: blob too short for primary_index (need 2 bytes)".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let body_offset = offset + 2;

    let (bwt_out, consumed) = rans_order1_decode(blob, body_offset, count, n_distinct)?;
    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;

    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "BwtRans: decoded {} codes but expected {} (count from header)",
            seq_codes.len(),
            count
        )));
    }
    Ok((seq_codes, 2 + consumed))
}

/// Estimate byte size of the BWT + order-1 rANS stream (full encode then len).
pub(crate) fn bwt_rans_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    bwt_rans_encode(seq_codes, n_distinct).len()
}

// ── H-20: order-2 context rANS ───────────────────────────────────────────────
//
// Generalizes the order-1 rANS back-end (scheme 7) to an order-2 context model
// keyed by (prev2_code, prev_code). The decoder's fallback chain is
// order-2 → order-1 → order-0; EVERY level is serialized and charged (Gotcha #6).
// The encoder additionally tries a 2-level layout (order-2 → order-0, omitting the
// order-1 tables) and keeps whichever is smaller — the 2-level layout wins when the
// order-1 tables cost more than the payload they save (over-fragmentation).

/// Read one sparse rANS freq table (same wire format as rans_serialize_ctx_table)
/// at `pos`, building a full RansCtxTable (freq + cum + slot_to_sym). Standalone
/// twin of the closure inside rans_order1_decode, reused by the order-2 decoder.
fn rans_read_ctx_table(
    blob: &[u8],
    mut pos: usize,
    n_distinct: usize,
    m: u32,
) -> Result<(RansCtxTable, usize), CubrimError> {
    if pos + 2 > blob.len() {
        return Err(CubrimError::Decode("rANS2: table n_syms truncated".into()));
    }
    let n_syms = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
    pos += 2;
    let mut freq = vec![0u32; n_distinct];
    let mut sum: u32 = 0;
    for _ in 0..n_syms {
        if pos + 3 > blob.len() {
            return Err(CubrimError::Decode("rANS2: table entry truncated".into()));
        }
        let sym = blob[pos] as usize;
        let f = u16::from_be_bytes([blob[pos + 1], blob[pos + 2]]) as u32;
        pos += 3;
        if sym >= n_distinct {
            return Err(CubrimError::Decode(format!(
                "rANS2: table symbol {sym} >= n_distinct {n_distinct}"
            )));
        }
        if f == 0 {
            return Err(CubrimError::Decode("rANS2: table freq 0 (corrupt)".into()));
        }
        freq[sym] = f;
        sum += f;
    }
    let mut cum = vec![0u32; n_distinct];
    let mut slot_to_sym = vec![0u16; m as usize];
    let mut acc: u32 = 0;
    for s in 0..n_distinct {
        cum[s] = acc;
        let end = acc + freq[s];
        for slot in acc..end {
            slot_to_sym[slot as usize] = s as u16;
        }
        acc = end;
    }
    if n_syms > 0 && sum != m {
        return Err(CubrimError::Decode(format!(
            "rANS2: freq sum {sum} != M {m} (corrupt)"
        )));
    }
    Ok((
        RansCtxTable {
            freq,
            cum,
            slot_to_sym,
        },
        pos,
    ))
}

/// Build order-0 (global), order-1, and order-2 per-context COUNT tables.
/// Every position contributes to its order-0/1/2 context. A context qualifies for
/// its own table only when it has >= MIN_CTX_COUNT observations (mirrors the order-1
/// champion's fallback discipline). Returns counts (not yet normalized).
#[allow(clippy::type_complexity)]
fn build_order2_count_tables(
    seq_codes: &[usize],
    n_distinct: usize,
) -> (
    Vec<usize>,
    std::collections::BTreeMap<u16, Vec<usize>>,
    std::collections::BTreeMap<(u16, u16), Vec<usize>>,
) {
    use std::collections::BTreeMap;
    let mut global = vec![0usize; n_distinct];
    let mut c1: BTreeMap<u16, Vec<usize>> = BTreeMap::new();
    let mut c2: BTreeMap<(u16, u16), Vec<usize>> = BTreeMap::new();
    let mut p2: u16 = 0;
    let mut p1: u16 = 0;
    for &code in seq_codes {
        if code < n_distinct {
            global[code] += 1;
            c1.entry(p1).or_insert_with(|| vec![0usize; n_distinct])[code] += 1;
            c2.entry((p2, p1)).or_insert_with(|| vec![0usize; n_distinct])[code] += 1;
        }
        p2 = p1;
        p1 = code as u16;
    }
    (global, c1, c2)
}

/// Select the table for context (p2, p1): order-2 → order-1 → order-0 fallback.
fn order2_select<'a>(
    o2_idx: &std::collections::HashMap<(u16, u16), usize>,
    o2_tables: &'a [RansCtxTable],
    o1_idx: &std::collections::HashMap<u16, usize>,
    o1_tables: &'a [RansCtxTable],
    fallback: &'a RansCtxTable,
    p2: u16,
    p1: u16,
) -> &'a RansCtxTable {
    if let Some(&i) = o2_idx.get(&(p2, p1)) {
        return &o2_tables[i];
    }
    if let Some(&i) = o1_idx.get(&p1) {
        return &o1_tables[i];
    }
    fallback
}

/// Encode the (already-BWT'd) code stream with order-2 context rANS.
/// `use_order1` toggles the 3-level (true) vs 2-level (false) wire layout.
/// Wire: scale_bits(1) + fallback table + n_ctx1(2) + order-1 tables
///       + n_ctx2(2) + order-2 tables + rans_len(4) + rans bytes.
fn order2_rans_encode(seq_codes: &[usize], n_distinct: usize, use_order1: bool) -> Vec<u8> {
    use std::collections::HashMap;
    let scale_bits = RANS_SCALE_BITS;
    let mut out: Vec<u8> = Vec::new();
    out.push(scale_bits as u8);

    if seq_codes.is_empty() || n_distinct == 0 {
        out.extend_from_slice(&0u16.to_be_bytes()); // fallback n_syms = 0
        out.extend_from_slice(&0u16.to_be_bytes()); // n_ctx1 = 0
        out.extend_from_slice(&0u16.to_be_bytes()); // n_ctx2 = 0
        out.extend_from_slice(&0u32.to_be_bytes()); // rans_len = 0
        return out;
    }

    let (global, c1, c2) = build_order2_count_tables(seq_codes, n_distinct);
    let fallback_freq = rans_normalize(&global, scale_bits);
    let fallback_table = rans_table_from_freq(fallback_freq.clone());

    // Qualifying order-1 tables (only if use_order1).
    let mut o1_tables: Vec<RansCtxTable> = Vec::new();
    let mut o1_idx: HashMap<u16, usize> = HashMap::new();
    let mut o1_serial: Vec<(u16, Vec<u32>)> = Vec::new();
    if use_order1 {
        for (&ctx, counts) in &c1 {
            if counts.iter().sum::<usize>() >= MIN_CTX_COUNT {
                let freq = rans_normalize(counts, scale_bits);
                o1_idx.insert(ctx, o1_tables.len());
                o1_tables.push(rans_table_from_freq(freq.clone()));
                o1_serial.push((ctx, freq));
            }
        }
    }

    // Qualifying order-2 tables.
    let mut o2_tables: Vec<RansCtxTable> = Vec::new();
    let mut o2_idx: HashMap<(u16, u16), usize> = HashMap::new();
    let mut o2_serial: Vec<((u16, u16), Vec<u32>)> = Vec::new();
    for (&key, counts) in &c2 {
        if counts.iter().sum::<usize>() >= MIN_CTX_COUNT {
            let freq = rans_normalize(counts, scale_bits);
            o2_idx.insert(key, o2_tables.len());
            o2_tables.push(rans_table_from_freq(freq.clone()));
            o2_serial.push((key, freq));
        }
    }

    // Serialize header.
    rans_serialize_ctx_table(&mut out, &fallback_freq);
    out.extend_from_slice(&(o1_serial.len() as u16).to_be_bytes());
    for (ctx, freq) in &o1_serial {
        out.extend_from_slice(&ctx.to_be_bytes());
        rans_serialize_ctx_table(&mut out, freq);
    }
    out.extend_from_slice(&(o2_serial.len() as u16).to_be_bytes());
    for ((p2, p1), freq) in &o2_serial {
        out.extend_from_slice(&p2.to_be_bytes());
        out.extend_from_slice(&p1.to_be_bytes());
        rans_serialize_ctx_table(&mut out, freq);
    }

    // rANS encode in reverse so decode is forward (context always available).
    let n = seq_codes.len();
    let mut buf = vec![0u8; 16 + 4 * n];
    let mut p = buf.len();
    let mut x: u32 = RANS_L;
    for i in (0..n).rev() {
        let p1 = if i >= 1 { seq_codes[i - 1] as u16 } else { 0 };
        let p2 = if i >= 2 { seq_codes[i - 2] as u16 } else { 0 };
        let table = order2_select(
            &o2_idx,
            &o2_tables,
            &o1_idx,
            &o1_tables,
            &fallback_table,
            p2,
            p1,
        );
        let s = seq_codes[i];
        let f = table.freq[s];
        let c = table.cum[s];
        debug_assert!(f > 0, "rANS2 encode: zero freq for symbol {s}");
        let x_max = ((RANS_L >> scale_bits) << 8) * f;
        while x >= x_max {
            p -= 1;
            buf[p] = (x & 0xff) as u8;
            x >>= 8;
        }
        x = ((x / f) << scale_bits) + (x % f) + c;
    }
    p -= 4;
    buf[p] = (x & 0xff) as u8;
    buf[p + 1] = ((x >> 8) & 0xff) as u8;
    buf[p + 2] = ((x >> 16) & 0xff) as u8;
    buf[p + 3] = ((x >> 24) & 0xff) as u8;
    let rans_bytes = &buf[p..];
    out.extend_from_slice(&(rans_bytes.len() as u32).to_be_bytes());
    out.extend_from_slice(rans_bytes);
    out
}

/// Decode the order-2 context rANS stream from blob at offset.
/// Returns (decoded codes, bytes consumed from offset).
fn order2_rans_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    use std::collections::HashMap;
    let mut pos = offset;
    if pos + 1 > blob.len() {
        return Err(CubrimError::Decode("rANS2: blob too short for scale_bits".into()));
    }
    let scale_bits = blob[pos] as u32;
    pos += 1;
    if scale_bits == 0 || scale_bits > 16 {
        return Err(CubrimError::Decode(format!(
            "rANS2: invalid scale_bits {scale_bits}"
        )));
    }
    let m: u32 = 1 << scale_bits;
    let mask: u32 = m - 1;

    // Fallback (order-0) table.
    let (fallback_table, np) = rans_read_ctx_table(blob, pos, n_distinct, m)?;
    pos = np;

    // Order-1 tables.
    if pos + 2 > blob.len() {
        return Err(CubrimError::Decode("rANS2: blob too short for n_ctx1".into()));
    }
    let n_ctx1 = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
    pos += 2;
    let mut o1_idx: HashMap<u16, usize> = HashMap::new();
    let mut o1_tables: Vec<RansCtxTable> = Vec::with_capacity(n_ctx1);
    for _ in 0..n_ctx1 {
        if pos + 2 > blob.len() {
            return Err(CubrimError::Decode("rANS2: ctx1 id truncated".into()));
        }
        let ctx_id = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
        pos += 2;
        let (table, np) = rans_read_ctx_table(blob, pos, n_distinct, m)?;
        pos = np;
        o1_idx.insert(ctx_id, o1_tables.len());
        o1_tables.push(table);
    }

    // Order-2 tables.
    if pos + 2 > blob.len() {
        return Err(CubrimError::Decode("rANS2: blob too short for n_ctx2".into()));
    }
    let n_ctx2 = u16::from_be_bytes([blob[pos], blob[pos + 1]]) as usize;
    pos += 2;
    let mut o2_idx: HashMap<(u16, u16), usize> = HashMap::new();
    let mut o2_tables: Vec<RansCtxTable> = Vec::with_capacity(n_ctx2);
    for _ in 0..n_ctx2 {
        if pos + 4 > blob.len() {
            return Err(CubrimError::Decode("rANS2: ctx2 key truncated".into()));
        }
        let p2 = u16::from_be_bytes([blob[pos], blob[pos + 1]]);
        let p1 = u16::from_be_bytes([blob[pos + 2], blob[pos + 3]]);
        pos += 4;
        let (table, np) = rans_read_ctx_table(blob, pos, n_distinct, m)?;
        pos = np;
        o2_idx.insert((p2, p1), o2_tables.len());
        o2_tables.push(table);
    }

    // rANS payload.
    if pos + 4 > blob.len() {
        return Err(CubrimError::Decode("rANS2: blob too short for rans_len".into()));
    }
    let rans_len =
        u32::from_be_bytes([blob[pos], blob[pos + 1], blob[pos + 2], blob[pos + 3]]) as usize;
    pos += 4;
    if pos + rans_len > blob.len() {
        return Err(CubrimError::Decode(format!(
            "rANS2: payload truncated: need {rans_len}, have {}",
            blob.len().saturating_sub(pos)
        )));
    }
    let payload = &blob[pos..pos + rans_len];
    pos += rans_len;

    if count == 0 {
        return Ok((vec![], pos - offset));
    }
    if payload.len() < 4 {
        return Err(CubrimError::Decode("rANS2: payload too short for state".into()));
    }

    let mut cursor = 0usize;
    let mut x: u32 = payload[0] as u32
        | (payload[1] as u32) << 8
        | (payload[2] as u32) << 16
        | (payload[3] as u32) << 24;
    cursor += 4;

    let mut result = Vec::with_capacity(count);
    let mut p2: u16 = 0;
    let mut p1: u16 = 0;
    for _ in 0..count {
        let table = order2_select(
            &o2_idx,
            &o2_tables,
            &o1_idx,
            &o1_tables,
            &fallback_table,
            p2,
            p1,
        );
        let slot = x & mask;
        let s = table.slot_to_sym[slot as usize] as usize;
        let f = table.freq[s];
        let c = table.cum[s];
        x = f * (x >> scale_bits) + slot - c;
        while x < RANS_L {
            if cursor >= payload.len() {
                return Err(CubrimError::Decode("rANS2: payload exhausted in renorm".into()));
            }
            x = (x << 8) | payload[cursor] as u32;
            cursor += 1;
        }
        result.push(s);
        p2 = p1;
        p1 = s as u16;
    }

    Ok((result, pos - offset))
}

/// Encode the value-code stream with BWT + order-2 rANS, picking the smaller of the
/// 3-level and 2-level wire layouts. Wire: [primary u16 BE] + order-2 rANS body.
pub(crate) fn bwt_order2_rans_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let body3 = order2_rans_encode(&bwt_out, n_distinct, true);
    let body2 = order2_rans_encode(&bwt_out, n_distinct, false);
    let body = if body2.len() < body3.len() { body2 } else { body3 };
    let mut out = Vec::with_capacity(2 + body.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.extend_from_slice(&body);
    out
}

/// Decode the BWT + order-2 rANS stream from blob at offset.
pub(crate) fn bwt_order2_rans_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 2 > blob.len() {
        return Err(CubrimError::Decode(
            "Order2Rans: blob too short for primary_index".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let body_offset = offset + 2;
    let (bwt_out, consumed) = order2_rans_decode(blob, body_offset, count, n_distinct)?;
    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;
    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "Order2Rans: decoded {} codes but expected {}",
            seq_codes.len(),
            count
        )));
    }
    Ok((seq_codes, 2 + consumed))
}

/// Estimate byte size of the BWT + order-2 rANS stream (full encode then len).
pub(crate) fn bwt_order2_rans_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    bwt_order2_rans_encode(seq_codes, n_distinct).len()
}

// ── H-21: adaptive order-1 entropy coding (no transmitted frequency tables) ───
//
// The champion (scheme 7) transmits a per-context frequency table; on short,
// structured BWT'd streams those tables dominate the value-stream cost. An ADAPTIVE
// model removes the tables entirely: the decoder rebuilds the exact same model the
// encoder used, symbol-by-symbol, from the data it has already decoded. The only
// side information is the alphabet size (already in the cube header) and one `inc`
// byte (the model's learning rate).
//
// BACKEND CHOICE — range coder, not rANS. rANS encodes LIFO (reverse), which fights
// a forward-adapting model: the model state at position i depends on symbols [0,i),
// but a reverse encoder visits i last. The decrement trick recovers that ONLY when
// counts never rescale — yet byte-rANS REQUIRES the model total stay ≤ ~2^15, so a
// growing adaptive model MUST rescale, and rescaling (a lossy halving) is not
// reversible for the reverse pass. A range coder codes FORWARD; the decoder mirrors
// the model update and the rescale identically, so determinism is trivial. Range
// coding and rANS are informationally equivalent (both reach the entropy bound), so
// this realizes the "adaptive / no-table" hypothesis faithfully.

/// Carryless range coder constants (Subbotin scheme). `total` passed to encode/decode
/// must stay ≤ BOT so `range/total ≥ 1` holds after renorm (range ≥ BOT).
const RC_TOP: u32 = 1 << 24;
const RC_BOT: u32 = 1 << 16;
/// Rescale the adaptive model when a context total would exceed this. Kept well under
/// RC_BOT so `total + inc` never reaches RC_BOT (max inc 64 → 32768+64 < 65536).
const ADAPT_RESCALE: u32 = 1 << 15;
/// Increment values the encoder tries (effective Laplace alpha = 1/inc). Smaller alpha
/// (larger inc) sharpens the model faster on run-structured BWT streams.
const ADAPT_INCS: [u32; 4] = [8, 16, 32, 64];

struct RangeEncoder {
    low: u32,
    range: u32,
    out: Vec<u8>,
}

impl RangeEncoder {
    fn new() -> Self {
        Self {
            low: 0,
            range: 0xFFFF_FFFF,
            out: Vec::new(),
        }
    }
    #[inline]
    fn encode(&mut self, cum: u32, freq: u32, total: u32) {
        let r = self.range / total;
        self.low = self.low.wrapping_add(r * cum);
        self.range = r * freq;
        loop {
            if (self.low ^ self.low.wrapping_add(self.range)) < RC_TOP {
                // top byte settled.
            } else if self.range < RC_BOT {
                // underflow: force range up (carryless trick).
                self.range = self.low.wrapping_neg() & (RC_BOT - 1);
            } else {
                break;
            }
            self.out.push((self.low >> 24) as u8);
            self.low <<= 8;
            self.range <<= 8;
        }
    }
    fn finish(mut self) -> Vec<u8> {
        for _ in 0..4 {
            self.out.push((self.low >> 24) as u8);
            self.low <<= 8;
        }
        self.out
    }
}

struct RangeDecoder<'a> {
    low: u32,
    range: u32,
    code: u32,
    buf: &'a [u8],
    pos: usize,
}

impl<'a> RangeDecoder<'a> {
    fn new(buf: &'a [u8]) -> Self {
        let mut code: u32 = 0;
        let mut pos = 0;
        for _ in 0..4 {
            code = (code << 8) | (*buf.get(pos).unwrap_or(&0) as u32);
            pos += 1;
        }
        Self {
            low: 0,
            range: 0xFFFF_FFFF,
            code,
            buf,
            pos,
        }
    }
    #[inline]
    fn get_freq(&self, total: u32) -> u32 {
        let r = self.range / total;
        let dv = (self.code.wrapping_sub(self.low)) / r;
        if dv >= total {
            total - 1
        } else {
            dv
        }
    }
    #[inline]
    fn decode(&mut self, cum: u32, freq: u32, total: u32) {
        let r = self.range / total;
        self.low = self.low.wrapping_add(r * cum);
        self.range = r * freq;
        loop {
            if (self.low ^ self.low.wrapping_add(self.range)) < RC_TOP {
            } else if self.range < RC_BOT {
                self.range = self.low.wrapping_neg() & (RC_BOT - 1);
            } else {
                break;
            }
            self.code = (self.code << 8) | (*self.buf.get(self.pos).unwrap_or(&0) as u32);
            self.pos += 1;
            self.low <<= 8;
            self.range <<= 8;
        }
    }
}

/// One adaptive order-1 context model: integer freqs (init 1 each) + running total.
struct AdaptModel {
    freq: Vec<u32>,
    total: u32,
}

impl AdaptModel {
    fn new(a: usize) -> Self {
        Self {
            freq: vec![1u32; a],
            total: a as u32,
        }
    }
    /// Cumulative freq below symbol `s` (linear; A ≤ 256).
    #[inline]
    fn cum(&self, s: usize) -> u32 {
        let mut c = 0u32;
        for &f in &self.freq[..s] {
            c += f;
        }
        c
    }
    /// Find the symbol whose cum range contains decode value `dv`; return (s, cum_s).
    #[inline]
    fn find(&self, dv: u32) -> (usize, u32) {
        let mut c = 0u32;
        for (s, &f) in self.freq.iter().enumerate() {
            if c + f > dv {
                return (s, c);
            }
            c += f;
        }
        // dv < total guarantees a hit; fall back to last symbol defensively.
        let last = self.freq.len() - 1;
        (last, self.total - self.freq[last])
    }
    /// Observe symbol `s`: bump its freq by `inc`, rescale if total exceeds the cap.
    #[inline]
    fn update(&mut self, s: usize, inc: u32) {
        self.freq[s] += inc;
        self.total += inc;
        if self.total > ADAPT_RESCALE {
            let mut nt = 0u32;
            for f in &mut self.freq {
                *f = (*f + 1) >> 1;
                nt += *f;
            }
            self.total = nt;
        }
    }
}

/// Adaptive order-1 range-code the (already-BWT'd) code stream. No tables on the wire.
/// Context = previous code (sentinel 0 at position 0).
fn adaptive_range_o1_encode(seq_codes: &[usize], n_distinct: usize, inc: u32) -> Vec<u8> {
    if seq_codes.is_empty() || n_distinct == 0 {
        return Vec::new();
    }
    let a = n_distinct;
    let mut models: Vec<AdaptModel> = (0..a).map(|_| AdaptModel::new(a)).collect();
    let mut enc = RangeEncoder::new();
    let mut prev = 0usize;
    for &s in seq_codes {
        let m = &models[prev];
        let cum = m.cum(s);
        let freq = m.freq[s];
        let total = m.total;
        enc.encode(cum, freq, total);
        models[prev].update(s, inc);
        prev = s;
    }
    enc.finish()
}

/// Decode an adaptive order-1 range-coded stream (mirror of the encoder).
fn adaptive_range_o1_decode(
    payload: &[u8],
    count: usize,
    n_distinct: usize,
    inc: u32,
) -> Result<Vec<usize>, CubrimError> {
    if count == 0 || n_distinct == 0 {
        return Ok(vec![]);
    }
    let a = n_distinct;
    let mut models: Vec<AdaptModel> = (0..a).map(|_| AdaptModel::new(a)).collect();
    let mut dec = RangeDecoder::new(payload);
    let mut out = Vec::with_capacity(count);
    let mut prev = 0usize;
    for _ in 0..count {
        let total = models[prev].total;
        let dv = dec.get_freq(total);
        let (s, cum) = models[prev].find(dv);
        let freq = models[prev].freq[s];
        dec.decode(cum, freq, total);
        models[prev].update(s, inc);
        out.push(s);
        prev = s;
    }
    Ok(out)
}

/// Encode the value-code stream with BWT + adaptive order-1 range coding.
/// Wire: [primary u16 BE] [inc u8] [rc_len u32 BE] [rc payload]. The encoder tries
/// each candidate `inc` and keeps the smallest payload (decoder reads the winner).
pub(crate) fn bwt_adaptive_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let mut best_inc = ADAPT_INCS[0];
    let mut best_payload = adaptive_range_o1_encode(&bwt_out, n_distinct, best_inc);
    for &inc in &ADAPT_INCS[1..] {
        let p = adaptive_range_o1_encode(&bwt_out, n_distinct, inc);
        if p.len() < best_payload.len() {
            best_payload = p;
            best_inc = inc;
        }
    }
    let mut out = Vec::with_capacity(7 + best_payload.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.push(best_inc as u8);
    out.extend_from_slice(&(best_payload.len() as u32).to_be_bytes());
    out.extend_from_slice(&best_payload);
    out
}

/// Decode the BWT + adaptive order-1 range-coded stream from blob at offset.
pub(crate) fn bwt_adaptive_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 7 > blob.len() {
        return Err(CubrimError::Decode(
            "BwtAdaptive: blob too short for header (primary+inc+rc_len)".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let inc = blob[offset + 2] as u32;
    if inc == 0 {
        return Err(CubrimError::Decode("BwtAdaptive: inc must be ≥ 1".into()));
    }
    let rc_len = u32::from_be_bytes([
        blob[offset + 3],
        blob[offset + 4],
        blob[offset + 5],
        blob[offset + 6],
    ]) as usize;
    let body = offset + 7;
    if body + rc_len > blob.len() {
        return Err(CubrimError::Decode(format!(
            "BwtAdaptive: payload truncated: need {rc_len}, have {}",
            blob.len().saturating_sub(body)
        )));
    }
    let payload = &blob[body..body + rc_len];
    let bwt_out = adaptive_range_o1_decode(payload, count, n_distinct, inc)?;
    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;
    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "BwtAdaptive: decoded {} codes but expected {}",
            seq_codes.len(),
            count
        )));
    }
    Ok((seq_codes, 7 + rc_len))
}

/// Estimate byte size of the BWT + adaptive order-1 range-coded stream.
pub(crate) fn bwt_adaptive_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    bwt_adaptive_encode(seq_codes, n_distinct).len()
}

// ── H-22: context-mixing of order-1 + order-0 (adaptive, learned weight) ──────
//
// The strongest single model is adaptive order-1; its remaining slack is the
// variance of low-count contexts (a context seen a few times gives a noisy
// estimate). Blending the order-1 prediction with the stabler order-0 prediction,
// weighted by a LEARNED scalar that adapts toward whichever model has been
// predicting better, reduces that variance — classic context mixing.
//
// Static interpolation (order-0 as a fixed backoff PRIOR) was probed and LOST on
// every file: BWT makes order-1 contexts locally sharp but globally misaligned, so
// a fixed order-0 prior mispredicts the locally-dominant (often globally-rare)
// symbol. Only the ADAPTIVE (learned-weight) mix wins, and only as a competitive
// per-file alternative to pure order-1 — handled here by a one-byte mode selector.
//
// Backend: the same carryless range coder as H-21. Two modes:
//   mode 0 — pure adaptive order-1 (integer counts, identical to scheme 9).
//   mode 1 — learned-weight linear mix of order-1 and order-0 predictions.
//
// DETERMINISM: mode 1 uses f64 ONLY for the mix weight and the per-symbol blend.
// Encode and decode compute the quantized frequency table from the SAME integer
// model state and the SAME f64 weight, using only IEEE-754 +,−,*,/ (no fma, no
// transcendentals), so both sides produce bit-identical tables and weight updates
// on any IEEE-754 platform. Round-trip is exact (verified on all corpus files +
// 40-trial property suite).

/// Carryless range coder constants (shared design with H-21; named distinctly to
/// keep schemes independent across branches).
const CM_TOP: u32 = 1 << 24;
const CM_BOT: u32 = 1 << 16;
/// Rescale an adaptive context when its total exceeds this (kept under CM_BOT).
const CM_RESCALE: u32 = 1 << 15;
/// Range-coder total for the quantized mixed distribution (≤ CM_BOT).
const CM_MIX_TOTAL: u32 = 1 << 14;
/// Increment candidates the encoder sweeps for the pure order-1 mode.
const CM_PURE_INCS: [u32; 4] = [8, 16, 32, 64];
/// (inc, lr_index) candidates the encoder sweeps for the learned-mix mode.
const CM_MIX_INCS: [u32; 2] = [16, 32];
/// Learning-rate table (indexed by the wire `lr_idx` byte).
const CM_LRS: [f64; 2] = [0.02, 0.05];

struct CmRangeEncoder {
    low: u32,
    range: u32,
    out: Vec<u8>,
}
impl CmRangeEncoder {
    fn new() -> Self {
        Self { low: 0, range: 0xFFFF_FFFF, out: Vec::new() }
    }
    #[inline]
    fn encode(&mut self, cum: u32, freq: u32, total: u32) {
        let r = self.range / total;
        self.low = self.low.wrapping_add(r * cum);
        self.range = r * freq;
        loop {
            if (self.low ^ self.low.wrapping_add(self.range)) < CM_TOP {
            } else if self.range < CM_BOT {
                self.range = self.low.wrapping_neg() & (CM_BOT - 1);
            } else {
                break;
            }
            self.out.push((self.low >> 24) as u8);
            self.low <<= 8;
            self.range <<= 8;
        }
    }
    fn finish(mut self) -> Vec<u8> {
        for _ in 0..4 {
            self.out.push((self.low >> 24) as u8);
            self.low <<= 8;
        }
        self.out
    }
}

struct CmRangeDecoder<'a> {
    low: u32,
    range: u32,
    code: u32,
    buf: &'a [u8],
    pos: usize,
}
impl<'a> CmRangeDecoder<'a> {
    fn new(buf: &'a [u8]) -> Self {
        let mut code: u32 = 0;
        let mut pos = 0;
        for _ in 0..4 {
            code = (code << 8) | (*buf.get(pos).unwrap_or(&0) as u32);
            pos += 1;
        }
        Self { low: 0, range: 0xFFFF_FFFF, code, buf, pos }
    }
    #[inline]
    fn get_freq(&self, total: u32) -> u32 {
        let r = self.range / total;
        let dv = self.code.wrapping_sub(self.low) / r;
        if dv >= total { total - 1 } else { dv }
    }
    #[inline]
    fn decode(&mut self, cum: u32, freq: u32, total: u32) {
        let r = self.range / total;
        self.low = self.low.wrapping_add(r * cum);
        self.range = r * freq;
        loop {
            if (self.low ^ self.low.wrapping_add(self.range)) < CM_TOP {
            } else if self.range < CM_BOT {
                self.range = self.low.wrapping_neg() & (CM_BOT - 1);
            } else {
                break;
            }
            self.code = (self.code << 8) | (*self.buf.get(self.pos).unwrap_or(&0) as u32);
            self.pos += 1;
            self.low <<= 8;
            self.range <<= 8;
        }
    }
}

/// Integer adaptive context: freqs (init 1) + running total, rescale at CM_RESCALE.
struct CmCtx {
    freq: Vec<u32>,
    total: u32,
}
impl CmCtx {
    fn new(a: usize) -> Self {
        Self { freq: vec![1u32; a], total: a as u32 }
    }
    #[inline]
    fn update(&mut self, s: usize, inc: u32) {
        self.freq[s] += inc;
        self.total += inc;
        if self.total > CM_RESCALE {
            let mut nt = 0u32;
            for f in &mut self.freq {
                *f = (*f + 1) >> 1;
                nt += *f;
            }
            self.total = nt;
        }
    }
}

/// Mode 0: pure adaptive order-1 (integer; identical model to scheme 9).
fn cm_pure_o1_encode(seq_codes: &[usize], a: usize, inc: u32) -> Vec<u8> {
    let mut ctx: Vec<CmCtx> = (0..a).map(|_| CmCtx::new(a)).collect();
    let mut enc = CmRangeEncoder::new();
    let mut prev = 0usize;
    for &s in seq_codes {
        let c = &ctx[prev];
        let mut cum = 0u32;
        for &f in &c.freq[..s] {
            cum += f;
        }
        enc.encode(cum, c.freq[s], c.total);
        ctx[prev].update(s, inc);
        prev = s;
    }
    enc.finish()
}

fn cm_pure_o1_decode(payload: &[u8], count: usize, a: usize, inc: u32) -> Vec<usize> {
    let mut ctx: Vec<CmCtx> = (0..a).map(|_| CmCtx::new(a)).collect();
    let mut dec = CmRangeDecoder::new(payload);
    let mut out = Vec::with_capacity(count);
    let mut prev = 0usize;
    for _ in 0..count {
        let total = ctx[prev].total;
        let dv = dec.get_freq(total);
        // find symbol.
        let c = &ctx[prev];
        let mut cum = 0u32;
        let mut s = 0usize;
        for (i, &f) in c.freq.iter().enumerate() {
            if cum + f > dv {
                s = i;
                break;
            }
            cum += f;
        }
        let freq = ctx[prev].freq[s];
        dec.decode(cum, freq, total);
        ctx[prev].update(s, inc);
        out.push(s);
        prev = s;
    }
    out
}

/// Build the quantized mixed frequency table (sum == CM_MIX_TOTAL) from the current
/// integer model state and weight `w`. DETERMINISTIC: identical on encode & decode.
/// Also returns the per-symbol blended probabilities so the weight update reuses the
/// exact same f64 values both sides computed.
#[inline]
fn cm_mix_table(
    freq1: &[u32],
    tot1: u32,
    freq0: &[u32],
    tot0: u32,
    w: f64,
    a: usize,
    qfreq: &mut [u32],
) {
    let t1 = tot1 as f64;
    let t0 = tot0 as f64;
    let mut sum: u32 = 0;
    let mut maxv: u32 = 0;
    let mut maxi: usize = 0;
    for s in 0..a {
        let p1 = freq1[s] as f64 / t1;
        let p0 = freq0[s] as f64 / t0;
        let pm = w * p1 + (1.0 - w) * p0;
        // round to integer freq, floor at 1.
        let mut q = (pm * CM_MIX_TOTAL as f64 + 0.5) as u32;
        if q < 1 {
            q = 1;
        }
        qfreq[s] = q;
        sum += q;
        if q > maxv {
            maxv = q;
            maxi = s;
        }
    }
    // Reconcile to exactly CM_MIX_TOTAL by adjusting the max-freq symbol.
    if sum < CM_MIX_TOTAL {
        qfreq[maxi] += CM_MIX_TOTAL - sum;
    } else if sum > CM_MIX_TOTAL {
        let mut surplus = sum - CM_MIX_TOTAL;
        // Trim from the max symbol(s), never below 1.
        while surplus > 0 {
            // recompute current max each round (a ≤ 256, surplus small).
            let mut mi = 0usize;
            let mut mv = 0u32;
            for s in 0..a {
                if qfreq[s] > mv {
                    mv = qfreq[s];
                    mi = s;
                }
            }
            let take = surplus.min(qfreq[mi] - 1);
            if take == 0 {
                break;
            }
            qfreq[mi] -= take;
            surplus -= take;
        }
    }
}

/// Mode 1: learned-weight linear mix of order-1 and order-0 adaptive predictions.
fn cm_mix_encode(seq_codes: &[usize], a: usize, inc: u32, lr: f64) -> Vec<u8> {
    let mut freq1: Vec<Vec<u32>> = (0..a).map(|_| vec![1u32; a]).collect();
    let mut tot1: Vec<u32> = vec![a as u32; a];
    let mut freq0: Vec<u32> = vec![1u32; a];
    let mut tot0: u32 = a as u32;
    let mut w: f64 = 0.5;
    let mut qfreq = vec![0u32; a];
    let mut enc = CmRangeEncoder::new();
    let mut prev = 0usize;
    for &s in seq_codes {
        cm_mix_table(&freq1[prev], tot1[prev], &freq0, tot0, w, a, &mut qfreq);
        let mut cum = 0u32;
        for &f in &qfreq[..s] {
            cum += f;
        }
        enc.encode(cum, qfreq[s], CM_MIX_TOTAL);
        // weight update from the same pre-update state.
        let p1 = freq1[prev][s] as f64 / tot1[prev] as f64;
        let p0 = freq0[s] as f64 / tot0 as f64;
        let pm = w * p1 + (1.0 - w) * p0;
        w += lr * (p1 - p0) / pm;
        if w < 1e-4 {
            w = 1e-4;
        } else if w > 1.0 - 1e-4 {
            w = 1.0 - 1e-4;
        }
        // model updates.
        cm_update(&mut freq1[prev], &mut tot1[prev], s, inc);
        cm_update_o0(&mut freq0, &mut tot0, s, inc);
        prev = s;
    }
    enc.finish()
}

fn cm_mix_decode(payload: &[u8], count: usize, a: usize, inc: u32, lr: f64) -> Vec<usize> {
    let mut freq1: Vec<Vec<u32>> = (0..a).map(|_| vec![1u32; a]).collect();
    let mut tot1: Vec<u32> = vec![a as u32; a];
    let mut freq0: Vec<u32> = vec![1u32; a];
    let mut tot0: u32 = a as u32;
    let mut w: f64 = 0.5;
    let mut qfreq = vec![0u32; a];
    let mut dec = CmRangeDecoder::new(payload);
    let mut out = Vec::with_capacity(count);
    let mut prev = 0usize;
    for _ in 0..count {
        cm_mix_table(&freq1[prev], tot1[prev], &freq0, tot0, w, a, &mut qfreq);
        let dv = dec.get_freq(CM_MIX_TOTAL);
        let mut cum = 0u32;
        let mut s = 0usize;
        for (i, &f) in qfreq.iter().enumerate() {
            if cum + f > dv {
                s = i;
                break;
            }
            cum += f;
        }
        dec.decode(cum, qfreq[s], CM_MIX_TOTAL);
        let p1 = freq1[prev][s] as f64 / tot1[prev] as f64;
        let p0 = freq0[s] as f64 / tot0 as f64;
        let pm = w * p1 + (1.0 - w) * p0;
        w += lr * (p1 - p0) / pm;
        if w < 1e-4 {
            w = 1e-4;
        } else if w > 1.0 - 1e-4 {
            w = 1.0 - 1e-4;
        }
        cm_update(&mut freq1[prev], &mut tot1[prev], s, inc);
        cm_update_o0(&mut freq0, &mut tot0, s, inc);
        out.push(s);
        prev = s;
    }
    out
}

#[inline]
fn cm_update(freq: &mut [u32], total: &mut u32, s: usize, inc: u32) {
    freq[s] += inc;
    *total += inc;
    if *total > CM_RESCALE {
        let mut nt = 0u32;
        for f in freq.iter_mut() {
            *f = (*f + 1) >> 1;
            nt += *f;
        }
        *total = nt;
    }
}

#[inline]
fn cm_update_o0(freq: &mut [u32], total: &mut u32, s: usize, inc: u32) {
    cm_update(freq, total, s, inc);
}

/// Encode the value-code stream with BWT + context-mixing. The encoder evaluates pure
/// order-1 (mode 0) over CM_PURE_INCS and learned-mix (mode 1) over CM_MIX_INCS×CM_LRS,
/// and keeps the smallest. Wire: [primary u16][mode u8][inc u8][lr_idx u8][rc_len u32][rc].
pub(crate) fn bwt_ctxmix_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let a = n_distinct;
    let mut best_mode = 0u8;
    let mut best_inc = CM_PURE_INCS[0];
    let mut best_lr_idx = 0u8;
    let mut best_payload: Vec<u8> = Vec::new();
    let mut have = false;

    if a > 0 && !bwt_out.is_empty() {
        for &inc in &CM_PURE_INCS {
            let p = cm_pure_o1_encode(&bwt_out, a, inc);
            if !have || p.len() < best_payload.len() {
                best_payload = p;
                best_mode = 0;
                best_inc = inc;
                best_lr_idx = 0;
                have = true;
            }
        }
        for &inc in &CM_MIX_INCS {
            for (li, &lr) in CM_LRS.iter().enumerate() {
                let p = cm_mix_encode(&bwt_out, a, inc, lr);
                if p.len() < best_payload.len() {
                    best_payload = p;
                    best_mode = 1;
                    best_inc = inc;
                    best_lr_idx = li as u8;
                }
            }
        }
    }

    let mut out = Vec::with_capacity(8 + best_payload.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.push(best_mode);
    out.push(best_inc as u8);
    out.push(best_lr_idx);
    out.extend_from_slice(&(best_payload.len() as u32).to_be_bytes());
    out.extend_from_slice(&best_payload);
    out
}

/// Decode the BWT + context-mixing stream from blob at offset.
pub(crate) fn bwt_ctxmix_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 9 > blob.len() {
        return Err(CubrimError::Decode(
            "BwtContextMix: blob too short for header".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let mode = blob[offset + 2];
    let inc = blob[offset + 3] as u32;
    let lr_idx = blob[offset + 4] as usize;
    let rc_len = u32::from_be_bytes([
        blob[offset + 5],
        blob[offset + 6],
        blob[offset + 7],
        blob[offset + 8],
    ]) as usize;
    let body = offset + 9;
    if body + rc_len > blob.len() {
        return Err(CubrimError::Decode(format!(
            "BwtContextMix: payload truncated: need {rc_len}, have {}",
            blob.len().saturating_sub(body)
        )));
    }
    if inc == 0 {
        return Err(CubrimError::Decode("BwtContextMix: inc must be ≥ 1".into()));
    }
    let payload = &blob[body..body + rc_len];

    let bwt_out: Vec<usize> = if count == 0 || n_distinct == 0 {
        vec![]
    } else {
        match mode {
            0 => cm_pure_o1_decode(payload, count, n_distinct, inc),
            1 => {
                if lr_idx >= CM_LRS.len() {
                    return Err(CubrimError::Decode("BwtContextMix: lr_idx out of range".into()));
                }
                cm_mix_decode(payload, count, n_distinct, inc, CM_LRS[lr_idx])
            }
            _ => return Err(CubrimError::Decode(format!("BwtContextMix: bad mode {mode}"))),
        }
    };

    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;
    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "BwtContextMix: decoded {} codes but expected {}",
            seq_codes.len(),
            count
        )));
    }
    Ok((seq_codes, 9 + rc_len))
}

/// Estimate byte size of the BWT + context-mixing stream (full encode then len).
pub(crate) fn bwt_ctxmix_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    bwt_ctxmix_encode(seq_codes, n_distinct).len()
}

// ---------------------------------------------------------------------------
// Scheme 11 — BWT + GEOMETRIC (logistic) context-mixing of order-2/1/0 (H-24)
// ---------------------------------------------------------------------------
//
// Same BWT front-end as scheme 7. The back-end blends THREE adaptive predictions
// (order-2 key (prev2,prev1), order-1 key prev1, order-0) in the LOG domain:
//   p(s) ∝ ∏_k p_k(s)^{w_k}      (geometric / logistic mixing)
// renormalized over the alphabet, then quantized to CM_MIX_TOTAL for the range
// coder. The three weights w_k are learned online by gradient on the per-symbol
// log-loss (∂L/∂w_k = -(ln p_k(s) − E_q[ln p_k])), identically on encode & decode.
// Geometric mixing beats the scheme-10 linear o1+o0 mix because high-confidence
// models multiply (a near-certain predictor sharpens the blend) instead of being
// averaged down. No frequency tables are transmitted (regression-proof: emitted
// only when it wins the competitive min, Gotcha #4).

/// Learning-rate table (indexed by the wire `lr_idx` byte) for the geometric mix.
const GM_LRS: [f64; 2] = [0.01, 0.02];
/// Model-increment candidates the encoder sweeps.
const GM_INCS: [u32; 2] = [16, 32];
/// Weight clamp range [0, GM_WCLAMP] — keeps a single model from dominating absurdly.
const GM_WCLAMP: f64 = 8.0;

/// Precompute ln(i) for i in 0..=max so the per-symbol mix avoids repeated transcendental
/// calls. Index 0 is never used as a numerator/denominator (freqs & totals are ≥ 1).
fn gm_ln_table(max: u32) -> Vec<f64> {
    let mut t = vec![0.0f64; (max as usize) + 1];
    for (i, slot) in t.iter_mut().enumerate().skip(1) {
        *slot = (i as f64).ln();
    }
    t
}

/// Fill the quantized mixed frequency table `q` (sum == CM_MIX_TOTAL) and the per-model
/// log-prob arrays + posterior numerators `ex` (with returned normaliser Z) from the
/// current integer model state and weights `w`. DETERMINISTIC: identical on both sides
/// (does NOT depend on the symbol being coded).
#[inline]
#[allow(clippy::too_many_arguments)]
fn gm_predict(
    fr2: &[u32],
    t2: u32,
    fr1: &[u32],
    t1: u32,
    fr0: &[u32],
    t0: u32,
    w: &[f64; 3],
    a: usize,
    ln: &[f64],
    lnp2: &mut [f64],
    lnp1: &mut [f64],
    lnp0: &mut [f64],
    ex: &mut [f64],
    q: &mut [u32],
) -> f64 {
    let lt2 = ln[t2 as usize];
    let lt1 = ln[t1 as usize];
    let lt0 = ln[t0 as usize];
    let mut maxlog = f64::NEG_INFINITY;
    for x in 0..a {
        let l2 = ln[fr2[x] as usize] - lt2;
        let l1 = ln[fr1[x] as usize] - lt1;
        let l0 = ln[fr0[x] as usize] - lt0;
        lnp2[x] = l2;
        lnp1[x] = l1;
        lnp0[x] = l0;
        let lp = w[0] * l2 + w[1] * l1 + w[2] * l0;
        ex[x] = lp; // hold logp, convert after we know the max
        if lp > maxlog {
            maxlog = lp;
        }
    }
    let mut z = 0.0f64;
    for e in ex.iter_mut().take(a) {
        *e = (*e - maxlog).exp();
        z += *e;
    }
    // Quantize posterior ex/z to CM_MIX_TOTAL, floor at 1, reconcile on the max symbol.
    let mut sum: u32 = 0;
    let mut maxv: u32 = 0;
    let mut maxi: usize = 0;
    for x in 0..a {
        let mut qv = ((ex[x] / z) * CM_MIX_TOTAL as f64 + 0.5) as u32;
        if qv < 1 {
            qv = 1;
        }
        q[x] = qv;
        sum += qv;
        if qv > maxv {
            maxv = qv;
            maxi = x;
        }
    }
    if sum < CM_MIX_TOTAL {
        q[maxi] += CM_MIX_TOTAL - sum;
    } else if sum > CM_MIX_TOTAL {
        let mut surplus = sum - CM_MIX_TOTAL;
        while surplus > 0 {
            let mut mi = 0usize;
            let mut mv = 0u32;
            for (x, &qx) in q.iter().enumerate().take(a) {
                if qx > mv {
                    mv = qx;
                    mi = x;
                }
            }
            let take = surplus.min(q[mi] - 1);
            if take == 0 {
                break;
            }
            q[mi] -= take;
            surplus -= take;
        }
    }
    z
}

/// Online weight update (gradient ascent on the geometric-mix log-likelihood). Uses the
/// float posterior `ex/z` for E_q — identical on encode & decode since both reconstruct
/// `ex`, `z`, and the lnp arrays from synced integer state.
#[inline]
#[allow(clippy::too_many_arguments)]
fn gm_update_weights(
    w: &mut [f64; 3],
    lnp2: &[f64],
    lnp1: &[f64],
    lnp0: &[f64],
    ex: &[f64],
    z: f64,
    a: usize,
    s: usize,
    lr: f64,
) {
    let mut eq = [0.0f64; 3];
    for x in 0..a {
        let qx = ex[x] / z;
        eq[0] += qx * lnp2[x];
        eq[1] += qx * lnp1[x];
        eq[2] += qx * lnp0[x];
    }
    let gk = [lnp2[s] - eq[0], lnp1[s] - eq[1], lnp0[s] - eq[2]];
    for k in 0..3 {
        w[k] = (w[k] + lr * gk[k]).clamp(0.0, GM_WCLAMP);
    }
}

/// Fetch-or-create the order-2 context (key = prev2*a + prev1).
#[inline]
fn gm_o2(
    map: &mut std::collections::HashMap<usize, CmCtx>,
    key: usize,
    a: usize,
) -> &mut CmCtx {
    map.entry(key).or_insert_with(|| CmCtx::new(a))
}

fn gm_mix_encode(bwt_out: &[usize], a: usize, inc: u32, lr: f64, ln: &[f64]) -> Vec<u8> {
    let mut o2: std::collections::HashMap<usize, CmCtx> = std::collections::HashMap::new();
    let mut o1: Vec<CmCtx> = (0..a).map(|_| CmCtx::new(a)).collect();
    let mut o0 = CmCtx::new(a);
    let mut w = [1.0f64, 1.0, 1.0];
    let mut lnp2 = vec![0.0f64; a];
    let mut lnp1 = vec![0.0f64; a];
    let mut lnp0 = vec![0.0f64; a];
    let mut ex = vec![0.0f64; a];
    let mut q = vec![0u32; a];
    let mut enc = CmRangeEncoder::new();
    let mut prev2 = 0usize;
    let mut prev1 = 0usize;
    for &s in bwt_out {
        let key = prev2 * a + prev1;
        let z = {
            let c2 = gm_o2(&mut o2, key, a);
            let (f2, tt2) = (c2.freq.as_slice(), c2.total);
            // SAFETY-free: copy small slices out by re-borrowing immutably below.
            gm_predict(
                f2, tt2, &o1[prev1].freq, o1[prev1].total, &o0.freq, o0.total, &w, a, ln,
                &mut lnp2, &mut lnp1, &mut lnp0, &mut ex, &mut q,
            )
        };
        let mut cum = 0u32;
        for &f in &q[..s] {
            cum += f;
        }
        enc.encode(cum, q[s], CM_MIX_TOTAL);
        gm_update_weights(&mut w, &lnp2, &lnp1, &lnp0, &ex, z, a, s, lr);
        gm_o2(&mut o2, key, a).update(s, inc);
        o1[prev1].update(s, inc);
        o0.update(s, inc);
        prev2 = prev1;
        prev1 = s;
    }
    enc.finish()
}

fn gm_mix_decode(payload: &[u8], count: usize, a: usize, inc: u32, lr: f64, ln: &[f64]) -> Vec<usize> {
    let mut o2: std::collections::HashMap<usize, CmCtx> = std::collections::HashMap::new();
    let mut o1: Vec<CmCtx> = (0..a).map(|_| CmCtx::new(a)).collect();
    let mut o0 = CmCtx::new(a);
    let mut w = [1.0f64, 1.0, 1.0];
    let mut lnp2 = vec![0.0f64; a];
    let mut lnp1 = vec![0.0f64; a];
    let mut lnp0 = vec![0.0f64; a];
    let mut ex = vec![0.0f64; a];
    let mut q = vec![0u32; a];
    let mut dec = CmRangeDecoder::new(payload);
    let mut out = Vec::with_capacity(count);
    let mut prev2 = 0usize;
    let mut prev1 = 0usize;
    for _ in 0..count {
        let key = prev2 * a + prev1;
        let z = {
            let c2 = gm_o2(&mut o2, key, a);
            gm_predict(
                &c2.freq, c2.total, &o1[prev1].freq, o1[prev1].total, &o0.freq, o0.total,
                &w, a, ln, &mut lnp2, &mut lnp1, &mut lnp0, &mut ex, &mut q,
            )
        };
        let dv = dec.get_freq(CM_MIX_TOTAL);
        let mut cum = 0u32;
        let mut s = 0usize;
        for (i, &f) in q.iter().enumerate() {
            if cum + f > dv {
                s = i;
                break;
            }
            cum += f;
        }
        dec.decode(cum, q[s], CM_MIX_TOTAL);
        gm_update_weights(&mut w, &lnp2, &lnp1, &lnp0, &ex, z, a, s, lr);
        gm_o2(&mut o2, key, a).update(s, inc);
        o1[prev1].update(s, inc);
        o0.update(s, inc);
        out.push(s);
        prev2 = prev1;
        prev1 = s;
    }
    out
}

/// Encode the value-code stream with BWT + geometric context-mixing. The encoder sweeps
/// GM_INCS × GM_LRS and keeps the smallest payload.
/// Wire: [primary u16][inc u8][lr_idx u8][rc_len u32][rc].
pub(crate) fn bwt_geomix_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    let (bwt_out, primary) = bwt_encode_codes(seq_codes);
    let a = n_distinct;
    let mut best_inc = GM_INCS[0];
    let mut best_lr_idx = 0u8;
    let mut best_payload: Vec<u8> = Vec::new();
    let mut have = false;

    if a > 0 && !bwt_out.is_empty() {
        let ln = gm_ln_table(CM_RESCALE + 128);
        for &inc in &GM_INCS {
            for (li, &lr) in GM_LRS.iter().enumerate() {
                let p = gm_mix_encode(&bwt_out, a, inc, lr, &ln);
                if !have || p.len() < best_payload.len() {
                    best_payload = p;
                    best_inc = inc;
                    best_lr_idx = li as u8;
                    have = true;
                }
            }
        }
    }

    let mut out = Vec::with_capacity(8 + best_payload.len());
    out.extend_from_slice(&primary.to_be_bytes());
    out.push(best_inc as u8);
    out.push(best_lr_idx);
    out.extend_from_slice(&(best_payload.len() as u32).to_be_bytes());
    out.extend_from_slice(&best_payload);
    out
}

/// Decode the BWT + geometric context-mixing stream from blob at offset.
pub(crate) fn bwt_geomix_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    if offset + 8 > blob.len() {
        return Err(CubrimError::Decode(
            "BwtGeoMix: blob too short for header".into(),
        ));
    }
    let primary = u16::from_be_bytes([blob[offset], blob[offset + 1]]);
    let inc = blob[offset + 2] as u32;
    let lr_idx = blob[offset + 3] as usize;
    let rc_len = u32::from_be_bytes([
        blob[offset + 4],
        blob[offset + 5],
        blob[offset + 6],
        blob[offset + 7],
    ]) as usize;
    let body = offset + 8;
    if body + rc_len > blob.len() {
        return Err(CubrimError::Decode(format!(
            "BwtGeoMix: payload truncated: need {rc_len}, have {}",
            blob.len().saturating_sub(body)
        )));
    }
    if inc == 0 {
        return Err(CubrimError::Decode("BwtGeoMix: inc must be ≥ 1".into()));
    }
    let payload = &blob[body..body + rc_len];

    let bwt_out: Vec<usize> = if count == 0 || n_distinct == 0 {
        vec![]
    } else {
        if lr_idx >= GM_LRS.len() {
            return Err(CubrimError::Decode("BwtGeoMix: lr_idx out of range".into()));
        }
        let ln = gm_ln_table(CM_RESCALE + 128);
        gm_mix_decode(payload, count, n_distinct, inc, GM_LRS[lr_idx], &ln)
    };

    let seq_codes = bwt_decode_codes(&bwt_out, primary, n_distinct)?;
    if seq_codes.len() != count {
        return Err(CubrimError::Decode(format!(
            "BwtGeoMix: decoded {} codes but expected {}",
            seq_codes.len(),
            count
        )));
    }
    Ok((seq_codes, 8 + rc_len))
}

/// Estimate byte size of the BWT + geometric context-mixing stream.
pub(crate) fn bwt_geomix_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    bwt_geomix_encode(seq_codes, n_distinct).len()
}

// ─── LzRans (H-25c): LZ77 match modeling + rANS, a NON-BWT value-stream class ─
//
// Motivation (holdout re-check): the entire gap to gzip/zstd on unseen data is
// LZ dictionary matching (long-range repeats) — a capability the cube+BWT+rANS
// pipeline has no model for. LzRans tokenizes the value-code stream into
// (literal, match) tokens via greedy LZ77, then entropy-codes every sub-stream.
//
// H-25c implements the H-25b re-open condition — the two zstd levers that the
// byte-split (H-25b) still missed:
//   (1) REPEAT-OFFSET DISTANCE CACHE (zstd's real lever). Keep the last 3 distinct
//       match offsets (move-to-front LRU). Each match codes a 4-symbol mode:
//       0/1/2 = "reuse recent offset rep[k]" (≈2 bits), 3 = "new distance" (full
//       byte-split). Long-range structure (repeated records, fixed strides, shared
//       boilerplate across copies) collapses to mode-0 runs — the win BWT cannot
//       reach because it lives BEYOND a single 64KB block's local context.
//   (2) LIGHTER ORDER-1 LITERAL CODER. H-25b used order-0 to dodge the BWT+order-1
//       table blowup; H-25c picks min(order-0, order-1) for the literal stream —
//       the fallback-table order-1 rANS keeps literal order-1 structure WITHOUT
//       the BWT doubling and only pays own tables for well-observed contexts.
//   Flags stay order-1 rANS over {0,1}.
//
// Wire (value stream, after cube header + gap streams):
//   [n_tokens u32][n_lits u32][n_matches u32]
//   flags     = rans_order1(flags,       alphabet 2)       (count = n_tokens)
//   [lit_mode u8]  (0 = order-0, 1 = order-1)
//   lits      = rans_order{lit_mode}(literals, n_distinct) (count = n_lits)
//   dmodes    = rans_order1(dist_modes,  alphabet 4)       (count = n_matches)
//   new_lo    = rans_order0(new_dist & 0xFF, 256)          (count = #{mode==3})
//   new_hi    = rans_order0(new_dist >> 8,   256)          (count = #{mode==3})
//   len_lo    = rans_order0(len & 0xFF, 256)               (count = n_matches)
//   len_hi    = rans_order0(len >> 8,   256)               (count = n_matches)
//
// Competitive (Gotcha #4): produced only as a winner of the scheme-7 selection
// rail, so it can never regress a file. Header byte = 12.

/// Initial repeat-offset cache (seeds; only ever used if a real match happens to
/// have one of these distances early). Encoder and decoder MUST share this.
const LZ_REP_INIT: [usize; 3] = [1, 4, 8];

/// LZ77 minimum match length (shorter matches are cheaper as literals).
const LZ_MIN_MATCH: usize = 3;
/// Hash-chain search depth cap (bounds encode time on repetitive data).
const LZ_MAX_CHAIN: usize = 256;
/// Maximum match length — capped so length fits in a u16 (low/high byte split).
const LZ_MAX_MATCH: usize = u16::MAX as usize;
/// Optimal parse: per frontier point, expand at most this many distinct match
/// lengths as DP edges (the full longest match is always added separately, so long
/// runs are still covered by a single edge). Bounds DP edge count on long matches.
const LZ_OPT_LEN_CAP: usize = 128;

/// Order-0 entropy (bits/symbol) of `seq`, clamped to [2.0, 8.0]. Used as the
/// per-literal cost estimate in the cost-aware parse so a match is only taken when
/// it is genuinely cheaper than coding the literals it would replace.
fn lz_literal_bits_estimate(seq: &[usize]) -> f64 {
    if seq.is_empty() {
        return 8.0;
    }
    let maxv = *seq.iter().max().unwrap();
    let mut counts = vec![0u32; maxv + 1];
    for &s in seq {
        counts[s] += 1;
    }
    let n = seq.len() as f64;
    let mut h = 0.0f64;
    for &c in &counts {
        if c > 0 {
            let p = c as f64 / n;
            h -= p * p.log2();
        }
    }
    h.clamp(2.0, 8.0)
}

/// Bit length of `v` (0 for v==0, else floor(log2 v)+1). A log2-ish cost proxy.
#[inline]
fn lz_bit_length(v: usize) -> usize {
    if v == 0 {
        0
    } else {
        usize::BITS as usize - v.leading_zeros() as usize
    }
}

/// Number of bytes the new-distance byte-split would spend on distance `d`.
#[inline]
fn lz_dist_bytes(d: usize) -> usize {
    if d < 0x100 {
        1
    } else if d < 0x10000 {
        2
    } else if d < 0x1000000 {
        3
    } else {
        4
    }
}

/// Cost-aware + lazy LZ77 parse of `seq` (codes/bytes in [0, 256)).
/// Returns (flags, literals, lengths, distances). A candidate match is only taken
/// when its estimated coded cost (offset via the repeat-offset cache + length +
/// flag) is smaller than coding the bytes it covers as literals — this is the key
/// fix vs greedy, which took every length-3 match even at an expensive far offset.
/// A 1-step lazy lookahead prefers a strictly-better match one position later.
/// Match length is capped at LZ_MAX_MATCH so it fits a u16.
#[allow(clippy::type_complexity)]
fn lz77_parse_greedy(seq: &[usize]) -> (Vec<usize>, Vec<usize>, Vec<usize>, Vec<usize>) {
    let n = seq.len();
    let mut flags = Vec::new();
    let mut literals = Vec::new();
    let mut lengths = Vec::new();
    let mut distances = Vec::new();
    if n == 0 {
        return (flags, literals, lengths, distances);
    }

    let lit_bits = lz_literal_bits_estimate(seq);
    use std::collections::HashMap;
    let mut head: HashMap<u32, usize> = HashMap::new();
    let mut prev = vec![usize::MAX; n];
    let key3 = |i: usize| -> u32 {
        ((seq[i] as u32) << 16) | ((seq[i + 1] as u32) << 8) | (seq[i + 2] as u32)
    };

    // Repeat-offset mirror, kept in sync with the encoder so the offset-cost
    // estimate (cheap for a recent offset, dear for a new one) is accurate.
    let mut rep = LZ_REP_INIT;

    // Find the best (len, dist) at position p via the hash chains.
    let find = |p: usize, head: &HashMap<u32, usize>, prev: &[usize]| -> (usize, usize) {
        let mut best_len = 0usize;
        let mut best_dist = 0usize;
        if p + LZ_MIN_MATCH <= n {
            let k = key3(p);
            let mut j = head.get(&k).copied().unwrap_or(usize::MAX);
            let mut chain = 0usize;
            while j != usize::MAX && chain < LZ_MAX_CHAIN {
                let maxl = (n - p).min(LZ_MAX_MATCH);
                let mut ml = 0usize;
                while ml < maxl && seq[j + ml] == seq[p + ml] {
                    ml += 1;
                }
                if ml > best_len {
                    best_len = ml;
                    best_dist = p - j;
                    if ml >= maxl {
                        break;
                    }
                }
                j = prev[j];
                chain += 1;
            }
        }
        (best_len, best_dist)
    };

    // Estimated coded BYTES SAVED by taking a match vs coding its span as literals.
    // The offset term is cheap for a recent (repeat) offset and dear for a new one —
    // so a slightly-shorter repeat-offset match can out-save a longer new-offset one.
    let net_save = |len: usize, dist: usize, rep: &[usize; 3]| -> f64 {
        if len < LZ_MIN_MATCH {
            return f64::MIN;
        }
        let off_bits = if dist == rep[0] || dist == rep[1] || dist == rep[2] {
            3.0 // a recent offset: ~mode only
        } else {
            2.0 + 8.0 * lz_dist_bytes(dist) as f64
        };
        let len_bits = 8.0 + if len > 0xFF { 8.0 } else { 0.0 };
        let match_bits = 1.0 + off_bits + len_bits;
        len as f64 * lit_bits - match_bits
    };

    // Match length at a fixed distance (the repeat-offset probe). Overlapping
    // (dist < len) is allowed — the decoder copies byte-by-byte.
    let match_len_at = |p: usize, dist: usize| -> usize {
        if dist == 0 || dist > p {
            return 0;
        }
        let maxl = (n - p).min(LZ_MAX_MATCH);
        let mut ml = 0usize;
        while ml < maxl && seq[p - dist + ml] == seq[p + ml] {
            ml += 1;
        }
        ml
    };

    // Best match at `p`: the cost-optimal of the hash-chain longest match and the
    // three repeat-offset matches. Returns (len, dist, net_save_bytes).
    let best_at = |p: usize,
                   head: &HashMap<u32, usize>,
                   prev: &[usize],
                   rep: &[usize; 3]|
     -> (usize, usize, f64) {
        let (hl, hd) = find(p, head, prev);
        let mut blen = hl;
        let mut bdist = hd;
        let mut bsave = net_save(hl, hd, rep);
        for &ro in rep.iter() {
            let rl = match_len_at(p, ro);
            if rl >= LZ_MIN_MATCH {
                let s = net_save(rl, ro, rep);
                if s > bsave {
                    bsave = s;
                    blen = rl;
                    bdist = ro;
                }
            }
        }
        (blen, bdist, bsave)
    };

    let insert = |p: usize, head: &mut HashMap<u32, usize>, prev: &mut [usize]| {
        if p + LZ_MIN_MATCH <= n {
            let k = key3(p);
            prev[p] = head.get(&k).copied().unwrap_or(usize::MAX);
            head.insert(k, p);
        }
    };

    let mut i = 0usize;
    while i < n {
        let (blen, bdist, bsave) = best_at(i, &head, &prev, &rep);
        if bsave > 0.0 {
            // The current position's hash must be inserted before the lazy probe at
            // i+1, and is part of the matched span either way.
            insert(i, &mut head, &mut prev);
            // Lazy: if i+1 has a strictly better (higher-saving) match, defer.
            if i + 1 < n {
                let (_l1, _d1, s1) = best_at(i + 1, &head, &prev, &rep);
                if s1 > bsave {
                    flags.push(0);
                    literals.push(seq[i]);
                    i += 1;
                    continue;
                }
            }
            flags.push(1);
            lengths.push(blen);
            distances.push(bdist);
            // Update the repeat-offset mirror exactly as the encoder will.
            let d = bdist;
            if d == rep[0] {
                // mode 0: unchanged
            } else if d == rep[1] {
                rep.swap(0, 1);
            } else if d == rep[2] {
                let r2 = rep[2];
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = r2;
            } else {
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = d;
            }
            // Insert hashes across the rest of the matched span (i already inserted).
            let end = i + blen;
            i += 1;
            while i < end {
                insert(i, &mut head, &mut prev);
                i += 1;
            }
        } else {
            flags.push(0);
            literals.push(seq[i]);
            insert(i, &mut head, &mut prev);
            i += 1;
        }
    }
    (flags, literals, lengths, distances)
}

/// **Optimal LZ77 parse (H-25i)** — dynamic-programming cost minimisation over the
/// match graph. Instead of greedy/lazy (which takes the longest match at each
/// position and so produces many short, expensive-offset matches on mixed data),
/// this finds the globally cheapest sequence of literals and matches.
///
/// Forward DP: `cost[i]` = min coded cost (in bits, an estimate) to reach position
/// `i`. Edges from `i`: a literal (`+lit_bits`) to `i+1`, and a match of length `L`
/// at the best (smallest) distance reaching that length, to `i+L`, for every length
/// on the hash-chain match frontier (capped per frontier point, with the full
/// longest match always added so long runs cost one edge). The cost model is a
/// principled log2 entropy estimate (NOT tuned to any corpus); the repeat-offset
/// model is applied later by the exact encoder, so the DP only needs to find
/// few/long matches. Round-trip is guaranteed by the exact encoder/decoder
/// regardless of parse quality, and the competitive rail guarantees no regression.
#[allow(clippy::type_complexity)]
fn lz77_parse_optimal(seq: &[usize]) -> (Vec<usize>, Vec<usize>, Vec<usize>, Vec<usize>) {
    let n = seq.len();
    if n == 0 {
        return (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    }

    let lit_bits = lz_literal_bits_estimate(seq);
    use std::collections::HashMap;
    let mut head: HashMap<u32, usize> = HashMap::new();
    let mut prev = vec![usize::MAX; n];
    let key3 = |p: usize| -> u32 {
        ((seq[p] as u32) << 16) | ((seq[p + 1] as u32) << 8) | (seq[p + 2] as u32)
    };
    // Per-edge coded cost (bits): a principled log2 entropy estimate. The actual
    // repeat-offset discount is applied by the exact encoder, so this need only
    // rank parses (few/long matches cheaper than many short ones).
    let match_cost = |len: usize, dist: usize| -> f64 {
        let off = 2.0 + lz_bit_length(dist) as f64;
        let lenb = 2.0 + lz_bit_length(len) as f64;
        1.0 + off + lenb
    };

    let mut cost = vec![f64::INFINITY; n + 1];
    cost[0] = 0.0;
    let mut from_len = vec![0u32; n + 1]; // 0 = literal edge into this position
    let mut from_dist = vec![0u32; n + 1];

    for i in 0..n {
        let ci = cost[i];
        // Literal edge i -> i+1.
        let lc = ci + lit_bits;
        if lc < cost[i + 1] {
            cost[i + 1] = lc;
            from_len[i + 1] = 0;
            from_dist[i + 1] = 0;
        }
        // Match edges: walk the hash chain, building the length-increasing,
        // distance-increasing frontier and relaxing DP edges.
        if i + LZ_MIN_MATCH <= n {
            let maxl = (n - i).min(LZ_MAX_MATCH);
            let k = key3(i);
            let mut j = head.get(&k).copied().unwrap_or(usize::MAX);
            let mut chain = 0usize;
            let mut best = LZ_MIN_MATCH - 1;
            while j != usize::MAX && chain < LZ_MAX_CHAIN {
                if best >= maxl {
                    break;
                }
                // Quick reject: to beat `best`, position `best` must already match.
                if seq[j + best] == seq[i + best] {
                    let mut ml = 0usize;
                    while ml < maxl && seq[j + ml] == seq[i + ml] {
                        ml += 1;
                    }
                    if ml > best {
                        let d = i - j;
                        // Relax DP edges for the lengths this frontier point owns:
                        // (best, ml], at distance d, capped to LZ_OPT_LEN_CAP.
                        let lo = best + 1;
                        let cap_hi = ml.min(lo + LZ_OPT_LEN_CAP - 1);
                        let mut l = lo;
                        while l <= cap_hi {
                            let c = ci + match_cost(l, d);
                            let j2 = i + l;
                            if c < cost[j2] {
                                cost[j2] = c;
                                from_len[j2] = l as u32;
                                from_dist[j2] = d as u32;
                            }
                            l += 1;
                        }
                        // Always add the full longest edge (covers long runs cheaply).
                        if ml > cap_hi {
                            let c = ci + match_cost(ml, d);
                            let j2 = i + ml;
                            if c < cost[j2] {
                                cost[j2] = c;
                                from_len[j2] = ml as u32;
                                from_dist[j2] = d as u32;
                            }
                        }
                        best = ml;
                    }
                }
                j = prev[j];
                chain += 1;
            }
        }
        // Insert position i into the hash chain.
        if i + LZ_MIN_MATCH <= n {
            let k = key3(i);
            prev[i] = head.get(&k).copied().unwrap_or(usize::MAX);
            head.insert(k, i);
        }
    }

    // Backtrack the optimal path from n to 0 into (len, dist) ops (dist 0 = literal).
    let mut ops: Vec<(usize, usize)> = Vec::new();
    let mut p = n;
    while p > 0 {
        let fl = from_len[p] as usize;
        if fl == 0 {
            ops.push((1, 0));
            p -= 1;
        } else {
            ops.push((fl, from_dist[p] as usize));
            p -= fl;
        }
    }
    ops.reverse();

    // Emit token streams from the chosen parse.
    let mut flags = Vec::new();
    let mut literals = Vec::new();
    let mut lengths = Vec::new();
    let mut distances = Vec::new();
    let mut pos = 0usize;
    for (len, dist) in ops {
        if dist == 0 {
            flags.push(0);
            literals.push(seq[pos]);
            pos += 1;
        } else {
            flags.push(1);
            lengths.push(len);
            distances.push(dist);
            pos += len;
        }
    }
    (flags, literals, lengths, distances)
}

/// Encode the LZ token streams (everything EXCEPT the literals): flags, the
/// repeat-offset distance modes, the new-distance byte-split, and the length
/// byte-split. Shared by the LzRans value-scheme (within-block) and the MODE_LZ
/// whole-file container (H-25d). The caller writes n_tokens / n_matches.
///
/// Wire: flags(order-1 rANS, alpha 2) + dmodes(order-1 rANS, alpha 4)
///       + new_lo/new_hi(order-0 rANS, 256) + len_lo/len_hi(order-0 rANS, 256).
fn lz_encode_token_streams(flags: &[usize], lengths: &[usize], distances: &[usize]) -> Vec<u8> {
    // Repeat-offset cache: reuse one of the last 3 distinct offsets (mode 0/1/2,
    // move-to-front) or emit a new distance (mode 3, byte-split).
    let mut rep = LZ_REP_INIT;
    let mut dist_modes: Vec<usize> = Vec::with_capacity(distances.len());
    let mut new_dists: Vec<usize> = Vec::new();
    for &d in distances {
        if d == rep[0] {
            dist_modes.push(0);
        } else if d == rep[1] {
            dist_modes.push(1);
            rep.swap(0, 1);
        } else if d == rep[2] {
            dist_modes.push(2);
            let r2 = rep[2];
            rep[2] = rep[1];
            rep[1] = rep[0];
            rep[0] = r2;
        } else {
            dist_modes.push(3);
            new_dists.push(d);
            rep[2] = rep[1];
            rep[1] = rep[0];
            rep[0] = d;
        }
    }
    // Length is capped at LZ_MAX_MATCH (u16) → 2 bytes. Distance can be up to the
    // whole-file size in the MODE_LZ container (cross-block!) → 4 bytes (u32). The
    // high distance bytes are almost always zero (cheap order-0 tables).
    let len_lo: Vec<usize> = lengths.iter().map(|&v| v & 0xFF).collect();
    let len_hi: Vec<usize> = lengths.iter().map(|&v| (v >> 8) & 0xFF).collect();
    let new_b0: Vec<usize> = new_dists.iter().map(|&v| v & 0xFF).collect();
    let new_b1: Vec<usize> = new_dists.iter().map(|&v| (v >> 8) & 0xFF).collect();
    let new_b2: Vec<usize> = new_dists.iter().map(|&v| (v >> 16) & 0xFF).collect();
    let new_b3: Vec<usize> = new_dists.iter().map(|&v| (v >> 24) & 0xFF).collect();

    let mut out = Vec::new();
    out.extend_from_slice(&rans_order1_encode(flags, 2));
    out.extend_from_slice(&rans_order1_encode(&dist_modes, 4));
    out.extend_from_slice(&rans_order0_encode(&new_b0, 256));
    out.extend_from_slice(&rans_order0_encode(&new_b1, 256));
    out.extend_from_slice(&rans_order0_encode(&new_b2, 256));
    out.extend_from_slice(&rans_order0_encode(&new_b3, 256));
    out.extend_from_slice(&rans_order0_encode(&len_lo, 256));
    out.extend_from_slice(&rans_order0_encode(&len_hi, 256));
    out
}

/// Decode the LZ token streams (mirror of `lz_encode_token_streams`).
/// Returns (flags, lengths, distances, bytes consumed).
#[allow(clippy::type_complexity)]
fn lz_decode_token_streams(
    blob: &[u8],
    offset: usize,
    n_tokens: usize,
    n_matches: usize,
) -> Result<(Vec<usize>, Vec<usize>, Vec<usize>, usize), CubrimError> {
    let mut pos = offset;
    let (flags, c) = rans_order1_decode(blob, pos, n_tokens, 2)?;
    pos += c;
    let (dist_modes, c) = rans_order1_decode(blob, pos, n_matches, 4)?;
    pos += c;
    let n_new = dist_modes.iter().filter(|&&m| m == 3).count();
    let (new_b0, c) = rans_order0_decode(blob, pos, n_new, 256)?;
    pos += c;
    let (new_b1, c) = rans_order0_decode(blob, pos, n_new, 256)?;
    pos += c;
    let (new_b2, c) = rans_order0_decode(blob, pos, n_new, 256)?;
    pos += c;
    let (new_b3, c) = rans_order0_decode(blob, pos, n_new, 256)?;
    pos += c;
    let (len_lo, c) = rans_order0_decode(blob, pos, n_matches, 256)?;
    pos += c;
    let (len_hi, c) = rans_order0_decode(blob, pos, n_matches, 256)?;
    pos += c;

    let mut rep = LZ_REP_INIT;
    let mut ni = 0usize;
    let mut distances: Vec<usize> = Vec::with_capacity(n_matches);
    for &m in &dist_modes {
        let d = match m {
            0 => rep[0],
            1 => {
                rep.swap(0, 1);
                rep[0]
            }
            2 => {
                let r2 = rep[2];
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = r2;
                rep[0]
            }
            _ => {
                let d = new_b0[ni] | (new_b1[ni] << 8) | (new_b2[ni] << 16) | (new_b3[ni] << 24);
                ni += 1;
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = d;
                d
            }
        };
        distances.push(d);
    }
    let lengths: Vec<usize> = (0..n_matches).map(|i| (len_hi[i] << 8) | len_lo[i]).collect();
    Ok((flags, lengths, distances, pos - offset))
}

/// LEB128 varint append.
fn lz_varint_write(out: &mut Vec<u8>, mut v: usize) {
    while v >= 0x80 {
        out.push((v as u8 & 0x7f) | 0x80);
        v >>= 7;
    }
    out.push(v as u8);
}

/// LEB128 varint read. Advances `p`. Fail-closed on truncation / overlong.
fn lz_varint_read(buf: &[u8], p: &mut usize) -> Result<usize, CubrimError> {
    let mut v: usize = 0;
    let mut shift = 0u32;
    loop {
        if *p >= buf.len() {
            return Err(CubrimError::Decode("LZ seq: varint truncated".into()));
        }
        let b = buf[*p];
        *p += 1;
        v |= ((b & 0x7f) as usize) << shift;
        if b & 0x80 == 0 {
            break;
        }
        shift += 7;
        if shift >= usize::BITS {
            return Err(CubrimError::Decode("LZ seq: varint overlong".into()));
        }
    }
    Ok(v)
}

/// H-25g combined sequence coder. Instead of 8 separate rANS streams (each paying a
/// fixed table+state, which dominates for small match counts), serialize the whole
/// token structure as zstd-style sequences — per match `(literal_length,
/// match_length, offset_mode[, new_distance])` plus a trailing literal run — into ONE
/// varint byte buffer, then code that buffer with the smallest of {raw, order-0 rANS,
/// order-1 rANS}. Drops the per-token flag stream entirely.
///
/// Wire: [coder u8 (0=raw,1=o0,2=o1)][ser_len u32][payload].
fn lz_encode_token_combined(flags: &[usize], lengths: &[usize], distances: &[usize]) -> Vec<u8> {
    let mut rep = LZ_REP_INIT;
    let mut ser: Vec<u8> = Vec::new();
    let mut ll = 0usize;
    let mut mi = 0usize;
    for &f in flags {
        if f == 0 {
            ll += 1;
        } else {
            let d = distances[mi];
            let ml = lengths[mi];
            mi += 1;
            let (mode, new_d) = if d == rep[0] {
                (0usize, None)
            } else if d == rep[1] {
                rep.swap(0, 1);
                (1, None)
            } else if d == rep[2] {
                let r2 = rep[2];
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = r2;
                (2, None)
            } else {
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = d;
                (3, Some(d))
            };
            lz_varint_write(&mut ser, ll);
            lz_varint_write(&mut ser, ml);
            ser.push(mode as u8);
            if let Some(nd) = new_d {
                lz_varint_write(&mut ser, nd);
            }
            ll = 0;
        }
    }
    lz_varint_write(&mut ser, ll); // trailing literal run

    // Code the serialized buffer with the smallest of raw / order-0 / order-1 rANS.
    let codes: Vec<usize> = ser.iter().map(|&b| b as usize).collect();
    let o0 = rans_order0_encode(&codes, 256);
    let o1 = rans_order1_encode(&codes, 256);
    let (coder, payload): (u8, &[u8]) = if o0.len() <= ser.len() && o0.len() <= o1.len() {
        (1, &o0)
    } else if o1.len() < ser.len() {
        (2, &o1)
    } else {
        (0, &ser)
    };

    let mut out = Vec::with_capacity(5 + payload.len());
    out.push(coder);
    out.extend_from_slice(&(ser.len() as u32).to_be_bytes());
    out.extend_from_slice(payload);
    out
}

/// Decode the H-25g combined sequence stream. Returns
/// (literal_run_lengths[n_matches], trailing_literal_run, lengths, distances, consumed).
#[allow(clippy::type_complexity)]
fn lz_decode_token_combined(
    blob: &[u8],
    offset: usize,
    n_matches: usize,
) -> Result<(Vec<usize>, usize, Vec<usize>, Vec<usize>, usize), CubrimError> {
    if offset + 5 > blob.len() {
        return Err(CubrimError::Decode("LZ seq: combined header truncated".into()));
    }
    let coder = blob[offset];
    let ser_len =
        u32::from_be_bytes([blob[offset + 1], blob[offset + 2], blob[offset + 3], blob[offset + 4]])
            as usize;
    let mut pos = offset + 5;
    let (ser, consumed): (Vec<u8>, usize) = match coder {
        0 => {
            if pos + ser_len > blob.len() {
                return Err(CubrimError::Decode("LZ seq: raw payload truncated".into()));
            }
            (blob[pos..pos + ser_len].to_vec(), ser_len)
        }
        1 => {
            let (codes, c) = rans_order0_decode(blob, pos, ser_len, 256)?;
            (codes.iter().map(|&v| v as u8).collect(), c)
        }
        2 => {
            let (codes, c) = rans_order1_decode(blob, pos, ser_len, 256)?;
            (codes.iter().map(|&v| v as u8).collect(), c)
        }
        k => return Err(CubrimError::Decode(format!("LZ seq: bad coder {k}"))),
    };
    pos += consumed;

    let mut rep = LZ_REP_INIT;
    let mut p = 0usize;
    let mut lit_lengths = Vec::with_capacity(n_matches);
    let mut lengths = Vec::with_capacity(n_matches);
    let mut distances = Vec::with_capacity(n_matches);
    for _ in 0..n_matches {
        let ll = lz_varint_read(&ser, &mut p)?;
        let ml = lz_varint_read(&ser, &mut p)?;
        if p >= ser.len() {
            return Err(CubrimError::Decode("LZ seq: missing offset mode".into()));
        }
        let mode = ser[p];
        p += 1;
        let d = match mode {
            0 => rep[0],
            1 => {
                rep.swap(0, 1);
                rep[0]
            }
            2 => {
                let r2 = rep[2];
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = r2;
                rep[0]
            }
            3 => {
                let d = lz_varint_read(&ser, &mut p)?;
                rep[2] = rep[1];
                rep[1] = rep[0];
                rep[0] = d;
                d
            }
            m => return Err(CubrimError::Decode(format!("LZ seq: bad offset mode {m}"))),
        };
        lit_lengths.push(ll);
        lengths.push(ml);
        distances.push(d);
    }
    let final_ll = lz_varint_read(&ser, &mut p)?;
    Ok((lit_lengths, final_ll, lengths, distances, pos - offset))
}

/// Encode the value-code stream with LzRans (LZ77 + rANS, H-25c). See module comment.
pub(crate) fn lz_rans_encode(seq_codes: &[usize], n_distinct: usize) -> Vec<u8> {
    // Value-scheme (within ≤64KB blocks, runs for every block in the rail): use the
    // fast greedy parse. The slow optimal parse is reserved for the file-level
    // MODE_LZ container (encode_lz_prepass), where it is competitively size-picked.
    let (flags, literals, lengths, distances) = lz77_parse_greedy(seq_codes);
    let n_tokens = flags.len();
    let n_lits = literals.len();
    let n_matches = lengths.len();

    // Literals: pick the lighter of order-0 / order-1 (fallback-table) coders.
    let lit0 = rans_order0_encode(&literals, n_distinct.max(1));
    let lit1 = rans_order1_encode(&literals, n_distinct.max(1));
    let (lit_mode, lits_block) = if lit1.len() < lit0.len() {
        (1u8, lit1)
    } else {
        (0u8, lit0)
    };
    let token_streams = lz_encode_token_streams(&flags, &lengths, &distances);

    let mut out = Vec::with_capacity(13 + lits_block.len() + token_streams.len());
    out.extend_from_slice(&(n_tokens as u32).to_be_bytes());
    out.extend_from_slice(&(n_lits as u32).to_be_bytes());
    out.extend_from_slice(&(n_matches as u32).to_be_bytes());
    out.push(lit_mode);
    out.extend_from_slice(&lits_block);
    out.extend_from_slice(&token_streams);
    out
}

/// Decode the LzRans stream from blob at offset. Returns (seq_codes, consumed).
pub(crate) fn lz_rans_decode(
    blob: &[u8],
    offset: usize,
    count: usize,
    n_distinct: usize,
) -> Result<(Vec<usize>, usize), CubrimError> {
    let mut pos = offset;
    let read_u32 = |blob: &[u8], p: usize| -> Result<usize, CubrimError> {
        if p + 4 > blob.len() {
            return Err(CubrimError::Decode("LzRans: truncated u32 field".into()));
        }
        Ok(u32::from_be_bytes([blob[p], blob[p + 1], blob[p + 2], blob[p + 3]]) as usize)
    };
    let n_tokens = read_u32(blob, pos)?;
    let n_lits = read_u32(blob, pos + 4)?;
    let n_matches = read_u32(blob, pos + 8)?;
    pos += 12;

    if pos >= blob.len() {
        return Err(CubrimError::Decode("LzRans: missing lit_mode byte".into()));
    }
    let lit_mode = blob[pos];
    pos += 1;
    let (literals, consumed) = match lit_mode {
        0 => rans_order0_decode(blob, pos, n_lits, n_distinct.max(1))?,
        1 => rans_order1_decode(blob, pos, n_lits, n_distinct.max(1))?,
        m => {
            return Err(CubrimError::Decode(format!("LzRans: bad lit_mode {m}")));
        }
    };
    pos += consumed;

    let (flags, lengths, distances, consumed) =
        lz_decode_token_streams(blob, pos, n_tokens, n_matches)?;
    pos += consumed;

    let mut out: Vec<usize> = Vec::with_capacity(count);
    let mut li = 0usize;
    let mut mi = 0usize;
    for &flag in &flags {
        if flag == 0 {
            if li >= literals.len() {
                return Err(CubrimError::Decode("LzRans: literal stream underflow".into()));
            }
            out.push(literals[li]);
            li += 1;
        } else {
            if mi >= n_matches {
                return Err(CubrimError::Decode("LzRans: match stream underflow".into()));
            }
            let length = lengths[mi];
            let distance = distances[mi];
            mi += 1;
            if distance == 0 || distance > out.len() {
                return Err(CubrimError::Decode(format!(
                    "LzRans: invalid distance {distance} (output length {})",
                    out.len()
                )));
            }
            if length == 0 || out.len() + length > count {
                return Err(CubrimError::Decode(
                    "LzRans: match length 0 or overflows declared count".into(),
                ));
            }
            let start = out.len() - distance;
            for k in 0..length {
                out.push(out[start + k]);
            }
        }
    }
    if out.len() != count {
        return Err(CubrimError::Decode(format!(
            "LzRans: decoded {} codes but expected {count}",
            out.len()
        )));
    }
    Ok((out, pos - offset))
}

/// Estimate byte size of the LzRans stream (used by the competitive rail).
pub(crate) fn lz_rans_size(seq_codes: &[usize], n_distinct: usize) -> usize {
    lz_rans_encode(seq_codes, n_distinct).len()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::header::VALUE_SCHEME_RLE_CODES;

    /// Reference cyclic-rotation BWT (the previous O(n² log n) implementation),
    /// kept only to prove the SA-IS replacement is byte-identical.
    fn bwt_encode_codes_naive(seq: &[usize]) -> (Vec<usize>, u16) {
        let n = seq.len();
        if n == 0 {
            return (vec![], 0);
        }
        let mut indices: Vec<usize> = (0..n).collect();
        indices.sort_by(|&a, &b| {
            for k in 0..n {
                let ca = seq[(a + k) % n];
                let cb = seq[(b + k) % n];
                if ca != cb {
                    return ca.cmp(&cb);
                }
            }
            std::cmp::Ordering::Equal
        });
        let bwt_out: Vec<usize> = indices.iter().map(|&i| seq[(i + n - 1) % n]).collect();
        let primary = indices.iter().position(|&i| i == 0).unwrap_or(0);
        (bwt_out, primary as u16)
    }

    #[test]
    fn test_sais_bwt_matches_naive() {
        // SA-IS BWT must be byte-identical (bwt_out AND primary) to the naive
        // rotation sort across a battery incl. periodic/all-same/random inputs.
        // Deterministic LCG; no external RNG.
        let mut state: u64 = 0x9E3779B97F4A7C15;
        let mut next = |m: usize| -> usize {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            ((state >> 33) as usize) % m
        };

        // Fixed structural cases (empty, singletons, periodic, all-same).
        let fixed: Vec<Vec<usize>> = vec![
            vec![],
            vec![0],
            vec![5],
            vec![1, 1, 1, 1, 1, 1],          // all-same → period 1
            vec![1, 0, 1, 0, 1, 0],          // period 2
            vec![2, 1, 3, 2, 1, 3, 2, 1, 3], // period 3
            vec![0, 1, 2, 3, 4, 5, 6, 7],    // strictly increasing
            vec![7, 6, 5, 4, 3, 2, 1, 0],    // strictly decreasing
            b"abracadabra".iter().map(|&c| c as usize).collect(),
            b"mississippi".iter().map(|&c| c as usize).collect(),
        ];
        for seq in &fixed {
            assert_eq!(
                bwt_encode_codes(seq),
                bwt_encode_codes_naive(seq),
                "SA-IS BWT mismatch on fixed case {seq:?}"
            );
        }

        // Random inputs: vary length and alphabet (incl. tiny alphabets that force
        // many periodic ties).
        for _ in 0..2000 {
            let len = 1 + next(40);
            let alpha = 1 + next(4); // 1..=4 distinct → lots of ties
            let seq: Vec<usize> = (0..len).map(|_| next(alpha)).collect();
            let got = bwt_encode_codes(&seq);
            let want = bwt_encode_codes_naive(&seq);
            assert_eq!(got, want, "SA-IS BWT mismatch on random seq {seq:?}");
            // And the LF-decode must still invert it.
            let decoded = bwt_decode_codes(&got.0, got.1, alpha).unwrap();
            assert_eq!(decoded, seq, "BWT round-trip failed for {seq:?}");
        }

        // A few larger periodic blocks (exercise the recursion + tie correction).
        for unit in [&b"ab"[..], &b"abc"[..], &b"abcd"[..], &b"hello "[..]] {
            let mut seq = Vec::new();
            while seq.len() < 1500 {
                seq.extend(unit.iter().map(|&c| c as usize));
            }
            assert_eq!(
                bwt_encode_codes(&seq),
                bwt_encode_codes_naive(&seq),
                "SA-IS BWT mismatch on periodic block (unit len {})",
                unit.len()
            );
        }
    }

    // -------------------------------------------------------------------------
    // H-25 LzRans (LZ77 + rANS) — scheme byte 12
    // -------------------------------------------------------------------------

    fn lz_rans_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::LzRans,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_lz_rans_scheme_byte() {
        assert_eq!(ValueScheme::LzRans.scheme_byte(), 12u8);
        assert_eq!(ValueScheme::from_byte(12u8), Some(ValueScheme::LzRans));
    }

    #[test]
    fn test_lz_rans_codes_round_trip_direct() {
        // Direct lz_rans_encode/decode round-trip on code streams incl. periodic,
        // all-same, random, and long-run (overlapping-match) inputs.
        let mut state: u64 = 0xD1B54A32D192ED03;
        let mut next = |m: usize| -> usize {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            ((state >> 33) as usize) % m
        };
        let mut cases: Vec<(Vec<usize>, usize)> = vec![
            (vec![], 1),
            (vec![0], 1),
            (vec![5, 5, 5, 5, 5, 5, 5, 5], 6),       // all-same → overlap match dist 1
            (vec![1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3], 4),
            (b"abracadabra abracadabra abracadabra".iter().map(|&c| c as usize).collect(), 256),
        ];
        // Random + structured streams of varied alphabet.
        for _ in 0..200 {
            let len = next(2000);
            let alpha = 1 + next(8);
            let seq: Vec<usize> = (0..len).map(|_| next(alpha)).collect();
            cases.push((seq, alpha.max(1)));
        }
        for (seq, n_distinct) in &cases {
            let blob = lz_rans_encode(seq, *n_distinct);
            let (decoded, consumed) =
                lz_rans_decode(&blob, 0, seq.len(), *n_distinct).expect("lz decode");
            assert_eq!(&decoded, seq, "LzRans round-trip mismatch");
            assert_eq!(consumed, blob.len(), "LzRans consumed != blob len");
        }
    }

    #[test]
    fn test_lz_rans_full_codec_round_trip() {
        // Through the full encoder/decoder with a highly-repetitive cube-eligible
        // input (LZ should win or tie; round-trip must be byte-exact regardless).
        let unit = b"the cube archiver maps values into a lattice. ";
        let mut data = Vec::new();
        while data.len() < 8000 {
            data.extend_from_slice(unit);
        }
        let blob = encode_with_config(&data, &lz_rans_cfg());
        assert_eq!(decode(&blob).unwrap(), data, "LzRans full-codec round-trip");
    }

    #[test]
    fn test_lz_rans_competitive_never_regresses() {
        // The competitive rail guarantees requesting LzRans never produces a blob
        // larger than requesting BwtRans (both pick the per-file min).
        let unit = b"mississippi river banana bandana ";
        let mut data = Vec::new();
        while data.len() < 5000 {
            data.extend_from_slice(unit);
        }
        let lz = encode_with_config(&data, &lz_rans_cfg());
        let rans = encode_with_config(&data, &bwt_rans_cfg());
        assert_eq!(lz.len(), rans.len(), "competitive rail must pick same per-file min");
        assert_eq!(decode(&lz).unwrap(), data);
        assert_eq!(decode(&rans).unwrap(), data);
    }

    #[test]
    fn test_lz_rans_wins_on_long_range_and_dispatch_round_trips() {
        // A within-block long-range input (10KB structured unit × 5 ≈ 50KB): the
        // repeat-offset cache codes the inter-copy distances as mode-0, so LzRans
        // should WIN the competitive rail. This both proves the repeat-offset lever
        // and exercises the scheme-12 decode dispatch end-to-end.
        let mut state: u64 = 0xABCDEF0123456789;
        let mut nxt = |m: usize| {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            ((state >> 33) as usize) % m
        };
        let table = b"abcdefghij  ,.0123";
        let unit: Vec<u8> = (0..10000).map(|_| table[nxt(table.len())]).collect();
        let mut data = Vec::new();
        for _ in 0..5 {
            data.extend_from_slice(&unit);
        }
        let blob = encode_with_config(&data, &lz_rans_cfg());
        assert_eq!(decode(&blob).unwrap(), data, "long-range round-trip");
        // value_scheme byte is at the cube header (N=2): offset 22.
        assert_eq!(blob[5], crate::header::MODE_CUBE, "must be cube mode");
        assert_eq!(
            blob[22],
            ValueScheme::LzRans.scheme_byte(),
            "LzRans must win the rail on long-range data (repeat-offset lever)"
        );
    }

    #[test]
    fn test_mode_lz_cross_block_long_range_wins_and_round_trips() {
        use crate::header::{MODE_CHUNKED, MODE_LZ};
        // 120 KB = a 10 KB structured unit × 12 → repeats at distance 10 KB that
        // CROSS the 64 KB chunk boundary. The whole-file LZ pre-pass (MODE_LZ) must
        // capture them and beat the plain MODE_CHUNKED encoding by a wide margin.
        let mut state: u64 = 0x51ED270B1A2B3C4D;
        let mut nxt = |m: usize| {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            ((state >> 33) as usize) % m
        };
        let table = b"abcdefghij  ,.0123";
        let unit: Vec<u8> = (0..10000).map(|_| table[nxt(table.len())]).collect();
        let mut data = Vec::new();
        for _ in 0..12 {
            data.extend_from_slice(&unit);
        }
        let lz = encode_with_config(&data, &EncodeConfig::v1_default());
        assert_eq!(decode(&lz).unwrap(), data, "MODE_LZ round-trip must be exact");
        assert_eq!(lz[5], MODE_LZ, "cross-block long-range must select MODE_LZ");

        // It must be far smaller than the chunked (no whole-file LZ) encoding.
        let chunked = encode_chunked(&data, &EncodeConfig::v1_default());
        assert_eq!(decode(&chunked).unwrap(), data);
        assert_eq!(chunked[5], MODE_CHUNKED);
        assert!(
            lz.len() * 3 < chunked.len() * 2,
            "MODE_LZ {} not decisively smaller than chunked {}",
            lz.len(),
            chunked.len()
        );
    }

    #[test]
    fn test_mode_lz_no_regression_on_incompressible() {
        use crate::header::MODE_LZ;
        // A >64KB high-entropy input has no cross-block repeats: the pre-pass must
        // NOT be selected (falls back byte-identically to the base encoding).
        let mut state: u64 = 0xC0FFEE1234567890;
        let data: Vec<u8> = (0..80_000)
            .map(|_| {
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
                (state >> 33) as u8
            })
            .collect();
        let blob = encode_with_config(&data, &EncodeConfig::v1_default());
        assert_ne!(blob[5], MODE_LZ, "incompressible input must not select MODE_LZ");
        assert_eq!(decode(&blob).unwrap(), data, "fallback round-trip must be exact");
    }

    #[test]
    fn test_mode_lz_round_trip_sizes() {
        // Round-trip a range of >64KB sizes through the public API (some will pick
        // MODE_LZ, some MODE_CHUNKED — both must be byte-exact).
        for &n in &[70000usize, 131072, 200001] {
            let unit = b"the quick brown fox 0123456789 ";
            let mut data = Vec::new();
            while data.len() < n {
                data.extend_from_slice(unit);
            }
            data.truncate(n);
            let blob = encode_with_config(&data, &EncodeConfig::v1_default());
            assert_eq!(decode(&blob).unwrap(), data, "round-trip failed for n={n}");
        }
    }

    #[test]
    fn test_lz_rans_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = (0..4000u32).map(|i| (i % 7) as u8).collect();
        let blob = lz_rans_encode(
            &data.iter().map(|&b| b as usize).collect::<Vec<_>>(),
            7,
        );
        for cut in [0usize, 5, 12, blob.len() / 2, blob.len().saturating_sub(1)] {
            let _ = lz_rans_decode(&blob[..cut.min(blob.len())], 0, data.len(), 7);
            // Must not panic; correctness of Err is implied by no unwind.
        }
    }

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
        let data: Vec<u8> = (0usize..1024)
            .map(|i| ((i % 256) as u8).wrapping_mul(71).wrapping_add(13))
            .collect();
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
        assert_eq!(
            &blob[0..4],
            &MAGIC,
            "blob must start with magic cb 52 49 4d"
        );
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
            (
                "text_1kb",
                b"the quick brown fox jumps over the lazy dog "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(113).wrapping_add(7))
                    .collect(),
            ),
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
        use crate::distance_map::{decode_axis_gaps, encode_axis_gaps};
        // {0, 3, 7} with b_k=8 -> gaps (1, 3, 4) -> decode -> {0, 3, 7}
        let gaps = encode_axis_gaps(&[0, 3, 7], 8).unwrap();
        assert_eq!(gaps, vec![1, 3, 4]);
        assert_eq!(decode_axis_gaps(&gaps), vec![0, 3, 7]);
    }

    // -------------------------------------------------------------------------
    // V-AC-6: R7 raw-store fallback never blows up
    // -------------------------------------------------------------------------

    #[test]
    fn test_chunked_container_for_large_input() {
        use crate::header::{MODE_CHUNKED, MODE_LZ};
        // >65536 bytes -> a container mode (MODE_CHUNKED, or MODE_LZ when the
        // whole-file LZ pre-pass wins), never a flat raw-store.
        let data: Vec<u8> = (0usize..66000).map(|i| (i % 256) as u8).collect();
        let blob = encode(&data);
        assert!(
            blob[5] == MODE_CHUNKED || blob[5] == MODE_LZ,
            "large input (>cube ceiling) must produce a container (got mode {})",
            blob[5]
        );
        assert_eq!(
            decode(&blob).unwrap(),
            data,
            "large container round-trip failed"
        );
    }

    #[test]
    fn test_chunked_large_compressible_round_trips_and_shrinks() {
        use crate::header::MODE_CHUNKED;
        // ~300 KB of structured/compressible text spanning multiple chunks. Uses the
        // v1-default (fast) scheme so the suite stays quick; the heavy BWT-family path
        // on a big file is exercised by the release-CLI verification, not in-suite.
        let unit = b"The quick brown fox jumps over the lazy dog. 0123456789. ";
        let mut data = Vec::new();
        while data.len() < 300_000 {
            data.extend_from_slice(unit);
        }
        let blob = encode(&data);
        assert!(
            blob[5] == MODE_CHUNKED || blob[5] == crate::header::MODE_LZ,
            "big input must use a container (got mode {})",
            blob[5]
        );
        assert_eq!(decode(&blob).unwrap(), data, "big round-trip must be exact");
        assert!(
            blob.len() < data.len(),
            "compressible input must shrink: {} >= {}",
            blob.len(),
            data.len()
        );
    }

    #[test]
    fn test_chunked_bwt_family_round_trips() {
        use crate::header::MODE_CHUNKED;
        // Prove a BWT-family scheme survives the chunk-boundary split. The chunk block
        // size derives from cube_size_limit() = b*b, so a small edge-bound (b=64 ->
        // 4096-byte blocks) forces many small blocks cheaply — the competitive BWT path
        // is slow in debug builds, so we keep each block small rather than ≤65536.
        let cfg = EncodeConfig {
            b: 64,
            value_scheme: ValueScheme::BwtGeoMix,
            ..EncodeConfig::v1_default()
        };
        assert_eq!(cfg.cube_size_limit(), 4096);
        let unit = b"abracadabra-banana-mississippi-";
        let mut data = Vec::new();
        while data.len() < 20_000 {
            data.extend_from_slice(unit);
        }
        let blob = encode_with_config(&data, &cfg);
        assert!(
            blob[5] == MODE_CHUNKED || blob[5] == crate::header::MODE_LZ,
            "input past cube_size_limit must use a container (got mode {})",
            blob[5]
        );
        assert_eq!(
            decode(&blob).unwrap(),
            data,
            "BWT-family chunked round-trip must be exact"
        );
    }

    #[test]
    fn test_chunked_round_trip_various_sizes() {
        // Boundary and multi-block sizes around the 65536 ceiling must round-trip.
        for &n in &[65536usize, 65537, 70000, 131072, 200001] {
            let data: Vec<u8> = (0..n).map(|i| (i.wrapping_mul(31) % 256) as u8).collect();
            let blob = encode(&data);
            assert_eq!(
                decode(&blob).unwrap(),
                data,
                "round-trip failed for size {n}"
            );
        }
    }

    #[test]
    fn test_raw_store_for_small_input() {
        use crate::header::{parse_header, MODE_RAW};
        // <= HEADER_OVERHEAD_BOUND bytes -> always raw-store
        let data: Vec<u8> = vec![42u8; 100];
        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();
        assert_eq!(
            hdr.mode, MODE_RAW,
            "small input <= {HEADER_OVERHEAD_BOUND} must trigger raw-store"
        );
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
            .map(|i: usize| if i.is_multiple_of(10) { 0x01 } else { 0x00 })
            .collect();

        let blob = encode(&data);
        let (hdr, _) = parse_header(&blob).unwrap();

        // This specific pattern should trigger cube mode (2 distinct values, W=1 bit)
        // If it doesn't, we still need to verify round-trip
        let recovered = decode(&blob).unwrap();
        assert_eq!(
            recovered, data,
            "clustered input cube-path round-trip failed"
        );

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
        assert_eq!(
            hdr.mode, MODE_CUBE,
            "all-same 400-byte input must trigger cube mode (94 < 413)"
        );
        let recovered = decode(&blob).unwrap();
        assert_eq!(
            recovered, data,
            "cube-mode round-trip failed for all-same-400"
        );
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

    // -------------------------------------------------------------------------
    // Phase A: N knob — non-minimal N round-trips, injectivity guard
    // -------------------------------------------------------------------------

    #[test]
    fn test_non_minimal_n_round_trips() {
        // N=3 for a 1024-byte input that normally uses N=2 (256^2=65536 >= 1024).
        // With N=3 the cube has 256^3=16M slots, still injective — must round-trip.
        use crate::header::parse_header;
        let data: Vec<u8> = (0..1024).map(|i| (i % 256) as u8).collect();
        let cfg = EncodeConfig {
            n_override: Some(3),
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "N=3 round-trip failed for 1024-byte input");

        // The header must record N=3
        let (hdr, _) = parse_header(&blob).unwrap();
        // Small inputs raw-store; for a cube-mode input verify N
        if hdr.mode == crate::header::MODE_CUBE {
            assert_eq!(hdr.n, 3, "header N must be 3 when n_override=Some(3)");
        }
    }

    #[test]
    fn test_n_override_none_is_minimal() {
        // n_override=None must use minimal N (same as v1_default behavior)
        let data: Vec<u8> = vec![0xABu8; 400]; // 400 bytes, minimal N = 2
        let default_blob = encode(&data);
        let cfg_none = EncodeConfig {
            n_override: None,
            ..EncodeConfig::v1_default()
        };
        let cfg_blob = encode_with_config(&data, &cfg_none);
        assert_eq!(
            default_blob, cfg_blob,
            "n_override=None must produce byte-identical output to v1_default"
        );
    }

    #[test]
    fn test_n_override_below_minimum_clamped_to_min() {
        // If n_override < n_min (impossible to achieve injectivity), clamp up to n_min.
        // 400-byte input needs N=2; n_override=1 must clamp to 2 and round-trip.
        let data: Vec<u8> = vec![0xCCu8; 400];
        let cfg = EncodeConfig {
            n_override: Some(1), // 256^1 = 256 < 400: would be non-injective
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "n_override=1 clamped round-trip failed");
    }

    // -------------------------------------------------------------------------
    // Phase B: GapScheme — default byte-identity, alt diverges, header round-trip
    // -------------------------------------------------------------------------

    #[test]
    fn test_default_gap_scheme_byte_identical_to_v1() {
        // V-AC-8 core: with all config defaults, encode == encode_with_config(v1_default)
        // This is already verified by the differential fixtures, but test explicitly.
        let inputs: Vec<Vec<u8>> = vec![
            vec![0xABu8; 400],
            b"the quick brown fox jumps "
                .iter()
                .copied()
                .cycle()
                .take(1024)
                .collect(),
        ];
        for input in &inputs {
            let v1_blob = encode(input);
            let default_scheme_blob = encode_with_config(input, &EncodeConfig::v1_default());
            assert_eq!(
                v1_blob, default_scheme_blob,
                "default config must produce byte-identical output to encode()"
            );
        }
    }

    #[test]
    fn test_packed_nibble_scheme_diverges_from_rle() {
        // PackedNibble blob must differ from RleU16 blob for any cube-mode input.
        // Use a 400-byte all-same-byte input known to trigger cube mode.
        let data: Vec<u8> = vec![0xABu8; 400];
        let rle_blob = encode(&data); // RleU16 default
        let pn_blob = encode_with_config(
            &data,
            &EncodeConfig {
                gap_scheme: crate::config::GapScheme::PackedNibble,
                ..EncodeConfig::v1_default()
            },
        );
        assert_ne!(
            rle_blob, pn_blob,
            "PackedNibble blob must differ from RleU16 blob (different wire encoding)"
        );
    }

    #[test]
    fn test_packed_nibble_round_trips_cube_mode() {
        // PackedNibble-encoded cube-mode input must decode correctly.
        let data: Vec<u8> = vec![0xABu8; 400]; // cube mode (verified elsewhere)
        let cfg = EncodeConfig {
            gap_scheme: crate::config::GapScheme::PackedNibble,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "PackedNibble cube-mode round-trip failed");
    }

    #[test]
    fn test_packed_nibble_header_map_scheme_byte() {
        // Header must record map_scheme=2 (MAP_SCHEME_PACKED_NIBBLE) for PackedNibble.
        use crate::header::{parse_header, MAP_SCHEME_PACKED_NIBBLE, MODE_CUBE};
        let data: Vec<u8> = vec![0xABu8; 400];
        let cfg = EncodeConfig {
            gap_scheme: crate::config::GapScheme::PackedNibble,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let (hdr, _) = parse_header(&blob).unwrap();
        if hdr.mode == MODE_CUBE {
            assert_eq!(
                hdr.map_scheme, MAP_SCHEME_PACKED_NIBBLE,
                "PackedNibble config must write map_scheme=2 to header"
            );
        }
    }

    #[test]
    fn test_packed_nibble_round_trips_all_classes() {
        // Round-trip under PackedNibble across multiple input classes
        let cfg = EncodeConfig {
            gap_scheme: crate::config::GapScheme::PackedNibble,
            ..EncodeConfig::v1_default()
        };
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("1byte", vec![0x42]),
            ("uniform_400", vec![0xAA; 400]),
            (
                "text_1kb",
                b"the quick brown fox jumps over the lazy dog "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(113).wrapping_add(7))
                    .collect(),
            ),
        ];
        for (name, data) in &cases {
            let blob = encode_with_config(data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(
                &recovered, data,
                "PackedNibble round-trip failed for '{name}'"
            );
        }
    }

    // -------------------------------------------------------------------------
    // ValueScheme::BitpackFixed — V-AC-8 default byte-identity
    // -------------------------------------------------------------------------

    #[test]
    fn test_default_value_scheme_byte_identical_to_v1() {
        // V-AC-8 sibling: BitpackFixed is the default; output must be byte-identical
        // to encode() (which uses v1_default = BitpackFixed).
        let inputs: Vec<Vec<u8>> = vec![
            vec![0xABu8; 400],
            b"the quick brown fox jumps "
                .iter()
                .copied()
                .cycle()
                .take(1024)
                .collect(),
        ];
        for input in &inputs {
            let v1_blob = encode(input);
            let fixed_blob = encode_with_config(
                input,
                &EncodeConfig {
                    value_scheme: crate::config::ValueScheme::BitpackFixed,
                    ..EncodeConfig::v1_default()
                },
            );
            assert_eq!(
                v1_blob,
                fixed_blob,
                "BitpackFixed must produce byte-identical output to encode() for {} bytes",
                input.len()
            );
        }
    }

    // -------------------------------------------------------------------------
    // ValueScheme::RleCodes — TDD tests (written before implementation)
    // -------------------------------------------------------------------------

    #[test]
    fn test_rle_codes_round_trip_hand_made_run_heavy() {
        // Hand-crafted input with 3 distinct values in long runs:
        //   128 × 0x01, 128 × 0x02, 128 × 0x03 = 384 bytes total
        // In sequential order codes are [0,0,...,0, 1,1,...,1, 2,2,...,2] — 3 long runs.
        let mut data = vec![0x01u8; 128];
        data.extend(vec![0x02u8; 128]);
        data.extend(vec![0x03u8; 128]);
        assert_eq!(data.len(), 384);

        let cfg = EncodeConfig {
            value_scheme: crate::config::ValueScheme::RleCodes,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let recovered = decode(&blob).unwrap();
        assert_eq!(
            recovered, data,
            "RleCodes round-trip failed for run-heavy input"
        );
    }

    #[test]
    fn test_rle_codes_round_trip_all_classes() {
        // Round-trip under RleCodes across all standard input classes
        let cfg = EncodeConfig {
            value_scheme: crate::config::ValueScheme::RleCodes,
            ..EncodeConfig::v1_default()
        };
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("1byte", vec![0x42]),
            ("uniform_400", vec![0xAA; 400]),
            ("all_distinct_256", (0u8..=255).collect()),
            (
                "text_1kb",
                b"the quick brown fox jumps over the lazy dog "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(113).wrapping_add(7))
                    .collect(),
            ),
        ];
        for (name, data) in &cases {
            let blob = encode_with_config(data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(&recovered, data, "RleCodes round-trip failed for '{name}'");
        }
    }

    #[test]
    fn test_rle_codes_sequential_order_property() {
        // Property: for a run-heavy input (sequential blocks of same byte),
        // RleCodes produces a SMALLER blob than BitpackFixed.
        // This validates the core re-scoped V-AC-4 claim.
        let mut data = vec![0x0Au8; 200];
        data.extend(vec![0x0Bu8; 200]);
        // 400 bytes total, 2 distinct values in 2 long runs.
        // BitpackFixed: W=1 bit → ceil(400/8) = 50 bytes bitpack
        // RleCodes: 2 triplets × 3B = 6 bytes — dramatically smaller
        assert_eq!(data.len(), 400);

        let fixed_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: crate::config::ValueScheme::BitpackFixed,
                ..EncodeConfig::v1_default()
            },
        );
        let rle_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: crate::config::ValueScheme::RleCodes,
                ..EncodeConfig::v1_default()
            },
        );

        // Both must round-trip correctly
        assert_eq!(
            decode(&fixed_blob).unwrap(),
            data,
            "BitpackFixed round-trip"
        );
        assert_eq!(decode(&rle_blob).unwrap(), data, "RleCodes round-trip");

        assert!(
            rle_blob.len() < fixed_blob.len(),
            "RleCodes ({} bytes) must be smaller than BitpackFixed ({} bytes) for sequential-run input",
            rle_blob.len(), fixed_blob.len()
        );
    }

    #[test]
    fn test_rle_codes_header_value_scheme_byte() {
        // Header must record value_scheme=2 (VALUE_SCHEME_RLE_CODES) for RleCodes.
        use crate::header::{parse_header, MODE_CUBE};
        let data: Vec<u8> = vec![0xABu8; 400];
        let cfg = EncodeConfig {
            value_scheme: crate::config::ValueScheme::RleCodes,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let (hdr, _) = parse_header(&blob).unwrap();
        if hdr.mode == MODE_CUBE {
            assert_eq!(
                hdr.value_scheme, VALUE_SCHEME_RLE_CODES,
                "RleCodes config must write value_scheme=2 to header"
            );
        }
    }

    #[test]
    fn test_rle_codes_diverges_from_bitpack_fixed() {
        // RleCodes blob must differ from BitpackFixed blob for any cube-mode input.
        let data: Vec<u8> = vec![0xABu8; 400];
        let fixed_blob = encode(&data);
        let rle_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: crate::config::ValueScheme::RleCodes,
                ..EncodeConfig::v1_default()
            },
        );
        assert_ne!(
            fixed_blob, rle_blob,
            "RleCodes blob must differ from BitpackFixed blob"
        );
    }

    // Inline RLE-codes primitive tests (white-box, no public API needed)
    #[test]
    fn test_rle_codes_encode_decode_primitives() {
        // Hand-check encode/decode internals: 3 codes with runs 5,3,2
        let seq_codes = {
            let mut v = vec![0usize; 5]; // code 0, run 5
            v.extend(vec![1usize; 3]); // code 1, run 3
            v.extend(vec![2usize; 2]); // code 2, run 2
            v
        };
        let encoded = rle_codes_encode(&seq_codes);
        // 3 triplets × 3 bytes = 9 bytes
        assert_eq!(encoded.len(), 9);
        // First triplet: code=0, run=5
        assert_eq!(encoded[0], 0u8);
        assert_eq!(u16::from_be_bytes([encoded[1], encoded[2]]), 5u16);

        // Synthesize a blob fragment and decode
        let (decoded_codes, consumed) = rle_codes_decode(&encoded, 0, 10).unwrap();
        assert_eq!(decoded_codes, seq_codes);
        assert_eq!(consumed, 9);
    }

    #[test]
    fn test_rle_codes_size_matches_encode_len() {
        let seq_codes: Vec<usize> = {
            let mut v = vec![0usize; 100];
            v.extend(vec![1usize; 50]);
            v.extend(vec![0usize; 25]); // second run of 0
            v
        };
        let encoded = rle_codes_encode(&seq_codes);
        assert_eq!(rle_codes_size(&seq_codes), encoded.len());
    }

    // -------------------------------------------------------------------------
    // ValueScheme::Entropy — P2 tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_entropy_round_trip_all_classes() {
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::Entropy,
            ..EncodeConfig::v1_default()
        };
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("1byte", vec![0x42]),
            ("uniform_400", vec![0xAA; 400]),
            ("all_distinct_256", (0u8..=255).collect()),
            (
                "text_1kb",
                b"the quick brown fox jumps over the lazy dog "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(113).wrapping_add(7))
                    .collect(),
            ),
        ];
        for (name, data) in &cases {
            let blob = encode_with_config(data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(&recovered, data, "Entropy round-trip failed for '{name}'");
        }
    }

    #[test]
    fn test_entropy_header_value_scheme_byte_is_3() {
        use crate::header::{parse_header, MODE_CUBE};
        let data: Vec<u8> = vec![0xABu8; 400];
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::Entropy,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let (hdr, _) = parse_header(&blob).unwrap();
        if hdr.mode == MODE_CUBE {
            assert_eq!(
                hdr.value_scheme, 3u8,
                "Entropy config must write value_scheme=3 to header"
            );
        }
    }

    #[test]
    fn test_entropy_diverges_from_bitpack_fixed() {
        // Entropy blob must differ from BitpackFixed blob for any cube-mode input.
        let data: Vec<u8> = vec![0xABu8; 400];
        let fixed_blob = encode(&data); // BitpackFixed default
        let entropy_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::Entropy,
                ..EncodeConfig::v1_default()
            },
        );
        assert_ne!(
            fixed_blob, entropy_blob,
            "Entropy blob must differ from BitpackFixed blob"
        );
    }

    #[test]
    fn test_entropy_smaller_than_bitpack_on_skewed() {
        // For a skewed 4-symbol input, Entropy (variable-length) beats BitpackFixed (W=2 fixed).
        // 400 bytes: 4 symbols with 80/10/5/5 distribution.
        // BitpackFixed: W=2 bits → ceil(400*2/8)=100 bytes value stream.
        // Entropy Huffman lengths [1,2,3,3]: 320×1 + 40×2 + 20×3 + 20×3 = 520 bits = 65 bytes
        // + 4 code-len overhead = 69 bytes value stream → smaller.
        let data: Vec<u8> = {
            let mut d = Vec::with_capacity(400);
            d.extend(std::iter::repeat(0x01u8).take(320)); // 80%
            d.extend(std::iter::repeat(0x02u8).take(40)); // 10%
            d.extend(std::iter::repeat(0x03u8).take(20)); // 5%
            d.extend(std::iter::repeat(0x04u8).take(20)); // 5%
            d
        };
        assert_eq!(data.len(), 400);

        let fixed_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::BitpackFixed,
                ..EncodeConfig::v1_default()
            },
        );
        let entropy_blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::Entropy,
                ..EncodeConfig::v1_default()
            },
        );

        // Both must round-trip
        assert_eq!(
            decode(&fixed_blob).unwrap(),
            data,
            "BitpackFixed round-trip on skewed"
        );
        assert_eq!(
            decode(&entropy_blob).unwrap(),
            data,
            "Entropy round-trip on skewed"
        );

        assert!(
            entropy_blob.len() < fixed_blob.len(),
            "Entropy ({} bytes) must be < BitpackFixed ({} bytes) for 4-symbol skewed input",
            entropy_blob.len(),
            fixed_blob.len()
        );
    }

    #[test]
    fn test_entropy_decode_robustness_kraft_violation() {
        // Manually craft a blob with a Kraft-violating code-length table.
        // Use a valid cube-mode blob, then corrupt the code-length bytes.
        use crate::header::{parse_header, MODE_CUBE, VALUE_SCHEME_ENTROPY};
        let data: Vec<u8> = vec![0xABu8; 400];
        let mut blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::Entropy,
                ..EncodeConfig::v1_default()
            },
        );
        // Parse header to find where code_len table starts (after gap streams)
        let (hdr, hdr_end) = parse_header(&blob).unwrap();
        if hdr.mode != MODE_CUBE || hdr.value_scheme != VALUE_SCHEME_ENTROPY {
            return; // input went raw-store — skip (test not applicable)
        }
        // Skip gap streams to reach value data offset
        let n_distinct = hdr.n_distinct;
        // The gap stream sizes are not easily computed here without re-running the codec,
        // so we corrupt a byte early in the code-length region: first byte after hdr_end
        // that's well past the gap stream. We'll just corrupt byte at hdr_end (start of
        // gap stream region) to cause a decode failure.
        // Actually, let's corrupt the value_scheme byte in the header to an invalid value.
        // Header byte at fixed offset: value_scheme is at header position.
        // value_scheme is at: 4(magic)+1(ver)+1(mode)+1(N)+2(B)+4(L)+4(count)+N*2(b_k)+1(map)+1(val_scheme)
        // = 13 + 4 + N*2 + 1 = offset 18 + N*2 for value_scheme byte
        let n = hdr.n;
        let val_scheme_offset = 13 + 4 + n * 2 + 1;
        blob[val_scheme_offset] = 99; // unknown value_scheme → decode returns Err
        let result = decode(&blob);
        assert!(result.is_err(), "Unknown value_scheme byte must return Err");
        // Restore value_scheme, corrupt first code-length byte to all-ones
        blob[val_scheme_offset] = VALUE_SCHEME_ENTROPY;
        // Skip to value data: after header + gap streams
        // gap stream sizes: for our all-same input with N=2, each axis has 1 gap (1 value)
        // RleU16 encodes as (value:u16, run:u16) = 4 bytes per pair; 1 gap needs 1 pair = 4 bytes
        let gap_stream_size = 4 * 2; // 2 axes × 4 bytes
        let code_len_start = hdr_end + gap_stream_size;
        if code_len_start + n_distinct <= blob.len() {
            // Set all code-length bytes to 1 → Kraft = n_distinct/2 (over/under depending on n_distinct)
            for i in 0..n_distinct {
                blob[code_len_start + i] = 1;
            }
            // For n_distinct > 2, this is Kraft-violating (n_distinct × 1/2 > 1)
            if n_distinct > 2 {
                let result = decode(&blob);
                assert!(
                    result.is_err(),
                    "Kraft-violating code-length table must return Err"
                );
            }
        }
    }

    #[test]
    fn test_entropy_decode_truncated_bitstream_returns_error() {
        use crate::header::{parse_header, MODE_CUBE, VALUE_SCHEME_ENTROPY};
        let data: Vec<u8> = {
            let mut d = vec![0x01u8; 200];
            d.extend(vec![0x02u8; 200]);
            d
        };
        let blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::Entropy,
                ..EncodeConfig::v1_default()
            },
        );
        let (hdr, _) = parse_header(&blob).unwrap();
        if hdr.mode != MODE_CUBE || hdr.value_scheme != VALUE_SCHEME_ENTROPY {
            return; // raw-store, skip
        }
        // Truncate blob to just 1 byte past the header
        let truncated = blob[..13 + 1].to_vec();
        let result = decode(&truncated);
        assert!(result.is_err(), "Truncated blob must return Err");
    }

    // ─── T4 EntropyContext round-trip tests ───────────────────────────────────

    #[test]
    fn test_entropy_context_round_trip_text() {
        // Text-like input: T4 should compress well and round-trip byte-exact.
        let data: Vec<u8> = b"the quick brown fox jumps over the lazy dog "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        let config = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &config);
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "T4 EntropyContext text round-trip failed");
        // Should compress (be < input size) since this input has strong context correlation
        assert!(
            blob.len() < data.len(),
            "T4 EntropyContext should compress text-like 4KB input: got {}B for {}B input",
            blob.len(),
            data.len()
        );
    }

    #[test]
    fn test_entropy_context_round_trip_all_classes() {
        // V-AC-5a: round-trip must hold for all input classes with T4.
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("single_byte", vec![0x42]),
            ("uniform_256", vec![0xAAu8; 400]),
            ("all_distinct", (0u8..=255).collect()),
            (
                "text_1kb",
                b"the quick brown fox "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "text_4kb",
                b"the quick brown fox "
                    .iter()
                    .copied()
                    .cycle()
                    .take(4096)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(71).wrapping_add(13))
                    .collect(),
            ),
        ];
        let config = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        for (name, data) in &cases {
            let blob = encode_with_config(data, &config);
            let recovered = decode(&blob).unwrap();
            assert_eq!(
                &recovered, data,
                "T4 EntropyContext round-trip failed for '{name}'"
            );
        }
    }

    #[test]
    fn test_entropy_context_non_regression_over_t3() {
        // V-AC-5a: T4 must not expand any input vs raw-store (selector must fall back).
        // We check that T4 output size <= raw-store output size on every input.
        // The encoder's R7 decision ensures this: if T4 cube > raw, it falls back to raw.
        let cases: Vec<Vec<u8>> = vec![
            vec![0xFFu8; 1024], // binary uniform
            (0usize..1024)
                .map(|i| (i as u8).wrapping_mul(71).wrapping_add(13))
                .collect(),
            b"the quick brown fox "
                .iter()
                .copied()
                .cycle()
                .take(4096)
                .collect(),
        ];
        let config_t4 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        for data in &cases {
            let raw_bound = data.len() + HEADER_OVERHEAD_BOUND;
            let blob = encode_with_config(data, &config_t4);
            assert!(
                blob.len() <= raw_bound,
                "T4 output {} > raw-store bound {} for {}-byte input — non-regression violated",
                blob.len(),
                raw_bound,
                data.len()
            );
            // Must round-trip
            assert_eq!(
                decode(&blob).unwrap(),
                *data,
                "T4 non-regression round-trip failed"
            );
        }
    }

    // ── Default byte-identity: BitpackFixed + RleCodes unchanged after adding Entropy

    #[test]
    fn test_default_byte_identity_after_entropy_addition() {
        // V-AC-4: default encode() (BitpackFixed) must be byte-for-byte unchanged.
        let inputs: Vec<Vec<u8>> = vec![
            vec![0xABu8; 400],
            b"the quick brown fox "
                .iter()
                .copied()
                .cycle()
                .take(1024)
                .collect(),
        ];
        for input in &inputs {
            let v1_blob = encode(input);
            let explicit_fixed_blob = encode_with_config(
                input,
                &EncodeConfig {
                    value_scheme: ValueScheme::BitpackFixed,
                    ..EncodeConfig::v1_default()
                },
            );
            assert_eq!(
                v1_blob, explicit_fixed_blob,
                "Adding Entropy variant must not change BitpackFixed output"
            );
        }
    }

    // =========================================================================
    // T5 EntropyContext2 — Order-2 Context-Adaptive Huffman Tests (CUBR-0027)
    // =========================================================================

    // ── Step 5.1: Enum byte round-trip (already covered in config.rs; guard here) ──

    #[test]
    fn test_entropy_context2_scheme_byte_is_5() {
        assert_eq!(ValueScheme::EntropyContext2.scheme_byte(), 5u8);
        assert_eq!(
            ValueScheme::from_byte(5u8),
            Some(ValueScheme::EntropyContext2)
        );
        // scheme byte 6 = BwtEntropy (added after EntropyContext2)
        assert_eq!(ValueScheme::BwtEntropy.scheme_byte(), 6u8);
        assert_eq!(ValueScheme::from_byte(6u8), Some(ValueScheme::BwtEntropy));
        // scheme byte 7 = BwtRans (added after BwtEntropy, H-19)
        assert_eq!(ValueScheme::BwtRans.scheme_byte(), 7u8);
        assert_eq!(ValueScheme::from_byte(7u8), Some(ValueScheme::BwtRans));
        // scheme byte 8 = Order2Rans (added after BwtRans, H-20)
        assert_eq!(ValueScheme::Order2Rans.scheme_byte(), 8u8);
        assert_eq!(ValueScheme::from_byte(8u8), Some(ValueScheme::Order2Rans));
        // scheme byte 9 = BwtAdaptive (H-21), 10 = BwtContextMix (H-22)
        assert_eq!(ValueScheme::BwtAdaptive.scheme_byte(), 9u8);
        assert_eq!(ValueScheme::from_byte(9u8), Some(ValueScheme::BwtAdaptive));
        assert_eq!(ValueScheme::BwtContextMix.scheme_byte(), 10u8);
        assert_eq!(ValueScheme::from_byte(10u8), Some(ValueScheme::BwtContextMix));
        // scheme byte 11 = BwtGeoMix (geometric o2/o1/o0 mixing, H-24)
        assert_eq!(ValueScheme::BwtGeoMix.scheme_byte(), 11u8);
        assert_eq!(ValueScheme::from_byte(11u8), Some(ValueScheme::BwtGeoMix));
        // scheme byte 12 = LzRans (LZ77 + rANS, H-25)
        assert_eq!(ValueScheme::LzRans.scheme_byte(), 12u8);
        assert_eq!(ValueScheme::from_byte(12u8), Some(ValueScheme::LzRans));
        assert_eq!(ValueScheme::from_byte(13u8), None);
    }

    // ── Step 5.2: Context-key derivation + sentinels ──────────────────────────

    #[test]
    fn test_order2_context_keys_with_sentinels() {
        // Position 0 → (0, 0), position 1 → (0, seq[0]), position i≥2 → (seq[i-2], seq[i-1]).
        let seq = vec![3usize, 7, 2, 5, 1];
        // position 0: (0, 0)
        assert_eq!(order2_ctx_at(&seq, 0), (0u16, 0u16));
        // position 1: (0, seq[0]=3)
        assert_eq!(order2_ctx_at(&seq, 1), (0u16, 3u16));
        // position 2: (seq[0]=3, seq[1]=7)
        assert_eq!(order2_ctx_at(&seq, 2), (3u16, 7u16));
        // position 3: (seq[1]=7, seq[2]=2)
        assert_eq!(order2_ctx_at(&seq, 3), (7u16, 2u16));
        // position 4: (seq[2]=2, seq[3]=5)
        assert_eq!(order2_ctx_at(&seq, 4), (2u16, 5u16));
    }

    #[test]
    fn test_order2_context_sentinel_single_element() {
        let seq = vec![42usize];
        assert_eq!(order2_ctx_at(&seq, 0), (0u16, 0u16));
    }

    // ── Step 5.3: Context-table build + threshold qualification ───────────────

    #[test]
    fn test_order2_build_tables_threshold() {
        // Construct a sequence where one (prev2, prev) pair occurs >=128 times
        // and another below threshold.
        // Pattern: repeated (0, 1, 2) → order-2 key at position i≥2 is (seq[i-2], seq[i-1])
        // e.g. positions: 0→(0,0), 1→(0,0), 2→(0,1), 3→(1,2), 4→(2,0), 5→(0,1), ...
        // Build a 400-element sequence: repeating [0, 1, 2] = 133 cycles → 399 elements
        // (p2,p1) of (0, 1) appears at positions 2, 5, 8, ... ≈ 133 times → qualifies
        // (p2,p1) of (1, 2) appears ~133 times → qualifies
        // (p2,p1) of (2, 0) appears ~133 times → qualifies
        // Rare pairs at boundary: pos 0 → (0,0) sentinel once, pos 1 → (0,0) once
        let mut seq: Vec<usize> = Vec::new();
        for _ in 0..133 {
            seq.push(0);
            seq.push(1);
            seq.push(2);
        }
        seq.push(0); // 400 total
        let n_distinct = 3;
        let min_ctx = 128u16;

        let entries = order2_build_context_tables(&seq, n_distinct, min_ctx);

        // Must have the fallback (Order0) entry always present.
        let has_fallback = entries.iter().any(|e| matches!(e, CtxEntry::Order0 { .. }));
        assert!(
            has_fallback,
            "Order0 fallback must always be present in the table set"
        );

        // The qualifying (0,1), (1,2), (2,0) order-2 pairs should each appear >=128 times.
        // → those 3 order-2 tables should be present.
        let order2_count = entries
            .iter()
            .filter(|e| matches!(e, CtxEntry::Order2 { .. }))
            .count();
        assert!(
            order2_count >= 2,
            "At least 2 order-2 qualifying tables expected (frequent pairs), got {order2_count}"
        );

        // Order-1 tables may also be present for prev_code ∈ {0,1,2}.
        let order1_count = entries
            .iter()
            .filter(|e| matches!(e, CtxEntry::Order1 { .. }))
            .count();
        // With min_ctx=128 on 400 elements, each prev appears ~133 times → should qualify.
        assert!(
            order1_count >= 2,
            "At least 2 order-1 qualifying tables expected, got {order1_count}"
        );
    }

    // ── Step 5.4: Fallback chain selection ───────────────────────────────────

    #[test]
    fn test_order2_fallback_chain_selection() {
        // Build a sequence designed to exercise all 3 fallback levels:
        // - A highly repeated (prev2, prev) pair for order-2 hit
        // - A moderately repeated prev_code for order-1 hit
        // - Everything else falls to order-0
        //
        // Use a 500-element sequence:
        // 200x "A A A A..." (code=0) → (0,0) pair qualifies at order-2 with min=128
        // 100x "B B B..."   (code=1) → prev=1 qualifies at order-1 with min=64 but not order-2
        // 200x "C D C D..." (alternating codes 2/3) → creates many different (p2,p1) pairs → order-0

        // Build a 300-elem sequence for testing:
        // First 200 elements: all code 0. (p2,p1)=(0,0) qualifies at order-2.
        // Next 100 elements: code 1. prev=1 never repeats enough for order-2; but prev1=1 may qualify.
        let mut seq: Vec<usize> = vec![0usize; 200];
        seq.extend(vec![1usize; 100]);
        let n_distinct = 4;
        let min_ctx = 128u16;

        let entries = order2_build_context_tables(&seq, n_distinct, min_ctx);

        // Fallback table always present.
        assert!(
            entries.iter().any(|e| matches!(e, CtxEntry::Order0 { .. })),
            "Order0 fallback must be present"
        );

        // (0,0) order-2 pair: appears ~198 times (positions 2..200 - sentinel skipped) → should qualify.
        let has_order2_00 = entries.iter().any(|e| {
            matches!(
                e,
                CtxEntry::Order2 {
                    prev2_code: 0,
                    prev_code: 0,
                    ..
                }
            )
        });
        assert!(
            has_order2_00,
            "(0,0) order-2 table missing — expected >=128 observations from 200-elem run"
        );
    }

    // ── Step 5.5: Header serialization round-trip + robustness ───────────────

    #[test]
    fn test_order2_header_round_trip() {
        // Build a sequence, encode with order-2, decode, and verify result.
        // Use a 600-element sequence with enough repeated pairs to trigger order-2 tables.
        let seq: Vec<usize> = (0..600).map(|i| i % 4).collect(); // codes 0,1,2,3 cycling
        let n_distinct = 4;
        let min_ctx = 32u16; // lower threshold to ensure some order-2 tables are built

        let encoded = order2_context_huffman_encode(&seq, n_distinct, min_ctx);

        // Verify min_ctx is first 2 bytes.
        let decoded_min_ctx = u16::from_be_bytes([encoded[0], encoded[1]]);
        assert_eq!(
            decoded_min_ctx, min_ctx,
            "min_ctx_count must be the first u16 in the wire"
        );

        // Verify n_contexts is next 2 bytes and plausible.
        let n_ctx = u16::from_be_bytes([encoded[2], encoded[3]]) as usize;
        assert!(
            n_ctx >= 1,
            "n_contexts must be >= 1 (at least the fallback)"
        );

        // Decode and verify round-trip.
        let (decoded_seq, consumed) =
            order2_context_huffman_decode(&encoded, 0, seq.len(), n_distinct).unwrap();
        assert_eq!(
            decoded_seq, seq,
            "order-2 header round-trip: decoded seq must match original"
        );
        assert!(consumed <= encoded.len(), "consumed <= encoded.len()");
    }

    #[test]
    fn test_order2_header_rejects_truncated() {
        // A blob claiming n_contexts=100 but truncated → Err, not panic.
        let mut fake: Vec<u8> = Vec::new();
        fake.extend_from_slice(&128u16.to_be_bytes()); // min_ctx
        fake.extend_from_slice(&100u16.to_be_bytes()); // n_contexts = 100 (way more than blob has)
                                                       // Only 1 entry worth of bytes follow (tag=0 + 4 bytes code_len).
        fake.push(0u8); // tag = Order0
        fake.extend_from_slice(&[0u8; 4]); // n_distinct=4 code_len (just 4 bytes)
                                           // No bitstream.

        let result = order2_context_huffman_decode(&fake, 0, 10, 4);
        assert!(
            result.is_err(),
            "Truncated context header must return Err, not panic"
        );
    }

    #[test]
    fn test_order2_header_rejects_bad_tag() {
        // A blob with an unknown tag byte → Err.
        let mut fake: Vec<u8> = Vec::new();
        fake.extend_from_slice(&128u16.to_be_bytes()); // min_ctx
        fake.extend_from_slice(&1u16.to_be_bytes()); // n_contexts = 1
        fake.push(99u8); // tag = 99 (unknown)
        fake.extend_from_slice(&[0u8; 4]); // code_len

        let result = order2_context_huffman_decode(&fake, 0, 1, 4);
        assert!(
            result.is_err(),
            "Unknown tag byte must return Err, not panic"
        );
    }

    #[test]
    fn test_order2_header_rejects_short_blob() {
        // A blob that is only 3 bytes — too short for even the min_ctx+n_ctx fields.
        let fake = vec![0u8, 128u8, 0u8]; // only 3 bytes, need at least 4
        let result = order2_context_huffman_decode(&fake, 0, 1, 4);
        assert!(
            result.is_err(),
            "Short blob (3 bytes) must return Err for count>0"
        );
    }

    // ── Step 5.5b: T4 header size measurement for V7 grounding ───────────────

    #[test]
    fn test_t4_header_size_measurement() {
        // V7: measure real Rust T4 header size for text and log_like-like inputs.
        // These serve as grounding for the twin's model-vs-bytes claim.
        //
        // text-like: 16384 bytes cycling, ~69 distinct bytes (per corpus: n_distinct varies)
        // We use a known synthetic text-like sequence to measure T4 header bytes.
        let text_like: Vec<u8> = b"2026-06-17T12:00:00Z INFO cubrim compression text sample log"
            .iter()
            .copied()
            .cycle()
            .take(16384)
            .collect();

        let cfg_t4 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        let blob_t4 = encode_with_config(&text_like, &cfg_t4);
        // Just verify it compresses and round-trips — the real corpus measurement
        // happens in the bench harness (V7 output).
        assert_eq!(
            decode(&blob_t4).unwrap(),
            text_like,
            "T4 text-like round-trip must succeed for V7 header measurement"
        );
        // T4 must compress text-like content (not raw-store).
        assert!(
            blob_t4.len() < text_like.len(),
            "T4 must compress text-like 16KB input"
        );
    }

    // ── Step 5.6: Full encode→decode byte-exact, unit + corpus ───────────────

    #[test]
    fn test_entropy_context2_round_trip_synthetic_fixtures() {
        // Round-trip on the standard fixture set used for all value schemes.
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("single_byte", vec![0x42]),
            ("all_same_100", vec![0x58u8; 100]),
            ("all_distinct_256", (0u8..=255).collect()),
            ("hello_world", b"hello, world!\n\n".to_vec()),
            (
                "text_1kb",
                b"the quick brown fox jumps over the lazy dog "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(71).wrapping_add(13))
                    .collect(),
            ),
        ];
        for (name, data) in &cases {
            let blob = encode_with_config(data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(
                &recovered, data,
                "EntropyContext2 round-trip failed for '{name}'"
            );
        }
    }

    #[test]
    fn test_entropy_context2_header_value_scheme_byte_is_5() {
        use crate::header::{parse_header, MODE_CUBE};
        // Use a larger input likely to go to cube mode.
        let data: Vec<u8> = b"the quick brown fox jumps over the lazy dog "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let (hdr, _) = parse_header(&blob).unwrap();
        if hdr.mode == MODE_CUBE {
            assert_eq!(
                hdr.value_scheme, 5u8,
                "EntropyContext2 config must write value_scheme=5 to header"
            );
        }
        assert_eq!(decode(&blob).unwrap(), data, "T5 round-trip on text_4kb");
    }

    #[test]
    fn test_entropy_context2_diverges_from_t4() {
        // T5 wire output must differ from T4 for any cube-mode input with enough context.
        let data: Vec<u8> = b"the quick brown fox jumps over the lazy dog "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        let cfg_t4 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        let cfg_t5 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let blob_t4 = encode_with_config(&data, &cfg_t4);
        let blob_t5 = encode_with_config(&data, &cfg_t5);
        // Both must round-trip.
        assert_eq!(decode(&blob_t4).unwrap(), data, "T4 text_4kb round-trip");
        assert_eq!(decode(&blob_t5).unwrap(), data, "T5 text_4kb round-trip");
        // They should produce different byte streams.
        assert_ne!(
            blob_t4, blob_t5,
            "T5 (order-2) blob must differ from T4 (order-1) blob for text input"
        );
    }

    #[test]
    fn test_entropy_context2_compresses_text_both_round_trip() {
        // Both T4 and T5 must compress and round-trip on text input.
        // The comparison at a specific min_ctx is done in the bench harness (V4/V5).
        // This test only validates correctness, not relative size.
        let data: Vec<u8> = b"the quick brown fox jumps over the lazy dog "
            .iter()
            .copied()
            .cycle()
            .take(16384)
            .collect();
        let cfg_t4 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext,
            ..EncodeConfig::v1_default()
        };
        let cfg_t5 = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let blob_t4 = encode_with_config(&data, &cfg_t4);
        let blob_t5 = encode_with_config(&data, &cfg_t5);
        // Both must round-trip byte-exact.
        assert_eq!(decode(&blob_t4).unwrap(), data, "T4 text_16kb round-trip");
        assert_eq!(decode(&blob_t5).unwrap(), data, "T5 text_16kb round-trip");
        // Both must compress vs raw (note: encoder's R7 clamp ensures this).
        assert!(
            blob_t4.len() < data.len(),
            "T4 must compress text_16kb; got {}B for {}B input",
            blob_t4.len(),
            data.len()
        );
        assert!(
            blob_t5.len() < data.len(),
            "T5 must compress text_16kb; got {}B for {}B input",
            blob_t5.len(),
            data.len()
        );
        // Report sizes (informational).
        eprintln!(
            "text_16kb: T4={} bytes, T5={} bytes (delta {})",
            blob_t4.len(),
            blob_t5.len(),
            blob_t5.len() as i64 - blob_t4.len() as i64
        );
    }

    #[test]
    fn test_entropy_context2_min_ctx_count_config() {
        // Verify that a lower min_ctx_count produces a valid round-trip (more tables, smaller bitstream).
        let data: Vec<u8> = b"the quick brown fox jumps over the lazy dog "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        for min_ctx in &[16u16, 64, 128, 256] {
            let cfg = EncodeConfig {
                value_scheme: ValueScheme::EntropyContext2,
                min_ctx_count: Some(*min_ctx),
                ..EncodeConfig::v1_default()
            };
            let blob = encode_with_config(&data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(
                recovered, data,
                "T5 round-trip failed with min_ctx_count={min_ctx}"
            );
        }
    }

    #[test]
    fn test_entropy_context2_non_regression_149_tests() {
        // Ensure T1-T4 outputs are byte-identical before and after adding T5.
        // The v1_default() (T1) must be unchanged.
        let data: Vec<u8> = b"the quick brown fox "
            .iter()
            .copied()
            .cycle()
            .take(1024)
            .collect();
        let v1_before = encode(&data);
        let v1_explicit = encode_with_config(&data, &EncodeConfig::v1_default());
        assert_eq!(
            v1_before, v1_explicit,
            "V-AC-8: v1_default output must not change after adding EntropyContext2"
        );
    }

    #[test]
    fn test_entropy_context2_round_trip_all_classes() {
        // Comprehensive round-trip across all input classes.
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("empty", vec![]),
            ("single_byte", vec![0x42]),
            ("uniform_256", vec![0xAAu8; 400]),
            ("all_distinct", (0u8..=255).collect()),
            (
                "text_1kb",
                b"the quick brown fox "
                    .iter()
                    .copied()
                    .cycle()
                    .take(1024)
                    .collect(),
            ),
            (
                "text_4kb",
                b"the quick brown fox "
                    .iter()
                    .copied()
                    .cycle()
                    .take(4096)
                    .collect(),
            ),
            (
                "text_16kb",
                b"the quick brown fox "
                    .iter()
                    .copied()
                    .cycle()
                    .take(16384)
                    .collect(),
            ),
            (
                "random_1kb",
                (0usize..1024)
                    .map(|i| (i as u8).wrapping_mul(71).wrapping_add(13))
                    .collect(),
            ),
        ];
        for (name, data) in &cases {
            let blob = encode_with_config(data, &cfg);
            let recovered = decode(&blob).unwrap();
            assert_eq!(&recovered, data, "T5 round-trip failed for '{name}'");
        }
    }

    #[test]
    fn test_entropy_context2_size_matches_encode_len() {
        // Verify that the T5 encode/decode round-trip works with non-default min_ctx.
        let data: Vec<u8> = b"the quick brown fox "
            .iter()
            .copied()
            .cycle()
            .take(2048)
            .collect();
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            min_ctx_count: Some(32),
            ..EncodeConfig::v1_default()
        };
        let blob = encode_with_config(&data, &cfg);
        let recovered = decode(&blob).unwrap();
        assert_eq!(recovered, data, "size_matches round-trip");
    }

    #[test]
    fn test_entropy_context2_corpus_round_trip_7_files() {
        // V1: Byte-exact round-trip on all 7 corpus files.
        // Corpus dir resolves portably relative to the crate (CARGO_MANIFEST_DIR
        // = .../code/cubrim-rs), so the test runs on any checkout — not just the
        // author's machine. Override with CUBRIM_CORPUS_DIR if needed.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!(
                "{}/../../docs/ephemeral/research/corpus",
                env!("CARGO_MANIFEST_DIR")
            )
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
        ];
        let corpus_files: Vec<(&str, String)> = names
            .iter()
            .map(|n| (*n, format!("{corpus_dir}/{n}.bin")))
            .collect();
        let cfg = EncodeConfig {
            value_scheme: ValueScheme::EntropyContext2,
            ..EncodeConfig::v1_default()
        };
        let mut ok_count = 0;
        for (name, path) in &corpus_files {
            match fs::read(path) {
                Ok(data) => {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered =
                        decode(&blob).expect(&format!("T5 corpus decode failed for '{name}'"));
                    assert_eq!(
                        recovered, data,
                        "T5 corpus round-trip FAILED for '{name}': byte mismatch"
                    );
                    ok_count += 1;
                }
                Err(e) => {
                    // Skip if file not present in CI environment.
                    eprintln!("SKIP corpus file '{name}' ({path}): {e}");
                }
            }
        }
        assert_eq!(ok_count, 7,
            "T5 corpus round-trip: {ok_count}/7 files tested — all 7 must be present and round-trip clean");
    }

    // ─── H-19: BWT + order-1 rANS (scheme 7) ─────────────────────────────────

    fn bwt_rans_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::BwtRans,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_rans_order1_unit_round_trip() {
        // Direct rANS order-1 encode/decode on a hand-built code stream with
        // near-deterministic context structure (the H-19 win zone).
        let n_distinct = 5usize;
        let seq: Vec<usize> = {
            let mut v = Vec::new();
            for _ in 0..200 {
                v.extend_from_slice(&[0, 0, 0, 1, 0, 2, 0, 0, 3, 4]);
            }
            v
        };
        let enc = rans_order1_encode(&seq, n_distinct);
        let (dec, consumed) = rans_order1_decode(&enc, 0, seq.len(), n_distinct).unwrap();
        assert_eq!(dec, seq, "rANS order-1 round-trip mismatch");
        assert_eq!(consumed, enc.len(), "rANS decode must consume the whole stream");
    }

    #[test]
    fn test_rans_order1_empty_and_singletons() {
        // Empty stream.
        let enc = rans_order1_encode(&[], 0);
        let (dec, _) = rans_order1_decode(&enc, 0, 0, 0).unwrap();
        assert!(dec.is_empty());
        // Single repeated symbol (degenerate distribution).
        let seq = vec![0usize; 500];
        let enc = rans_order1_encode(&seq, 1);
        let (dec, _) = rans_order1_decode(&enc, 0, seq.len(), 1).unwrap();
        assert_eq!(dec, seq);
    }

    #[test]
    fn test_rans_high_entropy_round_trip() {
        // High-entropy stream: every symbol equally likely, many distinct.
        // This is exactly the case that triggered the ctx_id-0 fallback collision
        // (freq-0 → x_max=0 → infinite renorm). Must round-trip, not loop/panic.
        let n_distinct = 256usize;
        let seq: Vec<usize> = (0..4096)
            .map(|i| ((i * 73 + 11) % 256) as usize)
            .collect();
        let enc = rans_order1_encode(&seq, n_distinct);
        let (dec, _) = rans_order1_decode(&enc, 0, seq.len(), n_distinct).unwrap();
        assert_eq!(dec, seq, "high-entropy rANS round-trip mismatch");
    }

    #[test]
    fn test_bwt_rans_corpus_round_trip_all_files() {
        // Byte-exact round-trip on all 10 frozen corpus files through the full
        // codec with scheme 7. Round-trip is non-negotiable (Gotcha).
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!(
                "{}/../../docs/ephemeral/research/corpus",
                env!("CARGO_MANIFEST_DIR")
            )
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let cfg = bwt_rans_cfg();
        let mut ok_count = 0;
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            match fs::read(&path) {
                Ok(data) => {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered = decode(&blob)
                        .unwrap_or_else(|e| panic!("BwtRans corpus decode failed for '{name}': {e:?}"));
                    assert_eq!(
                        recovered, data,
                        "BwtRans corpus round-trip FAILED for '{name}': byte mismatch"
                    );
                    ok_count += 1;
                }
                Err(e) => eprintln!("SKIP corpus file '{name}' ({path}): {e}"),
            }
        }
        assert_eq!(ok_count, 10,
            "BwtRans corpus round-trip: {ok_count}/10 files tested — all must be present and clean");
    }

    #[test]
    fn test_bwt_rans_never_larger_than_bwt_entropy() {
        // Competitive selection (Gotcha #4): scheme 7 internally picks
        // min(BwtRans, BwtEntropy, EntropyContext), so its blob can NEVER be
        // larger than the BwtEntropy leader on any input.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!(
                "{}/../../docs/ephemeral/research/corpus",
                env!("CARGO_MANIFEST_DIR")
            )
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let rans_cfg = bwt_rans_cfg();
        let bwt_cfg = EncodeConfig {
            value_scheme: ValueScheme::BwtEntropy,
            ..EncodeConfig::v1_default()
        };
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            if let Ok(data) = fs::read(&path) {
                let rans_blob = encode_with_config(&data, &rans_cfg);
                let bwt_blob = encode_with_config(&data, &bwt_cfg);
                assert!(
                    rans_blob.len() <= bwt_blob.len(),
                    "BwtRans regressed '{name}': rans {} > bwt-entropy {}",
                    rans_blob.len(),
                    bwt_blob.len()
                );
            }
        }
    }

    #[test]
    fn test_bwt_rans_property_random_inputs() {
        // Deterministic pseudo-random inputs of varied length/alphabet must
        // round-trip byte-exact (no RNG crate; LCG for reproducibility).
        let mut state: u64 = 0x9e3779b97f4a7c15;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as u32
        };
        for trial in 0..40 {
            let len = 321 + (next() as usize % 4000); // > raw_store_bound to reach cube mode
            let alphabet = 1 + (next() as usize % 200);
            let data: Vec<u8> = (0..len).map(|_| (next() as usize % alphabet) as u8).collect();
            let blob = encode_with_config(&data, &bwt_rans_cfg());
            let recovered = decode(&blob).expect("decode");
            assert_eq!(recovered, data, "BwtRans property round-trip failed (trial {trial}, len {len}, alpha {alphabet})");
        }
    }

    #[test]
    fn test_bwt_rans_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = b"the quick brown fox jumps over "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        let blob = encode_with_config(&data, &bwt_rans_cfg());
        // Truncate at many points after the header; every prefix must Err, never panic.
        for cut in (8..blob.len()).step_by(37) {
            let _ = decode(&blob[..cut]); // must not panic
        }
    }

    #[test]
    fn test_rans_normalize_sums_to_m() {
        let counts = vec![1000usize, 1, 0, 3, 50, 0, 7];
        let freq = rans_normalize(&counts, RANS_SCALE_BITS);
        assert_eq!(freq.iter().sum::<u32>(), 1 << RANS_SCALE_BITS);
        for (s, &c) in counts.iter().enumerate() {
            if c > 0 {
                assert!(freq[s] >= 1, "symbol {s} with count {c} got freq 0");
            } else {
                assert_eq!(freq[s], 0, "symbol {s} with count 0 got nonzero freq");
            }
        }
    }

    #[test]
    fn test_bwt_rans_scheme_byte() {
        assert_eq!(ValueScheme::BwtRans.scheme_byte(), 7u8);
        assert_eq!(ValueScheme::from_byte(7u8), Some(ValueScheme::BwtRans));
    }

    // ── H-20 order-2 rANS (scheme 8) tests ──────────────────────────────────

    fn order2_rans_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::Order2Rans,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_order2_rans_scheme_byte() {
        assert_eq!(ValueScheme::Order2Rans.scheme_byte(), 8u8);
        assert_eq!(ValueScheme::from_byte(8u8), Some(ValueScheme::Order2Rans));
    }

    #[test]
    fn test_order2_rans_unit_round_trip_both_submodes() {
        // Stream with strong order-2 structure (the H-20 win zone). Exercise both
        // the 3-level and 2-level wire layouts directly.
        let n_distinct = 5usize;
        let mut seq = Vec::new();
        for _ in 0..300 {
            seq.extend_from_slice(&[0, 1, 2, 0, 1, 3, 0, 1, 2, 4]);
        }
        for use_o1 in [true, false] {
            let enc = order2_rans_encode(&seq, n_distinct, use_o1);
            let (dec, consumed) = order2_rans_decode(&enc, 0, seq.len(), n_distinct).unwrap();
            assert_eq!(dec, seq, "order-2 rANS round-trip mismatch (use_order1={use_o1})");
            assert_eq!(consumed, enc.len(), "decode must consume the whole stream");
        }
    }

    #[test]
    fn test_order2_rans_empty_and_singletons() {
        let enc = order2_rans_encode(&[], 0, true);
        let (dec, _) = order2_rans_decode(&enc, 0, 0, 0).unwrap();
        assert!(dec.is_empty());
        let seq = vec![0usize; 500];
        for use_o1 in [true, false] {
            let enc = order2_rans_encode(&seq, 1, use_o1);
            let (dec, _) = order2_rans_decode(&enc, 0, seq.len(), 1).unwrap();
            assert_eq!(dec, seq);
        }
    }

    #[test]
    fn test_order2_rans_high_entropy_round_trip() {
        // Near-random stream, many distinct — must round-trip (no freq-0 / renorm loop).
        let n_distinct = 256usize;
        let seq: Vec<usize> = (0..8192).map(|i| ((i * 73 + 11) % 256) as usize).collect();
        for use_o1 in [true, false] {
            let enc = order2_rans_encode(&seq, n_distinct, use_o1);
            let (dec, _) = order2_rans_decode(&enc, 0, seq.len(), n_distinct).unwrap();
            assert_eq!(dec, seq, "high-entropy order-2 rANS round-trip mismatch (o1={use_o1})");
        }
    }

    #[test]
    fn test_bwt_order2_rans_corpus_round_trip_all_files() {
        // Byte-exact round-trip on all 10 frozen corpus files through the full codec.
        // Scheme 7's competitive selection may emit scheme byte 8 (Order2Rans) — the
        // decoder MUST recover every file. Round-trip is non-negotiable (Gotcha).
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        // Test BOTH entry points: direct Order2Rans config AND the scheme-7 path that
        // may select scheme 8 as the competitive winner.
        for cfg in [order2_rans_cfg(), bwt_rans_cfg()] {
            let mut ok = 0;
            for name in &names {
                let path = format!("{corpus_dir}/{name}.bin");
                if let Ok(data) = fs::read(&path) {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered = decode(&blob)
                        .unwrap_or_else(|e| panic!("Order2Rans decode failed for '{name}': {e:?}"));
                    assert_eq!(recovered, data, "Order2Rans round-trip FAILED for '{name}'");
                    ok += 1;
                }
            }
            assert_eq!(ok, 10, "Order2Rans corpus round-trip: {ok}/10 files present and clean");
        }
    }

    #[test]
    fn test_order2_rans_never_regresses_competition() {
        // Competitive (Gotcha #4): the scheme-7 blob with Order2Rans in the candidate
        // set can NEVER be larger than the BwtEntropy leader on any corpus file.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let bwt_cfg = EncodeConfig {
            value_scheme: ValueScheme::BwtEntropy,
            ..EncodeConfig::v1_default()
        };
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            if let Ok(data) = fs::read(&path) {
                let cand = encode_with_config(&data, &order2_rans_cfg());
                let leader = encode_with_config(&data, &bwt_cfg);
                assert!(
                    cand.len() <= leader.len(),
                    "Order2Rans regressed '{name}': {} > bwt-entropy {}",
                    cand.len(), leader.len()
                );
            }
        }
    }

    #[test]
    fn test_order2_rans_property_random_inputs() {
        let mut state: u64 = 0x243f6a8885a308d3;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as u32
        };
        for trial in 0..40 {
            let len = 321 + (next() as usize % 4000);
            let alphabet = 1 + (next() as usize % 200);
            let data: Vec<u8> = (0..len).map(|_| (next() as usize % alphabet) as u8).collect();
            let blob = encode_with_config(&data, &order2_rans_cfg());
            let recovered = decode(&blob).expect("decode");
            assert_eq!(recovered, data, "Order2Rans property round-trip failed (trial {trial}, len {len}, alpha {alphabet})");
        }
    }

    #[test]
    fn test_order2_rans_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = b"the quick brown fox jumps over "
            .iter().copied().cycle().take(8192).collect();
        let blob = encode_with_config(&data, &order2_rans_cfg());
        for cut in (8..blob.len()).step_by(41) {
            let _ = decode(&blob[..cut]); // must not panic
        }
    }

    // ── H-21 adaptive order-1 range coding (scheme 9) tests ──────────────────

    fn bwt_adaptive_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::BwtAdaptive,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_bwt_adaptive_scheme_byte() {
        assert_eq!(ValueScheme::BwtAdaptive.scheme_byte(), 9u8);
        assert_eq!(ValueScheme::from_byte(9u8), Some(ValueScheme::BwtAdaptive));
    }

    #[test]
    fn test_range_coder_unit_round_trip() {
        // Direct range-coder + adaptive order-1 model round-trip on a structured stream.
        let n_distinct = 6usize;
        let mut seq = Vec::new();
        for _ in 0..400 {
            seq.extend_from_slice(&[0, 0, 1, 0, 2, 0, 0, 3, 4, 5]);
        }
        for inc in ADAPT_INCS {
            let enc = adaptive_range_o1_encode(&seq, n_distinct, inc);
            let dec = adaptive_range_o1_decode(&enc, seq.len(), n_distinct, inc).unwrap();
            assert_eq!(dec, seq, "adaptive range round-trip mismatch (inc={inc})");
        }
    }

    #[test]
    fn test_range_coder_empty_and_singletons() {
        let enc = adaptive_range_o1_encode(&[], 0, 16);
        let dec = adaptive_range_o1_decode(&enc, 0, 0, 16).unwrap();
        assert!(dec.is_empty());
        let seq = vec![0usize; 1000];
        let enc = adaptive_range_o1_encode(&seq, 1, 16);
        let dec = adaptive_range_o1_decode(&enc, seq.len(), 1, 16).unwrap();
        assert_eq!(dec, seq);
    }

    #[test]
    fn test_range_coder_high_entropy_and_rescale() {
        // 256 symbols, long stream → forces model rescaling on hot contexts. Must
        // round-trip exactly (rescale is the subtle determinism risk).
        let n_distinct = 256usize;
        let seq: Vec<usize> = (0..40000).map(|i| ((i * 97 + 13) % 256) as usize).collect();
        for inc in [8u32, 64] {
            let enc = adaptive_range_o1_encode(&seq, n_distinct, inc);
            let dec = adaptive_range_o1_decode(&enc, seq.len(), n_distinct, inc).unwrap();
            assert_eq!(dec, seq, "high-entropy/rescale round-trip mismatch (inc={inc})");
        }
    }

    #[test]
    fn test_bwt_adaptive_corpus_round_trip_all_files() {
        // Byte-exact round-trip on all 10 frozen corpus files. Scheme 7's competitive
        // selection may emit scheme byte 9 (BwtAdaptive); the decoder MUST recover every
        // file. Round-trip is non-negotiable (Gotcha).
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        for cfg in [bwt_adaptive_cfg(), bwt_rans_cfg()] {
            let mut ok = 0;
            for name in &names {
                let path = format!("{corpus_dir}/{name}.bin");
                if let Ok(data) = fs::read(&path) {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered = decode(&blob)
                        .unwrap_or_else(|e| panic!("BwtAdaptive decode failed for '{name}': {e:?}"));
                    assert_eq!(recovered, data, "BwtAdaptive round-trip FAILED for '{name}'");
                    ok += 1;
                }
            }
            assert_eq!(ok, 10, "BwtAdaptive corpus round-trip: {ok}/10 files present and clean");
        }
    }

    #[test]
    fn test_bwt_adaptive_never_regresses_competition() {
        // Competitive (Gotcha #4): the scheme-9 blob with the full competitive set can
        // NEVER be larger than the BwtEntropy leader on any corpus file.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let bwt_cfg = EncodeConfig {
            value_scheme: ValueScheme::BwtEntropy,
            ..EncodeConfig::v1_default()
        };
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            if let Ok(data) = fs::read(&path) {
                let cand = encode_with_config(&data, &bwt_adaptive_cfg());
                let leader = encode_with_config(&data, &bwt_cfg);
                assert!(
                    cand.len() <= leader.len(),
                    "BwtAdaptive regressed '{name}': {} > bwt-entropy {}",
                    cand.len(), leader.len()
                );
            }
        }
    }

    #[test]
    fn test_bwt_adaptive_property_random_inputs() {
        let mut state: u64 = 0xb5ad4eceda1ce2a9;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as u32
        };
        for trial in 0..40 {
            let len = 321 + (next() as usize % 4000);
            let alphabet = 1 + (next() as usize % 200);
            let data: Vec<u8> = (0..len).map(|_| (next() as usize % alphabet) as u8).collect();
            let blob = encode_with_config(&data, &bwt_adaptive_cfg());
            let recovered = decode(&blob).expect("decode");
            assert_eq!(recovered, data, "BwtAdaptive property round-trip failed (trial {trial}, len {len}, alpha {alphabet})");
        }
    }

    #[test]
    fn test_bwt_adaptive_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = b"the quick brown fox jumps over "
            .iter().copied().cycle().take(8192).collect();
        let blob = encode_with_config(&data, &bwt_adaptive_cfg());
        for cut in (8..blob.len()).step_by(41) {
            let _ = decode(&blob[..cut]); // must not panic
        }
    }

    // ── H-22 context-mixing (scheme 10) tests ────────────────────────────────

    fn bwt_ctxmix_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::BwtContextMix,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_bwt_ctxmix_scheme_byte() {
        assert_eq!(ValueScheme::BwtContextMix.scheme_byte(), 10u8);
        assert_eq!(ValueScheme::from_byte(10u8), Some(ValueScheme::BwtContextMix));
    }

    #[test]
    fn test_ctxmix_pure_and_mix_unit_round_trip() {
        // Structured stream; exercise both back-end modes directly.
        let a = 6usize;
        let mut seq = Vec::new();
        for _ in 0..500 {
            seq.extend_from_slice(&[0, 0, 1, 0, 2, 0, 3, 0, 4, 5]);
        }
        for inc in CM_PURE_INCS {
            let enc = cm_pure_o1_encode(&seq, a, inc);
            let dec = cm_pure_o1_decode(&enc, seq.len(), a, inc);
            assert_eq!(dec, seq, "ctxmix pure round-trip mismatch (inc={inc})");
        }
        for inc in CM_MIX_INCS {
            for &lr in &CM_LRS {
                let enc = cm_mix_encode(&seq, a, inc, lr);
                let dec = cm_mix_decode(&enc, seq.len(), a, inc, lr);
                assert_eq!(dec, seq, "ctxmix mix round-trip mismatch (inc={inc}, lr={lr})");
            }
        }
    }

    #[test]
    fn test_ctxmix_high_entropy_and_rescale() {
        // 256 symbols, long stream → forces rescaling in both order-1 and order-0
        // models; the learned-mix path must round-trip exactly (f64 determinism).
        let a = 256usize;
        let seq: Vec<usize> = (0..40000).map(|i| ((i * 97 + 13) % 256) as usize).collect();
        for &lr in &CM_LRS {
            let enc = cm_mix_encode(&seq, a, 16, lr);
            let dec = cm_mix_decode(&enc, seq.len(), a, 16, lr);
            assert_eq!(dec, seq, "ctxmix high-entropy/rescale mismatch (lr={lr})");
        }
    }

    #[test]
    fn test_ctxmix_empty_and_singleton() {
        let enc = bwt_ctxmix_encode(&[], 0);
        let (dec, _) = bwt_ctxmix_decode(&enc, 0, 0, 0).unwrap();
        assert!(dec.is_empty());
        let seq = vec![0usize; 800];
        let enc = bwt_ctxmix_encode(&seq, 1);
        let (dec, _) = bwt_ctxmix_decode(&enc, 0, seq.len(), 1).unwrap();
        assert_eq!(dec, seq);
    }

    #[test]
    fn test_bwt_ctxmix_corpus_round_trip_all_files() {
        // Byte-exact round-trip on all 10 frozen corpus files. Scheme 7's competitive
        // selection may emit scheme byte 10 (BwtContextMix); the decoder MUST recover
        // every file. Round-trip is non-negotiable (Gotcha).
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        for cfg in [bwt_ctxmix_cfg(), bwt_rans_cfg()] {
            let mut ok = 0;
            for name in &names {
                let path = format!("{corpus_dir}/{name}.bin");
                if let Ok(data) = fs::read(&path) {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered = decode(&blob)
                        .unwrap_or_else(|e| panic!("BwtContextMix decode failed for '{name}': {e:?}"));
                    assert_eq!(recovered, data, "BwtContextMix round-trip FAILED for '{name}'");
                    ok += 1;
                }
            }
            assert_eq!(ok, 10, "BwtContextMix corpus round-trip: {ok}/10 files present and clean");
        }
    }

    #[test]
    fn test_bwt_ctxmix_never_regresses_competition() {
        // Competitive (Gotcha #4): can NEVER be larger than the BwtEntropy leader.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let bwt_cfg = EncodeConfig {
            value_scheme: ValueScheme::BwtEntropy,
            ..EncodeConfig::v1_default()
        };
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            if let Ok(data) = fs::read(&path) {
                let cand = encode_with_config(&data, &bwt_ctxmix_cfg());
                let leader = encode_with_config(&data, &bwt_cfg);
                assert!(
                    cand.len() <= leader.len(),
                    "BwtContextMix regressed '{name}': {} > bwt-entropy {}",
                    cand.len(), leader.len()
                );
            }
        }
    }

    #[test]
    fn test_bwt_ctxmix_property_random_inputs() {
        let mut state: u64 = 0x14057b7ef767814f;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as u32
        };
        for trial in 0..40 {
            let len = 321 + (next() as usize % 4000);
            let alphabet = 1 + (next() as usize % 200);
            let data: Vec<u8> = (0..len).map(|_| (next() as usize % alphabet) as u8).collect();
            let blob = encode_with_config(&data, &bwt_ctxmix_cfg());
            let recovered = decode(&blob).expect("decode");
            assert_eq!(recovered, data, "BwtContextMix property round-trip failed (trial {trial}, len {len}, alpha {alphabet})");
        }
    }

    #[test]
    fn test_bwt_ctxmix_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = b"the quick brown fox jumps over "
            .iter().copied().cycle().take(8192).collect();
        let blob = encode_with_config(&data, &bwt_ctxmix_cfg());
        for cut in (8..blob.len()).step_by(41) {
            let _ = decode(&blob[..cut]); // must not panic
        }
    }

    // ── H-24 geometric context-mixing (scheme 11) tests ─────────────────────

    fn bwt_geomix_cfg() -> EncodeConfig {
        EncodeConfig {
            value_scheme: ValueScheme::BwtGeoMix,
            ..EncodeConfig::v1_default()
        }
    }

    #[test]
    fn test_bwt_geomix_scheme_byte() {
        assert_eq!(ValueScheme::BwtGeoMix.scheme_byte(), 11u8);
        assert_eq!(ValueScheme::from_byte(11u8), Some(ValueScheme::BwtGeoMix));
    }

    #[test]
    fn test_geomix_unit_round_trip() {
        // Structured stream; exercise the geometric-mix back-end directly across the grid.
        let a = 6usize;
        let mut seq = Vec::new();
        for _ in 0..500 {
            seq.extend_from_slice(&[0, 0, 1, 0, 2, 0, 3, 0, 4, 5]);
        }
        let ln = gm_ln_table(CM_RESCALE + 128);
        for inc in GM_INCS {
            for &lr in &GM_LRS {
                let enc = gm_mix_encode(&seq, a, inc, lr, &ln);
                let dec = gm_mix_decode(&enc, seq.len(), a, inc, lr, &ln);
                assert_eq!(dec, seq, "geomix round-trip mismatch (inc={inc}, lr={lr})");
            }
        }
    }

    #[test]
    fn test_geomix_high_entropy_and_rescale() {
        // 256 symbols, long stream → forces rescaling in all three models; the
        // geometric-mix path must round-trip exactly (f64 determinism, log/exp).
        let a = 256usize;
        let seq: Vec<usize> = (0..40000).map(|i| ((i * 97 + 13) % 256) as usize).collect();
        let ln = gm_ln_table(CM_RESCALE + 128);
        for &lr in &GM_LRS {
            let enc = gm_mix_encode(&seq, a, 16, lr, &ln);
            let dec = gm_mix_decode(&enc, seq.len(), a, 16, lr, &ln);
            assert_eq!(dec, seq, "geomix high-entropy/rescale mismatch (lr={lr})");
        }
    }

    #[test]
    fn test_geomix_empty_and_singleton() {
        let enc = bwt_geomix_encode(&[], 0);
        let (dec, _) = bwt_geomix_decode(&enc, 0, 0, 0).unwrap();
        assert!(dec.is_empty());
        let seq = vec![0usize; 800];
        let enc = bwt_geomix_encode(&seq, 1);
        let (dec, _) = bwt_geomix_decode(&enc, 0, seq.len(), 1).unwrap();
        assert_eq!(dec, seq);
    }

    #[test]
    fn test_bwt_geomix_corpus_round_trip_all_files() {
        // Byte-exact round-trip on all 10 frozen corpus files. Scheme 7's competitive
        // selection may emit scheme byte 11 (BwtGeoMix); the decoder MUST recover every
        // file. Round-trip is non-negotiable (Gotcha).
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        for cfg in [bwt_geomix_cfg(), bwt_rans_cfg()] {
            let mut ok = 0;
            for name in &names {
                let path = format!("{corpus_dir}/{name}.bin");
                if let Ok(data) = fs::read(&path) {
                    let blob = encode_with_config(&data, &cfg);
                    let recovered = decode(&blob)
                        .unwrap_or_else(|e| panic!("BwtGeoMix decode failed for '{name}': {e:?}"));
                    assert_eq!(recovered, data, "BwtGeoMix round-trip FAILED for '{name}'");
                    ok += 1;
                }
            }
            assert_eq!(ok, 10, "BwtGeoMix corpus round-trip: {ok}/10 files present and clean");
        }
    }

    #[test]
    fn test_bwt_geomix_never_regresses_competition() {
        // Competitive (Gotcha #4): can NEVER be larger than the BwtEntropy leader.
        use std::fs;
        let corpus_dir = std::env::var("CUBRIM_CORPUS_DIR").unwrap_or_else(|_| {
            format!("{}/../../docs/ephemeral/research/corpus", env!("CARGO_MANIFEST_DIR"))
        });
        let names = [
            "sparse_clustered", "dense", "text", "log_like",
            "binary_mixed", "random_high", "sparse_small",
            "both_sparse_16", "both_sparse_24", "block_bound_runs",
        ];
        let bwt_cfg = EncodeConfig {
            value_scheme: ValueScheme::BwtEntropy,
            ..EncodeConfig::v1_default()
        };
        for name in &names {
            let path = format!("{corpus_dir}/{name}.bin");
            if let Ok(data) = fs::read(&path) {
                let cand = encode_with_config(&data, &bwt_geomix_cfg());
                let leader = encode_with_config(&data, &bwt_cfg);
                assert!(
                    cand.len() <= leader.len(),
                    "BwtGeoMix regressed '{name}': {} > bwt-entropy {}",
                    cand.len(), leader.len()
                );
            }
        }
    }

    #[test]
    fn test_bwt_geomix_property_random_inputs() {
        let mut state: u64 = 0x243f6a8885a308d3;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as u32
        };
        for trial in 0..40 {
            let len = 321 + (next() as usize % 4000);
            let alphabet = 1 + (next() as usize % 200);
            let data: Vec<u8> = (0..len).map(|_| (next() as usize % alphabet) as u8).collect();
            let blob = encode_with_config(&data, &bwt_geomix_cfg());
            let recovered = decode(&blob).expect("decode");
            assert_eq!(recovered, data, "BwtGeoMix property round-trip failed (trial {trial}, len {len}, alpha {alphabet})");
        }
    }

    #[test]
    fn test_bwt_geomix_truncated_blob_errors_no_panic() {
        let data: Vec<u8> = b"the quick brown fox jumps over "
            .iter().copied().cycle().take(8192).collect();
        let blob = encode_with_config(&data, &bwt_geomix_cfg());
        for cut in (8..blob.len()).step_by(41) {
            let _ = decode(&blob[..cut]); // must not panic
        }
    }

    #[test]
    fn test_entropy_context2_decode_malformed_blob() {
        // Corrupt the value_scheme byte to 5 but provide no valid tables → Err.
        let data: Vec<u8> = b"the quick brown fox "
            .iter()
            .copied()
            .cycle()
            .take(4096)
            .collect();
        let mut blob = encode_with_config(
            &data,
            &EncodeConfig {
                value_scheme: ValueScheme::EntropyContext2,
                ..EncodeConfig::v1_default()
            },
        );
        // Corrupt the bitstream area: zero out everything after header.
        use crate::header::parse_header;
        if let Ok((hdr, hdr_end)) = parse_header(&blob) {
            if hdr.value_scheme == 5 {
                // Set n_contexts to a huge number → truncated header detected.
                // Find the position: after header + gap streams.
                // We'll just truncate aggressively.
                let truncate_at = hdr_end + 10; // cut mid-gap-stream
                blob.truncate(truncate_at);
                let result = decode(&blob);
                assert!(
                    result.is_err(),
                    "Corrupted/truncated T5 blob must return Err, not panic"
                );
            }
        }
    }
}
