//! Section-first lookup economics (AH-20): the mechanism test — hits from a
//! project's own section resolve in-section; the measured 80/20 profile is a
//! property of the pinned corpus generator, re-measured on the real fleet at
//! bench stage.

mod common;
use common::{open_addressor, text};
use tempfile::tempdir;

#[test]
fn own_section_hits_dominate_on_sectioned_corpus() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // per-section hot bodies: sections 0..6, each with its own shared body
    for sec in 0..6u8 {
        let body = text(60_000, 100 + sec as u64);
        for i in 0..3u64 {
            let mut f = body.clone();
            f.extend_from_slice(format!("-s{sec}-{i}").as_bytes());
            a.store_bytes_ctx(&f, sec, Some("data.log")).unwrap();
        }
    }
    // one cross-section body shared between sections 0 and 1 (20%-ish share)
    let cross = text(60_000, 999);
    for (i, sec) in [(0u64, 0u8), (1, 1), (2, 0), (3, 1)] {
        let mut f = cross.clone();
        f.extend_from_slice(format!("-x{i}").as_bytes());
        a.store_bytes_ctx(&f, sec, Some("data.log")).unwrap();
    }
    let rate = a.matrix.section_hit_rate();
    assert!(
        rate >= 0.8,
        "own-section hit rate {rate:.3} < 0.80 on sectioned corpus"
    );
    let sizes = a.matrix.section_sizes();
    let total: u64 = sizes.values().sum();
    let max_section = sizes.values().max().copied().unwrap_or(0);
    assert!(
        (max_section as f64) / (total as f64) <= 0.5,
        "one section holds >50% of the matrix"
    );
}
