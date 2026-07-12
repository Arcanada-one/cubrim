use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

use blake3::Hasher;
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
fn bare_invocation_prints_help_and_exits_zero() {
    let temp = tempdir().unwrap();
    let output = cubrim().current_dir(temp.path()).output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains(&format!("cubrim {}", env!("CARGO_PKG_VERSION"))));
    assert!(stdout.contains("Usage: cubrim"));
    assert!(stdout.contains("Commands:"));
    assert!(stdout.contains("  a   "));
    assert!(stdout.contains("  d   "));
}

#[test]
fn unknown_command_exits_nonzero_and_mentions_usage() {
    let output = cubrim().arg("bogus").output().unwrap();
    assert_eq!(output.status.code(), Some(2));
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("unrecognized subcommand 'bogus'"));
    assert!(stderr.contains("Usage: cubrim"));
}

#[test]
fn license_flag_prints_summary_and_exits_zero() {
    let output = cubrim().arg("--license").output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("free for non-commercial use"));
    assert!(stdout.contains("USD 50/year"));
    assert!(stdout.contains("install_id"));
}

#[test]
fn hidden_bench_commands_roundtrip_but_stay_out_of_help() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("input.bin");
    let blob = temp.path().join("input.cub");
    let output = temp.path().join("output.bin");
    fs::write(&input, b"hidden benchmark path\n").unwrap();

    let help = cubrim().output().unwrap();
    assert!(help.status.success());
    let stdout = String::from_utf8(help.stdout).unwrap();
    assert!(!stdout.contains("compress"));
    assert!(!stdout.contains("decompress"));

    assert!(cubrim()
        .args(["compress"])
        .arg(&input)
        .arg(&blob)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());
    assert!(cubrim()
        .args(["decompress"])
        .arg(&blob)
        .arg(&output)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());
    assert_eq!(fs::read(input).unwrap(), fs::read(output).unwrap());
}

#[test]
fn extract_flat_and_delete_follow_public_archive_contract() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("input");
    let nested = input.join("nested");
    fs::create_dir_all(&nested).unwrap();
    fs::write(input.join("root.txt"), b"root file\n").unwrap();
    fs::write(nested.join("child.bin"), b"child data child data\n").unwrap();
    fs::write(nested.join("drop.tmp"), b"delete me\n").unwrap();

    let archive = temp.path().join("archive.cbr");
    let flat = temp.path().join("flat");

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .arg("--force")
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    assert!(cubrim()
        .args(["e"])
        .arg(&archive)
        .args(["-o"])
        .arg(&flat)
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    assert_eq!(
        fs::read(input.join("root.txt")).unwrap(),
        fs::read(flat.join("root.txt")).unwrap()
    );
    assert_eq!(
        fs::read(nested.join("child.bin")).unwrap(),
        fs::read(flat.join("child.bin")).unwrap()
    );
    assert_eq!(
        fs::read(nested.join("drop.tmp")).unwrap(),
        fs::read(flat.join("drop.tmp")).unwrap()
    );

    assert!(cubrim()
        .args(["d"])
        .arg(&archive)
        .arg("*.tmp")
        .arg("--quiet")
        .status()
        .unwrap()
        .success());

    let list = cubrim().args(["l"]).arg(&archive).output().unwrap();
    assert!(list.status.success());
    let listing = String::from_utf8(list.stdout).unwrap();
    assert!(!listing.contains("drop.tmp"));
    assert!(listing.contains("child.bin"));
}

#[test]
fn extract_refuses_overwrite_without_force_then_succeeds_with_force() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("input.txt");
    let archive = temp.path().join("archive.cbr");
    let out_dir = temp.path().join("out");
    fs::write(&input, b"fresh payload\n").unwrap();

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .args(["--force", "--quiet"])
        .status()
        .unwrap()
        .success());

    fs::create_dir_all(&out_dir).unwrap();
    fs::write(out_dir.join("input.txt"), b"old payload\n").unwrap();

    let blocked = cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&out_dir)
        .output()
        .unwrap();
    assert_eq!(blocked.status.code(), Some(1));

    assert!(cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&out_dir)
        .args(["--force", "--quiet"])
        .status()
        .unwrap()
        .success());
    assert_eq!(
        fs::read(&input).unwrap(),
        fs::read(out_dir.join("input.txt")).unwrap()
    );
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

#[test]
fn large_directory_roundtrip_preserves_file_set_and_bytes() {
    let temp = tempdir().unwrap();
    let input = temp.path().join("bulk");
    let archive = temp.path().join("bulk.cbr");
    let output = temp.path().join("out");
    fs::create_dir_all(&input).unwrap();

    for shard in 0..8 {
        let dir = input.join(format!("shard-{shard}"));
        fs::create_dir_all(&dir).unwrap();
        for index in 0..120 {
            let path = dir.join(format!("file-{index:03}.bin"));
            let mut data = Vec::with_capacity(4096);
            for i in 0..4096u32 {
                data.push(((i + shard * 17 + index * 31) % 251) as u8);
            }
            fs::write(path, data).unwrap();
        }
    }

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .args(["--force", "--quiet"])
        .status()
        .unwrap()
        .success());
    assert!(cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&output)
        .args(["--quiet"])
        .status()
        .unwrap()
        .success());

    let source_manifest = digest_tree(&input);
    let restored_manifest = digest_tree(&output.join("bulk"));
    assert_eq!(source_manifest, restored_manifest);
}

fn digest_tree(root: &PathBuf) -> Vec<(String, String)> {
    let mut rows = Vec::new();
    for entry in walkdir::WalkDir::new(root)
        .follow_links(false)
        .sort_by_file_name()
    {
        let entry = entry.unwrap();
        let path = entry.path();
        if path == root {
            continue;
        }
        let rel = path.strip_prefix(root).unwrap().to_string_lossy().into_owned();
        if entry.file_type().is_dir() {
            rows.push((format!("dir:{rel}"), String::new()));
        } else if entry.file_type().is_file() {
            let mut hasher = Hasher::new();
            hasher.update(&fs::read(path).unwrap());
            rows.push((format!("file:{rel}"), hasher.finalize().to_hex().to_string()));
        } else if entry.file_type().is_symlink() {
            rows.push((
                format!("symlink:{rel}"),
                fs::read_link(path).unwrap().to_string_lossy().into_owned(),
            ));
        }
    }
    rows
}

#[cfg(unix)]
#[test]
fn preserve_roundtrip_restores_symlink_hardlink_xattr_and_non_utf8_name() {
    use std::ffi::OsString;
    use std::os::unix::ffi::{OsStrExt, OsStringExt};
    use std::os::unix::fs::{symlink, MetadataExt};

    let temp = tempdir().unwrap();
    let input = temp.path().join("input");
    let nested = input.join("nested");
    fs::create_dir_all(&nested).unwrap();

    let original = nested.join("original.bin");
    fs::write(&original, b"payload-1234\n").unwrap();

    let hard = nested.join("hard.bin");
    fs::hard_link(&original, &hard).unwrap();

    let link = nested.join("link.bin");
    symlink(PathBuf::from("original.bin"), &link).unwrap();

    let non_utf8 = nested.join(OsString::from_vec(b"name-\xff.bin".to_vec()));
    fs::write(&non_utf8, b"non-utf8\n").unwrap();

    xattr::set(&original, OsString::from("user.cubrim"), b"xattr-value").unwrap();

    let archive = temp.path().join("archive.cbr");
    let output = temp.path().join("output");

    assert!(cubrim()
        .args(["a"])
        .arg(&archive)
        .arg(&input)
        .args(["--force", "--quiet", "--preserve"])
        .status()
        .unwrap()
        .success());

    assert!(cubrim()
        .args(["x"])
        .arg(&archive)
        .args(["-o"])
        .arg(&output)
        .args(["--quiet", "--preserve"])
        .status()
        .unwrap()
        .success());

    let restored_original = output.join("input/nested/original.bin");
    let restored_hard = output.join("input/nested/hard.bin");
    let restored_link = output.join("input/nested/link.bin");
    let restored_non_utf8 = output
        .join("input/nested")
        .join(OsString::from_vec(b"name-\xff.bin".to_vec()));

    assert_eq!(fs::read(&original).unwrap(), fs::read(&restored_original).unwrap());
    assert_eq!(fs::read(&non_utf8).unwrap(), fs::read(&restored_non_utf8).unwrap());

    let restored_symlink_meta = fs::symlink_metadata(&restored_link).unwrap();
    assert!(restored_symlink_meta.file_type().is_symlink());
    let restored_target = fs::read_link(&restored_link).unwrap();
    assert_eq!(restored_target.as_os_str().as_bytes(), b"original.bin");

    let original_meta = fs::metadata(&restored_original).unwrap();
    let hard_meta = fs::metadata(&restored_hard).unwrap();
    assert_eq!(original_meta.ino(), hard_meta.ino());
    assert_eq!(original_meta.dev(), hard_meta.dev());

    let restored_xattr = xattr::get(&restored_original, OsString::from("user.cubrim"))
        .unwrap()
        .unwrap();
    assert_eq!(restored_xattr, b"xattr-value");
}
