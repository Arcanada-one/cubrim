// Cubrim CLI — compress / decompress subcommands.
// R6: uses the library encode/decode API; no algorithm logic here.
//
// Usage:
//   cubrim compress   <input> <output> [--raw-store-bound N]
//   cubrim decompress <input> <output>

use std::env;
use std::fs;
use std::process;

use cubrim::{encode, decode, encode_with_config, EncodeConfig};

fn usage() {
    eprintln!("Usage:");
    eprintln!("  cubrim compress   <input> <output> [--raw-store-bound N]");
    eprintln!("  cubrim decompress <input> <output>");
    process::exit(1);
}

fn parse_flag_usize(args: &[String], flag: &str, default: usize) -> usize {
    for i in 0..args.len().saturating_sub(1) {
        if args[i] == flag {
            if let Ok(v) = args[i + 1].parse::<usize>() {
                return v;
            }
        }
    }
    default
}

fn cmd_compress(input: &str, output: &str, config: &EncodeConfig) -> Result<(), Box<dyn std::error::Error>> {
    let data = fs::read(input)?;
    let blob = encode_with_config(&data, config);
    fs::write(output, &blob)?;
    eprintln!(
        "compressed: {} bytes -> {} bytes",
        data.len(),
        blob.len()
    );
    Ok(())
}

fn cmd_decompress(input: &str, output: &str) -> Result<(), Box<dyn std::error::Error>> {
    let blob = fs::read(input)?;
    let data = decode(&blob)?;
    fs::write(output, &data)?;
    eprintln!(
        "decompressed: {} bytes -> {} bytes",
        blob.len(),
        data.len()
    );
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 4 {
        usage();
    }

    let subcmd = &args[1];
    let input = &args[2];
    let output = &args[3];
    let extra_args = &args[4..];

    let result = match subcmd.as_str() {
        "compress" => {
            let mut config = EncodeConfig::v1_default();
            config.raw_store_bound = parse_flag_usize(extra_args, "--raw-store-bound", config.raw_store_bound);
            cmd_compress(input, output, &config)
        }
        "decompress" => cmd_decompress(input, output),
        _ => {
            eprintln!("Unknown subcommand: '{subcmd}'");
            usage();
            unreachable!()
        }
    };

    if let Err(e) = result {
        eprintln!("Error: {e}");
        process::exit(1);
    }
}
