# chromium/ — Cubrim Browser Technology Preview fork prep (CUBR-0079)

Everything the Chromium demo fork needs that is NOT the 100 GB tree itself:

- `BUILD.md` — pinned tag (151.0.7922.137), host rules, exact recipe,
  smoke-gate-before-target-build order, demo topology, evidence list.
- `run-demo.sh` + `netlog_verify.py` + `browser_evidence.mjs` — bounded
  browser demo, structural netlog verifier, in-browser decoded-body hash, and
  rendered screenshot capture.
- `ffi-check.c` — native proof of the decoder's C ABI (the surface the
  patch links against).
- `testdata/` — golden-vector manifest for the CbmSourceStream unittests.
- `patches/` — arrives in Phase P1: 0001 decoder+SourceStream, 0002
  feature+advertisement+dispatch, 0003 unittest+fuzzer.

Design: PRD-CUBR-0079 + CUBR-0079-design-consilium in the workspace datarim.
Hard gate: demo fork only — any upstream CL needs operator sign-off.
