# FH2-05 per-segment competitive-min — screen NO-GO

**Verdict:** `SCREEN NO-GO`.  Independently routing the first 64 `mozilla`
file-member frames made the same tar prefix **11.193381% larger** than one
whole-prefix Cubrim encode.  This exceeded the pre-registered +5% stop wall, so
the 525-member full probe was not run.

## Reproducible setup

- Isolated branch `research/cubr-fh2-05-probe` from `d2aa339`; no codec edits.
- Exact input `/root/corpus-full/silesia/mozilla`: 51,220,480 bytes, SHA-256
  `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b`.
- Fresh release CLI built from `d2aa339`: SHA-256
  `b2d286d1dd5ff25a0f93f16b4ba8fd41ab6da7ef91b2a7f24bfbd1298368cdfd`.
- The card's “525 members” means 525 regular files.  The raw tar also contains
  318 directory headers (843 header records total).  The first parser run
  stopped before compression on this count mismatch.  A RED→GREEN test then
  grouped directory headers with the following regular file, yielding exactly
  525 contiguous frames whose concatenation covers all 51,220,480 input bytes.
- Each frame includes all original tar headers/payload/padding in place.  It is
  independently passed through the unmodified default Cubrim competitive CLI,
  immediately decoded, and compared.  Candidate charge is deliberately
  conservative: 24-byte outer header + 4-byte compressed-length framing per
  segment + every complete nested Cubrim blob (including its repeated header).

## Baseline gate

The fresh CLI reproduced the authoritative whole-file MODE_LZ result exactly:
**15,788,540 bytes / 0.308246623**, mode 3, decode `cmp=0`.  Encode/decode took
408.740 / 1.060 seconds.  Fresh 7z remains 13,342,812 / 0.260497598.

## Paired screen

The screen was the same contiguous 7,341,568-byte prefix on both sides, ending
after regular-file segment 64.  Its SHA-256 was
`91bdadc2692d72276bb765bd0c7ca4e786a2cda14083360383d3607f961cc7ba`.

| Encoding of the same prefix | Charged bytes | Ratio |
|---|---:|---:|
| one whole-prefix default Cubrim blob | **4,310,315** | 0.587110955 |
| 64 independent blobs, before outer framing | 4,792,505 | 0.652790385 |
| 64 independent blobs + 24 + 64×4 framing | **4,792,785** | **0.652828524** |

The segmented candidate loses **482,470 bytes / 11.193381%**.  It did route
heterogeneously (27 MODE_RAW, 10 MODE_CUBE, 27 MODE_LZ), so failure is not a
dispatcher no-op: lost cross-member LZ matches and reset dictionaries dominate
the small local mode wins.  Replacing the conservative repeated nested headers
with the card's compact 3–6 byte frames could recover only hundreds of bytes,
not the 482 KB deficit.

All 64 nested archives passed their own decode compare.  A separate ordered
concatenation of the restored frames also passed `cmp=0` against the exact
screen prefix; both SHA-256 values were the screen hash above.

## Decision

The card required a full-file GO of at least 1.5% and allowed full execution
only when the paired screen was within 5% of whole-prefix.  At -11.19%, FH2-05
is closed before the expensive 525-member run.  Optional same-class state
continuation would cease to be the tested low-risk independent-frame mechanism
and would need a new shared-dictionary architecture; it is not inferred as a
rescue from this result.

The EXE gap remains open.  The next orthogonal cheap lever is FH2-04's charged
similarity ordering, which explicitly tries to restore adjacency rather than
reset state at every member.  PPMd `d2aa339`, the Opus axis, core, DB, and site
were untouched.
