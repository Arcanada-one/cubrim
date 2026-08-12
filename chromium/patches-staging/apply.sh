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

# 5. advertisement in http_request_headers.cc, gated + HTTPS/localhost like zstd.
#    The includes are added separately below (this file does not yet include
#    features.h / feature_list.h at the pinned tag — VERIFIED on the synced
#    tree, where the bogus no-op include anchor this edit used to carry made
#    the whole script abort).
edit('net/http/http_request_headers.cc',
     ['kCbmContentEncoding'],
     [('constexpr char kEncodingZstd[] = "zstd";',
       'constexpr char kEncodingZstd[] = "zstd";\nconstexpr char kEncodingCbm[] = "cbm";'),
      ('  if (!advertised_encoding_names.empty()) {',
       '  // CUBR-0079 demo coding, same secure/localhost guard as br/zstd.\n'
       '  if (base::FeatureList::IsEnabled(features::kCbmContentEncoding) &&\n'
       '      SupportsStreamType(accepted_stream_types, SourceStreamType::kCbm) &&\n'
       '      can_use_advanced_encodings) {\n'
       '    advertised_encoding_names.emplace_back(kEncodingCbm);\n'
       '  }\n'
       '  if (!advertised_encoding_names.empty()) {')])

# 5b. the two includes http_request_headers.cc needs for the feature check.
#     Anchored on base/logging.h (present at the tag) — a sed with a '#'
#     delimiter fails on the '#include' text, so this is done in Python.
def add_includes(path, anchor, includes):
    s = io.open(path).read()
    add = ''.join(inc + '\n' for inc in includes if inc.split('"')[1] not in s)
    if add:
        assert s.count(anchor) >= 1, f"{path}: include anchor missing"
        s = s.replace(anchor, add + anchor, 1)
        io.open(path, 'w').write(s)
        print(f"  {path}: includes added")
    else:
        print(f"  {path}: includes already present")

add_includes('net/http/http_request_headers.cc',
             '#include "base/logging.h"',
             ['#include "base/feature_list.h"', '#include "net/base/features.h"'])
PY

echo "== BUILD.gn: add cbm_source_stream sources + third_party/cubrim dep"
python3 - <<'PY'
import io
f='net/BUILD.gn'; s=io.open(f).read()
if 'cbm_source_stream.cc' not in s:
    anchor='      "filter/brotli_source_stream.cc",\n      "filter/brotli_source_stream.h",'
    assert s.count(anchor)==1
    s=s.replace(anchor, anchor+'\n      "filter/cbm_source_stream.cc",\n      "filter/cbm_source_stream.h",')
    io.open(f,'w').write(s); print('  net/BUILD.gn: sources patched')
else:
    print('  net/BUILD.gn: sources already patched')
# //third_party/cubrim dep on the net component (VERIFIED anchor on the tree).
if '//third_party/cubrim' not in s:
    dep_anchor='  deps = [\n    ":cronet_buildflags",\n    ":net_deps",'
    assert s.count(dep_anchor)==1, 'net component deps anchor'
    s=s.replace(dep_anchor, dep_anchor+'\n    "//third_party/cubrim",')
    io.open(f,'w').write(s); print('  net/BUILD.gn: //third_party/cubrim dep added')
else:
    print('  net/BUILD.gn: dep already present')
PY

echo "== services/network mojom SourceType + traits: add the kCbm case"
# net_unittests does NOT compile these, so this is invisible until a target
# that does (content_shell) is built — exactly the second unknown flagged at
# P1. The net::SourceStreamType enum's LINT.ThenChange points here.
python3 - <<'PY'
import io
f='services/network/public/mojom/source_type.mojom'; s=io.open(f).read()
if 'kCbm' not in s:
    s=s.replace('  kZstd,\n', '  kZstd,\n  kCbm,\n', 1)
    io.open(f,'w').write(s); print('  mojom SourceType: kCbm added')
else:
    print('  mojom SourceType: already present')

f='services/network/public/cpp/source_type_mojom_traits.cc'; s=io.open(f).read()
if 'kCbm' not in s:
    s=s.replace(
      '    case net::SourceStreamType::kZstd:\n      return network::mojom::SourceType::kZstd;\n',
      '    case net::SourceStreamType::kZstd:\n      return network::mojom::SourceType::kZstd;\n    case net::SourceStreamType::kCbm:\n      return network::mojom::SourceType::kCbm;\n', 1)
    s=s.replace(
      '    case network::mojom::SourceType::kZstd:\n      return net::SourceStreamType::kZstd;\n',
      '    case network::mojom::SourceType::kZstd:\n      return net::SourceStreamType::kZstd;\n    case network::mojom::SourceType::kCbm:\n      return net::SourceStreamType::kCbm;\n', 1)
    io.open(f,'w').write(s); print('  mojom traits: both switches patched')
else:
    print('  mojom traits: already present')
PY

echo "== third_party/cubrim: vendored decoder target"
echo "   BUILD.gn + the crate live under third_party/cubrim/. Two states:"
echo "   - integration-check: ffi/stub_ffi.cc satisfies the linker so //net"
echo "     compiles+links WITHOUT the real decoder (blake3 not yet vendored)."
echo "   - real decoder: rust_static_library over code/cubrim-web-decoder once"
echo "     blake3 + deps are vendored via tools/crates (gnrt). See BUILD.md."

echo "== DONE (apply). Next: gn gen out/cbm && autoninja -C out/cbm net_unittests"
echo "   Env prereqs proven on the tree (see BUILD.md): depot_tools cpython3"
echo "   bootstrap + build/install-build-deps.sh. gn gen is GREEN with these edits."
echo "   A services/network mojom-traits switch over SourceStreamType may still"
echo "   need a kCbm case — the net_unittests compile names it if so."
