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

#include <optional>
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
  explicit CbmTestServer(bool force_cbm = false) : force_cbm_(force_cbm) {
    server_.RegisterRequestHandler(
        base::BindRepeating(&CbmTestServer::Handle, base::Unretained(this)));
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
    std::string identity(reinterpret_cast<const char*>(kCbmGoldenOriginal),
                         sizeof(kCbmGoldenOriginal));
    const bool client_accepts_cbm =
        last_accept_encoding_.find("cbm") != std::string::npos;
    const bool serve_cbm = force_cbm_ || client_accepts_cbm;
    const std::string& body = serve_cbm ? frame : identity;
    std::string headers = "HTTP/1.1 200 OK\r\n";
    headers += "Content-Type: application/json\r\n";
    headers += "Vary: Accept-Encoding\r\n";
    if (serve_cbm) {
      headers += "Content-Encoding: cbm\r\n";
    }
    base::StringAppendF(&headers, "Content-Length: %zu\r\n", body.size());
    return std::make_unique<test_server::RawHttpResponse>(headers, body);
  }

  test_server::EmbeddedTestServer server_;
  const bool force_cbm_;
  std::string last_accept_encoding_;
};

class CbmUrlRequestTest : public TestWithTaskEnvironment {};

// The load-bearing browser-path test: one URL negotiates CBM when enabled and
// falls back to identity when disabled. The server is conditional, so this
// fails if the client advertises incorrectly or the response path is not
// actually controlled by the feature.
TEST_F(CbmUrlRequestTest, SameUrlNegotiatesCbmAndIdentity) {
  CbmTestServer server;
  ASSERT_TRUE(server.Start());
  const GURL url = server.url();

  {
    base::test::ScopedFeatureList features;
    features.InitAndEnableFeature(features::kCbmContentEncoding);

    auto context = CreateTestURLRequestContextBuilder()->Build();
    TestDelegate d;
    std::unique_ptr<URLRequest> r(context->CreateRequest(
        url, DEFAULT_PRIORITY, &d, TRAFFIC_ANNOTATION_FOR_TESTS));
    r->Start();
    d.RunUntilComplete();

    EXPECT_EQ(OK, d.request_status());
    ASSERT_EQ(sizeof(kCbmGoldenOriginal), d.data_received().size());
    EXPECT_EQ(
        std::string_view(reinterpret_cast<const char*>(kCbmGoldenOriginal),
                         sizeof(kCbmGoldenOriginal)),
        d.data_received());
    // The client advertised cbm (feature on, localhost is a secure-enough
    // context for advanced encodings), and the server selected it.
    EXPECT_NE(std::string::npos, server.last_accept_encoding().find("cbm"));
    ASSERT_TRUE(r->response_headers());
    const std::optional<std::string> content_encoding =
        r->response_headers()->GetNormalizedHeader("Content-Encoding");
    ASSERT_TRUE(content_encoding);
    EXPECT_EQ("cbm", *content_encoding);
    const std::optional<std::string> vary =
        r->response_headers()->GetNormalizedHeader("Vary");
    ASSERT_TRUE(vary);
    EXPECT_EQ("Accept-Encoding", *vary);
  }

  {
    base::test::ScopedFeatureList features;
    features.InitAndDisableFeature(features::kCbmContentEncoding);

    auto context = CreateTestURLRequestContextBuilder()->Build();
    TestDelegate d;
    std::unique_ptr<URLRequest> r(context->CreateRequest(
        url, DEFAULT_PRIORITY, &d, TRAFFIC_ANNOTATION_FOR_TESTS));
    r->Start();
    d.RunUntilComplete();

    EXPECT_EQ(OK, d.request_status());
    ASSERT_EQ(sizeof(kCbmGoldenOriginal), d.data_received().size());
    EXPECT_EQ(
        std::string_view(reinterpret_cast<const char*>(kCbmGoldenOriginal),
                         sizeof(kCbmGoldenOriginal)),
        d.data_received());
    EXPECT_EQ(std::string::npos, server.last_accept_encoding().find("cbm"));
    ASSERT_TRUE(r->response_headers());
    EXPECT_FALSE(
        r->response_headers()->GetNormalizedHeader("Content-Encoding"));
    const std::optional<std::string> vary =
        r->response_headers()->GetNormalizedHeader("Vary");
    ASSERT_TRUE(vary);
    EXPECT_EQ("Accept-Encoding", *vary);
  }
}

// A server that ignores negotiation must not make a disabled client decode an
// unsolicited cbm response. This is distinct from the same-URL identity
// control above: it proves the decoder dispatch itself is feature-gated.
TEST_F(CbmUrlRequestTest, FeatureOffRejectsForcedCbmResponse) {
  base::test::ScopedFeatureList features;
  features.InitAndDisableFeature(features::kCbmContentEncoding);

  CbmTestServer server(/*force_cbm=*/true);
  ASSERT_TRUE(server.Start());

  auto context = CreateTestURLRequestContextBuilder()->Build();
  TestDelegate d;
  std::unique_ptr<URLRequest> r(context->CreateRequest(
      server.url(), DEFAULT_PRIORITY, &d, TRAFFIC_ANNOTATION_FOR_TESTS));
  r->Start();
  d.RunUntilComplete();

  EXPECT_EQ(ERR_CONTENT_DECODING_INIT_FAILED, d.request_status());
  EXPECT_TRUE(d.data_received().empty());
  EXPECT_EQ(std::string::npos, server.last_accept_encoding().find("cbm"));
}

}  // namespace
}  // namespace net
