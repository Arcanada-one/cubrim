start H-20 order-2-rANS 2026-06-23T13:02:18Z
built H-20 charged probe (python, no rust needed for gate)
measured order-2-rANS: delta o2-o1 POSITIVE on all 10 files (+225 sparse_clustered ... +1144 text); aggregate stays 0.221726, zero per-file wins
built scheme-8 Order2Rans (rust compiles clean)
tests-green 190 passed incl order-2 round-trip+property+competitive on all 10 files
measured 0.207618 (champion 0.221726, -6.36% rel); scheme-8 wins binary_mixed 8205->6885, text 3177->2889, sparse_clustered 443->400; RT PASS all 10
VERDICT go H-20 order-2-rANS scheme-8: aggregate 0.221726 -> 0.207618 (-6.36% rel), RT clean 10/10, 190 tests green, committed 13c26aa on feat/cubr-h20-order2-rans (NOT pushed, leaderboard untouched)
STOP clean: GO committed-not-pushed, monitor assigns next hypothesis
start H-21 adaptive-streaming-rANS 2026-06-23T14:19:51Z
probe H-21 (FIXED order-1, range-coder-accurate w/ rescaling): adaptive order-1 NO transmitted tables wins big -- sparse_clustered vs 120, text vs 1719, log_like vs 482, block_bound 3433; projected agg 0.194 (cube-only, raw held)
built+tests-green scheme-9 BwtAdaptive (range coder), 190 passed incl rescale stress + corpus RT both entry points
measured 0.177122 vs champion 0.221726 (-20.12% rel); scheme-9 wins sparse_clustered 443->179, text 3177->1784, log_like 1402->570, binary_mixed 8205->6148 (raw->cube), block_bound_runs 4169->3495; RT PASS all 10
VERDICT go H-21 adaptive-range-coding scheme-9: aggregate 0.221726 -> 0.177122 (-20.12% rel), RT clean 10/10, 190 tests green, committed c1a9ce8 on feat/cubr-h21-adaptive-rans (NOT pushed, leaderboard untouched)
STOP clean: GO committed-not-pushed, monitor assigns next hypothesis
start H-22 context-mixing-o1+o0 2026-06-23T15:18:34Z
probe H-22: static JM-backoff NO-GO (order-0 prior misaligned w/ BWT contexts), but LEARNED-weight mix GO -- beats H-21 on 4/5 cube files (block_bound -711, binary_mixed -456, text -71); projected agg 0.16651 vs H-21 0.177122 vs champ 0.221726
built+tests-green scheme-10 BwtContextMix (range coder, pure+learned-mix modes), 190 passed incl f64-determinism rescale stress
measured 0.168262 vs champion 0.221726 (-24.11% rel) AND beats H-21 frontier 0.177122; scheme-10 wins all 5 cube files via learned-mix mode 1 (block_bound 4169->2950 beats gzip 3072, binary_mixed 8205->5679, text 3177->1757); RT PASS all 10
VERDICT go H-22 context-mixing scheme-10: aggregate 0.221726 -> 0.168262 (-24.11% rel), also beats H-21 frontier 0.177122; RT clean 10/10, 190 tests green, committed 42930fa on feat/cubr-h22-context-mixing (NOT pushed, leaderboard untouched)
NOTE: static order-0 backoff prior = documented NO-GO sub-result; learned-weight mix = GO
STOP clean: GO committed-not-pushed, monitor assigns next hypothesis
start H-23 interleaved/SIMD-rANS (throughput-only per brief) 2026-06-23T15:49:13Z
measured H-23: SIZE single=24387 -> 4way=24398 (+11 bytes, ratio-NEGATIVE); THROUGHPUT decode 4way 2.35x (502 vs 214 MB/s), 2way 1.68x; encode ~flat 1.05x
VERDICT nogo-throughput-only H-23 interleaved-rANS: ratio +11 bytes/file (NO-GO for ratio leaderboard), decode 2.35x faster (throughput-only, banked); committed 6dd7bb1 on feat/cubr-h23-interleaved-rans (NOT pushed, codec unchanged)
QUEUE EXHAUSTED: H-20 GO 0.2076, H-21 GO 0.1771, H-22 GO 0.1683, H-23 throughput-only NO-GO. All 4 brief hypotheses executed.
STOP clean.
start CONSOLIDATE-8-9-10 (port scheme-9 BwtAdaptive + scheme-10 BwtContextMix onto main which has scheme-8 Order2Rans) 2026-06-23T16:07:19Z
built consolidated codec: schemes 8+9+10 coexist behind unified competitive min() rail (BwtRans/BwtEntropy/EntropyContext/Order2Rans/BwtAdaptive/BwtContextMix), each keeps its own header byte (8,9,10); no name collisions (H-21 RangeEncoder/RC_*/AdaptModel vs H-22 CmRangeEncoder/CM_*/CmCtx are distinct)
tests-green 192 passed (incl 8 H-21 range-coder + 8 H-22 context-mix tests), RT PASS 10/10 corpus
measured combined aggregate 0.168227 via run_bench --value-scheme bwt-rans (competitive picks best per-file): sparse_clustered 179 (sch9), text 1757 (sch10), log_like 570 (sch9), binary_mixed 5679 (sch10), block_bound_runs 2950 (sch10); RT PASS all 10
VERDICT consolidate-8-9-10 OK: combined aggregate 0.168227 <= threshold 0.168262 (4 bytes better than H-22 standalone 0.168262, per-file min across schemes 9+10), RT clean 10/10, 192 tests green
FINAL AGGREGATE 0.168227
start H-24 logistic/geometric o2+o1+o0 mix (scheme-11) 2026-06-23T16:56:07Z
probe H-24: geometric mix of o2,o1,o0 beats current linear o1+o0 mix on ALL 5 cube files; quantized geo3Q SUM(cube) 9502.5 vs mix 10640.2 (-1138 ideal B); per-file wins text -238, binary_mixed -265, block_bound -515, log_like -92, sparse_clustered -7
projected aggregate 0.168227 -> ~0.1594 (clears champion decisively, edges gzip 0.159674)
VERDICT-PROBE go: implement scheme-11 BwtGeoMix (geometric/logistic learned-weight mix of order-2/1/0, regression-proof competitive min)
built scheme-11 BwtGeoMix (geometric/logistic o2+o1+o0 mix, range coder, ln-table); rust compiles clean, clippy adds 0 new warnings
tests-green 200 passed (+10 H-24: scheme-byte/unit-grid/high-entropy-rescale/corpus-RT/never-regress/property/truncated) incl f64-determinism stress; RT PASS 10/10 corpus + CLI
measured 0.158273 vs champion 0.168227 (-5.91% rel) AND BEATS gzip 0.159674 (-0.88% rel, 164 B); scheme-11 wins all 5 cube files: text 1757->1525, binary_mixed 5679->5330, block_bound 2950->2389 (beats gzip 3072 by 683), log_like 570->557, sparse_clustered 179->169; RT PASS all 10
added code_sha capture to run_bench.py gather_env (CLAUDE.md mandate gap fix)
VERDICT go H-24 geometric/logistic-mix scheme-11 BwtGeoMix: aggregate 0.168227 -> 0.158273 (-5.91% rel), ALSO BEATS gzip 0.159674 (-0.88% rel, 164 B) — GOAL REACHED; RT clean 10/10, 200 tests green, committed 3937caf (code) + 48e28b7 (bench) on feat/cubr-h24-logistic-mix (branched origin/main, NOT pushed, leaderboard untouched)
STOP clean: GO committed-not-pushed, gzip beaten, monitor assigns next hypothesis
start ROBUSTNESS-STUDY (holdout corpus: does gzip-parity generalise beyond the 10-file tuned leaderboard?) 2026-06-23T17:52:09Z
built SEPARATE diverse holdout corpus (6 real files, frozen+committed, DISJOINT from leaderboard corpus): rust_src.rs 26805 (huffman.rs), c_header.h 34649 (/usr/include/stdio.h), config.json 66294 (real WebStorm 3rd-party-libs JSON), prose.txt 17774 (man gzip English), data.csv 17029 (real financial CSV), exe.bin 39384 (/bin/cat ELF)
measured Cubrim (compress --value-scheme bwt-rans, competitive rail) AND bwt-geomix (champion scheme) vs gzip-9 vs zstd-19; RT PASS 6/6 both schemes; code_sha 48e28b7-dirty
NOTE bwt-rans and bwt-geomix produced BYTE-IDENTICAL output on ALL 6 holdout files — geomix's tuned-corpus win did not reproduce on a single holdout file (competitive rail selected the same per-file scheme)
per-file Cubrim-vs-gzip ratio: rust_src 0.2607 vs 0.2528 LOSS; c_header 0.2067 vs 0.1980 LOSS; config.json 1.0002 vs 0.1333 CATASTROPHIC-LOSS; prose 0.3713 vs 0.3762 WIN(marginal 1.3%); csv 0.2137 vs 0.2400 WIN(11%); exe 0.3705 vs 0.3653 LOSS(marginal)
AGGREGATE Cubrim 0.5214 vs gzip 0.2359 vs zstd 0.2214 — Cubrim 2.2x WORSE than gzip on holdout (vs +0.9% edge on tuned corpus); loses to zstd-19 on ALL 6 files
ROOT-CAUSE config.json catastrophe: 66294 B > b*b = 65536 (square-limit, use_square_limit=true) AND BWT primary index is u16 (<=65536) -> any input >64KB cannot enter cube/BWT mode, falls to raw-store = ZERO compression; confirmed boundary: 65000 B -> 0.134 cube mode, 66000 B -> 1.0002 raw
AGGREGATE-excl-oversized-file (5 files <=64KB) Cubrim 0.2874 vs gzip 0.2860 vs zstd 0.2681 — rough gzip PARITY holds within the 64KB cube envelope but Cubrim is NEVER ahead of gzip in aggregate and loses to zstd on every file
VERDICT robustness FAIL: the 2-byte gzip edge on the tuned 10-file corpus does NOT generalise. (1) hard 64KB architectural ceiling (u16 BWT index + square-limit) raw-stores any larger real file = unusable as a general archiver; (2) even within envelope Cubrim only reaches gzip parity, wins 2/6 files (csv, prose-marginal), loses to zstd-19 6/6. Champion is corpus-overfit, not a robust gzip-beater.
artefacts code/bench/gen_holdout_corpus.py + run_holdout_bench.py + docs/ephemeral/research/h-robust-bench.json + frozen holdout/ corpus; committed feat/cubr-robustness (NOT pushed)
STOP clean: robustness study complete, honest FAIL reported, leaderboard untouched
