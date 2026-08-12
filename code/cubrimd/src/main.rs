//! cubrimd CLI. See lib.rs for what the proxy does and deliberately does not.
//!
//! Usage:
//!   cubrimd --origin http://127.0.0.1:8080 [--listen 127.0.0.1:8078]
//!           [--block-size 65536] [--max-body-bytes 8388608]
//!           [--cache-entries 256]

use cubrimd::{Config, Proxy, METRICS_PATH};

fn main() {
    let mut config = Config::default();
    let mut listen = "127.0.0.1:8078".to_owned();

    let mut args = std::env::args().skip(1);
    while let Some(flag) = args.next() {
        let mut value = |flag: &str| {
            args.next()
                .unwrap_or_else(|| die(&format!("{flag} needs a value")))
        };
        match flag.as_str() {
            "--origin" => config.origin = value("--origin").trim_end_matches('/').to_owned(),
            "--listen" => listen = value("--listen"),
            "--block-size" => {
                let v: usize = parse(&value("--block-size"), "--block-size");
                config.block_size = if v == 0 { None } else { Some(v) };
            }
            "--max-body-bytes" => {
                config.max_body_bytes = parse(&value("--max-body-bytes"), "--max-body-bytes")
            }
            "--cache-entries" => {
                config.cache_entries = parse(&value("--cache-entries"), "--cache-entries")
            }
            "--help" | "-h" => {
                println!(
                    "cubrimd --origin <url> [--listen host:port] [--block-size N] \
                     [--max-body-bytes N] [--cache-entries N]"
                );
                return;
            }
            other => die(&format!("unknown flag: {other}")),
        }
    }
    if config.origin.is_empty() {
        die("--origin is required (e.g. --origin http://127.0.0.1:8080)");
    }
    if !config.origin.starts_with("http://") {
        // TLS to the origin is out of scope by design; refusing loudly beats
        // a confusing ureq error deep in the first request.
        die("--origin must be an http:// URL (TLS is deliberately out of scope)");
    }

    let origin = config.origin.clone();
    let proxy = Proxy::bind(&listen, config).unwrap_or_else(|e| die(&e));
    println!(
        "cubrimd: {listen} -> {origin} (Content-Encoding: cbm negotiated; metrics at {METRICS_PATH})",
        listen = listen,
    );
    proxy.run();
}

fn parse(value: &str, flag: &str) -> usize {
    value
        .parse()
        .unwrap_or_else(|_| die(&format!("{flag}: not a number: {value}")))
}

fn die(message: &str) -> ! {
    eprintln!("cubrimd: {message}");
    std::process::exit(2);
}
