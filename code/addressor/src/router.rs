//! Core A router: whole-file dedup → dup-fraction scan → threshold-gated
//! CDC dedup with r>=2 promotion → residual via the real Cubrim-1 backend →
//! competitive selection (structurally never worse than pure Cubrim-1).

use crate::cas::CasStore;
use crate::catalog::{Catalog, Ordinal};
use crate::chunker::chunk_bytes;
use crate::error::{AddressorError, Result};
use crate::format::{
    decode_cdc_payload, encode_cdc_payload, CdcEntry, Container, SchemeByte,
};
use crate::matrix::{classify, Matrix};
use crate::residual;
use std::path::Path;

/// Step threshold on per-file dup-fraction (D-REQ-07). Exported constant:
/// the threshold test reads this value instead of hardcoding 10%.
pub const DUP_THRESHOLD: f64 = 0.10;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StoreOutcome {
    pub ordinal: Ordinal,
    pub scheme: SchemeByte,
    /// true when the file was already present (whole-file dedup hit)
    pub deduped: bool,
    /// bytes of the container actually written (0 on dedup hit)
    pub container_len: usize,
}

pub struct Addressor {
    pub cas: CasStore,
    pub catalog: Catalog,
    pub matrix: Matrix,
}

impl Addressor {
    pub fn open(root: &Path) -> Result<Self> {
        Ok(Addressor {
            cas: CasStore::open(&root.join("store"))?,
            catalog: Catalog::open(&root.join("catalog"))?,
            matrix: Matrix::open(&root.join("matrix"))?,
        })
    }

    /// Per-file dup-fraction per the D-REQ-07 formula: share of file bytes
    /// covered by whole-file or chunk hits against the catalog.
    /// (Whole-file hit short-circuits to 1.0 in `store_bytes`.)
    pub fn dup_fraction(&self, data: &[u8]) -> Result<f64> {
        if data.is_empty() {
            return Ok(0.0);
        }
        let mut matched = 0u64;
        for chunk in chunk_bytes(data) {
            let h = *blake3::hash(&chunk.data).as_bytes();
            if self.catalog.lookup(&h, &self.cas)?.is_some() {
                matched += chunk.data.len() as u64;
            }
        }
        Ok(matched as f64 / data.len() as f64)
    }

    pub fn store_bytes(&mut self, data: &[u8]) -> Result<StoreOutcome> {
        self.store_bytes_ctx(data, 0, None)
    }

    /// Store with fleet context: `section` = originating project section
    /// (AH-20), `path_hint` feeds the content-class heuristic (AH-12).
    pub fn store_bytes_ctx(
        &mut self,
        data: &[u8],
        section: u8,
        path_hint: Option<&str>,
    ) -> Result<StoreOutcome> {
        let file_hash = *blake3::hash(data).as_bytes();

        // 1. Whole-file identity dedup — ALWAYS, independent of the threshold.
        if let Some(ord) = self.catalog.lookup(&file_hash, &self.cas)? {
            return Ok(StoreOutcome {
                ordinal: ord,
                scheme: SchemeByte::WholeFile,
                deduped: true,
                container_len: 0,
            });
        }

        // 2. Candidate B: pure Cubrim-1 path (competitive baseline).
        let candidate_b = Self::pure_cubrim_container(data);

        // 3. Candidate A: addressor path (threshold-gated CDC + residual).
        let candidate_a = self.addressor_container(data, section, path_hint)?;

        // 4. Competitive selection: the smaller container ships.
        let chosen = match &candidate_a {
            Some(a) if a.len() <= candidate_b.len() => a.clone(),
            _ => candidate_b,
        };

        let container_len = chosen.len();
        let blob = self.cas.put(&chosen)?;
        let scheme = Container::from_bytes(&chosen)?.scheme;
        // whole-file hash is ALWAYS inserted (identity dedup for re-uploads,
        // including below-threshold files) — flagged as a container entry.
        let ord = self.catalog.insert_kind(file_hash, blob, true)?;
        Ok(StoreOutcome {
            ordinal: ord,
            scheme,
            deduped: false,
            container_len,
        })
    }

    /// Pure Cubrim-1 container: min(cubrim-as-shipped, raw) — the regression
    /// baseline. Whole-input encode, exactly like the Cubrim-1 CLI does
    /// (inputs above the cube design limit raw-store inside the codec).
    pub fn pure_cubrim_container(data: &[u8]) -> Vec<u8> {
        let coded = if data.is_empty() {
            None
        } else {
            Some(cubrim::codec::encode(data))
        };
        match coded {
            Some(c) if c.len() < data.len() => Container {
                scheme: SchemeByte::Cubrim1,
                payload: c,
            }
            .to_bytes(),
            _ => Container {
                scheme: SchemeByte::Raw,
                payload: data.to_vec(),
            }
            .to_bytes(),
        }
    }

    /// Addressor-path container, or None when the path collapses to the pure
    /// baseline (below threshold — the residual of the whole file IS candidate
    /// B for large inputs; for small ones lite may still win, so we build it).
    fn addressor_container(
        &mut self,
        data: &[u8],
        section: u8,
        path_hint: Option<&str>,
    ) -> Result<Option<Vec<u8>>> {
        if data.is_empty() {
            return Ok(None);
        }
        let chunks = chunk_bytes(data);
        let total = data.len() as u64;

        // Scan pass: pre-existing chunk hits drive dup-fraction (D-REQ-07);
        // r-counting + r>=2 promotion happen GLOBALLY for every file
        // (threshold gates only whether THIS file uses phase 1 — otherwise
        // the counters never bootstrap from an empty catalog).
        #[derive(Clone, Copy)]
        enum ChunkFate {
            Hit(Ordinal),      // pre-existing catalog hit (counts into fraction)
            Promoted(Ordinal), // r reached 2 now: usable ref, not in fraction
            Cold,              // r=1: goes to the residual stream
        }
        let mut matched = 0u64;
        let mut fates: Vec<ChunkFate> = Vec::with_capacity(chunks.len());
        for chunk in &chunks {
            let h = *blake3::hash(&chunk.data).as_bytes();
            if let Some(ord) = self.catalog.lookup(&h, &self.cas)? {
                matched += chunk.data.len() as u64;
                self.matrix.probe(&h, section); // section-hit accounting
                fates.push(ChunkFate::Hit(ord));
                continue;
            }
            let count = self.catalog.bump_seen(&h)?;
            if count >= 2 {
                // r>=2: promote — the block earned a catalog slot (AH-19)
                let blob = self.cas.put(&chunk.data)?;
                let ord = self.catalog.insert_kind(h, blob, false)?;
                self.matrix
                    .add_member(&h, ord, section, classify(path_hint))?;
                fates.push(ChunkFate::Promoted(ord));
            } else {
                fates.push(ChunkFate::Cold);
            }
        }
        let dup_fraction = matched as f64 / total as f64;

        if dup_fraction >= DUP_THRESHOLD {
            // Phase 1 ON: reference hits + promoted blocks; cold → residual.
            let mut entries = Vec::with_capacity(chunks.len());
            let mut residual_stream = Vec::new();
            for (chunk, fate) in chunks.iter().zip(fates.iter()) {
                match fate {
                    ChunkFate::Hit(ord) | ChunkFate::Promoted(ord) => {
                        entries.push(CdcEntry::Matched { ordinal: *ord });
                    }
                    ChunkFate::Cold => {
                        entries.push(CdcEntry::Unmatched {
                            len: chunk.data.len() as u64,
                        });
                        residual_stream.extend_from_slice(&chunk.data);
                    }
                }
            }
            let payload = if residual_stream.is_empty() {
                encode_cdc_payload(&entries, None)
            } else {
                let (sub_scheme, sub_payload) = residual::encode(&residual_stream)?;
                encode_cdc_payload(&entries, Some((sub_scheme, &sub_payload)))
            };
            let scheme = if residual_stream.is_empty() {
                SchemeByte::CdcDedup
            } else {
                SchemeByte::CdcResidual
            };
            Ok(Some(Container { scheme, payload }.to_bytes()))
        } else {
            // Below threshold: residual of the whole file. The addressor path
            // differs from candidate B even here: candidate B is Cubrim-1
            // as-shipped (whole-input encode — raw-stores above the cube
            // limit), while the residual backend applies the real codec
            // block-wise at its design block size.
            let (scheme, payload) = residual::encode(data)?;
            Ok(Some(Container { scheme, payload }.to_bytes()))
        }
    }

    pub fn retrieve(&self, ordinal: Ordinal) -> Result<Vec<u8>> {
        let entry = self
            .catalog
            .entry(ordinal)?
            .ok_or_else(|| AddressorError::Catalog(format!("unknown ordinal {ordinal}")))?;
        let blob_bytes = self.cas.get(&entry.blob)?;
        if !entry.is_container {
            // chunk entry: blob bytes ARE the content
            return Ok(blob_bytes);
        }
        let container = Container::from_bytes(&blob_bytes)?;
        let data = self.decode_container(&container)?;
        // end-to-end integrity: reconstructed bytes must equal the original hash
        if blake3::hash(&data).as_bytes() != &entry.orig_hash {
            return Err(AddressorError::Integrity(format!(
                "retrieve({ordinal}): reconstructed content hash mismatch"
            )));
        }
        Ok(data)
    }

    fn decode_container(&self, c: &Container) -> Result<Vec<u8>> {
        match c.scheme {
            SchemeByte::Raw | SchemeByte::Cubrim1 | SchemeByte::Lite => {
                residual::decode(c.scheme, &c.payload)
            }
            SchemeByte::CdcDedup | SchemeByte::CdcResidual => {
                let with_residual = c.scheme == SchemeByte::CdcResidual;
                let (entries, residual_blob) = decode_cdc_payload(&c.payload, with_residual)?;
                let residual_stream = match residual_blob {
                    Some((scheme, payload)) => residual::decode(scheme, &payload)?,
                    None => Vec::new(),
                };
                let mut res_pos = 0usize;
                let mut out = Vec::new();
                for e in entries {
                    match e {
                        CdcEntry::Matched { ordinal } => {
                            let entry = self.catalog.entry(ordinal)?.ok_or_else(|| {
                                AddressorError::Format(format!(
                                    "container references unknown ordinal {ordinal}"
                                ))
                            })?;
                            if entry.is_container {
                                return Err(AddressorError::Format(
                                    "chunk ref points at a container entry".into(),
                                ));
                            }
                            out.extend_from_slice(&self.cas.get(&entry.blob)?);
                        }
                        CdcEntry::Unmatched { len } => {
                            let len = len as usize;
                            let end = res_pos.checked_add(len).ok_or_else(|| {
                                AddressorError::Format("residual overrun".into())
                            })?;
                            if end > residual_stream.len() {
                                return Err(AddressorError::Format(
                                    "residual stream shorter than declared".into(),
                                ));
                            }
                            out.extend_from_slice(&residual_stream[res_pos..end]);
                            res_pos = end;
                        }
                    }
                }
                if res_pos != residual_stream.len() {
                    return Err(AddressorError::Format(
                        "residual stream has trailing bytes".into(),
                    ));
                }
                Ok(out)
            }
            SchemeByte::WholeFile => Err(AddressorError::Format(
                "nested whole-file scheme not used by store".into(),
            )),
            SchemeByte::Delta => Err(AddressorError::Format(
                "delta scheme handled in Core B (phase 5)".into(),
            )),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn text(n: usize, seed: u64) -> Vec<u8> {
        // compressible pseudo-text
        let words = [
            "alpha", "beta", "gamma", "delta", "fleet", "router", "chunk", "store",
        ];
        let mut x = seed.wrapping_mul(0x9E3779B97F4A7C15) | 1;
        let mut out = Vec::new();
        while out.len() < n {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            out.extend_from_slice(words[(x % 8) as usize].as_bytes());
            out.push(b' ');
        }
        out.truncate(n);
        out
    }

    #[test]
    fn store_retrieve_roundtrip_small_and_large() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        for (n, seed) in [(1usize, 1u64), (100, 2), (50_000, 3), (300_000, 4)] {
            let data = text(n, seed);
            let out = a.store_bytes(&data).unwrap();
            assert!(!out.deduped);
            assert_eq!(a.retrieve(out.ordinal).unwrap(), data, "n={n}");
        }
    }

    #[test]
    fn whole_file_dedup_hits_regardless_of_threshold() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        // unique random-ish content => dup-fraction 0, below threshold
        let data = text(5_000, 42);
        let first = a.store_bytes(&data).unwrap();
        assert!(!first.deduped);
        let blobs_before = a.cas.blob_count().unwrap();
        let second = a.store_bytes(&data).unwrap();
        assert!(second.deduped, "identical re-upload must whole-file dedup");
        assert_eq!(second.ordinal, first.ordinal);
        assert_eq!(a.cas.blob_count().unwrap(), blobs_before, "no new blobs");
    }

    #[test]
    fn threshold_steps_on_exported_constant() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        // donor: seed the catalog with chunks of a base file (store twice so
        // its chunks pass r>=2 promotion and become matchable)
        let donor = text(200_000, 7);
        a.store_bytes(&donor).unwrap();
        let mut donor2 = donor.clone();
        donor2.extend_from_slice(b"tail-variation-1"); // different whole-file hash
        a.store_bytes(&donor2).unwrap(); // shared chunks reach r=2 → promoted

        // now craft inputs around the threshold from donor chunks + unique noise
        let make_input = |dup_target: f64, salt: u64| -> Vec<u8> {
            let dup_len = (200_000f64 * dup_target) as usize;
            let mut v = donor[..dup_len].to_vec();
            let mut noise = text(200_000 - dup_len, 1000 + salt);
            // make noise incompressible-ish unique
            for (i, b) in noise.iter_mut().enumerate() {
                *b = b.wrapping_add((i as u8).wrapping_mul(salt as u8 | 1));
            }
            v.extend_from_slice(&noise);
            v
        };
        let t = DUP_THRESHOLD;
        let below = make_input((t - 0.05).max(0.0), 1);
        let above = make_input(t + 0.15, 2);
        let f_below = a.dup_fraction(&below).unwrap();
        let f_above = a.dup_fraction(&above).unwrap();
        assert!(f_below < t, "constructed below-point measured {f_below}");
        assert!(f_above >= t, "constructed above-point measured {f_above}");

        let out_above = a.store_bytes(&above).unwrap();
        assert!(
            matches!(out_above.scheme, SchemeByte::CdcDedup | SchemeByte::CdcResidual),
            "above threshold must take phase 1, got {:?}",
            out_above.scheme
        );
        assert_eq!(a.retrieve(out_above.ordinal).unwrap(), above);

        let out_below = a.store_bytes(&below).unwrap();
        assert!(
            !matches!(out_below.scheme, SchemeByte::CdcDedup | SchemeByte::CdcResidual),
            "below threshold must NOT take phase 1, got {:?}",
            out_below.scheme
        );
        assert_eq!(a.retrieve(out_below.ordinal).unwrap(), below);
    }

    #[test]
    fn regression_proof_container_never_beats_pure_cubrim() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        for (n, seed) in [(800usize, 10u64), (60_000, 11), (250_000, 12)] {
            let data = text(n, seed);
            let pure = Addressor::pure_cubrim_container(&data);
            let out = a.store_bytes(&data).unwrap();
            assert!(
                out.container_len <= pure.len(),
                "n={n}: router {} > pure cubrim {}",
                out.container_len,
                pure.len()
            );
        }
    }

    #[test]
    fn r1_chunks_go_to_residual_r2_get_promoted() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        let base = text(150_000, 20);
        a.store_bytes(&base).unwrap();
        let catalog_after_first = a.catalog.len().unwrap();
        // first store: below-threshold path (nothing matched) → only the
        // whole-file entry lands, no chunk entries (r=1 nowhere promoted)
        assert_eq!(catalog_after_first, 1, "r=1 chunks must not enter catalog");

        // a sibling sharing most content: chunk seen-counts reach 2 → promote
        let mut sibling = base.clone();
        sibling.extend_from_slice(b"-sibling-tail");
        a.store_bytes(&sibling).unwrap();
        let catalog_after_second = a.catalog.len().unwrap();
        assert!(
            catalog_after_second > 2,
            "shared chunks must be promoted at r=2 (got {catalog_after_second} entries)"
        );
        // third file with same content now dedups against promoted chunks
        let mut third = base.clone();
        third.extend_from_slice(b"-third-tail!!");
        let f = a.dup_fraction(&third).unwrap();
        assert!(f >= DUP_THRESHOLD, "third sibling should scan as dup-heavy");
        let out = a.store_bytes(&third).unwrap();
        assert!(matches!(
            out.scheme,
            SchemeByte::CdcDedup | SchemeByte::CdcResidual
        ));
        assert_eq!(a.retrieve(out.ordinal).unwrap(), third);
    }

    #[test]
    fn empty_file_roundtrip() {
        let dir = tempdir().unwrap();
        let mut a = Addressor::open(dir.path()).unwrap();
        let out = a.store_bytes(b"").unwrap();
        assert_eq!(a.retrieve(out.ordinal).unwrap(), b"");
    }
}
