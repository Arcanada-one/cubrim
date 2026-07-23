#![forbid(unsafe_code)]

mod archive;
mod cli;
mod crypto;
mod license;
mod self_update;

use std::process;
use std::time::Instant;

use archive::{add_archive, extract_or_decompress, list_archive, test_archive};
use clap::Parser;
use cli::{Cli, Commands};
use cubrim::{decode, encode_with_config};

fn main() {
    let cli = Cli::parse();
    let result = run(cli);

    if let Err(err) = result {
        eprintln!("Error: {}", err.message);
        process::exit(err.exit_code);
    }
}

fn run(cli: Cli) -> Result<(), AppError> {
    if cli.license {
        return license::show_license();
    }
    let env_accept = std::env::var("CUBRIM_ACCEPT_LICENSE").ok().as_deref() == Some("1");
    if cli.accept_license && cli.command.is_none() && !cli.update {
        return license::accept_license_noninteractive();
    }
    if cli.update {
        if cli.accept_license || env_accept {
            license::accept_license_for_automation()?;
        } else {
            license::ensure_license_accepted()?;
        }
        return self_update::run_update();
    }

    if cli.accept_license || env_accept {
        license::accept_license_for_automation()?;
    } else {
        license::ensure_license_accepted()?;
    }

    match cli.command {
        Some(Commands::Compress(args)) => {
            let started = Instant::now();
            let data = std::fs::read(&args.input);
            match data {
                Ok(data) => {
                    let config = args.encode_config();
                    let blob = encode_with_config(&data, &config);
                    std::fs::write(&args.output, &blob)
                        .map(|_| {
                            if !args.quiet {
                                let secs = started.elapsed().as_secs_f64();
                                let ratio = if data.is_empty() {
                                    0.0
                                } else {
                                    blob.len() as f64 / data.len() as f64
                                };
                                let note = if data.is_empty() {
                                    String::new()
                                } else if ratio >= 1.0 {
                                    " (stored; input not compressible)".to_string()
                                } else {
                                    format!(" ({:.2}x smaller)", 1.0 / ratio)
                                };
                                eprintln!(
                                    "compressed: {} -> {} bytes  ratio {:.4}{}  {}  compress {}",
                                    data.len(),
                                    blob.len(),
                                    ratio,
                                    note,
                                    fmt_throughput(data.len(), secs),
                                    fmt_ms(secs),
                                );
                            }
                        })
                        .map_err(AppError::from)
                }
                Err(err) => Err(AppError::from(err)),
            }
        }
        Some(Commands::Decompress(args)) => {
            let started = Instant::now();
            let blob = std::fs::read(&args.input);
            match blob {
                Ok(blob) => match decode(&blob) {
                    Ok(data) => std::fs::write(&args.output, &data)
                        .map(|_| {
                            if !args.quiet {
                                let secs = started.elapsed().as_secs_f64();
                                eprintln!(
                                    "decompressed: {} -> {} bytes  {}  decompress {}",
                                    blob.len(),
                                    data.len(),
                                    fmt_throughput(data.len(), secs),
                                    fmt_ms(secs),
                                );
                            }
                        })
                        .map_err(AppError::from),
                    Err(err) => Err(AppError::integrity(err.to_string())),
                },
                Err(err) => Err(AppError::from(err)),
            }
        }
        Some(Commands::Add(args)) => add_archive(args),
        Some(Commands::Extract(args)) => extract_or_decompress(args),
        Some(Commands::List(args)) => list_archive(args),
        Some(Commands::Test(args)) => test_archive(args),
        None => Err(AppError::usage(
            "no command supplied; run `cubrim --help` for usage",
        )),
    }
}

/// Human-readable wall-clock duration for the stats line.
fn fmt_ms(secs: f64) -> String {
    let ms = secs * 1000.0;
    if ms < 1.0 {
        format!("{:.2} ms", ms)
    } else if ms < 10000.0 {
        format!("{} ms", ms.round() as u64)
    } else {
        format!("{:.1} s", secs)
    }
}

/// Throughput in decimal MB/s (bytes / 1e6 / seconds). Returns "-" when the
/// elapsed time is too small to measure meaningfully.
fn fmt_throughput(bytes: usize, secs: f64) -> String {
    if secs <= 0.0005 || bytes == 0 {
        "- MB/s".to_string()
    } else {
        format!("{:.1} MB/s", (bytes as f64 / 1.0e6) / secs)
    }
}

#[derive(Debug)]
pub struct AppError {
    message: String,
    exit_code: i32,
}

impl AppError {
    pub fn usage(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            exit_code: 1,
        }
    }

    pub fn integrity(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            exit_code: 2,
        }
    }

    pub fn io(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            exit_code: 3,
        }
    }
}

impl From<std::io::Error> for AppError {
    fn from(value: std::io::Error) -> Self {
        Self::io(value.to_string())
    }
}
