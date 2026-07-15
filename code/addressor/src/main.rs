use addressor::router::Addressor;
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "cubrim-addr", version, about = "Cubrim-2 Addressor — fleet CAS/dedup router over Cubrim-1")]
struct Cli {
    /// Addressor root directory (store + catalog)
    #[arg(long, env = "ADDRESSOR_ROOT", default_value = "./addr-root")]
    root: PathBuf,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Store a file; prints the ordinal reference
    Store {
        file: PathBuf,
        /// Build a Merkle verification sidecar (optional, default off)
        #[arg(long)]
        verify: bool,
    },
    /// Retrieve by ordinal reference to stdout or -o file
    Retrieve {
        ordinal: u64,
        #[arg(short, long)]
        out: Option<PathBuf>,
        /// Verify against the Merkle sidecar (optional, default off)
        #[arg(long)]
        verify: bool,
    },
    /// Store/catalog statistics
    Stats,
    /// Print the BLAKE3-256 hex of a file (used by sync scripts)
    Hash { file: PathBuf },
    /// Pure Cubrim-1 container size for a file (the regression baseline)
    PureSize { file: PathBuf },
    /// Regression-proof bench over a corpus dir (per-file + charged aggregate)
    BenchRegression {
        corpus: PathBuf,
        /// also assert the corpus-level charged aggregate (needs dup-fraction
        /// above the router threshold; exits 3 on a wrong-corpus precondition)
        #[arg(long)]
        charged: bool,
    },
    /// Delta sizes over a pairs dir (each subdir holds files `old` and `new`)
    BenchDelta { pairs: PathBuf },
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Store { file, verify } => {
            let data = std::fs::read(&file)?;
            let mut a = Addressor::open(&cli.root)?;
            let out = a.store_bytes(&data)?;
            if verify && !out.deduped {
                // runtime-optional Merkle sidecar over the stored container
                let entry = a.catalog.entry(out.ordinal)?.expect("fresh entry");
                let blob_path = a.cas.blob_path(&entry.blob);
                let blob_bytes = a.cas.get(&entry.blob)?;
                addressor::merkle::write_sidecar(&blob_path, &blob_bytes)?;
            }
            println!(
                "{} scheme={:?} deduped={} container_bytes={}",
                out.ordinal, out.scheme, out.deduped, out.container_len
            );
        }
        Cmd::Retrieve { ordinal, out, verify } => {
            let a = Addressor::open(&cli.root)?;
            if verify {
                let entry = a
                    .catalog
                    .entry(ordinal)?
                    .ok_or_else(|| format!("unknown ordinal {ordinal}"))?;
                let blob_path = a.cas.blob_path(&entry.blob);
                let blob_bytes = a.cas.get(&entry.blob)?;
                addressor::merkle::verify_sidecar(&blob_path, &blob_bytes)?;
            }
            let data = a.retrieve(ordinal)?;
            match out {
                Some(p) => std::fs::write(p, &data)?,
                None => {
                    use std::io::Write;
                    std::io::stdout().write_all(&data)?;
                }
            }
        }
        Cmd::Hash { file } => {
            let data = std::fs::read(&file)?;
            println!("{}", blake3::hash(&data).to_hex());
        }
        Cmd::PureSize { file } => {
            let data = std::fs::read(&file)?;
            println!("{}", Addressor::pure_cubrim_container(&data).len());
        }
        Cmd::BenchRegression { corpus, charged } => {
            bench_regression(&cli.root, &corpus, charged)?;
        }
        Cmd::BenchDelta { pairs } => {
            bench_delta(&pairs)?;
        }
        Cmd::Stats => {
            let a = Addressor::open(&cli.root)?;
            println!("catalog_entries={}", a.catalog.len()?);
            println!("entries_r1={}", a.catalog.entries_r1()?);
            println!("cas_blobs={}", a.cas.blob_count()?);
            println!("fp16_slots={} bytes_per_slot=2.0", a.catalog.fp16_slot_count());
            println!("matrix_members={}", a.matrix.member_count());
            println!("seen_distinct={}", a.catalog.seen_distinct()?);
            println!("section_hit_rate={:.4}", a.matrix.section_hit_rate());
        }
    }
    Ok(())
}

fn walk_files(root: &std::path::Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(d) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&d) else { continue };
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                stack.push(p);
            } else if p.file_name().map(|n| n != "manifest.json").unwrap_or(false) {
                out.push(p);
            }
        }
    }
    out.sort();
    out
}

fn dir_bytes(root: &std::path::Path) -> u64 {
    walk_files(root).iter().filter_map(|p| std::fs::metadata(p).ok()).map(|m| m.len()).sum()
}

fn bench_regression(
    root: &std::path::Path,
    corpus: &std::path::Path,
    charged: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut a = Addressor::open(root)?;
    let files = walk_files(corpus);
    if files.is_empty() {
        return Err("empty corpus".into());
    }
    let (mut total_in, mut total_pure, mut total_container) = (0u64, 0u64, 0u64);
    let mut per_file_violations = 0u64;
    let mut dup_weighted = 0f64;
    for f in &files {
        let data = std::fs::read(f)?;
        let pure = Addressor::pure_cubrim_container(&data).len() as u64;
        let dup = a.dup_fraction(&data)?;
        let out = a.store_bytes(&data)?;
        if !out.deduped && out.container_len as u64 > pure {
            per_file_violations += 1;
            eprintln!("VIOLATION {}: router {} > pure {}", f.display(), out.container_len, pure);
        }
        total_in += data.len() as u64;
        total_pure += pure;
        total_container += out.container_len as u64;
        dup_weighted += dup * data.len() as f64;
    }
    let corpus_dup_fraction = dup_weighted / total_in as f64;
    // charged aggregate: containers + ALL metadata (catalog, fp16, matrix)
    let metadata = dir_bytes(&root.join("catalog")) + dir_bytes(&root.join("matrix"));
    let charged_total = total_container + metadata;
    println!("files={} input_bytes={total_in}", files.len());
    println!("pure_cubrim_total={total_pure}");
    println!("router_containers_total={total_container} metadata_bytes={metadata} charged_total={charged_total}");
    println!("corpus_dup_fraction={corpus_dup_fraction:.4}");
    println!("per_file_violations={per_file_violations}");
    if per_file_violations > 0 {
        return Err("per-file regression property violated".into());
    }
    if charged {
        if corpus_dup_fraction < addressor::router::DUP_THRESHOLD {
            eprintln!(
                "wrong corpus: dup_fraction {corpus_dup_fraction:.4} < threshold {} — charged aggregate precondition unmet",
                addressor::router::DUP_THRESHOLD
            );
            std::process::exit(3);
        }
        println!(
            "charged_vs_pure_ratio={:.4}",
            charged_total as f64 / total_pure as f64
        );
        if charged_total > total_pure {
            return Err("charged aggregate exceeds pure Cubrim-1 aggregate".into());
        }
    }
    Ok(())
}

fn bench_delta(pairs: &std::path::Path) -> Result<(), Box<dyn std::error::Error>> {
    let (mut delta_total, mut new_total, mut n) = (0u64, 0u64, 0u64);
    for e in std::fs::read_dir(pairs)? {
        let d = e?.path();
        if !d.is_dir() {
            continue;
        }
        let old = std::fs::read(d.join("old"))?;
        let new = std::fs::read(d.join("new"))?;
        let bh = *blake3::hash(&old).as_bytes();
        let delta = addressor::delta::encode(&old, &bh, &new)?;
        // round-trip sanity on every pair
        let back = addressor::delta::decode(&old, &delta)?;
        if back != new {
            return Err(format!("delta roundtrip failed for {}", d.display()).into());
        }
        delta_total += delta.len() as u64;
        new_total += new.len() as u64;
        n += 1;
    }
    if n == 0 {
        return Err("no pairs found".into());
    }
    println!("pairs={n} new_bytes={new_total} delta_bytes={delta_total}");
    println!("delta_ratio={:.6}", delta_total as f64 / new_total as f64);
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}
