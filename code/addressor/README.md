# Cubrim-2 Addressor (`cubrim-addr`)

Fleet-internal CAS/dedup addresser + router over Cubrim-1. Not a public release.

## AAL manifest

```yaml
current_aal: L1
target_aal: L2
```

L1: human-driven CLI tool — every phase decision is operator-visible and overridable.
L2 gate: auto phase selection (dup-fraction threshold + size-based residual backend)
enabled by default only after regression-proof and threshold acceptance criteria
are green on a real fleet corpus >= 1 GiB. Until then auto-selection sits behind `--auto`.

## Architecture (measured basis)

Two cores per the research phase-verdict (GO:15 / NO-GO:9):
- Core A — identity/CDC router: whole-file dedup, CDC chunks (8 KiB target),
  curated matrix (r>=2), per-project sections, ordinal refs, real Cubrim-1 residual
  backend on large inputs, step threshold DUP_THRESHOLD on per-file dup-fraction,
  competitive selection (never worse than pure Cubrim-1 per file).
- Core B — version-chain delta: zstd patch-from (ref_prefix + LDM), baseline
  comparison ONLY against zstd --ultra -22 (+trained dict) or Cubrim-1.

Standalone crate: no shared workspace with cubrim-rs (anti-absorption), path-dependency only.
