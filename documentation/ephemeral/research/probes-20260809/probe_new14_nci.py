#!/usr/bin/env python3
"""PROBE NEW-14 (nci residual): simulate cm2.rs m1/m2/m3 direct-mapped match
tables on nci prefixes and measure collision/eviction stress vs prefix size.

Replicates cm2.rs exactly:
  hash: h = 0xABCDEF01 ^ minlen; for j in 0..minlen: h = h*0x85EBCA77 + buf[t-j];
        h ^= h >> 13;  slot = h & ((1<<tbits)-1)
  table[slot] = t at EVERY position t >= minlen-1 (Match::end inserts always);
  lookup at t reads table[slot] BEFORE the write -> candidate = previous
  position with the same slot value. No gram verification at lookup.

Metrics per (prefix, model):
  - occupancy (distinct slots / 2^tbits), distinct grams
  - repeat positions (gram seen before): retrieval rate = candidate's gram ==
    current gram (else the repeat is LOST to a collision-eviction)
  - novel positions: false-candidate rate (table offers a wrong gram)
  - retrieval rate bucketed by distance to nearest previous TRUE occurrence
  - repeat structure: nearest-prev-occurrence distance distribution (12-gram
    exact; 16-gram via same method for NEW-06 comparability)

Per-position stats (encoder looks up only when len==0; stated in notes).
"""
import sys
import numpy as np

MUL = np.uint32(0x85EBCA77)
FP_MUL = np.uint64(0x100000001B3)  # FNV-ish odd multiplier for 64-bit gram id


def tbits_for(n: int) -> int:
    ceil_log2 = (max(n, 2) - 1).bit_length()
    return min(max(ceil_log2 + 3, 18), 27)


def slots_and_fp(buf: np.ndarray, minlen: int, tbits: int):
    """slot and 64-bit gram fingerprint for every t in [minlen-1, len)."""
    n = len(buf)
    t0 = minlen - 1
    m = n - t0
    h = np.full(m, np.uint32(0xABCDEF01) ^ np.uint32(minlen), dtype=np.uint32)
    fp = np.zeros(m, dtype=np.uint64)
    with np.errstate(over="ignore"):
        for j in range(minlen):
            b = buf[t0 - j : n - j]  # buf[t-j] for t in [t0, n)
            h = h * MUL + b.astype(np.uint32)
            h ^= h >> np.uint32(13)
            fp = fp * FP_MUL + b.astype(np.uint64)
    mask = np.uint32((1 << tbits) - 1)
    return (h & mask), fp


def prev_same(vals: np.ndarray) -> np.ndarray:
    """prev[i] = largest j<i with vals[j]==vals[i], else -1 (indices into vals)."""
    order = np.argsort(vals, kind="stable")
    sv = vals[order]
    same = np.empty(len(vals), dtype=bool)
    same[0] = False
    same[1:] = sv[1:] == sv[:-1]
    prev = np.full(len(vals), -1, dtype=np.int64)
    idx = np.flatnonzero(same)
    prev[order[idx]] = order[idx - 1]
    return prev


DIST_BUCKETS = [(0, 64 << 10, "<=64K"), (64 << 10, 1 << 20, "64K-1M"),
                (1 << 20, 4 << 20, "1-4M"), (4 << 20, 8 << 20, "4-8M"),
                (8 << 20, 16 << 20, "8-16M"), (16 << 20, 1 << 62, ">16M")]


def analyze(buf: np.ndarray, minlen: int, tbits: int, tag: str):
    slots, fp = slots_and_fp(buf, minlen, tbits)
    m = len(slots)
    prev_slot = prev_same(slots)          # what the table would return
    prev_true = prev_same(fp)             # nearest previous true occurrence
    have_cand = prev_slot >= 0
    is_repeat = prev_true >= 0
    # candidate correctness: candidate's gram equals current gram
    cand_ok = np.zeros(m, dtype=bool)
    cand_idx = np.flatnonzero(have_cand)
    cand_ok[cand_idx] = fp[prev_slot[cand_idx]] == fp[cand_idx]
    n_rep = int(is_repeat.sum())
    n_nov = m - n_rep
    retrieved = cand_ok & is_repeat
    lost = is_repeat & ~cand_ok
    false_on_novel = have_cand & ~is_repeat  # novel gram but table offers something
    occ = len(np.unique(slots))
    n_grams = len(np.unique(fp))
    print(f"[{tag}] minlen={minlen} tbits={tbits} positions={m}")
    print(f"  distinct grams={n_grams}  slot-occupancy={occ}/{1<<tbits}"
          f" ({occ/(1<<tbits):.4f})  gram/slot pressure={n_grams/(1<<tbits):.4f}")
    print(f"  repeat positions={n_rep} ({n_rep/m:.4%})  novel={n_nov}")
    if n_rep:
        print(f"  RETRIEVAL rate (repeat & candidate correct): {retrieved.sum()/n_rep:.4%}")
        print(f"  LOST-to-collision rate among repeats:        {lost.sum()/n_rep:.4%}")
    if n_nov:
        print(f"  FALSE-candidate rate among novel grams:      {false_on_novel.sum()/n_nov:.4%}")
    print(f"  overall wrong-candidate rate (all positions):  {(have_cand & ~cand_ok).sum()/m:.4%}")
    # retrieval vs true-distance buckets
    d = np.flatnonzero(is_repeat)
    dist = d - prev_true[d]
    ok = cand_ok[d]
    parts = []
    for lo, hi, name in DIST_BUCKETS:
        sel = (dist > lo) & (dist <= hi) if lo else (dist <= hi)
        c = int(sel.sum())
        parts.append(f"{name}: n={c}" + (f" surv={ok[sel].sum()/c:.3%}" if c else ""))
    print("  survival by true-distance: " + " | ".join(parts))
    if n_rep:
        print(f"  mean true-distance: retrieved={dist[ok].mean():,.0f}"
              + (f"  lost={dist[~ok].mean():,.0f}" if lost.sum() else ""))
    sys.stdout.flush()
    del slots, fp, prev_slot, prev_true, cand_ok
    return


def repeat_structure(buf: np.ndarray, gram: int, tag: str):
    """Nearest-previous-occurrence distance distribution for exact grams."""
    _, fp = slots_and_fp(buf, gram, 18)  # slots unused
    prev_true = prev_same(fp)
    m = len(fp)
    d = np.flatnonzero(prev_true >= 0)
    dist = d - prev_true[d]
    print(f"[{tag}] {gram}-gram repeat structure: positions={m} repeats={len(d)/m:.4%}")
    for lim, name in [(64 << 10, ">64K"), (1 << 20, ">1M"), (4 << 20, ">4M"),
                      (8 << 20, ">8M"), (16 << 20, ">16M")]:
        frac = (dist > lim).sum() / m
        print(f"    nearest-prev beyond {name}: {frac:.4%} of positions")
    sys.stdout.flush()
    del fp, prev_true


def main():
    path = sys.argv[1]
    buf = np.fromfile(path, dtype=np.uint8)
    full = len(buf)
    print(f"file={path} len={full}")
    prefixes = [4 << 20, 8 << 20, 16 << 20, full]
    for p in prefixes:
        sub = buf[:p]
        tb = tbits_for(p)
        tag = f"{p/(1<<20):.1f}MB"
        for minlen in (3, 6, 12):
            analyze(sub, minlen, tb, tag)
    # counterfactual: whole file at uncapped tbits=28 (what TBITS_MAX blocks)
    for minlen in (3, 6, 12):
        analyze(buf, minlen, 28, "FULL-tbits28-counterfactual")
    # repeat structure, m3 12-gram exact + 16-gram (NEW-06 comparability)
    repeat_structure(buf, 12, "FULL")
    repeat_structure(buf, 16, "FULL")


if __name__ == "__main__":
    main()
