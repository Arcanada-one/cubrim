# H-37 — BCJ / branch-conversion filter for executables

**Status:** PLANNED (research candidate, round-2 ladder). No Cubrim measurement yet — numbers below are literature estimates.

**Class targeted:** ELF / machine-code executables. CUBR-0034 measured `exe.bin` (/bin/cat ELF) LOSING to both gzip (14590 vs 14388) and zstd-19 — the only structural lever left unexplored for this class.

## Hypothesis

Applying a BCJ (branch/call/jump) filter to the executable's machine-code span before the existing `bwt-rans` rail will reduce its compressed size, because BCJ converts relative CALL/JMP operands to absolute addresses, making repeated call targets byte-identical so the BWT+geomix/LZ backend can capture them as repeats.

## Why it might help (mechanism)

Machine code encodes branch targets relative to the instruction pointer, so the same callee yields a different operand byte-sequence at every call site — invisible to LZ/BWT. BCJ rewrites those operands to absolute addresses (x86 E8/E9 opcodes; ARM/ARM64/RISC-V variants), collapsing the variation to repeats. Fully reversible (inverse filter on decode), parameter-free, zero model cost.

## Expected lever (estimate — NOT a Cubrim measurement)

- xz/LZMA2: 0–15% smaller `.xz` on x86 executables from BCJ alone.
- ZPAQ E8E9: ~6–8% on x86.
- Honest cap: only the `.text` machine-code span benefits; data/rodata are neutral, so the whole-ELF gain is diluted.

## Mandatory gate (do FIRST — ~50-LoC Python, no Rust)

1. Apply x86 E8E9 to `exe.bin`; run the existing `bwt-rans` rail on filtered vs raw bytes; compare bytes.
2. Run on the REAL ELF, not a hand-picked code span (the dilution must be visible).
3. Wire as competitive `min(raw, bcj)` + 1 filter-id byte → regression-proof by construction.
4. If whole-file try-both across architectures is used, record the detection/selection cost.

## Refs

- BCJ (algorithm), Wikipedia — https://en.wikipedia.org/wiki/BCJ_(algorithm)
- XZ data compression, Linux kernel doc — https://www.kernel.org/doc/html/v5.10/staging/xz.html
- LZMA SDK BCJ filters (Pavlov), 7-zip / xz-utils (Collin).

## Measured

_Pending — to be filled by the implementing session with cubrim vs gzip-9 vs zstd-19, RT result, and code SHA._

## Verdict

_Pending._
