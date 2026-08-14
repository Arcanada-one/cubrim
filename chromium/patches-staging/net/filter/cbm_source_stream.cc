// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "net/filter/cbm_source_stream.h"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include "base/compiler_specific.h"
#include "base/containers/span.h"
#include "base/memory/raw_ptr_exclusion.h"
#include "net/base/io_buffer.h"
#include "net/base/net_errors.h"
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
// retries are transactional in-place. This native caller supplies its output,
// ratio, and decoder-memory ceilings through cbm_stream_new_with_limits().
// Format v2's
// window-log field (capped at 8 MiB, mirroring Chromium's zstd clamp) is the
// real fix for retained output — tracked in the epic, deliberately not
// invented here.
constexpr size_t kMaxRetainedOutput = 64 * 1024 * 1024;
constexpr size_t kMaxDecoderMemory = 192 * 1024 * 1024;
constexpr size_t kMaxExpansionRatio = 1024;
constexpr size_t kAggregateMemoryBudget = 512 * 1024 * 1024;
// Covers the C++ object, allocator slack, and the fixed decoder-table charge
// not visible in the pending-output vector. Dynamic stream charges grow from
// this admission floor as the FFI reports actual capacities.
constexpr size_t kNativeStreamOverhead = 1 * 1024 * 1024;

std::atomic<size_t> g_cbm_aggregate_budget{kAggregateMemoryBudget};
std::atomic<size_t> g_cbm_aggregate_reserved{0};

bool TryGrowReservation(size_t current, size_t desired, size_t* result) {
  if (desired <= current) {
    *result = current;
    return true;
  }
  const size_t delta = desired - current;
  size_t reserved = g_cbm_aggregate_reserved.load(std::memory_order_relaxed);
  for (;;) {
    const size_t budget = g_cbm_aggregate_budget.load(std::memory_order_acquire);
    if (reserved > budget || delta > budget - reserved) {
      return false;
    }
    if (g_cbm_aggregate_reserved.compare_exchange_weak(
            reserved, reserved + delta, std::memory_order_acq_rel,
            std::memory_order_relaxed)) {
      *result = desired;
      return true;
    }
  }
}

void ReleaseReservation(size_t bytes) {
  if (bytes != 0) {
    g_cbm_aggregate_reserved.fetch_sub(bytes, std::memory_order_acq_rel);
  }
}

bool SetReservation(size_t current, size_t desired, size_t* result) {
  if (desired <= current) {
    ReleaseReservation(current - desired);
    *result = desired;
    return true;
  }
  return TryGrowReservation(current, desired, result);
}

// CbmSourceStream applies Cubrim Web Profile ("cbm") content decoding to a
// data stream. Wire format: documentation/reference/cubrim-web-profile-format
// in the cubrim repository. The decoder itself is the vendored
// #![forbid(unsafe_code)]-decode-path Rust reference decoder, consumed
// through its handle-based C ABI (`cbm_stream_*`) — one owned decoder object
// per stream, safe under the network service's interleaving.
class CbmSourceStream : public FilterSourceStream {
 public:
  explicit CbmSourceStream(std::unique_ptr<SourceStream> upstream)
      : FilterSourceStream(SourceStreamType::kCbm, std::move(upstream)) {
    if (!TryGrowReservation(0, kNativeStreamOverhead, &reservation_)) {
      return;
    }
    stream_ = cbm_stream_new_with_limits(kMaxRetainedOutput,
                                         kMaxExpansionRatio,
                                         kMaxDecoderMemory);
    if (!stream_) {
      ReleaseReservation(reservation_);
      reservation_ = 0;
    }
  }

  CbmSourceStream(const CbmSourceStream&) = delete;
  CbmSourceStream& operator=(const CbmSourceStream&) = delete;

  ~CbmSourceStream() override {
    cbm_stream_free(stream_);
    ReleaseReservation(reservation_);
  }

 private:
  // SourceStream implementation
  std::string GetTypeAsString() const override { return kCbmStreamName; }

  base::expected<size_t, Error> FilterData(IOBuffer* output_buffer,
                                           size_t output_buffer_size,
                                           IOBuffer* input_buffer,
                                           size_t input_buffer_size,
                                           size_t* consumed_bytes,
                                           bool upstream_end_reached) override {
    // The FFI constructor is nullable. Keep allocation failure request-local;
    // aborting the network service here would turn a decoder resource failure
    // into a process-wide availability failure.
    if (!stream_) {
      *consumed_bytes = input_buffer_size;
      return base::unexpected(ERR_CONTENT_DECODING_INIT_FAILED);
    }
    if (failed_) {
      *consumed_bytes = input_buffer_size;
      return base::unexpected(ERR_CONTENT_DECODING_FAILED);
    }
    if (verified_) {
      *consumed_bytes = input_buffer_size;
      return 0;
    }

    // 1. Feed every input byte to the decoder. The decoder buffers input
    //    internally, so consuming the whole chunk keeps the base-class
    //    contract: whenever this call returns 0 output bytes, all input has
    //    been consumed.
    if (input_buffer_size > 0) {
      // The FFI must allocate decoder input/output before it can report the
      // declared length. Reserve the worst native-visible footprint first so
      // concurrent streams cannot allocate past the process-wide budget and
      // only discover the collision after the allocation has happened.
      if (!SetReservation(reservation_, WorstCaseReservation(),
                          &reservation_)) {
        *consumed_bytes = input_buffer_size;
        Fail();
        return base::unexpected(ERR_CONTENT_DECODING_INIT_FAILED);
      }
      if (cbm_stream_push(
              stream_, reinterpret_cast<const uint8_t*>(input_buffer->data()),
              input_buffer_size) != 1) {
        *consumed_bytes = input_buffer_size;
        Fail();
        return base::unexpected(ERR_CONTENT_DECODING_FAILED);
      }
      const size_t fresh_len = cbm_stream_fresh_len(stream_);
      if (fresh_len > 0) {
        const uint8_t* fresh_ptr = cbm_stream_fresh_ptr(stream_);
        if (!fresh_ptr) {
          *consumed_bytes = input_buffer_size;
          Fail();
          return base::unexpected(ERR_CONTENT_DECODING_FAILED);
        }
        base::span<const uint8_t> fresh_span = UNSAFE_BUFFERS(
            base::span(fresh_ptr, fresh_len));
        pending_.insert(pending_.end(), fresh_span.begin(), fresh_span.end());
      }
    }
    *consumed_bytes = input_buffer_size;

    if (!RefreshReservation()) {
      Fail();
      return base::unexpected(ERR_CONTENT_DECODING_FAILED);
    }

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
          Fail();
          return base::unexpected(ERR_CONTENT_DECODING_FAILED);
        }
        verified_ = true;
        ReleaseReservation(reservation_);
        reservation_ = 0;
      }
      return 0;
    }

    // Need more input; everything handed to us has been consumed.
    return 0;
  }

  static constexpr size_t WorstCaseReservation() {
    return kNativeStreamOverhead + kMaxDecoderMemory + kMaxRetainedOutput;
  }

  void Fail() {
    cbm_stream_free(stream_);
    stream_ = nullptr;
    std::vector<uint8_t>().swap(pending_);
    pending_offset_ = 0;
    ReleaseReservation(reservation_);
    reservation_ = 0;
    failed_ = true;
  }

  bool RefreshReservation() {
    const size_t measured = cbm_stream_memory_usage(stream_);
    const size_t pending = pending_.capacity();
    const size_t actual = measured > std::numeric_limits<size_t>::max() - pending
                              ? std::numeric_limits<size_t>::max()
                              : measured + pending;

    // Once the frame header is known, admit the decoder's full configured
    // budget plus the native pending-output copy before the next push. The
    // measured capacity remains the lower bound for small frames.
    const uint64_t declared = cbm_stream_declared_len(stream_);
    size_t admission = WorstCaseReservation();
    if (declared != std::numeric_limits<uint64_t>::max()) {
      const size_t output = static_cast<size_t>(std::min<uint64_t>(
          declared, static_cast<uint64_t>(kMaxRetainedOutput)));
      if (kNativeStreamOverhead > std::numeric_limits<size_t>::max() -
                                     kMaxDecoderMemory - output) {
        admission = std::numeric_limits<size_t>::max();
      } else {
        admission = kNativeStreamOverhead + kMaxDecoderMemory + output;
      }
    }
    const size_t desired = std::max(actual, admission);
    return SetReservation(reservation_, desired, &reservation_);
  }

  // Owned by Rust (Box::into_raw); not PartitionAlloc memory, so raw_ptr
  // is wrong here — exclude it explicitly.
  size_t reservation_ = 0;
  RAW_PTR_EXCLUSION CbmStream* stream_ = nullptr;
  std::vector<uint8_t> pending_;
  size_t pending_offset_ = 0;
  bool verified_ = false;
  bool failed_ = false;
};

}  // namespace

std::unique_ptr<FilterSourceStream> CreateCbmSourceStream(
    std::unique_ptr<SourceStream> upstream) {
  return std::make_unique<CbmSourceStream>(std::move(upstream));
}

size_t CbmAggregateMemoryBudgetForTesting() {
  return g_cbm_aggregate_budget.load(std::memory_order_acquire);
}

void SetCbmAggregateMemoryBudgetForTesting(size_t bytes) {
  g_cbm_aggregate_budget.store(bytes, std::memory_order_release);
}

}  // namespace net
