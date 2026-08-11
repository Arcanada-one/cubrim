# macOS build & release handoff (Mac-monitor)

Prep by branch C for the Mac-monitor, who owns the actual macOS build (no Mac
host here). Publishing anything public (GitHub Release, the site `/download`
page) is **operator-hard-gated** — this doc stops at build + local verification.

## Key finding: macOS is already SHIPPED — this is reconcile, not greenfield
- The live site **cubrim.com** already advertises macOS at **v0.2.2**
  (2026-07-12): the `/download` page (`pages/download.php`, data in
  `releases.php`) lists `macos_apple_silicon` + `macos_intel` with **notarized
  `.pkg` installers** primary and `.tar.gz` as the alternate.
- A **Homebrew tap** (`github.com/Arcanada-one/homebrew-cubrim`,
  `Formula/cubrim.rb`) pins per-arch tarballs at the same v0.2.2.
- Canonical asset naming (site + tap, GitHub release repo
  `github.com/Arcanada-one/cubrim`):
  ```
  cubrim-v<version>-macos-apple-silicon.tar.gz   (+ .pkg notarized installer)
  cubrim-v<version>-macos-intel.tar.gz           (+ .pkg notarized installer)
  ```
  arch labels are **`apple-silicon` / `intel`** — NOT `arm64`/`x86_64`, NOT `universal`.

## Convention reconciliation (what changed here)
This industrial branch previously carried only `scripts/build-macos-universal.sh`
— it emits ONE ad-hoc-signed `cubrim-macos-universal` raw binary that the site
and tap do **not** reference (off-convention name, no notarization). Added
`scripts/build-macos-perarch.sh` which builds the **two per-arch** tarballs with
the exact shipped naming via the existing generic `package-release.sh`. Use the
per-arch script for releases; treat the universal script as legacy.

## Build steps (Mac host)
```bash
cd code/cubrim-rs
rustup target add aarch64-apple-darwin x86_64-apple-darwin   # once
bash scripts/build-macos-perarch.sh
# → dist/release/cubrim-v<version>-macos-apple-silicon.tar.gz (+ .sha256 + .size)
# → dist/release/cubrim-v<version>-macos-intel.tar.gz         (+ .sha256 + .size)
# prints sha256 + size for each (for the download-page / Homebrew update)
```
Follow `docs/release-checklist.md`: §0 provenance gate (codec files unchanged vs
champion `6eaefad`) MUST pass first; run `scripts/smoke-cli.sh <binary>` on each
built arch.

## Mac-monitor-only steps (need Apple Developer credentials)
1. **Developer ID sign + notarize + staple** each per-arch binary
   (`codesign` with a real identity, `notarytool submit --wait`, `stapler`).
   The per-arch script only ad-hoc-signs (`codesign -s -`), enough to run
   locally but NOT what the download page advertises.
2. **Build the notarized `.pkg` installer** per arch (`pkgbuild`/`productbuild`
   + notarize). The site treats the `.pkg` as the PRIMARY macOS download
   (`pkg_url`/`pkg_sha256`/`pkg_size` in `releases.php`).
3. Verify: `lipo -archs` (single-arch each), `codesign -dv --verbose=4`,
   `spctl -a -vvv` (Gatekeeper accepts), round-trip via `smoke-cli.sh`.

## OPERATOR HARD-GATE (public release — do NOT do autonomously)
- Publish tarballs + `.pkg` + `checksums.txt` to the GitHub release.
- Update the site `releases.php` platform block: `filename`/`url`/`sha256`/
  `size` + `pkg_filename`/`pkg_url`/`pkg_sha256`/`pkg_size`. The `/download`
  page and translations already exist — **no new page needed**, only real
  measured sha256/size values.
- Update the Homebrew formula sha256s.

## Open decisions for the orchestrator/operator
- **Version skew:** this crate is `0.1.0-cubr0043`; the shipped site/tap are
  `0.2.2`. The release version for the industrial macOS build is an operator
  call — the build scripts read it from `Cargo.toml`, so set it there first.
- **CI parity (optional):** `.github/workflows/release.yml` builds Linux +
  Windows only; macOS is this manual Mac-host path. Adding a `macos-latest`
  matrix job would give CI parity but needs notarization secrets in CI.
