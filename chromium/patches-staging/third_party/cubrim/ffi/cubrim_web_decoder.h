// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// C declarations for the vendored cubrim-web-decoder handle-based ABI
// (src/ffi.rs in the cubrim repository, cbm_ffi_abi_version == 1).

#ifndef THIRD_PARTY_CUBRIM_FFI_CUBRIM_WEB_DECODER_H_
#define THIRD_PARTY_CUBRIM_FFI_CUBRIM_WEB_DECODER_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct CbmStream CbmStream;

uint32_t cbm_ffi_abi_version(void);

// max_output 0 = the decoder's default ceiling. Returns NULL on failure.
CbmStream* cbm_stream_new(size_t max_output);

// Explicit native policy. Zero selects the decoder default for that field.
// The browser seam uses this to pin its ratio and per-stream memory rules.
CbmStream* cbm_stream_new_with_limits(size_t max_output,
                                      size_t max_expansion_ratio,
                                      size_t max_decoder_memory);

// Conservative current capacity charge for the Rust decoder and its ABI
// fresh-output window. Returns 0 for NULL or a finished stream.
size_t cbm_stream_memory_usage(const CbmStream* stream);

// 1 = ok, 0 = error (message via cbm_stream_error_*; the stream is poisoned).
int32_t cbm_stream_push(CbmStream* stream, const uint8_t* ptr, size_t len);

// Bytes newly decoded by the LAST push; pointer valid until the next call on
// this stream.
const uint8_t* cbm_stream_fresh_ptr(const CbmStream* stream);
size_t cbm_stream_fresh_len(const CbmStream* stream);

// Declared decoded length, or UINT64_MAX until the frame header has arrived.
uint64_t cbm_stream_declared_len(const CbmStream* stream);

// Verify declared length + whole-stream checksum. 1 = authentic, 0 = fail.
int32_t cbm_stream_finish(CbmStream* stream);

const uint8_t* cbm_stream_error_ptr(const CbmStream* stream);
size_t cbm_stream_error_len(const CbmStream* stream);

// Safe on NULL.
void cbm_stream_free(CbmStream* stream);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // THIRD_PARTY_CUBRIM_FFI_CUBRIM_WEB_DECODER_H_
