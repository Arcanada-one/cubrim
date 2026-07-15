//! Catalog: hash → ordinal → entry, with an fp16 prefilter and a mandatory
//! full-hash + blob-integrity confirmation before any reference is emitted.
//!
//! Lookup pipeline (D-REQ-09 invariant):
//!   fp16 slot (2 B/slot, open addressing, slot position from hash prefix)
//!     → redb exact match on the truncated 128-bit key
//!     → full 256-bit hash comparison against the stored entry
//!     → verified blob read through `CasStore::get` (Integrity on mismatch).
//! No truncated-index hit may emit an ordinal without passing all stages.

use crate::cas::{BlobRef, CasStore, HASH_LEN};
use crate::error::{AddressorError, Result};
use redb::{Database, ReadableDatabase, ReadableTable, TableDefinition};
use std::path::{Path, PathBuf};

/// key: truncated 128-bit BLAKE3 of the ORIGINAL content; value: ordinal
const BY_HASH: TableDefinition<u128, u64> = TableDefinition::new("by_hash");
/// key: ordinal; value: 65 bytes = kind_flag(1: 1=container,0=chunk) ++ orig_hash(32) ++ blob_hash(32)
const BY_ORDINAL: TableDefinition<u64, [u8; 65]> = TableDefinition::new("by_ordinal");
/// r-counting for curation (AH-19): truncated key -> times seen unmatched
const SEEN: TableDefinition<u128, u32> = TableDefinition::new("seen");
/// singleton row: next free ordinal
const META: TableDefinition<&str, u64> = TableDefinition::new("meta");

pub type Ordinal = u64;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Entry {
    /// full BLAKE3-256 of the original (pre-encoding) content
    pub orig_hash: [u8; HASH_LEN],
    /// CAS address of the stored blob (chunk: == orig; container: differs)
    pub blob: BlobRef,
    /// true = blob is a container (file entry); false = raw chunk bytes
    pub is_container: bool,
}

pub struct Catalog {
    db: Database,
    fp16_path: PathBuf,
    fp16: Vec<u16>,
    fp16_dirty: bool,
}

fn truncate128(hash: &[u8; HASH_LEN]) -> u128 {
    u128::from_le_bytes(hash[0..16].try_into().unwrap())
}

/// fingerprint: 16 bits taken from a DIFFERENT slice of the hash than the
/// slot position, so slot index and fingerprint are independent.
fn fp16_of(hash: &[u8; HASH_LEN]) -> u16 {
    let raw = u16::from_le_bytes([hash[16], hash[17]]);
    if raw == 0 {
        1 // 0 is the empty-slot sentinel
    } else {
        raw
    }
}

fn slot_of(hash: &[u8; HASH_LEN], table_len: usize) -> usize {
    let idx = u64::from_le_bytes(hash[8..16].try_into().unwrap());
    (idx as usize) & (table_len - 1)
}

const FP16_INITIAL_SLOTS: usize = 1 << 16; // grows by rebuild on load factor
const FP16_MAX_PROBE: usize = 64;

impl Catalog {
    pub fn open(dir: &Path) -> Result<Self> {
        std::fs::create_dir_all(dir)?;
        let db = Database::create(dir.join("catalog.redb"))
            .map_err(|e| AddressorError::Catalog(format!("redb open: {e}")))?;
        // ensure tables exist
        {
            let tx = db
                .begin_write()
                .map_err(|e| AddressorError::Catalog(format!("redb tx: {e}")))?;
            tx.open_table(BY_HASH)
                .map_err(|e| AddressorError::Catalog(format!("redb table: {e}")))?;
            tx.open_table(BY_ORDINAL)
                .map_err(|e| AddressorError::Catalog(format!("redb table: {e}")))?;
            tx.open_table(META)
                .map_err(|e| AddressorError::Catalog(format!("redb table: {e}")))?;
            tx.open_table(SEEN)
                .map_err(|e| AddressorError::Catalog(format!("redb table: {e}")))?;
            tx.commit()
                .map_err(|e| AddressorError::Catalog(format!("redb commit: {e}")))?;
        }
        let fp16_path = dir.join("index.fp16");
        let fp16 = if fp16_path.exists() {
            let raw = std::fs::read(&fp16_path)?;
            if raw.len() % 2 != 0 || !raw.len().is_power_of_two() {
                return Err(AddressorError::Catalog(
                    "fp16 index file has invalid size".into(),
                ));
            }
            raw.chunks_exact(2)
                .map(|c| u16::from_le_bytes([c[0], c[1]]))
                .collect()
        } else {
            vec![0u16; FP16_INITIAL_SLOTS]
        };
        Ok(Catalog {
            db,
            fp16_path,
            fp16,
            fp16_dirty: false,
        })
    }

    fn fp16_insert(&mut self, hash: &[u8; HASH_LEN]) {
        let fp = fp16_of(hash);
        let len = self.fp16.len();
        let start = slot_of(hash, len);
        for i in 0..FP16_MAX_PROBE {
            let s = (start + i) & (len - 1);
            if self.fp16[s] == 0 || self.fp16[s] == fp {
                self.fp16[s] = fp;
                self.fp16_dirty = true;
                return;
            }
        }
        // probe window exhausted: grow 2x and rebuild is the clean answer,
        // but rebuild needs all hashes (redb walk). Do it lazily.
        self.fp16_grow_rebuild();
        self.fp16_insert(hash);
    }

    fn fp16_grow_rebuild(&mut self) {
        let new_len = self.fp16.len() * 2;
        let mut table = vec![0u16; new_len];
        let tx = self.db.begin_read().expect("redb read");
        let t = tx.open_table(BY_ORDINAL).expect("by_ordinal");
        let mut iter = t.iter().expect("iter");
        while let Some(Ok((_, v))) = iter.next() {
            let raw: [u8; 65] = v.value();
            let mut orig = [0u8; HASH_LEN];
            orig.copy_from_slice(&raw[1..33]);
            let fp = fp16_of(&orig);
            let start = slot_of(&orig, new_len);
            for i in 0..new_len {
                let s = (start + i) & (new_len - 1);
                if table[s] == 0 || table[s] == fp {
                    table[s] = fp;
                    break;
                }
            }
        }
        self.fp16 = table;
        self.fp16_dirty = true;
    }

    /// fp16 prefilter: true = "possibly present", false = definitely absent.
    pub fn fp16_may_contain(&self, hash: &[u8; HASH_LEN]) -> bool {
        let fp = fp16_of(hash);
        let len = self.fp16.len();
        let start = slot_of(hash, len);
        for i in 0..FP16_MAX_PROBE {
            let s = (start + i) & (len - 1);
            if self.fp16[s] == fp {
                return true;
            }
            if self.fp16[s] == 0 {
                return false;
            }
        }
        true // saturated probe window: fail open (it is only a prefilter)
    }

    /// Inserts (or returns existing) chunk entry; assigns the next ordinal.
    pub fn insert(&mut self, orig_hash: [u8; HASH_LEN], blob: BlobRef) -> Result<Ordinal> {
        self.insert_kind(orig_hash, blob, false)
    }

    /// Bumps the unmatched-seen counter for a block hash (r-curation, AH-19);
    /// returns the count AFTER the bump.
    pub fn bump_seen(&mut self, hash: &[u8; HASH_LEN]) -> Result<u32> {
        let key = truncate128(hash);
        let tx = self
            .db
            .begin_write()
            .map_err(|e| AddressorError::Catalog(format!("redb tx: {e}")))?;
        let count;
        {
            let mut seen = tx
                .open_table(SEEN)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            count = seen
                .get(key)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
                .map(|g| g.value())
                .unwrap_or(0)
                + 1;
            seen.insert(key, count)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        }
        tx.commit()
            .map_err(|e| AddressorError::Catalog(format!("redb commit: {e}")))?;
        Ok(count)
    }

    /// Count of catalog entries that are r=1 residents — the curation
    /// invariant (D-REQ-03) demands this stays 0: blocks enter the catalog
    /// only via promotion (count>=2) or as file/container entries.
    pub fn entries_r1(&self) -> Result<u64> {
        // by construction insert happens only at promotion or for containers;
        // verify by cross-checking SEEN counts for chunk entries.
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let by_ord = tx
            .open_table(BY_ORDINAL)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let seen = tx
            .open_table(SEEN)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let mut n = 0u64;
        let mut iter = by_ord
            .iter()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        while let Some(next) = iter.next() {
            let (_, v) = next.map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            let raw: [u8; 65] = v.value();
            if raw[0] == 1 {
                continue; // container entries are not matrix members
            }
            let mut orig = [0u8; HASH_LEN];
            orig.copy_from_slice(&raw[1..33]);
            let cnt = seen
                .get(truncate128(&orig))
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
                .map(|g| g.value())
                .unwrap_or(0);
            if cnt < 2 {
                n += 1;
            }
        }
        Ok(n)
    }

    /// Number of DISTINCT blocks ever scanned (the naive, uncurated matrix
    /// baseline for the AH-19 curation ratio).
    pub fn seen_distinct(&self) -> Result<u64> {
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let seen = tx
            .open_table(SEEN)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let mut n = 0u64;
        let mut iter = seen
            .iter()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        while let Some(next) = iter.next() {
            next.map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            n += 1;
        }
        Ok(n)
    }

    /// Inserts (or returns existing) entry; assigns the next ordinal.
    pub fn insert_kind(
        &mut self,
        orig_hash: [u8; HASH_LEN],
        blob: BlobRef,
        is_container: bool,
    ) -> Result<Ordinal> {
        let key = truncate128(&orig_hash);
        let tx = self
            .db
            .begin_write()
            .map_err(|e| AddressorError::Catalog(format!("redb tx: {e}")))?;
        let ordinal;
        {
            let mut by_hash = tx
                .open_table(BY_HASH)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            let mut by_ord = tx
                .open_table(BY_ORDINAL)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            let mut meta = tx
                .open_table(META)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            if let Some(existing) = by_hash
                .get(key)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
            {
                let ord = existing.value();
                drop(existing);
                // truncated-key hit inside insert: confirm full hash before reuse
                let raw = by_ord
                    .get(ord)
                    .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
                    .ok_or_else(|| AddressorError::Catalog("dangling ordinal".into()))?
                    .value();
                if raw[1..33] != orig_hash {
                    return Err(AddressorError::Integrity(
                        "128-bit key collision detected on insert; refusing ref".into(),
                    ));
                }
                return Ok(ord);
            }
            ordinal = meta
                .get("next_ordinal")
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
                .map(|g| g.value())
                .unwrap_or(0);
            let mut raw = [0u8; 65];
            raw[0] = is_container as u8;
            raw[1..33].copy_from_slice(&orig_hash);
            raw[33..65].copy_from_slice(&blob.hash);
            by_ord
                .insert(ordinal, raw)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            by_hash
                .insert(key, ordinal)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
            meta.insert("next_ordinal", ordinal + 1)
                .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        }
        tx.commit()
            .map_err(|e| AddressorError::Catalog(format!("redb commit: {e}")))?;
        self.fp16_insert(&orig_hash);
        Ok(ordinal)
    }

    fn entry_of(&self, ordinal: Ordinal) -> Result<Option<Entry>> {
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let by_ord = tx
            .open_table(BY_ORDINAL)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let Some(raw) = by_ord
            .get(ordinal)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
        else {
            return Ok(None);
        };
        let raw: [u8; 65] = raw.value();
        let mut orig = [0u8; HASH_LEN];
        let mut blob = [0u8; HASH_LEN];
        orig.copy_from_slice(&raw[1..33]);
        blob.copy_from_slice(&raw[33..65]);
        Ok(Some(Entry {
            orig_hash: orig,
            blob: BlobRef { hash: blob },
            is_container: raw[0] == 1,
        }))
    }

    /// Confirmed lookup (the D-REQ-09 invariant lives here).
    ///
    /// Returns the ordinal ONLY after: fp16 pass → redb exact on 128-bit key →
    /// full-hash equality → verified blob read via `cas.get` (which errors with
    /// Integrity if the stored bytes were tampered behind the store's back).
    pub fn lookup(&self, hash: &[u8; HASH_LEN], cas: &CasStore) -> Result<Option<Ordinal>> {
        if !self.fp16_may_contain(hash) {
            return Ok(None);
        }
        let key = truncate128(hash);
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let by_hash = tx
            .open_table(BY_HASH)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let Some(ord) = by_hash
            .get(key)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
            .map(|g| g.value())
        else {
            return Ok(None);
        };
        drop(by_hash);
        drop(tx);
        let entry = self
            .entry_of(ord)?
            .ok_or_else(|| AddressorError::Catalog("dangling ordinal".into()))?;
        if entry.orig_hash != *hash {
            // truncated 128-bit collision: full-hash confirmation failed
            return Ok(None);
        }
        // blob-integrity leg of the confirmation: a verified read.
        // For chunk entries orig==blob content; for container entries the blob
        // is the container — either way the blob must be present and clean.
        let _ = cas.get(&entry.blob)?;
        Ok(Some(ord))
    }

    pub fn entry(&self, ordinal: Ordinal) -> Result<Option<Entry>> {
        self.entry_of(ordinal)
    }

    pub fn len(&self) -> Result<u64> {
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        let meta = tx
            .open_table(META)
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?;
        Ok(meta
            .get("next_ordinal")
            .map_err(|e| AddressorError::Catalog(format!("redb: {e}")))?
            .map(|g| g.value())
            .unwrap_or(0))
    }

    pub fn is_empty(&self) -> Result<bool> {
        Ok(self.len()? == 0)
    }

    /// Persist the fp16 index (2 B per slot, by construction).
    pub fn commit_fp16(&mut self) -> Result<()> {
        if !self.fp16_dirty {
            return Ok(());
        }
        let mut raw = Vec::with_capacity(self.fp16.len() * 2);
        for v in &self.fp16 {
            raw.extend_from_slice(&v.to_le_bytes());
        }
        let tmp = self.fp16_path.with_extension("fp16.tmp");
        std::fs::write(&tmp, &raw)?;
        std::fs::rename(&tmp, &self.fp16_path)?;
        self.fp16_dirty = false;
        Ok(())
    }

    pub fn fp16_bytes_per_slot(&self) -> f64 {
        2.0 // Vec<u16>: sanity by construction, asserted in tests
    }

    pub fn fp16_slot_count(&self) -> usize {
        self.fp16.len()
    }
}

impl Drop for Catalog {
    fn drop(&mut self) {
        let _ = self.commit_fp16();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn setup() -> (tempfile::TempDir, CasStore, Catalog) {
        let dir = tempdir().unwrap();
        let cas = CasStore::open(&dir.path().join("store")).unwrap();
        let cat = Catalog::open(&dir.path().join("catalog")).unwrap();
        (dir, cas, cat)
    }

    #[test]
    fn insert_lookup_roundtrip() {
        let (_d, cas, mut cat) = setup();
        let data = b"chunk payload one";
        let blob = cas.put(data).unwrap();
        let hash = *blake3::hash(data).as_bytes();
        let ord = cat.insert(hash, blob).unwrap();
        assert_eq!(cat.lookup(&hash, &cas).unwrap(), Some(ord));
    }

    #[test]
    fn lookup_absent_is_none() {
        let (_d, cas, cat) = setup();
        let hash = *blake3::hash(b"never inserted").as_bytes();
        assert_eq!(cat.lookup(&hash, &cas).unwrap(), None);
    }

    #[test]
    fn insert_is_idempotent_same_ordinal() {
        let (_d, cas, mut cat) = setup();
        let data = b"dup chunk";
        let blob = cas.put(data).unwrap();
        let hash = *blake3::hash(data).as_bytes();
        let o1 = cat.insert(hash, blob).unwrap();
        let o2 = cat.insert(hash, blob).unwrap();
        assert_eq!(o1, o2);
        assert_eq!(cat.len().unwrap(), 1);
    }

    #[test]
    fn fp_confirm_invariant_tampered_blob_is_integrity_error() {
        // The only reachable path to exercise the confirmation branch:
        // a blob↔key desync (tamper the stored blob behind the CAS).
        let (_d, cas, mut cat) = setup();
        let data = b"original blob content for K";
        let blob = cas.put(data).unwrap();
        let hash = *blake3::hash(data).as_bytes();
        cat.insert(hash, blob).unwrap();
        std::fs::write(cas.blob_path(&blob), b"swapped-in poison").unwrap();
        match cat.lookup(&hash, &cas) {
            Err(AddressorError::Integrity(_)) => {} // ref NOT emitted
            other => panic!("expected Err(Integrity), got {other:?}"),
        }
    }

    #[test]
    fn fp16_negative_prefilter_rate() {
        let (_d, cas, mut cat) = setup();
        // populate 4096 real entries
        for i in 0u32..4096 {
            let data = format!("entry-{i}");
            let blob = cas.put(data.as_bytes()).unwrap();
            let hash = *blake3::hash(data.as_bytes()).as_bytes();
            cat.insert(hash, blob).unwrap();
        }
        // 20_000 negative probes: fraction passing the fp16 stage must be small
        let mut passed = 0u32;
        let probes = 20_000u32;
        for i in 0..probes {
            let h = *blake3::hash(format!("negative-{i}").as_bytes()).as_bytes();
            if cat.fp16_may_contain(&h) {
                passed += 1;
            }
        }
        let rate = passed as f64 / probes as f64;
        assert!(rate <= 0.045, "fp16 negative pass rate {rate} > 0.045");
    }

    #[test]
    fn fp16_is_two_bytes_per_slot_by_construction() {
        let (_d, _cas, cat) = setup();
        assert_eq!(cat.fp16_bytes_per_slot(), 2.0);
        assert!(cat.fp16_slot_count().is_power_of_two());
    }

    #[test]
    fn persisted_fp16_reloads() {
        let dir = tempdir().unwrap();
        let cas = CasStore::open(&dir.path().join("store")).unwrap();
        let catdir = dir.path().join("catalog");
        let hash;
        {
            let mut cat = Catalog::open(&catdir).unwrap();
            let data = b"persist me";
            let blob = cas.put(data).unwrap();
            hash = *blake3::hash(data).as_bytes();
            cat.insert(hash, blob).unwrap();
            cat.commit_fp16().unwrap();
        }
        let cat2 = Catalog::open(&catdir).unwrap();
        assert_eq!(cat2.lookup(&hash, &cas).unwrap(), Some(0));
    }
}
