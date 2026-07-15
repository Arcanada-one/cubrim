//! Two-directory hub/spoke simulation of the fleet sync (D-REQ-13):
//! (а) epoch snapshot pull with verify-then-switch;
//! (б) poisoned push rejected at ingest with a journal record;
//! (в) valid blob lands in the store;
//! (г) dedup-hit against the snapshot (bloom) survives the private split;
//! (д) no --delete aliases in the sync scripts;
//! (е) per-spoke quota rejects an over-cap inbox;
//! (ж) staging design: accepted blob leaves the inbox before verification
//!     completes (swap-after-verify race has nothing to swap);
//! (з) corrupt manifest → the current_snapshot symlink does not move.

mod common;
use addressor::bloom::FleetBloom;
use std::path::{Path, PathBuf};
use std::process::Command;
use tempfile::tempdir;

fn scripts_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("scripts/sync")
}

fn run(script: &str, args: &[&str], envs: &[(&str, &str)]) -> std::process::Output {
    let mut c = Command::new("bash");
    c.arg(scripts_dir().join(script));
    c.args(args);
    for (k, v) in envs {
        c.env(k, v);
    }
    c.output().expect("script runs")
}

fn blake3_hex(data: &[u8]) -> String {
    blake3::hash(data).to_hex().to_string()
}

fn addr_bin() -> &'static str {
    env!("CARGO_BIN_EXE_cubrim-addr")
}

#[test]
fn full_sync_lifecycle() {
    let dir = tempdir().unwrap();
    let hub = dir.path().join("hub");
    let spoke = dir.path().join("spoke");

    // layout
    assert!(run("setup.sh", &[hub.to_str().unwrap(), "hub"], &[]).status.success());
    assert!(run("setup.sh", &[spoke.to_str().unwrap(), "spoke"], &[]).status.success());

    // (д) no delete aliases in our sync scripts
    let grep = Command::new("grep")
        .args(["-rnE", "--", "--del\\b|--delete"])
        .arg(scripts_dir())
        .output()
        .unwrap();
    assert!(!grep.status.success(), "--delete alias found in sync scripts");

    // ---- hub publishes an epoch snapshot with a bloom over its keys ----
    let mut bloom = FleetBloom::new(100);
    let hub_key = *blake3::hash(b"block-on-hub").as_bytes();
    bloom.insert(&hub_key);
    let artifacts = dir.path().join("artifacts");
    std::fs::create_dir_all(&artifacts).unwrap();
    std::fs::write(artifacts.join("bloom.bin"), bloom.to_bytes().unwrap()).unwrap();
    std::fs::write(artifacts.join("catalog.snap"), b"catalog-snapshot-bytes").unwrap();
    let out = run(
        "publish-snapshot.sh",
        &[hub.to_str().unwrap(), artifacts.to_str().unwrap()],
        &[],
    );
    assert!(out.status.success(), "publish failed: {out:?}");

    // ---- (а) spoke pulls; verify-then-switch succeeds on a clean epoch ----
    let out = run(
        "pull-snapshot.sh",
        &[hub.to_str().unwrap(), spoke.to_str().unwrap()],
        &[],
    );
    assert!(out.status.success(), "pull failed: {out:?}");
    let current = spoke.join("current_snapshot");
    assert!(current.exists(), "current_snapshot symlink missing");
    let epoch1 = std::fs::read_link(&current).unwrap();

    // (г) dedup-hit against the snapshot survives the private split:
    // the spoke checks a hub-present block via the pulled bloom file.
    let pulled = FleetBloom::from_bytes(
        &std::fs::read(current.join("bloom.bin")).unwrap(),
    )
    .unwrap();
    assert!(pulled.contains(&hub_key), "hub block must hit via snapshot");
    assert!(!pulled.contains(blake3::hash(b"spoke-private").as_bytes()));

    // ---- (б)+(в)+(ж) push valid + poisoned blobs, ingest sorts them ----
    let valid = b"valid chunk content".to_vec();
    let valid_hex = blake3_hex(&valid);
    let poisoned_hex = blake3_hex(b"claimed content"); // name says one thing...
    let inbox_spoke = hub.join("inbox").join("spoke_test1");
    for (hex, bytes) in [(&valid_hex, valid.as_slice()), (&poisoned_hex, b"...bytes say another".as_slice())] {
        let d = inbox_spoke.join(&hex[0..2]).join(&hex[2..4]);
        std::fs::create_dir_all(&d).unwrap();
        std::fs::write(d.join(format!("{hex}.chunk")), bytes).unwrap();
    }
    // a junk-named file must be rejected by the name gate
    std::fs::write(inbox_spoke.join("evil name;rm.chunk"), b"junk").unwrap();

    let out = run(
        "ingest-hub.sh",
        &[hub.to_str().unwrap()],
        &[("ADDR_BIN", addr_bin())],
    );
    assert!(out.status.success(), "ingest failed: {out:?}");

    let stored_valid = hub
        .join("store")
        .join(&valid_hex[0..2])
        .join(&valid_hex[2..4])
        .join(format!("{valid_hex}.chunk"));
    assert!(stored_valid.exists(), "(в) valid blob must land in store");
    let stored_poisoned = hub
        .join("store")
        .join(&poisoned_hex[0..2])
        .join(&poisoned_hex[2..4])
        .join(format!("{poisoned_hex}.chunk"));
    assert!(!stored_poisoned.exists(), "(б) poisoned blob must NOT land");
    // (ж) nothing processable remains in the inbox (moved to staging first)
    let leftover = walk_files(&inbox_spoke);
    assert!(
        leftover.is_empty(),
        "inbox still holds processed files: {leftover:?}"
    );
    // journal: outside the inbox tree, records rejected-hash + rejected-name
    let journal = std::fs::read_to_string(hub.join("journal/ingest.jsonl")).unwrap();
    assert!(journal.contains("\"accepted\""));
    assert!(journal.contains("\"rejected-hash\""));
    assert!(journal.contains("\"rejected-name\""));
    assert!(!hub.join("inbox/journal.jsonl").exists());

    // ---- (е) per-spoke quota ----
    let big = inbox_spoke.join("aa").join("bb");
    std::fs::create_dir_all(&big).unwrap();
    let filler_hex = blake3_hex(b"filler");
    std::fs::write(
        big.join(format!("{filler_hex}.chunk")),
        vec![0u8; 4096],
    )
    .unwrap();
    let out = run(
        "ingest-hub.sh",
        &[hub.to_str().unwrap()],
        &[("ADDR_BIN", addr_bin()), ("ADDR_SPOKE_QUOTA_BYTES", "100")],
    );
    assert!(out.status.success());
    let journal = std::fs::read_to_string(hub.join("journal/ingest.jsonl")).unwrap();
    assert!(journal.contains("\"quota-exceeded\""), "quota record missing");

    // ---- (з) corrupt manifest: pull fails, symlink unchanged ----
    // publish a second epoch, then corrupt one file inside it on the hub
    std::fs::write(artifacts.join("bloom.bin"), b"new-bloom-v2").unwrap();
    assert!(run(
        "publish-snapshot.sh",
        &[hub.to_str().unwrap(), artifacts.to_str().unwrap()],
        &[],
    )
    .status
    .success());
    let latest2 = std::fs::read_to_string(hub.join("snapshots/LATEST")).unwrap();
    let latest2 = latest2.trim();
    std::fs::write(
        hub.join("snapshots").join(latest2).join("bloom.bin"),
        b"tampered-after-manifest",
    )
    .unwrap();
    let out = run(
        "pull-snapshot.sh",
        &[hub.to_str().unwrap(), spoke.to_str().unwrap()],
        &[],
    );
    assert!(!out.status.success(), "(з) corrupt epoch must fail the pull");
    let still = std::fs::read_link(&current).unwrap();
    assert_eq!(still, epoch1, "(з) symlink moved to a corrupt epoch");
}

fn walk_files(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if !root.exists() {
        return out;
    }
    let mut stack = vec![root.to_path_buf()];
    while let Some(d) = stack.pop() {
        for e in std::fs::read_dir(&d).unwrap() {
            let p = e.unwrap().path();
            if p.is_dir() {
                stack.push(p);
            } else {
                out.push(p);
            }
        }
    }
    out
}
