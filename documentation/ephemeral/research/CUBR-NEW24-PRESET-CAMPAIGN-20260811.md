# Preregistration: NEW-24 tier preset campaign (F12 adoption decision)

**State:** PREREGISTERED DESIGN — no measurement result is recorded here.
Committed to `main` before the campaign runs. Bases: tier-ladder results
(`CUBR-NEW24-TIERS-20260811-results.md`, PR #101, main 94c9555) and the
Phase C operating point (metas 36/37/38).

## Question this campaign answers

Should a shipping preset expose tier F12 (and M8S on database-class
inputs)? The tier ladder measured F12 at 2.24× decode for +1.7…+8.9%
density on five files; a preset decision needs the whole 24-file operating
corpus, both sides per file, under the same-host campaign convention.

## Design

- **Arms:** `full` (current `max` CM2, control) and `F12-forced`
  (`CUBR_CM2_TIER=f12 CUBR_CM2_TIER_FORCE=1`) on all 24 meta-36 corpus
  files; additionally `M8S-forced` on the database-class files (nci, osdb).
- **Per cell:** archive bytes + sha256; decode wall ×3 (median reported);
  decode peak RSS (`/usr/bin/time -v`); encode wall recorded for provenance
  only. Every archive round-trips (`cmp` + sha256 vs corpus original)
  before any number is read. The `full` arm's archives must be sha256-equal
  to the Phase C journal canonicals (G1-style identity, binary lineage
  check); a mismatch fails the cell.
- **Environment:** dev-ai, `/root/corpus-full`, current-main binary (sha
  recorded in the journal), `CUBRIM_ACCEPT_LICENSE=1 CUBR_THREADS=4
  RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4`, **unpinned quiet-host** matching
  the Phase C timing convention (comparable to metas 36–38; the 0–15 pin
  and its lanes untouched), `systemd-run --scope` memory caps 14G full /
  8G tiered, quiet gate load < 8.0, per-cell timeouts 3× the DB-derived
  expectation. Voids go to the campaign journal, never the DB.

## Falsifiable predictions

- **C-1 (scope of effect):** on files whose meta-36 winner is not CM2
  (image/binary class: mr, x-ray, sao, ptt5, kennedy.xls at minimum), the
  F12-forced archive is byte-identical to the full arm's (the tier only
  changes the CM2 candidate; the competitive rail's winner is unchanged),
  and decode wall is within noise (±10%).
- **C-2 (density):** on CM2-won files, F12 ratio worsening per class stays
  ≤ +5% text/code, ≤ +6% exe, ≤ +10% database — and cubrim's meta-36
  rank-1 survives on ≥80% of the files it currently leads. M8S on
  nci/osdb: worsening ≤ +8%.
- **C-3 (speed):** median F12 decode speedup on CM2-won files ≥ 1.5×;
  ≥ 2.0× on files ≥ 8 MB with `tbits ≥ 26`.
- **C-4 (memory, mechanism closure):** F12 decode peak RSS ≤ 60% of full
  on CM2-won files ≥ 16 MB (12+3 of 27 tables ≈ 56% — the working-set
  mechanism behind the above-map P-A speedups; this prediction closes it).

## Pre-committed adoption rule (the product decision, decided by rule not post-hoc)

- If C-2's lead-survival AND C-3's median-speedup conditions both hold:
  introduce a **new preset `fast`** = F12 (+M8S on database-classed inputs
  via the existing detector) in a follow-up implementation PR, leaving
  `max`/`balanced`/`web` semantics untouched (existing users' archives
  never change silently).
- If either fails: no preset change; the tier stays knob-only and the
  failing condition is recorded on the NEW-24 row as the reason.
- Either way, every per-file number (both sides of the trade) lands in the
  results record; whether new DB metas are minted for `fast` happens only
  after the preset exists in a release-lineage build, not from this
  campaign's runs.

## Budget and stop rules

≤ 16 h stand wall-clock, sequential cells, encode-once decode-thrice per
arm. A cell that cannot pass its gates is reported failed, never
substituted. If the stand cannot go quiet within a cell's window, the cell
voids to the journal. Canterbury files are measured and reported but
excluded from class-level claims (fixed-overhead-dominated, per protocol).
No corpus-wide averages; per-file figures only.
