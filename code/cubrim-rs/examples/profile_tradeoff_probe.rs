//! Source-bound probe for the CUBR-0075 static/dynamic profile comparison.
//!
//! The probe measures both Web Profile entry points against the same corpus in
//! one randomized schedule. It builds each frame once as an immutable content
//! address, then re-encodes and decodes it for every measured trial. Any byte,
//! mode, or round-trip drift aborts the run instead of producing partial
//! evidence.
//!
//! Usage:
//!   profile_tradeoff_probe measure <manifest.json> <trials> <warmups> <seed>

use cubrim::config::EncodeConfig;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::Path;
use std::process::ExitCode;
use std::time::Instant;

const BLOCK_SIZE: usize = 65_536;
const MODE_OFFSET: usize = 5;

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    samples: Vec<ManifestSample>,
}

#[derive(Debug, Deserialize, Clone)]
struct ManifestSample {
    sample_id: String,
    path: String,
    sha256: String,
    byte_count: usize,
}

#[derive(Debug, Serialize)]
struct Trial {
    trial_no: usize,
    randomized_order: usize,
    encode_ns: u128,
    decode_ns: u128,
    frame_sha256: String,
    decoded_sha256: String,
    roundtrip_exact: bool,
}

#[derive(Debug, Serialize)]
struct ProfileResult {
    frame_bytes: usize,
    frame_sha256: String,
    mode: String,
    trials: Vec<Trial>,
}

#[derive(Debug, Serialize)]
struct SampleResult {
    sample_id: String,
    path: String,
    input_bytes: usize,
    input_sha256: String,
    static_profile: ProfileResult,
    dynamic_profile: ProfileResult,
}

#[derive(Debug, Serialize)]
struct ProbeOutput {
    schema_version: u32,
    corpus_manifest_schema_version: u32,
    block_size: usize,
    trials_per_cell: usize,
    warmups: usize,
    seed: u64,
    samples: Vec<SampleResult>,
}

struct LoadedSample {
    manifest: ManifestSample,
    data: Vec<u8>,
    input_sha256: String,
    static_frame: Vec<u8>,
    dynamic_frame: Vec<u8>,
    static_sha256: String,
    dynamic_sha256: String,
    static_mode: String,
    dynamic_mode: String,
}

struct Lcg(u64);

impl Lcg {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        self.0 >> 16
    }
}

fn sha256(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn mode(frame: &[u8]) -> Result<String, String> {
    match frame.get(MODE_OFFSET).copied() {
        Some(cubrim::header::MODE_WEB) => Ok("web".into()),
        Some(cubrim::header::MODE_RAW) => Ok("raw_store".into()),
        Some(other) => Ok(format!("mode-{other}")),
        None => Err("frame is too short to carry a mode".into()),
    }
}

fn static_frame(data: &[u8]) -> Vec<u8> {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = Some(BLOCK_SIZE);
    cubrim::encode_with_config(data, &config)
}

fn dynamic_frame(data: &[u8]) -> Result<Vec<u8>, String> {
    cubrim::encode_web_dynamic(data, Some(BLOCK_SIZE))
        .ok_or_else(|| "dynamic encoder returned no frame".into())
}

fn load_samples(manifest_path: &Path) -> Result<(Manifest, Vec<LoadedSample>), String> {
    let manifest_bytes = fs::read(manifest_path)
        .map_err(|error| format!("read manifest {}: {error}", manifest_path.display()))?;
    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("parse manifest: {error}"))?;
    if manifest.schema_version != 2 {
        return Err(format!(
            "expected manifest.v3 corpus schema 2, got {}",
            manifest.schema_version
        ));
    }
    if manifest.samples.is_empty() {
        return Err("profile manifest is empty".into());
    }
    let root = manifest_path
        .parent()
        .ok_or_else(|| "manifest has no parent directory".to_string())?;
    let mut loaded = Vec::with_capacity(manifest.samples.len());
    for sample in &manifest.samples {
        let path = root.join(&sample.path);
        let data = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
        if data.len() != sample.byte_count {
            return Err(format!(
                "{} byte count {} != manifest {}",
                sample.sample_id,
                data.len(),
                sample.byte_count
            ));
        }
        let input_sha256 = sha256(&data);
        if input_sha256 != sample.sha256 {
            return Err(format!(
                "{} input SHA-256 differs from manifest",
                sample.sample_id
            ));
        }
        let static_frame = static_frame(&data);
        let dynamic_frame = dynamic_frame(&data)?;
        let static_mode = mode(&static_frame)?;
        let dynamic_mode = mode(&dynamic_frame)?;
        let static_decoded = cubrim::decode(&static_frame)
            .map_err(|error| format!("{} static preflight decode: {error}", sample.sample_id))?;
        let dynamic_decoded = cubrim::decode(&dynamic_frame)
            .map_err(|error| format!("{} dynamic preflight decode: {error}", sample.sample_id))?;
        if static_decoded != data || dynamic_decoded != data {
            return Err(format!(
                "{} failed a profile preflight round trip",
                sample.sample_id
            ));
        }
        loaded.push(LoadedSample {
            manifest: sample.clone(),
            data,
            input_sha256,
            static_sha256: sha256(&static_frame),
            dynamic_sha256: sha256(&dynamic_frame),
            static_mode,
            dynamic_mode,
            static_frame,
            dynamic_frame,
        });
    }
    Ok((manifest, loaded))
}

fn measure(manifest_path: &Path, trials: usize, warmups: usize, seed: u64) -> Result<(), String> {
    if trials != 30 {
        return Err("profile-tradeoff requires exactly 30 measured trials per cell".into());
    }
    if warmups != 3 {
        return Err("profile-tradeoff requires exactly 3 warmups per cell".into());
    }
    let (manifest, samples) = load_samples(manifest_path)?;
    let mut operations = Vec::with_capacity(samples.len() * 2);
    for sample_index in 0..samples.len() {
        operations.push((sample_index, false));
        operations.push((sample_index, true));
    }

    for _ in 0..warmups {
        for &(sample_index, dynamic) in &operations {
            let sample = &samples[sample_index];
            let frame = if dynamic {
                &sample.dynamic_frame
            } else {
                &sample.static_frame
            };
            let decoded =
                cubrim::decode(frame).map_err(|error| format!("warmup decode: {error}"))?;
            if decoded != sample.data {
                return Err(format!(
                    "{} warmup round trip failed",
                    sample.manifest.sample_id
                ));
            }
        }
    }

    let mut static_trials: Vec<Vec<Trial>> =
        samples.iter().map(|_| Vec::with_capacity(trials)).collect();
    let mut dynamic_trials: Vec<Vec<Trial>> =
        samples.iter().map(|_| Vec::with_capacity(trials)).collect();
    let mut rng = Lcg(seed);
    for trial_no in 1..=trials {
        let mut order: Vec<usize> = (0..operations.len()).collect();
        for index in (1..order.len()).rev() {
            let swap = (rng.next() as usize) % (index + 1);
            order.swap(index, swap);
        }
        for (position, operation_index) in order.into_iter().enumerate() {
            let (sample_index, dynamic) = operations[operation_index];
            let sample = &samples[sample_index];
            let expected_frame = if dynamic {
                &sample.dynamic_frame
            } else {
                &sample.static_frame
            };
            let expected_sha256 = if dynamic {
                &sample.dynamic_sha256
            } else {
                &sample.static_sha256
            };
            let encoded = if dynamic {
                dynamic_frame(&sample.data)?
            } else {
                static_frame(&sample.data)
            };
            if encoded.as_slice() != expected_frame.as_slice()
                || sha256(&encoded) != *expected_sha256
            {
                return Err(format!(
                    "{} {} frame changed during trial {trial_no}",
                    sample.manifest.sample_id,
                    if dynamic { "dynamic" } else { "static" }
                ));
            }
            let encode_start = Instant::now();
            let encoded_again = if dynamic {
                dynamic_frame(&sample.data)?
            } else {
                static_frame(&sample.data)
            };
            let encode_ns = encode_start.elapsed().as_nanos();
            if encoded_again.as_slice() != expected_frame.as_slice() {
                return Err(format!(
                    "{} {} encode is not deterministic",
                    sample.manifest.sample_id,
                    if dynamic { "dynamic" } else { "static" }
                ));
            }
            let decode_start = Instant::now();
            let decoded = cubrim::decode(expected_frame).map_err(|error| {
                format!(
                    "{} {} decode: {error}",
                    sample.manifest.sample_id,
                    if dynamic { "dynamic" } else { "static" }
                )
            })?;
            let decode_ns = decode_start.elapsed().as_nanos();
            let decoded_sha256 = sha256(&decoded);
            let roundtrip_exact = decoded == sample.data && decoded_sha256 == sample.input_sha256;
            if !roundtrip_exact {
                return Err(format!(
                    "{} {} trial round trip failed",
                    sample.manifest.sample_id,
                    if dynamic { "dynamic" } else { "static" }
                ));
            }
            let row = Trial {
                trial_no,
                randomized_order: position + 1,
                encode_ns,
                decode_ns,
                frame_sha256: expected_sha256.clone(),
                decoded_sha256,
                roundtrip_exact,
            };
            if dynamic {
                dynamic_trials[sample_index].push(row);
            } else {
                static_trials[sample_index].push(row);
            }
        }
    }

    let results = samples
        .into_iter()
        .zip(static_trials.into_iter().zip(dynamic_trials))
        .map(|(sample, (static_trials, dynamic_trials))| SampleResult {
            sample_id: sample.manifest.sample_id,
            path: sample.manifest.path,
            input_bytes: sample.data.len(),
            input_sha256: sample.input_sha256,
            static_profile: ProfileResult {
                frame_bytes: sample.static_frame.len(),
                frame_sha256: sample.static_sha256,
                mode: sample.static_mode,
                trials: static_trials,
            },
            dynamic_profile: ProfileResult {
                frame_bytes: sample.dynamic_frame.len(),
                frame_sha256: sample.dynamic_sha256,
                mode: sample.dynamic_mode,
                trials: dynamic_trials,
            },
        })
        .collect();
    let output = ProbeOutput {
        schema_version: 1,
        corpus_manifest_schema_version: manifest.schema_version,
        block_size: BLOCK_SIZE,
        trials_per_cell: trials,
        warmups,
        seed,
        samples: results,
    };
    println!(
        "{}",
        serde_json::to_string(&output).map_err(|error| format!("serialize output: {error}"))?
    );
    Ok(())
}

fn usage() -> ExitCode {
    eprintln!("usage: profile_tradeoff_probe measure <manifest.json> <trials> <warmups> <seed>");
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() != 5 || args[0] != "measure" {
        return usage();
    }
    let trials = match args[2].parse() {
        Ok(value) => value,
        Err(_) => {
            eprintln!("trials must be an integer");
            return ExitCode::from(2);
        }
    };
    let warmups = match args[3].parse() {
        Ok(value) => value,
        Err(_) => {
            eprintln!("warmups must be an integer");
            return ExitCode::from(2);
        }
    };
    let seed = match args[4].parse() {
        Ok(value) => value,
        Err(_) => {
            eprintln!("seed must be an integer");
            return ExitCode::from(2);
        }
    };
    match measure(Path::new(&args[1]), trials, warmups, seed) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("profile-tradeoff measurement void: {error}");
            ExitCode::FAILURE
        }
    }
}
