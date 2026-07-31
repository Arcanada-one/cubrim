//! D-REQ-09 confirmation invariant at the integration level: a blob↔key
//! desync must yield Err(Integrity), never a silently-emitted reference.

mod common;
use addressor::error::AddressorError;
use common::{open_addressor, text};
use tempfile::tempdir;

#[test]
fn tampered_promoted_chunk_blocks_reference_emission() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    let base = text(150_000, 5);
    a.store_bytes(&base).unwrap();
    let mut sib = base.clone();
    sib.extend_from_slice(b"-s");
    a.store_bytes(&sib).unwrap(); // promotes shared chunks into catalog+CAS
    // tamper every stored chunk blob (skip containers is fine — tamper all)
    let mut tampered = 0;
    for l1 in std::fs::read_dir(a.cas.root()).unwrap() {
        let l1 = l1.unwrap().path();
        if !l1.is_dir() { continue; }
        for l2 in std::fs::read_dir(&l1).unwrap() {
            let l2 = l2.unwrap().path();
            if !l2.is_dir() { continue; }
            for f in std::fs::read_dir(&l2).unwrap() {
                let f = f.unwrap().path();
                std::fs::write(&f, b"poison").unwrap();
                tampered += 1;
            }
        }
    }
    assert!(tampered > 0);
    // a third sibling triggers lookups against tampered blobs
    let mut third = base.clone();
    third.extend_from_slice(b"-t3");
    match a.store_bytes(&third) {
        Err(AddressorError::Integrity(_)) => {}
        other => panic!("expected Err(Integrity) on tampered store, got {other:?}"),
    }
}
