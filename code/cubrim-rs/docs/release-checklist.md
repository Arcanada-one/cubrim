# Cubrim CLI — Release Checklist

A release ships a downloadable, ad-hoc-signed macOS universal binary plus its
SHA-256. The **codec is frozen** at the world-benchmark champion — a release
must never silently change the compressed byte stream.

## 0. Provenance gate (must pass before anything else)

- [ ] `PROVENANCE.md` names the current champion commit and DB meta id.
- [ ] No codec file diverges from the champion commit:
      ```sh
      git diff --name-only <champion-sha> -- \
        code/cubrim-rs/src/codec.rs code/cubrim-rs/src/cm2.rs \
        code/cubrim-rs/src/config.rs code/cubrim-rs/src/header.rs \
        code/cubrim-rs/src/huffman.rs code/cubrim-rs/src/cube.rs \
        code/cubrim-rs/src/phi.rs code/cubrim-rs/src/distance_map.rs \
        code/cubrim-rs/src/rle.rs code/cubrim-rs/src/bitpack.rs
      ```
      Output must be empty.

## 1. Linux verification (build host)

- [ ] `cargo build --release` — clean.
- [ ] `cargo test --release --test differential` — codec byte-invariant, all pass.
- [ ] `cargo test --release --test cli_compress_smoke --test cli_archiver` — CLI, all pass.
- [ ] `bash -n scripts/*.sh` — scripts parse.
- [ ] `bash scripts/smoke-cli.sh target/release/cubrim` prints `CLI_SMOKE_OK`.
- [ ] Corpus-dependent bench tests (`cubr0027/0028/0031_bench`) need the research
      corpus; they are expected to fail as "0 files present" when the corpus is
      not staged locally — this is environmental, not a regression. Run them only
      with `CUBRIM_CORPUS_DIR` pointing at a staged corpus.

## 2. Version & changelog

- [ ] `Cargo.toml` `version` bumped for the release (the wire-format version byte
      is independent, so this never changes compressed output).
- [ ] `CHANGELOG.md` `[Unreleased]` section moved under the new version + date.
- [ ] `cubrim --version` prints the intended version.

## 3. macOS universal build (Mac monitor — see `MACOS_BUILD.md`)

- [ ] `rustup target add aarch64-apple-darwin x86_64-apple-darwin`.
- [ ] `bash scripts/build-macos-universal.sh` (one command: builds both arches →
      `lipo -create` → ad-hoc `codesign -s -` → SHA-256).
- [ ] `lipo -archs dist/macos/cubrim-macos-universal` shows `x86_64 arm64`.
- [ ] `codesign -dv …` shows `Signature=adhoc`.
- [ ] `bash scripts/smoke-cli.sh dist/macos/cubrim-macos-universal` → `CLI_SMOKE_OK`.
- [ ] Record `dist/macos/cubrim-macos-universal.sha256`.

## 4. Publish (HARD GATE — operator only)

> Public package release (putting the Mac binary where users download it) is an
> operator-gated action. Branch C prepares everything; it never publishes.

- [ ] Binary artifact placed at the agreed host (NOT in the site git repo).
- [ ] Download page (`/download` or `/algorithm` section) updated with the real
      SHA-256, Gatekeeper-bypass instructions (`xattr -d com.apple.quarantine`
      or right-click → Open), and example commands. Site deploy is push→CI only.
- [ ] Operator confirms the download link works and the binary runs on a real Mac
      (compress + decompress + `cmp` of a test file).

## 5. Post-release

- [ ] Tag the release commit; attach SHA-256 to the release notes.
- [ ] Update `[BUILD-C]` status with the shipped SHA and artifact location.

## Future enhancements (NOT release blockers — do not implement without codec-branch sign-off)

- **`--fast` / automatic large-input mode.** Compress time grows super-linearly
  (see the performance profile); files beyond a few MB are impractical
  interactively. A future option could auto-fall-back to a fast codec above an
  input-size threshold. This is a **codec change** (branch A/B domain) and MUST
  be kept strictly separate from the benchmark path — the world benchmark keeps
  the full context-mixing codec, or the #1 ratio ranking breaks. Ship the honest
  speed profile in the docs now; treat the guard as an optional later feature.
- **Small-input ratio.** Inputs below ~64 KB skip the strong entropy path and can
  lose to gzip. Extending competitive-min to small inputs is a zero-regression
  codec change (all 24 benchmark files are >64 KB, so numbers are unaffected) —
  also branch A/B domain.
