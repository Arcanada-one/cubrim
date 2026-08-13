# CUBR-0079 patch drafts — status

**Phase:** P2 COMPLETE — the real decoder links and the golden test passes.

**Verified on the synced arcana-kb tree (Chromium 151.0.7922.137):**
`net_unittests` builds, links the vendored Rust decoder + blake3, and passes
all four `CbmSourceStreamTest` cases — a real `Content-Encoding: cbm` frame
decodes **byte-exact** inside Chromium's net stack, at 1/7/64/512-byte chunks,
with corrupt and truncated frames rejected `ERR_CONTENT_DECODING_FAILED`.
The same URL negotiates CBM when the feature is enabled and returns identity
when it is disabled; an explicitly requested unsolicited CBM response fails
closed at stream setup. The boundary fuzzer also builds and completes a
1,000-run smoke on the pinned host.
`vendor-decoder.sh` reproduces the decoder-vendoring half; `apply.sh` the
net/ integration half. The stub is superseded — `third_party/cubrim/BUILD.gn`
here is the real `rust_static_library`.

**Verification refresh (2026-08-13):** the exact Chromium source commit was
`8f5d36bc16f57115aeeff34baf4ad6aa964d509c`. `gn gen` with the fuzzer enabled,
the full `net_unittests` target (1,030 build steps), the six focused CBM tests,
and `net_cbm_source_stream_fuzzer -runs=1000` all passed on arcana-kb.

## What is here

- `net/filter/cbm_source_stream.{h,cc}` — the CbmSourceStream, modelled on the
  pinned tag's `zstd_source_stream.cc` (same `FilterData` contract: return 0
  output only with all input consumed; drain a completed block across calls;
  verify the whole-stream checksum once at `upstream_end_reached` and fail with
  `ERR_CONTENT_DECODING_FAILED` on mismatch — gzip-guarantee level). Retained
  output capped at 64 MiB (format v1 has no window; v2's 8 MiB window-log is
  the real fix, tracked in CUBR-0076/0080).
- `third_party/cubrim/ffi/cubrim_web_decoder.h` — C declarations for the
  handle-based native ABI merged in cubrim PR #202 (`cbm_stream_*`). The Rust
  crate itself is vendored at P2 from `code/cubrim-web-decoder` on cubrim main.
- `apply.sh` — makes the small in-tree edits (enum `kCbm`, token map, the two
  `SourceStreamType` switches in `filter_source_stream.cc`, the
  `ToContentEncodingType` switch, a default-off `net::features::kCbmContentEncoding`,
  the HTTPS/localhost-gated advertisement in `http_request_headers.cc`,
  feature-off fail-closed dispatch, and `net/BUILD.gn` sources, tests, and
  fuzzer target). Guarded so a re-run does not double-insert.

## Confidence, stated honestly

- **Applies-clean:** high. Every anchor was taken from the sources at tag
  `151.0.7922.137` read directly from googlesource; `apply.sh` asserts each
  anchor is unique before editing.
- **Compiles / passes tests:** verified on the pinned arcana-kb tree as
  recorded above. The staged fuzzer and the six focused browser-path tests
  are both real Chromium targets, not Rust-only substitutes.
- **Still host-only:** browser-rendered decoded-body SHA-256, screenshot and
  netlog evidence, a one-hour ASan/UBSan run, and process-wide aggregate
  memory measurement. The current Rust budget remains decoder-local and the
  format-v1 retained-output ceiling remains per stream.
- The resolved P0-era question (no loopback TLS needed — the tag's guard is
  `SchemeIsCryptographic() || IsLocalhost(url)`) is already reflected here and
  in `chromium/BUILD.md`.

## Reproducible verification record

The staging inputs and `apply.sh` are the exact inputs used for the pinned
build. Reapplying the script is idempotent; the fuzzer and focused test
commands above are the bounded regression gate for future Chromium edits.
The backlog row remains `in_progress` for the separate live-browser and
resource-measurement gates, not for this compile/test slice.

## Both P1 unknowns resolved by real builds

1. `net_unittests` named the first: three hardening lints in
   `cbm_source_stream.cc` (fixed, PR #205).
2. `content_shell` named the second: the `services/network` mojom-traits
   switch over `net::SourceStreamType` needs a `kCbm` case — invisible to
   `net_unittests` (it does not compile services/network) and surfaced the
   moment a browser target was built. `apply.sh` now adds the mojom enum
   value and both traits switches. No third unknown remained at this layer.
