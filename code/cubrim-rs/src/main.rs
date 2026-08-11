#![forbid(unsafe_code)]

mod archive;
mod cli;
mod crypto;
mod license;
mod self_update;

use std::process;

use archive::{add_archive, delete_archive_members, extract_archive, extract_archive_flat, list_archive, test_archive};
use clap::{CommandFactory, Parser};
use cli::{Cli, Commands};

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
        Some(Commands::Add(args)) => add_archive(args),
        Some(Commands::Extract(args)) => extract_archive(args),
        Some(Commands::ExtractFlat(args)) => extract_archive_flat(args),
        Some(Commands::List(args)) => list_archive(args),
        Some(Commands::Test(args)) => test_archive(args),
        Some(Commands::Delete(args)) => delete_archive_members(args),
        None => {
            println!("cubrim {}", env!("CARGO_PKG_VERSION"));
            let mut cmd = Cli::command();
            cmd.print_help().map_err(AppError::from)?;
            println!();
            Ok(())
        }
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
