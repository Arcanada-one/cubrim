//! CUBR-0096 — sticky value-stream selection.
//!
//! Sticky selection reuses an anchor block's winning value scheme instead of running the
//! eight-way competition on every block. It is deliberately NOT byte-exact against the
//! full competition, so the properties worth testing are the ones that must hold anyway:
//!
//!   - the output still round-trips exactly (a faster encoder that loses bytes is a bug);
//!   - the output is a function of the input, not of thread scheduling;
//!   - the degenerate settings collapse onto the competitive path exactly;
//!   - it is off unless asked for, so `--max` cannot move.

use cubrim::{decode, encode_with_config, EncodeConfig, StickyParams};

/// Multi-block input: comfortably past the 64 KiB single-block ceiling so the chunked
/// path runs and there are real anchors and dependents.
///
/// Structured rather than random — random bytes are incompressible, take the raw-store
/// path, and never reach the value-stream competition the lever acts on.
fn multi_block_input() -> Vec<u8> {
    let mut data = Vec::with_capacity(400_000);
    let mut x: u32 = 0x1234_5678;
    while data.len() < 400_000 {
        x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
        // Runs of a small alphabet: compressible, and the run structure shifts along the
        // file so different blocks can genuinely prefer different schemes.
        let sym = (x >> 24) as u8 % 12;
        let run = 3 + ((x >> 8) % 40) as usize;
        for _ in 0..run {
            data.push(b'a' + sym);
        }
    }
    data.truncate(400_000);
    data
}

fn sticky_config(window: usize, recheck: usize) -> EncodeConfig {
    let mut cfg = EncodeConfig::v1_default();
    cfg.value_stream_sticky = Some(StickyParams::new(window, recheck));
    cfg
}

#[test]
fn sticky_round_trips_exactly() {
    let input = multi_block_input();
    for (w, k) in [(1usize, usize::MAX), (1, 8), (4, 16), (2, 3), (64, 64)] {
        let blob = encode_with_config(&input, &sticky_config(w, k));
        let restored = decode(&blob).expect("sticky blob must decode");
        assert_eq!(
            restored, input,
            "sticky(window={w}, recheck={k}) did not round-trip"
        );
    }
}

#[test]
fn sticky_output_is_deterministic() {
    // The anchor rule is index-derived and anchors are encoded in their own wave, so
    // repeated encodes of the same bytes must agree. If this ever fails, the sticky
    // choice has started depending on which worker thread got there first.
    let input = multi_block_input();
    let cfg = sticky_config(2, 5);
    let first = encode_with_config(&input, &cfg);
    for round in 0..4 {
        let again = encode_with_config(&input, &cfg);
        assert_eq!(
            first, again,
            "sticky output differed between encodes (round {round})"
        );
    }
}

#[test]
fn recheck_of_one_matches_the_full_competition_byte_for_byte() {
    // K=1 makes every block an anchor, so every block competes. That is the same work
    // the default path does, and it must produce the same bytes — this is the control
    // proving the sticky path itself does not perturb the encoding.
    let input = multi_block_input();
    let competitive = encode_with_config(&input, &EncodeConfig::v1_default());
    let every_block_anchors = encode_with_config(&input, &sticky_config(1, 1));
    assert_eq!(
        competitive, every_block_anchors,
        "sticky with recheck=1 must reproduce the competitive output exactly"
    );
}

#[test]
fn sticky_is_off_in_the_default_config() {
    // AC-2: no default behaviour change. The default config must not carry a sticky rule.
    assert_eq!(EncodeConfig::v1_default().value_stream_sticky, None);
}

#[test]
fn sticky_never_beats_the_competitive_minimum() {
    // Reusing a winner can only tie or lose against picking the per-block minimum.
    // An output SMALLER than the competition's would mean the competition is not
    // actually returning the minimum, which would be a defect in the default path.
    let input = multi_block_input();
    let competitive = encode_with_config(&input, &EncodeConfig::v1_default());
    let sticky = encode_with_config(&input, &sticky_config(1, usize::MAX));
    assert!(
        sticky.len() >= competitive.len(),
        "sticky ({} bytes) beat the competitive minimum ({} bytes) — the competition \
         is not returning the per-block minimum",
        sticky.len(),
        competitive.len()
    );
}
