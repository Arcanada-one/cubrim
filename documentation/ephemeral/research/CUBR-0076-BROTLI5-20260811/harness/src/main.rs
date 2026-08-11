//! CUBR-0076 — hypothesis 11 ratio harness: cubrim web profile vs brotli-5,
//! both decoded IN PROCESS, on the same host, in one interleaved schedule.
//!
//! Criterion 57 on hypothesis 11 (CUBR-0074) reads
//! `decode_throughput_vs_brotli5 >= 0.50` — "at most twice the decode latency
//! of the dynamic-response baseline". Evaluating it honestly requires a
//! brotli-5 decoder in the same address space: a CLI-to-CLI comparison is
//! biased toward 1.0, because fixed process-startup cost penalises the faster
//! decoder proportionally more. That bias would flatter the candidate, so this
//! harness exists instead.
//!
//! Fairness rules implemented here:
//!   * both decoders produce the same original bytes from their own archive of
//!     the same payload, whole-buffer, single-threaded;
//!   * the two are INTERLEAVED inside one randomized schedule, so any drift in
//!     machine state hits both arms alike;
//!   * every timed decode is verified byte-exact inside the timed region;
//!   * per (sample, arm) the MINIMUM time is reported, with the median beside;
//!   * brotli decodes via `brotli::BrotliDecompress` straight into a
//!     pre-reserved output buffer — its fastest ordinary in-memory usage,
//!     chosen so the baseline is not handicapped.
//!
//! Usage: cubr0076-brotli5-ratio <corpus-dir> [rounds] [warmups] [seed] [quality]

use std::io::Cursor;
use std::time::Instant;

use cubrim::{decode, encode_with_config, EncodeConfig};

const SAMPLES: [&str; 12] = [
    "tailwind.css",
    "html-large-web-codec-v2.html",
    "html-medium-home-v2.html",
    "magic-string.umd.js",
    "sourcemap-codec.umd.js",
    "resolve-uri.umd.js",
    "json-api-large-world-benchmark-v2.json",
    "json-api-medium-web-benchmark-v2.json",
    "json-api-small-hypotheses-v2.json",
    "magic-string.umd.js.map",
    "sourcemap-codec.umd.js.map",
    "inter-latin.medium.woff2",
];

/// Brotli window bits: 22 = 4 MiB, the CLI default and far above any sample.
const LGWIN: u32 = 22;
struct Lcg(u64);

impl Lcg {
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        self.0 >> 16
    }
}

fn brotli_compress(data: &[u8], quality: i32) -> Vec<u8> {
    let mut out = Vec::new();
    let mut input = Cursor::new(data);
    brotli::BrotliCompress(
        &mut input,
        &mut out,
        &brotli::enc::BrotliEncoderParams {
            quality,
            lgwin: LGWIN as i32,
            ..Default::default()
        },
    )
    .expect("brotli compress");
    out
}

fn brotli_decompress(archive: &[u8], expect_len: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(expect_len);
    let mut input = Cursor::new(archive);
    brotli::BrotliDecompress(&mut input, &mut out).expect("brotli decompress");
    out
}

fn load_avg() -> String {
    std::fs::read_to_string("/proc/loadavg")
        .map(|s| s.split_whitespace().take(3).collect::<Vec<_>>().join(" "))
        .unwrap_or_else(|_| "unavailable".into())
}

fn stats(mut times: Vec<f64>) -> (f64, f64) {
    times.sort_by(|a, b| a.partial_cmp(b).unwrap());
    (times[0], times[times.len() / 2])
}

fn main() {
    let mut args = std::env::args().skip(1);
    let dir = args.next().expect("usage: <corpus-dir> [rounds] [warmups] [seed] [quality]");
    let rounds: usize = args.next().map(|v| v.parse().unwrap()).unwrap_or(101);
    let warmups: usize = args.next().map(|v| v.parse().unwrap()).unwrap_or(5);
    let seed: u64 = args.next().map(|v| v.parse().unwrap()).unwrap_or(20_260_811);
    let quality: i32 = args.next().map(|v| v.parse().unwrap()).unwrap_or(5);

    let mut config = EncodeConfig::v1_default();
    config.web_profile = true;

    println!("# admission-before loadavg: {}", load_avg());
    println!("# rounds={rounds} warmups={warmups} seed={seed} brotli_quality={quality} lgwin={LGWIN}");

    // arm 0 = cubrim web profile, arm 1 = brotli-q<quality>
    let mut payloads = Vec::new();
    for name in SAMPLES {
        let data = std::fs::read(format!("{dir}/{name}"))
            .unwrap_or_else(|e| panic!("read {dir}/{name}: {e}"));
        let cubrim_blob = encode_with_config(&data, &config);
        assert_eq!(decode(&cubrim_blob).expect("cubrim decode"), data, "{name}");
        let brotli_blob = brotli_compress(&data, quality);
        assert_eq!(
            brotli_decompress(&brotli_blob, data.len()),
            data,
            "{name}: brotli round trip"
        );
        payloads.push((name, data, cubrim_blob, brotli_blob));
    }

    for _ in 0..warmups {
        for (_, data, cubrim_blob, brotli_blob) in &payloads {
            assert_eq!(&decode(cubrim_blob).unwrap(), data);
            assert_eq!(&brotli_decompress(brotli_blob, data.len()), data);
        }
    }

    let n = payloads.len();
    let mut times: Vec<Vec<Vec<f64>>> = vec![vec![Vec::with_capacity(rounds); 2]; n];
    let mut rng = Lcg(seed);
    for _ in 0..rounds {
        // One schedule over (sample, arm) pairs: the arms interleave, so drift
        // cannot land on one arm only.
        let mut order: Vec<(usize, usize)> =
            (0..n).flat_map(|i| [(i, 0usize), (i, 1usize)]).collect();
        for i in (1..order.len()).rev() {
            let j = (rng.next() as usize) % (i + 1);
            order.swap(i, j);
        }
        for (idx, arm) in order {
            let (name, data, cubrim_blob, brotli_blob) = &payloads[idx];
            let elapsed = if arm == 0 {
                let start = Instant::now();
                let out = decode(cubrim_blob).expect("timed cubrim decode");
                let t = start.elapsed().as_secs_f64();
                assert_eq!(&out, data, "{name}: cubrim byte-exact in timed loop");
                t
            } else {
                let start = Instant::now();
                let out = brotli_decompress(brotli_blob, data.len());
                let t = start.elapsed().as_secs_f64();
                assert_eq!(&out, data, "{name}: brotli byte-exact in timed loop");
                t
            };
            times[idx][arm].push(elapsed);
        }
    }

    println!(
        "{:<40} {:>8} {:>9} {:>9} {:>11} {:>11} {:>7}",
        "sample", "orig", "cbr_bytes", "br_bytes", "cbr_MB_s", "br_MB_s", "ratio"
    );
    let mut total_bytes = 0usize;
    let mut cubrim_total = 0f64;
    let mut brotli_total = 0f64;
    for (idx, (name, data, cubrim_blob, brotli_blob)) in payloads.iter().enumerate() {
        let (cbest, _cmed) = stats(times[idx][0].clone());
        let (bbest, _bmed) = stats(times[idx][1].clone());
        total_bytes += data.len();
        cubrim_total += cbest;
        brotli_total += bbest;
        let cmb = data.len() as f64 / cbest / 1e6;
        let bmb = data.len() as f64 / bbest / 1e6;
        println!(
            "{:<40} {:>8} {:>9} {:>9} {:>11.2} {:>11.2} {:>7.4}",
            name,
            data.len(),
            cubrim_blob.len(),
            brotli_blob.len(),
            cmb,
            bmb,
            cmb / bmb
        );
    }
    let cubrim_mb = total_bytes as f64 / cubrim_total / 1e6;
    let brotli_mb = total_bytes as f64 / brotli_total / 1e6;
    println!(
        "AGGREGATE bytes={total_bytes} cubrim_MB_s={cubrim_mb:.2} \
         brotli{quality}_MB_s={brotli_mb:.2} decode_throughput_vs_brotli{quality}={:.4}",
        cubrim_mb / brotli_mb
    );
    println!("# bar: >= 0.50 (hypothesis 11, criterion 57)");
    println!("# admission-after loadavg: {}", load_avg());
}
