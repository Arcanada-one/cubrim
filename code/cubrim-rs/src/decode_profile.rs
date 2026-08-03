//! Feature-gated decode attribution for the CUBR-0075 first slice.
//!
//! This module is intentionally opt-in. It is compiled only with the
//! `decode-profile` feature and is used by the separate profiler binary. The
//! normal library and CLI do not create a profiler, read profiler state, or
//! take timing branches.

use serde::Serialize;
use std::cell::RefCell;
use std::time::Instant;

pub const SCHEMA_VERSION: u32 = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Stage {
    Framing,
    Entropy,
    Transforms,
    MatchCopy,
    Allocation,
    OutputMaterialization,
}

impl Stage {
    pub const ALL: [Stage; 6] = [
        Self::Framing,
        Self::Entropy,
        Self::Transforms,
        Self::MatchCopy,
        Self::Allocation,
        Self::OutputMaterialization,
    ];

    pub const fn name(self) -> &'static str {
        match self {
            Self::Framing => "framing",
            Self::Entropy => "entropy",
            Self::Transforms => "transforms",
            Self::MatchCopy => "match_copy",
            Self::Allocation => "allocation",
            Self::OutputMaterialization => "output_materialization",
        }
    }

    const fn index(self) -> usize {
        match self {
            Self::Framing => 0,
            Self::Entropy => 1,
            Self::Transforms => 2,
            Self::MatchCopy => 3,
            Self::Allocation => 4,
            Self::OutputMaterialization => 5,
        }
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct StageTotals {
    calls: u64,
    nanos: u64,
    cycles: Option<u64>,
    applicable: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct StageReport {
    pub name: &'static str,
    pub calls: u64,
    pub nanos: u64,
    pub cycles: Option<u64>,
    pub applicable: bool,
    pub nanos_per_output_byte: Option<f64>,
    pub cycles_per_output_byte: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Report {
    pub schema_version: u32,
    pub input_bytes: usize,
    pub output_bytes: usize,
    pub cycles_supported: bool,
    pub cycle_source: &'static str,
    pub total_nanos: Option<u64>,
    pub total_cycles: Option<u64>,
    pub stages: Vec<StageReport>,
}

#[derive(Clone, Copy, Debug, Serialize)]
pub struct Timing {
    pub nanos: u64,
    pub cycles: Option<u64>,
}

#[derive(Clone, Copy, Debug)]
struct Accumulator {
    input_bytes: usize,
    stages: [StageTotals; 6],
}

impl Accumulator {
    fn new(input_bytes: usize) -> Self {
        Self {
            input_bytes,
            stages: [StageTotals::default(); 6],
        }
    }

    fn report(self, output_bytes: usize) -> Report {
        let mut report = Report {
            schema_version: SCHEMA_VERSION,
            input_bytes: self.input_bytes,
            output_bytes,
            cycles_supported: cycle_counter().is_some(),
            cycle_source: cycle_source(),
            total_nanos: None,
            total_cycles: None,
            stages: Vec::with_capacity(Stage::ALL.len()),
        };
        for stage in Stage::ALL {
            let totals = self.stages[stage.index()];
            report.stages.push(StageReport {
                name: stage.name(),
                calls: totals.calls,
                nanos: totals.nanos,
                cycles: totals.cycles,
                applicable: totals.applicable,
                nanos_per_output_byte: None,
                cycles_per_output_byte: None,
            });
        }
        report.refresh_per_byte();
        report
    }
}

thread_local! {
    static ACTIVE: RefCell<Option<Accumulator>> = const { RefCell::new(None) };
}

pub fn begin(input_bytes: usize) {
    ACTIVE.with(|active| {
        *active.borrow_mut() = Some(Accumulator::new(input_bytes));
    });
}

pub fn finish(output_bytes: usize) -> Option<Report> {
    ACTIVE.with(|active| {
        active
            .borrow_mut()
            .take()
            .map(|state| state.report(output_bytes))
    })
}

pub fn empty_report(input_bytes: usize, output_bytes: usize) -> Report {
    Accumulator::new(input_bytes).report(output_bytes)
}

pub fn measure_total<T>(f: impl FnOnce() -> T) -> (T, Timing) {
    let start = Clock::now();
    let value = f();
    (value, start.elapsed())
}

pub fn set_external_stage(report: &mut Report, stage: Stage, calls: u64, timing: Timing) {
    let row = &mut report.stages[stage.index()];
    row.calls = calls;
    row.nanos = timing.nanos;
    row.cycles = timing.cycles;
    row.applicable = true;
    report.refresh_per_byte();
}

pub fn assign_residual_stage(report: &mut Report, stage: Stage, total: Timing) {
    let known_nanos = report
        .stages
        .iter()
        .filter(|row| row.name != stage.name())
        .map(|row| row.nanos)
        .sum::<u64>();
    let known_cycles = report
        .stages
        .iter()
        .filter_map(|row| row.cycles)
        .sum::<u64>();
    let residual = Timing {
        nanos: total.nanos.saturating_sub(known_nanos),
        cycles: total
            .cycles
            .map(|cycles| cycles.saturating_sub(known_cycles)),
    };
    set_external_stage(report, stage, 1, residual);
}

impl Report {
    pub fn set_total(&mut self, total: Timing) {
        self.total_nanos = Some(total.nanos);
        self.total_cycles = total.cycles;
    }

    fn refresh_per_byte(&mut self) {
        let denominator = self.output_bytes as f64;
        for row in &mut self.stages {
            if row.applicable && self.output_bytes > 0 {
                row.nanos_per_output_byte = Some(row.nanos as f64 / denominator);
                row.cycles_per_output_byte = row.cycles.map(|cycles| cycles as f64 / denominator);
            } else {
                row.nanos_per_output_byte = None;
                row.cycles_per_output_byte = None;
            }
        }
    }
}

pub(crate) struct StageGuard {
    stage: Stage,
    start: Option<Clock>,
}

impl StageGuard {
    pub(crate) fn enter(stage: Stage) -> Self {
        let active = ACTIVE.with(|current| current.borrow().is_some());
        if active {
            ACTIVE.with(|current| {
                if let Some(accumulator) = current.borrow_mut().as_mut() {
                    accumulator.stages[stage.index()].applicable = true;
                }
            });
            Self {
                stage,
                start: Some(Clock::now()),
            }
        } else {
            Self { stage, start: None }
        }
    }
}

impl Drop for StageGuard {
    fn drop(&mut self) {
        let Some(start) = self.start.take() else {
            return;
        };
        let timing = start.elapsed();
        ACTIVE.with(|current| {
            if let Some(accumulator) = current.borrow_mut().as_mut() {
                let totals = &mut accumulator.stages[self.stage.index()];
                totals.calls = totals.calls.saturating_add(1);
                totals.nanos = totals.nanos.saturating_add(timing.nanos);
                if let Some(cycles) = timing.cycles {
                    let total = totals.cycles.unwrap_or(0).saturating_add(cycles);
                    totals.cycles = Some(total);
                }
            }
        });
    }
}

#[derive(Clone, Copy, Debug)]
struct Clock {
    instant: Instant,
    cycles: Option<u64>,
}

impl Clock {
    fn now() -> Self {
        Self {
            instant: Instant::now(),
            cycles: cycle_counter(),
        }
    }

    fn elapsed(self) -> Timing {
        let cycles = match (self.cycles, cycle_counter()) {
            (Some(start), Some(end)) => Some(end.saturating_sub(start)),
            _ => None,
        };
        Timing {
            nanos: self.instant.elapsed().as_nanos().min(u64::MAX as u128) as u64,
            cycles,
        }
    }
}

pub fn cycle_counter() -> Option<u64> {
    #[cfg(target_arch = "x86_64")]
    {
        // The profiler is the only feature that enables this code. Fences keep
        // the boundary useful for attribution; this is not a production clock.
        use core::arch::x86_64::{_mm_lfence, _rdtsc};
        // SAFETY: the x86_64 target provides both instructions. They only read
        // the processor counter and do not dereference memory.
        let value = unsafe {
            _mm_lfence();
            let value = _rdtsc();
            _mm_lfence();
            value
        };
        Some(value)
    }
    #[cfg(not(target_arch = "x86_64"))]
    {
        None
    }
}

fn cycle_source() -> &'static str {
    if cycle_counter().is_some() {
        "rdtsc-x86_64"
    } else {
        "unavailable"
    }
}
