# H-50 — ALP-RD (real-double bit-split) on raw float64: NO-GO (sub-byte separation loses to the byte backend)

**Status:** NO-GO (spike, no Rust). On CORPUS 2 (real UCI Superconductivity float64 .npy),
ALP-RD and every sub-byte separation are 1.7–2.5× **larger** than zstd-19 — the data is
low-precision (zstd-compressible), not full-entropy doubles, so bitpacking the "random"
low mantissa raw discards structure the backend already exploits.

**Class targeted:** raw IEEE-754 float64 arrays (sci/ML, sklearn StandardScaler output).
CORPUS 2 PRIMARY = `supercond_features_zscore_f64.npy` (2600×82, 0.000 % short-decimal).

## Spike (faithful, charged — `probe_h50_alprd.py`)

ALP-RD per column: split each `uint64(double)` into left = `bits>>R` (8-entry dictionary +
exception list) and right = low `R` bits (bitpacked raw). Best R per column; left-index
charged at its order-0 entropy (what a real rANS reaches); dictionary + exception list +
per-column header all charged (Gotcha #7). Also tested the simpler sub-byte separations
(byte-plane shuffle; column-transpose + shuffle). Compared to zstd-19 / xz-9 on the raw
double bytes; gate = ≥1.5× vs zstd-19.

| variant (PRIMARY z-score, zstd-19 = 570610, xz-9 = 564984, cubrim = 559656) | bytes | ×/zstd | gate |
|---|---:|---:|---|
| byte-plane shuffle | 967174 | 0.59× | ❌ |
| column-transpose + shuffle | 1030251 | 0.55× | ❌ |
| **ALP-RD (charged, right-raw, exc 1.7 %)** | 1433724 | **0.398×** | ❌ |
| CONTRAST array (raw, 24.9 % decimal): best sub-byte | — | 0.60× | ❌ |

Every sub-byte / bit separation is **1.7–2.5× larger** than zstd-19, consistently on both
arrays. (cubrim already **beats** zstd on the raw doubles: 559656 vs 570610 = −1.9 %, no
transform.)

## Why NO-GO (mechanism — refines Gotcha #11)

ALP-RD assumes the low mantissa is **random** → bitpack it raw (R bits/value). But these
doubles come from **low-precision measurements** (UCI source CSV is ~7 decimal digits ≈
23-bit precision; z-score is arithmetic of low-precision inputs), so the low mantissa is
**not random** — it carries structure that zstd/xz/cubrim entropy-code to ~21 bits/value.
Separating bytes/bits and bitpacking the right part RAW (~50 bits/value) **throws away the
cross-byte/limited-precision structure the backend already exploits** → a 1.7–2.5× net loss.

The brief's premise ("0.000 % short-decimal → full-double slack") measured the wrong thing:
0 % short-decimal means the **decimal trick** (×10^e, H-40) does not apply — it does NOT mean
the mantissa is full-entropy. The "random low-bit slack" ALP-RD targets is simply not present
in real measurement data stored as float64; the byte backend already captures it. ALP's
literature ×4.3 is on **full-entropy scientific doubles** (full-precision computation), a
different data property. "right = random → bitpack raw" is itself a subsumption trap when the
data is low-precision (Gotcha #11: spike through the real backend; don't assume incompressibility).

## Verdict

**NO-GO** (gate ≥1.5× vs zstd-19 not met; ALP-RD 0.398×, best sub-byte 0.59×). No Rust;
codec byte-identical. Sub-byte field separation is decisively counter-productive on this
real float64 corpus because the data is low-precision, not full-entropy. Next: H-49-reborn
on CORPUS 1 (non-temporal wide deterministic tables — covtype before adult).

**Code SHA:** spike on `6326cd7` (codec untouched). Leaderboard untouched, NOT pushed.
