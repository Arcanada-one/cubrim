# LEGAL-0001 Dependency License Audit

Date: 2026-07-09
Project: Cubrim
Scope: `code/cubrim-rs`

## Commands

```bash
cargo metadata --manifest-path code/cubrim-rs/Cargo.toml --format-version 1 --no-deps
cargo tree --manifest-path code/cubrim-rs/Cargo.toml
```

## Result

`cargo metadata` reported an empty dependency list for package `cubrim`
version `0.1.0-cubr0043`.

`cargo tree` output:

```text
cubrim v0.1.0-cubr0043 (/home/dev/cubr-legal-work/cubrim-code/code/cubrim-rs)
```

## Compatibility Finding

No third-party Rust dependencies were present in the audited crate graph, so no
dependency copyleft conflict was found. This finding is limited to the current
Cargo package graph. If future dependencies are added, re-run the audit before
shipping the license package or commercial release.
