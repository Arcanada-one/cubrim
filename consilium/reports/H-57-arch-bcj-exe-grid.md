# H-57 — arch-specific BCJ for exe: ARM64 BL filter (per-type grid, exe sub-types)

**Premise.** H-45 BCJ (x86 E8/E9) flipped exe→GO but is x86-only. Modern executables are largely ARM64; their PC-relative branches use the ARM64 `BL` encoding, invisible to an x86 E8/E9 filter. Hypothesis: an ARM64 BL BCJ filter is GO on real ARM64 ELF, and the x86 filter is NOT (arch-specificity).

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. ARM64 BL filter: 4-byte aligned LE words, `(instr>>26)==0x25` ⇒ BL; the 26-bit imm gets +word-pc (encode) / −word-pc (decode) mod 2²⁶; opcode top-6 bits unchanged ⇒ reversible (asserted). Cells: A=cub(raw), B=cub(ARM64-BCJ), **control** B=cub(x86-BCJ) on the SAME ARM64 binary (wrong arch → should not help). L=min(xz-9e/PPMd/brotli-q11). Cross-check: `xz` vs `xz --arm64` (confirms the lever exists in a reference filter). BL-only (the call lever; ADRP is a noted refinement). Spike `/tmp/uci-dl/spike_h57_arm64bcj.py`. Codec.rs untouched, NOT pushed.

**Corpus (real):** `rg_arm64_640k.bin` — ripgrep 14.1.1 `rg` (aarch64-unknown-linux-gnu, GitHub release, ELF-64 ARM aarch64 stripped), dense .text slice @128 KB +640 KB. Provenance: github.com/BurntSushi/ripgrep/releases/14.1.1.

## Measured (RT byte-exact). code SHA `422726d` (codec untouched).

| variant | cub bytes | self-gain | B/L (vs plain xz 72 476) | RT |
|---|---:|---:|---:|---|
| A = raw ARM64 .text | 92 994 | — | — | — |
| **B = cub + ARM64-BL BCJ** | **81 622** | **+12.23%** | 1.126 (closes **55%** of A→L gap) | OK |
| B = cub + x86-E8/E9 BCJ (CONTROL) | 110 885 | **−19.24%** | — | OK |

Universals on the raw ARM64 .text: xz-9e 72 476 | **xz --arm64 59 892** | PPMd 118 230 | brotli 82 238. xz BCJ cross-check: plain xz → xz --arm64 = **+17.36%** (reference filter confirms the lever; xz's filter also does ADRP + masking, hence larger than the BL-only +12.23% here).

## Reading

- **GO(exe·ARM64): the ARM64-BL filter is a real, large, non-subsumed win** — self-gain +12.23% (≫ +1.5% floor), comparable to x86's ooffice +10.53% (H-45). It closes 55% of the gap to plain xz (gate-2 met).
- **Arch-specificity proven decisively (the control).** Applying the **x86** E8/E9 filter to ARM64 code is **catastrophic (−19.24%)** — x86 opcode bytes are effectively random inside ARM64 instructions, so it scrambles the stream. The ARM64 filter on the same bytes is +12.23%. ⇒ BCJ MUST be matched to the binary's architecture (detect ELF `e_machine`); a single x86 filter is actively harmful on non-x86 exes.
- **Honest scope:** cubrim+ARM64-BCJ (81 622) does NOT beat **xz --arm64** (59 892) — the arch-tuned reference universal. The residual is cubrim's backend (bwt-rans) being weaker than LZMA2 on the filtered match stream — the SAME backend deficit seen on text/code, NOT a transform failure. Against default-flag universals (the H-45 convention: plain xz/ppmd/brotli) it clears gate-2; the transform itself is validated.

## Verdict vector

**H-57 arch-BCJ: GO{exe·ARM64} · (control) NO-GO{x86-filter-on-ARM64} — arch-match is mandatory.** Generalises H-45's exe GO across architectures: BCJ is GO per-arch when the filter matches `e_machine` (x86 H-45 +10.53%; ARM64 here +12.23%), and HARMFUL when mismatched (−19.24%). Ship plan: detect ELF `e_machine` (x86/x86-64 → E8/E9; AArch64 → BL[+ADRP]; RISC-V/PPC → their variants) and apply the matching filter behind competitive `min(raw, bcj_arch)` + id byte; byte-identical on non-exe / unknown-arch. ADRP handling would close more of the xz --arm64 gap (BL-only captures +12.23% of the reference +17.36%). RISC-V/PPC: same pattern, deferred (need real corpora).

**Mac orchestrator publishes the /evolution card for H-57** (title, mechanism, measured ARM64 +12.23% / arch-control −19.24% / status GO·arch-matched). Card-publishing is Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
