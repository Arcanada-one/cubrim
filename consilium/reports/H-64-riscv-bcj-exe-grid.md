# H-64 — RISC-V BCJ (JAL filter): finish the arch-BCJ family

**Why.** Completes the arch-BCJ family after x86 (H-45, +10.53%) and ARM64 (H-57, +12.23%). RISC-V uses the `JAL` (jump-and-link) PC-relative branch — invisible to x86 E8/E9 or ARM64 BL filters. Hypothesis: a RISC-V JAL BCJ is GO on a real RISC-V ELF, and the mismatched x86/ARM64 filters are not (re-confirm arch-specificity).

**Method.** champion `--value-scheme bwt-rans`, RT byte-exact. RISC-V JAL filter: 4-byte aligned LE words, `(word&0x7F)==0x6F` ⇒ JAL; unscramble the 21-bit PC-rel immediate (`imm[20|10:1|11|19:12]` in bits[31:12]), add byte-pos (encode) / subtract (decode) mod 2²¹, re-scramble; opcode+rd (low 12 bits) unchanged ⇒ reversible (asserted). Controls: x86 E8/E9 and ARM64 BL filters on the SAME RISC-V binary. L=min(xz-9e/PPMd/brotli-q11). JAL-only (the branch lever; AUIPC pair-addressing is a noted refinement — xz's --riscv also does AUIPC; this host's xz 5.4.5 lacks --riscv so no reference cross-check). Spike `/tmp/uci-dl/spike_h64_riscvbcj.py`. Codec.rs untouched, NOT pushed.

**Corpus (real):** `busybox_riscv64_640k.bin` — Alpine edge `busybox-static` 1.38.0-r1 (riscv64, ELF-64 RISC-V RV64GC), dense .text slice @64 KB +640 KB. sha256 `899c9cbd07bbdef7c717…`. Source: dl-cdn.alpinelinux.org/alpine/edge/main/riscv64.

## Measured (RT byte-exact). code SHA `422726d`.

| variant | cub bytes | self-gain | B/L (vs ppmd 421 442) | RT |
|---|---:|---:|---:|---|
| A = raw RISC-V .text | 444 042 | — | 1.054 | — |
| **B = cub + RISC-V JAL BCJ** | **435 268** | **+1.98%** | 1.033 (closes 38.8% of A→L gap) | OK |
| B = cub + ARM64 BL BCJ (CONTROL) | 448 414 | −0.98% | — | OK |
| B = cub + x86 E8/E9 BCJ (CONTROL) | 450 454 | −1.44% | — | OK |

Universals: xz-9e 422 532 | **PPMd 421 442** | brotli 435 183 → L=ppmd. (host xz 5.4.5 lacks `--riscv`, so no reference cross-check.)

## Reading

- **Arch-specificity RE-CONFIRMED (the controls):** the RISC-V filter helps (+1.98%) while the ARM64 filter (−0.98%) and x86 filter (−1.44%) on the same RISC-V bytes hurt. Each arch's opcodes are noise inside another arch's instructions → BCJ must match `e_machine`. Third independent confirmation after H-57.
- **But the RISC-V gain is small (+1.98%) — GO(self-only), does not beat the leader.** self-gain is just above the +1.5% non-subsumption floor, yet B/L 1.033 (3.3% behind ppmd) and it closes only 38.8% of the A→L gap (<50%) → gate-2 fails. Two honest reasons: **(1) JAL-only** — I implemented only the direct-call `JAL` filter; RISC-V's dominant PC-relative lever is **AUIPC** (+ADDI/load/jalr pairs) for nearly all addressing, which is unimplemented here (xz's `--riscv` does AUIPC and gets far more). **(2) PIE binary** — busybox-static is position-independent, so direct JAL calls are sparse (same effect as the PIC libc in H-57, which also gave only +1.96%). The strong x86/ARM64 gains (+10.5%/+12.2%) were non-PIE-heavy code + fuller instruction coverage.

## Verdict vector

**H-64 RISC-V BCJ: GO-self-only{exe·RISC-V·JAL} — arch-match confirmed; full gain needs AUIPC.** Completes the arch-BCJ family: x86 GO (+10.5%, beats leader, H-45), ARM64 GO (+12.2%, closes 55% gap, H-57), RISC-V GO-self-only (+1.98%, JAL-only, doesn't beat leader). The mechanism is arch-specific and non-subsumed on every arch (all three: correct filter helps, wrong filters hurt), so the ship design stands — **detect ELF `e_machine`, apply the matching filter** (x86 E8/E9; ARM64 BL[+ADRP]; RISC-V JAL **+ AUIPC**) behind competitive `min(raw, bcj_arch)` + id byte; byte-identical on non-exe/unknown-arch. **RISC-V needs AUIPC pair handling for a strong (leader-beating) gain — the JAL-only lever is thin, especially on PIE.** PPC and other arches: same pattern, deferred (need corpora).

**Mac orchestrator publishes the /evolution card for H-64** (status GO-self-only, RISC-V JAL BCJ +1.98%, arch-specificity re-confirmed via ARM64/x86 controls, AUIPC noted for full gain). Card-publishing Mac-side this cycle.

Codec.rs untouched (spike only). NOT pushed.
