# FH2-07 typed-field cheap-probe plan

**Scope:** research-only Python probe on `sao`; no Rust codec, core, DB, site, or
Opus-axis changes.  The paired comparison uses one deterministic arithmetic
coder and changes only the causal model supplying its bit probability.

**2026-07-22 priority correction:** the live authoritative aggregate confirms
binary is already rank #1.  The operator therefore capped this work at the
1 MiB margin screen even if it passes; steps 5-6 below are superseded and no
full-`sao` or integration work is authorised in this pass.

## Scientific contract

- Input must be exactly 7,251,944 bytes with SHA-256
  `c2d0ea2cc59d4c21b7fe43a71499342a00cbe530a1d5548770e91ecd6214adcc`.
- Detect record width with the bounded FH-10 lag-cost rule; expected `W=28`.
- Infer a non-overlapping `u8/u16le/u32le/f32le` schema from a bounded training
  prefix.  Transmit and charge the schema.  Bytes stay in their original order.
- Baseline context is FH-10-shaped:
  `(offset % W, previous-same-offset byte or first-record sentinel,
  current partial-byte prefix)`.
- Typed context may use only schema, values from completed earlier records,
  the previous whole-value delta, and lower bytes already decoded in the
  current little-endian field.  It must never inspect the current field value
  or a later source byte while predicting a bit.
- Both variants use identical integer adaptive counts, rescaling, arithmetic
  coder, input length framing, and width charge.  Typed alone pays its schema.
- Full-file `GO` requires typed charged size to beat paired baseline by at least
  1.5%.  Anything less is `NO-GO`; no tuning after seeing the full-file verdict.

## Execution

1. Add `documentation/ephemeral/research/probe_fh2_07_typed_fields.py` with:
   FH-10 width detection, deterministic field-schema detector, integer binary
   arithmetic encoder/decoder, baseline model, typed delta/carry model, exact
   framing charge, JSON result output, and a built-in self-test.
2. Add focused `unittest` coverage beside the probe.  Cover arithmetic RT,
   baseline and typed RT, causality under an encoder-side future-byte poison,
   width/schema detection on synthetic 28-byte records, and charge accounting.
3. Run tests and lint-level syntax verification:
   `python3 -m unittest documentation.ephemeral.research.test_probe_fh2_07`
   and `python3 -m py_compile ...`.
4. Fetch `sao` into an untracked temporary path, verify size/hash, and run the
   first 1 MiB screen.  Stop immediately if typed is not smaller than baseline;
   record an honest screen `NO-GO`.
5. Only if the screen is smaller, run the unchanged probe on full `sao`.  Repeat
   once if it reaches the 1.5% boundary closely.  Record wall time, detected
   schema, context counts, payload/header/charged sizes, ratios, and percent
   delta.  Verify decoder output byte-for-byte (`cmp=0`) for both probe streams.
6. If full-file improvement is at least 1.5%, write an FH-10 integration sketch
   without editing the codec.  Otherwise document why the typed field mechanism
   is closed at cheap-probe resolution.
7. Append the exact verdict under `[PPMD→FH2-07]` in
   `/home/dev/cubr-cm-status.md`, notify `CUBR-CM:1.1`, remove temporary corpus
   and archives, verify protected worktrees/branches are untouched, and commit
   only the isolated research artifacts.

## Stop conditions

- Wrong corpus identity, width other than 28, coder RT mismatch, causality-test
  failure, or inconsistent repeat: invalid probe, no ratio verdict.
- Screen typed size greater than or equal to baseline: screen `NO-GO`, no full
  run.
- Full improvement below 1.5%: final `NO-GO`, no Rust integration.
