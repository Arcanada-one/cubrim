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

## Interpretation and boundary

The next bounded hypothesis, if the programme chooses to examine one, is the model
state work in `update_bit` and `predict_bit`, not container framing, allocation
telemetry, or the range coder’s `get_freq`/`decode` calls. This result does not
authorize an optimization patch. The first-slice Amdahl limit and the possibility of a
distinct web decode path remain separate decisions.

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
