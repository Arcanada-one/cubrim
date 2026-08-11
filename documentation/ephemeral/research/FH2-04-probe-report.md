# FH2-04 similarity ordering — NO-GO

## Verdict

Deterministic similarity ordering of tar members is byte-exact but too weak.
On full `mozilla`, unchanged Cubrim improves by only **17,838 bytes / 0.112981%**
after charging the 681-byte permutation map.  The preregistered gate was 1.5%,
so FH2-04 is closed without tuning or codec integration.

## Contract and correctness

- Source: 51,220,480 bytes, SHA-256
  `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b`.
- Layout: 525 regular-file frames; 318 directory headers are attached to the
  following file; 3,584 trailer bytes remain outside the permutation.
- Ordering: greedy nearest-neighbour on normalized 256-bin payload histograms,
  largest payload first, original index as the deterministic tie break.
- Full order changed all 525 positions; order SHA-256
  `b7e87caa8c1bc17a800380e76aab0c2cdeb63a94e8e158791af79d1d481447a8`.
- Cubrim decompression matched the reordered tar (`cmp=0`).  Applying the
  inverse permutation then matched the original tar (`cmp=0`) and reproduced
  its exact SHA-256.  The xz and 1 MiB BCJ diagnostics also passed RT `cmp=0`.

## Measurements

| Rail | Original | Reordered blob | Map charge | Charged | Change |
|---|---:|---:|---:|---:|---:|
| Cubrim, first 64 frames | 4,310,315 | 4,307,659 | 72 | 4,307,731 | −2,584 / −0.059949% |
| Cubrim, full | 15,788,540 | 15,770,021 | 681 | 15,770,702 | −17,838 / −0.112981% |
| xz `-9e`, full | 13,376,240 | 13,364,336 | 681 | 13,365,017 | −11,223 / −0.083903% |

The positive 64-frame screen admitted the full Cubrim run exactly as planned.
The full run used the same `d2aa339` release binary as FH2-05.  Encode wall was
400.11 s and maximum RSS 7,124,932 KiB.  Despite the small gain, charged Cubrim
remains 2,427,890 bytes / 18.196% larger than fresh 7z LZMA2 (13,342,812).

## BCJ attribution check

The first 1 MiB of the same corpus was compressed by fresh 7-Zip 23.01 with
single-threaded plain LZMA2 and with a forced x86 BCJ→LZMA2 chain.  Plain was
641,771 bytes; forced BCJ was 641,863 bytes, 92 bytes / 0.014335% worse.  Both
decoded with `cmp=0`.  The screen is a NO-GO, so no full BCJ run was made.

This confirms the relevant mechanism boundary: `mozilla` contains Alpha code,
while 7z has no Alpha BCJ filter.  Its lead on this tar is therefore an LZMA2
backend advantage, not a hidden BCJ win.  Earlier Alpha-BCJ work and FH2-03
already showed that this residual is not closed by a reproducible ROLZ rail.

## Scope and hygiene

Only research scripts, tests, plan, and evidence live on the isolated
`research/cubr-fh2-04-probe` branch.  No codec, PPMd, Opus, core, DB, or site
files were changed.
