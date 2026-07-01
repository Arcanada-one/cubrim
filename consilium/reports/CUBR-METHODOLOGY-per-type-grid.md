# CUBR — Per-Type Grid Evaluation Methodology (consilium-ratified)

**Trigger.** Operator: «каждую гипотезу нужно проверять на каждом виде файлов из мирового бенчмарка, а не на одном. Где-то гипотеза ухудшила, где-то улучшила — возможно она GO, а записана в NO-GO. Пересобрать консилиум, переоценить каждую гипотезу, новые тоже считать правильно.»

**Consilium.** 3 free members (gpt-oss-120b / gemma-4-31b / nemotron-120b) + DeepSeek-v4 head. Winning proposal: gpt-oss-120b (only one with a real subsumption guard + dual threshold + named gaming traps). Head flagged all unverifiable corpus-size/leader claims as «requires empirical confirmation». This spec keeps only what is mechanically checkable against the actual version-locked World Benchmark corpora.

---

## The core fix

A single global GO/NO-GO is WRONG. A transform can hurt `text` while helping `image`/`exe`/`binary`. Every hypothesis is evaluated as a **(hypothesis × data-type) grid over all 6 types**: `text, code, binary, exe, image, database`. A hypothesis that is GO on even ONE type — and is **gated to engage only on that detected type** (zero harm to others) — is a SHIP candidate for that type.

## Per-cell measurement protocol (mandatory, every hypothesis × type cell)

Each cell runs FOUR measurements on the real, version-locked World Benchmark files of that type, all on champion `--value-scheme bwt-rans`, all round-trip byte-exact:

| Symbol | Measurement |
|---|---|
| **A** | Cubrim champion WITHOUT the hypothesis transform (the control / baseline rail) |
| **B** | Cubrim champion WITH the hypothesis transform |
| **L** | The strong universal leader on that type (xz / ppmd / brotli — whichever wins the type), strongest practical flags |
| **RT** | Round-trip of B must be byte-exact, else the cell is VOID (not NO-GO — VOID, re-implement) |

Per-cell metrics:
- **self-gain** = (A − B) / A  — how much the transform improves Cubrim's OWN champion on this type.
- **subsumption check** = self-gain must be > noise floor. If self-gain ≤ +1.5% absolute ratio improvement, the backend already extracts it → **subsumed → NO-GO(type)**. (The 1.5% floor separates a real structural gain from rANS/BWT noise; 0.5% is noise.)
- **competitive** = does B beat L on this type? (rank-up vs the strong leader, NOT vs a weak zstd-19 strawman.)

## Per-type verdict rule (dual gate — least gameable)

A hypothesis is **GO(type)** iff BOTH:
1. **self-gain ≥ +1.5%** (real non-subsumed gain over Cubrim's own champion), AND
2. it **moves Cubrim's rank up among the 8 archivers on that type**, OR closes ≥50% of the gap to the strong leader L.

Otherwise **NO-GO(type)**. A cell that improves self but stays last place is a weak GO at best — record as `GO(self-only)`, ship-gated, low priority.

Gaming traps explicitly closed: (a) never gate on beating zstd-19 (weak baseline); (b) single big file must not dominate a type — report per-file, aggregate by total bytes per type, and flag if one file >60% of the type's bytes; (c) absolute ratio improvement, not relative-to-a-cherry-picked-unit.

## Aggregation (final form of a hypothesis verdict)

Not one verdict — a **vector**: `H-XX: GO{image, binary} · NO-GO{text, code, exe, database}`. Shipping rule: if the transform is **type-gated** (engages only on detected type, provably no-op elsewhere — byte-identical output on non-target types), it SHIPS for its GO types regardless of NO-GO elsewhere. If it is NOT cleanly gatable (would touch all inputs), it ships only if it is net-positive aggregated by total bytes across all 6 types AND non-negative on each type.

## Config discipline (every cell, no exceptions)

- champion `--value-scheme bwt-rans` — never the weak default (past trap: false regressions).
- round-trip byte-exact or cell is VOID.
- real version-locked World Benchmark corpora; cite file list + sizes per type (no fabricated sizes).
- per-file numbers logged + provenance (corpus URL + SHA256). Ceilings tagged «estimate-from-lit» vs «measured».

## Re-evaluation ORDER (maximise false-NO-GO → GO flips first)

Single-corpus / mixed-corpus testing most likely BURIED a type-specific win for transforms whose mechanism is meaningful on ONE type only. Re-run order:

1. **H-37/H-45 BCJ for executables** — meaningless on text (drowned the exe gain), genuine on x86/x64, low subsumption risk. Highest flip probability. (Consilium head: spike this FIRST to validate the whole grid method.)
2. **H-39 2D spatial predictor for images** — MED/Paeth on the pixel grid; invisible to a 1-D byte pipeline; image type was a +38% gap.
3. **H-40 field-split / byte-plane for binary/numeric** — sao/kennedy.xls; per-column de-interleave.
4. **H-41 stronger text backend** — text-only; ppmd gap.
5. Then the remaining H-29..H-55 NO-GO/MARGINAL cells, then re-confirm the existing GO classes per-type.

**Standing rule for ALL new hypotheses:** compute the full 6-type grid from the start. No new global verdicts ever again.

---

_Ratified by free-model consilium 2026-06-26. Implementer: run H-45 BCJ/exe spike first; if it flips false-NO-GO→GO(exe), the grid method is validated and the full re-eval proceeds._
