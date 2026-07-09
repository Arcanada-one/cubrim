#![forbid(unsafe_code)]

mod archive;
mod cli;
mod crypto;

use std::process;

use archive::{add_archive, extract_or_decompress, list_archive, test_archive};
use clap::Parser;
use cli::{Cli, Commands};
use cubrim::{decode, encode_with_config};

fn main() {
    let cli = Cli::parse();
    let result = match cli.command {
        Commands::Compress(args) => {
            let config = args.encode_config();
            let data = std::fs::read(&args.input);
            match data {
                Ok(data) => {
                    let blob = encode_with_config(&data, &config);
                    std::fs::write(&args.output, &blob)
                        .map(|_| {
                            if !args.quiet {
                                eprintln!(
                                    "compressed: {} bytes -> {} bytes",
                                    data.len(),
                                    blob.len()
                                );
                            }
                        })
                        .map_err(AppError::from)
                }
                Err(err) => Err(AppError::from(err)),
            }
        }
        Commands::Decompress(args) => {
            let blob = std::fs::read(&args.input);
            match blob {
                Ok(blob) => match decode(&blob) {
                    Ok(data) => std::fs::write(&args.output, &data)
                        .map(|_| {
                            if !args.quiet {
                                eprintln!(
                                    "decompressed: {} bytes -> {} bytes",
                                    blob.len(),
                                    data.len()
                                );
                            }
                        })
                        .map_err(AppError::from),
                    Err(err) => Err(AppError::integrity(err.to_string())),
                },
                Err(err) => Err(AppError::from(err)),
            }
        }
        Commands::Add(args) => add_archive(args),
        Commands::Extract(args) => extract_or_decompress(args),
        Commands::List(args) => list_archive(args),
        Commands::Test(args) => test_archive(args),
    };

    if let Err(err) = result {
        eprintln!("Error: {}", err.message);
        process::exit(err.exit_code);
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
