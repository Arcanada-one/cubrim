# FH2-03 orz ceiling probe — NO-GO

Date: 2026-07-22 UTC. Branch: `research/cubr-fh2-03-probe`, based on `d2aa339`.

## Choice

Path B / FH2-03 was selected over another PPMd probability-refinement pass. The existing campaign had already measured final escape APM, BinSumm, and output-coder precision as NO-GO; a correct hit-probability APM for a multinomial symbol coder would require coupled renormalization or a bitwise-CM rewrite. That rewrite overlaps the active `research/cubr-cm-poc` axis, which this probe did not touch.

FH2-03 instead asks a cheaper class question: can a ready ROLZ implementation get close enough to LZMA on `mozilla` to justify building a new LZ+CM rail?

## Reproducible setup

- Input: `/root/corpus-full/silesia/{mozilla,sao,ooffice}` on `root@100.118.134.82`.
- orz: upstream tag `v1.6.2`, commit `87d004f849c8d660cf1e9c9533a39aece79f0357`, binary SHA256 `78cd717078c7bff5089e365f6f924add706f1d88c97e016e6d36eb33564ad446`.
- Upstream metadata caveat: the tag builds an executable reporting version `1.6.1`. Its CLI advertises/defaults to level 3, but the pinned source accepts only levels 0–2; level 2 is the strongest executable configuration.
- Comparator: 7-Zip 23.01, single-file `7z`, LZMA2, `-mx=9`, `-mmt=1`.
- Runner: `code/bench/fh2_03_orz_probe.sh`, deployed SHA256 `0fa3131675ba9618af066e5f6426ba8afd703b0057ffdd2ffd57297922eda946`.
- Every archive was decoded and checked with `cmp`; all reported rows are `cmp=0`.

Primary upstream source: <https://github.com/richox/orz>.

## Preregistered gate

After the 1 MiB screen, full `mozilla` was allowed because orz was only 2.95% behind fresh 7z on the prefix. The full-file gate was fixed before measurement:

- strong GO: orz no larger than 7z;
- directional GO for an LZ+CM build: orz within 5% relative of 7z, matching the FH2-03 card's estimated 3–6% literal-model headroom;
- NO-GO: more than 5% behind 7z.

## Results

The exact charged rows are in `FH2-03-orz-probe.tsv`.

| Scope | File | orz level 2 | 7z LZMA2 mx9 | Verdict |
|---|---|---:|---:|---|
| 1 MiB | mozilla | 660,725 / 0.630116463 | 641,771 / 0.612040520 | full allowed |
| 1 MiB | sao | 762,740 / 0.727405548 | 648,863 / 0.618803978 | screen NO-GO |
| 1 MiB | ooffice | 546,786 / 0.521455765 | 480,890 / 0.458612442 | screen NO-GO |
| full | mozilla | 17,462,672 / **0.340931440** | 13,342,812 / **0.260497598** | **NO-GO** |

Full `mozilla` SHA256 was `657fc3764b0c75ac9de9623125705831ebbfbe08fed248df73bc2dc66e2a963b`. orz was 4,119,860 bytes / 30.877% larger than fresh 7z and 1,674,132 bytes / 10.603% larger than Cubrim's existing MODE_LZ result (15,788,540 / 0.308246623). Full timings were orz encode/decode 2.91s/0.68s and 7z encode/decode 21.49s/0.87s; ratio, not speed, is the gate.

## Verdict

**FH2-03 probe-1 is NO-GO for building the proposed exe LZ+CM rail.** The accessible ROLZ implementation does not approach the LZMA ratio on the decisive 89%-weight `mozilla` file; the 30.877% gap is far beyond the preregistered 5% allowance and even loses to Cubrim's existing LZ rail.

RAZOR was not measured: the discoverable artifact is an old Windows demo/third-party stdio-patched binary without reproducible source or a Linux build. This is recorded as a limitation rather than substituted with forum benchmark claims. No Cubrim codec, DB/site state, PPMd champion, or `research/cubr-cm-poc` file was modified.
