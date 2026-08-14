# chromium/ — Cubrim Browser Technology Preview fork prep (CUBR-0079)

Everything the Chromium demo fork needs that is NOT the 100 GB tree itself:

- `BUILD.md` — pinned tag (151.0.7922.137), host rules, exact recipe,
  smoke-gate-before-target-build order, demo topology, evidence list.
- `run-demo.sh` + `netlog_verify.py` + `browser_evidence.mjs` — bounded
  browser demo, structural netlog verifier, in-browser decoded-body hash, and
  rendered screenshot capture.
- `run-transparent-page-metrics.sh` + `transparent_page_evidence.mjs` — a
  build-host-only paired page-timing proof for the native transparent HTTP
  path. It runs identity and `cbm` arms with fresh browser processes, exact
  body hashes, screenshots, netlogs, and the five page metrics; it does not
  change production traffic or publish a result by itself.
- `ffi-check.c` — native proof of the decoder's C ABI (the surface the
  patch links against).
- `testdata/` — golden-vector manifest for the CbmSourceStream unittests.
- `patches/` — arrives in Phase P1: 0001 decoder+SourceStream, 0002
  feature+advertisement+dispatch, 0003 unittest+fuzzer.

Design: PRD-CUBR-0079 + CUBR-0079-design-consilium in the workspace datarim.
Hard gate: demo fork only — any upstream CL needs operator sign-off.

## Transparent HTTP page timing

`run-transparent-page-metrics.sh` is the CUBR-0072 evidence path for the
remaining page/user-metrics boundary. It starts the existing loopback origin,
randomizes a fixed schedule, and runs exactly three warmups plus 30 measured
trials for each of two arms:

- `cbm`: the patched `content_shell` negotiates and decodes
  `Content-Encoding: cbm`;
- `identity`: the same browser build runs with the feature disabled and the
  origin returns identity bytes.

Every row is rejected unless the browser timing entries include TTFB, FCP,
LCP, TBT, and page-load duration, the decoded document matches the origin
hash, the screenshot is non-empty, and `netlog_verify.py` attributes the
expected transport. The aggregate validator records only hashes and timing
summaries; raw netlogs and screenshots remain in the evidence directory.

Run it on the pinned build host with the source identities supplied explicitly:

```sh
CUBRIM_SOURCE_SHA=<cubrim-main-sha> \
CHROMIUM_SOURCE_SHA=<chromium-source-sha> \
./chromium/run-transparent-page-metrics.sh
```

This is a measurement proof, not a compression-winner claim. API/site
publication remains a separate guarded step after a valid bundle exists.
