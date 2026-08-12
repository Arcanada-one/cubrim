//! CUBR-0101: find the smallest real-image input for which `MODE_GEOCM` wins the
//! competitive pick.
//!
//! CUBR-0099 established that the hostile-input fuzz corpus never reaches GeoCM:
//! 0 of 288 encodes produced mode 17, including two synthetic payloads written for
//! the geometric models and all ten committed corpus fixtures. The open question is
//! whether that is because synthetic data is the wrong shape, or because GeoCM only
//! wins above some size — and the answer decides whether a committable fixture is
//! plausible at all.
//!
//! This bisects prefixes of a real GeoCM winner. Give it a file whose full encoding
//! is known to be mode 17 (the NEW-24 campaign's control archives show `x-ray` and
//! `mr` are) and it reports, per prefix size, which container mode wins. The
//! smallest prefix that still yields 17 is the floor being looked for.
//!
//! ```text
//! cargo run --release --example geocm_floor -- /path/to/x-ray
//! ```
//!
//! Prefixes are used rather than downscaled images on purpose: a prefix of a real
//! image is still real image data, so a negative result cannot be blamed on the
//! synthesis.

use cubrim::config::EncodeConfig;
use std::fs;

fn mode_name(m: u8) -> &'static str {
    match m {
        0 => "CUBE",
        1 => "RAW",
        2 => "CHUNKED",
        3 => "LZ",
        7 => "MED16",
        8 => "BCJ",
        13 => "RECORDCM",
        16 => "CM2",
        17 => "GEOCM",
        _ => "other",
    }
}

fn main() {
    let path = match std::env::args().nth(1) {
        Some(p) => p,
        None => {
            eprintln!("usage: geocm_floor <file-known-to-encode-as-mode-17>");
            std::process::exit(2);
        }
    };
    let data = match fs::read(&path) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("cannot read {path}: {e}");
            std::process::exit(2);
        }
    };
    println!("source {path}: {} bytes", data.len());

    // Powers of two from 32 KiB up, plus the whole file. Small enough at the bottom
    // that a committed fixture would be defensible; large enough at the top to
    // confirm the known-positive control.
    let mut sizes: Vec<usize> = std::env::args()
        .skip(2)
        .filter_map(|a| a.parse::<usize>().ok())
        .collect();
    if sizes.is_empty() {
        sizes = (15..27).map(|k| 1usize << k).collect();
        sizes.push(data.len());
    }
    sizes.sort_unstable();
    sizes.retain(|&s| s <= data.len() && s > 0);
    sizes.dedup();

    let mut smallest_geocm: Option<usize> = None;
    for size in sizes {
        let slice = &data[..size];
        let config = EncodeConfig::v1_default();
        let blob = cubrim::encode_with_config(slice, &config);
        let mode = blob.get(5).copied().unwrap_or(255);
        // A mode reading is only meaningful if the stream is actually valid.
        let rt = cubrim::decode(&blob).map(|d| d == slice).unwrap_or(false);
        println!(
            "  {:>10} B -> mode {:>3} {:<9} {:>10} B archive  round-trip {}",
            size,
            mode,
            mode_name(mode),
            blob.len(),
            if rt { "OK" } else { "FAIL" }
        );
        if mode == 17 && rt && smallest_geocm.is_none() {
            smallest_geocm = Some(size);
        }
    }

    match smallest_geocm {
        Some(s) => println!(
            "\nsmallest prefix winning MODE_GEOCM: {s} B ({:.1} KiB)",
            s as f64 / 1024.0
        ),
        None => println!(
            "\nno prefix tested won MODE_GEOCM — the floor is above the largest \
             size tried, or this input never selects GeoCM"
        ),
    }
}
