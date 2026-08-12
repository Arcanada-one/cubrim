//! The binary contract, bound to the real web census.
//!
//! These tests run the built `cubrim-web` executable as a subprocess — the same
//! way the benchmark harness will — rather than calling the library functions
//! it wraps. That distinction is the whole point of the crate: the two-container
//! defect (PR #136) was invisible to every in-process test and appeared within
//! seconds of pushing real fixtures through the real artefact. An in-process
//! test here would reproduce that blind spot exactly.

use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

/// The 12 payloads of the pinned web census.
const CENSUS: [&str; 12] = [
    "tailwind.css",
    "html-large-web-codec-v2.html",
    "html-medium-home-v2.html",
    "magic-string.umd.js",
    "sourcemap-codec.umd.js",
    "resolve-uri.umd.js",
    "json-api-large-world-benchmark-v2.json",
    "json-api-medium-web-benchmark-v2.json",
    "json-api-small-hypotheses-v2.json",
    "magic-string.umd.js.map",
    "sourcemap-codec.umd.js.map",
    "inter-latin.medium.woff2",
];

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .expect("crate lives at code/cubrim-web-cli")
        .join("bench/web-corpus/payloads-v2")
}

fn binary() -> PathBuf {
    // CARGO_BIN_EXE_ is set by cargo for every [[bin]] in the crate under test.
    PathBuf::from(env!("CARGO_BIN_EXE_cubrim-web"))
}

fn run(args: &[&str]) -> Output {
    Command::new(binary())
        .args(args)
        .stdin(Stdio::null())
        .output()
        .expect("failed to spawn cubrim-web")
}

/// Encode a file, returning the frame bytes, asserting a clean exit.
fn encode(path: &Path, extra: &[&str]) -> Vec<u8> {
    let mut args: Vec<&str> = vec!["encode"];
    args.extend_from_slice(extra);
    let display = path.to_str().expect("utf-8 path");
    args.push(display);
    let out = run(&args);
    assert!(
        out.status.success(),
        "encode {display} failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    out.stdout
}

fn write_temp(name: &str, bytes: &[u8]) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("cubrim-web-cli-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("temp dir");
    let path = dir.join(name);
    std::fs::write(&path, bytes).expect("write temp");
    path
}

#[test]
fn every_census_payload_round_trips_byte_exactly_through_the_binary() {
    let dir = corpus_dir();
    for name in CENSUS {
        let source = dir.join(name);
        let original = std::fs::read(&source).unwrap_or_else(|e| panic!("read {name}: {e}"));

        let frame = encode(&source, &[]);
        let frame_path = write_temp(&format!("{name}.cbw"), &frame);

        let decoded = run(&["decode", frame_path.to_str().unwrap()]);
        assert!(
            decoded.status.success(),
            "decode {name} failed: {}",
            String::from_utf8_lossy(&decoded.stderr)
        );
        assert_eq!(
            decoded.stdout, original,
            "{name}: decoded output is not byte-identical to the input"
        );
    }
}

/// The container the two-container defect was about: on some payloads the
/// encoder's no-regression rail correctly declines to compress and emits a raw
/// frame. Both containers must survive the same CLI path — that is precisely
/// what the browser decoder could not do until PR #136.
#[test]
fn the_binary_reads_back_whatever_container_the_encoder_chose() {
    let dir = corpus_dir();
    let mut modes = std::collections::BTreeSet::new();
    for name in CENSUS {
        let source = dir.join(name);
        // Small blocks inflate the descriptor cost and are the setting that
        // pushed woff2 over into a verbatim copy.
        let frame = encode(&source, &["--block-size", "4096"]);
        assert!(frame.len() > 6, "{name}: frame is impossibly short");
        modes.insert(frame[5]);

        let frame_path = write_temp(&format!("{name}.blk.cbw"), &frame);
        let decoded = run(&["decode", frame_path.to_str().unwrap()]);
        assert!(
            decoded.status.success(),
            "decode {name} at 4 KiB blocks failed: {}",
            String::from_utf8_lossy(&decoded.stderr)
        );
        assert_eq!(
            decoded.stdout,
            std::fs::read(&source).unwrap(),
            "{name}: 4 KiB-block round trip is not byte-exact"
        );
    }
    assert!(
        modes.len() > 1,
        "expected the census at 4 KiB blocks to exercise more than one container, saw {modes:?} — \
         if the encoder's rail changed, this test is no longer covering the two-container case"
    );
}

#[test]
fn streaming_decode_matches_whole_buffer_decode_on_every_payload() {
    let dir = corpus_dir();
    for name in CENSUS {
        let source = dir.join(name);
        let original = std::fs::read(&source).unwrap();
        let frame = encode(&source, &["--block-size", "4096"]);
        let frame_path = write_temp(&format!("{name}.stream.cbw"), &frame);
        let path = frame_path.to_str().unwrap();

        let streamed = run(&["decode", "--stream", "--chunk", "1024", path]);
        assert!(
            streamed.status.success(),
            "streaming decode {name} failed: {}",
            String::from_utf8_lossy(&streamed.stderr)
        );
        assert_eq!(
            streamed.stdout, original,
            "{name}: streaming decode disagrees with the input"
        );
    }
}

#[test]
fn a_truncated_frame_is_refused_rather_than_silently_short() {
    let dir = corpus_dir();
    let source = dir.join("tailwind.css");
    let frame = encode(&source, &[]);
    let truncated = &frame[..frame.len() - 8];
    let path = write_temp("truncated.cbw", truncated);

    let out = run(&["decode", path.to_str().unwrap()]);
    assert!(!out.status.success(), "a truncated frame decoded cleanly");
    assert_eq!(out.status.code(), Some(3), "truncation must exit 3");
    assert!(
        out.stdout.is_empty(),
        "non-streaming decode wrote output for a frame it could not verify"
    );
}

/// Streaming trades verification order for latency, and the CLI must not
/// pretend otherwise: a corrupted frame still fails, but only after bytes have
/// gone out. Both halves are asserted here, because only asserting the failure
/// would pass just as well if the decoder had refused the frame up front —
/// which is the safe behaviour the streaming API deliberately does not have.
#[test]
fn a_flipped_checksum_fails_the_stream_only_after_bytes_are_already_out() {
    let dir = corpus_dir();
    let source = dir.join("tailwind.css");
    let mut frame = encode(&source, &["--block-size", "1024"]);
    assert_eq!(frame[5], 18, "expected a MODE_WEB frame to corrupt");
    // Bytes 6..10 are the declared length; 10..14 are the whole-content
    // checksum, which is the field `finish()` — and only `finish()` — checks.
    frame[10] ^= 0x01;
    let path = write_temp("corrupt.cbw", &frame);

    let out = run(&[
        "decode",
        "--stream",
        "--chunk",
        "512",
        path.to_str().unwrap(),
    ]);
    assert!(
        !out.status.success(),
        "a frame with a flipped checksum streamed to a clean exit"
    );
    assert_eq!(out.status.code(), Some(3));
    assert!(
        !out.stdout.is_empty(),
        "nothing was emitted before the checksum was rejected — the frame was \
         refused up front, so this test is no longer covering the property that \
         progressive output precedes verification"
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("checksum"),
        "expected a checksum rejection, got: {}",
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn usage_errors_are_distinguishable_from_decode_errors() {
    assert_eq!(run(&[]).status.code(), Some(1), "no command");
    assert_eq!(run(&["encode"]).status.code(), Some(1), "no input file");
    assert_eq!(
        run(&["encode", "--block-size", "0", "x"]).status.code(),
        Some(1),
        "zero block size"
    );
    assert_eq!(
        run(&["frobnicate", "x"]).status.code(),
        Some(1),
        "unknown command"
    );
    assert_eq!(
        run(&["decode", "/nonexistent/path/nope"]).status.code(),
        Some(2),
        "unreadable input is I/O, not a decode failure"
    );
    assert!(run(&["--version"]).status.success());
}
