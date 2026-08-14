// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "net/filter/cbm_source_stream.h"

#include <stdint.h>

#include <algorithm>
#include <string>
#include <string_view>
#include <vector>

#include "base/containers/span.h"
#include "base/memory/scoped_refptr.h"
#include "net/base/io_buffer.h"
#include "net/base/net_errors.h"
#include "net/base/test_completion_callback.h"
#include "net/filter/mock_source_stream.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "testing/platform_test.h"

namespace net {
namespace {

// A real MODE_WEB frame and its decoded bytes, generated from the pinned web
// census (json-api-small-hypotheses-v2.json) with the in-repo encoder. This
// is the whole point of the fork: bytes decoded here travel through the same
// vendored reference decoder a browser would run.
#include "net/filter/cbm_golden.inc"

class CbmSourceStreamTest : public PlatformTest {
 protected:
  // Feed the frame through CbmSourceStream in `chunk` byte pieces and return
  // the fully decoded output. `out_error` receives the terminal Read result.
  std::vector<uint8_t> Decode(base::span<const uint8_t> frame,
                              size_t chunk,
                              int* out_error) {
    auto source = std::make_unique<MockSourceStream>();
    MockSourceStream* raw_source = source.get();
    for (size_t off = 0; off < frame.size(); off += chunk) {
      const size_t n = std::min(chunk, frame.size() - off);
      raw_source->AddReadResult(base::as_string_view(frame.subspan(off, n)), OK,
                                MockSourceStream::SYNC);
    }
    raw_source->AddReadResult(std::string_view(), OK, MockSourceStream::SYNC);

    std::unique_ptr<SourceStream> stream =
        CreateCbmSourceStream(std::move(source));
    EXPECT_EQ("CBM", stream->Description());

    std::vector<uint8_t> out;
    auto buffer = base::MakeRefCounted<IOBufferWithSize>(4096u);
    for (;;) {
      TestCompletionCallback callback;
      int rv = stream->Read(buffer.get(), buffer->size(), callback.callback());
      if (rv == ERR_IO_PENDING) {
        rv = callback.WaitForResult();
      }
      if (rv <= 0) {
        // A decoder can reject a corrupt frame before the upstream EOF marker
        // is read. In that terminal-error case the mock's queued EOF is not
        // an unconsumed input contract violation.
        if (rv < 0) {
          raw_source->set_expect_all_input_consumed(false);
        }
        *out_error = rv;
        break;
      }
      const auto produced = buffer->span().first(static_cast<size_t>(rv));
      out.insert(out.end(), produced.begin(), produced.end());
    }
    return out;
  }
};

class ScopedCbmAggregateBudget {
 public:
  explicit ScopedCbmAggregateBudget(size_t bytes)
      : previous_(CbmAggregateMemoryBudgetForTesting()) {
    SetCbmAggregateMemoryBudgetForTesting(bytes);
  }

  ScopedCbmAggregateBudget(const ScopedCbmAggregateBudget&) = delete;
  ScopedCbmAggregateBudget& operator=(const ScopedCbmAggregateBudget&) = delete;

  ~ScopedCbmAggregateBudget() {
    SetCbmAggregateMemoryBudgetForTesting(previous_);
  }

 private:
  const size_t previous_;
};

std::unique_ptr<FilterSourceStream> EmptyCbmStream() {
  auto source = std::make_unique<MockSourceStream>();
  source->AddReadResult(std::string_view(), OK, MockSourceStream::SYNC);
  source->set_expect_all_input_consumed(false);
  return CreateCbmSourceStream(std::move(source));
}

// The load-bearing test: a real frame decodes byte-exact through the whole
// vendored Rust decoder, checksum and all.
TEST_F(CbmSourceStreamTest, GoldenFrameDecodesByteExact) {
  int error = 1;
  std::vector<uint8_t> out = Decode(base::span(kCbmGoldenFrame), 4096, &error);
  EXPECT_EQ(OK, error);
  ASSERT_EQ(sizeof(kCbmGoldenOriginal), out.size());
  EXPECT_TRUE(
      std::equal(out.begin(), out.end(), std::begin(kCbmGoldenOriginal)));
}

// The same frame arriving in tiny pieces must decode identically — the
// streaming path that a network body actually exercises.
TEST_F(CbmSourceStreamTest, GoldenFrameDecodesAcrossChunkSizes) {
  for (size_t chunk : {size_t{1}, size_t{7}, size_t{64}, size_t{512}}) {
    int error = 1;
    std::vector<uint8_t> out =
        Decode(base::span(kCbmGoldenFrame), chunk, &error);
    EXPECT_EQ(OK, error) << "chunk " << chunk;
    ASSERT_EQ(sizeof(kCbmGoldenOriginal), out.size()) << "chunk " << chunk;
    EXPECT_TRUE(
        std::equal(out.begin(), out.end(), std::begin(kCbmGoldenOriginal)))
        << "chunk " << chunk;
  }
}

// A flipped byte must fail the stream with ERR_CONTENT_DECODING_FAILED, never
// return silently-wrong output — the trailing checksum is the last line.
TEST_F(CbmSourceStreamTest, CorruptFrameFails) {
  std::vector<uint8_t> corrupt(std::begin(kCbmGoldenFrame),
                               std::end(kCbmGoldenFrame));
  corrupt[corrupt.size() / 2] ^= 0xFF;
  int error = 1;
  std::vector<uint8_t> out = Decode(base::span(corrupt), 4096, &error);
  EXPECT_EQ(ERR_CONTENT_DECODING_FAILED, error);
  // Even if some bytes were emitted before the failure, the result is not a
  // clean copy of the original.
  EXPECT_FALSE(
      out.size() == sizeof(kCbmGoldenOriginal) &&
      std::equal(out.begin(), out.end(), std::begin(kCbmGoldenOriginal)));
}

// A truncated frame (EOF before the declared length) fails, not silently
// returns a short body.
TEST_F(CbmSourceStreamTest, TruncatedFrameFails) {
  base::span<const uint8_t> whole(kCbmGoldenFrame);
  int error = 1;
  std::vector<uint8_t> out =
      Decode(whole.first(whole.size() - 8), 4096, &error);
  EXPECT_EQ(ERR_CONTENT_DECODING_FAILED, error);
}

TEST_F(CbmSourceStreamTest, AggregateAdmissionIsRequestLocalAndReleased) {
  // The base admission floor deliberately admits two streams but not three.
  // Removing the shared guard makes the third stream read through; failing to
  // release on destruction makes the recycled stream fail as well.
  ScopedCbmAggregateBudget budget(2 * 1024 * 1024);
  auto first = EmptyCbmStream();
  auto second = EmptyCbmStream();
  auto blocked = EmptyCbmStream();
  ASSERT_TRUE(second);

  auto buffer = base::MakeRefCounted<IOBufferWithSize>(64u);
  TestCompletionCallback blocked_callback;
  const int blocked_result =
      blocked->Read(buffer.get(), buffer->size(), blocked_callback.callback());
  EXPECT_EQ(ERR_CONTENT_DECODING_INIT_FAILED, blocked_result);

  first.reset();
  auto recycled = EmptyCbmStream();
  auto blocked_again = EmptyCbmStream();
  ASSERT_TRUE(recycled);
  TestCompletionCallback blocked_again_callback;
  const int blocked_again_result = blocked_again->Read(
      buffer.get(), buffer->size(), blocked_again_callback.callback());
  EXPECT_EQ(ERR_CONTENT_DECODING_INIT_FAILED, blocked_again_result);
}

}  // namespace
}  // namespace net
