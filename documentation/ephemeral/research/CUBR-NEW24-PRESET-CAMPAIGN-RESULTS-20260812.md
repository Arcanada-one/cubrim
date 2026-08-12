# NEW-24 preset campaign — results and F12 adoption adjudication

**State: FINAL. The campaign ran to completion and the pre-committed adoption rule
FIRES.** Prereg: `CUBR-NEW24-PRESET-CAMPAIGN-20260811.md` (main `563b94e`); the
runner logs `"prereg":"563b94e"` in its `run_start` line, so the design under which
these numbers were produced is pinned in the journal itself.

Nothing below is a corpus-wide average — the prereg forbids them. Every figure is
per file. Canterbury files are measured and reported but excluded from class-level
claims.

> **This record supersedes its own earlier IN-PROGRESS revision**, which adjudicated
> from a 22-cell partial journal covering 10 of 24 files. Thirteen more files have
> landed, so the criteria can now be scored rather than previewed. The partial
> journal is retained as `journal.partial.jsonl` beside the final one; the records
> the two share are **byte-identical**, so nothing was re-measured.
>
> **Two RSS columns changed anyway, and the reason is a convention, not a
> measurement.** The superseded revision reported the *mean* of the three decode
> reps divided by 1000; this record reports the *peak* divided by 1024. C-4 is
> written about "decode **peak** RSS", so peak is the statistic the criterion asks
> for, and `/usr/bin/time -v` reports KiB, so 1024 is the right divisor. `webster`
> therefore reads 8033 M / 3769 M here against 8224 M / 3859 M there, from the same
> three journal lines. The ratio — the thing C-4 actually tests — is 46.9% under
> both conventions, so no verdict moves. **All RSS figures in this record are peak
> across the three reps, in MiB.**

## Campaign status — complete

Started 2026-08-11T19:53:35Z, `run_end` 2026-08-12T03:21:05Z, ~7.5 h against a 16 h
budget. It survived the 23:45Z fleet kill because it was launched under
`setsid nohup`.

| | |
|---|---|
| cells complete | **48** |
| files with both arms | **23 of 24** |
| M8S cells | 2 (`nci`, `osdb`) |
| voids | **2** — `enwik8/full`, `enwik8/f12` |
| gate failures | **0** |

Every `full`-arm archive passed the canonical identity gate against the Phase C
journal canonicals, and every decode in every cell passed round-trip (`cmp` +
sha256) before its timing was read.

### The one void, and why it is not an infrastructure casualty

Both `enwik8` arms died `rc=137`. The obvious reading — the fleet was killed twice
that night, and `run_end` lands at 03:21:05Z, one minute after the 03:20Z kill — is
**wrong**, and it is worth writing down why, because the coincidence is convincing.

- `enwik8` is line 14 of a 25-line manifest, not the last. The loop continued past
  it and completed 11 more canterbury files afterwards.
- The final `cell_done` is `xargs.1/f12` at 03:21:05Z — and `xargs.1` is **the last
  line of the manifest**, with `run_end` stamped the same second. A run terminated
  by an external kill does not finish its last scheduled cell and then write its own
  end marker. The manifest was exhausted.
- The same journal shows the campaign eating straight through the *other* kill:
  `nci/m8s` completed 23:48:44Z and `ooffice/full` 23:56:56Z, both after 23:45Z.
- The kernel names the cause: `oom-kill:constraint=CONSTRAINT_MEMCG`,
  `anon-rss:14639908kB` — **exactly the campaign's own `MemoryMax=14G` encode cap**,
  on a host with 100 GB free. It is a cgroup cap kill, not host pressure and not the
  keepalive runaway.

So `enwik8` at 100 MB cannot be encoded at `--preset max` inside the preregistered
14 GiB cap. That is a **product fact**, not a stand failure, and it is symmetric:
both arms died the same way, so the file drops out of the comparison entirely rather
than biasing one side. The prereg says a cell that cannot pass its gates is
"reported failed, never substituted", so re-running it at a larger cap would be
substitution and was **not** done.

## Control-arm integrity

The strongest check available, and it is exact. For all 23 paired files the control
arm's ratio equals the Phase C meta-36 cubrim ratio **to 0.000%**:

<!-- gate:literal -->
```
alice29.txt 0.242700=0.242700   dickens  0.207263=0.207263   mozilla 0.239116=0.239116
webster     0.139745=0.139745   samba    0.145278=0.145278   x-ray   0.429187=0.429187
... 23 of 23 match, 0 mismatches
```
<!-- /gate:literal -->

So the F12 arm is being compared against a control that reproduces the standing DB
figures exactly, and every density percentage below has a denominator anchored to
meta-36 rather than to a re-measurement that drifted.

## Container mode — read off the wire, not inferred

Byte 5 of each retained control archive is the container mode. This is the ground
truth for "is this file CM2-won", which decides whether C-1 or C-2 applies to it:

| mode | meaning | files |
|---|---|---|
| 16 `MODE_CM2` | 18 files | alice29.txt, asyoulik.txt, cp.html, dickens, fields.c, grammar.lsp, **kennedy.xls**, lcet10.txt, mozilla, nci, osdb, plrabn12.txt, reymont, samba, sum, webster, xargs.1, xml |
| 17 `MODE_GEOCM` | 3 | mr, ptt5, x-ray |
| 13 `MODE_RECORDCM` | 1 | sao |
| 8 `MODE_BCJ` | 1 | ooffice |

**The prereg's own scope list was wrong on one file.** It named "mr, x-ray, sao,
ptt5, kennedy.xls at minimum" as the non-CM2 set. `kennedy.xls` is `MODE_CM2` (16)
and belongs to the C-2 group, not C-1's. The list was explicitly illustrative
("at minimum"), and the criterion is defined by the actual winner, so this is scored
on the measured set — but a prediction that names files should be checked against
the wire before it is used to scope anything.

## Per-file results (both sides of the trade)

`ident` = F12 archive byte-identical to control. `dens%` = F12 bytes vs control.
Decode figures are the median of three reps.

| file | class | mode | ident | dens% | dec full (s) | dec f12 (s) | speedup | RSS full | RSS f12 | RSS% |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| mr | image | 17 | **YES** | +0.00 | 6.59 | 6.61 | 1.00× | 88 M | 88 M | 100% |
| ptt5 † | image | 17 | **YES** | +0.00 | 0.43 | 0.43 | 1.02× | 77 M | 77 M | 100% |
| x-ray | image | 17 | **YES** | +0.00 | 6.25 | 6.14 | 1.02× | 88 M | 88 M | 100% |
| sao | binary | 13 | **YES** | +0.00 | 22.57 | 23.12 | 0.98× | 95 M | 94 M | 99% |
| ooffice | exe | 8 | **no** | **+8.79** | 57.13 | 26.29 | 2.17× | 5242 M | 2297 M | 44% |
| dickens | text | 16 | no | +3.58 | 100.96 | 44.62 | 2.26× | 7152 M | 3188 M | 45% |
| reymont | text | 16 | no | +4.08 | 59.83 | 25.59 | 2.34× | 4564 M | 1946 M | 43% |
| webster | text | 16 | no | +3.31 | 391.58 | 159.38 | 2.46× | 8033 M | 3769 M | 47% |
| xml | text | 16 | no | +4.14 | 44.04 | 19.25 | 2.29× | 4035 M | 1883 M | 47% |
| samba | code | 16 | no | +1.82 | 178.93 | 80.88 | 2.21× | 9962 M | 4538 M | 46% |
| mozilla | exe | 16 | no | **+7.53** | 419.90 | 195.01 | 2.15× | 10166 M | 4654 M | 46% |
| nci | database | 16 | no | +2.68 | 229.58 | 103.54 | 2.22× | 7128 M | 3116 M | 44% |
| osdb | database | 16 | no | **+8.85** | 109.34 | 47.56 | 2.30× | 9982 M | 4573 M | 46% |
| alice29.txt † | text | 16 | no | +2.65 | 1.45 | 0.65 | 2.24× | 182 M | 76 M | 42% |
| asyoulik.txt † | text | 16 | no | +2.12 | 1.18 | 0.51 | 2.32× | 100 M | 42 M | 42% |
| cp.html † | text | 16 | no | +3.89 | 0.25 | 0.13 | 1.88× | 30 M | 14 M | 47% |
| lcet10.txt † | text | 16 | no | +3.04 | 3.91 | 1.71 | 2.29× | 346 M | 145 M | 42% |
| plrabn12.txt † | text | 16 | no | +3.23 | 4.41 | 1.96 | 2.25× | 326 M | 140 M | 43% |
| xargs.1 † | text | 16 | no | +2.61 | 0.10 | 0.07 | 1.55× | 30 M | 14 M | 47% |
| fields.c † | code | 16 | no | +4.82 | 0.15 | 0.09 | 1.68× | 30 M | 14 M | 47% |
| grammar.lsp † | code | 16 | no | +3.74 | 0.09 | 0.07 | 1.35× | 28 M | 14 M | 48% |
| kennedy.xls † | binary | 16 | no | **+29.06** | 7.68 | 1.64 | 4.67× | 570 M | 77 M | 14% |
| sum † | binary | 16 | no | **+8.46** | 0.36 | 0.19 | 1.93× | 54 M | 25 M | 46% |
| enwik8 | text | — | **VOID** | — | — | — | — | — | — | — |

† canterbury — measured and reported, excluded from class-level claims.

`kennedy.xls` at **+29.06%** is the largest density loss in the campaign and the
largest speedup (4.67×). It is canterbury, so it does not enter a class claim, but
it is the clearest single illustration of the trade the tier makes.

## C-1 — scope of effect — **FALSIFIED**

> Predicts: on files whose meta-36 winner is not CM2, the F12 archive is
> byte-identical and decode wall is within ±10%.

| file | mode | byte-identical | decode deviation | verdict |
|---|---|---|---:|---|
| mr | 17 | YES | +0.2% | holds |
| ptt5 | 17 | YES | −1.6% | holds |
| x-ray | 17 | YES | −1.7% | holds |
| sao | 13 | YES | +2.4% | holds |
| **ooffice** | **8** | **NO** — 1,763,460 → 1,918,471 B | **−54.0%** | **FALSIFIES** |

Four of five hold exactly. `ooffice` breaks it in both halves at once, and the
mechanism is legible: `MODE_BCJ` **nests a `MODE_CM2` blob**, so the tier reaches
inside a container whose outer mode is not CM2. The prediction's premise — "the tier
only changes the CM2 candidate; the competitive rail's winner is unchanged" — is
true about the *rail* and false about the *archive*, because CM2 appears nested as
well as top-level.

A naive reading of the mode byte alone would have mis-scored `ooffice` as
CM2-untouched and hidden the falsification. C-1 is recorded as **falsified**, not
narrowed.

## C-2 — density

**Clause (a), per-class worsening ceilings — FALSIFIED in the exe class.**

Silesia only, per protocol:

| class | worst file | dens% | ceiling | verdict |
|---|---|---:|---:|---|
| text | xml | +4.14 | +5% | within |
| code | samba | +1.82 | +5% | within |
| database | osdb | +8.85 | +10% | within |
| **exe** | **mozilla** | **+7.53** | **+6%** | **EXCEEDS** |

`ooffice` (+8.79%) is the other exe file and also exceeds, but it is scored under
C-1 rather than here, since its container is not CM2. Either way the exe ceiling is
breached by every exe file in the corpus.

**Clause (b), lead-survival — the clause the adoption rule keys on — HOLDS.**

A led file survives when the F12 ratio still beats every other archiver. The prereg
words the scope ambiguously ("on CM2-won files … cubrim's meta-36 rank-1 survives on
≥80% of the files it currently leads"), so all four readings are reported. **The
threshold is met under every one of them**, which is the point — the result does not
depend on resolving the ambiguity:

| scope | survived | rate | verdict |
|---|---|---:|---|
| CM2-won only (narrowest) | 13/16 | **81.2%** | PASS |
| all paired files | 18/21 | 85.7% | PASS |
| Silesia CM2 only | 7/7 | 100% | PASS |
| Silesia, all modes | 11/11 | 100% | PASS |

The three losses are the same files in every scope — `cp.html` (24 KB),
`grammar.lsp` (3.7 KB) and `sum` (38 KB) — all canterbury, all tiny, all in the
regime the protocol already treats as fixed-overhead-dominated.

**The margin is thin and should be read honestly.** Under the narrowest scope the
result is 13 of 16; one further loss would be 75% and would fail. That thinness is
entirely a composition effect: it exists only because the narrow scope counts small
canterbury files, and on the Silesia subset the same measurement is 7/7 with no
losses at all. A future campaign that changes the corpus mix could move this number
without anything about the tier changing.

**Clause (c), M8S on database inputs — HOLDS.**

| file | dens% | ceiling | verdict |
|---|---:|---:|---|
| nci / M8S | +3.21 | +8% | within |
| osdb / M8S | +6.50 | +8% | within |

**M8S splits the two database files rather than beating F12 on both**, and the
adoption rule's "+M8S on database-classed inputs" clause should be read against that,
not against a uniform win:

| file | F12 | M8S | M8S vs F12 |
|---|---:|---:|---|
| nci | +2.68% | +3.21% | **worse** by 0.53 pt |
| osdb | +8.85% | +6.50% | better by 2.35 pt |

So the clause buys a real gain on `osdb` and pays a small loss on `nci`. Both stay
inside the +8% M8S ceiling and the +10% database ceiling, so nothing is falsified —
but "M8S on database inputs" is a net-positive default across these two files, not a
free improvement, and CUBR-0103 should implement it as such.

## C-3 — speed — **HOLDS**

> Predicts: median F12 decode speedup on CM2-won files ≥ 1.5×.

**Median speedup = 2.243×** across the 18 CM2-won files. Range 1.35× (`grammar.lsp`,
90 ms baseline) to 4.67× (`kennedy.xls`). Every file ≥ 8 MB lands between 2.15× and
2.46×, so the effect is not carried by a few outliers.

**The `tbits` sub-clause is NOT EVALUABLE.** The prereg also predicted "≥ 2.0× on
files ≥ 8 MB with `tbits ≥ 26`". The runner invoked cubrim with `--quiet`, so **no
`tbits` value was recorded anywhere in the campaign artefacts** — not in the journal,
not in the per-cell stdout/stderr captures. This is recorded as not evaluable rather
than quietly dropped, and rather than substituting "all files ≥ 8 MB" for the
`tbits`-gated subset, which would be a different prediction. For what it is worth,
all six files ≥ 8 MB do exceed 2.0× (2.15×–2.46×), but whether they satisfy
`tbits ≥ 26` is unmeasured.

The adoption rule keys on the *median-speedup* condition, which is evaluable and
holds, so the gap does not block the decision.

## C-4 — memory, mechanism closure — **HOLDS**

> Predicts: F12 decode peak RSS ≤ 60% of full on CM2-won files ≥ 16 MB.

| file | RSS full | RSS f12 | ratio | verdict |
|---|---:|---:|---:|---|
| mozilla | 9.93 GiB | 4.55 GiB | 45.8% | within |
| samba | 9.73 GiB | 4.43 GiB | 45.5% | within |
| webster | 7.84 GiB | 3.68 GiB | 46.9% | within |
| nci | 6.96 GiB | 3.04 GiB | 43.7% | within |

All four land at 44–47%, comfortably inside the 60% ceiling and close to the
12+3-of-27-tables ≈ 56% the prereg derived — slightly *better* than predicted. The
working-set mechanism behind the above-map P-A speedups is closed: the tier's speed
comes from touching roughly half the table memory, and the RSS numbers say so
directly.

## Scorecard

| criterion | verdict |
|---|---|
| C-1 scope of effect | **FALSIFIED** (`ooffice`, nested CM2 under `MODE_BCJ`) |
| C-2 (a) density ceilings | **FALSIFIED** (exe: `mozilla` +7.53% vs +6%) |
| C-2 (b) lead-survival | **HOLDS** (81.2%–100% depending on scope; ≥80% under all) |
| C-2 (c) M8S database | **HOLDS** |
| C-3 median speedup | **HOLDS** (2.243× vs ≥1.5×) |
| C-3 `tbits` sub-clause | **NOT EVALUABLE** (`--quiet`; no `tbits` recorded) |
| C-4 memory | **HOLDS** (44–47% vs ≤60%) |

Two of four predictions falsified. The campaign was worth running.

## The adoption rule

The rule was pre-committed in the prereg, before any of these numbers existed:

> If C-2's lead-survival AND C-3's median-speedup conditions both hold: introduce a
> new preset `fast` = F12 (+M8S on database-classed inputs via the existing
> detector), leaving `max`/`balanced`/`web` semantics untouched.

| condition | required | measured | |
|---|---|---|---|
| C-2 lead-survival | ≥ 80% | 81.2% (narrowest scope) | ✅ |
| C-3 median speedup | ≥ 1.5× | 2.243× | ✅ |

### **The rule FIRES.**

**It fires even though C-1 and C-2(a) were falsified, and that is not a loophole —
it is the entire reason the rule was written down in advance.** The rule was never
"adopt if every prediction holds"; it was "adopt if the density lead survives and
the speed is real", because those two are the product question and the others are
mechanism questions. Declining to adopt now, on the strength of failures the rule
deliberately did not key on, would be exactly the post-hoc renegotiation
preregistration exists to prevent. The falsifications are recorded as failures, in
full, and they change the *mechanism story* — not the decision.

What the rule licenses, and nothing more:

- A **new** preset `fast` = F12, plus M8S on database-classed inputs via the
  existing detector.
- `max`, `balanced` and `web` semantics **untouched** — no existing user's archive
  changes silently.
- The preset is a **follow-up implementation PR with its own tests**, not part of
  this record.
- **No new DB metas for `fast`** from this campaign's runs. Per the prereg, metas
  are minted only after the preset exists in a release-lineage build.

### What a `fast` user is buying, stated plainly

Roughly **2.2× faster decode** and **~55% less decode memory**, for **+1.8% to +8.9%**
archive size on CM2-won files — and up to **+29%** on small binary inputs like
`kennedy.xls`. On image and RecordCM inputs (`mr`, `ptt5`, `x-ray`, `sao`) the
preset is a **no-op**: byte-identical archives, identical timings. The implementation
should not pretend otherwise, and the exe class breaching its own preregistered
ceiling (+7.5% `mozilla`, +8.8% `ooffice`) belongs in the user-facing description.

## Artefacts

| file | what |
|---|---|
| `journal.final.jsonl` | complete 294-line campaign journal, 48 cells, sha256 `ed844389…` |
| `journal.partial.jsonl` | the 22-cell partial the superseded revision adjudicated from |
| `adjudicate-final.py` | scores C-1..C-4 and the adoption rule from the journal alone |
| `preset-campaign.sh` | the runner as executed on `dev-ai` |
| `meta36.psv` | Phase C meta-36 snapshot used for ratios and ranks |

`adjudicate-final.py` reads only the journal, the manifest, `meta36.psv` and the
mode-byte table, and reproduces every number in this record. No figure here was
carried over by hand from the superseded revision.
