//! Runtime-optional Merkle (AH-21): corruption detection with --verify,
//! observable default-OFF (no sidecar without the flag), --help mentions
//! --verify, overhead budget asserted in the module test.

mod common;
use common::text;
use std::process::Command;
use tempfile::tempdir;

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_cubrim-addr")
}

#[test]
fn cli_verify_lifecycle_and_default_off() {
    let dir = tempdir().unwrap();
    let root = dir.path().join("root");
    let f = dir.path().join("input.bin");
    std::fs::write(&f, text(50_000, 3)).unwrap();

    // store WITHOUT --verify: no sidecar anywhere (default OFF observable)
    let out = Command::new(bin())
        .args(["--root", root.to_str().unwrap(), "store", f.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(out.status.success(), "store failed: {out:?}");
    let sidecars = walk_count(&root, ".bao");
    assert_eq!(sidecars, 0, "sidecar created without --verify");

    // store a second file WITH --verify → exactly one sidecar appears
    let f2 = dir.path().join("input2.bin");
    std::fs::write(&f2, text(60_000, 4)).unwrap();
    let out = Command::new(bin())
        .args(["--root", root.to_str().unwrap(), "store", f2.to_str().unwrap(), "--verify"])
        .output()
        .unwrap();
    assert!(out.status.success());
    let ordinal: u64 = String::from_utf8_lossy(&out.stdout)
        .split_whitespace()
        .next()
        .unwrap()
        .parse()
        .unwrap();
    assert_eq!(walk_count(&root, ".bao"), 1, "sidecar missing after --verify");

    // retrieve --verify passes on clean store
    let ok = Command::new(bin())
        .args(["--root", root.to_str().unwrap(), "retrieve", &ordinal.to_string(), "--verify", "-o", dir.path().join("out.bin").to_str().unwrap()])
        .output()
        .unwrap();
    assert!(ok.status.success(), "verified retrieve failed: {ok:?}");

    // corrupt the container blob (bit flip) → retrieve --verify fails
    let blob = find_largest_chunk(&root);
    let mut raw = std::fs::read(&blob).unwrap();
    let mid = raw.len() / 2;
    raw[mid] ^= 0x01;
    std::fs::write(&blob, raw).unwrap();
    let bad = Command::new(bin())
        .args(["--root", root.to_str().unwrap(), "retrieve", &ordinal.to_string(), "--verify"])
        .output()
        .unwrap();
    assert!(!bad.status.success(), "corrupted retrieve must fail");

    // --help mentions --verify
    let help = Command::new(bin()).args(["store", "--help"]).output().unwrap();
    assert!(String::from_utf8_lossy(&help.stdout).contains("--verify"));
}

fn walk_count(root: &std::path::Path, suffix: &str) -> usize {
    let mut n = 0;
    if !root.exists() {
        return 0;
    }
    let mut stack = vec![root.to_path_buf()];
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).unwrap() {
            let p = e.unwrap().path();
            if p.is_dir() {
                stack.push(p);
            } else if p.to_string_lossy().ends_with(suffix) {
                n += 1;
            }
        }
    }
    n
}

fn find_largest_chunk(root: &std::path::Path) -> std::path::PathBuf {
    let mut best: Option<(u64, std::path::PathBuf)> = None;
    let mut stack = vec![root.to_path_buf()];
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).unwrap() {
            let p = e.unwrap().path();
            if p.is_dir() {
                stack.push(p);
            } else if p.extension().map(|x| x == "chunk").unwrap_or(false) {
                let len = std::fs::metadata(&p).unwrap().len();
                if best.as_ref().map(|(l, _)| len > *l).unwrap_or(true) {
                    best = Some((len, p));
                }
            }
        }
    }
    best.unwrap().1
}
