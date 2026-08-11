# NEW-02 canonical PPMd oracle-grid results

Date: 2026-08-10
Status: `COMPLETE` source publication; `CHARACTERIZED_NO_SELECT` scientific outcome

## Authority and boundary

The landed validator authenticated the immutable `new02-ppmd-oracle-4352d71ee8f4479c-20260810T020926Z` publication:
exact main `708cda945a285526610371d812e4f54725eb6baf`, harness run ID `4352d71ee8f4479c17312750d3b08f7095f0fb57737fbf55ac8877b10e0864ba`, manifest
SHA-256 `4a39fb5ec1914ae7e1e296c44b2cec4cf4ecf2afa48af3216a9ec2552f3cb88c`, and all 243 declared cells. Every cell
encoded, underwent exact one-member PPMd inspection, decoded, passed `cmp -s`, and
matched the frozen input SHA-256. `results.tsv` states all 243 outcomes and their
measured timing/RSS values without any corpus-wide average.

The preregistration contains no ceiling, aggregate, ranking, winner rule, or
implementation-selection rule. Therefore this package does not select a parameter
cell, issue GO/NO-GO, build a candidate, or compute a fraction of ceiling. The
scientific result is characterization only: `NO-SELECT`.

No systemd unit or systemd invocation ID is recorded by the canonical harness. The
authenticated invocation identity is the harness run ID above; the absence of those
two systemd fields is preserved explicitly in `provenance.json`, not inferred.

## Var.H and Var.I per-file effects

Var.H is the PPMd order axis (`4`, `6`, `8`). Var.I is requested PPMd memory
(`16`, `64`, `256` MiB). Each archive triple is `16/64/256 MiB`. Order deltas are
`4->6,6->8` at each fixed memory; memory deltas are `16->64,64->256` at each fixed
order. A negative delta means the later level charged fewer archive bytes. These are
exhaustive adjacent contrasts, not a ranking or selection rule.

| cohort/file | order 4 archives | order 6 archives | order 8 archives | Var.H deltas at m16; m64; m256 | Var.I deltas at o4; o6; o8 |
|---|---:|---:|---:|---|---|
| `world/dickens` | 2498671/2498671/2498671 | 2341442/2296792/2296792 | 2455623/2272524/2272524 | -157229,+114181; -201879,-24268; -201879,-24268 | +0,+0; -44650,+0; -183099,+0 |
| `world/reymont` | 1263399/1263399/1263399 | 1141461/1141461/1141461 | 1096885/1071818/1071818 | -121938,-44576; -121938,-69643; -121938,-69643 | +0,+0; +0,+0; -25067,+0 |
| `world/webster` | 7673604/7673604/7673604 | 7068044/6544130/6544130 | 7387437/6763725/6396385 | -605560,+319393; -1129474,+219595; -1129474,-147745 | +0,+0; -523914,+0; -623712,-367340 |
| `world/xml` | 606520/606520/606520 | 496463/496463/496463 | 436482/436482/436482 | -110057,-59981; -110057,-59981; -110057,-59981 | +0,+0; +0,+0; +0,+0 |
| `world/enwik8` | 26060068/25726214/25726214 | 24849810/23301162/22403589 | 25388742/23576806/22074472 | -1210258,+538932; -2425052,+275644; -3322625,-329117 | -333854,+0; -1548648,-897573; -1811936,-1502334 |
| `world/alice29.txt` † | 40053/40053/40053 | 38986/38986/38986 | 38890/38890/38890 | -1067,-96; -1067,-96; -1067,-96 | +0,+0; +0,+0; +0,+0 |
| `world/asyoulik.txt` † | 36690/36690/36690 | 36344/36344/36344 | 36340/36340/36340 | -346,-4; -346,-4; -346,-4 | +0,+0; +0,+0; +0,+0 |
| `world/cp.html` † | 6816/6816/6816 | 6692/6692/6692 | 6688/6688/6688 | -124,-4; -124,-4; -124,-4 | +0,+0; +0,+0; +0,+0 |
| `world/lcet10.txt` † | 101312/101312/101312 | 96553/96553/96553 | 96254/96254/96254 | -4759,-299; -4759,-299; -4759,-299 | +0,+0; +0,+0; +0,+0 |
| `world/plrabn12.txt` † | 134803/134803/134803 | 132529/132529/132529 | 133119/133119/133119 | -2274,+590; -2274,+590; -2274,+590 | +0,+0; +0,+0; +0,+0 |
| `world/xargs.1` † | 1621/1621/1621 | 1610/1610/1610 | 1612/1612/1612 | -11,+2; -11,+2; -11,+2 | +0,+0; +0,+0; +0,+0 |
| `tuned/binary_mixed.bin` | 5467/5467/5467 | 5467/5467/5467 | 5467/5467/5467 | +0,+0; +0,+0; +0,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/block_bound_runs.bin` | 2646/2646/2646 | 2621/2621/2621 | 2578/2578/2578 | -25,-43; -25,-43; -25,-43 | +0,+0; +0,+0; +0,+0 |
| `tuned/both_sparse_16.bin` | 166/166/166 | 166/166/166 | 166/166/166 | +0,+0; +0,+0; +0,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/both_sparse_24.bin` | 175/175/175 | 175/175/175 | 175/175/175 | +0,+0; +0,+0; +0,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/dense.bin` | 4394/4394/4394 | 4394/4394/4394 | 4394/4394/4394 | +0,+0; +0,+0; +0,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/log_like.bin` | 579/579/579 | 510/510/510 | 511/511/511 | -69,+1; -69,+1; -69,+1 | +0,+0; +0,+0; +0,+0 |
| `tuned/random_high.bin` | 4411/4411/4411 | 4411/4411/4411 | 4411/4411/4411 | +0,+0; +0,+0; +0,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/sparse_clustered.bin` | 244/244/244 | 249/249/249 | 253/253/253 | +5,+4; +5,+4; +5,+4 | +0,+0; +0,+0; +0,+0 |
| `tuned/sparse_small.bin` | 164/164/164 | 165/165/165 | 165/165/165 | +1,+0; +1,+0; +1,+0 | +0,+0; +0,+0; +0,+0 |
| `tuned/text.bin` | 1302/1302/1302 | 1298/1298/1298 | 1362/1362/1362 | -4,+64; -4,+64; -4,+64 | +0,+0; +0,+0; +0,+0 |
| `holdout/rust_src.rs` | 6176/6176/6176 | 5926/5926/5926 | 5777/5777/5777 | -250,-149; -250,-149; -250,-149 | +0,+0; +0,+0; +0,+0 |
| `holdout/c_header.h` | 6139/6139/6139 | 5711/5711/5711 | 5579/5579/5579 | -428,-132; -428,-132; -428,-132 | +0,+0; +0,+0; +0,+0 |
| `holdout/config.json` | 8133/8133/8133 | 7416/7416/7416 | 7163/7163/7163 | -717,-253; -717,-253; -717,-253 | +0,+0; +0,+0; +0,+0 |
| `holdout/prose.txt` | 5723/5723/5723 | 5642/5642/5642 | 5593/5593/5593 | -81,-49; -81,-49; -81,-49 | +0,+0; +0,+0; +0,+0 |
| `holdout/data.csv` | 3301/3301/3301 | 3287/3287/3287 | 3305/3305/3305 | -14,+18; -14,+18; -14,+18 | +0,+0; +0,+0; +0,+0 |
| `holdout/exe.bin` | 13267/13267/13267 | 13139/13139/13139 | 13064/13064/13064 | -128,-75; -128,-75; -128,-75 | +0,+0; +0,+0; +0,+0 |

† Registered Canterbury file: measured in all nine cells and retained in both TSV
files, but excluded from broader claims because fixed archive overhead dominates
these small inputs. This package makes no broader aggregate claim in any case.

## Files

- `results.tsv`: all 243 authenticated cell outcomes, exact archive/input/decoded
  identities, effective member method, measured timing/RSS, and round-trip gates.
- `effects.tsv`: the exact 27 per-file archive matrices and exhaustive adjacent
  Var.H/Var.I byte deltas shown above.
- `provenance.json`: COMPLETE source, exact-main/run/tool identities, and explicit
  absence of canonical systemd unit/invocation fields.
- `summary.json`: structured `CHARACTERIZED_NO_SELECT` verdict and reporting bounds.
- `SHA256SUMS`: deterministic package-data hashes.
- `verify_new02_results.py` and `test_verify_new02_results.py`: fail-closed verifier,
  raw re-authentication path, reproducible builder, and mutation tests.

No database, API, site, backlog, candidate, or campaign state is changed by this
package.
