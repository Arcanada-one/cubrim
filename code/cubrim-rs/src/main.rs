// Cubrim CLI — compress / decompress subcommands.
// R6: uses the library encode/decode API; no algorithm logic here.
//
// Usage:
//   cubrim compress <input> <output>
//   cubrim decompress <input> <output>

use std::env;
use std::fs;
use std::process;

use cubrim::{encode, decode};

fn usage() {
    eprintln!("Usage:");
    eprintln!("  cubrim compress   <input> <output>");
    eprintln!("  cubrim decompress <input> <output>");
    process::exit(1);
}

fn cmd_compress(input: &str, output: &str) -> Result<(), Box<dyn std::error::Error>> {
    let data = fs::read(input)?;
    let blob = encode(&data);
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

    let result = match subcmd.as_str() {
        "compress" => cmd_compress(input, output),
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
