#![forbid(unsafe_code)]

use std::ffi::OsStr;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Component, Path, PathBuf};

use blake3::Hash;
use cubrim::{decode, encode};
use walkdir::WalkDir;

use crate::cli::{AddArgs, ExtractArgs, ListArgs, TestArgs};
use crate::crypto::{decrypt_payload, encrypt_payload, random_salt, resolve_password, SALT_LEN};
use crate::AppError;

const MAGIC: &[u8; 4] = b"CUBR";
const VERSION_PLAIN: u8 = 1;
const VERSION_ENCRYPTED: u8 = 2;
const KIND_DIR: u8 = 0;
const KIND_FILE: u8 = 1;

#[derive(Debug, Clone)]
struct ArchiveEntry {
    path: PathBuf,
    kind: u8,
    original_size: u64,
    compressed_size: u64,
    mode: u32,
    mtime: i64,
    checksum: [u8; 32],
    data: Vec<u8>,
}

pub fn is_archive_path(path: &Path) -> bool {
    let mut header = [0u8; 4];
    File::open(path)
        .and_then(|mut file| file.read_exact(&mut header))
        .map(|_| &header == MAGIC)
        .unwrap_or(false)
}

pub fn add_archive(args: AddArgs) -> Result<(), AppError> {
    if args.archive.exists() && !args.force {
        return Err(AppError::usage(format!(
            "{} already exists; pass --force to overwrite",
            args.archive.display()
        )));
    }

    let password = resolve_password(&args.password, "Archive")?;
    let entries = collect_entries(&args.paths, args.preserve)?;
    let payload = serialize_entries(&entries)?;
    let mut archive = Vec::new();
    archive.extend_from_slice(MAGIC);
    if let Some(password) = password.as_deref() {
        let salt = random_salt();
        archive.push(VERSION_ENCRYPTED);
        archive.extend_from_slice(&salt);
        archive.extend_from_slice(&encrypt_payload(&payload, password, &salt)?);
    } else {
        archive.push(VERSION_PLAIN);
        archive.extend_from_slice(&payload);
    }

    fs::write(&args.archive, archive)?;
    if !args.quiet {
        let original: u64 = entries.iter().map(|entry| entry.original_size).sum();
        let compressed: u64 = entries.iter().map(|entry| entry.compressed_size).sum();
        eprintln!(
            "archive: {} entries, {} bytes -> {} bytes",
            entries.len(),
            original,
            compressed
        );
    }
    Ok(())
}

pub fn extract_or_decompress(args: ExtractArgs) -> Result<(), AppError> {
    if !is_archive_path(&args.input) {
        let output = args.output.ok_or_else(|| {
            AppError::usage("legacy decompression with x requires an output path")
        })?;
        let blob = fs::read(&args.input)?;
        let data = decode(&blob).map_err(|err| AppError::integrity(err.to_string()))?;
        if output.exists() && !args.force {
            return Err(AppError::usage(format!(
                "{} already exists; pass --force to overwrite",
                output.display()
            )));
        }
        fs::write(&output, &data)?;
        if !args.quiet {
            eprintln!("decompressed: {} bytes -> {} bytes", blob.len(), data.len());
        }
        return Ok(());
    }

    let password = resolve_password(&args.password, "Archive")?;
    let entries = read_archive(&args.input, password.as_deref())?;
    let out_dir = args
        .out_dir
        .or(args.output)
        .unwrap_or_else(|| PathBuf::from("."));
    fs::create_dir_all(&out_dir)?;
    for entry in entries {
        let target = safe_join(&out_dir, &entry.path)?;
        match entry.kind {
            KIND_DIR => {
                fs::create_dir_all(&target)?;
            }
            KIND_FILE => {
                if target.exists() && !args.force {
                    return Err(AppError::usage(format!(
                        "{} already exists; pass --force to overwrite",
                        target.display()
                    )));
                }
                let data =
                    decode(&entry.data).map_err(|err| AppError::integrity(err.to_string()))?;
                verify_checksum(&entry, &data)?;
                if let Some(parent) = target.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::write(&target, data)?;
                restore_metadata(&target, &entry, args.preserve)?;
                if !args.quiet {
                    eprintln!("extracted: {}", entry.path.display());
                }
            }
            _ => {
                return Err(AppError::integrity(
                    "archive contains an unknown entry kind",
                ))
            }
        }
    }
    Ok(())
}

pub fn list_archive(args: ListArgs) -> Result<(), AppError> {
    let password = resolve_password(&args.password, "Archive")?;
    let entries = read_archive(&args.archive, password.as_deref())?;
    if args.quiet {
        return Ok(());
    }
    println!(
        "{:<12} {:>12} {:>12} {:>8}",
        "Type", "Original", "Compressed", "Ratio"
    );
    let mut total_original = 0u64;
    let mut total_compressed = 0u64;
    for entry in &entries {
        let kind = if entry.kind == KIND_DIR {
            "dir"
        } else {
            "file"
        };
        let ratio = ratio(entry.original_size, entry.compressed_size);
        println!(
            "{:<12} {:>12} {:>12} {:>7.2}%  {}",
            kind,
            entry.original_size,
            entry.compressed_size,
            ratio,
            entry.path.display()
        );
        total_original += entry.original_size;
        total_compressed += entry.compressed_size;
    }
    println!(
        "{:<12} {:>12} {:>12} {:>7.2}%  TOTAL",
        "total",
        total_original,
        total_compressed,
        ratio(total_original, total_compressed)
    );
    Ok(())
}

pub fn test_archive(args: TestArgs) -> Result<(), AppError> {
    let password = resolve_password(&args.password, "Archive")?;
    let entries = read_archive(&args.archive, password.as_deref())?;
    for entry in &entries {
        if entry.kind == KIND_FILE {
            let data = decode(&entry.data).map_err(|err| AppError::integrity(err.to_string()))?;
            verify_checksum(entry, &data)?;
        }
    }
    if !args.quiet {
        println!("tested: {} entries OK", entries.len());
    }
    Ok(())
}

fn collect_entries(paths: &[PathBuf], preserve: bool) -> Result<Vec<ArchiveEntry>, AppError> {
    let mut entries = Vec::new();
    for input in paths {
        if !input.exists() {
            return Err(AppError::usage(format!(
                "{} does not exist",
                input.display()
            )));
        }
        let base = input.parent().unwrap_or_else(|| Path::new(""));
        if input.is_file() {
            entries.push(file_entry(
                input,
                input.strip_prefix(base).unwrap_or(input),
                preserve,
            )?);
            continue;
        }
        for item in WalkDir::new(input).follow_links(false).sort_by_file_name() {
            let item = item.map_err(|err| AppError::io(err.to_string()))?;
            let path = item.path();
            let rel = path.strip_prefix(base).unwrap_or(path);
            if item.file_type().is_symlink() {
                continue;
            }
            if item.file_type().is_dir() {
                if rel.as_os_str().is_empty() {
                    continue;
                }
                entries.push(dir_entry(path, rel, preserve)?);
            } else if item.file_type().is_file() {
                entries.push(file_entry(path, rel, preserve)?);
            }
        }
    }
    if entries.is_empty() {
        return Err(AppError::usage(
            "no regular files or directories to archive",
        ));
    }
    Ok(entries)
}

fn file_entry(path: &Path, rel: &Path, preserve: bool) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    let data = fs::read(path)?;
    let compressed = encode(&data);
    let metadata = fs::metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        kind: KIND_FILE,
        original_size: data.len() as u64,
        compressed_size: compressed.len() as u64,
        mode,
        mtime,
        checksum: *blake3::hash(&data).as_bytes(),
        data: compressed,
    })
}

fn dir_entry(path: &Path, rel: &Path, preserve: bool) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    let metadata = fs::metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        kind: KIND_DIR,
        original_size: 0,
        compressed_size: 0,
        mode,
        mtime,
        checksum: [0; 32],
        data: Vec::new(),
    })
}

fn serialize_entries(entries: &[ArchiveEntry]) -> Result<Vec<u8>, AppError> {
    let mut out = Vec::new();
    out.extend_from_slice(&(entries.len() as u32).to_le_bytes());
    for entry in entries {
        let path = entry.path.to_str().ok_or_else(|| {
            AppError::usage(format!("non-UTF-8 archive path: {}", entry.path.display()))
        })?;
        let path_bytes = path.as_bytes();
        if path_bytes.len() > u16::MAX as usize {
            return Err(AppError::usage(format!("archive path is too long: {path}")));
        }
        out.extend_from_slice(&(path_bytes.len() as u16).to_le_bytes());
        out.extend_from_slice(path_bytes);
        out.push(entry.kind);
        out.extend_from_slice(&entry.original_size.to_le_bytes());
        out.extend_from_slice(&entry.compressed_size.to_le_bytes());
        out.extend_from_slice(&entry.mode.to_le_bytes());
        out.extend_from_slice(&entry.mtime.to_le_bytes());
        out.extend_from_slice(&entry.checksum);
        out.extend_from_slice(&entry.data);
    }
    Ok(out)
}

fn read_archive(path: &Path, password: Option<&str>) -> Result<Vec<ArchiveEntry>, AppError> {
    let bytes = fs::read(path)?;
    if bytes.len() < 5 || &bytes[..4] != MAGIC {
        return Err(AppError::integrity("not a .cbr archive"));
    }
    let payload = match bytes[4] {
        VERSION_PLAIN => bytes[5..].to_vec(),
        VERSION_ENCRYPTED => {
            let password =
                password.ok_or_else(|| AppError::usage("archive is encrypted; pass --password"))?;
            if bytes.len() < 5 + SALT_LEN {
                return Err(AppError::integrity("encrypted archive is truncated"));
            }
            let salt: [u8; SALT_LEN] = bytes[5..5 + SALT_LEN].try_into().unwrap();
            decrypt_payload(&bytes[5 + SALT_LEN..], password, &salt)?
        }
        other => {
            return Err(AppError::integrity(format!(
                "unsupported .cbr version: {other}"
            )))
        }
    };
    parse_entries(&payload)
}

fn parse_entries(payload: &[u8]) -> Result<Vec<ArchiveEntry>, AppError> {
    let mut cursor = Cursor::new(payload);
    let count = cursor.read_u32()? as usize;
    let mut entries = Vec::with_capacity(count);
    for _ in 0..count {
        let path_len = cursor.read_u16()? as usize;
        let path_bytes = cursor.read_exact_vec(path_len)?;
        let path = std::str::from_utf8(&path_bytes)
            .map_err(|_| AppError::integrity("archive path is not valid UTF-8"))?;
        let path = PathBuf::from(path);
        validate_archive_path(&path)?;
        let kind = cursor.read_u8()?;
        let original_size = cursor.read_u64()?;
        let compressed_size = cursor.read_u64()?;
        let mode = cursor.read_u32()?;
        let mtime = cursor.read_i64()?;
        let checksum = cursor.read_hash()?;
        let data = if kind == KIND_FILE {
            cursor.read_exact_vec(compressed_size as usize)?
        } else {
            Vec::new()
        };
        entries.push(ArchiveEntry {
            path,
            kind,
            original_size,
            compressed_size,
            mode,
            mtime,
            checksum,
            data,
        });
    }
    if cursor.remaining() != 0 {
        return Err(AppError::integrity("archive has trailing payload bytes"));
    }
    Ok(entries)
}

fn validate_archive_path(path: &Path) -> Result<(), AppError> {
    if path.as_os_str().is_empty() || path.as_os_str() == OsStr::new(".") {
        return Err(AppError::integrity("archive path is empty"));
    }
    let text = path
        .to_str()
        .ok_or_else(|| AppError::integrity("archive path is not valid UTF-8"))?;
    if text.as_bytes().contains(&0) {
        return Err(AppError::integrity("archive path contains a NUL byte"));
    }
    for component in path.components() {
        match component {
            Component::Normal(_) => {}
            _ => {
                return Err(AppError::integrity(format!(
                    "unsafe archive path rejected: {}",
                    path.display()
                )))
            }
        }
    }
    Ok(())
}

fn safe_join(base: &Path, rel: &Path) -> Result<PathBuf, AppError> {
    validate_archive_path(rel)?;
    Ok(base.join(rel))
}

fn verify_checksum(entry: &ArchiveEntry, data: &[u8]) -> Result<(), AppError> {
    let hash: Hash = blake3::hash(data);
    if hash.as_bytes() != &entry.checksum {
        return Err(AppError::integrity(format!(
            "checksum mismatch for {}",
            entry.path.display()
        )));
    }
    if data.len() as u64 != entry.original_size {
        return Err(AppError::integrity(format!(
            "size mismatch for {}",
            entry.path.display()
        )));
    }
    Ok(())
}

fn ratio(original: u64, compressed: u64) -> f64 {
    if original == 0 {
        0.0
    } else {
        (compressed as f64 / original as f64) * 100.0
    }
}

fn metadata_values(metadata: &fs::Metadata, preserve: bool) -> (u32, i64) {
    if !preserve {
        return (0, 0);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        (metadata.mode(), metadata.mtime())
    }
    #[cfg(not(unix))]
    {
        let _ = metadata;
        (0, 0)
    }
}

fn restore_metadata(path: &Path, entry: &ArchiveEntry, preserve: bool) -> Result<(), AppError> {
    if !preserve {
        return Ok(());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if entry.mode != 0 {
            fs::set_permissions(path, fs::Permissions::from_mode(entry.mode))?;
        }
        if entry.mtime != 0 {
            let time = filetime::FileTime::from_unix_time(entry.mtime, 0);
            filetime::set_file_mtime(path, time)?;
        }
    }
    Ok(())
}

struct Cursor<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Cursor<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self { data, pos: 0 }
    }

    fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.pos)
    }

    fn read_exact_vec(&mut self, len: usize) -> Result<Vec<u8>, AppError> {
        if self.pos + len > self.data.len() {
            return Err(AppError::integrity("archive payload is truncated"));
        }
        let out = self.data[self.pos..self.pos + len].to_vec();
        self.pos += len;
        Ok(out)
    }

    fn read_u8(&mut self) -> Result<u8, AppError> {
        Ok(self.read_exact_vec(1)?[0])
    }

    fn read_u16(&mut self) -> Result<u16, AppError> {
        let bytes: [u8; 2] = self.read_exact_vec(2)?.try_into().unwrap();
        Ok(u16::from_le_bytes(bytes))
    }

    fn read_u32(&mut self) -> Result<u32, AppError> {
        let bytes: [u8; 4] = self.read_exact_vec(4)?.try_into().unwrap();
        Ok(u32::from_le_bytes(bytes))
    }

    fn read_u64(&mut self) -> Result<u64, AppError> {
        let bytes: [u8; 8] = self.read_exact_vec(8)?.try_into().unwrap();
        Ok(u64::from_le_bytes(bytes))
    }

    fn read_i64(&mut self) -> Result<i64, AppError> {
        let bytes: [u8; 8] = self.read_exact_vec(8)?.try_into().unwrap();
        Ok(i64::from_le_bytes(bytes))
    }

    fn read_hash(&mut self) -> Result<[u8; 32], AppError> {
        Ok(self.read_exact_vec(32)?.try_into().unwrap())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_traversal_is_rejected() {
        assert!(validate_archive_path(Path::new("../evil")).is_err());
        assert!(validate_archive_path(Path::new("/tmp/evil")).is_err());
        assert!(validate_archive_path(Path::new("safe/file.txt")).is_ok());
    }
}
