# Cubrim Browser Technology Preview — build instructions (CUBR-0079)

Reproduces the demo fork: a pinned Chromium tree plus the patch series in
this directory (patches land in Phase P1; this file is written at P0 so the
pin and the recipe exist before the first build hour is spent).

Design and phase plan: `~/arcanada/datarim/prd/PRD-CUBR-0079.md` +
`~/arcanada/datarim/reports/CUBR-0079-design-consilium.md`.

## Pin

| what | value |
|---|---|
| Chromium tag | **151.0.7922.137** (Linux stable channel) |
| chromium/src commit | `8f5d36bc16f57115aeeff34baf4ad6aa964d509c` |
| released | 2026-08-11T23:58:29Z (queried chromiumdash 2026-08-12) |
| cubrim decoder | vendored from cubrim main `53276b3` (`code/cubrim-web-decoder`) |

Rebase policy: **none** — the tag is the contract for the demo. A newer
stable only matters if the patch series stops applying, and then the pin is
updated deliberately, in its own commit.

## Host

Build on **arcana-kb** (12 threads / 62 GB RAM). Preconditions, from the
measured stand decision (consilium memo C):

- ≥150 GB free at build start (`df -BG /`), abort-and-clean if free space
  drops under 30 GB mid-build;
- exactly ONE out dir — a second gn config blows the disk margin;
- **never build on arcana-devs** (agent-fleet box, CI runners — fleet rule).

## Recipe

```sh
# 1. depot_tools
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$PWD/depot_tools:$PATH"

# 2. fetch at the pin, no history (~45-60 GB after hooks, 1-2 h)
mkdir chromium && cd chromium
fetch --no-history chromium
cd src
git fetch --depth 1 origin refs/tags/151.0.7922.137
git checkout FETCH_HEAD
gclient sync -D --no-history

# 3. apply the series (P1 artefacts; ordered)
for p in ../../patches/0*.patch; do git apply --index "$p"; done

# 4. smoke gate FIRST (~1.5-2.5 h): prove the decoder in net_unittests
gn gen out/cbm --args='is_debug=false symbol_level=0 blink_symbol_level=0
  v8_symbol_level=0 is_component_build=true enable_nacl=false
  is_official_build=false use_remoteexec=false'
autoninja -C out/cbm net_unittests
out/cbm/net_unittests --gtest_filter='CbmSourceStream*'
# NO-GO here = stop; do not spend the target build.

# 5. the preview target (~5-7 h cold on 12 threads)
autoninja -C out/cbm content_shell
```

## Demo

```sh
# origin + proxy (both in this repo, already on main):
node code/cubrim-web-decoder/web/serve.mjs <site-dir> 8080     # or any origin
cargo run --release --manifest-path code/cubrimd/Cargo.toml -- \
  --origin http://127.0.0.1:8080 --listen 127.0.0.1:8078

# the patched browser:
out/cbm/content_shell --enable-features=CbmContentEncoding \
  --log-net-log=/tmp/cbm-demo-netlog.json http://127.0.0.1:8078/
# No TLS needed: the advanced-encoding guard at the pinned tag is
# `url.SchemeIsCryptographic() || IsLocalhost(url)`
# (net/http/http_request_headers.cc, SetAcceptEncodingIfMissing), so br/zstd —
# and cbm alongside them — advertise on plain-http localhost. The P0-era open
# decision (loopback TLS vs relaxing the check) is RESOLVED: neither is needed.
```

Evidence to record (PRD V-AC2/V-AC3): netlog with `Accept-Encoding: … cbm`
request + `Content-Encoding: cbm` response; rendered-page screenshot;
wire-vs-decoded byte counts; `sha256(decoded) == sha256(origin file)`; a
control run without the flag receiving identity via the proxy's fallback.

## Prep artefacts already in this directory (P0, done 2026-08-12)

- `ffi-check.c` — standing native proof of the C ABI the patch consumes:
  abi=1, byte-exact golden decode, corrupt frame rejected cleanly. Run it
  after any decoder change before touching the Chromium tree.
- `testdata/golden-manifest.tsv` — sha256 pins for the 12 census originals
  and their single-block frames (regeneration recipe in `testdata/README.md`).

## FFI surface the patch links (verified 2026-08-12)

The wasm ABI (`src/wasm.rs`, `cbr_*`) keeps stream state in a thread_local
single slot — correct for a wasm instance, wrong for the network service,
which interleaves many response streams per thread. The Chromium patch links
the handle-based native ABI instead (`src/ffi.rs`, `cbm_stream_*`): one owned
heap object per stream, any number interleaved. Proven by
`tests/ffi_handles.rs`, including three streams interleaved on one thread,
1-byte-chunk feeds, poisoning after corruption, output-cap enforcement and
raw-store passthrough. `cbm_stream_declared_len` lets CbmSourceStream check
its output budget before decoding a block.

## Hard gate

This is a demo fork. **No upstream CL, no chromium.org interaction, no public
release of the fork or its binaries — operator sign-off required for each**
(CUBR-0079/0080 hard gates).
