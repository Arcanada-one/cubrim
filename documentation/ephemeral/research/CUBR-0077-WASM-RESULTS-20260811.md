# CUBR-0077 — WASM decoder proof of concept: results

**Date:** 2026-08-11 UTC
**Subject:** `code/cubrim-web-decoder` — the Web Profile reference decoder,
built for `wasm32-unknown-unknown` and driven from a real page.
**Depends on:** CUBR-0076's frame (`MODE_WEB`, container byte 18), merged and
measured (443.39 MB/s native decode at 0.9361 gzip-9 density).

## The recorded blocker was about the wrong thing

`bench/web-corpus/manifest.v2.json` carries this against CUBR-0077:

> Cubrim itself does not yet build for wasm32-unknown-unknown (getrandom
> requires a JS feature), which is CUBR-0077's subject.

True of the **whole crate** — `ureq`, `dirs`, `rpassword`, `walkdir` and `rand`
are CLI and archive dependencies — and irrelevant to a **decoder**, which needs
none of them. The design-around is a separate crate carrying the decoder only,
which is also exactly what the CUBR-0072 / ADR-0003 disclosure split makes
public: wire format, framing, limits, reference DECODER. Nothing encoder-side
is exposed; the crate cannot compress at all.

Two implementations of one format can drift, so drift is prevented
mechanically rather than by discipline — see *Differential equivalence* below.

## What was built

- `code/cubrim-web-decoder/` — the decoder, one dependency (`blake3`, for the
  frame checksum), no `unsafe` in the decode path.
- A hand-written C ABI (`cbr_alloc` / `cbr_decode` / `cbr_out_ptr` / …) instead
  of `wasm-bindgen`: **50,110 bytes** of wasm, no build tooling, ~40 lines of
  JS glue.
- `cubrimDecode(compressed: Uint8Array, maxOutput) -> Uint8Array`, synchronous,
  exactly as AC-2 specifies.
- A demo page that fetches 12 real web assets as `application/cubrim`, decodes
  each in WASM, **verifies every one against the original with SHA-256 before
  reporting any number**, and then uses the results: the stylesheet is applied
  via `adoptedStyleSheets`, the JSON is parsed, the WOFF2 is loaded as a
  `FontFace`.
- `web/serve.mjs` — a static server that serves `.cbr` as
  `Content-Type: application/cubrim` under a strict CSP.

## Measured

All figures byte-exact against the originals; a decode that did not reproduce
its asset is not reported.

| environment | corpus decode | how |
|---|---|---|
| native Rust (`cubrim::decode`) | 443.4 MB/s | prior CUBR-0076 measurement, quiet host, pinned |
| **Chromium headless, WASM** | **99.1 MB/s** | 3 warmups + 25 timed repeats per asset |
| **Node 22 (V8), WASM** | **94.5 MB/s** | 3 warmups + best of 20 per asset |

**Traffic: 965,410 B of content served as 120,939 B — 87.47% less.**
WASM linear memory after decoding all 12 assets: **1,638,400 B (1.6 MiB)**.
Module size: **50,110 B**. JS heap reported by the browser: 29.7 MB (that is
the whole page, not the decoder).

Per asset in Chromium (amortised ms, MB/s):

| asset | served | original | ms | MB/s |
|---|---|---|---|---|
| json-api-large-world-benchmark-v2.json | 18590 | 320976 | 2.112 | 152.0 |
| html-large-web-codec-v2.html | 14428 | 227968 | 1.636 | 139.3 |
| json-api-medium-web-benchmark-v2.json | 9630 | 98948 | 0.776 | 127.5 |
| magic-string.umd.js.map | 19058 | 112594 | 2.020 | 55.7 |
| tailwind.css | 10361 | 65257 | 1.028 | 63.5 |
| magic-string.umd.js | 9375 | 42936 | 0.564 | 76.1 |
| html-medium-home-v2.html | 5563 | 25031 | 0.364 | 68.8 |
| inter-latin.medium.woff2 | 23650 | 23664 | 0.432 | 54.8 |
| sourcemap-codec.umd.js | 3522 | 14590 | 0.260 | 56.1 |
| json-api-small-hypotheses-v2.json | 1558 | 13880 | 0.180 | 77.1 |
| resolve-uri.umd.js | 2797 | 9866 | 0.204 | 48.4 |
| sourcemap-codec.umd.js.map | 2407 | 9700 | 0.164 | 59.1 |

**WASM costs ~4.5x against native** (99.1 vs 443.4 MB/s), on an unoptimised
decoder in both cases. Stated plainly rather than buried: this is the price of
the sandbox plus the JS boundary copy, and it is still 2x the hypothesis-12 GO
bar that the whole web track was gated on.

### A measurement trap worth recording

The first browser run reported **0 ms for everything**. Chromium was launched
with `--virtual-time-budget`, which freezes `performance.now()` during
synchronous work — so a naive harness would have published an infinite MB/s or,
worse, a plausible-looking number. The second attempt, on the real clock,
produced quantised times (3 ms, 0.8 ms…) because browsers deliberately coarsen
`performance.now()`. Only the third form — warm up, time 25 decodes, divide —
measures anything real at these asset sizes. The demo does that and says so in
its own output.

## Differential equivalence (the anti-drift mechanism)

`tests/differential.rs`, 6 tests, all green:

- every census sample decoded by **both** this decoder and `cubrim::decode` —
  byte-identical, and byte-identical to the original;
- synthetic shapes the census may not cover: overlapping run-length matches,
  all-literal streams, every byte value, lengths 1..511;
- **4,000 single-bit mutants**: both decoders must agree on *validity*, and on
  output when both accept. A silent divergence fails the test;
- 3,000 random frames wearing a valid header — no panic;
- truncation at **every** offset of a valid frame fails closed;
- a frame declaring `u32::MAX` output is refused before allocation.

This is now a CI job (`.github/workflows/ci.yml` → *Web Profile reference
decoder*), so a future change to the frame in `cubrim` that is not mirrored
here turns CI red instead of shipping two incompatible decoders.

## Safety (AC-5)

- **Fuzzing: 1,107,133 executions, zero crashes** (`cargo fuzz run decode_frame`,
  121 s, memory-capped). The target also stamps a valid header on random bytes
  so the budget is spent inside the bitstream logic instead of dying at the
  magic check.
- **AddressSanitizer: on.** `cargo-fuzz` defaults to `--sanitizer address`;
  verified rather than assumed — the fuzz binary contains 414 `__asan` symbols.
- **UndefinedBehaviorSanitizer: not run, and here is why.** Rust's `-Zsanitizer`
  does not offer UBSan; the equivalent guarantees come from the language plus
  Miri. The decode path contains **no `unsafe` at all**, so the UB surface is
  the wasm ABI's pointer handling in `src/wasm.rs`, which is `wasm32`-only and
  documented at each call. Recorded as a scoped gap, not claimed as done.
- Fail-closed on: bad magic/version/mode, oversized alphabets, invalid or
  incomplete Huffman tables (Kraft-checked), out-of-range length/distance
  codes, distances before the output start, matches overrunning the declared
  length, truncation, and checksum mismatch.
- Output ceiling enforced against the declared length **before** allocating.

## CSP: two findings a PoC is for

Serving the demo under a strict policy immediately broke it, twice, and both
failures are the point:

1. `script-src` **needs `'wasm-unsafe-eval'`** or the browser refuses to
   instantiate the module at all.
2. A strict `script-src 'self'` **blocks inline `<script type="module">`**. The
   fix is an external `demo.js`, not `'unsafe-inline'` — the page was changed to
   fit the policy rather than the policy loosened to fit the page.

Shipped policy in `web/serve.mjs`:
`default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`.

## Acceptance criteria: what is met, and what is not

| AC | state |
|---|---|
| 1 — real desktop browser | **met** (Chromium headless, x86-64, 12/12 byte-exact) |
| 1 — ARM/mobile path | **NOT met**, see below |
| 2 — clean JS API | **met** (`cubrimDecode`, synchronous; streaming out of scope and documented) |
| 3 — real-site demo that uses the content | **met** (CSS applied, JSON parsed, font loaded) |
| 4 — measurements, no fabrication | **met** (traffic, decode time, wasm memory, module size; every number verified byte-exact) |
| 5 — fuzzing + sanitizer + limits | **met for ASan + fuzz + limits**; UBSan scoped out with reason |
| 6 — docs and limitations | **met** (`code/cubrim-web-decoder/README.md`) |

**ARM is a genuine gap, named precisely.** No `qemu-aarch64` on this host, and
the only online ARM device on the mesh is the operator's personal Mac; the two
Android handsets have been offline for 1 and 5 days. What would close it: an
ARM64 Linux host with node, or an emulator package, at which point
`web/node-check.mjs` runs unchanged — the module is architecture-independent
bytecode, so the variable is the engine, not the build.

**DB:** no rows written. AC-4 says measurements land in the CUBR-0074 tables
with the decoder hash; that write belongs to whoever owns the benchmark DB, and
the numbers plus the module hash are published here for it.

## Reproduction

```sh
cd code/cubrim-web-decoder
cargo test --release                                    # differential vs cubrim
cargo build --release --target wasm32-unknown-unknown    # 50,110 B module
cargo run --release --example make_web_fixtures -- ../../bench/web-corpus/payloads-v2 site/fixtures
cp web/{cubrim.js,demo.html,demo.js,serve.mjs} site/
cp target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm site/
node site/serve.mjs site 8077        # http://127.0.0.1:8077/
node web/node-check.mjs target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm site/fixtures
cargo +nightly fuzz run decode_frame -- -max_total_time=120
```
