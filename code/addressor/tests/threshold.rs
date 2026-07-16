//! DUP_THRESHOLD step behaviour, constructed against the exported constant
//! (not a hardcoded 10%): points T-5pp, T-1pp, T, T+1pp, T+5pp, T+10pp.
//! Two-step assert: (1) the router's own measured dup-fraction lands within
//! ±0.2pp of the intended point; (2) the phase decision matches.

mod common;
use addressor::format::SchemeByte;
use addressor::router::{Addressor, DUP_THRESHOLD};
use common::{noise, text};
use tempfile::tempdir;

/// Builds an input whose dup-fraction against `donor`'s promoted chunks is
/// `target` within ±0.2pp. Construction: FIXED chunk-aligned donor prefix
/// (matched bytes are then constant — CDC junction effects touch at most the
/// last chunk and stay fixed once the junction position is fixed), while the
/// unique-noise TAIL length is tuned continuously: fraction = matched/total,
/// total is byte-granular, so any target is reachable exactly.
fn build_point(a: &Addressor, donor: &[u8], target: f64, salt: u64) -> Vec<u8> {
    if target <= 0.0 {
        // pure-noise point: dup-fraction 0 by construction
        let mut v = noise(200_000, 5_000 + salt);
        for (i, b) in v.iter_mut().enumerate() {
            *b ^= (i as u8).wrapping_mul(salt as u8 | 1);
        }
        return v;
    }
    let prefix_len = 60_000.min(donor.len()); // ~ chunk-aligned enough: fixed
    let make = |tail_len: usize| -> Vec<u8> {
        let mut v = donor[..prefix_len].to_vec();
        let mut tail = noise(tail_len, 5_000 + salt);
        for (i, b) in tail.iter_mut().enumerate() {
            *b ^= (i as u8).wrapping_mul(salt as u8 | 1);
        }
        v.extend_from_slice(&tail);
        v
    };
    // iterate: measure matched, solve total = matched/target, adjust tail
    let mut tail_len = 200_000usize;
    let mut best = make(tail_len);
    for _ in 0..6 {
        let f = a.dup_fraction(&best).unwrap();
        let err = (f - target).abs();
        if err <= 0.002 && f > 0.0 {
            return best;
        }
        let matched = f * best.len() as f64;
        if matched <= 0.0 {
            panic!("donor prefix produced zero matched bytes — promotion failed");
        }
        let total_needed = (matched / target).round() as usize;
        tail_len = total_needed.saturating_sub(prefix_len).max(1);
        best = make(tail_len);
    }
    let f = a.dup_fraction(&best).unwrap();
    assert!(
        (f - target).abs() <= 0.002,
        "could not construct point {target}: measured {f}"
    );
    best
}

#[test]
fn phase1_steps_exactly_on_dup_threshold() {
    let dir = tempdir().unwrap();
    let mut a = Addressor::open(dir.path()).unwrap();
    // donor chunks must be promoted (r>=2) to be matchable
    let donor = text(400_000, 9);
    a.store_bytes(&donor).unwrap();
    let mut d2 = donor.clone();
    d2.extend_from_slice(b"!sibling");
    a.store_bytes(&d2).unwrap();

    let t = DUP_THRESHOLD;
    let points: Vec<(f64, bool)> = vec![
        ((t - 0.05).max(0.0), false),
        ((t - 0.01).max(0.0), false),
        (t, true),
        (t + 0.01, true),
        (t + 0.05, true),
        (t + 0.10, true),
    ];
    for (i, (target, expect_phase1)) in points.iter().enumerate() {
        let input = build_point(&a, &donor, *target, 10 + i as u64);
        let measured = a.dup_fraction(&input).unwrap();
        assert!(
            (measured - target).abs() <= 0.002,
            "point {target}: measured {measured}"
        );
        let out = a.store_bytes(&input).unwrap();
        let phase1 = matches!(out.scheme, SchemeByte::CdcDedup | SchemeByte::CdcResidual);
        assert_eq!(
            phase1, *expect_phase1,
            "point {target} (measured {measured}): phase1={phase1}, expected {expect_phase1}"
        );
        assert_eq!(a.retrieve(out.ordinal).unwrap(), input);
    }
}
