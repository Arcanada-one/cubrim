use std::fs;
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

use tempfile::tempdir;

static STATE_COUNTER: AtomicUsize = AtomicUsize::new(0);

fn cubrim() -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_cubrim"));
    command.env("CUBRIM_ACCEPT_LICENSE", "1");
    command.env(
        "CUBRIM_STATE_DIR",
        std::env::temp_dir().join(format!(
            "cubrim-test-state-{}-{}",
            std::process::id(),
            STATE_COUNTER.fetch_add(1, Ordering::Relaxed)
        )),
    );
    command.env("CUBRIM_API_BASE_URL", "http://127.0.0.1:9");
    command
}

#[test]
fn archive_directory_roundtrip_list_and_test() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("input");
    let nested = input.join("nested");
    fs::create_dir_all(&nested).unwrap();
    fs::write(input.join("root.txt"), b"root file\n").unwrap();
    fs::write(nested.join("child.bin"), b"child data child data\n").unwrap();
    let archive = temp.path().join("archive.cbr");
    let output = temp.path().join("output");

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .arg("--force")
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    let list = cubrim().args(["l"]).arg(&archive).output().unwrap();
    assert!(list.status.success());
    let listing = String::from_utf8(list.stdout).unwrap();
    assert!(listing.contains("input/root.txt"));
    assert!(listing.contains("input/nested/child.bin"));

    assert!(cubrim()
        .args(["t"])
        .arg(&archive)
        .status()
        .unwrap()
        .success());
    assert!(cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&output)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    assert_eq!(
        fs::read(input.join("root.txt")).unwrap(),
        fs::read(output.join("input/root.txt")).unwrap()
    );
    assert_eq!(
        fs::read(nested.join("child.bin")).unwrap(),
        fs::read(output.join("input/nested/child.bin")).unwrap()
    );
}

#[test]
fn encrypted_archive_roundtrip_and_wrong_password_failure() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("secret.txt");
    let archive = temp.path().join("secret.cbr");
    let output = temp.path().join("out");
    fs::write(&input, b"secret material\n").unwrap();

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .args(["--password", "correct", "--force", "--quiet"])
        .status()
        .unwrap()
        .success());

    let wrong = cubrim()
        .args(["t"])
        .arg(&archive)
        .args(["--password", "wrong"])
        .output()
        .unwrap();
    assert_eq!(wrong.status.code(), Some(2));

    assert!(cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&output)
        .args(["--password", "correct", "--quiet"])
        .status()
        .unwrap()
        .success());
    assert_eq!(
        fs::read(&input).unwrap(),
        fs::read(output.join("secret.txt")).unwrap()
    );
}

#[test]
fn legacy_x_decompresses_single_file_blob() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("input.txt");
    let blob = temp.path().join("input.cub");
    let output = temp.path().join("output.txt");
    fs::write(&input, b"legacy path\n").unwrap();

    assert!(cubrim()
        .args(["compress"])
        .arg(&input)
        .arg(&blob)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());
    assert!(cubrim()
        .args(["x"])
        .arg(&blob)
        .arg(&output)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());
    assert_eq!(fs::read(input).unwrap(), fs::read(output).unwrap());
}

#[test]
fn path_traversal_archive_is_rejected() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("safe.txt");
    let archive = temp.path().join("archive.cbr");
    let output = temp.path().join("out");
    fs::write(&input, b"safe\n").unwrap();

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .arg("--force")
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    let mut bytes = fs::read(&archive).unwrap();
    let needle = b"safe.txt";
    let pos = bytes
        .windows(needle.len())
        .position(|window| window == needle)
        .unwrap();
    bytes[pos..pos + needle.len()].copy_from_slice(b"../x.txt");
    fs::write(&archive, bytes).unwrap();

    let result = cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&output)
        .output()
        .unwrap();
    assert_eq!(result.status.code(), Some(2));
    assert!(!temp.path().join("x.txt").exists());
}

#[test]
fn corrupt_archive_fails_test_command() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("safe.txt");
    let archive = temp.path().join("archive.cbr");
    fs::write(&input, b"safe safe safe\n").unwrap();
    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .arg("--force")
        .arg("--quiet")
        .status()
        .unwrap()
        .success());
    let mut bytes = fs::read(&archive).unwrap();
    let last = bytes.len() - 1;
    bytes[last] ^= 0x55;
    fs::write(&archive, bytes).unwrap();
    let result = cubrim().args(["t"]).arg(&archive).output().unwrap();
    assert_eq!(result.status.code(), Some(2));
}
