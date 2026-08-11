#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::fs::{self, File};
use std::io::Read;
use std::path::{Component, Path, PathBuf};

use blake3::Hash;
use globset::{Glob, GlobSet, GlobSetBuilder};
use cubrim::{decode, encode};
use walkdir::WalkDir;

use crate::cli::{ArchiveAddArgs, DeleteArgs, ExtractArgs, ListArgs, TestArgs};
use crate::crypto::{decrypt_payload, encrypt_payload, random_salt, resolve_password, SALT_LEN};
use crate::AppError;

const MAGIC: &[u8; 4] = b"CUBR";
const VERSION_PLAIN_V1: u8 = 1;
const VERSION_ENCRYPTED_V1: u8 = 2;
const VERSION_PLAIN_V2: u8 = 3;
const VERSION_ENCRYPTED_V2: u8 = 4;

const KIND_DIR: u8 = 0;
const KIND_FILE: u8 = 1;
const KIND_SYMLINK: u8 = 2;
const KIND_HARDLINK: u8 = 3;

#[derive(Debug, Clone)]
struct XattrEntry {
    name: Vec<u8>,
    value: Vec<u8>,
}

#[derive(Debug, Clone)]
struct ArchiveEntry {
    path: PathBuf,
    path_bytes: Vec<u8>,
    kind: u8,
    original_size: u64,
    compressed_size: u64,
    mode: u32,
    mtime: i64,
    checksum: [u8; 32],
    data: Vec<u8>,
    link_target: Option<PathBuf>,
    link_target_bytes: Vec<u8>,
    xattrs: Vec<XattrEntry>,
}

#[cfg(unix)]
#[derive(Debug, Clone, Copy, Hash, PartialEq, Eq)]
struct HardlinkKey {
    dev: u64,
    ino: u64,
}

pub fn is_archive_path(path: &Path) -> bool {
    let mut header = [0u8; 4];
    File::open(path)
        .and_then(|mut file| file.read_exact(&mut header))
        .map(|_| &header == MAGIC)
        .unwrap_or(false)
}

pub fn add_archive(args: ArchiveAddArgs) -> Result<(), AppError> {
    if args.archive.exists() && !args.common.force {
        return Err(AppError::usage(format!(
            "{} already exists; pass --force to overwrite",
            args.archive.display()
        )));
    }

    let password = resolve_password(&args.common.password, "Archive")?;
    let entries = collect_entries(&args.paths, args.common.preserve)?;
    let payload = serialize_entries_v2(&entries)?;
    let archive = wrap_payload(&payload, password.as_deref())?;

    fs::write(&args.archive, archive)?;
    if !args.common.quiet {
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

pub fn extract_archive(args: ExtractArgs) -> Result<(), AppError> {
    extract_archive_impl(args, false)
}

pub fn extract_archive_flat(args: ExtractArgs) -> Result<(), AppError> {
    extract_archive_impl(args, true)
}

fn extract_archive_impl(args: ExtractArgs, flatten: bool) -> Result<(), AppError> {
    if !is_archive_path(&args.archive) {
        return Err(AppError::usage(format!(
            "{} is not a .cbr archive",
            args.archive.display()
        )));
    }

    let password = resolve_password(&args.common.password, "Archive")?;
    let entries = read_archive(&args.archive, password.as_deref())?;
    let out_dir = args.out_dir.unwrap_or_else(|| PathBuf::from("."));
    fs::create_dir_all(&out_dir)?;

    for entry in entries.iter().filter(|entry| entry.kind == KIND_DIR) {
        let target = target_path(&out_dir, entry, flatten)?;
        fs::create_dir_all(&target)?;
        restore_metadata(&target, entry, args.common.preserve)?;
    }

    for entry in entries
        .iter()
        .filter(|entry| entry.kind != KIND_DIR)
    {
        let target = target_path(&out_dir, entry, flatten)?;
        if let Some(parent) = target.parent() {
            fs::create_dir_all(parent)?;
        }
        if args.common.force {
            remove_existing_target(&target)?;
        } else if target.exists() {
            return Err(AppError::usage(format!(
                "{} already exists; pass --force to overwrite",
                target.display()
            )));
        }

        match entry.kind {
            KIND_FILE => {
                let data = decode(&entry.data).map_err(|err| AppError::integrity(err.to_string()))?;
                verify_checksum(entry, &data)?;
                fs::write(&target, data)?;
                restore_metadata(&target, entry, args.common.preserve)?;
            }
            KIND_SYMLINK => {
                let link_target = entry.link_target.as_ref().ok_or_else(|| {
                    AppError::integrity(format!(
                        "symlink entry missing target: {}",
                        entry.path.display()
                    ))
                })?;
                validate_symlink_target(&entry.path, link_target)?;
                create_symlink(link_target, &target)?;
                restore_metadata(&target, entry, args.common.preserve)?;
            }
            KIND_HARDLINK => {
                let referent_rel = entry.link_target.as_ref().ok_or_else(|| {
                    AppError::integrity(format!(
                        "hardlink entry missing referent: {}",
                        entry.path.display()
                    ))
                })?;
                let referent = if flatten {
                    flatten_target(&out_dir, referent_rel)?
                } else {
                    safe_join(&out_dir, referent_rel)?
                };
                fs::hard_link(&referent, &target)?;
            }
            other => {
                return Err(AppError::integrity(format!(
                    "archive contains an unknown entry kind: {other}"
                )))
            }
        }

        if !args.common.quiet {
            eprintln!("extracted: {}", entry.path.display());
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
        let kind = match entry.kind {
            KIND_DIR => "dir",
            KIND_FILE => "file",
            KIND_SYMLINK => "symlink",
            KIND_HARDLINK => "hardlink",
            _ => "unknown",
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
        } else if entry.kind == KIND_SYMLINK || entry.kind == KIND_HARDLINK {
            if entry.link_target.is_none() {
                return Err(AppError::integrity(format!(
                    "entry missing link target: {}",
                    entry.path.display()
                )));
            }
        }
    }
    if !args.quiet {
        println!("tested: {} entries OK", entries.len());
    }
    Ok(())
}

pub fn delete_archive_members(args: DeleteArgs) -> Result<(), AppError> {
    if !is_archive_path(&args.archive) {
        return Err(AppError::usage(format!(
            "{} is not a .cbr archive",
            args.archive.display()
        )));
    }

    let password = resolve_password(&args.common.password, "Archive")?;
    let mut entries = read_archive(&args.archive, password.as_deref())?;
    let matcher = compile_patterns(&args.patterns)?;
    let before = entries.len();
    entries.retain(|entry| !matcher.is_match(&entry.path));
    let removed = before.saturating_sub(entries.len());
    if removed == 0 {
        return Err(AppError::usage("no archive members matched the requested patterns"));
    }
    let payload = serialize_entries_v2(&entries)?;
    let archive = wrap_payload(&payload, password.as_deref())?;
    fs::write(&args.archive, archive)?;
    if !args.common.quiet {
        eprintln!("deleted: {removed} entries");
    }
    Ok(())
}

fn collect_entries(paths: &[PathBuf], preserve: bool) -> Result<Vec<ArchiveEntry>, AppError> {
    let mut entries = Vec::new();
    #[cfg(unix)]
    let mut seen_hardlinks: HashMap<HardlinkKey, PathBuf> = HashMap::new();

    for input in paths {
        if !input.exists() && fs::symlink_metadata(input).is_err() {
            return Err(AppError::usage(format!(
                "{} does not exist",
                input.display()
            )));
        }

        let base = input.parent().unwrap_or_else(|| Path::new(""));
        let metadata = fs::symlink_metadata(input)?;
        let rel = input.strip_prefix(base).unwrap_or(input);
        if metadata.file_type().is_symlink() {
            entries.push(symlink_entry(input, rel, preserve)?);
            continue;
        }
        if metadata.is_file() {
            #[cfg(unix)]
            {
                if let Some(entry) = maybe_hardlink_entry(
                    &mut seen_hardlinks,
                    input,
                    rel,
                    &metadata,
                    preserve,
                )? {
                    entries.push(entry);
                    continue;
                }
            }
            entries.push(file_entry(input, rel, preserve)?);
            continue;
        }
        if metadata.is_dir() {
            for item in WalkDir::new(input).follow_links(false).sort_by_file_name() {
                let item = item.map_err(|err| AppError::io(err.to_string()))?;
                let path = item.path();
                let rel = path.strip_prefix(base).unwrap_or(path);
                if rel.as_os_str().is_empty() {
                    continue;
                }
                let metadata = fs::symlink_metadata(path)?;
                let file_type = metadata.file_type();
                if file_type.is_symlink() {
                    entries.push(symlink_entry(path, rel, preserve)?);
                } else if file_type.is_dir() {
                    entries.push(dir_entry(path, rel, preserve)?);
                } else if file_type.is_file() {
                    #[cfg(unix)]
                    {
                        if let Some(entry) = maybe_hardlink_entry(
                            &mut seen_hardlinks,
                            path,
                            rel,
                            &metadata,
                            preserve,
                        )? {
                            entries.push(entry);
                            continue;
                        }
                    }
                    entries.push(file_entry(path, rel, preserve)?);
                }
            }
        }
    }
    if entries.is_empty() {
        return Err(AppError::usage(
            "no regular files, directories, or symlinks to archive",
        ));
    }
    Ok(entries)
}

#[cfg(unix)]
fn maybe_hardlink_entry(
    seen: &mut HashMap<HardlinkKey, PathBuf>,
    path: &Path,
    rel: &Path,
    metadata: &fs::Metadata,
    preserve: bool,
) -> Result<Option<ArchiveEntry>, AppError> {
    use std::os::unix::fs::MetadataExt;

    let key = HardlinkKey {
        dev: metadata.dev(),
        ino: metadata.ino(),
    };
    if metadata.nlink() <= 1 {
        seen.insert(key, rel.to_path_buf());
        return Ok(None);
    }
    if let Some(first_rel) = seen.get(&key) {
        return Ok(Some(hardlink_entry(path, rel, first_rel, preserve)?));
    }
    seen.insert(key, rel.to_path_buf());
    Ok(None)
}

fn file_entry(path: &Path, rel: &Path, preserve: bool) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    let data = fs::read(path)?;
    let compressed = encode(&data);
    let metadata = fs::symlink_metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        path_bytes: path_to_bytes(rel)?,
        kind: KIND_FILE,
        original_size: data.len() as u64,
        compressed_size: compressed.len() as u64,
        mode,
        mtime,
        checksum: *blake3::hash(&data).as_bytes(),
        data: compressed,
        link_target: None,
        link_target_bytes: Vec::new(),
        xattrs: read_xattrs(path, preserve)?,
    })
}

fn dir_entry(path: &Path, rel: &Path, preserve: bool) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    let metadata = fs::symlink_metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        path_bytes: path_to_bytes(rel)?,
        kind: KIND_DIR,
        original_size: 0,
        compressed_size: 0,
        mode,
        mtime,
        checksum: [0; 32],
        data: Vec::new(),
        link_target: None,
        link_target_bytes: Vec::new(),
        xattrs: read_xattrs(path, preserve)?,
    })
}

fn symlink_entry(path: &Path, rel: &Path, preserve: bool) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    let link_target = fs::read_link(path)?;
    validate_symlink_target(rel, &link_target)?;
    let metadata = fs::symlink_metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        path_bytes: path_to_bytes(rel)?,
        kind: KIND_SYMLINK,
        original_size: 0,
        compressed_size: 0,
        mode,
        mtime,
        checksum: [0; 32],
        data: Vec::new(),
        link_target: Some(link_target.clone()),
        link_target_bytes: path_to_bytes(&link_target)?,
        xattrs: read_xattrs(path, preserve)?,
    })
}

fn hardlink_entry(
    path: &Path,
    rel: &Path,
    first_rel: &Path,
    preserve: bool,
) -> Result<ArchiveEntry, AppError> {
    validate_archive_path(rel)?;
    validate_archive_path(first_rel)?;
    let metadata = fs::symlink_metadata(path)?;
    let (mode, mtime) = metadata_values(&metadata, preserve);
    Ok(ArchiveEntry {
        path: rel.to_path_buf(),
        path_bytes: path_to_bytes(rel)?,
        kind: KIND_HARDLINK,
        original_size: 0,
        compressed_size: 0,
        mode,
        mtime,
        checksum: [0; 32],
        data: Vec::new(),
        link_target: Some(first_rel.to_path_buf()),
        link_target_bytes: path_to_bytes(first_rel)?,
        xattrs: Vec::new(),
    })
}

fn wrap_payload(payload: &[u8], password: Option<&str>) -> Result<Vec<u8>, AppError> {
    let mut archive = Vec::new();
    archive.extend_from_slice(MAGIC);
    if let Some(password) = password {
        let salt = random_salt();
        archive.push(VERSION_ENCRYPTED_V2);
        archive.extend_from_slice(&salt);
        archive.extend_from_slice(&encrypt_payload(payload, password, &salt)?);
    } else {
        archive.push(VERSION_PLAIN_V2);
        archive.extend_from_slice(payload);
    }
    Ok(archive)
}

fn serialize_entries_v2(entries: &[ArchiveEntry]) -> Result<Vec<u8>, AppError> {
    let mut out = Vec::new();
    out.extend_from_slice(&(entries.len() as u32).to_le_bytes());
    for entry in entries {
        write_len_prefixed(&mut out, &entry.path_bytes);
        out.push(entry.kind);
        out.extend_from_slice(&entry.original_size.to_le_bytes());
        out.extend_from_slice(&entry.compressed_size.to_le_bytes());
        out.extend_from_slice(&entry.mode.to_le_bytes());
        out.extend_from_slice(&entry.mtime.to_le_bytes());
        out.extend_from_slice(&entry.checksum);
        write_len_prefixed(&mut out, &entry.link_target_bytes);
        out.extend_from_slice(&(entry.xattrs.len() as u32).to_le_bytes());
        for xattr in &entry.xattrs {
            write_len_prefixed(&mut out, &xattr.name);
            write_len_prefixed(&mut out, &xattr.value);
        }
        out.extend_from_slice(&(entry.data.len() as u64).to_le_bytes());
        out.extend_from_slice(&entry.data);
    }
    Ok(out)
}

fn read_archive(path: &Path, password: Option<&str>) -> Result<Vec<ArchiveEntry>, AppError> {
    let bytes = fs::read(path)?;
    if bytes.len() < 5 || &bytes[..4] != MAGIC {
        return Err(AppError::integrity("not a .cbr archive"));
    }
    match bytes[4] {
        VERSION_PLAIN_V1 => parse_entries_v1(&bytes[5..]),
        VERSION_ENCRYPTED_V1 => {
            let payload = decrypt_archive_payload(&bytes, password, VERSION_ENCRYPTED_V1)?;
            parse_entries_v1(&payload)
        }
        VERSION_PLAIN_V2 => parse_entries_v2(&bytes[5..]),
        VERSION_ENCRYPTED_V2 => {
            let payload = decrypt_archive_payload(&bytes, password, VERSION_ENCRYPTED_V2)?;
            parse_entries_v2(&payload)
        }
        other => Err(AppError::integrity(format!(
            "unsupported .cbr version: {other}"
        ))),
    }
}

fn decrypt_archive_payload(
    bytes: &[u8],
    password: Option<&str>,
    _version: u8,
) -> Result<Vec<u8>, AppError> {
    let password =
        password.ok_or_else(|| AppError::usage("archive is encrypted; pass --password"))?;
    if bytes.len() < 5 + SALT_LEN {
        return Err(AppError::integrity("encrypted archive is truncated"));
    }
    let salt: [u8; SALT_LEN] = bytes[5..5 + SALT_LEN].try_into().unwrap();
    decrypt_payload(&bytes[5 + SALT_LEN..], password, &salt)
}

fn parse_entries_v2(payload: &[u8]) -> Result<Vec<ArchiveEntry>, AppError> {
    let mut cursor = Cursor::new(payload);
    let count = cursor.read_u32()? as usize;
    let mut entries = Vec::with_capacity(count);
    for _ in 0..count {
        let path_bytes = cursor.read_len_prefixed()?;
        let path = bytes_to_path(&path_bytes)?;
        validate_archive_path(&path)?;
        let kind = cursor.read_u8()?;
        let original_size = cursor.read_u64()?;
        let compressed_size = cursor.read_u64()?;
        let mode = cursor.read_u32()?;
        let mtime = cursor.read_i64()?;
        let checksum = cursor.read_hash()?;
        let link_target_bytes = cursor.read_len_prefixed()?;
        let link_target = if link_target_bytes.is_empty() {
            None
        } else {
            Some(bytes_to_path(&link_target_bytes)?)
        };
        if let Some(target) = &link_target {
            if kind == KIND_HARDLINK {
                validate_archive_path(target)?;
            } else if kind == KIND_SYMLINK {
                validate_symlink_target(&path, target)?;
            }
        }
        let xattr_count = cursor.read_u32()? as usize;
        let mut xattrs = Vec::with_capacity(xattr_count);
        for _ in 0..xattr_count {
            xattrs.push(XattrEntry {
                name: cursor.read_len_prefixed()?,
                value: cursor.read_len_prefixed()?,
            });
        }
        let data_len = cursor.read_u64()? as usize;
        let data = cursor.read_exact_vec(data_len)?;
        entries.push(ArchiveEntry {
            path,
            path_bytes,
            kind,
            original_size,
            compressed_size,
            mode,
            mtime,
            checksum,
            data,
            link_target,
            link_target_bytes,
            xattrs,
        });
    }
    if cursor.remaining() != 0 {
        return Err(AppError::integrity("archive has trailing payload bytes"));
    }
    Ok(entries)
}

fn parse_entries_v1(payload: &[u8]) -> Result<Vec<ArchiveEntry>, AppError> {
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
            path_bytes,
            kind,
            original_size,
            compressed_size,
            mode,
            mtime,
            checksum,
            data,
            link_target: None,
            link_target_bytes: Vec::new(),
            xattrs: Vec::new(),
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
    ensure_no_nul(path.as_os_str())?;
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

fn validate_symlink_target(entry_path: &Path, target: &Path) -> Result<(), AppError> {
    ensure_no_nul(target.as_os_str())?;
    if target.is_absolute() {
        return Err(AppError::integrity(format!(
            "absolute symlink target rejected for {}",
            entry_path.display()
        )));
    }
    let mut depth = entry_path
        .parent()
        .map(|parent| parent.components().count())
        .unwrap_or(0);
    for component in target.components() {
        match component {
            Component::CurDir => {}
            Component::Normal(_) => depth += 1,
            Component::ParentDir => {
                if depth == 0 {
                    return Err(AppError::integrity(format!(
                        "symlink target escapes extraction root for {}",
                        entry_path.display()
                    )));
                }
                depth -= 1;
            }
            Component::RootDir | Component::Prefix(_) => {
                return Err(AppError::integrity(format!(
                    "unsafe symlink target rejected for {}",
                    entry_path.display()
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

fn flatten_target(base: &Path, rel: &Path) -> Result<PathBuf, AppError> {
    validate_archive_path(rel)?;
    let name = rel.file_name().ok_or_else(|| {
        AppError::integrity(format!(
            "cannot flatten archive entry without terminal name: {}",
            rel.display()
        ))
    })?;
    Ok(base.join(name))
}

fn target_path(base: &Path, entry: &ArchiveEntry, flatten: bool) -> Result<PathBuf, AppError> {
    if flatten {
        flatten_target(base, &entry.path)
    } else {
        safe_join(base, &entry.path)
    }
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

        if entry.kind != KIND_SYMLINK && entry.mode != 0 {
            fs::set_permissions(path, fs::Permissions::from_mode(entry.mode))?;
        }
        if entry.mtime != 0 {
            let time = filetime::FileTime::from_unix_time(entry.mtime, 0);
            if entry.kind == KIND_SYMLINK {
                filetime::set_symlink_file_times(path, time, time)?;
            } else {
                filetime::set_file_times(path, time, time)?;
            }
        }
        restore_xattrs(path, entry)?;
    }

    Ok(())
}

#[cfg(unix)]
fn restore_xattrs(path: &Path, entry: &ArchiveEntry) -> Result<(), AppError> {
    for xattr in &entry.xattrs {
        let name = os_string_from_bytes(&xattr.name)?;
        xattr::set(path, &name, &xattr.value)?;
    }
    Ok(())
}

#[cfg(not(unix))]
fn restore_xattrs(_path: &Path, _entry: &ArchiveEntry) -> Result<(), AppError> {
    Ok(())
}

#[cfg(unix)]
fn read_xattrs(path: &Path, preserve: bool) -> Result<Vec<XattrEntry>, AppError> {
    use std::ffi::OsString;
    use std::os::unix::ffi::OsStringExt;

    if !preserve {
        return Ok(Vec::new());
    }
    let mut out = Vec::new();
    for name in xattr::list(path)? {
        let name: OsString = name;
        let value = xattr::get(path, &name)?
            .ok_or_else(|| AppError::integrity("xattr listed but value was missing"))?;
        out.push(XattrEntry {
            name: name.into_vec(),
            value,
        });
    }
    Ok(out)
}

#[cfg(not(unix))]
fn read_xattrs(_path: &Path, _preserve: bool) -> Result<Vec<XattrEntry>, AppError> {
    Ok(Vec::new())
}

fn compile_patterns(patterns: &[String]) -> Result<GlobSet, AppError> {
    let mut builder = GlobSetBuilder::new();
    for pattern in patterns {
        builder.add(
            Glob::new(pattern)
                .map_err(|err| AppError::usage(format!("invalid delete pattern '{pattern}': {err}")))?,
        );
    }
    builder
        .build()
        .map_err(|err| AppError::usage(format!("failed to compile delete patterns: {err}")))
}

fn write_len_prefixed(out: &mut Vec<u8>, bytes: &[u8]) {
    out.extend_from_slice(&(bytes.len() as u32).to_le_bytes());
    out.extend_from_slice(bytes);
}

fn path_to_bytes(path: &Path) -> Result<Vec<u8>, AppError> {
    ensure_no_nul(path.as_os_str())?;
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        Ok(path.as_os_str().as_bytes().to_vec())
    }
    #[cfg(not(unix))]
    {
        let text = path
            .to_str()
            .ok_or_else(|| AppError::usage("non-UTF-8 paths are not supported on this platform"))?;
        Ok(text.as_bytes().to_vec())
    }
}

fn bytes_to_path(bytes: &[u8]) -> Result<PathBuf, AppError> {
    if bytes.contains(&0) {
        return Err(AppError::integrity("archive path contains a NUL byte"));
    }
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStringExt;
        Ok(PathBuf::from(OsString::from_vec(bytes.to_vec())))
    }
    #[cfg(not(unix))]
    {
        let text = std::str::from_utf8(bytes)
            .map_err(|_| AppError::integrity("archive path is not valid UTF-8"))?;
        Ok(PathBuf::from(text))
    }
}

fn ensure_no_nul(text: &OsStr) -> Result<(), AppError> {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        if text.as_bytes().contains(&0) {
            return Err(AppError::integrity("path contains a NUL byte"));
        }
    }
    #[cfg(not(unix))]
    {
        let rendered = text.to_string_lossy();
        if rendered.as_bytes().contains(&0) {
            return Err(AppError::integrity("path contains a NUL byte"));
        }
    }
    Ok(())
}

#[cfg(unix)]
fn os_string_from_bytes(bytes: &[u8]) -> Result<OsString, AppError> {
    if bytes.contains(&0) {
        return Err(AppError::integrity("xattr name contains a NUL byte"));
    }
    use std::os::unix::ffi::OsStringExt;
    Ok(OsString::from_vec(bytes.to_vec()))
}

fn remove_existing_target(path: &Path) -> Result<(), AppError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) => {
            let file_type = metadata.file_type();
            if file_type.is_dir() && !file_type.is_symlink() {
                fs::remove_dir_all(path)?;
            } else {
                fs::remove_file(path)?;
            }
            Ok(())
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(err) => Err(AppError::from(err)),
    }
}

#[cfg(unix)]
fn create_symlink(target: &Path, link: &Path) -> Result<(), AppError> {
    std::os::unix::fs::symlink(target, link)?;
    Ok(())
}

#[cfg(not(unix))]
fn create_symlink(_target: &Path, _link: &Path) -> Result<(), AppError> {
    Err(AppError::usage(
        "symlink archive entries are not supported on this platform",
    ))
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

    fn read_len_prefixed(&mut self) -> Result<Vec<u8>, AppError> {
        let len = self.read_u32()? as usize;
        self.read_exact_vec(len)
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

    #[test]
    fn internal_relative_symlink_is_allowed() {
        assert!(validate_symlink_target(Path::new("dir/link"), Path::new("../file.txt")).is_ok());
    }

    #[test]
    fn escaping_symlink_is_rejected() {
        assert!(validate_symlink_target(Path::new("dir/link"), Path::new("../../etc/passwd")).is_err());
        assert!(validate_symlink_target(Path::new("dir/link"), Path::new("/etc/passwd")).is_err());
    }
}
