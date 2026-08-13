// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "net/filter/cbm_source_stream.h"

#include <algorithm>
#include <string>
#include <vector>

#include "base/check.h"
#include "base/compiler_specific.h"
#include "base/containers/span.h"
#include "base/memory/raw_ptr_exclusion.h"
#include "base/numerics/safe_conversions.h"
#include "net/base/io_buffer.h"
#include "net/filter/source_stream_type.h"
#include "third_party/cubrim/ffi/cubrim_web_decoder.h"

namespace net {

namespace {

const char kCbmStreamName[] = "CBM";

// Retained-output ceiling per stream. Format v1's match window is the whole
// preceding output, so the decoder must hold the full decoded body until the
// trailing checksum; this cap is therefore a whole-body cap, not a window.
// 64 MiB matches the reference decoder's default. The Rust decoder also caps
// retained input, expansion ratio, and aggregate decoder memory; streaming
// retries are transactional in-place. This native caller supplies the output
// ceiling through cbm_stream_new(). Format v2's
// window-log field (capped at 8 MiB, mirroring Chromium's zstd clamp) is the
// real fix for retained output — tracked in the epic, deliberately not
// invented here.
constexpr size_t kMaxRetainedOutput = 64 * 1024 * 1024;

// CbmSourceStream applies Cubrim Web Profile ("cbm") content decoding to a
// data stream. Wire format: documentation/reference/cubrim-web-profile-format
// in the cubrim repository. The decoder itself is the vendored
// #![forbid(unsafe_code)]-decode-path Rust reference decoder, consumed
// through its handle-based C ABI (`cbm_stream_*`) — one owned decoder object
// per stream, safe under the network service's interleaving.
class CbmSourceStream : public FilterSourceStream {
 public:
  explicit CbmSourceStream(std::unique_ptr<SourceStream> upstream)
      : FilterSourceStream(SourceStreamType::kCbm, std::move(upstream)),
        stream_(cbm_stream_new(kMaxRetainedOutput)) {
    CHECK(stream_);
  }

  CbmSourceStream(const CbmSourceStream&) = delete;
  CbmSourceStream& operator=(const CbmSourceStream&) = delete;

  ~CbmSourceStream() override { cbm_stream_free(stream_); }

 private:
  // SourceStream implementation
  std::string GetTypeAsString() const override { return kCbmStreamName; }

  base::expected<size_t, Error> FilterData(IOBuffer* output_buffer,
                                           size_t output_buffer_size,
                                           IOBuffer* input_buffer,
                                           size_t input_buffer_size,
                                           size_t* consumed_bytes,
                                           bool upstream_end_reached) override {
    // 1. Feed every input byte to the decoder. The decoder buffers input
    //    internally, so consuming the whole chunk keeps the base-class
    //    contract: whenever this call returns 0 output bytes, all input has
    //    been consumed.
    if (input_buffer_size > 0) {
      if (cbm_stream_push(stream_,
                          reinterpret_cast<const uint8_t*>(input_buffer->data()),
                          input_buffer_size) != 1) {
        *consumed_bytes = input_buffer_size;
        return base::unexpected(ERR_CONTENT_DECODING_FAILED);
      }
      const size_t fresh_len = cbm_stream_fresh_len(stream_);
      if (fresh_len > 0) {
        base::span<const uint8_t> fresh_span =
            UNSAFE_BUFFERS(base::span(cbm_stream_fresh_ptr(stream_), fresh_len));
        pending_.insert(pending_.end(), fresh_span.begin(), fresh_span.end());
      }
    }
    *consumed_bytes = input_buffer_size;

    // 2. Drain decoded bytes into the caller's buffer, possibly across
    //    several calls (a completed block can exceed one IOBuffer).
    const size_t available = pending_.size() - pending_offset_;
    if (available > 0) {
      const size_t emit = std::min(available, output_buffer_size);
      output_buffer->span().first(emit).copy_from(
          base::span(pending_).subspan(pending_offset_, emit));
      pending_offset_ += emit;
      if (pending_offset_ == pending_.size()) {
        pending_.clear();
        pending_offset_ = 0;
      }
      return emit;
    }

    // 3. End of the response body: verify declared length and the
    //    whole-stream checksum exactly once. Bytes already delivered were
    //    unverified until now — same guarantee class as gzip's trailing CRC;
    //    a mismatch fails the request at the tail.
    if (upstream_end_reached) {
      if (!verified_) {
        if (cbm_stream_finish(stream_) != 1) {
          return base::unexpected(ERR_CONTENT_DECODING_FAILED);
        }
        verified_ = true;
      }
      return 0;
    }

    // Need more input; everything handed to us has been consumed.
    return 0;
  }

  // Owned by Rust (Box::into_raw); not PartitionAlloc memory, so raw_ptr
  // is wrong here — exclude it explicitly.
  RAW_PTR_EXCLUSION CbmStream* const stream_;
  std::vector<uint8_t> pending_;
  size_t pending_offset_ = 0;
  bool verified_ = false;
};

}  // namespace

std::unique_ptr<FilterSourceStream> CreateCbmSourceStream(
    std::unique_ptr<SourceStream> upstream) {
  return std::make_unique<CbmSourceStream>(std::move(upstream));
}

}  // namespace net
