//! Per-file regression-proof: the shipped container is never larger than the
//! pure Cubrim-1 container of the same bytes (structural, via competitive
//! selection). Corpus-level charged aggregate runs in the Phase 8 bench.

mod common;
use common::{noise, open_addressor, text};
use tempfile::tempdir;

fn pure_cubrim_container(data: &[u8]) -> usize {
    // the router's own candidate-B builder is public — use it directly so the
    // baseline in the test is byte-identical to the one selection ran against
    addressor::router::Addressor::pure_cubrim_container(data).len()
}

#[test]
fn container_never_exceeds_pure_cubrim() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // seed some dedup potential
    let donor = text(100_000, 77);
    a.store_bytes(&donor).unwrap();
    let mut d2 = donor.clone();
    d2.extend_from_slice(b"x");
    a.store_bytes(&d2).unwrap();
    for (i, data) in [
        text(500, 1),
        text(40_000, 2),
        noise(40_000, 3),
        {
            let mut v = donor[..60_000].to_vec();
            v.extend_from_slice(&noise(20_000, 4));
            v
        },
        text(220_000, 5),
    ]
    .iter()
    .enumerate()
    {
        let pure = pure_cubrim_container(data);
        let out = a.store_bytes(data).unwrap();
        assert!(
            out.container_len <= pure,
            "case {i}: router {} > pure {}",
            out.container_len,
            pure
        );
        assert_eq!(&a.retrieve(out.ordinal).unwrap(), data);
    }
}
