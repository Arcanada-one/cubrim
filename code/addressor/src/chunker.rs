//! CDC chunking: fastcdc v2020, 2/8/32 KiB (min = avg/4, max = 4*avg).
//!
//! The parameters are part of the on-disk format contract: changing them
//! destroys dedup against existing catalogs, so they are exposed as constants
//! and recorded in the store config (checked on open).

use fastcdc::v2020::FastCDC;

pub const CHUNK_MIN: usize = 2048;
pub const CHUNK_AVG: usize = 8192;
pub const CHUNK_MAX: usize = 32768;

#[derive(Debug, Clone)]
pub struct Chunk {
    pub offset: u64,
    pub data: Vec<u8>,
}

/// Splits `data` into content-defined chunks with the pinned 2/8/32 KiB params.
pub fn chunk_bytes(data: &[u8]) -> Vec<Chunk> {
    if data.is_empty() {
        return Vec::new();
    }
    FastCDC::new(data, CHUNK_MIN, CHUNK_AVG, CHUNK_MAX)
        .map(|entry| Chunk {
            offset: entry.offset as u64,
            data: data[entry.offset..entry.offset + entry.length].to_vec(),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pseudo_random(len: usize, seed: u64) -> Vec<u8> {
        // deterministic xorshift fill — no external RNG dep
        let mut x = seed.wrapping_mul(0x9E3779B97F4A7C15) | 1;
        (0..len)
            .map(|_| {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                (x & 0xff) as u8
            })
            .collect()
    }

    #[test]
    fn chunks_cover_input_exactly() {
        let data = pseudo_random(200_000, 42);
        let chunks = chunk_bytes(&data);
        let total: usize = chunks.iter().map(|c| c.data.len()).sum();
        assert_eq!(total, data.len());
        let mut rebuilt = Vec::new();
        for c in &chunks {
            assert_eq!(c.offset as usize, rebuilt.len());
            rebuilt.extend_from_slice(&c.data);
        }
        assert_eq!(rebuilt, data);
    }

    #[test]
    fn chunk_sizes_respect_bounds() {
        let data = pseudo_random(500_000, 7);
        let chunks = chunk_bytes(&data);
        for c in &chunks[..chunks.len() - 1] {
            assert!(c.data.len() >= CHUNK_MIN, "chunk below min");
            assert!(c.data.len() <= CHUNK_MAX, "chunk above max");
        }
    }

    #[test]
    fn shifted_content_shares_chunks() {
        // content-defined boundaries: inserting a prefix must not re-chunk
        // the whole stream — the tail chunks realign.
        let base = pseudo_random(150_000, 99);
        let mut shifted = pseudo_random(3_000, 5);
        shifted.extend_from_slice(&base);
        let a: std::collections::HashSet<_> = chunk_bytes(&base)
            .into_iter()
            .map(|c| *blake3::hash(&c.data).as_bytes())
            .collect();
        let b: std::collections::HashSet<_> = chunk_bytes(&shifted)
            .into_iter()
            .map(|c| *blake3::hash(&c.data).as_bytes())
            .collect();
        let shared = a.intersection(&b).count();
        assert!(shared > 0, "no shared chunks after shift — CDC broken");
    }

    #[test]
    fn empty_input_no_chunks() {
        assert!(chunk_bytes(&[]).is_empty());
    }
}
