//! In-process Phase-A ladder probe for CUBR-0075.
//!
//! The existing resource runner measures a subprocess protocol over a fixed
//! real-world corpus.  That is the wrong clock for the CUBR-0075 size ladders:
//! at the 4--64 KiB cube sizes, process startup would dominate the decoder.
//! This probe encodes each manifest sample once, then measures the library
//! `decode` call in-process while retaining a byte-exact check for every trial.
//!
//! Usage:
//!
//!   hypothesis_probe measure MANIFEST TRIALS WARMUPS SEED
//!
//! The manifest is a JSON object with a `samples` array.  Each sample contains
//! `sample_id`, `path`, and `expected_mode`.  The probe deliberately does not
//! assign a verdict; the Python evaluator owns the preregistered statistics and
//! thresholds.

use cubrim::config::EncodeConfig;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::process::ExitCode;
use std::time::Instant;

const MODE_OFFSET: usize = 5;

#[derive(Debug, Deserialize)]
struct Manifest {
    samples: Vec<ManifestSample>,
}

#[derive(Debug, Deserialize)]
struct ManifestSample {
    sample_id: String,
    path: String,
    expected_mode: String,
    #[serde(default)]
    input_sha256: Option<String>,
}

#[derive(Debug, Serialize)]
struct Trial {
    trial_no: usize,
    randomized_order: usize,
    decode_ns: u128,
    decoded_sha256: String,
    roundtrip_exact: bool,
}

#[derive(Debug, Serialize)]
struct SampleResult {
    sample_id: String,
    path: String,
    expected_mode: String,
    encoder_path: String,
    mode: String,
    input_bytes: usize,
    input_sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
    trials: Vec<Trial>,
}

#[derive(Debug, Serialize)]
struct ProbeOutput {
    schema_version: u32,
    codec_key: &'static str,
    codec_version: &'static str,
    trials_per_cell: usize,
    warmups: usize,
    seed: u64,
    samples: Vec<SampleResult>,
}

struct LoadedSample {
    manifest: ManifestSample,
    data: Vec<u8>,
    frame: Vec<u8>,
    input_sha256: String,
    frame_sha256: String,
    mode: String,
    encoder_path: String,
}

/// Small deterministic generator used only for the randomized measurement
/// schedule.  The seed is part of the output, so the schedule is replayable.
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
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn raw_store_frame(data: &[u8]) -> Result<Vec<u8>, String> {
    let length = u32::try_from(data.len())
        .map_err(|_| format!("raw-store sample is too large for v1: {} bytes", data.len()))?;
    let mut frame = Vec::with_capacity(13 + data.len());
    frame.extend_from_slice(&cubrim::header::MAGIC);
    frame.push(cubrim::header::VERSION);
    frame.push(cubrim::header::MODE_RAW);
    frame.push(2); // raw-store metadata is not used by the decoder
    frame.extend_from_slice(&256u16.to_be_bytes());
    frame.extend_from_slice(&length.to_be_bytes());
    frame.extend_from_slice(data);
    Ok(frame)
}

fn build_frame(data: &[u8], expected_mode: &str) -> Result<(Vec<u8>, &'static str), String> {
    match expected_mode {
        "cube" => Ok((
            cubrim::codec::encode_base(data, &EncodeConfig::v1_default()),
            "cubrim-file-v1/base-cube-raw",
        )),
        "raw_store" => Ok((raw_store_frame(data)?, "cubrim-file-v1/raw-store-wire")),
        other => Err(format!("unsupported hypothesis mode {other}")),
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

fn usage() -> ExitCode {
    eprintln!("usage: hypothesis_probe measure MANIFEST TRIALS WARMUPS SEED");
    ExitCode::from(2)
}

fn measure(manifest_path: &str, trials: usize, warmups: usize, seed: u64) -> Result<(), String> {
    if trials < 30 {
        return Err("CUBR-0075 requires at least 30 measured trials per cell".into());
    }
    if warmups != 3 {
        return Err("CUBR-0075 requires exactly 3 warmups per cell".into());
    }

    let manifest_bytes = fs::read(manifest_path)
        .map_err(|error| format!("read manifest {manifest_path}: {error}"))?;
    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("parse manifest {manifest_path}: {error}"))?;
    if manifest.samples.is_empty() {
        return Err("measurement manifest must contain at least one sample".into());
    }

    let mut samples = Vec::with_capacity(manifest.samples.len());
    for sample in manifest.samples {
        let data =
            fs::read(&sample.path).map_err(|error| format!("read {}: {error}", sample.path))?;
        let expected_input_sha256 = sample.input_sha256.clone();
        let input_sha256 = sha256(&data);
        if expected_input_sha256
            .as_deref()
            .is_some_and(|expected| expected != input_sha256)
        {
            return Err(format!(
                "{} input SHA-256 does not match the manifest",
                sample.sample_id
            ));
        }
        let (frame, encoder_path) = build_frame(&data, &sample.expected_mode)?;
        let actual_mode = mode(&frame)?;
        if actual_mode != sample.expected_mode {
            return Err(format!(
                "{} expected mode {}, encoder produced {}",
                sample.sample_id, sample.expected_mode, actual_mode
            ));
        }
        let decoded = cubrim::decode(&frame)
            .map_err(|error| format!("{} preflight decode failed: {error}", sample.sample_id))?;
        if decoded != data {
            return Err(format!(
                "{} failed the preflight exact round trip",
                sample.sample_id
            ));
        }
        samples.push(LoadedSample {
            manifest: sample,
            input_sha256,
            frame_sha256: sha256(&frame),
            data,
            frame,
            mode: actual_mode.to_string(),
            encoder_path: encoder_path.to_string(),
        });
    }

    // Warm every cell before the first timed observation.  These calls are
    // intentionally not included in the result.
    for _ in 0..warmups {
        for sample in &samples {
            let decoded = cubrim::decode(&sample.frame)
                .map_err(|error| format!("warmup decode failed: {error}"))?;
            if decoded != sample.data {
                return Err("warmup round trip was not exact".into());
            }
        }
    }

    let mut trial_rows: Vec<Vec<Trial>> =
        samples.iter().map(|_| Vec::with_capacity(trials)).collect();
    let mut rng = Lcg(seed);
    for trial_no in 1..=trials {
        let mut order: Vec<usize> = (0..samples.len()).collect();
        for index in (1..order.len()).rev() {
            let swap = (rng.next() as usize) % (index + 1);
            order.swap(index, swap);
        }
        for (position, sample_index) in order.into_iter().enumerate() {
            let sample = &samples[sample_index];
            let start = Instant::now();
            let decoded = cubrim::decode(&sample.frame).map_err(|error| {
                format!("{} trial decode failed: {error}", sample.manifest.sample_id)
            })?;
            let decode_ns = start.elapsed().as_nanos();
            let decoded_sha256 = sha256(&decoded);
            let roundtrip_exact = decoded == sample.data;
            if !roundtrip_exact || decoded_sha256 != sample.input_sha256 {
                return Err(format!(
                    "{} trial {trial_no} failed the exact round-trip check",
                    sample.manifest.sample_id
                ));
            }
            trial_rows[sample_index].push(Trial {
                trial_no,
                randomized_order: position + 1,
                decode_ns,
                decoded_sha256,
                roundtrip_exact,
            });
        }
    }

    let output = ProbeOutput {
        schema_version: 1,
        codec_key: "cubrim-file-v1",
        codec_version: env!("CARGO_PKG_VERSION"),
        trials_per_cell: trials,
        warmups,
        seed,
        samples: samples
            .into_iter()
            .zip(trial_rows)
            .map(|(sample, trials)| SampleResult {
                sample_id: sample.manifest.sample_id,
                path: sample.manifest.path,
                expected_mode: sample.manifest.expected_mode,
                encoder_path: sample.encoder_path,
                mode: sample.mode,
                input_bytes: sample.data.len(),
                input_sha256: sample.input_sha256,
                frame_bytes: sample.frame.len(),
                frame_sha256: sample.frame_sha256,
                trials,
            })
            .collect(),
    };
    println!(
        "{}",
        serde_json::to_string(&output).map_err(|error| format!("serialize output: {error}"))?
    );
    Ok(())
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
    match measure(&args[1], trials, warmups, seed) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
