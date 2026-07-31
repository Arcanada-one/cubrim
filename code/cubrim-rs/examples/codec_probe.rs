//! Codec-level probe used by the CUBR-0075 speed/streaming measurement harness.
//!
//! The shipped `cubrim` CLI operates on `.cbr` archives. The hypotheses in
//! CUBR-0075 are about the codec itself, so this example exposes the raw
//! `encode`/`decode` entry points plus a content-addressed capability manifest.
//! It is a measurement instrument, not a product surface: it prints machine
//! -readable lines on stdout and never inspects its input beyond the codec.
//!
//! Usage:
//!   codec_probe encode <input> <output> [scheme] [--no-square-limit]
//!   codec_probe decode <input> <output>
//!   codec_probe mode   <blob>            -- report cube vs raw-store
//!   codec_probe capabilities             -- emit the capability manifest as JSON
//!
//! Exit codes: 0 success, 1 decode/encode error (never a panic), 2 usage error.

use cubrim::config::{EncodeConfig, ValueScheme};
use std::process::ExitCode;

/// Map a scheme name to the value scheme it selects. The name is the wire
/// vocabulary the measurement harness records, so it must stay stable.
fn value_scheme(name: &str) -> Option<ValueScheme> {
    Some(match name {
        "bitpack-fixed" => ValueScheme::BitpackFixed,
        "rle-codes" => ValueScheme::RleCodes,
        "entropy" => ValueScheme::Entropy,
        "entropy-context" => ValueScheme::EntropyContext,
        "entropy-context2" => ValueScheme::EntropyContext2,
        "bwt-entropy" => ValueScheme::BwtEntropy,
        "bwt-rans" => ValueScheme::BwtRans,
        "order2-rans" => ValueScheme::Order2Rans,
        "bwt-adaptive" => ValueScheme::BwtAdaptive,
        "bwt-context-mix" => ValueScheme::BwtContextMix,
        "bwt-geo-mix" => ValueScheme::BwtGeoMix,
        _ => return None,
    })
}

/// Cubrim v1 header: [magic 4B][version 1B][mode 1B]..., so the mode
/// discriminant sits at offset 5. See src/header.rs.
const MODE_OFFSET: usize = 5;

fn usage() -> ExitCode {
    eprintln!(
        "usage: codec_probe encode|decode <input> <output> | mode <blob> | capabilities"
    );
    ExitCode::from(2)
}

fn read(path: &str) -> Result<Vec<u8>, String> {
    std::fs::read(path).map_err(|error| format!("read {path}: {error}"))
}

fn write(path: &str, bytes: &[u8]) -> Result<(), String> {
    std::fs::write(path, bytes).map_err(|error| format!("write {path}: {error}"))
}

/// The capability manifest the hypothesis evaluator consumes.
///
/// Every field is a fact about *this* build, established from the codec's own
/// API shape, not an aspiration. `incremental_decoder_nonempty_output` is false
/// because `decode` takes a complete blob and returns a complete `Vec<u8>`:
/// there is no API through which a caller could observe a byte before the whole
/// input has been supplied.
fn capabilities() -> String {
    let fields: [(&str, &str); 6] = [
        ("codec_key", "\"cubrim-file-v1\""),
        ("codec_version", concat!("\"", env!("CARGO_PKG_VERSION"), "\"")),
        ("incremental_decoder_nonempty_output", "false"),
        ("independent_block_decode", "false"),
        ("allocation_telemetry", "false"),
        ("profile_pair_static_dynamic", "false"),
    ];
    let body = fields
        .iter()
        .map(|(key, value)| format!("  \"{key}\": {value}"))
        .collect::<Vec<_>>()
        .join(",\n");
    format!("{{\n{body}\n}}")
}

fn run(args: &[String]) -> Result<(), String> {
    match args[0].as_str() {
        "encode" => {
            if args.len() < 3 {
                return Err("encode needs <input> <output> [scheme] [--no-square-limit]".into());
            }
            let input = read(&args[1])?;
            let mut config = EncodeConfig::v1_default();
            for extra in &args[3..] {
                if extra == "--no-square-limit" {
                    // Lifts the b*b cube-eligibility ceiling so inputs above
                    // 64 KiB can be measured in cube mode instead of raw store.
                    config.use_square_limit = false;
                } else {
                    config.value_scheme = value_scheme(extra)
                        .ok_or_else(|| format!("unknown value scheme {extra}"))?;
                }
            }
            let blob = cubrim::encode_with_config(&input, &config);
            write(&args[2], &blob)?;
            println!("input_bytes={} output_bytes={}", input.len(), blob.len());
            Ok(())
        }
        "decode" => {
            if args.len() != 3 {
                return Err("decode needs <input> <output>".into());
            }
            let blob = read(&args[1])?;
            let decoded = cubrim::decode(&blob).map_err(|error| error.to_string())?;
            write(&args[2], &decoded)?;
            println!("input_bytes={} output_bytes={}", blob.len(), decoded.len());
            Ok(())
        }
        "mode" => {
            if args.len() != 2 {
                return Err("mode needs <blob>".into());
            }
            let blob = read(&args[1])?;
            let mode = blob
                .get(MODE_OFFSET)
                .ok_or_else(|| "blob too short to carry a mode".to_string())?;
            println!(
                "mode={}",
                match *mode {
                    cubrim::header::MODE_CUBE => "cube",
                    cubrim::header::MODE_RAW => "raw_store",
                    other => return Err(format!("unknown mode discriminant {other}")),
                }
            );
            Ok(())
        }
        "capabilities" => {
            println!("{}", capabilities());
            Ok(())
        }
        other => Err(format!("unknown command {other}")),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        return usage();
    }
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
