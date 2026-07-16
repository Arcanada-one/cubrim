//! Byte-exact round-trip across size scales and content classes (fixture
//! scale; the pinned-corpus sweep runs via scripts/addr-roundtrip.sh).

mod common;
use common::{noise, open_addressor, text};
use tempfile::tempdir;

#[test]
fn roundtrip_across_classes_and_sizes() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    let mut inputs: Vec<Vec<u8>> = Vec::new();
    // sizes from 1 B up, text (compressible) and noise (incompressible)
    for (i, n) in [1usize, 17, 1000, 8192, 70_000, 200_000].iter().enumerate() {
        inputs.push(text(*n, 100 + i as u64));
        inputs.push(noise(*n, 200 + i as u64));
    }
    inputs.push(Vec::new()); // empty file
    let mut refs = Vec::new();
    for data in &inputs {
        let out = a.store_bytes(data).unwrap();
        refs.push(out.ordinal);
    }
    for (data, ord) in inputs.iter().zip(refs.iter()) {
        assert_eq!(&a.retrieve(*ord).unwrap(), data, "roundtrip diff for ordinal {ord}");
    }
}

#[test]
fn roundtrip_survives_catalog_reopen() {
    let dir = tempdir().unwrap();
    let data = text(50_000, 7);
    let ord;
    {
        let mut a = open_addressor(dir.path());
        ord = a.store_bytes(&data).unwrap().ordinal;
    }
    let a = open_addressor(dir.path());
    assert_eq!(a.retrieve(ord).unwrap(), data);
}

#[test]
fn chunk_equal_to_stored_whole_file_still_roundtrips() {
    // HIGH regression: a later file whose CDC chunk equals an earlier whole
    // stored file must not bind that chunk to the file's container ordinal
    // (which the decoder rejects). Round-trip must survive.
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // small file A, stored whole (becomes a container entry)
    let small = text(6000, 501);
    a.store_bytes(&small).unwrap();
    // build B so that A's exact bytes appear as an aligned CDC chunk, plus
    // enough shared structure to cross the threshold
    let donor = text(120_000, 502);
    a.store_bytes(&donor).unwrap();
    let mut d2 = donor.clone();
    d2.extend_from_slice(b"-sib");
    a.store_bytes(&d2).unwrap();
    let mut b = donor.clone();
    b.extend_from_slice(&small); // A's bytes embedded
    b.extend_from_slice(b"-tail-b");
    let out = a.store_bytes(&b).unwrap();
    assert_eq!(a.retrieve(out.ordinal).unwrap(), b, "container-hit round-trip broke");
}
