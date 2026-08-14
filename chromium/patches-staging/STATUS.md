# CUBR-0079 patch drafts — status

**Phase:** P2 COMPLETE + R2 resource-policy/sanitizer closure — the real
decoder links, the golden test passes, and the browser seam has bounded
native and process-wide memory admission.

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

**Live browser proof refresh (2026-08-13 UTC, arcana-kb):** Cubrim
`origin/main` was `393a04d80b5f70849d805f82ca80b26a54d28c77` and the pinned
Chromium source was `8f5d36bc16f57115aeeff34baf4ad6aa964d509c`. The normal
component `content_shell` build completed with `Build Succeeded: 37936
steps - 3.25/s`; its SHA-256 was
`108ac4f7e46d20dfdb2af9138d4d5e6c8e98a226157d9668648b52c33ed8862d`, with
`use_libfuzzer = false`. The live browser probe returned status 200, decoded
227,968 bytes, and matched the origin SHA-256
`7c9ef50500135a4d14c4d900c5fd6d7fa3b407c321d3aa3efd73a2a86a832119`; it
captured `browser-proof.png` (10,725 bytes,
`d8c4d4cf56ae3f2737df88c228fbfa2731df10643c2322e2bfed9c4519bf7b3f`) and a
valid final `netlog.json` (332,550 bytes,
`010e8aaf835dba7e85e05504447545b6ccb7c1f4c20e72fb9b5f7a0724bdcf4d`). The
structural verifier found `Accept-Encoding: cbm`, `Content-Encoding: cbm`,
`Vary: Accept-Encoding`, and no terminal `FAILED` event. The proof harness now
keeps the normal browser execution context alive for the DevTools fetch and
gracefully terminates the browser parent before netlog verification.

## R2 resource-policy and sanitizer closure (2026-08-14 UTC)

Cubrim PR #219 (`7b9321b8376c0e5f0b78a85c0ee4b7af2a07b32b`, all required CI
checks green) adds the native policy at the Chromium seam: 64 MiB retained
output, expansion ratio 1024, 192 MiB per-decoder memory, and a 512 MiB
process-wide admission budget. The Rust FFI now accepts the explicit native
limits and reports decoder/fresh-output capacity; the C++ stream charges its
pending-output copy and releases the reservation on success, failure, EOF, and
destruction. The Rust FFI limit test and the Chromium aggregate-admission test
are both in the shipped regression surface.

The aggregate guard is mutation-proven on `arcana-kb`: temporarily changing
the rejection return made
`CbmSourceStreamTest.AggregateAdmissionIsRequestLocalAndReleased` fail with
the expected blocked-stream error mismatch (exit 1); restoring the exact line,
rebuilding, and rerunning the test passed (exit 0). The final restored focused
run passed all 7 tests: 5 source-stream cases and 2 URLRequest cases.

The authoritative sanitizer campaign ran on Chromium source
`8f5d36bc16f57115aeeff34baf4ad6aa964d509c` with binary SHA-256
`8dcdbd93fdcb08c71c7474195af02a906ef396cd9222019cba01f1954bbc9ab3`, the
staged libFuzzer harness patch SHA-256
`01c2b67dd99d73fa9fb38b72f3fdda1b0ac08a8a80993db98b954f6a07128065`,
`is_asan=true`, `is_ubsan=true`, `is_ubsan_no_recover=true`, and
`-max_total_time=3600 -timeout=10 -rss_limit_mb=49152`. Unit
`cubr-0079-asan-ubsan-20260814` completed with `Result=success`, exit 0, no
residual fuzzer process, no sanitizer/error markers, and no crash artifacts:
`Done 10606486 runs in 3601 second(s)`, 2,945 average exec/s, and 400 MiB
peak RSS. The terminal run log SHA-256 is
`44f48f3e280673abef143a8442833d21e7eb5bacf132573a519edc27d76768f1`;
the manifest is under
`/root/cubr-0079/evidence/cbm-r2-sanitizer-20260814/meta.txt` on the host.

The live browser proof remains byte-exact: the decoded body SHA-256 is
`7c9ef50500135a4d14c4d900c5fd6d7fa3b407c321d3aa3efd73a2a86a832119`,
`browser-proof.png` is 10,725 bytes with SHA-256
`d8c4d4cf56ae3f2737df88c228fbfa2731df10643c2322e2bfed9c4519bf7b3f`, and
the final `netlog.json` is 322,097 bytes with SHA-256
`4567a734f4d4db487b5039ca3042d57eb74b32292af1162f76235c296686b95b`.
The normal `content_shell` SHA-256 is
`108ac4f7e46d20dfdb2af9138d4d5e6c8e98a226157d9668648b52c33ed8862d`, and
the current normal `libnet.so` SHA-256 is
`e9b6dc0ee6197acfeccb403154ad93946379e5dfb6dcb17a0279f7381905c38c`.
No upstream Chromium PR, public release, or standards action was taken.

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
- **Still host-only:** the proof artifacts above are host evidence from the
  pinned Chromium fork; no upstream Chromium or public release is implied.
  The native process-wide admission policy and the format-v1 retained-output
  ceiling remain deliberately scoped to this demo fork.
- The resolved P0-era question (no loopback TLS needed — the tag's guard is
  `SchemeIsCryptographic() || IsLocalhost(url)`) is already reflected here and
  in `chromium/BUILD.md`.

## Reproducible verification record

The staging inputs and `apply.sh` are the exact inputs used for the pinned
build. Reapplying the script is idempotent; the fuzzer and focused test
commands above are the bounded regression gate for future Chromium edits.
The parent workspace disposition is updated only after Cubrim PR #219's
resulting `origin/main` tree is read back; no external standardization action
is part of this closure.

## Both P1 unknowns resolved by real builds

1. `net_unittests` named the first: three hardening lints in
   `cbm_source_stream.cc` (fixed, PR #205).
2. `content_shell` named the second: the `services/network` mojom-traits
   switch over `net::SourceStreamType` needs a `kCbm` case — invisible to
   `net_unittests` (it does not compile services/network) and surfaced the
   moment a browser target was built. `apply.sh` now adds the mojom enum
   value and both traits switches. No third unknown remained at this layer.
