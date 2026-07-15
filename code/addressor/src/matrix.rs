//! Curated fleet matrix: project sections (AH-20), r>=2 curation accounting
//! (AH-19), per-class snapshot versions (AH-12).
//!
//! The matrix is the *curated* view over the catalog: only promoted (r>=2)
//! chunk blocks are members. Sections partition members by originating
//! project; lookups consult the caller's own section first (the measured
//! 80%-hit economics), then fall back to the full catalog.

use crate::cas::{CasStore, HASH_LEN};
use crate::catalog::{Catalog, Ordinal};
use crate::error::{AddressorError, Result};
use redb::{Database, ReadableDatabase, ReadableTable, TableDefinition};
use std::collections::{HashMap, HashSet};
use std::path::Path;

/// member: truncated key -> (section, ordinal)
const MEMBERS: TableDefinition<u128, (u8, u64)> = TableDefinition::new("members");
/// per-class snapshot version (AH-12 cadence): class id -> version
const CLASS_VERSIONS: TableDefinition<u8, u64> = TableDefinition::new("class_versions");

pub const SECTION_COUNT: u8 = 36;

/// Content class heuristic for per-class version cadence (AH-12).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum ContentClass {
    Media = 0,
    Archives = 1,
    Config = 2,
    Code = 3,
    Docs = 4,
    Www = 5,
    Other = 6,
}

pub fn classify(path_hint: Option<&str>) -> ContentClass {
    let Some(p) = path_hint else {
        return ContentClass::Other;
    };
    let ext = p.rsplit('.').next().unwrap_or("").to_ascii_lowercase();
    match ext.as_str() {
        "jpg" | "jpeg" | "png" | "gif" | "mp4" | "mp3" | "webm" | "webp" | "heic" => {
            ContentClass::Media
        }
        "zip" | "tar" | "gz" | "zst" | "xz" | "7z" | "bz2" => ContentClass::Archives,
        "conf" | "cfg" | "ini" | "yml" | "yaml" | "toml" | "json" | "env" => ContentClass::Config,
        "rs" | "py" | "js" | "ts" | "go" | "c" | "h" | "cpp" | "sh" | "php" | "sql" => {
            ContentClass::Code
        }
        "md" | "txt" | "rst" | "pdf" | "doc" | "docx" | "html" | "htm" => ContentClass::Docs,
        "log" | "access" | "error" => ContentClass::Www,
        _ => ContentClass::Other,
    }
}

pub struct Matrix {
    db: Database,
    /// in-memory section membership mirror: section -> truncated keys
    sections: HashMap<u8, HashSet<u128>>,
    /// lookup accounting for the section-hit metric (AH-20)
    pub own_section_hits: u64,
    pub cross_section_hits: u64,
}

fn truncate128(hash: &[u8; HASH_LEN]) -> u128 {
    u128::from_le_bytes(hash[0..16].try_into().unwrap())
}

impl Matrix {
    pub fn open(dir: &Path) -> Result<Self> {
        std::fs::create_dir_all(dir)?;
        let db = Database::create(dir.join("matrix.redb"))
            .map_err(|e| AddressorError::Catalog(format!("matrix redb: {e}")))?;
        {
            let tx = db
                .begin_write()
                .map_err(|e| AddressorError::Catalog(format!("matrix tx: {e}")))?;
            tx.open_table(MEMBERS)
                .map_err(|e| AddressorError::Catalog(format!("matrix table: {e}")))?;
            tx.open_table(CLASS_VERSIONS)
                .map_err(|e| AddressorError::Catalog(format!("matrix table: {e}")))?;
            tx.commit()
                .map_err(|e| AddressorError::Catalog(format!("matrix commit: {e}")))?;
        }
        let mut sections: HashMap<u8, HashSet<u128>> = HashMap::new();
        {
            let tx = db
                .begin_read()
                .map_err(|e| AddressorError::Catalog(format!("matrix read: {e}")))?;
            let t = tx
                .open_table(MEMBERS)
                .map_err(|e| AddressorError::Catalog(format!("matrix table: {e}")))?;
            let mut iter = t
                .iter()
                .map_err(|e| AddressorError::Catalog(format!("matrix iter: {e}")))?;
            while let Some(next) = iter.next() {
                let (k, v) =
                    next.map_err(|e| AddressorError::Catalog(format!("matrix iter: {e}")))?;
                let (section, _ord) = v.value();
                sections.entry(section).or_default().insert(k.value());
            }
        }
        Ok(Matrix {
            db,
            sections,
            own_section_hits: 0,
            cross_section_hits: 0,
        })
    }

    /// Registers a PROMOTED (r>=2) block as a matrix member of `section`.
    pub fn add_member(
        &mut self,
        hash: &[u8; HASH_LEN],
        ordinal: Ordinal,
        section: u8,
        class: ContentClass,
    ) -> Result<()> {
        let section = section % SECTION_COUNT;
        let key = truncate128(hash);
        let tx = self
            .db
            .begin_write()
            .map_err(|e| AddressorError::Catalog(format!("matrix tx: {e}")))?;
        {
            let mut members = tx
                .open_table(MEMBERS)
                .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
            if members
                .get(key)
                .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?
                .is_none()
            {
                members
                    .insert(key, (section, ordinal))
                    .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
            }
            let mut versions = tx
                .open_table(CLASS_VERSIONS)
                .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
            let v = versions
                .get(class as u8)
                .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?
                .map(|g| g.value())
                .unwrap_or(0);
            versions
                .insert(class as u8, v + 1)
                .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        }
        tx.commit()
            .map_err(|e| AddressorError::Catalog(format!("matrix commit: {e}")))?;
        self.sections.entry(section).or_default().insert(key);
        Ok(())
    }

    /// Section-first membership probe; updates the section-hit accounting.
    /// Returns whether the block is a matrix member (any section).
    pub fn probe(&mut self, hash: &[u8; HASH_LEN], own_section: u8) -> bool {
        let own_section = own_section % SECTION_COUNT;
        let key = truncate128(hash);
        if self
            .sections
            .get(&own_section)
            .map(|s| s.contains(&key))
            .unwrap_or(false)
        {
            self.own_section_hits += 1;
            return true;
        }
        for (sec, set) in &self.sections {
            if *sec != own_section && set.contains(&key) {
                self.cross_section_hits += 1;
                return true;
            }
        }
        false
    }

    pub fn member_count(&self) -> u64 {
        self.sections.values().map(|s| s.len() as u64).sum()
    }

    pub fn section_sizes(&self) -> HashMap<u8, u64> {
        self.sections
            .iter()
            .map(|(k, v)| (*k, v.len() as u64))
            .collect()
    }

    /// Fraction of hits resolved inside the caller's own section (AH-20).
    pub fn section_hit_rate(&self) -> f64 {
        let total = self.own_section_hits + self.cross_section_hits;
        if total == 0 {
            return 0.0;
        }
        self.own_section_hits as f64 / total as f64
    }

    pub fn class_version(&self, class: ContentClass) -> Result<u64> {
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        let t = tx
            .open_table(CLASS_VERSIONS)
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        Ok(t.get(class as u8)
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?
            .map(|g| g.value())
            .unwrap_or(0))
    }

    /// Serialized snapshot of one section (for the epoch snapshot / sync):
    /// varint(count) ++ [key_le16B ++ varint(ordinal)]*.
    pub fn section_snapshot(&self, section: u8) -> Result<Vec<u8>> {
        use crate::refs::varint_encode;
        let tx = self
            .db
            .begin_read()
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        let t = tx
            .open_table(MEMBERS)
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        let mut rows: Vec<(u128, u64)> = Vec::new();
        let mut iter = t
            .iter()
            .map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
        while let Some(next) = iter.next() {
            let (k, v) = next.map_err(|e| AddressorError::Catalog(format!("matrix: {e}")))?;
            let (sec, ord) = v.value();
            if sec == section {
                rows.push((k.value(), ord));
            }
        }
        rows.sort_unstable();
        let mut out = Vec::new();
        varint_encode(rows.len() as u64, &mut out);
        for (k, ord) in rows {
            out.extend_from_slice(&k.to_le_bytes());
            varint_encode(ord, &mut out);
        }
        Ok(out)
    }

    /// Curation ratio: curated members / naive distinct blocks seen.
    /// (`naive` comes from the catalog's SEEN counters — every distinct block
    /// ever scanned; the curated matrix keeps only r>=2.)
    pub fn curation_ratio(&self, catalog: &Catalog, _cas: &CasStore) -> Result<f64> {
        let naive = catalog.seen_distinct()?;
        if naive == 0 {
            return Ok(0.0);
        }
        Ok(self.member_count() as f64 / naive as f64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn h(s: &str) -> [u8; HASH_LEN] {
        *blake3::hash(s.as_bytes()).as_bytes()
    }

    #[test]
    fn member_registration_and_probe() {
        let dir = tempdir().unwrap();
        let mut m = Matrix::open(dir.path()).unwrap();
        let hash = h("block-1");
        m.add_member(&hash, 7, 3, ContentClass::Code).unwrap();
        assert!(m.probe(&hash, 3), "own-section probe");
        assert!(m.probe(&hash, 9), "cross-section probe");
        assert_eq!(m.own_section_hits, 1);
        assert_eq!(m.cross_section_hits, 1);
        assert!(!m.probe(&h("absent"), 3));
    }

    #[test]
    fn section_hit_rate_accounting() {
        let dir = tempdir().unwrap();
        let mut m = Matrix::open(dir.path()).unwrap();
        for i in 0..8 {
            m.add_member(&h(&format!("own-{i}")), i, 1, ContentClass::Docs)
                .unwrap();
        }
        for i in 0..2 {
            m.add_member(&h(&format!("foreign-{i}")), 100 + i, 2, ContentClass::Docs)
                .unwrap();
        }
        for i in 0..8 {
            assert!(m.probe(&h(&format!("own-{i}")), 1));
        }
        for i in 0..2 {
            assert!(m.probe(&h(&format!("foreign-{i}")), 1));
        }
        assert!((m.section_hit_rate() - 0.8).abs() < 1e-9);
    }

    #[test]
    fn class_versions_bump_on_mutation() {
        let dir = tempdir().unwrap();
        let mut m = Matrix::open(dir.path()).unwrap();
        assert_eq!(m.class_version(ContentClass::Media).unwrap(), 0);
        m.add_member(&h("m1"), 1, 0, ContentClass::Media).unwrap();
        m.add_member(&h("m2"), 2, 0, ContentClass::Media).unwrap();
        m.add_member(&h("c1"), 3, 0, ContentClass::Code).unwrap();
        assert_eq!(m.class_version(ContentClass::Media).unwrap(), 2);
        assert_eq!(m.class_version(ContentClass::Code).unwrap(), 1);
        assert_eq!(m.class_version(ContentClass::Docs).unwrap(), 0);
    }

    #[test]
    fn snapshot_roundtrip_shape_and_persistence() {
        let dir = tempdir().unwrap();
        {
            let mut m = Matrix::open(dir.path()).unwrap();
            m.add_member(&h("a"), 1, 5, ContentClass::Other).unwrap();
            m.add_member(&h("b"), 2, 5, ContentClass::Other).unwrap();
            m.add_member(&h("c"), 3, 6, ContentClass::Other).unwrap();
        }
        let m2 = Matrix::open(dir.path()).unwrap();
        assert_eq!(m2.member_count(), 3);
        let snap5 = m2.section_snapshot(5).unwrap();
        let snap6 = m2.section_snapshot(6).unwrap();
        use crate::refs::varint_decode;
        let mut pos = 0;
        assert_eq!(varint_decode(&snap5, &mut pos).unwrap(), 2);
        pos = 0;
        assert_eq!(varint_decode(&snap6, &mut pos).unwrap(), 1);
    }

    #[test]
    fn classify_heuristic() {
        assert_eq!(classify(Some("a/b/photo.JPG")), ContentClass::Media);
        assert_eq!(classify(Some("x.tar")), ContentClass::Archives);
        assert_eq!(classify(Some("main.rs")), ContentClass::Code);
        assert_eq!(classify(Some("readme.md")), ContentClass::Docs);
        assert_eq!(classify(None), ContentClass::Other);
    }
}
