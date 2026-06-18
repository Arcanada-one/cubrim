// Cubrim — lossless compression library.
// R1-R8: see individual modules for rulebook trace annotations.
//
// Public API:
//   encode(data: &[u8]) -> Vec<u8>       — compress; returns Cubrim v1 blob
//   decode(blob: &[u8]) -> Result<...>   — decompress; fail-closed on corrupt input

pub mod error;
pub mod phi;
pub mod domainize;
pub mod distance_map;
pub mod rle;
pub mod bitpack;
pub mod cube;
pub mod header;
pub mod config;
pub mod codec;
pub(crate) mod huffman;

pub use codec::{encode, decode, encode_with_config};
pub use config::{EncodeConfig, GapScheme, ValueScheme};
pub use error::CubrimError;

// V-AC-8: traceability check module
#[cfg(test)]
mod tests_traceability;
