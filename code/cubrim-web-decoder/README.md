# cubrim-web-decoder

Reference decoder for the **Cubrim Web Profile** frame (`MODE_WEB`, container
byte 18), buildable for `wasm32-unknown-unknown` so a web page can decode
content served as `Content-Type: application/cubrim`.

This crate **cannot compress**. It is the decoder half only, which is what the
CUBR-0072 / ADR-0003 disclosure split classifies as public along with the wire
format, its framing and its limits.

## Why a separate crate

The `cubrim` crate pulls `ureq`, `dirs`, `rpassword`, `walkdir` and `rand` for
its CLI and archive layers. Several of those do not build for
`wasm32-unknown-unknown` — the blocker recorded against CUBR-0077 in the corpus
manifest. A decoder needs none of them, so it lives here with one dependency
(`blake3`, for the frame checksum).

Two implementations of one wire format can drift. That is prevented mechanically,
not by discipline: `tests/differential.rs` decodes the whole census corpus, a set
of synthetic shapes, and thousands of bit-flipped frames with **both** this
decoder and `cubrim::decode`, and fails if they differ in any byte or disagree
about whether a frame is valid.

## Build

```sh
# native (for the differential tests)
cargo test --release

# wasm module
cargo build --release --target wasm32-unknown-unknown
# -> target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm  (~50 KB)
```

No `wasm-bindgen`, no bundler, no build script. The module exports a small C ABI
and `web/cubrim.js` is ~40 lines of glue against it.

## JavaScript API

```js
import CubrimDecoder from './cubrim.js';

const cubrim = await CubrimDecoder.load('./cubrim_web_decoder.wasm');

const frame = new Uint8Array(await (await fetch('/asset.css.cbr')).arrayBuffer());
const bytes = cubrim.cubrimDecode(frame, 8 << 20);   // Uint8Array -> Uint8Array
document.adoptedStyleSheets = [sheetFrom(new TextDecoder().decode(bytes))];
```

`cubrimDecode(compressed, maxOutput)` is synchronous and returns a copy owned by
the caller. `maxOutput` is a hard ceiling checked against the frame's declared
length **before** anything is allocated; pass a real bound for known assets.
A malformed frame throws with the decoder's message.

A streaming API (`ReadableStream`) is deliberately **not** implemented — see
*Known limitations*.

## Serving

`Content-Type: application/cubrim`, no `Content-Encoding` negotiation: the page
decodes explicitly. `web/serve.mjs` is a minimal static server that does this
correctly and applies a strict CSP.

Two deployment details this PoC surfaced, both worth knowing before shipping:

1. **`script-src` needs `'wasm-unsafe-eval'`.** Without it a modern browser
   refuses to instantiate the module at all.
2. **The page script must be external.** A strict `script-src 'self'` blocks
   inline `<script type="module">`, so the demo keeps its driver in `demo.js`
   rather than loosening the policy with `'unsafe-inline'`.

## Demo

```sh
cargo build --release --target wasm32-unknown-unknown
cargo run --release --example make_web_fixtures -- ../../bench/web-corpus/payloads-v2 site/fixtures
cp web/{cubrim.js,demo.html,demo.js,serve.mjs} site/
cp target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm site/
node site/serve.mjs site 8077   # then open http://127.0.0.1:8077/
```

The page fetches 12 real web assets as `application/cubrim`, decodes each in
WASM, verifies every one against the original bytes with SHA-256 **before**
reporting any number, and then uses the results: the stylesheet is applied, the
JSON is parsed, the WOFF2 is loaded as a `FontFace`.

Headless check without a browser (same V8 engine, no display):

```sh
node web/node-check.mjs target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm site/fixtures
```

## Measured

Full provenance in
`documentation/ephemeral/research/CUBR-0077-WASM-RESULTS-20260811.md`. Summary,
all byte-exact against the originals:

| environment | corpus decode | note |
|---|---|---|
| native Rust (`cubrim::decode`) | 443.4 MB/s | quiet host, pinned |
| Chromium headless, WASM | 99.1 MB/s | amortised over 25 repeats |
| Node 22, WASM | 94.5 MB/s | best of 20 per asset |

12 assets, 965,410 B of content served as 120,939 B — **87.47% less traffic**.
WASM linear memory after decoding all 12: 1.6 MiB. Module: 50,110 B.

## Safety

- Every malformed field is fail-closed: bad magic/version/mode, oversized
  alphabets, invalid or incomplete Huffman tables, out-of-range length and
  distance codes, distances past the output start, matches overrunning the
  declared length, truncation at any offset, and a final checksum mismatch.
  Corrupt output is never returned as success.
- The output ceiling is enforced against the declared length before allocation
  and again as output grows.
- No `unsafe` in the decoder itself; the only `unsafe` is the wasm ABI's
  pointer handling, which is documented and confined to `src/wasm.rs`.
- `cargo fuzz run decode_frame` targets arbitrary frames, including a variant
  that stamps a valid header on random bytes so the budget is spent inside the
  bitstream logic rather than at the magic check.

## Known limitations

- **Synchronous whole-buffer only.** No streaming/progressive decode. The frame
  is single-block by construction today, so a streaming API would need the
  multi-block path exercised first; the format already carries a `BFINAL` bit
  for it.
- **No encoder.** By design and by the disclosure split.
- **Timer coarsening** makes single-shot browser measurements meaningless at
  these asset sizes; the demo amortises over repeats and says so.
- **Untested on ARM.** See the results document — the machine available here is
  x86-64, and the honest scope is recorded rather than papered over.
