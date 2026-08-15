//! CUBR-0075 native streaming-performance measurement probe.
//!
//! This is an opt-in evidence binary. It exercises the same handle-based ABI
//! used by native embedders, measures every fresh output window and records the
//! conservative capacity bound defined by the frozen preregistration.

use cubrim::config::EncodeConfig;
use cubrim_web_decoder::ffi::{
    cbm_stream_declared_len, cbm_stream_finish, cbm_stream_free, cbm_stream_fresh_len,
    cbm_stream_fresh_ptr, cbm_stream_memory_usage, cbm_stream_new_with_limits, cbm_stream_push,
};
use cubrim_web_decoder::{decode, DecodeLimits, StreamDecoder};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::PathBuf;
use std::time::Instant;

const BLOCK_SIZE: usize = 65_536;
const CHUNK_SIZE: usize = 4_096;
const WARMUPS: usize = 3;
const TRIALS: usize = 30;
const SEED: u64 = 75_075;

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

struct LoadedSample {
    manifest: ManifestSample,
    original: Vec<u8>,
    frame: Vec<u8>,
    frame_sha256: String,
}

#[derive(Debug, Serialize)]
struct Run {
    schema_version: u32,
    task_id: &'static str,
    phase: &'static str,
    status: &'static str,
    corpus_key: String,
    protocol: Protocol,
    samples: Vec<SampleMeta>,
    independent_block_probe: IndependentBlockProbe,
    provenance: Provenance,
    trials: Vec<Trial>,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
struct Protocol {
    samples: usize,
    modes: usize,
    warmups: usize,
    trials: usize,
    seed: u64,
    block_size: usize,
    input_chunk_size: usize,
}

#[derive(Debug, Serialize)]
struct SampleMeta {
    sample_id: String,
    path: String,
    byte_count: usize,
    sha256: String,
    frame_bytes: usize,
    frame_sha256: String,
}

#[derive(Debug, Serialize)]
struct IndependentBlockProbe {
    success: bool,
    positive_control: bool,
    negative_control: bool,
    evidence: String,
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
    arch: String,
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
    compression_duration_ns: u64,
    input_sha256: String,
    frame_sha256: String,
    output_sha256: String,
    output_bytes: usize,
    output_events: usize,
    first_output_latency_ns: u64,
    first_output_input_bytes: usize,
    first_output_before_eof: bool,
    last_input_latency_ns: u64,
    output_complete_latency_ns: u64,
    declared_output_bytes: u64,
    decoder_retained_peak_bytes: u64,
    auxiliary_peak_bytes: u64,
    auxiliary_memory_bound_ratio: f64,
    finish_ok: bool,
    roundtrip_exact: bool,
    sink_exact: bool,
    status: &'static str,
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
            .ok_or("sink byte count overflow")?;
        self.hasher.update(bytes);
        Ok(())
    }

    fn finish(self) -> (usize, String) {
        (self.bytes, hex_digest(self.hasher.finalize().as_slice()))
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("streaming-performance probe: {error}");
        std::process::exit(2);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    let corpus_root = args
        .next()
        .map(PathBuf::from)
        .ok_or("usage: probe <corpus-root> <output-json>")?;
    let output_path = args
        .next()
        .map(PathBuf::from)
        .ok_or("usage: probe <corpus-root> <output-json>")?;
    if args.next().is_some() {
        return Err("usage: probe <corpus-root> <output-json>".into());
    }
    let manifest_path = corpus_root.join("manifest.v3.json");
    let manifest_bytes =
        fs::read(&manifest_path).map_err(|e| format!("read {}: {e}", manifest_path.display()))?;
    let manifest: Manifest =
        serde_json::from_slice(&manifest_bytes).map_err(|e| format!("parse manifest: {e}"))?;
    if manifest.samples.len() != 13 {
        return Err(format!(
            "manifest has {} samples, expected 13",
            manifest.samples.len()
        ));
    }

    let mut samples = Vec::with_capacity(manifest.samples.len());
    for item in &manifest.samples {
        let path = corpus_root.join(&item.path);
        let original = fs::read(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
        if original.len() != item.byte_count || sha256(&original) != item.sha256 {
            return Err(format!("{} does not match manifest", item.sample_id));
        }
        let frame = encode_web_frame(&original);
        if frame.len() < 10 || frame[5] != 18 {
            return Err(format!(
                "{} encoder returned a non-Web frame",
                item.sample_id
            ));
        }
        samples.push(LoadedSample {
            manifest: item.clone(),
            frame_sha256: sha256(&frame),
            original,
            frame,
        });
    }

    let independent_block_probe = probe_independent_capability(&samples[1])?;
    let mut order: Vec<(usize, &'static str)> = samples
        .iter()
        .enumerate()
        .flat_map(|(index, _)| [(index, "streaming"), (index, "whole_buffer")])
        .collect();
    shuffle(&mut order, SEED);
    let mut trials = Vec::with_capacity(order.len() * (WARMUPS + TRIALS));
    for (sample_index, mode) in order {
        let sample = &samples[sample_index];
        for run_index in 0..(WARMUPS + TRIALS) {
            let warmup = run_index < WARMUPS;
            let trial_index = if warmup {
                run_index + 1
            } else {
                run_index - WARMUPS + 1
            };
            let trial = if mode == "streaming" {
                stream_trial(sample, trial_index, warmup)?
            } else {
                whole_buffer_trial(sample, trial_index, warmup)?
            };
            trials.push(trial);
        }
    }

    let sample_meta = samples
        .iter()
        .map(|sample| SampleMeta {
            sample_id: sample.manifest.sample_id.clone(),
            path: sample.manifest.path.clone(),
            byte_count: sample.manifest.byte_count,
            sha256: sample.manifest.sha256.clone(),
            frame_bytes: sample.frame.len(),
            frame_sha256: sample.frame_sha256.clone(),
        })
        .collect();
    let run = Run {
        schema_version: 1,
        task_id: "CUBR-0075",
        phase: "streaming_performance",
        status: "COMPLETE",
        corpus_key: manifest.corpus_key,
        protocol: Protocol {
            samples: 13,
            modes: 2,
            warmups: WARMUPS,
            trials: TRIALS,
            seed: SEED,
            block_size: BLOCK_SIZE,
            input_chunk_size: CHUNK_SIZE,
        },
        samples: sample_meta,
        independent_block_probe,
        provenance: Provenance {
            source_commit: required_env("CUBR_SOURCE_COMMIT")?,
            probe_source_sha256: required_env("CUBR_PROBE_SOURCE_SHA256")?,
            probe_binary_sha256: required_env("CUBR_PROBE_BINARY_SHA256")?,
            runner_sha256: required_env("CUBR_RUNNER_SHA256")?,
            prereg_sha256: required_env("CUBR_PREREG_SHA256")?,
            manifest_sha256: sha256(&manifest_bytes),
            host: required_env("CUBR_HOST")?,
            arch: env::consts::ARCH.to_string(),
            cpu_affinity: current_affinity(),
            rustc: required_env("CUBR_RUSTC")?,
        },
        trials,
    };
    let encoded = serde_json::to_vec_pretty(&run).map_err(|e| format!("serialize run: {e}"))?;
    fs::write(&output_path, encoded).map_err(|e| format!("write {}: {e}", output_path.display()))
}

fn stream_trial(sample: &LoadedSample, trial_index: usize, warmup: bool) -> Result<Trial, String> {
    let compression_duration_ns = measure_compression_duration(sample)?;
    let started = Instant::now();
    let handle = cbm_stream_new_with_limits(
        DecodeLimits::DEFAULT_MAX_OUTPUT,
        DecodeLimits::DEFAULT_MAX_EXPANSION_RATIO,
        DecodeLimits::DEFAULT_MAX_DECODER_MEMORY,
    );
    if handle.is_null() {
        return Err("native stream allocation returned NULL".into());
    }
    let mut sink = DigestSink::new();
    let mut offset = 0usize;
    let mut output_events = 0usize;
    let mut first_output_latency_ns = None;
    let mut first_output_input_bytes = None;
    let mut declared_output_bytes = None;
    let mut decoder_retained_peak_bytes = 0u64;
    while offset < sample.frame.len() {
        let end = (offset + CHUNK_SIZE).min(sample.frame.len());
        let chunk = &sample.frame[offset..end];
        if unsafe { cbm_stream_push(handle, chunk.as_ptr(), chunk.len()) } == 0 {
            unsafe { cbm_stream_free(handle) };
            return Err(format!("push rejected {}", sample.manifest.sample_id));
        }
        offset = end;
        let declared = unsafe { cbm_stream_declared_len(handle) };
        if declared != u64::MAX {
            declared_output_bytes = Some(declared);
        }
        let fresh_len = unsafe { cbm_stream_fresh_len(handle) };
        let fresh_ptr = unsafe { cbm_stream_fresh_ptr(handle) };
        if fresh_len > 0 && fresh_ptr.is_null() {
            unsafe { cbm_stream_free(handle) };
            return Err("fresh length returned with NULL pointer".into());
        }
        let fresh = unsafe { std::slice::from_raw_parts(fresh_ptr, fresh_len) };
        if !fresh.is_empty() {
            output_events += 1;
            if first_output_latency_ns.is_none() {
                first_output_latency_ns = Some(elapsed_ns(&started));
                first_output_input_bytes = Some(offset);
            }
            let expected_start = sink.bytes;
            let expected_end = expected_start
                .checked_add(fresh.len())
                .ok_or("output overflow")?;
            if expected_end > sample.original.len()
                || sample.original[expected_start..expected_end] != *fresh
            {
                unsafe { cbm_stream_free(handle) };
                return Err(format!(
                    "decoded bytes differ for {}",
                    sample.manifest.sample_id
                ));
            }
            sink.write(fresh)?;
        }
        decoder_retained_peak_bytes =
            decoder_retained_peak_bytes.max(unsafe { cbm_stream_memory_usage(handle) as u64 });
    }
    let last_input_latency_ns = elapsed_ns(&started);
    if unsafe { cbm_stream_finish(handle) } == 0 {
        unsafe { cbm_stream_free(handle) };
        return Err(format!("finish rejected {}", sample.manifest.sample_id));
    }
    unsafe { cbm_stream_free(handle) };
    let declared_output_bytes =
        declared_output_bytes.ok_or("decoder never exposed declared output length")?;
    let (output_bytes, output_sha256) = sink.finish();
    let auxiliary_peak_bytes = decoder_retained_peak_bytes
        .checked_sub(sample.frame.len() as u64)
        .and_then(|value| value.checked_sub(declared_output_bytes))
        .ok_or("decoder retained capacity is below its measured components")?;
    let ratio = auxiliary_peak_bytes as f64 / sample.frame.len() as f64;
    let first_bytes = first_output_input_bytes.unwrap_or(sample.frame.len());
    let first_latency = first_output_latency_ns.unwrap_or(last_input_latency_ns);
    Ok(Trial {
        sample_id: sample.manifest.sample_id.clone(),
        sample_path: sample.manifest.path.clone(),
        mode: "streaming",
        trial_index,
        warmup,
        input_bytes: sample.original.len(),
        frame_bytes: sample.frame.len(),
        compression_duration_ns,
        input_sha256: sample.manifest.sha256.clone(),
        frame_sha256: sample.frame_sha256.clone(),
        output_sha256: output_sha256.clone(),
        output_bytes,
        output_events,
        first_output_latency_ns: first_latency,
        first_output_input_bytes: first_bytes,
        first_output_before_eof: first_bytes < sample.frame.len(),
        last_input_latency_ns,
        output_complete_latency_ns: elapsed_ns(&started),
        declared_output_bytes,
        decoder_retained_peak_bytes,
        auxiliary_peak_bytes,
        auxiliary_memory_bound_ratio: ratio,
        finish_ok: true,
        roundtrip_exact: output_bytes == sample.original.len()
            && output_sha256 == sample.manifest.sha256,
        sink_exact: output_bytes == sample.original.len()
            && output_sha256 == sample.manifest.sha256,
        status: "valid",
    })
}

fn whole_buffer_trial(
    sample: &LoadedSample,
    trial_index: usize,
    warmup: bool,
) -> Result<Trial, String> {
    let compression_duration_ns = measure_compression_duration(sample)?;
    let started = Instant::now();
    let decoded = decode(&sample.frame)
        .map_err(|e| format!("whole-buffer decode rejected: {}", e.message()))?;
    let mut sink = DigestSink::new();
    sink.write(&decoded)?;
    let first_output_latency_ns = elapsed_ns(&started);
    let (output_bytes, output_sha256) = sink.finish();
    let exact = decoded == sample.original
        && output_bytes == sample.original.len()
        && output_sha256 == sample.manifest.sha256;
    Ok(Trial {
        sample_id: sample.manifest.sample_id.clone(),
        sample_path: sample.manifest.path.clone(),
        mode: "whole_buffer",
        trial_index,
        warmup,
        input_bytes: sample.original.len(),
        frame_bytes: sample.frame.len(),
        compression_duration_ns,
        input_sha256: sample.manifest.sha256.clone(),
        frame_sha256: sample.frame_sha256.clone(),
        output_sha256,
        output_bytes,
        output_events: 1,
        first_output_latency_ns,
        first_output_input_bytes: sample.frame.len(),
        first_output_before_eof: false,
        last_input_latency_ns: first_output_latency_ns,
        output_complete_latency_ns: elapsed_ns(&started),
        declared_output_bytes: sample.original.len() as u64,
        decoder_retained_peak_bytes: 0,
        auxiliary_peak_bytes: 0,
        auxiliary_memory_bound_ratio: 0.0,
        finish_ok: true,
        roundtrip_exact: exact,
        sink_exact: exact,
        status: "valid",
    })
}

fn encode_web_frame(original: &[u8]) -> Vec<u8> {
    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = Some(BLOCK_SIZE);
    cubrim::encode_with_config(original, &config)
}

fn measure_compression_duration(sample: &LoadedSample) -> Result<u64, String> {
    let started = Instant::now();
    let frame = encode_web_frame(&sample.original);
    let duration_ns = elapsed_ns(&started);
    if frame.len() != sample.frame.len() || sha256(&frame) != sample.frame_sha256 {
        return Err(format!(
            "re-encoded frame drifted for {}",
            sample.manifest.sample_id
        ));
    }
    if duration_ns == 0 {
        return Err(format!(
            "compression timer returned zero for {}",
            sample.manifest.sample_id
        ));
    }
    Ok(duration_ns)
}

fn probe_independent_capability(sample: &LoadedSample) -> Result<IndependentBlockProbe, String> {
    let mut sequential = StreamDecoder::new(DecodeLimits::default());
    let sequential_ok = sequential.push(&sample.frame).is_ok() && sequential.finish().is_ok();
    if sample.frame.len() <= 10 {
        return Err("fixture frame has no payload suffix".into());
    }
    let mut fresh = StreamDecoder::new(DecodeLimits::default());
    let fresh_rejected_suffix = fresh.push(&sample.frame[10..]).is_err();
    Ok(IndependentBlockProbe {
        success: sequential_ok && !fresh_rejected_suffix,
        positive_control: sequential_ok,
        negative_control: fresh_rejected_suffix,
        evidence: "positive control decoded the complete ordered frame; a fresh decoder rejected the frame suffix without the container header, and the v1 API exposes no predecessor-free block operation".into(),
    })
}

fn required_env(name: &str) -> Result<String, String> {
    env::var(name).map_err(|_| format!("missing environment variable {name}"))
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

fn current_affinity() -> String {
    fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|status| {
            status
                .lines()
                .find_map(|line| line.strip_prefix("Cpus_allowed_list:\t"))
                .map(str::to_string)
        })
        .unwrap_or_else(|| "unknown".into())
}

fn shuffle<T>(items: &mut [T], mut state: u64) {
    for index in (1..items.len()).rev() {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        items.swap(index, (state as usize) % (index + 1));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn independent_probe_is_explicitly_negative_for_ordered_frames() {
        let original = b"cross-block context ".repeat(20_000);
        let mut config = EncodeConfig::v1_default();
        config.web_profile = true;
        config.web_block_size = Some(256);
        let frame = cubrim::encode_with_config(&original, &config);
        let sample = LoadedSample {
            manifest: ManifestSample {
                sample_id: "fixture".into(),
                path: "fixture".into(),
                byte_count: original.len(),
                sha256: sha256(&original),
            },
            frame_sha256: sha256(&frame),
            original,
            frame,
        };
        let probe = probe_independent_capability(&sample).expect("capability probe");
        assert!(probe.positive_control && probe.negative_control);
        assert!(!probe.success);
    }

    #[test]
    fn every_trial_serializes_source_derived_compression_duration() {
        let original = b"encode timing fixture ".repeat(2_000);
        let mut config = EncodeConfig::v1_default();
        config.web_profile = true;
        config.web_block_size = Some(BLOCK_SIZE);
        let frame = cubrim::encode_with_config(&original, &config);
        let sample = LoadedSample {
            manifest: ManifestSample {
                sample_id: "fixture".into(),
                path: "fixture".into(),
                byte_count: original.len(),
                sha256: sha256(&original),
            },
            frame_sha256: sha256(&frame),
            original,
            frame,
        };
        let trial = whole_buffer_trial(&sample, 1, false).expect("whole-buffer trial");
        let serialized = serde_json::to_value(trial).expect("serialize trial");
        assert!(
            serialized
                .get("compression_duration_ns")
                .and_then(serde_json::Value::as_u64)
                .is_some_and(|duration| duration > 0),
            "trial must carry a positive measured encode duration"
        );
    }
}
