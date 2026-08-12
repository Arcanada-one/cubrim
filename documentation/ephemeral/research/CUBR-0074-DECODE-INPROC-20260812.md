# CUBR-0074 — the decode gate, measured properly: FAILED at 0.36

**Status:** the gate Phase B recorded as UNMEASURABLE is now measurable, and the
answer is **FAIL**. The subprocess bundle had reported it **passed**.

Evidence: `CUBR-0074-DECODE-INPROC-20260812/decode-throughput.json`.

## What changed

Phase B (2026-08-12, PR #175) reported `decode_throughput_vs_brotli5 = 0.9764`
against a `>= 0.50` bar. That was an artefact: the five-metric protocol times a
subprocess per trial, every codec sat on a 3.5–4.1 ms floor of process spawn,
and the decode work was a sliver inside it. Every ratio was dragged toward 1.0,
so a decoder ten times slower would also have "passed".

`bench/web-benchmark/decode_throughput.py` removes the floor instead of
subtracting it: each decoder is called in-process, warmed, then timed, with the
output verified byte-exact on every iteration.

## Result

7 rounds × 30 repeats over a seeded randomized cell order = **210 observations
per cell**, 13 samples, corpus v3.

| codec | min MB/s | median MB/s | measured through |
|---|---|---|---|
| zstd-3 | 1540.8 | 925.4 | `libzstd.so.1.5.5` |
| zstd-19 | 1474.5 | 926.3 | `libzstd.so.1.5.5` |
| brotli-5 | 735.5 | 489.2 | `libbrotlidec.so.1.1.0` |
| brotli-11 | 687.1 | 463.6 | `libbrotlidec.so.1.1.0` |
| gzip-9 (zlib inflate) | 575.4 | 391.4 | zlib |
| **cubrim-web** | **265.0** | **173.5** | `libcubrim_web_decoder.so` (`cbr_decode`) |

```
decode_throughput_vs_brotli5 = 0.3603 (from minima)
                             = 0.3547 (from medians)
                               bar >= 0.50   FAIL
```

**The verdict is robust.** Minimum and median agree to within 0.006, which is
the internal check for whether the host was too noisy to conclude from. Across
four independent runs at host loads from 0.75 to 2.3 per CPU the ratio was
0.338, 0.365, 0.381, 0.360 — the absolute MB/s figures move a great deal with
load, and the ratio barely moves at all. The host was *above* the quiet ceiling
for the recorded run (2.26/CPU, 85 °C) and it does not matter at this margin:
the gate is missed by a factor of 1.4, not by a rounding error.

## Which decoder this is, and why that is the right one

Cubrim-Web is timed through `cbr_decode`, the C ABI the browser calls, in the
standalone reference decoder. That is deliberately **not** `cubrim::decode` in
the main crate, which the native harness has measured at 443 MB/s on a quiet
host. Those are two independent implementations of one wire format, and the one
that ships to browsers is the reference decoder. A gate whose stated rationale
is "decoding is on the browser critical path" has to be read against the code
the browser runs.

This also resolves a number that never quite fit: CUBR-0077 measured 99.1 MB/s
in Chromium against 443 MB/s "native", a 22% ratio that looked worse than WASM
usually costs. Against the reference decoder's native 265 MB/s it is ~37%,
which is an ordinary WASM penalty. The gap was never the browser; it was the
comparison.

## Both preregistered gates now fail

| criterion | bar | measured | verdict |
|---|---|---|---|
| `ratio_vs_brotli11` | ≤ 1.00 | 1.1163 | **FAIL** |
| `decode_throughput_vs_brotli5` | ≥ 0.50 | 0.3603 | **FAIL** |

The density result was already known and is unchanged. The decode result is
new, and it inverts what the harness said a day earlier. Density was described
in every prior round as "the only bar left between the profile and a WIN" — that
is no longer true. The profile is short on both axes it was measured against,
and the second one was hidden by an instrument that could not see it.

## Method notes worth carrying

1. **Time the decoder, not the binding.** The first version of this module
   timed `decode()` together with marshalling the output into Python bytes.
   `bytes(ctypes_array[:n])` converts element by element while `string_at` is a
   memcpy, so it reported Cubrim-Web at **10.4× brotli-5**. The implausible
   direction is what exposed it; a subtler error in the same place would have
   been believed.
2. **Randomize the schedule even in-process.** Measuring every cell of one
   codec before starting the next lets a load change land entirely on whichever
   codec is in flight. Rounds over a shuffled cell order, per-cell minimum.
3. **Record admission with the number, do not merely gate on it.** A figure
   without its load and temperature cannot be judged later, and a ratio can be
   sound on a host where an absolute throughput is not.
4. **Keep provenance when changing instrument.** The incumbents are timed
   through the same shared libraries their pinned CLIs wrap, at matching
   versions, with each library's path, size and SHA-256 in the report — the
   resolution improved without the comparability being traded away.
