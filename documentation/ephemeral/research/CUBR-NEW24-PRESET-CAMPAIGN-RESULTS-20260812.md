# NEW-24 preset campaign — results and F12 adoption adjudication

**State: IN PROGRESS.** The campaign is running detached on `dev-ai` and this record
is updated as cells land. Prereg: `CUBR-NEW24-PRESET-CAMPAIGN-20260811.md` (main
`563b94e`); the runner logs `"prereg":"563b94e"` in its `run_start` line, so the
design under which these numbers were produced is pinned in the journal itself.

Nothing below is a corpus-wide average — the prereg forbids them. Every figure is
per file. Canterbury files are measured and reported but excluded from class-level
claims.

## Campaign status

Started 2026-08-11T19:53Z, still running as of this writing, on the 16 h budget.
It **survived the 23:45Z fleet kill** because it was launched under
`setsid nohup`; the journal shows uninterrupted cell completions across that
boundary (`sao/f12` 01:25Z, `webster/full` 02:10Z).

| | |
|---|---|
| cells complete | 22 |
| files with both arms | 10 of 24 |
| voids / gate failures | **0** |
| remaining | `x-ray` (running), `xml`, `enwik8`, 11 canterbury |

Every `full`-arm archive passed the canonical identity gate against the Phase C
journal canonicals, and every decode in every cell passed round-trip (`cmp` +
sha256) before its timing was read. Zero voids means no cell has yet had to be
reported failed or substituted.

## Per-file results (both sides of the trade)

`ident` = the F12-forced archive is byte-identical to the control. `dens%` = F12
archive bytes vs control. Decode figures are the median of three reps.

| file | class | ident | dens% | dec full (s) | dec f12 (s) | speedup | RSS full | RSS f12 | RSS% |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| mr | image | **YES** | +0.00 | 6.6 | 6.6 | 1.00× | 88 M | 88 M | 100% |
| sao | binary | **YES** | +0.00 | 22.6 | 23.1 | 0.98× | 95 M | 94 M | 99% |
| dickens | text | no | +3.58 | 101.0 | 44.6 | 2.26× | 7151 M | 3188 M | 45% |
| reymont | text | no | +4.08 | 59.8 | 25.6 | 2.34× | 4563 M | 1946 M | 43% |
| samba | code | no | +1.82 | 178.9 | 80.9 | 2.21× | 9962 M | 4536 M | 46% |
| mozilla | exe | no | **+7.53** | 419.9 | 195.0 | 2.15× | 10166 M | 4654 M | 46% |
| ooffice | exe | no | **+8.79** | 57.1 | 26.3 | 2.17× | 5242 M | 2296 M | 44% |
| nci | database | no | +2.68 | 229.6 | 103.5 | 2.22× | 7127 M | 3116 M | 44% |
| osdb | database | no | +8.85 | 109.3 | 47.6 | 2.30× | 9982 M | 4572 M | 46% |
| webster | text | no | +3.31 | 391.6 | 158.7 | 2.47× | 8224 M | 3859 M | 47% |

### A cross-check the prereg did not ask for, and what it caught

The classification above uses archive-sha difference as the test for "did the tier
touch this file". That is a proxy, so it was checked against the wire itself by
reading byte 5 (the mode byte) of every retained control archive — free, no compute
on the stand mid-campaign:

| mode | meaning | files |
|---|---|---|
| 16 | `MODE_CM2` | dickens, mozilla, nci, osdb, reymont, samba, webster |
| 17 | `MODE_GEOCM` | mr |
| 13 | `MODE_RECORDCM` | sao |
| 8 | `MODE_BCJ` | ooffice |

The proxy agrees with the wire on all nine files, and the two apparent oddities
both resolve in its favour: `mr` and `sao` are byte-identical because **GeoCM and
RecordCM won there, not CM2**, which is precisely C-1's stated mechanism; and
`ooffice` is `MODE_BCJ` yet still moved, because the BCJ container **nests a
MODE_CM2 blob**, so the tier reaches it. Worth recording because a naive reading of
the mode byte alone would have mis-scored `ooffice` as CM2-untouched.

## C-1 — scope of effect

> Predicts: on files whose meta-36 winner is not CM2, the F12 archive is
> byte-identical and decode wall is within ±10%.

| file | byte-identical | decode deviation | verdict |
|---|---|---:|---|
| mr | YES | 0.2% | **holds** |
| sao | YES | 2.4% | **holds** |
| x-ray | — | — | not yet measured |
| ptt5 | — | — | not yet measured |
| kennedy.xls | — | — | not yet measured |

Holds on both files measured so far, and the mode-byte check confirms the
mechanism rather than just the outcome.

## C-2 — density

**Clause (a), per-class worsening ceilings — TWO FALSIFICATIONS, both in the exe class.**

| file | class | dens% | ceiling | verdict |
|---|---|---:|---:|---|
| dickens | text | +3.58 | +5% | within |
| reymont | text | +4.08 | +5% | within |
| samba | code | +1.82 | +5% | within |
| **mozilla** | **exe** | **+7.53** | **+6%** | **EXCEEDS** |
| **ooffice** | **exe** | **+8.79** | **+6%** | **EXCEEDS** |
| nci | database | +2.68 | +10% | within |
| osdb | database | +8.85 | +10% | within |
| nci / M8S | database | +3.21 | +8% | within |
| osdb / M8S | database | +6.50 | +8% | within |

Both exe files measured so far breach the +6% ceiling. This is a falsified
prediction and is recorded as one; see § *The adoption rule* for why it does not by
itself decide the product question, and why that is not a post-hoc rescue.

**Clause (b), lead-survival — the clause the adoption rule keys on.** cubrim holds
meta-36 rank-1 on 22 of 24 files (not `nci`, rank 3; not `xargs.1`, rank 2). A led
file survives when the F12 ratio still beats every other archiver.

| file | class | dens% | r_full | r_f12 | runner-up | verdict |
|---|---|---:|---:|---:|---|---|
| sao | binary | +0.00 | 0.52538 | 0.52538 | 7z 0.60865 | holds |
| samba | code | +1.82 | 0.14528 | 0.14792 | xz 0.17307 | holds |
| osdb | database | +8.85 | 0.21694 | **0.23613** | **ppmd 0.23664** | **holds by 0.2%** |
| mozilla | exe | +7.53 | 0.23912 | **0.25712** | **7z 0.26053** | **holds by 1.3%** |
| ooffice | exe | +8.79 | 0.28664 | 0.31184 | rar 0.37425 | holds |
| mr | image | +0.00 | 0.20776 | 0.20776 | ppmd 0.23079 | holds |
| dickens | text | +3.58 | 0.20726 | 0.21468 | ppmd 0.22534 | holds |
| reymont | text | +4.08 | 0.13884 | 0.14450 | ppmd 0.17224 | holds |
| webster | text | +3.31 | 0.13974 | 0.14437 | ppmd 0.15785 | holds |

**9 of 9 measured led-files survive (100%).** But 13 of the 22 led files are not yet
measured, so the corpus figure is bounded at worst 40.9% / best 100.0% against an
80% bar — **undecided**, and it must stay undecided rather than be reported as
"100% so far, therefore passing".

Two survivals are thin and should be read as such: `osdb` clears ppmd by **0.00051
absolute (0.2% relative)** and `mozilla` clears 7z by 1.3%. A lead that survives by
0.2% is a lead that a different host, a different ppmd build, or one more density
point would erase. The 80% bar has margin; those two individual cells do not.

## C-3 — speed

> Predicts: median F12 decode speedup on CM2-won files ≥ 1.5×; ≥ 2.0× on files
> ≥ 8 MB with `tbits ≥ 26`.

nci 2.22×, osdb 2.30×, mozilla 2.15×, ooffice 2.17×, samba 2.21×, dickens 2.26×,
reymont 2.34×, webster 2.47×.

**Median 2.22× against a 1.5× bar — holds, and not marginally.** The spread is
remarkably tight (2.15–2.47× across four classes and a 6–51 MB size range), which is
itself evidence the effect is structural rather than file-specific. The ≥ 8 MB /
`tbits ≥ 26` sub-clause also holds on every qualifying file measured so far.

## C-4 — memory, mechanism closure

> Predicts: F12 decode peak RSS ≤ 60% of full on CM2-won files ≥ 16 MB.

43.7% (nci), 45.8% (osdb), 45.8% (mozilla), 43.8% (ooffice), 45.5% (samba),
44.6% (dickens), 42.6% (reymont), 46.9% (webster).

**Holds on every CM2-won file, with wide margin — 42.6–46.9% against a 60% ceiling.**
The prereg predicted ≈56% from table arithmetic (12+3 of 27 tables); the measured
value is consistently *better* than that estimate, clustering near 45%. The
mechanism claim behind the above-map P-A speedups is closed: the working set really
does shrink by the predicted kind of factor, and the residual is smaller than the
table count alone suggests.

## The `nci` M8S cell needs a confirmation before it is quoted

`nci/m8s` reports a **831× decode speedup** (229.6 s → 0.277 s) at **70 MB RSS**, on
a 33.5 MB file, with round-trip passing and archive bytes only +3.21%.

That is not credible as "CM2 with 8 small tables": no context-mixing configuration
decodes 33.5 MB in 0.277 s, and 70 MB of RSS is barely more than the output buffer.
The coherent reading is that **M8S weakened the CM2 candidate enough that CM2 lost
the competitive pick entirely**, and a cheap backend won instead — which is
plausible on `nci` specifically, where cubrim is only rank 3 and xz (0.0432) and
brotli (0.0453) already sit beside cubrim's 0.0463, so a fast rail giving up just
3.21% is unsurprising.

**This is inference, not measurement.** The M8S archive was deleted by the runner
(`[ "$arm" != full ] && rm -f "$cub"`), so its mode byte cannot be read from what
survives. Confirming it costs one `nci` re-encode under `CUBR_CM2_TIER=m8s` and one
`od -An -tu1 -j5 -N1` — deferred deliberately until the campaign finishes, because
the runner's quiet gate is `load < 8.0` and running an encode now could void a live
cell. Until that check runs, the 831× figure is reported but **not** claimed as an
M8S tier speedup.

## The adoption rule

The prereg's rule is deliberately narrow, and it is quoted here verbatim before
being applied:

> If C-2's lead-survival AND C-3's median-speedup conditions both hold: introduce a
> new preset `fast` … If either fails: no preset change.

It names **two** conditions: lead-survival (C-2 clause b) and median speedup (C-3).
It does **not** name the per-class density ceilings (C-2 clause a). So on a literal
reading the mozilla/ooffice exceedances do not block adoption.

That reading is adopted, and the reason it is not a post-hoc rescue is that the
distinction was designed in: `fast` is a **new** preset, and the prereg says in the
same sentence that `max`/`balanced`/`web` semantics are untouched so "existing
users' archives never change silently". A density ceiling is the right gate for
changing a preset people already use; it is not the right gate for offering a new
operating point that nobody is opted into. Pre-committing the rule is worth nothing
if it is reinterpreted the moment a clause it did not cite comes out red.

The exceedance is therefore **recorded as a falsified prediction**, not discarded:
the F12 tier costs more density on executables than the tier-ladder data predicted,
and any future proposal to make F12 the default — as opposed to an opt-in preset —
inherits that finding as a blocker rather than a footnote.

### Current standing of the rule

| condition | status |
|---|---|
| C-2 lead-survival ≥ 80% | **UNDECIDED** — 8/8 measured, 14 of 22 led files outstanding |
| C-3 median speedup ≥ 1.5× | **HOLDS** — 2.22× |

**No adoption decision is recorded yet.** One of its two inputs is still open, and
the prereg's whole purpose is that the decision follows the rule rather than the
early returns. The remaining files include `enwik8`, which has never been run at
this scale in any prior Cubrim campaign, and `x-ray` / `ptt5` / `kennedy.xls`, which
carry the rest of C-1.

## Stand contention, observed live: the quiet gate held, but only by luck

At 2026-08-12T02:27Z, mid-`webster/f12`, `dev-ai`'s load average went from 1.34 to
**31.01** in under three minutes. Cause, identified from `ps`: the CUBR-0096
sticky-selection lane started `/root/cubr0096/ooffice-decide.sh`, a
baseline-versus-candidate encode pair at `CUBR_THREADS=64`, taking 42 cores.

Two lanes, one stand, and **no reservation mechanism of any kind** — no lock file,
no runbook convention, nothing on the box that would make either lane aware of the
other. Both were behaving correctly by their own lights.

**Why nothing was killed, and why no cell was voided.** The runner's `quiet()` gate
polls `load < 8.0` once a minute for up to 90 minutes before voiding a cell. The
colliding job is a short paired encode on a 6 MB file at 64 threads — minutes, not
hours. The gate absorbs it. Intervening would have meant destroying another lane's
in-flight measurement to protect against a stall the design already handles.

**Why the other lane's result is not damaged either.** Reading
`ooffice-decide.sh` before assuming: its verdict is a **sha256 comparison** of the
baseline and sticky archives — it asks whether forcing one value-stream winner
changes the output bytes at all. Byte-identity is load-independent. The script also
records `WALL`/`RSS`, and *those* figures are contaminated by this campaign's
concurrent `webster` encode and should not be quoted; the byte comparison that
actually decides its question is untouched.

**The finding is that this was luck, not design.** The same collision with a job of
campaign scale — the 4-hour `enwik8` cell, say — would have blown through the
90-minute budget and voided cells that then get "reported failed, never
substituted" per the stop rules. The remedy is small and worth having before the
next campaign: an advisory lock file under a known path that every stand script
takes and honours, plus the lane name and expected duration written into it, so a
second lane can see what it is about to walk into. Recorded here rather than filed
as its own task because it is a campaign-integrity property, and this is the record
the next campaign author reads.

FINDINGS F6 already documented that this encoder oversubscribes the machine and
that the damage shows up as collateral. This is the multi-lane version of the same
problem, and it is the second time it has cost something.


## Two corrections to this record and its tooling

**The other lane's collision is closed, and it published its own result.** The
CUBR-0096 `ooffice-decide.sh` run completed while this campaign continued: `base`
and `sticky` archives are byte-identical (`f4709c0a…`, 1,763,460 B), so forcing one
value-stream winner everywhere changes nothing in the output on that file. That
sha is also exactly this campaign's canonical `ooffice` archive, an unplanned
cross-check that both lanes are encoding the same thing. Their write-up is
`research(CUBR-0096): the ooffice tension is resolved` (PR #171). The claim made
above — that their byte comparison was unaffected by the load while their WALL/RSS
lines were — stands as stated, and is now settled rather than predicted.

**`adjudicate.py` hand-typed the file classes and got one wrong.** Its first version
carried its own `CLASS` dict, in which `samba` was `exe`; meta-36 says `code`. The
published tables above were right because they were written against the dataset, but
the script that will generate every future update was not. It now loads classes from
`meta36.psv` and has no hand-typed table at all. The wrong class would have applied a
+6% ceiling where +5% belongs — no verdict changes at `samba`'s +1.82%, but the next
file it mis-classified might not be so forgiving. A hand-typed table beside a
machine-readable one drifts from it; that is what happened here, and the fix is to
delete the table rather than correct it.
