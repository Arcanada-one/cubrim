//! CUBR-0075 streaming/first-output measurement probe.
//!
//! This is an opt-in measurement binary, not part of the shipped decoder. It
//! drives the public `StreamDecoder` API directly, handing every fresh output
//! window to a small independent digest sink. The probe therefore measures
//! the API-to-sink handoff, rather than pretending that a whole-buffer decode
//! is incremental.

use cubrim::config::EncodeConfig;
use cubrim_web_decoder::{decode, DecodeLimits, StreamDecoder};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;

const BLOCK_SIZE: usize = 65_536;
const CHUNK_SIZE: usize = 4_096;
const WARMUPS: usize = 3;
const TRIALS: usize = 30;
const SEED: u64 = 75_075;
const SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Deserialize)]
struct Manifest {
    corpus_key: String,
    samples: Vec<ManifestSample>,
}

#[derive(Debug, Clone, Deserialize)]
struct ManifestSample {
    sample_id: String,
    path: String,
    byte_count: usize,
    sha256: String,
}

#[derive(Debug, Serialize)]
struct Run {
    schema_version: u32,
    task_id: &'static str,
    status: &'static str,
    corpus_key: String,
    sample_count: usize,
    mode_count: usize,
    warmups_per_cell: usize,
    measured_trials_per_cell: usize,
    block_size: usize,
    input_chunk_size: usize,
    schedule_seed: u64,
    provenance: Provenance,
    trials: Vec<Trial>,
}

#[derive(Debug, Serialize)]
struct Provenance {
    source_commit: String,
    probe_source_sha256: String,
    probe_binary_sha256: String,
    runner_sha256: String,
    prereg_sha256: String,
    manifest_sha256: String,
    host: String,
    arch: &'static str,
    cpu_affinity: String,
    rustc: String,
}

#[derive(Debug, Serialize)]
struct Trial {
    sample_id: String,
    sample_path: String,
    mode: &'static str,
    trial_index: usize,
    warmup: bool,
    input_bytes: usize,
    frame_bytes: usize,
    input_sha256: String,
    expected_output_sha256: String,
    output_sha256: Option<String>,
    output_bytes: usize,
    output_events: usize,
    first_output_latency_ns: Option<u64>,
    first_output_input_bytes: Option<usize>,
    first_output_before_eof: bool,
    last_input_latency_ns: Option<u64>,
    output_complete_latency_ns: Option<u64>,
    finish_ok: bool,
    roundtrip_exact: bool,
    sink_exact: bool,
    status: &'static str,
    error: Option<String>,
}

struct DigestSink {
    hasher: Sha256,
    bytes: usize,
}

impl DigestSink {
    fn new() -> Self {
        Self {
            hasher: Sha256::new(),
            bytes: 0,
        }
    }

    fn write(&mut self, bytes: &[u8]) -> Result<(), String> {
        self.bytes = self
            .bytes
            .checked_add(bytes.len())
            .ok_or_else(|| "sink byte-count overflow".to_string())?;
        self.hasher.update(bytes);
        Ok(())
    }

    fn finish(self) -> (usize, String) {
        (self.bytes, hex_digest(self.hasher.finalize().as_slice()))
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("streaming-first-output probe: {error}");
        std::process::exit(2);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    let corpus_root = args
        .next()
        .map(PathBuf::from)
        .ok_or_else(|| "usage: probe <corpus-root> <output-json>".to_string())?;
    let output_path = args
        .next()
        .map(PathBuf::from)
        .ok_or_else(|| "usage: probe <corpus-root> <output-json>".to_string())?;
    if args.next().is_some() {
        return Err("usage: probe <corpus-root> <output-json>".to_string());
    }

    let manifest_path = corpus_root.join("manifest.v3.json");
    let manifest_bytes = fs::read(&manifest_path)
        .map_err(|error| format!("read {}: {error}", manifest_path.display()))?;
    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("parse {}: {error}", manifest_path.display()))?;
    if manifest.samples.len() != 13 {
        return Err(format!(
            "manifest has {} samples, expected 13",
            manifest.samples.len()
        ));
    }

    let mut samples = Vec::with_capacity(manifest.samples.len());
    for sample in &manifest.samples {
        let path = corpus_root.join(&sample.path);
        let bytes = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
        if bytes.len() != sample.byte_count {
            return Err(format!(
                "{}: byte count {} != manifest {}",
                sample.sample_id,
                bytes.len(),
                sample.byte_count
            ));
        }
        let digest = sha256(&bytes);
        if digest != sample.sha256 {
            return Err(format!(
                "{}: SHA-256 {} != manifest {}",
                sample.sample_id, digest, sample.sha256
            ));
        }
        let mut config = EncodeConfig::v1_default();
        config.web_profile = true;
        config.web_block_size = Some(BLOCK_SIZE);
        let frame = cubrim::encode_with_config(&bytes, &config);
        if frame.len() < 6 || (frame[5] != 18 && frame[5] != 1) {
            return Err(format!(
                "{}: encoder returned an unknown frame mode",
                sample.sample_id
            ));
        }
        samples.push((sample.clone(), bytes, frame));
    }

    let mut cells: Vec<(usize, &'static str)> = samples
        .iter()
        .enumerate()
        .flat_map(|(index, _)| [(index, "streaming"), (index, "whole_buffer")])
        .collect();
    shuffle(&mut cells, SEED);

    let mut trials = Vec::with_capacity(cells.len() * (WARMUPS + TRIALS));
    for (sample_index, mode) in cells {
        let (sample, original, frame) = &samples[sample_index];
        for trial_index in 0..(WARMUPS + TRIALS) {
            let warmup = trial_index < WARMUPS;
            let trial_number = if warmup {
                trial_index + 1
            } else {
                trial_index - WARMUPS + 1
            };
            let trial = if mode == "streaming" {
                stream_trial(sample, original, frame, trial_number, warmup)
            } else {
                whole_buffer_trial(sample, original, frame, trial_number, warmup)
            };
            if !warmup && trial.status != "valid" {
                trials.push(trial);
                return write_run(&output_path, manifest, manifest_bytes, trials, "VOID");
            }
            trials.push(trial);
        }
    }

    write_run(&output_path, manifest, manifest_bytes, trials, "COMPLETE")
}

fn stream_trial(
    sample: &ManifestSample,
    original: &[u8],
    frame: &[u8],
    trial_index: usize,
    warmup: bool,
) -> Trial {
    let started = Instant::now();
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let mut sink = DigestSink::new();
    let mut first_output_latency_ns = None;
    let mut first_output_input_bytes = None;
    let mut last_input_latency_ns = None;
    let mut output_events = 0;
    let mut offset = 0;

    while offset < frame.len() {
        let end = (offset + CHUNK_SIZE).min(frame.len());
        let fresh = match stream.push(&frame[offset..end]) {
            Ok(fresh) => fresh,
            Err(error) => {
                return invalid_trial(
                    sample,
                    frame,
                    "streaming",
                    trial_index,
                    warmup,
                    format!("push rejected input: {}", error.message()),
                )
            }
        };
        offset = end;
        if offset == frame.len() {
            last_input_latency_ns = Some(elapsed_ns(&started));
        }
        if !fresh.is_empty() {
            output_events += 1;
            if first_output_latency_ns.is_none() {
                first_output_latency_ns = Some(elapsed_ns(&started));
                first_output_input_bytes = Some(offset);
            }
            if let Err(error) = sink.write(fresh) {
                return invalid_trial(sample, frame, "streaming", trial_index, warmup, error);
            }
        }
    }

    let complete = match stream.finish() {
        Ok(complete) => complete,
        Err(error) => {
            return invalid_trial(
                sample,
                frame,
                "streaming",
                trial_index,
                warmup,
                format!("finish rejected complete frame: {}", error.message()),
            )
        }
    };
    if sink.bytes < complete.len() {
        output_events += 1;
        if first_output_latency_ns.is_none() {
            first_output_latency_ns = Some(elapsed_ns(&started));
            first_output_input_bytes = Some(frame.len());
        }
        if let Err(error) = sink.write(&complete[sink.bytes..]) {
            return invalid_trial(sample, frame, "streaming", trial_index, warmup, error);
        }
    }
    let (output_bytes, output_sha256) = sink.finish();
    let output_complete_latency_ns = Some(elapsed_ns(&started));
    let roundtrip_exact = complete == original;
    let sink_exact =
        output_bytes == original.len() && output_sha256.as_str() == sample.sha256.as_str();
    let first_output_before_eof = first_output_input_bytes.is_some_and(|bytes| bytes < frame.len());
    let status = if roundtrip_exact && sink_exact {
        "valid"
    } else {
        "VOID"
    };
    Trial {
        sample_id: sample.sample_id.clone(),
        sample_path: sample.path.clone(),
        mode: "streaming",
        trial_index,
        warmup,
        input_bytes: original.len(),
        frame_bytes: frame.len(),
        input_sha256: sha256(original),
        expected_output_sha256: sample.sha256.clone(),
        output_sha256: Some(output_sha256),
        output_bytes,
        output_events,
        first_output_latency_ns,
        first_output_input_bytes,
        first_output_before_eof,
        last_input_latency_ns,
        output_complete_latency_ns,
        finish_ok: true,
        roundtrip_exact,
        sink_exact,
        status,
        error: (status == "valid")
            .then_some(None)
            .unwrap_or_else(|| Some("round-trip or sink digest mismatch".to_string())),
    }
}

fn whole_buffer_trial(
    sample: &ManifestSample,
    original: &[u8],
    frame: &[u8],
    trial_index: usize,
    warmup: bool,
) -> Trial {
    let started = Instant::now();
    let last_input_latency_ns = Some(elapsed_ns(&started));
    let decoded = match decode(frame) {
        Ok(decoded) => decoded,
        Err(error) => {
            return invalid_trial(
                sample,
                frame,
                "whole_buffer",
                trial_index,
                warmup,
                format!("whole-buffer decode rejected frame: {}", error.message()),
            )
        }
    };
    let mut sink = DigestSink::new();
    if let Err(error) = sink.write(&decoded) {
        return invalid_trial(sample, frame, "whole_buffer", trial_index, warmup, error);
    }
    let first_output_latency_ns = Some(elapsed_ns(&started));
    let output_complete_latency_ns = first_output_latency_ns;
    let (output_bytes, output_sha256) = sink.finish();
    let roundtrip_exact = decoded == original;
    let sink_exact =
        output_bytes == original.len() && output_sha256.as_str() == sample.sha256.as_str();
    let status = if roundtrip_exact && sink_exact {
        "valid"
    } else {
        "VOID"
    };
    Trial {
        sample_id: sample.sample_id.clone(),
        sample_path: sample.path.clone(),
        mode: "whole_buffer",
        trial_index,
        warmup,
        input_bytes: original.len(),
        frame_bytes: frame.len(),
        input_sha256: sha256(original),
        expected_output_sha256: sample.sha256.clone(),
        output_sha256: Some(output_sha256),
        output_bytes,
        output_events: 1,
        first_output_latency_ns,
        first_output_input_bytes: Some(frame.len()),
        first_output_before_eof: false,
        last_input_latency_ns,
        output_complete_latency_ns,
        finish_ok: true,
        roundtrip_exact,
        sink_exact,
        status,
        error: (status == "valid")
            .then_some(None)
            .unwrap_or_else(|| Some("round-trip or sink digest mismatch".to_string())),
    }
}

fn invalid_trial(
    sample: &ManifestSample,
    frame: &[u8],
    mode: &'static str,
    trial_index: usize,
    warmup: bool,
    error: String,
) -> Trial {
    Trial {
        sample_id: sample.sample_id.clone(),
        sample_path: sample.path.clone(),
        mode,
        trial_index,
        warmup,
        input_bytes: 0,
        frame_bytes: frame.len(),
        input_sha256: String::new(),
        expected_output_sha256: sample.sha256.clone(),
        output_sha256: None,
        output_bytes: 0,
        output_events: 0,
        first_output_latency_ns: None,
        first_output_input_bytes: None,
        first_output_before_eof: false,
        last_input_latency_ns: None,
        output_complete_latency_ns: None,
        finish_ok: false,
        roundtrip_exact: false,
        sink_exact: false,
        status: "VOID",
        error: Some(error),
    }
}

fn write_run(
    output_path: &Path,
    manifest: Manifest,
    manifest_bytes: Vec<u8>,
    trials: Vec<Trial>,
    status: &'static str,
) -> Result<(), String> {
    let provenance = Provenance {
        source_commit: required_env("CUBR_SOURCE_COMMIT")?,
        probe_source_sha256: required_env("CUBR_PROBE_SOURCE_SHA256")?,
        probe_binary_sha256: required_env("CUBR_PROBE_BINARY_SHA256")?,
        runner_sha256: required_env("CUBR_RUNNER_SHA256")?,
        prereg_sha256: required_env("CUBR_PREREG_SHA256")?,
        manifest_sha256: sha256(&manifest_bytes),
        host: required_env("CUBR_HOST")?,
        arch: env::consts::ARCH,
        cpu_affinity: current_affinity(),
        rustc: required_env("CUBR_RUSTC")?,
    };
    let run = Run {
        schema_version: SCHEMA_VERSION,
        task_id: "CUBR-0075",
        status,
        corpus_key: manifest.corpus_key,
        sample_count: manifest.samples.len(),
        mode_count: 2,
        warmups_per_cell: WARMUPS,
        measured_trials_per_cell: TRIALS,
        block_size: BLOCK_SIZE,
        input_chunk_size: CHUNK_SIZE,
        schedule_seed: SEED,
        provenance,
        trials,
    };
    let encoded =
        serde_json::to_vec_pretty(&run).map_err(|error| format!("serialize run: {error}"))?;
    fs::write(output_path, encoded)
        .map_err(|error| format!("write {}: {error}", output_path.display()))
}

fn required_env(name: &str) -> Result<String, String> {
    env::var(name).map_err(|_| format!("missing required environment variable {name}"))
}

fn current_affinity() -> String {
    fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|status| {
            status
                .lines()
                .find_map(|line| line.strip_prefix("Cpus_allowed_list:\t"))
                .map(str::to_string)
        })
        .or_else(|| env::var("CUBR_AFFINITY").ok())
        .unwrap_or_else(|| "unknown".to_string())
}

fn elapsed_ns(started: &Instant) -> u64 {
    started.elapsed().as_nanos().min(u64::MAX as u128) as u64
}

fn sha256(bytes: &[u8]) -> String {
    hex_digest(Sha256::digest(bytes).as_slice())
}

fn hex_digest(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn shuffle<T>(items: &mut [T], mut state: u64) {
    for index in (1..items.len()).rev() {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        let other = (state as usize) % (index + 1);
        items.swap(index, other);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (ManifestSample, Vec<u8>, Vec<u8>) {
        let original = b"streaming probe fixture ".repeat(10_000);
        let mut config = EncodeConfig::v1_default();
        config.web_profile = true;
        config.web_block_size = Some(256);
        let frame = cubrim::encode_with_config(&original, &config);
        let sample = ManifestSample {
            sample_id: "fixture".to_string(),
            path: "fixture".to_string(),
            byte_count: original.len(),
            sha256: sha256(&original),
        };
        (sample, original, frame)
    }

    #[test]
    fn streaming_probe_observes_output_before_eof() {
        let (sample, original, frame) = fixture();
        let trial = stream_trial(&sample, &original, &frame, 1, false);
        assert_eq!(trial.status, "valid");
        assert!(trial.first_output_before_eof);
        assert!(trial.first_output_input_bytes.expect("first output event") < trial.frame_bytes);
        assert!(trial.roundtrip_exact && trial.sink_exact);
    }

    #[test]
    fn whole_buffer_control_cannot_claim_pre_eof_output() {
        let (sample, original, frame) = fixture();
        let trial = whole_buffer_trial(&sample, &original, &frame, 1, false);
        assert_eq!(trial.status, "valid");
        assert!(!trial.first_output_before_eof);
        assert_eq!(trial.first_output_input_bytes, Some(trial.frame_bytes));
    }
}
