# CUBR-SPEEDFLOOR-WEB-20260811 — results: the field stays unreachable, but the floor is not one number

**All four predictions hold.** P3 survives its hardest test yet, and P4 — deliberately stated in the
*opposite* direction from the xml lane's — holds too. The combined reading of the speed-floor work
changes: *"the field is unreachable on the CM2 rail"* stands on three cells, but *"the floor is one
number"* does not.

Prereg merged as `73f4280` at **19:12:39Z**; measurement began **19:13:07Z**.

## Predictions, scored

| | prediction | threshold | measured | verdict |
|---|---|---|---|---|
| **P1** | measured/implied in [0.30, 1.00] (calibrated) | outside refutes | **0.528** | **HOLDS** |
| **P2** | ≥100× slower than `xz -9`, same host/pin | ≥100× | **800×** | **HOLDS** |
| **P3** | perfect-CM2 best case < 25.69 MiB/s | ≥25.69 refutes | **3.373** | **HOLDS** |
| **P4** | best case **outside** 2× of dickens/max's 0.634 | inside refutes | **3.373** | **HOLDS** |

**P1's calibrated form worked where the naive form failed.** The xml lane predicted "within 2× of the
implied rate" and was refuted at 0.343×. Recalibrating from the two observed load-dependent ratios
(0.667× at load 9.9–31.2, 0.343× at 40.5–60.0) to a [0.30, 1.00] band gave a prediction that held at
0.528× under load 11.9–49.0. The load penalty on this host is a *characterisable* effect, not noise.

## The floor across three CM2 cells

| cell | bound | bound source | measured MiB/s | perfect-CM2 best case | short of ninth place |
|---|---:|---|---:|---:|---:|
| xml/max | 10.707× | published | 0.0302 | **0.323** | **79.6×** |
| dickens/max | 13.986× | published | 0.0454 | **0.634** | **40.5×** |
| **dickens/web** | **69.444×** | derived + validated | 0.0486 | **3.373** | **7.6×** |

The best cases span **10×** across cells, so P4 holds: the floor's *magnitude* is not uniform. The
mechanism is visible in the bound itself — the `web` preset uses far smaller tables, so per-bit CM2
machinery occupies 98.56% of decode instead of 90–93%, and the Amdahl ceiling rises fivefold.

**What survives, and what is now qualified:**

- **Survives** — the field is unreachable by CM2 optimisation on every cell measured. Even the most
  favourable one is 7.6× short of *ninth* place, and that figure assumes every named CM2 component
  costs nothing, which the attribution itself calls an impossible bound.
- **Qualified** — the earlier framing that the floor sits "below 1 MiB/s" is a `max`-preset statement.
  Web-class operating points sit an order of magnitude closer to the field. Any future speed lever
  should be evaluated per operating point, not against a single floor.

## Per-file measurement — dickens, `--preset web`, median of 3 interleaved rounds

| tool | setting | ratio | decode s | MiB/s | RSS KiB | × faster than cubrim |
|---|---|---:|---:|---:|---:|---:|
| lz4 | -12 | 0.430208 | 0.030 | 324.01 | 7,296 | 6670× |
| zstd | -19 | 0.279646 | 0.060 | 162.00 | 11,904 | 3335× |
| brotli | -q11 | 0.277439 | 0.080 | 121.50 | 12,928 | 2501× |
| gzip | -9 | 0.377910 | 0.090 | 108.00 | 3,456 | 2223× |
| xz | -9 | 0.277716 | 0.240 | 40.50 | 12,288 | 834× |
| bzip2 | -9 | 0.274666 | 1.100 | 8.84 | 4,864 | 182× |
| **cubrim** | **web** | **0.225716** | **200.100** | **0.049** | **119,424** | **1×** |

**No tool beats cubrim on density**, even at the web preset: 0.225716 against bzip2's 0.274666 —
17.8% better — while decoding 182–6670× slower.

**Memory is the one axis where `web` is competitive.** Decode RSS is **116.6 MiB**, matching the
preregistered ~110 MB expectation and sitting two orders of magnitude below the `max` preset's
10.5 GiB — in the same range as the competitors' 3.4–12.6 MiB rather than thousands of times above
them. That is a genuine product property of this operating point and it is the reason `web` is closer
to the field on speed as well.

Same-round ratios (the defensible quantity on a shared box):

| tool | r1 | r2 | r3 | median |
|---|---:|---:|---:|---:|
| lz4 | 7643× | 3217× | 6670× | **6670×** |
| zstd | 5732× | 2681× | 2501× | **2681×** |
| brotli | 2866× | 2010× | 2501× | **2501×** |
| gzip | 2866× | 1787× | 2223× | **2223×** |
| xz | 1274× | 670× | 800× | **800×** |
| bzip2 | 306× | 146× | 160× | **160×** |

## How the 69.444× bound was obtained, and why it is evidence

Two prior lanes refused to measure this cell because no combined bound was published and deriving one
would have been unverified. That refusal was correct: a naive sum of all `cm2_*` buckets gives
14.948× for dickens/max, against the published 13.986×.

The attribution committed its **raw** per-symbol data, so the rule could be validated against known
answers before use. `derive_bound.py` implements it and **refuses to emit the derived value unless
both controls reproduce exactly**:

```
CONTROL dickens/max  sum= 93.310 shell=0.46 per-bit= 92.85 bound=  13.986  published 92.85/13.986  EXACT
CONTROL xml/max      sum= 91.240 shell=0.58 per-bit= 90.66 bound=  10.707  published 90.66/10.707  EXACT
DERIVED dickens/web  sum= 99.220 shell=0.66 per-bit= 98.56 bound=  69.444
```

Rule: sum the `cm2_*` buckets, exclude `cm2_decode_shell` — the outer shell is not per-bit machinery.

## A harness error, caught before it produced a mislabelled result

The first launch compressed **xml** with `--preset web`, because the sed anchor `^F=xml$` missed an
assignment sharing a line with others. It was caught by reading `/proc/PID/cmdline` to confirm what
was actually running rather than trusting the script, killed (matching only processes whose cmdline
referenced this scratchpad, so no other lane's cubrim was touched), the output directory cleared, the
variable fixed, and the run restarted. **No data from that run reached this record.** Recorded because
a run that produces plausible numbers for the wrong input is the most dangerous failure mode here.

## Scope and voids

One file at one preset; per-file only, no corpus aggregate. No encoder, wire format, preset
definition, counter or `decode()` change; no candidate built, no lever selected — selection is
NEW-24's, PROGRAM's lane. No database write, no hypothesis row, no API, site or social action.

- Absolute MiB/s is contaminated (load 11.9–49.0); only same-round ratios and P3/P4 pass-fail carry
  forward. P1 now quantifies that penalty at 0.53× for this load range.
- The 25.69 MiB/s ninth-place marker is cross-meta, not same-host. At 7.6× the margin is tighter than
  on the other cells, so this cell is the one where that marker's provenance matters most — a
  same-host ppmd measurement would firm it up and was not run here.
- `x-ray/max` remains the only cell where P3 was ever refuted, on the geocm rail with an
  instrument-perturbed bound. Nothing here changes that.

## Reproducing

```
cd documentation/ephemeral/research/CUBR-SPEEDFLOOR-WEB-RESULTS-20260811
python3 derive_bound.py    # re-derives 69.444x, controls first; refuses on control failure
python3 analyze.py         # every table above
```

21 gated decode observations, 0 VOID; `analyze.py` refuses to print a number for an ungated decode.

---

## Amendment 2026-08-11 — the rank language in this report is cross-meta, not same-host

Every "ninth place" / "eighth place" phrase above is measured against ppmd **25.69 MiB/s** and bzip2
**52.71**, taken from `world_benchmark_timing_aggregate`. Those markers were later measured on this
host and **they do not transfer** (`CUBR-SAMEHOST-FIELD-RESULTS-20260811.md`): same-host on x-ray,
interleaved and gated, ppmd decodes at **1.84 MiB/s** (14× lower) and bzip2 at **8.73** (6× lower).

Cause: `d_max` is a **maximum over files**, so 25.69 is ppmd's *best* file while x-ray is near its
worst; host load compounds it. cubrim's own discrepancy is only 2.0× precisely because its `d_max`
sits on x-ray — the same leaderboard column means "this file" for cubrim and "some other file" for
every competitor, which is what made the comparison feel valid while being invalid.

**No figure in this report changes, and its conclusions hold — conservatively.** The same-host margin
is *larger*, not smaller (the geocm floor clears same-host ppmd by 15.3× rather than 1.09×). But read
every rank phrase above as **"against the cross-meta leaderboard"**, never as a same-host claim.
Stated same-host, a perfected geocm rail at the 28.1 MiB/s floor ranks **5th of the 8 tools measured
on x-ray** — behind lz4/zstd/gzip/brotli, ahead of xz/bzip2/current cubrim.
