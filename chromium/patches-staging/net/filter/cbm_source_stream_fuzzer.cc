// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "net/filter/cbm_source_stream.h"

#include <fuzzer/FuzzedDataProvider.h>

#include <cstddef>
#include <cstdint>
#include <memory>

#include "base/memory/ref_counted.h"
#include "net/base/io_buffer.h"
#include "net/base/test_completion_callback.h"
#include "net/filter/fuzzed_source_stream.h"

namespace {

// Keep malformed input bounded so the fuzzer explores decoder state rather
// than spending the entire testcase budget on attacker-sized retained input.
constexpr size_t kMaxInputSizeBytes = 300 * 1024;
constexpr size_t kMaxReads = 10 * 1024;

}  // namespace

// This target is deliberately at the Chromium SourceStream/FFI boundary. The
// Rust fuzz target covers the decoder core; this one exercises the browser's
// input chunking, asynchronous Read contract, and lifetime of the output
// buffer around the real CbmSourceStream wrapper.
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  if (size > kMaxInputSizeBytes) {
    return 0;
  }

  FuzzedDataProvider data_provider(data, size);
  auto fuzzed_source_stream =
      std::make_unique<net::FuzzedSourceStream>(&data_provider);
  std::unique_ptr<net::SourceStream> cbm_stream =
      net::CreateCbmSourceStream(std::move(fuzzed_source_stream));

  size_t num_reads = 0;
  while (num_reads < kMaxReads) {
    scoped_refptr<net::IOBufferWithSize> io_buffer =
        base::MakeRefCounted<net::IOBufferWithSize>(64);
    net::TestCompletionCallback callback;
    int result = cbm_stream->Read(io_buffer.get(), io_buffer->size(),
                                  callback.callback());
    ++num_reads;

    // Releasing the caller-owned buffer immediately exercises the wrapper's
    // promise not to retain an IOBuffer beyond the Read call.
    io_buffer = nullptr;
    if (callback.GetResult(result) <= 0) {
      break;
    }
  }

  return 0;
}
