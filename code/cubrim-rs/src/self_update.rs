#![forbid(unsafe_code)]

use crate::{license, AppError};
use semver::Version;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct ReleaseInfo {
    version: String,
    changelog: String,
    platforms: Vec<ReleasePlatform>,
}

#[derive(Debug, Deserialize)]
struct ReleasePlatform {
    os: String,
    arch: String,
    url: String,
    sha256: String,
}

pub fn run_update() -> Result<(), AppError> {
    let body = license::usage_payload("release_check")?;
    let value = license::post_json("/api/release-check", body)
        .map_err(|err| AppError::io(format!("release check failed: {err}")))?;
    let info: ReleaseInfo =
        serde_json::from_value(value).map_err(|err| AppError::io(err.to_string()))?;
    run_update_with_release(info)
}

fn run_update_with_release(info: ReleaseInfo) -> Result<(), AppError> {
    let current = parse_version(env!("CARGO_PKG_VERSION"))?;
    let latest = parse_version(&info.version)?;
    if latest <= current {
        println!("you have the latest stable v{}", info.version);
        return Ok(());
    }

    let platform = info
        .platforms
        .iter()
        .find(|p| p.os == std::env::consts::OS && p.arch == std::env::consts::ARCH)
        .ok_or_else(|| AppError::usage("no update available for your platform"))?;

    println!("Cubrim {} is available.", info.version);
    println!("{}", info.changelog.trim());
    if !confirm(&format!("Download version {}? [y/N] ", info.version))? {
        return Ok(());
    }

    let current_exe = std::env::current_exe().map_err(AppError::from)?;
    let tmp_path = download_to_temp(platform)?;
    verify_sha256(&tmp_path, &platform.sha256)?;
    println!("Downloaded and verified: {}", tmp_path.display());
    if !confirm(&format!(
        "Replace current cubrim binary at {}? [y/N] ",
        current_exe.display()
    ))? {
        cleanup_download(&tmp_path);
        return Ok(());
    }
    replace_current_binary(&tmp_path, &current_exe)
}

fn parse_version(raw: &str) -> Result<Version, AppError> {
    let cleaned = raw.trim_start_matches('v');
    Version::parse(cleaned).map_err(|err| AppError::usage(format!("invalid version: {err}")))
}

fn download_to_temp(platform: &ReleasePlatform) -> Result<PathBuf, AppError> {
    validate_download_url(&platform.url)?;
    let dir = std::env::temp_dir().join(format!("cubrim-update-{}", std::process::id()));
    fs::create_dir_all(&dir).map_err(AppError::from)?;
    let path = dir.join("cubrim.new");
    let mut response = license::http_agent()
        .get(&platform.url)
        .call()
        .map_err(|err| AppError::io(err.to_string()))?
        .into_reader();
    let mut out = fs::File::create(&path).map_err(AppError::from)?;
    io::copy(&mut response, &mut out).map_err(AppError::from)?;
    Ok(path)
}

/// Reject release URLs a legitimate manifest should never contain.
///
/// This is defence in depth, not a trust anchor. The expected SHA-256 is
/// supplied by the same `/api/release-check` response that supplies the URL,
/// so a forged or compromised manifest can still name an attacker host and a
/// matching hash. Only a signature over the release, verified against a key
/// this binary already trusts, closes that; see
/// `documentation/ephemeral/research/CUBR-SELFUPDATE-TRUST-20260811.md`.
///
/// What this *does* close needs no knowledge of the release host:
/// a plaintext download, and credentials smuggled into the authority.
fn validate_download_url(raw: &str) -> Result<(), AppError> {
    const SCHEME: &str = "https://";
    let head = raw
        .get(..SCHEME.len())
        .ok_or_else(|| AppError::integrity(URL_NOT_HTTPS))?;
    if !head.eq_ignore_ascii_case(SCHEME) {
        return Err(AppError::integrity(URL_NOT_HTTPS));
    }
    let authority = raw[SCHEME.len()..]
        .split(['/', '?', '#'])
        .next()
        .unwrap_or_default();
    if authority.is_empty() {
        return Err(AppError::integrity(
            "release URL has no host; refusing to download an update",
        ));
    }
    if authority.contains('@') {
        return Err(AppError::integrity(
            "release URL embeds credentials; refusing to download an update",
        ));
    }
    Ok(())
}

const URL_NOT_HTTPS: &str = "release URL is not https; refusing to download an update";

fn verify_sha256(path: &Path, expected_hex: &str) -> Result<(), AppError> {
    let bytes = fs::read(path).map_err(AppError::from)?;
    let actual = hex::encode(Sha256::digest(&bytes));
    if actual.eq_ignore_ascii_case(expected_hex) {
        Ok(())
    } else {
        let _ = fs::remove_file(path);
        Err(AppError::integrity(
            "download SHA256 mismatch; refusing to replace current binary",
        ))
    }
}

fn replace_current_binary(tmp_path: &Path, current_exe: &Path) -> Result<(), AppError> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(tmp_path)
            .map_err(AppError::from)?
            .permissions();
        perms.set_mode(0o755);
        fs::set_permissions(tmp_path, perms).map_err(AppError::from)?;
    }
    fs::rename(tmp_path, current_exe).map_err(|err| {
        AppError::io(format!(
            "cannot replace binary atomically: {err}; verified binary remains at {}",
            tmp_path.display()
        ))
    })?;
    cleanup_download(tmp_path);
    Ok(())
}

fn cleanup_download(tmp_path: &Path) {
    if let Some(parent) = tmp_path.parent() {
        let _ = fs::remove_dir_all(parent);
    }
}

fn confirm(prompt: &str) -> Result<bool, AppError> {
    eprint!("{prompt}");
    io::stderr().flush().map_err(AppError::from)?;
    let mut answer = String::new();
    io::stdin().read_line(&mut answer).map_err(AppError::from)?;
    Ok(answer.trim().eq_ignore_ascii_case("y") || answer.trim().eq_ignore_ascii_case("yes"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn https_release_url_is_accepted() {
        validate_download_url("https://example.invalid/cubrim-linux-x86_64").unwrap();
        validate_download_url("HTTPS://EXAMPLE.INVALID/a").unwrap();
    }

    #[test]
    fn plaintext_release_url_is_refused() {
        let err = validate_download_url("http://example.invalid/cubrim").unwrap_err();
        assert_eq!(err.exit_code, 2);
        let err = validate_download_url("ftp://example.invalid/cubrim").unwrap_err();
        assert_eq!(err.exit_code, 2);
    }

    #[test]
    fn credentials_in_release_url_are_refused() {
        let err = validate_download_url("https://user:pass@evil.invalid/cubrim").unwrap_err();
        assert_eq!(err.exit_code, 2);
    }

    #[test]
    fn hostless_or_truncated_release_url_is_refused() {
        assert!(validate_download_url("https://").is_err());
        assert!(validate_download_url("https://?q=1").is_err());
        assert!(validate_download_url("http").is_err());
        assert!(validate_download_url("").is_err());
    }

    #[test]
    fn download_to_temp_rejects_a_bad_url_before_touching_network_or_disk() {
        let platform = ReleasePlatform {
            os: std::env::consts::OS.to_string(),
            arch: std::env::consts::ARCH.to_string(),
            url: "http://evil.invalid/cubrim".to_string(),
            sha256: "00".repeat(32),
        };
        let dir = std::env::temp_dir().join(format!("cubrim-update-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);

        let err = download_to_temp(&platform).unwrap_err();

        assert_eq!(err.exit_code, 2);
        assert!(
            !dir.exists(),
            "a rejected URL must not create the update directory"
        );
    }

    #[test]
    fn sha256_mismatch_fails_closed_and_removes_temp_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("cubrim.new");
        fs::write(&path, b"bad binary").unwrap();
        let err = verify_sha256(&path, "0000").unwrap_err();
        assert_eq!(err.exit_code, 2);
        assert!(!path.exists());
    }

    #[test]
    fn replace_current_binary_removes_update_directory() {
        let dir = tempfile::tempdir().unwrap();
        let update_dir = dir.path().join("update");
        fs::create_dir(&update_dir).unwrap();
        let new_binary = update_dir.join("cubrim.new");
        let current = dir.path().join("cubrim");
        fs::write(&new_binary, b"new").unwrap();
        fs::write(&current, b"old").unwrap();

        replace_current_binary(&new_binary, &current).unwrap();

        assert_eq!(fs::read(&current).unwrap(), b"new");
        assert!(!update_dir.exists());
    }
}
