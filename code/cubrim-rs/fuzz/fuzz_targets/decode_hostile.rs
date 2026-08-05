//! Fuzz `decode()` against wholly untrusted bytes.
//!
//! The property under test is the decoder's entire contract for hostile input:
//! it returns `Ok` or `Err`, and never panics, aborts, or allocates without
//! bound. libFuzzer treats a panic or an OOM as a crash, so the target needs no
//! assertions of its own — reaching the end of the body is the pass.
//!
//! Run with an explicit memory ceiling so that an unbounded allocation is
//! reported as a finding rather than taken out on the host:
//!
//! ```text
//! cargo +nightly fuzz run decode_hostile -- -rss_limit_mb=2048 -max_total_time=300
//! ```
//!
//! That ceiling is not incidental. Before the CUBR-0075 hardening, a hostile
//! header drove the decoder to ~111 GB of anonymous RSS and the kernel's OOM
//! killer took down the entire process group, so an uncapped run destroyed the
//! session rather than reporting a bug.

#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // A decoded output is fine; a wrong one is a correctness bug that the
    // round-trip target covers. Here only the absence of a crash matters.
    let _ = cubrim::decode(data);
});
