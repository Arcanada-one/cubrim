//! Content-addressed store: write-once, sharded `store/ab/cd/<hex>.chunk`.
//!
//! Blobs are stored raw (compression is the caller's concern and lives only in
//! lite.rs / residual.rs / delta.rs). Every read re-verifies BLAKE3 against the
//! addressing hash; a mismatch is an Integrity error, never silent data.

use crate::error::{AddressorError, Result};
use std::fs;
use std::path::{Path, PathBuf};

pub const HASH_LEN: usize = 32;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct BlobRef {
    pub hash: [u8; HASH_LEN],
}

impl BlobRef {
    pub fn from_bytes(data: &[u8]) -> Self {
        BlobRef {
            hash: *blake3::hash(data).as_bytes(),
        }
    }

    pub fn to_hex(&self) -> String {
        self.hash.iter().map(|b| format!("{b:02x}")).collect()
    }

    pub fn from_hex(s: &str) -> Result<Self> {
        if s.len() != HASH_LEN * 2 || !s.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(AddressorError::Format(format!("bad blob ref hex: {s:?}")));
        }
        let mut hash = [0u8; HASH_LEN];
        for (i, chunk) in s.as_bytes().chunks(2).enumerate() {
            let hi = (chunk[0] as char).to_digit(16).unwrap() as u8;
            let lo = (chunk[1] as char).to_digit(16).unwrap() as u8;
            hash[i] = (hi << 4) | lo;
        }
        Ok(BlobRef { hash })
    }
}

pub struct CasStore {
    root: PathBuf,
}

impl CasStore {
    /// Opens (creating if needed) a CAS store rooted at `root`.
    pub fn open(root: &Path) -> Result<Self> {
        fs::create_dir_all(root)?;
        Ok(CasStore {
            root: root.to_path_buf(),
        })
    }

    pub fn blob_path(&self, r: &BlobRef) -> PathBuf {
        let hex = r.to_hex();
        self.root
            .join(&hex[0..2])
            .join(&hex[2..4])
            .join(format!("{hex}.chunk"))
    }

    /// Write-once put: hashes `data`, writes to a temp file in the target
    /// shard dir, verifies, then atomically renames into place.
    pub fn put(&self, data: &[u8]) -> Result<BlobRef> {
        let r = BlobRef::from_bytes(data);
        let path = self.blob_path(&r);
        if path.exists() {
            return Ok(r); // write-once: identical content already present
        }
        let dir = path.parent().expect("shard dir");
        fs::create_dir_all(dir)?;
        let tmp = dir.join(format!(".tmp-{}", r.to_hex()));
        fs::write(&tmp, data)?;
        // paranoia: re-read and verify before the blob becomes addressable
        let written = fs::read(&tmp)?;
        if blake3::hash(&written).as_bytes() != &r.hash {
            let _ = fs::remove_file(&tmp);
            return Err(AddressorError::Integrity(format!(
                "temp write verification failed for {}",
                r.to_hex()
            )));
        }
        fs::rename(&tmp, &path)?;
        Ok(r)
    }

    /// Verified read: content is re-hashed and compared to the address.
    pub fn get(&self, r: &BlobRef) -> Result<Vec<u8>> {
        let path = self.blob_path(r);
        let data = fs::read(&path).map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                AddressorError::Catalog(format!("blob not found: {}", r.to_hex()))
            } else {
                AddressorError::Io(e)
            }
        })?;
        if blake3::hash(&data).as_bytes() != &r.hash {
            return Err(AddressorError::Integrity(format!(
                "blob {} content does not match its address",
                r.to_hex()
            )));
        }
        Ok(data)
    }

    pub fn contains(&self, r: &BlobRef) -> bool {
        self.blob_path(r).exists()
    }

    /// Number of blobs in the store (walks shard dirs; test/stats use only).
    pub fn blob_count(&self) -> Result<u64> {
        let mut n = 0u64;
        if !self.root.exists() {
            return Ok(0);
        }
        for l1 in fs::read_dir(&self.root)? {
            let l1 = l1?.path();
            if !l1.is_dir() {
                continue;
            }
            for l2 in fs::read_dir(&l1)? {
                let l2 = l2?.path();
                if !l2.is_dir() {
                    continue;
                }
                for f in fs::read_dir(&l2)? {
                    let f = f?.path();
                    if f.extension().map(|e| e == "chunk").unwrap_or(false) {
                        n += 1;
                    }
                }
            }
        }
        Ok(n)
    }

    pub fn root(&self) -> &Path {
        &self.root
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn put_get_roundtrip() {
        let dir = tempdir().unwrap();
        let cas = CasStore::open(dir.path()).unwrap();
        let data = b"hello addressor";
        let r = cas.put(data).unwrap();
        assert_eq!(cas.get(&r).unwrap(), data);
    }

    #[test]
    fn put_is_write_once_idempotent() {
        let dir = tempdir().unwrap();
        let cas = CasStore::open(dir.path()).unwrap();
        let r1 = cas.put(b"same").unwrap();
        let r2 = cas.put(b"same").unwrap();
        assert_eq!(r1, r2);
        assert_eq!(cas.blob_count().unwrap(), 1);
    }

    #[test]
    fn get_detects_on_disk_tampering() {
        let dir = tempdir().unwrap();
        let cas = CasStore::open(dir.path()).unwrap();
        let r = cas.put(b"original content").unwrap();
        // corrupt the stored blob behind the store's back
        std::fs::write(cas.blob_path(&r), b"poisoned content!").unwrap();
        match cas.get(&r) {
            Err(AddressorError::Integrity(_)) => {}
            other => panic!("expected Integrity error, got {other:?}"),
        }
    }

    #[test]
    fn hex_roundtrip() {
        let r = BlobRef::from_bytes(b"x");
        let r2 = BlobRef::from_hex(&r.to_hex()).unwrap();
        assert_eq!(r, r2);
        assert!(BlobRef::from_hex("zz").is_err());
    }
}
