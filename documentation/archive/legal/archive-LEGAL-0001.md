# Archive LEGAL-0001: Cubrim licensing model + non-commercial/commercial texts

Date: 2026-07-09
Branch: `legal/cubrim-licensing-model`
Worktree: `/home/dev/cubr-legal-work/cubrim-code`

## Summary

Selected a dual-path Cubrim licensing model:

- Free non-commercial use under PolyForm Noncommercial License 1.0.0.
- Paid commercial use under a separate Arcanada commercial EULA.
- Standard commercial target: USD 50/year per named user seat or per installed computer/device.

This is an engineering/legal-policy draft, not legal advice. Arcanada should
obtain professional legal review before relying on it for commercial sales or
enforcement.

## Files Changed

- `code/cubrim-rs/Cargo.toml`: replaced `license = "MIT"` with `license-file = "LICENSE"`.
- `code/cubrim-rs/LICENSE`: non-commercial license notice with EN/RU text and PolyForm canonical URL.
- `code/cubrim-rs/LICENSE-COMMERCIAL.md`: commercial EULA draft with EN/RU text.
- `code/cubrim-rs/PROVENANCE.md`: package README license notice.
- `code/README.md`: repository usage license notice.
- `LICENSE`: repository-level pointer.
- `documentation/legal/license-recommendation.md`: model comparison and recommendation.
- `documentation/legal/license-audit.md`: dependency license audit.
- `documentation/legal/cubrim-license-policy-v1.0.md`: Legal Arcana-ready policy summary.
- `datarim/*`: task, PRD, plan, and index artifacts.

## Recommendation

PolyForm Noncommercial 1.0.0 is the recommended non-commercial path because it
directly maps to the operator's "free non-commercial, paid commercial" target.
BSL 1.1 was not selected because its standard framing is non-production use plus
a change-date mechanism, which is less direct for Cubrim's intended model.
Custom language was not selected as the primary path because it is less
recognizable and requires more attorney review.

## Dependency License Audit

Commands:

```bash
cargo metadata --manifest-path code/cubrim-rs/Cargo.toml --format-version 1 --no-deps
cargo tree --manifest-path code/cubrim-rs/Cargo.toml
```

Result: the current `cubrim` crate has no Rust dependencies. No dependency
copyleft conflict was found in the audited Cargo graph.

## Verification

Fresh verification after implementation:

```text
cargo metadata --manifest-path code/cubrim-rs/Cargo.toml --format-version 1 --no-deps
  exit 0; metadata reports license=null, license_file="LICENSE", dependencies=[]

cargo tree --manifest-path code/cubrim-rs/Cargo.toml
  exit 0; output only cubrim v0.1.0-cubr0043

cargo package --manifest-path code/cubrim-rs/Cargo.toml --allow-dirty
  exit 0; packaged 48 files; verification compile succeeded

rg -n 'license = "MIT"|MIT License' shipped artifacts
  exit 1; no stale MIT metadata found in shipped artifacts

git diff --check
  exit 0
```

Baseline note: `cargo test --manifest-path code/cubrim-rs/Cargo.toml` was run
before license edits and failed with 231 passed / 6 failed. All six failures
reported missing local corpus fixture files under
`documentation/ephemeral/research/corpus/`, matching the known worktree-family
fixture gap and unrelated to licensing edits.

## Coordination Text

Use this modal copy for CUBR-DOWNLOAD:

English:

```text
Cubrim is free for non-commercial use under PolyForm Noncommercial 1.0.0.
Commercial use requires a paid Arcanada commercial license.
Standard commercial target: USD 50/year per named user seat or per installed device.
Until Legal Arcana launches, canonical license text is published through cubrim.com.
```

Russian:

```text
Cubrim бесплатен для некоммерческого использования по PolyForm Noncommercial 1.0.0.
Коммерческое использование требует платной коммерческой лицензии Arcanada.
Стандартный ориентир: 50 долларов США в год за именованное место или установленное устройство.
До запуска Legal Arcana канонический текст лицензии публикуется через cubrim.com.
```

Temporary canonical target: `https://cubrim.com/legal/cubrim-license`

Future canonical target: `https://legal.arcanada.ai/policies/cubrim/license/v1.0`

## Open Legal Review Items

- Confirm formal licensor entity name.
- Choose governing law and venue.
- Complete payment, tax, export-control, privacy, and support terms.
- Decide public messaging for earlier MIT-labeled copies.
