//! Source-bound probe for the CUBR-0075 hostile/truncated-input gate.
//!
//! The Python runner owns containment, host admission, repeated trials, and
//! the preregistered time/RSS decision. This binary owns only deterministic
//! payload/frame construction and one valid decode plus the scheduled invalid
//! cases. Every hostile case is a proper prefix or a header mutation of the
//! content-addressed valid frame; no arbitrary success is treated as an error.

use cubrim::config::EncodeConfig;
use cubrim::CubrimError;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::Instant;

const MODE_OFFSET: usize = 5;
const MAGIC_LEN: usize = 4;

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    samples: Vec<ManifestSample>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
struct ManifestSample {
    sample_id: String,
    family: String,
    path: String,
    input_bytes: usize,
    input_sha256: String,
}

#[derive(Debug, Serialize)]
struct PreparedManifest {
    schema_version: u32,
    case_schedule: String,
    samples: Vec<PreparedSample>,
}

#[derive(Debug, Serialize)]
struct PreparedSample {
    sample_id: String,
    family: String,
    path: String,
    input_bytes: usize,
    input_sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
    mode: String,
    case_count: usize,
    proper_prefix_count: usize,
    case_ids: Vec<String>,
}

#[derive(Debug, Clone)]
struct HostileCase {
    case_id: String,
    kind: String,
    bytes: Vec<u8>,
}

#[derive(Debug, Serialize)]
struct CaseObservation {
    case_id: String,
    kind: String,
    input_bytes: usize,
    input_sha256: String,
    duration_ns: u128,
    outcome: String,
    error_kind: Option<String>,
    panic: bool,
}

#[derive(Debug, Serialize)]
struct TrialOutput {
    schema_version: u32,
    sample_id: String,
    family: String,
    input_bytes: usize,
    input_sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
    mode: String,
    trial_no: usize,
    randomized_order: Vec<String>,
    encode_ns: u128,
    valid_decode_ns: u128,
    valid_roundtrip_exact: bool,
    cases: Vec<CaseObservation>,
}

fn sha256(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
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

fn allowed_family(family: &str) -> bool {
    matches!(
        family,
        "structured_text" | "structured_json" | "high_entropy"
    )
}

fn mode(frame: &[u8]) -> Result<String, String> {
    match frame.get(MODE_OFFSET).copied() {
        Some(cubrim::header::MODE_CUBE) => Ok("cube".into()),
        Some(cubrim::header::MODE_RAW) => Ok("raw_store".into()),
        Some(cubrim::header::MODE_WEB) => Ok("web".into()),
        Some(other) => Ok(format!("mode-{other}")),
        None => Err("frame is too short to carry a mode".into()),
    }
}

fn build_frame(data: &[u8]) -> Vec<u8> {
    cubrim::codec::encode_base(data, &EncodeConfig::v1_default())
}

fn proper_prefix_lengths(frame_len: usize) -> Vec<usize> {
    let candidates = [
        0,
        1,
        MAGIC_LEN - 1,
        MODE_OFFSET,
        13,
        frame_len / 2,
        frame_len - 1,
    ];
    let mut lengths = Vec::new();
    for length in candidates {
        if length < frame_len && !lengths.contains(&length) {
            lengths.push(length);
        }
    }
    lengths
}

fn hostile_cases(frame: &[u8]) -> Result<Vec<HostileCase>, String> {
    if frame.len() <= 13 {
        return Err("valid frame is too short for the hostile schedule".into());
    }
    let mut cases = Vec::new();
    for (index, length) in proper_prefix_lengths(frame.len()).into_iter().enumerate() {
        cases.push(HostileCase {
            case_id: format!("prefix-{index:02}"),
            kind: "proper_prefix".into(),
            bytes: frame[..length].to_vec(),
        });
    }

    let mut magic = frame.to_vec();
    magic[0] ^= 0x01;
    cases.push(HostileCase {
        case_id: "mutation-magic".into(),
        kind: "header_mutation".into(),
        bytes: magic,
    });

    let mut version = frame.to_vec();
    version[4] = 0xff;
    cases.push(HostileCase {
        case_id: "mutation-version".into(),
        kind: "header_mutation".into(),
        bytes: version,
    });

    let mut frame_mode = frame.to_vec();
    frame_mode[MODE_OFFSET] = 0xff;
    cases.push(HostileCase {
        case_id: "mutation-mode".into(),
        kind: "header_mutation".into(),
        bytes: frame_mode,
    });
    Ok(cases)
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
        return Err("hostile manifest must contain at least one sample".into());
    }
    for sample in &manifest.samples {
        if !allowed_family(&sample.family) {
            return Err(format!("{} has an unknown media family", sample.sample_id));
        }
    }
    Ok(manifest)
}

fn load_frame(sample: &ManifestSample, manifest_path: &str) -> Result<(Vec<u8>, Vec<u8>), String> {
    let payload_path = resolve_manifest_path(manifest_path, &sample.path);
    let data = fs::read(&payload_path)
        .map_err(|error| format!("read {}: {error}", payload_path.display()))?;
    if data.len() != sample.input_bytes || sha256(&data) != sample.input_sha256 {
        return Err(format!(
            "{} input metadata does not match payload",
            sample.sample_id
        ));
    }
    let frame = build_frame(&data);
    let decoded = cubrim::decode(&frame).map_err(|error| {
        format!(
            "{} valid preflight decode failed: {error}",
            sample.sample_id
        )
    })?;
    if decoded != data {
        return Err(format!(
            "{} valid preflight round trip was not exact",
            sample.sample_id
        ));
    }
    Ok((data, frame))
}

fn prepare(manifest_path: &str) -> Result<(), String> {
    let manifest = read_manifest(manifest_path)?;
    let mut samples = Vec::with_capacity(manifest.samples.len());
    for sample in manifest.samples {
        let (data, frame) = load_frame(&sample, manifest_path)?;
        let cases = hostile_cases(&frame)?;
        let proper_prefix_count = cases
            .iter()
            .filter(|case| case.kind == "proper_prefix")
            .count();
        let case_ids = cases.iter().map(|case| case.case_id.clone()).collect();
        samples.push(PreparedSample {
            sample_id: sample.sample_id,
            family: sample.family,
            path: sample.path,
            input_bytes: data.len(),
            input_sha256: sha256(&data),
            frame_bytes: frame.len(),
            frame_sha256: sha256(&frame),
            mode: mode(&frame)?,
            case_count: cases.len(),
            proper_prefix_count,
            case_ids,
        });
    }
    println!(
        "{}",
        serde_json::to_string(&PreparedManifest {
            schema_version: 1,
            case_schedule: "proper prefixes at deterministic boundaries plus magic/version/mode header mutations".into(),
            samples,
        })
        .map_err(|error| format!("serialize prepared manifest: {error}"))?
    );
    Ok(())
}

fn error_kind(error: &CubrimError) -> &'static str {
    match error {
        CubrimError::InvalidMagic(_) => "invalid_magic",
        CubrimError::UnsupportedVersion(_) => "unsupported_version",
        CubrimError::GapInvariant(_) => "gap_invariant",
        CubrimError::Decode(_) => "decode",
        CubrimError::ResourceLimit(_) => "resource_limit",
        CubrimError::Io(_) => "io",
    }
}

fn shuffle_cases(mut cases: Vec<HostileCase>, seed: u64) -> Vec<HostileCase> {
    let mut state = seed | 1;
    for index in (1..cases.len()).rev() {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        let swap = ((state >> 16) as usize) % (index + 1);
        cases.swap(index, swap);
    }
    cases
}

fn observe_case(case: HostileCase) -> CaseObservation {
    let input_bytes = case.bytes.len();
    let input_sha256 = sha256(&case.bytes);
    let started = Instant::now();
    let result = catch_unwind(AssertUnwindSafe(|| cubrim::decode(&case.bytes)));
    let duration_ns = started.elapsed().as_nanos();
    match result {
        Ok(Ok(_decoded)) => CaseObservation {
            case_id: case.case_id,
            kind: case.kind,
            input_bytes,
            input_sha256,
            duration_ns,
            outcome: "accepted".into(),
            error_kind: None,
            panic: false,
        },
        Ok(Err(error)) => CaseObservation {
            case_id: case.case_id,
            kind: case.kind,
            input_bytes,
            input_sha256,
            duration_ns,
            outcome: "error".into(),
            error_kind: Some(error_kind(&error).into()),
            panic: false,
        },
        Err(_) => CaseObservation {
            case_id: case.case_id,
            kind: case.kind,
            input_bytes,
            input_sha256,
            duration_ns,
            outcome: "panic".into(),
            error_kind: None,
            panic: true,
        },
    }
}

struct TrialRequest<'a> {
    payload_path: &'a str,
    family: &'a str,
    expected_input_bytes: usize,
    expected_input_sha256: &'a str,
    expected_frame_sha256: &'a str,
    sample_id: &'a str,
    trial_no: usize,
    seed: u64,
}

fn trial(request: TrialRequest<'_>) -> Result<(), String> {
    let TrialRequest {
        payload_path,
        family,
        expected_input_bytes,
        expected_input_sha256,
        expected_frame_sha256,
        sample_id,
        trial_no,
        seed,
    } = request;
    let data = fs::read(payload_path).map_err(|error| format!("read {payload_path}: {error}"))?;
    if data.len() != expected_input_bytes || sha256(&data) != expected_input_sha256 {
        return Err(format!("{sample_id} input metadata changed before trial"));
    }
    let encode_started = Instant::now();
    let frame = build_frame(&data);
    let encode_ns = encode_started.elapsed().as_nanos();
    let frame_sha256 = sha256(&frame);
    if frame_sha256 != expected_frame_sha256 {
        return Err(format!("{sample_id} frame SHA-256 changed before trial"));
    }
    let valid_started = Instant::now();
    let decoded =
        cubrim::decode(&frame).map_err(|error| format!("valid decode failed: {error}"))?;
    let valid_decode_ns = valid_started.elapsed().as_nanos();
    let valid_roundtrip_exact = decoded == data && sha256(&decoded) == expected_input_sha256;
    if !valid_roundtrip_exact {
        return Err(format!(
            "{sample_id} valid trial failed the exact round-trip gate"
        ));
    }

    let cases = shuffle_cases(hostile_cases(&frame)?, seed ^ trial_no as u64);
    let randomized_order = cases.iter().map(|case| case.case_id.clone()).collect();
    let observations = cases.into_iter().map(observe_case).collect();
    println!(
        "{}",
        serde_json::to_string(&TrialOutput {
            schema_version: 1,
            sample_id: sample_id.to_string(),
            family: family.to_string(),
            input_bytes: data.len(),
            input_sha256: expected_input_sha256.to_string(),
            frame_bytes: frame.len(),
            frame_sha256,
            mode: mode(&frame)?,
            trial_no,
            randomized_order,
            encode_ns,
            valid_decode_ns,
            valid_roundtrip_exact,
            cases: observations,
        })
        .map_err(|error| format!("serialize trial: {error}"))?
    );
    Ok(())
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: hostile_truncated_probe prepare MANIFEST\n       hostile_truncated_probe trial PAYLOAD FAMILY BYTES INPUT_SHA FRAME_SHA SAMPLE_ID TRIAL_NO SEED"
    );
    ExitCode::from(2)
}

fn main() -> ExitCode {
    std::panic::set_hook(Box::new(|_| {}));
    let args: Vec<String> = env::args().skip(1).collect();
    let result = match args.as_slice() {
        [command, manifest] if command == "prepare" => prepare(manifest),
        [command, payload, family, bytes, input_sha, frame_sha, sample_id, trial_no, seed]
            if command == "trial" =>
        {
            let input_bytes = bytes
                .parse::<usize>()
                .map_err(|_| "invalid input byte count".to_string());
            let trial_no = trial_no
                .parse::<usize>()
                .map_err(|_| "invalid trial number".to_string());
            let seed = seed
                .parse::<u64>()
                .map_err(|_| "invalid trial seed".to_string());
            match (input_bytes, trial_no, seed) {
                (Ok(input_bytes), Ok(trial_no), Ok(seed)) => trial(TrialRequest {
                    payload_path: payload,
                    family,
                    expected_input_bytes: input_bytes,
                    expected_input_sha256: input_sha,
                    expected_frame_sha256: frame_sha,
                    sample_id,
                    trial_no,
                    seed,
                }),
                (Err(error), _, _) | (_, Err(error), _) | (_, _, Err(error)) => Err(error),
            }
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
