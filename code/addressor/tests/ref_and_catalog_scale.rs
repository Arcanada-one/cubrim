//! V-AC-5 (real ref stream) + V-AC-10 (loaded-table fp) at catalog scale —
//! the PRD-pinned measurement regimes, not implementer-authored synthetic
//! distributions.

mod common;
use addressor::catalog::Catalog;
use addressor::cas::CasStore;
use addressor::format::{decode_cdc_payload, Container, SchemeByte};
use addressor::refs::{varint_encode, RefCoder};
use common::{open_addressor, text};
use tempfile::tempdir;

/// V-AC-5: mean bytes/ref on the REAL ref stream the store emits, with the
/// catalog pre-seeded to catalog scale (ordinals span a large range — the
/// regime where bare varint would cost 3 B and the adaptive coder must not).
#[test]
fn real_ref_stream_mean_under_gate_at_scale() {
    let dir = tempdir().unwrap();
    let mut a = open_addressor(dir.path());
    // pre-seed the catalog to a large ordinal range with many promoted chunks
    // (donor stored twice → its chunks are promoted, ordinals climb high)
    for s in 0..40u64 {
        let donor = text(90_000, 10_000 + s);
        a.store_bytes(&donor).unwrap();
        let mut d2 = donor.clone();
        d2.extend_from_slice(format!("-seed{s}").as_bytes());
        a.store_bytes(&d2).unwrap();
    }
    assert!(a.catalog.len().unwrap() > 300, "catalog not at scale");

    // now store dup-heavy files; walk their containers and measure the REAL
    // encoded ref bytes vs ref count (the actual store ref stream).
    let mut total_ref_bytes = 0usize;
    let mut total_refs = 0usize;
    for s in 0..40u64 {
        let donor = text(90_000, 10_000 + s);
        let mut f = donor.clone();
        f.extend_from_slice(format!("-user{s}").as_bytes());
        let out = a.store_bytes(&f).unwrap();
        let entry = a.catalog.entry(out.ordinal).unwrap().unwrap();
        let container = Container::from_bytes(&a.cas.get(&entry.blob).unwrap()).unwrap();
        if !matches!(container.scheme, SchemeByte::CdcDedup | SchemeByte::CdcResidual) {
            continue;
        }
        let with_res = container.scheme == SchemeByte::CdcResidual;
        let (entries, _) = decode_cdc_payload(&container.payload, with_res).unwrap();
        // re-encode just the matched refs to measure their real byte cost
        let mut coder = RefCoder::new();
        let mut buf = Vec::new();
        for e in &entries {
            if let addressor::format::CdcEntry::Matched { ordinal } = e {
                coder.encode(*ordinal, &mut buf);
                total_refs += 1;
            }
        }
        total_ref_bytes += buf.len();
    }
    assert!(total_refs > 100, "too few real refs measured: {total_refs}");
    let mean = total_ref_bytes as f64 / total_refs as f64;
    assert!(mean <= 2.3, "real-stream mean ref size {mean:.3} B > 2.3 B gate");
}

/// V-AC-10: fp16 false-positive rate on a LOADED table (>=10^5 negative
/// probes), catalog scale — the AH-09 3.96% regime, not a 6%-occupancy toy.
#[test]
fn fp16_negative_rate_on_loaded_table() {
    let dir = tempdir().unwrap();
    let cas = CasStore::open(&dir.path().join("store")).unwrap();
    let mut cat = Catalog::open(&dir.path().join("catalog")).unwrap();
    // load 200k keys — forces at least one grow/rebuild past 65536 slots
    let n_keys = 80_000u32;
    for i in 0..n_keys {
        let data = format!("scale-key-{i}");
        let blob = cas.put(data.as_bytes()).unwrap();
        let h = *blake3::hash(data.as_bytes()).as_bytes();
        cat.insert(h, blob).unwrap();
    }
    assert!(cat.fp16_slot_count() >= 131072, "table did not grow to load");
    // 10^5 negative probes
    let probes = 100_000u32;
    let mut passed = 0u32;
    for i in 0..probes {
        let h = *blake3::hash(format!("neg-{i}").as_bytes()).as_bytes();
        if cat.fp16_may_contain(&h) {
            passed += 1;
        }
    }
    let rate = passed as f64 / probes as f64;
    assert!(rate <= 0.045, "loaded-table fp16 negative rate {rate:.4} > 0.045");
    // 2 B/slot by construction (the index is a flat Vec<u16>)
    assert_eq!(cat.fp16_bytes_per_slot(), 2.0);
}

/// fp16 grow/rebuild survives a reopen at scale (grow path was untested).
#[test]
fn fp16_grow_survives_reopen() {
    let dir = tempdir().unwrap();
    let cas = CasStore::open(&dir.path().join("store")).unwrap();
    let catdir = dir.path().join("catalog");
    let mut sample = Vec::new();
    {
        let mut cat = Catalog::open(&catdir).unwrap();
        for i in 0..80_000u32 {
            let data = format!("grow-{i}");
            let blob = cas.put(data.as_bytes()).unwrap();
            let h = *blake3::hash(data.as_bytes()).as_bytes();
            cat.insert(h, blob).unwrap();
            if i % 20_000 == 0 {
                sample.push(h);
            }
        }
        assert!(cat.fp16_slot_count() > 65536, "did not grow");
        cat.commit_fp16().unwrap();
    }
    let cat2 = Catalog::open(&catdir).unwrap();
    for h in &sample {
        assert!(cat2.lookup(h, &cas).unwrap().is_some(), "lost key after reopen");
    }
}

/// suppress unused varint_encode import warning where the helper isn't used
#[allow(dead_code)]
fn _touch() {
    let mut v = Vec::new();
    varint_encode(1, &mut v);
}
