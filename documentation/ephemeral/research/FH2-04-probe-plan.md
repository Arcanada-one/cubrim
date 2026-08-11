# FH2-04 similarity-order EXE probe plan

**Scope:** isolated `research/cubr-fh2-04-probe` from `d2aa339`; research
scripts only, no codec/PPMd/Opus/core/DB/site edits.

## Scientific contract

- Exact `mozilla`: 51,220,480 bytes, SHA-256
  `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b`.
- Parse 525 regular-file frames.  Attach each of the 318 directory headers to
  the following file frame; keep terminal zero/trailing bytes outside the
  permutation.  Frames plus trailer must cover the source exactly once.
- Signature = normalized 256-bin byte histogram of the regular-file payload
  only.  Order = deterministic greedy nearest-neighbour under L1 distance,
  starting with the largest payload; ties break by original index.
- Frame bytes are never changed.  The charged permutation is conservative:
  `24 + ceil(525 * ceil(log2(525)) / 8) = 681` bytes.
- Decode means: decompress reordered stream, parse its frames, apply the
  transmitted inverse permutation, append the trailer, and require external
  byte-for-byte comparison with the source.
- GO requires charged improvement of at least 1.5% on a preregistered rail.
  No tuning after observing a full result.

## Execution

1. TDD a Python parser/reorder runner.  Tests cover mixed directory/file tar,
   exact coverage, deterministic non-identity ordering on synthetic similar
   payloads, inverse RT, and 681-byte charge.
2. Build `d2aa339` release CLI and record its hash.  Reuse only exact baseline
   evidence from the immediately preceding FH2-05 run when binary hash, source
   hash, and raw prefix hash all match:
   - full original Cubrim MODE_LZ: 15,788,540 bytes, RT `cmp=0`;
   - first-64-file prefix: 7,341,568 raw / 4,310,315 compressed, RT `cmp=0`.
3. Build the full reordered stream and inverse-restore it before compression.
   Stop invalid on any parse/coverage/permutation/RT mismatch.
4. Run fresh `xz -9e` on original and reordered full streams; decompress both.
   Compare charged reordered size with fresh original size.  This is an
   independent long-window diagnostic, not a gate on Cubrim.
5. Run fresh Cubrim on the similarity-reordered version of the same first 64
   frames used by FH2-05, charge the screen permutation, decompress, inverse
   restore, and compare with the exact original prefix.  Full Cubrim is admitted
   only if charged screen improvement is positive; a non-positive paired screen
   is screen NO-GO for the Cubrim rail.
6. If admitted, run the unchanged full reordered stream through the same Cubrim
   binary and compare `size + 681` with 15,788,540.  Full GO only at >=1.5%.
7. Record exact sizes, ratios, permutation/hash evidence, timing/RSS, and all
   `cmp=0` checks.  Append `[PPMD→EXE/FH2-04]` to
   `/home/dev/cubr-cm-status.md`, notify coord, remove temporary streams and
   commit branch-local research artifacts.

## Stop conditions

- Any identity/RT mismatch: invalid probe, no ratio verdict.
- xz gain <1.5%: xz NO-GO only; still run Cubrim screen.
- Cubrim screen charged gain <=0: Cubrim screen NO-GO, no full Cubrim.
- No rail reaches 1.5%: final FH2-04 NO-GO.
