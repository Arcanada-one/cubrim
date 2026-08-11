# CUBR-RAILMAP-20260811 — preregistration: which rail dominates decode, per data class?

**Committed to `main` BEFORE measurement.**

## The question, and why it is the right next one

This series established two facts that only make sense together:

- **CM2 cannot reach the field at any effort** — best cases 0.323 / 0.634 / 3.373 MiB/s on
  `xml/max`, `dickens/max`, `dickens/web`.
- **geocm is the only measured route in** — on `x-ray/max`, the replay path is ~98–99% of decode and
  a perfected rail clears same-host ppmd by 15.3×.

Both rest on **four cells covering three data classes**: text, markup, and one image. The generalising
claim underneath them — *"the CM2 rail is hopeless, the geocm rail is not"* — is a claim about
**rails**, but every cell measured so far is a class where the rail assignment was already known.
Nothing establishes **which rail a given class actually lands on**, and that is the fact a rail
decision needs.

Silesia has classes this series has never profiled: **`sao` (32-bit float star catalogue)** and
**`osdb` (database dump)**. Neither is text, neither is an image. If both are CM2-dominated, the
"everything but images is hopeless" reading is confirmed. If either is geocm-dominated, the headroom
applies to more of the product surface than one image file, and the rail decision changes shape.

This is answerable now because the capability exists: a gate-passing profile method
(`CUBR-XRAY-ATTRIB-CLEAN`), a bucket rule validated against two published bounds
(`CUBR-SPEEDFLOOR-WEB`), and an interleaved gated throughput harness.

## Method (fixed before running)

- **Files**: `sao` (7,251,944 B) and `osdb` (10,085,684 B), `--preset max`, whole files.
- **Binary**: `8947ea9b…` (commit `3a13f486`) — the same binary every cell in this series used, so
  the bucket rule and prior figures apply unchanged.
- **Profile**: `perf record -F 25`, **12 instrumented runs pooled**, each paired with a plain decode
  in the same window. Perturbation = median of per-pair ratios, against the **≤1.05** gate. This is
  the configuration that passed at 1.00533 on x-ray; it is preregistered here, not selected after
  seeing results.
- **Bucketing**: symbols classified `cm2_*` / `geocm_*` / kernel / other exactly as the landed
  attribution does. Rail assignment = whichever family holds the larger share.
- **Bound**: for whichever family dominates, the combined outer bound is computed on the
  **shell-excluded** basis (`cm2_decode_shell` / `geocm_decode` removed), the basis the CM2 cells
  publish. Both bases reported where they differ.
- **Throughput**: cubrim and `bzip2 -9` decoded interleaved, 3 rounds, on each file — bzip2 as a
  same-host reference, since the cross-meta markers were shown not to transfer
  (`CUBR-SAMEHOST-FIELD-RESULTS`). Ratios logged beside speed.
- **Gates**: `cmp` **and** sha256 before any timing row; a VOID aborts that cell.
- `systemd-run --scope MemoryMax=64G MemorySwapMax=0`, `taskset -c 0-15`, pin not widened.
  `kernel.perf_event_paranoid` 4 → 1 for the run, **restored to 4** afterwards.
- Per-file only. Two files stay two files; no class-level generalisation is drawn from one file each,
  and the report will say so.

## Predictions (falsifiable)

- **P1 — the method transfers.** Perturbation ≤ **1.05** on both files at `-F 25`. *Refuted* above,
  on either.
- **P2 — the rail split is class-dependent, not image-versus-everything.** **At least one** of `sao`
  / `osdb` is **geocm-dominated** (geocm share > cm2 share). *Refuted* if both are CM2-dominated —
  which would confirm the narrower reading that only images escape the CM2 floor.
- **P3 — the CM2 floor binds wherever CM2 dominates.** For any CM2-dominated file here, its
  shell-excluded bound × measured throughput stays **below same-host `bzip2 -9`** on that same file.
  *Refuted* if a CM2-dominated file's perfect-rail best case reaches its own same-host bzip2.
- **P4 — decode concentration is high on every rail.** The dominant family holds ≥ **90%** on both
  files, as it did on all four prior cells (90.66–98.99%). *Refuted* below 90% on either — which
  would mean some classes spread decode across both rails and neither bound is meaningful there.

P2 is the one that changes what the programme should do: it decides whether geocm headroom is a
one-file curiosity or a property of a whole class of operating points.

## Boundaries

Read-only profiling plus decode timing. No encoder, wire format, preset, counter or `decode()`
change; no candidate built, no lever selected — selection is NEW-24's, PROGRAM's lane. No database
write, no hypothesis row, no API, site or social action.
