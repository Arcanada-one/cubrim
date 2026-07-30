# Cubrim macOS Universal Binary Build

## Prerequisites

The build machine must be a **macOS** host (Intel or Apple Silicon) running macOS 11+.

- **Xcode Command Line Tools**  
  Install via `xcode-select --install` or as part of Xcode.

- **Rust toolchain** (latest stable)  
  Install via `rustup` if not already present.

- **rustup targets** for both architectures:  

  ```bash
  rustup target add aarch64-apple-darwin x86_64-apple-darwin
  ```

- **Build tools** - `cargo`, `rustup`, `lipo`, `codesign`, `shasum` are required.  
  All are present in a standard macOS developer environment after installing Xcode CLT and Rust.

## One-Command Build

From the repository root (`cubrim-rs/`), run:

```bash
bash scripts/build-macos-universal.sh
```

This single command will:

1. Detect the project version from `Cargo.toml`.
2. Build a release binary for `aarch64-apple-darwin` and `x86_64-apple-darwin`.
3. Combine them into a universal binary via `lipo -create`.
4. Ad-hoc codesign the resulting binary (no Apple Developer account needed for local testing).
5. Produce a SHA-256 checksum file.

## Expected Artifacts

After a successful build, the following files are created:

- `dist/macos/cubrim-macos-universal` - the universal (fat) binary.
- `dist/macos/cubrim-macos-universal.sha256` - its SHA-256 hash.

The version directory under `dist` is named `macos` (i.e., `dist/macos/`). No version subfolder is used for local builds; that is handled later in the release pipeline.

## Verification

### Code Signature

Ad-hoc signature details can be inspected with:

```bash
codesign -dv dist/macos/cubrim-macos-universal
```

You should see `Signature=adhoc` and no errors.

### Architecture Check

Confirm both architectures are present:

```bash
lipo -archs dist/macos/cubrim-macos-universal
```

Expected output includes both `x86_64` and `arm64`.

### CLI Smoke Test

The binary must run correctly on a small input file:

```bash
printf 'CUBR macOS smoke test\n%.0s' {1..512} > /tmp/cubrim-smoke.txt
./dist/macos/cubrim-macos-universal compress /tmp/cubrim-smoke.txt /tmp/cubrim-smoke.cubr
./dist/macos/cubrim-macos-universal decompress /tmp/cubrim-smoke.cubr /tmp/cubrim-smoke.out
cmp /tmp/cubrim-smoke.txt /tmp/cubrim-smoke.out
./dist/macos/cubrim-macos-universal --version
```

The compress command should print `ratio=...` and `time_ms=...`; decompress should
print `time_ms=...`.

## Deployment Notes

- The universal binary **must not be committed to the site repository** (e.g., `cubrim-site`).  
- Artifact placement and download URLs are defined later in the release pipeline (P4.4 / P4.5).  
- This handoff is for local testing and CI verification only.
