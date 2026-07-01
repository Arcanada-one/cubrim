# Cubrim — Hypothesis Stage Reports

Permanent, git-tracked record of every hypothesis round in the compression race.
**One file per hypothesis**, holding the hypothesis AND its measured result.

This directory is canonical and permanent — distinct from `documentation/ephemeral/research/`
(transient probes/prototypes). The full stage report is promoted here.

## Naming

`H-NN-<short-slug>.md` (e.g. `H-29-class-c-columnar.md`).

## Each report carries

- **Hypothesis** — what is being tested.
- **Why it might help** — the mechanism / lever.
- **Implementation / probe** — what was built or measured.
- **Measured** — real bench numbers (cubrim vs gzip-9 vs zstd-19); never estimated.
- **Verdict** — GO / NO-GO / MARGINAL.
- **Code SHA** — the commit the measurement ran on.

## Related

- `../hypothesis-log.md` — running one-line-per-round journal; the `/evolution` publish source.
- `cubrim.com/data/evolution.json` — public race cards (numbers grep-confirmed against the log).
- Race goal: beat **zstd-19** (gzip-9 already passed at H-24).
