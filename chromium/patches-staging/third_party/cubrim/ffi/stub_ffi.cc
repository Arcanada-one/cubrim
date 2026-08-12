// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
//
// STUB implementation of the cbm_stream_* ABI. Exists ONLY to let //net link
// during the P2 integration compile-check while blake3 is vendored for the
// real Rust decoder. Every call fails safely; a build that uses this cannot
// decode a real cbm frame. Do NOT ship it.
#include "third_party/cubrim/ffi/cubrim_web_decoder.h"

extern "C" {
uint32_t cbm_ffi_abi_version(void) { return 1; }
CbmStream* cbm_stream_new(size_t) { return reinterpret_cast<CbmStream*>(1); }
int32_t cbm_stream_push(CbmStream*, const uint8_t*, size_t) { return 0; }
const uint8_t* cbm_stream_fresh_ptr(const CbmStream*) { return nullptr; }
size_t cbm_stream_fresh_len(const CbmStream*) { return 0; }
uint64_t cbm_stream_declared_len(const CbmStream*) { return UINT64_MAX; }
int32_t cbm_stream_finish(CbmStream*) { return 0; }
const uint8_t* cbm_stream_error_ptr(const CbmStream*) { return nullptr; }
size_t cbm_stream_error_len(const CbmStream*) { return 0; }
void cbm_stream_free(CbmStream*) {}
}
