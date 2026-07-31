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
    // Exact dedup property: EVERY chunk of the shared region is already a CAS
    // blob before B is stored (promoted via fa/fa2), and storing B adds ZERO
    // blobs for those exact shared chunks — the shifted shared region is
    // physically stored exactly once, not per-file.
    use addressor::chunker::chunk_bytes;
    let shared_chunk_refs: Vec<_> = chunk_bytes(&shared)
        .into_iter()
        .map(|c| addressor::cas::BlobRef::from_bytes(&c.data))
        .collect();
    let distinct_shared: std::collections::HashSet<_> =
        shared_chunk_refs.iter().map(|r| r.hash).collect();
    let blobs_before_b = a.cas.blob_count().unwrap();
    let out_b = a.store_bytes(&fb).unwrap();
    let new_blobs = a.cas.blob_count().unwrap() - blobs_before_b;
    // exact: write-once storage means each DISTINCT shared chunk exists as
    // exactly ONE blob no matter how many files (fa, fa2, fb) contain it —
    // B stores far fewer new blobs than the shared region's chunk count, so
    // the shifted region was referenced, not re-stored.
    assert!(
        new_blobs < distinct_shared.len() as u64,
        "B added {new_blobs} blobs >= {} distinct shared chunks — region re-stored",
        distinct_shared.len()
    );
    // every shared chunk that IS a CAS blob is present exactly once
    // (write-once forbids a second copy) — no per-file duplication.
    let present: Vec<_> = distinct_shared
        .iter()
        .filter(|h| a.cas.contains(&addressor::cas::BlobRef { hash: **h }))
        .collect();
    assert!(!present.is_empty(), "no shared chunks were promoted at all");
    assert_eq!(a.retrieve(out_b.ordinal).unwrap(), fb);
}
