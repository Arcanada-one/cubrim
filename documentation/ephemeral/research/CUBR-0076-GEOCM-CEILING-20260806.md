# CUBR-0076 — the ceiling of the existing cheap path (GeoCM), measured and bounded

**Measured/derived:** 2026-08-06 UTC.
**Task:** CUBR-0076, brief step 2 — establish whether GeoCM as-is puts the
web-profile gate within reach, *before* designing anything.
**Verdict:** **No — twice over.** GeoCM is never selected on web content
(0 of 12, measured today), and every composition of the programme's measured
numbers leaves it at least ~9× short of even the laxest registered decode bar.
**The prototype is an algorithm problem, not a routing problem.**

## 1. Routing half — the mode census (new measurement, this pass)

Stock encoder at `main` = `96485d1` (binary sha256 `f3316a1e910cbc89…14caa3`,
built with rustc 1.97.1), run on all 12 real samples of
`bench/web-corpus/manifest.v2.json`, every payload SHA-verified against the
manifest first, byte-exact round-trip after every decode. Full rows with
SHA-256 provenance: [`census.tsv`](CUBR-0076-WEBMODE-CENSUS-20260806/census.tsv),
[`provenance.txt`](CUBR-0076-WEBMODE-CENSUS-20260806/provenance.txt), raw
archives under `CUBR-0076-WEBMODE-CENSUS-20260806/raw/`.

| sample | family | orig B | comp B | ratio | outer mode | round trip |
|---|---|---:|---:|---:|---|---|
| css-medium-tailwind-v2 | css | 65,257 | 6,847 | 0.1049 | 16 CM2 | PASS |
| html-large-web-codec-v2 | html | 227,968 | 10,629 | 0.0466 | 16 CM2 | PASS |
| html-medium-home-v2 | html | 25,031 | 4,700 | 0.1878 | 16 CM2 | PASS |
| javascript-medium-magic-string-v2 | javascript | 42,936 | 7,242 | 0.1687 | 16 CM2 | PASS |
| javascript-medium-sourcemap-codec-v2 | javascript | 14,590 | 2,893 | 0.1983 | 16 CM2 | PASS |
| javascript-small-resolve-uri-v2 | javascript | 9,866 | 2,420 | 0.2453 | 16 CM2 | PASS |
| json-api-large-world-benchmark-v2 | json-api | 320,976 | 13,323 | 0.0415 | 16 CM2 | PASS |
| json-api-medium-web-benchmark-v2 | json-api | 98,948 | 5,719 | 0.0578 | 16 CM2 | PASS |
| json-api-small-hypotheses-v2 | json-api | 13,880 | 1,442 | 0.1039 | 16 CM2 | PASS |
| source-map-large-magic-string-v2 | source-map | 112,594 | 13,664 | 0.1214 | 16 CM2 | PASS |
| source-map-small-sourcemap-codec-v2 | source-map | 9,700 | 1,829 | 0.1886 | 16 CM2 | PASS |
| woff2-medium-inter-latin-v20 | woff2 | 23,664 | 23,677 | 1.0005 | 1 RAW | PASS |

**GeoCM: 0 of 12. CM2: 11 of 12. RAW: 1 of 12.**

GeoCM is gated by `geocm::should_try()` — a 2-D periodicity heuristic aimed at
image-like data — and web text never triggers it. There is no configuration,
preset, or environment knob that routes web content to GeoCM; reaching it
would require an encoder change, which is out of scope for this slice by the
brief's own boundary. So "route the web corpus to the cheap path" is not an
available move in the codec as it exists.

Two side observations the prototype design inherits: the woff2 sample goes to
RAW passthrough at ratio 1.0005 (already-compressed content is handled
correctly and decodes at copy speed — the profile must keep that), and CM2's
density on this corpus is the density WIN's substance — whatever replaces CM2
at decode time is spending that measured advantage.

## 2. Speed half — what the measured numbers already bound

No new wall-clock timing was measured in this pass, and that refusal is
recorded below. Every anchor is a prior measurement with committed provenance;
each is labeled with its scope. The registered bars (see
[`CUBR-0076-GATE-20260806.md`](CUBR-0076-GATE-20260806.md)): GO ≥ 50 MB/s,
WIN ≥ 200 MB/s, product bar ≥ 0.50 × brotli-5.

**Anchor A — the binding web-corpus verdict (CUBR-0074, quiet stand,
harness protocol).** `decode_throughput_vs_brotli5 = 0.004410` on the real
web corpus, CM2-dominated (the census above shows CM2 is what actually runs
there). Miss vs 0.50: **113×**.

**Anchor B — GeoCM's own best case (dev-ai pinned campaign, meta 35,
FINDINGS F16).** `mr` — the file GeoCM wins, its natural data class —
decodes 9,970,564 B in 5.9 s ≈ **1.69 MB/s**. Against the 50 MB/s GO bar:
**~30× short**, in the mode's most favourable measured setting.

**Anchor C — cycle attribution (this host, core-pinned rdtsc at the 3.6 GHz
TSC, CUBR-DECODESPREAD-GEO-20260804, two-file diagnostic).** GeoCM on the
`mr` 2 MiB slice: 105,262.41 cycles per compressed byte ×
(404,341 / 2,097,152) = **20,295 cycles per output byte**. The gate budgets,
converted at the same 3.6 GHz TSC the instrument records
(`total_cycles / total_nanos` = 3.600 GHz exactly): 50 MB/s ⇒ **72 cycles per
output byte**, 200 MB/s ⇒ 18. GeoCM's measured cost is **~282× the GO
budget** on its best-case data. Caveat carried from the source document: the
instrumented totals are denominators for attribution, not a decode-speed
verdict — this anchor is direction and order of magnitude, and it agrees with
Anchor B's uninstrumented 30× at full-file scale.

**Anchor D — the steel-man composition.** Grant web-corpus CM2 decode the
*entire* mode-level advantage measured on the STICKY12 pair (12.67× per
compressed byte, mr-GeoCM vs nci-CM2): 0.004410 × 12.67 = **0.0559** vs
0.50 — still **8.9× short**. Using the per-output-byte form of the same
spread (3.26×): 0.0144 — 35× short. This deliberately mixes file classes in
GeoCM's favour and it still fails.

**Anchor E — the Amdahl wall (CUBR-0075 attribution).** Eliminating the CM2
model *entirely* — adaptation 52.09% + counter-state lookup 28.34% +
dot products 19.57% — yields at most **22.52×**: 0.004410 × 22.52 = 0.0993,
**5.0× short of 0.50**. No optimisation of the existing CM2 decode path
reaches the gate even at the unreachable limit.

## 3. Recorded timing refusal

A fresh decode-throughput measurement of the census archives would require a
genuinely quiet host. `arcana-devs` carries a steady ~1.2-core adsessor soak
plus three live CI runners — unfit for timing under the programme's own
standard (FINDINGS F15). `dev-ai`/`162.55.81.5` is the pinned campaign stand:
files may be read, compute may not run. **Therefore no new timing number
exists in this document, and none is estimated.** This is the same refusal
Phase C recorded, for the same reason. The void stays in this journal; the DB
(`web_benchmark_hypothesis_evaluation` = 0) is untouched.

## 4. Conclusion

The brief asked: if GeoCM as-is is within reach of the gate, the prototype is
a routing problem. Measured answer: GeoCM is not reachable by routing
(0 of 12), and not within reach if routed (≥ 8.9× short under the most
favourable composition of measured numbers; ~30–282× short on its own
measured best case). Combined with Anchor E, the conclusion is structural:
**no existing decode path, routed or optimised, reaches the registered gate.
The web profile must change the decode-time architecture** — which is exactly
the pre-registered hypothesis family 13–17. The proposal is in
[`CUBR-0076-PROTOTYPE-SHAPE-20260806.md`](CUBR-0076-PROTOTYPE-SHAPE-20260806.md).

## The standing dual verdict, quoted whole

**Archival: worth pursuing** — best single split 2.09×, whole model 22.52×.
**Web: unreachable on this algorithm** — density WIN `0.877644` never ships
without decode `0.004410` in the same sentence; the gate needs 0.50 and the
measured miss is 113×.
