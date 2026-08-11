//! Reference decoder for the Cubrim Web Profile frame (`MODE_WEB`).
//!
//! This crate exists so a web page can decode `application/cubrim` content: it
//! is the CUBR-0076 frame's **reference decoder**, which the CUBR-0072 /
//! ADR-0003 disclosure split classifies as public along with the wire format,
//! its framing and its limits. No encoder-side technique appears here — this
//! crate cannot compress, only decompress.
//!
//! It is a separate crate from `cubrim` because the main crate pulls `ureq`,
//! `dirs`, `rpassword`, `walkdir` and `rand` for its CLI and archive layers,
//! which do not build for `wasm32-unknown-unknown`. That was the blocker
//! recorded against CUBR-0077 in the corpus manifest; a decoder needs none of
//! them.
//!
//! **Equivalence is enforced, not asserted:** `tests/differential.rs` decodes
//! every census sample and a corpus of corrupted frames with both this decoder
//! and `cubrim::decode`, and fails if the outputs differ in any byte or if the
//! two disagree about whether a frame is valid.
//!
//! # Frame
//!
//! ```text
//! [MAGIC 4 = CB 52 49 4D][VERSION 1][MODE_WEB 1 = 18][orig_len u32 BE][checksum u32]
//! bitstream, MSB-first:
//!   [BFINAL 1][BTYPE 2]      BTYPE 1 = one literal context, 2 = three contexts
//!   [HLIT 5][HDIST 6][HCLEN 4]
//!   [code-length-code lengths: 3 bits each, in CL_ORDER]
//!   [code lengths for each context table then the distance table, RLE-coded]
//!   [symbols: literal | (length code + extra)(distance code + extra) | EOB]
//! ```
//!
//! The literal/length table in force is selected by a fixed function of the
//! previously emitted byte, so the decoder needs no transmitted context map.

#![forbid(unsafe_op_in_unsafe_fn)]

extern crate alloc;

use alloc::format;
use alloc::string::String;
use alloc::vec;
use alloc::vec::Vec;

#[cfg(target_arch = "wasm32")]
pub mod wasm;

/// Decode failure. Every variant is fail-closed: no partial output escapes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodeError(pub String);

impl core::fmt::Display for DecodeError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "cubrim-web-decoder: {}", self.0)
    }
}

macro_rules! fail {
    ($($arg:tt)*) => {
        return Err(DecodeError(format!($($arg)*)))
    };
}

pub const MAGIC: [u8; 4] = [0xCB, b'R', b'I', b'M'];
pub const VERSION: u8 = 1;
pub const MODE_WEB: u8 = 18;
/// Fixed frame prefix: magic, version, mode, original length, checksum.
pub const FRAME_HEADER_SIZE: usize = 14;

const MIN_MATCH: usize = 3;
const MAX_MATCH: usize = 258;
const LITLEN_ALPHABET: usize = 286;
const EOB_SYMBOL: usize = 256;
const N_LENGTH_CODES: usize = 29;
const MAX_CODE_LEN: u8 = 14;
const MAX_CL_CODE_LEN: u8 = 7;
const CL_ALPHABET: usize = 19;
const MAX_DIST_CODES: usize = 64;
const CL_ORDER: [usize; CL_ALPHABET] = [
    16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15,
];

const LENGTH_BASE: [usize; N_LENGTH_CODES] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131,
    163, 195, 227, 258,
];
const LENGTH_EXTRA: [u32; N_LENGTH_CODES] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];

/// Caller-selected resource policy. A hostile frame declares whatever length it
/// likes, so the budget is checked against the declaration **before** a byte is
/// decoded and again as output grows.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DecodeLimits {
    /// Largest output this decode may produce, in bytes.
    pub max_output_size: usize,
}

impl DecodeLimits {
    /// 64 MiB — generous for a web asset, small enough that a hostile frame
    /// cannot exhaust a browser tab before the check fires.
    pub const DEFAULT_MAX_OUTPUT: usize = 64 << 20;
}

impl Default for DecodeLimits {
    fn default() -> Self {
        Self {
            max_output_size: Self::DEFAULT_MAX_OUTPUT,
        }
    }
}

fn distance_tables() -> (Vec<usize>, Vec<u32>) {
    let mut base = vec![1usize, 2, 3, 4];
    let mut extra = vec![0u32, 0, 0, 0];
    let mut next = 5usize;
    let mut bits = 1u32;
    while base.len() < MAX_DIST_CODES {
        for _ in 0..2 {
            base.push(next);
            extra.push(bits);
            next += 1usize << bits;
        }
        bits += 1;
    }
    (base, extra)
}

/// Fixed, public context function of the previously emitted byte.
fn context_class(byte: u8, contexts: usize) -> usize {
    if contexts <= 1 {
        return 0;
    }
    let is_digit = byte.is_ascii_digit();
    let is_word = is_digit || byte.is_ascii_alphabetic() || byte == b'_';
    if !is_word {
        0
    } else if is_digit && contexts >= 3 {
        2
    } else {
        1
    }
}

// ---------------------------------------------------------------------------
// Canonical Huffman: validation and a flat lookup table
// ---------------------------------------------------------------------------

/// Kraft check: a complete prefix-free code, or the single-symbol exception.
fn kraft_ok(code_len: &[u8]) -> bool {
    let present: Vec<u8> = code_len.iter().copied().filter(|&l| l > 0).collect();
    if present.is_empty() {
        return false;
    }
    if present.len() == 1 {
        return present[0] == 1;
    }
    let max_len = *present.iter().max().unwrap() as u32;
    if max_len > 30 {
        return false;
    }
    let capacity: u64 = 1u64 << max_len;
    let sum: u64 = present.iter().map(|&l| 1u64 << (max_len - l as u32)).sum();
    sum == capacity
}

/// Flat table over the next `bits` bits: one entry per pattern.
struct HuffTable {
    bits: u8,
    entries: Vec<(u16, u8)>,
}

impl HuffTable {
    /// Build from transmitted code lengths, rejecting anything a valid encoder
    /// cannot have produced. Untrusted input reaches this directly.
    fn build(code_len: &[u8], max_bits: u8) -> Option<Self> {
        if !kraft_ok(code_len) {
            return None;
        }
        let max_len = code_len.iter().copied().max().unwrap_or(0);
        if max_len == 0 || max_len > max_bits {
            return None;
        }
        // Canonical code assignment: symbols ordered by (length, symbol).
        let mut symbols: Vec<usize> = (0..code_len.len()).filter(|&s| code_len[s] > 0).collect();
        symbols.sort_by_key(|&s| (code_len[s], s));
        let size = 1usize << max_len;
        let mut entries = vec![(0u16, 0u8); size];
        let mut code: u32 = 0;
        let mut prev_len: u8 = 0;
        for &sym in &symbols {
            let len = code_len[sym];
            if prev_len > 0 {
                code = code.checked_shl((len - prev_len) as u32)?;
            }
            let shift = max_len - len;
            let base = (code as usize).checked_shl(shift as u32)?;
            let span = 1usize << shift;
            if base + span > size {
                return None;
            }
            entries[base..base + span].fill((sym as u16, len));
            code = code.checked_add(1)?;
            prev_len = len;
        }
        Some(Self {
            bits: max_len,
            entries,
        })
    }
}

// ---------------------------------------------------------------------------
// Bit reader (MSB-first, refilled accumulator)
// ---------------------------------------------------------------------------

struct BitReader<'a> {
    data: &'a [u8],
    pos: usize,
    acc: u64,
    count: u32,
}

impl<'a> BitReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            pos: 0,
            acc: 0,
            count: 0,
        }
    }

    fn remaining(&self) -> usize {
        (self.data.len() - self.pos) * 8 + self.count as usize
    }

    #[inline]
    fn refill(&mut self) {
        while self.count <= 56 && self.pos < self.data.len() {
            self.acc = (self.acc << 8) | self.data[self.pos] as u64;
            self.pos += 1;
            self.count += 8;
        }
    }

    fn read(&mut self, len: u32) -> Result<u32, DecodeError> {
        if len == 0 {
            return Ok(0);
        }
        self.refill();
        if self.count < len {
            fail!(
                "bitstream truncated (want {len} bits, {} remain)",
                self.remaining()
            );
        }
        self.count -= len;
        let mask = if len >= 64 {
            u64::MAX
        } else {
            (1u64 << len) - 1
        };
        Ok(((self.acc >> self.count) & mask) as u32)
    }

    #[inline]
    fn read_symbol(&mut self, table: &HuffTable) -> Result<usize, DecodeError> {
        self.refill();
        if self.count == 0 {
            fail!("bitstream exhausted mid-block");
        }
        let want = table.bits as u32;
        let take = want.min(self.count);
        let index =
            (((self.acc >> (self.count - take)) & ((1u64 << take) - 1)) << (want - take)) as usize;
        let (symbol, len) = table.entries[index];
        if len == 0 {
            fail!("no codeword at this position (corrupt stream)");
        }
        if len as u32 > self.count {
            fail!("codeword runs past end of stream");
        }
        self.count -= len as u32;
        Ok(symbol as usize)
    }
}

// ---------------------------------------------------------------------------
// Decode
// ---------------------------------------------------------------------------

/// Decode a Web Profile frame under the default resource policy.
pub fn decode(frame: &[u8]) -> Result<Vec<u8>, DecodeError> {
    decode_with_limits(frame, &DecodeLimits::default())
}

/// Decode a Web Profile frame under a caller-selected resource policy.
///
/// Fail-closed on every malformed field, and on a checksum mismatch: corrupt
/// output is never returned as success.
pub fn decode_with_limits(frame: &[u8], limits: &DecodeLimits) -> Result<Vec<u8>, DecodeError> {
    if frame.len() < FRAME_HEADER_SIZE {
        fail!("frame too short: {} < {FRAME_HEADER_SIZE}", frame.len());
    }
    if frame[0..4] != MAGIC {
        fail!("bad magic");
    }
    if frame[4] != VERSION {
        fail!("unsupported version {}", frame[4]);
    }
    if frame[5] != MODE_WEB {
        fail!("not a Web Profile frame (mode {})", frame[5]);
    }
    let orig_len = u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]) as usize;
    if orig_len > limits.max_output_size {
        fail!(
            "declared output {orig_len} exceeds the limit {}",
            limits.max_output_size
        );
    }
    let expected_checksum = [frame[10], frame[11], frame[12], frame[13]];

    let (dist_base, dist_extra) = distance_tables();
    let mut reader = BitReader::new(&frame[FRAME_HEADER_SIZE..]);
    // Reserving the declared length is safe: it was bounded above.
    let mut out: Vec<u8> = Vec::with_capacity(orig_len);

    loop {
        let final_block = reader.read(1)? == 1;
        let contexts = match reader.read(2)? {
            1 => 1usize,
            2 => 3usize,
            other => fail!("unknown block type {other}"),
        };
        let hlit = reader.read(5)? as usize + 257;
        let hdist = reader.read(6)? as usize + 1;
        let hclen = reader.read(4)? as usize + 4;
        if hlit > LITLEN_ALPHABET || hdist > MAX_DIST_CODES || hclen > CL_ALPHABET {
            fail!("alphabet size out of range");
        }

        let mut cl_lengths = vec![0u8; CL_ALPHABET];
        for &symbol in CL_ORDER.iter().take(hclen) {
            cl_lengths[symbol] = reader.read(3)? as u8;
        }
        let cl_table = match HuffTable::build(&cl_lengths, MAX_CL_CODE_LEN) {
            Some(t) => t,
            None => fail!("invalid code-length table"),
        };

        let wanted = contexts * hlit + hdist;
        let sequence = read_code_lengths(&mut reader, &cl_table, wanted)?;

        let mut tables = Vec::with_capacity(contexts);
        for ctx in 0..contexts {
            match HuffTable::build(&sequence[ctx * hlit..(ctx + 1) * hlit], MAX_CODE_LEN) {
                Some(t) => tables.push(t),
                None => fail!("invalid literal/length table for context {ctx}"),
            }
        }
        let dist_table = match HuffTable::build(&sequence[contexts * hlit..], MAX_CODE_LEN) {
            Some(t) => t,
            None => fail!("invalid distance table"),
        };

        loop {
            let ctx = if out.is_empty() {
                context_class(b' ', contexts)
            } else {
                context_class(out[out.len() - 1], contexts)
            };
            let symbol = reader.read_symbol(&tables[ctx])?;
            if symbol == EOB_SYMBOL {
                break;
            }
            if symbol < EOB_SYMBOL {
                if out.len() >= orig_len {
                    fail!("output longer than the declared length");
                }
                out.push(symbol as u8);
                continue;
            }
            let lc = symbol - EOB_SYMBOL - 1;
            if lc >= N_LENGTH_CODES {
                fail!("length code {lc} out of range");
            }
            let length = LENGTH_BASE[lc] + reader.read(LENGTH_EXTRA[lc])? as usize;
            if !(MIN_MATCH..=MAX_MATCH).contains(&length) {
                fail!("match length {length} out of range");
            }
            let dc = reader.read_symbol(&dist_table)?;
            if dc >= dist_base.len() {
                fail!("distance code {dc} out of range");
            }
            let distance = dist_base[dc] + reader.read(dist_extra[dc])? as usize;
            if distance == 0 || distance > out.len() {
                fail!("invalid distance {distance} (output length {})", out.len());
            }
            if out.len() + length > orig_len {
                fail!("match overruns the declared length");
            }
            let start = out.len() - distance;
            if distance >= length {
                out.extend_from_within(start..start + length);
            } else {
                // Overlapping run: later bytes read what this loop just wrote,
                // so the copy must stay byte-wise.
                for k in 0..length {
                    let byte = out[start + k];
                    out.push(byte);
                }
            }
        }

        if final_block {
            break;
        }
    }

    if out.len() != orig_len {
        fail!(
            "decoded {} bytes but the header declares {orig_len}",
            out.len()
        );
    }
    let digest = blake3::hash(&out);
    let bytes = digest.as_bytes();
    if [bytes[0], bytes[1], bytes[2], bytes[3]] != expected_checksum {
        fail!("checksum mismatch — refusing to return corrupt output");
    }
    Ok(out)
}

fn read_code_lengths(
    reader: &mut BitReader,
    table: &HuffTable,
    wanted: usize,
) -> Result<Vec<u8>, DecodeError> {
    let mut lengths: Vec<u8> = Vec::with_capacity(wanted);
    while lengths.len() < wanted {
        let symbol = reader.read_symbol(table)?;
        match symbol {
            0..=15 => lengths.push(symbol as u8),
            16 => {
                let last = match lengths.last() {
                    Some(&l) => l,
                    None => fail!("repeat-previous with no previous length"),
                };
                let run = reader.read(2)? as usize + 3;
                if lengths.len() + run > wanted {
                    fail!("code-length repeat overruns the table");
                }
                lengths.resize(lengths.len() + run, last);
            }
            17 | 18 => {
                let run = if symbol == 17 {
                    reader.read(3)? as usize + 3
                } else {
                    reader.read(7)? as usize + 11
                };
                if lengths.len() + run > wanted {
                    fail!("zero-run overruns the table");
                }
                lengths.resize(lengths.len() + run, 0);
            }
            other => fail!("bad code-length symbol {other}"),
        }
    }
    Ok(lengths)
}

/// True when `frame` carries the Web Profile magic, version and mode bytes.
/// Cheap enough for a content sniffer; says nothing about the payload.
pub fn is_web_frame(frame: &[u8]) -> bool {
    frame.len() >= FRAME_HEADER_SIZE
        && frame[0..4] == MAGIC
        && frame[4] == VERSION
        && frame[5] == MODE_WEB
}

/// Original length declared by a frame header, without decoding it.
pub fn declared_len(frame: &[u8]) -> Option<usize> {
    if !is_web_frame(frame) {
        return None;
    }
    Some(u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]) as usize)
}
