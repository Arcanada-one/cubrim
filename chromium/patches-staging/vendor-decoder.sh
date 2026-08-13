#!/usr/bin/env bash
# Vendor the Cubrim reference decoder (and blake3) into a Chromium tree so the
# CbmSourceStream links the REAL decoder, not the integration-check stub
# (CUBR-0079 P2). Run from chromium/src AFTER apply.sh, with CBM_STAGING set and
# CUBRIM_DECODER pointing at a checkout of code/cubrim-web-decoder (blake3 must
# already be the `pure` feature there — cubrim PR #206).
#
# STATUS: this exact sequence was executed on the synced arcana-kb tree
# (Chromium 151.0.7922.137) and the resulting net_unittests passes the four
# CbmSourceStreamTest cases plus the two CbmUrlRequestTest negotiation cases
# (golden byte-exact, chunked 1/7/64/512, corrupt and truncated rejected).
# Each step below is the fix for a concrete failure
# the build named, in order.
set -euo pipefail
: "${CBM_STAGING:?}"; : "${CUBRIM_DECODER:?}"
test -f tools/crates/run_gnrt.py || { echo "run from chromium/src"; exit 1; }
GNRT() { vpython3 tools/crates/run_gnrt.py "$@"; }
CIO=third_party/rust/chromium_crates_io

echo "== 1. decoder crate into the tree (crate_root for the rust_static_library)"
mkdir -p third_party/cubrim/decoder/src
cp "$CUBRIM_DECODER"/src/{lib.rs,ffi.rs,wasm.rs} third_party/cubrim/decoder/src/
cp "$CBM_STAGING"/third_party/cubrim/BUILD.gn third_party/cubrim/BUILD.gn

echo "== 2. blake3 (pure) into the crate manifest"
grep -q '^blake3' "$CIO/Cargo.toml" || \
  sed -i 's|^bitflags = "2"|bitflags = "2"\nblake3 = { version = "1.8.5", default-features = false, features = ["pure"] }|' "$CIO/Cargo.toml"

echo "== 3. gnrt_config: blake3 license files (vendored dir names them non-standardly)"
grep -q '\[crate.blake3\]' "$CIO/gnrt_config.toml" || cat >> "$CIO/gnrt_config.toml" <<'CFG'

[crate.blake3]
# blake3 resolves to a single Apache-2.0 licensee out of its OR expression.
license_files = ["LICENSE_A2"]
allow_first_party_usage = false
CFG

echo "== 4. teach gnrt the two license kinds its table lacks (arrayref BSD-2, constant_time_eq CC0)"
python3 - <<'PY'
import io
f="tools/crates/gnrt/lib/readme.rs"; s=io.open(f).read()
if "\n    BSD2,\n" not in s:
    a='    #[strum(serialize = "BSD-3-Clause")]\n    BSD3,\n'
    s=s.replace(a, a+'    /// https://spdx.org/licenses/BSD-2-Clause.html\n    #[strum(serialize = "BSD-2-Clause")]\n    BSD2,\n    /// https://spdx.org/licenses/CC0-1.0.html\n    #[strum(serialize = "CC0-1.0")]\n    CC0,\n')
    io.open(f,'w').write(s); print("  gnrt: BSD2+CC0 taught")
else: print("  gnrt: already taught")
PY

echo "== 5. vendor + gen (downloads blake3/arrayref/arrayvec/constant_time_eq/cpufeatures)"
GNRT vendor
GNRT gen

echo "== 6. post-gen fixups the build named"
# 6a. cpufeatures embeds its README via include_str! — gnrt omits it from inputs.
sed -i 's|  inputs = \[\]|  inputs = [ "//third_party/rust/chromium_crates_io/vendor/cpufeatures-v0_3/README.md" ]|' \
  third_party/rust/cpufeatures/v0_3/BUILD.gn
# 6b. blake3 pure uses pure-Rust SIMD; its build.rs (which also drags in the cc
#     crate for the non-pure C path, whose gnrt BUILD.gn is incomplete) only
#     sets these three cfgs. Set them directly and drop the build script.
python3 - <<'PY'
import io
f="third_party/rust/blake3/v1/BUILD.gn"; s=io.open(f).read()
s=s.replace('  build_deps = [ "//third_party/rust/cc/v1:buildrs_support" ]\n','')
s=s.replace('  build_root = "//third_party/rust/chromium_crates_io/vendor/blake3-v1/build.rs"\n  build_sources =\n      [ "//third_party/rust/chromium_crates_io/vendor/blake3-v1/build.rs" ]\n','')
if "blake3_sse2_rust" not in s:
    a='  features = [ "pure" ]\n'
    s=s.replace(a, a+'  rustflags = [\n    "--cfg=blake3_sse2_rust",\n    "--cfg=blake3_sse41_rust",\n    "--cfg=blake3_avx2_rust",\n  ]\n')
io.open(f,'w').write(s); print("  blake3: build.rs dropped, pure-SIMD cfgs set")
PY

echo "== 7. wire both cbm tests into net_unittests"
cp "$CBM_STAGING"/net/filter/cbm_source_stream_unittest.cc net/filter/
cp "$CBM_STAGING"/net/filter/cbm_url_request_unittest.cc net/filter/
cp "$CBM_STAGING"/net/filter/cbm_golden.inc net/filter/
python3 - <<'PY'
import io
f="net/BUILD.gn"; s=io.open(f).read()
if "cbm_source_stream_unittest.cc" not in s:
    a='  if (!disable_brotli_filter) {\n    sources += [ "filter/brotli_source_stream_unittest.cc" ]\n  }\n'
    add=a + '  sources += [ "filter/cbm_source_stream_unittest.cc" ]\n'
    add += '  sources += [ "filter/cbm_url_request_unittest.cc" ]\n'
    s=s.replace(a, add)
    io.open(f,'w').write(s); print("  net_unittests: cbm SourceStream + URLRequest tests wired")
else: print("  net_unittests: already wired")
PY

echo "== DONE. Now: gn gen out/cbm && autoninja -C out/cbm net_unittests"
echo "   out/cbm/net_unittests --gtest_filter='CbmSourceStream*'  # expect 4/4 PASS"
echo "   out/cbm/net_unittests --gtest_filter='CbmUrlRequest*'     # expect 2/2 PASS"
echo "   The URLRequest tests exercise the real browser HTTP path — feature-gated"
echo "   Accept-Encoding advertisement, SetUpSourceStream dispatch, decode over"
echo "   EmbeddedTestServer — which the MockSourceStream test does not cover."
