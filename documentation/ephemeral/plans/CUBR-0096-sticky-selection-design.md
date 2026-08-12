# CUBR-0096 — sticky value-scheme selection: design sketch (2026-07-31, Fable session)

Status: **design sketch — the mechanism below is not yet on `main`.** Per PRESETS.md rule, NO
preset name exists until the corpus numbers do — the mechanism ships behind an internal
config field first.

> ## ⚠ THIS LEVER HAS ALREADY BEEN BUILT AND MEASURED — AND IT FAILED ITS GATE
>
> **Read `../research/CUBR-0096-inner-sticky-gate-result.md` before writing any code against
> this design.** The § Mechanism below was implemented in full on 2026-08-02 (under the
> then-current label `CUBR-0092`) and **KILLED by its pre-registered gate**: 1.33× on x-ray and
> 1.05× on ooffice against a 1.50× bar, with byte-exact round-trip and *identical* compressed
> bytes on both. The candidate source is on `rescue/INFRA-0394/codex/cubr-0092-inner-sticky` @
> `cfea5da8`; the measurement evidence is on `dev-ai` and in `hypotheses` row `NEW-29`.
>
> That result never reached `main`, which is why the status note below — correctly reading
> `origin/main` and finding no `vs_pin` / `vs_sticky` / `VsSticky` — concluded the mechanism was
> unbuilt. It was not unbuilt; it was unrecorded.
>
> **The single most important number for anyone continuing:** tuning `compete_blocks` /
> `recheck_every` cannot rescue this. The killed candidate already probed only ~6–8% of blocks,
> so a *perfect oracle* with no probing at all is bounded at **≈1.37× on x-ray and ≈1.06× on
> ooffice** — still under the gate. The gate result derives that bound from the measured cells.
> The corpus arm, by contrast, genuinely never ran, and neither did anything at enwik8 scale.

## Status check (2026-08-12, verified against `origin/main` @ `ad4650a`)

This document is the durable record of the design; the lever is now in active implementation
on a separate branch.

> **Superseded in part, same day:** the two bullets below stating the mechanism is "still
> unbuilt" describe `origin/main` accurately but not the world — see the box above.

- **Live lane:** branch `cubr-0096-sticky-vs` (pushed, no PR yet) carries `a44555f`
  "instrument(CUBR-0096): record the FINAL per-block value-stream winner" — method step 1,
  instrument-before-deciding. It records the winner of each block itself, because
  `prof::win()` fires on every new running minimum and so cannot answer whether the winner is
  CONSTANT across blocks, which is what this lever turns on. Profile-gated
  (`CUBRIM_PROFILE=1`), emitted bytes unchanged. That branch notes the port from CUBR-0087
  F18 had to be adapted for the candidates-array refactor, where a BWT-family candidate may
  decline (`None`) and is never scored — so the winner is an `Option` unwrapped after the loop.
- **Not yet on `main`:** no `vs_pin`, `vs_sticky`, or `VsSticky` in `code/cubrim-rs/src/` on
  `origin/main`; the sticky mechanism proper (§ Mechanism below) is still unbuilt.
- The original blocker line ("corpus measurement BLOCKED until the timing campaign releases
  dev-ai, ~Aug 2") is **stale**. That Phase C campaign has since become a fixed baseline —
  later work cites its operating point (metas 36/37/38) and compares against "the Phase C
  journal canonicals" (`../research/CUBR-NEW24-PRESET-CAMPAIGN-20260811.md`). The corpus
  measurement is unblocked.
- Code anchors below have drifted. Current line numbers on `origin/main`:
  `encode_rans_family_value_stream` at `codec.rs:622` (design cites ~513), `encode_base` at
  `codec.rs:736`, `encode_blocks_parallel` at `codec.rs:1171` (design cites ~1032). The
  structural claims — that the eight-way competition takes no config and that the nested
  competition flows through `encode_blocks_parallel` — still hold; re-verify before coding.

Anyone picking this up should coordinate with the live branch rather than restarting, and
re-confirm the F17/F18 evidence base against current FINDINGS before implementing. Note the
design's own warning: stickiness is **not** byte-exact — the winners are the expensive
candidates, so it costs ratio and must be measured per class on the full 24-file corpus
(slice figures forbidden, F19).

## Evidence base (FINDINGS.md F17/F18 — do not re-derive)

- The 64–80× image/exe encode asymmetry lives in the eight-way per-block
  value-stream competition inside the WINNING path (med16 → nested chunked
  base): ~700 CPU-s per 2 MB spent on the seven losers.
- The competition computes a CONSTANT where it runs: geomix 384/384 blocks on
  x-ray AND ooffice. On text/database, L1 abandons the deferred base before any
  block completes — scope is image/exe only; do not quote a text figure.
- NOT byte-exact: the winners are the expensive candidates, so bounding losers
  saves ~190 s of ~1,100 s. Stickiness costs ratio; it must be measured per
  class on the full 24-file corpus (slice figures forbidden — F19).

## Code anatomy (verified in codec.rs @ 53f4368)

- `encode_rans_family_value_stream(seq_codes, n_distinct)` (line ~513) IS the
  eight-way competition; called once per block by the cube path of
  `encode_base`. It takes NO config — the pin must be threaded in.
- `encode_chunked_bounded` → `encode_blocks_parallel(blocks, config, bound)`
  (~line 1032): work-stealing parallel loop over independent blocks, each via
  `encode_base(b, config)`. **The expensive nested competition (a transform's
  inner chunked container) flows through this same function**, so a sticky
  mechanism here lands exactly where F18 measured the waste.
- Requesting a specific `ValueScheme` family member today still runs the FULL
  competition (consolidated, Gotcha #4) — there is no run-only-this-scheme
  mode. That mode is the primitive stickiness needs.

## Mechanism (deterministic under parallelism)

1. `EncodeConfig.vs_pin: Option<ValueScheme>` (internal): when `Some(s)`,
   `encode_rans_family_value_stream` runs ONLY scheme `s` and returns it.
   Threaded: `encode_base` → cube path → competition fn.
2. `EncodeConfig.vs_sticky: Option<VsSticky { compete_blocks: usize,
   recheck_every: usize }>` (internal): consumed by `encode_blocks_parallel`.
   Probe set = { i < compete_blocks } ∪ { (i - compete_blocks) % recheck_every == 0 }.
   Probe blocks encode with `vs_pin = None` (full competition) and report their
   winning scheme; non-probe block i encodes with `vs_pin = winner of the
   nearest preceding probe block`. Windows between probes may run in parallel;
   the window chain is sequential — determinism holds because every block's
   pin is a pure function of block index + preceding probe winners.
3. Winner capture: `encode_base` needs to surface the block's vs winner.
   Cleanest: an internal `encode_base_vs(b, config) -> (Vec<u8>, Option<ValueScheme>)`
   where the cube path returns the scheme it chose (transform/raw/cm2 paths
   return None → such a probe does not move the pin; if the FIRST probes give
   None, subsequent blocks keep pin=None (full competition) until a probe
   yields a winner — fail-open to correctness).
4. Wire format: UNCHANGED. Decode already replays one scheme per block from
   the header. Round-trip must still be byte-verified per file.
5. `vs_sticky = None` must be byte-identical to today's output — regression
   test against the 10 committed fixtures + a synthetic multi-block input.

## Tests planned

- None-config byte-identity (fixtures + synthetic multi-MB).
- Sticky round-trip byte-exactness on synthetic multi-block inputs.
- Probe/pin schedule unit test (pure function of indices).
- A drift input (first half favors scheme A, second half scheme B) where a
  recheck probe re-pins — proves the recheck path is live, not decorative.

## Measurement plan (AFTER campaign; on dev-ai, quiet, pinned)

- Per-class corpus: encode time + ratio delta vs max, per file, byte-exact RT.
- The 0.21 threshold guard applies to any stacked combination; this lever gets
  its OWN operating point and is never silently stacked (backlog constraint).
