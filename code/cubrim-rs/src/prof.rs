// Encoder candidate attribution probe (development instrumentation).
//
// Purpose: the encoder is a competitive-min rail — it builds many candidate
// encodings of the same input and emits the smallest. The decoder replays only
// the winner. That asymmetry is the leading suspect for the measured
// encode/decode gap, and it cannot be attributed from the outside: an external
// timer sees one number for the whole rail.
//
// This module records, per named candidate: call count, total wall time, total
// candidate output bytes, and how often the candidate became the running
// minimum. Off unless `CUBRIM_PROFILE=1`, in which case a table is written to
// stderr at process exit.
//
// It is a measurement instrument, not a feature:
//   - it never changes what bytes are emitted;
//   - when disabled the added cost is one relaxed atomic load per candidate;
//   - it is not wired into any public API.
//
// Nested candidates (a transform whose body re-enters the encoder) attribute
// their inner time to the inner name as well as the outer, so column totals
// deliberately exceed wall-clock. Read the table as attribution, not a
// partition.

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

#[derive(Default, Clone, Copy)]
pub(crate) struct Slot {
    pub calls: u64,
    pub nanos: u128,
    pub out_bytes: u128,
    pub wins: u64,
}

static STATE: OnceLock<Mutex<BTreeMap<&'static str, Slot>>> = OnceLock::new();
// 0 = not yet resolved, 1 = enabled, 2 = disabled.
static ENABLED: AtomicU8 = AtomicU8::new(0);
static REPORTED: AtomicBool = AtomicBool::new(false);

pub(crate) fn enabled() -> bool {
    match ENABLED.load(Ordering::Relaxed) {
        1 => true,
        2 => false,
        _ => {
            let on = std::env::var("CUBRIM_PROFILE")
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(false);
            ENABLED.store(if on { 1 } else { 2 }, Ordering::Relaxed);
            on
        }
    }
}

fn state() -> &'static Mutex<BTreeMap<&'static str, Slot>> {
    STATE.get_or_init(|| Mutex::new(BTreeMap::new()))
}

/// Time `f`, attributing its wall time and output size to `name`.
///
/// Returns `f`'s value untouched, so a call site can be wrapped without
/// changing behaviour. `size_of` maps the result to its candidate byte length
/// (a candidate that declined to run reports 0).
pub(crate) fn track<T>(
    name: &'static str,
    size_of: impl Fn(&T) -> usize,
    f: impl FnOnce() -> T,
) -> T {
    if !enabled() {
        return f();
    }
    let t0 = Instant::now();
    let out = f();
    let dt = t0.elapsed().as_nanos();
    let bytes = size_of(&out) as u128;
    if let Ok(mut map) = state().lock() {
        let slot = map.entry(name).or_default();
        slot.calls += 1;
        slot.nanos += dt;
        slot.out_bytes += bytes;
    }
    out
}

/// Record that `name` became the running competitive minimum.
pub(crate) fn win(name: &'static str) {
    if !enabled() {
        return;
    }
    if let Ok(mut map) = state().lock() {
        map.entry(name).or_default().wins += 1;
    }
}

/// Write the attribution table to stderr. Idempotent — the first call reports,
/// later calls are no-ops, so wiring it into several exit paths is safe.
pub(crate) fn report(total_nanos: u128) {
    if !enabled() || REPORTED.swap(true, Ordering::Relaxed) {
        return;
    }
    let map = match state().lock() {
        Ok(m) => m.clone(),
        Err(_) => return,
    };
    let mut rows: Vec<(&'static str, Slot)> = map.into_iter().collect();
    rows.sort_by_key(|r| std::cmp::Reverse(r.1.nanos));
    eprintln!("\n=== CUBRIM ENCODER CANDIDATE ATTRIBUTION ===");
    eprintln!("total measured wall: {:.3} s", total_nanos as f64 / 1e9);
    eprintln!(
        "{:<26} {:>9} {:>12} {:>8} {:>9} {:>14}",
        "candidate", "calls", "seconds", "share%", "wins", "out_bytes"
    );
    for (name, s) in &rows {
        let share = if total_nanos > 0 {
            100.0 * s.nanos as f64 / total_nanos as f64
        } else {
            0.0
        };
        eprintln!(
            "{:<26} {:>9} {:>12.3} {:>8.2} {:>9} {:>14}",
            name,
            s.calls,
            s.nanos as f64 / 1e9,
            share,
            s.wins,
            s.out_bytes
        );
    }
    eprintln!(
        "=== END ATTRIBUTION (nested candidates double-count; attribution, not partition) ===\n"
    );
}
