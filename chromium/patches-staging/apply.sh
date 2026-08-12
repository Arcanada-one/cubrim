#!/usr/bin/env bash
# Apply the CbmSourceStream demo patch to a Chromium tree (CUBR-0079 P1→P2).
#
# Idempotent-ish: copies the new files, then makes the in-place edits guarded
# by a grep so a second run does not double-insert. Run from chromium/src with
# CBM_STAGING pointing at this directory.
#
# STATUS: these edits apply cleanly against the pinned tag 151.0.7922.137
# (sources read directly from googlesource at that tag). They are NOT yet
# compile-verified — that is Phase P2 on the synced arcana-kb tree, which is
# what turns this from a draft into a landed patch series. The exhaustive
# switch over net::SourceStreamType may need a case in a services/network
# mojom-traits file the source read did not cover; the P2 build surfaces it.
set -euo pipefail
: "${CBM_STAGING:?set CBM_STAGING to the patches-staging dir}"
test -f net/filter/filter_source_stream.cc || { echo "run from chromium/src"; exit 1; }

echo "== copy new files"
mkdir -p third_party/cubrim/ffi
cp "$CBM_STAGING"/net/filter/cbm_source_stream.h net/filter/
cp "$CBM_STAGING"/net/filter/cbm_source_stream.cc net/filter/
cp "$CBM_STAGING"/third_party/cubrim/ffi/cubrim_web_decoder.h third_party/cubrim/ffi/
# The vendored decoder crate + its BUILD.gn are dropped in by the P2 driver
# (BUILD.md step) from cubrim main code/cubrim-web-decoder; kept out of this
# script so the crate has one source of truth.

python3 - <<'PY'
import io, sys

def edit(path, checks, subs):
    s = io.open(path).read()
    if all(c in s for c in checks):
        print(f"  {path}: already patched, skipping")
        return
    for old, new in subs:
        assert s.count(old) == 1, f"{path}: anchor not unique/found: {old!r}"
        s = s.replace(old, new)
    io.open(path, 'w').write(s)
    print(f"  {path}: patched")

# 1. enum
edit('net/filter/source_stream_type.h', ['kCbm'],
     [("  kZstd,\n  kUnknown,", "  kZstd,\n  kCbm,\n  kUnknown,")])

# 2. token map + the two switches in filter_source_stream.cc
edit('net/filter/filter_source_stream.cc',
     ['SourceStreamType::kCbm'],
     [('constexpr char kZstd[] = "zstd";',
       'constexpr char kZstd[] = "zstd";\nconstexpr char kCbm[] = "cbm";'),
      ('          {kZstd, SourceStreamType::kZstd},\n      });',
       '          {kZstd, SourceStreamType::kZstd},\n          {kCbm, SourceStreamType::kCbm},\n      });'),
      ('      case SourceStreamType::kZstd:\n        if (accepted_stream_types &&',
       '      case SourceStreamType::kZstd:\n      case SourceStreamType::kCbm:\n        if (accepted_stream_types &&'),
      ('      case SourceStreamType::kZstd:\n        downstream = CreateZstdSourceStream(std::move(upstream));\n        break;',
       '      case SourceStreamType::kZstd:\n        downstream = CreateZstdSourceStream(std::move(upstream));\n        break;\n      case SourceStreamType::kCbm:\n        downstream = CreateCbmSourceStream(std::move(upstream));\n        break;')])

# 2b. include for the factory in filter_source_stream.cc
edit('net/filter/filter_source_stream.cc',
     ['cbm_source_stream.h'],
     [('#include "net/filter/brotli_source_stream.h"',
       '#include "net/filter/brotli_source_stream.h"\n#include "net/filter/cbm_source_stream.h"')])

# 3. ToContentEncodingType switch in url_request_http_job.cc — add a case so
#    the enum stays exhaustive. Map to kUnknown UMA bucket (demo coding).
edit('net/url_request/url_request_http_job.cc',
     ['SourceStreamType::kCbm:\n      return ContentEncodingType::kUnknown'],
     [('    case SourceStreamType::kZstd:\n      return ContentEncodingType::kZstd;',
       '    case SourceStreamType::kZstd:\n      return ContentEncodingType::kZstd;\n    case SourceStreamType::kCbm:\n      return ContentEncodingType::kUnknown;')])

# 4. feature declaration + definition
edit('net/base/features.h',
     ['kCbmContentEncoding'],
     [('NET_EXPORT BASE_DECLARE_FEATURE(kAlpsForHttp2);',
       'NET_EXPORT BASE_DECLARE_FEATURE(kAlpsForHttp2);\n// CUBR-0079 demo: advertise + decode the unregistered `cbm` content coding.\nNET_EXPORT BASE_DECLARE_FEATURE(kCbmContentEncoding);')])
edit('net/base/features.cc',
     ['kCbmContentEncoding'],
     [('BASE_FEATURE(kAlpsForHttp2, base::FEATURE_ENABLED_BY_DEFAULT);',
       'BASE_FEATURE(kAlpsForHttp2, base::FEATURE_ENABLED_BY_DEFAULT);\nBASE_FEATURE(kCbmContentEncoding, base::FEATURE_DISABLED_BY_DEFAULT);')])

# 5. advertisement in http_request_headers.cc, gated + HTTPS/localhost like zstd
edit('net/http/http_request_headers.cc',
     ['kCbmContentEncoding'],
     [('#include "net/base/features.h"',  # add include if missing handled below
       '#include "net/base/features.h"'),
      ('constexpr char kEncodingZstd[] = "zstd";',
       'constexpr char kEncodingZstd[] = "zstd";\nconstexpr char kEncodingCbm[] = "cbm";'),
      ('  if (!advertised_encoding_names.empty()) {',
       '  // CUBR-0079 demo coding, same secure/localhost guard as br/zstd.\n'
       '  if (base::FeatureList::IsEnabled(features::kCbmContentEncoding) &&\n'
       '      SupportsStreamType(accepted_stream_types, SourceStreamType::kCbm) &&\n'
       '      can_use_advanced_encodings) {\n'
       '    advertised_encoding_names.emplace_back(kEncodingCbm);\n'
       '  }\n'
       '  if (!advertised_encoding_names.empty()) {')])
PY

# http_request_headers.cc may not include features.h / feature_list.h yet.
grep -q '#include "net/base/features.h"' net/http/http_request_headers.cc || \
  sed -i 's##include "net/base/net_export.h"#include "base/feature_list.h"\n#include "net/base/features.h"\n#include "net/base/net_export.h"#' net/http/http_request_headers.cc || true
grep -q '#include "base/feature_list.h"' net/http/http_request_headers.cc || \
  sed -i '0,/#include/{s##include "base/feature_list.h"\n#include#}' net/http/http_request_headers.cc || true

echo "== BUILD.gn: add cbm_source_stream sources + third_party/cubrim dep"
python3 - <<'PY'
import io
f='net/BUILD.gn'; s=io.open(f).read()
if 'cbm_source_stream.cc' not in s:
    anchor='      "filter/brotli_source_stream.cc",\n      "filter/brotli_source_stream.h",'
    assert s.count(anchor)==1
    s=s.replace(anchor, anchor+'\n      "filter/cbm_source_stream.cc",\n      "filter/cbm_source_stream.h",')
    io.open(f,'w').write(s); print('  net/BUILD.gn: patched')
else:
    print('  net/BUILD.gn: already patched')
PY

echo "== DONE (apply). Next: add third_party/cubrim/BUILD.gn dep to //net, then"
echo "   gn gen out/cbm && autoninja -C out/cbm net_unittests"
echo "   NOTE: a services/network mojom-traits switch over SourceStreamType may"
echo "   still need a kCbm case — the build will name it if so."
