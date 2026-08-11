# CUBR-0076 — step 2 prototype, results

**Executed:** 2026-08-11 UTC
**Preregistration:** [`CUBR-0076-PROTOTYPE-PREREG-20260811.md`](CUBR-0076-PROTOTYPE-PREREG-20260811.md),
committed before the corpus was touched.
**Code:** `code/cubrim-rs/src/web.rs` (MODE_WEB), gate
`code/cubrim-rs/tests/web_profile_corpus.rs`.
**Scope:** density and correctness only. **Nothing here is timed.** The
decode-speed leg of hypothesis 12 remains a void until a quiet host exists
under the CUBR-0074 protocol; `evaluation` stays 0 and no DB row is written.

## Verdict

**The prototype reproduces the modelled GO, on real bytes, byte-exactly.**

```
web profile aggregate    120939 B      12 of 12 round-trips byte-exact
gzip-9   (GO bar)        129193 B      ratio 0.9361   PASS
brotli-11 (WIN bar)      108495 B      ratio 1.1147   FAIL
charged size model       121608 B      prototype is 0.55% BELOW the model
original                 965410 B
```

All twelve samples beat their own gzip-9 baseline; none reaches brotli-11.

| sample | orig | web profile | gzip-9 | brotli-11 | vs gz | vs br |
|---|---|---|---|---|---|---|
| tailwind.css | 65257 | 10361 | 11278 | 9161 | 0.919 | 1.131 |
| html-large-web-codec-v2.html | 227968 | 14428 | 15804 | 11746 | 0.913 | 1.228 |
| html-medium-home-v2.html | 25031 | 5563 | 5801 | 4763 | 0.959 | 1.168 |
| magic-string.umd.js | 42936 | 9375 | 9896 | 8672 | 0.947 | 1.081 |
| sourcemap-codec.umd.js | 14590 | 3522 | 3705 | 3280 | 0.951 | 1.074 |
| resolve-uri.umd.js | 9866 | 2797 | 2895 | 2467 | 0.966 | 1.134 |
| json-api-large-world-benchmark-v2.json | 320976 | 18590 | 21196 | 14910 | 0.877 | 1.247 |
| json-api-medium-web-benchmark-v2.json | 98948 | 9630 | 10516 | 8344 | 0.916 | 1.154 |
| json-api-small-hypotheses-v2.json | 13880 | 1558 | 1674 | 1383 | 0.931 | 1.127 |
| magic-string.umd.js.map | 112594 | 19058 | 20194 | 17827 | 0.944 | 1.069 |
| sourcemap-codec.umd.js.map | 9700 | 2407 | 2546 | 2319 | 0.945 | 1.038 |
| inter-latin.medium.woff2 | 23664 | 23650 | 23688 | 23623 | 0.998 | 1.001 |
| **total** | **965410** | **120939** | **129193** | **108495** | **0.936** | **1.115** |

Twelve fixed files, reported per file. The total row is a sum of the same
twelve files under every column — not a corpus-wide average compression claim.

## What the prototype is

`MODE_WEB` (container byte 18): a whole-file LZ parse coded with canonical
Huffman tables that are transmitted in the block header and frozen for the
block. Decode adapts nothing; it runs through the repository's existing flat
`HuffTable` lookup, one table read per symbol. Extended distance codes carry
the whole-file window the size model showed was worth ~2.4 KB per large sample
against the 64 KiB carrier. The encoder offers 1-context and 3-context literal
tables (context = a fixed public function of the previously emitted byte) and
keeps the smaller; the parse is the shortest-path parse the size model showed
was decisive.

It is opt-in (`EncodeConfig::web_profile`, default `false`). With the profile
off, output is byte-identical to before — asserted per sample by
`web_profile_off_is_byte_identical_to_the_default_encoder`.

## The finding that changed the design: a density-only pick defeats the profile

The first integration selected `min(web candidate, whole existing stack)` —
the competitive-min pattern every other candidate in this encoder uses. Run on
the census it chose **the incumbent on 11 of 12 samples** and returned a
94358 B aggregate that looks like a triumph and is worthless: those 11 archives
are CM2 archives, whose decode is precisely the 113x-too-slow path the web gate
exists to rule out. The profile had silently become a no-op that made the
output *denser*.

The cause is structural, not a bug: the table-driven scheme **spends** density
to buy decode-time architecture (+28.8% over CM2 by construction), so a
density-only comparison can never pick it while the adaptive champion is in the
running. A profile that selects on the axis it is trading away cannot work.

The fix, now in `encode_with_config`: when `web_profile` is on, the candidate
set is the **decode-eligible** class only — the table-driven container and
raw-store, whose decode is a bounds-checked copy. Every other mode's decode
class is unclassified, so it stays out of the set until it is measured. The
no-regression property is kept against the eligible floor: the profile's output
is never larger than raw-store, asserted by
`web_profile_never_regresses_a_file`.

**Generalisable rule this produces:** when a mode exists to trade axis A for
axis B, its selection rule must range over candidates that are admissible on
axis B. Competitive-min on axis A is not a safe default there — it is a silent
opt-out.

## Predictions: four held, one wrong in an instructive way

1. **Held.** Round trip 12 of 12 byte-exact, through the public `decode` entry
   point.
2. **Held.** Predicted aggregate 119000-127000 B; measured **120939 B**.
3. **Held.** Below the gzip-9 bar, above the brotli-11 bar.
4. **WRONG as stated.** "MODE_WEB is selected on at least 11 of 12 samples"
   was true only after the selection-class fix above (now 12 of 12). As
   originally integrated it was selected on **1** of 12 — and the one was
   woff2, exactly the sample the prediction singled out as the doubtful case.
   The prediction was written as if the profile competed within its own class;
   the code competed against everything. Recorded as wrong, and it is the most
   useful thing this step produced.
5. **Held.** With the profile off, every sample encodes byte-identically to the
   default encoder, and MODE_WEB never appears.

## Prototype versus model

The prototype came in **669 B (0.55%) below** the charged size model, despite
three deviations that should each cost bytes (14-bit code-length limit instead
of 15, to reuse the repository's flat decode table; a 14-byte fixed frame
header instead of ~12 varint bytes; an 18-bit hash chain instead of an exact
3-byte dictionary).

The difference is **not attributed**. The two implementations also differ in
the seed parse handed to the shortest-path refinement, which is the most likely
source, but that was not isolated. What can be said honestly: the model was
conservative in the direction it claimed to be, and the gap is small enough
(0.55%) that neither bar's verdict moves. Two samples (`resolve-uri.umd.js`,
`sourcemap-codec.umd.js.map`) land byte-identical to the model.

## Gates, all green

- `web_profile_corpus`: 3 tests — byte-exact round trip on all 12 samples with
  the aggregate gzip-9 bar asserted, default-path byte-identity, no-regression.
- `web.rs` unit tests: 16 — round trips over text, JSON, single-byte runs, all
  byte values, incompressible bytes and every length 1..64; fail-closed on
  truncation, on corruption (with a no-panic sweep over the payload), on
  declared-length mismatch and on checksum mismatch; code-length limit and
  completeness; code-length RLE round trip; distance-alphabet coverage.
- Existing suite unchanged and green: 338 lib tests, `scheme_roundtrip` 7/7
  (the CI silent-data-loss gate), `differential` 10/10, `hostile_inputs` 6/6
  (run memory-capped per the standing rule), `cli_archiver` 5/5.
- `cargo fmt --check` clean; `cargo clippy --release --all-targets` reports
  zero warnings.

## Deliberately not done

- **No CLI flag.** The library surface (`EncodeConfig::web_profile`) is enough
  to run the research. A user-facing `--profile web` would advertise a
  decode-speed property that is still unmeasured; shipping it before the quiet-
  host measurement would be a product claim the evidence does not support.
- **No decode-speed number, no throughput estimate, not even an order of
  magnitude.** The architecture-class argument (flat table lookup per symbol,
  no adaptation) is the reason to expect the budget is reachable. It is an
  argument. It is not upgraded by this document.
- **No DB write, no leaderboard, no site.** `evaluation` stays 0.

## What is now licensed

Step 3 of the prototype slice — density range per media family on the census
corpus — can run on any host, and the numbers above are already most of it.
Step 4, throughput, is the one that decides hypothesis 12, and it needs the
quiet host. The standing refusal holds until stand time exists: no number is
estimated in the meantime.

Standing dual verdict, unchanged: archival **worth pursuing** (best single
split 2.09x, whole model 22.52x); web **unreachable on this algorithm** —
density WIN `0.877644` never without decode `0.004410` in the same sentence.
What steps 1 and 2 establish is that a *different* value scheme holds gzip-9
density on real web bytes with a decode that adapts nothing — the density leg
of hypothesis 13, measured rather than argued. The speed leg is untouched.

## Disclosure

Wire format, decoder-branch inventory, mode byte, the extended distance-code
construction, and all results above are format/decoder-side or benchmark
results — **public**. The encoder uses a textbook hash-chain match finder and a
shortest-path parse against a real price table, both long-standing public
technique, and a context function that is a fixed published function of the
previous byte. No new encoder-side technique was invented, so the
name-and-escalate rule (CUBR-0072 / LEGAL-0062) is not triggered.
