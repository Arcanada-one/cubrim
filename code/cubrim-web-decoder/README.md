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
The decoder also applies finite defaults for retained input (64 MiB), decoded
expansion (4096x), and aggregate decoder memory (256 MiB). A native caller that
needs stricter policy uses the Rust `DecodeLimits` fields directly. A malformed
frame throws with the decoder's message.

### Streaming

```js
const response = await fetch('/asset.js.cbr');
const generator = cubrim.cubrimDecodeStream(response.body, 8 << 20);

let step = await generator.next();
while (!step.done) {
  render(step.value);          // bytes decoded so far, block by block
  step = await generator.next();
}
const verified = step.value;   // whole output, length + checksum checked
```

Accepts a `ReadableStream` or any async iterable of `Uint8Array`. **Blocks are
the unit of progress**: a multi-block frame yields as each block completes, a
single-block frame yields once at the end. That is honest behaviour rather than
a fake trickle — a Huffman symbol split across a chunk boundary cannot be
decoded twice.

**Integrity, stated plainly:** bytes yielded before completion are *not yet*
verified against the frame checksum. The generator throws if final verification
fails, so a consumer that has already rendered early bytes must be prepared to
discard them. Use `cubrimDecode` when that is unacceptable. This is the real
cost of progressive decode, not a footnote.

## Serving

`web/serve.mjs` is a minimal static server that speaks both transports the
frame travels over, and applies a strict CSP:

1. **`Content-Type: application/cubrim`** — a direct request for a `.cbr`
   file; the page decodes explicitly. This is the CUBR-0077 transport and it
   needs nothing from the client's `Accept-Encoding`.

2. **`Content-Encoding: cbm`** — the epic's namesake (CUBR-0072). A client
   that lists `cbm` in `Accept-Encoding` gets the resource under its own
   `Content-Type` with `Content-Encoding: cbm` and the frame as the body;
   every other client gets identity. Negotiation is RFC 9110 §12.5.3 parsing
   (`web/encoding.mjs`) with one deliberate narrowing: `*` never selects
   `cbm`, because a generic client advertising `*` has no Cubrim decoder —
   the coding is chosen only on an explicit `cbm` token with non-zero weight.
   Every resource with a precompressed variant carries
   `Vary: Accept-Encoding`, whichever representation is sent, so a shared
   cache cannot hand cbm bytes to a client that never asked.

**What transport 2 is and is not.** It is the real HTTP mechanism — the same
negotiation gzip, br and zstd use, exercised end-to-end by
`web/encoding-check.mjs` (a Node client sets `Accept-Encoding: cbm`, the
response body pipes through the real WASM module, output verified
byte-exact). It is **not** reachable from today's browsers: page JavaScript
cannot set `Accept-Encoding` (a forbidden request header), and a browser will
refuse a `Content-Encoding` it did not offer. Native `cbm` in the browser's
network stack is exactly CUBR-0079 (Chromium technology preview); until then
transport 1 is what a web page can use, and transport 2 is for clients that
control their own headers (Node, native apps, proxies, Electron).

The token `cbm` is a working name; it is **not** IANA-registered, and
registration is an operator-gated step (CUBR-0080).

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

The `Content-Encoding: cbm` transport has its own end-to-end suite — real
server on an ephemeral port, real module, negotiation edge cases, streaming
decode from a `fetch` body (multi-block fixtures in the second directory):

```sh
cargo run --release --example make_web_fixtures -- ../../bench/web-corpus/payloads-v2 site/fixtures-4k 4096
node web/encoding-check.mjs target/wasm32-unknown-unknown/release/cubrim_web_decoder.wasm site/fixtures site/fixtures-4k
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
- Retained compressed input is capped at 64 MiB by default, so a streaming
  caller cannot append bytes forever while waiting for a frame to complete.
- Decoded-to-compressed expansion is capped at 4096x by default and checked
  again when a stream finishes. Callers can select a stricter ratio.
- Aggregate decoder memory is capped at 256 MiB by default and includes
  retained input, retained output, the native/WASM ABI fresh-output window,
  and table/state allowance. Streaming block retries are transactional
  in-place, so a partial block does not allocate a second full output body.
  Reservations use fallible allocation and fail closed.
- No `unsafe` in the decoder itself; the only `unsafe` is the wasm ABI's
  pointer handling, which is documented and confined to `src/wasm.rs`.
- `cargo fuzz run decode_frame` targets arbitrary frames, including a variant
  that stamps a valid header on random bytes so the budget is spent inside the
  bitstream logic rather than at the magic check. `cargo fuzz run decode_ffi`
  exercises the native handle ABI, including pointer accessors and poisoned
  stream sequencing.

## Two containers, one media type

An `application/cubrim` response is not always a `MODE_WEB` frame. The encoder
competes the profile against a verbatim copy per file, so an already-compressed
asset (WOFF2, PNG) arrives as a **raw-store** frame. This decoder accepts both,
and `is_decodable_frame()` reports it — a decoder that handled only `MODE_WEB`
would fail on exactly the assets where compression was correctly declined.

## Multi-block frames

`EncodeConfig::web_block_size` cuts a frame into blocks of roughly N output
bytes. A boundary resets the **entropy tables, not the output window**: a match
in a later block may still reach into an earlier one. That is what a streaming
consumer needs — a block is decodable as soon as its predecessors have been
emitted — and it costs one table descriptor per extra block (measured: 120,939 B
single-block vs 126,378 B at 4 KiB blocks over the 12-sample census, 86.91%
traffic reduction against 87.47%).

Verified end to end through the WASM module: 12/12 assets byte-exact at 4 KiB
blocks, including the raw-store fallback, at 100.5 MB/s in Node.

## Known limitations

- **Streaming yields per block, not per byte.** A single-block frame therefore
  yields once, at the end. Finer progress needs smaller blocks, which costs
  bytes (see *Multi-block frames*).
- **Early bytes are unverified** until `finish` succeeds — inherent to
  progressive decode, and called out at the API.
- **No encoder.** By design and by the disclosure split.
- **Timer coarsening** makes single-shot browser measurements meaningless at
  these asset sizes; the demo amortises over repeats and says so.
- **ARM correctness only.** The module decodes byte-exactly on ARM64 V8 under
  emulation; performance on real ARM silicon is unmeasured and no emulated
  number is quoted. See the results document.
