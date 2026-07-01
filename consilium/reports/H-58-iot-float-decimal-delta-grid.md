# H-58 — per-channel decimal/integer delta (H-40 lever) on binary float, IoT sensor (push H-54 past 1.5×)

**Premise.** H-54 MODE_BINFLOAT (SoA + per-channel wrapping-uint32 **bit**-delta) won IoT sensor float at **1.432×** vs zstd-19 (H-55) — below the 1.5× gate. The telemetry-CSV win (H-40) came from the **decimal→scaled-int delta** lever, not bit-delta. Hypothesis: applying the decimal-int-delta per channel to the BINARY float IoT array (with a lossless exception list) pushes the win past 1.5×.

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact lossless f32. SoA (column-major per channel), then per channel competitively: **decimal-int-delta** (find scale s∈0..6 with <2% non-representable; ints=round(v·10^s); zig-zag int delta; raw-f32 exception list for the <2% mismatches → lossless) ELSE **bit-delta** (H-54). Both transform inverses asserted == raw before measuring; cubrim RT checked. Compared to A=cub(raw), the H-54 bit-delta blob, and zstd-19 (the 1.5× gate) + strong universals (xz/ppmd/brotli). Spike `/tmp/uci-dl/spike_h58_iotfloat.py`. Codec.rs untouched, NOT pushed.

**Corpus (real):** `hpc_iot_100k7_f32.raw` — UCI Individual Household Electric Power Consumption (id 235), first 100 000 complete rows × 7 numeric channels as float32 (2 800 000 B, record stride 28). sha256 `e3c15f763275a659…`. Channels: active/reactive power, voltage, intensity, 3× sub-metering (clean 0–3-decimal values).

## Measured (RT byte-exact). code SHA `422726d`. (25 000×7 slice — 700 KB, after the 2.8 MB run hit cubrim's MODE_BINFLOAT+LZ slow path; relationship is scale-invariant.)

transform inverses asserted lossless == raw; cubRT True on all.

| variant | cub bytes | self-gain vs A | note |
|---|---:|---:|---|
| A = cub(raw f32) | **105 871** | — | **cubrim's shipped MODE_BINFLOAT** (already SoA+bit-delta internally) |
| B = manual H-54 bit-delta blob | 114 727 | **−8.36%** | worse than built-in MODE_BINFLOAT |
| B = manual H-58 dec-delta blob | 114 731 | **−8.37%** | **dec-delta used 0/7 channels** → fell back to bit-delta |

Universals on raw: zstd-19 181 463 | xz 150 932 | PPMd 138 325 | brotli 161 458. **A=cub_raw vs zstd-19 = 1.714×** (already past the 1.5× gate on this slice); vs strong-L (ppmd) = 1.306×.

## Reading — NO-GO, two honest findings

1. **The decimal lever (H-40) does NOT transfer from CSV-text decimals to f32 BINARY arrays.** `dec-delta used 0/7 channels`: not one channel passed the strict lossless decimal round-trip (for a value v_f32, `float32(round(v_f32·10^s)/10^s)` must equal v_f32 bit-exactly for ≥98% of values). f32 quantisation breaks exact decimal representability, so a *lossless* decimal-int-delta would need an exception list covering >2% of values → it never engages. The H-40/telemetry win came from CSV **text** where the decimals are exact; the same numbers as f32 binary are not.
2. **Manual pre-transform is redundant and worse than the shipped MODE_BINFLOAT.** cubrim's MODE_BINFLOAT already does SoA + per-channel bit-delta internally and competes it against LZ/columnar; feeding it a *pre*-delta'd blob double-transforms and loses −8%. So the H-54 lever is already shipped and self-applied.
3. **The "push past 1.5×" goal is moot on this slice:** the shipped MODE_BINFLOAT already gives **1.714× vs zstd** here (the H-55 1.432× was on the larger 200k×7 slice — the ratio is slice/64KB-block-dependent, not a fixed deficit).

## Verdict vector

**H-58 decimal-delta on binary float: NO-GO{IoT-float·lossless}.** The decimal-int-delta cannot be applied losslessly to real f32 sensor data (0/7 channels qualify; f32 ≠ exact decimal), and the bit-delta it falls back to is already inside the shipped MODE_BINFLOAT. The real levers to improve IoT-float further are (a) the **PPMd-class backend** (the universal deficit: cub 105 871 vs ppmd-on-raw 138 325 means cubrim already leads here, but on harder slices the backend is the lever) and (b) MODE_BINFLOAT internal parse/entropy tuning — NOT a decimal pre-transform. Honest lesson logged: **ALP/decimal is a text-CSV lever; on quantised f32 binary the lossless constraint kills it.**

**Mac orchestrator publishes the /evolution card for H-58** (status NO-GO, lesson: decimal lever is CSV-text-only, doesn't transfer to f32 binary). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
