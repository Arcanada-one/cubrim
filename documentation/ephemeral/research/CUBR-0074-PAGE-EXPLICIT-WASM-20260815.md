# CUBR-0074 — explicit-WASM page protocol result

**Date:** 2026-08-15 UTC
**Status:** PASS for the explicit-WASM browser path; transparent HTTP is not
included in this result.
**Source:** `bb221e7e39e19d853ee9e80f5a92c8b02246555c` (`origin/main`)
**Protocol:** `page_id=explicit-wasm-home-v1`, 3 warmups plus 30 measured
trials, fresh Chromium process per trial, loopback-only HTTP, `no-store`.

This closes the executable page proof for the delivery mode that explicitly
loads `cubrim-web-decoder.wasm` in the page.  It does not turn that proof into
a transparent HTTP claim: the bundle records
`transparent_http_page.available=false` because the patched `content_shell`
proof is a separate protocol.

## What was measured

Chromium loaded four `application/cubrim` resources, decoded them through the
browser WASM module, and checked the decoded bytes against the canonical v3
manifest on every trial:

- `html-medium-home-v2` as the document;
- `css-medium-tailwind-v2` as the stylesheet;
- `javascript-small-resolve-uri-v2` as the script;
- `json-api-small-hypotheses-v2` as the data resource.

All 30 trials completed, giving **120/120 exact resource assertions**.  The
page protocol also completed with accepted host admission at load
`0.284973/CPU` and `79 °C` (ceiling `1.0` and `90 °C`).  The browser was
Chromium `151.0.7922.108 snap` on x86-64 Linux.

| metric | median | p95 | observed range |
|---|---:|---:|---:|
| time to first byte | 103.75 ms | 385.50 ms | 84.60–454.40 ms |
| first contentful paint | 136.00 ms | 412.00 ms | 112.00–476.00 ms |
| largest contentful paint | 196.00 ms | 472.00 ms | 160.00–536.00 ms |
| total blocking time | 0.00 ms | 0.00 ms | 0.00–0.00 ms |
| page load duration | 308.45 ms | 565.30 ms | 262.10–633.10 ms |

These are browser-page observations, not a codec comparison or a throughput
claim.  The page run has no incumbent baseline and writes no benchmark DB row.

## Provenance

| artefact | SHA-256 |
|---|---|
| `cubrim-web` CLI | `54a70b3d78b0191cd337b7f11f7ef2a4792a702677d0ce6e5dd6d5e3b69744af` |
| `cubrim-web-decoder.wasm` | `48608e9992269f692f287a632251e2e1e80906b5373fcd92d12dbe3e889467bf` |
| page result bundle | `d86f7bcd741bc438919169f11ac3f3ed427bd3424879ce13abf93bad932ae11c` |
| hostile-input proof | `5f3c21f9c4f8146d6c5716b76d400ab265c99009c82fbb913ae90fa05b966e4b` |

The CLI identity binds the binary to the source head and the exact build
command (`cargo build --locked --release`, working directory
`code/cubrim-web-cli`).  The separate hostile-input proof on the same source
and binary rejected all 15 bounded malformed frames with zero faults; its
reference is recorded in the page bundle as
`CUBR-0075:web-decoder-hostile:5f3c21f9c4f8146d6c5716b76d400ab2`.

## Boundaries that remain open

- This is explicit WASM application delivery.  It does not prove transparent
  HTTP negotiation or a browser-native `Content-Encoding` path.
- It is an x86-64 browser run.  ARM/native-host correctness and performance
  remain separate parent criteria; no ARM timing is inferred.
- No production deploy, public page change, or database publication was made
  by this evidence run.

The machine-readable result and the hostile-input proof are committed beside
this report as `page.json` and `web-hostile.json`.

## Reproduction

```sh
cargo build --locked --release                         # code/cubrim-web-cli
cargo build --release --target wasm32-unknown-unknown --offline  # decoder
python3 bench/web-benchmark/page_benchmark.py \
  --manifest bench/web-corpus/manifest.v3.json \
  --resource-bundle <current-candidate-bundle.json> \
  --codec-binary code/cubrim-web-cli/target/release/cubrim-web \
  --wasm code/cubrim-web-decoder/target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm \
  --browser /snap/bin/chromium \
  --out page.json \
  --timeout 100
```

The resource bundle's `cubrim-web` identity must match the source head and
binary hash above; an older candidate identity is not interchangeable.
