#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS universal build requires Darwin with lipo and codesign; skipping on $(uname -s)."
  exit 0
fi

mkdir -p dist/macos
rustup target add aarch64-apple-darwin x86_64-apple-darwin
cargo build --release --target aarch64-apple-darwin
cargo build --release --target x86_64-apple-darwin
lipo -create \
  target/aarch64-apple-darwin/release/cubrim \
  target/x86_64-apple-darwin/release/cubrim \
  -output dist/macos/cubrim-macos-universal
codesign --force --sign - dist/macos/cubrim-macos-universal
shasum -a 256 dist/macos/cubrim-macos-universal > dist/macos/cubrim-macos-universal.sha256
lipo -archs dist/macos/cubrim-macos-universal
cat dist/macos/cubrim-macos-universal.sha256
