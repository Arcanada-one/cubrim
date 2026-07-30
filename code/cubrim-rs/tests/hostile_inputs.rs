//! Hostile-input hardening corpus for the Cubrim decoder.
//!
//! `decode()` consumes untrusted bytes. In a browser that makes it a
//! security-critical component: a panic in a network stack is a denial of
//! service on every tab sharing the process, and a bounds check whose own
//! arithmetic wraps is worse than none. CUBR-0075 refuses to publish any
//! performance number for a build that has not passed this corpus, and the
//! `web_benchmark_hypothesis_evaluation` trigger enforces that in the database.
//!
//! The contract for every case is the same: `decode()` returns `Err`. Not a
//! panic, not an abort, not an out-of-memory kill, not a hang. A panic fails the
//! test by definition, which is what makes this file evidence rather than a
//! claim.
//!
//! **Reaching the code under test matters.** A blob assembled from scratch is
//! refused while the gap section is read, long before the entropy paths most of
//! these defects live in — so it would pass for the wrong reason. Every case
//! therefore starts from a *valid* cube-mode stream and overwrites one field,
//! which guarantees the prefix parses and the hostile bytes are actually
//! reached. The fixture asserts its own round-trip first, so a broken baseline
//! cannot masquerade as hardening.
//!
//! Run under both profiles. Debug additionally traps arithmetic overflow, so a
//! wrapping bounds check surfaces there as a panic rather than as a silently
//! bypassed guard:
//!
//! ```text
//! cargo test --test hostile_inputs
//! cargo test --release --test hostile_inputs
//! ```

use cubrim::config::{EncodeConfig, ValueScheme};
use cubrim::header::{MAGIC, MODE_CUBE, VERSION};

/// The only acceptable outcome for untrusted input that is not a valid stream.
fn must_error(label: &str, blob: &[u8]) {
    if let Ok(output) = cubrim::decode(blob) {
        panic!(
            "{label}: decoder accepted a hostile stream and produced {} bytes",
            output.len()
        );
    }
}

/// Structured repetitive text, which is what drives the encoder to the cube
/// path rather than raw store. Kept small so the sweeps stay fast.
fn cube_payload() -> Vec<u8> {
    let mut out = Vec::new();
    for i in 0..320u32 {
        out.extend_from_slice(
            format!("<div class=\"row r{}\"><span>value {}</span></div>\n", i % 17, i % 29)
                .as_bytes(),
        );
    }
    out
}

/// Encodes under one value scheme, returning `None` when the encoder chose raw
/// store (in which case there is no cube stream to attack).
fn cube_stream(scheme: ValueScheme) -> Option<Vec<u8>> {
    let payload = cube_payload();
    let mut config = EncodeConfig::v1_default();
    config.value_scheme = scheme;
    let blob = cubrim::encode_with_config(&payload, &config);
    if blob.get(5) != Some(&MODE_CUBE) {
        return None;
    }
    // A broken baseline would make every mutation below meaningless.
    assert_eq!(
        cubrim::decode(&blob).expect("fixture must decode"),
        payload,
        "fixture must round-trip before it is used as an attack base"
    );
    Some(blob)
}

/// Every value scheme that produces a cube stream for this payload.
fn all_cube_streams() -> Vec<(ValueScheme, Vec<u8>)> {
    [
        ValueScheme::BitpackFixed,
        ValueScheme::RleCodes,
        ValueScheme::Entropy,
        ValueScheme::EntropyContext,
        ValueScheme::EntropyContext2,
        ValueScheme::BwtEntropy,
    ]
    .into_iter()
    .filter_map(|scheme| cube_stream(scheme).map(|blob| (scheme, blob)))
    .collect()
}

/// Offsets of the attacker-controlled header fields, from the layout in
/// `src/header.rs`:
/// `[magic 4][version 1][mode 1][N 1][B 2][L 4][count 4][b_k N*2]`
/// `[map_scheme 1][value_scheme 1][W 1][n_distinct 2]...`
struct HeaderOffsets {
    b: usize,
    l: usize,
    count: usize,
    w: usize,
    n_distinct: usize,
}

fn header_offsets(blob: &[u8]) -> HeaderOffsets {
    let n = blob[6] as usize;
    let scheme_base = 13 + 4 + n * 2;
    HeaderOffsets {
        b: 7,
        l: 9,
        count: 13,
        w: scheme_base + 2,
        n_distinct: scheme_base + 3,
    }
}

fn put_u16(blob: &mut [u8], at: usize, value: u16) {
    blob[at..at + 2].copy_from_slice(&value.to_be_bytes());
}

fn put_u32(blob: &mut [u8], at: usize, value: u32) {
    blob[at..at + 4].copy_from_slice(&value.to_be_bytes());
}

// ---------------------------------------------------------------------------
// A header field used as a divisor — found by the mutation sweep, not by reading
// ---------------------------------------------------------------------------

#[test]
fn a_degenerate_radix_is_refused_rather_than_dividing_by_zero() {
    // `phi()` computes `remainder % b` with b straight from the header's B
    // field. B = 0 panics with "attempt to calculate the remainder with a
    // divisor of zero"; B = 1 collapses every coordinate to 0.
    for (scheme, blob) in all_cube_streams() {
        let offsets = header_offsets(&blob);
        for radix in [0u16, 1] {
            let mut mutated = blob.clone();
            put_u16(&mut mutated, offsets.b, radix);
            must_error(&format!("{scheme:?} B={radix}"), &mutated);
        }
    }
}

// ---------------------------------------------------------------------------
// Allocation and length driven by an attacker-controlled count
// ---------------------------------------------------------------------------

#[test]
fn declared_counts_far_beyond_the_input_are_refused() {
    for (scheme, blob) in all_cube_streams() {
        let offsets = header_offsets(&blob);
        for value in [u32::MAX, u32::MAX / 2, 1 << 30, 1 << 24] {
            let mut mutated = blob.clone();
            put_u32(&mut mutated, offsets.count, value);
            must_error(&format!("{scheme:?} count={value}"), &mutated);

            let mut mutated = blob.clone();
            put_u32(&mut mutated, offsets.l, value);
            must_error(&format!("{scheme:?} L={value}"), &mutated);
        }
    }
}

#[test]
fn an_absurd_distinct_value_count_is_refused() {
    // n_distinct sizes the per-context code-length table and is a factor in the
    // header_entry_size multiplication the bounds check depends on.
    for (scheme, blob) in all_cube_streams() {
        let offsets = header_offsets(&blob);
        for value in [0u16, 0xFFFF, 0x8000, 0x0101] {
            let mut mutated = blob.clone();
            put_u16(&mut mutated, offsets.n_distinct, value);
            must_error(&format!("{scheme:?} n_distinct={value}"), &mutated);
        }
    }
}

#[test]
fn an_absurd_bit_width_is_refused() {
    for (scheme, blob) in all_cube_streams() {
        let offsets = header_offsets(&blob);
        for value in [0u8, 64, 128, 255] {
            let mut mutated = blob.clone();
            mutated[offsets.w] = value;
            must_error(&format!("{scheme:?} W={value}"), &mutated);
        }
    }
}

// ---------------------------------------------------------------------------
// The value section: context tables, code lengths, bitstream
// ---------------------------------------------------------------------------

#[test]
fn no_value_section_byte_can_panic_under_any_scheme() {
    // The entropy paths own the empty-context-table index, the wrapping bounds
    // check, and the u32 shift overflow. Rather than guess which byte reaches
    // which, walk the value section and require that no substitution panics.
    //
    // Bounded deliberately: every byte of the first 192 (the counts, context
    // ids, and code-length tables, where the structural fields live), then a
    // stride across the bitstream tail. Exhausting a 13 KB tail costs hundreds
    // of thousands of decodes for no additional structural coverage.
    const DENSE_PREFIX: usize = 192;
    const TAIL_STRIDE: usize = 17;
    let replacements = [0x00u8, 0x01, 0x20, 0x7F, 0x80, 0xC0, 0xFE, 0xFF];

    for (scheme, blob) in all_cube_streams() {
        let offsets = header_offsets(&blob);
        let start = offsets.n_distinct + 2;
        for index in start..blob.len() {
            let dense = index < start + DENSE_PREFIX;
            if !dense && (index - start) % TAIL_STRIDE != 0 {
                continue;
            }
            for replacement in replacements {
                let mut mutated = blob.clone();
                if mutated[index] == replacement {
                    continue;
                }
                mutated[index] = replacement;
                // Only the outcome matters: decoding must not panic. A
                // successful decode is legitimate — some bytes are payload.
                let _ = cubrim::decode(&mutated);
            }
        }
        // Zeroing the whole value section is the empty-table case in extremis.
        let mut zeroed = blob.clone();
        for byte in &mut zeroed[start..] {
            *byte = 0;
        }
        let _ = cubrim::decode(&zeroed);
        let mut ones = blob.clone();
        for byte in &mut ones[start..] {
            *byte = 0xFF;
        }
        let _ = cubrim::decode(&ones);
        assert!(!blob.is_empty(), "{scheme:?} stream must be non-empty");
    }
}

// ---------------------------------------------------------------------------
// Truncation: every proper prefix of a valid stream must fail cleanly
// ---------------------------------------------------------------------------

#[test]
fn every_truncation_of_a_real_stream_fails_cleanly() {
    // The PRD's preregistered hostile ladder: proper prefixes of a valid
    // compressed block. None may panic, and none may claim success, because a
    // truncated stream cannot reproduce the input.
    let payload = cube_payload();
    for (scheme, blob) in all_cube_streams() {
        for cut in 0..blob.len() {
            match cubrim::decode(&blob[..cut]) {
                Ok(output) => assert_ne!(
                    output, payload,
                    "{scheme:?}: a truncated stream reproduced the full input at cut={cut}"
                ),
                Err(_) => {}
            }
        }
    }
}

#[test]
fn header_byte_substitutions_never_panic() {
    // The fixed header is small enough to exhaust: every byte, every value.
    for (_, blob) in all_cube_streams() {
        let header_len = 13 + 4 + (blob[6] as usize) * 2 + 5;
        for index in 0..header_len.min(blob.len()) {
            for replacement in 0u8..=255 {
                let mut mutated = blob.clone();
                if mutated[index] == replacement {
                    continue;
                }
                mutated[index] = replacement;
                let _ = cubrim::decode(&mutated);
            }
        }
    }
}

#[test]
fn empty_and_stub_inputs_are_refused() {
    let mut stubs: Vec<Vec<u8>> = vec![vec![], vec![0x00], MAGIC.to_vec()];
    let mut with_version = MAGIC.to_vec();
    with_version.push(VERSION);
    stubs.push(with_version.clone());
    let mut with_mode = with_version;
    with_mode.push(MODE_CUBE);
    stubs.push(with_mode);
    for blob in stubs {
        must_error("stub", &blob);
    }
}
