// Cubrim — lossless compression library.
// R1-R8: see individual modules for rulebook trace annotations.
//
// Public API:
//   encode(data: &[u8]) -> Vec<u8>       — compress; returns Cubrim v1 blob
//   decode(blob: &[u8]) -> Result<...>   — decompress; fail-closed on corrupt input

pub mod bitpack;
pub(crate) mod cm2;
pub mod codec;
pub mod config;
pub mod cube;
pub mod distance_map;
pub mod domainize;
pub mod error;
pub(crate) mod geocm;
pub mod header;
pub(crate) mod huffman;
pub mod limits;
pub mod phi;
pub(crate) mod ppmd;
pub(crate) mod prof;
pub mod rle;
pub(crate) mod web;

pub use codec::{decode, decode_with_limits, encode, encode_with_config, ORDER2_DEFAULT_MIN_CTX};

/// Encode a Web Profile frame with the near-realtime dynamic profile.
///
/// The returned frame uses the same `MODE_WEB` version-1 wire format as the
/// density-first `EncodeConfig::web_profile` path. `None` is returned only for
/// empty input; callers should compare the frame with identity before sending
/// it, just as the reverse proxy does.
pub fn encode_web_dynamic(data: &[u8], block_size: Option<usize>) -> Option<Vec<u8>> {
    web::encode_web_dynamic_blocked(data, block_size)
}

/// Write the encoder candidate-attribution table to stderr, given the wall time
/// of the encode it should be attributed against. No-op unless
/// `CUBRIM_PROFILE=1`. Development instrumentation — see `prof`.
pub fn report_encode_profile(total_nanos: u128) {
    prof::report(total_nanos);
}
pub use config::{EncodeConfig, GapScheme, Preset, ValueScheme};
pub use error::CubrimError;
pub use limits::DecodeLimits;

// V-AC-8: traceability check module
#[cfg(test)]
mod tests_traceability;
