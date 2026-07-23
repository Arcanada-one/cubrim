//! Industrial CLI smoke tests for the single-file `compress` / `decompress`
//! commands: round-trip correctness on edge inputs, deterministic output,
//! documented exit codes, and the `--quiet` contract.
//!
//! These guard the user-facing surface of the shipped binary; they are
//! independent of the codec internals (which are covered by the differential
//! and bench suites) and assert only externally observable behaviour.

use std::fs;
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

use tempfile::tempdir;

static STATE_COUNTER: AtomicUsize = AtomicUsize::new(0);

fn cubrim() -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_cubrim"));
    command.env("CUBRIM_ACCEPT_LICENSE", "1");
    command.env(
        "CUBRIM_STATE_DIR",
        std::env::temp_dir().join(format!(
            "cubrim-smoke-state-{}-{}",
            std::process::id(),
            STATE_COUNTER.fetch_add(1, Ordering::Relaxed)
        )),
    );
    command.env("CUBRIM_API_BASE_URL", "http://127.0.0.1:9");
    command
}

/// Compress `input` bytes then decompress, asserting a byte-exact round trip.
/// Returns the compressed blob so callers can make size/determinism assertions.
fn round_trip(name: &str, input: &[u8]) -> Vec<u8> {
    let temp = tempdir().unwrap();
    let src = temp.path().join(format!("{name}.in"));
    let cub = temp.path().join(format!("{name}.cub"));
    let out = temp.path().join(format!("{name}.out"));
    fs::write(&src, input).unwrap();

    let status = cubrim()
        .args(["compress"])
        .arg(&src)
        .arg(&cub)
        .arg("--quiet")
        .status()
        .unwrap();
    assert!(status.success(), "compress failed for {name}: {status:?}");

    let status = cubrim()
        .args(["decompress"])
        .arg(&cub)
        .arg(&out)
        .arg("--quiet")
        .status()
        .unwrap();
    assert!(status.success(), "decompress failed for {name}: {status:?}");

    let restored = fs::read(&out).unwrap();
    assert_eq!(restored, input, "round-trip not byte-exact for {name}");
    fs::read(&cub).unwrap()
}

#[test]
fn round_trip_empty_file() {
    // A zero-byte input must survive the round trip (fail-closed, never panics).
    round_trip("empty", &[]);
}

#[test]
fn round_trip_single_byte() {
    round_trip("one", b"A");
}

#[test]
fn round_trip_small_text() {
    let text = "the quick brown fox jumps over the lazy dog\n".repeat(64);
    round_trip("small_text", text.as_bytes());
}

#[test]
fn round_trip_incompressible_random_is_fail_safe() {
    // Pseudo-random, high-entropy bytes cannot be compressed; the encoder must
    // still produce a losslessly decodable blob (stored path), never corrupt it.
    let mut data = vec![0u8; 200_000];
    let mut x: u32 = 0x9e3779b9;
    for b in data.iter_mut() {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        *b = (x & 0xff) as u8;
    }
    let blob = round_trip("random", &data);
    // Fail-safe: the stored path adds only a bounded header, never a blow-up.
    assert!(
        blob.len() <= data.len() + 1024,
        "incompressible input expanded too much: {} -> {}",
        data.len(),
        blob.len()
    );
}

#[test]
fn compress_is_deterministic() {
    // Same input compressed twice must yield byte-identical output (CA.3).
    let text = "deterministic payload — cube corner φ mapping\n".repeat(4096);
    let a = round_trip("det_a", text.as_bytes());
    let b = round_trip("det_b", text.as_bytes());
    assert_eq!(a, b, "compression is not deterministic");
}

#[test]
fn quiet_suppresses_stats_line() {
    let temp = tempdir().unwrap();
    let src = temp.path().join("q.in");
    let cub = temp.path().join("q.cub");
    fs::write(&src, b"payload payload payload\n").unwrap();

    let output = cubrim()
        .args(["compress"])
        .arg(&src)
        .arg(&cub)
        .arg("--quiet")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(
        output.stderr.is_empty(),
        "--quiet must not print the stats line, got: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn stats_line_printed_without_quiet() {
    let temp = tempdir().unwrap();
    let src = temp.path().join("s.in");
    let cub = temp.path().join("s.cub");
    fs::write(&src, "compress me ".repeat(4096).as_bytes()).unwrap();

    let output = cubrim()
        .args(["compress"])
        .arg(&src)
        .arg(&cub)
        .output()
        .unwrap();
    assert!(output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("compressed:") && stderr.contains("ratio"),
        "expected a human-readable stats line, got: {stderr}"
    );
}

#[test]
fn decompress_corrupt_input_exits_integrity_code_2() {
    // Garbage that is not a valid Cubrim blob must be rejected with exit code 2
    // (integrity), not silently produce wrong output.
    let temp = tempdir().unwrap();
    let bad = temp.path().join("garbage.cub");
    let out = temp.path().join("out.bin");
    fs::write(&bad, b"this is definitely not a cubrim container").unwrap();

    let status = cubrim()
        .args(["decompress"])
        .arg(&bad)
        .arg(&out)
        .arg("--quiet")
        .status()
        .unwrap();
    assert_eq!(
        status.code(),
        Some(2),
        "corrupt input must exit with integrity code 2"
    );
}

#[test]
fn decompress_missing_input_exits_io_code_3() {
    let temp = tempdir().unwrap();
    let missing = temp.path().join("does-not-exist.cub");
    let out = temp.path().join("out.bin");

    let status = cubrim()
        .args(["decompress"])
        .arg(&missing)
        .arg(&out)
        .arg("--quiet")
        .status()
        .unwrap();
    assert_eq!(
        status.code(),
        Some(3),
        "missing input file must exit with I/O code 3"
    );
}

#[test]
fn no_command_exits_usage_code_1() {
    let status = cubrim().status().unwrap();
    assert_eq!(
        status.code(),
        Some(1),
        "invoking with no subcommand must exit with usage code 1"
    );
}
