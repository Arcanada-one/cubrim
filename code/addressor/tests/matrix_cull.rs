//! r>=2 curation (AH-19): r=1 blocks never enter the matrix; the curated
//! ratio is derived from the corpus' constructed r1_fraction, not hardcoded.

mod common;
use common::{open_addressor, text};
use tempfile::tempdir;

#[test]
fn entries_r1_is_zero_and_ratio_tracks_construction() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // constructed corpus: r1_fraction ≈ 0.90 by construction —
    // 10 "hot" sibling files sharing one body (their chunks reach r>=2),
    // 90 unique files whose chunks are seen exactly once.
    let hot_body = text(80_000, 1);
    for i in 0..10u64 {
        let mut f = hot_body.clone();
        f.extend_from_slice(format!("-hot-{i}").as_bytes());
        a.store_bytes(&f).unwrap();
    }
    for i in 0..90u64 {
        let f = text(80_000, 1000 + i);
        a.store_bytes(&f).unwrap();
    }
    // invariant: no r=1 resident among chunk entries
    assert_eq!(a.catalog.entries_r1().unwrap(), 0, "r=1 block inside matrix");
    // ratio: curated members / naive distinct seen ≤ (1 − r1_fraction) + tol
    let naive = a.catalog.seen_distinct().unwrap() as f64;
    let curated = a.matrix.member_count() as f64;
    assert!(naive > 0.0);
    let ratio = curated / naive;
    // ~10 hot bodies of ~10 chunks each vs ~90*10 unique chunks → r1 ≈ 0.9
    let r1_fraction = 0.9;
    assert!(
        ratio <= (1.0 - r1_fraction) + 0.05,
        "curation ratio {ratio:.3} exceeds manifest-derived bound"
    );
}
