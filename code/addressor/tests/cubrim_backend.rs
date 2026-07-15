//! The residual backend on large inputs is the REAL Cubrim-1 codec: the
//! stored payload decodes with cubrim::codec::decode block-by-block, which a
//! zstd stand-in cannot fake. (The file-level zstd gate is a shell script:
//! scripts/addr-no-build-gate.sh / V-AC-6 command.)

mod common;
use addressor::format::{Container, SchemeByte};
use addressor::refs::varint_decode;
use common::{open_addressor, text};
use tempfile::tempdir;

#[test]
fn large_residual_container_is_genuine_cubrim_blocks() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    let data = text(300_000, 33); // low-dup large input → residual path
    let out = a.store_bytes(&data).unwrap();
    assert_eq!(out.scheme, SchemeByte::Cubrim1, "large residual must be cubrim");
    // dig the container out of CAS and verify each block decodes as cubrim
    let entry = a.catalog.entry(out.ordinal).unwrap().unwrap();
    let container = Container::from_bytes(&a.cas.get(&entry.blob).unwrap()).unwrap();
    assert_eq!(container.scheme, SchemeByte::Cubrim1);
    let mut pos = 0usize;
    let n = varint_decode(&container.payload, &mut pos).unwrap();
    assert!(n >= 4, "300KB must span several 64KiB cube blocks, got {n}");
    let mut rebuilt = Vec::new();
    for _ in 0..n {
        let len = varint_decode(&container.payload, &mut pos).unwrap() as usize;
        let block = &container.payload[pos..pos + len];
        rebuilt.extend_from_slice(
            &cubrim::codec::decode(block).expect("each block is a real cubrim container"),
        );
        pos += len;
    }
    assert_eq!(rebuilt, data);
}
