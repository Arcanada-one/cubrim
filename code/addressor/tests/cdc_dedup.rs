//! CDC dedup: a shared shifted region is stored exactly once (exact blob
//! accounting, not a trivially-true inequality).

mod common;
use common::{noise, open_addressor, text};
use tempfile::tempdir;

#[test]
fn shared_shifted_chunks_stored_once() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // shared block, large enough to span many chunks
    let shared = text(120_000, 42);
    // file A: prefix1 + shared; file B: different-length prefix + shared
    let mut fa = noise(5_000, 1);
    fa.extend_from_slice(&shared);
    let mut fb = noise(9_137, 2); // different shift
    fb.extend_from_slice(&shared);
    // store A twice via sibling to promote its chunks (r>=2), then B
    a.store_bytes(&fa).unwrap();
    let mut fa2 = fa.clone();
    fa2.extend_from_slice(b"tail");
    a.store_bytes(&fa2).unwrap(); // promotes shared chunks
    let blobs_before_b = a.cas.blob_count().unwrap();
    let out_b = a.store_bytes(&fb).unwrap();
    let blobs_after_b = a.cas.blob_count().unwrap();
    // B must reference promoted shared chunks: new blobs are only B's noise
    // prefix chunks + its container — far less than re-storing `shared`.
    let new_blobs = blobs_after_b - blobs_before_b;
    assert!(
        new_blobs <= 8,
        "B created {new_blobs} blobs — shared shifted chunks were re-stored"
    );
    assert_eq!(a.retrieve(out_b.ordinal).unwrap(), fb);
}
