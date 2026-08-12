# CUBR-0087 API coverage consilium

Date: 2026-08-01
Question: Is the apparent DB-to-feed gap a data defect, a mapper defect, or both?

## Outcome — IMPLEMENTED (verified 2026-08-12 against `cubrim-api` `origin/main` @ `c2b658d`)

All seven decision points below are live in the service. Evidence, by decision number:

1. No DB write, no prose rewrite — `src/queries.ts` still selects the whole table; the
   vocabulary was widened instead.
2. Single classifier with case-insensitive leading-token parse — `src/build.ts`
   `normalizeVerdict()` (regex + `.toUpperCase()`) feeding `classifyVerdict()`. This also
   resolves the casing drop the handover flagged: `GO-to-PLAN` / `GO-self-only` now match.
3. Observed result tokens in the feed vocabulary — `RESOLVED_VERDICTS` now carries
   `IMPLEMENTED`, `KILLED`, `BYTE-IDENTICAL`, `MEASURED-OPPORTUNITY`, `UNMEASURED`; each maps
   to UI status `CLOSED` via `VERDICT_STATUS` without altering the emitted verdict code.
4. Additive raw verdict — `verdict_detail` on both feed and roadmap items
   (`src/types.ts`, `src/build.ts`).
5. `_reconciliation` metadata — source/represented row counts, `unrepresented_ids`,
   `unknown_verdicts`; surfaced through `src/server.ts`.
6. Validation fails loudly — `test/validate.ts` fails the run when `unrepresented_ids` or
   `unknown_verdicts` is non-empty; fixture coverage in `test/build.test.ts`.
7. Override precedence retained — `const toFeed = ov?.to_feed ?? classifyVerdict(...).toFeed`.

The durable reconciliation check the handover asked for therefore exists: it compares source
row IDs against feed ∪ roadmap membership and names the gaps, so a content gap can no longer
hide behind a green route sweep.

## Evidence

- `arcanada_cubrim.hypotheses` is the source of truth and currently contains 129 rows.
- `src/queries.ts` selects the complete `hypotheses` table; it does not filter rows.
- `src/build.ts` groups rows into site cards, normalizes only the leading verdict token, and sends a card to the feed only when that token is in `RESOLVED_VERDICTS` or an explicit override says `to_feed=true`.
- The live API currently reports 76 feed cards and 36 roadmap cards. `NEW-22`, `NEW-28`, and `NEW-29` are present in the roadmap, not absent from the API.
- Live result verdicts include `KILLED`, `BYTE-IDENTICAL`, `MEASURED`, `IMPLEMENTED`, `UNMEASURED`, and `MEASURED-OPPORTUNITY` as leading tokens. The first four result classes are not all members of the current resolved set.
- The raw verdict prose contains the evidence and must remain available; changing DB prose to short keywords would destroy source meaning.

## Panel

### Architect

The source read is complete. This is primarily a projection-contract defect: the mapper recognizes an older closed vocabulary while the DB has acquired evidence-bearing result codes. Do not mutate the DB to satisfy a stale projection. Add a typed classification boundary and an explicit reconciliation result.

### Developer

Keep the existing leading-token parser, make the recognized result vocabulary explicit, and add tests for every observed result token plus a future unknown token. Preserve the full raw verdict as an additive output field. Feed routing must be deterministic and override precedence must remain unchanged.

### Security

The new fields are additive DB-derived content, not executable input. Do not expose credentials, paths, or host diagnostics in reconciliation output. Do not make the API silently hide source rows; a named discrepancy is safer than an apparently healthy partial feed.

### SRE

Coverage must be checked mechanically at build/validation time. A card count cannot equal a row count because title grouping is intentional, so the check must compare source row IDs against the union of feed and roadmap member IDs and must name any unrepresented IDs and unknown leading codes.

### Strategist

The smallest durable fix is mapper plus validation, not a schema rewrite. New result rows should receive feed prominence because they are evidence-bearing outcomes, including negative and unmeasured outcomes. Planning rows remain roadmap rows. Unknown tokens must remain visible but fail the validation gate until deliberately classified.

## Decision

1. No DB write and no prose rewrite.
2. Introduce a single verdict classifier with the existing case-insensitive leading-token parse.
3. Add the observed result tokens to the explicit feed vocabulary and map their UI status without changing the emitted verdict code.
4. Preserve the full source verdict in an additive `verdict_detail` field on feed and roadmap items.
5. Add `_reconciliation` metadata containing source-row count, represented-row count, feed/roadmap card counts, collapsed member count, unrepresented IDs, and unknown leading codes. The check must operate on source row IDs, not card counts.
6. Make offline/live validation fail when any source row is unrepresented or any leading token is unknown. Add fixture tests for positive result rows, negative/unmeasured rows, title-collapsed members, and unknown tokens.
7. Keep explicit `hypothesis_overrides.to_feed` precedence. Overrides remain the exception mechanism for presentation-specific decisions, not the replacement for a vocabulary.

## Rejected alternatives

- Rewriting DB verdict prose into keywords: rejected; it loses evidence and violates the DB-as-source contract.
- Filtering or deleting rows in `queries.ts`: rejected; it would hide source rows and make reconciliation impossible.
- Treating every unknown token as feed without a diagnostic: rejected; it prevents future drift from failing loudly.
- Comparing only 129 source rows with 112 card objects: rejected; title grouping intentionally collapses multiple rows into one card.

## Acceptance boundary

The API change is locally complete only when the fixture suite proves all observed result tokens route as intended, unknown tokens are reported, every source row is represented, and the existing override/card ordering contract remains green. Merge, deployment, and public route closure still require the repository CI and production readback gates.
