# FH2-05 Research Probe Plan: Per‑segment competitive-min on mozilla tar

## Purpose
Cheap probe to decide **GO / NO‑GO** before any codec modifications.
The experiment mimics segment‑wise routing by partitioning the mozilla tar
at member boundaries, compressing each segment independently with the
current Cubrim CLI, and charging the framing overhead.

## Test file
- **File**: mozilla binary distribution tar, exactly 51 220 480 bytes,
  SHA-256 `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b`.
- **Members**: 525 (tar records) – mixed code, data, text, resources.
- **Baseline** (whole‑file, d2aa339 `cubrim` default):
  Cubrim 15 788 540 bytes, 7z 13 342 812 bytes.

## Probe runner
A Python script (`probe_fh2_05_segment_min.py`) that:
1. Parses raw 512-byte tar headers to locate every member’s byte range.
   Boundaries must be exact and cover the entire file without gaps or overlaps.
   Each segment contains the member header, payload, and padding; the terminal
   zero/trailing area is attached to the last member so concatenation is the
   original tar byte-for-byte.
2. For each member:
   - Extract raw bytes to a temporary file.
   - Invoke `cubrim` (commit `d2aa339`, default options) to compress,
     capture the output size.
   - Immediately decompress with `cubrim` and compare byte‑for‑byte
     with the original member bytes (assert `cmp` 0).
3. **Candidate charge** (conservative, no design‑stage shortcuts):
   - Outer fixed header: 24 bytes (magic, version, segment count).
   - Per segment: 4 bytes big‑endian length of compressed blob
     + the compressed blob bytes.
   - **Charged size** = 24 + Σ (4 + len(compressed_member_i)).
   This deliberately overcharges the card's proposed 3–6 byte frame because
   each complete nested Cubrim blob also repeats its own magic/version/mode and
   original length.  A loss under this accounting is conservative evidence.

## Procedure
### 1. Reproduce whole‑file baseline
Compress the entire mozilla tar with the used Cubrim binary; confirm the
result exactly equals 15 788 540 bytes. If not, bisect CLI/environment.

### 2. Paired contiguous-prefix screen
Take the shortest whole-member prefix containing at least 8 MiB (up to 64
members), encode those exact bytes once as a whole-prefix baseline, then encode
the same prefix as its independently framed member segments.  Compare only
like-for-like bytes.

- Proceed to full if charged segmentation is no worse than 5% relative behind
  its whole-prefix baseline.  This wide direction gate avoids rejecting a
  later heterogeneous mix on a locally LZ-heavy prefix.
- Stop screen `NO-GO` only if the paired prefix loses by more than 5%; the
  mechanism would need an implausibly large reversal on the remaining members.

### 3. Full probe (if the paired screen is within 5%)
Compress all 525 members, verify decodability, compute charged size.
Compare with whole‑file baseline.

## GO / NO‑GO criterion
**GO** if the full‑probe relative gain is **≥ 1.5%**.
Otherwise **NO‑GO**.

_Why 1.5%_ – the per‑member approach omits inter‑member LZ dictionary
matches, making the estimate **pessimistic**. A measured gain ≥ 1.5%
even without continuation signals that the real implementation
will exceed that (FH2‑05 allows intra‑class state continuation,
which can only improve compression). Thus 1.5% is a safe screening
threshold.

## Scope restrictions
- No codec modifications; use the existing `d2aa339` Cubrim CLI binary.
- No PPMd, Opus, core‑engine, database, or site edits.
- Probe script, exact result table, and report are branch-local research
  artifacts; temporary corpus/archives are removed after evidence capture.

## Deliverables
- `probe_fh2_05_segment_min.py` plus focused parser/charge tests (self-contained,
  idempotent, reporting charged size,
  verified decodability, and gain).
- Report section appended here with:
  - Reproduced whole‑file size.
  - Per‑segment charged size.
  - Screened gain and decision to proceed.
  - Final gain and GO/NO‑GO verdict.
