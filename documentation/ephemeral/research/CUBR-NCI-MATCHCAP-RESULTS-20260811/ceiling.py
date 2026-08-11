#!/usr/bin/env python3
"""Regenerate every ceiling, bound and prediction verdict in
CUBR-NCI-MATCHCAP-RESULTS-20260811.md directly from the probe output.

Nothing in the report is hand-typed arithmetic: parse nci-probe.out, apply the
ceiling model fixed in the preregistration, print the tables.

Model (preregistered, both bounds reported because the NEW-06 notes state a
decoder-branch charge that their own published numbers omit):
    optimistic     : gain_bpb = rec_cov * (c - f)                 <- NEW-06's published arithmetic
    branch-honest  : gain_bpb = rec_cov * (c - f) - H2(rec_cov)   <- NEW-06's stated formula
Eviction: p_survive(d) = exp(-d / 2**tbits); recoverable share of a bucket is
(1 - survive) for a perfect model and (survive_30 - survive_27) for TBITS_MAX 27->30.
"""
import math, os, re, sys

N_BYTES = 33553445
CUBRIM_RATIO, XZ_RATIO = 0.046335, 0.043193
C = 8 * CUBRIM_RATIO          # CM2 cost on nci, bits/byte
F = 0.10                      # NEW-06's optimistic per-covered-byte residual charge
TBITS = 27                    # clamp(ceil(log2 33553445)+3, 18, 27)
GAP_B = round((CUBRIM_RATIO - XZ_RATIO) * N_BYTES)

BUCKET_EDGES = {              # label -> (lo, hi) in bytes, matching probe_longrange.py
    "<=64K":  (1, 64 << 10),
    "64K-1M": (64 << 10, 1 << 20),
    "1M-8M":  (1 << 20, 8 << 20),
    "8M-16M": (8 << 20, 16 << 20),
    ">16M":   (16 << 20, N_BYTES),
}
ORDER = ["<=64K", "64K-1M", "1M-8M", "8M-16M", ">16M"]


def h2(p):
    return 0.0 if p <= 0 or p >= 1 else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def survive(d, tbits):
    return math.exp(-d / 2 ** tbits)


def parse(path):
    """Pull (coverage-fraction, mean-ext-len) per bucket out of the raw probe output."""
    pat = re.compile(r"PROBE bucket\s+(\S+):\s+anchors\s+(\d+)\s+frac\s+([\d.]+)%\s+mean-ext-len\s+([\d.]+)")
    out = {}
    for line in open(path):
        m = pat.search(line)
        if m:
            out[m.group(1)] = (float(m.group(3)) / 100.0, float(m.group(4)))
    missing = [b for b in ORDER if b not in out]
    if missing:
        sys.exit(f"probe output missing buckets: {missing}")
    return out


def recoverable(buckets, weighted=False, factor=1.0, lever="ideal"):
    base_ml = buckets["<=64K"][1]
    total = 0.0
    for label in ORDER:
        cov, ml = buckets[label]
        lo, hi = BUCKET_EDGES[label]
        d = math.sqrt(max(lo, 1) * hi)              # representative distance: geometric mean
        w = (ml / base_ml * factor) if weighted else 1.0
        s27 = survive(d, TBITS)
        share = (1 - s27) if lever == "ideal" else (survive(d, 30) - s27)
        total += cov * w * share
    return total


def bounds(rec):
    opt = rec * (C - F)
    return opt, opt - h2(rec)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    buckets = parse(os.path.join(here, "nci-probe.out"))

    print(f"nci: {N_BYTES:,} B, tbits={TBITS} ({2**TBITS:,} slots = "
          f"{2**TBITS/N_BYTES:.2f}x more slots than positions)")
    print(f"c = {C:.5f} b/B, f = {F}, margin c-f = {C-F:.5f} b/B, gap = {GAP_B:,} B\n")

    print(f"{'bucket':>8} {'cov':>9} {'mean-ext':>9} {'d_rep':>9} {'surv27':>8} {'ideal_rec':>10}")
    for label in ORDER:
        cov, ml = buckets[label]
        lo, hi = BUCKET_EDGES[label]
        d = math.sqrt(max(lo, 1) * hi)
        print(f"{label:>8} {cov*100:8.3f}% {ml:9.1f} {d/2**20:8.2f}M "
              f"{survive(d,TBITS):8.4f} {cov*(1-survive(d,TBITS))*100:9.4f}%")

    need_cov = (CUBRIM_RATIO - XZ_RATIO) * 8 / (C - F)
    print(f"\ncoverage that would CLOSE the gap: {need_cov*100:.2f}% recovered "
          f"= {need_cov/(1-survive(N_BYTES,TBITS))*100:.1f}% raw at whole-file distance")
    print(f"measured >16MiB coverage: {buckets['>16M'][0]*100:.3f}%  "
          f"-> short by {need_cov/(1-survive(N_BYTES,TBITS))/buckets['>16M'][0]:.0f}x\n")

    for lever in ("ideal", "tbits30"):
        rec = recoverable(buckets, lever=lever)
        opt, hon = bounds(rec)
        name = "ideal (eviction-free)" if lever == "ideal" else "TBITS_MAX 27->30"
        print(f"{name:22} rec_cov={rec*100:7.4f}%  "
              f"optimistic {opt/8*N_BYTES:+8,.0f} B ({opt/8*N_BYTES/GAP_B*100:+6.2f}% of gap)  "
              f"branch-honest {hon/8*N_BYTES:+9,.0f} B")

    print("\nsensitivity — far buckets extend 3-5x longer, so anchor-fraction under-states their\n"
          "byte coverage. Verdict must survive correcting for that:")
    for tag, kw in (("raw anchor-fraction", {}),
                    ("ext-len weighted", {"weighted": True}),
                    ("ext-len weighted x2", {"weighted": True, "factor": 2.0})):
        rec = recoverable(buckets, **kw)
        opt, hon = bounds(rec)
        print(f"  {tag:22} rec_cov={rec*100:7.4f}%  optimistic {opt/8*N_BYTES:+8,.0f} B "
              f"({opt/8*N_BYTES/GAP_B*100:+6.2f}% of gap)  branch-honest {hon/8*N_BYTES:+9,.0f} B")

    cov16 = buckets[">16M"][0] * 100
    rec_t30 = recoverable(buckets, lever="tbits30")
    opt_t30 = bounds(rec_t30)[0] / 8 * N_BYTES / GAP_B * 100
    print("\nPREREGISTERED PREDICTIONS")
    print(f"  P1 cov>16MiB < 10%      (refute >=42.0%): measured {cov16:.3f}%  -> "
          f"{'HOLDS' if cov16 < 10 else 'REFUTED'}")
    print(f"  P2 t30 recovers < 20%   (refute >=20%)  : measured {opt_t30:.2f}%  -> "
          f"{'HOLDS' if opt_t30 < 20 else 'REFUTED'}")
    print(f"  P3 cov>16MiB > 1.469%   (refute <=)     : measured {cov16:.3f}%  -> "
          f"{'HOLDS' if cov16 > 1.469 else 'REFUTED'}")


if __name__ == "__main__":
    main()
