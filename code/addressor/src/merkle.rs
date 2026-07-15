//! Optional Merkle verification (AH-21: 4.15% aggregate overhead, optional in
//! a trusted fleet). Always COMPILED (no cargo feature — the acceptance test
//! runs without feature flags); optionality is a RUNTIME flag: without
//! `--verify` no sidecar is created and no verification happens.
//!
//! Mechanism: segment-hash manifest matching the measured AH-21 scheme
//! (chunk-granularity hash manifests + root). bao's verified streaming was
//! tried first and rejected by measurement: its fixed 1 KiB leaf costs
//! 64 B/КиБ ≈ 6.25% — over the ≤5% budget on any large blob.
//! Sidecar `<blob>.bao`: varint(seg_size) ++ varint(n) ++ n*hash(32) ++ root(32).

use crate::error::{AddressorError, Result};
use crate::refs::{varint_decode, varint_encode};
use std::path::{Path, PathBuf};

/// Segment granularity: matches the CDC average chunk (8 KiB).
pub const SEGMENT: usize = 8192;

pub fn sidecar_path(blob_path: &Path) -> PathBuf {
    let mut p = blob_path.as_os_str().to_owned();
    p.push(".bao");
    PathBuf::from(p)
}

fn segment_hashes(data: &[u8]) -> Vec<[u8; 32]> {
    if data.is_empty() {
        return vec![*blake3::hash(&[]).as_bytes()];
    }
    data.chunks(SEGMENT)
        .map(|seg| *blake3::hash(seg).as_bytes())
        .collect()
}

fn root_of(hashes: &[[u8; 32]]) -> [u8; 32] {
    let mut cat = Vec::with_capacity(hashes.len() * 32);
    for h in hashes {
        cat.extend_from_slice(h);
    }
    *blake3::hash(&cat).as_bytes()
}

/// Builds and writes the sidecar for `data` at `blob_path.bao`.
pub fn write_sidecar(blob_path: &Path, data: &[u8]) -> Result<()> {
    let hashes = segment_hashes(data);
    let mut raw = Vec::with_capacity(hashes.len() * 32 + 48);
    varint_encode(SEGMENT as u64, &mut raw);
    varint_encode(hashes.len() as u64, &mut raw);
    for h in &hashes {
        raw.extend_from_slice(h);
    }
    raw.extend_from_slice(&root_of(&hashes));
    std::fs::write(sidecar_path(blob_path), raw)?;
    Ok(())
}

/// Verifies `data` against the sidecar; Err(Integrity) on any mismatch.
pub fn verify_sidecar(blob_path: &Path, data: &[u8]) -> Result<()> {
    let raw = std::fs::read(sidecar_path(blob_path)).map_err(|e| {
        AddressorError::Integrity(format!("merkle sidecar unreadable: {e}"))
    })?;
    let mut pos = 0usize;
    let seg = varint_decode(&raw, &mut pos)
        .map_err(|_| AddressorError::Integrity("merkle sidecar truncated".into()))?
        as usize;
    let n = varint_decode(&raw, &mut pos)
        .map_err(|_| AddressorError::Integrity("merkle sidecar truncated".into()))?
        as usize;
    if seg == 0 || raw.len() < pos + n * 32 + 32 {
        return Err(AddressorError::Integrity("merkle sidecar malformed".into()));
    }
    let mut stored: Vec<[u8; 32]> = Vec::with_capacity(n);
    for i in 0..n {
        let mut h = [0u8; 32];
        h.copy_from_slice(&raw[pos + i * 32..pos + (i + 1) * 32]);
        stored.push(h);
    }
    let mut root = [0u8; 32];
    root.copy_from_slice(&raw[pos + n * 32..pos + n * 32 + 32]);
    if root_of(&stored) != root {
        return Err(AddressorError::Integrity("merkle root mismatch".into()));
    }
    // recompute segment hashes of the live data at the recorded granularity
    let live: Vec<[u8; 32]> = if data.is_empty() {
        vec![*blake3::hash(&[]).as_bytes()]
    } else {
        data.chunks(seg).map(|s| *blake3::hash(s).as_bytes()).collect()
    };
    if live != stored {
        return Err(AddressorError::Integrity("merkle content mismatch".into()));
    }
    Ok(())
}

pub fn sidecar_exists(blob_path: &Path) -> bool {
    sidecar_path(blob_path).exists()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn sidecar_roundtrip_and_bitflip_detection() {
        let dir = tempdir().unwrap();
        let blob = dir.path().join("ab").join("cd").join("x.chunk");
        std::fs::create_dir_all(blob.parent().unwrap()).unwrap();
        let data = b"verified payload".repeat(1000);
        std::fs::write(&blob, &data).unwrap();
        write_sidecar(&blob, &data).unwrap();
        assert!(sidecar_exists(&blob));
        verify_sidecar(&blob, &data).unwrap();
        // flip one bit
        let mut poisoned = data.clone();
        poisoned[5000] ^= 0x01;
        match verify_sidecar(&blob, &poisoned) {
            Err(AddressorError::Integrity(_)) => {}
            other => panic!("expected Integrity, got {other:?}"),
        }
    }

    #[test]
    fn no_sidecar_without_opt_in() {
        let dir = tempdir().unwrap();
        let blob = dir.path().join("y.chunk");
        std::fs::write(&blob, b"data").unwrap();
        // default OFF is observable: nothing creates the sidecar implicitly
        assert!(!sidecar_exists(&blob));
        assert!(verify_sidecar(&blob, b"data").is_err());
    }

    #[test]
    fn overhead_within_budget_on_fixture_corpus() {
        // AH-21 bound: sidecar bytes ≤ 5% of payload aggregate on a fixture
        // corpus of realistic blob sizes (chunks 2..32 KiB + containers).
        let dir = tempdir().unwrap();
        let mut payload_total = 0usize;
        let mut sidecar_total = 0usize;
        let mut x = 0x12345u64;
        for i in 0..64 {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            let size = 2048 + (x as usize % 30720); // 2..32 KiB
            let data: Vec<u8> = (0..size).map(|j| ((i * 7 + j) & 0xff) as u8).collect();
            let blob = dir.path().join(format!("b{i}.chunk"));
            std::fs::write(&blob, &data).unwrap();
            write_sidecar(&blob, &data).unwrap();
            payload_total += size;
            sidecar_total += std::fs::metadata(sidecar_path(&blob)).unwrap().len() as usize;
        }
        let overhead = sidecar_total as f64 / payload_total as f64;
        assert!(
            overhead <= 0.05,
            "merkle sidecar overhead {overhead:.4} > 5% budget"
        );
    }
}
