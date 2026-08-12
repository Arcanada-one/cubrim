// Copyright 2026 The Cubrim Authors (demo fork, CUBR-0079).
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// End-to-end over the real URLRequest path: this is what the browser does that
// CbmSourceStreamTest (MockSourceStream) does not — the feature-gated
// Accept-Encoding advertisement, the Content-Encoding dispatch in
// URLRequestHttpJob::SetUpSourceStream, and the decode, all over real HTTP via
// EmbeddedTestServer. It covers exactly the integration edits (feature,
// advertisement, dispatch switch) the browser demo would exercise manually.

#include <string>
#include <string_view>

#include "base/strings/string_util.h"
#include "base/test/scoped_feature_list.h"
#include "net/base/features.h"
#include "net/test/embedded_test_server/embedded_test_server.h"
#include "net/test/embedded_test_server/http_request.h"
#include "net/test/embedded_test_server/http_response.h"
#include "net/test/test_with_task_environment.h"
#include "net/traffic_annotation/network_traffic_annotation_test_helper.h"
#include "net/url_request/url_request.h"
#include "net/url_request/url_request_context.h"
#include "net/url_request/url_request_context_builder.h"
#include "net/url_request/url_request_test_util.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace net {
namespace {

#include "net/filter/cbm_golden.inc"

// Serves the golden frame under Content-Encoding: cbm, and records the
// Accept-Encoding the client sent (so a test can assert advertisement).
class CbmTestServer {
 public:
  CbmTestServer() {
    server_.RegisterRequestHandler(base::BindRepeating(
        &CbmTestServer::Handle, base::Unretained(this)));
  }

  bool Start() { return server_.Start(); }
  GURL url() { return server_.GetURL("/doc"); }
  std::string last_accept_encoding() const { return last_accept_encoding_; }

 private:
  std::unique_ptr<test_server::HttpResponse> Handle(
      const test_server::HttpRequest& request) {
    auto it = request.headers.find("Accept-Encoding");
    last_accept_encoding_ = it != request.headers.end() ? it->second : "";

    std::string frame(reinterpret_cast<const char*>(kCbmGoldenFrame),
                      sizeof(kCbmGoldenFrame));
    std::string headers = "HTTP/1.1 200 OK\r\n";
    headers += "Content-Type: application/json\r\n";
    headers += "Content-Encoding: cbm\r\n";
    base::StringAppendF(&headers, "Content-Length: %zu\r\n", frame.size());
    return std::make_unique<test_server::RawHttpResponse>(headers, frame);
  }

  test_server::EmbeddedTestServer server_;
  std::string last_accept_encoding_;
};

class CbmUrlRequestTest : public TestWithTaskEnvironment {};

// The load-bearing browser-path test: a cbm response fetched over real HTTP is
// decoded byte-exact by the network stack — advertisement, dispatch, decode.
TEST_F(CbmUrlRequestTest, DecodesCbmResponseOverHttp) {
  base::test::ScopedFeatureList features;
  features.InitAndEnableFeature(features::kCbmContentEncoding);

  CbmTestServer server;
  ASSERT_TRUE(server.Start());

  auto context = CreateTestURLRequestContextBuilder()->Build();
  TestDelegate d;
  std::unique_ptr<URLRequest> r(context->CreateRequest(
      server.url(), DEFAULT_PRIORITY, &d, TRAFFIC_ANNOTATION_FOR_TESTS));
  r->Start();
  d.RunUntilComplete();

  EXPECT_EQ(OK, d.request_status());
  ASSERT_EQ(sizeof(kCbmGoldenOriginal), d.data_received().size());
  EXPECT_EQ(std::string_view(reinterpret_cast<const char*>(kCbmGoldenOriginal),
                             sizeof(kCbmGoldenOriginal)),
            d.data_received());
  // The client advertised cbm (feature on, localhost is a secure-enough
  // context for advanced encodings).
  EXPECT_NE(std::string::npos, server.last_accept_encoding().find("cbm"));
}

// With the feature off, the client must NOT advertise cbm — the demo coding is
// gated and a stock build is unchanged.
TEST_F(CbmUrlRequestTest, DoesNotAdvertiseCbmWhenFeatureOff) {
  base::test::ScopedFeatureList features;
  features.InitAndDisableFeature(features::kCbmContentEncoding);

  CbmTestServer server;
  ASSERT_TRUE(server.Start());

  auto context = CreateTestURLRequestContextBuilder()->Build();
  TestDelegate d;
  std::unique_ptr<URLRequest> r(context->CreateRequest(
      server.url(), DEFAULT_PRIORITY, &d, TRAFFIC_ANNOTATION_FOR_TESTS));
  r->Start();
  d.RunUntilComplete();

  // The server still forces cbm and the dispatch still decodes it (recognition
  // is not feature-gated, only advertisement is), so the body is correct — but
  // the client did not ASK for cbm.
  EXPECT_EQ(std::string::npos, server.last_accept_encoding().find("cbm"));
}

}  // namespace
}  // namespace net
