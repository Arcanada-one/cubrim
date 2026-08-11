// H-23: interleaved / SIMD-friendly rANS — THROUGHPUT-ONLY benchmark.
//
// Per CUBR-CONT-BRIEF.md hypothesis 4: rANS interleaving is a THROUGHPUT lever, not
// a ratio lever, and only worth it once ratio space is exhausted. This standalone
// benchmark (compiled with `rustc -O`, no crate changes) measures BOTH:
//   (1) output SIZE — single-stream vs N-way interleaved on the same order-0 model,
//       to confirm interleaving is ratio-neutral (+ (N-1)*4 bytes of extra state).
//   (2) encode/decode THROUGHPUT — to quantify the instruction-level-parallelism win
//       from N independent rANS states updated per round.
//
// The entropy model is identical to the production byte-rANS (RANS_L=1<<23, M=1<<12),
// so the size comparison is faithful. Round-trip is asserted for every variant.

use std::time::Instant;

const RANS_L: u32 = 1 << 23;
const SCALE_BITS: u32 = 12;
const M: u32 = 1 << SCALE_BITS;

fn normalize(counts: &[u32]) -> Vec<u32> {
    let total: u64 = counts.iter().map(|&c| c as u64).sum();
    let n = counts.len();
    let mut freq = vec![0u32; n];
    if total == 0 {
        return freq;
    }
    let mut allocated: u32 = 0;
    for (s, &c) in counts.iter().enumerate() {
        if c == 0 {
            continue;
        }
        let scaled = ((c as u64 * M as u64) + total / 2) / total;
        let f = scaled.max(1) as u32;
        freq[s] = f;
        allocated += f;
    }
    if allocated < M {
        let mx = (0..n).filter(|&s| freq[s] > 0).max_by_key(|&s| freq[s]).unwrap();
        freq[mx] += M - allocated;
    } else if allocated > M {
        let mut surplus = allocated - M;
        while surplus > 0 {
            let mx = (0..n).filter(|&s| freq[s] > 1).max_by_key(|&s| freq[s]).unwrap();
            let take = surplus.min(freq[mx] - 1);
            freq[mx] -= take;
            surplus -= take;
        }
    }
    freq
}

struct Tables {
    freq: Vec<u32>,
    cum: Vec<u32>,
    slot_to_sym: Vec<u16>,
}
fn build_tables(freq: Vec<u32>) -> Tables {
    let n = freq.len();
    let mut cum = vec![0u32; n + 1];
    for s in 0..n {
        cum[s + 1] = cum[s] + freq[s];
    }
    let mut slot_to_sym = vec![0u16; M as usize];
    for s in 0..n {
        for slot in cum[s]..cum[s + 1] {
            slot_to_sym[slot as usize] = s as u16;
        }
    }
    Tables { freq, cum: cum[..n].to_vec(), slot_to_sym }
}

// ── single-stream byte rANS (matches production) ─────────────────────────────
fn enc_single(syms: &[u16], t: &Tables) -> Vec<u8> {
    let n = syms.len();
    let mut buf = vec![0u8; 16 + 4 * n];
    let mut p = buf.len();
    let mut x: u32 = RANS_L;
    for i in (0..n).rev() {
        let s = syms[i] as usize;
        let f = t.freq[s];
        let c = t.cum[s];
        let x_max = ((RANS_L >> SCALE_BITS) << 8) * f;
        while x >= x_max {
            p -= 1;
            buf[p] = (x & 0xff) as u8;
            x >>= 8;
        }
        x = ((x / f) << SCALE_BITS) + (x % f) + c;
    }
    p -= 4;
    buf[p..p + 4].copy_from_slice(&x.to_le_bytes());
    buf[p..].to_vec()
}

fn dec_single(payload: &[u8], n: usize, t: &Tables) -> Vec<u16> {
    let mask = M - 1;
    let mut x = u32::from_le_bytes([payload[0], payload[1], payload[2], payload[3]]);
    let mut cur = 4usize;
    let mut out = vec![0u16; n];
    for o in out.iter_mut() {
        let slot = x & mask;
        let s = t.slot_to_sym[slot as usize];
        let f = t.freq[s as usize];
        let c = t.cum[s as usize];
        x = f * (x >> SCALE_BITS) + slot - c;
        while x < RANS_L {
            x = (x << 8) | payload[cur] as u32;
            cur += 1;
        }
        *o = s;
    }
    out
}

// ── N-way interleaved byte rANS (one shared byte stack, symbol i -> state i%N) ──
// Round-trips because the single LIFO buffer + per-symbol op order mirror exactly
// between encode-reverse and decode-forward, and the state index i%N is a pure
// function of i (identical on both sides). Throughput rises because the N state
// updates per round are register-independent → the CPU overlaps them (ILP/SIMD).
fn enc_interleaved<const NW: usize>(syms: &[u16], t: &Tables) -> Vec<u8> {
    let n = syms.len();
    let mut buf = vec![0u8; 16 * NW + 4 * n];
    let mut p = buf.len();
    let mut x = [RANS_L; NW];
    for i in (0..n).rev() {
        let lane = i % NW;
        let s = syms[i] as usize;
        let f = t.freq[s];
        let c = t.cum[s];
        let x_max = ((RANS_L >> SCALE_BITS) << 8) * f;
        let mut xi = x[lane];
        while xi >= x_max {
            p -= 1;
            buf[p] = (xi & 0xff) as u8;
            xi >>= 8;
        }
        x[lane] = ((xi / f) << SCALE_BITS) + (xi % f) + c;
    }
    // Flush states for lanes in REVERSE lane order so decode reads them in lane order.
    for lane in (0..NW).rev() {
        p -= 4;
        buf[p..p + 4].copy_from_slice(&x[lane].to_le_bytes());
    }
    buf[p..].to_vec()
}

fn dec_interleaved<const NW: usize>(payload: &[u8], n: usize, t: &Tables) -> Vec<u16> {
    let mask = M - 1;
    let mut x = [0u32; NW];
    let mut cur = 0usize;
    for lane in 0..NW {
        x[lane] = u32::from_le_bytes([
            payload[cur], payload[cur + 1], payload[cur + 2], payload[cur + 3],
        ]);
        cur += 4;
    }
    let mut out = vec![0u16; n];
    let mut i = 0usize;
    // Process NW symbols per round; the NW decodes are state-independent (ILP).
    while i + NW <= n {
        for lane in 0..NW {
            let xi = x[lane];
            let slot = xi & mask;
            let s = t.slot_to_sym[slot as usize];
            let f = t.freq[s as usize];
            let c = t.cum[s as usize];
            let mut nx = f * (xi >> SCALE_BITS) + slot - c;
            while nx < RANS_L {
                nx = (nx << 8) | payload[cur] as u32;
                cur += 1;
            }
            x[lane] = nx;
            out[i + lane] = s;
        }
        i += NW;
    }
    while i < n {
        let lane = i % NW;
        let xi = x[lane];
        let slot = xi & mask;
        let s = t.slot_to_sym[slot as usize];
        let f = t.freq[s as usize];
        let c = t.cum[s as usize];
        let mut nx = f * (xi >> SCALE_BITS) + slot - c;
        while nx < RANS_L {
            nx = (nx << 8) | payload[cur] as u32;
            cur += 1;
        }
        x[lane] = nx;
        out[i] = s;
        i += 1;
    }
    out
}

fn mbps(bytes: usize, secs: f64) -> f64 {
    (bytes as f64 / 1.0e6) / secs
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let path = args.get(1).cloned().unwrap_or_else(|| {
        "docs/ephemeral/research/corpus/block_bound_runs.bin".to_string()
    });
    let data = std::fs::read(&path).expect("read corpus file");
    // Symbols = raw bytes (order-0, 256 alphabet) — representative for throughput and
    // an exact size comparison; the entropy model is the production byte-rANS.
    let syms: Vec<u16> = data.iter().map(|&b| b as u16).collect();
    let n = syms.len();
    let mut counts = vec![0u32; 256];
    for &s in &syms {
        counts[s as usize] += 1;
    }
    let t = build_tables(normalize(&counts));

    // Correctness + size.
    let s1 = enc_single(&syms, &t);
    assert_eq!(dec_single(&s1, n, &t), syms, "single round-trip failed");
    let s2 = enc_interleaved::<2>(&syms, &t);
    assert_eq!(dec_interleaved::<2>(&s2, n, &t), syms, "2-way round-trip failed");
    let s4 = enc_interleaved::<4>(&syms, &t);
    assert_eq!(dec_interleaved::<4>(&s4, n, &t), syms, "4-way round-trip failed");

    println!("file: {path}  ({n} symbols)");
    println!("payload size: single={} 2way={} (+{}) 4way={} (+{})",
        s1.len(), s2.len(), s2.len() as i64 - s1.len() as i64,
        s4.len(), s4.len() as i64 - s1.len() as i64);

    // Throughput: repeat enough to total ≥ ~200 MB processed.
    let reps = (200_000_000 / n.max(1)).max(20);
    macro_rules! time_dec {
        ($name:expr, $f:expr, $payload:expr) => {{
            // warm-up
            let _ = $f($payload, n, &t);
            let t0 = Instant::now();
            let mut acc = 0u64;
            for _ in 0..reps {
                let o = $f($payload, n, &t);
                acc = acc.wrapping_add(o[o.len() - 1] as u64);
            }
            let dt = t0.elapsed().as_secs_f64();
            std::hint::black_box(acc);
            println!("decode {:7}: {:8.1} MB/s  ({:.3}s for {} reps)",
                $name, mbps(n * reps, dt), dt, reps);
            mbps(n * reps, dt)
        }};
    }
    macro_rules! time_enc {
        ($name:expr, $f:expr) => {{
            let _ = $f(&syms, &t);
            let t0 = Instant::now();
            let mut acc = 0u64;
            for _ in 0..reps {
                let o = $f(&syms, &t);
                acc = acc.wrapping_add(o[o.len() - 1] as u64);
            }
            let dt = t0.elapsed().as_secs_f64();
            std::hint::black_box(acc);
            println!("encode {:7}: {:8.1} MB/s  ({:.3}s for {} reps)",
                $name, mbps(n * reps, dt), dt, reps);
            mbps(n * reps, dt)
        }};
    }

    let de1 = time_dec!("single", dec_single, &s1);
    let de2 = time_dec!("2way", dec_interleaved::<2>, &s2);
    let de4 = time_dec!("4way", dec_interleaved::<4>, &s4);
    let _en1 = time_enc!("single", enc_single);
    let _en2 = time_enc!("2way", enc_interleaved::<2>);
    let _en4 = time_enc!("4way", enc_interleaved::<4>);

    println!("decode speedup: 2way={:.2}x  4way={:.2}x  (vs single)", de2 / de1, de4 / de1);
    println!("RATIO verdict: interleaving adds {} (2way) / {} (4way) bytes — ratio-neutral-to-negative.",
        s2.len() as i64 - s1.len() as i64, s4.len() as i64 - s1.len() as i64);
}
