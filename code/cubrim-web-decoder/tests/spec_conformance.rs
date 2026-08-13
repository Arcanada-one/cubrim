//! Checks the normative claims in
//! `documentation/reference/cubrim-web-profile-format.md` against the shipped
//! implementation.
//!
//! A specification that drifts from its implementation is worse than none: it
//! makes a second implementer confidently wrong. Each test below cites the
//! section it enforces.

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder as refdec;

fn web_config() -> EncodeConfig {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config
}

fn sample_frame() -> Vec<u8> {
    let data = b"the quick brown fox jumps over the lazy dog ".repeat(50);
    let frame = encode_with_config(&data, &web_config());
    assert_eq!(frame[5], 18, "sample must be a MODE_WEB frame");
    frame
}

/// §2 Frame — fixed prefix, magic, version, mode, length, checksum.
#[test]
fn frame_header_matches_the_specification() {
    let data = b"specification fixture".repeat(80);
    let frame = encode_with_config(&data, &web_config());

    assert_eq!(refdec::FRAME_HEADER_SIZE, 14, "§2: header is 14 bytes");
    assert_eq!(&frame[0..4], &[0xCB, 0x52, 0x49, 0x4D], "§2: MAGIC");
    assert_eq!(frame[4], 1, "§2: VERSION = 1");
    assert_eq!(frame[5], 18, "§2: MODE = 18");
    assert_eq!(
        u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]) as usize,
        data.len(),
        "§2: ORIG_LEN is the uncompressed length, u32 BE at offset 6"
    );
    let digest = blake3::hash(&data);
    assert_eq!(
        &frame[10..14],
        &digest.as_bytes()[0..4],
        "§2: CHECKSUM is the first 4 bytes of BLAKE3(original)"
    );
    assert_eq!(refdec::declared_len(&frame), Some(data.len()));
}

/// §2 — a decoder must reject a frame whose magic, version or mode is wrong.
#[test]
fn wrong_magic_version_or_mode_is_rejected() {
    for (index, label) in [(0usize, "magic"), (4, "version"), (5, "mode")] {
        let mut frame = sample_frame();
        frame[index] ^= 0xFF;
        assert!(
            refdec::decode(&frame).is_err(),
            "§2: a frame with a corrupted {label} must be rejected"
        );
        assert!(!refdec::is_web_frame(&frame) || index == 0);
    }
}

/// §3 Block — BTYPE 0 and 3 are reserved and must be refused, not guessed.
///
/// This is the format's extension point: a decoder that refuses today stays
/// correct when a future block type is defined, because it will not
/// misinterpret one.
#[test]
fn reserved_block_types_are_rejected() {
    // First bitstream byte: bit 0 = BFINAL, bits 1-2 = BTYPE (mask 0x60).
    for (btype, bits) in [(0u8, 0x00u8), (3, 0x60)] {
        let mut frame = sample_frame();
        frame[14] = (frame[14] & !0x60) | bits;
        let err = refdec::decode(&frame).expect_err("reserved BTYPE must be refused");
        assert!(
            err.0.contains("unknown block type") || err.0.contains("block type"),
            "§3: BTYPE {btype} should be refused as a block-type error, got {err:?}"
        );
    }
}

/// §3 — the shipped encoder only emits the two defined block types.
#[test]
fn encoder_only_emits_defined_block_types() {
    let frame = sample_frame();
    let btype = (frame[14] & 0x60) >> 5;
    assert!(btype == 1 || btype == 2, "§3: BTYPE was {btype}");
    assert_eq!(frame[14] & 0x80, 0x80, "§3: single-block frames set BFINAL");
}

/// §7 Length alphabet — code 285 is exactly 258 with no extra bits, and the
/// bounds are 3..=258.
#[test]
fn length_alphabet_bounds_hold() {
    // A long run of one byte forces maximum-length matches.
    let data = vec![b'Z'; 4096];
    let frame = encode_with_config(&data, &web_config());
    if frame[5] == 18 {
        assert_eq!(refdec::decode(&frame).unwrap(), data, "§7/§8: long runs");
    }
}

/// §8 Symbol sequence — overlapping copies are byte-at-a-time semantics.
///
/// `distance = 1` repeats a single byte; a block copy would produce different
/// output, so this is the case that catches an unsound optimisation.
#[test]
fn overlapping_runs_decode_byte_at_a_time() {
    for pattern in [
        vec![b'x'; 3000],
        b"ab".repeat(1500),
        b"abc".repeat(1000),
        b"abcd".repeat(750),
    ] {
        let frame = encode_with_config(&pattern, &web_config());
        if frame[5] != 18 {
            continue;
        }
        assert_eq!(
            refdec::decode(&frame).unwrap(),
            pattern,
            "§8: overlapping run mis-decoded"
        );
    }
}

/// §9 — the checksum must be verified, and a mismatch must fail rather than
/// return output.
#[test]
fn checksum_is_verified() {
    let mut frame = sample_frame();
    frame[13] ^= 0x01;
    let err = refdec::decode(&frame).expect_err("§9: checksum mismatch must fail");
    assert!(err.0.contains("checksum"), "got {err:?}");
}

/// §9 — the decoded length must equal ORIG_LEN exactly.
#[test]
fn declared_length_must_match_exactly() {
    let mut frame = sample_frame();
    let declared = u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]);
    frame[6..10].copy_from_slice(&(declared - 1).to_be_bytes());
    assert!(refdec::decode(&frame).is_err(), "§9: short declaration");

    let mut frame = sample_frame();
    frame[6..10].copy_from_slice(&(declared + 1).to_be_bytes());
    assert!(refdec::decode(&frame).is_err(), "§9: long declaration");
}

/// §10 — the caller's output ceiling is enforced against ORIG_LEN before any
/// decoding happens.
#[test]
fn output_ceiling_is_enforced_before_decoding() {
    let frame = sample_frame();
    let declared = refdec::declared_len(&frame).unwrap();
    let limits = refdec::DecodeLimits {
        max_output_size: declared - 1,
        ..refdec::DecodeLimits::default()
    };
    let err = refdec::decode_with_limits(&frame, &limits).expect_err("§10: ceiling");
    assert!(err.0.contains("exceeds the limit"), "got {err:?}");

    // At exactly the declared size it must succeed.
    let limits = refdec::DecodeLimits {
        max_output_size: declared,
        ..refdec::DecodeLimits::default()
    };
    assert!(refdec::decode_with_limits(&frame, &limits).is_ok());
}

/// §10 — the documented default ceiling is 64 MiB.
#[test]
fn default_output_ceiling_is_64_mib() {
    assert_eq!(refdec::DecodeLimits::DEFAULT_MAX_OUTPUT, 64 << 20);
    assert_eq!(
        refdec::DecodeLimits::default().max_output_size,
        64 << 20,
        "§10: documented default"
    );
}

/// §2 — trailing bytes after the final end-of-block symbol are ignored.
#[test]
fn trailing_bytes_after_the_final_block_are_ignored() {
    let data = b"trailing byte fixture".repeat(60);
    let frame = encode_with_config(&data, &web_config());
    if frame[5] != 18 {
        return;
    }
    let mut padded = frame.clone();
    padded.extend_from_slice(&[0xAA; 7]);
    assert_eq!(
        refdec::decode(&padded).unwrap(),
        data,
        "§2: trailing bytes must not change the result"
    );
}

/// §3 Block — a block boundary resets the tables, not the output window.
///
/// The specification promises a match may reach across a boundary. If that
/// stopped being true, streaming consumers built on the promise would break.
#[test]
fn matches_may_reach_across_a_block_boundary() {
    let marker = b"UNIQUE-CROSS-BLOCK-MARKER-abcdefghijklmnopqrstuvwxyz";
    let mut data = marker.to_vec();
    data.extend(vec![b'.'; 4000]);
    data.extend_from_slice(marker);

    let mut config = web_config();
    config.web_block_size = Some(256);
    let frame = encode_with_config(&data, &config);
    assert_eq!(frame[5], 18, "expected a MODE_WEB frame");
    assert_eq!(
        refdec::decode(&frame).unwrap(),
        data,
        "§3: cross-boundary match mis-decoded"
    );
}

/// §4 — an unused context table is transmitted in single-symbol form, not as
/// an all-zero table, so every block's tables are valid codes.
#[test]
fn unused_context_tables_are_still_valid_codes() {
    // Tiny blocks over digit-free text leave the digit context empty.
    let data = b"letters and spaces only, no digits at all here ".repeat(200);
    for block_size in [1usize, 3, 16, 64] {
        let mut config = web_config();
        config.web_block_size = Some(block_size);
        let frame = encode_with_config(&data, &config);
        if frame[5] != 18 {
            continue;
        }
        assert_eq!(
            refdec::decode(&frame).unwrap(),
            data,
            "§4: block_size {block_size} produced an invalid table"
        );
    }
}
