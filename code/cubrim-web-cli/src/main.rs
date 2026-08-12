//! `cubrim-web` — command-line encoder/decoder for the Cubrim Web Profile.
//!
//! The Web Profile shipped as a library and as a browser artefact. It had no
//! command line, and that absence was load-bearing: the web benchmark
//! (`bench/web-benchmark/`) measures every codec as a subprocess that reads a
//! file and writes to stdout, exactly as gzip, brotli and zstd do. With no such
//! binary, `Cubrim-Web` could not be measured against them at all — the format
//! was complete and unmeasurable at the same time.
//!
//! So the argv shape here is not a matter of taste. It mirrors
//! `gzip -9 -c FILE` and `brotli --stdout FILE` so that the candidate runs
//! through the identical sandbox, timing, peak-RSS and round-trip machinery as
//! the incumbents, with nothing special-cased in its favour.
//!
//! ## Which decoder this uses, and why it matters
//!
//! Encoding calls `cubrim`. Decoding calls `cubrim_web_decoder` — the
//! independent reference decoder that the WASM artefact wraps, not the
//! encoder's own inverse. A decode measured through this binary is therefore a
//! statement about the decoder a browser actually runs. That choice is the
//! direct lesson of the two-container defect (PR #136): every in-process Rust
//! test passed while the deployed artefact could not read frames the encoder
//! legitimately emitted, because the tests went through `cubrim::decode`, which
//! understands every mode, and the artefact did not.
//!
//! ## Usage
//!
//! ```text
//! cubrim-web encode [--block-size N] FILE   # frame to stdout
//! cubrim-web decode FILE                    # original to stdout (verified)
//! cubrim-web decode --stream [--chunk N] FILE
//! cubrim-web --version
//! ```
//!
//! `decode --stream` emits each block as it completes, before the whole-content
//! checksum can be verified. That is the property the streaming API exists to
//! provide and the one it cannot make safe: on a corrupt or truncated frame the
//! command exits non-zero *after* having already written bytes. Plain `decode`
//! writes nothing until the frame verifies, and is the default for that reason.

use std::io::{self, Read, Write};
use std::path::Path;
use std::process::ExitCode;

use cubrim::{encode_with_config, EncodeConfig};
use cubrim_web_decoder::{decode_with_limits, DecodeLimits, StreamDecoder};

const USAGE: &str = "\
cubrim-web — Cubrim Web Profile (MODE_WEB) encoder/decoder

USAGE:
    cubrim-web encode [--block-size N] <FILE>
    cubrim-web decode [--stream [--chunk N]] <FILE>
    cubrim-web --version

Output always goes to stdout, like gzip -c / brotli --stdout.

OPTIONS:
    --block-size N   cut the frame into blocks of ~N output bytes. A boundary
                     resets the entropy tables but not the output window, so
                     matches still reach across it. Costs one table descriptor
                     per extra block; buys per-region tables and streaming.
    --stream         decode incrementally, writing each block as it completes.
                     Emits bytes BEFORE the whole-content checksum is checked.
    --chunk N        feed the stream decoder N bytes at a time (default 65536).
                     Only meaningful with --stream; models a network read size.

EXIT CODES:
    0 success   1 usage   2 I/O   3 decode rejected the frame
";

const EXIT_USAGE: u8 = 1;
const EXIT_IO: u8 = 2;
const EXIT_DECODE: u8 = 3;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("cubrim-web: {}", err.message);
            ExitCode::from(err.code)
        }
    }
}

struct Failure {
    code: u8,
    message: String,
}

fn fail(code: u8, message: impl Into<String>) -> Failure {
    Failure {
        code,
        message: message.into(),
    }
}

fn run(args: &[String]) -> Result<(), Failure> {
    let Some(first) = args.first() else {
        eprint!("{USAGE}");
        return Err(fail(EXIT_USAGE, "no command given"));
    };

    match first.as_str() {
        "--version" | "-V" => {
            println!("cubrim-web {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        "--help" | "-h" | "help" => {
            print!("{USAGE}");
            Ok(())
        }
        "encode" => encode(&args[1..]),
        "decode" => decode(&args[1..]),
        other => {
            eprint!("{USAGE}");
            Err(fail(EXIT_USAGE, format!("unknown command {other:?}")))
        }
    }
}

/// Parse `--name VALUE` where VALUE is a positive integer, removing both from
/// the argument list. Returns `None` when the flag is absent.
fn take_usize_flag(args: &mut Vec<String>, name: &str) -> Result<Option<usize>, Failure> {
    let Some(index) = args.iter().position(|a| a == name) else {
        return Ok(None);
    };
    let raw = args
        .get(index + 1)
        .ok_or_else(|| fail(EXIT_USAGE, format!("{name} needs a value")))?
        .clone();
    let value: usize = raw
        .parse()
        .map_err(|_| fail(EXIT_USAGE, format!("{name} value {raw:?} is not a number")))?;
    if value == 0 {
        return Err(fail(
            EXIT_USAGE,
            format!("{name} must be greater than zero"),
        ));
    }
    args.drain(index..=index + 1);
    Ok(Some(value))
}

fn take_flag(args: &mut Vec<String>, name: &str) -> bool {
    match args.iter().position(|a| a == name) {
        Some(index) => {
            args.remove(index);
            true
        }
        None => false,
    }
}

fn single_path(args: &[String]) -> Result<&Path, Failure> {
    match args {
        [one] => Ok(Path::new(one)),
        [] => Err(fail(EXIT_USAGE, "no input file given")),
        _ => Err(fail(
            EXIT_USAGE,
            format!("expected exactly one input file, got {}", args.len()),
        )),
    }
}

fn read_input(path: &Path) -> Result<Vec<u8>, Failure> {
    if path == Path::new("-") {
        let mut buffer = Vec::new();
        io::stdin()
            .lock()
            .read_to_end(&mut buffer)
            .map_err(|err| fail(EXIT_IO, format!("reading stdin: {err}")))?;
        return Ok(buffer);
    }
    std::fs::read(path).map_err(|err| fail(EXIT_IO, format!("reading {}: {err}", path.display())))
}

fn write_stdout(bytes: &[u8]) -> Result<(), Failure> {
    let mut out = io::stdout().lock();
    out.write_all(bytes)
        .and_then(|()| out.flush())
        .map_err(|err| fail(EXIT_IO, format!("writing stdout: {err}")))
}

fn encode(args: &[String]) -> Result<(), Failure> {
    let mut args = args.to_vec();
    let block_size = take_usize_flag(&mut args, "--block-size")?;
    let path = single_path(&args)?;
    let input = read_input(path)?;

    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;
    config.web_block_size = block_size;

    write_stdout(&encode_with_config(&input, &config))
}

fn decode(args: &[String]) -> Result<(), Failure> {
    let mut args = args.to_vec();
    let streaming = take_flag(&mut args, "--stream");
    let chunk = take_usize_flag(&mut args, "--chunk")?.unwrap_or(64 * 1024);
    if !streaming && args.iter().any(|a| a == "--chunk") {
        return Err(fail(EXIT_USAGE, "--chunk is only meaningful with --stream"));
    }
    let path = single_path(&args)?;
    let frame = read_input(path)?;

    if streaming {
        decode_streaming(&frame, chunk)
    } else {
        let output = decode_with_limits(&frame, &DecodeLimits::default())
            .map_err(|err| fail(EXIT_DECODE, err.0))?;
        write_stdout(&output)
    }
}

fn decode_streaming(frame: &[u8], chunk: usize) -> Result<(), Failure> {
    let mut stream = StreamDecoder::new(DecodeLimits::default());
    let mut emitted = 0usize;

    for piece in frame.chunks(chunk) {
        let fresh = stream.push(piece).map_err(|err| fail(EXIT_DECODE, err.0))?;
        if !fresh.is_empty() {
            // Copy before releasing the borrow on `stream`; these are the bytes
            // a progressive consumer would already be rendering.
            let ready = fresh.to_vec();
            emitted += ready.len();
            write_stdout(&ready)?;
        }
    }

    let complete = stream.finish().map_err(|err| {
        fail(
            EXIT_DECODE,
            format!(
                "{} (after {emitted} byte(s) had already been written to stdout — \
                 a streaming consumer must be prepared to discard them)",
                err.0
            ),
        )
    })?;

    // `finish` hands back everything it decoded. Anything not already emitted
    // belongs to a block that completed only at the end of the frame.
    if complete.len() > emitted {
        write_stdout(&complete[emitted..])?;
    } else if complete.len() < emitted {
        return Err(fail(
            EXIT_DECODE,
            format!(
                "stream emitted {emitted} bytes but the frame declares {}",
                complete.len()
            ),
        ));
    }
    Ok(())
}
