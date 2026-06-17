// Error types for the Cubrim archiver.
// Hand-rolled (no thiserror dependency) per plan requirements.

use std::fmt;

/// All errors produced by the Cubrim codec.
#[derive(Debug, Clone)]
pub enum CubrimError {
    /// Invalid magic bytes — not a Cubrim v1 file.
    InvalidMagic(String),
    /// Unsupported format version.
    UnsupportedVersion(u8),
    /// Gap invariant violated (R3.1).
    GapInvariant(String),
    /// General decode error (corrupt/truncated stream).
    Decode(String),
    /// IO error (file operations).
    Io(String),
}

impl fmt::Display for CubrimError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CubrimError::InvalidMagic(msg) => write!(f, "InvalidMagic: {msg}"),
            CubrimError::UnsupportedVersion(v) => {
                write!(f, "UnsupportedVersion: {v} (only version 1 is supported)")
            }
            CubrimError::GapInvariant(msg) => write!(f, "GapInvariant: {msg}"),
            CubrimError::Decode(msg) => write!(f, "DecodeError: {msg}"),
            CubrimError::Io(msg) => write!(f, "IoError: {msg}"),
        }
    }
}

impl std::error::Error for CubrimError {}

impl From<std::io::Error> for CubrimError {
    fn from(e: std::io::Error) -> Self {
        CubrimError::Io(e.to_string())
    }
}
