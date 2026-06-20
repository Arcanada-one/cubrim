// Cubrim — lossless compression library.
// R1-R8: see individual modules for rulebook trace annotations.
//
// Public API:
//   encode(data: &[u8]) -> Vec<u8>       — compress; returns Cubrim v1 blob
//   decode(blob: &[u8]) -> Result<...>   — decompress; fail-closed on corrupt input

pub mod bitpack;
pub mod codec;
pub mod config;
pub mod cube;
pub mod distance_map;
pub mod domainize;
pub mod error;
pub mod header;
pub(crate) mod huffman;
pub mod phi;
pub mod rle;

pub use codec::{decode, encode, encode_with_config, ORDER2_DEFAULT_MIN_CTX};
pub use config::{EncodeConfig, GapScheme, ValueScheme};
pub use error::CubrimError;

// V-AC-8: traceability check module
#[cfg(test)]
mod tests_traceability;
