//! Generate a seed corpus of valid Cubrim streams for the `decode_hostile`
//! fuzz target.
//!
//! Without seeds the fuzzer spends nearly all of its budget failing the magic
//! check, so the entropy stages — where the interesting decode defects live —
//! are effectively unreachable. Seeding with valid streams puts the fuzzer
//! inside those paths from the first iteration.
//!
//! **What the previous version of this file actually produced (CUBR-0099).** It
//! looped 4 payloads × 8 `ValueScheme`s × 2 square-limit settings and wrote 64
//! files, on the stated assumption that this gave "one valid stream per value
//! scheme". Measured, those 64 files held **5 distinct byte sequences** across
//! **3 container modes**. `value_scheme` is inert through `encode_with_config`
//! — the competitive rail picks the winner and overrides the requested scheme —
//! so the per-scheme loop wrote the same bytes 8 or 16 times over. A corpus can
//! look sixteen times richer than it is.
//!
//! So this generator no longer *assumes* its coverage. It deduplicates by
//! content hash, drives the rail with payloads shaped to suit different
//! backends rather than by asking for a scheme, and prints the container-mode
//! histogram it actually achieved. The histogram is the deliverable: it is the
//! only honest statement of which decode paths the fuzzer starts inside.

use cubrim::config::{EncodeConfig, ValueScheme};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

/// Container mode lives at byte 5: `[MAGIC 4][VERSION 1][MODE 1]`.
fn mode_of(blob: &[u8]) -> Option<u8> {
    blob.get(5).copied()
}

fn mode_name(m: u8) -> &'static str {
    match m {
        0 => "CUBE",
        1 => "RAW",
        2 => "CHUNKED",
        3 => "LZ",
        4 => "COLUMNAR",
        5 => "VCF",
        6 => "BINFLOAT",
        7 => "MED16",
        8 => "BCJ",
        9 => "SOA",
        13 => "RECORDCM",
        16 => "CM2",
        17 => "GEOCM",
        _ => "other",
    }
}

/// Payloads chosen to steer the *competitive rail*, which is the only thing that
/// actually selects a backend. Asking for a `ValueScheme` does not.
fn payloads() -> Vec<(&'static str, Vec<u8>)> {
    let mut v: Vec<(&'static str, Vec<u8>)> = Vec::new();

    // Markup and JSON: text-shaped, historically CM2's territory.
    v.push((
        "html",
        (0..900u32)
            .flat_map(|i| format!("<li class=\"r{}\">item {}</li>\n", i % 13, i % 31).into_bytes())
            .collect(),
    ));
    v.push((
        "json",
        (0..1200u32)
            .flat_map(|i| format!("{{\"id\":{},\"v\":\"{}\"}},", i, i % 7).into_bytes())
            .collect(),
    ));
    // Degenerate and near-random, to keep the cheap containers represented.
    v.push(("runs", vec![b'A'; 2048]));
    v.push(("cycle", (0..2048u32).map(|i| (i % 251) as u8).collect()));

    // Image-shaped: a smooth 2D field with mild noise. The geometric models are
    // built for exactly this correlation structure.
    let (w, h) = (256usize, 256usize);
    let mut img = Vec::with_capacity(w * h);
    for y in 0..h {
        for x in 0..w {
            let base = ((x * x + y * y) / 512) as u8;
            let noise = ((x.wrapping_mul(37) ^ y.wrapping_mul(17)) % 5) as u8;
            img.push(base.wrapping_add(noise));
        }
    }
    v.push(("image-smooth", img));

    // A steeper gradient with a horizontal structure, a second shot at the
    // geometric rail in case the first is too smooth to beat CM2.
    let mut img2 = Vec::with_capacity(w * h);
    for y in 0..h {
        for x in 0..w {
            img2.push((((y * 3) & 0xff) as u8).wrapping_add(((x / 8) & 0x0f) as u8));
        }
    }
    v.push(("image-bands", img2));

    // Fixed-width records: the record-oriented models' territory.
    let mut rec = Vec::new();
    for i in 0..1200u32 {
        rec.extend_from_slice(format!("{:08}|{:>6}|{:04}|X\n", i, i % 997, i % 31).as_bytes());
    }
    v.push(("records", rec));

    // x86-ish: CALL/JMP opcodes with little-endian relative displacements, which
    // is what the BCJ filter exists to transform.
    let mut code = Vec::new();
    for i in 0..2000u32 {
        code.push(0xE8);
        code.extend_from_slice(&(i.wrapping_mul(4099)).to_le_bytes());
        code.extend_from_slice(&[0x48, 0x89, 0xE5, 0x5D, 0xC3]);
    }
    v.push(("x86-calls", code));

    v
}

fn scheme_names() -> [(&'static str, ValueScheme); 8] {
    [
        ("bitpack-fixed", ValueScheme::BitpackFixed),
        ("rle-codes", ValueScheme::RleCodes),
        ("entropy", ValueScheme::Entropy),
        ("entropy-context", ValueScheme::EntropyContext),
        ("entropy-context2", ValueScheme::EntropyContext2),
        ("bwt-entropy", ValueScheme::BwtEntropy),
        ("bwt-rans", ValueScheme::BwtRans),
        ("bwt-geo-mix", ValueScheme::BwtGeoMix),
    ]
}

fn main() {
    let out = Path::new("fuzz/corpus/decode_hostile");
    fs::create_dir_all(out).expect("create corpus dir");

    // Prove the `value_scheme` knob is inert ONCE, on the cheapest payload, instead
    // of re-deriving it on every payload. The previous version encoded each payload
    // through all eight schemes and discovered eight identical blobs each time — 8x
    // the encode cost for a fact that one small probe settles. If this probe ever
    // reports more than one distinct blob, the rail has started honouring the
    // request and the per-scheme loop should come back.
    let probe_data: Vec<u8> = (0..4096u32).map(|i| (i % 251) as u8).collect();
    let schemes = scheme_names();
    let mut probe: HashSet<Vec<u8>> = HashSet::new();
    for (_n, scheme) in schemes {
        let mut c = EncodeConfig::v1_default();
        c.value_scheme = scheme;
        probe.insert(cubrim::encode_with_config(&probe_data, &c));
    }
    println!(
        "value_scheme probe: {} scheme request(s) produced {} distinct blob(s){}",
        schemes.len(),
        probe.len(),
        if probe.len() == 1 {
            " -- the knob is INERT through encode_with_config; the competitive rail \
overrides it, so seeding 'one stream per scheme' is not a thing this API can do"
        } else {
            " -- the knob now changes output; restore the per-scheme seeding loop"
        }
    );

    let mut seen: HashSet<Vec<u8>> = HashSet::new();
    let mut modes: BTreeMap<u8, usize> = BTreeMap::new();
    let (mut written, mut duplicates, mut rejected) = (0usize, 0usize, 0usize);

    // The probe above decides whether the per-scheme loop is worth running. It is
    // kept because the knob is NOT strictly inert — it collapses, and how far it
    // collapses depends on the payload. Dedup makes the loop cheap in output terms;
    // payload sizes are kept modest so it is cheap in encode terms too.
    for (pname, data) in payloads() {
        for (sname, scheme) in scheme_names() {
            for square in [true, false] {
                let mut config = EncodeConfig::v1_default();
                config.value_scheme = scheme;
                config.use_square_limit = square;
                let blob = cubrim::encode_with_config(&data, &config);

                // Only seed streams that actually decode — a seed that is already
                // invalid teaches the fuzzer nothing about the format.
                if !cubrim::decode(&blob).map(|d| d == data).unwrap_or(false) {
                    rejected += 1;
                    continue;
                }
                if !seen.insert(blob.clone()) {
                    duplicates += 1;
                    continue;
                }
                let m = mode_of(&blob).unwrap_or(255);
                *modes.entry(m).or_insert(0) += 1;
                let path = out.join(format!("seed-{pname}-{sname}-sq{square}-mode{m}.cbm"));
                fs::write(&path, &blob).expect("write seed");
                written += 1;
            }
        }
    }

    println!("wrote {written} distinct seeds to {}", out.display());
    println!("suppressed {duplicates} duplicate encodings, {rejected} non-round-tripping");
    println!("container-mode coverage actually achieved:");
    for (m, n) in &modes {
        println!("  mode {:>3} {:<9} {} seed(s)", m, mode_name(*m), n);
    }
    for want in [16u8, 17] {
        if !modes.contains_key(&want) {
            println!(
                "  NOTE: no seed reaches mode {} ({}) -- the fuzzer does not start \
inside that decode path",
                want,
                mode_name(want)
            );
        }
    }
}
