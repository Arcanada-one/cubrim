//! Opt-in CUBR-0075 bounded-state allocator probe.
//!
//! This binary is deliberately separate from the shipped decoder. It uses a
//! counting allocator around the existing native stream ABI and reports
//! allocation/capacity metrics only; the instrumentation is not a timing
//! benchmark and is never enabled by the default crate build.

use cubrim::config::EncodeConfig;
use cubrim_web_decoder::ffi::{
    cbm_stream_declared_len, cbm_stream_error_len, cbm_stream_error_ptr, cbm_stream_finish,
    cbm_stream_free, cbm_stream_fresh_len, cbm_stream_fresh_ptr, cbm_stream_memory_usage,
    cbm_stream_new_with_limits, cbm_stream_push,
};
use cubrim_web_decoder::DecodeLimits;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::Cell;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const BLOCK_SIZE: usize = 65_536;
const CHUNK_SIZE: usize = 65_536;
const TRIALS: usize = 30;
const WARMUPS: usize = 3;
const SEED: u64 = 75_075;
const MODE_OFFSET: usize = 5;

#[derive(Default)]
struct CounterState {
    allocation_count: AtomicU64,
    allocated_bytes: AtomicU64,
    deallocated_bytes: AtomicU64,
    current_live_bytes: AtomicU64,
    baseline_live_bytes: AtomicU64,
    peak_live_bytes: AtomicU64,
    largest_single_allocation_bytes: AtomicU64,
}

static COUNTERS: CounterState = CounterState {
    allocation_count: AtomicU64::new(0),
    allocated_bytes: AtomicU64::new(0),
    deallocated_bytes: AtomicU64::new(0),
    current_live_bytes: AtomicU64::new(0),
    baseline_live_bytes: AtomicU64::new(0),
    peak_live_bytes: AtomicU64::new(0),
    largest_single_allocation_bytes: AtomicU64::new(0),
};

thread_local! {
    static IN_ALLOCATOR_HOOK: Cell<bool> = const { Cell::new(false) };
}

struct CountingAllocator;

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

fn saturating_add(atom: &AtomicU64, value: u64) {
    let _ = atom.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |current| {
        Some(current.saturating_add(value))
    });
}

fn saturating_sub(atom: &AtomicU64, value: u64) {
    let _ = atom.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |current| {
        Some(current.saturating_sub(value))
    });
}

fn update_max(atom: &AtomicU64, value: u64) {
    let _ = atom.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |current| {
        (value > current).then_some(value)
    });
}

fn record_live_peak() {
    let current = COUNTERS.current_live_bytes.load(Ordering::Relaxed);
    let baseline = COUNTERS.baseline_live_bytes.load(Ordering::Relaxed);
    update_max(&COUNTERS.peak_live_bytes, current.saturating_sub(baseline));
}

fn record_allocated(size: usize) {
    let size = size as u64;
    saturating_add(&COUNTERS.allocation_count, 1);
    saturating_add(&COUNTERS.allocated_bytes, size);
    saturating_add(&COUNTERS.current_live_bytes, size);
    update_max(&COUNTERS.largest_single_allocation_bytes, size);
    record_live_peak();
}

fn record_deallocated(size: usize) {
    let size = size as u64;
    saturating_add(&COUNTERS.deallocated_bytes, size);
    saturating_sub(&COUNTERS.current_live_bytes, size);
}

fn record_reallocation(old_size: usize, new_size: usize) {
    let old_size = old_size as u64;
    let new_size = new_size as u64;
    saturating_add(&COUNTERS.allocation_count, 1);
    saturating_add(&COUNTERS.allocated_bytes, new_size);
    saturating_add(&COUNTERS.deallocated_bytes, old_size);
    if new_size >= old_size {
        saturating_add(&COUNTERS.current_live_bytes, new_size - old_size);
    } else {
        saturating_sub(&COUNTERS.current_live_bytes, old_size - new_size);
    }
    update_max(&COUNTERS.largest_single_allocation_bytes, new_size);
    record_live_peak();
}

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let reentrant = IN_ALLOCATOR_HOOK.with(|guard| {
            if guard.get() {
                true
            } else {
                guard.set(true);
                false
            }
        });
        let pointer = unsafe { System.alloc(layout) };
        if !reentrant {
            if !pointer.is_null() {
                record_allocated(layout.size());
            }
            IN_ALLOCATOR_HOOK.with(|guard| guard.set(false));
        }
        pointer
    }

    unsafe fn dealloc(&self, pointer: *mut u8, layout: Layout) {
        let reentrant = IN_ALLOCATOR_HOOK.with(|guard| {
            if guard.get() {
                true
            } else {
                guard.set(true);
                false
            }
        });
        unsafe { System.dealloc(pointer, layout) };
        if !reentrant {
            record_deallocated(layout.size());
            IN_ALLOCATOR_HOOK.with(|guard| guard.set(false));
        }
    }

    unsafe fn realloc(&self, pointer: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let reentrant = IN_ALLOCATOR_HOOK.with(|guard| {
            if guard.get() {
                true
            } else {
                guard.set(true);
                false
            }
        });
        let new_pointer = unsafe { System.realloc(pointer, layout, new_size) };
        if !reentrant {
            if !new_pointer.is_null() {
                record_reallocation(layout.size(), new_size);
            }
            IN_ALLOCATOR_HOOK.with(|guard| guard.set(false));
        }
        new_pointer
    }
}

#[derive(Clone, Copy, Debug, Serialize)]
struct AllocationSnapshot {
    allocation_count: u64,
    allocated_bytes: u64,
    deallocated_bytes: u64,
    peak_live_bytes: u64,
    largest_single_allocation_bytes: u64,
    live_bytes_after: u64,
}

fn begin_measurement() {
    COUNTERS.baseline_live_bytes.store(
        COUNTERS.current_live_bytes.load(Ordering::Relaxed),
        Ordering::Relaxed,
    );
    COUNTERS.allocation_count.store(0, Ordering::Relaxed);
    COUNTERS.allocated_bytes.store(0, Ordering::Relaxed);
    COUNTERS.deallocated_bytes.store(0, Ordering::Relaxed);
    COUNTERS.peak_live_bytes.store(0, Ordering::Relaxed);
    COUNTERS
        .largest_single_allocation_bytes
        .store(0, Ordering::Relaxed);
}

fn snapshot() -> AllocationSnapshot {
    let current = COUNTERS.current_live_bytes.load(Ordering::Relaxed);
    let baseline = COUNTERS.baseline_live_bytes.load(Ordering::Relaxed);
    AllocationSnapshot {
        allocation_count: COUNTERS.allocation_count.load(Ordering::Relaxed),
        allocated_bytes: COUNTERS.allocated_bytes.load(Ordering::Relaxed),
        deallocated_bytes: COUNTERS.deallocated_bytes.load(Ordering::Relaxed),
        peak_live_bytes: COUNTERS.peak_live_bytes.load(Ordering::Relaxed),
        largest_single_allocation_bytes: COUNTERS
            .largest_single_allocation_bytes
            .load(Ordering::Relaxed),
        live_bytes_after: current.saturating_sub(baseline),
    }
}

#[derive(Debug, Deserialize, Clone)]
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

#[derive(Clone)]
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

#[derive(Debug, Serialize)]
struct Protocol {
    samples: usize,
    profiles: usize,
    warmups: usize,
    trials: usize,
    seed: u64,
    chunk_size: usize,
    block_size: usize,
}

#[derive(Debug, Serialize)]
struct Provenance {
    source_sha: String,
    runner_sha: String,
    probe_sha: String,
    binary_sha: String,
    manifest_sha: String,
    preregistration_sha: String,
}

#[derive(Debug, Serialize)]
struct Environment {
    hostname: String,
    effective_affinity: String,
    load_per_cpu: Option<f64>,
    max_temperature_c: Option<f64>,
    recorded_at_epoch: u64,
}

#[derive(Debug, Serialize)]
struct Trial {
    trial_no: usize,
    randomized_order: usize,
    roundtrip_exact: bool,
    decoded_sha256: String,
    allocation_count: u64,
    allocated_bytes: u64,
    deallocated_bytes: u64,
    peak_live_bytes: u64,
    largest_single_allocation_bytes: u64,
    live_bytes_after: u64,
    caller_input_bytes: u64,
    declared_output_bytes: u64,
    decoder_retained_peak_bytes: u64,
    decoder_retained_after_drop_bytes: u64,
    auxiliary_peak_bytes: u64,
    auxiliary_ratio_numerator_bytes: u64,
    auxiliary_ratio_denominator_bytes: u64,
    auxiliary_memory_bound_ratio: f64,
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
struct Summary {
    max_largest_single_allocation_bytes: u64,
    max_auxiliary_memory_bound_ratio: f64,
    win_largest_single_allocation_bytes: bool,
    go_largest_single_allocation_bytes: bool,
    go_auxiliary_memory_bound_ratio: bool,
    decision: String,
}

#[derive(Debug, Serialize)]
struct ProbeOutput {
    schema_version: u32,
    task_id: String,
    phase: String,
    protocol: Protocol,
    provenance: Provenance,
    environment: Environment,
    results: Vec<SampleResult>,
    summary: Summary,
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

fn sha256_file(path: &Path) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|error| format!("read {}: {error}", path.display()))?;
    Ok(sha256(&bytes))
}

fn git_sha(repo_root: &Path) -> Result<String, String> {
    let output = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(repo_root)
        .output()
        .map_err(|error| format!("git rev-parse: {error}"))?;
    if !output.status.success() {
        return Err("git rev-parse HEAD failed".into());
    }
    String::from_utf8(output.stdout)
        .map(|value| value.trim().to_string())
        .map_err(|error| format!("git SHA is not UTF-8: {error}"))
}

fn mode(frame: &[u8]) -> Result<String, String> {
    match frame.get(MODE_OFFSET).copied() {
        Some(cubrim::header::MODE_WEB) => Ok("web".into()),
        Some(cubrim::header::MODE_RAW) => Ok("raw_store".into()),
        Some(other) => Err(format!("unsupported frame mode {other}")),
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
    let bytes = fs::read(manifest_path)
        .map_err(|error| format!("read manifest {}: {error}", manifest_path.display()))?;
    let manifest: Manifest =
        serde_json::from_slice(&bytes).map_err(|error| format!("parse manifest: {error}"))?;
    if manifest.schema_version != 2 || manifest.samples.len() != 13 {
        return Err(format!(
            "expected manifest schema 2 with 13 samples, got schema {} and {} samples",
            manifest.schema_version,
            manifest.samples.len()
        ));
    }
    let root = manifest_path
        .parent()
        .ok_or_else(|| "manifest has no parent".to_string())?;
    let mut loaded = Vec::with_capacity(manifest.samples.len());
    for sample in &manifest.samples {
        let path = root.join(&sample.path);
        let data = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
        if data.len() != sample.byte_count || sha256(&data) != sample.sha256 {
            return Err(format!("{} differs from manifest", sample.sample_id));
        }
        let static_frame = static_frame(&data);
        let dynamic_frame = dynamic_frame(&data)?;
        let static_mode = mode(&static_frame)?;
        let dynamic_mode = mode(&dynamic_frame)?;
        if cubrim::decode(&static_frame).map_err(|error| error.to_string())? != data
            || cubrim::decode(&dynamic_frame).map_err(|error| error.to_string())? != data
        {
            return Err(format!(
                "{} failed profile preflight round trip",
                sample.sample_id
            ));
        }
        loaded.push(LoadedSample {
            manifest: sample.clone(),
            data: data.clone(),
            input_sha256: sha256(&data),
            static_sha256: sha256(&static_frame),
            dynamic_sha256: sha256(&dynamic_frame),
            static_frame,
            dynamic_frame,
            static_mode,
            dynamic_mode,
        });
    }
    Ok((manifest, loaded))
}

fn ffi_error(handle: *mut cubrim_web_decoder::ffi::CbmStream) -> String {
    unsafe {
        let pointer = cbm_stream_error_ptr(handle);
        let length = cbm_stream_error_len(handle);
        if pointer.is_null() || length == 0 {
            return "native decoder returned an unspecified error".into();
        }
        String::from_utf8_lossy(std::slice::from_raw_parts(pointer, length)).into_owned()
    }
}

fn measure_trial(
    sample: &LoadedSample,
    frame: &[u8],
    trial_no: usize,
    randomized_order: usize,
) -> Result<Trial, String> {
    let hasher = Sha256::new();
    let mut hasher = hasher;
    let mut decoded_offset = 0usize;
    let mut declared_output_bytes = None;
    let mut decoder_retained_peak_bytes = 0u64;
    begin_measurement();
    let handle = cbm_stream_new_with_limits(
        DecodeLimits::DEFAULT_MAX_OUTPUT,
        DecodeLimits::DEFAULT_MAX_EXPANSION_RATIO,
        DecodeLimits::DEFAULT_MAX_DECODER_MEMORY,
    );
    if handle.is_null() {
        return Err("native stream allocation returned NULL".into());
    }
    for chunk in frame.chunks(CHUNK_SIZE) {
        if unsafe { cbm_stream_push(handle, chunk.as_ptr(), chunk.len()) } == 0 {
            let error = ffi_error(handle);
            unsafe { cbm_stream_free(handle) };
            return Err(format!("push failed: {error}"));
        }
        let declared = unsafe { cbm_stream_declared_len(handle) };
        if declared != u64::MAX {
            declared_output_bytes = Some(declared);
        }
        let fresh_len = unsafe { cbm_stream_fresh_len(handle) };
        let fresh_ptr = unsafe { cbm_stream_fresh_ptr(handle) };
        if fresh_len > 0 && fresh_ptr.is_null() {
            unsafe { cbm_stream_free(handle) };
            return Err("native decoder returned fresh length with NULL pointer".into());
        }
        let fresh = unsafe { std::slice::from_raw_parts(fresh_ptr, fresh_len) };
        let end = decoded_offset
            .checked_add(fresh.len())
            .ok_or_else(|| "decoded output length overflow".to_string())?;
        if end > sample.data.len() || sample.data[decoded_offset..end] != *fresh {
            unsafe { cbm_stream_free(handle) };
            return Err("decoded bytes differ from the canonical sample".into());
        }
        hasher.update(fresh);
        decoded_offset = end;
        decoder_retained_peak_bytes =
            decoder_retained_peak_bytes.max(unsafe { cbm_stream_memory_usage(handle) as u64 });
    }
    let declared_output_bytes = declared_output_bytes
        .ok_or_else(|| "decoder never exposed a declared output length".to_string())?;
    if unsafe { cbm_stream_finish(handle) } == 0 {
        let error = ffi_error(handle);
        unsafe { cbm_stream_free(handle) };
        return Err(format!("finish failed: {error}"));
    }
    unsafe { cbm_stream_free(handle) };
    if decoded_offset != sample.data.len() {
        return Err(format!(
            "decoded {} bytes but expected {}",
            decoded_offset,
            sample.data.len()
        ));
    }
    let decoded_sha256 = format!("{:x}", hasher.finalize());
    let roundtrip_exact = decoded_sha256 == sample.input_sha256;
    if !roundtrip_exact {
        return Err("decoded SHA-256 differs from the canonical sample".into());
    }
    let snapshot = snapshot();
    let auxiliary_peak_bytes = decoder_retained_peak_bytes
        .saturating_sub(frame.len() as u64)
        .saturating_sub(declared_output_bytes);
    let auxiliary_ratio_denominator_bytes = frame.len() as u64;
    let auxiliary_memory_bound_ratio =
        auxiliary_peak_bytes as f64 / auxiliary_ratio_denominator_bytes.max(1) as f64;
    Ok(Trial {
        trial_no,
        randomized_order,
        roundtrip_exact,
        decoded_sha256,
        allocation_count: snapshot.allocation_count,
        allocated_bytes: snapshot.allocated_bytes,
        deallocated_bytes: snapshot.deallocated_bytes,
        peak_live_bytes: snapshot.peak_live_bytes,
        largest_single_allocation_bytes: snapshot.largest_single_allocation_bytes,
        live_bytes_after: snapshot.live_bytes_after,
        caller_input_bytes: frame.len() as u64,
        declared_output_bytes,
        decoder_retained_peak_bytes,
        decoder_retained_after_drop_bytes: snapshot.live_bytes_after,
        auxiliary_peak_bytes,
        auxiliary_ratio_numerator_bytes: auxiliary_peak_bytes,
        auxiliary_ratio_denominator_bytes,
        auxiliary_memory_bound_ratio,
    })
}

fn summarize(results: &[SampleResult]) -> Summary {
    let trials = results.iter().flat_map(|sample| {
        sample
            .static_profile
            .trials
            .iter()
            .chain(sample.dynamic_profile.trials.iter())
    });
    let mut max_largest = 0u64;
    let mut max_ratio = 0.0f64;
    for trial in trials {
        max_largest = max_largest.max(trial.largest_single_allocation_bytes);
        max_ratio = max_ratio.max(trial.auxiliary_memory_bound_ratio);
    }
    let win_largest = max_largest <= 65_536;
    let go_largest = max_largest <= 4_194_304;
    let go_auxiliary = max_ratio <= 1.0;
    let decision = if win_largest && go_auxiliary {
        "WIN"
    } else if go_largest && go_auxiliary {
        "GO"
    } else {
        "NO_GO"
    };
    Summary {
        max_largest_single_allocation_bytes: max_largest,
        max_auxiliary_memory_bound_ratio: max_ratio,
        win_largest_single_allocation_bytes: win_largest,
        go_largest_single_allocation_bytes: go_largest,
        go_auxiliary_memory_bound_ratio: go_auxiliary,
        decision: decision.into(),
    }
}

fn environment() -> Environment {
    Environment {
        hostname: env::var("CUBRIM_HOSTNAME")
            .or_else(|_| env::var("HOSTNAME"))
            .unwrap_or_else(|_| "unknown".into()),
        effective_affinity: env::var("CUBRIM_EFFECTIVE_AFFINITY")
            .unwrap_or_else(|_| "unknown".into()),
        load_per_cpu: env::var("CUBRIM_LOAD_PER_CPU")
            .ok()
            .and_then(|v| v.parse().ok()),
        max_temperature_c: env::var("CUBRIM_MAX_TEMPERATURE_C")
            .ok()
            .and_then(|v| v.parse().ok()),
        recorded_at_epoch: SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_secs())
            .unwrap_or(0),
    }
}

fn probe_sha() -> Result<String, String> {
    let executable = env::current_exe().map_err(|error| format!("current executable: {error}"))?;
    sha256_file(&executable)
}

fn measure(manifest_path: &Path) -> Result<ProbeOutput, String> {
    let repo_root = manifest_path
        .canonicalize()
        .map_err(|error| format!("canonicalize manifest: {error}"))?
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .ok_or_else(|| "manifest does not resolve below a repository root".to_string())?
        .to_path_buf();
    let manifest_sha = sha256_file(manifest_path)?;
    let source_sha = git_sha(&repo_root)?;
    let probe_sha = probe_sha()?;
    let (_, samples) = load_samples(manifest_path)?;
    let mut operations = Vec::with_capacity(samples.len() * 2);
    for sample_index in 0..samples.len() {
        operations.push((sample_index, false));
        operations.push((sample_index, true));
    }
    for _ in 0..WARMUPS {
        for &(sample_index, dynamic) in &operations {
            let sample = &samples[sample_index];
            let frame = if dynamic {
                &sample.dynamic_frame
            } else {
                &sample.static_frame
            };
            if cubrim::decode(frame).map_err(|error| error.to_string())? != sample.data {
                return Err(format!(
                    "{} warmup round trip failed",
                    sample.manifest.sample_id
                ));
            }
        }
    }
    let mut static_trials: Vec<Vec<Trial>> =
        samples.iter().map(|_| Vec::with_capacity(TRIALS)).collect();
    let mut dynamic_trials: Vec<Vec<Trial>> =
        samples.iter().map(|_| Vec::with_capacity(TRIALS)).collect();
    let mut rng = Lcg(SEED);
    for trial_no in 1..=TRIALS {
        let mut order: Vec<usize> = (0..operations.len()).collect();
        for index in (1..order.len()).rev() {
            order.swap(index, (rng.next() as usize) % (index + 1));
        }
        for (position, operation_index) in order.into_iter().enumerate() {
            let (sample_index, dynamic) = operations[operation_index];
            let sample = &samples[sample_index];
            let frame = if dynamic {
                &sample.dynamic_frame
            } else {
                &sample.static_frame
            };
            let trial = measure_trial(sample, frame, trial_no, position + 1)?;
            if dynamic {
                dynamic_trials[sample_index].push(trial);
            } else {
                static_trials[sample_index].push(trial);
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
        .collect::<Vec<_>>();
    let summary = summarize(&results);
    Ok(ProbeOutput {
        schema_version: 1,
        task_id: "CUBR-0075".into(),
        phase: "allocator_telemetry".into(),
        protocol: Protocol {
            samples: results.len(),
            profiles: 2,
            warmups: WARMUPS,
            trials: TRIALS,
            seed: SEED,
            chunk_size: CHUNK_SIZE,
            block_size: BLOCK_SIZE,
        },
        provenance: Provenance {
            source_sha,
            runner_sha: env::var("CUBRIM_RUNNER_SHA").unwrap_or_else(|_| "unbound".into()),
            probe_sha: probe_sha.clone(),
            binary_sha: probe_sha,
            manifest_sha,
            preregistration_sha: env::var("CUBRIM_PREREG_SHA").unwrap_or_else(|_| "unbound".into()),
        },
        environment: environment(),
        results,
        summary,
    })
}

fn usage() -> ! {
    eprintln!("usage: allocator_telemetry_probe measure <manifest.json>");
    std::process::exit(2);
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() != 2 || args[0] != "measure" {
        usage();
    }
    match measure(&PathBuf::from(&args[1])) {
        Ok(output) => println!(
            "{}",
            serde_json::to_string_pretty(&output).expect("probe output serialization cannot fail")
        ),
        Err(error) => {
            eprintln!("allocator telemetry measurement void: {error}");
            std::process::exit(1);
        }
    }
}
