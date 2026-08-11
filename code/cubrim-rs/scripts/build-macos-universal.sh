#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${ROOT}/dist/macos"
VERSION="$(grep -m1 '^version = ' "${ROOT}/Cargo.toml" | sed -E 's/version = "([^"]+)"/\1/')"
BIN_NAME="cubrim"
ARM_TARGET="aarch64-apple-darwin"
X86_TARGET="x86_64-apple-darwin"
UNIVERSAL="${DIST}/${BIN_NAME}-macos-universal"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  die "macOS build must run on a Mac. This host reports uname -s=$(uname -s)."
fi

need_cmd cargo
need_cmd rustup
need_cmd lipo
need_cmd codesign
need_cmd shasum

if ! rustup target list --installed | grep -qx "${ARM_TARGET}"; then
  die "missing Rust target ${ARM_TARGET}; run: rustup target add ${ARM_TARGET}"
fi

if ! rustup target list --installed | grep -qx "${X86_TARGET}"; then
  die "missing Rust target ${X86_TARGET}; run: rustup target add ${X86_TARGET}"
fi

mkdir -p "${DIST}"

printf 'Building Cubrim %s for %s...\n' "${VERSION}" "${ARM_TARGET}"
cargo build --release --target "${ARM_TARGET}" --manifest-path "${ROOT}/Cargo.toml"

printf 'Building Cubrim %s for %s...\n' "${VERSION}" "${X86_TARGET}"
cargo build --release --target "${X86_TARGET}" --manifest-path "${ROOT}/Cargo.toml"

ARM_BIN="${ROOT}/target/${ARM_TARGET}/release/${BIN_NAME}"
X86_BIN="${ROOT}/target/${X86_TARGET}/release/${BIN_NAME}"

[[ -x "${ARM_BIN}" ]] || die "missing arm64 binary: ${ARM_BIN}"
[[ -x "${X86_BIN}" ]] || die "missing x86_64 binary: ${X86_BIN}"

rm -f "${UNIVERSAL}" "${UNIVERSAL}.sha256"
lipo -create -output "${UNIVERSAL}" "${ARM_BIN}" "${X86_BIN}"
chmod 0755 "${UNIVERSAL}"
codesign -s - --force "${UNIVERSAL}"
shasum -a 256 "${UNIVERSAL}" > "${UNIVERSAL}.sha256"

printf '\nBuilt universal macOS binary:\n'
printf '  %s\n' "${UNIVERSAL}"
printf '  %s.sha256\n' "${UNIVERSAL}"
printf '\nArchitectures:\n'
lipo -archs "${UNIVERSAL}"
printf '\nCode signature:\n'
codesign -dv "${UNIVERSAL}" 2>&1 | sed 's/^/  /'
printf '\nSHA256:\n'
cat "${UNIVERSAL}.sha256"
