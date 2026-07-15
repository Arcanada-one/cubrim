use std::path::Path;

/// Deterministic compressible pseudo-text (no external RNG dep).
pub fn text(n: usize, seed: u64) -> Vec<u8> {
    let words = [
        "alpha", "beta", "gamma", "delta", "fleet", "router", "chunk", "store",
        "matrix", "ordinal", "bloom", "merkle",
    ];
    let mut x = seed.wrapping_mul(0x9E3779B97F4A7C15) | 1;
    let mut out = Vec::new();
    while out.len() < n {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        out.extend_from_slice(words[(x % 12) as usize].as_bytes());
        out.push(b' ');
    }
    out.truncate(n);
    out
}

/// Deterministic incompressible noise.
pub fn noise(n: usize, seed: u64) -> Vec<u8> {
    let mut x = seed.wrapping_mul(0x9E3779B97F4A7C15) | 1;
    (0..n)
        .map(|_| {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            (x & 0xff) as u8
        })
        .collect()
}

pub fn open_addressor(root: &Path) -> addressor::router::Addressor {
    addressor::router::Addressor::open(root).expect("open addressor")
}
