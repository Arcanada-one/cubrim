# CUBR-0076 — dynamic Web Profile encoder, implementation readback

**Executed:** 2026-08-14 UTC

**Implementation:** `e6333f7a14ee55aa2b2867d80a6b242ed12976b6`

**Host:** Linux 6.8.0-124-generic, x86_64, 16 logical CPUs

## Delivered slice

The existing static Web Profile encoder remains unchanged: it uses the
256-deep match chain and three shortest-path parse refinement passes. The new
dynamic entry point uses the same `MODE_WEB` version-1 frame, checksum, block
planner, Huffman table writer, and decoder, but uses a bounded 32-deep match
chain and one greedy/lazy seed parse. It is exposed as
`cubrim::encode_web_dynamic(data, block_size)`.

`cubrimd` now uses the dynamic entry point for the request path. The proxy
still compares the resulting frame with identity and sends identity when the
frame is not smaller. Archive callers retain the static
`EncodeConfig::web_profile` path.

No decoder or wire-format change was needed. The reference decoder accepts
the dynamic output because the encoder choice is not represented in the frame;
both modes are conformant `MODE_WEB` producers.

## Real web-census evidence

The 12 samples in `bench/web-corpus/payloads-v2` all round-trip byte-exactly
through the public decoder under the dynamic entry point. With 65,536-byte
streaming blocks:

| observation | result |
|---|---:|
| dynamic frames round-tripped | 12/12 |
| dynamic frames smaller than identity | 12/12 |
| aggregate dynamic frame bytes | 131,565 B |
| aggregate static Web Profile bytes | 120,939 B |

The static and dynamic test commands included decode and test-harness work,
so their wall times are comparative evidence only, not a portable throughput
claim: static `2.75 s`, dynamic `0.39 s` on this host for the corresponding
12-sample tests. The dynamic path is deliberately bounded and trades some
density for request-path latency.

## Verification

- Web unit tests: 21 passed, including dynamic no-block and multi-block
  round-trips plus existing corruption/truncation checks.
- Real-census Web Profile integration tests: 5 passed.
- Scheme round-trip gate: 7 passed.
- Hostile-input gate: 6 passed.
- Reference decoder dynamic differential test: passed; full reference-decoder
  suite: 67 passed.
- `cubrimd` proxy suite: 12 passed, including an assertion that the negotiated
  response bytes are produced by the dynamic entry point.
- `cargo clippy --release --all-targets -- -D warnings` passed for `cubrim`,
  `cubrim-web-decoder`, and `cubrimd`.
- `git diff --check`: zero findings.

The monolithic `cubrim` library test command was also attempted with the
operator's sub-two-minute shell ceiling. It reached pre-existing expensive
CM/chunk/columnar tests and timed out at 105 seconds without a reported test
failure; the relevant suites above were run separately to completion.

This result closes the previously missing dynamic-mode implementation slice.
It does not evaluate the registered hypothesis-12 decode-speed gate, change
the density verdict, write benchmark DB rows, or perform any public/IETF/IANA
action.
