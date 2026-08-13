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
use core::ops::Range;

// The C ABI is not wasm-specific — wasm was simply its first consumer. Built
// natively it produces a cdylib the benchmark can call in-process, which is the
// only way to time a decoder at web-asset sizes: a subprocess per decode puts a
// 3.5-4 ms spawn floor under a sub-millisecond operation and stops
// discriminating entirely (CUBR-0074 Phase B, 2026-08-12).
//
// Measuring through this ABI rather than through `decode_with_limits` directly
// is deliberate: it is the same entry point the browser calls, so a number
// measured here describes the artefact that actually ships.
pub mod ffi;
pub mod wasm;

/// Why a decode stopped.
///
/// The distinction matters for streaming: a frame that simply has not arrived
/// yet must not be reported as corrupt, or a streaming consumer would abort on
/// every chunk boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorKind {
    /// The bytes seen so far are consistent but incomplete. A streaming caller
    /// should feed more input; a whole-buffer caller has a truncated frame.
    NeedMoreInput,
    /// The bytes are malformed, and no amount of further input fixes them.
    Invalid,
}

/// Decode failure. Every variant is fail-closed: no partial output escapes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodeError(pub String, pub ErrorKind);

impl DecodeError {
    /// True when more input could still complete this decode.
    pub fn needs_more_input(&self) -> bool {
        self.1 == ErrorKind::NeedMoreInput
    }

    /// The failure message.
    pub fn message(&self) -> &str {
        &self.0
    }
}

impl core::fmt::Display for DecodeError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "cubrim-web-decoder: {}", self.0)
    }
}

macro_rules! fail {
    ($($arg:tt)*) => {
        return Err(DecodeError(format!($($arg)*), ErrorKind::Invalid))
    };
}

/// Stop because the input ran out, not because it was wrong.
macro_rules! need_more {
    ($($arg:tt)*) => {
        return Err(DecodeError(format!($($arg)*), ErrorKind::NeedMoreInput))
    };
}

pub const MAGIC: [u8; 4] = [0xCB, b'R', b'I', b'M'];
pub const VERSION: u8 = 1;
pub const MODE_WEB: u8 = 18;
/// Raw-store frame: the encoder emits this when no compressed form beats a
/// verbatim copy, so a page fetching `application/cubrim` must handle it.
pub const MODE_RAW: u8 = 1;
/// Fixed frame prefix: magic, version, mode, original length, checksum.
pub const FRAME_HEADER_SIZE: usize = 14;
/// Raw-store header: magic, version, mode, dimension count, edge bound, length.
pub const RAW_HEADER_SIZE: usize = 13;

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

/// Caller-selected resource policy for both whole-buffer and streaming decode.
///
/// A hostile frame controls its declared output length, compressed input length,
/// and match expansion. Every budget is checked before the corresponding
/// allocation or decode step. `max_decoder_memory` includes retained input,
/// retained output, and a fixed allowance for Huffman tables and small decoder
/// state. Streaming retries are transactional in-place and do not allocate a
/// second copy of the decoded body.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DecodeLimits {
    /// Largest output this decode may produce, in bytes.
    pub max_output_size: usize,
    /// Largest compressed frame the streaming decoder may retain, in bytes.
    pub max_input_size: usize,
    /// Largest permitted decoded-to-compressed expansion ratio.
    pub max_expansion_ratio: usize,
    /// Aggregate decoder memory budget, including decoder state and the ABI
    /// fresh-output window when the native or WASM streaming surface is used.
    pub max_decoder_memory: usize,
}

impl DecodeLimits {
    /// 64 MiB — generous for a web asset, small enough that a hostile frame
    /// cannot exhaust a browser tab before the check fires.
    pub const DEFAULT_MAX_OUTPUT: usize = 64 << 20;
    /// 64 MiB — bounds the streaming decoder's retained compressed input.
    pub const DEFAULT_MAX_INPUT: usize = 64 << 20;
    /// 4096x — preserves highly repetitive web assets while keeping the
    /// expansion bound finite and caller-overridable for stricter contexts.
    pub const DEFAULT_MAX_EXPANSION_RATIO: usize = 4096;
    /// 256 MiB — covers 64 MiB input, 64 MiB output, and decoder/table overhead
    /// without making the default unbounded.
    pub const DEFAULT_MAX_DECODER_MEMORY: usize = 256 << 20;

    /// Fixed allowance for Huffman tables, distance tables, and small vectors.
    const DECODER_OVERHEAD: usize = 1 << 20;
}

impl Default for DecodeLimits {
    fn default() -> Self {
        Self {
            max_output_size: Self::DEFAULT_MAX_OUTPUT,
            max_input_size: Self::DEFAULT_MAX_INPUT,
            max_expansion_ratio: Self::DEFAULT_MAX_EXPANSION_RATIO,
            max_decoder_memory: Self::DEFAULT_MAX_DECODER_MEMORY,
        }
    }
}

fn ensure_input_limit(input_len: usize, limits: &DecodeLimits) -> Result<(), DecodeError> {
    if input_len > limits.max_input_size {
        fail!(
            "input size {input_len} exceeds the limit {}",
            limits.max_input_size
        );
    }
    Ok(())
}

fn ensure_expansion_ratio(
    output_len: usize,
    compressed_len: usize,
    limits: &DecodeLimits,
) -> Result<(), DecodeError> {
    if output_len == 0 {
        return Ok(());
    }
    if limits.max_expansion_ratio == 0 {
        fail!("expansion ratio limit must be non-zero");
    }
    let allowed = compressed_len
        .max(1)
        .saturating_mul(limits.max_expansion_ratio);
    if output_len > allowed {
        fail!(
            "expansion ratio {} exceeds the limit {}",
            output_len,
            limits.max_expansion_ratio
        );
    }
    Ok(())
}

fn ensure_decoder_memory(
    retained_input: usize,
    retained_output: usize,
    limits: &DecodeLimits,
) -> Result<(), DecodeError> {
    ensure_decoder_memory_with_extra(retained_input, retained_output, 0, limits)
}

fn ensure_decoder_memory_with_extra(
    retained_input: usize,
    retained_output: usize,
    extra: usize,
    limits: &DecodeLimits,
) -> Result<(), DecodeError> {
    let total = retained_input
        .checked_add(retained_output)
        .and_then(|n| n.checked_add(extra))
        .and_then(|n| n.checked_add(DecodeLimits::DECODER_OVERHEAD));
    if total.is_none_or(|n| n > limits.max_decoder_memory) {
        fail!(
            "decoder memory estimate exceeds the limit {}",
            limits.max_decoder_memory
        );
    }
    Ok(())
}

fn try_reserve_exact<T>(
    buffer: &mut Vec<T>,
    additional: usize,
    what: &str,
) -> Result<(), DecodeError> {
    buffer.try_reserve_exact(additional).map_err(|_| {
        DecodeError(
            format!("unable to reserve {what} bytes"),
            ErrorKind::Invalid,
        )
    })
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

    /// Start reading at an absolute bit offset — how a streaming decoder
    /// resumes at the block boundary it last completed.
    fn at(data: &'a [u8], bit_offset: usize) -> Self {
        let mut reader = Self::new(data);
        reader.pos = (bit_offset / 8).min(data.len());
        let skew = bit_offset % 8;
        if skew > 0 {
            reader.refill();
            // Discard the bits before the offset; `count` cannot be short here
            // unless the buffer ends mid-byte, which `bit_pos` never reports.
            reader.count = reader.count.saturating_sub(skew as u32);
        }
        reader
    }

    /// Absolute bit position: bits consumed from the start of `data`.
    fn bit_pos(&self) -> usize {
        self.pos * 8 - self.count as usize
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
            need_more!(
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
            need_more!("bitstream exhausted mid-block");
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
            need_more!("codeword runs past end of stream");
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
    ensure_input_limit(frame.len(), limits)?;
    if frame.len() < 6 {
        need_more!("frame too short: {} < 6", frame.len());
    }
    if frame[0..4] != MAGIC {
        fail!("bad magic");
    }
    if frame[4] != VERSION {
        fail!("unsupported version {}", frame[4]);
    }
    if frame[5] == MODE_RAW {
        return decode_raw(frame, limits);
    }
    if frame[5] != MODE_WEB {
        fail!("not a Web Profile frame (mode {})", frame[5]);
    }
    if frame.len() < FRAME_HEADER_SIZE {
        need_more!("frame too short: {} < {FRAME_HEADER_SIZE}", frame.len());
    }
    let orig_len = u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]) as usize;
    if orig_len > limits.max_output_size {
        fail!(
            "declared output {orig_len} exceeds the limit {}",
            limits.max_output_size
        );
    }
    ensure_expansion_ratio(orig_len, frame.len() - FRAME_HEADER_SIZE, limits)?;
    ensure_decoder_memory(0, orig_len, limits)?;
    let expected_checksum = [frame[10], frame[11], frame[12], frame[13]];

    let (dist_base, dist_extra) = distance_tables();
    let mut reader = BitReader::new(&frame[FRAME_HEADER_SIZE..]);
    // Reserving the declared length is safe: it was bounded and budgeted above.
    let mut out = Vec::new();
    try_reserve_exact(&mut out, orig_len, "decoded output")?;
    ensure_decoder_memory(0, out.capacity(), limits)?;

    loop {
        let final_block =
            decode_one_block(&mut reader, &mut out, orig_len, &dist_base, &dist_extra)?;
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

/// Decode one block from `reader`, appending to `out`. Returns whether it was
/// the final block.
///
/// Factored out so the whole-buffer decoder and the streaming decoder run the
/// same code: a streaming caller retries this at the last completed block
/// boundary when more input arrives.
fn decode_one_block(
    reader: &mut BitReader,
    out: &mut Vec<u8>,
    orig_len: usize,
    dist_base: &[usize],
    dist_extra: &[u32],
) -> Result<bool, DecodeError> {
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
    let sequence = read_code_lengths(reader, &cl_table, wanted)?;

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

    Ok(final_block)
}
/// Decode a raw-store frame: the encoder's verbatim-copy container.
///
/// The web profile competes against raw-store per file, so an
/// `application/cubrim` response for an already-compressed asset — a WOFF2, a
/// PNG — is legitimately a raw-store frame. A decoder that only understood
/// MODE_WEB would fail on exactly the payloads where compression was correctly
/// declined, which is why this lives here rather than in the caller.
///
/// Layout: `[MAGIC 4][VERSION 1][MODE_RAW 1][N 1][B u16][LEN u32][payload]`.
/// There is no checksum in this container; the bytes are the payload.
fn decode_raw(frame: &[u8], limits: &DecodeLimits) -> Result<Vec<u8>, DecodeError> {
    if frame.len() < RAW_HEADER_SIZE {
        need_more!("raw frame too short: {} < {RAW_HEADER_SIZE}", frame.len());
    }
    let length = u32::from_be_bytes([frame[9], frame[10], frame[11], frame[12]]) as usize;
    if length > limits.max_output_size {
        fail!(
            "declared output {length} exceeds the limit {}",
            limits.max_output_size
        );
    }
    ensure_decoder_memory(0, length, limits)?;
    let payload = &frame[RAW_HEADER_SIZE..];
    if payload.len() < length {
        need_more!(
            "raw payload truncated: {} bytes for a declared {length}",
            payload.len()
        );
    }
    let mut output = Vec::new();
    try_reserve_exact(&mut output, length, "raw output")?;
    ensure_decoder_memory(0, output.capacity(), limits)?;
    output.extend_from_slice(&payload[..length]);
    Ok(output)
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

/// True when `frame` is a container this decoder can handle — a Web Profile
/// frame or a raw-store frame. Both are valid `application/cubrim` responses.
pub fn is_decodable_frame(frame: &[u8]) -> bool {
    is_web_frame(frame)
        || (frame.len() >= RAW_HEADER_SIZE
            && frame[0..4] == MAGIC
            && frame[4] == VERSION
            && frame[5] == MODE_RAW)
}

/// Original length declared by a frame header, without decoding it.
pub fn declared_len(frame: &[u8]) -> Option<usize> {
    if is_web_frame(frame) {
        return Some(u32::from_be_bytes([frame[6], frame[7], frame[8], frame[9]]) as usize);
    }
    if is_decodable_frame(frame) {
        return Some(u32::from_be_bytes([frame[9], frame[10], frame[11], frame[12]]) as usize);
    }
    None
}

// ---------------------------------------------------------------------------
// Streaming
// ---------------------------------------------------------------------------

/// Incremental decoder: feed it a frame in pieces, take output as it becomes
/// available.
///
/// This is what multi-block frames are for. A block is decodable as soon as its
/// predecessors' output exists, so a consumer can render or parse the head of a
/// document while the tail is still arriving. Blocks are the unit of progress —
/// a half-arrived block yields nothing, because a Huffman symbol split across a
/// chunk boundary cannot be decoded twice.
///
/// The integrity contract is unchanged and is **not** weakened by streaming:
/// bytes handed out early are not yet verified against the frame checksum, so
/// [`finish`](Self::finish) must be called and must succeed before the output
/// is treated as authentic. A consumer that renders progressively is trusting
/// the transport until `finish` returns `Ok`; one that cannot accept that
/// should use [`decode`] instead. This is stated rather than hidden because it
/// is the real cost of progressive decode.
///
/// ```no_run
/// # use cubrim_web_decoder::{StreamDecoder, DecodeLimits};
/// let mut stream = StreamDecoder::new(DecodeLimits::default());
/// for chunk in [&b"..."[..]] {
///     let fresh = stream.push(chunk)?;   // newly decoded bytes, may be empty
///     let _ = fresh;
/// }
/// let all = stream.finish()?;            // verifies length and checksum
/// # Ok::<(), cubrim_web_decoder::DecodeError>(())
/// ```
pub struct StreamDecoder {
    limits: DecodeLimits,
    input: Vec<u8>,
    output: Vec<u8>,
    /// Bits consumed from the bitstream, i.e. the start of the next block.
    bit_offset: usize,
    /// How much of `output` the caller has already been shown.
    delivered: usize,
    header: Option<FrameHeader>,
    finished: bool,
    dist_base: Vec<usize>,
    dist_extra: Vec<u32>,
}

#[derive(Clone, Copy)]
struct FrameHeader {
    orig_len: usize,
    checksum: [u8; 4],
    raw: bool,
}

impl StreamDecoder {
    pub fn new(limits: DecodeLimits) -> Self {
        let (dist_base, dist_extra) = distance_tables();
        Self {
            limits,
            input: Vec::new(),
            output: Vec::new(),
            bit_offset: 0,
            delivered: 0,
            header: None,
            finished: false,
            dist_base,
            dist_extra,
        }
    }

    /// Feed a chunk and copy its fresh output into an ABI-owned buffer while
    /// charging that copy against the same aggregate decoder-memory budget.
    pub(crate) fn push_into(
        &mut self,
        chunk: &[u8],
        fresh: &mut Vec<u8>,
    ) -> Result<(), DecodeError> {
        // The previous window is no longer externally visible once the next
        // push starts. Release its capacity before the decoder can allocate.
        fresh.clear();
        fresh.shrink_to_fit();

        let decoded = self.push_range(chunk)?;
        let decoded_len = decoded.end - decoded.start;
        ensure_decoder_memory_with_extra(
            self.input.capacity(),
            self.output.capacity(),
            decoded_len,
            &self.limits,
        )?;
        try_reserve_exact(fresh, decoded_len, "streaming output")?;
        if let Err(err) = ensure_decoder_memory_with_extra(
            self.input.capacity(),
            self.output.capacity(),
            fresh.capacity(),
            &self.limits,
        ) {
            fresh.clear();
            fresh.shrink_to_fit();
            return Err(err);
        }
        fresh.extend_from_slice(&self.output[decoded]);
        Ok(())
    }

    /// Feed the next piece of the frame; returns the bytes newly decoded by
    /// this call, which is empty whenever the chunk did not complete a block.
    ///
    /// A malformed frame fails here and the decoder must not be used again.
    /// Truncation is not a failure — it is the normal state between chunks.
    pub fn push(&mut self, chunk: &[u8]) -> Result<&[u8], DecodeError> {
        let fresh = self.push_range(chunk)?;
        Ok(&self.output[fresh])
    }

    fn push_range(&mut self, chunk: &[u8]) -> Result<Range<usize>, DecodeError> {
        if self.finished {
            fail!("push after finish");
        }
        let new_len = self
            .input
            .len()
            .checked_add(chunk.len())
            .ok_or_else(|| DecodeError("input size overflow".into(), ErrorKind::Invalid))?;
        ensure_input_limit(new_len, &self.limits)?;
        let projected_capacity = self.input.capacity().max(new_len);
        ensure_decoder_memory(projected_capacity, self.output.capacity(), &self.limits)?;
        if self.input.capacity() < new_len {
            try_reserve_exact(&mut self.input, chunk.len(), "stream input")?;
        }
        self.input.extend_from_slice(chunk);
        ensure_decoder_memory(self.input.capacity(), self.output.capacity(), &self.limits)?;
        self.parse_header()?;
        let Some(header) = self.header else {
            let end = self.output.len();
            return Ok(end..end);
        };

        if header.raw {
            let available = self.input.len().saturating_sub(RAW_HEADER_SIZE);
            let wanted = header.orig_len.min(available);
            if wanted > self.output.len() {
                self.output.extend_from_slice(
                    &self.input[RAW_HEADER_SIZE + self.output.len()..RAW_HEADER_SIZE + wanted],
                );
            }
        } else {
            self.decode_ready_blocks(header)?;
        }

        let fresh = self.delivered;
        self.delivered = self.output.len();
        Ok(fresh..self.output.len())
    }

    /// Finish the frame: verify the decoded length and the checksum, then hand
    /// back everything decoded. Fails if the frame is incomplete.
    pub fn finish(mut self) -> Result<Vec<u8>, DecodeError> {
        let Some(header) = self.header else {
            need_more!("frame header never completed");
        };
        if self.output.len() != header.orig_len {
            need_more!(
                "decoded {} bytes of a declared {}",
                self.output.len(),
                header.orig_len
            );
        }
        if !header.raw {
            ensure_expansion_ratio(
                header.orig_len,
                self.input.len().saturating_sub(FRAME_HEADER_SIZE),
                &self.limits,
            )?;
            let digest = blake3::hash(&self.output);
            let bytes = digest.as_bytes();
            if [bytes[0], bytes[1], bytes[2], bytes[3]] != header.checksum {
                fail!("checksum mismatch — refusing to return corrupt output");
            }
        }
        self.finished = true;
        Ok(core::mem::take(&mut self.output))
    }

    /// Bytes decoded so far. Not yet checksum-verified; see the type comment.
    pub fn decoded_len(&self) -> usize {
        self.output.len()
    }

    /// The frame's declared output length, once the header has arrived.
    pub fn declared_len(&self) -> Option<usize> {
        self.header.map(|h| h.orig_len)
    }

    fn parse_header(&mut self) -> Result<(), DecodeError> {
        if self.header.is_some() {
            return Ok(());
        }
        if self.input.len() < 6 {
            return Ok(());
        }
        if self.input[0..4] != MAGIC {
            fail!("bad magic");
        }
        if self.input[4] != VERSION {
            fail!("unsupported version {}", self.input[4]);
        }
        let raw = match self.input[5] {
            MODE_WEB => false,
            MODE_RAW => true,
            other => fail!("not a decodable frame (mode {other})"),
        };
        let need = if raw {
            RAW_HEADER_SIZE
        } else {
            FRAME_HEADER_SIZE
        };
        if self.input.len() < need {
            return Ok(());
        }
        let orig_len = if raw {
            u32::from_be_bytes([
                self.input[9],
                self.input[10],
                self.input[11],
                self.input[12],
            ])
        } else {
            u32::from_be_bytes([self.input[6], self.input[7], self.input[8], self.input[9]])
        } as usize;
        if orig_len > self.limits.max_output_size {
            fail!(
                "declared output {orig_len} exceeds the limit {}",
                self.limits.max_output_size
            );
        }
        let checksum = if raw {
            [0u8; 4]
        } else {
            [
                self.input[10],
                self.input[11],
                self.input[12],
                self.input[13],
            ]
        };
        ensure_decoder_memory(self.input.capacity(), orig_len, &self.limits)?;
        try_reserve_exact(&mut self.output, orig_len, "stream output")?;
        ensure_decoder_memory(self.input.capacity(), self.output.capacity(), &self.limits)?;
        self.header = Some(FrameHeader {
            orig_len,
            checksum,
            raw,
        });
        Ok(())
    }

    /// Decode every block whose bytes have fully arrived, leaving `bit_offset`
    /// at the start of the first block that has not.
    fn decode_ready_blocks(&mut self, header: FrameHeader) -> Result<(), DecodeError> {
        if self.output.len() == header.orig_len {
            return Ok(());
        }
        let body = &self.input[FRAME_HEADER_SIZE..];
        loop {
            let mut reader = BitReader::at(body, self.bit_offset);
            ensure_decoder_memory(self.input.capacity(), self.output.capacity(), &self.limits)?;
            let output_before_block = self.output.len();
            match decode_one_block(
                &mut reader,
                &mut self.output,
                header.orig_len,
                &self.dist_base,
                &self.dist_extra,
            ) {
                Ok(final_block) => {
                    self.bit_offset = reader.bit_pos();
                    if final_block {
                        return Ok(());
                    }
                }
                // Out of input: keep the offset where it was and wait. The
                // partial block's output is truncated, so a retry re-decodes
                // it from the same boundary without allocating a second body.
                Err(err) if err.needs_more_input() => {
                    self.output.truncate(output_before_block);
                    return Ok(());
                }
                Err(err) => {
                    self.output.truncate(output_before_block);
                    return Err(err);
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{DecodeLimits, StreamDecoder};
    use cubrim::{encode_with_config, EncodeConfig};

    #[test]
    fn abi_fresh_copy_is_charged_to_decoder_memory() {
        let data = b"fresh-window-budget".repeat(4096);
        let mut config = EncodeConfig::v1_default();
        config.web_profile = true;
        let frame = encode_with_config(&data, &config);
        let limits = DecodeLimits {
            max_decoder_memory: frame.len() + data.len() + (1 << 20),
            ..DecodeLimits::default()
        };
        let mut core_only = StreamDecoder::new(limits);
        core_only
            .push(&frame)
            .expect("core decoder allocation must fit without the ABI copy");

        let mut stream = StreamDecoder::new(limits);
        let mut fresh = Vec::new();

        let err = stream
            .push_into(&frame, &mut fresh)
            .expect_err("the ABI copy must consume budget");
        assert!(err.message().contains("decoder memory"));
        assert!(fresh.is_empty());
    }
}
