//! GeoCM image codec — port of cubr2-geocm v13 (frozen tag research-final-v13 = 42118aa).
//! Detected native-axis (stride) neighbour + match-model contexts feeding an integer logistic
//! mixer + APM chain through a carryless binary range coder. Integer-deterministic, fail-closed
//! (self-describing CG2 container with an FNV-1a-64 checksum verified after decode),
//! competitive-min internally and wrapped as a MODE_GEOCM candidate. Second-wave port over v6.
#![allow(clippy::needless_range_loop, dead_code, clippy::too_many_arguments)]

// ==================== rc (carryless binary range coder) ====================
// Carryless binary range coder (LZMA-style), integer-only, deterministic.
// Probabilities are 12-bit (0..4096), p = P(bit == 1).

pub const PBITS: u32 = 12;
pub const PMAX: u16 = 1 << PBITS; // 4096
pub const PINIT: u16 = PMAX / 2;
const TOP: u32 = 1 << 24;
const RATE: u32 = 5;

#[inline]
pub fn update(p: &mut u16, bit: u8) {
    if bit == 1 {
        *p += (PMAX - *p) >> RATE;
    } else {
        *p -= *p >> RATE;
    }
}

pub struct RcEnc {
    low: u64,
    range: u32,
    cache: u8,
    cache_size: u64,
    pub out: Vec<u8>,
}

impl RcEnc {
    pub fn new() -> Self {
        RcEnc { low: 0, range: u32::MAX, cache: 0, cache_size: 1, out: Vec::new() }
    }

    #[inline]
    fn shift_low(&mut self) {
        if self.low < 0xFF00_0000 || self.low > 0xFFFF_FFFF {
            let carry = (self.low >> 32) as u8;
            self.out.push(self.cache.wrapping_add(carry));
            for _ in 1..self.cache_size {
                self.out.push(0xFFu8.wrapping_add(carry));
            }
            self.cache = (self.low >> 24) as u8;
            self.cache_size = 0;
        }
        self.cache_size += 1;
        self.low = (self.low & 0x00FF_FFFF) << 8;
    }

    #[inline]
    pub fn encode_bit(&mut self, p: u16, bit: u8) {
        let bound = (self.range >> PBITS) * p as u32;
        if bit == 1 {
            self.range = bound;
        } else {
            self.low += bound as u64;
            self.range -= bound;
        }
        while self.range < TOP {
            self.range <<= 8;
            self.shift_low();
        }
    }

    pub fn finish(mut self) -> Vec<u8> {
        for _ in 0..5 {
            self.shift_low();
        }
        self.out
    }
}

pub struct RcDec<'a> {
    range: u32,
    code: u32,
    buf: &'a [u8],
    pos: usize,
}

impl<'a> RcDec<'a> {
    /// Fail-closed: returns None if the stream is too short to prime.
    pub fn new(buf: &'a [u8]) -> Option<Self> {
        if buf.len() < 5 {
            return None;
        }
        let mut d = RcDec { range: u32::MAX, code: 0, buf, pos: 1 };
        for _ in 0..4 {
            d.code = (d.code << 8) | d.next_byte();
        }
        Some(d)
    }

    #[inline]
    /// Real input bytes consumed, saturating at the end of the coded stream. `next_byte`
    /// advances `pos` unconditionally while feeding zero-padding past the end, so an
    /// unclamped value would keep advancing forever and any stall guard built on it would
    /// be unfirable (the QA-F-001 defect, ported here as QA-F-008).
    #[inline]
    pub fn progress(&self) -> usize {
        self.pos.min(self.buf.len())
    }

    fn next_byte(&mut self) -> u32 {
        // Past-the-end reads pad with 0; corruption is caught by the
        // container checksum (fail-closed at the codec layer).
        let b = if self.pos < self.buf.len() { self.buf[self.pos] } else { 0 };
        self.pos += 1;
        b as u32
    }

    #[inline]
    pub fn decode_bit(&mut self, p: u16) -> u8 {
        let bound = (self.range >> PBITS) * p as u32;
        let bit;
        if self.code < bound {
            self.range = bound;
            bit = 1;
        } else {
            self.code -= bound;
            self.range -= bound;
            bit = 0;
        }
        while self.range < TOP {
            self.range <<= 8;
            self.code = (self.code << 8) | self.next_byte();
        }
        bit
    }
}

// ==================== mix (integer logistic mixer + APM) ====================
// Integer logistic mixing (lpaq/CM2 pattern).
//
// f64 is used ONLY to build the static stretch/squash tables once at startup
// (deterministic: same code -> same tables on every IEEE-754 platform, the
// same discipline as cubr-cm-poc cm2.rs). The per-bit predict/mix/update
// loop is integer-only, so encoder and decoder reconstruct identical state.


pub const STRETCH_MAX: i32 = 2047;

pub struct Tables {
    /// stretch[p] for p in 0..4096 -> [-STRETCH_MAX, STRETCH_MAX]
    pub stretch: Vec<i32>,
    /// squash[x + 2048] for x in [-2048, 2047] -> p in [1, 4095]
    pub squash: Vec<u16>,
}

impl Tables {
    pub fn new() -> Self {
        let mut squash = vec![0u16; 4096];
        for i in 0..4096usize {
            let x = (i as f64 - 2048.0) / 256.0;
            let p = 1.0 / (1.0 + (-x).exp());
            let v = (p * PMAX as f64) as i64;
            squash[i] = v.clamp(1, (PMAX - 1) as i64) as u16;
        }
        let mut stretch = vec![0i32; PMAX as usize];
        // invert squash monotonically
        let mut j = 0usize;
        for p in 0..PMAX as usize {
            while j < 4095 && (squash[j] as usize) < p {
                j += 1;
            }
            stretch[p] = j as i32 - 2048;
        }
        for p in 0..PMAX as usize {
            stretch[p] = stretch[p].clamp(-STRETCH_MAX, STRETCH_MAX);
        }
        Tables { stretch, squash }
    }

    #[inline]
    pub fn squash_i(&self, x: i32) -> u16 {
        let xi = x.clamp(-2048, 2047) + 2048;
        self.squash[xi as usize]
    }
}

/// One weight set per mixer context; NM model inputs.
pub struct Mixer {
    pub weights: Vec<i32>, // n_sets * nm, 16.16-ish fixed point
    nm: usize,
}

impl Mixer {
    pub fn new(n_sets: usize, nm: usize) -> Self {
        // start at ~0.3 weight each so the initial mix is a mild average
        Mixer { weights: vec![1 << 14; n_sets * nm], nm }
    }

    /// Returns (p12, dot) — caller passes stretched inputs st[0..nm].
    #[inline]
    pub fn predict(&self, tabs: &Tables, set: usize, st: &[i32]) -> (u16, i32) {
        let base = set * self.nm;
        let mut dot: i64 = 0;
        for (i, &s) in st.iter().enumerate() {
            dot += self.weights[base + i] as i64 * s as i64;
        }
        let x = (dot >> 16) as i32;
        (tabs.squash_i(x), x)
    }

    #[inline]
    pub fn update(&mut self, set: usize, st: &[i32], p: u16, bit: u8) {
        let err = ((bit as i32) << 12) - p as i32; // [-4095, 4095]
        let base = set * self.nm;
        for (i, &s) in st.iter().enumerate() {
            let w = &mut self.weights[base + i];
            *w += (s * err) >> 10;
            *w = (*w).clamp(-(1 << 20), 1 << 20);
        }
    }
}

/// Adaptive probability map (SSE): 33 interpolated buckets per context.
pub struct Apm {
    t: Vec<u16>,
    idx: usize,
    w: i32,
}

impl Apm {
    pub fn new(n_ctx: usize, tabs: &Tables) -> Self {
        let mut t = vec![0u16; n_ctx * 33];
        for c in 0..n_ctx {
            for j in 0..33 {
                t[c * 33 + j] = tabs.squash_i((j as i32 - 16) * 128);
            }
        }
        Apm { t, idx: 0, w: 0 }
    }

    #[inline]
    pub fn pp(&mut self, tabs: &Tables, p: u16, cx: usize) -> u16 {
        let st = tabs.stretch[p as usize] + 2048; // 0..4095
        let w = st & 127;
        let idx = cx * 33 + (st >> 7) as usize;
        self.idx = idx;
        self.w = w;
        (((self.t[idx] as i32) * (128 - w) + (self.t[idx + 1] as i32) * w) >> 7)
            .clamp(1, 4095) as u16
    }

    #[inline]
    pub fn update(&mut self, bit: u8) {
        let g = (bit as i32) << 12;
        let a = &mut self.t[self.idx];
        *a = (*a as i32 + ((g - *a as i32) >> 7)) as u16;
        let b = &mut self.t[self.idx + 1];
        *b = (*b as i32 + ((g - *b as i32) >> 7)) as u16;
    }
}

// ==================== geodetect ====================
// M0 — GeoDetect: deterministic integer detection of native axis strides.
// Byte-equality autocorrelation over a sampled window; ties break to the
// smaller stride. No floats, no RNG — same input always yields same output.

pub const MAX_STRIDE: usize = 8192;
const MAX_SAMPLES: usize = 1 << 18; // 262144 comparisons per stride

/// Top-k candidate strides (s >= 2), best (highest match count) first.
pub fn detect_strides(data: &[u8], k: usize) -> Vec<u32> {
    let n = data.len();
    if n < 16 {
        return Vec::new();
    }
    let max_s = MAX_STRIDE.min(n - 1);
    let mut scored: Vec<(u64, usize)> = Vec::with_capacity(max_s);
    for s in 2..=max_s {
        let avail = n - s;
        let step = (avail / MAX_SAMPLES).max(1);
        let mut eq: u64 = 0;
        let mut cnt: u64 = 0;
        let mut i = 0usize;
        while i < avail {
            if data[i] == data[i + s] {
                eq += 1;
            }
            cnt += 1;
            i += step;
        }
        // normalize to per-2^20 samples to compare across strides fairly
        let score = if cnt > 0 { eq * (1 << 20) / cnt } else { 0 };
        scored.push((score, s));
    }
    // sort by score desc, then stride asc (deterministic tie-break)
    scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    scored.into_iter().take(k).map(|(_, s)| s as u32).collect()
}

/// Second-axis (slice) stride: best multiple k*s1 (k >= 2) by sampled
/// byte-equality. Returns 0 when no meaningful second axis exists.
pub fn detect_slice_stride(data: &[u8], s1: usize) -> u32 {
    let n = data.len();
    if s1 < 2 || n < s1 * 8 {
        return 0;
    }
    let max_k = 4096usize.min((n - 1) / s1);
    if max_k < 2 {
        return 0;
    }
    let mut best_score: u64 = 0;
    let mut best_s: usize = 0;
    for k in 2..=max_k {
        let s = k * s1;
        let avail = n - s;
        let step = (avail / 65536).max(1);
        let mut eq: u64 = 0;
        let mut cnt: u64 = 0;
        let mut i = 0usize;
        while i < avail {
            if data[i] == data[i + s] {
                eq += 1;
            }
            cnt += 1;
            i += step;
        }
        let score = eq * (1 << 20) / cnt.max(1);
        if score > best_score {
            best_score = score;
            best_s = s;
        }
    }
    best_s as u32
}

// ==================== match_model ====================
// Match model (LZ-style) as a mixer input: hash of the last MM_ORDER bytes
// points at the previous occurrence; while the match holds, the next byte's
// bits are predicted with a confidence learned per match-length bucket.
// Integer-only; encoder and decoder run the identical causal state machine
// over the already-decoded history, so no positions are ever transmitted
// (BWT-class escape from the Gotcha-#7 map tax: the "coordinate" is derived,
// not stored).


pub const MM_HBITS: u32 = 20;
pub const MM_ORDER: usize = 6;

pub struct MatchModel {
    ht: Vec<u32>,
    ptr: usize,
    len: u32,
    probs: [u16; 128], // [len_bucket 0..63][predicted bit]
    pred: u8,
    valid: bool,
    bucket: usize,
    pb: u8,
    idx: usize,
    active_bit: bool,
}

impl MatchModel {
    pub fn new() -> Self {
        MatchModel {
            ht: vec![0; 1 << MM_HBITS],
            ptr: 0,
            len: 0,
            probs: [PINIT; 128],
            pred: 0,
            valid: false,
            bucket: 0,
            pb: 0,
            idx: 0,
            active_bit: false,
        }
    }

    #[inline]
    fn hash_at(hist: &[u8], pos: usize) -> usize {
        let mut h: u32 = 0x811c_9dc5;
        for k in (pos - MM_ORDER)..pos {
            h = (h ^ hist[k] as u32).wrapping_mul(16_777_619);
        }
        (h >> (32 - MM_HBITS)) as usize
    }

    pub fn byte_start(&mut self, hist: &[u8], i: usize) {
        if self.len == 0 && i >= MM_ORDER {
            let j = self.ht[Self::hash_at(hist, i)] as usize;
            if j > 0 && j < i {
                self.ptr = j;
                self.len = 1;
            }
        }
        if self.len > 0 {
            self.pred = hist[self.ptr];
            self.valid = true;
            self.bucket = self.len.min(63) as usize;
        } else {
            self.valid = false;
        }
    }

    /// Stretched prediction for bit k of the current byte (0 = neutral).
    #[inline]
    pub fn bit_pred(&mut self, tabs: &Tables, k: u32) -> i32 {
        if !self.valid || self.len == 0 {
            self.active_bit = false;
            return 0;
        }
        self.pb = (self.pred >> k) & 1;
        self.idx = self.bucket * 2 + self.pb as usize;
        let pc = self.probs[self.idx]; // P(actual bit == predicted bit)
        let p1: u16 = if self.pb == 1 { pc } else { PMAX - pc };
        self.active_bit = true;
        tabs.stretch[p1.clamp(1, (PMAX - 1) as u16) as usize]
    }

    #[inline]
    pub fn bit_update(&mut self, bit: u8) {
        if !self.active_bit {
            return;
        }
        let hit = (bit == self.pb) as u8;
        update(&mut self.probs[self.idx], hit);
        if hit == 0 {
            self.valid = false;
        }
    }

    /// `hist` must already include byte `i`.
    pub fn byte_end(&mut self, hist: &[u8], i: usize) {
        if self.len > 0 {
            if hist[i] == self.pred {
                self.len += 1;
                self.ptr += 1;
            } else {
                self.len = 0;
            }
        }
        let pos = i + 1;
        if pos >= MM_ORDER {
            self.ht[Self::hash_at(hist, pos)] = pos as u32;
        }
    }
}

// ==================== codec ====================
// M1 — GeoCM(image2d) MVP codec.
//
// Container (fixed 25-byte header):
//   magic  "CG2" + version 0x01          (4 B)
//   mode   u8: 0=RAW, 1=GEO, 2=O1        (1 B)
//   orig_len u64 LE                      (8 B)
//   fnv64 of original data, u64 LE       (8 B)
//   stride u32 LE (0 unless mode=GEO)    (4 B)
// payload follows.
//
// Invariants: lossless byte-exact round-trip; fail-closed decode (magic,
// version, bounds, and FNV-1a 64 checksum verified after decode); integer
// determinism (no floats anywhere); raw fallback bounds expansion to
// HEADER_LEN bytes. Encoder is competitive-min over {RAW, O1, GEO(top
// strides)} — picking a candidate never makes output worse than raw.
//
// Models (bitwise, one 12-bit adaptive probability per node):
//   O1 : ctx = prev byte                          (256 * 256 nodes)
//   GEO: ctx = above byte (t-S) * 16 + prev>>4    (4096 * 256 nodes)
// The GEO context is the X1-probe winner (see cubr-cubecore-research,
// x-experiment-verdict.md): real-adaptive KT cost 0.552 bpb on ptt5 vs
// champion 0.754 bpb.


// QA-F-008 fail-closed decode guards (branch F adversarial-QA, release-candidate audit).
// `orig_len` comes straight from the container header and sizes BOTH the output vector and
// the decode loop, with the FNV-1a-64 checksum verified only AFTER the full decode — so a
// 68-byte blob claiming 5e9 drove a 5 GB allocation and aborted instead of returning Err.
// A real coded stream of `payload_len` bytes cannot expand past a bounded factor.
//
// Calibrated by measurement (geocm_encoder_output_satisfies_expansion_bound pins it): worst
// real GeoCM ratios are all-zeros / short-period repeats — zeros 64K 1928x, zeros 1M 2752x,
// rep2 1M 2400x, const 1M 1362x, gradient 464x, strided 178x. 10000x is a >3.6x margin over
// the measured worst, so no legitimate high-ratio image is rejected.
pub const GEO_MAX_EXPANSION: u64 = 10_000;
/// Additive slack for short streams (model still warming up) and the minimal-blob edge.
pub const GEO_EXPANSION_SLACK: u64 = 1 << 16;
/// Output bytes produced without the range decoder consuming a new real input byte. Bounds
/// fabricated output from a truncated stream before it fails closed.
pub const GEO_STALL_LIMIT: usize = 1 << 16;
/// Pre-allocation ceiling: `with_capacity` is a hint, so capping it cannot change output —
/// it only stops an unvalidated header length from reserving gigabytes up front.
pub const GEO_PREALLOC_CAP: usize = 1 << 20;

pub const MAGIC: [u8; 4] = *b"CG2\x07";
pub const HEADER_LEN: usize = 30;
pub const MODE_RAW: u8 = 0;
pub const MODE_GEO: u8 = 1;
pub const MODE_O1: u8 = 2;
pub const MODE_GEOA: u8 = 3;
pub const MODE_MIX: u8 = 4;

#[derive(Debug, PartialEq, Eq)]
pub enum CodecError {
    BadMagic,
    Truncated,
    BadMode(u8),
    ChecksumMismatch,
    BadStride,
    /// Declared output length is implausible for the coded payload, or the coded stream ran
    /// out before that many bytes could be produced (QA-F-008 fail-closed).
    ImplausibleLength,
}

pub fn fnv64(data: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in data {
        h ^= b as u64;
        h = h.wrapping_mul(0x1000_0000_01b3);
    }
    h
}

fn header(mode: u8, orig_len: u64, check: u64, stride: u32, cfg: u8, stride2: u32) -> Vec<u8> {
    let mut h = Vec::with_capacity(HEADER_LEN);
    h.extend_from_slice(&MAGIC);
    h.push(mode);
    h.extend_from_slice(&orig_len.to_le_bytes());
    h.extend_from_slice(&check.to_le_bytes());
    h.extend_from_slice(&stride.to_le_bytes());
    h.push(cfg);
    h.extend_from_slice(&stride2.to_le_bytes());
    h
}

/// Encode `data` bytewise: 8 bits per byte through a per-context node tree.
/// `ctx_of(i)` must be pure and depend only on already-decoded bytes.
fn encode_stream<F: Fn(&[u8], usize) -> usize>(
    data: &[u8],
    n_ctx: usize,
    ctx_of: F,
) -> Vec<u8> {
    let mut probs = vec![PINIT; n_ctx * 256];
    let mut enc = RcEnc::new();
    for i in 0..data.len() {
        let g = ctx_of(data, i);
        debug_assert!(g < n_ctx);
        let base = g * 256;
        let x = data[i];
        let mut node: usize = 1;
        for k in (0..8).rev() {
            let bit = (x >> k) & 1;
            let p = &mut probs[base + node];
            enc.encode_bit(*p, bit);
            update(p, bit);
            node = (node << 1) | bit as usize;
        }
    }
    enc.finish()
}

fn decode_stream<F: Fn(&[u8], usize) -> usize>(
    payload: &[u8],
    orig_len: usize,
    n_ctx: usize,
    ctx_of: F,
) -> Result<Vec<u8>, CodecError> {
    let mut probs = vec![PINIT; n_ctx * 256];
    let mut dec = RcDec::new(payload).ok_or(CodecError::Truncated)?;
    let mut out: Vec<u8> = Vec::with_capacity(orig_len.min(GEO_PREALLOC_CAP));
    let mut last_progress = dec.progress();
    let mut stall = 0usize;
    for i in 0..orig_len {
        // QA-F-008 stall guard: once the real payload is exhausted the decoder only reads
        // zero-padding, so further output is fabricated. Fail closed instead of running to
        // the declared length.
        let pr = dec.progress();
        if pr != last_progress {
            last_progress = pr;
            stall = 0;
        } else {
            stall += 1;
            if stall > GEO_STALL_LIMIT {
                return Err(CodecError::ImplausibleLength);
            }
        }
        let g = ctx_of(&out, i);
        debug_assert!(g < n_ctx);
        let base = g * 256;
        let mut node: usize = 1;
        for _ in 0..8 {
            let p = &mut probs[base + node];
            let bit = dec.decode_bit(*p);
            update(p, bit);
            node = (node << 1) | bit as usize;
        }
        out.push((node & 0xFF) as u8);
    }
    Ok(out)
}

#[inline]
fn ctx_o1(hist: &[u8], i: usize) -> usize {
    if i == 0 { 0 } else { hist[i - 1] as usize }
}

#[inline]
fn ctx_geoa(hist: &[u8], i: usize, s: usize) -> usize {
    if i >= s { hist[i - s] as usize } else { 0 }
}

#[inline]
fn ctx_geo(hist: &[u8], i: usize, s: usize) -> usize {
    let above = if i >= s { hist[i - s] as usize } else { 0 };
    let prev = if i > 0 { hist[i - 1] as usize } else { 0 };
    above * 16 + (prev >> 4)
}


// ---------------- MODE_MIX: logistic mixing of 6 geo/1D models ----------------

const NTAB: usize = 10;
const NM: usize = NTAB + 1; // + match model input
const MIX_NCTX: [usize; NTAB] =
    [256, 256, 256, 4096, 256, 256, 65536, 65536, 256, 4096];

#[inline]
fn med_u8(a: i32, b: i32, c: i32) -> usize {
    (a + b - c).clamp(0, 255) as usize
}

/// Contexts for the 6 mixed models; depends only on already-decoded bytes.
#[inline]
fn mix_ctxs(hist: &[u8], i: usize, s: usize, s2: usize, ctx: &mut [usize; NTAB]) {
    let prev = if i > 0 { hist[i - 1] as i32 } else { 0 };
    let t2 = if i > 1 { hist[i - 2] as i32 } else { 0 };
    let ab = if i >= s { hist[i - s] as i32 } else { 0 };
    let ab1 = if i >= s + 1 { hist[i - s - 1] as i32 } else { 0 };
    let ab2 = if i >= s + 2 { hist[i - s - 2] as i32 } else { 0 };
    ctx[0] = prev as usize;
    ctx[1] = t2 as usize;
    ctx[2] = ab as usize;
    ctx[3] = (ab as usize) * 16 + ((prev as usize) >> 4);
    ctx[4] = med_u8(prev, ab, ab1);
    ctx[5] = med_u8(t2, ab, ab2);
    ctx[6] = (prev as usize) * 256 + t2 as usize;
    ctx[7] = (ab as usize) * 256 + t2 as usize;
    ctx[8] = if s2 > 0 && i >= s2 { hist[i - s2] as usize } else { 0 };
    ctx[9] = (i % s).min(4095); // offset-in-record (RECORDCM mo analogue)
}

struct MixState {
    tabs: Tables,
    probs: Vec<Vec<u16>>,
    mixer: Mixer,
    apm: Apm,
    apm2: Apm,
    apm3: Apm, // per-offset SSE (record classes, cfg&4)
    mm: MatchModel,
}

impl MixState {
    fn new(cfg: u8) -> Self {
        let _ = cfg;
        let tabs = Tables::new();
        let apm = Apm::new(256, &tabs);
        let apm2 = Apm::new(256, &tabs);
        let apm3 = Apm::new(256, &tabs);
        MixState {
            tabs,
            probs: MIX_NCTX.iter().map(|&n| vec![PINIT; n * 256]).collect(),
            mixer: Mixer::new(1024, NM),
            apm,
            apm2,
            apm3,
            mm: MatchModel::new(),
        }
    }
}

fn encode_stream_mix(data: &[u8], s: usize, s2: usize, cfg: u8) -> Vec<u8> {
    let mut st = MixState::new(cfg);
    let mut enc = RcEnc::new();
    let mut ctx = [0usize; NTAB];
    let mut stv = [0i32; NM];
    for i in 0..data.len() {
        mix_ctxs(data, i, s, s2, &mut ctx);
        st.mm.byte_start(data, i);
        let x = data[i];
        let mut node: usize = 1;
        for k in (0..8).rev() {
            let bit = (x >> k) & 1;
            for m in 0..NTAB {
                let pm = st.probs[m][ctx[m] * 256 + node];
                stv[m] = st.tabs.stretch[pm as usize];
            }
            stv[NTAB] = st.mm.bit_pred(&st.tabs, k);
            let set = if cfg & 4 != 0 {
                node + (((i % s) & 3) << 8)
            } else if cfg & 1 != 0 {
                node + ((i & 1) << 8)
            } else {
                node
            };
            let (p, _) = st.mixer.predict(&st.tabs, set, &stv);
            let pa = st.apm.pp(&st.tabs, p, ctx[0]);
            let pf1 = (((p as u32) + 3 * (pa as u32)) >> 2).clamp(1, 4095) as u16;
            let pf = if cfg & 2 != 0 {
                let pa2 = st.apm2.pp(&st.tabs, pf1, ctx[2]);
                (((pf1 as u32) + 3 * (pa2 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf1
            };
            let pf = if cfg & 8 != 0 {
                let pa3 = st.apm3.pp(&st.tabs, pf, (i % s).min(255));
                (((pf as u32) + 3 * (pa3 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf
            };
            enc.encode_bit(pf, bit);
            st.apm.update(bit);
            if cfg & 2 != 0 {
                st.apm2.update(bit);
            }
            if cfg & 8 != 0 {
                st.apm3.update(bit);
            }
            st.mm.bit_update(bit);
            st.mixer.update(set, &stv, p, bit);
            for m in 0..NTAB {
                update(&mut st.probs[m][ctx[m] * 256 + node], bit);
            }
            node = (node << 1) | bit as usize;
        }
        st.mm.byte_end(data, i);
    }
    enc.finish()
}

fn decode_stream_mix(
    payload: &[u8],
    orig_len: usize,
    s: usize,
    s2: usize,
    cfg: u8,
) -> Result<Vec<u8>, CodecError> {
    let mut st = MixState::new(cfg);
    let mut dec = RcDec::new(payload).ok_or(CodecError::Truncated)?;
    let mut out: Vec<u8> = Vec::with_capacity(orig_len.min(GEO_PREALLOC_CAP));
    let mut ctx = [0usize; NTAB];
    let mut stv = [0i32; NM];
    let mut last_progress = dec.progress();
    let mut stall = 0usize;
    for i in 0..orig_len {
        // QA-F-008 stall guard (see decode_stream).
        let pr = dec.progress();
        if pr != last_progress {
            last_progress = pr;
            stall = 0;
        } else {
            stall += 1;
            if stall > GEO_STALL_LIMIT {
                return Err(CodecError::ImplausibleLength);
            }
        }
        mix_ctxs(&out, i, s, s2, &mut ctx);
        st.mm.byte_start(&out, i);
        let mut node: usize = 1;
        for k in (0..8u32).rev() {
            for m in 0..NTAB {
                let pm = st.probs[m][ctx[m] * 256 + node];
                stv[m] = st.tabs.stretch[pm as usize];
            }
            stv[NTAB] = st.mm.bit_pred(&st.tabs, k);
            let set = if cfg & 4 != 0 {
                node + (((i % s) & 3) << 8)
            } else if cfg & 1 != 0 {
                node + ((i & 1) << 8)
            } else {
                node
            };
            let (p, _) = st.mixer.predict(&st.tabs, set, &stv);
            let pa = st.apm.pp(&st.tabs, p, ctx[0]);
            let pf1 = (((p as u32) + 3 * (pa as u32)) >> 2).clamp(1, 4095) as u16;
            let pf = if cfg & 2 != 0 {
                let pa2 = st.apm2.pp(&st.tabs, pf1, ctx[2]);
                (((pf1 as u32) + 3 * (pa2 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf1
            };
            let pf = if cfg & 8 != 0 {
                let pa3 = st.apm3.pp(&st.tabs, pf, (i % s).min(255));
                (((pf as u32) + 3 * (pa3 as u32)) >> 2).clamp(1, 4095) as u16
            } else {
                pf
            };
            let bit = dec.decode_bit(pf);
            st.apm.update(bit);
            if cfg & 2 != 0 {
                st.apm2.update(bit);
            }
            if cfg & 8 != 0 {
                st.apm3.update(bit);
            }
            st.mm.bit_update(bit);
            st.mixer.update(set, &stv, p, bit);
            for m in 0..NTAB {
                update(&mut st.probs[m][ctx[m] * 256 + node], bit);
            }
            node = (node << 1) | bit as usize;
        }
        out.push((node & 0xFF) as u8);
        st.mm.byte_end(&out, i);
    }
    Ok(out)
}


fn run_candidate(data: &[u8], mode: u8, s: u32, s2: u32, cfg: u8) -> Vec<u8> {
    let su = s as usize;
    match mode {
        MODE_O1 => encode_stream(data, 256, |h, i| ctx_o1(h, i)),
        MODE_GEO => encode_stream(data, 4096, |h, i| ctx_geo(h, i, su)),
        MODE_GEOA => encode_stream(data, 256, |h, i| ctx_geoa(h, i, su)),
        MODE_MIX => encode_stream_mix(data, su, s2 as usize, cfg),
        _ => unreachable!("run_candidate: raw is not a coded candidate"),
    }
}

pub fn encode(data: &[u8]) -> Vec<u8> {
    let check = fnv64(data);
    let n = data.len() as u64;
    // candidate: RAW (always available)
    let mut best_mode = MODE_RAW;
    let mut best_stride: u32 = 0;
    let mut best_cfg: u8 = 0;
    let mut best_stride2: u32 = 0;
    let mut best_payload: Vec<u8> = data.to_vec();

    if !data.is_empty() {
        // Candidate plan: (mode, stride, stride2, cfg)
        let mut plan: Vec<(u8, u32, u32, u8)> = vec![(MODE_O1, 0, 0, 0)];
        let top = detect_strides(data, 3);
        for (rank, &s) in top.iter().enumerate() {
            let su = s as usize;
            if su < 2 || su >= data.len() {
                continue;
            }
            plan.push((MODE_GEO, s, 0, 0));
            plan.push((MODE_GEOA, s, 0, 0));
            if rank < 2 {
                let s2 = detect_slice_stride(data, su);
                for cfg in [0u8, 3u8, 4u8, 12u8] {
                    plan.push((MODE_MIX, s, s2, cfg));
                }
            }
        }
        // I3 prefix pruning: rank candidates on a 1 MiB prefix, keep only
        // those within 5% of the prefix winner (always >= 1 survivor).
        const PREFIX: usize = 1 << 20;
        if data.len() > PREFIX * 2 && plan.len() > 2 {
            let pre = &data[..PREFIX];
            let mut costs: Vec<(usize, usize)> = std::thread::scope(|scope| {
                let handles: Vec<_> = plan
                    .iter()
                    .enumerate()
                    .map(|(idx, &(mode, s, s2, cfg))| {
                        scope.spawn(move || {
                            (run_candidate(pre, mode, s, s2, cfg).len(), idx)
                        })
                    })
                    .collect();
                handles.into_iter().map(|h| h.join().unwrap()).collect()
            });
            let best_pc = costs.iter().map(|&(c, _)| c).min().unwrap();
            let cut = best_pc + best_pc / 20; // +5%
            costs.retain(|&(c, _)| c <= cut);
            costs.sort_by_key(|&(c, i)| (c, i));
            let keep: Vec<usize> = costs.iter().map(|&(_, i)| i).collect();
            plan = keep.iter().map(|&i| plan[i]).collect();
        }
        // full passes for survivors in parallel; deterministic selection by
        // (payload_len, plan_index) regardless of thread completion order
        let results: Vec<(usize, Vec<u8>)> = std::thread::scope(|scope| {
            let handles: Vec<_> = plan
                .iter()
                .enumerate()
                .map(|(idx, &(mode, s, s2, cfg))| {
                    scope.spawn(move || (idx, run_candidate(data, mode, s, s2, cfg)))
                })
                .collect();
            handles.into_iter().map(|h| h.join().unwrap()).collect()
        });
        let mut ranked: Vec<&(usize, Vec<u8>)> = results.iter().collect();
        ranked.sort_by_key(|(idx, payload)| (payload.len(), *idx));
        if let Some((idx, payload)) = ranked.first() {
            if payload.len() < best_payload.len() {
                let (mode, s, s2, cfg) = plan[*idx];
                best_mode = mode;
                best_stride = s;
                best_stride2 = s2;
                best_cfg = cfg;
                best_payload = payload.clone();
            }
        }
    }
    let mut out = header(best_mode, n, check, best_stride, best_cfg, best_stride2);
    out.extend_from_slice(&best_payload);
    out
}

pub fn decode(blob: &[u8]) -> Result<Vec<u8>, CodecError> {
    if blob.len() < HEADER_LEN {
        return Err(CodecError::Truncated);
    }
    if blob[0..4] != MAGIC {
        return Err(CodecError::BadMagic);
    }
    let mode = blob[4];
    let orig_len = u64::from_le_bytes(blob[5..13].try_into().unwrap()) as usize;
    let check = u64::from_le_bytes(blob[13..21].try_into().unwrap());
    let stride = u32::from_le_bytes(blob[21..25].try_into().unwrap()) as usize;
    let cfg = blob[25];
    let stride2 = u32::from_le_bytes(blob[26..30].try_into().unwrap()) as usize;
    let payload = &blob[HEADER_LEN..];

    // QA-F-008 expansion bound — MUST precede every dispatch below, since each CM path sizes
    // its output vector and its loop from `orig_len` while the checksum is only verified at
    // the very end. Anything the payload cannot plausibly expand into is rejected in O(1).
    let max_plausible = (payload.len() as u64)
        .saturating_mul(GEO_MAX_EXPANSION)
        .saturating_add(GEO_EXPANSION_SLACK);
    if orig_len as u64 > max_plausible {
        return Err(CodecError::ImplausibleLength);
    }

    let out = match mode {
        MODE_RAW => {
            if payload.len() != orig_len {
                return Err(CodecError::Truncated);
            }
            payload.to_vec()
        }
        MODE_O1 => {
            if orig_len == 0 {
                Vec::new()
            } else {
                decode_stream(payload, orig_len, 256, |h, i| ctx_o1(h, i))?
            }
        }
        MODE_GEO => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            decode_stream(payload, orig_len, 4096, |h, i| ctx_geo(h, i, stride))?
        }
        MODE_GEOA => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            decode_stream(payload, orig_len, 256, |h, i| ctx_geoa(h, i, stride))?
        }
        MODE_MIX => {
            if stride < 2 || stride >= orig_len {
                return Err(CodecError::BadStride);
            }
            if stride2 != 0 && (stride2 < 2 || stride2 >= orig_len) {
                return Err(CodecError::BadStride);
            }
            decode_stream_mix(payload, orig_len, stride, stride2, cfg)?
        }
        m => return Err(CodecError::BadMode(m)),
    };
    if fnv64(&out) != check {
        return Err(CodecError::ChecksumMismatch);
    }
    Ok(out)
}

// ==================== shipped-rail gate ====================

/// Performance gate for the shipped competitive-min: run GeoCM only on image-like inputs
/// (a strongly periodic native byte-axis, bounded size). Correctness never depends on this —
/// competitive-min discards GeoCM whenever it is not strictly smaller.
pub fn should_try(data: &[u8]) -> bool {
    let n = data.len();
    if n < 8192 || n > 12_000_000 {
        return false;
    }
    let max_s = MAX_STRIDE.min(n - 1);
    if max_s < 2 {
        return false;
    }
    const MAX_SAMPLES: usize = 1 << 16;
    let mut scores: Vec<u64> = Vec::with_capacity(max_s);
    for s in 2..=max_s {
        let avail = n - s;
        let step = (avail / MAX_SAMPLES).max(1);
        let (mut eq, mut cnt, mut i) = (0u64, 0u64, 0usize);
        while i < avail {
            if data[i] == data[i + s] {
                eq += 1;
            }
            cnt += 1;
            i += step;
        }
        scores.push(if cnt > 0 { eq * (1 << 20) / cnt } else { 0 });
    }
    let best = *scores.iter().max().unwrap_or(&0);
    best >= (1u64 << 20) * 15 / 100
}

#[cfg(test)]
mod qaf_probe {
    use super::*;
    #[test]
    #[ignore]
    fn geocm_expansion_ratio_probe() {
        let cases: Vec<(&str, Vec<u8>)> = vec![
            ("zeros_64k", vec![0u8; 65536]),
            ("zeros_1M", vec![0u8; 1 << 20]),
            ("const_1M", vec![0x5Au8; 1 << 20]),
            ("rep2_1M", (0..(1 << 20)).map(|i| (i % 2) as u8).collect()),
            ("stride512_1M", (0..(1 << 20)).map(|i| ((i / 512) % 256) as u8).collect()),
            ("grad_1M", (0..(1 << 20)).map(|i| (i % 256) as u8).collect()),
        ];
        let mut worst = 0f64;
        for (name, data) in cases {
            let blob = encode(&data);
            let payload = blob.len().saturating_sub(HEADER_LEN).max(1);
            let ratio = data.len() as f64 / payload as f64;
            if ratio > worst { worst = ratio; }
            println!("GEO-RATIO {name}: orig={} payload={} ratio={:.1} mode={}",
                     data.len(), payload, ratio, blob[4]);
        }
        println!("GEO-RATIO WORST={worst:.1}");
    }
}
