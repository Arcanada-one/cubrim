# CUBR-0079 patch drafts — status

**Phase:** P2 COMPLETE — the real decoder links and the golden test passes.

**Verified on the synced arcana-kb tree (Chromium 151.0.7922.137):**
`net_unittests` builds, links the vendored Rust decoder + blake3, and passes
all four `CbmSourceStreamTest` cases — a real `Content-Encoding: cbm` frame
decodes **byte-exact** inside Chromium's net stack, at 1/7/64/512-byte chunks,
with corrupt and truncated frames rejected `ERR_CONTENT_DECODING_FAILED`.
`vendor-decoder.sh` reproduces the decoder-vendoring half; `apply.sh` the
net/ integration half. The stub is superseded — `third_party/cubrim/BUILD.gn`
here is the real `rust_static_library`.

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
  `net/BUILD.gn` sources). Guarded so a re-run does not double-insert.

## Confidence, stated honestly

- **Applies-clean:** high. Every anchor was taken from the sources at tag
  `151.0.7922.137` read directly from googlesource; `apply.sh` asserts each
  anchor is unique before editing.
- **Compiles / passes tests:** NOT YET VERIFIED. That is Phase P2 on the
  synced arcana-kb tree and is the gate that turns these drafts into a landed
  patch series. Two known unknowns the build will resolve:
  1. a `services/network` mojom-traits switch over `net::SourceStreamType` may
     need a `kCbm` case (the LINT.ThenChange on the enum points at
     `source_type.mojom`); the compile names it if so.
  2. `third_party/cubrim/BUILD.gn` (`rust_static_library` + blake3 pure-Rust)
     is the likeliest friction — see `chromium/BUILD.md`.
- The resolved P0-era question (no loopback TLS needed — the tag's guard is
  `SchemeIsCryptographic() || IsLocalhost(url)`) is already reflected here and
  in `chromium/BUILD.md`.

## Why land drafts rather than wait for the green build

Unpushed work is lost work, and the compile-iterate loop is a multi-hour
build on a single host. These drafts + `apply.sh` are the exact input P2
consumes; landing them means the build phase resumes from a reviewed artefact
rather than from a scratch directory. The backlog row stays `in_progress` and
says precisely this.
