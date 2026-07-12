#![forbid(unsafe_code)]

use crate::AppError;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;
use std::time::Duration;
use uuid::Uuid;

const FALLBACK_LICENSE: &str = include_str!("../LICENSE-SHORT.txt");
const DEFAULT_API_BASE: &str = "https://api.cubrim.com";
const CURRENT_LICENSE_VERSION: &str = "1.0.0";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct State {
    install_id: Uuid,
    accepted: bool,
    license_version: Option<String>,
    accepted_at: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct LicenseResponse {
    license_text: String,
    version: String,
    #[allow(dead_code)]
    updated_at: Option<String>,
    #[serde(default)]
    offline: bool,
}

pub fn show_license() -> Result<(), AppError> {
    let state = load_or_create_state()?;
    let license = fetch_license(&state, "license_fetch").unwrap_or_else(fallback_license);
    print_license(&license);
    Ok(())
}

pub fn accept_license_noninteractive() -> Result<(), AppError> {
    accept_license_noninteractive_impl(false)
}

pub fn accept_license_for_automation() -> Result<(), AppError> {
    accept_license_noninteractive_impl(true)
}

fn accept_license_noninteractive_impl(silent: bool) -> Result<(), AppError> {
    let mut state = load_or_create_state()?;
    if state.accepted {
        return Ok(());
    }
    let license = fetch_license(&state, "first_run_accept").unwrap_or_else(fallback_license);
    if !silent {
        print_license(&license);
    }
    mark_accepted(&mut state, &license.version);
    save_state(&state)?;
    if !silent {
        eprintln!("Cubrim license accepted.");
    }
    Ok(())
}

pub fn ensure_license_accepted() -> Result<(), AppError> {
    let mut state = load_or_create_state()?;
    if state.accepted {
        return Ok(());
    }

    let license = fetch_license(&state, "license_fetch").unwrap_or_else(fallback_license);
    print_license(&license);
    eprintln!();
    eprint!("Do you accept the Cubrim license terms? [Y/n] ");
    io::stderr().flush().map_err(AppError::from)?;

    let mut answer = String::new();
    read_tty_line(&mut answer)?;
    let answer = answer.trim();
    if answer.is_empty()
        || answer.eq_ignore_ascii_case("y")
        || answer.eq_ignore_ascii_case("yes")
    {
        let accept_license =
            fetch_license(&state, "first_run_accept").unwrap_or_else(|| license.clone());
        mark_accepted(&mut state, &accept_license.version);
        save_state(&state)?;
        eprintln!("Cubrim license accepted.");
        Ok(())
    } else {
        Err(AppError::usage(
            "license not accepted; command was not executed",
        ))
    }
}

pub fn usage_payload(event_type: &str) -> Result<serde_json::Value, AppError> {
    let state = load_or_create_state()?;
    Ok(payload_for_state(&state, event_type))
}

pub fn api_base_url() -> String {
    std::env::var("CUBRIM_API_BASE_URL")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_API_BASE.to_string())
        .trim_end_matches('/')
        .to_string()
}

pub fn http_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(3))
        .timeout_read(Duration::from_secs(5))
        .timeout_write(Duration::from_secs(3))
        .build()
}

pub fn post_json(path: &str, body: serde_json::Value) -> Result<serde_json::Value, String> {
    let url = format!("{}{}", api_base_url(), path);
    http_agent()
        .post(&url)
        .set("content-type", "application/json")
        .send_json(body)
        .map_err(|err| err.to_string())?
        .into_json::<serde_json::Value>()
        .map_err(|err| err.to_string())
}

fn fetch_license(state: &State, event_type: &str) -> Option<LicenseResponse> {
    let body = payload_for_state(state, event_type);
    let value = post_json("/api/license", body).ok()?;
    serde_json::from_value(value).ok()
}

fn fallback_license() -> LicenseResponse {
    LicenseResponse {
        license_text: format!("Offline copy, may be outdated.\n\n{}", FALLBACK_LICENSE),
        version: CURRENT_LICENSE_VERSION.to_string(),
        updated_at: None,
        offline: true,
    }
}

fn print_license(license: &LicenseResponse) {
    println!("{}", license.license_text.trim());
    if license.offline {
        println!();
        println!("Note: offline copy, may be outdated.");
    }
}

fn mark_accepted(state: &mut State, license_version: &str) {
    state.accepted = true;
    state.license_version = Some(license_version.to_string());
    state.accepted_at = Some(Utc::now().to_rfc3339());
}

fn payload_for_state(state: &State, event_type: &str) -> serde_json::Value {
    json!({
        "install_id": state.install_id,
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "cli_version": env!("CARGO_PKG_VERSION"),
        "event_type": event_type,
    })
}

fn load_or_create_state() -> Result<State, AppError> {
    let path = state_path()?;
    if path.exists() {
        let text = fs::read_to_string(&path).map_err(AppError::from)?;
        let mut state: State =
            serde_json::from_str(&text).map_err(|err| AppError::io(err.to_string()))?;
        if state.install_id.is_nil() {
            state.install_id = Uuid::new_v4();
        }
        return Ok(state);
    }

    let state = State {
        install_id: Uuid::new_v4(),
        accepted: false,
        license_version: None,
        accepted_at: None,
    };
    save_state(&state)?;
    Ok(state)
}

fn save_state(state: &State) -> Result<(), AppError> {
    let path = state_path()?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(AppError::from)?;
        set_private_dir_permissions(parent)?;
    }
    let text = serde_json::to_string_pretty(state).map_err(|err| AppError::io(err.to_string()))?;
    fs::write(&path, text).map_err(AppError::from)?;
    set_private_file_permissions(&path)
}

fn state_path() -> Result<PathBuf, AppError> {
    if let Ok(dir) = std::env::var("CUBRIM_STATE_DIR") {
        return Ok(PathBuf::from(dir).join("state.json"));
    }
    let base = dirs::config_dir()
        .ok_or_else(|| AppError::io("could not determine user config directory"))?;
    Ok(base.join("cubrim").join("state.json"))
}

#[cfg(unix)]
fn set_private_dir_permissions(path: &std::path::Path) -> Result<(), AppError> {
    use std::os::unix::fs::PermissionsExt;
    let mut perms = fs::metadata(path).map_err(AppError::from)?.permissions();
    perms.set_mode(0o700);
    fs::set_permissions(path, perms).map_err(AppError::from)
}

#[cfg(not(unix))]
fn set_private_dir_permissions(_path: &std::path::Path) -> Result<(), AppError> {
    Ok(())
}

#[cfg(unix)]
fn set_private_file_permissions(path: &std::path::Path) -> Result<(), AppError> {
    use std::os::unix::fs::PermissionsExt;
    let mut perms = fs::metadata(path).map_err(AppError::from)?.permissions();
    perms.set_mode(0o600);
    fs::set_permissions(path, perms).map_err(AppError::from)
}

#[cfg(not(unix))]
fn set_private_file_permissions(_path: &std::path::Path) -> Result<(), AppError> {
    Ok(())
}

#[cfg(unix)]
fn read_tty_line(out: &mut String) -> Result<(), AppError> {
    use std::io::BufRead;
    let tty = fs::File::open("/dev/tty").map_err(AppError::from)?;
    let mut reader = io::BufReader::new(tty);
    reader.read_line(out).map_err(AppError::from)?;
    Ok(())
}

#[cfg(not(unix))]
fn read_tty_line(out: &mut String) -> Result<(), AppError> {
    io::stdin().read_line(out).map_err(AppError::from)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn payload_contains_only_allowed_client_fields() {
        let state = State {
            install_id: Uuid::parse_str("00000000-0000-4000-8000-000000000001").unwrap(),
            accepted: false,
            license_version: None,
            accepted_at: None,
        };
        let value = payload_for_state(&state, "license_fetch");
        let mut keys = value
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>();
        keys.sort();
        assert_eq!(
            keys,
            vec!["arch", "cli_version", "event_type", "install_id", "os"]
        );
    }

    #[cfg(unix)]
    #[test]
    fn state_file_is_private_on_unix() {
        use std::os::unix::fs::PermissionsExt;

        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("CUBRIM_STATE_DIR", dir.path());
        let state = State {
            install_id: Uuid::parse_str("00000000-0000-4000-8000-000000000002").unwrap(),
            accepted: true,
            license_version: Some(CURRENT_LICENSE_VERSION.to_string()),
            accepted_at: Some("2026-07-09T00:00:00Z".to_string()),
        };

        save_state(&state).unwrap();

        let state_path = dir.path().join("state.json");
        assert_eq!(
            fs::metadata(dir.path()).unwrap().permissions().mode() & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(state_path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        std::env::remove_var("CUBRIM_STATE_DIR");
    }
}
