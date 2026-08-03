#![allow(unsafe_code)]

use cubrim::decode;
use cubrim::decode_profile::{self, Stage, Timing};
use cubrim::header::{MODE_CM2, MODE_CUBE, MODE_RAW};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::alloc::{GlobalAlloc, Layout, System};
use std::env;
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

struct CountingAllocator;

#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;

static ALLOCATION_CALLS: AtomicU64 = AtomicU64::new(0);
static DEALLOCATION_CALLS: AtomicU64 = AtomicU64::new(0);
static REALLOCATION_CALLS: AtomicU64 = AtomicU64::new(0);
static BYTES_ALLOCATED: AtomicU64 = AtomicU64::new(0);
static BYTES_FREED: AtomicU64 = AtomicU64::new(0);
static LIVE_BYTES: AtomicU64 = AtomicU64::new(0);
static PEAK_LIVE_BYTES: AtomicU64 = AtomicU64::new(0);
static TIMING_NANOS: AtomicU64 = AtomicU64::new(0);
static TIMING_CYCLES: AtomicU64 = AtomicU64::new(0);
static TIMING_CYCLE_SAMPLES: AtomicU64 = AtomicU64::new(0);

impl CountingAllocator {
    fn record_timing(start: Instant, start_cycles: Option<u64>) {
        TIMING_NANOS.fetch_add(
            start.elapsed().as_nanos().min(u64::MAX as u128) as u64,
            Ordering::Relaxed,
        );
        if let (Some(start), Some(end)) = (start_cycles, decode_profile::cycle_counter()) {
            TIMING_CYCLES.fetch_add(end.saturating_sub(start), Ordering::Relaxed);
            TIMING_CYCLE_SAMPLES.fetch_add(1, Ordering::Relaxed);
        }
    }

    fn add_live(bytes: usize) {
        let bytes = bytes.min(u64::MAX as usize) as u64;
        let live = LIVE_BYTES
            .fetch_add(bytes, Ordering::Relaxed)
            .saturating_add(bytes);
        let mut peak = PEAK_LIVE_BYTES.load(Ordering::Relaxed);
        while live > peak {
            match PEAK_LIVE_BYTES.compare_exchange_weak(
                peak,
                live,
                Ordering::Relaxed,
                Ordering::Relaxed,
            ) {
                Ok(_) => break,
                Err(observed) => peak = observed,
            }
        }
    }

    fn remove_live(bytes: usize) {
        let bytes = bytes.min(u64::MAX as usize) as u64;
        let _ = LIVE_BYTES.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |live| {
            Some(live.saturating_sub(bytes))
        });
    }

    fn record_alloc(size: usize) {
        ALLOCATION_CALLS.fetch_add(1, Ordering::Relaxed);
        BYTES_ALLOCATED.fetch_add(size.min(u64::MAX as usize) as u64, Ordering::Relaxed);
        Self::add_live(size);
    }

    fn record_dealloc(size: usize) {
        DEALLOCATION_CALLS.fetch_add(1, Ordering::Relaxed);
        BYTES_FREED.fetch_add(size.min(u64::MAX as usize) as u64, Ordering::Relaxed);
        Self::remove_live(size);
    }

    fn record_realloc(old_size: usize, new_size: usize) {
        REALLOCATION_CALLS.fetch_add(1, Ordering::Relaxed);
        BYTES_ALLOCATED.fetch_add(new_size.min(u64::MAX as usize) as u64, Ordering::Relaxed);
        BYTES_FREED.fetch_add(old_size.min(u64::MAX as usize) as u64, Ordering::Relaxed);
        if new_size >= old_size {
            Self::add_live(new_size - old_size);
        } else {
            Self::remove_live(old_size - new_size);
        }
    }

    fn snapshot() -> AllocationSnapshot {
        AllocationSnapshot {
            allocation_calls: ALLOCATION_CALLS.load(Ordering::Relaxed),
            deallocation_calls: DEALLOCATION_CALLS.load(Ordering::Relaxed),
            reallocation_calls: REALLOCATION_CALLS.load(Ordering::Relaxed),
            bytes_allocated: BYTES_ALLOCATED.load(Ordering::Relaxed),
            bytes_freed: BYTES_FREED.load(Ordering::Relaxed),
            live_bytes: LIVE_BYTES.load(Ordering::Relaxed),
            peak_live_bytes: PEAK_LIVE_BYTES.load(Ordering::Relaxed),
            timing_nanos: TIMING_NANOS.load(Ordering::Relaxed),
            timing_cycles: TIMING_CYCLES.load(Ordering::Relaxed),
            timing_cycle_samples: TIMING_CYCLE_SAMPLES.load(Ordering::Relaxed),
        }
    }
}

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let start = Instant::now();
        let start_cycles = decode_profile::cycle_counter();
        let ptr = unsafe { System.alloc(layout) };
        Self::record_timing(start, start_cycles);
        if !ptr.is_null() {
            Self::record_alloc(layout.size());
        }
        ptr
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let start = Instant::now();
        let start_cycles = decode_profile::cycle_counter();
        let ptr = unsafe { System.alloc_zeroed(layout) };
        Self::record_timing(start, start_cycles);
        if !ptr.is_null() {
            Self::record_alloc(layout.size());
        }
        ptr
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        let start = Instant::now();
        let start_cycles = decode_profile::cycle_counter();
        unsafe { System.dealloc(ptr, layout) };
        Self::record_timing(start, start_cycles);
        Self::record_dealloc(layout.size());
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let start = Instant::now();
        let start_cycles = decode_profile::cycle_counter();
        let new_ptr = unsafe { System.realloc(ptr, layout, new_size) };
        Self::record_timing(start, start_cycles);
        if !new_ptr.is_null() {
            Self::record_realloc(layout.size(), new_size);
        }
        new_ptr
    }
}

#[derive(Clone, Copy, Debug)]
struct AllocationSnapshot {
    allocation_calls: u64,
    deallocation_calls: u64,
    reallocation_calls: u64,
    bytes_allocated: u64,
    bytes_freed: u64,
    live_bytes: u64,
    peak_live_bytes: u64,
    timing_nanos: u64,
    timing_cycles: u64,
    timing_cycle_samples: u64,
}

impl AllocationSnapshot {
    fn delta(self, before: Self) -> AllocationDelta {
        AllocationDelta {
            allocation_calls: self
                .allocation_calls
                .saturating_sub(before.allocation_calls),
            deallocation_calls: self
                .deallocation_calls
                .saturating_sub(before.deallocation_calls),
            reallocation_calls: self
                .reallocation_calls
                .saturating_sub(before.reallocation_calls),
            bytes_allocated: self.bytes_allocated.saturating_sub(before.bytes_allocated),
            bytes_freed: self.bytes_freed.saturating_sub(before.bytes_freed),
            live_bytes_after_decode: self.live_bytes.saturating_sub(before.live_bytes),
            peak_live_bytes: self.peak_live_bytes.saturating_sub(before.live_bytes),
            timing_nanos: self.timing_nanos.saturating_sub(before.timing_nanos),
            timing_cycles: if self.timing_cycle_samples > before.timing_cycle_samples {
                Some(self.timing_cycles.saturating_sub(before.timing_cycles))
            } else {
                None
            },
            retained_state_bytes: 0,
        }
    }
}

#[derive(Clone, Copy, Debug, serde::Serialize)]
struct AllocationDelta {
    allocation_calls: u64,
    deallocation_calls: u64,
    reallocation_calls: u64,
    bytes_allocated: u64,
    bytes_freed: u64,
    live_bytes_after_decode: u64,
    peak_live_bytes: u64,
    timing_nanos: u64,
    timing_cycles: Option<u64>,
    #[serde(skip)]
    retained_state_bytes: u64,
}

#[derive(Debug)]
struct Args {
    input: PathBuf,
    original: PathBuf,
    output: PathBuf,
    affinity: String,
}

fn parse_args() -> Result<Args, String> {
    let mut input = None;
    let mut original = None;
    let mut output = None;
    let mut affinity = String::from("unspecified");
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = |args: &mut std::iter::Skip<env::Args>, name: &str| {
            args.next()
                .ok_or_else(|| format!("missing value for {name}"))
        };
        match arg.as_str() {
            "--input" => input = Some(PathBuf::from(value(&mut args, "--input")?)),
            "--original" => original = Some(PathBuf::from(value(&mut args, "--original")?)),
            "--output" => output = Some(PathBuf::from(value(&mut args, "--output")?)),
            "--affinity" => affinity = value(&mut args, "--affinity")?,
            "--help" | "-h" => {
                return Err(
                    "usage: cubrim-decode-profile --input ARCHIVE --original PAYLOAD \
                     --output REPORT [--affinity one-core|fixed-core]"
                        .into(),
                )
            }
            other => return Err(format!("unknown argument: {other}")),
        }
    }
    Ok(Args {
        input: input.ok_or_else(|| "--input is required".to_string())?,
        original: original.ok_or_else(|| "--original is required".to_string())?,
        output: output.ok_or_else(|| "--output is required".to_string())?,
        affinity,
    })
}

fn sha256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().into()
}

fn mode_name(mode: u8) -> Option<&'static str> {
    match mode {
        MODE_CUBE => Some("cube"),
        MODE_RAW => Some("raw"),
        MODE_CM2 => Some("cm2"),
        _ => None,
    }
}

fn hex_digest(digest: [u8; 32]) -> String {
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn run(args: Args) -> Result<(), String> {
    let blob = fs::read(&args.input).map_err(|err| format!("read archive: {err}"))?;
    let original = fs::read(&args.original).map_err(|err| format!("read original: {err}"))?;
    let original_len = original.len();
    let original_digest = sha256(&original);
    drop(original);

    let mode = *blob
        .get(5)
        .ok_or_else(|| "archive is shorter than the mode byte".to_string())?;
    let mode_label = mode_name(mode).ok_or_else(|| {
        format!("unsupported mode {mode}; first-slice profiler supports only cube, raw, and cm2")
    })?;

    let before = CountingAllocator::snapshot();
    decode_profile::begin(blob.len());
    let (decoded, total_timing) = decode_profile::measure_total(|| decode(&blob));
    let decoded = match decoded {
        Ok(decoded) => decoded,
        Err(err) => {
            let _ = decode_profile::finish(0);
            return Err(format!("decode {mode_label}: {err}"));
        }
    };
    let decoded_len = decoded.len();
    let after_decode = CountingAllocator::snapshot();
    let decoded_digest = sha256(&decoded);
    let exact_roundtrip = decoded_len == original_len && decoded_digest == original_digest;
    drop(decoded);
    let after_drop = CountingAllocator::snapshot();

    let mut report = decode_profile::finish(decoded_len)
        .ok_or_else(|| "profile was not active at finish".to_string())?;
    report.set_total(total_timing);

    let mut allocation = after_decode.delta(before);
    allocation.retained_state_bytes = after_drop.live_bytes.saturating_sub(before.live_bytes);
    decode_profile::set_external_stage(
        &mut report,
        Stage::Allocation,
        allocation
            .allocation_calls
            .saturating_add(allocation.reallocation_calls),
        Timing {
            nanos: allocation.timing_nanos,
            cycles: allocation.timing_cycles,
        },
    );
    if mode != MODE_CM2 {
        decode_profile::assign_residual_stage(
            &mut report,
            Stage::OutputMaterialization,
            total_timing,
        );
    }

    let record = serde_json::json!({
        "kind": "cubrim-decode-attribution",
        "schema_version": decode_profile::SCHEMA_VERSION,
        "profiler_version": env!("CARGO_PKG_VERSION"),
        "input_path": args.input,
        "original_path": args.original,
        "affinity": args.affinity,
        "mode": {"byte": mode, "name": mode_label},
        "input_bytes": blob.len(),
        "original_bytes": original_len,
        "decoded_bytes": decoded_len,
        "original_sha256": hex_digest(original_digest),
        "decoded_sha256": hex_digest(decoded_digest),
        "exact_roundtrip": exact_roundtrip,
        "allocation": {
            "allocation_calls": allocation.allocation_calls,
            "deallocation_calls": allocation.deallocation_calls,
            "reallocation_calls": allocation.reallocation_calls,
            "bytes_allocated": allocation.bytes_allocated,
            "bytes_freed": allocation.bytes_freed,
            "live_bytes_after_decode": allocation.live_bytes_after_decode,
            "peak_live_bytes": allocation.peak_live_bytes,
            "retained_state_bytes_after_output_drop": allocation.retained_state_bytes,
            "timing_nanos": allocation.timing_nanos,
            "timing_cycles": allocation.timing_cycles,
        },
        "decode_profile": report,
    });

    if !exact_roundtrip {
        return Err("decoded output is not byte-exact with the original".to_string());
    }

    if let Some(parent) = args.output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).map_err(|err| format!("create report directory: {err}"))?;
        }
    }
    let bytes = serde_json::to_vec_pretty(&Value::from(record))
        .map_err(|err| format!("serialize report: {err}"))?;
    fs::write(&args.output, bytes).map_err(|err| format!("write report: {err}"))?;
    Ok(())
}

fn main() {
    let result = parse_args().and_then(run);
    if let Err(err) = result {
        eprintln!("cubrim-decode-profile: {err}");
        std::process::exit(2);
    }
}
