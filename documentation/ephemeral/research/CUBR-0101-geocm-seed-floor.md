# CUBR-0101 — GeoCM is reachable after all, and it cost no committed bytes

**Closed. The gap was a size threshold, not a data-shape problem, and the fix is two
characters of payload geometry.**

CUBR-0099 measured that the hostile-input fuzz corpus never reached `MODE_GEOCM`: 0 of
288 encodes, across 18 payloads including two written specifically for the geometric
models and all ten committed corpus fixtures. CUBR-0101 inherited that with a DoD
framed around committing an image fixture — a repository-weight decision, since the
only known GeoCM winners were `mr` (9.97 MB) and `x-ray` (8.47 MB).

That framing was wrong, and cheaply disprovable.

## The floor, measured on real data

`examples/geocm_floor` encodes increasing prefixes of a file known to select GeoCM
and reports the winning container mode per prefix. On `x-ray`:

| prefix | mode | archive | round-trip |
|---:|---|---:|---|
| 32,768 B | 16 `CM2` | 15,832 B | OK |
| **65,536 B** | **16 `CM2`** | 31,046 B | OK |
| **69,632 B** | **17 `GEOCM`** | 32,315 B | OK |
| 73,728 B | 17 `GEOCM` | 34,104 B | OK |
| 81,920 B | 17 `GEOCM` | 37,785 B | OK |
| 106,496 B | 17 `GEOCM` | 49,256 B | OK |
| 131,072 B | 17 `GEOCM` | 60,459 B | OK |

**The floor sits between 65,536 and 69,632 bytes** — immediately above the
single-block cube ceiling, which `header.rs` documents as ≤ 65,536. GeoCM only becomes
competitive once the input clears that ceiling and the chunked path engages. Below it,
no amount of image-likeness helps.

Prefixes rather than downscaled images on purpose: a prefix of a real radiograph is
still real radiograph data, so a negative result could not have been blamed on
synthesis.

## Why CUBR-0099's synthetic images failed, and why that was invisible

Both were **256 × 256 = 65,536 bytes** — sitting exactly on the ceiling, on the losing
side. Their *shape* was never tested, because their *size* disqualified them first. A
negative result at one size was read as a fact about the payload class.

`examples/geocm_synth` settles it by holding shape constant and varying size:

| shape | dimensions | bytes | mode |
|---|---|---:|---|
| smooth | 256×256 | 65,536 | 16 `CM2` |
| **smooth** | **256×512** | **131,072** | **17 `GEOCM`** |
| smooth | 512×512 | 262,144 | 17 `GEOCM` |

**A generated image above the ceiling wins GeoCM.** So no fixture is needed, no corpus
data is redistributed, and the repository gains no binary weight.

## The fix, and the histogram that proves it

`gen_fuzz_seeds`'s two image payloads changed from 256×256 to 256×512. That is the
entire change. Before and after, from the generator's own output:

<!-- gate:literal -->
```
before:  mode 0 CUBE 4 | mode 1 RAW 7 | mode 16 CM2 11
         NOTE: no seed reaches mode 17 (GEOCM)

after:   mode 0 CUBE 8 | mode 1 RAW 8 | mode 7 MED16 1 | mode 16 CM2 10 | mode 17 GEOCM 1
```
<!-- /gate:literal -->

`MODE_GEOCM` is now seeded, and `MODE_MED16` came along unbidden — a fifth container
the fuzzer had never started inside either, and one nobody had noticed was missing
because nothing was counting. Distinct seeds went 22 → 28; the corpus originally held
5.

## What this does not claim

The fuzzer now *starts* inside GeoCM. Whether libFuzzer's mutations stay inside it, and
what coverage accumulates over a real campaign, is a different question that needs a
real campaign to answer — the histogram measures the seed corpus, not the fuzzing run.

`MODE_RECORDCM` (13) and the remaining containers are still unseeded. The same method
applies to them: find a real input that selects the mode, bisect for the floor, check
whether a generated payload clears it. Not done here, and not implied.

## Method note worth keeping

The whole result came from reading **one byte** — byte 5 of each blob is the container
mode. No coverage instrumentation, no profiler, no ambiguity about what "reached"
means. When a question is "which branch did this take", it is worth checking whether
the artefact already says so on its face before building machinery to find out.
