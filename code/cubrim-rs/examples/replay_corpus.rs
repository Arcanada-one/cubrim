//! Replay a fuzz corpus through `cubrim::decode` so coverage can be measured.
//!
//! The `decode_hostile` fuzz target's whole contract is that `cubrim::decode()`
//! never panics on untrusted bytes. That says nothing about *which* decode paths
//! the corpus actually reaches, and a target that never enters a backend is
//! providing no assurance over it however green it looks.
//!
//! This binary is the instrument for that question (CUBR-0099). It calls the same
//! public entry point the fuzz target calls, once per corpus file, so a coverage
//! run over it reports honest hit counts per decode path:
//!
//! ```text
//! cargo llvm-cov --release --example replay_corpus -- fuzz/corpus/decode_hostile
//! ```
//!
//! It is deliberately *not* a test: it asserts nothing about decode results. A
//! corpus of hostile inputs is expected to be mostly `Err`, and an `Err` still
//! executes the path under measurement.

use std::path::PathBuf;

fn main() {
    let dir: PathBuf = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "fuzz/corpus/decode_hostile".to_string())
        .into();

    let mut entries: Vec<PathBuf> = match std::fs::read_dir(&dir) {
        Ok(rd) => rd.filter_map(|e| e.ok()).map(|e| e.path()).collect(),
        Err(e) => {
            eprintln!("cannot read corpus dir {}: {e}", dir.display());
            std::process::exit(2);
        }
    };
    // Deterministic order so two runs are comparable.
    entries.sort();

    let (mut ok, mut err) = (0usize, 0usize);
    for path in &entries {
        if !path.is_file() {
            continue;
        }
        let Ok(bytes) = std::fs::read(path) else {
            continue;
        };
        match cubrim::decode(&bytes) {
            Ok(_) => ok += 1,
            Err(_) => err += 1,
        }
    }

    println!(
        "replayed {} file(s) from {}: {ok} decoded, {err} rejected",
        ok + err,
        dir.display()
    );
}
