# CUBR-0099 — do the hostile-input fuzzers reach the CM2 / GeoCM / PPMd decode paths?

**Answered. The task's own premise was wrong in two directions, and the real defect
is one it did not ask about.**

CUBR-0099 was filed out of CUBR-0095 on the reasoning that `decode_hostile` fuzzes
`cubrim::decode()` on arbitrary bytes, that random bytes are unlikely to satisfy a
valid CM2 header by chance, and that "the honest prior is that these paths are NOT
being fuzzed and the green harness is providing false assurance over exactly the
surface that most needs it."

Measured, that prior is wrong about CM2, moot about PPMd, and right about GeoCM.

## Method

Container mode is byte 5 of every blob (`[MAGIC 4][VERSION 1][MODE 1]`), so seed
reachability is decidable by reading one byte per seed — no coverage instrumentation
needed, and no ambiguity about what "reached" means.

`examples/gen_fuzz_seeds` was rewritten to deduplicate by content hash and to print
the container-mode histogram it actually achieves. That histogram is the deliverable:
it is the only honest statement of which decode paths the fuzzer starts inside, and
it prints on every future run, so this cannot silently rot again.

## Result 1 — CM2 is well seeded. My hypothesis was wrong.

| mode | | seeds |
|---:|---|---:|
| 0 | `CUBE` | 4 |
| 1 | `RAW` | 7 |
| **16** | **`CM2`** | **11** |
| 17 | `GEOCM` | **0** |

Eleven of twenty-two seeds — **half the corpus** — start inside the CM2 decode path.
The concern that motivated the task does not apply to CM2. The reason is that CM2 is
the *competitive winner* on most text-shaped payloads, so any seed generator that
encodes realistic text lands in CM2 whether or not it intended to.

## Result 2 — PPMd is not reachable at all, so the question is void

`ppm_decode` and `ppm_encode` have **zero call sites** anywhere in `src/` outside
`ppmd.rs`. `ppmd_o0_decode` / `ppmd_o0_encode` are `pub(crate)` and referenced only
by a single test at `ppmd.rs:1109`. There is no `MODE_PPMD` in `header.rs`.

So there is no PPMd decode path reachable from `cubrim::decode()` to fuzz. That third
of CUBR-0099's scope is **moot rather than unmet** — the honest close, not a pass.
(Whether the module should stay is a separate question; `611bad4` shows the project
has made CM2 dead code explicit before.)

## Result 3 — GeoCM is genuinely unreachable from anything in this repo

**0 of 288 encodes produced mode 17**, across 18 distinct payloads:

- eight synthetic shapes, including **two written specifically to suit the geometric
  models** — a smooth 2D field `((x²+y²)/512)` with mild noise, and a banded gradient
  with horizontal structure;
- all **ten committed corpus fixtures** (`documentation/ephemeral/research/corpus/*.bin`),
  which are real recorded data, tracked in git since CUBR-0094, and already used by the
  crate's own round-trip tests.

Both image payloads lose the competitive pick to CM2. This is consistent with the
NEW-24 campaign's control archives, where `mode 17` appears on exactly one corpus
file — `mr`, a 9.97 MB Silesia image — and nothing of that character exists in this
repository.

**Conclusion: GeoCM cannot be seeded from material currently in the tree.** Closing it
needs a committed image-like fixture large and real enough for GeoCM to win, which is
a deliberate decision about repository weight, not something to smuggle in here.

## Result 4 — the finding nobody asked for: the corpus was 5 files wearing 64

The previous generator looped 4 payloads × 8 `ValueScheme`s × 2 square-limit settings
and wrote 64 files, documented as giving "one valid stream per value scheme".

Those 64 files contained **5 distinct byte sequences.**

`value_scheme` is not honoured through `encode_with_config` — the competitive rail
picks the winner and overrides the request — so the per-scheme loop wrote the same
bytes eight or sixteen times over. libFuzzer would have deduplicated them, so nothing
was *broken*; but every reader of that directory, including the file's own header
comment, would have believed the corpus was sixteen times richer than it was.

The knob is **collapsing rather than strictly inert**, which is worth stating
precisely: a probe of all eight scheme requests on one payload yields **2** distinct
blobs, not 1. So the loop is retained — if the rail ever starts honouring the request,
dedup lets the new variants through — and the generator now reports the collapse
instead of hiding it:

```
value_scheme probe: 8 scheme request(s) produced 2 distinct blob(s)
wrote 22 distinct seeds to fuzz/corpus/decode_hostile
suppressed 266 duplicate encodings, 0 non-round-tripping
```

**266 of 288 encodes were duplicates — a 92% collapse rate.** Distinct seeds went from
5 to 22. Mode coverage did not improve (CUBE / RAW / CM2 before and after); what
improved is diversity *within* those modes, and the fact that the number is now
printed rather than assumed.

## What is closed and what is not

| item | state |
|---|---|
| CM2 decode path reached by the seed corpus | **yes — 11 seeds. Closed.** |
| PPMd decode path | **not reachable from `decode()` at all. Void.** |
| GeoCM decode path reached | **no — 0 of 288. Needs a committed image fixture.** |
| Seed-corpus diversity honestly reported | **closed — histogram printed every run** |

The one live remainder is GeoCM, and it is a repository-content decision rather than a
fuzzing one. Recorded here rather than left implicit, because "the fuzzer covers
`decode()`" will otherwise keep being read as "the fuzzer covers every backend behind
`decode()`", and on GeoCM it demonstrably does not.
