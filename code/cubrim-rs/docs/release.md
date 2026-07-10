# Release Handoff

The Linux-side task prepares the source and scripts. The Mac monitor builds the
universal macOS binary.

## Linux Verification

```sh
cargo test --test cli_archiver
cargo test --bin cubrim
cargo build --release
./target/release/cubrim --version
bash -n scripts/build-macos-universal.sh
```

## Mac Monitor Build

```sh
bash scripts/build-macos-universal.sh
bash scripts/smoke-cli.sh dist/macos/cubrim-macos-universal
```

Required evidence:

- SHA256 from `dist/macos/cubrim-macos-universal.sha256`
- `lipo -archs dist/macos/cubrim-macos-universal` includes `arm64 x86_64`
- `codesign -dv dist/macos/cubrim-macos-universal` shows ad-hoc signature
- smoke script prints `CLI_SMOKE_OK`
