#!/usr/bin/env bash
# build-macos-perarch.sh — Mac-monitor build path that MATCHES the shipped
# release convention (cubrim.com /download + Homebrew tap): two per-arch
# tarballs named cubrim-v<version>-macos-apple-silicon.tar.gz and
# cubrim-v<version>-macos-intel.tar.gz, each with .sha256 + .size sidecars.
#
# WHY per-arch (not the universal fat binary): the live download page
# (releases.php -> platforms macos_apple_silicon / macos_intel) and the
# Homebrew formula (on_arm/on_intel) both consume PER-ARCH assets with the
# arch labels "apple-silicon" / "intel". The older build-macos-universal.sh
# emits a single off-convention "cubrim-macos-universal" raw binary that the
# site/tap do NOT reference — prefer THIS script for release builds.
#
# This script stops at the signed+packaged tarballs. NOTARIZATION and the
# .pkg installer (which the download page advertises as "notarized") require
# Apple Developer credentials on the Mac host and are the Mac-monitor's step
# — see MACOS_BUILD_HANDOFF.md. Publishing to GitHub Releases and updating the
# site /download page are OPERATOR-HARD-GATED (public release).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${ROOT}/Cargo.toml" | head -n1)"
BIN_NAME="cubrim"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

[[ "$(uname -s)" == "Darwin" ]] || die "macOS build must run on a Mac (uname -s=$(uname -s))."
need_cmd cargo; need_cmd rustup; need_cmd codesign; need_cmd shasum; need_cmd tar

# target-triple  ->  shipped arch label (site/tap convention)
BUILDS=(
  "aarch64-apple-darwin:apple-silicon"
  "x86_64-apple-darwin:intel"
)

for pair in "${BUILDS[@]}"; do
  triple="${pair%%:*}"
  rustup target list --installed | grep -qx "${triple}" \
    || die "missing Rust target ${triple}; run: rustup target add ${triple}"
done

DIST_DIR="${ROOT}/dist/release"
printf 'Building Cubrim %s per-arch macOS assets...\n\n' "${VERSION}"

for pair in "${BUILDS[@]}"; do
  triple="${pair%%:*}"
  arch_label="${pair##*:}"
  printf '== %s (macos %s) ==\n' "${triple}" "${arch_label}"
  cargo build --release --target "${triple}" --manifest-path "${ROOT}/Cargo.toml"
  bin="${ROOT}/target/${triple}/release/${BIN_NAME}"
  [[ -x "${bin}" ]] || die "missing built binary: ${bin}"
  # Ad-hoc sign the binary before packaging (matches build-macos-universal.sh;
  # a real Developer ID signature + notarization is layered on by the Mac-monitor).
  codesign -s - --force "${bin}"
  # Reuse the shipped generic packager -> cubrim-v<version>-macos-<arch_label>.tar.gz
  bash "${ROOT}/scripts/package-release.sh" "${triple}" "macos" "${arch_label}" "tar.gz"
done

printf '\n== macOS per-arch assets (for the download-page / Homebrew update) ==\n'
for pair in "${BUILDS[@]}"; do
  arch_label="${pair##*:}"
  asset="${DIST_DIR}/cubrim-v${VERSION}-macos-${arch_label}.tar.gz"
  [[ -f "${asset}" ]] || die "expected asset missing: ${asset}"
  printf '  %s\n    sha256: %s\n    size:   %s bytes\n' \
    "${asset}" "$(cat "${asset}.sha256")" "$(cat "${asset}.size")"
done

cat <<'MACNEXT'

NEXT (Mac-monitor, then OPERATOR hard-gate) — see MACOS_BUILD_HANDOFF.md:
  1. Developer ID sign + notarize + staple each per-arch binary; build the
     notarized .pkg installer for each arch.
  2. Verify: lipo -archs (per-arch, single-arch), codesign -dv --verbose=4,
     spctl -a -vvv (Gatekeeper), and scripts/smoke-cli.sh on each binary.
  3. OPERATOR GATE: publish the tarballs + .pkg + checksums to the GitHub
     release, then update releases.php (version, url, sha256, size, pkg_*).
MACNEXT
