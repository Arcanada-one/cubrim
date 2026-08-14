# CUBR-0075 Bounded-State / Allocation Telemetry — Result

Status: measured, locally independently validated, not database-published
Scope: CUBR-0075 `bounded-state` hypothesis only
Date: 2026-08-14 UTC

This report records the valid internal measurement. It does not close
CUBR-0075 as a whole, does not reinterpret the profile-tradeoff result, and
does not authorize public or upstream action.

## Provenance and host

- Cubrim source: branch commit `85b31fc5190167155817a7b21b1ae1ff7224567f`.
- Probe binary SHA-256:
  `32e69b91d0380c905ae3a0c09140483864a421b6d65c24738d84db57b39d46b7`.
- Probe source SHA-256:
  `4b13513eb9965c506d346e92d0276e0c83ebed26292c65646bfee0e86ef20c2d`.
- Runner SHA-256:
  `9767b08686d3ab1abf2b969d66b530c873ec150844348436dfcdf9b2a9f0735f`.
- Canonical manifest SHA-256:
  `43474bfc8fafe7cba96b4843a1700141c49b29f0cda5711861a11f654923f9d5`.
- Frozen preregistration SHA-256:
  `efc7a171d2f52296a7b32a677a00e0ee817a18153af0e0b50d0cf85be1873e90`.
- Bundle SHA-256:
  `a49d6ad8f191828aaf5040bc172895dec49a4faaa79f81a00735e04446e6ea66`.
- Journal SHA-256:
  `36d7264317d8dc3cc2d5595692965489a7b831f9b2944b03109cf1cd6add9e21`.
- First-attempt clean-tree void journal SHA-256:
  `8be7f77bc5ec750edf6c64ee24e35a993161acb6749ec0597e6988596fefb187`.

The run executed on Aether (`dev-ai`, x86_64 EPYC host) with effective
affinity `[0]`. Admission passed before and after the probe: load per CPU was
`0.01840972900390625`, maximum sampled temperature was `53.85 C`, and the
host reported 64 logical CPUs. The first attempt was voided before execution
because an exact copied probe remained as an untracked file at the worktree
root; it was removed, the tree was rechecked clean, and the valid run used a
fresh evidence directory and a corrected host-provenance binding. The void is
not part of the measured bundle.

## Frozen protocol and integrity

The probe ran the canonical 13 samples for both static and dynamic Web Profile
frames, with three warmups and 30 measured trials per sample/profile, seed
`75075`, 65,536-byte blocks/chunks, and 780 valid trial cells. Every trial
passed the native stream finish/checksum path, SHA-256 verification, and
byte-for-byte decoded-output comparison. There were zero round-trip failures.

The counting allocator was reset immediately before each native stream handle
was created. It recorded successful allocation/reallocation/deallocation
events, peak live bytes relative to the trial baseline, and the largest
requested allocation. The probe also recorded the decoder's conservative
`cbm_stream_memory_usage` peak. The reported auxiliary value is that decoder
capacity upper bound minus known frame-input bytes and declared output bytes,
saturating at zero; its ratio is divided by frame-input bytes. It is not kernel
RSS, allocator arena-page usage, or a timing measurement.

## Measurement

| profile | maximum largest allocation | maximum decoder-retained peak | maximum peak live delta | maximum auxiliary ratio |
| --- | ---: | ---: | ---: | ---: |
| static | `320,976 B` | `1,708,973 B` | `661,381 B` | `681.9358151476251` |
| dynamic | `320,976 B` | `1,713,445 B` | `665,853 B` | `657.460396039604` |

Across both profiles there were `73,200` allocation events. The largest
post-drop live delta was `64 B`; this is the allocator baseline-delta scope,
not a claim that the process has no retained RSS. The largest allocation is
below the registered GO ceiling but above the registered WIN ceiling. The
auxiliary ratio is above its GO ceiling in both profiles.

## Frozen decision

The bounded-state result is `NO_GO`:

- allocation WIN (`<= 65,536 B`): not satisfied;
- allocation GO (`<= 4,194,304 B`): satisfied;
- auxiliary-memory GO (`<= 1`): not satisfied, with overall maximum
  `681.9358151476251`.

This is a valid negative for the registered conservative capacity metric. It
does not prove that the decoder leaks, does not establish a kernel-RSS limit,
and does not identify a timing regression. The ratio is intentionally
conservative because the existing ABI reports retained capacity plus its
fixed decoder allowance; the operands are persisted in every raw trial so a
future narrower attribution can be compared without relabeling this result.

## Evidence and boundaries

Local retained evidence is under
`/home/dev/evidence/CUBR-0075-ALLOCATOR-TELEMETRY-20260814/`:
`allocator-telemetry.json` and `journal.jsonl`. The local runner independently
validated schema, provenance, 780-cell cardinality, counter invariants, exact
round trips, raw-row summary derivation, and the decision after the Aether
copy was read back.

This measurement did not write API or database rows. The `allocator-telemetry`
dependency remains a measured internal negative only until its publication
contract is deliberately wired to the existing guarded writer. ARM silicon,
streaming first-output performance, independent-block behavior, density/WIN,
and the remaining CUBR-0075/CUBR-0072 lanes remain separate. No public or
upstream action was taken.
