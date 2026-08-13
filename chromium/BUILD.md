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

## P2 environment — provisioned on arcana-kb 2026-08-12 (facts, not plan)

The synced tree needed setup the recipe above understated; recorded so the
next run does not rediscover it:

1. **depot_tools cpython3.** `gn`/`autoninja` use the depot_tools `python3`
   wrapper, which reads `python3_bin_reldir.txt`. On this host the wrapper
   pointed at an unpopulated path. Fix that worked:
   `python3 depot_tools/bootstrap/bootstrap.py --bootstrap-name python3` to
   write the reldir, then fetch the interpreter itself with the bundled cipd
   client — `depot_tools/.cipd_client ensure -ensure-file <cpython3.ensure>
   -root depot_tools/python3` (package
   `infra/3pp/tools/cpython3/${platform} version:2@3.11.8.chromium.35`, taken
   from `depot_tools/bootstrap/manifest.txt`) — and set
   `python3_bin_reldir.txt` to the actual layout (`python3/bin`). `vpython3`
   already worked and is what proves cipd is healthy.
2. **System build deps.** `gn gen` fails on missing `pkg-config`/`file`, then
   the GTK/atk stack. `apt-get install -y pkg-config file`, then
   `build/install-build-deps.sh --no-prompt --no-arm --no-nacl
   --no-chromeos-fonts`.
3. **Result:** with the apply.sh edits + `//third_party/cubrim`, **`gn gen`
   is GREEN** (31626 targets resolved) — the whole gn wiring is verified
   against the real tree. `net_unittests` compile/link is the remaining gate.

## blake3 — the one isolated sub-task for the REAL decoder

`third_party/rust/` vendors `cfg_if` but NOT blake3, which the decoder needs
for its frame checksum. The gn-integrated build therefore uses
`third_party/cubrim/ffi/stub_ffi.cc` (linker-satisfying no-op stubs) to verify
the C++ integration compiles+links. The real decoder needs blake3 + its deps
(`arrayref`, `arrayvec`, `constant_time_eq`) vendored via Chromium's crate
tooling (`tools/crates`, gnrt), then `third_party/cubrim/BUILD.gn` swapped from
the stub `static_library` to a `rust_static_library` over
`code/cubrim-web-decoder`. Until then the golden-frame V-AC1 test cannot run
in-tree; the decoder itself is already proven byte-exact natively
(`chromium/ffi-check.c`, and the handle ABI's own `ffi_handles` suite).

## Live demo — P4 (`chromium/run-demo.sh`)

Once `content_shell` is built, the demo is one script. Topology:
`patched content_shell -> web/serve.mjs (loopback :8078, negotiates
Content-Encoding: cbm per PR #199) -> pre-generated .cbr frames`.

`run-demo.sh`, `netlog_verify.py` (copy them and the census fixtures +
`web/serve.mjs`/`encoding.mjs` to the build host):

1. starts the origin/encoder (`node serve.mjs`);
2. control curl — a plain `Accept-Encoding: gzip, br` client gets identity;
3. curl with `Accept-Encoding: cbm` gets `Content-Encoding: cbm` + `Vary`;
4. `xvfb-run content_shell --run-web-tests
   --enable-features=CbmContentEncoding --log-net-log=…
   http://127.0.0.1:8078/<doc>` — render the page and exit cleanly after the
   web-test pass; the browser decodes the cbm document in its network stack;
5. `netlog_verify.py` follows the document's URLRequest source and requires
   `Accept-Encoding: … cbm`, `Content-Encoding: cbm`, `Vary: Accept-Encoding`,
   and no `FAILED` event. It parses the completed netlog structurally, rather
   than scanning Chromium's constants table for error strings. The script
   also records the identity and wire `.cbr` byte counts.

The advertisement works on plain-http localhost with no TLS: the pinned tag's
guard is `SchemeIsCryptographic() || IsLocalhost(url)` (resolved at P0). The
codec path itself is already proven at the unit level — this demo is the
canon-stage-4 optics on top of the passing `CbmSourceStreamTest`.

## Hard gate

This is a demo fork. **No upstream CL, no chromium.org interaction, no public
release of the fork or its binaries — operator sign-off required for each**
(CUBR-0079/0080 hard gates).
