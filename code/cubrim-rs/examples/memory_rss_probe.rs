//! One-process-at-a-time CUBR-0075 whole-process RSS probe.
//!
//! `prepare MANIFEST` hashes the deterministic payloads and builds the exact
//! frames that the measured trial will construct.  `trial PAYLOAD MODE ...`
//! then performs one encode/decode round trip in one short-lived process.  The
//! Python runner wraps that process in GNU time, so its peak RSS is not a
//! parent-process or repeated run-level observation.
//!
//! The probe emits no verdict.  The preregistered RSS fit and decision belong
//! to `memory_rss_runner.py`.

use cubrim::config::EncodeConfig;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::Instant;

const MODE_OFFSET: usize = 5;

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    samples: Vec<ManifestSample>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
struct ManifestSample {
    sample_id: String,
    path: String,
    expected_mode: String,
    input_bytes: usize,
    input_sha256: String,
}

#[derive(Debug, Serialize)]
struct PreparedManifest {
    schema_version: u32,
    samples: Vec<PreparedSample>,
}

#[derive(Debug, Serialize)]
struct PreparedSample {
    sample_id: String,
    path: String,
    expected_mode: String,
    input_bytes: usize,
    input_sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
}

#[derive(Debug, Serialize)]
struct TrialOutput {
    schema_version: u32,
    sample_id: String,
    expected_mode: String,
    input_bytes: usize,
    input_sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
    encode_ns: u128,
    decode_ns: u128,
    decoded_sha256: String,
    roundtrip_exact: bool,
}

fn sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn resolve_manifest_path(manifest_path: &str, path: &str) -> PathBuf {
    let candidate = Path::new(path);
    if candidate.is_absolute() {
        candidate.to_path_buf()
    } else {
        Path::new(manifest_path)
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join(candidate)
    }
}

fn raw_store_frame(data: &[u8]) -> Result<Vec<u8>, String> {
    let length = u32::try_from(data.len())
        .map_err(|_| format!("raw-store sample is too large for v1: {} bytes", data.len()))?;
    let mut frame = Vec::with_capacity(13 + data.len());
    frame.extend_from_slice(&cubrim::header::MAGIC);
    frame.push(cubrim::header::VERSION);
    frame.push(cubrim::header::MODE_RAW);
    frame.push(2);
    frame.extend_from_slice(&256u16.to_be_bytes());
    frame.extend_from_slice(&length.to_be_bytes());
    frame.extend_from_slice(data);
    Ok(frame)
}

fn build_frame(data: &[u8], expected_mode: &str) -> Result<Vec<u8>, String> {
    match expected_mode {
        "cube" => Ok(cubrim::codec::encode_base(
            data,
            &EncodeConfig::v1_default(),
        )),
        "raw_store" => raw_store_frame(data),
        other => Err(format!("unsupported memory-rss mode {other}")),
    }
}

fn mode(frame: &[u8]) -> Result<&'static str, String> {
    match frame.get(MODE_OFFSET).copied() {
        Some(cubrim::header::MODE_CUBE) => Ok("cube"),
        Some(cubrim::header::MODE_RAW) => Ok("raw_store"),
        Some(other) => Err(format!("unknown frame mode {other}")),
        None => Err("frame is too short to carry a mode".into()),
    }
}

fn read_manifest(path: &str) -> Result<Manifest, String> {
    let bytes = fs::read(path).map_err(|error| format!("read manifest {path}: {error}"))?;
    let manifest: Manifest = serde_json::from_slice(&bytes)
        .map_err(|error| format!("parse manifest {path}: {error}"))?;
    if manifest.schema_version != 1 {
        return Err(format!(
            "unsupported manifest schema {}",
            manifest.schema_version
        ));
    }
    if manifest.samples.is_empty() {
        return Err("memory-rss manifest must contain at least one sample".into());
    }
    Ok(manifest)
}

fn prepare(manifest_path: &str) -> Result<(), String> {
    let manifest = read_manifest(manifest_path)?;
    let mut samples = Vec::with_capacity(manifest.samples.len());
    for sample in manifest.samples {
        let payload_path = resolve_manifest_path(manifest_path, &sample.path);
        let data = fs::read(&payload_path)
            .map_err(|error| format!("read {}: {error}", payload_path.display()))?;
        let actual_input_sha = sha256(&data);
        if actual_input_sha != sample.input_sha256 || data.len() != sample.input_bytes {
            return Err(format!(
                "{} input metadata does not match payload",
                sample.sample_id
            ));
        }
        let frame = build_frame(&data, &sample.expected_mode)?;
        if mode(&frame)? != sample.expected_mode {
            return Err(format!("{} mode attribution mismatch", sample.sample_id));
        }
        let decoded = cubrim::decode(&frame)
            .map_err(|error| format!("{} preflight decode failed: {error}", sample.sample_id))?;
        if decoded != data {
            return Err(format!(
                "{} preflight round trip was not exact",
                sample.sample_id
            ));
        }
        samples.push(PreparedSample {
            sample_id: sample.sample_id,
            path: sample.path,
            expected_mode: sample.expected_mode,
            input_bytes: data.len(),
            input_sha256: actual_input_sha,
            frame_bytes: frame.len(),
            frame_sha256: sha256(&frame),
        });
    }
    println!(
        "{}",
        serde_json::to_string(&PreparedManifest {
            schema_version: 1,
            samples,
        })
        .map_err(|error| format!("serialize prepared manifest: {error}"))?
    );
    Ok(())
}

fn trial(
    payload_path: &str,
    expected_mode: &str,
    expected_input_sha256: &str,
    expected_frame_sha256: &str,
    sample_id: &str,
) -> Result<(), String> {
    let data =
        fs::read(payload_path).map_err(|error| format!("read payload {payload_path}: {error}"))?;
    let input_sha256 = sha256(&data);
    if input_sha256 != expected_input_sha256 {
        return Err(format!("{sample_id} input SHA-256 changed before trial"));
    }
    let encode_started = Instant::now();
    let frame = build_frame(&data, expected_mode)?;
    let encode_ns = encode_started.elapsed().as_nanos();
    if mode(&frame)? != expected_mode {
        return Err(format!("{sample_id} encoded mode differs from attribution"));
    }
    let frame_sha256 = sha256(&frame);
    if frame_sha256 != expected_frame_sha256 {
        return Err(format!("{sample_id} frame SHA-256 changed between trials"));
    }
    let decode_started = Instant::now();
    let decoded =
        cubrim::decode(&frame).map_err(|error| format!("{sample_id} decode failed: {error}"))?;
    let decode_ns = decode_started.elapsed().as_nanos();
    let decoded_sha256 = sha256(&decoded);
    let roundtrip_exact = decoded == data && decoded_sha256 == input_sha256;
    if !roundtrip_exact {
        return Err(format!(
            "{sample_id} trial failed the exact round-trip check"
        ));
    }
    println!(
        "{}",
        serde_json::to_string(&TrialOutput {
            schema_version: 1,
            sample_id: sample_id.to_string(),
            expected_mode: expected_mode.to_string(),
            input_bytes: data.len(),
            input_sha256,
            frame_bytes: frame.len(),
            frame_sha256,
            encode_ns,
            decode_ns,
            decoded_sha256,
            roundtrip_exact,
        })
        .map_err(|error| format!("serialize trial: {error}"))?
    );
    Ok(())
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: memory_rss_probe prepare MANIFEST\n       memory_rss_probe trial PAYLOAD MODE INPUT_SHA FRAME_SHA SAMPLE_ID"
    );
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = match args.as_slice() {
        [command, manifest] if command == "prepare" => prepare(manifest),
        [command, payload, mode_name, input_sha, frame_sha, sample_id] if command == "trial" => {
            trial(payload, mode_name, input_sha, frame_sha, sample_id)
        }
        _ => return usage(),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
