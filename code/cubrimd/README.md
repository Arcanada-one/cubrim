# cubrimd

Reverse proxy that serves **`Content-Encoding: cbm`** — the Cubrim Web
Profile over the real HTTP negotiation — to clients that ask for it, and
stays out of the way for everyone else (CUBR-0078, canon stage 3:
`Browser → cubrimd → nginx/app`).

```sh
cargo run --release -- --origin http://127.0.0.1:8080 --listen 127.0.0.1:8078
```

## What it does per request

| client `Accept-Encoding` | origin sees | client gets |
|---|---|---|
| lists `cbm` (explicit token, q > 0) | `identity` | eligible bodies as a Web Profile frame, `Content-Encoding: cbm` |
| anything else | the same list with the `cbm` token stripped | the origin's own choice — brotli, zstd, gzip, identity — byte-untouched |

That second row **is** the fallback story: the origin already speaks the
incumbent codings, and re-implementing them here would only add a second
place for them to be wrong.

Eligibility for the `cbm` leg: `GET`, status 200, compressible
`Content-Type` (allowlist — already-compressed media is never negotiated),
no origin `Content-Encoding`, no `Cache-Control: no-transform`, body within
`--max-body-bytes` (over the cap the response streams through unencoded).
A frame that fails to beat identity is discarded and identity is served —
negative-value encoding is never shipped.

The proxy uses the Web Profile's near-realtime dynamic encoder: it emits the
same version-1 frame and uses the same decoder as the density-first static
profile, but bounds match-search work for request latency. Archive callers can
still opt into the static `EncodeConfig::web_profile` path when encode time is
less important than density.

Every resource the proxy would negotiate carries `Vary: Accept-Encoding`
whichever representation is sent — the canon calls this the critical header:
without it a shared cache hands `cbm` bytes to a client that never asked.
The origin's `ETag` is dropped from `cbm` responses (an entity tag names a
representation, and the frame is a different one).

## Cache

Compressed variants are cached in memory (FIFO, `--cache-entries`, keyed by
path+query) and guarded by the origin's validator (`ETag`, else
`Last-Modified`): a response with no validator is never cached, and a
validator change is a miss. The cache avoids re-*encoding*; the origin is
still consulted per request, which is what keeps a stale frame impossible.
Conditional requests to the origin (`If-None-Match`) would save that
transfer and are deliberately future work.

## Metrics

`GET /__cubrimd/metrics` — Prometheus text: requests, cbm responses,
identity-eligible, passthrough, origin errors, cache hits/misses, original
vs cbm bytes. Real counters from real responses; nothing estimated.

## Negotiation

RFC 9110 §12.5.3 parsing with the same deliberate narrowing as the
reference server (`code/cubrim-web-decoder/web/encoding.mjs`): `*` never
selects `cbm` — a generic client advertising `*` has no Cubrim decoder, and
the epic's rule is "pick Cubrim only for clients that support it".
Malformed header members are dropped, not guessed at.

## Deliberately not here

TLS (run it behind the terminator), HTTP/2, a second content coding,
conditional origin revalidation, request-smuggling hardening beyond
hop-by-hop stripping. The `cbm` token is a working name; IANA registration
is a hard-gated CUBR-0080 step.

## Tests

`cargo test --release` — unit (negotiation, eligibility, Vary merge, cache
semantics) plus end-to-end: a real origin and the real proxy on ephemeral
ports, bodies decoded with `cubrim::decode` and compared byte-exact, the
origin's recorded `Accept-Encoding` asserted per leg, cache hits proven via
the metrics endpoint, dead origin answered with 502.
