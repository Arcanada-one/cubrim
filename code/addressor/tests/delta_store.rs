//! Core B integration through the store API (D-REQ-08): a version stored as
//! a delta against its base round-trips and is far smaller than storing it
//! whole.

mod common;
use common::text;
use tempfile::tempdir;

#[test]
fn store_delta_roundtrips_and_is_small() {
    let dir = tempdir().unwrap();
    let mut a = common::open_addressor(dir.path());
    let base = text(200_000, 71);
    let base_out = a.store_bytes(&base).unwrap();
    let mut v2 = base.clone();
    v2.splice(50_000..50_000, b"# a new config line\n".iter().copied());
    v2.extend_from_slice(b"appended\n");
    let d_out = a.store_delta(base_out.ordinal, &v2).unwrap();
    assert_eq!(a.retrieve(d_out.ordinal).unwrap(), v2, "delta round-trip");
    // the delta container is far smaller than a whole store of v2
    let whole = addressor::router::Addressor::pure_cubrim_container(&v2).len();
    assert!(
        d_out.container_len * 4 < whole,
        "delta {} not << whole {}",
        d_out.container_len,
        whole
    );
}

#[test]
fn store_config_refuses_param_mismatch() {
    let dir = tempdir().unwrap();
    {
        let mut a = common::open_addressor(dir.path());
        a.store_bytes(&text(1000, 1)).unwrap();
    }
    // corrupt the store config to simulate a param change
    std::fs::write(dir.path().join("store.config"), "cdc_min=9999 cdc_avg=1 cdc_max=2 format=CBA1\n").unwrap();
    assert!(addressor::router::Addressor::open(dir.path()).is_err());
}
