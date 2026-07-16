use std::fmt;

/// Unified error type for the addressor crate.
#[derive(Debug)]
pub enum AddressorError {
    Io(std::io::Error),
    /// Stored blob bytes do not match the hash they are addressed by,
    /// or a truncated-index hit failed full-hash confirmation.
    Integrity(String),
    /// Malformed container / snapshot / varint stream.
    Format(String),
    /// Catalog (redb / fp16 index) failure.
    Catalog(String),
    /// Residual / lite / delta codec failure.
    Codec(String),
    /// Fleet sync layer failure.
    Sync(String),
}

impl fmt::Display for AddressorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AddressorError::Io(e) => write!(f, "io: {e}"),
            AddressorError::Integrity(m) => write!(f, "integrity: {m}"),
            AddressorError::Format(m) => write!(f, "format: {m}"),
            AddressorError::Catalog(m) => write!(f, "catalog: {m}"),
            AddressorError::Codec(m) => write!(f, "codec: {m}"),
            AddressorError::Sync(m) => write!(f, "sync: {m}"),
        }
    }
}

impl std::error::Error for AddressorError {}

impl From<std::io::Error> for AddressorError {
    fn from(e: std::io::Error) -> Self {
        AddressorError::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, AddressorError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_covers_variants() {
        let e = AddressorError::Integrity("blob mismatch".into());
        assert!(format!("{e}").contains("integrity"));
        let e = AddressorError::Format("bad scheme".into());
        assert!(format!("{e}").contains("format"));
    }
}
