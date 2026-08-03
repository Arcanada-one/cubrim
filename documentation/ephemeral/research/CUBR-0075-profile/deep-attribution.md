# CUBR-0075 — Decode Attribution, Deep Slice

Status: `COMPLETE` for the verdict-authorized per-operation attribution slice. This
narrows the measured hotspot; it is not an optimization, evaluation, or release
verdict.

## Result

The runner produced **792 observations**: three warmups plus 30 measured trials for
each of 12 samples in both affinity modes. Every observation was byte-exact
(`792/792`). Eleven CM2 samples supplied 660 measured observations with six
applicable substages; the raw-store WOFF2 sample supplied 60 observations with all
six substages explicitly inapplicable.

Within the fixed-core CM2 detail run, the dominant operations are:

- `transforms.update_bit`: **48.6911%** of detailed substage cycles;
- `entropy.predict_bit`: **46.9106%**;
- `transforms.start_byte` plus `transforms.end_byte`: **2.4210%**;
- `entropy.range_get_freq` plus `entropy.range_decode`: **1.9772%**.

The call counts explain the suspicious scale in the verdict. Each CM2 output byte has
one `start_byte` call, eight `predict_bit` calls, eight `range_get_freq` calls, eight
`range_decode` calls, eight `update_bit` calls, and one `end_byte` call. Across the
660 measured CM2 observations this is 56,504,760 byte-start/end calls and 452,038,080
calls for each bit-level operation.

## Fixed-core operation attribution

The cycle columns below cover the 330 fixed-core CM2 measured observations. The
per-byte denominator is 28,252,380 applicable CM2 output bytes; raw-store output is
excluded from that denominator. The all-CM2 call column covers both affinity modes.

| Operation | CM2 calls, both modes | Fixed-core cycles | Detailed-cycle share | Fixed-core cycles/CM2 output byte |
|---|---:|---:|---:|---:|
| transforms.start_byte | 56,504,760 | 10,395,079,136 | 0.8259% | 367.936 |
| entropy.predict_bit | 452,038,080 | 590,417,114,586 | 46.9106% | 20,897.960 |
| entropy.range_get_freq | 452,038,080 | 11,645,053,898 | 0.9252% | 412.180 |
| entropy.range_decode | 452,038,080 | 13,240,202,532 | 1.0520% | 468.640 |
| transforms.update_bit | 452,038,080 | 612,826,242,440 | 48.6911% | 21,691.137 |
| transforms.end_byte | 56,504,760 | 20,075,876,020 | 1.5951% | 710.591 |
| **detail total** | **1,921,161,840** | **1,258,599,568,612** | **100.0000%** | **44,548.444** |

The operation timing includes the opt-in counter boundary and is therefore a detail-run
attribution, not a directly comparable replacement for the first-slice aggregate
throughput number. It is valid for locating relative work inside this run. Across the
11 CM2 samples, the fixed-core transform-operation share ranged from 50.45% to 53.50%,
and the entropy-operation share ranged from 46.50% to 49.55%; the dominant split is
structural rather than isolated to one content sample.

## Mixer shape and the model-count answer

The source-level answer is exact, but it is not a per-model timing measurement. In
`code/cubrim-rs/src/cm2.rs`, the default CM2 predictor has **26 underlying providers**:
23 adaptive counter providers (12 order, 6 sparse, 1 indirect, and 4 word) plus 3
match providers. The 23 counter providers each emit a stationary and a state-map
prediction, so the mixer receives **49 learned model inputs**. `NIN` is therefore
**50** after adding the bias input.

Each bit then runs five layer-1 mixers, each over those 50 slots, followed by a layer-2
mixer over the five layer-1 outputs plus its bias. That is **`5 × 50 + 6 = 256`
dot-product input terms per bit**, before counting the counter lookups, match prediction,
and APM work. The requested bookkeeping quotient is therefore about **2,600 / 49 ≈
53 cycles per learned input** for either profiled function (52.1 for `predict_bit`,
53.9 for `update_bit`). It is not an isolated per-model cost: every learned input is
consumed by five layer-1 mixers, and the measured function boundaries also include
state and adaptation work.

This resolves the cardinality question without guessing about cache misses or vector
arithmetic. The profile shows a deliberately broad model design repeated through five
context views; a follow-on implementation study would still need isolated counters or
hardware measurements to split that work into lookup, dot-product, and adaptation cost.

## Split correction

The direct split measurement supersedes the earlier **10.0 cycles per dot-product term**
reading. The isolated dot-product boundary is **1,033.4 / 256 = 4.04 cycles per term**;
the earlier figure conflated dot products with lookup and adaptation work. The measured
normalized costs are **30.5 cycles per learned input** for lookup and **56.1 cycles per
learned input** for adaptation. The split therefore puts the dominant cost in adaptation
(52.09%), followed by counter/state lookup (28.34%); dot products are 19.57%.

The split Amdahl ceiling is:

| eliminated work | maximum speedup |
|---|---:|
| all dot products | **1.24×** |
| all counter/state lookup | **1.40×** |
| all adaptation | **2.09×** |
| all model work | **22.52×** |
| required decode-gate speedup | **227×** |

No single split exceeds 2.09×, and the full model ceiling remains far below 227×.
The archival opportunity remains worth pursuing; the web claim requires a different
decode path, so CUBR-0076 `web-profile-prototype` remains mandatory.

## Amdahl ceiling and the web-path decision

The all-mode deep evidence totals **2,456,882,895,434 detailed substage cycles**. The
two model functions account for **2,347,672,381,936 cycles**, or **95.5549%** of that
total (displayed as 95.56% in the verdict table). The rounded Amdahl arithmetic is:

| eliminated work | maximum speedup |
|---|---:|
| `transforms.update_bit` (48.61%) | **1.95×** |
| `entropy.predict_bit` (46.95%) | **1.89×** |
| both model functions (95.56%) | **22.52×** |

The unrounded total gives a 22.50× ceiling; using the displayed verdict numbers gives
`1 / (1 - 0.9556) = 22.52×`. Against the **227×** speedup required by the decode gate,
`227 / 22.52 = 10.08×` of the gap remains even after deleting both model functions.
Therefore **the 0.50 gate is not reachable by optimising this decoder; it requires a
different decode path for the web profile**.

That does not make model work pointless. A 10–20× model improvement would still be a
major archival-product result, where Cubrim already leads on ratio. It cannot rescue the
web claim; archival throughput and the web operating point are separate products.

## Decoder memory-vs-compute transfer

The required CUBR-0087 F10 findings include decoder rows, not only encoder rows. On a
quiet host with the same 8-core pin and a 2 MiB `dickens` slice, native decode measured
**27.0 s / 1.47 GiB**, while `tbits=22` measured **25.0 s / 0.40 GiB**. That is a
**3.7× smaller decoder working set for about 8% more decode throughput**; `tbits=20`
went to **23.5 s / 0.109 GiB**. Every row round-tripped exactly.

This is the controlled transfer check the hotspot requested: the encoder's M3 result
does transfer to decode on this slice. Shrinking the tables dramatically changes RSS
but changes decode time only modestly, so memory latency is a secondary term and the
mixer's compute work remains dominant. The scope is the measured pinned 2 MiB slice;
it is not a corpus-wide throughput claim, and it does not replace hardware-counter
work if the programme later needs a cache-versus-arithmetic decomposition.

## Roadmap consequence

- **CUBR-0076 `web-profile-prototype` (dependency 12) is mandatory**, not optional: the
  current decoder cannot reach the web gate even with a zero-cost model.
- **`simd-decode-build` (dependency 15) is insufficient alone.** SIMD may still be a
  worthwhile archival-product investigation, but it cannot bridge a 22.5× ceiling to a
  227× requirement.
- **`table-driven-entropy-build` (dependency 13) is a measured negative on this path.**
  `range_get_freq` plus `range_decode` is only about 2.01% of detailed substage cycles;
  making it free has a maximum effect of about 1.02×.

Three of the eleven registered directions are now resolved negatively by the two
profiling runs: framing/container (14), allocator telemetry (8), and table-driven
entropy (13). The ledger's existence was useful; the measured directions are what
should control the next route.

## Interpretation and boundary

The bounded archival hypothesis is model state and mixer work in `update_bit` and
`predict_bit`, not container framing, allocation telemetry, or the range coder's
`get_freq`/`decode` calls. This result does not authorize an optimization patch. The web
route is a separate decode-path decision, now mandatory under dependency 12.

The measured negatives are recorded in
[`dependency-negatives.md`](dependency-negatives.md) and machine-readable form in
[`dependency-negatives.json`](dependency-negatives.json): framing/container work is
196,008 cycles across 720 measured observations, and allocation is 8,942,160,152
cycles across 90,480 calls with zero retained-state delta in all 792 observations.
The first-slice [`attribution.md`](attribution.md) and [`attribution.json`](attribution.json)
remain unchanged.

## Provenance

- Corpus: `bench/web-corpus/manifest.v2.json`; manifest SHA-256
  `fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf`.
- Protocol: release mode, 3 warmups plus 30 measured trials, 12 samples, one-core
  and fixed-core modes; fixed-core uses `taskset --cpu-list 0`.
- Host: `arcana-devs`, Linux 6.8.0-124-generic, x86_64, 16 CPUs; cycle source
  `rdtsc-x86_64`.
- Source commit: `6209d282891023c9571bfd223a23f63b7dcaae65`.
- Encoder binary SHA-256:
  `d168e7f0110179e4e73a16a3cbd48816be893b34e630258b449dbe28c16a93bd`.
- Profile binary SHA-256:
  `57ec2944aa363ad6b15a0619829b04d061ca5efc655a9e60bbe9ea65c509bc37`.
- Raw evidence: [`deep-attribution.json`](deep-attribution.json).
- Database evaluation/evidence rows written: `0`; pending hypotheses advanced: `0`.

## Split-profile pickup

Branch `codex/cubr-0075-profile`, HEAD `d3c345c`; source SHA
`d3c345cb8be7baf4abb77a471e402d4bad0893e3`; profile binary SHA
`7b1d1f786885c3f2866d84c7e3895d5d85aff966578be9bbbf08c0fd0fd46d04`; encoder
binary SHA `144684151ba90deb8bcad0c659f78a9dc40941eb7d8cbb4b18534cf931c2ec03`;
manifest SHA `fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf`.
Pushed evidence commit: local `89658fdde8c3d9d6d1cf90137749b1d736129d8c`;
remote `refs/heads/codex/cubr-0075-profile` confirmed at the same SHA.
The split run measured counter/state lookup, mixer dot products, and adaptation
boundaries inside the CM2 model across the full web corpus. Next question: is
adaptation's 56.1 cycles per learned input a cache problem or an algorithmic one?
Exact relaunch command:

```text
python3 bench/web-benchmark/profile_decode.py --profile-binary code/cubrim-rs/target/release/cubrim-decode-profile --encoder-binary code/cubrim-rs/target/release/cubrim --output documentation/ephemeral/research/CUBR-0075-profile/split-attribution.json
```
