//! MODE_WEB — table-driven static-entropy container (CUBR-0076, hypothesis 13).
//!
//! Decode is table-driven end to end: every alphabet's canonical Huffman table
//! is transmitted in the block header and frozen for the whole block, so the
//! decoder runs a flat lookup per symbol and adapts nothing. That is the whole
//! point of the mode — the web-profile kill gate (hypothesis 12) implies a
//! decode budget no adaptive per-bit model in this codebase can reach, and the
//! charged size model in
//! `documentation/ephemeral/research/CUBR-0076-SIZEMODEL-RESULTS-20260811.md`
//! showed this architecture class holds gzip-9 density on the real web corpus
//! (121608 B modelled against a 129193 B bar) while missing brotli-11 parity.
//!
//! This container is **opt-in** (`EncodeConfig::web_profile`) and competitive:
//! the encoder keeps it only when it is strictly smaller than the incumbent, so
//! an input that does not benefit falls back byte-identically to the existing
//! encoding. Default output is unchanged.
//!
//! Wire format (all multi-byte integers big-endian, bitstream MSB-first):
//!
//! ```text
//! [MAGIC 4][VERSION 1][MODE_WEB 1][orig_len u32][checksum u32]  = 14 bytes
//! bitstream:
//!   [BFINAL 1][BTYPE 2]                     BTYPE 1 = one literal context
//!                                           BTYPE 2 = three literal contexts
//!   [HLIT 5]   number of literal/length codes - 257
//!   [HDIST 6]  number of distance codes - 1
//!   [HCLEN 4]  number of code-length codes - 4
//!   [CL lengths: 3 bits each, in CL_ORDER]
//!   [code-length sequence for each context table, then the distance table,
//!    RLE-coded (16 = repeat previous 3-6, 17 = zero 3-10, 18 = zero 11-138)
//!    and Huffman-coded with the code-length alphabet]
//!   [symbols: literal | (length code + extra) (distance code + extra) | EOB]
//! ```
//!
//! The literal/length table in force is selected by a fixed, public function of
//! the previously emitted byte ([`context_class`]) — known to the decoder for
//! literals and matches alike, so every context table carries the whole
//! alphabet.

use crate::error::CubrimError;
use crate::header::{MAGIC, MODE_WEB, VERSION};
use crate::huffman::HuffTable;

/// Minimum match length, as in DEFLATE.
const MIN_MATCH: usize = 3;
/// Maximum match length, as in DEFLATE.
const MAX_MATCH: usize = 258;

/// 256 literals + end-of-block + 29 length codes.
const LITLEN_ALPHABET: usize = 286;
const EOB_SYMBOL: usize = 256;
const N_LENGTH_CODES: usize = 29;

/// Code-length limit for the literal/length and distance alphabets.
///
/// Fourteen rather than fifteen: the shared flat decode table
/// ([`HuffTable`]) refuses codes deeper than that, and reusing the repository's
/// table-driven decoder is worth more than one bit of code depth.
const MAX_CODE_LEN: u8 = 14;
/// Code-length limit for the code-length alphabet itself.
const MAX_CL_CODE_LEN: u8 = 7;
const CL_ALPHABET: usize = 19;
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

/// Largest distance alphabet the format allows (covers a 1 GiB window).
const MAX_DIST_CODES: usize = 64;
/// Fixed container prefix: magic, version, mode, original length, checksum.
const WEB_HEADER_SIZE: usize = 14;
/// Hash-chain index width for the match finder.
const HASH_BITS: u32 = 18;
/// Chain depth walked per position by the match finder.
const MAX_CHAIN: usize = 256;
/// Shortest-path parse refinement passes.
const PARSE_ITERATIONS: usize = 3;
/// Match lengths below this are all probed by the optimal parse; above it only
/// the lengths the match finder actually reported are probed.
const EXPLORE_LENGTHS: usize = 32;

/// DEFLATE distance codes, extended by doubling past 32 KiB.
///
/// Codes 0..3 are distances 1..4 with no extra bits; every later pair of codes
/// doubles the covered range and adds one extra bit. Extending the same rule
/// past DEFLATE's 30 codes is what buys the whole-file window.
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

fn length_code(length: usize) -> usize {
    debug_assert!((MIN_MATCH..=MAX_MATCH).contains(&length));
    match LENGTH_BASE.binary_search(&length) {
        Ok(idx) => idx,
        Err(idx) => idx - 1,
    }
}

fn dist_code(base: &[usize], distance: usize) -> usize {
    match base.binary_search(&distance) {
        Ok(idx) => idx,
        Err(idx) => idx - 1,
    }
}

/// Fixed, public context function of the previously emitted byte.
///
/// Three-way: non-word bytes (whitespace and punctuation, which dominate the
/// structural skeleton of web text), letters, and digits. The split is frozen
/// in the format, so the decoder computes it without any transmitted map.
pub(crate) fn context_class(byte: u8, contexts: usize) -> usize {
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
// Bit I/O (MSB-first, matching every other bitstream in this codebase)
// ---------------------------------------------------------------------------

struct BitWriter {
    out: Vec<u8>,
    acc: u64,
    bits: u32,
}

impl BitWriter {
    fn new(capacity: usize) -> Self {
        Self {
            out: Vec::with_capacity(capacity),
            acc: 0,
            bits: 0,
        }
    }

    fn write(&mut self, value: u32, len: u32) {
        if len == 0 {
            return;
        }
        debug_assert!(len <= 32);
        let mask: u64 = if len >= 32 {
            u32::MAX as u64
        } else {
            (1u64 << len) - 1
        };
        self.acc = (self.acc << len) | (value as u64 & mask);
        self.bits += len;
        while self.bits >= 8 {
            self.bits -= 8;
            self.out.push(((self.acc >> self.bits) & 0xFF) as u8);
        }
    }

    fn finish(mut self) -> Vec<u8> {
        if self.bits > 0 {
            let pad = 8 - self.bits;
            self.out.push(((self.acc << pad) & 0xFF) as u8);
        }
        self.out
    }
}

struct BitReader<'a> {
    data: &'a [u8],
    bit_pos: usize,
}

impl<'a> BitReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self { data, bit_pos: 0 }
    }

    fn remaining(&self) -> usize {
        (self.data.len() * 8).saturating_sub(self.bit_pos)
    }

    fn read(&mut self, len: u32) -> Result<u32, CubrimError> {
        if (len as usize) > self.remaining() {
            return Err(CubrimError::Decode(format!(
                "MODE_WEB: bitstream truncated (want {len} bits, {} remain)",
                self.remaining()
            )));
        }
        let mut value = 0u32;
        for _ in 0..len {
            let byte = self.data[self.bit_pos / 8];
            let bit = (byte >> (7 - (self.bit_pos % 8))) & 1;
            value = (value << 1) | bit as u32;
            self.bit_pos += 1;
        }
        Ok(value)
    }

    /// Decode one symbol with a prebuilt flat table. Fail-closed: an unmatched
    /// bit pattern or a codeword that runs past the end of the stream is an
    /// error, never a panic and never a silent zero.
    fn read_symbol(&mut self, table: &HuffTable) -> Result<usize, CubrimError> {
        let want = table.bits() as usize;
        let available = self.remaining();
        if available == 0 {
            return Err(CubrimError::Decode(
                "MODE_WEB: bitstream exhausted mid-block".into(),
            ));
        }
        let take = want.min(available);
        let mut index = 0usize;
        for i in 0..take {
            let pos = self.bit_pos + i;
            let byte = self.data[pos / 8];
            let bit = (byte >> (7 - (pos % 8))) & 1;
            index = (index << 1) | bit as usize;
        }
        index <<= want - take;
        let (symbol, len) = table.lookup(index);
        if len == 0 {
            return Err(CubrimError::Decode(format!(
                "MODE_WEB: no codeword at bit {} (corrupt stream)",
                self.bit_pos
            )));
        }
        if len as usize > available {
            return Err(CubrimError::Decode(
                "MODE_WEB: codeword runs past end of stream".into(),
            ));
        }
        self.bit_pos += len as usize;
        Ok(symbol as usize)
    }
}

// ---------------------------------------------------------------------------
// Length-limited canonical Huffman (package-merge)
// ---------------------------------------------------------------------------

/// Optimal code lengths under a hard maximum length.
///
/// Plain Huffman first; package-merge only when the unconstrained code would
/// exceed the limit. A single present symbol gets length 1 (DEFLATE
/// convention), which [`crate::huffman::kraft_ok`] accepts.
pub(crate) fn limited_code_lengths(freqs: &[usize], limit: u8) -> Vec<u8> {
    let n = freqs.len();
    let mut lengths = vec![0u8; n];
    let present: Vec<usize> = (0..n).filter(|&s| freqs[s] > 0).collect();
    if present.is_empty() {
        return lengths;
    }
    if present.len() == 1 {
        lengths[present[0]] = 1;
        return lengths;
    }

    let plain = plain_huffman(freqs, &present);
    if plain.iter().copied().max().unwrap_or(0) <= limit {
        return plain;
    }
    package_merge(freqs, &present, limit)
}

fn plain_huffman(freqs: &[usize], present: &[usize]) -> Vec<u8> {
    // (weight, tie-break, node index); children stored out of line.
    let mut depth = vec![0u8; freqs.len()];
    let mut groups: Vec<(usize, usize, Vec<usize>)> = present
        .iter()
        .enumerate()
        .map(|(order, &s)| (freqs[s], order, vec![s]))
        .collect();
    let mut counter = groups.len();
    while groups.len() > 1 {
        groups.sort_by_key(|(w, order, _)| (*w, *order));
        let (w1, _, g1) = groups.remove(0);
        let (w2, _, g2) = groups.remove(0);
        for &s in g1.iter().chain(g2.iter()) {
            depth[s] = depth[s].saturating_add(1);
        }
        let mut merged = g1;
        merged.extend(g2);
        groups.push((w1 + w2, counter, merged));
        counter += 1;
    }
    depth
}

fn package_merge(freqs: &[usize], present: &[usize], limit: u8) -> Vec<u8> {
    let k = present.len();
    debug_assert!((1usize << limit) >= k, "limit too small for the alphabet");
    // Items are (weight, members-by-index-into-present).
    let base: Vec<(usize, Vec<usize>)> = {
        let mut items: Vec<(usize, usize)> = present
            .iter()
            .enumerate()
            .map(|(idx, &s)| (freqs[s], idx))
            .collect();
        items.sort_by_key(|(w, idx)| (*w, *idx));
        items.into_iter().map(|(w, idx)| (w, vec![idx])).collect()
    };
    let mut current = base.clone();
    for _ in 1..limit {
        let mut packages: Vec<(usize, Vec<usize>)> = Vec::with_capacity(current.len() / 2);
        let mut j = 0;
        while j + 1 < current.len() {
            let weight = current[j].0 + current[j + 1].0;
            let mut members = current[j].1.clone();
            members.extend_from_slice(&current[j + 1].1);
            packages.push((weight, members));
            j += 2;
        }
        current = base.clone();
        current.extend(packages);
        current.sort_by_key(|(w, members)| (*w, members.len(), members[0]));
    }

    let mut counts = vec![0usize; k];
    for (_, members) in current.iter().take(2 * k - 2) {
        for &idx in members {
            counts[idx] += 1;
        }
    }
    let mut lengths = vec![0u8; freqs.len()];
    // `present` order was re-sorted into `base`; recover it the same way.
    let mut order: Vec<usize> = (0..k).collect();
    order.sort_by_key(|&idx| (freqs[present[idx]], idx));
    for (slot, &idx) in order.iter().enumerate() {
        lengths[present[idx]] = counts[slot].max(1) as u8;
    }
    lengths
}

// ---------------------------------------------------------------------------
// Code-length RLE (the table descriptors on the wire)
// ---------------------------------------------------------------------------

/// One RLE item: (code-length-alphabet symbol, extra bit count, extra value).
type RleItem = (usize, u32, u32);

fn rle_code_lengths(lengths: &[u8]) -> Vec<RleItem> {
    let mut out = Vec::new();
    let n = lengths.len();
    let mut i = 0usize;
    while i < n {
        let current = lengths[i];
        let mut run = 1usize;
        while i + run < n && lengths[i + run] == current {
            run += 1;
        }
        if current == 0 {
            while run >= 11 {
                let take = run.min(138);
                out.push((18usize, 7u32, (take - 11) as u32));
                run -= take;
                i += take;
            }
            while run >= 3 {
                let take = run.min(10);
                out.push((17usize, 3u32, (take - 3) as u32));
                run -= take;
                i += take;
            }
            for _ in 0..run {
                out.push((0usize, 0u32, 0u32));
                i += 1;
            }
        } else {
            out.push((current as usize, 0u32, 0u32));
            i += 1;
            run -= 1;
            while run >= 3 {
                let take = run.min(6);
                out.push((16usize, 2u32, (take - 3) as u32));
                run -= take;
                i += take;
            }
            for _ in 0..run {
                out.push((current as usize, 0u32, 0u32));
                i += 1;
            }
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Match finding and the shortest-path parse
// ---------------------------------------------------------------------------

/// A parsed token: a literal, or a match of `length` bytes at `distance` back.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Token {
    pub(crate) literal: u8,
    pub(crate) length: usize,
    pub(crate) distance: usize,
}

impl Token {
    fn literal(byte: u8) -> Self {
        Self {
            literal: byte,
            length: 0,
            distance: 0,
        }
    }

    fn matched(length: usize, distance: usize) -> Self {
        Self {
            literal: 0,
            length,
            distance,
        }
    }
}

fn hash3(data: &[u8], pos: usize) -> usize {
    let key = ((data[pos] as u32) << 16) | ((data[pos + 1] as u32) << 8) | data[pos + 2] as u32;
    (key.wrapping_mul(2_654_435_761) >> (32 - HASH_BITS)) as usize
}

/// Per position, the improving `(length, distance)` pairs on the hash chain.
///
/// A pair `(l, d)` means every match length in `(previous reported l, l]` is
/// available at distance `d`.
fn collect_candidates(data: &[u8]) -> Vec<Vec<(u32, u32)>> {
    let n = data.len();
    let mut out: Vec<Vec<(u32, u32)>> = vec![Vec::new(); n];
    if n < MIN_MATCH {
        return out;
    }
    let mut head = vec![u32::MAX; 1usize << HASH_BITS];
    let mut prev = vec![u32::MAX; n];
    for pos in 0..=(n - MIN_MATCH) {
        let h = hash3(data, pos);
        let mut candidate = head[h];
        let max_len = MAX_MATCH.min(n - pos);
        let mut best_len = 0usize;
        let mut chain = MAX_CHAIN;
        while candidate != u32::MAX && chain > 0 {
            let cand = candidate as usize;
            let distance = pos - cand;
            if best_len == 0 || data[cand + best_len] == data[pos + best_len] {
                let mut length = 0usize;
                while length < max_len && data[cand + length] == data[pos + length] {
                    length += 1;
                }
                if length > best_len && length >= MIN_MATCH {
                    best_len = length;
                    out[pos].push((length as u32, distance as u32));
                    if length == max_len {
                        break;
                    }
                }
            }
            candidate = prev[cand];
            chain -= 1;
        }
        prev[pos] = head[h];
        head[h] = pos as u32;
    }
    out
}

struct Prices {
    litlen: Vec<Vec<u32>>,
    dist: Vec<u32>,
}

/// Bit prices from a parse's own histograms. Unused symbols are priced just
/// above the length limit rather than excluded, so the parse can still reach
/// for them on the next iteration.
fn prices_from(tokens: &[Token], data: &[u8], contexts: usize, dist_base: &[usize]) -> Prices {
    let (litlen_freqs, dist_freqs) = histograms(tokens, data, contexts, dist_base);
    let unused = (MAX_CODE_LEN + 2) as u32;
    let litlen = litlen_freqs
        .iter()
        .map(|freqs| {
            limited_code_lengths(freqs, MAX_CODE_LEN)
                .into_iter()
                .map(|l| if l == 0 { unused } else { l as u32 })
                .collect()
        })
        .collect();
    let dist = limited_code_lengths(&dist_freqs, MAX_CODE_LEN)
        .into_iter()
        .map(|l| if l == 0 { unused } else { l as u32 })
        .collect();
    Prices { litlen, dist }
}

/// Greedy-with-lazy parse, used to seed the price table.
fn seed_parse(data: &[u8], candidates: &[Vec<(u32, u32)>]) -> Vec<Token> {
    let n = data.len();
    let mut tokens = Vec::new();
    let mut i = 0usize;
    while i < n {
        let best = candidates[i].last().copied();
        match best {
            Some((length, distance)) if length as usize >= MIN_MATCH => {
                let next_better =
                    i + 1 < n && candidates[i + 1].last().is_some_and(|&(l, _)| l > length);
                if next_better {
                    tokens.push(Token::literal(data[i]));
                    i += 1;
                } else {
                    tokens.push(Token::matched(length as usize, distance as usize));
                    i += length as usize;
                }
            }
            _ => {
                tokens.push(Token::literal(data[i]));
                i += 1;
            }
        }
    }
    tokens
}

/// Shortest-path (zopfli-class) parse against the real bit prices.
///
/// The charged size model showed this is what decides the gate: a lazy parse
/// alone leaves the aggregate 1.11% above the gzip-9 bar, and the shortest-path
/// parse clears it by 5.9%. Long-standing public technique — nothing new is
/// invented here.
fn optimal_parse(
    data: &[u8],
    contexts: usize,
    dist_base: &[usize],
    dist_extra: &[u32],
) -> Vec<Token> {
    let n = data.len();
    if n == 0 {
        return Vec::new();
    }
    let candidates = collect_candidates(data);
    let mut tokens = seed_parse(data, &candidates);

    for _ in 0..PARSE_ITERATIONS {
        let prices = prices_from(&tokens, data, contexts, dist_base);
        let mut cost = vec![0u64; n + 1];
        let mut choice = vec![(0u32, 0u32); n + 1];
        for i in (0..n).rev() {
            let ctx = if i == 0 {
                context_class(b' ', contexts)
            } else {
                context_class(data[i - 1], contexts)
            };
            let mut best_cost = prices.litlen[ctx][data[i] as usize] as u64 + cost[i + 1];
            let mut best_choice = (0u32, 0u32);
            let mut floor_len = MIN_MATCH - 1;
            for &(length, distance) in &candidates[i] {
                let length = length as usize;
                let dc = dist_code(dist_base, distance as usize);
                let dist_price = prices.dist[dc] as u64 + dist_extra[dc] as u64;
                let upper = length.min(EXPLORE_LENGTHS);
                let long_probe = if length > EXPLORE_LENGTHS {
                    Some(length)
                } else {
                    None
                };
                for probe in (floor_len + 1..=upper).chain(long_probe) {
                    let lc = length_code(probe);
                    let price = prices.litlen[ctx][EOB_SYMBOL + 1 + lc] as u64
                        + LENGTH_EXTRA[lc] as u64
                        + dist_price
                        + cost[i + probe];
                    if price < best_cost {
                        best_cost = price;
                        best_choice = (probe as u32, distance);
                    }
                }
                floor_len = length;
            }
            cost[i] = best_cost;
            choice[i] = best_choice;
        }

        tokens = Vec::new();
        let mut i = 0usize;
        while i < n {
            let (length, distance) = choice[i];
            if length == 0 {
                tokens.push(Token::literal(data[i]));
                i += 1;
            } else {
                tokens.push(Token::matched(length as usize, distance as usize));
                i += length as usize;
            }
        }
    }
    tokens
}

/// Per-context literal/length histograms and the shared distance histogram.
fn histograms(
    tokens: &[Token],
    data: &[u8],
    contexts: usize,
    dist_base: &[usize],
) -> (Vec<Vec<usize>>, Vec<usize>) {
    let mut litlen = vec![vec![0usize; LITLEN_ALPHABET]; contexts];
    let mut dist = vec![0usize; MAX_DIST_CODES];
    let mut pos = 0usize;
    for token in tokens {
        let ctx = if pos == 0 {
            context_class(b' ', contexts)
        } else {
            context_class(data[pos - 1], contexts)
        };
        if token.length == 0 {
            litlen[ctx][token.literal as usize] += 1;
            pos += 1;
        } else {
            let lc = length_code(token.length);
            litlen[ctx][EOB_SYMBOL + 1 + lc] += 1;
            dist[dist_code(dist_base, token.distance)] += 1;
            pos += token.length;
        }
    }
    let final_ctx = if data.is_empty() {
        context_class(b' ', contexts)
    } else {
        context_class(data[data.len() - 1], contexts)
    };
    litlen[final_ctx][EOB_SYMBOL] += 1;
    (litlen, dist)
}

// ---------------------------------------------------------------------------
// Encoder
// ---------------------------------------------------------------------------

/// Encode `data` as a MODE_WEB container, or `None` when the mode does not
/// apply (empty input, or a block that would need a deeper distance alphabet
/// than the format allows).
///
/// The caller keeps the result only when it is strictly smaller than the
/// incumbent candidate, so this can never regress a file.
pub(crate) fn encode_web(data: &[u8]) -> Option<Vec<u8>> {
    if data.is_empty() {
        return None;
    }
    let (dist_base, dist_extra) = distance_tables();
    let mut best: Option<Vec<u8>> = None;
    for contexts in [1usize, 3] {
        let tokens = optimal_parse(data, contexts, &dist_base, &dist_extra);
        let candidate = emit_block(data, &tokens, contexts, &dist_base, &dist_extra)?;
        if best.as_ref().is_none_or(|b| candidate.len() < b.len()) {
            best = Some(candidate);
        }
    }
    best
}

fn emit_block(
    data: &[u8],
    tokens: &[Token],
    contexts: usize,
    dist_base: &[usize],
    dist_extra: &[u32],
) -> Option<Vec<u8>> {
    let (litlen_freqs, dist_freqs) = histograms(tokens, data, contexts, dist_base);
    let litlen_lengths: Vec<Vec<u8>> = litlen_freqs
        .iter()
        .map(|f| limited_code_lengths(f, MAX_CODE_LEN))
        .collect();
    let mut dist_lengths = limited_code_lengths(&dist_freqs, MAX_CODE_LEN);

    // A block with no matches still needs a one-symbol distance alphabet, so
    // the decoder's table build has something valid to read.
    if dist_lengths.iter().all(|&l| l == 0) {
        dist_lengths[0] = 1;
    }

    let hlit = trimmed_len(&litlen_lengths[0], 257).max(
        litlen_lengths
            .iter()
            .map(|l| trimmed_len(l, 257))
            .max()
            .unwrap_or(257),
    );
    let hdist = trimmed_len(&dist_lengths, 1);
    if hlit > LITLEN_ALPHABET || hdist > MAX_DIST_CODES {
        return None;
    }

    // Code-length sequence: every context table, then the distance table.
    let mut sequence: Vec<u8> = Vec::with_capacity(contexts * hlit + hdist);
    for lengths in &litlen_lengths {
        sequence.extend_from_slice(&lengths[..hlit]);
    }
    sequence.extend_from_slice(&dist_lengths[..hdist]);
    let rle = rle_code_lengths(&sequence);

    let mut cl_freqs = vec![0usize; CL_ALPHABET];
    for &(symbol, _, _) in &rle {
        cl_freqs[symbol] += 1;
    }
    let cl_lengths = limited_code_lengths(&cl_freqs, MAX_CL_CODE_LEN);
    let mut hclen = CL_ALPHABET;
    while hclen > 4 && cl_lengths[CL_ORDER[hclen - 1]] == 0 {
        hclen -= 1;
    }

    let cl_codes = crate::huffman::assign_canonical_codes(&cl_lengths);
    let litlen_codes: Vec<Vec<(u32, u8)>> = litlen_lengths
        .iter()
        .map(|l| crate::huffman::assign_canonical_codes(l))
        .collect();
    let dist_codes = crate::huffman::assign_canonical_codes(&dist_lengths);

    let mut writer = BitWriter::new(data.len() / 2 + 64);
    writer.write(1, 1); // BFINAL
    writer.write(if contexts == 1 { 1 } else { 2 }, 2); // BTYPE
    writer.write((hlit - 257) as u32, 5);
    writer.write((hdist - 1) as u32, 6);
    writer.write((hclen - 4) as u32, 4);
    for &symbol in CL_ORDER.iter().take(hclen) {
        writer.write(cl_lengths[symbol] as u32, 3);
    }
    for &(symbol, extra_bits, extra_value) in &rle {
        let (code, len) = cl_codes[symbol];
        writer.write(code, len as u32);
        if extra_bits > 0 {
            writer.write(extra_value, extra_bits);
        }
    }

    let mut pos = 0usize;
    for token in tokens {
        let ctx = if pos == 0 {
            context_class(b' ', contexts)
        } else {
            context_class(data[pos - 1], contexts)
        };
        if token.length == 0 {
            let (code, len) = litlen_codes[ctx][token.literal as usize];
            writer.write(code, len as u32);
            pos += 1;
        } else {
            let lc = length_code(token.length);
            let (code, len) = litlen_codes[ctx][EOB_SYMBOL + 1 + lc];
            writer.write(code, len as u32);
            if LENGTH_EXTRA[lc] > 0 {
                writer.write((token.length - LENGTH_BASE[lc]) as u32, LENGTH_EXTRA[lc]);
            }
            let dc = dist_code(dist_base, token.distance);
            let (code, len) = dist_codes[dc];
            writer.write(code, len as u32);
            if dist_extra[dc] > 0 {
                writer.write((token.distance - dist_base[dc]) as u32, dist_extra[dc]);
            }
            pos += token.length;
        }
    }
    let final_ctx = context_class(data[data.len() - 1], contexts);
    let (code, len) = litlen_codes[final_ctx][EOB_SYMBOL];
    writer.write(code, len as u32);

    let payload = writer.finish();
    let mut out = Vec::with_capacity(WEB_HEADER_SIZE + payload.len());
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.push(MODE_WEB);
    out.extend_from_slice(&(data.len() as u32).to_be_bytes());
    out.extend_from_slice(&checksum(data));
    out.extend_from_slice(&payload);
    Some(out)
}

fn trimmed_len(lengths: &[u8], minimum: usize) -> usize {
    let mut used = lengths.len();
    while used > minimum && lengths[used - 1] == 0 {
        used -= 1;
    }
    used
}

/// Four-byte content checksum: the leading bytes of the BLAKE3 digest already
/// used by the archive layer.
fn checksum(data: &[u8]) -> [u8; 4] {
    let digest = blake3::hash(data);
    let bytes = digest.as_bytes();
    [bytes[0], bytes[1], bytes[2], bytes[3]]
}

// ---------------------------------------------------------------------------
// Decoder
// ---------------------------------------------------------------------------

/// Decode a MODE_WEB container. Fail-closed on every malformed field: no
/// panic, no partial output, and a checksum mismatch is an error rather than a
/// silent corruption.
pub(crate) fn decode_web(blob: &[u8]) -> Result<Vec<u8>, CubrimError> {
    if blob.len() < WEB_HEADER_SIZE {
        return Err(CubrimError::Decode(format!(
            "MODE_WEB container too short: {} < {WEB_HEADER_SIZE}",
            blob.len()
        )));
    }
    let orig_len = u32::from_be_bytes([blob[6], blob[7], blob[8], blob[9]]) as usize;
    let expected_checksum = [blob[10], blob[11], blob[12], blob[13]];
    let (dist_base, dist_extra) = distance_tables();

    let mut reader = BitReader::new(&blob[WEB_HEADER_SIZE..]);
    let mut out: Vec<u8> = Vec::with_capacity(orig_len.min(1 << 20));

    loop {
        let final_block = reader.read(1)? == 1;
        let btype = reader.read(2)?;
        let contexts = match btype {
            1 => 1usize,
            2 => 3usize,
            other => {
                return Err(CubrimError::Decode(format!(
                    "MODE_WEB: unknown block type {other}"
                )))
            }
        };
        let hlit = reader.read(5)? as usize + 257;
        let hdist = reader.read(6)? as usize + 1;
        let hclen = reader.read(4)? as usize + 4;
        if hlit > LITLEN_ALPHABET || hdist > MAX_DIST_CODES || hclen > CL_ALPHABET {
            return Err(CubrimError::Decode(
                "MODE_WEB: alphabet size out of range".into(),
            ));
        }

        let mut cl_lengths = vec![0u8; CL_ALPHABET];
        for &symbol in CL_ORDER.iter().take(hclen) {
            cl_lengths[symbol] = reader.read(3)? as u8;
        }
        let cl_table = HuffTable::build_bounded(&cl_lengths, MAX_CL_CODE_LEN)
            .ok_or_else(|| CubrimError::Decode("MODE_WEB: invalid code-length table".into()))?;

        let wanted = contexts * hlit + hdist;
        let sequence = read_code_lengths(&mut reader, &cl_table, wanted)?;

        let mut tables = Vec::with_capacity(contexts);
        for ctx in 0..contexts {
            let lengths = &sequence[ctx * hlit..(ctx + 1) * hlit];
            tables.push(
                HuffTable::build_bounded(lengths, MAX_CODE_LEN).ok_or_else(|| {
                    CubrimError::Decode(format!(
                        "MODE_WEB: invalid literal/length table for context {ctx}"
                    ))
                })?,
            );
        }
        let dist_lengths = &sequence[contexts * hlit..];
        let dist_table = HuffTable::build_bounded(dist_lengths, MAX_CODE_LEN)
            .ok_or_else(|| CubrimError::Decode("MODE_WEB: invalid distance table".into()))?;

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
                    return Err(CubrimError::Decode(
                        "MODE_WEB: output longer than the declared length".into(),
                    ));
                }
                out.push(symbol as u8);
                continue;
            }
            let lc = symbol - EOB_SYMBOL - 1;
            if lc >= N_LENGTH_CODES {
                return Err(CubrimError::Decode(format!(
                    "MODE_WEB: length code {lc} out of range"
                )));
            }
            let length = LENGTH_BASE[lc] + reader.read(LENGTH_EXTRA[lc])? as usize;
            let dc = reader.read_symbol(&dist_table)?;
            if dc >= dist_base.len() {
                return Err(CubrimError::Decode(format!(
                    "MODE_WEB: distance code {dc} out of range"
                )));
            }
            let distance = dist_base[dc] + reader.read(dist_extra[dc])? as usize;
            if distance == 0 || distance > out.len() {
                return Err(CubrimError::Decode(format!(
                    "MODE_WEB: invalid distance {distance} (output length {})",
                    out.len()
                )));
            }
            if out.len() + length > orig_len {
                return Err(CubrimError::Decode(
                    "MODE_WEB: match overruns the declared length".into(),
                ));
            }
            let start = out.len() - distance;
            for k in 0..length {
                let byte = out[start + k];
                out.push(byte);
            }
        }

        if final_block {
            break;
        }
    }

    if out.len() != orig_len {
        return Err(CubrimError::Decode(format!(
            "MODE_WEB: decoded {} bytes but the header declares {orig_len}",
            out.len()
        )));
    }
    if checksum(&out) != expected_checksum {
        return Err(CubrimError::Decode(
            "MODE_WEB: checksum mismatch — refusing to return corrupt output".into(),
        ));
    }
    Ok(out)
}

fn read_code_lengths(
    reader: &mut BitReader,
    table: &HuffTable,
    wanted: usize,
) -> Result<Vec<u8>, CubrimError> {
    let mut lengths: Vec<u8> = Vec::with_capacity(wanted);
    while lengths.len() < wanted {
        let symbol = reader.read_symbol(table)?;
        match symbol {
            0..=15 => lengths.push(symbol as u8),
            16 => {
                let last = *lengths.last().ok_or_else(|| {
                    CubrimError::Decode("MODE_WEB: repeat-previous with no previous length".into())
                })?;
                let run = reader.read(2)? as usize + 3;
                if lengths.len() + run > wanted {
                    return Err(CubrimError::Decode(
                        "MODE_WEB: code-length repeat overruns the table".into(),
                    ));
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
                    return Err(CubrimError::Decode(
                        "MODE_WEB: zero-run overruns the table".into(),
                    ));
                }
                lengths.resize(lengths.len() + run, 0);
            }
            other => {
                return Err(CubrimError::Decode(format!(
                    "MODE_WEB: bad code-length symbol {other}"
                )))
            }
        }
    }
    Ok(lengths)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn round_trip(data: &[u8]) {
        let blob = encode_web(data).expect("web encode");
        assert_eq!(blob[5], MODE_WEB, "mode byte");
        let decoded = decode_web(&blob).expect("web decode");
        assert_eq!(decoded, data, "MODE_WEB round trip must be byte-exact");
    }

    #[test]
    fn round_trip_text() {
        round_trip(
            b"the quick brown fox jumps over the lazy dog "
                .repeat(50)
                .as_slice(),
        );
    }

    #[test]
    fn round_trip_json() {
        round_trip(
            br#"{"name":"alpha","value":1234,"tags":["x","y"]}"#
                .repeat(80)
                .as_slice(),
        );
    }

    #[test]
    fn round_trip_single_byte_repeated() {
        round_trip(&vec![b'A'; 5000]);
    }

    #[test]
    fn round_trip_all_byte_values() {
        let data: Vec<u8> = (0..=255u8).cycle().take(4096).collect();
        round_trip(&data);
    }

    #[test]
    fn round_trip_incompressible() {
        // Deterministic pseudo-random bytes: no matches, all literals.
        let mut state = 0x12345678u32;
        let data: Vec<u8> = (0..8192)
            .map(|_| {
                state = state.wrapping_mul(1_103_515_245).wrapping_add(12345);
                (state >> 16) as u8
            })
            .collect();
        round_trip(&data);
    }

    #[test]
    fn round_trip_short_inputs() {
        for len in 1..64usize {
            let data: Vec<u8> = (0..len).map(|i| (i % 7) as u8 + b'a').collect();
            round_trip(&data);
        }
    }

    #[test]
    fn empty_input_declines() {
        assert!(encode_web(b"").is_none());
    }

    #[test]
    fn truncated_container_fails_closed() {
        let data = b"abcabcabcabcabcabcabcabc".repeat(20);
        let blob = encode_web(&data).unwrap();
        for cut in [3usize, 10, WEB_HEADER_SIZE, blob.len() - 1] {
            assert!(
                decode_web(&blob[..cut]).is_err(),
                "truncation at {cut} must fail closed"
            );
        }
    }

    #[test]
    fn corrupt_payload_never_panics() {
        let data = b"the quick brown fox ".repeat(40);
        let blob = encode_web(&data).unwrap();
        for byte_index in WEB_HEADER_SIZE..blob.len().min(WEB_HEADER_SIZE + 48) {
            for mask in [0x01u8, 0x40, 0xFF] {
                let mut corrupt = blob.clone();
                corrupt[byte_index] ^= mask;
                // Either an error, or a decode that no longer matches — never a
                // panic, and never silent corruption presented as success.
                if let Ok(out) = decode_web(&corrupt) {
                    assert_eq!(out, data, "checksum must catch corruption");
                }
            }
        }
    }

    #[test]
    fn declared_length_mismatch_fails_closed() {
        let data = b"abcdefghij".repeat(50);
        let mut blob = encode_web(&data).unwrap();
        blob[9] = blob[9].wrapping_add(1);
        assert!(decode_web(&blob).is_err());
    }

    #[test]
    fn checksum_mismatch_fails_closed() {
        let data = b"abcdefghij".repeat(50);
        let mut blob = encode_web(&data).unwrap();
        blob[10] ^= 0xFF;
        assert!(decode_web(&blob).is_err());
    }

    #[test]
    fn code_lengths_respect_the_limit() {
        // Fibonacci frequencies force a deep unconstrained code.
        let mut freqs = vec![1usize, 1];
        while freqs.len() < 40 {
            let next = freqs[freqs.len() - 1] + freqs[freqs.len() - 2];
            freqs.push(next);
        }
        let lengths = limited_code_lengths(&freqs, MAX_CODE_LEN);
        assert!(lengths.iter().copied().max().unwrap() <= MAX_CODE_LEN);
        assert!(crate::huffman::kraft_ok(&lengths), "code must be complete");
    }

    #[test]
    fn code_lengths_are_complete_for_random_histograms() {
        let mut state = 0xC0FFEEu32;
        for _ in 0..40 {
            let n = 2 + (state as usize % 200);
            let freqs: Vec<usize> = (0..n)
                .map(|_| {
                    state = state.wrapping_mul(1_103_515_245).wrapping_add(12345);
                    ((state >> 16) % 500) as usize
                })
                .collect();
            let present = freqs.iter().filter(|&&f| f > 0).count();
            if present < 2 {
                continue;
            }
            let lengths = limited_code_lengths(&freqs, MAX_CODE_LEN);
            assert!(crate::huffman::kraft_ok(&lengths));
            for (i, &f) in freqs.iter().enumerate() {
                assert_eq!(lengths[i] > 0, f > 0, "presence must match");
            }
        }
    }

    #[test]
    fn rle_round_trips_code_lengths() {
        let cases: Vec<Vec<u8>> = vec![
            vec![0; 300],
            vec![5; 20],
            (0..50).map(|i| (i % 16) as u8).collect(),
            [vec![0; 140], vec![3; 9], vec![0; 5], vec![7; 1]].concat(),
        ];
        for case in cases {
            let mut rebuilt: Vec<u8> = Vec::new();
            for (symbol, _, extra) in rle_code_lengths(&case) {
                match symbol {
                    0..=15 => rebuilt.push(symbol as u8),
                    16 => {
                        let last = *rebuilt.last().unwrap();
                        rebuilt.resize(rebuilt.len() + (extra as usize + 3), last);
                    }
                    17 => rebuilt.resize(rebuilt.len() + (extra as usize + 3), 0),
                    _ => rebuilt.resize(rebuilt.len() + (extra as usize + 11), 0),
                }
            }
            assert_eq!(rebuilt, case);
        }
    }

    #[test]
    fn context_class_is_stable_and_bounded() {
        for byte in 0..=255u8 {
            assert_eq!(context_class(byte, 1), 0);
            assert!(context_class(byte, 3) < 3);
        }
        assert_eq!(context_class(b'7', 3), 2);
        assert_eq!(context_class(b'q', 3), 1);
        assert_eq!(context_class(b' ', 3), 0);
    }

    #[test]
    fn distance_alphabet_covers_a_whole_file_window() {
        let (base, extra) = distance_tables();
        let reach = base[base.len() - 1] + (1usize << extra[extra.len() - 1]) - 1;
        assert!(reach >= 1 << 24, "distance alphabet reach {reach}");
        for distance in [1usize, 2, 5, 1000, 32768, 65535, 320_975] {
            let code = dist_code(&base, distance);
            assert!(base[code] <= distance);
            assert!(distance < base[code] + (1usize << extra[code]));
        }
    }
}
