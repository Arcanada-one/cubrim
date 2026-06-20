// Cubrim CLI — compress / decompress subcommands.
// R6: uses the library encode/decode API; no algorithm logic here.
//
// Usage:
//   cubrim compress   <input> <output> [--raw-store-bound N] [--b N] [--n N] [--gap-scheme rle|packed_nibble]
//   cubrim decompress <input> <output>

use std::env;
use std::fs;
use std::process;

use cubrim::{decode, encode_with_config, EncodeConfig, GapScheme, ValueScheme};

fn usage() {
    eprintln!("Usage:");
    eprintln!("  cubrim compress   <input> <output> [--raw-store-bound N] [--b N] [--n N] [--gap-scheme rle|packed_nibble] [--value-scheme bitpack-fixed|rle-codes|entropy|entropy-context|entropy-context-2] [--min-ctx-count N]");
    eprintln!("  cubrim decompress <input> <output>");
    process::exit(1);
}

fn parse_flag_u16(args: &[String], flag: &str) -> Option<u16> {
    for i in 0..args.len().saturating_sub(1) {
        if args[i] == flag {
            if let Ok(v) = args[i + 1].parse::<u16>() {
                return Some(v);
            }
        }
    }
    None
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

fn parse_flag_str<'a>(args: &'a [String], flag: &str) -> Option<&'a str> {
    for i in 0..args.len().saturating_sub(1) {
        if args[i] == flag {
            return Some(&args[i + 1]);
        }
    }
    None
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
            config.b = parse_flag_usize(extra_args, "--b", config.b);
            // --n: optional N override
            if let Some(n_str) = parse_flag_str(extra_args, "--n") {
                match n_str.parse::<usize>() {
                    Ok(n) => config.n_override = Some(n),
                    Err(_) => { eprintln!("Invalid --n value: {n_str}"); process::exit(1); }
                }
            }
            // --gap-scheme: rle (default) or packed_nibble
            if let Some(scheme_str) = parse_flag_str(extra_args, "--gap-scheme") {
                config.gap_scheme = match scheme_str {
                    "rle" | "rle_u16" => GapScheme::RleU16,
                    "packed_nibble" => GapScheme::PackedNibble,
                    other => {
                        eprintln!("Unknown --gap-scheme: {other}. Use rle or packed_nibble.");
                        process::exit(1);
                    }
                };
            }
            // --value-scheme: bitpack-fixed (default), rle-codes, entropy, entropy-context, entropy-context-2
            if let Some(vs_str) = parse_flag_str(extra_args, "--value-scheme") {
                config.value_scheme = match vs_str {
                    "bitpack-fixed" | "bitpack_fixed" => ValueScheme::BitpackFixed,
                    "rle-codes" | "rle_codes" => ValueScheme::RleCodes,
                    "entropy" => ValueScheme::Entropy,
                    "entropy-context" | "entropy_context" => ValueScheme::EntropyContext,
                    "entropy-context-2" | "entropy_context_2" => ValueScheme::EntropyContext2,
                    other => {
                        eprintln!("Unknown --value-scheme: {other}. Use bitpack-fixed, rle-codes, entropy, entropy-context, or entropy-context-2.");
                        process::exit(1);
                    }
                };
            }
            // --min-ctx-count: minimum observation count for order-2 Huffman context tables.
            // Only used when --value-scheme entropy-context-2 is set.
            // Default = ORDER2_DEFAULT_MIN_CTX (128) when not specified.
            if let Some(mcc) = parse_flag_u16(extra_args, "--min-ctx-count") {
                config.min_ctx_count = Some(mcc);
            }
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
