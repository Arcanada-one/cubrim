use addressor::router::Addressor;
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "cubrim-addr", version, about = "Cubrim-2 Addressor — fleet CAS/dedup router over Cubrim-1")]
struct Cli {
    /// Addressor root directory (store + catalog)
    #[arg(long, env = "ADDRESSOR_ROOT", default_value = "./addr-root")]
    root: PathBuf,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Store a file; prints the ordinal reference
    Store {
        file: PathBuf,
        /// Build a Merkle verification sidecar (optional, default off)
        #[arg(long)]
        verify: bool,
    },
    /// Retrieve by ordinal reference to stdout or -o file
    Retrieve {
        ordinal: u64,
        #[arg(short, long)]
        out: Option<PathBuf>,
        /// Verify against the Merkle sidecar (optional, default off)
        #[arg(long)]
        verify: bool,
    },
    /// Store/catalog statistics
    Stats,
    /// Print the BLAKE3-256 hex of a file (used by sync scripts)
    Hash { file: PathBuf },
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Store { file, verify } => {
            let data = std::fs::read(&file)?;
            let mut a = Addressor::open(&cli.root)?;
            let out = a.store_bytes(&data)?;
            if verify && !out.deduped {
                // runtime-optional Merkle sidecar over the stored container
                let entry = a.catalog.entry(out.ordinal)?.expect("fresh entry");
                let blob_path = a.cas.blob_path(&entry.blob);
                let blob_bytes = a.cas.get(&entry.blob)?;
                addressor::merkle::write_sidecar(&blob_path, &blob_bytes)?;
            }
            println!(
                "{} scheme={:?} deduped={} container_bytes={}",
                out.ordinal, out.scheme, out.deduped, out.container_len
            );
        }
        Cmd::Retrieve { ordinal, out, verify } => {
            let a = Addressor::open(&cli.root)?;
            if verify {
                let entry = a
                    .catalog
                    .entry(ordinal)?
                    .ok_or_else(|| format!("unknown ordinal {ordinal}"))?;
                let blob_path = a.cas.blob_path(&entry.blob);
                let blob_bytes = a.cas.get(&entry.blob)?;
                addressor::merkle::verify_sidecar(&blob_path, &blob_bytes)?;
            }
            let data = a.retrieve(ordinal)?;
            match out {
                Some(p) => std::fs::write(p, &data)?,
                None => {
                    use std::io::Write;
                    std::io::stdout().write_all(&data)?;
                }
            }
        }
        Cmd::Hash { file } => {
            let data = std::fs::read(&file)?;
            println!("{}", blake3::hash(&data).to_hex());
        }
        Cmd::Stats => {
            let a = Addressor::open(&cli.root)?;
            println!("catalog_entries={}", a.catalog.len()?);
            println!("entries_r1={}", a.catalog.entries_r1()?);
            println!("cas_blobs={}", a.cas.blob_count()?);
            println!("fp16_slots={} bytes_per_slot=2.0", a.catalog.fp16_slot_count());
        }
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}
