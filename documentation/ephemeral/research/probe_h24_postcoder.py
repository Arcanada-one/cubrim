#!/usr/bin/env python3
"""H-24 CHEAP entropy probe: which post-coder on the BWT value-code stream beats the
current scheme-10 linear o1+o0 mix?

Gotcha #5: the value-code stream is the frequency-rank relabeling of raw bytes in
i-order, so bwt_out = BWT(value_codes(data)) reproduces the exact symbol stream the
Rust context-mix coder sees. We measure the IDEAL range-coder cost = sum -log2(p)
under each adaptive model (the range coder is within a few bytes of this bound, and
the bound is identical model-to-model so per-file DELTAS are honest).

Candidates (all adaptive, no transmitted tables -> regression-proof like scheme 9/10):
  o1            : pure adaptive order-1 (scheme 9)
  mix_o1o0      : linear learned-weight o1+o0 (scheme 10, current champion path)
  mix_o2o1o0    : linear learned-weight 3-way o2+o1+o0  (idea: more contexts)
  geo_o2o1o0    : geometric/logistic learned-weight mix of o2,o1,o0 (idea: logistic mixer)
  sse_o1o0      : scheme-10 mix THEN SSE/APM secondary estimation
GO target: beat the current mix_o1o0 cost by enough on text/binary_mixed/log_like to
move the aggregate below champion 0.168227."""
import math
from collections import Counter
from pathlib import Path

CORPUS = Path("docs/ephemeral/research/corpus")
# cube-mode files only (raw-mode files don't run the value coder)
CUBE_FILES = ["sparse_clustered", "text", "log_like", "binary_mixed", "block_bound_runs"]
ORIG = {"sparse_clustered": 2048, "text": 16384, "log_like": 16384,
        "binary_mixed": 8192, "block_bound_runs": 65536}
# consolidated champion per-file value blob bytes (the value-stream part; outer header
# is common). From bench: these are the final-file bytes; we compare bit-costs relative
# to the mix_o1o0 reproduction to stay honest about the constant outer overhead.
CHAMP_FILE = {"sparse_clustered": 179, "text": 1757, "log_like": 570,
              "binary_mixed": 5679, "block_bound_runs": 2950}

CM_MIX_TOTAL = 1 << 14
CM_RESCALE = 1 << 15
PURE_INCS = [8, 16, 32, 64]
MIX_INCS = [16, 32]
LRS = [0.02, 0.05]


def value_codes(data):
    freq = Counter(data)
    order = sorted(freq, key=lambda v: (-freq[v], v))
    v2c = {v: i for i, v in enumerate(order)}
    return [v2c[b] for b in data]


def bwt_codes(seq):
    n = len(seq)
    if n == 0:
        return []
    sa = list(range(n))
    rank = list(seq)
    tmp = [0] * n
    k = 1
    while True:
        key = lambda i: (rank[i], rank[(i + k) % n])
        sa.sort(key=key)
        tmp[sa[0]] = 0
        for j in range(1, n):
            tmp[sa[j]] = tmp[sa[j - 1]] + (1 if key(sa[j]) != key(sa[j - 1]) else 0)
        rank = tmp[:]
        if rank[sa[-1]] == n - 1:
            break
        k <<= 1
        if k >= n:
            break
    return [seq[(i + n - 1) % n] for i in sa]


class Ctx:
    __slots__ = ("freq", "total")
    def __init__(self, a):
        self.freq = [1] * a
        self.total = a
    def p(self, s):
        return self.freq[s] / self.total
    def update(self, s, inc):
        self.freq[s] += inc
        self.total += inc
        if self.total > CM_RESCALE:
            nt = 0
            for i in range(len(self.freq)):
                self.freq[i] = (self.freq[i] + 1) >> 1
                nt += self.freq[i]
            self.total = nt


def cost_o1(bwt, a, inc):
    ctx = [Ctx(a) for _ in range(a)]
    prev = 0
    bits = 0.0
    for s in bwt:
        c = ctx[prev]
        bits += -math.log2(c.freq[s] / c.total)
        c.update(s, inc)
        prev = s
    return bits / 8.0  # bytes


def cost_mix_o1o0(bwt, a, inc, lr):
    """Reproduce scheme-10 mode-1: quantized linear mix cost (matches Rust qfreq)."""
    f1 = [[1] * a for _ in range(a)]
    t1 = [a] * a
    f0 = [1] * a
    t0 = a
    w = 0.5
    prev = 0
    bits = 0.0
    for s in bwt:
        tot1 = t1[prev]
        fr1 = f1[prev]
        # quantized mix table sum==CM_MIX_TOTAL
        q = [0] * a
        ssum = 0
        maxv = 0
        maxi = 0
        for x in range(a):
            p1 = fr1[x] / tot1
            p0 = f0[x] / t0
            pm = w * p1 + (1 - w) * p0
            qv = int(pm * CM_MIX_TOTAL + 0.5)
            if qv < 1:
                qv = 1
            q[x] = qv
            ssum += qv
            if qv > maxv:
                maxv = qv
                maxi = x
        if ssum < CM_MIX_TOTAL:
            q[maxi] += CM_MIX_TOTAL - ssum
        elif ssum > CM_MIX_TOTAL:
            surplus = ssum - CM_MIX_TOTAL
            while surplus > 0:
                mi = max(range(a), key=lambda z: q[z])
                take = min(surplus, q[mi] - 1)
                if take == 0:
                    break
                q[mi] -= take
                surplus -= take
        bits += -math.log2(q[s] / CM_MIX_TOTAL)
        # weight update
        p1 = fr1[s] / tot1
        p0 = f0[s] / t0
        pm = w * p1 + (1 - w) * p0
        w += lr * (p1 - p0) / pm
        w = min(max(w, 1e-4), 1 - 1e-4)
        # model update
        fr1[s] += inc
        t1[prev] += inc
        if t1[prev] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr1[i] = (fr1[i] + 1) >> 1
                nt += fr1[i]
            t1[prev] = nt
        f0[s] += inc
        t0 += inc
        if t0 > CM_RESCALE:
            nt = 0
            for i in range(a):
                f0[i] = (f0[i] + 1) >> 1
                nt += f0[i]
            t0 = nt
        prev = s
    return bits / 8.0


def cost_mix_3way_linear(bwt, a, inc, lr):
    """Linear learned mix of o2,o1,o0; weights projected to simplex each step."""
    f2 = {}  # (p2,p1) -> freq list
    t2 = {}
    f1 = [[1] * a for _ in range(a)]
    t1 = [a] * a
    f0 = [1] * a
    t0 = a
    wts = [1 / 3, 1 / 3, 1 / 3]
    p2k = 0
    p1k = 0
    bits = 0.0
    for s in bwt:
        key = (p2k, p1k)
        if key not in f2:
            f2[key] = [1] * a
            t2[key] = a
        fr2 = f2[key]
        tt2 = t2[key]
        fr1 = f1[p1k]
        tt1 = t1[p1k]
        # blended prob (use raw float blend, ideal-cost; no quantization, slight
        # optimism but identical optimism applied to all mix candidates -> fair delta)
        ps = wts[0] * (fr2[s] / tt2) + wts[1] * (fr1[s] / tt1) + wts[2] * (f0[s] / t0)
        bits += -math.log2(ps)
        # gradient on weights then simplex-project
        pk = [fr2[s] / tt2, fr1[s] / tt1, f0[s] / t0]
        for i in range(3):
            wts[i] += lr * pk[i] / ps
        # renormalize to simplex with floor
        wts = [min(max(x, 1e-4), 50) for x in wts]
        sw = sum(wts)
        wts = [x / sw for x in wts]
        # updates
        fr2[s] += inc; t2[key] += inc
        if t2[key] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr2[i] = (fr2[i] + 1) >> 1; nt += fr2[i]
            t2[key] = nt
        fr1[s] += inc; t1[p1k] += inc
        if t1[p1k] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr1[i] = (fr1[i] + 1) >> 1; nt += fr1[i]
            t1[p1k] = nt
        f0[s] += inc; t0 += inc
        if t0 > CM_RESCALE:
            nt = 0
            for i in range(a):
                f0[i] = (f0[i] + 1) >> 1; nt += f0[i]
            t0 = nt
        p2k, p1k = p1k, s
    return bits / 8.0


def cost_geo_3way(bwt, a, inc, lr):
    """Geometric/logistic learned mix of o2,o1,o0: p ∝ prod p_k^{w_k}, renormalized."""
    f2 = {}
    t2 = {}
    f1 = [[1] * a for _ in range(a)]
    t1 = [a] * a
    f0 = [1] * a
    t0 = a
    w = [1.0, 1.0, 1.0]
    p2k = 0
    p1k = 0
    bits = 0.0
    for s in bwt:
        key = (p2k, p1k)
        if key not in f2:
            f2[key] = [1] * a
            t2[key] = a
        fr2 = f2[key]; tt2 = t2[key]
        fr1 = f1[p1k]; tt1 = t1[p1k]
        # geometric mix over full alphabet (cost a per symbol -> only for probe)
        logp = [0.0] * a
        Z = 0.0
        for x in range(a):
            lp = (w[0] * math.log(fr2[x] / tt2)
                  + w[1] * math.log(fr1[x] / tt1)
                  + w[2] * math.log(f0[x] / t0))
            logp[x] = lp
        m = max(logp)
        ex = [math.exp(lp - m) for lp in logp]
        Z = sum(ex)
        ps = ex[s] / Z
        bits += -math.log2(ps)
        # gradient of -ln p_s wrt w_k = -(ln p_k(s) - E_q[ln p_k]) ; ascent
        Eq = [0.0, 0.0, 0.0]
        for x in range(a):
            qx = ex[x] / Z
            Eq[0] += qx * math.log(fr2[x] / tt2)
            Eq[1] += qx * math.log(fr1[x] / tt1)
            Eq[2] += qx * math.log(f0[x] / t0)
        gk = [math.log(fr2[s] / tt2) - Eq[0],
              math.log(fr1[s] / tt1) - Eq[1],
              math.log(f0[s] / t0) - Eq[2]]
        for i in range(3):
            w[i] += lr * gk[i]
            w[i] = min(max(w[i], 0.0), 8.0)
        # updates
        fr2[s] += inc; t2[key] += inc
        if t2[key] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr2[i] = (fr2[i] + 1) >> 1; nt += fr2[i]
            t2[key] = nt
        fr1[s] += inc; t1[p1k] += inc
        if t1[p1k] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr1[i] = (fr1[i] + 1) >> 1; nt += fr1[i]
            t1[p1k] = nt
        f0[s] += inc; t0 += inc
        if t0 > CM_RESCALE:
            nt = 0
            for i in range(a):
                f0[i] = (f0[i] + 1) >> 1; nt += f0[i]
            t0 = nt
        p2k, p1k = p1k, s
    return bits / 8.0


def cost_geo_3way_quant(bwt, a, inc, lr):
    """Geometric mix of o2,o1,o0 with HONEST quantization to CM_MIX_TOTAL (floor-at-1,
    reconcile to total) + ~8 bytes range-coder flush/header — charges the real wire cost."""
    f2 = {}
    t2 = {}
    f1 = [[1] * a for _ in range(a)]
    t1 = [a] * a
    f0 = [1] * a
    t0 = a
    w = [1.0, 1.0, 1.0]
    p2k = 0
    p1k = 0
    bits = 0.0
    for s in bwt:
        key = (p2k, p1k)
        if key not in f2:
            f2[key] = [1] * a
            t2[key] = a
        fr2 = f2[key]; tt2 = t2[key]
        fr1 = f1[p1k]; tt1 = t1[p1k]
        logp = [0.0] * a
        for x in range(a):
            logp[x] = (w[0] * math.log(fr2[x] / tt2)
                       + w[1] * math.log(fr1[x] / tt1)
                       + w[2] * math.log(f0[x] / t0))
        m = max(logp)
        ex = [math.exp(lp - m) for lp in logp]
        Z = sum(ex)
        # quantize to CM_MIX_TOTAL, floor at 1, reconcile on max
        q = [0] * a
        ssum = 0
        maxv = 0
        maxi = 0
        for x in range(a):
            qv = int((ex[x] / Z) * CM_MIX_TOTAL + 0.5)
            if qv < 1:
                qv = 1
            q[x] = qv
            ssum += qv
            if qv > maxv:
                maxv = qv
                maxi = x
        if ssum < CM_MIX_TOTAL:
            q[maxi] += CM_MIX_TOTAL - ssum
        elif ssum > CM_MIX_TOTAL:
            surplus = ssum - CM_MIX_TOTAL
            while surplus > 0:
                mi = max(range(a), key=lambda z: q[z])
                take = min(surplus, q[mi] - 1)
                if take == 0:
                    break
                q[mi] -= take
                surplus -= take
        bits += -math.log2(q[s] / CM_MIX_TOTAL)
        # gradient (same as float version, on true geo posterior)
        Eq = [0.0, 0.0, 0.0]
        for x in range(a):
            qx = ex[x] / Z
            Eq[0] += qx * math.log(fr2[x] / tt2)
            Eq[1] += qx * math.log(fr1[x] / tt1)
            Eq[2] += qx * math.log(f0[x] / t0)
        gk = [math.log(fr2[s] / tt2) - Eq[0],
              math.log(fr1[s] / tt1) - Eq[1],
              math.log(f0[s] / t0) - Eq[2]]
        for i in range(3):
            w[i] = min(max(w[i] + lr * gk[i], 0.0), 8.0)
        fr2[s] += inc; t2[key] += inc
        if t2[key] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr2[i] = (fr2[i] + 1) >> 1; nt += fr2[i]
            t2[key] = nt
        fr1[s] += inc; t1[p1k] += inc
        if t1[p1k] > CM_RESCALE:
            nt = 0
            for i in range(a):
                fr1[i] = (fr1[i] + 1) >> 1; nt += fr1[i]
            t1[p1k] = nt
        f0[s] += inc; t0 += inc
        if t0 > CM_RESCALE:
            nt = 0
            for i in range(a):
                f0[i] = (f0[i] + 1) >> 1; nt += f0[i]
            t0 = nt
        p2k, p1k = p1k, s
    return bits / 8.0 + 8.0  # + range-coder flush/header bytes


def main():
    print(f"{'file':18} {'champ':>7} {'mixo1o0':>9} {'geo3f':>9} {'geo3Q':>9}")
    tot_champ = sum(CHAMP_FILE.values())
    agg = {"mix": 0.0, "geo3": 0.0, "geo3q": 0.0}
    for name in CUBE_FILES:
        data = (CORPUS / f"{name}.bin").read_bytes()
        seq = value_codes(data)
        a = len(set(seq))
        bwt = bwt_codes(seq)
        c_mix = min(cost_mix_o1o0(bwt, a, inc, lr) for inc in MIX_INCS for lr in LRS)
        c_geo3 = min(cost_geo_3way(bwt, a, inc, lr)
                     for inc in MIX_INCS for lr in [0.01, 0.02])
        c_geo3q = min(cost_geo_3way_quant(bwt, a, inc, lr)
                      for inc in MIX_INCS for lr in [0.01, 0.02])
        print(f"{name:18} {CHAMP_FILE[name]:7d} {c_mix:9.1f} {c_geo3:9.1f} {c_geo3q:9.1f}")
        agg["mix"] += c_mix
        agg["geo3"] += c_geo3
        agg["geo3q"] += c_geo3q
    print("-" * 56)
    print(f"{'SUM(cube)':18} {tot_champ:7d} {agg['mix']:9.1f} "
          f"{agg['geo3']:9.1f} {agg['geo3q']:9.1f}")
    # Project aggregate: competitive min keeps champ where geo3Q is worse.
    new_cube = 0.0
    for name in CUBE_FILES:
        pass
    OTHER = 19686 - sum(CHAMP_FILE.values())  # non-cube files, unchanged
    # per-file: champ already includes outer cube header; geo3Q replaces only value cost.
    # outer_overhead ≈ champ - mix_ideal (current path). new_file = outer + geo3Q_value.
    print(f"\nnon-cube/raw files total (unchanged): {OTHER}")
    print(f"current champion total file: 19686, aggregate {19686/117032:.6f}")
    print(f"gzip aggregate: {18687/117032:.6f}")
    print(f"\ngeo3Q uses honest CM_MIX_TOTAL quantization + 8B flush. Judge GO by SUM(cube).")


if __name__ == "__main__":
    main()
