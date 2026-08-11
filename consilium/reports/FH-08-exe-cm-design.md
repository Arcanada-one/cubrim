# FH-08 sparse executable CM forced probe

**Status:** design for a private non-default experiment. FH-07 has not yet
produced a measured result.

## Question

After architecture-matched BCJ, can two cheap aligned sparse contexts improve
the plain FH-07 CM candidate on `mozilla` and `ooffice`? This first stage does
not attempt instruction decoding, ModR/M parsing, or operand classification.

## Mechanism

- Add decoder-capable `MODE_EXECM=14`, absent from all production encoder
  dispatch paths and CLI options.
- Private `encode_exe_cm_probe` requires strict ELF/PE architecture detection,
  applies the existing x86/ARM64/SPARC BCJ filter, then invokes an executable CM
  predictor profile.
- The ordinary nine CM inputs remain. Exe instances add exactly two inputs:
  `(byte[t-4], global_position % 4, partial-byte-prefix)` and
  `(byte[t-8], global_position % 4, partial-byte-prefix)`. Before enough bytes
  exist, each uses an explicit unavailable-history context.
- The exe mixer is selected by `(global_position % 4, bit_position)`. Encoder
  and decoder observe identical online state. Ordinary `CmPredictor::new()`,
  record-CM, and MODE_CM use their existing branches and bytes.

## Wire

```text
MAGIC[4] VERSION MODE_EXECM
orig_len:u64 block_size:u32 n_blocks:u32 arch:u8
n_blocks * (comp_len:u32 filtered_hash64:u64)
concatenated range-coded BCJ-filtered blocks
```

The decoder validates architecture, block count, all lengths, every filtered
block hash, and reconstructed length before applying inverse BCJ. Predictor
instances receive each block's global start offset; the first 4/8 bytes of a
block use explicit unavailable-history contexts.

## Verification

Local focused tests cover x86 ELF BCJ→exe-CM round-trip and rejection of
truncated framing, invalid arch, bad lengths, and corrupt hashes. Existing
BCJ-CM, record-CM, and direct MODE_CM tests remain green. Required static gates:
`cargo fmt --check`, `cargo check --lib`, and `git diff --check`.

The ignored dev-ai test runs after FH-10 under a fresh three-minute `load<12`,
`paxbt=0`, Cubrim-idle gate with `CUBR_THREADS=4`. For full `mozilla` and
`ooffice`, sequentially, it records exact complete archive sizes and RT/cmp for:

1. current top-level competitive rail;
2. FH-07 BCJ→plain-CM;
3. FH-08 BCJ→sparse-exe-CM.

Fresh orientation measurements use the canonical commands `xz -9e`,
`7z -t7z -m0=LZMA2 -mx=9`, and `rar a -m5 -ep`, each extracted and compared.
The official exe aggregate is `(mozilla_comp + ooffice_comp) /
(mozilla_orig + ooffice_orig)`, not an unweighted average.

## Gates

- **GO-to-full-24:** FH-08 is at least 1.5% smaller than FH-07 on one target,
  the original-byte-weighted exe aggregate improves, and all RT/cmp checks pass.
- **NO-GO:** neither file clears 1.5%, aggregate regresses, strict executable
  detection fails, or any correctness check fails.
- FH-07 losing to the current rail does not automatically falsify FH-08: report
  both comparisons and require FH-08 to beat the current rail before any later
  default integration proposal.
- No DB mutation or default-rail integration occurs before a real full-24 run.
